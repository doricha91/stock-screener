import itertools
import pandas as pd
import sqlite3
import data_manager
import strategy
import indicator
from backtesting import engine, metrics
from tqdm import tqdm
import config

# ==========================================
# 1. 실험할 파라미터 그리드 (핵심 변수)
# ==========================================
PARAM_GRID = {
    'entry_period': [20, 50, 60],  # 진입: 한달 vs 분기
    'exit_period': [10, 20],  # 청산: 2주 vs 한달
    'turtle_weight': [2.0, 3.0],  # 가중치
    'score_threshold': [2.0, 3.0]  # 합격점
}

# 테스트할 대표 우량주 (섹터별 대장주)
TEST_TICKERS = ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'JPM', 'LLY']


# ==========================================
# 2. 동적 파라미터 적용 앙상블 함수
# ==========================================
def run_dynamic_ensemble_backtest(df, params):
    """
    params 딕셔너리에 있는 설정값(기간 등)을 적용하여 백테스트를 수행합니다.
    """
    # 1. 지표 계산 (파라미터 적용)
    # config.py의 기본값 대신, 실험용 params를 우선 사용합니다.
    context = params.copy()

    # 지표 추가 (indicator.py 함수들이 context의 변수를 쓰도록 되어있음)
    df = indicator.add_turtle_indicators(df, context)
    df = indicator.add_rsi_indicators(df, context)
    df = indicator.add_sma_indicators(df, context)
    df = indicator.add_bollinger_band_indicators(df, context)
    df = indicator.add_macd_indicators(df, context)
    df = indicator.add_bbs_indicators(df, context)
    df = indicator.add_dema_indicators(df, context)

    # 2. 전략 신호 생성
    df = strategy.apply_ensemble_strategy(df, context)

    # 3. 앙상블 점수 계산
    # 가중치 설정 (실험값 적용)
    weights = {
        'turtle': context['turtle_weight'],
        'rsi': 1.0, 'sma': 1.0, 'bbands': 1.0,
        'macd': 1.0, 'bbs': 1.5, 'dema': 1.0
    }

    df['ensemble_score'] = 0.0
    for name, weight in weights.items():
        col = f'signal_{name}'
        if col in df.columns:
            df['ensemble_score'] += df[col].apply(lambda x: weight if x == 1 else 0)

    # 4. 최종 매매 신호
    df['signal'] = 0
    df['position'] = 0
    current_pos = 0
    threshold = context['score_threshold']

    # 벡터화 대신 루프 사용 (터틀 청산 로직 반영을 위해)
    # exit_low는 위에서 계산된(params가 적용된) 값을 사용함
    for i in range(1, len(df)):
        score = df['ensemble_score'].iloc[i]
        price = df['close'].iloc[i]
        exit_price = df['exit_low'].iloc[i]

        # Buy Logic
        if current_pos == 0 and score >= threshold:
            df.at[df.index[i], 'signal'] = 1
            current_pos = 1
        # Sell Logic (터틀 청산 or 손절)
        elif current_pos == 1 and price < exit_price:
            df.at[df.index[i], 'signal'] = -1
            current_pos = 0

        df.at[df.index[i], 'position'] = current_pos

    # 5. 엔진 실행
    # (리스크 관리를 위해 strategy_name='turtle'로 설정하여 ATR 손절 기능 활성화)
    context['strategy_name'] = 'turtle'
    portfolio, trades = engine.run_backtest(df, 10000.0, context)

    # 6. 결과 통계 반환
    return metrics.calculate_metrics(portfolio, trades, df, 10000.0)


# ==========================================
# 3. 메인 실행기
# ==========================================
def main():
    print(f"🔬 [Final Optimization] 전략의 최적 변수를 찾습니다...")

    # 파라미터 조합 생성
    keys, values = zip(*PARAM_GRID.items())
    combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]

    print(
        f"📊 테스트할 조합: {len(combinations)}개 x 종목 {len(TEST_TICKERS)}개 = 총 {len(combinations) * len(TEST_TICKERS)}회 시뮬레이션")

    results = []

    # 종목별 루프
    for symbol in tqdm(TEST_TICKERS, desc="Processing Tickers"):
        # 데이터 로드 (2018년부터 현재까지 - 충분한 기간)
        df_raw = data_manager.get_price_data(symbol, start_date='2018-01-01')
        if df_raw is None or len(df_raw) < 200: continue

        # 파라미터 조합별 루프
        for params in combinations:
            try:
                stats = run_dynamic_ensemble_backtest(df_raw.copy(), params)

                if stats:
                    res = {
                        'Symbol': symbol,
                        'Entry': params['entry_period'],
                        'Exit': params['exit_period'],
                        'Weight': params['turtle_weight'],
                        'Threshold': params['score_threshold'],
                        'Return(%)': round(stats['total_return'], 2),
                        'MDD(%)': round(stats['max_drawdown'], 2),
                        'Trades': stats['total_trades'],
                        'WinRate(%)': round(stats.get('win_rate', 0) * 100, 1),
                        'ProfitFactor': round(stats.get('profit_factor', 0), 2)
                    }
                    results.append(res)
            except Exception as e:
                # print(f"Error: {e}")
                continue

    # 결과 분석 및 출력
    if not results:
        print("결과가 없습니다.")
        return

    df_res = pd.DataFrame(results)

    # DB 저장
    conn = sqlite3.connect("backtest_log.db")
    df_res.to_sql('final_optimization_results', conn, if_exists='replace', index=False)
    conn.close()

    print("\n🏆 [최적 파라미터 분석 결과]")

    # 파라미터별 평균 수익률 집계
    # (종목 상관없이 어떤 설정이 평균적으로 가장 좋았나?)
    group_cols = ['Entry', 'Exit', 'Weight', 'Threshold']
    summary = df_res.groupby(group_cols)[['Return(%)', 'MDD(%)', 'Trades']].mean()
    summary = summary.sort_values(by='Return(%)', ascending=False)

    print(summary.head(10).to_string())

    print("\n💡 Tip: 가장 상단에 있는 설정값(Entry, Exit 등)을 config.py에 반영하세요.")


if __name__ == "__main__":
    main()
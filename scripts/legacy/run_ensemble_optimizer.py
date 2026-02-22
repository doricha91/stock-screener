import itertools
import pandas as pd
import sqlite3
from screener import data_manager, strategy, indicator
from backtesting import engine, metrics
from tqdm import tqdm


# [재사용 1] 파라미터 조합 생성기
def generate_param_combinations(grid):
    keys, values = zip(*grid.items())
    combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
    return combinations


# [재사용 2] DB 저장 함수 (테이블명만 변경)
def save_result_to_db(result_data):
    conn = sqlite3.connect("../../outputs/backtest_log.db")
    df_result = pd.DataFrame([result_data])
    try:
        df_result.to_sql('ensemble_optimization_log', conn, if_exists='append', index=False)
    except Exception as e:
        print(f"DB 저장 오류: {e}")
    finally:
        conn.close()


# [핵심] 앙상블 전용 신호 생성기 (기존 run_optimization과 다른 점)
def generate_ensemble_signals(df, context):
    # 1. 지표 계산 (모든 전략 지표 추가)
    # (실제로는 indicator.py의 함수들을 호출해야 함 - 간소화 예시)
    df = indicator.add_turtle_indicators(df, context)
    df = indicator.add_rsi_indicators(df, context)
    df = indicator.add_sma_indicators(df, context)
    df = indicator.add_bollinger_band_indicators(df, context)
    df = indicator.add_macd_indicators(df, context)
    df = indicator.add_bbs_indicators(df, context)
    df = indicator.add_dema_indicators(df, context)

    # 2. 앙상블 전략 실행
    df = strategy.apply_ensemble_strategy(df, context)

    # 3. 점수 합산 및 신호 결정 (그리드 서치 대상)
    threshold = context.get('score_threshold', 3.0)
    turtle_weight = context.get('turtle_weight', 2.0)  # 가중치 실험 가능

    # 가중치 설정 (실험 대상인 turtle_weight 적용)
    weights = {
        'turtle': turtle_weight, 'rsi': 1.0, 'sma': 1.0,
        'bbands': 1.0, 'macd': 1.0, 'bbs': 1.5, 'dema': 1.0
    }

    df['ensemble_score'] = 0.0
    for name, weight in weights.items():
        col = f'signal_{name}'
        if col in df.columns:
            df['ensemble_score'] += df[col].apply(lambda x: weight if x == 1 else 0)

    # 매매 신호 생성
    df['signal'] = 0
    df['position'] = 0
    current_pos = 0

    for i in range(1, len(df)):
        score = df['ensemble_score'].iloc[i]
        # Buy: 점수가 기준점 이상
        if current_pos == 0 and score >= threshold:
            df.at[df.index[i], 'signal'] = 1
            current_pos = 1
        # Sell: 터틀 청산 (예시)
        elif current_pos == 1 and df['close'].iloc[i] < df['exit_low'].iloc[i]:
            df.at[df.index[i], 'signal'] = -1
            current_pos = 0
        df.at[df.index[i], 'position'] = current_pos

    return df


# [재사용 3] 무소음 백테스트 실행기
def run_silent_ensemble_test(df, context):
    # 앙상블 신호 생성
    df_signals = generate_ensemble_signals(df.copy(), context)

    # 엔진 실행 (터틀 방식의 리스크 관리 사용 가정)
    context['strategy_name'] = 'turtle'
    portfolio, trades = engine.run_backtest(df_signals, 10000.0, context)

    # 통계 계산
    return metrics.calculate_metrics(portfolio, trades, df_signals, 10000.0)


# --- 메인 실행 ---
if __name__ == "__main__":

    # 1. 실험할 파라미터 그리드 (여기가 핵심!)
    # 점수 기준을 2.0부터 3.0까지, 터틀 가중치를 1.0과 2.0으로 바꿔가며 테스트
    PARAM_GRID = {
        'score_threshold': [2.0, 2.5, 3.0],
        'turtle_weight': [1.0, 2.0]
    }

    # 2. 테스트할 종목 (대표 종목 선정)
    TEST_TICKERS = ['AAPL', 'MSFT', 'TSLA', 'NVDA']

    combinations = generate_param_combinations(PARAM_GRID)
    print(f"🔥 총 {len(combinations)}가지 조합에 대해 테스트를 시작합니다.")

    for symbol in tqdm(TEST_TICKERS):
        df_raw = data_manager.get_price_data(symbol, start_date='2023-01-01')
        if df_raw is None or len(df_raw) < 100: continue

        for params in combinations:
            context = {**params, 'initial_capital': 10000.0}

            # 백테스트 실행
            stats = run_silent_ensemble_test(df_raw, context)

            if stats:
                # 결과 저장
                result = {
                    'Symbol': symbol,
                    'Threshold': params['score_threshold'],
                    'Turtle_Weight': params['turtle_weight'],
                    'Trades': stats['total_trades'],
                    'Return(%)': round(stats['total_return'], 2),
                    'MDD(%)': round(stats['max_drawdown'], 2),
                    'WinRate(%)': round(stats.get('win_rate', 0) * 100, 1)
                }
                save_result_to_db(result)

    print("\n✅ 실험 완료! 'backtest_log.db'의 'ensemble_optimization_log' 테이블을 확인하세요.")
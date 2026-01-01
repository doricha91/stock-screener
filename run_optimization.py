import itertools
import pandas as pd
import csv
import os
import sqlite3
from datetime import datetime
import config
import data_manager
import indicator
import strategy
from market_analyzer import analyze_market_status
from backtesting import engine, metrics

# --- 전략 매핑 ---
INDICATOR_FUNCTIONS = {
    'turtle': indicator.add_turtle_indicators,
    'rsi': indicator.add_rsi_indicators,
    'sma': indicator.add_sma_indicators,
    'bbands': indicator.add_bollinger_band_indicators,
    'macd': indicator.add_macd_indicators,
    'bbs': indicator.add_bbs_indicators,
    'dema': indicator.add_dema_indicators,
}

SIGNAL_FUNCTIONS = {
    'turtle': strategy.generate_turtle_signals,
    'rsi': strategy.generate_rsi_signals,
    'sma': strategy.generate_sma_signals,
    'bbands': strategy.generate_bbands_signals,
    'macd': strategy.generate_macd_signals,
    'bbs': strategy.generate_bbs_signals,
    'dema': strategy.generate_dema_signals,
}


def generate_param_combinations(grid):
    """
    config.py의 그리드 딕셔너리를 입력받아,
    가능한 모든 파라미터 조합(List of Dicts)을 생성합니다.
    """
    keys, values = zip(*grid.items())
    combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
    return combinations


def _run_silent_backtest(df_target, context):
    """
    로그 출력 없이 백테스트를 수행하고 결과(stats)만 반환하는 내부 함수
    """
    strategy_name = context.get('strategy_name')

    # 1. 지표 계산
    indicator_func = INDICATOR_FUNCTIONS[strategy_name]
    df_indicators = indicator_func(df_target.copy(), context)
    if df_indicators is None: return None

    # 2. 신호 생성
    signal_func = SIGNAL_FUNCTIONS[strategy_name]
    df_signals = signal_func(df_indicators, context)
    if df_signals is None: return None

    # 3. 엔진 실행
    initial_capital = context.get('initial_capital', 10000.0)
    portfolio_history, trade_history = engine.run_backtest(df_signals, initial_capital, context)

    # 4. 통계 계산
    stats = metrics.calculate_metrics(portfolio_history, trade_history, df_signals, initial_capital)
    return stats


def save_optimization_result(result_data):
    """
    결과 딕셔너리(result_data)를 DataFrame으로 변환 후,
    SQLite DB의 'optimization_log' 테이블에 저장합니다.
    """
    # 1. 딕셔너리를 리스트로 감싸서 DataFrame 생성
    df_result = pd.DataFrame([result_data])

    # 2. DB 연결
    conn = sqlite3.connect(config.BACKTEST_DB_NAME)

    try:
        # 3. DB에 저장 (append 모드)
        df_result.to_sql('optimization_log', conn, if_exists='append', index=False)
        print(f"   💾 결과가 DB('{config.BACKTEST_DB_NAME}')에 저장되었습니다.")

    except Exception as e:
        print(f"   ⚠️ DB 저장 중 오류 발생: {e}")

    finally:
        conn.close()


def run_optimization(strategy_name, target_regime, target_symbol='SPY'):
    """
    특정 종목(target_symbol) + 시장(target_regime) + 전략(strategy_name) 조합을 최적화합니다.
    """

    print(f"\n🚀 [최적화 시작] 종목: {target_symbol} | 전략: {strategy_name} | 시장: {target_regime}")

    # 1. 데이터 로드
    df_raw = data_manager.get_stock_data(target_symbol, output_size='full')

    if df_raw is None or df_raw.empty:
        print(f"   ❌ 오류: {target_symbol} 데이터를 불러올 수 없습니다.")
        return

    # 시장 상태 분석
    df_regime = analyze_market_status(df_raw)

    # 2. 데이터 분할
    in_sample_mask = (df_regime.index >= config.IN_SAMPLE_START) & (df_regime.index <= config.IN_SAMPLE_END)
    out_sample_mask = (df_regime.index >= config.OUT_OF_SAMPLE_START) & (df_regime.index <= config.OUT_OF_SAMPLE_END)

    regime_mask = df_regime['market_regime'] == target_regime

    df_in = df_regime[in_sample_mask & regime_mask].copy()
    df_out = df_regime[out_sample_mask & regime_mask].copy()

    in_period_str = f"{config.IN_SAMPLE_START}~{config.IN_SAMPLE_END}"
    out_period_str = f"{config.OUT_OF_SAMPLE_START}~{config.OUT_OF_SAMPLE_END}"

    print(f"   - 훈련 데이터(In): {len(df_in)}일")
    print(f"   - 검증 데이터(Out): {len(df_out)}일")

    if len(df_in) < 30:
        print("   ⚠️ 훈련 데이터 부족으로 스킵.")
        return

    # 3. 그리드 서치
    param_grid = config.STRATEGY_GRID_MAP.get(strategy_name)
    if not param_grid:
        print(f"   ❌ 설정 오류: {strategy_name} 파라미터 그리드 없음.")
        return

    combinations = generate_param_combinations(param_grid)

    best_score = -999
    best_params = None
    best_stats = None

    # In-Sample 테스트
    for params in combinations:
        context = {
            'strategy_name': strategy_name,
            'initial_capital': 10000.0,
            'risk_percent': config.RISK_PER_TRADE_PERCENT,
            'stop_loss_atr': config.STOP_LOSS_ATR_MULTIPLIER,
            'atr_period': config.ATR_PERIOD,
            **params
        }

        stats = _run_silent_backtest(df_in, context)

        if stats:
            score = stats['total_return']  # 평가 기준: 수익률

            if score > best_score:
                best_score = score
                best_params = params
                best_stats = stats

    if best_stats is None:
        print("   ⚠️ 유효한 거래가 발생하지 않음.")
        return

    # 4. Out-of-Sample 검증
    context_out = {
        'strategy_name': strategy_name,
        'initial_capital': 10000.0,
        **best_params
    }

    oos_stats = _run_silent_backtest(df_out, context_out)

    if oos_stats:
        # --- [ 데이터 기록 강화 ] ---
        # metrics.py에서 계산된 값들을 가져옵니다.

        result_row = {
            'Run_Time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'Symbol': target_symbol,
            'Target_Regime': target_regime,
            'Strategy': strategy_name,
            'Best_Params': str(best_params),

            # --- In-Sample (훈련) ---
            'In_Period': in_period_str,
            'In_Return(%)': round(best_stats['total_return'], 2),
            'In_WinRate(%)': round(best_stats.get('win_rate', 0) * 100, 1),
            'In_ProfitFactor': round(best_stats.get('profit_factor', 0), 2),
            'In_SQN': round(best_stats.get('sqn', 0), 2),  # [추가]
            'In_Exposure(%)': round(best_stats.get('exposure_pct', 0), 1),  # [추가]
            'In_Trades': best_stats['total_trades'],

            # --- Out-of-Sample (검증) ---
            'Out_Period': out_period_str,
            'Out_Return(%)': round(oos_stats['total_return'], 2),
            'Out_BH_Return(%)': round(oos_stats['buy_and_hold_return'], 2),
            'Out_WinRate(%)': round(oos_stats.get('win_rate', 0) * 100, 1),
            'Out_ProfitFactor': round(oos_stats.get('profit_factor', 0), 2),
            'Out_SQN': round(oos_stats.get('sqn', 0), 2),  # [추가]
            'Out_Exposure(%)': round(oos_stats.get('exposure_pct', 0), 1),  # [추가]
            'Out_Trades': oos_stats['total_trades'],
            'Out_MDD(%)': round(oos_stats['max_drawdown'], 2),
        }

        # DB 저장
        save_optimization_result(result_row)

        # 콘솔 출력
        print(f"   🏆 검증 수익률: {oos_stats['total_return']:.2f}% (SQN: {oos_stats.get('sqn', 0):.2f})")

    else:
        print("   ⚠️ 검증 데이터 부족으로 테스트 불가.")


if __name__ == "__main__":

    # 1. 타겟 설정 (원하는 만큼 리스트에 넣으세요)
    TARGET_REGIMES = ['BEAR_TREND', 'BULL_TREND', 'BULL_SIDEWAYS', 'BEAR_SIDEWAYS']
    TARGET_STRATEGIES = ['macd', 'dema', 'bbs', 'sma', 'turtle']
    TARGET_SYMBOLS = ['TSLA', 'TQQQ', 'SOXL']  # [수정] 여기에 원하는 종목 추가

    print(f"🔥 [배치 작업 시작] 총 {len(TARGET_REGIMES) * len(TARGET_STRATEGIES) * len(TARGET_SYMBOLS)}개의 실험을 진행합니다...\n")

    # 3중 반복문: 시장 -> 종목 -> 전략
    for regime in TARGET_REGIMES:
        print(f"==================================================")
        print(f"🌍 [시장 변경] 현재 타겟 시장: {regime}")
        print(f"==================================================")

        for symbol in TARGET_SYMBOLS:
            print(f"   target: {symbol}")

            for strategy in TARGET_STRATEGIES:
                try:
                    # [수정] target_symbol 인자를 명시적으로 전달
                    run_optimization(strategy_name=strategy, target_regime=regime, target_symbol=symbol)

                except Exception as e:
                    print(f"   ⚠️ 오류 발생 ({symbol}-{strategy}): {e}")
                    continue
            print("-" * 30)

    print("\n🎉 [모든 배치 작업 완료] 결과는 DB(backtest_log.db)를 확인하세요.")
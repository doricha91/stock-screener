import pandas as pd
import numpy as np
import data_manager
import strategy
import indicator
from backtesting import engine, metrics
from tqdm import tqdm
import config

# ==========================================
# 설정 (검증할 최종 스펙)
# ==========================================
FINAL_PARAMS = {
    'entry_period': 20,
    'exit_period': 10,
    'score_threshold': 2.0,
    'turtle_weight': 2.0,
    'initial_capital': 10000.0,
    'atr_period': 20,
    'stop_loss_atr': 2.0,
    'risk_percent': 0.02
}

# SPY, QQQ가 이제 daily_price에 있다면 여기 포함 가능
TARGET_SYMBOLS = ['SPY', 'QQQ', 'AAPL', 'MSFT', 'NVDA', 'TSLA']


# ==========================================
# 헬퍼 함수: MDD 계산기
# ==========================================
def calculate_max_drawdown(value_series):
    """
    자산 가치 시리즈(Series)를 받아 MDD(%)를 계산합니다.
    """
    if len(value_series) < 1: return 0.0

    # 누적 최대값 (Peak)
    running_max = value_series.cummax()
    # 낙폭 (Drawdown)
    drawdown = (value_series - running_max) / running_max
    # 최대 낙폭 (MDD)
    mdd = drawdown.min() * 100  # 퍼센트로 변환
    return round(mdd, 2)


# ==========================================
# 비교 로직 (수익률 + MDD 계산 추가)
# ==========================================

def calculate_buy_and_hold_stats(df, initial_capital):
    """Buy & Hold의 수익률과 MDD 계산"""
    if df.empty: return 0.0, 0.0

    # 자산 가치 변화 = (주가 / 시작주가) * 원금
    asset_values = (df['close'] / df['close'].iloc[0]) * initial_capital

    # 수익률
    total_return = ((asset_values.iloc[-1] - initial_capital) / initial_capital) * 100

    # MDD
    mdd = calculate_max_drawdown(asset_values)

    return total_return, mdd


def calculate_dca_stats(df, monthly_amount=1000):
    """월 적립식(DCA)의 수익률과 MDD 계산"""
    if df.empty: return 0.0, 0.0

    df = df.copy()
    df['year_month'] = df.index.to_period('M')

    total_invested = 0
    total_shares = 0

    # 날짜별 포트폴리오 가치를 저장할 리스트
    portfolio_values = []

    # 월별 첫 거래일 찾기 (매수일)
    # 경고 해결: include_groups=False 옵션 추가
    buy_dates = df.groupby('year_month').apply(lambda x: x.index[0], include_groups=False)
    buy_dates_set = set(buy_dates)

    for date, row in df.iterrows():
        # 매수일이면 주식 추가
        if date in buy_dates_set:
            shares_bought = monthly_amount / row['close']
            total_shares += shares_bought
            total_invested += monthly_amount

        # 매일매일의 평가금액 기록 (보유주식수 * 현재가)
        # 아직 투자가 시작 안 된 날은 0
        current_value = total_shares * row['close']
        if total_invested > 0:
            portfolio_values.append(current_value)
        else:
            portfolio_values.append(0)

    # Series로 변환
    value_series = pd.Series(portfolio_values)

    # 수익률 계산 (총평가액 - 총투자금) / 총투자금
    final_value = value_series.iloc[-1]
    if total_invested == 0: return 0.0, 0.0

    total_return = ((final_value - total_invested) / total_invested) * 100

    # MDD 계산
    mdd = calculate_max_drawdown(value_series)

    return total_return, mdd


def run_ensemble_strategy(df, params):
    """우리의 앙상블 전략 실행"""
    # (기존 로직과 동일)
    context = params.copy()

    df = indicator.add_turtle_indicators(df, context)
    df = indicator.add_rsi_indicators(df, context)
    df = indicator.add_sma_indicators(df, context)
    df = indicator.add_bollinger_band_indicators(df, context)
    df = indicator.add_macd_indicators(df, context)
    df = indicator.add_bbs_indicators(df, context)
    df = indicator.add_dema_indicators(df, context)
    df = strategy.apply_ensemble_strategy(df, context)

    weights = {'turtle': context['turtle_weight'], 'rsi': 1.0, 'sma': 1.0,
               'bbands': 1.0, 'macd': 1.0, 'bbs': 1.5, 'dema': 1.0}

    df['ensemble_score'] = 0.0
    for name, weight in weights.items():
        col = f'signal_{name}'
        if col in df.columns:
            df['ensemble_score'] += df[col].apply(lambda x: weight if x == 1 else 0)

    df['signal'] = 0
    df['position'] = 0
    current_pos = 0
    threshold = context['score_threshold']

    for i in range(1, len(df)):
        score = df['ensemble_score'].iloc[i]
        price = df['close'].iloc[i]
        exit_price = df['exit_low'].iloc[i]

        if current_pos == 0 and score >= threshold:
            df.at[df.index[i], 'signal'] = 1
            current_pos = 1
        elif current_pos == 1 and price < exit_price:
            df.at[df.index[i], 'signal'] = -1
            current_pos = 0
        df.at[df.index[i], 'position'] = current_pos

    context['strategy_name'] = 'turtle'
    portfolio, trades = engine.run_backtest(df, params['initial_capital'], context)
    stats = metrics.calculate_metrics(portfolio, trades, df, params['initial_capital'])
    return stats


# ==========================================
# 메인 실행
# ==========================================
def main():
    print(f"⚖️ [최종 검증] 전략 vs 존버 vs 적립식 (수익률 & MDD)")
    print("-" * 100)
    # 헤더 수정: MDD 컬럼 추가
    print(
        f"{'Symbol':<6} | {'Strat %':<9} {'MDD %':<7} | {'B&H %':<9} {'MDD %':<7} | {'DCA %':<9} {'MDD %':<7} | {'Win?'}")
    print("-" * 100)

    wins = 0

    for symbol in TARGET_SYMBOLS:
        df = data_manager.get_price_data(symbol, start_date='2018-01-01')
        if df is None or len(df) < 200:
            print(f"⚠️ [{symbol}] 데이터 부족")
            continue

        # 1. 전략
        strat_stats = run_ensemble_strategy(df.copy(), FINAL_PARAMS)
        strat_ret = strat_stats['total_return']
        strat_mdd = strat_stats['max_drawdown']

        # 2. B&H
        bh_ret, bh_mdd = calculate_buy_and_hold_stats(df.copy(), FINAL_PARAMS['initial_capital'])

        # 3. DCA
        dca_ret, dca_mdd = calculate_dca_stats(df.copy())

        # 승리 판단 (수익률이 B&H보다 높거나, MDD가 절반 이하면서 수익률 70% 이상 방어)
        is_win = "NO"
        if strat_ret > bh_ret:
            is_win = "YES (Alpha)"
        elif strat_mdd > (bh_mdd / 2) and strat_ret > (bh_ret * 0.7):
            is_win = "YES (Stable)"

        print(
            f"{symbol:<6} | {strat_ret:9.1f} {strat_mdd:7.1f} | {bh_ret:9.1f} {bh_mdd:7.1f} | {dca_ret:9.1f} {dca_mdd:7.1f} | {is_win}")

    print("-" * 100)


if __name__ == "__main__":
    main()
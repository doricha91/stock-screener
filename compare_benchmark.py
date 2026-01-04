import pandas as pd
import data_manager
import numpy as np

# ==========================================
# 사용자 전략 성적 (방금 나온 결과 입력)
# ==========================================
MY_STRATEGY = {
    'name': 'My Strategy (Trend)',
    'return': 111.11,
    'mdd': -35.71,
    'cagr': 9.82
}


# ==========================================
# 벤치마크 계산 함수
# ==========================================
def calculate_benchmark_stats(ticker, start_date='2018-01-02', end_date='2025-12-22'):
    df = data_manager.get_price_data(ticker, start_date=start_date, end_date=end_date)

    if df is None or df.empty:
        print(f"⚠️ {ticker} 데이터가 없습니다.")
        return None

    # 1. Buy & Hold (거치식)
    initial_price = df['close'].iloc[0]
    final_price = df['close'].iloc[-1]

    bh_return = ((final_price - initial_price) / initial_price) * 100

    # MDD 계산
    roll_max = df['close'].cummax()
    daily_drawdown = (df['close'] / roll_max) - 1.0
    bh_mdd = daily_drawdown.min() * 100

    # CAGR 계산
    days = (df.index[-1] - df.index[0]).days
    bh_cagr = ((final_price / initial_price) ** (365 / days) - 1) * 100

    return {
        'name': ticker + ' (Buy&Hold)',
        'return': bh_return,
        'mdd': bh_mdd,
        'cagr': bh_cagr
    }


# ==========================================
# 실행 및 비교 출력
# ==========================================
def run_comparison():
    print(f"⚖️ [전략 vs 벤치마크 성과 비교]")
    print(f"📅 기간: 2018-01-02 ~ 2025-12-22")
    print("-" * 65)
    print(f"{'Strategy':<20} | {'Return (%)':<12} {'CAGR (%)':<10} {'MDD (%)':<10}")
    print("-" * 65)

    # 1. 내 전략 출력
    print(
        f"{MY_STRATEGY['name']:<20} | {MY_STRATEGY['return']:12.2f} {MY_STRATEGY['cagr']:10.2f} {MY_STRATEGY['mdd']:10.2f}")

    # 2. SPY, QQQ 계산 및 출력
    for ticker in ['SPY', 'QQQ']:
        stats = calculate_benchmark_stats(ticker)
        if stats:
            print(f"{stats['name']:<20} | {stats['return']:12.2f} {stats['cagr']:10.2f} {stats['mdd']:10.2f}")

    print("-" * 65)


if __name__ == "__main__":
    run_comparison()
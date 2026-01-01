import pandas as pd
import numpy as np
import sqlite3  # DB 저장을 위해 추가
import data_manager
import strategy
import indicator
from backtesting import engine, metrics
from tqdm import tqdm
import config
from datetime import datetime

# ==========================================
# 1. 설정 (현재 20/10/2.0 유지)
# ==========================================
FINAL_PARAMS = {
    'entry_period': 20,
    'exit_period': 50,
    'score_threshold': 2.0,
    'turtle_weight': 2.0,
    'initial_capital': 100000.0,  # 10만불
    'atr_period': 20,
    'stop_loss_atr': 2.0,
    'risk_percent': 0.02
}

# 결과 저장할 DB 정보
DB_NAME = "backtest_log.db"
TABLE_NAME = "final_verification_results"


# ==========================================
# 2. 헬퍼 함수들
# ==========================================
def calculate_max_drawdown(value_series):
    if len(value_series) < 1: return 0.0
    running_max = value_series.cummax()
    drawdown = (value_series - running_max) / running_max
    mdd = drawdown.min() * 100
    return round(mdd, 2)


def calculate_buy_and_hold_stats(df, initial_capital):
    if df.empty: return 0.0, 0.0
    asset_values = (df['close'] / df['close'].iloc[0]) * initial_capital
    total_return = ((asset_values.iloc[-1] - initial_capital) / initial_capital) * 100
    mdd = calculate_max_drawdown(asset_values)
    return total_return, mdd


def calculate_dca_stats(df, monthly_amount=1000):
    if df.empty: return 0.0, 0.0
    df = df.copy()
    df['year_month'] = df.index.to_period('M')

    # [유지] 경고 메시지 해결 옵션
    buy_dates = df.groupby('year_month').apply(lambda x: x.index[0], include_groups=False)
    buy_dates_set = set(buy_dates)

    total_invested = 0
    total_shares = 0
    portfolio_values = []

    for date, row in df.iterrows():
        if date in buy_dates_set:
            shares_bought = monthly_amount / row['close']
            total_shares += shares_bought
            total_invested += monthly_amount

        current_value = total_shares * row['close']
        portfolio_values.append(current_value if total_invested > 0 else 0)

    value_series = pd.Series(portfolio_values)
    if total_invested == 0: return 0.0, 0.0

    final_value = value_series.iloc[-1]
    total_return = ((final_value - total_invested) / total_invested) * 100
    mdd = calculate_max_drawdown(value_series)
    return total_return, mdd


def run_ensemble_strategy(df, params):
    context = params.copy()

    try:
        df = indicator.add_turtle_indicators(df, context)
        df = indicator.add_rsi_indicators(df, context)
        df = indicator.add_sma_indicators(df, context)
        df = indicator.add_bollinger_band_indicators(df, context)
        df = indicator.add_macd_indicators(df, context)
        df = indicator.add_bbs_indicators(df, context)
        df = indicator.add_dema_indicators(df, context)
        df = strategy.apply_ensemble_strategy(df, context)
    except Exception:
        return None

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
# 3. 메인 실행 (전 종목 스캔)
# ==========================================
def main():
    print(f"🌎 [Global Verification] S&P500 전 종목 검증 시작")
    print(
        f"   - 설정: Entry {FINAL_PARAMS['entry_period']} / Exit {FINAL_PARAMS['exit_period']} / Threshold {FINAL_PARAMS['score_threshold']}")
    print("-" * 60)

    tickers = data_manager.get_ticker_list()
    # tickers = tickers[:10] # 테스트용 (필요 시 주석 해제)

    print(f"📊 총 {len(tickers)}개 종목 데이터를 로드하고 분석합니다...")

    results = []

    for symbol in tqdm(tickers):
        try:
            # 2018년부터 검증
            df = data_manager.get_price_data(symbol, start_date='2018-01-01')
            if df is None or len(df) < 250: continue

            # 1. 전략 실행
            strat_stats = run_ensemble_strategy(df.copy(), FINAL_PARAMS)
            if strat_stats is None: continue

            # 2. B&H 계산
            bh_ret, bh_mdd = calculate_buy_and_hold_stats(df.copy(), FINAL_PARAMS['initial_capital'])

            # 3. DCA 계산
            dca_ret, dca_mdd = calculate_dca_stats(df.copy())

            # 승리 여부 판단
            is_win = False
            win_type = "Lose"

            strat_ret = strat_stats['total_return']
            strat_mdd = strat_stats['max_drawdown']

            if strat_ret > bh_ret:
                win_type = "Alpha"
                is_win = True
            elif strat_mdd > (bh_mdd * 0.5) and strat_ret > 0:
                # MDD가 B&H의 절반 수준(예: -10% > -30% * 0.5)으로 방어력이 좋고 수익이 난 경우
                # (주의: MDD는 음수이므로 클수록(-5 > -30) 좋은 것임)
                win_type = "Defense"
                is_win = True

            results.append({
                'Symbol': symbol,
                'Strat_Ret': round(strat_ret, 2),
                'Strat_MDD': round(strat_mdd, 2),
                'BH_Ret': round(bh_ret, 2),
                'BH_MDD': round(bh_mdd, 2),
                'DCA_Ret': round(dca_ret, 2),
                'Trades': strat_stats['total_trades'],
                'Win_Type': win_type,
                'Run_Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # 실행 시간 기록
            })

        except Exception as e:
            continue

    # ==========================================
    # 4. 결과 저장 (SQLite)
    # ==========================================
    if not results:
        print("결과 데이터가 없습니다.")
        return

    df_res = pd.DataFrame(results)

    # DB 연결 및 저장
    try:
        conn = sqlite3.connect(DB_NAME)
        # if_exists='replace': 테이블이 있으면 지우고 새로 만듦 (항상 최신 전체 스캔 결과 유지)
        # 만약 누적하고 싶다면 'append'로 변경
        df_res.to_sql(TABLE_NAME, conn, if_exists='append', index=False)
        conn.close()
        print(f"\n💾 상세 결과가 DB('{DB_NAME}')의 '{TABLE_NAME}' 테이블에 저장되었습니다.")

    except Exception as e:
        print(f"\n❌ DB 저장 중 오류 발생: {e}")
        # 혹시 모르니 CSV로도 백업 저장
        df_res.to_csv("backup_verification.csv", index=False)
        print("   (backup_verification.csv 파일로 백업되었습니다)")

    # 통계 요약 출력
    avg_strat = df_res['Strat_Ret'].mean()
    avg_bh = df_res['BH_Ret'].mean()
    avg_dca = df_res['DCA_Ret'].mean()

    win_count = len(df_res[df_res['Win_Type'] != 'Lose'])
    total_count = len(df_res)
    win_rate = (win_count / total_count) * 100

    print("\n" + "=" * 50)
    print(f"🏆 [S&P500 전체 검증 결과 요약]")
    print("=" * 50)
    print(f"1. 전체 종목 수 : {total_count}개")
    print(f"2. 전략 승률    : {win_rate:.1f}% ({win_count}개 종목에서 우위)")
    print("-" * 50)
    print(f"3. 평균 수익률 비교:")
    print(f"   - 🐢 내 전략   : {avg_strat:.2f}% (MDD 평균: {df_res['Strat_MDD'].mean():.2f}%)")
    print(f"   - 💎 Buy&Hold  : {avg_bh:.2f}%    (MDD 평균: {df_res['BH_MDD'].mean():.2f}%)")
    print(f"   - 💰 DCA(적립) : {avg_dca:.2f}%")
    print("-" * 50)

    print("\n🌟 전략 수익률 Top 5:")
    top_5 = df_res.sort_values(by='Strat_Ret', ascending=False).head(5)
    print(top_5[['Symbol', 'Strat_Ret', 'BH_Ret', 'Trades']].to_string(index=False))


if __name__ == "__main__":
    main()
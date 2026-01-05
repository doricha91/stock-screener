import pandas as pd
import numpy as np
import data_manager
import strategy
import indicator
from tqdm import tqdm
import sqlite3
import json
from datetime import datetime
import warnings
from multiprocessing import Pool, cpu_count
from portfolio import PortfolioDB
from run_portfolio_backtest2 import PORTFOLIO_CONFIG

# 경고 메시지 차단
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.filterwarnings("ignore")

# ==========================================
# ⚙️ 포트폴리오 설정 (기본값)
# ==========================================
# 이 값은 참고용일 뿐, 실제 실행 시에는 외부에서 주입된 config가 사용됩니다.
PORTFOLIO_CONFIG = {
    'initial_capital': 100000.0,
    'risk_per_trade': 0.05,
    'max_positions': 4,
    'entry_period': 20,
    'exit_period': 10,
    'score_threshold': 1.0,

    # 가중치 변수들
    'turtle_weight': 1.0,
    'rs_weight': 3.0,
    'rsi_weight': 1.0,
    'sma_weight': 1.0,
    'bbands_weight': 1.0,
    'macd_weight': 1.0,
    'bbs_weight': 1.0,
    'dema_weight': 1.0,
    'obv_weight': 0.5,
    'mfi_weight': 0.5,
    'vol_spike_weight': 0.5,

    # 지표 기간
    'atr_period': 20,
    'rsi_period': 14,
    'sma_short_period': 50,
    'sma_long_period': 200,
    'bbands_period': 20,
    'macd_fast_period': 12,
    'macd_slow_period': 26,
    'dema_short_period': 20,
    'mfi_period': 14,
    'rs_lookback': 120,

    # 트레일링 스탑 설정
    'trailing_stop_multiplier': 2.5
}

# ==========================================
# 전역 변수 및 워커 함수 (멀티프로세싱용)
# ==========================================
spy_global = None


def init_worker(spy_data):
    """메인 프로세스에서 SPY 데이터를 받아와 전역 변수에 저장"""
    global spy_global
    spy_global = spy_data


def calculate_relative_strength(stock_df, spy_df, lookback=120):
    """개별 종목과 SPY의 수익률 차이(RS) 계산"""
    try:
        common_index = stock_df.index.intersection(spy_df.index)
        if len(common_index) < lookback:
            return pd.Series(0, index=stock_df.index)

        stock_close = stock_df.loc[common_index, 'close']
        spy_close = spy_df.loc[common_index, 'close']

        # 단순 수익률 차이 (Momentum Spread)
        rs_series = stock_close.pct_change(lookback) - spy_close.pct_change(lookback)
        return rs_series.reindex(stock_df.index).fillna(-1.0)
    except Exception:
        return pd.Series(0, index=stock_df.index)


# ==========================================
# [수정] 워커 함수 (Config를 인자로 받음)
# ==========================================
def process_single_stock(args):
    """
    args: (symbol, df, config)
    -> config를 직접 받아서 사용하므로 멀티프로세싱에서도 설정이 적용됨
    """
    symbol, df, config = args  # [핵심] Config 언패킹
    global spy_global

    try:
        if len(df) < 130: return None
        df = df.sort_index()

        # 전달받은 config 사용
        context = config.copy()
        context['symbol'] = symbol

        # 지표 계산
        df = indicator.add_turtle_indicators(df, context)
        df = indicator.add_atr_indicators(df, context)
        df = indicator.add_rsi_indicators(df, context)
        df = indicator.add_sma_indicators(df, context)
        df = indicator.add_bollinger_band_indicators(df, context)
        df = indicator.add_macd_indicators(df, context)
        df = indicator.add_bbs_indicators(df, context)
        df = indicator.add_dema_indicators(df, context)
        df = indicator.add_volume_indicators(df, context)

        # 전략 적용
        df = strategy.apply_ensemble_strategy(df, context)

        # RS 계산
        if spy_global is not None:
            # RS 기간도 설정값에서 가져옴
            df['rs_val'] = calculate_relative_strength(df, spy_global, context.get('rs_lookback', 120))
        else:
            df['rs_val'] = 0.0

        if 'entry_high' not in df.columns: return None

        # 점수 합산
        weights = {
            'turtle': context.get('turtle_weight', 1.0),
            'rsi': context.get('rsi_weight', 1.0),
            'sma': context.get('sma_weight', 1.0),
            'bbands': context.get('bbands_weight', 1.0),
            'macd': context.get('macd_weight', 1.0),
            'bbs': context.get('bbs_weight', 1.0),
            'dema': context.get('dema_weight', 1.0),
            'obv': context.get('obv_weight', 0.5),
            'mfi': context.get('mfi_weight', 0.5),
            'vol_spike': context.get('vol_spike_weight', 0.5),
            'rs': context.get('rs_weight', 0.0)
        }

        df['score'] = 0.0
        for name, weight in weights.items():
            col_name = f'signal_{name}'
            if col_name in df.columns:
                df['score'] += df[col_name].apply(lambda x: weight if x == 1 else 0)

        if weights['rs'] > 0:
            df['score'] += (df['rs_val'] > 0).astype(int) * weights['rs']

        df['vol_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
        df['symbol'] = symbol

        # 신호 생성
        df['buy_signal'] = (df['score'] >= context['score_threshold']) & \
                           (df['rs_val'] > 0)

        df['sell_signal'] = df['close'] < df['exit_low']

        if 'date' not in df.columns: df = df.reset_index()
        df.rename(columns={'index': 'date', 'Date': 'date'}, inplace=True)

        cols = ['date', 'symbol', 'open', 'high', 'low', 'close', 'atr', 'buy_signal', 'sell_signal', 'score',
                'vol_ratio', 'rs_val']
        return df[[c for c in cols if c in df.columns]]

    except Exception:
        return None


# ==========================================
# [수정] 데이터 로드 (Config 전달)
# ==========================================
def prepare_market_data(config=PORTFOLIO_CONFIG):
    """
    Config에 정의된 종목 리스트(target_tickers)를 우선 사용하고,
    없으면 DB에서 NASDAQ100 종목을 조회합니다.
    """
    target_tickers = []

    # 1. [신규] Config에서 커스텀 종목 리스트 확인
    if 'target_tickers' in config and config['target_tickers']:
        print(f"🎯 [설정] 커스텀 종목 바스켓 사용 ({len(config['target_tickers'])}종목)")
        target_tickers = config['target_tickers']
    else:
        # 2. 기존 로직 (NASDAQ100 조회)
        print("⏳ [Step 1] 나스닥 100 종목 리스트 DB 조회...")
        conn = sqlite3.connect("market_data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT symbol FROM tickers WHERE listing_board = 'NASDAQ100'")
        rows = cursor.fetchall()
        target_tickers = [row[0] for row in rows]
        conn.close()

        if not target_tickers:
            target_tickers = data_manager.get_ticker_list()

    # [수정] 지표 계산을 위해 데이터는 넉넉하게 미리(2017년부터) 가져옵니다.
    # (백테스트 시작이 2018년이라도, 이평선 계산 등을 위해 이전 데이터가 필요함)
    print("⏳ [Step 2] 데이터 로드 중 (Bulk Load)...")
    df_all = data_manager.get_all_price_data_bulk(start_date='2013-01-01')
    if df_all.empty: return {}, []

    try:
        spy_df = df_all[df_all['symbol'] == 'SPY'].set_index('date').sort_index()
        if spy_df.empty:
            spy_df = df_all[df_all['symbol'] == df_all['symbol'].iloc[0]].set_index('date').sort_index()
    except:
        return {}, []

    print(f"🚀 [Step 3] 병렬 데이터 생성...")
    tasks = []
    grouped = df_all.groupby('symbol')

    for symbol, group in grouped:
        if symbol in target_tickers and symbol != 'SPY':
            # [핵심] 일꾼에게 config를 함께 포장해서 전달!
            tasks.append((symbol, group.set_index('date').sort_index(), config))

    all_signals = []
    with Pool(processes=cpu_count(), initializer=init_worker, initargs=(spy_df,)) as pool:
        # tqdm 제거 (Optimizer 실행 시 로그 너무 많음)
        results = list(pool.imap(process_single_stock, tasks))
        all_signals = [res for res in results if res is not None]

    if not all_signals: return {}, []

    print("🔄 데이터 병합 및 기간 필터링 중...")
    full_df = pd.concat(all_signals)
    full_df['date'] = pd.to_datetime(full_df['date'])

    # ==============================================================================
    # [수정된 부분] Config에서 날짜를 받아와서 필터링 (OOS 검증용)
    # ==============================================================================
    # 1. config에서 날짜 가져오기 (없으면 기본값 사용)
    start_date = config.get('start_date', '2018-01-01')
    end_date = config.get('end_date', '2025-12-31')

    # 2. 해당 기간의 데이터만 남기기 (Masking)
    mask = (full_df['date'] >= start_date) & (full_df['date'] <= end_date)
    full_df = full_df.loc[mask].sort_values(['date', 'symbol'])

    print(f"   👉 설정 기간: {start_date} ~ {end_date} (데이터 수: {len(full_df)})")
    # ==============================================================================

    return {date: data for date, data in full_df.groupby('date')}, full_df['date'].unique()


# ==========================================
# [수정 3] 실행 엔진 (DB 모드 적용)
# ==========================================
def run_backtest_with_config(config, verbose=False):
    """
    Optimizer 및 단독 실행용 백테스트 함수
    - verbose=True일 경우 상세 리포트(analyze_results)를 출력합니다.
    """
    global PORTFOLIO_CONFIG
    PORTFOLIO_CONFIG = config

    # 1. 데이터 준비
    market_data, date_list = prepare_market_data(config)
    if not market_data: return None

    # 2. PortfolioDB 초기화 (속도를 위해 메모리 DB 사용)
    # PortfolioDB는 portfolio.py에서 import 해야 합니다.
    pf = PortfolioDB(db_path=":memory:", initial_cash=config['initial_capital'])

    # 자산 흐름 기록용 리스트 (CAGR, MDD 계산용)
    equity_history = []

    # ----------------------------------------------------------------------
    # 📅 일별 시뮬레이션 루프 시작
    # ----------------------------------------------------------------------
    for date in date_list:
        day_data = market_data[date].set_index('symbol')
        current_prices = day_data['close'].to_dict()

        # [Step 1] 보유 종목 상태 업데이트 (현재가, 평가금액, 최고가 갱신)
        # 딕셔너리 키(symbol)만 가져와서 순회
        current_positions = pf.get_positions()
        for sym in current_positions.keys():
            if sym in current_prices:
                pf.update_market_status(sym, current_prices[sym])

        # [Step 2] 자산 가치 기록
        status = pf.get_account_status()
        equity_history.append({'date': date, 'equity': status['total_equity']})

        # [Step 3] 매도 로직 (Strategy Exit OR Trailing Stop)
        # 매도 시 딕셔너리가 변경되므로 list로 키를 복사해서 순회
        for symbol in list(current_positions.keys()):
            if symbol not in day_data.index: continue

            row = day_data.loc[symbol]
            current_price = row['close']
            current_atr = row['atr']
            pos_info = current_positions[symbol]  # 보유 정보

            # A. 트레일링 스탑 체크
            ts_mult = config.get('trailing_stop_multiplier', 2.5)
            ts_triggered, _ = pf.check_trailing_stop(symbol, current_price, current_atr, ts_mult)

            # B. 전략 매도 신호
            signal_sell = row['sell_signal']

            # 매도 실행
            if signal_sell or ts_triggered:
                reason = "Trailing Stop" if ts_triggered else "Signal Exit"
                pf.sell(symbol, current_price, pos_info['shares'], date, reason=reason)

        # [Step 4] 매수 로직 (Ensemble Entry)
        # 다시 현재 상태 조회 (매도로 인해 현금/슬롯이 변했을 수 있음)
        status = pf.get_account_status()
        current_holdings_count = len(pf.get_positions())

        # 슬롯이 남고 현금이 있을 때만 진입 시도
        if current_holdings_count < config['max_positions'] and status['cash'] > 0:
            candidates = day_data[day_data['buy_signal'] == True]

            # 이미 보유한 종목 제외
            already_owned = pf.get_positions().keys()
            candidates = candidates[~candidates.index.isin(already_owned)]

            if not candidates.empty:
                # RS 높은 순으로 정렬 (우선순위)
                candidates = candidates.sort_values(by='rs_val', ascending=False)

                for symbol, row in candidates.iterrows():
                    # 반복문 안에서도 실시간 상태 확인
                    status = pf.get_account_status()
                    if len(pf.get_positions()) >= config['max_positions']: break
                    if status['cash'] < row['close']: break

                    # 자금 관리: 1/N 균등 배분
                    target_equity_per_stock = status['total_equity'] / config['max_positions']
                    shares_to_buy = int(target_equity_per_stock / row['close'])

                    # 현금 부족 시 가능한 만큼만
                    max_affordable = int(status['cash'] / row['close'])
                    shares_to_buy = min(shares_to_buy, max_affordable)

                    if shares_to_buy > 0:
                        pf.buy(symbol, row['close'], shares_to_buy, date, strategy_name="Ensemble")

    # ----------------------------------------------------------------------
    # 📊 결과 집계 및 메트릭 계산
    # ----------------------------------------------------------------------
    if not equity_history: return None

    # 1. Equity Curve DataFrame 생성
    history_df = pd.DataFrame(equity_history).set_index('date')
    history_df.index = pd.to_datetime(history_df.index)
    history_df['daily_ret'] = history_df['equity'].pct_change().fillna(0)

    # 2. 핵심 지표 계산
    final_equity = history_df['equity'].iloc[-1]
    total_ret = (final_equity - config['initial_capital']) / config['initial_capital'] * 100
    mdd = ((history_df['equity'] - history_df['equity'].cummax()) / history_df['equity'].cummax()).min() * 100

    days = (history_df.index[-1] - history_df.index[0]).days
    cagr = ((final_equity / config['initial_capital']) ** (365 / days) - 1) * 100 if days > 0 else 0

    std_dev = history_df['daily_ret'].std() * np.sqrt(252)
    sharpe = (cagr / 100) / std_dev if std_dev > 0 else 0
    down_std = history_df[history_df['daily_ret'] < 0]['daily_ret'].std() * np.sqrt(252)
    sortino = (cagr / 100) / down_std if down_std > 0 else 0
    calmar = abs(cagr / mdd) if mdd != 0 else 0

    # 3. 연도별 수익률 (JSON 저장용)
    yearly = history_df['equity'].resample('YE').last().pct_change() * 100
    if not yearly.empty:
        # 첫 해 수익률 보정
        first_ret = (history_df['equity'].resample('YE').last().iloc[0] - config['initial_capital']) / config[
            'initial_capital'] * 100
        yearly.iloc[0] = first_ret
    yearly_json = json.dumps({str(k.year): round(v, 2) for k, v in yearly.items()})

    # 4. 거래 기록 분석 (DB에서 조회)
    conn = pf._get_conn()
    trades_df = pd.read_sql("SELECT * FROM trade_history WHERE type='SELL'", conn)
    conn.close()

    total_trades = 0
    win_rate = 0.0
    profit_factor = 0.0
    avg_win = 0.0
    avg_loss = 0.0

    if not trades_df.empty:
        total_trades = len(trades_df)
        win_trades = trades_df[trades_df['profit'] > 0]
        loss_trades = trades_df[trades_df['profit'] <= 0]

        win_rate = len(win_trades) / total_trades * 100
        gross_profit = win_trades['profit'].sum()
        gross_loss = abs(loss_trades['profit'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss != 0 else 99.9

        # 참고: 정확한 수익률(%) 평균은 entry amount가 있어야 정확하지만, 여기선 생략

    # -------------------------------------------------------
    # [상세 리포트 출력] verbose=True 일 때만 실행
    # -------------------------------------------------------
    if verbose:
        # analyze_results 함수는 앞서 정의해둔 것을 사용
        analyze_results(equity_history, trades_df, config['initial_capital'])

    # 최종 결과 반환
    return {
        'return': total_ret,
        'cagr': cagr,
        'mdd': mdd,
        'final_equity': final_equity,
        'sharpe': sharpe,
        'sortino': sortino,
        'calmar': calmar,
        'yearly_json': yearly_json,
        'total_trades': total_trades,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'avg_win': avg_win,
        'avg_loss': avg_loss
    }


# [수정] 단독 실행 함수
def run_portfolio_simulation():
    print("🚀 단독 백테스트 모드 (PortfolioDB 사용)")

    # 예시: 커스텀 바스켓 설정 테스트
    # PORTFOLIO_CONFIG['target_tickers'] = ['AAPL', 'TSLA', 'NVDA', 'MSFT', 'AMZN']

    # verbose=True로 설정하여 상세 리포트 출력
    run_backtest_with_config(PORTFOLIO_CONFIG, verbose=True)

# ==========================================
# 상세 분석 출력 함수
# ==========================================
def analyze_results(equity_history, trades_df, initial_capital):
    """
    상세 분석 리포트 출력 함수 (DB 버전 호환)
    - equity_history: [{'date':..., 'equity':...}] 형태의 리스트
    - trades_df: trade_history 테이블에서 조회한 DataFrame
    """
    if not equity_history: return

    # 1. 자산 데이터 가공
    history_df = pd.DataFrame(equity_history).set_index('date')
    history_df.index = pd.to_datetime(history_df.index)
    history_df['daily_ret'] = history_df['equity'].pct_change().fillna(0)

    final = history_df['equity'].iloc[-1]
    total_ret = (final - initial_capital) / initial_capital * 100

    # MDD 계산
    roll_max = history_df['equity'].cummax()
    mdd = ((history_df['equity'] - roll_max) / roll_max).min() * 100

    # CAGR 계산
    days = (history_df.index[-1] - history_df.index[0]).days
    cagr = ((final / initial_capital) ** (365 / days) - 1) * 100 if days > 0 else 0

    # 주요 지표
    std_dev = history_df['daily_ret'].std() * np.sqrt(252)
    sharpe = (cagr / 100) / std_dev if std_dev > 0 else 0
    down_std = history_df[history_df['daily_ret'] < 0]['daily_ret'].std() * np.sqrt(252)
    sortino = (cagr / 100) / down_std if down_std > 0 else 0
    calmar = abs(cagr / mdd) if mdd != 0 else 0

    print("\n" + "=" * 50)
    print(f"📊 [최종 백테스트 상세 리포트]")
    print("=" * 50)
    print(f"💰 자본: ${initial_capital:,.0f} ➔ ${final:,.0f}")
    print(f"🚀 총 수익률 : {total_ret:.2f}%")
    print(f"📈 CAGR     : {cagr:.2f}%")
    print(f"🛡️ MDD      : {mdd:.2f}%")
    print(f"📐 Sharpe   : {sharpe:.2f} | Sortino: {sortino:.2f} | Calmar: {calmar:.2f}")
    print("-" * 50)

    # 2. 거래 기록 분석
    if not trades_df.empty:
        # DB에는 profit(금액) 정보가 있음
        total = len(trades_df)
        wins = len(trades_df[trades_df['profit'] > 0])
        win_rate = wins / total * 100

        gross_profit = trades_df[trades_df['profit'] > 0]['profit'].sum()
        gross_loss = abs(trades_df[trades_df['profit'] <= 0]['profit'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss != 0 else 99.9

        # 보유 기간 계산 (매수일/매도일 정보 필요 - trade_history 테이블 구조상 date만 있음)
        # 정확한 보유일 계산을 위해선 매수/매도 매칭이 필요하지만, 여기선 약식으로 처리하거나 생략

        print(f"🔄 총 거래수 : {total}회")
        print(f"🎯 승률     : {win_rate:.2f}%")
        print(f"⚖️ 손익비   : {profit_factor:.2f}")

        best = trades_df.loc[trades_df['profit'].idxmax()]
        worst = trades_df.loc[trades_df['profit'].idxmin()]

        # 수익률 정보가 없다면 금액으로만 표시
        print(f"🏆 Best : {best['symbol']} (${best['profit']:,.0f})")
        print(f"💀 Worst: {worst['symbol']} (${worst['profit']:,.0f})")

    print("-" * 50)
    print("[연도별 수익률]")
    yearly = history_df['equity'].resample('YE').last().pct_change() * 100
    # 첫 해 수익률 보정
    if not yearly.empty:
        first_year_ret = (history_df['equity'].resample('YE').last().iloc[0] - initial_capital) / initial_capital * 100
        yearly.iloc[0] = first_year_ret

    for y, r in yearly.items():
        print(f"{y.year}: {r:6.2f}%")
    print("=" * 50)


if __name__ == "__main__":
    run_portfolio_simulation()




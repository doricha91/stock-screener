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
    'atr_period': 20,
    'rsi_period': 14,
    'sma_short_period': 50,
    'sma_long_period': 200,
    'bbands_period': 20,
    'macd_fast_period': 12,
    'macd_slow_period': 26,
    'dema_short_period': 20,
    'mfi_period': 14,
    'rs_lookback': 120
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
    config를 인자로 받아서 워커들에게 전달하고,
    config에 설정된 기간(start_date ~ end_date)의 데이터만 필터링하여 반환합니다.
    """
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
# Portfolio 클래스
# ==========================================
class Portfolio:
    def __init__(self, initial_cash, max_pos):
        self.initial_capital = initial_cash
        self.cash = initial_cash
        self.equity = initial_cash
        self.max_positions = max_pos
        self.positions = {}
        self.history = []
        self.trade_log = []

    def update_equity(self, current_prices):
        pos_value = 0
        for symbol, info in self.positions.items():
            price = current_prices.get(symbol, info['last_price'])
            pos_value += info['shares'] * price
            self.positions[symbol]['last_price'] = price
        self.equity = self.cash + pos_value

    def can_buy(self):
        return len(self.positions) < self.max_positions and self.cash > 0

    def calculate_shares(self, price):
        # 1/N Equal Weight
        if price == 0: return 0
        target_amt = self.equity / self.max_positions
        shares = int(target_amt / price)
        if shares * price > self.cash: shares = int(self.cash / price)
        return shares

    def record_trade(self, symbol, entry_date, exit_date, entry_price, exit_price, shares, note=""):
        profit = (exit_price - entry_price) * shares
        ret = (exit_price - entry_price) / entry_price
        self.trade_log.append({
            'symbol': symbol,
            'entry_date': entry_date,
            'exit_date': exit_date,
            'return': ret,
            'profit': profit,
            'holding_days': (exit_date - entry_date).days,
            'note': note
        })


# ==========================================
# [수정] 실행 엔진
# ==========================================
def run_backtest_with_config(config):
    """Optimizer용 실행 함수"""
    global PORTFOLIO_CONFIG
    PORTFOLIO_CONFIG = config
    # [핵심] config를 prepare_market_data에 전달
    market_data, date_list = prepare_market_data(config)
    if not market_data: return None

    pf = Portfolio(config['initial_capital'], config['max_positions'])

    for date in date_list:
        day_data = market_data[date].set_index('symbol')
        current_prices = day_data['close'].to_dict()
        pf.update_equity(current_prices)
        pf.history.append({'date': date, 'equity': pf.equity})

        symbols_to_sell = []
        for symbol, info in pf.positions.items():
            if symbol not in day_data.index: continue
            row = day_data.loc[symbol]
            if row['sell_signal']:
                pf.cash += info['shares'] * row['close']
                pf.record_trade(symbol, info['entry_date'], date, info['entry_price'], row['close'], info['shares'])
                symbols_to_sell.append(symbol)
        for s in symbols_to_sell: del pf.positions[s]

        if pf.can_buy():
            candidates = day_data[day_data['buy_signal'] == True]
            candidates = candidates[~candidates.index.isin(pf.positions.keys())]
            if not candidates.empty:
                candidates = candidates.sort_values(by='rs_val', ascending=False)
                for symbol, row in candidates.iterrows():
                    if not pf.can_buy(): break
                    shares = pf.calculate_shares(row['close'])
                    if shares > 0:
                        pf.cash -= shares * row['close']
                        pf.positions[symbol] = {
                            'shares': shares, 'entry_price': row['close'],
                            'entry_date': date, 'last_price': row['close']
                        }

    if not pf.history: return None

    history_df = pd.DataFrame(pf.history).set_index('date')
    history_df['daily_ret'] = history_df['equity'].pct_change().fillna(0)

    final_equity = history_df['equity'].iloc[-1]
    total_ret = (final_equity - config['initial_capital']) / config['initial_capital'] * 100
    mdd = ((history_df['equity'] - history_df['equity'].cummax()) / history_df['equity'].cummax()).min() * 100
    days = (history_df.index[-1] - history_df.index[0]).days
    cagr = ((final_equity / config['initial_capital']) ** (365 / days) - 1) * 100 if days > 0 else 0

    # Metrics
    std_dev = history_df['daily_ret'].std() * np.sqrt(252)
    sharpe = (cagr / 100) / std_dev if std_dev > 0 else 0
    down_std = history_df[history_df['daily_ret'] < 0]['daily_ret'].std() * np.sqrt(252)
    sortino = (cagr / 100) / down_std if down_std > 0 else 0
    calmar = abs(cagr / mdd) if mdd != 0 else 0

    yearly = history_df['equity'].resample('Y').last().pct_change() * 100
    yearly.iloc[0] = (history_df['equity'].resample('Y').last().iloc[0] - config['initial_capital']) / config[
        'initial_capital'] * 100
    yearly_json = json.dumps({str(k.year): round(v, 2) for k, v in yearly.items()})

    trades_df = pd.DataFrame(pf.trade_log)
    if not trades_df.empty:
        total_trades = len(trades_df)
        win_trades = trades_df[trades_df['return'] > 0]
        loss_trades = trades_df[trades_df['return'] <= 0]
        win_rate = len(win_trades) / total_trades * 100
        profit_factor = win_trades['profit'].sum() / abs(loss_trades['profit'].sum()) if loss_trades[
                                                                                             'profit'].sum() != 0 else 99.9
        avg_win = win_trades['return'].mean() * 100 if not win_trades.empty else 0
        avg_loss = loss_trades['return'].mean() * 100 if not loss_trades.empty else 0
    else:
        total_trades = 0;
        win_rate = 0.0;
        profit_factor = 0.0;
        avg_win = 0.0;
        avg_loss = 0.0

    return {
        'return': total_ret, 'cagr': cagr, 'mdd': mdd, 'final_equity': final_equity,
        'sharpe': sharpe, 'sortino': sortino, 'calmar': calmar, 'yearly_json': yearly_json,
        'total_trades': total_trades, 'win_rate': win_rate, 'profit_factor': profit_factor,
        'avg_win': avg_win, 'avg_loss': avg_loss
    }


def run_portfolio_simulation():
    """단독 실행용"""
    # 단독 실행 시에는 DEFAULT_CONFIG 사용
    print("🚀 단독 백테스트 모드")
    res = run_backtest_with_config(PORTFOLIO_CONFIG)
    if res:
        print("\n" + "=" * 40)
        print(f"💰 최종 자본: ${res['final_equity']:,.0f}")
        print(f"🚀 총 수익률 : {res['return']:.2f}%")
        print(f"🛡️ MDD      : {res['mdd']:.2f}%")
        print("=" * 40)


if __name__ == "__main__":
    run_portfolio_simulation()


# ==========================================
# 상세 분석 출력 함수
# ==========================================
def analyze_results(pf):
    if not pf.history: return

    # 데이터 가공
    history_df = pd.DataFrame(pf.history).set_index('date')
    history_df['daily_ret'] = history_df['equity'].pct_change().fillna(0)

    final = history_df['equity'].iloc[-1]
    initial = pf.initial_capital
    total_ret = (final - initial) / initial * 100

    roll_max = history_df['equity'].cummax()
    mdd = ((history_df['equity'] - roll_max) / roll_max).min() * 100

    days = (history_df.index[-1] - history_df.index[0]).days
    cagr = ((final / initial) ** (365 / days) - 1) * 100 if days > 0 else 0

    # 지표
    std_dev = history_df['daily_ret'].std() * np.sqrt(252)
    sharpe = (cagr / 100) / std_dev if std_dev > 0 else 0
    down_std = history_df[history_df['daily_ret'] < 0]['daily_ret'].std() * np.sqrt(252)
    sortino = (cagr / 100) / down_std if down_std > 0 else 0
    calmar = abs(cagr / mdd) if mdd != 0 else 0

    trades_df = pd.DataFrame(pf.trade_log)

    print("\n" + "=" * 50)
    print(f"📊 [최종 백테스트 상세 리포트]")
    print("=" * 50)
    print(f"💰 자본: ${initial:,.0f} ➔ ${final:,.0f}")
    print(f"🚀 총 수익률 : {total_ret:.2f}%")
    print(f"📈 CAGR     : {cagr:.2f}%")
    print(f"🛡️ MDD      : {mdd:.2f}%")
    print(f"📐 Sharpe   : {sharpe:.2f} | Sortino: {sortino:.2f} | Calmar: {calmar:.2f}")
    print("-" * 50)

    if not trades_df.empty:
        total = len(trades_df)
        wins = len(trades_df[trades_df['return'] > 0])
        win_rate = wins / total * 100
        pf_val = trades_df[trades_df['return'] > 0]['profit'].sum() / abs(
            trades_df[trades_df['return'] <= 0]['profit'].sum())

        print(f"🔄 총 거래수 : {total}회")
        print(f"🎯 승률     : {win_rate:.2f}%")
        print(f"⚖️ 손익비   : {pf_val:.2f}")
        print(f"⏱️ 평균보유 : {trades_df['holding_days'].mean():.1f}일")

        best = trades_df.loc[trades_df['profit'].idxmax()]
        worst = trades_df.loc[trades_df['profit'].idxmin()]
        print(f"🏆 Best : {best['symbol']} (+{best['return'] * 100:.1f}%, ${best['profit']:,.0f})")
        print(f"💀 Worst: {worst['symbol']} ({worst['return'] * 100:.1f}%, ${worst['profit']:,.0f})")

    print("-" * 50)
    print("[연도별 수익률]")
    yearly = history_df['equity'].resample('Y').last().pct_change() * 100
    yearly.iloc[0] = (history_df['equity'].resample('Y').last().iloc[0] - initial) / initial * 100
    for y, r in yearly.items():
        print(f"{y.year}: {r:6.2f}%")
    print("=" * 50)

    # 단독 실행 시에도 DB 저장
    res_dict = {
        'return': total_ret, 'cagr': cagr, 'mdd': mdd, 'sharpe': sharpe, 'sortino': sortino,
        'calmar': calmar, 'yearly_json': json.dumps({str(k.year): round(v, 2) for k, v in yearly.items()}),
        'final_equity': final, 'total_trades': total, 'win_rate': win_rate, 'profit_factor': pf_val,
        'avg_win': 0, 'avg_loss': 0  # analyze_results에서는 생략했지만 DB 저장을 위해 dummy
    }
    # save_to_db는 optimizer에 있으므로 여기서는 생략하거나 별도 구현


if __name__ == "__main__":
    run_portfolio_simulation()
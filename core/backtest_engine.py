import pandas as pd
import numpy as np
import json
import market_analyzer
import csv
from multiprocessing import Pool, cpu_count
from screener import data_manager, strategy, indicator
from screener.portfolio import PortfolioDB
from pathlib import Path


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


def get_market_index_data(symbol):
    """market_index 테이블에서 특정 심볼(인버스 ETF 등)의 모든 데이터를 가져옴"""
    import sqlite3
    from core.paths import market_db_path
    conn = sqlite3.connect(market_db_path())
    query = f"SELECT date, close FROM market_index WHERE symbol = '{symbol}' ORDER BY date"
    df = pd.read_sql(query, conn)
    conn.close()
    if df.empty:
        return {}
    df['date'] = pd.to_datetime(df['date'])
    return df.set_index('date')['close'].to_dict()


# [수정] 워커 함수 (Config를 인자로 받음)
def process_single_stock(args):
    """
    args: (symbol, df, config)
    -> config를 직접 받아서 사용하므로 멀티프로세싱에서도 설정이 적용됨
    """
    symbol, df, config = args  # [핵심] Config 언패킹
    global spy_global

    try:
        if len(df) < 130:
            return None
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

        if 'entry_high' not in df.columns:
            return None

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
        df['buy_signal'] = (df['score'] >= context['score_threshold']) & (df['rs_val'] > 0)
        df['sell_signal'] = df['close'] < df['exit_low']

        if 'date' not in df.columns:
            df = df.reset_index()
        df.rename(columns={'index': 'date', 'Date': 'date'}, inplace=True)

        cols = ['date', 'symbol', 'open', 'high', 'low', 'close', 'atr',
                'buy_signal', 'sell_signal', 'score', 'vol_ratio', 'rs_val']
        return df[[c for c in cols if c in df.columns]]

    except Exception as e:
        print(f"   ❌ [process_single_stock] {symbol} 처리 중 에러: {e}")
        import traceback
        traceback.print_exc()
        return None


# [수정] 데이터 로드 (Config 전달)
def prepare_market_data(config):
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
        conn = market_analyzer.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT symbol FROM tickers WHERE listing_board = 'NASDAQ100'")
        rows = cursor.fetchall()
        target_tickers = [row[0] for row in rows]
        conn.close()

        if not target_tickers:
            target_tickers = data_manager.get_ticker_list()

    # 지표 계산을 위해 데이터는 넉넉하게 미리(2013년부터) 가져옵니다.
    print("⏳ [Step 2] 데이터 로드 중 (Bulk Load)...")
    bulk_start = '2013-01-01'
    df_all = data_manager.get_all_price_data_bulk(start_date=bulk_start)
    if df_all.empty:
        return {}, []

    try:
        spy_df = df_all[df_all['symbol'] == 'SPY'].set_index('date').sort_index()
        if spy_df.empty:
            spy_df = df_all[df_all['symbol'] == df_all['symbol'].iloc[0]].set_index('date').sort_index()
    except Exception:
        return {}, []

    print(f"🚀 [Step 3] 병렬 데이터 생성...")
    tasks = []
    grouped = df_all.groupby('symbol')

    for symbol, group in grouped:
        if symbol in target_tickers and symbol != 'SPY':
            tasks.append((symbol, group.set_index('date').sort_index(), config))

    with Pool(processes=cpu_count(), initializer=init_worker, initargs=(spy_df,)) as pool:
        results = list(pool.imap(process_single_stock, tasks))
        all_signals = [res for res in results if res is not None]

    if not all_signals:
        return {}, []

    print("🔄 데이터 병합 및 기간 필터링 중...")
    full_df = pd.concat(all_signals)
    full_df['date'] = pd.to_datetime(full_df['date'])

    # ======================================================================
    # Config에서 날짜를 받아와서 필터링 (OOS 검증용)
    # ======================================================================
    start_date = config.get('start_date', '2018-01-01')
    end_date = config.get('end_date', '2025-12-31')

    mask = (full_df['date'] >= start_date) & (full_df['date'] <= end_date)
    full_df = full_df.loc[mask].sort_values(['date', 'symbol'])

    print(f"   👉 설정 기간: {start_date} ~ {end_date} (데이터 수: {len(full_df)})")
    # ======================================================================

    return {date: data for date, data in full_df.groupby('date')}, full_df['date'].unique()


# [수정 3] 실행 엔진 (DB 모드 적용)
def run_backtest_with_config(config, verbose=False, prev_trade_halted=None):
    """
    Optimizer 및 단독 실행용 백테스트 함수
    - verbose=True일 경우 상세 리포트(analyze_results)를 출력합니다.
    """
    global PORTFOLIO_CONFIG
    PORTFOLIO_CONFIG = config

    # 1. 데이터 준비
    market_data, date_list = prepare_market_data(config)
    if not market_data:
        return None

    # 2. PortfolioDB 초기화 (속도를 위해 메모리 DB 사용)
    pf = PortfolioDB(db_path=":memory:", initial_cash=config['initial_capital'])

    # 자산 흐름 기록용 리스트
    equity_history = []

    # [신규] Hedge 모드 상태 변수
    current_mode = "LONG"
    mode_start_date = None
    hedge_asset_prices = {}
    if config.get('USE_HEDGE_MODE', False):
        hedge_tickers = config.get('HEDGE_TICKERS', [])
        for t in hedge_tickers:
            hedge_asset_prices[t] = get_market_index_data(t)

    # [신규] 안전장치 및 국면 통계 초기화
    safety_stats = {
        'cb_halt_days': 0,
        'vix_trigger_count': 0,
        'drawdown_trigger_count': 0,
        'breadth_low_count': 0,
        'ma_cross_bearish_count': 0,
        'panic_days': 0,
        'bear_days': 0,
        'unstable_days': 0,
        'bull_days': 0
    }

    # [NEW] 의사결정 로그 초기화
    d_logger = None
    if config.get('enable_decision_logging', False):
        run_name = config.get('run_name', 'backtest')
        from backtesting.logger import DecisionLogger
        d_logger = DecisionLogger(run_name=run_name)

    # 이전 상태 기억용
    prev_regime_name = None
    prev_trade_halted = None
    target_cash_ratio = 0.0

    # ----------------------------------------------------------------------
    # 📅 일별 시뮬레이션 루프 시작
    # ----------------------------------------------------------------------
    for date in date_list:
        date_str = date.strftime('%Y-%m-%d')
        trade_halted = False

        if config.get('use_market_regime', True):
            # [The Brain] 국면 판단
            if hasattr(market_analyzer, "get_market_state"):
                state = market_analyzer.get_market_state(target_date=date_str)
                regime_name = state["regime"]
                regime_rule = state["plan"]
                trade_halted = bool(state.get("trade_halted", False))
            else:
                regime_name, regime_rule = market_analyzer.get_market_regime(target_date=date_str)
                trade_halted = False

            # 국면 변경 로그
            if regime_name != prev_regime_name:
                if verbose:
                    print(f"📌 [{date_str}] 시장 국면 변경: {prev_regime_name} ➔ {regime_name}")
                if d_logger:
                    status = pf.get_account_status()
                    d_logger.log_event(date_str, regime_name, current_mode, "REGIME_CHANGE", 
                                     f"{prev_regime_name} -> {regime_name} ({regime_rule['description']})", 
                                     status, target_cash_ratio)
                prev_regime_name = regime_name

            # Config 동적 업데이트
            for strategy_name, weight in regime_rule['weights'].items():
                key = f"{strategy_name}_weight"
                config[key] = weight
            config['trailing_stop_multiplier'] = regime_rule['trailing_stop_multiplier']
            target_cash_ratio = regime_rule['target_cash_ratio']

            # Hedge 모드 판정 및 전환
            if config.get('USE_HEDGE_MODE', False):
                min_days = config.get('MIN_MODE_MAINTAIN_DAYS', 5)
                can_switch = (mode_start_date is None) or ((date - mode_start_date).days >= min_days)

                if regime_name in ['BEAR', 'PANIC'] and current_mode == "LONG" and can_switch:
                    current_mode = "HEDGE"
                    mode_start_date = date
                    if verbose: print(f"🛡️ [{date_str}] Hedge 모드 진입 (국면: {regime_name})")
                    
                    # (Hedge 매수 로직 생략 - 기존과 동일)
                    ratio = config.get('HEDGE_RATIO_PANIC' if regime_name == 'PANIC' else 'HEDGE_RATIO_BEAR', 0.2)
                    status = pf.get_account_status()
                    target_hedge_value = status['total_equity'] * ratio
                    
                    if d_logger:
                        d_logger.log_event(date_str, regime_name, current_mode, "MODE_CHANGE", 
                                         f"LONG -> HEDGE (Target Ratio: {ratio})", status, target_cash_ratio)

                    # ... (매각 및 매수 로직 기존과 동일하게 유지) ...
                    # [최소 수정을 위해 기존 로직 유지하되 로그만 삽입]
                    current_positions = pf.get_positions()
                    if current_positions:
                        priority = config.get('HEDGE_LIQUIDATION_PRIORITY', 'rs_low')
                        pos_list = []
                        for sym, info in current_positions.items():
                            if info.get('strategy_name') == "Hedge": continue
                            ret = (current_prices.get(sym, info['avg_price']) - info['avg_price']) / info['avg_price']
                            weight = (info['shares'] * current_prices.get(sym, info['avg_price'])) / status['total_equity']
                            rs_val = day_data.loc[sym, 'rs_val'] if sym in day_data.index else -1.0
                            age = (date - pd.to_datetime(info['entry_date'])).days
                            pos_list.append({'symbol': sym, 'shares': info['shares'], 'rs_low': rs_val, 'return_low': ret, 'weight_low': weight, 'age_high': -age})
                        pos_list.sort(key=lambda x: x.get(priority, 0))
                        for p in pos_list:
                            status = pf.get_account_status()
                            if status['cash'] >= target_hedge_value: break
                            sym = p['symbol']
                            price = current_prices.get(sym, 0)
                            if price > 0: pf.sell(sym, price, p['shares'], date, reason=f"Hedge Liquidation ({priority})")

                    status = pf.get_account_status()
                    hedge_asset = config.get('HEDGE_ASSET', 'PSQ')
                    asset_price = hedge_asset_prices.get(hedge_asset, {}).get(date)
                    if asset_price and asset_price > 0:
                        buy_amount = min(status['cash'], target_hedge_value)
                        shares = int(buy_amount / asset_price)
                        if shares > 0: pf.buy(hedge_asset, asset_price, shares, date, strategy_name="Hedge")

                elif regime_name in ['BULL', 'UNSTABLE'] and current_mode == "HEDGE" and can_switch:
                    current_mode = "LONG"
                    mode_start_date = date
                    if verbose: print(f"🚀 [{date_str}] LONG 모드 복귀 (국면: {regime_name})")
                    if d_logger:
                        status = pf.get_account_status()
                        d_logger.log_event(date_str, regime_name, current_mode, "MODE_CHANGE", 
                                         "HEDGE -> LONG (Exit Inverse)", status, target_cash_ratio)
                    
                    # (Hedge 청산 로직 생략 - 기존과 동일)
                    current_positions = pf.get_positions()
                    for sym, info in current_positions.items():
                        if info.get('strategy_name') == "Hedge":
                            price = hedge_asset_prices.get(sym, {}).get(date, info['current_price'])
                            pf.sell(sym, price, info['shares'], date, reason="Hedge Exit")

            # 통계 집계
            regime_map = {'PANIC': 'panic_days', 'BEAR': 'bear_days', 'UNSTABLE': 'unstable_days', 'BULL': 'bull_days'}
            if regime_name in regime_map: safety_stats[regime_map[regime_name]] += 1
            if trade_halted: safety_stats['cb_halt_days'] += 1
        else:
            target_cash_ratio = 0.0
            trade_halted = False

        # 데이터 준비
        day_data = market_data[date].set_index('symbol')
        current_prices = day_data['close'].to_dict()

        # Step 1: 포지션 업데이트
        current_positions = pf.get_positions()
        for sym in list(current_positions.keys()):
            if sym in current_prices: pf.update_market_status(sym, current_prices[sym])

        # Step 2: 자산 기록
        status = pf.get_account_status()
        equity_history.append({'date': date, 'equity': status['total_equity']})

        # Step 3: 매도 (기존 로직 유지)
        for symbol in list(current_positions.keys()):
            if symbol not in day_data.index: continue
            row = day_data.loc[symbol]
            pos_info = current_positions[symbol]
            ts_mult = config.get('trailing_stop_multiplier', 2.5)
            ts_triggered, _ = pf.check_trailing_stop(symbol, row['close'], row['atr'], ts_mult)
            if row['sell_signal'] or ts_triggered:
                pf.sell(symbol, row['close'], pos_info['shares'], date, reason="Trailing Stop" if ts_triggered else "Signal Exit")

        # Step 4: 매수 (주문 차단 로그 삽입)
        status = pf.get_account_status()
        current_holdings_count = len(pf.get_positions())
        required_cash = status['total_equity'] * target_cash_ratio
        available_cash_for_trading = status['cash'] - required_cash

        if trade_halted:
            if d_logger and date.day == 1: # 로그 폭주 방지: 월 1회만 기록하거나 상태 변경 시 기록 (간소화)
                 d_logger.log_event(date_str, regime_name, current_mode, "ORDER_BLOCKED", "Circuit Breaker / Trade Halted", status, target_cash_ratio)
        elif current_holdings_count >= config['max_positions']:
            pass # 포트폴리오 가득 참 (일반적 상황)
        elif available_cash_for_trading <= 0 and target_cash_ratio > 0:
            if d_logger:
                d_logger.log_event(date_str, regime_name, current_mode, "ORDER_BLOCKED", 
                                 f"Insufficient Cash for target_cash_ratio ({target_cash_ratio*100:.0f}%)", 
                                 status, target_cash_ratio)

        if (not trade_halted) and current_holdings_count < config['max_positions'] and available_cash_for_trading > 0:
            candidates = day_data[day_data['buy_signal'] == True]
            already_owned = pf.get_positions().keys()
            candidates = candidates[~candidates.index.isin(already_owned)]
            if not candidates.empty:
                candidates = candidates.sort_values(by='rs_val', ascending=False)
                for symbol, row in candidates.iterrows():
                    status = pf.get_account_status()
                    current_available_cash = status['cash'] - (status['total_equity'] * target_cash_ratio)
                    if len(pf.get_positions()) >= config['max_positions']: break
                    if current_available_cash < row['close']: break
                    target_equity_per_stock = status['total_equity'] / config['max_positions']
                    shares_to_buy = min(int(target_equity_per_stock / row['close']), int(current_available_cash / row['close']))
                    if shares_to_buy > 0:
                        pf.buy(symbol, row['close'], shares_to_buy, date, strategy_name="Ensemble")

    # ----------------------------------------------------------------------
    # 📊 결과 집계 및 메트릭 계산
    # ----------------------------------------------------------------------
    if not equity_history:
        return None

    history_df = pd.DataFrame(equity_history).set_index('date')
    history_df.index = pd.to_datetime(history_df.index)
    history_df['daily_ret'] = history_df['equity'].pct_change().fillna(0)

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

    yearly = history_df['equity'].resample('YE').last().pct_change() * 100
    if not yearly.empty:
        first_ret = (history_df['equity'].resample('YE').last().iloc[0] - config['initial_capital']) / config[
            'initial_capital'] * 100
        yearly.iloc[0] = first_ret
    yearly_json = json.dumps({str(k.year): round(v, 2) for k, v in yearly.items()})

    # 4. 거래 기록 분석
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

    if verbose:
        analyze_results(equity_history, trades_df, config['initial_capital'])

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
        'avg_loss': avg_loss,
        'safety_stats': safety_stats
    }

def run_backtest_with_prepared_data(config, market_data, date_list, verbose=False, prev_trade_halted=None, write_market_log=False):
    """
    ✅ 랩 속도 개선용:
    - prepare_market_data()를 밖에서 1번만 실행하고, 여기서는 daily loop만 수행
    - 레짐/게이트는 매일 재계산(토글에 따라 달라짐)
    - market_analyzer 기록은 write_market_log로 제어(랩에서는 False 권장)
    """
    # 2. PortfolioDB 초기화 (속도를 위해 메모리 DB 사용)
    pf = PortfolioDB(db_path=":memory:", initial_cash=config['initial_capital'])

    equity_history = []

    # [신규] Hedge 모드 상태 변수
    current_mode = "LONG"
    mode_start_date = None
    hedge_asset_prices = {}
    if config.get('USE_HEDGE_MODE', False):
        hedge_tickers = config.get('HEDGE_TICKERS', [])
        for t in hedge_tickers:
            hedge_asset_prices[t] = get_market_index_data(t)

    # [신규] 안전장치 및 국면 통계 초기화
    safety_stats = {
        'cb_halt_days': 0,
        'vix_trigger_count': 0,
        'drawdown_trigger_count': 0,
        'breadth_low_count': 0,
        'ma_cross_bearish_count': 0,
        'panic_days': 0,
        'bear_days': 0,
        'unstable_days': 0,
        'bull_days': 0
    }

    prev_regime_name = None
    target_cash_ratio = 0.0

    for date in date_list:
        date_str = date.strftime('%Y-%m-%d')
        trade_halted = False

        if config.get('use_market_regime', True):
            if hasattr(market_analyzer, "get_market_state"):
                state = market_analyzer.get_market_state(target_date=date_str, write_log=write_market_log)
                regime_name = state["regime"]
                regime_rule = state["plan"]
                trade_halted = bool(state.get("trade_halted", False))
            else:
                regime_name, regime_rule = market_analyzer.get_market_regime(target_date=date_str)
                trade_halted = False

            if regime_name != prev_regime_name:
                if verbose:
                    print(f"📌 [{date_str}] 시장 국면 변경: {prev_regime_name} ➔ {regime_name}")
                if verbose:
                    print(f"✅ {regime_rule['description']}")
                prev_regime_name = regime_name

            if prev_trade_halted is None or trade_halted != prev_trade_halted:
                if verbose:
                    print(f"⛔ [{date_str}] trade_halted = {trade_halted} (신규 매수만 금지)")
                prev_trade_halted = trade_halted

            for strategy_name, weight in regime_rule['weights'].items():
                key = f"{strategy_name}_weight"
                config[key] = weight

            config['trailing_stop_multiplier'] = regime_rule['trailing_stop_multiplier']
            target_cash_ratio = regime_rule['target_cash_ratio']

            # [신규] Hedge 모드 판정 및 전환 로직
            if config.get('USE_HEDGE_MODE', False):
                min_days = config.get('MIN_MODE_MAINTAIN_DAYS', 5)
                # 첫 전환이거나 기간이 경과했을 때만 전환 허용
                can_switch = (mode_start_date is None) or ((date - mode_start_date).days >= min_days)

                # --- [A] Hedge 모드 진입 (LONG -> HEDGE) ---
                if regime_name in ['BEAR', 'PANIC'] and current_mode == "LONG" and can_switch:
                    current_mode = "HEDGE"
                    mode_start_date = date
                    if verbose: print(f"🛡️ [{date_str}] Hedge 모드 진입 (국면: {regime_name})")

                    # 1. 목표 헤지 금액 계산
                    ratio = config.get('HEDGE_RATIO_PANIC' if regime_name == 'PANIC' else 'HEDGE_RATIO_BEAR', 0.2)
                    status = pf.get_account_status()
                    target_hedge_value = status['total_equity'] * ratio
                    
                    # 2. 부족한 현금 확보를 위해 종목 매각 순서 결정
                    current_positions = pf.get_positions()
                    if current_positions:
                        # 매각 우선순위 파라미터 확인 (기본값: rs_low)
                        priority = config.get('HEDGE_LIQUIDATION_PRIORITY', 'rs_low')
                        
                        # 정렬 기준 데이터 생성
                        pos_list = []
                        for sym, info in current_positions.items():
                            # 인버스는 매각 대상에서 제외
                            if info.get('strategy_name') == "Hedge": continue
                            
                            # 정렬용 메트릭 계산
                            ret = (current_prices.get(sym, info['avg_price']) - info['avg_price']) / info['avg_price']
                            weight = (info['shares'] * current_prices.get(sym, info['avg_price'])) / status['total_equity']
                            rs_val = day_data.loc[sym, 'rs_val'] if sym in day_data.index else -1.0
                            age = (date - pd.to_datetime(info['entry_date'])).days
                            
                            pos_list.append({
                                'symbol': sym, 'shares': info['shares'], 'rs_low': rs_val,
                                'return_low': ret, 'weight_low': weight, 'age_high': -age # 큰 값이 먼저 오게 하기 위해 음수화
                            })
                        
                        # 설정된 우선순위에 따라 오름차순 정렬 (값이 낮을수록 먼저 매도)
                        pos_list.sort(key=lambda x: x.get(priority, 0))

                        # 3. 목표 현금이 확보될 때까지 매도 집행
                        for p in pos_list:
                            status = pf.get_account_status()
                            if status['cash'] >= target_hedge_value: break
                            
                            sym = p['symbol']
                            price = current_prices.get(sym, 0)
                            if price > 0:
                                pf.sell(sym, price, p['shares'], date, reason=f"Hedge Liquidation ({priority})")

                    # 4. 확보된 현금으로 인버스 ETF 매수
                    status = pf.get_account_status()
                    hedge_asset = config.get('HEDGE_ASSET', 'PSQ')
                    asset_price = hedge_asset_prices.get(hedge_asset, {}).get(date)
                    
                    if asset_price and asset_price > 0:
                        buy_amount = min(status['cash'], target_hedge_value)
                        shares = int(buy_amount / asset_price)
                        if shares > 0:
                            pf.buy(hedge_asset, asset_price, shares, date, strategy_name="Hedge")
                            if verbose: print(f"  💰 {hedge_asset} {shares}주 매수 (가격: ${asset_price:.2f})")

                # --- [B] LONG 모드 복귀 (HEDGE -> LONG) ---
                elif regime_name in ['BULL', 'UNSTABLE'] and current_mode == "HEDGE" and can_switch:
                    current_mode = "LONG"
                    mode_start_date = date
                    if verbose: print(f"🚀 [{date_str}] LONG 모드 복귀 (국면: {regime_name})")
                    
                    # 보유 중인 모든 Hedge 자산 매도
                    current_positions = pf.get_positions()
                    for sym, info in current_positions.items():
                        if info.get('strategy_name') == "Hedge":
                            # market_index에서 현재가 조회 (없으면 마지막 가격)
                            price = hedge_asset_prices.get(sym, {}).get(date, info['current_price'])
                            pf.sell(sym, price, info['shares'], date, reason="Hedge Exit")
                            if verbose: print(f"  💸 {sym} 전량 매도 (가격: ${price:.2f})")

            # [신규] 통계 집계
            regime_map = {'PANIC': 'panic_days', 'BEAR': 'bear_days', 'UNSTABLE': 'unstable_days', 'BULL': 'bull_days'}
            if regime_name in regime_map:
                safety_stats[regime_map[regime_name]] += 1
            
            if trade_halted:
                safety_stats['cb_halt_days'] += 1
            
            triggers = state.get("triggers", {})
            if triggers.get("vix_breakout"): safety_stats['vix_trigger_count'] += 1
            if triggers.get("drawdown"): safety_stats['drawdown_trigger_count'] += 1
            if triggers.get("breadth_low"): safety_stats['breadth_low_count'] += 1
            if triggers.get("ma_cross_bearish"): safety_stats['ma_cross_bearish_count'] += 1
        else:
            target_cash_ratio = 0.0
            trade_halted = False

        day_data = market_data[date].set_index('symbol')
        current_prices = day_data['close'].to_dict()

        # Step 1: 포지션 상태 업데이트
        current_positions = pf.get_positions()
        for sym in list(current_positions.keys()):
            if sym in current_prices:
                pf.update_market_status(sym, current_prices[sym])

        # Step 2: 자산 기록
        status = pf.get_account_status()
        equity_history.append({'date': date, 'equity': status['total_equity']})

        # Step 3: 매도
        current_positions = pf.get_positions()
        for symbol in list(current_positions.keys()):
            if symbol not in day_data.index:
                continue

            row = day_data.loc[symbol]
            current_price = row['close']
            current_atr = row['atr']
            pos_info = current_positions[symbol]

            ts_mult = config.get('trailing_stop_multiplier', 2.5)
            ts_triggered, _ = pf.check_trailing_stop(symbol, current_price, current_atr, ts_mult)

            signal_sell = row['sell_signal']
            if signal_sell or ts_triggered:
                reason = "Trailing Stop" if ts_triggered else "Signal Exit"
                pf.sell(symbol, current_price, pos_info['shares'], date, reason=reason)

        # Step 4: 매수 (trade_halted면 신규 매수 금지)
        status = pf.get_account_status()
        current_holdings_count = len(pf.get_positions())

        current_total_equity = status['total_equity']
        required_cash = current_total_equity * target_cash_ratio
        available_cash_for_trading = status['cash'] - required_cash

        if (not trade_halted) and current_holdings_count < config['max_positions'] and available_cash_for_trading > 0:
            candidates = day_data[day_data['buy_signal'] == True]
            already_owned = pf.get_positions().keys()
            candidates = candidates[~candidates.index.isin(already_owned)]

            if not candidates.empty:
                candidates = candidates.sort_values(by='rs_val', ascending=False)
                for symbol, row in candidates.iterrows():
                    status = pf.get_account_status()
                    current_available_cash = status['cash'] - required_cash

                    if len(pf.get_positions()) >= config['max_positions']:
                        break
                    if current_available_cash < row['close']:
                        break

                    target_equity_per_stock = status['total_equity'] / config['max_positions']
                    shares_to_buy = int(target_equity_per_stock / row['close'])

                    max_affordable = int(current_available_cash / row['close'])
                    shares_to_buy = min(shares_to_buy, max_affordable)

                    if shares_to_buy > 0:
                        pf.buy(symbol, row['close'], shares_to_buy, date, strategy_name="Ensemble")

    # 결과 집계 (기존 run_backtest_with_config 하단과 동일 로직)
    if not equity_history:
        return None

    history_df = pd.DataFrame(equity_history).set_index('date')
    history_df.index = pd.to_datetime(history_df.index)
    history_df['daily_ret'] = history_df['equity'].pct_change().fillna(0)

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

    yearly = history_df['equity'].resample('YE').last().pct_change() * 100
    if not yearly.empty:
        first_ret = (history_df['equity'].resample('YE').last().iloc[0] - config['initial_capital']) / config['initial_capital'] * 100
        yearly.iloc[0] = first_ret
    yearly_json = json.dumps({str(k.year): round(v, 2) for k, v in yearly.items()})

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

    if verbose:
        analyze_results(equity_history, trades_df, config['initial_capital'])

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
        'avg_loss': avg_loss,
        'safety_stats': safety_stats
    }


def analyze_results(equity_history, trades_df, initial_capital):
    """
    상세 분석 리포트 출력 함수 (DB 버전 호환)
    - equity_history: [{'date':..., 'equity':...}] 형태의 리스트
    - trades_df: trade_history 테이블에서 조회한 DataFrame
    """
    if not equity_history:
        return

    history_df = pd.DataFrame(equity_history).set_index('date')
    history_df.index = pd.to_datetime(history_df.index)
    history_df['daily_ret'] = history_df['equity'].pct_change().fillna(0)

    final = history_df['equity'].iloc[-1]
    total_ret = (final - initial_capital) / initial_capital * 100

    roll_max = history_df['equity'].cummax()
    mdd = ((history_df['equity'] - roll_max) / roll_max).min() * 100

    days = (history_df.index[-1] - history_df.index[0]).days
    cagr = ((final / initial_capital) ** (365 / days) - 1) * 100 if days > 0 else 0

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

    if not trades_df.empty:
        total = len(trades_df)
        wins = len(trades_df[trades_df['profit'] > 0])
        win_rate = wins / total * 100

        gross_profit = trades_df[trades_df['profit'] > 0]['profit'].sum()
        gross_loss = abs(trades_df[trades_df['profit'] <= 0]['profit'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss != 0 else 99.9

        print(f"🔄 총 거래수 : {total}회")
        print(f"🎯 승률     : {win_rate:.2f}%")
        print(f"⚖️ 손익비   : {profit_factor:.2f}")

        best = trades_df.loc[trades_df['profit'].idxmax()]
        worst = trades_df.loc[trades_df['profit'].idxmin()]

        print(f"🏆 Best : {best['symbol']} (${best['profit']:,.0f})")
        print(f"💀 Worst: {worst['symbol']} (${worst['profit']:,.0f})")

    print("-" * 50)
    print("[연도별 수익률]")
    yearly = history_df['equity'].resample('YE').last().pct_change() * 100
    if not yearly.empty:
        first_year_ret = (history_df['equity'].resample('YE').last().iloc[0] - initial_capital) / initial_capital * 100
        yearly.iloc[0] = first_year_ret

    for y, r in yearly.items():
        print(f"{y.year}: {r:6.2f}%")
    print("=" * 50)
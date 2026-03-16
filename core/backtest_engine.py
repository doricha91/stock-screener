import pandas as pd
import numpy as np
import json
import market_analyzer
import csv
from multiprocessing import Pool, cpu_count
from screener import data_manager, strategy, indicator
from screener.portfolio import PortfolioDB
from pathlib import Path
from core.target_portfolio_state import (
    build_target_portfolio_state, 
    CurrentPortfolioState, 
    evaluate_rebalance_need,
    get_cash_policy_status
)


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


def process_single_stock(args):
    """개별 종목 데이터 처리 및 신호 생성"""
    symbol, df, config = args
    global spy_global

    try:
        if len(df) < 130:
            return None
        df = df.sort_index()

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
        return None


def prepare_market_data(config):
    """데이터 로드 및 신호 생성 통합 준비"""
    target_tickers = config.get('target_tickers', [])
    if not target_tickers:
        conn = market_analyzer.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT symbol FROM tickers WHERE listing_board = 'NASDAQ100'")
        rows = cursor.fetchall()
        target_tickers = [row[0] for row in rows]
        conn.close()

    if not target_tickers:
        target_tickers = data_manager.get_ticker_list()

    bulk_start = '2021-01-01'
    load_tickers = list(set(target_tickers + ['SPY', 'QQQ', '^VIX']))
    df_all = data_manager.get_all_price_data_bulk(start_date=bulk_start, tickers=load_tickers)
    
    if df_all.empty:
        return {}, []

    spy_df = df_all[df_all['symbol'] == 'SPY'].set_index('date').sort_index()
    if spy_df.empty:
        spy_df = df_all[df_all['symbol'] == df_all['symbol'].iloc[0]].set_index('date').sort_index()

    init_worker(spy_df)
    tasks = [(symbol, group.set_index('date').sort_index(), config) 
             for symbol, group in df_all.groupby('symbol') if symbol in target_tickers]

    all_signals = []
    for task in tasks:
        res = process_single_stock(task)
        if res is not None: all_signals.append(res)

    if not all_signals:
        return {}, []

    full_df = pd.concat(all_signals)
    full_df['date'] = pd.to_datetime(full_df['date'])
    start_date, end_date = config.get('start_date', '2021-01-01'), config.get('end_date', '2025-12-31')
    full_df = full_df[(full_df['date'] >= start_date) & (full_df['date'] <= end_date)].sort_values(['date', 'symbol'])

    return {date: data for date, data in full_df.groupby('date')}, full_df['date'].unique()


def run_backtest_with_config(config, verbose=False):
    """백테스트 메인 엔진"""
    market_data, date_list = prepare_market_data(config)
    if not market_data: return None

    pf = PortfolioDB(db_path=":memory:", initial_cash=config['initial_capital'])
    equity_history = []
    current_mode = "LONG"
    mode_start_date = None
    hedge_asset_prices = {}
    if config.get('USE_HEDGE_MODE', False):
        for t in config.get('HEDGE_TICKERS', ['PSQ']):
            hedge_asset_prices[t] = get_market_index_data(t)

    safety_stats = {
        'panic_days': 0, 'bear_days': 0, 'unstable_days': 0, 'bull_days': 0,
        'mode_change_count': 0, 'regime_change_count': 0, 'order_blocked_count': 0, 'cb_halt_days': 0
    }

    d_logger = None
    if config.get('enable_decision_logging', False):
        from backtesting.logger import DecisionLogger
        d_logger = DecisionLogger(run_name=config.get('run_id', 'backtest'))

    prev_regime_name = None
    target_cash_ratio = 0.0

    for i, date in enumerate(date_list):
        date_str = date.strftime('%Y-%m-%d')
        trade_halted = False
        regime_name = "UNKNOWN"

        if config.get('use_market_regime', True):
            state = market_analyzer.get_market_state(target_date=date_str, write_log=False)
            regime_name, regime_rule = state["regime"], state["plan"]
            trade_halted = bool(state.get("trade_halted", False))

            if regime_name != prev_regime_name:
                safety_stats['regime_change_count'] += 1
                if d_logger:
                    status = pf.get_account_status()
                    cp_status = get_cash_policy_status(status['cash'], status['total_equity'], target_cash_ratio)
                    d_logger.log_event(
                        date_str, regime_name, current_mode, "REGIME_CHANGE", 
                        f"{prev_regime_name} -> {regime_name}", status, target_cash_ratio,
                        required_cash_buffer=cp_status['required_cash_buffer'],
                        available_buying_power=cp_status['available_buying_power'],
                        is_violating_buffer=cp_status['is_violating_buffer']
                    )
                prev_regime_name = regime_name

            for strat, weight in regime_rule['weights'].items(): config[f"{strat}_weight"] = weight
            config['trailing_stop_multiplier'] = regime_rule['trailing_stop_multiplier']
            target_cash_ratio = regime_rule['target_cash_ratio']

            if config.get('USE_HEDGE_MODE', False):
                min_days = config.get('MIN_MODE_MAINTAIN_DAYS', 5)
                can_switch = (mode_start_date is None) or ((date - mode_start_date).days >= min_days)

                if regime_name in ['BEAR', 'PANIC'] and current_mode == "LONG" and can_switch:
                    current_mode = "HEDGE"; mode_start_date = date; safety_stats['mode_change_count'] += 1
                    ratio = config.get('HEDGE_RATIO_PANIC' if regime_name == 'PANIC' else 'HEDGE_RATIO_BEAR', 0.2)
                    status = pf.get_account_status(); target_val = status['total_equity'] * ratio
                    
                    day_data = market_data[date].set_index('symbol')
                    current_prices = day_data['close'].to_dict()
                    positions = pf.get_positions()
                    if positions:
                        prio = config.get('HEDGE_LIQUIDATION_PRIORITY', 'rs_low')
                        pos_list = []
                        for s, info in positions.items():
                            if info.get('strategy_name') == "Hedge": continue
                            rs = day_data.loc[s, 'rs_val'] if s in day_data.index else -1.0
                            pos_list.append({'symbol': s, 'shares': info['shares'], 'rs_low': rs})
                        pos_list.sort(key=lambda x: x.get(prio, 0))
                        for p in pos_list:
                            if pf.get_account_status()['cash'] >= target_val: break
                            pf.sell(p['symbol'], current_prices.get(p['symbol'], 0), p['shares'], date, reason="Hedge Liq")

                    h_asset = config.get('HEDGE_ASSET', 'PSQ')
                    h_price = hedge_asset_prices.get(h_asset, {}).get(date)
                    if h_price:
                        shares = int(min(pf.get_account_status()['cash'], target_val) / h_price)
                        if shares > 0: pf.buy(h_asset, h_price, shares, date, strategy_name="Hedge")

                elif regime_name in ['BULL', 'UNSTABLE'] and current_mode == "HEDGE" and can_switch:
                    current_mode = "LONG"; mode_start_date = date
                    for s, info in pf.get_positions().items():
                        if info.get('strategy_name') == "Hedge":
                            pf.sell(s, hedge_asset_prices.get(s, {}).get(date, info['current_price']), info['shares'], date, reason="Hedge Exit")

            regime_map = {'PANIC': 'panic_days', 'BEAR': 'bear_days', 'UNSTABLE': 'unstable_days', 'BULL': 'bull_days'}
            if regime_name in regime_map: safety_stats[regime_map[regime_name]] += 1
            if trade_halted: safety_stats['cb_halt_days'] += 1

        day_data = market_data[date].set_index('symbol')
        current_prices = day_data['close'].to_dict()
        
        for s in list(pf.get_positions().keys()):
            if s in current_prices: pf.update_market_status(s, current_prices[s])
        
        equity_history.append({'date': date, 'equity': pf.get_account_status()['total_equity']})

        # [MFU1-C] 1. 목표 포트폴리오 상태 계산 (Target State)
        candidate_rows = []
        for s, row in day_data.iterrows():
            # [정책 해석] TargetPortfolioState의 entry_signal은 현재 엔진의 'buy_signal'과 매핑함.
            # 이는 기존 엔진이 '매수 가능 후보'라고 판단한 종목 리스트의 의미를 최대한 보존하기 위한 보수적 연결임.
            candidate_rows.append({
                'symbol': s,
                'score': row.get('score', 0.0),
                'rs_val': row.get('rs_val', 0.0),
                'entry_signal': bool(row.get('buy_signal', False))
            })
        
        target_state = build_target_portfolio_state(
            market_state=regime_name,
            candidate_rows=candidate_rows,
            config=config
        )

        # [MFU1-C] 2. 현재 포트폴리오 상태 구성 (Current State)
        status = pf.get_account_status()
        positions = pf.get_positions()
        
        current_symbols = [s for s, info in positions.items() if info.get('strategy_name') != "Hedge"]
        hedge_symbols = [s for s, info in positions.items() if info.get('strategy_name') == "Hedge"]
        
        total_equity = status['total_equity']
        current_cash_ratio = status['cash'] / total_equity if total_equity > 0 else 1.0
        
        hedge_value = 0.0
        for s in hedge_symbols:
            pos_info = positions[s]
            hedge_value += pos_info['shares'] * pos_info['current_price']
        current_hedge_ratio = hedge_value / total_equity if total_equity > 0 else 0.0

        current_state = CurrentPortfolioState(
            current_symbols=current_symbols,
            current_cash_ratio=current_cash_ratio,
            current_hedge_ratio=current_hedge_ratio,
            hedge_symbols=hedge_symbols
        )

        # [MFU1-C] 3. 리밸런싱 판정 (Rebalance Decision)
        decision = evaluate_rebalance_need(current_state, target_state, config)

        # [MFU2-2] 현금 정책 상태 계산 (Shallow Integration)
        cp_status = get_cash_policy_status(status['cash'], total_equity, target_state.target_cash_ratio)

        # [MFU1-C] 4. 의사결정 로깅
        if d_logger:
            d_logger.log_event(
                date=date_str,
                regime=regime_name,
                mode=current_mode,
                event="DAILY_CHECK",
                details=f"TargetSlots: {target_state.target_long_slots}",
                status=status,
                target_cash_ratio=target_state.target_cash_ratio,
                rebalance_needed=decision.rebalance_needed,
                rebalance_reason="|".join(decision.rebalance_reason),
                target_symbols="|".join(target_state.target_symbols),
                current_symbols="|".join(current_symbols),
                required_cash_buffer=cp_status['required_cash_buffer'],
                available_buying_power=cp_status['available_buying_power'],
                is_violating_buffer=cp_status['is_violating_buffer']
            )

        for s, info in list(pf.get_positions().items()):
            if s not in day_data.index: continue
            row = day_data.loc[s]; ts_mult = config.get('trailing_stop_multiplier', 2.5)
            ts_trig, _ = pf.check_trailing_stop(s, row['close'], row['atr'], ts_mult)
            if row['sell_signal'] or ts_trig: pf.sell(s, row['close'], info['shares'], date, reason="Exit")

        status = pf.get_account_status(); req_cash = status['total_equity'] * target_cash_ratio
        if (not trade_halted) and len(pf.get_positions()) < config['max_positions'] and (status['cash'] - req_cash) > 0:
            candidates = day_data[day_data['buy_signal'] == True]
            candidates = candidates[~candidates.index.isin(pf.get_positions().keys())].sort_values(by='rs_val', ascending=False)
            for s, row in candidates.iterrows():
                cash = pf.get_account_status()['cash'] - req_cash
                if len(pf.get_positions()) >= config['max_positions'] or cash < row['close']: break
                shares = min(int((status['total_equity']/config['max_positions'])/row['close']), int(cash/row['close']))
                if shares > 0: pf.buy(s, row['close'], shares, date, strategy_name="Ensemble")
        elif (status['cash'] - req_cash) <= 0 and target_cash_ratio > 0:
            safety_stats['order_blocked_count'] += 1

    results = calculate_metrics(equity_history, pf, config, safety_stats)
    if verbose: analyze_results(equity_history, pf, config)
    if 'run_id' in config: save_run_results(config, results)
    return results


def calculate_metrics(equity_history, pf, config, safety_stats):
    """지표 계산 공통 로직"""
    history_df = pd.DataFrame(equity_history).set_index('date')
    history_df['daily_ret'] = history_df['equity'].pct_change().fillna(0)
    final_equity = history_df['equity'].iloc[-1]
    total_ret = (final_equity - config['initial_capital']) / config['initial_capital'] * 100
    mdd = ((history_df['equity'] - history_df['equity'].cummax()) / history_df['equity'].cummax()).min() * 100
    days = (history_df.index[-1] - history_df.index[0]).days
    cagr = ((final_equity / config['initial_capital']) ** (365 / max(days, 1)) - 1) * 100
    std = history_df['daily_ret'].std() * np.sqrt(252)
    sharpe = (cagr / 100) / max(std, 0.0001)

    conn = pf.conn; trades_df = pd.read_sql("SELECT * FROM trade_history WHERE type='SELL'", conn)
    total_trades = len(trades_df)
    win_rate = 0.0
    profit_factor = 0.0
    
    avg_win = 0.0
    avg_loss = 0.0
    
    if total_trades > 0:
        win_trades = trades_df[trades_df['profit'] > 0]
        loss_trades = trades_df[trades_df['profit'] <= 0]
        win_rate = len(win_trades) / total_trades * 100
        
        gross_profit = win_trades['profit'].sum()
        gross_loss = abs(loss_trades['profit'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 99.9
        
        avg_win = win_trades['profit'].mean() if not win_trades.empty else 0.0
        avg_loss = abs(loss_trades['profit'].mean()) if not loss_trades.empty else 0.0

    # 연도별 수익률 계산
    history_df['equity'] = pd.to_numeric(history_df['equity'])
    yearly = history_df['equity'].resample('YE').last().pct_change() * 100
    if not yearly.empty:
        first_ret = (history_df['equity'].resample('YE').last().iloc[0] - config['initial_capital']) / config['initial_capital'] * 100
        yearly.iloc[0] = first_ret
    yearly_json = json.dumps({str(k.year): round(v, 2) for k, v in yearly.items()})

    return {
        'return': total_ret, 'cagr': cagr, 'mdd': mdd, 'final_equity': final_equity, 'sharpe': sharpe,
        'total_trades': total_trades, 'win_rate': win_rate, 'profit_factor': profit_factor,
        'avg_win': avg_win, 'avg_loss': avg_loss, 'yearly_json': yearly_json,
        'safety_stats': safety_stats,
        'period': f"{history_df.index[0].date()} ~ {history_df.index[-1].date()}"
    }


def analyze_results(equity_history, pf, config):
    """상세 리포트 출력"""
    history_df = pd.DataFrame(equity_history).set_index('date')
    final = history_df['equity'].iloc[-1]; total_ret = (final - config['initial_capital']) / config['initial_capital'] * 100
    mdd = ((history_df['equity'] - history_df['equity'].cummax()) / history_df['equity'].cummax()).min() * 100
    print("\n" + "=" * 50); print(f"📊 [최종 백테스트 상세 리포트]"); print("=" * 50)
    print(f"💰 자산: ${config['initial_capital']:,.0f} ➔ ${final:,.0f}"); print(f"🚀 수익률: {total_ret:.2f}% | MDD: {mdd:.2f}%")
    
    conn = pf.conn; trades_df = pd.read_sql("SELECT * FROM trade_history WHERE type='SELL'", conn)
    if not trades_df.empty:
        total = len(trades_df); wins = len(trades_df[trades_df['profit'] > 0])
        gross_profit = trades_df[trades_df['profit'] > 0]['profit'].sum()
        gross_loss = abs(trades_df[trades_df['profit'] <= 0]['profit'].sum())
        pf_val = gross_profit / gross_loss if gross_loss > 0 else 99.9
        print(f"🔄 거래: {total}회 | 승률: {wins/total*100:.2f}% | PF: {pf_val:.2f}")
    print("=" * 50)


def save_run_results(config, results):
    """실행 메타데이터와 성과 요약 저장"""
    import datetime
    run_id = config.get("run_id", "unknown")
    meta_dir, summary_dir = Path("outputs/meta"), Path("outputs/summary")
    meta_dir.mkdir(parents=True, exist_ok=True); summary_dir.mkdir(parents=True, exist_ok=True)
    
    meta_data = {
        "run_id": run_id, "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "params": { k: config.get(k) for k in ["USE_HEDGE_MODE", "HEDGE_RATIO_BEAR", "HEDGE_RATIO_PANIC", "MIN_MODE_MAINTAIN_DAYS", "HEDGE_LIQUIDATION_PRIORITY"] }
    }
    with open(meta_dir / f"meta_{run_id}.json", "w", encoding="utf-8") as f: json.dump(meta_data, f, indent=4, ensure_ascii=False)
    
    summary_file = summary_dir / f"summary_{run_id}.csv"
    headers = ['run_id', 'use_hedge_mode', 'hedge_ratio_bear', 'hedge_ratio_panic', 'min_maintain_days', 'total_return', 'cagr', 'mdd', 'sharpe', 'profit_factor', 'total_trades', 'mode_change_count', 'regime_change_count']
    row = {
        'run_id': run_id, 
        'use_hedge_mode': config.get('USE_HEDGE_MODE'), 
        'hedge_ratio_bear': config.get('HEDGE_RATIO_BEAR'), 
        'hedge_ratio_panic': config.get('HEDGE_RATIO_PANIC'),
        'min_maintain_days': config.get('MIN_MODE_MAINTAIN_DAYS'), 
        'total_return': round(results.get('return', 0), 2), 
        'cagr': round(results.get('cagr', 0), 2),
        'mdd': round(results.get('mdd', 0), 2), 
        'sharpe': round(results.get('sharpe', 0), 2), 
        'profit_factor': round(results.get('profit_factor', 0), 2),
        'total_trades': results.get('total_trades', 0),
        'mode_change_count': results.get('safety_stats', {}).get('mode_change_count', 0), 
        'regime_change_count': results.get('safety_stats', {}).get('regime_change_count', 0)
    }
    with open(summary_file, "w", encoding="utf-8-sig", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers); writer.writeheader(); writer.writerow(row)
    print(f"📊 [실험 결과 저장 완료] ID: {run_id}")

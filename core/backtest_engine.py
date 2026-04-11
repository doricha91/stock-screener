import pandas as pd
import numpy as np
import json
import market_analyzer
import csv
from multiprocessing import Pool, cpu_count
from core.decision_core import compute_candidate_score, is_enterable_candidate
from screener import data_manager, strategy, indicator
from screener.portfolio import PortfolioDB
from pathlib import Path
from core.target_portfolio_state import (
    build_target_portfolio_state, 
    CurrentPortfolioState, 
    evaluate_rebalance_need,
    get_cash_policy_status
)
from backtesting.reason_codes import ReasonCode


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

        # 점수 합산 가중치 정의
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
        }

        # 하이브리드 코어 모듈을 사용하여 DataFrame 전체에 대해 벡터 점수 계산 수행
        df['score'], _ = compute_candidate_score(df, weights)
        
        # RS 가중치 별도 합산 (현재 signal_rs 형태가 아니므로 벡터 연산으로 기존 로직 유지)
        rs_weight = context.get('rs_weight', 0.0)
        if rs_weight > 0:
            # RS가 0보다 큰 경우에만 가중치 합산 (벡터 연산)
            df['score'] += (df['rs_val'] > 0).astype(float) * rs_weight

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


def is_rebalance_day(date: pd.Timestamp, freq: str) -> bool:
    """
    현재 날짜가 설정된 리밸런싱 주기에 해당하는지 판별합니다.
    
    Args:
        date: 현재 시뮬레이션 날짜
        freq: 'D' (Daily), 'W' (Weekly), 'M' (Monthly), 'Q' (Quarterly)
        
    Returns:
        bool: 리밸런싱 수행 여부
    """
    if freq == 'D':
        return True
    elif freq == 'W':
        # 주의 마지막 거래일(금요일 또는 데이터상 마지막 날) 판별
        # 간단하게 금요일(4)로 처리하거나, pandas의 WeekOfMonth 등을 활용할 수 있음
        return date.weekday() == 4
    elif freq == 'M':
        # 월말 판별
        return date.is_month_end
    elif freq == 'Q':
        # 분기말 판별
        return date.is_quarter_end
    return True


def run_backtest_with_config(config, verbose=False):
    """백테스트 메인 엔진"""
    market_data, date_list = prepare_market_data(config)
    if not market_data: return None

    # 원본 설정을 보존하여 매일 새로운 국면 설정을 적용할 때 템플릿으로 사용 (AGENTS.md SSOT 준수)
    base_run_config = config.copy()

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
        'mode_change_count': 0, 'regime_change_count': 0, 'order_blocked_count': 0, 'cb_halt_days': 0,
        # MFU2-4: Cash Policy Summary Stats
        'cash_policy_violation_days': 0,
        'order_skipped_count': 0,
        'sum_current_cash_ratio': 0.0,
        'sum_target_cash_ratio': 0.0,
        'sum_available_buying_power': 0.0,
        'min_cash_ratio': 1.0,
        'max_cash_ratio': 0.0,
        'total_days': 0
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
            regime_name = state["regime"]
            trade_halted = bool(state.get("trade_halted", False))

            # [신규] 국면별 동적 Config 덮어쓰기 (SSOT 준수)
            from core.config_factory import get_regime_config
            config = get_regime_config(regime_name, config)

            if regime_name != prev_regime_name:
                safety_stats['regime_change_count'] += 1
                if d_logger:
                    status = pf.get_account_status()
                    # config에서 업데이트된 target_cash_ratio 사용
                    target_cash_ratio = config.get('target_cash_ratio', 0.0)
                    cp_status = get_cash_policy_status(status['cash'], status['total_equity'], target_cash_ratio)
                    d_logger.log_event(
                        date_str, regime_name, current_mode, "REGIME_CHANGE", 
                        f"{prev_regime_name} -> {regime_name}", status, target_cash_ratio,
                        required_cash_buffer=cp_status['required_cash_buffer'],
                        available_buying_power=cp_status['available_buying_power'],
                        is_violating_buffer=cp_status['is_violating_buffer']
                    )
                prev_regime_name = regime_name

            # config에서 업데이트된 값 사용
            target_cash_ratio = config.get('target_cash_ratio', 0.0)

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
                            pf.sell(p['symbol'], current_prices.get(p['symbol'], 0), p['shares'], date, reason=ReasonCode.HEDGE_LIQUIDATION)

                    h_asset = config.get('HEDGE_ASSET', 'PSQ')
                    h_price = hedge_asset_prices.get(h_asset, {}).get(date)
                    if h_price:
                        shares = int(min(pf.get_account_status()['cash'], target_val) / h_price)
                        if shares > 0: pf.buy(h_asset, h_price, shares, date, strategy_name="Hedge", reason=ReasonCode.HEDGE_ENTER)

                elif regime_name in ['BULL', 'UNSTABLE'] and current_mode == "HEDGE" and can_switch:
                    current_mode = "LONG"; mode_start_date = date
                    for s, info in pf.get_positions().items():
                        if info.get('strategy_name') == "Hedge":
                            pf.sell(s, hedge_asset_prices.get(s, {}).get(date, info['current_price']), info['shares'], date, reason=ReasonCode.HEDGE_EXIT)

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
            absolute_cash=float(status['cash']),
            shares={s: int(info['shares']) for s, info in positions.items()},
            avg_price={s: float(info['avg_price']) for s, info in positions.items()},
            highest_prices={s: float(info.get('highest_price', info['avg_price'])) for s, info in positions.items()},
            hedge_symbols=hedge_symbols
        )

        # [MFU1-C] 3. 리밸런싱 판정 (Rebalance Decision)
        decision = evaluate_rebalance_need(current_state, target_state, config)

        # [MFU2-2] 현금 정책 상태 계산
        cp_status = get_cash_policy_status(status['cash'], total_equity, target_state.target_cash_ratio)
        
        # MFU2-4: 일일 통계 업데이트
        safety_stats['total_days'] += 1
        safety_stats['sum_current_cash_ratio'] += cp_status['current_cash_ratio']
        safety_stats['sum_target_cash_ratio'] += cp_status['target_cash_ratio']
        safety_stats['sum_available_buying_power'] += cp_status['available_buying_power']
        safety_stats['min_cash_ratio'] = min(safety_stats['min_cash_ratio'], cp_status['current_cash_ratio'])
        safety_stats['max_cash_ratio'] = max(safety_stats['max_cash_ratio'], cp_status['current_cash_ratio'])
        if cp_status['is_violating_buffer']:
            safety_stats['cash_policy_violation_days'] += 1

        # MFU2-4: 현금 정책 상태 요약 생성
        if cp_status['is_violating_buffer']:
            cp_reason = "BUFFER_VIOLATED"
        elif cp_status['available_buying_power'] <= 0:
            cp_reason = "BUY_BLOCKED"
        elif cp_status['available_buying_power'] < total_equity * 0.01: # 임의의 낮은 기준 (1%)
            cp_reason = "LIMITED_BUYING_POWER"
        else:
            cp_reason = "CASH_POLICY_OK"

        # [MFU1-C] 4. 의사결정 로깅
        if d_logger:
            d_logger.log_event(
                date=date_str,
                regime=regime_name,
                mode=current_mode,
                event="DAILY_CHECK",
                details=f"TargetSlots: {target_state.target_long_slots} | CP_Status: {cp_reason}",
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

        # [MFU2-3] 신규 매수 집행 제약 반영
        remaining_bp = cp_status['available_buying_power']

        for s, info in list(pf.get_positions().items()):
            if s not in day_data.index: continue
            row = day_data.loc[s]; ts_mult = config.get('trailing_stop_multiplier', 2.5)
            ts_trig, _ = pf.check_trailing_stop(s, row['close'], row['atr'], ts_mult)
            
            if row['sell_signal']:
                pf.sell(s, row['close'], info['shares'], date, reason=ReasonCode.EXIT_SIGNAL)
            elif ts_trig:
                pf.sell(s, row['close'], info['shares'], date, reason=ReasonCode.EXIT_TRAILING_STOP)

        # 신규 매수 루프 (리밸런싱 주기에만 실행)
        rebal_freq = config.get('REBALANCE_FREQUENCY', 'D')
        is_rebal = is_rebalance_day(date, rebal_freq)

        if (not trade_halted) and is_rebal and len(pf.get_positions()) < config['max_positions']:
            # [MFU 4-2] 교체 매매(Switching)를 위한 보유 종목 재평가
            current_pos_scores = []
            positions = pf.get_positions()
            
            # 현재 적용 중인 전략 가중치 재구성
            active_weights = {
                'turtle': config.get('turtle_weight', 1.0),
                'rsi': config.get('rsi_weight', 1.0),
                'sma': config.get('sma_weight', 1.0),
                'bbands': config.get('bbands_weight', 1.0),
                'macd': config.get('macd_weight', 1.0),
                'bbs': config.get('bbs_weight', 1.0),
                'dema': config.get('dema_weight', 1.0),
                'obv': config.get('obv_weight', 0.5),
                'mfi': config.get('mfi_weight', 0.5),
                'vol_spike': config.get('vol_spike_weight', 0.5),
            }

            for s, info in positions.items():
                if info.get('strategy_name') == "Hedge": continue
                if s in day_data.index:
                    row = day_data.loc[s]
                    score, _ = compute_candidate_score(row, active_weights)
                    rs_weight = config.get('rs_weight', 0.0)
                    if rs_weight > 0 and row.get('rs_val', 0) > 0:
                        score += rs_weight
                    
                    p_ret = (info['current_price'] - info['avg_price']) / info['avg_price'] if info['avg_price'] > 0 else 0
                    current_pos_scores.append({
                        'symbol': s, 'score': score, 'return': p_ret, 
                        'shares': info['shares'], 'price': info['current_price']
                    })
            
            # 점수 낮은 순으로 정렬
            current_pos_scores.sort(key=lambda x: x['score'])

            if remaining_bp <= 0 and not current_pos_scores:
                if target_cash_ratio > 0 and d_logger:
                    d_logger.log_event(
                        date=date_str, regime=regime_name, mode=current_mode,
                        event="ORDER_BLOCKED", details=f"Cash policy restriction. BP: {remaining_bp:.2f}",
                        status=status, target_cash_ratio=target_state.target_cash_ratio,
                        rebalance_reason=ReasonCode.BUY_BLOCKED_BY_CASH_BUFFER,
                        required_cash_buffer=cp_status['required_cash_buffer'],
                        available_buying_power=cp_status['available_buying_power'],
                        is_violating_buffer=cp_status['is_violating_buffer']
                    )
                if remaining_bp <= 0 and target_cash_ratio > 0:
                    safety_stats['order_blocked_count'] += 1
            else:
                # 1. buy_signal이 True인 후보들 추출
                candidates = day_data[day_data['buy_signal'] == True]
                
                if not candidates.empty:
                    # 2. [MFU3] 진입 차단(Reject) 로그 추가를 위한 필터링 단계 분리
                    valid_mask = is_enterable_candidate(candidates['score'], config['score_threshold'], regime_name)
                    
                    # 탈락 사유 기록
                    rejected = candidates[~valid_mask]
                    if d_logger and not rejected.empty:
                        for s, r_row in rejected.iterrows():
                            if regime_name == "PANIC":
                                r_reason = ReasonCode.REJECT_BY_PANIC
                            elif r_row['score'] < config['score_threshold']:
                                r_reason = ReasonCode.REJECT_LOW_SCORE
                            else:
                                r_reason = "REJECT_OTHER"
                            
                            d_logger.log_event(
                                date=date_str, regime=regime_name, mode=current_mode,
                                event="ENTRY_REJECTED", details=f"Symbol: {s}, Score: {r_row['score']:.2f}",
                                status=pf.get_account_status(), target_cash_ratio=target_state.target_cash_ratio,
                                rebalance_reason=r_reason
                            )
                    
                    candidates = candidates[valid_mask]
                
                candidates = candidates[~candidates.index.isin(pf.get_positions().keys())].sort_values(by='rs_val', ascending=False)
                
                for s, row in candidates.iterrows():
                    if len(pf.get_positions()) >= config['max_positions']:
                        if d_logger:
                            d_logger.log_event(
                                date=date_str, regime=regime_name, mode=current_mode,
                                event="ORDER_SKIPPED", details=f"Max positions ({config['max_positions']}) reached. Skipping {s}",
                                status=pf.get_account_status(), target_cash_ratio=target_state.target_cash_ratio,
                                rebalance_reason=ReasonCode.ORDER_SKIPPED_MAX_POS
                            )
                        break
                        
                    # 현금 부족 시 교체 매매 판단
                    can_buy = remaining_bp >= row['close']
                    switched = False

                    if not can_buy and current_pos_scores:
                        premium = config.get('SWITCHING_PREMIUM', 1.0)
                        target_sell = current_pos_scores[0]
                        
                        if row['score'] > (target_sell['score'] + premium) and target_sell['return'] < 0:
                            s_to_sell = target_sell['symbol']
                            sell_price = day_data.loc[s_to_sell, 'close'] if s_to_sell in day_data.index else target_sell['price']
                            
                            pf.sell(s_to_sell, sell_price, target_sell['shares'], date, reason=ReasonCode.SWITCH_OUT)
                            
                            if d_logger:
                                d_logger.log_event(
                                    date=date_str, regime=regime_name, mode=current_mode,
                                    event="POSITION_SWITCHED", details=f"Sell {s_to_sell} (Score: {target_sell['score']:.1f}, Ret: {target_sell['return']*100:.1f}%) to Buy {s} (Score: {row['score']:.1f})",
                                    status=pf.get_account_status(), target_cash_ratio=target_state.target_cash_ratio,
                                    rebalance_reason=ReasonCode.SWITCH_OUT,
                                    required_cash_buffer=cp_status['required_cash_buffer'],
                                    available_buying_power=pf.get_account_status()['cash'] - cp_status['required_cash_buffer'],
                                    is_violating_buffer=False
                                )
                            
                            new_status = pf.get_account_status()
                            new_cp = get_cash_policy_status(new_status['cash'], new_status['total_equity'], target_state.target_cash_ratio)
                            remaining_bp = new_cp['available_buying_power']
                            
                            current_pos_scores.pop(0)
                            can_buy = remaining_bp >= row['close']
                            switched = True

                    if not can_buy:
                        if d_logger:
                            event_type = "ORDER_SKIPPED" if not switched else "SWITCH_FAILED"
                            r_reason = ReasonCode.INSUFFICIENT_BUYING_POWER if not switched else ReasonCode.SWITCH_FAILED
                            d_logger.log_event(
                                date=date_str, regime=regime_name, mode=current_mode,
                                event=event_type, details=f"Insufficient BP for {s}. Req: {row['close']:.2f}, BP: {remaining_bp:.2f}",
                                status=pf.get_account_status(), target_cash_ratio=target_state.target_cash_ratio,
                                rebalance_reason=r_reason,
                                required_cash_buffer=cp_status['required_cash_buffer'],
                                available_buying_power=remaining_bp,
                                is_violating_buffer=cp_status['is_violating_buffer']
                            )
                        safety_stats['order_skipped_count'] += 1
                        continue
                    
                    target_pos_value = total_equity / config['max_positions']
                    affordable_value = min(target_pos_value, remaining_bp)
                    shares = int(affordable_value / row['close'])
                    
                    if shares > 0:
                        order_value = shares * row['close']
                        buy_reason = ReasonCode.SWITCH_IN if switched else ReasonCode.ENTRY_SCORE_PASS
                        pf.buy(s, row['close'], shares, date, strategy_name="Ensemble", reason=buy_reason)
                        remaining_bp -= order_value


    results = calculate_metrics(equity_history, pf, config, safety_stats)
    if verbose: analyze_results(equity_history, pf, config)
    if 'run_id' in config: save_run_results(config, results)
    return results


def calculate_metrics(equity_history, pf, config, safety_stats):
    """지표 계산 공통 로직 (MFU2-4 확장)"""
    history_df = pd.DataFrame(equity_history).set_index('date')
    history_df['daily_ret'] = history_df['equity'].pct_change().fillna(0)
    final_equity = history_df['equity'].iloc[-1]
    total_ret = (final_equity - config['initial_capital']) / config['initial_capital'] * 100
    mdd = ((history_df['equity'] - history_df['equity'].cummax()) / history_df['equity'].cummax()).min() * 100
    days_diff = (history_df.index[-1] - history_df.index[0]).days
    cagr = ((final_equity / config['initial_capital']) ** (365 / max(days_diff, 1)) - 1) * 100
    std = history_df['daily_ret'].std() * np.sqrt(252)
    sharpe = (cagr / 100) / max(std, 0.0001)

    conn = pf.conn
    all_trades_df = pd.read_sql("SELECT * FROM trade_history ORDER BY date, id", conn)
    trades_df = all_trades_df[all_trades_df['type'] == 'SELL']
    
    total_trades = len(trades_df)
    win_rate = 0.0
    profit_factor = 0.0
    
    if total_trades > 0:
        win_trades = trades_df[trades_df['profit'] > 0]
        loss_trades = trades_df[trades_df['profit'] <= 0]
        win_rate = len(win_trades) / total_trades * 100
        gross_profit = win_trades['profit'].sum()
        gross_loss = abs(loss_trades['profit'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 99.9

    # MFU2-4: 현금 정책 통계 최종 계산
    total_days = max(safety_stats.get('total_days', 1), 1)
    safety_stats['avg_current_cash_ratio'] = safety_stats.get('sum_current_cash_ratio', 0) / total_days
    safety_stats['avg_target_cash_ratio'] = safety_stats.get('sum_target_cash_ratio', 0) / total_days
    safety_stats['avg_available_buying_power'] = safety_stats.get('sum_available_buying_power', 0) / total_days

    history_df['equity'] = pd.to_numeric(history_df['equity'])
    yearly = history_df['equity'].resample('YE').last().pct_change() * 100
    if not yearly.empty:
        first_ret = (history_df['equity'].resample('YE').last().iloc[0] - config['initial_capital']) / config['initial_capital'] * 100
        yearly.iloc[0] = first_ret
    yearly_json = json.dumps({str(k.year): round(v, 2) for k, v in yearly.items()})

    return {
        'return': total_ret, 'cagr': cagr, 'mdd': mdd, 'final_equity': final_equity, 'sharpe': sharpe,
        'total_trades': total_trades, 'win_rate': win_rate, 'profit_factor': profit_factor,
        'yearly_json': yearly_json,
        'safety_stats': safety_stats,
        'all_trades': all_trades_df,
        'period': f"{history_df.index[0].date()} ~ {history_df.index[-1].date()}"
    }


def analyze_results(equity_history, pf, config):
    """상세 리포트 출력"""
    history_df = pd.DataFrame(equity_history).set_index('date')
    final = history_df['equity'].iloc[-1]; total_ret = (final - config['initial_capital']) / config['initial_capital'] * 100
    mdd = ((history_df['equity'] - history_df['equity'].cummax()) / history_df['equity'].cummax()).min() * 100
    print("\n" + "=" * 50); print(f"📊 [최종 백테스트 상세 리포트]"); print("=" * 50)
    print(f"💰 자산: ${config['initial_capital']:,.0f} ➔ ${final:,.0f}"); print(f"🚀 수익률: {total_ret:.2f}% | MDD: {mdd:.2f}%")
    
    conn = pf.conn; 
    all_trades_df = pd.read_sql("SELECT * FROM trade_history ORDER BY date, id", conn)
    trades_df = all_trades_df[all_trades_df['type'] == 'SELL']
    
    if not trades_df.empty:
        total = len(trades_df); wins = len(trades_df[trades_df['profit'] > 0])
        gross_profit = trades_df[trades_df['profit'] > 0]['profit'].sum()
        gross_loss = abs(trades_df[trades_df['profit'] <= 0]['profit'].sum())
        pf_val = gross_profit / gross_loss if gross_loss > 0 else 99.9
        print(f"🔄 거래: {total}회 | 승률: {wins/total*100:.2f}% | PF: {pf_val:.2f}")
    
    print("\n📜 [매매 내역 상세]")
    rebal_freq = config.get('REBALANCE_FREQUENCY', 'D')
    for _, row in all_trades_df.iterrows():
        date_val = pd.to_datetime(row['date'])
        is_end_of_period = ""
        if row['type'] == 'BUY':
            if rebal_freq == 'M':
                is_month_end = date_val.is_month_end
                is_end_of_period = " (Month End)" if is_month_end else " (NOT Month End! ⚠️)"
            elif rebal_freq == 'W':
                is_end_of_period = " (Week End)" if date_val.weekday() == 4 else ""
        
        print(f"  {row['date']} | {row['type']:4} | {row['symbol']:5} | {row['shares']:4}주 | {row['price']:8.2f} | {row['strategy_name']}{is_end_of_period}")

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
    headers = [
        'run_id', 'use_hedge_mode', 'hedge_ratio_bear', 'hedge_ratio_panic', 'min_maintain_days', 
        'total_return', 'cagr', 'mdd', 'sharpe', 'profit_factor', 'total_trades', 
        'mode_change_count', 'regime_change_count',
        # MFU2-4: Cash Policy Stats in Summary
        'avg_current_cash_ratio', 'avg_target_cash_ratio', 'cash_policy_violation_days',
        'order_blocked_count', 'order_skipped_count'
    ]
    s_stats = results.get('safety_stats', {})
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
        'mode_change_count': s_stats.get('mode_change_count', 0), 
        'regime_change_count': s_stats.get('regime_change_count', 0),
        # MFU2-4 fields
        'avg_current_cash_ratio': round(s_stats.get('avg_current_cash_ratio', 0), 4),
        'avg_target_cash_ratio': round(s_stats.get('avg_target_cash_ratio', 0), 4),
        'cash_policy_violation_days': s_stats.get('cash_policy_violation_days', 0),
        'order_blocked_count': s_stats.get('order_blocked_count', 0),
        'order_skipped_count': s_stats.get('order_skipped_count', 0)
    }
    with open(summary_file, "w", encoding="utf-8-sig", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers); writer.writeheader(); writer.writerow(row)
    print(f"📊 [실험 결과 저장 완료] ID: {run_id}")

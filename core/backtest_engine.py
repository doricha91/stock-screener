import pandas as pd
import numpy as np
import json
import market_analyzer
import csv
from typing import List, Dict, Any, Optional
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


def evaluate_switching_opportunity(
    candidates: pd.DataFrame, 
    current_pos_scores: List[Dict[str, Any]], 
    config: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    신규 후보와 현재 보유 종목을 비교하여 교체 기회를 평가합니다. (MFU 5)
    """
    premium = config.get('SWITCHING_PREMIUM', 1.0)
    allow_profit_switch = config.get('ALLOW_PROFIT_SWITCH', False)
    max_switches = config.get('SWITCHING_MAX_COUNT', 2)
    
    switch_pairs = []
    
    # [안정성] 방어적 복사 및 명시적 정렬 (점수 낮은 순)
    temp_holdings = sorted(
        [dict(h) for h in current_pos_scores], 
        key=lambda x: (x['score'], x['return'])
    )
    
    # [안정성] 후보 데이터프레임 복사본 사용
    sorted_candidates = candidates.copy().sort_values(by=['score', 'rs_val'], ascending=False)
    
    for symbol, c_row in sorted_candidates.iterrows():
        if not temp_holdings or len(switch_pairs) >= max_switches:
            break
            
        # 가장 점수가 낮은 보유 종목과 비교
        worst_h = temp_holdings[0]
        
        # 조건 1: 점수 차이가 프리미엄보다 큰가
        score_gap = c_row['score'] - worst_h['score']
        
        # 조건 2: 수익 중인 종목 교체 허용 여부
        is_loss = worst_h['return'] < 0
        can_switch_by_profit = allow_profit_switch or is_loss
        
        if score_gap > premium and can_switch_by_profit:
            switch_pairs.append({
                'sell_symbol': worst_h['symbol'],
                'buy_symbol': symbol,
                'buy_row': c_row,
                'worst_h': worst_h,
                'score_gap': score_gap
            })
            temp_holdings.pop(0) # 매도 예정이므로 목록에서 제거
            
    return switch_pairs


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

        # [MFU 6-1] Phase 1: 점수 계산 로직 제거
        # 가중치가 국면별로 다르므로, 여기서 미리 계산하지 않고 메인 루프에서 실시간으로 계산함.
        
        df['vol_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
        df['symbol'] = symbol

        # [MFU 6-1] Phase 1: 매수 신호 제거 (메인 루프에서 생성)
        # 매도 신호는 기술적 절대 기준(Turtle Exit 등)이므로 유지 가능
        df['sell_signal'] = df['close'] < df['exit_low']

        if 'date' not in df.columns:
            df = df.reset_index()
        df.rename(columns={'index': 'date', 'Date': 'date'}, inplace=True)

        # 반환 컬럼 최적화 (점수와 매수신호 제외)
        cols = ['date', 'symbol', 'open', 'high', 'low', 'close', 'atr',
                'sell_signal', 'vol_ratio', 'rs_val',
                'turtle_signal', 'rsi_signal', 'sma_signal', 'bbands_signal', 
                'macd_signal', 'bbs_signal', 'dema_signal', 
                'signal_obv', 'signal_mfi', 'signal_vol_spike']
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

    # [수정] 하드코딩 제거: 설정된 시작일로부터 1년(약 252거래일) 앞선 날짜부터 데이터를 로드
    # SMA 200 등 장기 지표 계산을 위한 충분한 버퍼 확보
    # (주의: 인자이름 config와 모듈 config 충돌 방지를 위해 market_analyzer.config 참조)
    requested_start = pd.to_datetime(config.get('start_date', market_analyzer.config.IN_SAMPLE_START))
    bulk_start_dt = requested_start - pd.Timedelta(days=400) # 넉넉하게 약 1년 이상
    bulk_start = bulk_start_dt.strftime('%Y-%m-%d')

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
    
    # [수정] 하위 호환성을 위해 config.py의 전역 설정값을 기본값으로 사용
    start_date = pd.to_datetime(config.get('start_date', market_analyzer.config.IN_SAMPLE_START))
    end_date = pd.to_datetime(config.get('end_date', market_analyzer.config.OUT_OF_SAMPLE_END))
    
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
            # config_overrides에 현재 설정을 주입하여 최적화 파라미터가 반영되게 함
            state = market_analyzer.get_market_state(target_date=date_str, write_log=False, config_overrides=config)
            regime_name = state["regime"]
            trade_halted = bool(state.get("trade_halted", False))

            # [MFU4 Step 2] 국면 선택적 백테스트 필터 로직 추가
            # 설정된 TARGET_REGIMES가 있고, 현재 국면이 그에 해당하지 않는 경우 처리
            target_regimes = config.get('TARGET_REGIMES', [])
            filter_mode = config.get('REGIME_FILTER_MODE', 'FREEZE')
            
            is_outside_regime = len(target_regimes) > 0 and (regime_name not in target_regimes)
            
            if is_outside_regime:
                if filter_mode == 'EXCLUSIVE':
                    # 1) EXCLUSIVE 모드: 대상 국면이 아니면 모든 포지션 정리 후 관망 (격리 테스트)
                    positions = pf.get_positions()
                    if positions:
                        for s, info in list(positions.items()):
                            sell_price = current_prices.get(s, info['current_price'])
                            pf.sell(s, sell_price, info['shares'], date, reason="REGIME_FILTER_EXCLUSIVE")
                    # 오늘 하루는 거래 중단 상태로 강제 설정
                    trade_halted = True 
                elif filter_mode == 'FREEZE':
                    # 2) FREEZE 모드: 기존 종목은 유지하되, 신규 매수(진입)만 차단
                    trade_halted = True
                
                if d_logger and i % 20 == 0: # 로그 너무 많아지는 것 방지 위해 가끔씩만 기록
                    d_logger.log_event(date_str, regime_name, current_mode, "REGIME_FILTER_ACTIVE", 
                                     f"Mode: {filter_mode} | Halted: {trade_halted}", pf.get_account_status())

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

        # [MFU 6-2] Phase 2: 실시간 동적 점수 및 신호 생성
        day_data = market_data[date].set_index('symbol')
        current_prices = day_data['close'].to_dict()

        # 현재 국면 가중치 구성
        active_weights = {
            'turtle': config.get('turtle_weight', 1.0), 'rsi': config.get('rsi_weight', 1.0),
            'sma': config.get('sma_weight', 1.0), 'bbands': config.get('bbands_weight', 1.0),
            'macd': config.get('macd_weight', 1.0), 'bbs': config.get('bbs_weight', 1.0),
            'dema': config.get('dema_weight', 1.0), 'obv': config.get('obv_weight', 0.5),
            'mfi': config.get('mfi_weight', 0.5), 'vol_spike': config.get('vol_spike_weight', 0.5),
        }

        # 모든 종목에 대해 실시간 점수 계산 (Vectorized)
        day_data['score'], _ = compute_candidate_score(day_data, active_weights)
        
        # RS 가중치 합산
        rs_weight = config.get('rs_weight', 0.0)
        if rs_weight > 0:
            day_data['score'] += (day_data['rs_val'] > 0).astype(float) * rs_weight
            
        # 매수 신호 생성 (현재 국면의 threshold 적용)
        day_data['buy_signal'] = (day_data['score'] >= config['score_threshold']) & (day_data['rs_val'] > 0)

        # 시장 지표 통계 업데이트
        if config.get('use_market_regime', True):
            regime_map = {'PANIC': 'panic_days', 'BEAR': 'bear_days', 'UNSTABLE': 'unstable_days', 'BULL': 'bull_days'}
            if regime_name in regime_map: safety_stats[regime_map[regime_name]] += 1
            if trade_halted: safety_stats['cb_halt_days'] += 1

        for s in list(pf.get_positions().keys()):
            if s in current_prices: pf.update_market_status(s, current_prices[s])
        
        equity_history.append({'date': date, 'equity': pf.get_account_status()['total_equity']})

        # [MFU1-C] 1. 목표 포트폴리오 상태 계산 (Target State)
        candidate_rows = []
        for s, row in day_data.iterrows():
            candidate_rows.append({
                'symbol': s,
                'score': row['score'],
                'rs_val': row.get('rs_val', 0.0),
                'entry_signal': bool(row['buy_signal'])
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

        # 신규 매수 및 교체 루프
        rebal_freq = config.get('REBALANCE_FREQUENCY', 'D')
        is_rebal = is_rebalance_day(date, rebal_freq)

        if (not trade_halted) and is_rebal:
            # 1. 현재 보유 종목 재평가 (Phase 2: 실시간 점수 참조)
            current_pos_scores = []
            positions = pf.get_positions()

            for s, info in positions.items():
                if info.get('strategy_name') == "Hedge": continue
                if s in day_data.index:
                    row = day_data.loc[s]
                    # [MFU 6-2] 이미 상단에서 계산된 실시간 점수 사용
                    score = row['score']
                    p_ret = (info['current_price'] - info['avg_price']) / info['avg_price'] if info['avg_price'] > 0 else 0
                    current_pos_scores.append({
                        'symbol': s, 'score': score, 'return': p_ret, 
                        'shares': info['shares'], 'price': info['current_price']
                    })
            current_pos_scores.sort(key=lambda x: x['score']) # 점수 낮은 순

            # 2. 신규 후보군 추출 (Phase 2: 이미 생성된 buy_signal 사용)
            candidates = day_data[day_data['buy_signal'] == True]
            candidates = candidates[~candidates.index.isin(pf.get_positions().keys())]
            
            if not candidates.empty:
                # [MFU 6-2] 이미 상단에서 threshold 필터링이 완료된 상태이므로 정렬만 수행
                candidates = candidates.sort_values(by='rs_val', ascending=False)

            # 3. 능동적 스위칭 (Active Switching)
            switched_count = 0
            if not candidates.empty and current_pos_scores:
                switch_opportunities = evaluate_switching_opportunity(candidates, current_pos_scores, config)
                for opt in switch_opportunities:
                    s_sell = opt['sell_symbol']
                    s_buy = opt['buy_symbol']
                    buy_row = opt['buy_row']
                    
                    # [순서 강제] 1. 매도 먼저 실행하여 현금 확보
                    pf.sell(s_sell, current_prices.get(s_sell, opt['worst_h']['price']), opt['worst_h']['shares'], date, reason=ReasonCode.SWITCH_OUT)
                    switched_count += 1
                    
                    # [상태 갱신] 2. 매도 후 즉시 계좌 상태 및 BP 재계산
                    new_status = pf.get_account_status()
                    new_cp = get_cash_policy_status(new_status['cash'], new_status['total_equity'], target_state.target_cash_ratio)
                    remaining_bp = new_cp['available_buying_power']
                    
                    # [순서 강제] 3. 확보된 현금으로 매수 실행
                    shares = int(remaining_bp / buy_row['close'])
                    if shares > 0:
                        pf.buy(s_buy, buy_row['close'], shares, date, strategy_name="Ensemble", reason=ReasonCode.SWITCH_IN)
                        if d_logger:
                            d_logger.log_event(date_str, regime_name, current_mode, "POSITION_SWITCHED", 
                                f"Active Switch: {s_sell}({opt['worst_h']['score']:.1f}) -> {s_buy}({buy_row['score']:.1f})", 
                                new_status, target_state.target_cash_ratio, rebalance_reason=ReasonCode.SWITCH_OUT)
                        
                        # [상태 갱신] 후보 및 보유 목록에서 즉시 제거하여 중복 매매 방지
                        candidates = candidates.drop(s_buy)
                        current_pos_scores = [h for h in current_pos_scores if h['symbol'] != s_sell]
                        remaining_bp -= (shares * buy_row['close'])
                    
                    if switched_count >= config.get('SWITCHING_MAX_COUNT', 2): break

            # 4. 일반 매수 (남은 슬롯 및 현금 범위 내)
            for s, row in candidates.iterrows():
                if len(pf.get_positions()) >= config['max_positions']: 
                    if d_logger: d_logger.log_event(date_str, regime_name, current_mode, "ORDER_SKIPPED", f"Max pos reached. Skipping {s}", pf.get_account_status(), target_state.target_cash_ratio, ReasonCode.ORDER_SKIPPED_MAX_POS)
                    break
                
                cp_now = get_cash_policy_status(pf.get_account_status()['cash'], pf.get_account_status()['total_equity'], target_state.target_cash_ratio)
                remaining_bp = cp_now['available_buying_power']
                
                if remaining_bp >= row['close']:
                    target_pos_value = cp_now['total_equity'] / config['max_positions']
                    shares = int(min(target_pos_value, remaining_bp) / row['close'])
                    if shares > 0:
                        pf.buy(s, row['close'], shares, date, strategy_name="Ensemble", reason=ReasonCode.ENTRY_SCORE_PASS)
                        remaining_bp -= (shares * row['close'])
                elif d_logger:
                    d_logger.log_event(date_str, regime_name, current_mode, "ORDER_SKIPPED", f"Low BP for {s}", pf.get_account_status(), target_state.target_cash_ratio, ReasonCode.INSUFFICIENT_BUYING_POWER)



    results = calculate_metrics(equity_history, pf, config, safety_stats)
    if verbose: analyze_results(equity_history, pf, config)
    if 'run_id' in config: save_run_results(config, results)
    return results


def calculate_metrics(equity_history, pf, config, safety_stats):
    """지표 계산 공통 로직 (MFU2-4 확장, Avg Win/Loss, Sortino, Calmar 추가)"""
    history_df = pd.DataFrame(equity_history).set_index('date')
    history_df['daily_ret'] = history_df['equity'].pct_change().fillna(0)
    final_equity = history_df['equity'].iloc[-1]
    total_ret = (final_equity - config['initial_capital']) / config['initial_capital'] * 100
    mdd = ((history_df['equity'] - history_df['equity'].cummax()) / history_df['equity'].cummax()).min() * 100
    days_diff = (history_df.index[-1] - history_df.index[0]).days
    cagr = ((final_equity / config['initial_capital']) ** (365 / max(days_diff, 1)) - 1) * 100
    std = history_df['daily_ret'].std() * np.sqrt(252)
    sharpe = (cagr / 100) / max(std, 0.0001)

    # [추가] Sortino Ratio: 하방 편차(Downside Deviation) 기반
    negative_rets = history_df['daily_ret'][history_df['daily_ret'] < 0]
    downside_std = negative_rets.std() * np.sqrt(252) if not negative_rets.empty else 0.0001
    sortino = (cagr / 100) / max(downside_std, 0.0001)

    # [추가] Calmar Ratio: CAGR / Abs(MDD)
    calmar = (cagr / abs(mdd)) if mdd != 0 else 0

    conn = pf.conn
    all_trades_df = pd.read_sql("SELECT * FROM trade_history ORDER BY date, id", conn)
    trades_df = all_trades_df[all_trades_df['type'] == 'SELL']
    
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
        
        # [추가] Avg Win / Avg Loss
        avg_win = win_trades['profit'].mean() if not win_trades.empty else 0.0
        avg_loss = abs(loss_trades['profit'].mean()) if not loss_trades.empty else 0.0

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
        'return': total_ret, 'cagr': cagr, 'mdd': mdd, 'final_equity': final_equity, 
        'sharpe': sharpe, 'sortino': sortino, 'calmar': calmar,
        'total_trades': total_trades, 'win_rate': win_rate, 'profit_factor': profit_factor,
        'avg_win': avg_win, 'avg_loss': avg_loss,
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

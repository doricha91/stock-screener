# core/daily_plan_generator.py
import os
import sqlite3
import sys
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import config
import market_analyzer
from screener.screener import build_screener_results
from core.portfolio_state_manager import load_current_state
from core.target_portfolio_state import (
    build_target_portfolio_state, 
    evaluate_rebalance_need,
    get_cash_policy_status,
    calculate_available_buying_power,
    CurrentPortfolioState,
    TargetPortfolioState,
    RebalanceDecision
)
from core.paths import FRONT_TEST_DIR, market_db_path
from core.backtest_engine import evaluate_switching_opportunity
from core.config_factory import make_config, get_regime_config
from core.universe_manager import load_latest_universe_snapshot


def _configure_console_encoding() -> None:
    """Best-effort UTF-8 console setup for Windows terminals."""
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def load_market_index_series(symbol: str, end_date: str, start_date: str | None = None) -> pd.Series:
    """Load benchmark/index close series from market_index up to end_date."""
    conn = sqlite3.connect(market_db_path())
    try:
        params: list[str] = [symbol, end_date]
        query = """
            SELECT date, close
            FROM market_index
            WHERE symbol = ? AND date <= ?
        """
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        query += " ORDER BY date ASC"
        df = pd.read_sql(query, conn, params=params)
    finally:
        conn.close()

    if df.empty:
        return pd.Series(dtype="float64")

    df["date"] = pd.to_datetime(df["date"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    return df.set_index("date")["close"].dropna()


def load_price_history_until(symbol: str, end_date: str, lookback_days: int = 10) -> pd.DataFrame:
    """Load stock price history ending on or before end_date without look-ahead."""
    end_ts = pd.to_datetime(end_date)
    start_date = (end_ts - pd.Timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    df = data_manager.get_price_data(symbol, start_date=start_date, end_date=end_date)
    if df is None or df.empty:
        return pd.DataFrame()
    return df.sort_index()[df.index <= end_ts]


def calculate_candidate_rs_val(
    symbol: str,
    asof_date: pd.Timestamp,
    benchmark_close: pd.Series,
    rs_lookback: int,
) -> Optional[float]:
    """Calculate candidate relative strength using only history up to asof_date."""
    if benchmark_close is None or benchmark_close.empty:
        return None

    history_days = max(rs_lookback * 3, rs_lookback + 30)
    start_date = (asof_date - pd.Timedelta(days=history_days)).strftime("%Y-%m-%d")
    end_date = asof_date.strftime("%Y-%m-%d")

    stock_df = data_manager.get_price_data(symbol, start_date=start_date, end_date=end_date)
    if stock_df is None or stock_df.empty or 'close' not in stock_df.columns:
        return None

    stock_close = stock_df.sort_index()['close']
    stock_close = stock_close[stock_close.index <= asof_date]
    bench_close = benchmark_close[benchmark_close.index <= asof_date]

    common_index = stock_close.index.intersection(bench_close.index)
    if len(common_index) <= rs_lookback:
        return None

    stock_common = stock_close.loc[common_index]
    bench_common = bench_close.loc[common_index]

    stock_ret = stock_common.pct_change(rs_lookback).iloc[-1]
    bench_ret = bench_common.pct_change(rs_lookback).iloc[-1]
    if pd.isna(stock_ret) or pd.isna(bench_ret):
        return None

    return float(stock_ret - bench_ret)


def build_candidate_filter_diagnostics(
    formatted_candidates: List[Dict[str, Any]],
    score_threshold: float,
    data_date: str,
) -> tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Build read-only diagnostics that mirror current candidate filters."""
    diagnostics: List[Dict[str, Any]] = []
    summary = {
        "total": 0,
        "pass": 0,
        "failed_score": 0,
        "failed_rs": 0,
        "failed_rs_calc": 0,
        "failed_entry": 0,
        "stale": 0,
    }
    data_ts = pd.to_datetime(data_date)

    for candidate in formatted_candidates:
        summary["total"] += 1
        symbol = candidate.get("symbol", "N/A")
        latest_price_date = candidate.get("latest_price_date")
        latest_ts = pd.to_datetime(latest_price_date) if latest_price_date else None
        stale_days = max((data_ts - latest_ts).days, 0) if latest_ts is not None else None

        score = candidate.get("score")
        rs_val = candidate.get("rs_val")
        entry_signal = bool(candidate.get("entry_signal", False))
        score_ok = pd.notna(score) and float(score) >= float(score_threshold)
        rs_ok = pd.notna(rs_val) and float(rs_val) > 0

        fail_reason = "pass"
        if not entry_signal:
            fail_reason = "entry_signal_false"
            summary["failed_entry"] += 1
        elif pd.isna(score):
            fail_reason = "missing_score"
            summary["failed_score"] += 1
        elif float(score) < float(score_threshold):
            fail_reason = "score_below_threshold"
            summary["failed_score"] += 1
        elif not candidate.get("rs_calc_success", True):
            fail_reason = "rs_calc_failed"
            summary["failed_rs_calc"] += 1
        elif pd.isna(rs_val):
            fail_reason = "missing_rs_val"
            summary["failed_rs_calc"] += 1
        elif float(rs_val) <= 0:
            fail_reason = "rs_lte_0"
            summary["failed_rs"] += 1

        passed = fail_reason == "pass"
        if passed:
            summary["pass"] += 1

        stale_flag = stale_days is not None and stale_days > 0
        if stale_flag:
            summary["stale"] += 1

        display_reason = "stale_data" if stale_flag else fail_reason

        diagnostics.append({
            "symbol": symbol,
            "latest_price_date": latest_price_date or "N/A",
            "data_date": data_date,
            "stale_days": stale_days if stale_days is not None else "N/A",
            "score": score if pd.notna(score) else None,
            "score_threshold": score_threshold,
            "rs_val": rs_val if pd.notna(rs_val) else None,
            "entry_signal": entry_signal,
            "score_ok": score_ok,
            "rs_ok": rs_ok,
            "pass": passed,
            "fail_reason": display_reason,
        })

    return diagnostics, summary


def is_stale_candidate(
    latest_price_date: Optional[str],
    data_date: str,
    max_days: int = 7,
) -> tuple[bool, Optional[int]]:
    """Return whether a candidate is stale relative to data_date."""
    try:
        if not latest_price_date:
            return True, None
        latest_ts = pd.to_datetime(latest_price_date)
        data_ts = pd.to_datetime(data_date)
        stale_days = max((data_ts - latest_ts).days, 0)
        return stale_days > max_days, stale_days
    except Exception:
        return True, None

def check_trailing_stop_manual(
    symbol: str, 
    current_price: float, 
    highest_price_so_far: float, 
    atr: float, 
    multiplier: float = 2.5
) -> tuple[bool, float]:
    """
    JSON 스냅샷 데이터를 기반으로 트레일링 스탑 여부를 판단합니다.
    - 반환값: (is_triggered, stop_price)
    """
    # 최고가 갱신
    new_highest = max(highest_price_so_far, current_price)
    
    # ATR이 유효하지 않으면 보수적으로 현재가의 2% 사용
    safe_atr = atr if atr > 0 else (current_price * 0.02)
    stop_price = new_highest - (safe_atr * multiplier)
    
    is_triggered = current_price < stop_price
    return is_triggered, stop_price

from screener import data_manager

def generate_daily_plan(date_str: str = None) -> str:
    """
    일일 판단 산출물(Action Plan)을 생성하고 파일로 저장합니다.
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    plan_date = date_str

    _configure_console_encoding()
        
    print(f"[START] Generating Daily Action Plan for {plan_date}...")

    # 1. 현재 상태 로드 (FT3)
    try:
        current_state = load_current_state()
    except Exception as e:
        print(f"[ERROR] Failed to load current state: {e}")
        return ""

    # 2. 시장 국면 판단
    m_state = market_analyzer.get_market_state(target_date=plan_date)
    data_date = m_state["date"]
    regime = m_state["regime"]
    print(f"[INFO] plan_date={plan_date}, data_date={data_date}")
    base_config = make_config({}, data_date, data_date)
    merged_config = get_regime_config(regime, base_config)
    universe_snapshot = load_latest_universe_snapshot()
    removed_universe_symbols = {
        str(symbol).strip().upper()
        for symbol in universe_snapshot.get("removed", [])
        if str(symbol).strip()
    }
    removed_candidate_exclusions: List[Dict[str, Any]] = []
    stale_holdings_alert: List[str] = []
    
    # 3. 신규 매수 후보 스크리닝 (Raw Signals)
    df_candidates = build_screener_results(market_state=m_state)
    if not df_candidates.empty and removed_universe_symbols:
        symbol_col = "Symbol" if "Symbol" in df_candidates.columns else "symbol" if "symbol" in df_candidates.columns else None
        if symbol_col:
            excluded_candidates = sorted(
                {
                    str(symbol).strip().upper()
                    for symbol in df_candidates[symbol_col].tolist()
                    if str(symbol).strip().upper() in removed_universe_symbols
                }
            )
            if excluded_candidates:
                removed_candidate_exclusions = [
                    {"symbol": symbol, "reason": "universe_removed"}
                    for symbol in excluded_candidates
                ]
                df_candidates = df_candidates[
                    ~df_candidates[symbol_col].astype(str).str.strip().str.upper().isin(removed_universe_symbols)
                ].copy()
                print(
                    "⚠️ [Freshness Guard] Excluded stale/removed candidates: "
                    + ", ".join(excluded_candidates)
                )
    if not df_candidates.empty:
        df_candidates = df_candidates.rename(columns={
            'Symbol': 'symbol',
            'Price': 'close',
            'Score': 'score',
        }).copy()
        if 'rs_val' not in df_candidates.columns:
            rs_lookback = int(merged_config.get('rs_lookback', 120))
            benchmark_symbol = merged_config.get('MARKET_BENCHMARK_SYMBOL', 'SPY')
            asof_date = pd.to_datetime(data_date)
            bench_start = (asof_date - pd.Timedelta(days=max(rs_lookback * 3, rs_lookback + 30))).strftime("%Y-%m-%d")
            benchmark_close = load_market_index_series(
                benchmark_symbol,
                end_date=data_date,
                start_date=bench_start,
            )

            rs_values: List[float] = []
            rs_calc_success: List[bool] = []
            rs_success = 0
            rs_positive = 0
            for symbol in df_candidates['symbol'].tolist():
                rs_val = calculate_candidate_rs_val(symbol, asof_date, benchmark_close, rs_lookback)
                if rs_val is None:
                    rs_values.append(0.0)
                    rs_calc_success.append(False)
                    continue
                rs_values.append(rs_val)
                rs_calc_success.append(True)
                rs_success += 1
                if rs_val > 0:
                    rs_positive += 1

            df_candidates['rs_val'] = rs_values
            df_candidates['rs_calc_success'] = rs_calc_success
            rs_failed = len(df_candidates) - rs_success
            print(
                f"RS calc: candidates={len(df_candidates)}, success={rs_success}, "
                f"failed={rs_failed}, positive={rs_positive}"
            )
            if rs_success == 0:
                print("[WARN] RS calc failed for all candidates; target selection may remain empty.")
    
    # [MFU 6-4] Phase 4: 실시간 국면 가중치 적용 (백테스트 엔진과 동일 로직)
    # 현재 국면 가중치 구성 (config.REGIME_RULES 및 전역 기본값 병합)
    from core.decision_core import compute_candidate_score
    
    active_weights = {
        'turtle': merged_config.get('turtle_weight', 1.0),
        'rsi': merged_config.get('rsi_weight', 1.0),
        'sma': merged_config.get('sma_weight', 1.0),
        'bbands': merged_config.get('bbands_weight', 1.0),
        'macd': merged_config.get('macd_weight', 1.0),
        'bbs': merged_config.get('bbs_weight', 1.0),
        'dema': merged_config.get('dema_weight', 1.0),
        'obv': merged_config.get('obv_weight', 0.5),
        'mfi': merged_config.get('mfi_weight', 0.5),
        'vol_spike': merged_config.get('vol_spike_weight', 0.5),
    }

    if not df_candidates.empty:
        # 모든 후보에 대해 실시간 점수 계산 (백테스트와 100% 동일 가중치)
        # build_screener_results에서 온 컬럼명(Signal_*)을 compute_candidate_score가 이해하는 형식으로 매핑
        signal_cols = [f"signal_{name}" for name in active_weights.keys()]
        if any(col in df_candidates.columns for col in signal_cols):
            df_candidates['score'], _ = compute_candidate_score(df_candidates, active_weights)
        
        # RS 가중치 합산
        rs_weight = merged_config.get('rs_weight', getattr(config, 'RS_WEIGHT', 1.0))
        if rs_weight > 0:
            rs_series = df_candidates['rs_val'] if 'rs_val' in df_candidates.columns else pd.Series(0.0, index=df_candidates.index)
            df_candidates['score'] += (rs_series > 0).astype(float) * rs_weight
        
        # 실시간 기준에 따른 최종 필터링 및 정렬
        score_threshold = merged_config.get('score_threshold', getattr(config, 'SCORE_THRESHOLD', 1.5))
        sort_col = 'rs_val' if 'rs_val' in df_candidates.columns else 'score'
        df_candidates = df_candidates[df_candidates['score'] >= score_threshold].sort_values(by=sort_col, ascending=False)

    stale_candidate_max_days = int(merged_config.get('stale_candidate_max_days', 7))
    candidate_rows = df_candidates.to_dict(orient='records') if not df_candidates.empty else []
    stale_exclusions: List[Dict[str, Any]] = []
    formatted_candidates = []
    for c in candidate_rows:
        latest_price_date = c.get('Date', c.get('date'))
        stale_flag, stale_days = is_stale_candidate(latest_price_date, data_date, stale_candidate_max_days)
        if stale_flag:
            stale_exclusions.append({
                'symbol': c['symbol'],
                'latest_price_date': latest_price_date or "N/A",
                'stale_days': stale_days if stale_days is not None else "N/A",
            })
            continue

        formatted_candidates.append({
            'symbol': c['symbol'],
            'score': c['score'],
            'rs_val': c.get('rs_val', 0.0),
            'rs_calc_success': c.get('rs_calc_success', True),
            'latest_price_date': latest_price_date,
            'entry_signal': True,
            'price': c['close']
        })
    print(
        f"Stale candidate filter: excluded={len(stale_exclusions)}, "
        f"kept={len(formatted_candidates)}, threshold={stale_candidate_max_days}d"
    )

    # 4. 목표 상태 빌드 및 리밸런싱 판단
    score_threshold = merged_config.get('score_threshold', getattr(config, 'SCORE_THRESHOLD', 1.5))
    candidate_diagnostics, candidate_diag_summary = build_candidate_filter_diagnostics(
        formatted_candidates,
        score_threshold,
        data_date,
    )
    print(
        "Candidate filter summary: "
        f"total={candidate_diag_summary['total']}, "
        f"pass={candidate_diag_summary['pass']}, "
        f"failed_score={candidate_diag_summary['failed_score']}, "
        f"failed_rs={candidate_diag_summary['failed_rs']}, "
        f"failed_rs_calc={candidate_diag_summary['failed_rs_calc']}, "
        f"failed_entry={candidate_diag_summary['failed_entry']}, "
        f"stale={candidate_diag_summary['stale']}"
    )
    target_state = build_target_portfolio_state(regime, formatted_candidates, merged_config)
    rebalance = evaluate_rebalance_need(current_state, target_state, merged_config)
    
    # 총 자산 계산을 위해 현재 보유 종목의 최신가 필요
    # ... (생략된 기존 가격 수집 로직)
    total_stock_value = 0
    current_prices = {}
    for s in current_state.current_symbols:
        if s in removed_universe_symbols:
            stale_holdings_alert.append(s)
            print(
                f"⚠️ [Freshness Guard] Holding {s} is listed in latest universe snapshot removed list. Review manually."
            )
        try:
            df = load_price_history_until(s, data_date, lookback_days=10)
            price = df.iloc[-1]['close'] if not df.empty else current_state.avg_price[s]
            current_prices[s] = price
            total_stock_value += (current_state.shares[s] * price)
        except:
            current_prices[s] = current_state.avg_price[s]
            total_stock_value += (current_state.shares[s] * current_state.avg_price[s])

    cp_status = get_cash_policy_status(
        current_state.absolute_cash, 
        current_state.absolute_cash + total_stock_value,
        target_state.target_cash_ratio
    )

    # [MFU 5] 능동적 스위칭 (Active Switching) 판단
    switch_pairs = []
    if not df_candidates.empty and current_state.current_symbols:
        # 1. 현재 보유 종목 점수 재계산 (백테스트와 동일 로직)
        current_pos_scores = []
        # 국면별 가중치 가져오기 (config.REGIME_RULES 참조)
        candidates_by_symbol = df_candidates.set_index('symbol', drop=False) if 'symbol' in df_candidates.columns else pd.DataFrame()
        
        from core.decision_core import compute_candidate_score
        
        for s in current_state.current_symbols:
            try:
                # 최신 지표가 포함된 데이터 필요 (screener/indicator.py 활용 권장하나, 여기서는 후보군 생성 시 계산된 값 참조가 어려우므로 단순화된 비교 수행)
                # 실전에서는 build_screener_results()가 이미 모든 종목(보유주 포함)의 점수를 계산하도록 설계되어 있어야 함.
                # 현재 build_screener_results는 후보만 반환하므로, 보유주가 후보에 포함되지 않았을 경우를 대비해 기본 점수 획득 로직 필요.
                
                # 보유 종목이 후보군(df_candidates)에 있다면 그 점수를 사용
                if not candidates_by_symbol.empty and s in candidates_by_symbol.index:
                    score = candidates_by_symbol.loc[s, 'score']
                else:
                    # 후보군에 없다는 것은 점수가 낮거나 시그널이 없다는 뜻이므로 보수적으로 0점 처리 또는 재계산
                    # 여기서는 안전하게 0.0으로 처리하여 교체 대상 1순위가 되도록 유도
                    score = 0.0
                
                p_ret = (current_prices[s] - current_state.avg_price[s]) / current_state.avg_price[s] if current_state.avg_price[s] > 0 else 0
                current_pos_scores.append({
                    'symbol': s, 'score': score, 'return': p_ret, 
                    'shares': current_state.shares[s], 'price': current_prices[s]
                })
            except Exception as e:
                print(f"[WARN] Failed to re-evaluate score for {s}: {e}")

        # 2. 교체 기회 평가
        # candidates 데이터프레임 형식 맞추기 (score, rs_val 등 필요)
        c_df = df_candidates.copy()
        # rs_val이 없을 경우를 대비해 0.0 기본값
        if 'rs_val' not in c_df.columns:
            c_df['rs_val'] = 0.0
        
        switch_pairs = evaluate_switching_opportunity(c_df, current_pos_scores, merged_config)

    # 5. 상세 행동 산출 (매도/매수 수량)
    action_items = []
    processed_symbols = set()
    stop_alerts = [] # 트레일링 스탑 감시 목록
    
    # [MFU 5] 5-0. 교체 매매 액션 추가 (최우선 순위 - 슬롯 확보용)
    for pair in switch_pairs:
        s_sell = pair['sell_symbol']
        s_buy = pair['buy_symbol']
        b_row = pair['buy_row']
        shares_to_sell = current_state.shares[s_sell]
        
        # 1. 매도 지시
        action_items.append({
            "type": "SELL",
            "symbol": s_sell,
            "shares": shares_to_sell,
            "price": current_prices.get(s_sell, 0),
            "reason": f"SWITCH_OUT (to {s_buy}, Score Gap: {pair['score_gap']:.1f})"
        })
        
        # 2. 매수 지시 (매도 후 확보될 가상 현금 고려 - 실전에서는 주의 요망)
        # 매수 수량 계산: (기존 가치 + 가용 현금 일부) 기반이나, 여기서는 안전하게 기존 슬롯 대체로 계산
        price_buy = b_row['close']
        shares_to_buy = int((shares_to_sell * current_prices.get(s_sell, 0)) / price_buy)
        
        if shares_to_buy > 0:
            action_items.append({
                "type": "BUY",
                "symbol": s_buy,
                "shares": shares_to_buy,
                "price": price_buy,
                "reason": f"SWITCH_IN (from {s_sell})"
            })
            
        processed_symbols.add(s_sell)

    for symbol in current_state.current_symbols:
        if symbol in processed_symbols:
            continue
        shares = current_state.shares.get(symbol, 0)
        if shares <= 0:
            continue

    # 5-1. 매도 판단 (Trailing Stop 및 일반 리밸런싱 매도)
    # ... (기존 코드 유지)
        # ... (기존 코드 유지)
        try:
            df_hist = load_price_history_until(symbol, data_date, lookback_days=10)
            if not df_hist.empty:
                latest_row = df_hist.iloc[-1]
                # core/backtest_engine.py의 로직과 동일하게 ATR 기반 스탑 계산
                atr = latest_row.get('atr', latest_row['close'] * 0.02)
                curr_price = latest_row['close']
                highest = current_state.highest_prices.get(symbol, curr_price)
                
                is_triggered, stop_price = check_trailing_stop_manual(
                    symbol, curr_price, highest, atr, merged_config.get('trailing_stop_multiplier', getattr(config, 'TRAILING_STOP_MULTIPLIER', 2.5))
                )
                
                if is_triggered:
                    action_items.append({
                        "type": "SELL",
                        "symbol": symbol,
                        "shares": shares,
                        "price": curr_price,
                        "reason": f"TRAILING_STOP (Triggered at ${stop_price:.2f})"
                    })
                    processed_symbols.add(symbol)
                    continue # 스탑 터지면 리밸런싱 체크 건너뜀
                else:
                    # 장중 실시간 감시를 위한 알림 목록 추가 (Neo의 비판 1 반영)
                    stop_alerts.append({
                        "symbol": symbol,
                        "stop_price": stop_price,
                        "current_price": curr_price,
                        "distance": ((curr_price - stop_price) / curr_price) * 100
                    })
        except Exception as e:
            print(f"[WARN] Trailing stop check failed for {symbol}: {e}")

        # (B) 리밸런싱 매도 체크 (전략적 제외)
        if symbol in rebalance.symbol_diff_removed:
            action_items.append({
                "type": "SELL",
                "symbol": symbol,
                "shares": shares,
                "price": current_prices.get(symbol, 0),
                "reason": "STRATEGY_EXIT (Rebalance Out)"
            })
            processed_symbols.add(symbol)

    # 5-2. 매수 판단
    buying_power = calculate_available_buying_power(
        current_state.absolute_cash,
        cp_status['total_equity'],
        target_state.target_cash_ratio,
        buffer_ratio=0.02
    )
    
    # 매수 종목도 이미 매도된 종목의 현금을 고려하지 않는 보수적 집행 (실전 안정성)
    for symbol in rebalance.symbol_diff_added:
        if symbol in current_state.current_symbols: continue # 이미 보유 중이면 추가 매수 로직은 추후 확장
        
        price = 0
        for c in formatted_candidates:
            if c['symbol'] == symbol:
                price = c['price']
                break
        
        if price > 0:
            shares_to_buy = int(buying_power / price)
            if shares_to_buy > 0:
                action_items.append({
                    "type": "BUY",
                    "symbol": symbol,
                    "shares": shares_to_buy,
                    "price": price,
                    "reason": "STRATEGY_ENTRY"
                })
                buying_power -= (shares_to_buy * price)

    # 6. 마크다운 리포트 생성
    report_path = FRONT_TEST_DIR / f"daily_action_plan_{plan_date.replace('-', '')}.md"
    
    # 기록용 사전 기입 데이터 준비 (MFU-FT2 긴급 수정 반영)
    journal_rows = []
    for item in action_items:
        journal_rows.append({
            "date": plan_date,
            "regime": regime,
            "symbol": item['symbol'],
            "type": item['type'],
            "rec_shares": item['shares'],
            "rec_price": f"{item['price']:.2f}"
        })

    report_content = format_markdown_report(
        plan_date,
        m_state,
        cp_status,
        action_items,
        stop_alerts,
        journal_rows,
        candidate_diagnostics=candidate_diagnostics,
        stale_exclusions=stale_exclusions,
        stale_candidate_max_days=stale_candidate_max_days,
        removed_candidate_exclusions=removed_candidate_exclusions,
        stale_holdings_alert=stale_holdings_alert,
    )
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print(f"[OK] Action Plan saved to: {report_path}")
    return str(report_path)

def format_markdown_report(
    date_str: str,
    m_state: dict,
    cp_status: dict,
    action_items: List[dict],
    stop_alerts: List[dict],
    journal_rows: List[dict],
    candidate_diagnostics: Optional[List[Dict[str, Any]]] = None,
    stale_exclusions: Optional[List[Dict[str, Any]]] = None,
    stale_candidate_max_days: int = 7,
    removed_candidate_exclusions: Optional[List[Dict[str, Any]]] = None,
    stale_holdings_alert: Optional[List[str]] = None,
) -> str:
    """마크다운 리포트 템플릿을 작성합니다."""
    # ... (상단 로직 유지)
    regime = m_state['regime']
    vix = m_state['vix_value']
    
    summary_action = "관망 (Wait)"
    if any(item['type'] == 'SELL' for item in action_items):
        summary_action = "매도 및 리밸런싱 (Sell/Rebalance)"
    elif any(item['type'] == 'BUY' for item in action_items):
        summary_action = "신규 매수 (Buy)"
    
    if regime == "PANIC":
        summary_action = "패닉 모드: 매수 금지 / 현금 확보 (PANIC: No Buy)"

    stale_holdings_notice = ""
    if stale_holdings_alert:
        joined = ", ".join(sorted(set(stale_holdings_alert)))
        stale_holdings_notice = (
            f"\n> ⚠️ 주의: 보유 종목 중 `{joined}` 이(가) 유니버스(지수)에서 편출되었거나 "
            "데이터가 정지되었을 수 있습니다. 확인 요망!\n"
        )

    report = f"""# 📈 Daily Action Plan [{date_str}]
> **중요 공지**: 본 리포트의 수량은 전일 종가 기준입니다. 장 개장 후 갭상승/하락이 클 경우 실제 가용 현금 내에서 수량을 미세 조절하십시오.
{stale_holdings_notice}

## 1. 오늘의 시장 국면 및 정책
- **현재 국면**: `{regime}` (VIX: `{vix:.2f}`)
- **현금 정책**: 목표 현금 `{cp_status['target_cash_ratio']*100:.0f}%` 유지
- **특이사항**: {m_state.get('triggers', {})}

## 2. 자산 현황
- **총 자산**: `${cp_status['total_equity']:,.2f}`
- **가용 현금 (Buying Power)**: **`${cp_status['available_buying_power']:,.2f}`** (2% 예비 버퍼 제외됨)

## 3. 실시간 조건부 매도 감시 (Trailing Stop)
> 장중 아래 가격(Stop Price)에 도달하면 전략적 판단과 관계없이 **즉시 전량 매도**하십시오.

| 종목 | 현재가 | 손절/익절가 (Stop) | 거리(%) | 지시 |
| :--- | :--- | :--- | :--- | :--- |
"""
    if not stop_alerts:
        report += "| - | - | - | - | 감시 종목 없음 |\n"
    else:
        for a in stop_alerts:
            report += f"| **{a['symbol']}** | ${a['current_price']:,.2f} | **${a['stop_price']:,.2f}** | {a['distance']:.2f}% | 이탈 시 즉시 매도 |\n"

    report += f"""
## 4. 확정 매매 지시 (장 시작 즉시 실행)
| 타입 | 종목 | 수량 | 예상단가 | 매매 사유 |
| :--- | :--- | :--- | :--- | :--- |
"""
    if not action_items:
        report += "| - | - | - | - | 오늘 실행할 확정 매매 없음 |\n"
    else:
        for item in action_items:
            report += f"| {item['type']} | **{item['symbol']}** | {item['shares']}주 | ${item['price']:,.2f} | {item['reason']} |\n"

    # MFU-FT2: 기록용 템플릿 섹션 (세분화 및 빈칸 강제)
    report += """
## 4-1. 후보 필터 진단 (Candidate Filter Diagnostics)
| Symbol | Latest Date | Stale Days | Score | RS | Entry | Result | Reason |
| :--- | :--- | :---: | ---: | ---: | :---: | :--- | :--- |
"""
    if removed_candidate_exclusions:
        report += "Freshness Guard exclusions (latest universe snapshot removed list):\n"
        for item in removed_candidate_exclusions:
            report += f"- {item['symbol']}: {item['reason']}\n"
        report += "\n"

    if stale_exclusions:
        report += (
            f"Stale candidate filter: excluded={len(stale_exclusions)}, "
            f"kept={len(candidate_diagnostics or [])}, threshold={stale_candidate_max_days}d\n\n"
        )
        report += "Excluded stale candidates:\n"
        for item in stale_exclusions:
            report += (
                f"- {item['symbol']}: latest={item['latest_price_date']}, "
                f"stale_days={item['stale_days']}\n"
            )
        report += "\n"

    if not candidate_diagnostics:
        report += "| - | - | - | - | - | - | no_candidates | 후보 종목이 없습니다. |\n"
    else:
        for diag in candidate_diagnostics:
            score_display = "N/A" if diag["score"] is None else f"{float(diag['score']):.2f}"
            rs_display = "N/A" if diag["rs_val"] is None else f"{float(diag['rs_val']):.6f}"
            entry_display = "Y" if diag["entry_signal"] else "N"
            result_display = "pass" if diag["pass"] else "fail"
            report += (
                f"| {diag['symbol']} | {diag['latest_price_date']} | {diag['stale_days']} | "
                f"{score_display} | {rs_display} | {entry_display} | {result_display} | {diag['fail_reason']} |\n"
            )

    report += f"""
## 5. 📝 프론트테스트 실행 기록 (Copy & Paste to Journal)
> 아래 표를 복사하여 기록 도구에 붙여넣으십시오. **Actual** 필드와 **Reason**은 직접 기입해야 합니다.

| Date | Regime | Symbol | Type | Rec_Shares | Rec_Price | Act_Shares | Act_Price | Reason | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
    if not journal_rows:
        report += f"| {date_str} | {regime} | - | WAIT | 0 | 0.00 | [ ] | [ ] | MATCH | 특이사항 없음 |\n"
    else:
        for j in journal_rows:
            report += f"| {j['date']} | {j['regime']} | **{j['symbol']}** | {j['type']} | {j['rec_shares']} | {j['rec_price']} | [ ] | [ ] | [ ] | | \n"

    report += """
---
**입력 가이드**:
- `Act_Shares / Act_Price`: 실제 체결된 수량과 가격을 **숫자만** 입력하십시오.
- `Reason Codes`: `MATCH`(일치), `INSUFFICIENT_BP`(현금부족), `PRICE_GAP`(가격변동), `MANUAL_SKIP`(거부)
"""
    return report

if __name__ == "__main__":
    generate_daily_plan()

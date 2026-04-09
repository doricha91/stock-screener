# core/daily_plan_generator.py
import os
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

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
from core.paths import FRONT_TEST_DIR

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
        
    print(f"🚀 Generating Daily Action Plan for {date_str}...")

    # 1. 현재 상태 로드 (FT3)
    try:
        current_state = load_current_state()
    except Exception as e:
        print(f"❌ Failed to load current state: {e}")
        return ""

    # 2. 시장 국면 판단
    m_state = market_analyzer.get_market_state(target_date=date_str)
    regime = m_state["regime"]
    
    # 3. 신규 매수 후보 스크리닝
    df_candidates = build_screener_results(market_state=m_state)
    candidate_rows = df_candidates.to_dict(orient='records') if not df_candidates.empty else []
    formatted_candidates = []
    for c in candidate_rows:
        formatted_candidates.append({
            'symbol': c['Symbol'],
            'score': c['Score'],
            'rs_val': c.get('rs_val', 1.0),
            'entry_signal': True,
            'price': c['Price']
        })

    # 4. 목표 상태 빌드 및 리밸런싱 판단
    target_state = build_target_portfolio_state(regime, formatted_candidates, config.__dict__)
    rebalance = evaluate_rebalance_need(current_state, target_state, config.__dict__)
    
    # 총 자산 계산을 위해 현재 보유 종목의 최신가 필요
    total_stock_value = 0
    current_prices = {}
    for s in current_state.current_symbols:
        try:
            df = data_manager.get_price_data(s, start_date=date_str)
            price = df.iloc[-1]['close'] if df is not None else current_state.avg_price[s]
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

    # 5. 상세 행동 산출 (매도/매수 수량)
    action_items = []
    stop_alerts = [] # 트레일링 스탑 감시 목록
    
    # 5-1. 매도 판단 (Trailing Stop 우선! - 지침 1 반영)
    processed_symbols = set()
    
    for symbol in current_state.current_symbols:
        shares = current_state.shares.get(symbol, 0)
        if shares <= 0: continue
        
        # (A) Trailing Stop 체크 (Safety First)
        try:
            df_hist = data_manager.get_price_data(symbol, start_date=date_str)
            if df_hist is not None and not df_hist.empty:
                latest_row = df_hist.iloc[-1]
                # core/backtest_engine.py의 로직과 동일하게 ATR 기반 스탑 계산
                atr = latest_row.get('atr', latest_row['close'] * 0.02)
                curr_price = latest_row['close']
                highest = current_state.highest_prices.get(symbol, curr_price)
                
                is_triggered, stop_price = check_trailing_stop_manual(
                    symbol, curr_price, highest, atr, config.TRAILING_STOP_MULTIPLIER
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
            print(f"⚠️ Trailing stop check failed for {symbol}: {e}")

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
    report_path = FRONT_TEST_DIR / f"daily_action_plan_{date_str.replace('-', '')}.md"
    
    # 기록용 사전 기입 데이터 준비 (MFU-FT2 긴급 수정 반영)
    journal_rows = []
    for item in action_items:
        journal_rows.append({
            "date": date_str,
            "regime": regime,
            "symbol": item['symbol'],
            "type": item['type'],
            "rec_shares": item['shares'],
            "rec_price": f"{item['price']:.2f}"
        })

    report_content = format_markdown_report(date_str, m_state, cp_status, action_items, stop_alerts, journal_rows)
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print(f"✅ Action Plan saved to: {report_path}")
    return str(report_path)

def format_markdown_report(date_str: str, m_state: dict, cp_status: dict, action_items: List[dict], stop_alerts: List[dict], journal_rows: List[dict]) -> str:
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

    report = f"""# 📈 Daily Action Plan [{date_str}]
> **중요 공지**: 본 리포트의 수량은 전일 종가 기준입니다. 장 개장 후 갭상승/하락이 클 경우 실제 가용 현금 내에서 수량을 미세 조절하십시오.

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

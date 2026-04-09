# core/preflight_check.py
import sys
from datetime import datetime
from typing import Tuple
try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Python 3.9 미만 환경 대응 (현재 프로젝트는 3.11이므로 안전)
    from backports.zoneinfo import ZoneInfo

import market_analyzer
from core.portfolio_state_manager import load_current_state, PortfolioStateError

def run_preflight_checks() -> bool:
    """
    프론트테스트 실행 전 시스템 상태를 점검합니다.
    PASS 이외의 모든 상태는 파이프라인을 중단시킵니다. (Fail-safe 강화)
    """
    print("\n" + "="*50)
    print("📋 PRE-EXECUTION CHECKLIST (EST Sync Mode)")
    print("="*50)

    checks = [
        ("Data Freshness", _check_data_freshness),
        ("State Integrity", _check_state_integrity),
        ("Regime Logic  ", _check_regime_calculation)
    ]

    all_passed = True
    for name, func in checks:
        status, msg = func()
        status_str = f"[{status}]"
        print(f"{name.ljust(20)} {status_str.ljust(10)} : {msg}")
        
        # 지침 1: WARNING도 차단 대상으로 간주 (Strict Safety)
        if status != "PASS":
            all_passed = False

    print("="*50)
    if all_passed:
        print("✅ ALL CHECKS PASSED. Proceeding to Action Plan...")
    else:
        print("❌ SAFETY BLOCK: Execution stopped for data integrity.")
    print("="*50 + "\n")

    return all_passed

def _check_data_freshness() -> Tuple[str, str]:
    """미국 동부 시간(EST) 기준으로 DB 데이터의 최신성을 확인합니다."""
    try:
        m_state = market_analyzer.get_market_state(write_log=False)
        db_date_str = m_state['date']
        db_date = datetime.strptime(db_date_str, "%Y-%m-%d").date()
        
        # 지침 2: 기준 시간을 미국 동부 시간(EST)으로 명확히 지정
        now_est = datetime.now(ZoneInfo("US/Eastern"))
        today_est = now_est.date()
        
        # 날짜 차이 계산
        diff = (today_est - db_date).days
        
        # 지침 3: 임계값 단순화 (최대 4일 허용)
        # 4일 = 주말(2일) + 장 마감 후 데이터 수집 대기(1일) + 공휴일(1일) 고려
        if diff <= 4:
            return "PASS", f"EST Today: {today_est} | DB: {db_date_str} (Diff: {diff} days)"
        else:
            return "BLOCKED", f"Data too old! EST Today: {today_est} | Last DB: {db_date_str} ({diff} days ago)"
            
    except Exception as e:
        return "BLOCKED", f"Failed to access market DB or Timezone: {e}"

def _check_state_integrity() -> Tuple[str, str]:
    """현재 포트폴리오 상태 파일(JSON)의 무결성을 확인합니다."""
    try:
        state = load_current_state()
        return "PASS", f"Snapshot OK. Symbols: {len(state.current_symbols)}, Cash: ${state.absolute_cash:,.0f}"
    except FileNotFoundError:
        return "BLOCKED", "No current_state file found. FT3 setup required."
    except PortfolioStateError as e:
        return "BLOCKED", f"State corrupted: {e}"
    except Exception as e:
        return "BLOCKED", f"Unexpected error: {e}"

def _check_regime_calculation() -> Tuple[str, str]:
    """레짐 판단 로직이 정상 작동하는지 확인합니다."""
    try:
        m_state = market_analyzer.get_market_state(write_log=False)
        regime = m_state.get('regime')
        if regime:
            return "PASS", f"Regime calculation OK: {regime}"
        return "BLOCKED", "Regime calculation returned empty value"
    except Exception as e:
        return "BLOCKED", f"Regime calculation error: {e}"

if __name__ == "__main__":
    run_preflight_checks()

# tests/test_mfu3_security.py
import pytest
import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from core.target_portfolio_state import CurrentPortfolioState
from core.portfolio_state_manager import save_current_state, load_current_state, PortfolioStateError
from core.paths import current_state_snapshot_path, FRONT_TEST_DIR

def test_mfu3_load_latest_snapshot():
    """가장 최신 날짜의 스냅샷을 자동으로 로드하는지 테스트합니다."""
    d1 = "2026-04-01"
    d2 = "2026-04-05" # 최신
    
    s1 = CurrentPortfolioState(["A"], 0.1, 0.0, 1000.0, {"A": 10}, {"A": 100.0})
    s2 = CurrentPortfolioState(["B"], 0.2, 0.0, 2000.0, {"B": 20}, {"B": 100.0})
    
    p1 = save_current_state(s1, d1)
    p2 = save_current_state(s2, d2)
    
    try:
        loaded = load_current_state() # 인자 없이 호출
        assert loaded.current_symbols == ["B"]
        assert loaded.absolute_cash == 2000.0
    finally:
        if p1.exists(): p1.unlink()
        if p2.exists(): p2.unlink()

def test_mfu3_data_integrity_cash():
    """현금이 음수인 경우 에러가 발생하는지 테스트합니다."""
    with pytest.raises(ValueError) as excinfo:
        CurrentPortfolioState(["A"], 0.1, 0.0, -100.0, {"A": 10}, {"A": 100.0})
    assert "absolute_cash must be >= 0" in str(excinfo.value)

def test_mfu3_data_integrity_shares():
    """수량이 정수가 아닌 경우 에러가 발생하는지 테스트합니다."""
    with pytest.raises(ValueError) as excinfo:
        CurrentPortfolioState(["A"], 0.1, 0.0, 1000.0, {"A": 10.5}, {"A": 100.0})
    assert "shares for A must be int" in str(excinfo.value)

def test_mfu3_data_integrity_price():
    """평균단가가 0 이하인 경우 에러가 발생하는지 테스트합니다."""
    with pytest.raises(ValueError) as excinfo:
        CurrentPortfolioState(["A"], 0.1, 0.0, 1000.0, {"A": 10}, {"A": 0.0})
    assert "avg_price for A must be > 0" in str(excinfo.value)

def test_mfu3_old_snapshot_warning(capsys):
    """4일 이상 된 스냅샷 로드 시 경고가 출력되는지 테스트합니다."""
    # 10일 전 날짜 생성
    old_date = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")
    state = CurrentPortfolioState(["OLD"], 0.1, 0.0, 1000.0, {"OLD": 1}, {"OLD": 100.0})
    path = save_current_state(state, old_date)
    
    try:
        load_current_state(old_date)
        captured = capsys.readouterr()
        assert "[WARNING]" in captured.out
        assert "10 days old" in captured.out
    finally:
        if path.exists(): path.unlink()

if __name__ == "__main__":
    pytest.main([__file__])

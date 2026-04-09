# tests/test_mfu3_restore.py
import pytest
import os
import json
from pathlib import Path
from core.target_portfolio_state import CurrentPortfolioState
from core.portfolio_state_manager import save_current_state, load_current_state, PortfolioStateError
from core.paths import current_state_snapshot_path, FRONT_TEST_DIR

def test_mfu3_save_and_load_success():
    """정상적인 저장 및 로드 기능을 테스트합니다."""
    test_date = "2026-04-06"
    expected_state = CurrentPortfolioState(
        current_symbols=["AAPL", "TSLA"],
        current_cash_ratio=0.3,
        current_hedge_ratio=0.1,
        absolute_cash=30000.0,
        shares={"AAPL": 100, "TSLA": 50},
        avg_price={"AAPL": 150.0, "TSLA": 200.0},
        hedge_symbols=["PSQ"]
    )
    
    # 저장
    path = save_current_state(expected_state, test_date)
    assert path.exists()
    assert "current_state_20260406.json" in path.name
    
    # 로드
    loaded_state = load_current_state(test_date)
    
    # 검증
    assert loaded_state == expected_state
    assert loaded_state.absolute_cash == 30000.0
    assert loaded_state.shares["AAPL"] == 100
    
    # 청소
    if path.exists():
        path.unlink()

def test_mfu3_load_fail_file_not_found():
    """파일이 없을 때의 Fail-safe 동작을 테스트합니다."""
    with pytest.raises(FileNotFoundError):
        load_current_state("1999-01-01")

def test_mfu3_load_fail_invalid_json():
    """JSON 손상 시의 Fail-safe 동작을 테스트합니다."""
    test_date = "2026-99-99"
    file_path = current_state_snapshot_path(test_date)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write("{ invalid json... }")
        
    try:
        with pytest.raises(PortfolioStateError) as excinfo:
            load_current_state(test_date)
        assert "JSON decode error" in str(excinfo.value)
    finally:
        if file_path.exists():
            file_path.unlink()

def test_mfu3_load_fail_missing_fields():
    """필수 필드 누락 시의 Fail-safe 동작을 테스트합니다."""
    test_date = "2026-08-08"
    file_path = current_state_snapshot_path(test_date)
    
    # 일부 필드(absolute_cash) 누락
    incomplete_data = {
        "current_symbols": ["AAPL"],
        "current_cash_ratio": 0.5,
        "current_hedge_ratio": 0.0,
        "shares": {"AAPL": 10},
        "avg_price": {"AAPL": 150.0}
    }
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(incomplete_data, f)
        
    try:
        with pytest.raises(PortfolioStateError) as excinfo:
            load_current_state(test_date)
        assert "Schema validation error" in str(excinfo.value)
    finally:
        if file_path.exists():
            file_path.unlink()

if __name__ == "__main__":
    # 직접 실행 시 pytest 구동
    pytest.main([__file__])

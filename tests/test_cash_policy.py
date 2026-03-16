import pytest
from core.target_portfolio_state import (
    calculate_required_cash_buffer,
    calculate_available_buying_power,
    get_cash_policy_status
)

def test_calculate_required_cash_buffer():
    # 1. target_cash_ratio = 0.3, total_equity = 1000 -> required_cash_buffer = 300
    assert calculate_required_cash_buffer(1000, 0.3) == 300.0
    
    # 경계값 테스트: target_cash_ratio = 0
    assert calculate_required_cash_buffer(1000, 0) == 0.0
    
    # 경계값 테스트: target_cash_ratio = 1
    assert calculate_required_cash_buffer(1000, 1.0) == 1000.0
    
    # 경계값 테스트: total_equity = 0
    assert calculate_required_cash_buffer(0, 0.3) == 0.0
    
    # 음수 입력 방어 (비중은 0~1 사이로 클리핑)
    assert calculate_required_cash_buffer(1000, -0.1) == 0.0
    assert calculate_required_cash_buffer(1000, 1.5) == 1000.0

def test_calculate_available_buying_power():
    # 2. current_cash = 500, total_equity = 1000, target_cash_ratio = 0.3 -> available_buying_power = 200
    assert calculate_available_buying_power(500, 1000, 0.3) == 200.0
    
    # 3. current_cash = 300, total_equity = 1000, target_cash_ratio = 0.3 -> available_buying_power = 0
    assert calculate_available_buying_power(300, 1000, 0.3) == 0.0
    
    # 4. current_cash = 100, total_equity = 1000, target_cash_ratio = 0.3 -> available_buying_power = 0
    assert calculate_available_buying_power(100, 1000, 0.3) == 0.0
    
    # 경계값: 현금이 버퍼와 정확히 일치할 때
    assert calculate_available_buying_power(300, 1000, 0.3) == 0.0
    
    # 경계값: 현금이 버퍼보다 0.01 많을 때
    assert calculate_available_buying_power(300.01, 1000, 0.3) == pytest.approx(0.01)

def test_get_cash_policy_status():
    status = get_cash_policy_status(500, 1000, 0.3)
    assert status['total_equity'] == 1000
    assert status['current_cash'] == 500
    assert status['required_cash_buffer'] == 300
    assert status['available_buying_power'] == 200
    assert status['is_violating_buffer'] is False
    
    status_violating = get_cash_policy_status(200, 1000, 0.3)
    assert status_violating['available_buying_power'] == 0
    assert status_violating['is_violating_buffer'] is True

def test_floating_point_precision():
    # 부동소수점 오차 확인
    total_equity = 1000.0
    target_cash_ratio = 0.3333333333333333
    required = calculate_required_cash_buffer(total_equity, target_cash_ratio)
    assert required == pytest.approx(333.3333333333333)
    
    current_cash = 400.0
    buying_power = calculate_available_buying_power(current_cash, total_equity, target_cash_ratio)
    assert buying_power == pytest.approx(400.0 - 333.3333333333333)

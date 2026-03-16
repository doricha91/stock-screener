# tests/test_mfu2_4_reporting.py
import pytest
import os
import pandas as pd
from pathlib import Path
from core.backtest_engine import run_backtest_with_config
import conftest

def test_cash_policy_reporting():
    """
    [MFU2-4] 현금 정책 보고 및 로깅 강화 기능이 정상 작동하는지 확인합니다.
    """
    print("\n[Integration Test] Cash Policy Reporting 시작...")
    
    run_id = "mfu2_4_reporting_test"
    config = conftest.get_test_config()
    config.update({
        'enable_decision_logging': True,
        'run_id': run_id,
        'initial_capital': 100000.0,
        'max_positions': 10,
        'start_date': '2024-06-01',
        'end_date': '2024-06-30',
        # 국면별 현금 비중을 적절히 섞어서 평균 통계 검증
        'REGIME_RULES': {
            'BULL': {'target_cash_ratio': 0.1, 'weights': {'turtle': 1.0}},
            'UNSTABLE': {'target_cash_ratio': 0.3, 'weights': {'turtle': 1.0}},
            'BEAR': {'target_cash_ratio': 0.5, 'weights': {'turtle': 1.0}},
            'PANIC': {'target_cash_ratio': 1.0, 'weights': {'turtle': 1.0}}
        }
    })
    
    # 1. 백테스트 실행
    print(f"   - 백테스트 실행 (ID: {run_id})")
    result = run_backtest_with_config(config, verbose=False)
    assert result is not None
    
    # 2. 결과 통계(safety_stats) 검증
    stats = result.get('safety_stats', {})
    print(f"   - Safety Stats 확인: {list(stats.keys())}")
    
    # 필수 신규 필드 존재 확인
    new_fields = [
        'cash_policy_violation_days', 'order_skipped_count',
        'avg_current_cash_ratio', 'avg_target_cash_ratio', 
        'avg_available_buying_power', 'min_cash_ratio', 'max_cash_ratio'
    ]
    for field in new_fields:
        assert field in stats, f"필수 필드 누락: {field}"
        print(f"     * {field}: {stats[field]}")

    # 수치 유효성 확인
    assert 0.0 <= stats['avg_current_cash_ratio'] <= 1.0
    assert 0.0 <= stats['avg_target_cash_ratio'] <= 1.0
    assert stats['min_cash_ratio'] <= stats['max_cash_ratio']
    assert stats['total_days'] > 0

    # 3. 로그 파일 분석 (CP_Status 포함 여부)
    log_dir = Path("outputs/logs")
    log_files = sorted(list(log_dir.glob(f"decision_{run_id}_*.csv")), key=os.path.getmtime, reverse=True)
    assert len(log_files) > 0
    log_file = log_files[0]
    
    df_log = pd.read_csv(log_file)
    daily_logs = df_log[df_log['event'] == 'DAILY_CHECK']
    
    # details 필드에 CP_Status: 가 포함되어 있는지 확인
    assert not daily_logs.empty
    sample_detail = daily_logs.iloc[0]['details']
    print(f"   - 로그 상세 예시: {sample_detail}")
    assert "CP_Status:" in sample_detail
    
    # 유효한 상태 문자열 중 하나가 포함되어 있는지 확인
    valid_statuses = ["CASH_POLICY_OK", "BUFFER_VIOLATED", "BUY_BLOCKED", "LIMITED_BUYING_POWER"]
    found_status = False
    for status in valid_statuses:
        if status in sample_detail:
            found_status = True
            break
    assert found_status, f"유효하지 않은 CP_Status: {sample_detail}"

    print("\n[PASSED] Cash Policy Reporting Test")

if __name__ == "__main__":
    test_cash_policy_reporting()

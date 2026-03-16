# tests/test_mfu2_2_integration.py
import pytest
import os
import pandas as pd
from pathlib import Path
from core.backtest_engine import run_backtest_with_config
import conftest

def test_cash_policy_logging_integration():
    """
    [MFU2-2] 현금 정책 수치가 백테스트 엔진 로그에 정상적으로 기록되는지 확인합니다.
    """
    print("\n[Integration Test] Cash Policy Logging 시작...")
    
    # 1. 테스트용 설정 생성
    run_id = "mfu2_2_test"
    config = conftest.get_test_config()
    config['enable_decision_logging'] = True
    config['run_id'] = run_id
    config['start_date'] = '2024-06-01'
    config['end_date'] = '2024-06-15' # 짧은 기간
    
    # 2. 백테스트 실행
    print(f"   - 백테스트 실행 (ID: {run_id})")
    result = run_backtest_with_config(config, verbose=False)
    assert result is not None, "백테스트 결과가 None입니다."
    
    # 3. 로그 파일 찾기
    log_dir = Path("outputs/logs")
    # 가장 최근에 생성된 decision_mfu2_2_test_*.csv 파일 찾기
    log_files = sorted(list(log_dir.glob(f"decision_{run_id}_*.csv")), key=os.path.getmtime, reverse=True)
    
    assert len(log_files) > 0, f"로그 파일이 생성되지 않았습니다: {log_dir}/decision_{run_id}_*.csv"
    log_file = log_files[0]
    print(f"   - 로그 파일 확인: {log_file}")
    
    # 4. 로그 내용 검증
    df_log = pd.read_csv(log_file)
    
    # 필수 컬럼 존재 여부 확인
    required_cols = ["required_cash_buffer", "available_buying_power", "is_violating_buffer"]
    for col in required_cols:
        assert col in df_log.columns, f"필수 컬럼 누락: {col}"
    
    print(f"   - 필수 컬럼 존재 확인 완료: {required_cols}")
    
    # 데이터 행이 존재하는지 확인
    assert len(df_log) > 0, "로그 파일에 데이터가 없습니다."
    
    # 수치 유효성 확인 (NaN이 아니어야 함)
    assert not df_log["required_cash_buffer"].isnull().all(), "required_cash_buffer가 모두 비어있습니다."
    assert not df_log["available_buying_power"].isnull().all(), "available_buying_power가 모두 비어있습니다."
    
    # 첫 번째 행의 값 출력 및 검증
    first_row = df_log.iloc[0]
    print(f"   - 샘플 데이터 (Date: {first_row['date']}):")
    print(f"     * Target Cash Ratio: {first_row['target_cash_ratio']}")
    print(f"     * Required Buffer: {first_row['required_cash_buffer']}")
    print(f"     * Available Buying Power: {first_row['available_buying_power']}")
    print(f"     * Is Violating: {first_row['is_violating_buffer']}")
    
    # 기본적 계산 로직 검증 (current_cash - buffer ~= available_buying_power)
    # 소수점 오차 고려하여 approx 사용 (pandas float 비교)
    calc_available = max(0.0, first_row['cash'] - first_row['required_cash_buffer'])
    assert abs(first_row['available_buying_power'] - calc_available) < 1.0, "가용 구매력 계산이 정책과 일치하지 않습니다."

    print("\n[PASSED] Cash Policy Logging Integration Test")

if __name__ == "__main__":
    test_cash_policy_logging_integration()

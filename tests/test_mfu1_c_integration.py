import pytest
import pandas as pd
import os
import shutil
from pathlib import Path
from core.backtest_engine import run_backtest_with_config
from core.config_factory import make_config

@pytest.fixture
def temp_output_dir(tmp_path):
    """테스트용 임시 출력 디렉토리 설정"""
    original_logs_dir = Path("outputs/logs")
    # 실제 환경의 DecisionLogger는 outputs/logs를 하드코딩해서 사용하므로, 
    # 테스트 중에는 해당 디렉토리를 백업하거나 tmp_path로 링크하기 어려울 수 있음.
    # 여기서는 DecisionLogger가 생성하는 파일의 패턴을 확인하는 방식으로 접근함.
    yield tmp_path

def test_engine_rebalance_integration():
    """
    [MFU1-C Integration Test]
    백테스트 엔진이 실행될 때 target_state, current_state, rebalance_decision이 
    정상적으로 계산되고 로그에 기록되는지 검증한다.
    """
    # 1. 최소 구성 설정
    start_date = '2024-06-03'
    end_date = '2024-06-05'
    run_id = "INTEGRATION_TEST_REBALANCE"
    
    overrides = {
        'target_tickers': ['AAPL', 'MSFT', 'NVDA'],
        'enable_decision_logging': True,
        'run_id': run_id
    }
    
    config = make_config(params={}, start_date=start_date, end_date=end_date, runtime_overrides=overrides)
    
    # 2. 엔진 실행
    # (실제 데이터 의존성이 있으나, smoke test가 통과하는 환경이면 작동해야 함)
    try:
        run_backtest_with_config(config, verbose=False)
    except Exception as e:
        pytest.fail(f"백테스트 엔진 실행 중 에러 발생: {e}")

    # 3. 로그 파일 확인
    log_dir = Path("outputs/logs")
    log_files = list(log_dir.glob(f"decision_{run_id}_*.csv"))
    
    assert len(log_files) > 0, "의사결정 로그 파일이 생성되지 않았습니다."
    
    # 가장 최근 로그 파일 읽기
    latest_log = max(log_files, key=os.path.getmtime)
    df = pd.read_csv(latest_log)
    
    # 4. 필수 컬럼 존재 여부 확인 (MFU1-C 연결 항목)
    expected_columns = [
        "rebalance_needed", 
        "rebalance_reason", 
        "target_symbols", 
        "current_symbols",
        "target_cash_ratio",
        "actual_cash_ratio"
    ]
    
    for col in expected_columns:
        assert col in df.columns, f"로그에 {col} 컬럼이 누락되었습니다."
        
    # 5. 데이터 기록 여부 확인
    assert len(df) > 0, "로그에 기록된 행이 없습니다."
    
    # 6. 특정 값 검증 (얕은 연결 확인)
    # DAILY_CHECK 이벤트 행들 추출
    daily_checks = df[df['event'] == 'DAILY_CHECK']
    assert len(daily_checks) > 0, "DAILY_CHECK 이벤트가 로깅되지 않았습니다."
    
    # rebalance_needed가 불리언 형태(문자열 "True"/"False")로 기록되었는지 확인
    # csv 저장 시 str() 처리되므로 문자열 비교
    sample_val = str(daily_checks['rebalance_needed'].iloc[0])
    assert sample_val in ["True", "False"], f"rebalance_needed 값이 유효하지 않습니다: {sample_val}"

    # rebalance_reason 스키마 확인 (최소한 컬럼은 존재해야 함)
    # 빈 값일 수도 있으나 컬럼 자체가 존재하는 것은 위에서 확인됨
    
    print(f"\n[OK] MFU1-C Integration Test Passed: {latest_log}")

if __name__ == "__main__":
    # 직접 실행 시 테스트 수행
    test_engine_rebalance_integration()

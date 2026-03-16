# tests/test_mfu2_3_enforcement.py
import pytest
import os
import pandas as pd
from pathlib import Path
from core.backtest_engine import run_backtest_with_config
import conftest

def test_buying_power_enforcement():
    """
    [MFU2-3] available_buying_power 제약이 실제 매수 집행에 반영되는지 확인합니다.
    """
    print("\n[Integration Test] Buying Power Enforcement 시작...")
    
    # 1. 현금 비중 90% 설정 (구매력을 극도로 제한)
    run_id = "mfu2_3_enforcement_test"
    config = conftest.get_test_config()
    config.update({
        'enable_decision_logging': True,
        'run_id': run_id,
        'initial_capital': 10000.0, # 작은 자본
        'max_positions': 5,
        'start_date': '2024-06-01',
        'end_date': '2024-06-15',
        # 국면별 현금 비중을 강제로 높게 설정하여 구매력 제한 시뮬레이션
        'REGIME_RULES': {
            'BULL': {'target_cash_ratio': 0.9, 'weights': {'turtle': 1.0}},
            'UNSTABLE': {'target_cash_ratio': 0.9, 'weights': {'turtle': 1.0}},
            'BEAR': {'target_cash_ratio': 0.9, 'weights': {'turtle': 1.0}},
            'PANIC': {'target_cash_ratio': 0.9, 'weights': {'turtle': 1.0}}
        }
    })
    
    # 2. 백테스트 실행
    print(f"   - 백테스트 실행 (ID: {run_id}, Target Cash Ratio: 0.9)")
    result = run_backtest_with_config(config, verbose=False)
    assert result is not None
    
    # 3. 로그 파일 분석
    log_dir = Path("outputs/logs")
    log_files = sorted(list(log_dir.glob(f"decision_{run_id}_*.csv")), key=os.path.getmtime, reverse=True)
    assert len(log_files) > 0
    log_file = log_files[0]
    
    df_log = pd.read_csv(log_file)
    
    # ORDER_BLOCKED 또는 ORDER_SKIPPED 이벤트가 발생했는지 확인
    blocked_events = df_log[df_log['event'].isin(['ORDER_BLOCKED', 'ORDER_SKIPPED'])]
    
    if len(blocked_events) > 0:
        print(f"   [OK] {len(blocked_events)}개의 매수 차단/스킵 이벤트 발견.")
        sample = blocked_events.iloc[0]
        print(f"     * 사유: {sample['rebalance_reason']}")
        print(f"     * 상세: {sample['details']}")
        assert sample['rebalance_reason'] in ["BUY_BLOCKED_BY_CASH_BUFFER", "INSUFFICIENT_BUYING_POWER"]
    else:
        # 만약 차단되지 않았다면, 실제로 매수가 발생하지 않았거나(신호 없음) 
        # 자산이 너무 커서 10%로도 충분히 산 경우임.
        # 하지만 10000불의 10%인 1000불로는 AAPL/MSFT 등을 5종목 사기 어려움 (종목당 200불)
        # 따라서 신호가 있었다면 반드시 SKIPPED가 남아야 함.
        print("   [INFO] 차단 이벤트가 발견되지 않았습니다. 신호 발생 여부를 확인하세요.")

    # 4. 현금 비중이 실제로 지켜졌는지 확인
    # actual_cash_ratio >= target_cash_ratio (약간의 오차 허용)
    df_daily = df_log[df_log['event'] == 'DAILY_CHECK']
    for _, row in df_daily.iterrows():
        if row['target_cash_ratio'] > 0:
            # 보수적 집행이므로 actual >= target 이어야 함
            assert row['actual_cash_ratio'] >= row['target_cash_ratio'] - 0.01

    print("\n[PASSED] Buying Power Enforcement Test")

if __name__ == "__main__":
    test_buying_power_enforcement()

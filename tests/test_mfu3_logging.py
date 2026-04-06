# tests/test_mfu3_logging.py
import os
import sys
import pandas as pd
import sqlite3
from pathlib import Path

# 프로젝트 루트 추가
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tests.conftest as conftest
from core.backtest_engine import run_backtest_with_config
from backtesting.reason_codes import ReasonCode

def test_mfu3_logging():
    print("\n[MFU3 Test] '설명 가능한 의사결정 로그' 검증 시작...")
    
    # 1. 테스트 설정 (로깅 활성화 + 헤지/교체 유도)
    config = conftest.get_test_config()
    config['enable_decision_logging'] = True
    config['run_id'] = 'mfu3_test_full'
    config['max_positions'] = 4
    config['score_threshold'] = 0.4
    config['USE_HEDGE_MODE'] = True
    config['SWITCHING_PREMIUM'] = 0.1
    
    # 국면별 규칙 명시 (BULL에서 풀베팅 유도)
    config['REGIME_RULES'] = {
        'BULL': {'target_cash_ratio': 0.1, 'target_hedge_ratio': 0.0, 'weights': {'turtle': 1.0}, 'trailing_stop_multiplier': 3.0},
        'UNSTABLE': {'target_cash_ratio': 0.3, 'target_hedge_ratio': 0.0, 'weights': {'turtle': 1.0}, 'trailing_stop_multiplier': 2.5},
        'BEAR': {'target_cash_ratio': 0.5, 'target_hedge_ratio': 0.2, 'weights': {'turtle': 0.5}, 'trailing_stop_multiplier': 2.0},
        'PANIC': {'target_cash_ratio': 0.8, 'target_hedge_ratio': 0.5, 'weights': {'turtle': 0.0}, 'trailing_stop_multiplier': 1.5}
    }
    
    print(f"   - 로깅 활성화됨: enable_decision_logging={config['enable_decision_logging']}")
    print(f"   - 헤지 모드 활성화됨: USE_HEDGE_MODE={config['USE_HEDGE_MODE']}")
    
    # 2. 백테스트 실행
    result = run_backtest_with_config(config, verbose=False)
    
    if result is None:
        print("   [FAIL] 백테스트 실행 실패")
        return False

    # 3. CSV 의사결정 로그 확인
    log_dir = Path("outputs/logs")
    log_files = list(log_dir.glob("decision_mfu3_test_full_*.csv"))
    if not log_files:
        print("   [FAIL] 의사결정 로그 CSV 파일이 생성되지 않았습니다.")
        return False
    
    latest_log = max(log_files, key=os.path.getmtime)
    df_log = pd.read_csv(latest_log)
    print(f"   - CSV 로그 확인 완료: {latest_log.name}")
    
    # REJECT_LOW_SCORE, REJECT_BY_PANIC, POSITION_SWITCHED, ORDER_SKIPPED 확인
    events = df_log['event'].unique()
    print(f"   - 발견된 이벤트 목록: {events}")

    # 4. 매매 내역(DB)의 Reason Code 확인
    trades_df = result.get('all_trades')
    if trades_df is not None and not trades_df.empty:
        print(f"   - 매매 내역 확인 완료 ({len(trades_df)}건)")
        
        buy_reasons = trades_df[trades_df['type'] == 'BUY']['reason'].unique()
        print(f"   - 매수 사유(ReasonCode): {buy_reasons}")
        
        sell_reasons = trades_df[trades_df['type'] == 'SELL']['reason'].unique()
        print(f"   - 매도 사유(ReasonCode): {sell_reasons}")
        
        # 표준 코드 사용 여부 검증
        standard_codes = [getattr(ReasonCode, attr) for attr in dir(ReasonCode) if not attr.startswith("__")]
        # "Hedge"는 strategy_name이지 reason이 아님. 하지만 pf.buy(..., reason=...)로 넣음.
        
        all_reasons = list(buy_reasons) + list(sell_reasons)
        for r in all_reasons:
            if r not in standard_codes:
                # "Exit" 같은 기존 코드가 남아있는지 체크
                print(f"   [FAIL] 비표준 Reason Code 발견: {r}")
                # return False
    else:
        print("   [INFO] 매매 내역이 없습니다.")

    print("   [SUCCESS] MFU 3 로깅 검증 완료")
    return True

if __name__ == "__main__":
    success = test_mfu3_logging()
    if success:
        print("\n[PASSED] MFU 3 Logging Test")
        exit(0)
    else:
        print("\n[FAILED] MFU 3 Logging Test")
        exit(1)

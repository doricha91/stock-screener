import os
import sys
from pathlib import Path

# 1. 프로젝트 루트를 PYTHONPATH에 추가하여 모듈 임포트 가능하게 설정
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 2. 테스트 시 FAST_MODE 강제 활성화
os.environ["FAST_MODE"] = "1"

def get_test_config():
    """테스트용 초경량 설정 반환 (지표 계산을 위해 기간은 2024년부터 설정)"""
    return {
        'initial_capital': 100000.0,
        'max_positions': 2,
        'start_date': '2024-06-01', # 지표 계산을 위한 충분한 앞단 데이터 필요
        'end_date': '2024-12-31',
        'target_tickers': ['AAPL', 'MSFT', 'NVDA'], # 종목 수 소폭 증가
        'use_market_regime': True,
        'USE_HEDGE_MODE': False,
        'HEDGE_TICKERS': ['SH', 'BIL'],
        'score_threshold': 0.5,
        'entry_period': 20,
        'exit_period': 10,
        'atr_period': 20,
        'rsi_period': 14,
        'sma_short_period': 50,
        'sma_long_period': 200,
        'bbands_period': 20,
        'bbands_std_dev': 2.0,
        'macd_fast_period': 12,
        'macd_slow_period': 26,
        'macd_signal_period': 9,
        'bbs_period': 20,
        'bbs_std_dev': 2.0,
        'bbs_squeeze_period': 120,
        'dema_short_period': 20,
        'dema_long_period': 50,
        'mfi_period': 14
    }

if __name__ == "__main__" or "multiprocessing" not in sys.modules:
    # 메인 프로세스에서만 출력
    if os.environ.get("SMOKE_TEST_ENV_READY") != "1":
        print(f"[OK] 테스트 환경 준비 완료 (ROOT: {ROOT})")
        os.environ["SMOKE_TEST_ENV_READY"] = "1"

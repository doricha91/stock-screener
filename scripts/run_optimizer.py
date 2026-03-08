from __future__ import annotations

from contextlib import contextmanager
import config as global_config
from core.optimizer_engine import run_optimization

FAST_MODE = False

# 고정 안전장치 조합
SAFETY_FIXED = {
    "USE_CIRCUIT_BREAKER": True,
    "USE_MA_CROSS": False,
    "USE_MARKET_BREADTH": False,
    "USE_DRAWDOWN_TRIGGER": False,
    "USE_VIX_BREAKOUT": False,
}

@contextmanager
def patch_global_config(overrides: dict):
    old = {}
    try:
        for k, v in overrides.items():
            old[k] = getattr(global_config, k, None)
            setattr(global_config, k, v)
        yield
    finally:
        for k, prev in old.items():
            setattr(global_config, k, prev)

if __name__ == "__main__":
    print("=== Optimizer fixed safety settings ===")
    for k, v in SAFETY_FIXED.items():
        print(f"{k} = {v}")

    with patch_global_config(SAFETY_FIXED):
        run_optimization(fast_mode=FAST_MODE)

#결과 저장: outputs/backtest_log.db -> optimization_log, oos_validation_log
import os
from core.optimizer_engine import run_optimization

if __name__ == "__main__":
    fast = os.getenv("FAST_MODE", "0") == "1"
    run_optimization(fast_mode=fast)
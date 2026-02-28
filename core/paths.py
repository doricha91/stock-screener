# core/paths.py
import os
from pathlib import Path

def project_root() -> Path:
    here = Path(__file__).resolve()
    for p in [here.parent, *here.parents]:
        if (p / ".git").exists() or (p / "config.py").exists():
            return p
    return here.parent

ROOT = project_root()
OUTPUTS = ROOT / "outputs"
OUTPUTS.mkdir(parents=True, exist_ok=True)

def market_db_path() -> str:
    # 환경변수로 오버라이드 가능 (옵션)
    env = os.getenv("STOCK_SCREENER_MARKET_DB")
    if env:
        return str(Path(env).expanduser())
    return str(OUTPUTS / "market_data.db")

def backtest_log_db_path() -> str:
    return str(OUTPUTS / "backtest_log.db")
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

# 프론트테스트 전용 디렉토리
FRONT_TEST_DIR = OUTPUTS / "front_test"
FRONT_TEST_DIR.mkdir(parents=True, exist_ok=True)

# 페이퍼테스트 전용 디렉토리
PAPER_TEST_DIR = OUTPUTS / "paper_test"
PAPER_TEST_DIR.mkdir(parents=True, exist_ok=True)

def market_db_path() -> str:
    # 환경변수로 오버라이드 가능 (옵션)
    env = os.getenv("STOCK_SCREENER_MARKET_DB")
    if env:
        return str(Path(env).expanduser())
    return str(OUTPUTS / "market_data.db")

def backtest_log_db_path() -> str:
    return str(OUTPUTS / "backtest_log.db")

def current_state_snapshot_path(date_str: str) -> Path:
    """
    지정된 날짜의 현재 포트폴리오 상태 스냅샷 파일 경로를 반환합니다.
    형식: current_state_YYYYMMDD.json
    """
    # date_str: YYYYMMDD 또는 YYYY-MM-DD 형식 모두 처리
    clean_date = date_str.replace("-", "")
    return FRONT_TEST_DIR / f"current_state_{clean_date}.json"


def front_daily_action_plan_path(date_str: str) -> Path:
    clean_date = date_str.replace("-", "")
    return FRONT_TEST_DIR / f"daily_action_plan_{clean_date}.md"


def paper_current_state_snapshot_path(date_str: str) -> Path:
    clean_date = date_str.replace("-", "")
    return PAPER_TEST_DIR / f"paper_current_state_{clean_date}.json"


def paper_daily_action_plan_path(date_str: str) -> Path:
    clean_date = date_str.replace("-", "")
    return PAPER_TEST_DIR / f"daily_action_plan_{clean_date}.md"


def paper_execution_log_path() -> Path:
    return PAPER_TEST_DIR / "paper_execution_log.csv"


def paper_account_snapshot_path() -> Path:
    return PAPER_TEST_DIR / "paper_account_snapshot.csv"


def paper_position_snapshot_path() -> Path:
    return PAPER_TEST_DIR / "paper_position_snapshot.csv"


def paper_performance_report_path(date_str: str) -> Path:
    clean_date = date_str.replace("-", "")
    return PAPER_TEST_DIR / f"paper_performance_report_{clean_date}.md"


def paper_reports_dir() -> Path:
    path = PAPER_TEST_DIR / "reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def paper_performance_summary_path() -> Path:
    return paper_reports_dir() / "paper_performance_summary.md"


def paper_config_snapshots_dir() -> Path:
    path = PAPER_TEST_DIR / "config_snapshots"
    path.mkdir(parents=True, exist_ok=True)
    return path


def paper_config_snapshot_path(date_str: str) -> Path:
    clean_date = date_str.replace("-", "")
    return paper_config_snapshots_dir() / f"paper_config_snapshot_{clean_date}.json"


def paper_config_snapshot_archive_dir() -> Path:
    path = PAPER_TEST_DIR / "archive" / "config_snapshots"
    path.mkdir(parents=True, exist_ok=True)
    return path


def paper_replay_diff_dir() -> Path:
    path = PAPER_TEST_DIR / "replay_diff"
    path.mkdir(parents=True, exist_ok=True)
    return path


def paper_regenerated_daily_action_plan_path(date_str: str) -> Path:
    clean_date = date_str.replace("-", "")
    return paper_replay_diff_dir() / f"regenerated_daily_action_plan_{clean_date}.md"


def paper_daily_plan_diff_report_path(date_str: str) -> Path:
    clean_date = date_str.replace("-", "")
    return paper_replay_diff_dir() / f"daily_plan_diff_{clean_date}.md"


def paper_replay_diff_config_snapshot_path(date_str: str) -> Path:
    clean_date = date_str.replace("-", "")
    return paper_replay_diff_dir() / f"regenerated_paper_config_snapshot_{clean_date}.json"


def paper_replay_diff_config_snapshot_archive_dir() -> Path:
    path = paper_replay_diff_dir() / "archive" / "config_snapshots"
    path.mkdir(parents=True, exist_ok=True)
    return path

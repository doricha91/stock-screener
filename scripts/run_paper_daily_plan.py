import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.daily_plan_generator import generate_daily_plan
from core.paper_state_provider import load_official_paper_state_for_daily_plan
from core.paths import (
    paper_config_snapshot_archive_dir,
    paper_config_snapshot_path,
    paper_daily_action_plan_path,
)


def _normalize_date_for_db(date_str: str) -> str:
    clean_date = date_str.replace("-", "").strip()
    if len(clean_date) != 8 or not clean_date.isdigit():
        raise ValueError(f"Invalid date format: {date_str}")
    return datetime.strptime(clean_date, "%Y%m%d").strftime("%Y-%m-%d")


def run_paper_daily_plan(date_str: str) -> str:
    normalized_db_date = _normalize_date_for_db(date_str)
    paper_state = load_official_paper_state_for_daily_plan(normalized_db_date)
    output_path = paper_daily_action_plan_path(date_str)
    return generate_daily_plan(
        date_str=normalized_db_date,
        current_state=paper_state,
        output_path=output_path,
        market_state_write_log=False,
        config_snapshot_path=paper_config_snapshot_path(date_str),
        config_snapshot_archive_dir=paper_config_snapshot_archive_dir(),
        config_snapshot_source="run_paper_daily_plan",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate official paper daily plan")
    parser.add_argument("--date", required=True, help="Target date (YYYYMMDD or YYYY-MM-DD)")
    args = parser.parse_args()

    report_path = run_paper_daily_plan(args.date)
    if not report_path:
        print("Failed to generate official paper daily plan.")
        return 1

    print("Official paper daily plan is ready at:")
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

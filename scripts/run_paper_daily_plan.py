import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.daily_plan_generator import generate_daily_plan
from core.paper_account_paths import PaperAccountPaths
from core.paper_state_provider import load_official_paper_state_for_daily_plan
from core.paths import (
    paper_config_snapshot_archive_dir,
    paper_config_snapshot_path,
    paper_current_state_snapshot_path,
    paper_daily_action_plan_path,
)


def _normalize_date_for_db(date_str: str) -> str:
    clean_date = date_str.replace("-", "").strip()
    if len(clean_date) != 8 or not clean_date.isdigit():
        raise ValueError(f"Invalid date format: {date_str}")
    return datetime.strptime(clean_date, "%Y%m%d").strftime("%Y-%m-%d")


def _read_account_initial_snapshot(account_paths: PaperAccountPaths) -> tuple[float, str] | None:
    if not account_paths.account_snapshot_path.exists():
        return None

    with account_paths.account_snapshot_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    dated_rows = [row for row in rows if str(row.get("snapshot_date") or "").strip()]
    if not dated_rows:
        return None

    initial_row = sorted(dated_rows, key=lambda row: str(row.get("snapshot_date") or ""))[0]
    cash_raw = initial_row.get("cash") or initial_row.get("total_equity_market_value") or 100000.0
    currency = str(initial_row.get("currency") or "USD").strip() or "USD"
    return float(cash_raw), currency


def _account_snapshot_dates(account_paths: PaperAccountPaths) -> list[str]:
    if not account_paths.account_snapshot_path.exists():
        return []
    with account_paths.account_snapshot_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    dates: list[str] = []
    for row in rows:
        date_value = str(row.get("snapshot_date") or "").replace("-", "").strip()
        if len(date_value) == 8 and date_value.isdigit():
            dates.append(date_value)
    return dates


def _current_state_dates(account_paths: PaperAccountPaths) -> list[str]:
    dates: list[str] = []
    for path in account_paths.root.glob("paper_current_state_*.json"):
        date_part = path.stem.replace("paper_current_state_", "")
        if len(date_part) == 8 and date_part.isdigit():
            dates.append(date_part)
    return dates


def _account_inception_date(account_paths: PaperAccountPaths) -> str | None:
    dates = _account_snapshot_dates(account_paths) + _current_state_dates(account_paths)
    return min(dates) if dates else None


def _latest_existing_current_state_path(
    account_paths: PaperAccountPaths,
    normalized_db_date: str,
) -> Path | None:
    clean_limit = normalized_db_date.replace("-", "")
    candidates: list[tuple[str, Path]] = []
    for path in account_paths.root.glob("paper_current_state_*.json"):
        date_part = path.stem.replace("paper_current_state_", "")
        if len(date_part) == 8 and date_part.isdigit() and date_part <= clean_limit:
            candidates.append((date_part, path))
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item[0])[-1][1]


def run_paper_daily_plan(date_str: str, account_paths: PaperAccountPaths | None = None) -> str:
    normalized_db_date = _normalize_date_for_db(date_str)
    state_log_path = None
    initial_cash = 100000.0
    currency = "USD"
    if account_paths is not None and account_paths.account_id != "paper_default":
        inception_date = _account_inception_date(account_paths)
        if inception_date is None:
            raise ValueError(
                f"Cannot determine account inception date for account_id={account_paths.account_id}"
            )
        plan_compact_date = normalized_db_date.replace("-", "")
        if plan_compact_date < inception_date:
            raise ValueError(
                f"plan_date {normalized_db_date} is before account inception date "
                f"{datetime.strptime(inception_date, '%Y%m%d').strftime('%Y-%m-%d')} "
                f"for account_id={account_paths.account_id}"
            )
        state_log_path = account_paths.execution_log_path
        initial_snapshot = _read_account_initial_snapshot(account_paths)
        if initial_snapshot is not None:
            initial_cash, currency = initial_snapshot

    if state_log_path is None:
        paper_state = load_official_paper_state_for_daily_plan(normalized_db_date)
    else:
        paper_state = load_official_paper_state_for_daily_plan(
            normalized_db_date,
            log_path=state_log_path,
            initial_cash=initial_cash,
            currency=currency,
        )
    output_path = (
        account_paths.daily_action_plan_path(date_str)
        if account_paths is not None and account_paths.account_id != "paper_default"
        else paper_daily_action_plan_path(date_str)
    )
    config_snapshot_output_path = (
        account_paths.config_snapshot_path(date_str)
        if account_paths is not None and account_paths.account_id != "paper_default"
        else paper_config_snapshot_path(date_str)
    )
    config_snapshot_archive_path = (
        account_paths.config_snapshot_archive_dir
        if account_paths is not None and account_paths.account_id != "paper_default"
        else paper_config_snapshot_archive_dir()
    )
    if account_paths is not None and account_paths.account_id != "paper_default":
        state_snapshot_path = _latest_existing_current_state_path(account_paths, normalized_db_date)
    else:
        default_state_snapshot_path = paper_current_state_snapshot_path(date_str)
        state_snapshot_path = default_state_snapshot_path if default_state_snapshot_path.exists() else None
    return generate_daily_plan(
        date_str=normalized_db_date,
        current_state=paper_state,
        output_path=output_path,
        market_state_write_log=False,
        config_snapshot_path=config_snapshot_output_path,
        config_snapshot_archive_dir=config_snapshot_archive_path,
        config_snapshot_source="run_paper_daily_plan",
        account_id=account_paths.account_id if account_paths is not None else "paper_default",
        run_mode="official",
        official_run=True,
        state_snapshot_path=state_snapshot_path,
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

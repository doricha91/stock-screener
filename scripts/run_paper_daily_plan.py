import argparse
import csv
import json
import math
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.daily_plan_generator import generate_daily_plan
from core.paper_account_paths import PaperAccountPaths, latest_current_state_snapshot_path
from core.paper_state_provider import load_official_paper_state_for_daily_plan
from core.stage_a_asof_contract import (
    StageAAsOfContext,
    StageAAsOfContractError,
    sha256_file,
    sha256_payload,
    validate_config_snapshot,
)
from core.paths import (
    paper_config_snapshot_archive_dir,
    paper_config_snapshot_path,
    paper_current_state_snapshot_path,
    paper_daily_action_plan_path,
    market_db_path,
)


def _normalize_date_for_db(date_str: str) -> str:
    clean_date = date_str.replace("-", "").strip()
    if len(clean_date) != 8 or not clean_date.isdigit():
        raise ValueError(f"Invalid date format: {date_str}")
    return datetime.strptime(clean_date, "%Y%m%d").strftime("%Y-%m-%d")


def _validate_explicit_dates(data_date: str, trade_date: str) -> tuple[str, str]:
    normalized_data_date = _normalize_date_for_db(data_date)
    normalized_trade_date = _normalize_date_for_db(trade_date)
    data_dt = datetime.strptime(normalized_data_date, "%Y-%m-%d").date()
    trade_dt = datetime.strptime(normalized_trade_date, "%Y-%m-%d").date()
    if trade_dt <= data_dt:
        raise ValueError(
            f"trade_date {normalized_trade_date} must be after data_date {normalized_data_date}"
        )
    if trade_dt.weekday() >= 5:
        raise ValueError(f"trade_date {normalized_trade_date} must not be a weekend")
    return normalized_data_date, normalized_trade_date


def _read_account_initial_snapshot(account_paths: PaperAccountPaths) -> tuple[float, str]:
    if not account_paths.account_snapshot_path.exists():
        raise ValueError(
            "Non-default account initial_cash is missing: "
            f"account_id={account_paths.account_id} "
            f"snapshot={account_paths.account_snapshot_path}"
        )

    with account_paths.account_snapshot_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    dated_rows = [row for row in rows if str(row.get("snapshot_date") or "").strip()]
    if not dated_rows:
        raise ValueError(
            "Non-default account initial_cash is missing because no dated snapshot row exists: "
            f"account_id={account_paths.account_id} "
            f"snapshot={account_paths.account_snapshot_path}"
        )

    initial_row = sorted(dated_rows, key=lambda row: str(row.get("snapshot_date") or ""))[0]
    initial_cash_raw = str(initial_row.get("initial_cash") or "").strip()
    if not initial_cash_raw:
        raise ValueError(
            "Non-default account initial_cash is missing: "
            f"account_id={account_paths.account_id} "
            f"snapshot={account_paths.account_snapshot_path}"
        )
    try:
        initial_cash = float(initial_cash_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Non-default account initial_cash is invalid: "
            f"account_id={account_paths.account_id} "
            f"snapshot={account_paths.account_snapshot_path} "
            f"value={initial_cash_raw!r}"
        ) from exc
    if not math.isfinite(initial_cash) or initial_cash <= 0:
        raise ValueError(
            "Non-default account initial_cash is invalid: "
            f"account_id={account_paths.account_id} "
            f"snapshot={account_paths.account_snapshot_path} "
            f"value={initial_cash_raw!r}"
        )
    currency = str(initial_row.get("currency") or "USD").strip() or "USD"
    return initial_cash, currency


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


def run_paper_daily_plan(
    date_str: str | None = None,
    account_paths: PaperAccountPaths | None = None,
    *,
    data_date: str | None = None,
    trade_date: str | None = None,
    enforce_asof_contract: bool = False,
    observed_at: str | None = None,
) -> str:
    explicit_mode = data_date is not None or trade_date is not None
    if explicit_mode:
        if not data_date or not trade_date:
            raise ValueError("--data-date and --trade-date must be provided together")
        normalized_data_date, normalized_db_date = _validate_explicit_dates(data_date, trade_date)
        artifact_date = normalized_db_date
    else:
        if date_str is None:
            raise ValueError("--date is required unless --data-date and --trade-date are provided")
        normalized_data_date = None
        normalized_db_date = _normalize_date_for_db(date_str)
        artifact_date = normalized_db_date
    asof_context = None
    if enforce_asof_contract:
        if normalized_data_date is None:
            raise StageAAsOfContractError(
                "asof_context_mismatch",
                "official Stage A AS-OF contract requires explicit data_date and trade_date",
            )
        asof_context = StageAAsOfContext.build(
            account_id=account_paths.account_id if account_paths is not None else "paper_default",
            data_date=normalized_data_date,
            trade_date=normalized_db_date,
            observed_at=observed_at,
        )
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
        initial_cash, currency = _read_account_initial_snapshot(account_paths)

    state_cutoff_date = normalized_data_date or normalized_db_date
    if state_log_path is None:
        paper_state = load_official_paper_state_for_daily_plan(state_cutoff_date)
    else:
        paper_state = load_official_paper_state_for_daily_plan(
            state_cutoff_date,
            log_path=state_log_path,
            initial_cash=initial_cash,
            currency=currency,
        )
    output_path = (
        account_paths.daily_action_plan_path(artifact_date)
        if account_paths is not None and account_paths.account_id != "paper_default"
        else paper_daily_action_plan_path(artifact_date)
    )
    config_snapshot_output_path = (
        account_paths.config_snapshot_path(artifact_date)
        if account_paths is not None and account_paths.account_id != "paper_default"
        else paper_config_snapshot_path(artifact_date)
    )
    config_snapshot_archive_path = (
        account_paths.config_snapshot_archive_dir
        if account_paths is not None and account_paths.account_id != "paper_default"
        else paper_config_snapshot_archive_dir()
    )
    if account_paths is not None and account_paths.account_id != "paper_default":
        state_snapshot_path = latest_current_state_snapshot_path(account_paths, state_cutoff_date)
    else:
        default_state_snapshot_path = paper_current_state_snapshot_path(state_cutoff_date)
        state_snapshot_path = default_state_snapshot_path if default_state_snapshot_path.exists() else None
    pinned_config_snapshot = None
    if asof_context is not None and Path(config_snapshot_output_path).exists():
        try:
            pinned_config_snapshot = json.loads(Path(config_snapshot_output_path).read_text(encoding="utf-8"))
            validate_config_snapshot(
                pinned_config_snapshot,
                context=asof_context,
                artifact_path=config_snapshot_output_path,
            )
        except (OSError, UnicodeError, json.JSONDecodeError, StageAAsOfContractError) as exc:
            if asof_context.historical:
                detail = exc.detail if isinstance(exc, StageAAsOfContractError) else str(exc)
                raise StageAAsOfContractError(
                    "historical_config_snapshot_missing",
                    f"No valid immutable config snapshot exists for {normalized_db_date}: {detail}",
                    source="config",
                ) from exc
            raise
    elif asof_context is not None and asof_context.historical:
        raise StageAAsOfContractError(
            "historical_config_snapshot_missing",
            f"No immutable config snapshot exists for {normalized_db_date}",
            source="config",
        )

    account_source_path = state_snapshot_path or state_log_path
    account_revision = (
        sha256_file(account_source_path)
        if account_source_path is not None and Path(account_source_path).is_file()
        else sha256_payload(
            {
                "cutoff": state_cutoff_date,
                "symbols": sorted(paper_state.current_symbols),
                "shares": paper_state.shares,
                "cash": paper_state.absolute_cash,
            }
        )
    )
    account_lineage = {
        "source": str(account_source_path or "derived_paper_state"),
        "selected_max_date": state_cutoff_date,
        "observed_at": asof_context.observed_at if asof_context is not None else datetime.now().astimezone().isoformat(timespec="seconds"),
        "revision": account_revision,
        "validator_result": "PASS",
    }
    return generate_daily_plan(
        date_str=normalized_db_date,
        data_date=normalized_data_date,
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
        asof_context=asof_context,
        pinned_config_snapshot=pinned_config_snapshot,
        account_lineage=account_lineage if asof_context is not None else None,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate official paper daily plan")
    parser.add_argument("--date", help="Legacy target date (YYYYMMDD or YYYY-MM-DD)")
    parser.add_argument("--data-date", help="Completed market data date (YYYYMMDD or YYYY-MM-DD)")
    parser.add_argument("--trade-date", help="Paper trade/plan date (YYYYMMDD or YYYY-MM-DD)")
    args = parser.parse_args()

    report_path = run_paper_daily_plan(
        args.date,
        data_date=args.data_date,
        trade_date=args.trade_date,
    )
    if not report_path:
        print("Failed to generate official paper daily plan.")
        return 1

    print("Official paper daily plan is ready at:")
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

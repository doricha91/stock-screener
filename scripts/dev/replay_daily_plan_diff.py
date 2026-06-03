from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.daily_plan_generator import generate_daily_plan  # noqa: E402
from core.paper_account_paths import build_paper_account_paths  # noqa: E402
from core.paper_replay_diff import (  # noqa: E402
    CATEGORY_ACCOUNT_DATE_MISMATCH,
    CATEGORY_MISSING_INPUT,
    STATUS_FAIL,
    compare_daily_plan_files,
    compact_replay_diff_date,
    load_daily_plan_json,
    normalize_replay_diff_date,
    write_daily_plan_diff_report,
)
from core.paper_state_provider import load_official_paper_state_for_daily_plan  # noqa: E402


WRAPPER_SCHEMA_VERSION = "paper_daily_plan_replay_wrapper.v1"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dry-run Daily Plan replay wrapper that generates a replay-only sidecar and runs replay diff."
    )
    parser.add_argument("--account-id", required=True, help="Paper account id, e.g. paper_sandbox.")
    parser.add_argument("--date", required=True, help="Plan date in YYYY-MM-DD or YYYYMMDD format.")
    parser.add_argument("--baseline-plan", required=True, help="Path to baseline Daily Plan JSON sidecar.")
    parser.add_argument(
        "--output-dir",
        help="Replay diff output root. Defaults to the account replay_diff directory.",
    )
    parser.add_argument("--run-id", help="Optional replay run id. Defaults to UTC timestamp.")
    parser.add_argument("--json", action="store_true", help="Print a JSON wrapper summary.")
    return parser


def run_replay_daily_plan_diff(
    *,
    account_id: str,
    date: str,
    baseline_plan: str | Path,
    output_dir: str | Path | None = None,
    run_id: str | None = None,
) -> tuple[dict[str, Any], int]:
    plan_date = normalize_replay_diff_date(date)
    compact_date = compact_replay_diff_date(plan_date)
    baseline_path = Path(baseline_plan)
    output_root = Path(output_dir) if output_dir is not None else build_paper_account_paths(account_id, create=True).replay_diff_dir
    resolved_run_id = run_id or datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_dir = output_root / "runs" / resolved_run_id

    baseline = load_daily_plan_json(baseline_path)
    if baseline.error_category:
        return _failure_summary(
            account_id=account_id,
            plan_date=plan_date,
            run_id=resolved_run_id,
            run_dir=run_dir,
            baseline_path=baseline_path,
            category=baseline.error_category,
            message=baseline.error_message,
        ), 1

    mismatch = _baseline_mismatch(
        baseline.payload or {},
        account_id=account_id,
        plan_date=plan_date,
    )
    if mismatch:
        return _failure_summary(
            account_id=account_id,
            plan_date=plan_date,
            run_id=resolved_run_id,
            run_dir=run_dir,
            baseline_path=baseline_path,
            category=CATEGORY_ACCOUNT_DATE_MISMATCH,
            message=mismatch,
        ), 1

    run_dir.mkdir(parents=True, exist_ok=True)
    regenerated_markdown_path = run_dir / f"regenerated_daily_action_plan_{compact_date}.md"
    regenerated_config_path = run_dir / f"regenerated_paper_config_snapshot_{compact_date}.json"
    regenerated_state_path = build_paper_account_paths(account_id, create=False).current_state_snapshot_path(plan_date)

    paper_state = load_official_paper_state_for_daily_plan(plan_date)
    generate_daily_plan(
        date_str=plan_date,
        current_state=paper_state,
        output_path=regenerated_markdown_path,
        market_state_write_log=False,
        config_snapshot_path=regenerated_config_path,
        config_snapshot_archive_dir=run_dir / "archive" / "config_snapshots",
        config_snapshot_source="replay_daily_plan_diff",
        account_id=account_id,
        run_mode="replay",
        official_run=False,
        state_snapshot_path=regenerated_state_path,
    )

    regenerated_sidecar_path = regenerated_markdown_path.with_suffix(".json")
    report = compare_daily_plan_files(
        account_id=account_id,
        plan_date=plan_date,
        baseline_plan_path=baseline_path,
        regenerated_plan_path=regenerated_sidecar_path,
    )
    paths = write_daily_plan_diff_report(report, output_dir=run_dir)

    summary = _summary_from_report(
        report,
        run_id=resolved_run_id,
        run_dir=run_dir,
        baseline_path=baseline_path,
        regenerated_markdown_path=regenerated_markdown_path,
        regenerated_sidecar_path=regenerated_sidecar_path,
        diff_json_path=paths["json_path"],
        diff_markdown_path=paths["markdown_path"],
    )
    return summary, 0


def _baseline_mismatch(payload: dict[str, Any], *, account_id: str, plan_date: str) -> str | None:
    baseline_account = payload.get("account_id")
    baseline_date = payload.get("plan_date") or payload.get("date")
    if baseline_account != account_id:
        return f"Baseline account_id mismatch: expected {account_id}, got {baseline_account}."
    try:
        normalized_baseline_date = normalize_replay_diff_date(str(baseline_date))
    except ValueError:
        return f"Baseline plan_date is invalid: {baseline_date}."
    if normalized_baseline_date != plan_date:
        return f"Baseline plan_date mismatch: expected {plan_date}, got {normalized_baseline_date}."
    return None


def _failure_summary(
    *,
    account_id: str,
    plan_date: str,
    run_id: str,
    run_dir: Path,
    baseline_path: Path,
    category: str,
    message: str,
) -> dict[str, Any]:
    return {
        "schema_version": WRAPPER_SCHEMA_VERSION,
        "account_id": account_id,
        "plan_date": plan_date,
        "run_id": run_id,
        "run_dir": str(run_dir),
        "overall_status": STATUS_FAIL,
        "diff_categories": [category or CATEGORY_MISSING_INPUT],
        "message": message,
        "baseline_plan": str(baseline_path),
        "regenerated_markdown_path": None,
        "regenerated_sidecar_path": None,
        "diff_json_path": None,
        "diff_markdown_path": None,
        "write_executed": False,
        "actual_executed": False,
        "notion_api_called": False,
        "notion_sync_executed": False,
        "notion_write_export_sync_executed": False,
        "commit_append_executed": False,
    }


def _summary_from_report(
    report: dict[str, Any],
    *,
    run_id: str,
    run_dir: Path,
    baseline_path: Path,
    regenerated_markdown_path: Path,
    regenerated_sidecar_path: Path,
    diff_json_path: str,
    diff_markdown_path: str,
) -> dict[str, Any]:
    return {
        "schema_version": WRAPPER_SCHEMA_VERSION,
        "account_id": report["account_id"],
        "plan_date": report["plan_date"],
        "run_id": run_id,
        "run_dir": str(run_dir),
        "overall_status": report["overall_status"],
        "diff_categories": report["diff_categories"],
        "summary": report["summary"],
        "cause_candidates": report["cause_candidates"],
        "baseline_plan": str(baseline_path),
        "regenerated_markdown_path": str(regenerated_markdown_path),
        "regenerated_sidecar_path": str(regenerated_sidecar_path),
        "diff_json_path": diff_json_path,
        "diff_markdown_path": diff_markdown_path,
        "write_executed": False,
        "actual_executed": False,
        "notion_api_called": False,
        "notion_sync_executed": False,
        "notion_write_export_sync_executed": False,
        "commit_append_executed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        summary, exit_code = run_replay_daily_plan_diff(
            account_id=args.account_id,
            date=args.date,
            baseline_plan=args.baseline_plan,
            output_dir=args.output_dir,
            run_id=args.run_id,
        )
    except ValueError as exc:
        parser.error(str(exc))

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    elif exit_code:
        print(f"Daily Plan replay wrapper stopped: {summary.get('message')}")
    else:
        print(f"Daily Plan replay diff written: {summary['diff_json_path']}")
        print(f"Markdown report written: {summary['diff_markdown_path']}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

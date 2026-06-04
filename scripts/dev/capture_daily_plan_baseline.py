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

from core.daily_plan_generator import DAILY_PLAN_JSON_SCHEMA_VERSION, generate_daily_plan  # noqa: E402
from core.paper_account_paths import build_paper_account_paths  # noqa: E402
from core.paper_state_provider import load_official_paper_state_for_daily_plan  # noqa: E402


CAPTURE_SCHEMA_VERSION = "paper_daily_plan_baseline_capture.v1"
DEFAULT_RUN_MODE = "baseline_capture"
CONFIG_HASH_POLICY = "paper_config_hash.v1"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dev-only controlled Daily Plan baseline capture helper."
    )
    parser.add_argument("--account-id", required=True, help="Paper account id, e.g. paper_sandbox.")
    parser.add_argument("--date", required=True, help="Plan date in YYYY-MM-DD or YYYYMMDD format.")
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Required controlled output directory. No default official output path is used.",
    )
    parser.add_argument(
        "--run-mode",
        default=DEFAULT_RUN_MODE,
        help=f"Daily Plan run_mode metadata. Defaults to {DEFAULT_RUN_MODE}.",
    )
    parser.add_argument("--json", action="store_true", help="Print a JSON capture summary.")
    return parser


def run_capture_daily_plan_baseline(
    *,
    account_id: str,
    date: str,
    output_dir: str | Path,
    run_mode: str = DEFAULT_RUN_MODE,
) -> tuple[dict[str, Any], int]:
    plan_date = _normalize_plan_date(date)
    compact_date = plan_date.replace("-", "")
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    markdown_path = output_root / f"daily_action_plan_{compact_date}.md"
    sidecar_json_path = markdown_path.with_suffix(".json")
    config_snapshot_path = output_root / "config_snapshots" / f"paper_config_snapshot_{compact_date}.json"
    config_snapshot_archive_dir = output_root / "archive" / "config_snapshots"
    state_snapshot_path = build_paper_account_paths(account_id, create=False).current_state_snapshot_path(plan_date)

    paper_state = load_official_paper_state_for_daily_plan(plan_date)
    report_path = generate_daily_plan(
        date_str=plan_date,
        current_state=paper_state,
        output_path=markdown_path,
        market_state_write_log=False,
        config_snapshot_path=config_snapshot_path,
        config_snapshot_archive_dir=config_snapshot_archive_dir,
        config_snapshot_source="capture_daily_plan_baseline",
        account_id=account_id,
        run_mode=run_mode,
        official_run=False,
        json_sidecar_path=sidecar_json_path,
        write_json_sidecar=True,
        state_snapshot_path=state_snapshot_path,
    )

    eligibility = inspect_sidecar_eligibility(
        sidecar_json_path,
        expected_account_id=account_id,
        expected_plan_date=plan_date,
    )
    exit_code = 0 if eligibility["eligible"] else 1
    summary = {
        "schema_version": CAPTURE_SCHEMA_VERSION,
        "account_id": account_id,
        "plan_date": plan_date,
        "output_dir": str(output_root),
        "markdown_path": str(Path(report_path)) if report_path else str(markdown_path),
        "sidecar_json_path": str(sidecar_json_path),
        "config_snapshot_path": str(config_snapshot_path),
        "run_mode": run_mode,
        "official_run": False,
        "sidecar_eligibility": eligibility,
        **safety_markers(),
    }
    return summary, exit_code


def inspect_sidecar_eligibility(
    sidecar_path: str | Path,
    *,
    expected_account_id: str,
    expected_plan_date: str,
) -> dict[str, Any]:
    path = Path(sidecar_path)
    if not path.exists():
        return {
            "eligible": False,
            "status": "missing_sidecar",
            "warnings": [],
            "errors": [f"sidecar not found: {path}"],
        }

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "eligible": False,
            "status": "malformed_sidecar",
            "warnings": [],
            "errors": [f"sidecar JSON parse failed: {exc}"],
        }

    errors: list[str] = []
    warnings: list[str] = []
    fingerprints = payload.get("fingerprints")
    if payload.get("schema_version") != DAILY_PLAN_JSON_SCHEMA_VERSION:
        errors.append("schema_version is not paper_daily_plan.v1")
    if payload.get("account_id") != expected_account_id:
        errors.append("account_id mismatch")
    if _safe_normalize_date(payload.get("plan_date")) != expected_plan_date:
        errors.append("plan_date mismatch")
    if not isinstance(payload.get("items"), list):
        errors.append("items is not a list")
    if not isinstance(fingerprints, dict):
        errors.append("fingerprints is not an object")
        fingerprints = {}
    if not fingerprints.get("config_hash"):
        warnings.append("config_hash missing")
    if fingerprints.get("config_hash_policy") != CONFIG_HASH_POLICY:
        warnings.append("config_hash_policy missing or not paper_config_hash.v1")

    return {
        "eligible": not errors,
        "status": "eligible" if not errors else "invalid_sidecar",
        "schema_version": payload.get("schema_version"),
        "account_id": payload.get("account_id"),
        "plan_date": payload.get("plan_date"),
        "items_count": len(payload.get("items", [])) if isinstance(payload.get("items"), list) else None,
        "fingerprints_present": isinstance(fingerprints, dict),
        "config_hash_present": bool(fingerprints.get("config_hash")),
        "config_hash_policy": fingerprints.get("config_hash_policy"),
        "warnings": warnings,
        "errors": errors,
    }


def safety_markers() -> dict[str, bool]:
    return {
        "write_executed": False,
        "actual_executed": False,
        "notion_api_called": False,
        "notion_sync_executed": False,
        "notion_write_export_sync_executed": False,
        "commit_append_executed": False,
    }


def _normalize_plan_date(value: str) -> str:
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"Invalid date format: {value}")


def _safe_normalize_date(value: Any) -> str | None:
    try:
        return _normalize_plan_date(str(value))
    except (TypeError, ValueError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        summary, exit_code = run_capture_daily_plan_baseline(
            account_id=args.account_id,
            date=args.date,
            output_dir=args.output_dir,
            run_mode=args.run_mode,
        )
    except ValueError as exc:
        parser.error(str(exc))

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    elif exit_code:
        print(f"Daily Plan baseline capture failed eligibility: {summary['sidecar_eligibility']['status']}")
    else:
        print(f"Daily Plan baseline captured: {summary['sidecar_json_path']}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

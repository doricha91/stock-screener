from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.paper_alert_report import (  # noqa: E402
    build_paper_alert_report,
    compact_alert_report_date,
    normalize_alert_report_date,
    write_paper_alert_report,
)


def _load_json(path: str | None, *, source_name: str, report_missing: bool = False) -> tuple[dict, dict | None]:
    if not path:
        if not report_missing:
            return {}, None
        return {}, {
            "source": source_name,
            "status": "missing",
            "source_path": "",
            "message": f"{source_name} JSON source was not provided.",
        }
    source_path = Path(path)
    if not source_path.exists():
        return {}, {
            "source": source_name,
            "status": "missing",
            "source_path": str(source_path),
            "message": f"{source_name} JSON source file does not exist.",
        }
    try:
        with source_path.open("r", encoding="utf-8-sig") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as exc:
        return {}, {
            "source": source_name,
            "status": "malformed",
            "source_path": str(source_path),
            "message": f"{source_name} JSON source could not be parsed: {exc.msg}.",
        }
    if not isinstance(payload, dict):
        return {}, {
            "source": source_name,
            "status": "malformed",
            "source_path": str(source_path),
            "message": f"{source_name} JSON source must contain an object.",
        }
    return payload, None


def _resolve_source_path(
    *,
    explicit_path: str | None,
    source_root: str | None,
    source_name: str,
    report_date: str,
) -> str | None:
    if explicit_path:
        return explicit_path
    if not source_root:
        return None
    root = Path(source_root)
    date_key = compact_alert_report_date(report_date)
    if source_name == "daily_ops_status":
        candidates = (
            root / f"daily_ops_status_{date_key}.json",
            root / "daily_ops_status.json",
        )
    elif source_name == "daily_ops_actual_preflight":
        candidates = (
            root / f"daily_ops_actual_preflight_{date_key}.json",
            root / f"preflight_daily_ops_status_actual_{date_key}.json",
            root / "preflight.json",
        )
    elif source_name == "manual_execution":
        candidates = (
            root / f"manual_execution_{date_key}.json",
            root / f"manual_execution_status_{date_key}.json",
            root / f"manual_execution_import_commit_{date_key}.json",
            root / "manual_execution.json",
        )
    else:
        candidates = (
            root / f"manual_review_{date_key}.json",
            root / f"manual_review_status_{date_key}.json",
            root / f"manual_review_append_{date_key}.json",
            root / "manual_review.json",
        )
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return str(candidates[0])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a local Paper Ops Exception Alert Report from Daily Ops payloads."
    )
    parser.add_argument("--account-id", required=True, help="Paper account id, e.g. paper_sandbox.")
    parser.add_argument("--date", required=True, help="Report date in YYYY-MM-DD or YYYYMMDD format.")
    parser.add_argument(
        "--phase",
        default="closeout",
        choices=["closeout"],
        help="Alert evaluation phase. Only closeout is supported in PAPER18-2.",
    )
    parser.add_argument(
        "--actual-intent",
        action="store_true",
        help="Escalate actual-export preflight warnings because the operator intends actual export.",
    )
    parser.add_argument("--daily-ops-status-json", help="Path to a Daily Ops Status payload JSON file.")
    parser.add_argument("--preflight-json", help="Path to a PAPER17 Daily Ops actual preflight JSON file.")
    parser.add_argument("--manual-execution-json", help="Path to a Manual Execution high-level status JSON file.")
    parser.add_argument("--manual-review-json", help="Path to a Manual Review high-level status JSON file.")
    parser.add_argument(
        "--source-root",
        help="Optional directory for account/date source resolution when explicit JSON paths are omitted.",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory for JSON/Markdown output. Defaults to the account alerts directory.",
    )
    parser.add_argument("--json", action="store_true", help="Print a JSON summary.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    report_date = normalize_alert_report_date(args.date)
    daily_ops_path = _resolve_source_path(
        explicit_path=args.daily_ops_status_json,
        source_root=args.source_root,
        source_name="daily_ops_status",
        report_date=report_date,
    )
    preflight_path = _resolve_source_path(
        explicit_path=args.preflight_json,
        source_root=args.source_root,
        source_name="daily_ops_actual_preflight",
        report_date=report_date,
    )
    daily_ops_payload, daily_ops_event = _load_json(
        daily_ops_path,
        source_name="daily_ops_status",
        report_missing=bool(args.source_root or args.daily_ops_status_json),
    )
    preflight_payload, preflight_event = _load_json(
        preflight_path,
        source_name="daily_ops_actual_preflight",
        report_missing=bool(args.source_root or args.preflight_json),
    )
    manual_execution_path = _resolve_source_path(
        explicit_path=args.manual_execution_json,
        source_root=args.source_root,
        source_name="manual_execution",
        report_date=report_date,
    )
    manual_review_path = _resolve_source_path(
        explicit_path=args.manual_review_json,
        source_root=args.source_root,
        source_name="manual_review",
        report_date=report_date,
    )
    manual_execution_payload, manual_execution_event = _load_json(
        manual_execution_path,
        source_name="manual_execution",
        report_missing=bool(args.source_root or args.manual_execution_json),
    )
    manual_review_payload, manual_review_event = _load_json(
        manual_review_path,
        source_name="manual_review",
        report_missing=bool(args.source_root or args.manual_review_json),
    )
    source_events = [
        event
        for event in (daily_ops_event, preflight_event, manual_execution_event, manual_review_event)
        if event is not None
    ]
    report = build_paper_alert_report(
        account_id=args.account_id,
        report_date=report_date,
        phase=args.phase,
        actual_intent=args.actual_intent,
        daily_ops_status=daily_ops_payload,
        preflight=preflight_payload,
        manual_execution=manual_execution_payload,
        manual_review=manual_review_payload,
        source_events=source_events,
        daily_ops_source_path=daily_ops_path or "",
        preflight_source_path=preflight_path or "",
        manual_execution_source_path=manual_execution_path or "",
        manual_review_source_path=manual_review_path or "",
    )
    paths = write_paper_alert_report(report, output_dir=args.output_dir)
    summary = {
        "account_id": report["account_id"],
        "report_date": report["report_date"],
        "phase": report["phase"],
        "actual_intent": report["actual_intent"],
        "summary": report["summary"],
        "item_count": len(report["items"]),
        "json_path": paths["json_path"],
        "markdown_path": paths["markdown_path"],
        "delivery_executed": False,
        "notion_api_called": False,
        "notion_write_export_sync_executed": False,
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"Alert report written: {paths['json_path']}")
        print(f"Markdown report written: {paths['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

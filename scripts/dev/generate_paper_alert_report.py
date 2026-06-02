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
    write_paper_alert_report,
)


def _load_json(path: str | None) -> dict:
    if not path:
        return {}
    with Path(path).open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"JSON input must contain an object: {path}")
    return payload


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
    parser.add_argument(
        "--output-dir",
        help="Directory for JSON/Markdown output. Defaults to the account alerts directory.",
    )
    parser.add_argument("--json", action="store_true", help="Print a JSON summary.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    daily_ops_payload = _load_json(args.daily_ops_status_json)
    preflight_payload = _load_json(args.preflight_json)
    report = build_paper_alert_report(
        account_id=args.account_id,
        report_date=args.date,
        phase=args.phase,
        actual_intent=args.actual_intent,
        daily_ops_status=daily_ops_payload,
        preflight=preflight_payload,
        daily_ops_source_path=args.daily_ops_status_json or "",
        preflight_source_path=args.preflight_json or "",
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

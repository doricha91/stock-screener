from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.paper_daily_ops_orchestrator import OpsEvidencePaths, build_daily_ops_status  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only local paper daily ops stage status and next-command recommender."
    )
    subparsers = parser.add_subparsers(dest="command")
    status = subparsers.add_parser("status", help="Inspect local daily ops status without writes or Notion reads")
    status.add_argument("--account-id", required=True, help="Paper account id")
    status.add_argument("--data-date", required=True, help="Completed market data date, YYYYMMDD or YYYY-MM-DD")
    status.add_argument("--trade-date", required=True, help="Paper trade/operation date, YYYYMMDD or YYYY-MM-DD")
    status.add_argument("--account-root", help="Optional account root override for tests or diagnostics")
    status.add_argument("--legacy-root", help="Optional legacy paper_test root override for tests or diagnostics")
    status.add_argument("--execution-preview-json", help="Optional Manual Execution preview JSON evidence path")
    status.add_argument("--execution-commit-report", help="Optional Manual Execution commit report JSON evidence path")
    status.add_argument("--review-preview-json", help="Optional Manual Review preview JSON evidence path")
    status.add_argument("--review-commit-report", help="Optional Manual Review commit report JSON evidence path")
    status.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    status.set_defaults(handler=handle_status)
    return parser


def handle_status(args: argparse.Namespace) -> int:
    evidence = OpsEvidencePaths(
        execution_preview_json=Path(args.execution_preview_json) if args.execution_preview_json else None,
        execution_commit_report=Path(args.execution_commit_report) if args.execution_commit_report else None,
        review_preview_json=Path(args.review_preview_json) if args.review_preview_json else None,
        review_commit_report=Path(args.review_commit_report) if args.review_commit_report else None,
    )
    try:
        payload = build_daily_ops_status(
            account_id=args.account_id,
            data_date=args.data_date,
            trade_date=args.trade_date,
            account_root=Path(args.account_root) if args.account_root else None,
            legacy_root=Path(args.legacy_root) if args.legacy_root else None,
            evidence_paths=evidence,
        )
    except ValueError as exc:
        payload = {
            "overall_status": "BLOCKED",
            "read_only": True,
            "write_executed": False,
            "notion_api_called": False,
            "commit_append_executed": False,
            "error": str(exc),
            "stages": [],
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"PAPER DAILY OPS STATUS BLOCKED\n  error: {exc}")
        return 2

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("PAPER DAILY OPS STATUS")
        print(f"  account_id: {payload['account_id']}")
        print(f"  data_date: {payload['data_date']}")
        print(f"  trade_date: {payload['trade_date']}")
        print(f"  overall_status: {payload['overall_status']}")
        print(f"  workflow_status: {payload.get('workflow_status') or '-'}")
        print(f"  legacy_default_used: {str(payload['legacy_default_used']).lower()}")
        print(f"  next_command: {payload.get('next_command') or '-'}")
        for stage in payload["stages"]:
            print(f"  {stage['stage_name']}: {stage['status']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "handler"):
        parser.print_help()
        return 0
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())

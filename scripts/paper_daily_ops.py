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
    status.add_argument("--write-status-report", action="store_true", help="Persist the generated status JSON report")
    status.add_argument("--status-report-path", help="Optional status report output path")
    status.add_argument(
        "--strict-exit",
        action="store_true",
        help="Return WARNING/UNKNOWN as 1 and BLOCKED as 2 after successful status generation",
    )
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
            "schema_version": "mfu_oper9_daily_ops_status.v1",
            "overall_status": "BLOCKED",
            "read_only": True,
            "write_executed": False,
            "operation_write_executed": False,
            "notion_api_called": False,
            "commit_append_executed": False,
            "status_report_written": False,
            "status_report_path": None,
            "error": str(exc),
            "next_command": None,
            "next_action": None,
            "summary": {
                "terminal": False,
                "needs_attention": True,
                "has_blockers": True,
                "has_warnings": False,
                "has_unknowns": False,
                "recommended_operator_action": "RESOLVE_BLOCKERS",
            },
            "stage_counts": {
                "DONE": 0,
                "READY": 0,
                "BLOCKED": 0,
                "WARNING": 0,
                "UNKNOWN": 0,
                "NOT_STARTED": 0,
            },
            "stages": [],
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"PAPER DAILY OPS STATUS BLOCKED\n  error: {exc}")
        return 2
    except Exception as exc:
        payload = {
            "schema_version": "mfu_oper9_daily_ops_status.v1",
            "overall_status": "ERROR",
            "read_only": True,
            "write_executed": False,
            "operation_write_executed": False,
            "notion_api_called": False,
            "commit_append_executed": False,
            "status_report_written": False,
            "status_report_path": None,
            "error": str(exc),
            "stages": [],
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"PAPER DAILY OPS STATUS ERROR\n  error: {exc}")
        return 3

    if args.write_status_report:
        report_path = _status_report_path(payload, args.status_report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        payload["status_report_written"] = True
        payload["status_report_path"] = str(report_path).replace("/", "\\")
        report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

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
        print(f"  status_report_path: {payload.get('status_report_path') or '-'}")
        for stage in payload["stages"]:
            print(f"  {stage['stage_name']}: {stage['status']}")
    return _exit_code(payload, strict=bool(args.strict_exit))


def _status_report_path(payload: dict, explicit_path: str | None) -> Path:
    if explicit_path:
        return Path(explicit_path)
    account_root = Path(str(payload["account_root"]))
    trade_date = str(payload["trade_date"])
    return account_root / "reports" / f"daily_ops_status_{trade_date}.json"


def _exit_code(payload: dict, *, strict: bool) -> int:
    if not strict:
        return 0
    overall_status = str(payload.get("overall_status") or "")
    if overall_status == "BLOCKED":
        return 2
    if overall_status in {"WARNING", "UNKNOWN"}:
        return 1
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

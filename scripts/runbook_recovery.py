from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.runbook_calendar import load_market_calendar
from core.runbook_recovery import authorize_recovery, preview_recovery, recovery_status


def _identity_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--runbook-day-id", required=True)


def _authorization_arguments(parser: argparse.ArgumentParser) -> None:
    _identity_arguments(parser)
    parser.add_argument("--restart-data-date", required=True)
    parser.add_argument("--restart-trade-date", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--confirm-paper-test", action="store_true")
    parser.add_argument("--confirm-contaminated-incomplete", action="store_true")
    parser.add_argument("--confirm-no-real-trades", action="store_true")
    parser.add_argument("--confirm-gap-without-backfill", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Authorize an immutable paper/test runbook recovery.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    status_parser = subparsers.add_parser("status")
    _identity_arguments(status_parser)
    preview_parser = subparsers.add_parser("preview")
    _authorization_arguments(preview_parser)
    authorize_parser = subparsers.add_parser("authorize")
    _authorization_arguments(authorize_parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    calendar = load_market_calendar()
    common = {
        "workspace": Path(args.workspace),
        "account_id": args.account_id,
        "source_runbook_day_id": args.runbook_day_id,
        "calendar": calendar,
    }
    try:
        if args.command == "status":
            result = recovery_status(**common)
        else:
            values = {
                **common,
                "restart_data_date": args.restart_data_date,
                "restart_trade_date": args.restart_trade_date,
                "reason": args.reason,
                "confirm_paper_test": bool(args.confirm_paper_test),
                "confirm_contaminated_incomplete": bool(args.confirm_contaminated_incomplete),
                "confirm_no_real_trades": bool(args.confirm_no_real_trades),
                "confirm_gap_without_backfill": bool(args.confirm_gap_without_backfill),
            }
            result = preview_recovery(**values) if args.command == "preview" else authorize_recovery(**values)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        result = {
            "runner_result": "BLOCKED",
            "mode": f"RECOVERY_{args.command.upper()}",
            "reason": "recovery_operation_failed",
            "blockers": [f"{type(exc).__name__}:{exc}"],
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["runner_result"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())

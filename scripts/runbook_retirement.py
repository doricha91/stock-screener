from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.runbook_retirement import retire_runbook, retirement_status


def _context_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--data-date", required=True)
    parser.add_argument("--trade-date", required=True)
    parser.add_argument("--runbook-day-id", required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Retire a zero-progress paper/test runbook day.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    retire_parser = subparsers.add_parser("retire")
    _context_arguments(retire_parser)
    retire_parser.add_argument("--reason", required=True)
    retire_parser.add_argument("--confirm-paper-test", action="store_true")
    retire_parser.add_argument("--confirm-retire-zero-progress", action="store_true")
    status_parser = subparsers.add_parser("status")
    _context_arguments(status_parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    common = {
        "workspace": Path(args.workspace),
        "account_id": args.account_id,
        "data_date": args.data_date,
        "trade_date": args.trade_date,
        "runbook_day_id": args.runbook_day_id,
    }
    try:
        if args.command == "retire":
            result = retire_runbook(
                **common,
                reason=args.reason,
                confirm_paper_test=bool(args.confirm_paper_test),
                confirm_retire_zero_progress=bool(args.confirm_retire_zero_progress),
            )
        else:
            result = retirement_status(**common)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        result = {
            "runner_result": "BLOCKED",
            "reason": "retirement_operation_failed",
            "blockers": [f"{type(exc).__name__}:{exc}"],
            "retired": False,
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["runner_result"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())

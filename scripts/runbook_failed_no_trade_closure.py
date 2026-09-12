from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import failed_no_trade_closure
from scripts import runbook_state


def _context_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--data-date", required=True)
    parser.add_argument("--trade-date", required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Assess or record an immutable failed Stage B no-trade closure."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    status_parser = subparsers.add_parser("status")
    assess_parser = subparsers.add_parser("assess")
    close_parser = subparsers.add_parser("close")
    for item in (status_parser, assess_parser, close_parser):
        _context_arguments(item)
    for item in (assess_parser, close_parser):
        item.add_argument("--failed-idempotency-key", required=True)
        item.add_argument("--account-root", type=Path)
    close_parser.add_argument("--operator", required=True)
    close_parser.add_argument("--reason", required=True)
    close_parser.add_argument("--confirm-no-actual-trades", action="store_true")
    close_parser.add_argument("--confirm-no-reexecution", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        state_path = runbook_state.get_state_path_for_context(
            args.workspace,
            args.account_id,
            args.data_date,
            args.trade_date,
        )
        if args.command == "status":
            state = runbook_state.load_state(state_path)
            validation = failed_no_trade_closure.validate_closure_evidence(
                args.workspace, state_path, state
            )
            result = {
                "runner_result": (
                    "PASS" if not validation["exists"] or validation["valid"] else "BLOCKED"
                ),
                "closed": validation["valid"],
                "terminal_classification": (
                    failed_no_trade_closure.TERMINAL_CLASSIFICATION
                    if validation["valid"]
                    else None
                ),
                "evidence_path": str(validation["path"]),
                "evidence_exists": validation["exists"],
                "evidence_valid": validation["valid"],
                "blockers": validation["blockers"],
            }
        elif args.command == "assess":
            result = failed_no_trade_closure.assess_failed_no_trade_closure(
                workspace=args.workspace,
                account_id=args.account_id,
                data_date=args.data_date,
                trade_date=args.trade_date,
                failed_idempotency_key=args.failed_idempotency_key,
                account_root=args.account_root,
            )
        else:
            result = failed_no_trade_closure.close_failed_no_trade(
                workspace=args.workspace,
                account_id=args.account_id,
                data_date=args.data_date,
                trade_date=args.trade_date,
                failed_idempotency_key=args.failed_idempotency_key,
                operator=args.operator,
                reason=args.reason,
                confirm_no_actual_trades=args.confirm_no_actual_trades,
                confirm_no_reexecution=args.confirm_no_reexecution,
                account_root=args.account_root,
            )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        result = {
            "runner_result": "BLOCKED",
            "closed": False,
            "reason": f"{type(exc).__name__}:{exc}",
            "blockers": [str(exc)],
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["runner_result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

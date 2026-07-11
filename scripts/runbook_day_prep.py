from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.runbook_calendar import load_market_calendar
from core.runbook_day_prep import prepare_env_local


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare the next paper/test runbook local environment.")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--env-local", required=True)
    parser.add_argument("--write-env-local", action="store_true")
    parser.add_argument("--confirm-paper-test", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = prepare_env_local(
            args.workspace,
            args.account_id,
            args.env_local,
            load_market_calendar(),
            write_env_local=args.write_env_local,
            confirm_paper_test=args.confirm_paper_test,
        )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        result = {
            "runner_result": "BLOCKED",
            "mode": "WRITE_ENV_LOCAL",
            "reason": "prep_configuration_invalid",
            "blockers": [f"{type(exc).__name__}:{exc}"],
            "safe_to_prepare": False,
            "next_required_action": "Fix the prep configuration before retrying.",
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["runner_result"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKSPACE = Path(r"D:\n8n\workspace\stock_screener_ops")
ALLOWED_COMMAND_KEYS = {"status", "eod_dryrun", "context"}
EOD_REQUIRED_PASS_FIELDS = {
    "eod_mode": "accounting_close",
    "would_append_execution_log": "false",
    "would_write_current_state": "true",
    "would_write_account_snapshot": "true",
    "would_write_position_snapshot": "true",
}


@dataclass(frozen=True)
class OpsContext:
    account_id: str
    data_date: str
    trade_date: str


def _normalize_date(value: str, field_name: str) -> str:
    clean = str(value or "").strip().replace("-", "")
    if len(clean) != 8 or not clean.isdigit():
        raise ValueError(f"{field_name} must be YYYY-MM-DD or YYYYMMDD: {value}")
    return datetime.strptime(clean, "%Y%m%d").strftime("%Y-%m-%d")


def _workspace(args: argparse.Namespace) -> Path:
    return Path(args.workspace) if args.workspace else DEFAULT_WORKSPACE


def _context_path(workspace: Path) -> Path:
    return workspace / "context.json"


def _load_context(workspace: Path) -> OpsContext:
    path = _context_path(workspace)
    if not path.exists():
        raise FileNotFoundError(f"context file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    missing = [key for key in ("account_id", "data_date", "trade_date") if not payload.get(key)]
    if missing:
        raise ValueError(f"context file missing required fields: {', '.join(missing)}")
    return OpsContext(
        account_id=str(payload["account_id"]).strip(),
        data_date=_normalize_date(str(payload["data_date"]), "data_date"),
        trade_date=_normalize_date(str(payload["trade_date"]), "trade_date"),
    )


def _write_context(workspace: Path, args: argparse.Namespace) -> OpsContext:
    if not args.account_id or not args.data_date or not args.trade_date:
        raise ValueError("context requires --account-id, --data-date, and --trade-date")
    context = OpsContext(
        account_id=str(args.account_id).strip(),
        data_date=_normalize_date(args.data_date, "data_date"),
        trade_date=_normalize_date(args.trade_date, "trade_date"),
    )
    workspace.mkdir(parents=True, exist_ok=True)
    _context_path(workspace).write_text(
        json.dumps(
            {
                "account_id": context.account_id,
                "data_date": context.data_date,
                "trade_date": context.trade_date,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return context


def _run_python(argv: list[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *argv],
        cwd=str(ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        timeout=timeout_seconds,
    )


def _extract_json(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end < start:
            raise
        payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("command JSON output must be an object")
    return payload


def _parse_key_values(text: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line or line.startswith("|"):
            continue
        key, value = line.split(":", 1)
        clean_key = key.strip().lower().replace(" ", "_")
        if clean_key:
            parsed[clean_key] = value.strip()
    return parsed


def _status_text(payload: dict[str, Any], context: OpsContext, exit_code: int) -> str:
    summary = payload.get("operator_summary") if isinstance(payload.get("operator_summary"), dict) else {}
    lines = [
        "Paper Daily Ops Status",
        f"account_id: {context.account_id}",
        f"data_date: {context.data_date}",
        f"trade_date: {context.trade_date}",
        f"runner_result: {'PASS' if exit_code == 0 else 'FAIL'}",
        f"overall_status: {payload.get('overall_status') or '-'}",
        f"workflow_status: {payload.get('workflow_status') or '-'}",
        f"current_step: {summary.get('current_step') or '-'}",
        f"current_step_status: {summary.get('current_step_status') or '-'}",
        f"recommended_operator_action: {summary.get('recommended_operator_action') or '-'}",
        f"risk_level: {summary.get('risk_level') or '-'}",
        f"requires_manual_approval: {str(bool(summary.get('requires_manual_approval'))).lower()}",
        f"terminal: {str(bool(summary.get('terminal'))).lower()}",
        f"next_command: {summary.get('next_command') or '-'}",
    ]
    warnings = summary.get("warnings") or []
    blockers = summary.get("blockers") or []
    if warnings:
        lines.append("warnings:")
        lines.extend(f"- {warning}" for warning in warnings)
    if blockers:
        lines.append("blockers:")
        lines.extend(f"- {blocker}" for blocker in blockers)
    return "\n".join(lines) + "\n"


def _eod_text(parsed: dict[str, str], context: OpsContext, exit_code: int) -> str:
    failed = [
        f"{key} expected {expected}, got {parsed.get(key) or '-'}"
        for key, expected in EOD_REQUIRED_PASS_FIELDS.items()
        if str(parsed.get(key) or "").lower() != expected
    ]
    result = "PASS" if exit_code == 0 and not failed else "FAIL"
    lines = [
        "Paper EOD Dry-Run",
        f"account_id: {context.account_id}",
        f"trade_date: {context.trade_date}",
        f"runner_result: {result}",
        f"process_exit_code: {exit_code}",
        f"eod_mode: {parsed.get('eod_mode') or '-'}",
        f"execution_candidate_count: {parsed.get('execution_candidate_count') or '-'}",
        f"execution_log_rows_for_date: {parsed.get('execution_log_rows_for_date') or '-'}",
        f"ready_preview_count: {parsed.get('ready_preview_count') or '-'}",
        f"no_action_day: {parsed.get('no_action_day') or '-'}",
        f"would_append_execution_log: {parsed.get('would_append_execution_log') or '-'}",
        f"would_write_current_state: {parsed.get('would_write_current_state') or '-'}",
        f"would_write_account_snapshot: {parsed.get('would_write_account_snapshot') or '-'}",
        f"would_write_position_snapshot: {parsed.get('would_write_position_snapshot') or '-'}",
        f"source_snapshot_date: {parsed.get('source_snapshot_date') or '-'}",
        f"target_snapshot_date: {parsed.get('target_snapshot_date') or '-'}",
    ]
    if failed:
        lines.append("pass_condition_failures:")
        lines.extend(f"- {item}" for item in failed)
    return "\n".join(lines) + "\n"


def _error_text(command_key: str, error: str, context: OpsContext | None = None) -> str:
    lines = [
        f"Paper Ops Runner Error",
        f"command_key: {command_key}",
        "runner_result: FAIL",
    ]
    if context is not None:
        lines.extend(
            [
                f"account_id: {context.account_id}",
                f"data_date: {context.data_date}",
                f"trade_date: {context.trade_date}",
            ]
        )
    lines.append(f"error: {error}")
    return "\n".join(lines) + "\n"


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def handle_context(args: argparse.Namespace) -> int:
    workspace = _workspace(args)
    try:
        context = _write_context(workspace, args)
        text = (
            "Paper Ops Context\n"
            "runner_result: PASS\n"
            f"account_id: {context.account_id}\n"
            f"data_date: {context.data_date}\n"
            f"trade_date: {context.trade_date}\n"
            f"context_path: {_context_path(workspace)}\n"
        )
        _write_text(workspace / "context_latest.txt", text)
        print(text, end="")
        return 0
    except Exception as exc:
        text = _error_text("context", str(exc))
        _write_text(workspace / "context_latest.txt", text)
        print(text, end="")
        return 1


def handle_status(args: argparse.Namespace) -> int:
    workspace = _workspace(args)
    context: OpsContext | None = None
    try:
        context = _load_context(workspace)
        completed = _run_python(
            [
                "scripts\\paper_daily_ops.py",
                "status",
                "--account-id",
                context.account_id,
                "--data-date",
                context.data_date,
                "--trade-date",
                context.trade_date,
                "--json",
                "--include-notion-read",
            ],
            timeout_seconds=args.timeout_seconds,
        )
        payload = _extract_json(completed.stdout)
        payload["runner"] = {
            "command_key": "status",
            "process_exit_code": completed.returncode,
            "stderr": completed.stderr.strip(),
        }
        _write_json(workspace / "status_latest.json", payload)
        text = _status_text(payload, context, completed.returncode)
        if completed.returncode != 0:
            text += f"stderr: {completed.stderr.strip() or '-'}\n"
        _write_text(workspace / "status_latest.txt", text)
        print(text, end="")
        return completed.returncode
    except Exception as exc:
        text = _error_text("status", str(exc), context)
        _write_text(workspace / "status_latest.txt", text)
        _write_json(workspace / "status_latest.json", {"runner_result": "FAIL", "error": str(exc)})
        print(text, end="")
        return 1


def handle_eod_dryrun(args: argparse.Namespace) -> int:
    workspace = _workspace(args)
    context: OpsContext | None = None
    try:
        context = _load_context(workspace)
        completed = _run_python(
            [
                "scripts\\paper.py",
                "eod",
                "--date",
                context.trade_date,
                "--account-id",
                context.account_id,
                "--dry-run",
            ],
            timeout_seconds=args.timeout_seconds,
        )
        raw_text = completed.stdout
        if completed.stderr.strip():
            raw_text += "\nSTDERR:\n" + completed.stderr
        _write_text(workspace / "eod_dryrun_latest.raw.txt", raw_text)
        parsed = _parse_key_values(completed.stdout)
        text = _eod_text(parsed, context, completed.returncode)
        if completed.returncode != 0:
            text += f"stderr: {completed.stderr.strip() or '-'}\n"
        _write_text(workspace / "eod_dryrun_latest.txt", text)
        print(text, end="")
        return 0 if "runner_result: PASS" in text else 1
    except Exception as exc:
        text = _error_text("eod_dryrun", str(exc), context)
        _write_text(workspace / "eod_dryrun_latest.txt", text)
        _write_text(workspace / "eod_dryrun_latest.raw.txt", text)
        print(text, end="")
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="File-based n8n/Telegram runner for safe paper ops commands.")
    parser.add_argument("command_key", choices=sorted(ALLOWED_COMMAND_KEYS))
    parser.add_argument("--workspace", help=f"Output workspace. Defaults to {DEFAULT_WORKSPACE}")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--account-id", help="Context account_id. Only used by command_key=context.")
    parser.add_argument("--data-date", help="Context data_date. Only used by command_key=context.")
    parser.add_argument("--trade-date", help="Context trade_date. Only used by command_key=context.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    handlers = {
        "context": handle_context,
        "status": handle_status,
        "eod_dryrun": handle_eod_dryrun,
    }
    return handlers[args.command_key](args)


if __name__ == "__main__":
    raise SystemExit(main())

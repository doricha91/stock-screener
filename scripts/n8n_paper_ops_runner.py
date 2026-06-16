from __future__ import annotations

import argparse
import contextlib
import io
import json
import sqlite3
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.paths import market_db_path  # noqa: E402

DEFAULT_WORKSPACE = Path(r"D:\n8n\workspace\stock_screener_ops")
ALLOWED_COMMAND_KEYS = {"status", "eod_dryrun", "context", "daily_refresh"}
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


@dataclass(frozen=True)
class DailyRefreshDateResolution:
    account_id: str
    data_date: str | None
    trade_date: str | None
    source_data_max_date: str | None
    daily_price_max_date: str | None
    market_index_max_date: str | None
    daily_indicators_max_date: str | None
    runner_result: str
    stale: bool
    stale_days: int | None
    date_policy: str
    reason: str
    recommended_operator_action: str


def _normalize_date(value: str, field_name: str) -> str:
    clean = str(value or "").strip().replace("-", "")
    if len(clean) != 8 or not clean.isdigit():
        raise ValueError(f"{field_name} must be YYYY-MM-DD or YYYYMMDD: {value}")
    return datetime.strptime(clean, "%Y%m%d").strftime("%Y-%m-%d")


def _normalize_as_of_date(value: date | datetime | str | None) -> date:
    if value is None:
        return date.today()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(_normalize_date(str(value), "as_of_date"), "%Y-%m-%d").date()


def _fail_date_resolution(account_id: str, reason: str, action: str) -> DailyRefreshDateResolution:
    return DailyRefreshDateResolution(
        account_id=account_id,
        data_date=None,
        trade_date=None,
        source_data_max_date=None,
        daily_price_max_date=None,
        market_index_max_date=None,
        daily_indicators_max_date=None,
        runner_result="FAIL",
        stale=False,
        stale_days=None,
        date_policy="latest_complete_market_data_to_next_weekday",
        reason=reason,
        recommended_operator_action=action,
    )


def _sqlite_readonly_uri(db_path: Path) -> str:
    return f"file:{db_path.resolve().as_posix()}?mode=ro"


def _sqlite_table_has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
        return False
    return any(row[1] == column for row in conn.execute(f"PRAGMA table_info({table})"))


def _query_max_date(conn: sqlite3.Connection, table: str, column: str = "date", where: str = "", params: tuple[Any, ...] = ()) -> str | None:
    query = f"SELECT MAX({column}) FROM {table}"
    if where:
        query += f" WHERE {where}"
    value = conn.execute(query, params).fetchone()[0]
    return _normalize_date(str(value), f"{table}.{column}") if value else None


def _next_weekday_after(value: str) -> str:
    cursor = datetime.strptime(value, "%Y-%m-%d").date() + timedelta(days=1)
    while cursor.weekday() >= 5:
        cursor += timedelta(days=1)
    return cursor.strftime("%Y-%m-%d")


def resolve_daily_refresh_dates(
    *,
    account_id: str | None,
    db_path: str | Path,
    as_of_date: date | datetime | str | None = None,
    stale_threshold_days: int = 3,
    market_index_symbol: str = "SPY",
) -> DailyRefreshDateResolution:
    """Resolve read-only daily refresh dates from market DB freshness."""
    clean_account_id = str(account_id or "").strip()
    if not clean_account_id:
        return _fail_date_resolution(
            "",
            "account_id is required",
            "Provide account_id before running daily refresh date resolution",
        )

    try:
        resolved_as_of = _normalize_as_of_date(as_of_date)
    except Exception as exc:
        return _fail_date_resolution(clean_account_id, str(exc), "Provide as_of_date as YYYY-MM-DD or YYYYMMDD")

    db_file = Path(db_path)
    if not db_file.exists():
        return _fail_date_resolution(
            clean_account_id,
            f"market DB not found: {db_file}",
            "Refresh or restore market DB before running daily refresh",
        )

    required_columns = [
        ("daily_price", "date"),
        ("market_index", "date"),
        ("market_index", "symbol"),
        ("daily_indicators", "date"),
    ]

    try:
        with sqlite3.connect(_sqlite_readonly_uri(db_file), uri=True) as conn:
            for table, column in required_columns:
                if not _sqlite_table_has_column(conn, table, column):
                    return _fail_date_resolution(
                        clean_account_id,
                        f"required table/column missing: {table}.{column}",
                        "Initialize or repair market DB schema before running daily refresh",
                    )

            daily_price_max = _query_max_date(conn, "daily_price")
            market_index_max = _query_max_date(
                conn,
                "market_index",
                where="symbol = ?",
                params=(market_index_symbol,),
            )
            daily_indicators_max = _query_max_date(conn, "daily_indicators")
    except Exception as exc:
        return _fail_date_resolution(
            clean_account_id,
            f"failed to read market DB: {exc}",
            "Inspect market DB accessibility and schema",
        )

    if not daily_price_max:
        return _fail_date_resolution(clean_account_id, "daily_price has no date rows", "Refresh daily_price data")
    if not market_index_max:
        return _fail_date_resolution(
            clean_account_id,
            f"market_index has no date rows for {market_index_symbol}",
            "Refresh market_index data for SPY before running daily refresh",
        )
    if not daily_indicators_max:
        return _fail_date_resolution(
            clean_account_id,
            "daily_indicators has no date rows",
            "Refresh daily_indicators before running daily refresh",
        )

    source_data_max = min(daily_price_max, market_index_max, daily_indicators_max)
    data_dt = datetime.strptime(source_data_max, "%Y-%m-%d").date()
    stale_days = max(0, (resolved_as_of - data_dt).days)
    stale = stale_days > stale_threshold_days
    trade_date = _next_weekday_after(source_data_max)

    warnings: list[str] = []
    if len({daily_price_max, market_index_max, daily_indicators_max}) > 1:
        warnings.append("required market data sources are not aligned; using conservative min(max_date)")
    if stale:
        warnings.append(f"complete data_date is stale by {stale_days} calendar days")
    if data_dt.weekday() >= 5:
        warnings.append("complete data_date falls on a weekend; verify DB date quality")

    runner_result = "WARNING" if warnings else "PASS"
    reason = "; ".join(warnings) if warnings else "latest complete market data date found in DB"
    action = (
        "Verify market data freshness and trade_date manually before enabling daily_refresh automation"
        if warnings
        else "none"
    )

    return DailyRefreshDateResolution(
        account_id=clean_account_id,
        data_date=source_data_max,
        trade_date=trade_date,
        source_data_max_date=source_data_max,
        daily_price_max_date=daily_price_max,
        market_index_max_date=market_index_max,
        daily_indicators_max_date=daily_indicators_max,
        runner_result=runner_result,
        stale=stale,
        stale_days=stale_days,
        date_policy="latest_complete_market_data_to_next_weekday",
        reason=reason,
        recommended_operator_action=action,
    )


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


def _context_text(context: OpsContext, workspace: Path) -> str:
    return (
        "Paper Ops Context\n"
        "runner_result: PASS\n"
        f"account_id: {context.account_id}\n"
        f"data_date: {context.data_date}\n"
        f"trade_date: {context.trade_date}\n"
        f"context_path: {_context_path(workspace)}\n"
    )


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


def _stage_result(result: str, exit_code: int | None = None, error: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"result": result}
    if exit_code is not None:
        payload["exit_code"] = exit_code
    if error:
        payload["error"] = error
    return payload


def _capture_handler(handler, args: argparse.Namespace) -> int:
    with contextlib.redirect_stdout(io.StringIO()):
        return int(handler(args))


def _resolution_to_dict(resolution: DailyRefreshDateResolution) -> dict[str, Any]:
    return asdict(resolution)


def _daily_refresh_text(payload: dict[str, Any]) -> str:
    lines = [
        "Daily Runner Refresh",
        f"runner_result: {payload.get('runner_result') or '-'}",
        f"generated_at: {payload.get('generated_at') or '-'}",
    ]
    failed_stage = payload.get("failed_stage")
    if failed_stage:
        lines.append(f"stage: {failed_stage}")
    lines.extend(
        [
            f"account_id: {payload.get('account_id') or '-'}",
            f"data_date: {payload.get('data_date') or '-'}",
            f"trade_date: {payload.get('trade_date') or '-'}",
            f"source_data_max_date: {payload.get('source_data_max_date') or '-'}",
            f"date_policy: {payload.get('date_policy') or '-'}",
            f"date_reason: {payload.get('date_reason') or '-'}",
            f"stale: {str(bool(payload.get('stale'))).lower()}",
            f"stale_days: {payload.get('stale_days') if payload.get('stale_days') is not None else '-'}",
            f"context_result: {payload.get('stages', {}).get('context', {}).get('result') or '-'}",
            f"status_result: {payload.get('stages', {}).get('status', {}).get('result') or '-'}",
            f"eod_dryrun_result: {payload.get('stages', {}).get('eod_dryrun', {}).get('result') or '-'}",
            f"recommended_operator_action: {payload.get('recommended_operator_action') or '-'}",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_daily_refresh_outputs(workspace: Path, payload: dict[str, Any]) -> None:
    _write_json(workspace / "daily_refresh_latest.json", payload)
    _write_text(workspace / "daily_refresh_latest.txt", _daily_refresh_text(payload))


def _load_account_id_for_refresh(workspace: Path, explicit_account_id: str | None) -> str:
    if explicit_account_id and str(explicit_account_id).strip():
        return str(explicit_account_id).strip()
    context = _load_context(workspace)
    return context.account_id


def handle_context(args: argparse.Namespace) -> int:
    workspace = _workspace(args)
    try:
        context = _write_context(workspace, args)
        text = _context_text(context, workspace)
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


def handle_daily_refresh(args: argparse.Namespace) -> int:
    workspace = _workspace(args)
    generated_at = datetime.now().isoformat(timespec="seconds")
    stages: dict[str, dict[str, Any]] = {}

    try:
        account_id = _load_account_id_for_refresh(workspace, args.account_id)
    except Exception as exc:
        account_id = str(args.account_id or "").strip()
        resolution = _fail_date_resolution(
            account_id,
            str(exc),
            "Provide --account-id or create a valid context.json before running daily_refresh",
        )
    else:
        resolution = resolve_daily_refresh_dates(
            account_id=account_id,
            db_path=Path(args.db_path) if args.db_path else Path(market_db_path()),
            as_of_date=args.as_of_date,
            stale_threshold_days=args.stale_threshold_days,
        )

    stages["resolve_dates"] = _stage_result(resolution.runner_result)
    if resolution.runner_result == "FAIL":
        payload = {
            "runner_result": "FAIL",
            "generated_at": generated_at,
            "failed_stage": "resolve_dates",
            "account_id": resolution.account_id or account_id or None,
            "data_date": resolution.data_date,
            "trade_date": resolution.trade_date,
            "source_data_max_date": resolution.source_data_max_date,
            "date_policy": resolution.date_policy,
            "date_reason": resolution.reason,
            "stale": resolution.stale,
            "stale_days": resolution.stale_days,
            "date_resolution": _resolution_to_dict(resolution),
            "stages": stages,
            "recommended_operator_action": resolution.recommended_operator_action,
        }
        _write_daily_refresh_outputs(workspace, payload)
        print(_daily_refresh_text(payload), end="")
        return 1

    context_args = argparse.Namespace(
        workspace=str(workspace),
        timeout_seconds=args.timeout_seconds,
        account_id=resolution.account_id,
        data_date=resolution.data_date,
        trade_date=resolution.trade_date,
    )
    context_exit = _capture_handler(handle_context, context_args)
    stages["context"] = _stage_result("PASS" if context_exit == 0 else "FAIL", context_exit)
    if context_exit != 0:
        payload = _daily_refresh_payload(generated_at, resolution, stages, "context")
        _write_daily_refresh_outputs(workspace, payload)
        print(_daily_refresh_text(payload), end="")
        return 1

    stage_args = argparse.Namespace(workspace=str(workspace), timeout_seconds=args.timeout_seconds)
    status_exit = _capture_handler(handle_status, stage_args)
    stages["status"] = _stage_result("PASS" if status_exit == 0 else "FAIL", status_exit)
    if status_exit != 0:
        payload = _daily_refresh_payload(generated_at, resolution, stages, "status")
        _write_daily_refresh_outputs(workspace, payload)
        print(_daily_refresh_text(payload), end="")
        return 1

    eod_exit = _capture_handler(handle_eod_dryrun, stage_args)
    stages["eod_dryrun"] = _stage_result("PASS" if eod_exit == 0 else "FAIL", eod_exit)
    failed_stage = "eod_dryrun" if eod_exit != 0 else None
    payload = _daily_refresh_payload(generated_at, resolution, stages, failed_stage)
    _write_daily_refresh_outputs(workspace, payload)
    print(_daily_refresh_text(payload), end="")
    return 1 if eod_exit != 0 else 0


def _daily_refresh_payload(
    generated_at: str,
    resolution: DailyRefreshDateResolution,
    stages: dict[str, dict[str, Any]],
    failed_stage: str | None,
) -> dict[str, Any]:
    if failed_stage:
        runner_result = "FAIL"
        action = f"Fix {failed_stage} failure before relying on daily refresh output"
    else:
        runner_result = "WARNING" if resolution.runner_result == "WARNING" else "PASS"
        action = resolution.recommended_operator_action if runner_result == "WARNING" else "NONE"
    payload: dict[str, Any] = {
        "runner_result": runner_result,
        "generated_at": generated_at,
        "account_id": resolution.account_id,
        "data_date": resolution.data_date,
        "trade_date": resolution.trade_date,
        "source_data_max_date": resolution.source_data_max_date,
        "daily_price_max_date": resolution.daily_price_max_date,
        "market_index_max_date": resolution.market_index_max_date,
        "daily_indicators_max_date": resolution.daily_indicators_max_date,
        "date_policy": resolution.date_policy,
        "date_reason": resolution.reason,
        "stale": resolution.stale,
        "stale_days": resolution.stale_days,
        "date_resolution": _resolution_to_dict(resolution),
        "stages": stages,
        "recommended_operator_action": action,
    }
    if failed_stage:
        payload["failed_stage"] = failed_stage
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="File-based n8n/Telegram runner for safe paper ops commands.")
    parser.add_argument("command_key", choices=sorted(ALLOWED_COMMAND_KEYS))
    parser.add_argument("--workspace", help=f"Output workspace. Defaults to {DEFAULT_WORKSPACE}")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--account-id", help="Context account_id. Used by command_key=context and daily_refresh.")
    parser.add_argument("--data-date", help="Context data_date. Only used by command_key=context.")
    parser.add_argument("--trade-date", help="Context trade_date. Only used by command_key=context.")
    parser.add_argument("--db-path", help="Market data DB path. Only used by command_key=daily_refresh.")
    parser.add_argument("--as-of-date", help="As-of date for stale checks. Only used by command_key=daily_refresh.")
    parser.add_argument(
        "--stale-threshold-days",
        type=int,
        default=3,
        help="Calendar-day stale threshold. Only used by command_key=daily_refresh.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    handlers = {
        "context": handle_context,
        "status": handle_status,
        "eod_dryrun": handle_eod_dryrun,
        "daily_refresh": handle_daily_refresh,
    }
    return handlers[args.command_key](args)


if __name__ == "__main__":
    raise SystemExit(main())

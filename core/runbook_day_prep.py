from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any, Callable

from core.runbook_calendar import MarketCalendar
from core.runbook_day_rollover import preview_rollover
from scripts import runbook_state


ACCOUNT_KEYS = ("ACCOUNT_ID", "ACCOUNT_MODE")
RUNBOOK_DAY_KEYS = ("DATA_DATE", "TRADE_DATE", "RUNBOOK_DAY_ID")
SET_LINE_PATTERN = re.compile(r'^set "([A-Z0-9_]+)=([^"]+)"$')
NEXT_ACTION = "Review all three local environment files, then proceed to 6-4D."
BLOCKED_ACTION = "Resolve the blockers before preparing the runbook day environment."


def _blocked(reason: str, blockers: list[str] | None = None) -> dict[str, Any]:
    return {
        "runner_result": "BLOCKED",
        "mode": "WRITE_RUNBOOK_DAY_LOCAL",
        "reason": reason,
        "blockers": blockers or [reason],
        "safe_to_prepare": False,
        "next_required_action": BLOCKED_ACTION,
    }


def _read_local_assignments(path: str | Path, expected_keys: tuple[str, ...]) -> dict[str, str]:
    lines = Path(path).read_text(encoding="ascii").splitlines()
    if len(lines) != len(expected_keys) + 2:
        raise ValueError("invalid_local_structure")
    if lines[0].lower() != "@echo off" or lines[-1].lower() != "exit /b 0":
        raise ValueError("invalid_local_structure")
    values: dict[str, str] = {}
    for line in lines[1:-1]:
        match = SET_LINE_PATTERN.fullmatch(line)
        if not match:
            raise ValueError("invalid_local_assignment")
        key, value = match.groups()
        if key in values:
            raise ValueError(f"duplicate_local_key:{key}")
        values[key] = value
    if tuple(values) != expected_keys:
        raise ValueError("local_keys_or_order_invalid")
    return values


def read_account_local(path: str | Path) -> dict[str, str]:
    values = _read_local_assignments(path, ACCOUNT_KEYS)
    if values["ACCOUNT_MODE"].upper() != "PAPER":
        raise ValueError("account_mode_must_be_paper")
    return values


def render_runbook_day_local(values: dict[str, str]) -> bytes:
    lines = [
        "@echo off",
        *(f'set "{key}={values[key]}"' for key in RUNBOOK_DAY_KEYS),
        "exit /b 0",
        "",
    ]
    return "\r\n".join(lines).encode("ascii")


def read_runbook_day_local(
    path: str | Path,
    *,
    account_id: str,
) -> dict[str, str]:
    values = _read_local_assignments(path, RUNBOOK_DAY_KEYS)
    expected_id = runbook_state.get_runbook_day_id(
        account_id,
        values["DATA_DATE"],
        values["TRADE_DATE"],
    )
    if values["RUNBOOK_DAY_ID"] != expected_id:
        raise ValueError("runbook_day_id_mismatch")
    return values


def _values_from_rollover(result: dict[str, Any], account_id: str) -> dict[str, str]:
    if str(result.get("account_id") or "") != account_id:
        raise ValueError("rollover_account_mismatch")
    values = {
        "DATA_DATE": str(result.get("next_data_date") or ""),
        "TRADE_DATE": str(result.get("next_trade_date") or ""),
        "RUNBOOK_DAY_ID": str(result.get("next_runbook_day_id") or ""),
    }
    expected_id = runbook_state.get_runbook_day_id(
        account_id,
        values["DATA_DATE"],
        values["TRADE_DATE"],
    )
    if values["RUNBOOK_DAY_ID"] != expected_id:
        raise ValueError("rollover_runbook_day_id_mismatch")
    return values


def prepare_runbook_day_local(
    workspace: str | Path,
    account_id: str,
    account_local_path: str | Path,
    runbook_day_local_path: str | Path,
    calendar: MarketCalendar,
    *,
    write_env_local: bool,
    confirm_paper_test: bool,
    validate_temp: Callable[..., dict[str, str]] = read_runbook_day_local,
) -> dict[str, Any]:
    if not write_env_local:
        return _blocked("write_env_local_confirmation_required")

    account_id = str(account_id or "").strip()
    account_path = Path(account_local_path)
    day_path = Path(runbook_day_local_path)
    legacy_path = day_path.parent / "_env.local.cmd"
    if legacy_path.exists():
        return _blocked(
            "legacy_env_local_detected",
            ["Manual migration required; automatic migration is not supported."],
        )
    try:
        account_values = read_account_local(account_path)
    except (OSError, UnicodeError, ValueError) as exc:
        return _blocked("account_local_invalid", [f"{type(exc).__name__}:{exc}"])
    if account_values["ACCOUNT_ID"] != account_id:
        return _blocked("account_local_mismatch")

    rollover = preview_rollover(
        workspace,
        account_id,
        calendar,
        confirm_paper_test=confirm_paper_test,
    )
    if rollover.get("runner_result") != "PASS":
        return _blocked(
            str(rollover.get("reason") or "rollover_blocked"),
            list(rollover.get("blockers") or ["rollover_blocked"]),
        )
    if rollover.get("already_exists") is not False or rollover.get("safe_to_prepare") is not True:
        return _blocked("rollover_not_safe_to_prepare", ["next_runbook_day_already_exists"])
    try:
        values = _values_from_rollover(rollover, account_id)
    except ValueError as exc:
        return _blocked("rollover_result_invalid", [str(exc)])

    if not day_path.parent.is_dir():
        return _blocked("runbook_day_parent_directory_not_found", [str(day_path.parent)])
    if day_path.exists():
        try:
            if read_runbook_day_local(day_path, account_id=account_id) == values:
                return _pass_result(account_id, values, day_path, False, False)
        except (OSError, UnicodeError, ValueError):
            pass

    temp_path = day_path.with_name(f"{day_path.name}.tmp")
    backup_path = day_path.with_name(f"{day_path.name}.bak")
    backup_created = False
    try:
        temp_path.write_bytes(render_runbook_day_local(values))
        if validate_temp(temp_path, account_id=account_id) != values:
            raise ValueError("temp_runbook_day_values_mismatch")
        if day_path.exists():
            shutil.copy2(day_path, backup_path)
            backup_created = True
        os.replace(temp_path, day_path)
    except (OSError, UnicodeError, ValueError) as exc:
        return _blocked("runbook_day_write_failed", [f"{type(exc).__name__}:{exc}"])
    finally:
        if temp_path.exists():
            temp_path.unlink()

    return _pass_result(account_id, values, day_path, backup_created, True)


def _pass_result(
    account_id: str,
    values: dict[str, str],
    day_path: Path,
    backup_created: bool,
    file_changed: bool,
) -> dict[str, Any]:
    return {
        "runner_result": "PASS",
        "mode": "WRITE_RUNBOOK_DAY_LOCAL",
        "account_id": account_id,
        "data_date": values["DATA_DATE"],
        "trade_date": values["TRADE_DATE"],
        "runbook_day_id": values["RUNBOOK_DAY_ID"],
        "runbook_day_local_path": str(day_path).replace("\\", "/"),
        "backup_created": backup_created,
        "file_changed": file_changed,
        "safe_to_prepare": True,
        "next_required_action": NEXT_ACTION,
    }

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any, Callable

from core.runbook_calendar import MarketCalendar
from core.runbook_day_rollover import preview_rollover
from scripts import runbook_state


ENV_KEYS = ("ACCOUNT_ID", "DATA_DATE", "TRADE_DATE", "RUNBOOK_DAY_ID")
SET_LINE_PATTERN = re.compile(r'^set "(ACCOUNT_ID|DATA_DATE|TRADE_DATE|RUNBOOK_DAY_ID)=([^"]+)"$')
NEXT_ACTION = "Review _env.local.cmd, then proceed to 6-4D."
BLOCKED_ACTION = "Resolve the blockers before preparing the local runbook environment."


def _blocked(reason: str, blockers: list[str] | None = None) -> dict[str, Any]:
    return {
        "runner_result": "BLOCKED",
        "mode": "WRITE_ENV_LOCAL",
        "reason": reason,
        "blockers": blockers or [reason],
        "safe_to_prepare": False,
        "next_required_action": BLOCKED_ACTION,
    }


def render_env_local(values: dict[str, str]) -> bytes:
    lines = [
        "@echo off",
        *(f'set "{key}={values[key]}"' for key in ENV_KEYS),
        "exit /b 0",
        "",
    ]
    return "\r\n".join(lines).encode("ascii")


def read_env_local(path: str | Path) -> dict[str, str]:
    lines = Path(path).read_text(encoding="ascii").splitlines()
    if len(lines) != 6 or lines[0].lower() != "@echo off" or lines[-1].lower() != "exit /b 0":
        raise ValueError("invalid_env_local_structure")
    values: dict[str, str] = {}
    for line in lines[1:-1]:
        match = SET_LINE_PATTERN.fullmatch(line)
        if not match:
            raise ValueError("invalid_env_local_assignment")
        key, value = match.groups()
        if key in values:
            raise ValueError(f"duplicate_env_local_key:{key}")
        values[key] = value
    if tuple(values) != ENV_KEYS:
        raise ValueError("env_local_keys_or_order_invalid")
    expected_id = runbook_state.get_runbook_day_id(
        values["ACCOUNT_ID"],
        values["DATA_DATE"],
        values["TRADE_DATE"],
    )
    if values["RUNBOOK_DAY_ID"] != expected_id:
        raise ValueError("env_local_runbook_day_id_mismatch")
    return values


def _values_from_rollover(result: dict[str, Any], account_id: str) -> dict[str, str]:
    values = {
        "ACCOUNT_ID": str(result.get("account_id") or ""),
        "DATA_DATE": str(result.get("next_data_date") or ""),
        "TRADE_DATE": str(result.get("next_trade_date") or ""),
        "RUNBOOK_DAY_ID": str(result.get("next_runbook_day_id") or ""),
    }
    if values["ACCOUNT_ID"] != account_id:
        raise ValueError("rollover_account_mismatch")
    expected_id = runbook_state.get_runbook_day_id(
        values["ACCOUNT_ID"],
        values["DATA_DATE"],
        values["TRADE_DATE"],
    )
    if values["RUNBOOK_DAY_ID"] != expected_id:
        raise ValueError("rollover_runbook_day_id_mismatch")
    return values


def prepare_env_local(
    workspace: str | Path,
    account_id: str,
    env_local_path: str | Path,
    calendar: MarketCalendar,
    *,
    write_env_local: bool,
    confirm_paper_test: bool,
    validate_temp: Callable[[str | Path], dict[str, str]] = read_env_local,
) -> dict[str, Any]:
    if not write_env_local:
        return _blocked("write_env_local_confirmation_required")

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
        values = _values_from_rollover(rollover, str(account_id or "").strip())
    except ValueError as exc:
        return _blocked("rollover_result_invalid", [str(exc)])

    env_path = Path(env_local_path)
    if not env_path.parent.is_dir():
        return _blocked("env_local_parent_directory_not_found", [str(env_path.parent)])
    expected_content = render_env_local(values)
    if env_path.exists():
        try:
            if read_env_local(env_path) == values:
                return _pass_result(values, env_path, backup_created=False, file_changed=False)
        except (OSError, UnicodeError, ValueError):
            pass

    temp_path = env_path.with_name(f"{env_path.name}.tmp")
    backup_path = env_path.with_name(f"{env_path.name}.bak")
    backup_created = False
    try:
        temp_path.write_bytes(expected_content)
        if validate_temp(temp_path) != values:
            raise ValueError("temp_env_local_values_mismatch")
        if env_path.exists():
            shutil.copy2(env_path, backup_path)
            backup_created = True
        os.replace(temp_path, env_path)
    except (OSError, UnicodeError, ValueError) as exc:
        return _blocked("env_local_write_failed", [f"{type(exc).__name__}:{exc}"])
    finally:
        if temp_path.exists():
            temp_path.unlink()

    return _pass_result(values, env_path, backup_created=backup_created, file_changed=True)


def _pass_result(
    values: dict[str, str],
    env_path: Path,
    *,
    backup_created: bool,
    file_changed: bool,
) -> dict[str, Any]:
    return {
        "runner_result": "PASS",
        "mode": "WRITE_ENV_LOCAL",
        "account_id": values["ACCOUNT_ID"],
        "data_date": values["DATA_DATE"],
        "trade_date": values["TRADE_DATE"],
        "runbook_day_id": values["RUNBOOK_DAY_ID"],
        "env_local_path": str(env_path).replace("\\", "/"),
        "backup_created": backup_created,
        "file_changed": file_changed,
        "safe_to_prepare": True,
        "next_required_action": NEXT_ACTION,
    }

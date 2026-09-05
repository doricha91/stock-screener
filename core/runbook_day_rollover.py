from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from core.paper_account_paths import build_paper_account_paths
from core.runbook_calendar import CalendarCoverageError, MarketCalendar
from core import runbook_recovery, runbook_retirement
from scripts import runbook_stage_e_evidence
from scripts import runbook_stage_f_evidence
from scripts import runbook_state


NEXT_ACTION = "Run 6-4C to prepare the local runbook environment."
BLOCKED_ACTION = "Resolve the blockers before preparing a new runbook day."
RUNBOOK_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+_\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2}$")
COMPLETION_STAGES = ("A", "GATE1", "B", "C", "GATE2", "D", "E", "F")
DUPLICATE_DIRS = (
    "artifacts",
    "command_runs",
    "stage_runs",
    "gate_runs",
    "reconciliation_runs",
    "verification_runs",
)


@dataclass(frozen=True)
class StateRecord:
    path: Path
    state: runbook_state.RunbookState
    raw_stage_status: dict[str, Any]


def _blocked(reason: str, blockers: list[str] | None = None) -> dict[str, Any]:
    return {
        "runner_result": "BLOCKED",
        "mode": "PREVIEW",
        "reason": reason,
        "blockers": blockers or [reason],
        "safe_to_prepare": False,
        "next_required_action": BLOCKED_ACTION,
    }


def _is_standard_completed(workspace: Path, state: runbook_state.RunbookState) -> bool:
    state_complete = (
        state.current_stage == "F"
        and state.current_status == "PASS"
        and state.last_completed_step == 21
        and state.last_completed_stage == "F"
        and all(state.stage_status.get(stage_id) == "PASS" for stage_id in COMPLETION_STAGES)
        and bool(state.artifacts.get("final_status_report_json"))
        and bool(state.artifacts.get("account_snapshot_notion_report_json"))
        and bool(state.artifacts.get("benchmark_notion_report_json"))
        and state.last_error is None
    )
    if not state_complete:
        return False
    try:
        account_root = build_paper_account_paths(
            state.frozen_context.account_id, create=False
        ).root.resolve(strict=False)
    except ValueError:
        return False
    if not account_root.is_dir():
        return False
    if not runbook_stage_e_evidence.validate_stage_e_completion_evidence(
        workspace, state, account_root
    )["valid"]:
        return False
    evidence = runbook_stage_f_evidence.validate_stage_f_completion_evidence(
        workspace,
        state,
        account_root,
    )
    return bool(evidence["valid"])


def _is_legacy_completed(workspace: Path, record: StateRecord) -> bool:
    state = record.state
    legacy_stages = COMPLETION_STAGES[:-1]
    state_complete = (
        "F" not in record.raw_stage_status
        and set(record.raw_stage_status) == set(legacy_stages)
        and all(record.raw_stage_status.get(stage_id) == "PASS" for stage_id in legacy_stages)
        and state.current_stage == "E"
        and state.current_status == "PASS"
        and state.last_completed_step == 18
        and state.last_completed_stage == "E"
        and state.last_error is None
        and bool(state.artifacts.get("final_status_report_json"))
    )
    if not state_complete:
        return False
    return bool(
        runbook_stage_e_evidence.validate_legacy_stage_e_completion_evidence(
            workspace, state
        )["valid"]
    )


def classify_state(
    workspace: Path,
    record: StateRecord,
    calendar: MarketCalendar | None = None,
) -> dict[str, Any]:
    if _is_standard_completed(workspace, record.state):
        classification = "STANDARD_COMPLETED"
        blockers: list[str] = []
    elif _is_legacy_completed(workspace, record):
        classification = "LEGACY_COMPLETED"
        blockers = []
    else:
        retirement = runbook_retirement.validate_retirement_evidence(
            workspace, record.path, record.state
        )
        if retirement["valid"]:
            classification = "RETIRED"
            blockers = []
        else:
            recovery = runbook_recovery.validate_recovery_evidence(
                workspace,
                record.path,
                record.state,
                calendar or runbook_recovery.default_calendar(),
            )
            if recovery["valid"]:
                classification = "RECOVERY_EXCLUDED"
                blockers = []
            else:
                classification = "ACTIVE_INCOMPLETE"
                blockers = recovery["blockers"] if recovery["exists"] else (
                    retirement["blockers"] if retirement["exists"] else []
                )
    return {
        "runbook_day_id": record.state.runbook_day_id,
        "data_date": record.state.frozen_context.data_date,
        "trade_date": record.state.frozen_context.trade_date,
        "classification": classification,
        "blockers": blockers,
    }


def _account_filename_prefix(account_id: str) -> str:
    marker = runbook_state.get_runbook_day_id(account_id, "2000-01-01", "2000-01-02")
    return marker.rsplit("_2000-01-01_2000-01-02", 1)[0] + "_"


def _load_account_states(workspace: Path, account_id: str) -> tuple[list[StateRecord], list[str]]:
    state_dir = workspace / runbook_state.STATE_DIRNAME
    if not state_dir.is_dir():
        return [], ["runbook_states_directory_not_found"]

    records: list[StateRecord] = []
    blockers: list[str] = []
    prefix = _account_filename_prefix(account_id)
    for path in sorted(state_dir.glob("*.json")):
        try:
            raw_payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw_payload, dict):
                raise ValueError("state_json_must_be_object")
            raw_stage_status = raw_payload.get("stage_status")
            if not isinstance(raw_stage_status, dict):
                raise ValueError("stage_status_must_be_object")
            state = runbook_state.load_state(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            if path.name.startswith(prefix):
                blockers.append(f"invalid_state_file:{path.name}:{type(exc).__name__}")
            continue
        if state.frozen_context.account_id != account_id:
            if path.name.startswith(prefix):
                blockers.append(f"state_account_mismatch:{path.name}")
            continue
        validation_errors = runbook_state.validate_state(state)
        if validation_errors:
            blockers.extend(f"invalid_state:{path.name}:{error}" for error in validation_errors)
            continue
        if not RUNBOOK_ID_PATTERN.fullmatch(state.runbook_day_id):
            blockers.append(f"invalid_runbook_day_id:{path.name}")
            continue
        if path.name != f"{state.runbook_day_id}.json":
            blockers.append(f"state_filename_mismatch:{path.name}")
            continue
        records.append(StateRecord(path=path, state=state, raw_stage_status=dict(raw_stage_status)))
    return records, blockers


def classify_account_runbooks(workspace: str | Path, account_id: str) -> dict[str, Any]:
    workspace_path = Path(workspace).resolve(strict=False)
    records, blockers = _load_account_states(workspace_path, str(account_id or "").strip())
    return {
        "classifications": [classify_state(workspace_path, record) for record in records],
        "blockers": blockers,
    }


def _already_exists(workspace: Path, runbook_day_id: str) -> bool:
    state_path = runbook_state.get_state_path_for_runbook_day_id(workspace, runbook_day_id)
    if state_path.exists():
        return True
    return any((workspace / dirname / runbook_day_id).exists() for dirname in DUPLICATE_DIRS)


def preview_rollover(
    workspace: str | Path,
    account_id: str,
    calendar: MarketCalendar,
    *,
    confirm_paper_test: bool,
) -> dict[str, Any]:
    workspace_path = Path(workspace).resolve(strict=False)
    account_id = str(account_id or "").strip()
    if not confirm_paper_test:
        return _blocked("paper_test_confirmation_required")
    if "paper" not in account_id.lower() and "test" not in account_id.lower():
        return _blocked("paper_account_required")
    if not workspace_path.is_dir():
        return _blocked("invalid_workspace")

    records, state_blockers = _load_account_states(workspace_path, account_id)
    if state_blockers:
        return _blocked("invalid_runbook_state", state_blockers)
    if not records:
        return _blocked("completed_runbook_day_not_found")

    classified = [(record, classify_state(workspace_path, record, calendar)) for record in records]
    active = [record for record, item in classified if item["classification"] == "ACTIVE_INCOMPLETE"]
    if len(active) > 1:
        return _blocked(
            "multiple_active_runbook_days",
            [f"active_runbook_day:{record.state.runbook_day_id}" for record in active],
        )
    if active:
        return _blocked(
            "active_runbook_day_exists",
            [f"active_runbook_day:{active[0].state.runbook_day_id}"],
        )

    recoveries = [
        record for record, item in classified if item["classification"] == "RECOVERY_EXCLUDED"
    ]
    current_recoveries, recovery_blockers = (
        runbook_recovery._current_recovery_authorizations(
            workspace_path,
            recoveries,
            calendar,
        )
    )
    if recovery_blockers:
        return _blocked("recovery_authorization_invalid", recovery_blockers)
    if len(current_recoveries) > 1:
        return _blocked(
            "multiple_recovery_authorizations",
            [
                f"recovery_source:{record.state.runbook_day_id}"
                for record, _ in current_recoveries
            ],
        )
    if current_recoveries:
        source, recovery = current_recoveries[0]
        restart = recovery["payload"]["restart"]
        already_exists = _already_exists(workspace_path, restart["runbook_day_id"])
        if already_exists:
            return _blocked("recovery_target_already_exists")
        return {
            "runner_result": "PASS",
            "mode": "PREVIEW",
            "rollover_mode": "RECOVERY",
            "account_id": account_id,
            "previous_runbook_day_id": recovery["payload"]["latest_completed"]["runbook_day_id"],
            "recovery_source_runbook_day_id": source.state.runbook_day_id,
            "next_data_date": restart["data_date"],
            "next_trade_date": restart["trade_date"],
            "next_runbook_day_id": restart["runbook_day_id"],
            "runbook_classifications": [item for _, item in classified],
            "already_exists": False,
            "safe_to_prepare": True,
            "next_required_action": NEXT_ACTION,
        }

    completed = [
        record
        for record, item in classified
        if item["classification"] in {"STANDARD_COMPLETED", "LEGACY_COMPLETED"}
    ]
    if not completed:
        return _blocked("completed_runbook_day_not_found")
    latest_trade_date = max(record.state.frozen_context.trade_date for record in completed)
    latest = [record for record in completed if record.state.frozen_context.trade_date == latest_trade_date]
    if len(latest) != 1:
        return _blocked(
            "latest_completed_runbook_day_ambiguous",
            [f"candidate:{record.state.runbook_day_id}" for record in latest],
        )

    previous = latest[0].state
    previous_data_date = date.fromisoformat(previous.frozen_context.data_date)
    previous_trade_date = date.fromisoformat(previous.frozen_context.trade_date)
    next_data_date = previous_trade_date
    try:
        next_trade_date = calendar.next_trading_day(next_data_date)
    except CalendarCoverageError as exc:
        return _blocked("calendar_coverage_exceeded", [str(exc)])
    if next_data_date < previous_data_date or next_trade_date <= previous_trade_date:
        return _blocked("calculated_dates_move_backward")

    next_runbook_day_id = runbook_state.get_runbook_day_id(
        account_id,
        next_data_date.isoformat(),
        next_trade_date.isoformat(),
    )
    already_exists = _already_exists(workspace_path, next_runbook_day_id)
    return {
        "runner_result": "PASS",
        "mode": "PREVIEW",
        "account_id": account_id,
        "previous_runbook_day_id": previous.runbook_day_id,
        "next_data_date": next_data_date.isoformat(),
        "next_trade_date": next_trade_date.isoformat(),
        "next_runbook_day_id": next_runbook_day_id,
        "runbook_classifications": [item for _, item in classified],
        "already_exists": already_exists,
        "safe_to_prepare": not already_exists,
        "next_required_action": NEXT_ACTION if not already_exists else "Inspect the existing next runbook day before 6-4C.",
    }

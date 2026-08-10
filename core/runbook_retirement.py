from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from scripts import runbook_state


SCHEMA_VERSION = "runbook_retirement.v1"
RETIREMENT_DIRNAME = "runbook_retirements"
OPERATIONAL_EVIDENCE_DIRS = (
    "artifacts",
    "command_runs",
    "stage_runs",
    "gate_runs",
    "reconciliation_runs",
    "verification_runs",
)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def retirement_path(workspace: Path, runbook_day_id: str) -> Path:
    return workspace / RETIREMENT_DIRNAME / f"{runbook_day_id}.json"


def _load_raw_state(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("state_json_must_be_object")
    return payload


def assess_zero_progress(
    workspace: Path,
    state_path: Path,
    state: runbook_state.RunbookState,
) -> dict[str, Any]:
    blockers: list[str] = []
    try:
        raw = _load_raw_state(state_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return {"eligible": False, "blockers": [f"state_invalid:{type(exc).__name__}"]}
    if runbook_state.validate_state(state):
        blockers.append("state_contract_invalid")
    if state.current_stage != "A" or state.current_status != "READY":
        blockers.append("state_not_initial_ready")
    if state.last_completed_stage is not None or state.last_completed_step is not None:
        blockers.append("completed_progress_present")
    raw_status = raw.get("stage_status")
    if not isinstance(raw_status, dict) or set(raw_status) != set(runbook_state.STAGE_IDS):
        blockers.append("stage_status_contract_invalid")
    elif any(raw_status.get(stage_id) != "PENDING" for stage_id in runbook_state.STAGE_IDS):
        blockers.append("stage_progress_present")
    if state.artifacts:
        blockers.append("artifact_evidence_present")
    if state.idempotency_records:
        blockers.append("command_evidence_present")
    if state.recovery_authorizations:
        blockers.append("recovery_evidence_present")
    if state.history:
        blockers.append("history_progress_present")
    if state.last_error is not None:
        blockers.append("last_error_present")
    for dirname in OPERATIONAL_EVIDENCE_DIRS:
        evidence_root = workspace / dirname / state.runbook_day_id
        try:
            if evidence_root.exists() and any(evidence_root.rglob("*")):
                blockers.append(f"workspace_evidence_present:{dirname}")
        except OSError:
            blockers.append(f"workspace_evidence_unreadable:{dirname}")
    return {
        "eligible": not blockers,
        "blockers": blockers,
        "state_sha256": sha256_file(state_path) if not blockers else None,
    }


def validate_retirement_evidence(
    workspace: Path,
    state_path: Path,
    state: runbook_state.RunbookState,
) -> dict[str, Any]:
    path = retirement_path(workspace, state.runbook_day_id)
    if not path.is_file():
        return {"valid": False, "exists": False, "path": path, "blockers": ["retirement_evidence_missing"]}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"valid": False, "exists": True, "path": path, "blockers": ["retirement_evidence_invalid_json"]}
    blockers: list[str] = []
    expected_context = {
        "account_id": state.frozen_context.account_id,
        "data_date": state.frozen_context.data_date,
        "trade_date": state.frozen_context.trade_date,
    }
    expected_ref = state_path.relative_to(workspace).as_posix()
    if not isinstance(payload, dict):
        blockers.append("retirement_evidence_must_be_object")
    else:
        expected_values = {
            "schema_version": SCHEMA_VERSION,
            "status": "RETIRED",
            "runbook_day_id": state.runbook_day_id,
            "frozen_context": expected_context,
            "state_ref": expected_ref,
        }
        for field, expected in expected_values.items():
            if payload.get(field) != expected:
                blockers.append(f"retirement_{field}_mismatch")
        if not isinstance(payload.get("reason"), str) or not payload["reason"].strip():
            blockers.append("retirement_reason_missing")
        created_at = payload.get("created_at")
        try:
            created_dt = datetime.fromisoformat(created_at) if isinstance(created_at, str) else None
        except ValueError:
            created_dt = None
        if created_dt is None or created_dt.tzinfo is None:
            blockers.append("retirement_created_at_invalid")
        pinned_sha = payload.get("state_sha256")
        if not isinstance(pinned_sha, str) or SHA256_PATTERN.fullmatch(pinned_sha) is None:
            blockers.append("retirement_state_sha256_invalid")
        elif pinned_sha != sha256_file(state_path):
            blockers.append("retirement_state_sha256_mismatch")
        if payload.get("zero_progress_verified") is not True:
            blockers.append("retirement_zero_progress_not_verified")
    assessment = assess_zero_progress(workspace, state_path, state)
    blockers.extend(f"retirement_state_not_zero_progress:{item}" for item in assessment["blockers"])
    return {
        "valid": not blockers,
        "exists": True,
        "path": path,
        "payload": payload,
        "blockers": blockers,
    }


def _blocked(reason: str, blockers: list[str] | None = None) -> dict[str, Any]:
    return {
        "runner_result": "BLOCKED",
        "reason": reason,
        "blockers": blockers or [reason],
        "retired": False,
    }


def retire_runbook(
    workspace: Path,
    *,
    account_id: str,
    data_date: str,
    trade_date: str,
    runbook_day_id: str,
    reason: str,
    confirm_paper_test: bool,
    confirm_retire_zero_progress: bool,
) -> dict[str, Any]:
    workspace = workspace.resolve(strict=False)
    account_id = str(account_id or "").strip()
    reason = str(reason or "").strip()
    if not confirm_paper_test:
        return _blocked("paper_test_confirmation_required")
    if not confirm_retire_zero_progress:
        return _blocked("retirement_confirmation_required")
    if "paper" not in account_id.lower() and "test" not in account_id.lower():
        return _blocked("paper_account_required")
    if not reason:
        return _blocked("retirement_reason_required")
    try:
        expected_id = runbook_state.get_runbook_day_id(account_id, data_date, trade_date)
    except ValueError as exc:
        return _blocked("retirement_context_invalid", [str(exc)])
    if runbook_day_id != expected_id:
        return _blocked("runbook_day_id_mismatch")
    state_path = runbook_state.get_state_path_for_runbook_day_id(workspace, runbook_day_id)
    try:
        state = runbook_state.load_state(state_path)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        return _blocked("runbook_state_invalid", [f"{type(exc).__name__}:{exc}"])
    if not runbook_state.context_matches_state(state, account_id, data_date, trade_date):
        return _blocked("runbook_state_context_mismatch")

    existing = validate_retirement_evidence(workspace, state_path, state)
    if existing["exists"]:
        if not existing["valid"]:
            return _blocked("existing_retirement_evidence_invalid", existing["blockers"])
        if existing["payload"].get("reason") != reason:
            return _blocked("retirement_reason_mismatch")
        return {
            "runner_result": "PASS",
            "retired": True,
            "already_retired": True,
            "runbook_day_id": runbook_day_id,
            "evidence_path": str(existing["path"]),
            "state_sha256": existing["payload"]["state_sha256"],
        }

    assessment = assess_zero_progress(workspace, state_path, state)
    if not assessment["eligible"]:
        return _blocked("runbook_not_zero_progress", assessment["blockers"])
    evidence = {
        "schema_version": SCHEMA_VERSION,
        "status": "RETIRED",
        "created_at": datetime.now(ZoneInfo(state.timezone)).isoformat(),
        "runbook_day_id": runbook_day_id,
        "frozen_context": {
            "account_id": state.frozen_context.account_id,
            "data_date": state.frozen_context.data_date,
            "trade_date": state.frozen_context.trade_date,
        },
        "reason": reason,
        "state_ref": state_path.relative_to(workspace).as_posix(),
        "state_sha256": assessment["state_sha256"],
        "zero_progress_verified": True,
    }
    path = retirement_path(workspace, runbook_day_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    try:
        temp_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    return {
        "runner_result": "PASS",
        "retired": True,
        "already_retired": False,
        "runbook_day_id": runbook_day_id,
        "evidence_path": str(path),
        "state_sha256": evidence["state_sha256"],
    }


def retirement_status(
    workspace: Path,
    *,
    account_id: str,
    data_date: str,
    trade_date: str,
    runbook_day_id: str,
) -> dict[str, Any]:
    workspace = workspace.resolve(strict=False)
    try:
        expected_id = runbook_state.get_runbook_day_id(account_id, data_date, trade_date)
    except ValueError as exc:
        return _blocked("retirement_context_invalid", [str(exc)])
    if runbook_day_id != expected_id:
        return _blocked("runbook_day_id_mismatch")
    state_path = runbook_state.get_state_path_for_runbook_day_id(workspace, runbook_day_id)
    try:
        state = runbook_state.load_state(state_path)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        return _blocked("runbook_state_invalid", [f"{type(exc).__name__}:{exc}"])
    if not runbook_state.context_matches_state(state, account_id, data_date, trade_date):
        return _blocked("runbook_state_context_mismatch")
    validation = validate_retirement_evidence(workspace, state_path, state)
    if not validation["exists"]:
        assessment = assess_zero_progress(workspace, state_path, state)
        return {
            "runner_result": "PASS",
            "retired": False,
            "retirement_status": "NOT_RETIRED",
            "runbook_day_id": runbook_day_id,
            "retire_eligible": assessment["eligible"],
            "blockers": assessment["blockers"],
        }
    if not validation["valid"]:
        return _blocked("retirement_evidence_invalid", validation["blockers"])
    return {
        "runner_result": "PASS",
        "retired": True,
        "retirement_status": "RETIRED",
        "runbook_day_id": runbook_day_id,
        "evidence_path": str(validation["path"]),
        "state_sha256": validation["payload"]["state_sha256"],
        "reason": validation["payload"]["reason"],
    }

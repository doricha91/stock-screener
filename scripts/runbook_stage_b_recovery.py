from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.paper_account_paths import build_paper_account_paths
from core.paper_execution_log import paper_trade_preview_to_row
from core.paper_manual_execution_commit import _candidate_to_trade_preview
from scripts import runbook_state
from scripts.runbook_state import RunbookState


ASSESSMENT_SCHEMA_VERSION = "stage_b_recovery_assessment.v1"
PRESEAL_SCHEMA_VERSION = "stage_b_execution_commit_preseal.v1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def canonical_json_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _canonical_number(value: Any) -> str:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid_numeric_value:{value}") from exc
    normalized = format(number.normalize(), "f")
    return "0" if normalized in {"-0", ""} else normalized


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"json_root_must_be_object:{path}")
    return payload


def resolve_workspace_ref(workspace: Path, ref: str) -> Path:
    path = Path(str(ref or "").strip())
    if not str(path):
        raise ValueError("artifact_ref_required")
    return path.resolve(strict=False) if path.is_absolute() else (workspace / path).resolve(strict=False)


def normalize_candidate_sequence(preview: dict[str, Any], state: RunbookState) -> list[dict[str, Any]]:
    candidates = preview.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("execution_preview_candidates_required")
    normalized: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            raise ValueError("execution_preview_candidate_must_be_object")
        account_id = str(candidate.get("account_id") or "").strip()
        execution_date = str(candidate.get("execution_date") or "").strip()
        if account_id != state.frozen_context.account_id or execution_date != state.frozen_context.trade_date:
            raise ValueError("execution_preview_candidate_context_mismatch")
        trade_row = paper_trade_preview_to_row(_candidate_to_trade_preview(candidate))
        normalized.append(
            {
                "sequence_index": index,
                "trade_id": str(trade_row["trade_id"]),
                "symbol": str(candidate.get("symbol") or "").strip().upper(),
                "side": str(candidate.get("side") or "").strip().upper(),
                "shares": int(trade_row["shares"]),
                "quantity": int(candidate.get("quantity") or 0),
                "execution_price": _canonical_number(candidate.get("actual_price")),
                "execution_date": execution_date,
                "account_id": account_id,
            }
        )
    return normalized


def normalize_reconciliation(payload: dict[str, Any], state: RunbookState) -> dict[str, Any]:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("reconciliation_rows_required")
    normalized_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError("reconciliation_row_must_be_object")
        normalized_rows.append(
            {
                "sequence_index": index,
                "plan_external_key": str(row.get("plan_external_key") or ""),
                "manual_execution_external_key": str(row.get("manual_execution_external_key") or ""),
                "symbol": str(row.get("symbol") or "").strip().upper(),
                "side": str(row.get("side") or "").strip().upper(),
                "planned_quantity": int(row.get("planned_quantity") or 0),
                "actual_quantity": int(row.get("actual_quantity") or 0),
                "planned_price": _canonical_number(row.get("planned_price") or 0),
                "actual_price": _canonical_number(row.get("actual_price") or 0),
                "reconciliation_status": str(row.get("reconciliation_status") or "").upper(),
                "deviation_type": str(row.get("deviation_type") or "").upper(),
                "severity": str(row.get("severity") or "").upper(),
            }
        )
    context = {
        "account_id": str(payload.get("account_id") or ""),
        "data_date": str(payload.get("data_date") or ""),
        "trade_date": str(payload.get("trade_date") or ""),
    }
    expected = {
        "account_id": state.frozen_context.account_id,
        "data_date": state.frozen_context.data_date,
        "trade_date": state.frozen_context.trade_date,
    }
    if context != expected:
        raise ValueError("reconciliation_context_mismatch")
    return {
        "schema_version": str(payload.get("schema_version") or ""),
        "runner_result": str(payload.get("runner_result") or "").upper(),
        **context,
        "notion_row_count": int(payload.get("notion_row_count") or 0),
        "actual_count": int(payload.get("actual_count") or 0),
        "planned_count": int(payload.get("planned_count") or 0),
        "matched_count": int(payload.get("matched_count") or 0),
        "deviated_count": int(payload.get("deviated_count") or 0),
        "missing_count": int(payload.get("missing_count") or 0),
        "extra_count": int(payload.get("extra_count") or 0),
        "warning_count": int(payload.get("warning_count") or 0),
        "needs_review_count": int(payload.get("needs_review_count") or 0),
        "blocked_count": int(payload.get("blocked_count") or 0),
        "rows": normalized_rows,
    }


def build_stage_b_logical_operation(state: RunbookState, workspace: Path) -> dict[str, Any]:
    workspace = Path(workspace).resolve(strict=False)
    refs = {
        "daily_plan": state.artifacts.get("daily_plan_json"),
        "execution_preview": state.artifacts.get("execution_preview_json"),
        "reconciliation_preview": state.artifacts.get("execution_reconciliation_preview_json"),
    }
    paths: dict[str, Path] = {}
    for name, ref in refs.items():
        if not ref:
            raise ValueError(f"{name}_artifact_required")
        path = resolve_workspace_ref(workspace, str(ref))
        if not path.is_file():
            raise ValueError(f"{name}_artifact_missing")
        paths[name] = path

    preview = _load_json(paths["execution_preview"])
    reconciliation = _load_json(paths["reconciliation_preview"])
    candidate_sequence = normalize_candidate_sequence(preview, state)
    reconciliation_content = normalize_reconciliation(reconciliation, state)
    candidate_sha = canonical_json_sha256(candidate_sequence)
    reconciliation_sha = canonical_json_sha256(reconciliation_content)
    daily_plan_sha = sha256_file(paths["daily_plan"]).lower()
    logical_payload = {
        "runbook_day_id": state.runbook_day_id,
        "command_key": "execution_commit",
        "account_id": state.frozen_context.account_id,
        "trade_date": state.frozen_context.trade_date,
        "daily_plan_sha256": daily_plan_sha,
        "candidate_sequence_sha256": candidate_sha,
        "reconciliation_content_sha256": reconciliation_sha,
    }
    logical_sha = canonical_json_sha256(logical_payload)
    return {
        "logical_operation_id": f"sha256:{logical_sha}",
        "logical_operation_sha256": logical_sha,
        "logical_operation_payload": logical_payload,
        "candidate_sequence": candidate_sequence,
        "candidate_sequence_sha256": candidate_sha,
        "reconciliation_content": reconciliation_content,
        "reconciliation_content_sha256": reconciliation_sha,
        "daily_plan_path": str(paths["daily_plan"]),
        "daily_plan_sha256": daily_plan_sha,
        "execution_preview_path": str(paths["execution_preview"]),
        "execution_preview_sha256": sha256_file(paths["execution_preview"]).lower(),
        "reconciliation_preview_path": str(paths["reconciliation_preview"]),
        "reconciliation_preview_sha256": sha256_file(paths["reconciliation_preview"]).lower(),
        "expected_trade_ids": [item["trade_id"] for item in candidate_sequence],
    }


def _file_evidence(path: Path) -> dict[str, Any]:
    path = Path(path).resolve(strict=False)
    exists = path.is_file()
    return {"path": str(path), "exists": exists, "sha256": sha256_file(path).lower() if exists else None}


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _date_row_count(rows: list[dict[str, str]], trade_date: str) -> int:
    fields = ("date", "snapshot_date", "execution_date", "trade_date")
    return sum(1 for row in rows if any(str(row.get(field) or "").strip() == trade_date for field in fields))


def _command_result_path(workspace: Path, state: RunbookState) -> Path:
    last_error = state.last_error if isinstance(state.last_error, dict) else {}
    error = last_error.get("error") if isinstance(last_error.get("error"), dict) else {}
    ref = str(error.get("command_result_json") or "").strip()
    if not ref:
        raise ValueError("failed_command_result_required")
    path = resolve_workspace_ref(workspace, ref)
    if not path.is_file():
        raise ValueError("failed_command_result_missing")
    return path


def _matching_legacy_backups(
    account_root: Path,
    trade_date: str,
    command_result: dict[str, Any],
    current_paths: dict[str, Path],
) -> dict[str, dict[str, Any]]:
    created_at = str(command_result.get("created_at") or "")
    try:
        attempt_stamp = datetime.fromisoformat(created_at).strftime("%Y%m%d_%H%M%S")
    except ValueError:
        attempt_stamp = ""
    trade_compact = trade_date.replace("-", "")
    backup_root = account_root / "archive" / "dev_backups"
    result: dict[str, dict[str, Any]] = {}
    for name, current_path in current_paths.items():
        pattern = f"{current_path.stem}_before_manual_execution_commit_{trade_compact}_{attempt_stamp}.csv"
        candidates = sorted(backup_root.glob(pattern)) if attempt_stamp else []
        backup_path = candidates[-1] if candidates else backup_root / pattern
        evidence = _file_evidence(backup_path)
        evidence["matches_current"] = bool(
            evidence["exists"] and current_path.is_file() and evidence["sha256"] == sha256_file(current_path).lower()
        )
        result[name] = evidence
    return result


def _preseal_from_failed_record(workspace: Path, record: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    refs = record.get("artifact_refs") if isinstance(record.get("artifact_refs"), dict) else {}
    ref = str(refs.get("precommit_evidence_json") or "").strip()
    if not ref:
        return None, None
    path = resolve_workspace_ref(workspace, ref)
    if not path.is_file():
        return None, str(path)
    return _load_json(path), str(path)


def assess_stage_b_recovery(
    *,
    workspace: Path,
    account_id: str,
    data_date: str,
    trade_date: str,
    failed_idempotency_key: str,
    account_root: Path | None = None,
) -> dict[str, Any]:
    workspace = Path(workspace).resolve(strict=False)
    state_path = runbook_state.get_state_path_for_context(workspace, account_id, data_date, trade_date)
    state = runbook_state.load_state(state_path)
    state_sha = sha256_file(state_path).lower()
    blockers: list[str] = []
    warnings: list[str] = []
    if not runbook_state.context_matches_state(state, account_id, data_date, trade_date):
        blockers.append("state_context_mismatch")
    if state.current_stage != "B" or state.current_status != "FAILED" or state.stage_status.get("B") != "FAILED":
        blockers.append("stage_b_failed_state_required")
    record = state.idempotency_records.get(failed_idempotency_key)
    if not isinstance(record, dict):
        record = {}
        blockers.append("failed_idempotency_record_required")
    elif not (
        record.get("stage_id") == "B"
        and record.get("step_id") == 8
        and record.get("command_key") == "execution_commit"
        and record.get("status") == "FAILED"
    ):
        blockers.append("failed_idempotency_record_context_mismatch")

    command_path: Path | None = None
    command_payload: dict[str, Any] = {}
    try:
        command_path = _command_result_path(workspace, state)
        command_payload = _load_json(command_path)
    except ValueError as exc:
        blockers.append(str(exc))
    process = command_payload.get("process") if isinstance(command_payload.get("process"), dict) else {}
    executed = process.get("executed") is True
    exit_code = process.get("exit_code")
    timed_out = process.get("timed_out") is True or exit_code == 124
    raw_payload = command_payload.get("raw_payload") if isinstance(command_payload.get("raw_payload"), dict) else {}
    raw_status = str(raw_payload.get("status") or raw_payload.get("runner_result") or "").upper()
    raw_error = str(raw_payload.get("error") or "")
    explicit_failure = executed and isinstance(exit_code, int) and exit_code != 0 and not timed_out
    if not explicit_failure or raw_status not in {"FAIL", "FAILED", "BLOCKED"} or not raw_error:
        blockers.append("explicit_nonzero_execution_commit_failure_required")
    if timed_out or not executed:
        blockers.append("ambiguous_command_outcome")

    logical: dict[str, Any] = {}
    try:
        logical = build_stage_b_logical_operation(state, workspace)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        blockers.append(f"logical_operation_evidence_invalid:{exc}")

    paths = build_paper_account_paths(account_id, account_root=account_root, create=False)
    current_paths = {
        "execution": paths.execution_log_path,
        "account": paths.account_snapshot_path,
        "position": paths.position_snapshot_path,
    }
    current_files = {name: _file_evidence(path) for name, path in current_paths.items()}
    csv_rows = {name: _read_csv(path) for name, path in current_paths.items()}
    expected_ids = list(logical.get("expected_trade_ids") or [])
    ledger_ids = [str(row.get("trade_id") or "").strip() for row in csv_rows["execution"]]
    present_ids = [trade_id for trade_id in expected_ids if trade_id in ledger_ids]
    if not expected_ids:
        blockers.append("expected_trade_ids_required")
    if present_ids:
        blockers.append("expected_trade_id_already_present")
    same_date_counts = {name: _date_row_count(rows, trade_date) for name, rows in csv_rows.items()}
    if any(same_date_counts.values()):
        blockers.append("candidate_related_same_date_mutation_present")
    current_state_path = paths.current_state_snapshot_path(trade_date)
    if current_state_path.exists():
        blockers.append("target_current_state_mutation_present")

    commit_ref = str(state.artifacts.get("execution_commit_report_json") or "")
    sync_ref = str(
        state.artifacts.get("execution_status_sync_report_json")
        or state.artifacts.get("execution_status_sync_report")
        or ""
    )
    commit_exists = bool(commit_ref and resolve_workspace_ref(workspace, commit_ref).is_file())
    sync_exists = bool(sync_ref and resolve_workspace_ref(workspace, sync_ref).is_file())
    pass_evidence = any(
        isinstance(item, dict)
        and item.get("command_key") == "execution_commit"
        and item.get("status") == "PASS"
        for item in state.idempotency_records.values()
    )
    if commit_exists or pass_evidence:
        blockers.append("successful_execution_commit_evidence_present")
    if sync_exists:
        blockers.append("execution_sync_evidence_present")

    preseal, preseal_path = _preseal_from_failed_record(workspace, record)
    backups: dict[str, dict[str, Any]] = {}
    evidence_mode = "PRECOMMIT_SEALED"
    if preseal:
        sealed_files = preseal.get("operational_files") if isinstance(preseal.get("operational_files"), dict) else {}
        for name, current in current_files.items():
            sealed = sealed_files.get(name) if isinstance(sealed_files.get(name), dict) else {}
            if sealed.get("sha256") != current.get("sha256"):
                blockers.append(f"{name}_hash_changed_since_preseal")
    else:
        evidence_mode = "LEGACY_BACKUP_CORROBORATED"
        warnings.append("legacy_evidence_tier_requires_human_authorization")
        backups = _matching_legacy_backups(paths.root, trade_date, command_payload, current_paths)
        for name, backup in backups.items():
            if not backup.get("matches_current"):
                blockers.append(f"{name}_backup_hash_mismatch")

    if timed_out or not explicit_failure:
        classification = "AMBIGUOUS_OUTCOME"
    elif present_ids or any(same_date_counts.values()) or current_state_path.exists():
        classification = "PARTIAL_WRITE"
    elif blockers:
        classification = "FORENSIC_RECOVERY_REQUIRED"
    else:
        classification = "HUMAN_RECOVERY_ELIGIBLE"
    eligible = classification == "HUMAN_RECOVERY_ELIGIBLE"
    evidence_seal_payload = {
        "runbook_day_id": state.runbook_day_id,
        "state_sha256": state_sha,
        "failed_idempotency_key": failed_idempotency_key,
        "command_result_sha256": sha256_file(command_path).lower() if command_path else None,
        "logical_operation_id": logical.get("logical_operation_id"),
        "daily_plan_sha256": logical.get("daily_plan_sha256"),
        "candidate_sequence_sha256": logical.get("candidate_sequence_sha256"),
        "reconciliation_content_sha256": logical.get("reconciliation_content_sha256"),
        "expected_trade_ids": expected_ids,
        "current_files": current_files,
        "same_date_counts": same_date_counts,
        "current_state_exists": current_state_path.exists(),
        "backups": backups,
        "preseal_path": preseal_path,
        "commit_exists": commit_exists,
        "sync_exists": sync_exists,
        "pass_evidence": pass_evidence,
        "classification": classification,
        "blockers": blockers,
    }
    return {
        "schema_version": ASSESSMENT_SCHEMA_VERSION,
        "created_at": datetime.now().astimezone().isoformat(timespec="microseconds"),
        "runbook_day_id": state.runbook_day_id,
        "frozen_context": state.frozen_context.__dict__,
        "state_path": str(state_path.resolve(strict=False)),
        "state_sha256": state_sha,
        "current_stage": state.current_stage,
        "current_status": state.current_status,
        "last_error": state.last_error,
        "failed_idempotency_key": failed_idempotency_key,
        "failed_idempotency_status": record.get("status"),
        "failed_command": {
            "stage_id": record.get("stage_id"),
            "step_id": record.get("step_id"),
            "command_key": record.get("command_key"),
            "result_path": str(command_path) if command_path else None,
            "result_sha256": sha256_file(command_path).lower() if command_path else None,
            "process": process,
            "explicit_failure": explicit_failure,
            "ambiguous": timed_out or not executed,
        },
        "execution_preview_path": logical.get("execution_preview_path"),
        "execution_preview_sha256": logical.get("execution_preview_sha256"),
        "reconciliation_preview_path": logical.get("reconciliation_preview_path"),
        "reconciliation_preview_sha256": logical.get("reconciliation_preview_sha256"),
        "daily_plan_path": logical.get("daily_plan_path"),
        "daily_plan_sha256": logical.get("daily_plan_sha256"),
        "normalized_candidate_sequence": logical.get("candidate_sequence", []),
        "candidate_sequence_sha256": logical.get("candidate_sequence_sha256"),
        "reconciliation_content_sha256": logical.get("reconciliation_content_sha256"),
        "logical_operation_id": logical.get("logical_operation_id"),
        "expected_trade_ids": expected_ids,
        "same_operation_trade_ids_present": present_ids,
        "operational_files": current_files,
        "same_date_row_counts": same_date_counts,
        "current_state_target": {"path": str(current_state_path), "exists": current_state_path.exists()},
        "commit_report_exists": commit_exists,
        "sync_report_exists": sync_exists,
        "successful_commit_evidence_exists": pass_evidence,
        "precommit_evidence": {"path": preseal_path, "payload": preseal},
        "legacy_backups": backups,
        "evidence_mode": evidence_mode,
        "recovery_classification": classification,
        "human_retry_eligible": eligible,
        "evidence_seal_sha256": canonical_json_sha256(evidence_seal_payload),
        "account_root": str(paths.root.resolve(strict=False)),
        "blockers": blockers,
        "warnings": warnings,
    }


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f"{path.name}.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def authorize_stage_b_recovery(
    *,
    workspace: Path,
    account_id: str,
    data_date: str,
    trade_date: str,
    assessment_path: Path,
    operator: str,
    reason: str,
    confirm_rollback_proven: bool,
) -> dict[str, Any]:
    if not confirm_rollback_proven:
        raise ValueError("confirm_rollback_proven_required")
    assessment_path = Path(assessment_path).resolve(strict=True)
    assessment = _load_json(assessment_path)
    if assessment.get("schema_version") != ASSESSMENT_SCHEMA_VERSION:
        raise ValueError("assessment_schema_invalid")
    expected_context = {"account_id": account_id, "data_date": data_date, "trade_date": trade_date}
    if assessment.get("frozen_context") != expected_context:
        raise ValueError("assessment_context_mismatch")
    state_path = runbook_state.get_state_path_for_context(Path(workspace), account_id, data_date, trade_date)
    if sha256_file(state_path).lower() != assessment.get("state_sha256"):
        raise ValueError("assessment_state_sha256_drift")
    current = assess_stage_b_recovery(
        workspace=Path(workspace),
        account_id=account_id,
        data_date=data_date,
        trade_date=trade_date,
        failed_idempotency_key=str(assessment.get("failed_idempotency_key") or ""),
        account_root=Path(str(assessment.get("account_root") or "")),
    )
    if not current.get("human_retry_eligible"):
        raise ValueError("assessment_no_longer_human_retry_eligible")
    if current.get("evidence_seal_sha256") != assessment.get("evidence_seal_sha256"):
        raise ValueError("assessment_evidence_drift")
    assessment_sha = sha256_file(assessment_path).lower()
    state = runbook_state.load_state(state_path)
    authorization_id = f"stage_b_retry_{uuid.uuid4().hex}"
    next_state = runbook_state.authorize_stage_b_retry(
        state,
        authorization_id=authorization_id,
        logical_operation_id=str(assessment.get("logical_operation_id") or ""),
        failed_idempotency_key=str(assessment.get("failed_idempotency_key") or ""),
        assessment_path=str(assessment_path),
        assessment_sha256=assessment_sha,
        state_before_sha256=str(assessment.get("state_sha256") or ""),
        operator=operator,
        reason=reason,
    )
    runbook_state.save_state(next_state, state_path)
    return {
        "runner_result": "PASS",
        "authorization_id": authorization_id,
        "logical_operation_id": assessment.get("logical_operation_id"),
        "state_path": str(state_path),
        "current_stage": next_state.current_stage,
        "current_status": next_state.current_status,
        "assessment_sha256": assessment_sha,
    }


def write_precommit_evidence(
    *,
    workspace: Path,
    state_path: Path,
    state: RunbookState,
    logical: dict[str, Any],
    attempt_id: str,
    account_root: Path | None = None,
) -> tuple[Path, str]:
    workspace = Path(workspace).resolve(strict=False)
    paths = build_paper_account_paths(state.frozen_context.account_id, account_root=account_root, create=False)
    current_state_path = paths.current_state_snapshot_path(state.frozen_context.trade_date)
    payload = {
        "schema_version": PRESEAL_SCHEMA_VERSION,
        "created_at": datetime.now().astimezone().isoformat(timespec="microseconds"),
        "runbook_day_id": state.runbook_day_id,
        "frozen_context": state.frozen_context.__dict__,
        "logical_operation_id": logical["logical_operation_id"],
        "attempt_id": attempt_id,
        "daily_plan_sha256": logical["daily_plan_sha256"],
        "candidate_sequence_sha256": logical["candidate_sequence_sha256"],
        "reconciliation_content_sha256": logical["reconciliation_content_sha256"],
        "expected_trade_ids": logical["expected_trade_ids"],
        "execution_preview": {
            "path": logical["execution_preview_path"],
            "sha256": logical["execution_preview_sha256"],
        },
        "reconciliation_preview": {
            "path": logical["reconciliation_preview_path"],
            "sha256": logical["reconciliation_preview_sha256"],
        },
        "operational_files": {
            "execution": _file_evidence(paths.execution_log_path),
            "account": _file_evidence(paths.account_snapshot_path),
            "position": _file_evidence(paths.position_snapshot_path),
        },
        "target_current_state": _file_evidence(current_state_path),
        "state_path": str(Path(state_path).resolve(strict=False)),
        "state_sha256_before_attempt": sha256_file(state_path).lower(),
    }
    output = workspace / "artifacts" / state.runbook_day_id / "stage_b" / f"stage_b_execution_commit_preseal_{attempt_id}.json"
    write_json_atomic(output, payload)
    return output, runbook_state.canonicalize_artifact_ref(str(output), workspace)


def validate_stage_b_commit_proof(
    *, state: RunbookState, workspace: Path, account_root: Path | None = None
) -> dict[str, Any]:
    workspace = Path(workspace).resolve(strict=False)
    pass_records = [
        record
        for record in state.idempotency_records.values()
        if isinstance(record, dict)
        and record.get("command_key") == "execution_commit"
        and record.get("status") == "PASS"
    ]
    if len(pass_records) != 1:
        return {"valid": False, "reason": "execution_commit_pass_record_required"}
    record = pass_records[0]
    artifact_report_ref = str(state.artifacts.get("execution_commit_report_json") or "")
    record_report_ref = str(record.get("result_ref") or "")
    report_ref = artifact_report_ref or record_report_ref
    if not report_ref:
        return {"valid": False, "reason": "execution_commit_report_required"}
    report_path = resolve_workspace_ref(workspace, report_ref)
    if not report_path.is_file():
        return {"valid": False, "reason": "execution_commit_report_required"}
    if artifact_report_ref and record_report_ref:
        if resolve_workspace_ref(workspace, artifact_report_ref) != resolve_workspace_ref(workspace, record_report_ref):
            return {"valid": False, "reason": "execution_commit_report_ref_mismatch"}
    try:
        report = _load_json(report_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return {"valid": False, "reason": "execution_commit_report_invalid"}
    if report.get("status") != "COMMITTED":
        return {"valid": False, "reason": "execution_commit_report_invalid"}
    if str(report.get("account_id") or "") != state.frozen_context.account_id:
        return {"valid": False, "reason": "execution_commit_report_context_mismatch"}
    if str(report.get("execution_date") or "") != state.frozen_context.trade_date:
        return {"valid": False, "reason": "execution_commit_report_context_mismatch"}
    trade_ids = [str(item or "").strip() for item in report.get("committed_trade_ids", [])]
    if not trade_ids or len(trade_ids) != int(report.get("committed_row_count") or 0) or len(set(trade_ids)) != len(trade_ids):
        return {"valid": False, "reason": "execution_commit_report_trade_ids_invalid"}
    paths = build_paper_account_paths(state.frozen_context.account_id, account_root=account_root, create=False)
    rows = _read_csv(paths.execution_log_path)
    ledger_ids = [str(row.get("trade_id") or "").strip() for row in rows]
    if any(ledger_ids.count(trade_id) != 1 for trade_id in trade_ids):
        return {"valid": False, "reason": "execution_commit_ledger_proof_mismatch"}
    logical_id = str(record.get("logical_operation_id") or "")
    if logical_id:
        try:
            logical = build_stage_b_logical_operation(state, workspace)
        except (OSError, ValueError, json.JSONDecodeError):
            return {"valid": False, "reason": "execution_commit_logical_proof_invalid"}
        if logical_id != logical["logical_operation_id"]:
            return {"valid": False, "reason": "execution_commit_logical_proof_mismatch"}
        if trade_ids != logical["expected_trade_ids"]:
            return {"valid": False, "reason": "execution_commit_trade_sequence_mismatch"}
    return {
        "valid": True,
        "reason": None,
        "record": record,
        "report_path": str(report_path),
        "report_sha256": sha256_file(report_path).lower(),
        "committed_trade_ids": trade_ids,
        "committed_row_count": len(trade_ids),
        "logical_operation_id": logical_id or None,
    }


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage B strict-write recovery assessment and authorization")
    subparsers = parser.add_subparsers(dest="command", required=True)
    assess_parser = subparsers.add_parser("assess", help="Create a read-only Stage B recovery assessment")
    authorize_parser = subparsers.add_parser("authorize", help="Authorize one proven-rollback Stage B retry")
    for item in (assess_parser, authorize_parser):
        item.add_argument("--workspace", type=Path, required=True)
        item.add_argument("--account-id", required=True)
        item.add_argument("--data-date", required=True)
        item.add_argument("--trade-date", required=True)
    assess_parser.add_argument("--failed-idempotency-key", required=True)
    assess_parser.add_argument("--account-root", type=Path)
    assess_parser.add_argument("--output", type=Path, required=True)
    authorize_parser.add_argument("--assessment-json", type=Path, required=True)
    authorize_parser.add_argument("--operator", required=True)
    authorize_parser.add_argument("--reason", required=True)
    authorize_parser.add_argument("--confirm-rollback-proven", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "assess":
            result = assess_stage_b_recovery(
                workspace=args.workspace,
                account_id=args.account_id,
                data_date=args.data_date,
                trade_date=args.trade_date,
                failed_idempotency_key=args.failed_idempotency_key,
                account_root=args.account_root,
            )
            write_json_atomic(args.output, result)
            _print_json({**result, "assessment_path": str(args.output.resolve(strict=False))})
            return 0 if result["human_retry_eligible"] else 1
        result = authorize_stage_b_recovery(
            workspace=args.workspace,
            account_id=args.account_id,
            data_date=args.data_date,
            trade_date=args.trade_date,
            assessment_path=args.assessment_json,
            operator=args.operator,
            reason=args.reason,
            confirm_rollback_proven=args.confirm_rollback_proven,
        )
        _print_json(result)
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _print_json({"runner_result": "BLOCKED", "reason": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

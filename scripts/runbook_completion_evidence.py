from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from core.paper_execution_intent import validate_daily_plan_execution_intent
from core.paper_execution_log import PAPER_EXECUTION_LOG_COLUMNS
from core.paper_account_snapshot import PAPER_ACCOUNT_SNAPSHOT_COLUMNS
from core.paper_manual_review_log_validator import (
    load_paper_manual_review_log_rows,
    validate_paper_manual_review_log_rows,
)
from core.paper_symbol_unrealized_performance import (
    load_paper_account_snapshot_rows,
    load_paper_position_snapshot_rows,
)
from core.paper_position_snapshot import PAPER_POSITION_SNAPSHOT_COLUMNS
from scripts import runbook_result
from scripts.runbook_state import RunbookState


MANIFEST_SCHEMA_VERSION = "runbook_completion_manifest.v1"
STANDARD_COMPLETION_SCHEMA_VERSION = "runbook_standard_completion.v1"
STANDARD_REQUIRED_PASS_STAGES = ("A", "GATE1", "B", "C", "GATE2", "D")
STANDARD_EXPORT_COMMANDS = {
    "DAILY_PLAN_NOTION_EXPORT": ("A", 4, "export_daily_plan_notion"),
    "MANUAL_EXECUTION_TEMPLATE": ("A", 5, "export_execution_template"),
    "MANUAL_REVIEW_TEMPLATE": ("C", 11, "export_review_template"),
}
NO_ACTION_ARTIFACT_KEYS = (
    "execution_preview_json",
    "execution_commit_report_json",
    "execution_commit_report",
    "execution_status_sync_report_json",
    "execution_status_sync_report",
    "review_preview_json",
    "review_append_report_json",
    "review_commit_report",
    "review_status_sync_report_json",
    "review_status_sync_report",
)
NO_ACTION_WRITE_COMMAND_KEYS = {
    "execution_commit",
    "sync_execution_status",
    "review_append",
    "sync_review_status",
}


class CompletionEvidenceError(ValueError):
    def __init__(self, reason: str, detail: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail or reason


def resolve_workspace_ref(
    workspace: Path | str,
    ref: Path | str,
    *,
    require_exists: bool = True,
    require_file: bool = True,
) -> Path:
    workspace_path = Path(workspace).resolve(strict=False)
    text = str(ref or "").strip()
    if not text:
        raise CompletionEvidenceError("workspace_ref_required")
    candidate = Path(text.replace("\\", "/"))
    resolved = (
        candidate.resolve(strict=False)
        if candidate.is_absolute()
        else (workspace_path / candidate).resolve(strict=False)
    )
    try:
        resolved.relative_to(workspace_path)
    except ValueError as exc:
        raise CompletionEvidenceError("workspace_ref_outside_workspace") from exc
    if require_exists and not resolved.exists():
        raise CompletionEvidenceError("workspace_ref_missing")
    if require_file and resolved.exists() and not resolved.is_file():
        raise CompletionEvidenceError("workspace_ref_not_file")
    return resolved


def workspace_relative_ref(workspace: Path | str, path: Path | str) -> str:
    resolved = resolve_workspace_ref(workspace, path, require_exists=False, require_file=False)
    return resolved.relative_to(Path(workspace).resolve(strict=False)).as_posix()


def validate_no_action_contradictions(state: RunbookState) -> None:
    for artifact_name in NO_ACTION_ARTIFACT_KEYS:
        if state.artifacts.get(artifact_name):
            raise CompletionEvidenceError(
                "no_action_write_artifact_present",
                f"{artifact_name} contradicts NO_ACTION completion",
            )
    for record in state.idempotency_records.values():
        if str(record.get("command_key") or "") in NO_ACTION_WRITE_COMMAND_KEYS:
            raise CompletionEvidenceError(
                "no_action_write_idempotency_present",
                f"{record.get('command_key')} idempotency contradicts NO_ACTION completion",
            )


def build_standard_completion_context(
    workspace: Path | str,
    state: RunbookState,
) -> dict[str, Any]:
    workspace_path = Path(workspace).resolve(strict=False)
    for stage_id in STANDARD_REQUIRED_PASS_STAGES:
        if state.stage_status.get(stage_id) != "PASS":
            raise CompletionEvidenceError("standard_runbook_stage_incomplete", stage_id)

    expected_context = {
        "account_id": state.frozen_context.account_id,
        "data_date": state.frozen_context.data_date,
        "trade_date": state.frozen_context.trade_date,
    }
    zero_review_evidence = _build_standard_zero_review_evidence(
        workspace_path,
        state,
        expected_context,
    )
    summaries = {
        stage_id: _load_standard_stage_summary(workspace_path, state, stage_id, expected_context)
        for stage_id in {spec[0] for spec in STANDARD_EXPORT_COMMANDS.values()}
    }
    authoritative_stages: dict[str, Any] = {}
    for stage_name, (stage_id, step_id, command_key) in STANDARD_EXPORT_COMMANDS.items():
        summary, summary_path = summaries[stage_id]
        matching_steps = [
            step
            for step in summary["steps"]
            if isinstance(step, dict)
            and step.get("step_id") == step_id
            and step.get("command_key") == command_key
        ]
        if len(matching_steps) != 1 or matching_steps[0].get("runner_result") != "PASS":
            raise CompletionEvidenceError("standard_runbook_command_missing_or_failed", command_key)
        result_ref = str(matching_steps[0].get("result_json_ref") or "").strip()
        result_path = resolve_workspace_ref(workspace_path, result_ref)
        if command_key == "export_review_template":
            pinned_ref = str(state.artifacts.get("notion_review_template_report_json") or "").strip()
            if not pinned_ref or resolve_workspace_ref(workspace_path, pinned_ref) != result_path:
                raise CompletionEvidenceError("standard_runbook_pinned_artifact_mismatch", command_key)
        result = _load_json_object(result_path, "standard_runbook_command_result_invalid")
        _validate_standard_command_result(
            result,
            state=state,
            stage_id=stage_id,
            step_id=step_id,
            command_key=command_key,
            allow_zero_review=zero_review_evidence is not None,
        )
        authoritative_stages[stage_name] = {
            "stage_id": stage_id,
            "step_id": step_id,
            "command_key": command_key,
            "summary_ref": workspace_relative_ref(workspace_path, summary_path),
            "summary_sha256": _sha256_file(summary_path),
            "result_ref": workspace_relative_ref(workspace_path, result_path),
            "result_sha256": _sha256_file(result_path),
        }
    result = {
        "schema_version": STANDARD_COMPLETION_SCHEMA_VERSION,
        "runbook_day_id": state.runbook_day_id,
        **expected_context,
        "action_mode": "STANDARD",
        "authoritative_stages": authoritative_stages,
    }
    if zero_review_evidence is not None:
        result["zero_review_evidence"] = zero_review_evidence
    return result


def _load_standard_stage_summary(
    workspace: Path,
    state: RunbookState,
    stage_id: str,
    expected_context: dict[str, str],
) -> tuple[dict[str, Any], Path]:
    path = workspace / "stage_runs" / state.runbook_day_id / f"latest_{stage_id}.json"
    path = resolve_workspace_ref(workspace, path)
    summary = _load_json_object(path, "standard_runbook_stage_summary_invalid")
    if runbook_result.validate_stage_summary(summary):
        raise CompletionEvidenceError("standard_runbook_stage_summary_invalid", stage_id)
    if (
        summary.get("runner_result") != "PASS"
        or summary.get("stage_status") != "PASS"
        or summary.get("runbook_day_id") != state.runbook_day_id
        or summary.get("frozen_context") != expected_context
        or summary.get("stage_id") != stage_id
    ):
        raise CompletionEvidenceError("standard_runbook_stage_summary_mismatch", stage_id)
    return summary, path


def _validate_standard_command_result(
    result: dict[str, Any],
    *,
    state: RunbookState,
    stage_id: str,
    step_id: int,
    command_key: str,
    allow_zero_review: bool = False,
) -> None:
    if runbook_result.validate_command_result(result):
        raise CompletionEvidenceError("standard_runbook_command_result_invalid", command_key)
    expected_context = {
        "account_id": state.frozen_context.account_id,
        "data_date": state.frozen_context.data_date,
        "trade_date": state.frozen_context.trade_date,
    }
    process = result.get("process")
    summary = result.get("summary")
    if (
        result.get("runner_result") != "PASS"
        or result.get("runbook_day_id") != state.runbook_day_id
        or result.get("frozen_context") != expected_context
        or result.get("stage_id") != stage_id
        or result.get("step_id") != step_id
        or result.get("command_key") != command_key
        or not isinstance(process, dict)
        or process.get("executed") is not True
        or process.get("exit_code") != 0
        or not isinstance(summary, dict)
        or bool(summary.get("blockers"))
    ):
        raise CompletionEvidenceError("standard_runbook_command_result_mismatch", command_key)
    _validate_standard_export_payload(
        result.get("raw_payload"),
        state,
        command_key,
        allow_zero_review=allow_zero_review,
    )


def _validate_standard_export_payload(
    payload: Any,
    state: RunbookState,
    command_key: str,
    *,
    allow_zero_review: bool = False,
) -> None:
    if not isinstance(payload, dict):
        raise CompletionEvidenceError("standard_runbook_export_payload_invalid", command_key)
    account_id = state.frozen_context.account_id
    trade_date = state.frozen_context.trade_date
    if command_key == "export_daily_plan_notion":
        rows = payload.get("json")
        valid = (
            isinstance(rows, list)
            and len(rows) == 1
            and isinstance(rows[0], dict)
            and rows[0].get("target") == "daily_plans"
            and rows[0].get("account_id") == account_id
            and rows[0].get("external_key") == f"daily_plan:{account_id}:{trade_date}"
            and rows[0].get("failed_count") == 0
            and rows[0].get("dry_run") is False
        )
    else:
        expected = {
            "export_execution_template": ("manual_execution_template", "execution_date"),
            "export_review_template": ("manual_review_template", "review_date"),
        }
        target, date_field = expected[command_key]
        candidate_count = payload.get("candidate_count")
        processed_count = sum(
            value if isinstance(value, int) and not isinstance(value, bool) else -10**9
            for value in (payload.get("create_count"), payload.get("update_count"), payload.get("skip_count"))
        )
        valid = (
            payload.get("target") == target
            and payload.get("account_id") == account_id
            and payload.get(date_field) == trade_date
            and isinstance(candidate_count, int)
            and not isinstance(candidate_count, bool)
            and (
                candidate_count > 0
                or (command_key == "export_review_template" and allow_zero_review and candidate_count == 0)
            )
            and processed_count >= candidate_count
            and payload.get("failed_count") == 0
            and payload.get("dry_run") is False
            and payload.get("would_write") is (candidate_count > 0)
        )
    if not valid:
        raise CompletionEvidenceError("standard_runbook_export_payload_invalid", command_key)


def _build_standard_zero_review_evidence(
    workspace: Path,
    state: RunbookState,
    expected_context: dict[str, str],
) -> dict[str, Any] | None:
    scope_ref = str(state.artifacts.get("manual_review_scope_json") or "").strip()
    if not scope_ref:
        return None
    scope_path = resolve_workspace_ref(workspace, scope_ref)
    scope = _load_json_object(scope_path, "standard_zero_review_scope_invalid")
    counts = scope.get("counts")
    if not isinstance(counts, dict) or counts.get("total") != 0:
        return None
    frozen_context = scope.get("frozen_context")
    if (
        scope.get("schema_version") != "paper_daily_manual_review_scope.v1"
        or scope.get("action_mode") != "EXECUTION"
        or not isinstance(frozen_context, dict)
        or frozen_context
        != {"runbook_day_id": state.runbook_day_id, **expected_context}
        or scope.get("canonical_keys") != []
        or scope.get("rows") != []
    ):
        raise CompletionEvidenceError("standard_zero_review_scope_invalid")
    scope_basis = {
        key: scope[key]
        for key in (
            "schema_version",
            "frozen_context",
            "action_mode",
            "sources",
            "manual_review_symbols",
            "current_open_symbols",
            "position_symbols",
            "execution_symbols",
            "canonical_keys",
            "rows",
        )
    }
    scope_sha256 = hashlib.sha256(
        json.dumps(scope_basis, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    if scope.get("scope_sha256") != scope_sha256:
        raise CompletionEvidenceError("standard_zero_review_scope_invalid")

    stage_c_summary, stage_c_summary_path = _load_standard_stage_summary(
        workspace,
        state,
        "C",
        expected_context,
    )
    stage_c_raw = stage_c_summary.get("raw_payload")
    if not isinstance(stage_c_raw, dict) or not (
        stage_c_raw.get("action_mode") == "EXECUTION"
        and stage_c_raw.get("verified_no_action") is False
        and stage_c_raw.get("verified_zero_write") is True
        and stage_c_raw.get("manual_review_scope_sha256") == scope_sha256
        and stage_c_raw.get("manual_review_scope_count") == 0
    ):
        raise CompletionEvidenceError("standard_zero_review_stage_c_invalid")

    verification_ref = str(state.artifacts.get("stage_b_verification_json") or "").strip()
    verification_path = resolve_workspace_ref(workspace, verification_ref)
    verification = _load_json_object(
        verification_path,
        "standard_zero_review_stage_b_invalid",
    )
    if not (
        verification.get("schema_version") == "stage_b_verification.v1"
        and verification.get("runner_result") == "PASS"
        and verification.get("action_mode") == "EXECUTION"
        and verification.get("execution_contract_version") == "execution_reconciliation_preview.v2"
        and verification.get("verified_no_action") is False
        and verification.get("verified_zero_write") is True
        and verification.get("committed_row_count") == 0
        and verification.get("executed_count") == 0
        and verification.get("partial_count") == 0
        and verification.get("planned_count") == verification.get("not_executed_count")
    ):
        raise CompletionEvidenceError("standard_zero_review_stage_b_invalid")

    gate_ref = str(state.artifacts.get("gate2_readiness_json") or "").strip()
    gate_path = resolve_workspace_ref(workspace, gate_ref)
    gate = _load_json_object(gate_path, "standard_zero_review_gate2_invalid")
    if not (
        gate.get("schema_version") == "gate2_review_readiness.v1"
        and gate.get("runner_result") == "PASS"
        and gate.get("action_mode") == "EXECUTION"
        and gate.get("manual_review_scope_sha256") == scope_sha256
        and gate.get("manual_review_scope_count") == 0
        and gate.get("candidate_count") == 0
        and gate.get("required_count") == 0
        and gate.get("manual_review_row_count") == 0
    ):
        raise CompletionEvidenceError("standard_zero_review_gate2_invalid")

    artifact_specs = {
        "review_preview": (
            "review_preview_json",
            lambda payload: (
                payload.get("account_id") == state.frozen_context.account_id
                and payload.get("review_date") == state.frozen_context.trade_date
                and payload.get("candidate_count") == 0
                and payload.get("fail_count") == 0
                and payload.get("blocked_count", 0) == 0
                and payload.get("append_allowed") == "true"
                and payload.get("candidates") == []
            ),
        ),
        "review_append": (
            "review_append_report_json",
            lambda payload: (
                payload.get("account_id") == state.frozen_context.account_id
                and payload.get("review_date") == state.frozen_context.trade_date
                and payload.get("candidate_count") == 0
                and payload.get("appended_count") == 0
                and payload.get("failed_count") == 0
                and payload.get("rows") == []
            ),
        ),
        "review_status_sync": (
            "review_status_sync_report_json",
            lambda payload: (
                payload.get("overall_status") == "SUCCESS"
                and payload.get("account_id") == state.frozen_context.account_id
                and payload.get("review_date") == state.frozen_context.trade_date
                and payload.get("candidate_count") == 0
                and payload.get("updated_count") == 0
                and payload.get("failed_count") == 0
                and payload.get("rows") == []
            ),
        ),
    }
    artifacts: dict[str, Any] = {}
    for label, (artifact_name, validator) in artifact_specs.items():
        ref = str(state.artifacts.get(artifact_name) or "").strip()
        path = resolve_workspace_ref(workspace, ref)
        payload = _load_json_object(path, f"standard_zero_review_{label}_invalid")
        if not validator(payload):
            raise CompletionEvidenceError(f"standard_zero_review_{label}_invalid")
        artifacts[label] = {
            "ref": workspace_relative_ref(workspace, path),
            "sha256": _sha256_file(path),
        }

    stage_d_summary, stage_d_summary_path = _load_standard_stage_summary(
        workspace,
        state,
        "D",
        expected_context,
    )
    command_keys = {
        step.get("command_key")
        for step in stage_d_summary.get("steps", [])
        if isinstance(step, dict) and step.get("runner_result") == "PASS"
    }
    if not {"review_append", "sync_review_status"}.issubset(command_keys):
        raise CompletionEvidenceError("standard_zero_review_stage_d_invalid")
    return {
        "required_review_count": 0,
        "verified_zero_review": True,
        "manual_review_scope_ref": workspace_relative_ref(workspace, scope_path),
        "manual_review_scope_sha256": scope_sha256,
        "stage_b_verification_ref": workspace_relative_ref(workspace, verification_path),
        "stage_b_verification_sha256": _sha256_file(verification_path),
        "stage_c_summary_ref": workspace_relative_ref(workspace, stage_c_summary_path),
        "stage_c_summary_sha256": _sha256_file(stage_c_summary_path),
        "gate2_ref": workspace_relative_ref(workspace, gate_path),
        "gate2_sha256": _sha256_file(gate_path),
        "stage_d_summary_ref": workspace_relative_ref(workspace, stage_d_summary_path),
        "stage_d_summary_sha256": _sha256_file(stage_d_summary_path),
        "artifacts": artifacts,
    }


def _load_json_object(path: Path, reason: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CompletionEvidenceError(reason) from exc
    if not isinstance(payload, dict):
        raise CompletionEvidenceError(reason)
    return payload


def build_runbook_completion_manifest(
    workspace: Path | str,
    state: RunbookState,
    account_root: Path | str,
) -> dict[str, Any]:
    workspace_path = Path(workspace).resolve(strict=False)
    account_path = Path(account_root).resolve(strict=False)
    if not account_path.is_dir():
        raise CompletionEvidenceError("account_root_missing")
    if state.stage_status.get("D") != "PASS":
        raise CompletionEvidenceError("stage_d_required")

    no_action = bool(state.artifacts.get("stage_d_no_action_json"))
    if no_action:
        validate_no_action_contradictions(state)
        from scripts.runbook_no_action import build_no_action_completion_context

        build_no_action_completion_context(workspace_path, state, account_root=account_path)

    trade_date = _normalize_date(state.frozen_context.trade_date, "trade_date")
    daily_plan = _daily_plan_source(workspace_path, account_path, state)
    execution = _csv_source(
        account_path / "paper_execution_log.csv",
        logical_ref="account:paper_execution_log.csv",
        scope_date=trade_date,
        date_field="date",
        loader=lambda path: _load_execution_rows(path, account_path),
        expected_account_id=state.frozen_context.account_id,
    )
    review = _csv_source(
        account_path / "reviews" / "paper_manual_review_log.csv",
        logical_ref="account:reviews/paper_manual_review_log.csv",
        scope_date=trade_date,
        date_field="review_date",
        loader=lambda path: _load_review_rows(path, account_path),
        expected_account_id=state.frozen_context.account_id,
    )
    account_snapshot = _csv_source(
        account_path / "paper_account_snapshot.csv",
        logical_ref="account:paper_account_snapshot.csv",
        scope_date=trade_date,
        date_field="snapshot_date",
        loader=lambda path: _load_account_snapshot(path, account_path),
        expected_account_id=state.frozen_context.account_id,
    )
    position_snapshot = _csv_source(
        account_path / "paper_position_snapshot.csv",
        logical_ref="account:paper_position_snapshot.csv",
        scope_date=trade_date,
        date_field="snapshot_date",
        loader=lambda path: _load_position_snapshot(path, account_path),
        expected_account_id=state.frozen_context.account_id,
    )
    if no_action and (execution["record_count"] or review["record_count"]):
        raise CompletionEvidenceError("no_action_same_date_rows_present")
    if not no_action and state.artifacts.get("manual_review_scope_json"):
        scope_payload = _load_json_object(
            resolve_workspace_ref(workspace_path, state.artifacts["manual_review_scope_json"]),
            "standard_zero_review_scope_invalid",
        )
        scope_counts = scope_payload.get("counts")
        if (
            scope_payload.get("action_mode") == "EXECUTION"
            and isinstance(scope_counts, dict)
            and scope_counts.get("total") == 0
        ):
            completion = build_standard_completion_context(workspace_path, state)
            if not isinstance(completion.get("zero_review_evidence"), dict):
                raise CompletionEvidenceError("standard_zero_review_evidence_required")
            if execution["record_count"] or review["record_count"]:
                raise CompletionEvidenceError("standard_zero_review_same_date_rows_present")
    eod_commit = _eod_source(workspace_path, state)
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "runbook_day_id": state.runbook_day_id,
        "account_id": state.frozen_context.account_id,
        "data_date": _normalize_date(state.frozen_context.data_date, "data_date"),
        "trade_date": trade_date,
        "completion_mode": "NO_ACTION" if no_action else "STANDARD",
        "sources": {
            "daily_plan": daily_plan,
            "execution_ledger": execution,
            "review_ledger": review,
            "account_snapshot": account_snapshot,
            "position_snapshot": position_snapshot,
            "eod_commit": eod_commit,
        },
    }


def validate_completion_sources(
    workspace: Path | str,
    state: RunbookState,
    account_root: Path | str,
    *,
    stored_payload: dict[str, Any] | None,
    stored_manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    blockers: list[str] = []
    if not isinstance(stored_payload, dict):
        blockers.append("completion_payload_required")
    if not isinstance(stored_manifest, dict):
        blockers.append("completion_manifest_required")
    payload_manifest = stored_payload.get("completion_manifest") if isinstance(stored_payload, dict) else None
    if not isinstance(payload_manifest, dict):
        blockers.append("completion_manifest_required")
    if isinstance(payload_manifest, dict) and isinstance(stored_manifest, dict) and payload_manifest != stored_manifest:
        blockers.append("completion_manifest_artifact_mismatch")
    try:
        current = build_runbook_completion_manifest(workspace, state, account_root)
    except (OSError, ValueError) as exc:
        blockers.append(getattr(exc, "reason", type(exc).__name__))
        current = None
    if current is not None:
        if isinstance(payload_manifest, dict) and payload_manifest != current:
            blockers.append("completion_manifest_source_mismatch")
        if isinstance(stored_manifest, dict) and stored_manifest != current:
            blockers.append("completion_manifest_source_mismatch")
        if isinstance(stored_payload, dict) and stored_payload.get("completion_mode") != current["completion_mode"]:
            blockers.append("completion_mode_source_mismatch")
    return {"valid": not blockers, "blockers": list(dict.fromkeys(blockers)), "manifest": current}


def _daily_plan_source(workspace: Path, account_root: Path, state: RunbookState) -> dict[str, Any]:
    ref = state.artifacts.get("daily_plan_json")
    if not ref:
        raise CompletionEvidenceError("daily_plan_json_missing")
    workspace_plan = resolve_workspace_ref(workspace, str(ref))
    account_plan = account_root / f"daily_action_plan_{state.frozen_context.trade_date.replace('-', '')}.json"
    if not account_plan.is_file():
        raise CompletionEvidenceError("account_daily_plan_required")
    try:
        payload = json.loads(workspace_plan.read_text(encoding="utf-8"))
        account_payload = json.loads(account_plan.read_text(encoding="utf-8"))
        validate_daily_plan_execution_intent(
            payload,
            expected_account_id=state.frozen_context.account_id,
            expected_data_date=state.frozen_context.data_date,
            expected_trade_date=state.frozen_context.trade_date,
        )
        validate_daily_plan_execution_intent(
            account_payload,
            expected_account_id=state.frozen_context.account_id,
            expected_data_date=state.frozen_context.data_date,
            expected_trade_date=state.frozen_context.trade_date,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise CompletionEvidenceError("daily_plan_execution_intent_invalid") from exc
    workspace_digest = _sha256_file(workspace_plan)
    account_digest = _sha256_file(account_plan)
    if workspace_digest != account_digest:
        raise CompletionEvidenceError("daily_plan_hash_mismatch")
    return {
        "kind": "json_file",
        "scope_date": state.frozen_context.trade_date,
        "logical_ref": f"workspace:{workspace_relative_ref(workspace, workspace_plan)}|account:{account_plan.name}",
        "presence": "required_present",
        "record_count": 1,
        "digest": workspace_digest,
        "workspace_digest": workspace_digest,
        "account_digest": account_digest,
    }


def _load_execution_rows(path: Path, account_root: Path) -> list[dict[str, str]]:
    _require_under_root(path, account_root)
    if not path.is_file():
        raise CompletionEvidenceError("source_file_missing", path.name)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = [str(item or "").replace("\ufeff", "").strip() for item in (reader.fieldnames or [])]
        missing = [field for field in PAPER_EXECUTION_LOG_COLUMNS if field not in fields]
        if missing:
            raise CompletionEvidenceError("source_schema_invalid", ",".join(missing))
        return list(reader)


def _load_review_rows(path: Path, account_root: Path) -> list[dict[str, str]]:
    try:
        rows = load_paper_manual_review_log_rows(path, allowed_root=account_root)
    except FileNotFoundError as exc:
        raise CompletionEvidenceError("source_file_missing", path.name) from exc
    issues, _ = validate_paper_manual_review_log_rows(rows)
    if any(issue.get("severity") == "error" for issue in issues):
        raise CompletionEvidenceError("source_schema_invalid", path.name)
    return rows


def _load_account_snapshot(path: Path, account_root: Path) -> list[dict[str, str]]:
    _validate_csv_header(path, PAPER_ACCOUNT_SNAPSHOT_COLUMNS)
    return load_paper_account_snapshot_rows(path, allowed_root=account_root)


def _load_position_snapshot(path: Path, account_root: Path) -> list[dict[str, str]]:
    _validate_csv_header(path, PAPER_POSITION_SNAPSHOT_COLUMNS)
    return load_paper_position_snapshot_rows(path, allowed_root=account_root)


def _validate_csv_header(path: Path, required: list[str]) -> None:
    if not path.is_file():
        raise CompletionEvidenceError("source_file_missing", path.name)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        fields = [str(item or "").replace("\ufeff", "").strip() for item in (csv.DictReader(handle).fieldnames or [])]
    missing = [field for field in required if field not in fields]
    if missing:
        raise CompletionEvidenceError("source_schema_invalid", ",".join(missing))


def _csv_source(
    path: Path,
    *,
    logical_ref: str,
    scope_date: str,
    date_field: str,
    loader: Callable[[Path], list[dict[str, str]]],
    expected_account_id: str,
) -> dict[str, Any]:
    if not path.is_file():
        raise CompletionEvidenceError("source_file_missing", logical_ref)
    try:
        rows = loader(path)
    except CompletionEvidenceError:
        raise
    except (OSError, ValueError) as exc:
        raise CompletionEvidenceError("source_schema_invalid", logical_ref) from exc
    selected: list[dict[str, Any]] = []
    for row in rows:
        raw_date = str(row.get(date_field) or "").strip()
        if not raw_date:
            continue
        try:
            row_date = _normalize_date(raw_date, date_field)
        except ValueError as exc:
            raise CompletionEvidenceError("source_date_invalid", logical_ref) from exc
        if row_date == scope_date:
            row_account = str(row.get("account_id") or "").strip()
            if row_account and row_account != expected_account_id:
                raise CompletionEvidenceError("source_context_mismatch", logical_ref)
            selected.append({str(key): _canonical_value(value) for key, value in row.items()})
    selected.sort(key=_canonical_json)
    return {
        "kind": "append_only_csv_date_slice",
        "scope_date": scope_date,
        "logical_ref": logical_ref,
        "presence": "required_present",
        "record_count": len(selected),
        "digest": _sha256_bytes(_canonical_json(selected).encode("utf-8")),
    }


def _eod_source(workspace: Path, state: RunbookState) -> dict[str, Any]:
    ref = state.artifacts.get("eod_commit_report_json")
    if not ref:
        raise CompletionEvidenceError("eod_commit_report_required")
    path = resolve_workspace_ref(workspace, str(ref))
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompletionEvidenceError("eod_commit_report_invalid") from exc
    expected = {
        "runner_result": "PASS",
        "status": "COMMITTED",
        "mode": "commit",
        "account_id": state.frozen_context.account_id,
        "date": state.frozen_context.trade_date,
        "trade_date": state.frozen_context.trade_date,
        "failed_count": 0,
        "blocked_count": 0,
        "current_state_written": True,
        "account_snapshot_written": True,
        "position_snapshot_written": True,
        "market_valuation_status": "success",
    }
    if any(payload.get(key) != value for key, value in expected.items()):
        raise CompletionEvidenceError("eod_commit_report_invalid")
    return {
        "kind": "json_file",
        "scope_date": state.frozen_context.trade_date,
        "logical_ref": f"workspace:{workspace_relative_ref(workspace, path)}",
        "presence": "required_present",
        "record_count": 1,
        "digest": _sha256_file(path),
    }


def _require_under_root(path: Path, root: Path) -> None:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError as exc:
        raise CompletionEvidenceError("account_source_outside_root") from exc


def _normalize_date(value: str, field: str) -> str:
    text = str(value or "").strip()
    try:
        if len(text) == 8 and text.isdigit():
            return datetime.strptime(text, "%Y%m%d").strftime("%Y-%m-%d")
        return datetime.strptime(text, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{field}_invalid") from exc


def _canonical_value(value: Any) -> Any:
    if value is None:
        return None
    return str(value).strip()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

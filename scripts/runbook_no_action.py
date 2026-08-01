from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paper_execution_intent import validate_daily_plan_execution_intent
from core.paper_manual_review_log_validator import load_paper_manual_review_log_rows
from scripts.runbook_state import RunbookState


NO_ACTION_SCHEMA_VERSION = "stage_b_no_action.v1"
NO_ACTION_COMPLETION_SCHEMA_VERSION = "runbook_no_action_completion.v1"
SKIPPED_COMMAND_KEYS = (
    "execution_preview",
    "execution_reconciliation_preview",
    "execution_commit",
    "sync_execution_status",
)


class EvidenceError(ValueError):
    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


def artifact_path(workspace: Path, artifact_ref: str) -> Path:
    path = Path(str(artifact_ref))
    workspace_resolved = Path(workspace).resolve(strict=False)
    resolved = path.resolve(strict=False) if path.is_absolute() else (workspace_resolved / path).resolve(strict=False)
    try:
        resolved.relative_to(workspace_resolved)
    except ValueError as exc:
        raise EvidenceError("artifact_ref_outside_workspace", f"artifact is outside workspace: {resolved}") from exc
    return resolved


def build_no_action_completion_context(
    workspace: Path,
    state: RunbookState,
    *,
    account_root: Path | None = None,
) -> dict[str, Any]:
    if state.stage_status.get("D") != "PASS":
        raise EvidenceError("stage_d_required", "Stage D must be PASS for no-action completion")
    context = validate_no_action_through_gate2(workspace, state)
    if context.get("action_mode") != "NO_ACTION" or context.get("verified_no_action") is not True:
        raise EvidenceError("no_action_evidence_mismatch", "Verified no-action context is required")
    evidence, evidence_path = load_stage_d_no_action_evidence(
        workspace,
        state,
        daily_plan_sha256=str(context.get("daily_plan_sha256") or ""),
    )
    if any(state.artifacts.get(key) for key in ("review_preview_json", "review_append_report_json", "review_status_sync_report_json")):
        raise EvidenceError("unexpected_review_artifact_for_no_action", "Review artifacts contradict no-action completion")

    eod_ref = state.artifacts.get("eod_commit_report_json")
    if not eod_ref:
        raise EvidenceError("eod_commit_report_required", "EOD commit report is not pinned")
    eod_path = artifact_path(workspace, str(eod_ref))
    eod = _load_json(eod_path, "eod_commit_report_required", "eod_commit_report_invalid")
    expected_eod = {
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
    if any(eod.get(key) != value for key, value in expected_eod.items()):
        raise EvidenceError("eod_commit_report_invalid", "EOD commit report does not prove same-date completion")
    for field in ("failed_count", "blocked_count"):
        if isinstance(eod.get(field), bool) or not isinstance(eod.get(field), int):
            raise EvidenceError("eod_commit_report_invalid", f"{field} must be an integer")

    if account_root is not None:
        account_plan = Path(account_root) / f"daily_action_plan_{state.frozen_context.trade_date.replace('-', '')}.json"
        if not account_plan.is_file():
            raise EvidenceError("account_daily_plan_required", "Account-root Daily Plan is required")
        if sha256_file(account_plan) != context["daily_plan_sha256"]:
            raise EvidenceError("daily_plan_hash_mismatch", "Account-root Daily Plan hash does not match proof")

    return {
        "schema_version": NO_ACTION_COMPLETION_SCHEMA_VERSION,
        "runbook_day_id": state.runbook_day_id,
        "account_id": state.frozen_context.account_id,
        "data_date": state.frozen_context.data_date,
        "trade_date": state.frozen_context.trade_date,
        "action_mode": "NO_ACTION",
        "verified_no_action": True,
        "execution_required": False,
        "review_required": False,
        "candidate_execution_count": 0,
        "manual_review_row_count": 0,
        "required_status_sync": False,
        "execution_write_performed": False,
        "review_write_performed": False,
        "eod_close_verified": True,
        "daily_plan_sha256": context["daily_plan_sha256"],
        "stage_d_no_action_json": str(state.artifacts.get("stage_d_no_action_json")),
        "eod_commit_report_json": str(eod_ref),
    }


def load_daily_plan_evidence(
    workspace: Path,
    state: RunbookState,
) -> tuple[dict[str, Any], dict[str, Any], Path]:
    artifact_ref = state.artifacts.get("daily_plan_json")
    if not artifact_ref:
        raise EvidenceError("daily_plan_json_missing", "daily_plan_json is not pinned in runbook state")
    path = artifact_path(workspace, str(artifact_ref))
    payload = _load_json(path, "daily_plan_json_missing", "daily_plan_json_invalid")
    try:
        intent = validate_daily_plan_execution_intent(
            payload,
            expected_account_id=state.frozen_context.account_id,
            expected_data_date=state.frozen_context.data_date,
            expected_trade_date=state.frozen_context.trade_date,
        )
    except ValueError as exc:
        detail = str(exc)
        reason = (
            "daily_plan_context_mismatch"
            if detail in {"account_id_mismatch", "data_date_mismatch", "trade_date_mismatch"}
            else "daily_plan_execution_intent_invalid"
        )
        raise EvidenceError(reason, detail) from exc
    return payload, intent, path


def load_gate1_evidence(workspace: Path, state: RunbookState) -> tuple[dict[str, Any], Path]:
    artifact_ref = state.artifacts.get("gate1_readiness_json")
    if not artifact_ref:
        raise EvidenceError("gate1_readiness_missing", "gate1_readiness_json is not pinned in runbook state")
    path = artifact_path(workspace, str(artifact_ref))
    payload = _load_json(path, "gate1_readiness_missing", "gate1_readiness_invalid")
    return payload, path


def load_stage_b_verification_evidence(
    workspace: Path,
    state: RunbookState,
) -> tuple[dict[str, Any], Path]:
    artifact_ref = state.artifacts.get("stage_b_verification_json")
    if not artifact_ref:
        raise EvidenceError("stage_b_verification_required", "stage_b_verification_json is not pinned")
    path = artifact_path(workspace, str(artifact_ref))
    payload = _load_json(path, "stage_b_verification_required", "stage_b_verification_required")
    expected_context = {
        "runbook_day_id": state.runbook_day_id,
        "account_id": state.frozen_context.account_id,
        "data_date": state.frozen_context.data_date,
        "trade_date": state.frozen_context.trade_date,
    }
    if payload.get("schema_version") != "stage_b_verification.v1" or payload.get("runner_result") != "PASS":
        raise EvidenceError("stage_b_verification_required", "Stage B verification is not PASS")
    if any(payload.get(key) != value for key, value in expected_context.items()):
        raise EvidenceError("stage_b_verification_context_mismatch", "Stage B verification context mismatch")
    return payload, path


def load_stage_c_summary_evidence(
    workspace: Path,
    state: RunbookState,
) -> tuple[dict[str, Any], Path]:
    artifact_ref = state.artifacts.get("stage_c_summary_json")
    if not artifact_ref:
        raise EvidenceError("stage_c_summary_required", "stage_c_summary_json is not pinned")
    path = artifact_path(workspace, str(artifact_ref))
    payload = _load_json(path, "stage_c_summary_required", "stage_c_summary_invalid")
    if (
        payload.get("schema_version") != "runbook_stage_summary.v1"
        or payload.get("runner_result") != "PASS"
        or payload.get("stage_id") != "C"
        or payload.get("runbook_day_id") != state.runbook_day_id
    ):
        raise EvidenceError("stage_c_summary_invalid", "Stage C summary is not a PASS summary")
    expected_context = {
        "account_id": state.frozen_context.account_id,
        "data_date": state.frozen_context.data_date,
        "trade_date": state.frozen_context.trade_date,
    }
    if payload.get("frozen_context") != expected_context:
        raise EvidenceError("stage_c_summary_context_mismatch", "Stage C summary context mismatch")
    return payload, path


def validate_no_action_through_gate2(
    workspace: Path,
    state: RunbookState,
) -> dict[str, Any]:
    _, intent, daily_plan_path = load_daily_plan_evidence(workspace, state)
    if intent["action_mode"] != "NO_ACTION":
        return {"action_mode": "EXECUTION"}
    verification, _ = load_stage_b_verification_evidence(workspace, state)
    if (
        verification.get("action_mode") != "NO_ACTION"
        or verification.get("verified_no_action") is not True
        or int(verification.get("committed_row_count") or 0) != 0
        or int(verification.get("failed_count") or 0) != 0
    ):
        raise EvidenceError("no_action_evidence_mismatch", "Stage B no-action verification mismatch")
    validate_stage_b_no_action_evidence(workspace, state, daily_plan_path=daily_plan_path)
    stage_c, _ = load_stage_c_summary_evidence(workspace, state)
    stage_c_raw = stage_c.get("raw_payload")
    if not isinstance(stage_c_raw, dict) or (
        stage_c_raw.get("action_mode") != "NO_ACTION"
        or stage_c_raw.get("verified_no_action") is not True
    ):
        raise EvidenceError("no_action_evidence_mismatch", "Stage C no-action summary mismatch")
    gate2_ref = state.artifacts.get("gate2_readiness_json")
    if not gate2_ref:
        raise EvidenceError("gate2_required", "gate2_readiness_json is not pinned")
    gate2_path = artifact_path(workspace, str(gate2_ref))
    gate2 = _load_json(gate2_path, "gate2_required", "no_action_evidence_mismatch")
    expected_context = {
        "account_id": state.frozen_context.account_id,
        "data_date": state.frozen_context.data_date,
        "trade_date": state.frozen_context.trade_date,
    }
    if (
        gate2.get("schema_version") != "gate2_review_readiness.v1"
        or gate2.get("runner_result") != "PASS"
        or gate2.get("action_mode") != "NO_ACTION"
        or gate2.get("review_required") is not False
        or gate2.get("manual_review_row_count") != 0
        or gate2.get("frozen_context") != expected_context
    ):
        raise EvidenceError("no_action_evidence_mismatch", "Gate 2 no-action evidence mismatch")
    template_ref = state.artifacts.get("manual_review_template_csv")
    if not template_ref:
        raise EvidenceError("manual_review_template_required", "manual_review_template_csv is not pinned")
    template_path = artifact_path(workspace, str(template_ref))
    try:
        rows = load_paper_manual_review_log_rows(template_path, allowed_root=Path(workspace))
    except (FileNotFoundError, ValueError) as exc:
        raise EvidenceError("no_action_evidence_mismatch", str(exc)) from exc
    if rows:
        raise EvidenceError("no_action_evidence_mismatch", "Manual Review template contains data rows")
    return {
        "action_mode": "NO_ACTION",
        "verified_no_action": True,
        "daily_plan_sha256": sha256_file(daily_plan_path),
        "stage_b_verification_json": str(state.artifacts.get("stage_b_verification_json")),
        "stage_c_summary_json": str(state.artifacts.get("stage_c_summary_json")),
        "gate2_readiness_json": str(gate2_ref),
        "manual_review_template_csv": str(template_ref),
    }


def write_stage_d_no_action_evidence(
    workspace: Path,
    state: RunbookState,
    *,
    schema_version: str,
    payload: dict[str, Any],
) -> tuple[Path, Path]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")
    directory = Path(workspace) / "no_action_runs" / _safe_part(state.runbook_day_id)
    suffix = "stage_d_no_action_preview" if schema_version == "stage_d_no_action_preview.v1" else "stage_d_no_action"
    json_path = directory / f"{stamp}_{suffix}.json"
    md_path = directory / f"{stamp}_{suffix}.md"
    body = {
        "schema_version": schema_version,
        "runner_result": "PASS",
        "runbook_day_id": state.runbook_day_id,
        "account_id": state.frozen_context.account_id,
        "data_date": state.frozen_context.data_date,
        "trade_date": state.frozen_context.trade_date,
        **payload,
    }
    directory.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_format_stage_d_no_action_markdown(body), encoding="utf-8")
    (directory / f"latest_{suffix}.json").write_text(
        json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (directory / f"latest_{suffix}.md").write_text(_format_stage_d_no_action_markdown(body), encoding="utf-8")
    return json_path, md_path


def load_stage_d_no_action_preview(workspace: Path, state: RunbookState) -> tuple[dict[str, Any], Path]:
    ref = state.artifacts.get("stage_d_no_action_preview_json")
    if not ref:
        raise EvidenceError("stage_d_no_action_preview_required", "preview evidence is not pinned")
    path = artifact_path(workspace, str(ref))
    payload = _load_json(path, "stage_d_no_action_preview_required", "stage_d_no_action_preview_invalid")
    expected = {
        "schema_version": "stage_d_no_action_preview.v1",
        "runner_result": "PASS",
        "runbook_day_id": state.runbook_day_id,
        "account_id": state.frozen_context.account_id,
        "data_date": state.frozen_context.data_date,
        "trade_date": state.frozen_context.trade_date,
        "action_mode": "NO_ACTION",
        "verified_no_action": True,
        "candidate_count": 0,
        "review_preview_executed": False,
        "review_log_write_performed": False,
        "notion_write_performed": False,
    }
    if any(payload.get(key) != value for key, value in expected.items()):
        raise EvidenceError("no_action_evidence_mismatch", "Stage D preview evidence mismatch")
    return payload, path


def load_stage_d_no_action_evidence(
    workspace: Path,
    state: RunbookState,
    *,
    daily_plan_sha256: str,
) -> tuple[dict[str, Any], Path]:
    ref = state.artifacts.get("stage_d_no_action_json")
    if not ref:
        raise EvidenceError("stage_d_no_action_evidence_required", "Stage D no-action evidence is not pinned")
    path = artifact_path(workspace, str(ref))
    payload = _load_json(path, "stage_d_no_action_evidence_required", "stage_d_no_action_evidence_invalid")
    expected = {
        "schema_version": "stage_d_no_action.v1",
        "runner_result": "PASS",
        "runbook_day_id": state.runbook_day_id,
        "account_id": state.frozen_context.account_id,
        "data_date": state.frozen_context.data_date,
        "trade_date": state.frozen_context.trade_date,
        "action_mode": "NO_ACTION",
        "verified_no_action": True,
        "candidate_count": 0,
        "appended_count": 0,
        "updated_count": 0,
        "failed_count": 0,
        "review_preview_executed": False,
        "review_append_executed": False,
        "review_sync_executed": False,
        "review_log_write_performed": False,
        "notion_write_performed": False,
        "idempotency_created": False,
    }
    if any(payload.get(key) != value for key, value in expected.items()):
        raise EvidenceError("no_action_evidence_mismatch", "Stage D no-action evidence mismatch")
    if str(payload.get("daily_plan_sha256") or "") != daily_plan_sha256:
        raise EvidenceError("no_action_evidence_mismatch", "Stage D Daily Plan SHA-256 mismatch")
    preview_ref = state.artifacts.get("stage_d_no_action_preview_json")
    if not preview_ref or payload.get("stage_d_no_action_preview_json") != str(preview_ref):
        raise EvidenceError("no_action_evidence_mismatch", "Stage D preview evidence reference mismatch")
    return payload, path


def validate_stage_b_no_action_evidence(
    workspace: Path,
    state: RunbookState,
    *,
    daily_plan_path: Path,
) -> tuple[dict[str, Any], Path]:
    artifact_ref = state.artifacts.get("stage_b_no_action_json")
    if not artifact_ref:
        raise EvidenceError(
            "stage_b_no_action_evidence_required",
            "stage_b_no_action_json is not pinned in runbook state",
        )
    path = artifact_path(workspace, str(artifact_ref))
    payload = _load_json(
        path,
        "stage_b_no_action_evidence_required",
        "no_action_evidence_context_mismatch",
    )
    expected = {
        "schema_version": NO_ACTION_SCHEMA_VERSION,
        "runner_result": "PASS",
        "runbook_day_id": state.runbook_day_id,
        "account_id": state.frozen_context.account_id,
        "data_date": state.frozen_context.data_date,
        "trade_date": state.frozen_context.trade_date,
        "action_mode": "NO_ACTION",
        "execution_required": False,
        "candidate_execution_count": 0,
        "manual_execution_row_count": 0,
        "daily_plan_json": str(state.artifacts.get("daily_plan_json")),
        "gate1_readiness_json": str(state.artifacts.get("gate1_readiness_json")),
        "skipped_command_keys": list(SKIPPED_COMMAND_KEYS),
        "ledger_write_performed": False,
        "notion_write_performed": False,
        "idempotency_record_created": False,
    }
    mismatches = [key for key, value in expected.items() if payload.get(key) != value]
    if mismatches:
        raise EvidenceError(
            "no_action_evidence_context_mismatch",
            f"mismatched fields: {', '.join(mismatches)}",
        )
    if str(payload.get("daily_plan_sha256") or "") != sha256_file(daily_plan_path):
        raise EvidenceError("daily_plan_hash_mismatch", "daily plan SHA-256 does not match no-action evidence")
    return payload, path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_stage_b_no_action_evidence(
    workspace: Path,
    state: RunbookState,
    *,
    daily_plan_path: Path,
    gate1_path: Path,
) -> tuple[dict[str, Any], Path, Path]:
    paths = get_stage_b_no_action_paths(workspace, state.runbook_day_id)
    payload = {
        "schema_version": NO_ACTION_SCHEMA_VERSION,
        "runner_result": "PASS",
        "runbook_day_id": state.runbook_day_id,
        "account_id": state.frozen_context.account_id,
        "data_date": state.frozen_context.data_date,
        "trade_date": state.frozen_context.trade_date,
        "action_mode": "NO_ACTION",
        "execution_required": False,
        "candidate_execution_count": 0,
        "manual_execution_row_count": 0,
        "daily_plan_json": str(state.artifacts.get("daily_plan_json")),
        "daily_plan_sha256": sha256_file(daily_plan_path),
        "gate1_readiness_json": str(state.artifacts.get("gate1_readiness_json")),
        "skipped_command_keys": list(SKIPPED_COMMAND_KEYS),
        "ledger_write_performed": False,
        "notion_write_performed": False,
        "idempotency_record_created": False,
    }
    json_text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    markdown = _format_no_action_markdown(payload)
    paths["json"].parent.mkdir(parents=True, exist_ok=True)
    paths["json"].write_text(json_text, encoding="utf-8")
    paths["md"].write_text(markdown, encoding="utf-8")
    paths["latest_json"].write_text(json_text, encoding="utf-8")
    paths["latest_md"].write_text(markdown, encoding="utf-8")
    return payload, paths["json"], paths["md"]


def get_stage_b_no_action_paths(
    workspace: Path,
    runbook_day_id: str,
    timestamp: str | None = None,
) -> dict[str, Path]:
    stamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S%f")
    directory = Path(workspace) / "no_action_runs" / _safe_part(runbook_day_id)
    return {
        "json": directory / f"{stamp}_stage_b_no_action.json",
        "md": directory / f"{stamp}_stage_b_no_action.md",
        "latest_json": directory / "latest_stage_b_no_action.json",
        "latest_md": directory / "latest_stage_b_no_action.md",
    }


def _load_json(path: Path, missing_reason: str, invalid_reason: str) -> dict[str, Any]:
    if not path.is_file():
        raise EvidenceError(missing_reason, f"evidence file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(invalid_reason, str(exc)) from exc
    if not isinstance(payload, dict):
        raise EvidenceError(invalid_reason, "evidence root must be an object")
    return payload


def _safe_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value).strip())
    return cleaned.strip("_") or "unknown"


def _format_no_action_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Stage B No-Action Evidence",
            "",
            f"- runner_result: {payload['runner_result']}",
            f"- runbook_day_id: {payload['runbook_day_id']}",
            f"- action_mode: {payload['action_mode']}",
            f"- candidate_execution_count: {payload['candidate_execution_count']}",
            f"- manual_execution_row_count: {payload['manual_execution_row_count']}",
            f"- daily_plan_sha256: {payload['daily_plan_sha256']}",
            "- ledger_write_performed: false",
            "- notion_write_performed: false",
            "- idempotency_record_created: false",
            "",
        ]
    )


def _format_stage_d_no_action_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {payload['schema_version']}",
            "",
            f"- runner_result: {payload['runner_result']}",
            f"- runbook_day_id: {payload['runbook_day_id']}",
            f"- action_mode: {payload['action_mode']}",
            f"- candidate_count: {payload['candidate_count']}",
            f"- review_preview_executed: {str(payload['review_preview_executed']).lower()}",
            f"- notion_write_performed: {str(payload['notion_write_performed']).lower()}",
            "",
        ]
    )

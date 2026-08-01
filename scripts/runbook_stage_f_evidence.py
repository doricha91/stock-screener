from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts import runbook_result
from scripts.runbook_state import RunbookState


STAGE_F_EVIDENCE_ARTIFACTS = (
    "benchmark_report_json",
    "account_snapshot_notion_report_json",
    "benchmark_notion_report_json",
)


def _payload_validation(
    runner_result: str,
    message: str,
    artifact_refs: dict[str, str],
    blockers: list[str],
) -> dict[str, Any]:
    return {
        "runner_result": runner_result,
        "message": message,
        "artifact_refs": artifact_refs,
        "warnings": [],
        "blockers": blockers,
    }


def _int_payload(payload: dict[str, Any], field: str) -> int:
    try:
        return int(payload.get(field) or 0)
    except (TypeError, ValueError):
        return 0


def path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
    except ValueError:
        return False
    return True


def resolve_workspace_artifact(workspace: Path, artifact_ref: object) -> tuple[Path | None, str | None]:
    cleaned = str(artifact_ref or "").strip()
    if not cleaned:
        return None, "artifact_ref_missing"
    candidate = Path(cleaned)
    resolved = candidate.resolve(strict=False) if candidate.is_absolute() else (workspace / candidate).resolve(strict=False)
    if not path_is_within(resolved, workspace):
        return None, "artifact_ref_outside_workspace"
    if not resolved.is_file():
        return None, "artifact_file_missing"
    return resolved, None


def load_workspace_json_artifact(
    workspace: Path,
    artifact_ref: object,
) -> tuple[dict[str, Any] | None, Path | None, str | None]:
    path, error = resolve_workspace_artifact(workspace, artifact_ref)
    if error:
        return None, path, error
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, path, "artifact_json_invalid"
    if not isinstance(payload, dict):
        return None, path, "artifact_json_must_be_object"
    return payload, path, None


def validate_stage_f_benchmark_payload(
    payload: dict[str, Any],
    state: RunbookState,
    account_root: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    if str(payload.get("account_id") or "").strip() != state.frozen_context.account_id:
        blockers.append("benchmark account_id must match frozen context")
    if str(payload.get("latest_snapshot_date") or "").strip() != state.frozen_context.trade_date:
        blockers.append("benchmark latest_snapshot_date must match trade_date")
    json_path = Path(str(payload.get("json_path") or ""))
    markdown_path = Path(str(payload.get("markdown_path") or ""))
    reports_root = (account_root / "reports").resolve(strict=False)
    for label, path in (("benchmark json_path", json_path), ("benchmark markdown_path", markdown_path)):
        if not str(path) or str(path) == "." or not path.is_file():
            blockers.append(f"{label} must exist")
        elif not path_is_within(path, reports_root):
            blockers.append(f"{label} must be under the account reports root")
    if json_path.is_file():
        try:
            report_payload = json.loads(json_path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            blockers.append("benchmark JSON must be valid")
        else:
            if str(report_payload.get("account_id") or "").strip() != state.frozen_context.account_id:
                blockers.append("benchmark JSON account_id must match frozen context")
            if str(report_payload.get("latest_snapshot_date") or "").strip() != state.frozen_context.trade_date:
                blockers.append("benchmark JSON latest_snapshot_date must match trade_date")
    artifacts = {
        "benchmark_report_json": str(json_path),
        "benchmark_report_md": str(markdown_path),
    }
    return _payload_validation(
        "BLOCKED" if blockers else "PASS",
        "Benchmark artifacts are account/date scoped and pinned." if not blockers else "Benchmark result failed validation.",
        artifacts if not blockers else {},
        blockers,
    )


def validate_stage_f_export_payload(
    payload: dict[str, Any],
    state: RunbookState,
    account_root: Path,
    *,
    expected_source: Path,
    label: str,
) -> dict[str, Any]:
    blockers: list[str] = []
    rows = payload.get("json")
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        return _payload_validation("FAILED", f"{label} exporter returned invalid JSON.", {}, ["one export result is required"])
    item = rows[0]
    if str(item.get("account_id") or "").strip() != state.frozen_context.account_id:
        blockers.append("export account_id must match frozen context")
    if _int_payload(item, "failed_count") != 0:
        blockers.append("failed_count must be 0")
    if str(item.get("action") or "").strip().lower() not in {"created", "updated", "skipped"}:
        blockers.append("action must be created/updated/skipped")
    if not str(item.get("external_key") or "").strip():
        blockers.append("external_key is required")
    source_path = Path(str(item.get("source_path") or ""))
    if not source_path.is_file():
        blockers.append("source_path must exist")
    else:
        if source_path.resolve(strict=False) != expected_source.resolve(strict=False):
            blockers.append("source_path must match the frozen account source")
        if not path_is_within(source_path, account_root.resolve(strict=False)):
            blockers.append("source_path must be under the frozen account root")
    return _payload_validation(
        "BLOCKED" if blockers else "PASS",
        f"{label} Notion upsert is validated." if not blockers else f"{label} Notion upsert failed validation.",
        {},
        blockers,
    )


def _validate_benchmark_artifact(
    workspace: Path,
    state: RunbookState,
    artifact_ref: object,
) -> list[str]:
    payload, _, error = load_workspace_json_artifact(workspace, artifact_ref)
    if error:
        return [f"benchmark_report_json:{error}"]
    blockers: list[str] = []
    if str(payload.get("account_id") or "").strip() != state.frozen_context.account_id:
        blockers.append("benchmark_report_json:account_id_mismatch")
    if str(payload.get("latest_snapshot_date") or "").strip() != state.frozen_context.trade_date:
        blockers.append("benchmark_report_json:latest_snapshot_date_mismatch")
    return blockers


def _validate_notion_command_evidence(
    workspace: Path,
    state: RunbookState,
    account_root: Path,
    artifact_name: str,
    command_key: str,
    step_id: int,
    expected_source: Path,
    label: str,
) -> list[str]:
    payload, _, error = load_workspace_json_artifact(workspace, state.artifacts.get(artifact_name))
    if error:
        return [f"{artifact_name}:{error}"]
    blockers = [f"{artifact_name}:schema:{item}" for item in runbook_result.validate_command_result(payload)]
    expected_context = {
        "account_id": state.frozen_context.account_id,
        "data_date": state.frozen_context.data_date,
        "trade_date": state.frozen_context.trade_date,
    }
    if payload.get("runner_result") != "PASS":
        blockers.append(f"{artifact_name}:runner_result_not_pass")
    if payload.get("runbook_day_id") != state.runbook_day_id:
        blockers.append(f"{artifact_name}:runbook_day_id_mismatch")
    if payload.get("frozen_context") != expected_context:
        blockers.append(f"{artifact_name}:frozen_context_mismatch")
    if payload.get("stage_id") != "F":
        blockers.append(f"{artifact_name}:stage_id_mismatch")
    if payload.get("step_id") != step_id:
        blockers.append(f"{artifact_name}:step_id_mismatch")
    if payload.get("command_key") != command_key:
        blockers.append(f"{artifact_name}:command_key_mismatch")
    raw_payload = payload.get("raw_payload")
    if isinstance(raw_payload, dict):
        validation = validate_stage_f_export_payload(
            raw_payload,
            state,
            account_root,
            expected_source=expected_source,
            label=label,
        )
        blockers.extend(f"{artifact_name}:payload:{item}" for item in validation["blockers"])
    else:
        blockers.append(f"{artifact_name}:raw_payload_invalid")
    return blockers


def validate_stage_f_completion_evidence(
    workspace: Path,
    state: RunbookState,
    account_root: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    expected_state = {
        "E": state.stage_status.get("E") == "PASS",
        "F": state.stage_status.get("F") == "PASS",
        "current_stage": state.current_stage == "F",
        "current_status": state.current_status == "PASS",
        "last_completed_step": state.last_completed_step == 21,
        "last_completed_stage": state.last_completed_stage == "F",
        "last_error": state.last_error is None,
    }
    blockers.extend(f"state:{field}_invalid" for field, valid in expected_state.items() if not valid)
    blockers.extend(
        _validate_benchmark_artifact(workspace, state, state.artifacts.get("benchmark_report_json"))
    )
    blockers.extend(
        _validate_notion_command_evidence(
            workspace,
            state,
            account_root,
            "account_snapshot_notion_report_json",
            "account_snapshot_notion_upsert",
            20,
            account_root / "paper_account_snapshot.csv",
            "Account Snapshot",
        )
    )
    blockers.extend(
        _validate_notion_command_evidence(
            workspace,
            state,
            account_root,
            "benchmark_notion_report_json",
            "benchmark_report_notion_upsert",
            21,
            account_root / "reports" / "paper_benchmark_comparison.json",
            "Benchmark Report",
        )
    )
    return {"valid": not blockers, "blockers": blockers}

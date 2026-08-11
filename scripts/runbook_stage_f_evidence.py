from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.notion_account_keys import (
    build_account_snapshot_external_key,
    build_benchmark_report_external_key,
)
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


def _strict_zero_count(payload: dict[str, Any], field: str) -> list[str]:
    if field not in payload:
        return [f"{field}_missing"]
    value = payload[field]
    if isinstance(value, bool) or not isinstance(value, int):
        return [f"{field}_type_invalid"]
    if value != 0:
        return [f"{field}_not_zero"]
    return []


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
            if not isinstance(report_payload, dict):
                blockers.append("benchmark JSON must be an object")
            else:
                if str(report_payload.get("account_id") or "").strip() != state.frozen_context.account_id:
                    blockers.append("benchmark JSON account_id must match frozen context")
                if str(report_payload.get("latest_snapshot_date") or "").strip() != state.frozen_context.trade_date:
                    blockers.append("benchmark JSON latest_snapshot_date must match trade_date")
                if "run_mode" not in report_payload:
                    blockers.append("benchmark JSON run_mode is required")
                elif not isinstance(report_payload["run_mode"], str) or not report_payload["run_mode"].strip():
                    blockers.append("benchmark JSON run_mode must be a non-empty string")
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
    frozen_benchmark_payload: dict[str, Any] | None = None,
    read_current_benchmark_source: bool = True,
) -> dict[str, Any]:
    blockers: list[str] = []
    rows = payload.get("json")
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        return _payload_validation("FAILED", f"{label} exporter returned invalid JSON.", {}, ["one export result is required"])
    item = rows[0]
    if str(item.get("account_id") or "").strip() != state.frozen_context.account_id:
        blockers.append("export account_id must match frozen context")
    blockers.extend(_strict_zero_count(item, "failed_count"))
    if str(item.get("action") or "").strip().lower() not in {"created", "updated", "skipped"}:
        blockers.append("action must be created/updated/skipped")
    source_ref = str(item.get("source_path") or "").strip()
    source_path = Path(source_ref)
    source_valid = True
    historical_benchmark = label == "Benchmark Report" and not read_current_benchmark_source
    if not source_ref or (not historical_benchmark and not source_path.is_file()):
        blockers.append("source_path must exist")
        source_valid = False
    else:
        if source_path.resolve(strict=False) != expected_source.resolve(strict=False):
            blockers.append("source_path must match the frozen account source")
            source_valid = False
        if not path_is_within(source_path, account_root.resolve(strict=False)):
            blockers.append("source_path must be under the frozen account root")
            source_valid = False

    expected_external_key: str | None = None
    if label == "Account Snapshot":
        expected_external_key = build_account_snapshot_external_key(
            state.frozen_context.account_id,
            state.frozen_context.trade_date,
        )
    elif label == "Benchmark Report" and source_valid:
        benchmark_source = frozen_benchmark_payload
        if read_current_benchmark_source:
            try:
                benchmark_source = json.loads(source_path.read_text(encoding="utf-8-sig"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                blockers.append("benchmark_source_json_invalid")
        if benchmark_source is not None:
            if not isinstance(benchmark_source, dict):
                blockers.append("benchmark_source_json_must_be_object")
            else:
                if str(benchmark_source.get("account_id") or "").strip() != state.frozen_context.account_id:
                    blockers.append("benchmark_source_account_id_mismatch")
                if str(benchmark_source.get("latest_snapshot_date") or "").strip() != state.frozen_context.trade_date:
                    blockers.append("benchmark_source_latest_snapshot_date_mismatch")
                if "run_mode" not in benchmark_source:
                    blockers.append("benchmark_source_run_mode_missing")
                elif not isinstance(benchmark_source["run_mode"], str) or not benchmark_source["run_mode"].strip():
                    blockers.append("benchmark_source_run_mode_type_invalid")
                else:
                    expected_external_key = build_benchmark_report_external_key(
                        state.frozen_context.account_id,
                        state.frozen_context.trade_date,
                        benchmark_source["run_mode"],
                    )

    if "external_key" not in item:
        blockers.append("external_key_missing")
    elif not isinstance(item["external_key"], str):
        blockers.append("external_key_type_invalid")
    elif not item["external_key"].strip():
        blockers.append("external_key_missing")
    elif expected_external_key is not None and item["external_key"].strip() != expected_external_key:
        blockers.append("external_key_mismatch")
    return _payload_validation(
        "BLOCKED" if blockers else "PASS",
        f"{label} Notion upsert is validated." if not blockers else f"{label} Notion upsert failed validation.",
        {},
        blockers,
    )


def _load_and_validate_benchmark_artifact(
    workspace: Path,
    state: RunbookState,
    artifact_ref: object,
) -> tuple[dict[str, Any] | None, list[str]]:
    payload, _, error = load_workspace_json_artifact(workspace, artifact_ref)
    if error:
        return None, [f"benchmark_report_json:{error}"]
    blockers: list[str] = []
    if str(payload.get("account_id") or "").strip() != state.frozen_context.account_id:
        blockers.append("benchmark_report_json:account_id_mismatch")
    if str(payload.get("latest_snapshot_date") or "").strip() != state.frozen_context.trade_date:
        blockers.append("benchmark_report_json:latest_snapshot_date_mismatch")
    if "run_mode" not in payload:
        blockers.append("benchmark_report_json:run_mode_missing")
    elif not isinstance(payload["run_mode"], str) or not payload["run_mode"].strip():
        blockers.append("benchmark_report_json:run_mode_type_invalid")
    return payload, blockers


def _validate_notion_command_evidence(
    workspace: Path,
    state: RunbookState,
    account_root: Path,
    artifact_name: str,
    command_key: str,
    step_id: int,
    expected_source: Path,
    label: str,
    frozen_benchmark_payload: dict[str, Any] | None = None,
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
            frozen_benchmark_payload=frozen_benchmark_payload,
            read_current_benchmark_source=False,
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
    from scripts import runbook_stage_e_evidence

    stage_e = runbook_stage_e_evidence.validate_stage_e_completion_evidence(
        workspace, state, account_root
    )
    blockers.extend(f"stage_e:{item}" for item in stage_e["blockers"])
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
    frozen_benchmark_payload, benchmark_blockers = _load_and_validate_benchmark_artifact(
        workspace, state, state.artifacts.get("benchmark_report_json")
    )
    blockers.extend(benchmark_blockers)
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
            frozen_benchmark_payload=frozen_benchmark_payload,
        )
    )
    return {"valid": not blockers, "blockers": blockers}

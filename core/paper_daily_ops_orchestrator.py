from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paper_account_paths import (
    LEGACY_PAPER_DEFAULT_ROOT,
    PAPER_ACCOUNTS_ROOT,
    build_paper_account_paths,
)
from core.paper_account_profile import validate_account_id
from core.paper_daily_ops_evidence import (
    EVIDENCE_DAILY_PLAN_NOTION_EXPORT,
    EVIDENCE_MANUAL_EXECUTION_STATUS_SYNC,
    EVIDENCE_MANUAL_EXECUTION_TEMPLATE,
    EVIDENCE_MANUAL_REVIEW_STATUS_SYNC,
    EVIDENCE_MANUAL_REVIEW_TEMPLATE,
    EvidenceEvaluation,
    evaluate_notion_evidence,
)
from core.paper_daily_ops_notion_status import (
    SKIPPED as NOTION_SKIPPED,
    UNKNOWN as NOTION_UNKNOWN,
    build_notion_live_read_status,
    skipped_notion_live_read_status,
)
from core.paper_daily_ops_operator_summary import build_operator_summary
from core.paper_daily_ops_reconciliation import apply_reconciliation
from core.paper_daily_plan_candidates import CANDIDATE_COUNT_RULE, count_daily_plan_execution_candidates
from core.paper_status import WORKFLOW_REVIEW_DONE, run_paper_status


SCHEMA_VERSION = "mfu_oper9_daily_ops_status.v1"
COMPLETION_MODE_STANDARD = "STANDARD"
COMPLETION_MODE_NO_ACTION = "NO_ACTION"
NO_ACTION_COMPLETION_SCHEMA_VERSION = "runbook_no_action_completion.v1"
STANDARD_COMPLETION_SCHEMA_VERSION = "runbook_standard_completion.v1"
STANDARD_AUTHORITATIVE_STAGES = {
    "DAILY_PLAN_NOTION_EXPORT",
    "MANUAL_EXECUTION_TEMPLATE",
    "MANUAL_REVIEW_TEMPLATE",
}

DONE = "DONE"
READY = "READY"
BLOCKED = "BLOCKED"
WARNING = "WARNING"
UNKNOWN = "UNKNOWN"
NOT_STARTED = "NOT_STARTED"

COMMAND_TYPE_READ_ONLY = "READ_ONLY"
COMMAND_TYPE_NOTION_WRITE = "NOTION_WRITE"
COMMAND_TYPE_LEDGER_WRITE = "LEDGER_WRITE"
COMMAND_TYPE_STATUS_SYNC = "STATUS_SYNC"
COMMAND_TYPE_UNKNOWN = "UNKNOWN"

RISK_SAFE = "SAFE"
RISK_REQUIRES_MANUAL_REVIEW = "REQUIRES_MANUAL_REVIEW"
RISK_DANGEROUS = "DANGEROUS"

RECOMMENDED_ACTION_NONE = "NONE"
RECOMMENDED_ACTION_RUN_NEXT_COMMAND = "RUN_NEXT_COMMAND"
RECOMMENDED_ACTION_REVIEW_WARNINGS = "REVIEW_WARNINGS"
RECOMMENDED_ACTION_RESOLVE_BLOCKERS = "RESOLVE_BLOCKERS"
RECOMMENDED_ACTION_CHECK_NOTION = "CHECK_NOTION"

STAGE_NAMES = [
    "DATA_FRESHNESS",
    "DAILY_PLAN",
    "DAILY_PLAN_NOTION_EXPORT",
    "MANUAL_EXECUTION_TEMPLATE",
    "MANUAL_EXECUTION_PREVIEW",
    "MANUAL_EXECUTION_COMMIT",
    "MANUAL_EXECUTION_STATUS_SYNC",
    "DAILY_REVIEW",
    "MANUAL_REVIEW_TEMPLATE",
    "MANUAL_REVIEW_PREVIEW",
    "MANUAL_REVIEW_APPEND",
    "MANUAL_REVIEW_STATUS_SYNC",
    "FINAL_STATUS",
]


@dataclass(frozen=True)
class OpsEvidencePaths:
    execution_preview_json: Path | None = None
    execution_commit_report: Path | None = None
    review_preview_json: Path | None = None
    review_commit_report: Path | None = None


def build_daily_ops_status(
    *,
    account_id: str,
    data_date: str,
    trade_date: str,
    account_root: Path | None = None,
    legacy_root: Path | None = None,
    evidence_paths: OpsEvidencePaths | None = None,
    include_notion_read: bool = False,
    notion_timeout_seconds: int = 30,
    notion_status_report: dict[str, Any] | None = None,
    completion_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    normalized_account_id = _validate_required_account_id(account_id)
    normalized_data_date = _normalize_date(data_date, "data_date")
    normalized_trade_date = _normalize_date(trade_date, "trade_date")
    data_dt = datetime.strptime(normalized_data_date, "%Y-%m-%d").date()
    trade_dt = datetime.strptime(normalized_trade_date, "%Y-%m-%d").date()
    validated_completion = _validate_completion_context(
        completion_context,
        account_id=normalized_account_id,
        data_date=normalized_data_date,
        trade_date=normalized_trade_date,
    )
    no_action_completion = (
        validated_completion
        if validated_completion and validated_completion.get("action_mode") == "NO_ACTION"
        else None
    )
    standard_completion = (
        validated_completion
        if validated_completion and validated_completion.get("action_mode") == "STANDARD"
        else None
    )
    if trade_dt <= data_dt:
        blockers.append(f"trade_date {normalized_trade_date} must be after data_date {normalized_data_date}.")

    resolved = _resolve_roots(
        account_id=normalized_account_id,
        account_root=account_root,
        legacy_root=legacy_root,
    )
    root = resolved["account_root"]
    legacy = resolved["legacy_root"]
    legacy_default_used = resolved["legacy_default_used"]
    if legacy_default_used:
        warnings.append("paper_default is using legacy outputs/paper_test fallback.")

    artifacts = _artifact_paths(root, normalized_trade_date)
    legacy_artifacts = _artifact_paths(legacy, normalized_trade_date)
    legacy_matches = _existing_legacy_matches(
        account_id=normalized_account_id,
        artifacts=artifacts,
        legacy_artifacts=legacy_artifacts,
    )
    if legacy_matches:
        warnings.append(
            "Legacy paper_test artifacts exist for the requested trade_date but are not used as non-default account evidence."
        )

    evidence = evidence_paths or OpsEvidencePaths()
    if evidence.execution_preview_json is not None:
        artifacts["execution_preview_json"] = Path(evidence.execution_preview_json)
    if evidence.execution_commit_report is not None:
        artifacts["execution_commit_json"] = Path(evidence.execution_commit_report)
    if evidence.review_preview_json is not None:
        artifacts["review_preview_json"] = Path(evidence.review_preview_json)
    if evidence.review_commit_report is not None:
        artifacts["review_commit_json"] = Path(evidence.review_commit_report)

    stage_context = {
        "account_id": normalized_account_id,
        "data_date": normalized_data_date,
        "trade_date": normalized_trade_date,
        "root": root,
        "legacy_root": legacy,
        "legacy_matches": legacy_matches,
        "artifacts": artifacts,
        "legacy_artifacts": legacy_artifacts,
        "global_blockers": blockers,
    }
    notion_report = _build_notion_report(
        include_notion_read=include_notion_read,
        notion_timeout_seconds=notion_timeout_seconds,
        notion_status_report=notion_status_report,
        account_id=normalized_account_id,
        data_date=normalized_data_date,
        trade_date=normalized_trade_date,
    )
    stages = [
        _stage_data_freshness(stage_context),
        _stage_daily_plan(stage_context),
        _stage_daily_plan_notion_export(stage_context),
        _stage_manual_execution_template(stage_context),
        _stage_manual_execution_preview(stage_context),
        _stage_manual_execution_commit(stage_context),
        _stage_manual_execution_status_sync(stage_context),
        _stage_daily_review(stage_context),
        _stage_manual_review_template(stage_context),
        _stage_manual_review_preview(stage_context),
        _stage_manual_review_append(stage_context),
        _stage_manual_review_status_sync(stage_context),
        _stage_final_status(stage_context),
    ]
    zero_review_standard_completion = bool(
        standard_completion
        and isinstance(standard_completion.get("zero_review_evidence"), dict)
        and standard_completion["zero_review_evidence"].get("verified_zero_review") is True
    )
    workflow_status = (
        WORKFLOW_REVIEW_DONE
        if zero_review_standard_completion
        else _safe_workflow_status(root, normalized_trade_date)
    )
    _apply_notion_report(stages, notion_report)
    reconciliation_summary = apply_reconciliation(stages, workflow_status=workflow_status)
    _suppress_manual_execution_no_candidate_skips_when_notion_rows_exist(stages)
    _ensure_ready_stage_commands(stages, stage_context)
    completion_mode = COMPLETION_MODE_NO_ACTION if no_action_completion else COMPLETION_MODE_STANDARD
    if no_action_completion:
        _apply_verified_no_action_completion(stages)
    elif standard_completion:
        _apply_verified_standard_completion(stages)
        if zero_review_standard_completion:
            _apply_verified_standard_zero_review_completion(stages)
    terminal = _is_terminal_workflow(workflow_status, stages, completion_mode=completion_mode)
    if terminal:
        for stage in stages:
            stage["next_command"] = None
            stage["next_action"] = None

    overall_status = _derive_overall_status(blockers, warnings, stages)
    next_command = _first_next_command(stages, workflow_status=workflow_status)
    if terminal:
        next_command = None
    stage_counts = _stage_counts(stages)
    summary = _summary(
        workflow_status=workflow_status,
        terminal=terminal,
        blockers=blockers,
        warnings=warnings,
        stages=stages,
        next_command=next_command,
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "account_id": normalized_account_id,
        "account_root": _path_str(root),
        "data_date": normalized_data_date,
        "trade_date": normalized_trade_date,
        "overall_status": overall_status,
        "workflow_status": workflow_status,
        "completion_mode": completion_mode,
        "completion_proof": no_action_completion,
        "runbook_completion_evidence": standard_completion,
        "read_only": True,
        "write_executed": False,
        "operation_write_executed": False,
        "notion_api_called": False,
        "notion_live_read_enabled": bool(include_notion_read),
        "notion_live_read_called": bool(notion_report.get("called")),
        "notion_live_read_status": str(notion_report.get("status") or NOTION_SKIPPED),
        "notion_live_read_errors": list(notion_report.get("errors") or []),
        "notion_live_read_summary": dict(notion_report.get("summary") or {}),
        "commit_append_executed": False,
        "status_report_written": False,
        "status_report_path": None,
        "legacy_default_used": legacy_default_used,
        "paper_test_artifacts_detected": bool(legacy_matches),
        "guards": {
            "account_id_required": True,
            "data_date_required": True,
            "trade_date_required": True,
            "trade_date_after_data_date": trade_dt > data_dt,
            "paper_test_fallback_detected": bool(legacy_matches) or legacy_default_used,
            "write_actions_enabled": False,
        },
        "blockers": blockers,
        "warnings": warnings,
        "next_command": next_command,
        "next_action": _next_action(next_command),
        "summary": summary,
        "stage_counts": stage_counts,
        "reconciliation_summary": reconciliation_summary,
        "stages": stages,
    }
    payload["operator_summary"] = build_operator_summary(payload)
    return payload


def _validate_completion_context(
    context: dict[str, Any] | None,
    *,
    account_id: str,
    data_date: str,
    trade_date: str,
) -> dict[str, Any] | None:
    if context is None:
        return None
    if not isinstance(context, dict):
        raise ValueError("completion_context_must_be_object")
    action_mode = context.get("action_mode")
    if action_mode == "STANDARD":
        return _validate_standard_completion_context(
            context,
            account_id=account_id,
            data_date=data_date,
            trade_date=trade_date,
        )
    if action_mode != "NO_ACTION":
        raise ValueError("completion_context_action_mode_invalid")
    return _validate_no_action_completion_context(
        context,
        account_id=account_id,
        data_date=data_date,
        trade_date=trade_date,
    )


def _validate_no_action_completion_context(
    context: dict[str, Any],
    *,
    account_id: str,
    data_date: str,
    trade_date: str,
) -> dict[str, Any]:
    expected = {
        "schema_version": NO_ACTION_COMPLETION_SCHEMA_VERSION,
        "account_id": account_id,
        "data_date": data_date,
        "trade_date": trade_date,
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
    }
    mismatches = [field for field, expected_value in expected.items() if context.get(field) != expected_value]
    if mismatches:
        raise ValueError(f"no_action_completion_context_mismatch:{','.join(mismatches)}")
    strict_bool_fields = (
        "verified_no_action",
        "execution_required",
        "review_required",
        "required_status_sync",
        "execution_write_performed",
        "review_write_performed",
        "eod_close_verified",
    )
    if any(not isinstance(context.get(field), bool) for field in strict_bool_fields):
        raise ValueError("no_action_completion_boolean_type_invalid")
    for field in ("candidate_execution_count", "manual_review_row_count"):
        value = context.get(field)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"no_action_completion_{field}_type_invalid")
    for field in ("runbook_day_id", "daily_plan_sha256", "stage_d_no_action_json", "eod_commit_report_json"):
        value = context.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"no_action_completion_{field}_required")
    return dict(context)


def _validate_standard_completion_context(
    context: dict[str, Any],
    *,
    account_id: str,
    data_date: str,
    trade_date: str,
) -> dict[str, Any]:
    expected = {
        "schema_version": STANDARD_COMPLETION_SCHEMA_VERSION,
        "runbook_day_id": f"{account_id}_{data_date}_{trade_date}",
        "account_id": account_id,
        "data_date": data_date,
        "trade_date": trade_date,
        "action_mode": "STANDARD",
    }
    mismatches = [field for field, expected_value in expected.items() if context.get(field) != expected_value]
    if mismatches:
        raise ValueError(f"standard_completion_context_mismatch:{','.join(mismatches)}")
    stages = context.get("authoritative_stages")
    if not isinstance(stages, dict) or set(stages) != STANDARD_AUTHORITATIVE_STAGES:
        raise ValueError("standard_completion_authoritative_stages_mismatch")
    for stage_name, evidence in stages.items():
        if not isinstance(evidence, dict):
            raise ValueError(f"standard_completion_evidence_invalid:{stage_name}")
        for field in ("stage_id", "command_key", "summary_ref", "result_ref"):
            if not isinstance(evidence.get(field), str) or not evidence[field].strip():
                raise ValueError(f"standard_completion_evidence_invalid:{stage_name}:{field}")
        if isinstance(evidence.get("step_id"), bool) or not isinstance(evidence.get("step_id"), int):
            raise ValueError(f"standard_completion_evidence_invalid:{stage_name}:step_id")
        for field in ("summary_sha256", "result_sha256"):
            value = evidence.get(field)
            if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
                raise ValueError(f"standard_completion_evidence_invalid:{stage_name}:{field}")
    zero_review = context.get("zero_review_evidence")
    if zero_review is not None:
        if not isinstance(zero_review, dict):
            raise ValueError("standard_completion_zero_review_evidence_invalid")
        if zero_review.get("required_review_count") != 0 or zero_review.get(
            "verified_zero_review"
        ) is not True:
            raise ValueError("standard_completion_zero_review_evidence_invalid")
        for field in (
            "manual_review_scope_ref",
            "stage_b_verification_ref",
            "stage_c_summary_ref",
            "gate2_ref",
            "stage_d_summary_ref",
        ):
            if not isinstance(zero_review.get(field), str) or not zero_review[field].strip():
                raise ValueError(f"standard_completion_zero_review_evidence_invalid:{field}")
        for field in (
            "manual_review_scope_sha256",
            "stage_b_verification_sha256",
            "stage_c_summary_sha256",
            "gate2_sha256",
            "stage_d_summary_sha256",
        ):
            value = zero_review.get(field)
            if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
                raise ValueError(f"standard_completion_zero_review_evidence_invalid:{field}")
        artifacts = zero_review.get("artifacts")
        if not isinstance(artifacts, dict) or set(artifacts) != {
            "review_preview",
            "review_append",
            "review_status_sync",
        }:
            raise ValueError("standard_completion_zero_review_evidence_invalid:artifacts")
        for name, artifact in artifacts.items():
            if not isinstance(artifact, dict) or not isinstance(artifact.get("ref"), str):
                raise ValueError(f"standard_completion_zero_review_evidence_invalid:{name}")
            digest = artifact.get("sha256")
            if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
                raise ValueError(f"standard_completion_zero_review_evidence_invalid:{name}")
    return dict(context)


def _apply_verified_no_action_completion(stages: list[dict[str, Any]]) -> None:
    for stage in stages:
        stage["status"] = DONE
        stage["blockers"] = []
        stage["warnings"] = []
        stage["next_command"] = None
        stage["next_action"] = None
        stage["note"] = "Verified runbook NO_ACTION completion requires no further local operator action."


def _apply_verified_standard_completion(stages: list[dict[str, Any]]) -> None:
    for stage in stages:
        if stage.get("stage_name") not in STANDARD_AUTHORITATIVE_STAGES:
            continue
        stage["status"] = DONE
        stage["blockers"] = []
        stage["warnings"] = []
        stage["next_command"] = None
        stage["next_action"] = None
        stage["note"] = "Verified official runbook command evidence supersedes the legacy diagnostic sidecar."


def _apply_verified_standard_zero_review_completion(stages: list[dict[str, Any]]) -> None:
    completed = {
        "DAILY_REVIEW",
        "MANUAL_REVIEW_TEMPLATE",
        "MANUAL_REVIEW_PREVIEW",
        "MANUAL_REVIEW_APPEND",
        "MANUAL_REVIEW_STATUS_SYNC",
        "FINAL_STATUS",
    }
    for stage in stages:
        if stage.get("stage_name") not in completed:
            continue
        stage["status"] = DONE
        stage["blockers"] = []
        stage["warnings"] = []
        stage["next_command"] = None
        stage["next_action"] = None
        stage["note"] = "Verified zero-required-review STANDARD runbook evidence is complete."


def _validate_required_account_id(account_id: str) -> str:
    value = str(account_id or "").strip()
    if not value:
        raise ValueError("account_id is required.")
    return validate_account_id(value)


def _normalize_date(value: str, label: str) -> str:
    clean = str(value or "").replace("-", "").strip()
    if len(clean) != 8 or not clean.isdigit():
        raise ValueError(f"{label} is required in YYYYMMDD or YYYY-MM-DD format.")
    return datetime.strptime(clean, "%Y%m%d").strftime("%Y-%m-%d")


def _resolve_roots(*, account_id: str, account_root: Path | None, legacy_root: Path | None) -> dict[str, Any]:
    legacy = Path(legacy_root) if legacy_root is not None else LEGACY_PAPER_DEFAULT_ROOT
    if account_root is not None:
        root = Path(account_root)
        legacy_default_used = account_id == "paper_default" and root == legacy
    elif account_id == "paper_default":
        paths = build_paper_account_paths(account_id, create=False)
        root = paths.root
        legacy_default_used = paths.legacy_default_used
    else:
        root = PAPER_ACCOUNTS_ROOT / account_id
        legacy_default_used = False
    return {"account_root": root, "legacy_root": legacy, "legacy_default_used": legacy_default_used}


def _artifact_paths(root: Path, trade_date: str) -> dict[str, Path]:
    compact = trade_date.replace("-", "")
    return {
        "daily_plan_md": root / f"daily_action_plan_{compact}.md",
        "daily_plan_json": root / f"daily_action_plan_{compact}.json",
        "config_snapshot": root / "config_snapshots" / f"paper_config_snapshot_{compact}.json",
        "execution_preview_json": root / "reports" / f"manual_execution_import_preview_{compact}.json",
        "execution_preview_md": root / "reports" / f"manual_execution_import_preview_{compact}.md",
        "execution_commit_json": root / "reports" / f"manual_execution_import_commit_{compact}.json",
        "execution_commit_md": root / "reports" / f"manual_execution_import_commit_{compact}.md",
        "execution_log": root / "paper_execution_log.csv",
        "current_state": root / f"paper_current_state_{compact}.json",
        "account_snapshot": root / "paper_account_snapshot.csv",
        "position_snapshot": root / "paper_position_snapshot.csv",
        "daily_review_summary": root / "reports" / "paper_daily_review_summary.md",
        "performance_summary": root / "reports" / "paper_performance_summary.md",
        "review_template_csv": root / "reviews" / "paper_manual_review_log_template.csv",
        "review_template_md": root / "reviews" / "paper_manual_review_log_template.md",
        "review_validation_report": root / "reviews" / "paper_manual_review_log_validation_report.md",
        "review_preview_json": root / "reports" / f"manual_review_import_preview_{compact}.json",
        "review_preview_md": root / "reports" / f"manual_review_import_preview_{compact}.md",
        "review_commit_json": root / "reports" / f"manual_review_import_commit_{compact}.json",
        "review_commit_md": root / "reports" / f"manual_review_import_commit_{compact}.md",
        "review_log": root / "reviews" / "paper_manual_review_log.csv",
    }


def _existing_legacy_matches(
    *,
    account_id: str,
    artifacts: dict[str, Path],
    legacy_artifacts: dict[str, Path],
) -> list[str]:
    if account_id == "paper_default":
        return []
    matches = []
    for key, legacy_path in legacy_artifacts.items():
        if legacy_path.exists() and not artifacts[key].exists():
            matches.append(_path_str(legacy_path))
    return matches


def _stage(
    name: str,
    status: str,
    *,
    required: list[Path] | None = None,
    blockers: list[str] | None = None,
    warnings: list[str] | None = None,
    next_command: str | None = None,
    evidence: EvidenceEvaluation | None = None,
    note: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    required_paths = required or []
    existing = [path for path in required_paths if path.exists()]
    missing = [path for path in required_paths if not path.exists()]
    payload = {
        "stage_name": name,
        "status": status,
        "blockers": blockers or [],
        "warnings": warnings or [],
        "required_artifacts": [_path_str(path) for path in required_paths],
        "existing_artifacts": [_path_str(path) for path in existing],
        "missing_artifacts": [_path_str(path) for path in missing],
        "next_command": next_command,
        "next_action": _next_action(next_command),
        "evidence_path": _path_str(evidence.path) if evidence is not None else None,
        "evidence_status": evidence.evidence_status if evidence is not None else None,
        "evidence_checked": bool(evidence.checked) if evidence is not None else False,
        "evidence_errors": list(evidence.blockers) if evidence is not None else [],
        "notion_checked": False,
        "notion_status": NOTION_SKIPPED,
        "notion_row_count": 0,
        "notion_status_counts": {},
        "notion_errors": [],
        "notion_warnings": [],
        "notion_details": {},
        "local_stage_status": status,
        "notion_stage_status": None,
        "reconciliation_status": None,
        "reconciliation_rule_id": None,
        "reconciliation_reason": None,
        "reconciliation_checked": False,
        "note": note,
    }
    payload.update(kwargs)
    return payload


def _stage_data_freshness(ctx: dict[str, Any]) -> dict[str, Any]:
    if ctx["global_blockers"]:
        return _stage("DATA_FRESHNESS", BLOCKED, blockers=list(ctx["global_blockers"]))
    return _stage(
        "DATA_FRESHNESS",
        READY,
        next_command=f"python scripts\\paper.py data-freshness --date {ctx['data_date']}",
        note="MVP does not run the freshness check automatically; run the read-only command to verify data_date.",
    )


def _stage_daily_plan(ctx: dict[str, Any]) -> dict[str, Any]:
    artifacts = ctx["artifacts"]
    required = [artifacts["daily_plan_md"], artifacts["daily_plan_json"], artifacts["config_snapshot"]]
    blockers = list(ctx["global_blockers"])
    warnings: list[str] = []
    if _has_legacy_for(ctx, ["daily_plan_md", "daily_plan_json", "config_snapshot"]) and not all(path.exists() for path in required):
        blockers.append("Matching legacy paper_test Daily Plan artifacts exist but cannot be used for this account.")
    if blockers:
        return _stage("DAILY_PLAN", BLOCKED, required=required, blockers=blockers)
    if all(path.exists() for path in required):
        payload = _read_json(artifacts["daily_plan_json"])
        if payload is None:
            return _stage("DAILY_PLAN", UNKNOWN, required=required, warnings=["Daily Plan JSON could not be parsed."])
        account_id = str(payload.get("account_id") or "").strip()
        data_date = str(payload.get("data_date") or "").strip()
        trade_date = str(payload.get("trade_date") or payload.get("plan_date") or "").strip()
        if account_id and account_id != ctx["account_id"]:
            blockers.append(f"Daily Plan account_id mismatch: {account_id} != {ctx['account_id']}.")
        if data_date and data_date != ctx["data_date"]:
            blockers.append(f"Daily Plan data_date mismatch: {data_date} != {ctx['data_date']}.")
        if trade_date and trade_date != ctx["trade_date"]:
            blockers.append(f"Daily Plan trade_date mismatch: {trade_date} != {ctx['trade_date']}.")
        return _stage("DAILY_PLAN", BLOCKED if blockers else DONE, required=required, blockers=blockers, warnings=warnings)
    return _stage(
        "DAILY_PLAN",
        READY,
        required=required,
        next_command=(
            f"python scripts\\paper.py plan --data-date {ctx['data_date']} "
            f"--trade-date {ctx['trade_date']} --account-id {ctx['account_id']}"
        ),
    )


def _stage_daily_plan_notion_export(ctx: dict[str, Any]) -> dict[str, Any]:
    plan = _stage_daily_plan(ctx)
    if plan["status"] == DONE:
        command = (
            f"python scripts\\export_paper_to_notion.py --daily-plan --account-id {ctx['account_id']} "
            f"--date {ctx['trade_date']} --confirm-actual --json"
        )
        evidence = _notion_evidence(ctx, EVIDENCE_DAILY_PLAN_NOTION_EXPORT)
        if evidence.checked:
            return _stage(
                "DAILY_PLAN_NOTION_EXPORT",
                evidence.stage_status or UNKNOWN,
                blockers=list(evidence.blockers),
                warnings=list(evidence.warnings),
                evidence=evidence,
                note="Local Notion evidence sidecar was evaluated.",
            )
        return _stage(
            "DAILY_PLAN_NOTION_EXPORT",
            UNKNOWN,
            next_command=command,
            evidence=evidence,
            note="No local export sidecar proves this Notion write stage.",
        )
    return _stage("DAILY_PLAN_NOTION_EXPORT", BLOCKED, blockers=["Daily Plan is not DONE."])


def _stage_manual_execution_template(ctx: dict[str, Any]) -> dict[str, Any]:
    if _stage_daily_plan(ctx)["status"] != DONE:
        return _stage("MANUAL_EXECUTION_TEMPLATE", BLOCKED, blockers=["Daily Plan JSON sidecar is required."])

    plan_json = ctx["artifacts"]["daily_plan_json"]
    candidate_count = _daily_plan_execution_candidate_count(plan_json)

    command = (
        f"python scripts\\export_paper_to_notion.py --manual-execution-template --account-id {ctx['account_id']} "
        f"--date {ctx['trade_date']} --confirm-actual --json"
    )
    evidence = _notion_evidence(ctx, EVIDENCE_MANUAL_EXECUTION_TEMPLATE)
    evidence_payload = _read_json(evidence.path) if evidence.checked and evidence.path else None
    downstream_evidence_exists = (
        ctx["artifacts"]["execution_preview_json"].exists()
        or ctx["artifacts"]["execution_commit_json"].exists()
    )

    # NO-CANDIDATES GUARD
    if candidate_count == 0 and not downstream_evidence_exists:
        return _stage(
            "MANUAL_EXECUTION_TEMPLATE",
            DONE,
            note="Skipped: No execution candidates found in Daily Plan.",
            no_execution_candidates=True,
            execution_candidate_count=0,
            plan_candidate_source="daily_plan_json",
            candidate_count_rule=CANDIDATE_COUNT_RULE,
            evidence=evidence
        )
    if (
        evidence.checked
        and evidence.evidence_status == "PASS"
        and evidence_payload
        and evidence_payload.get("candidate_count") == 0
        and not downstream_evidence_exists
    ):
        return _stage(
            "MANUAL_EXECUTION_TEMPLATE",
            DONE,
            note="Skipped: Evidence confirms 0 execution candidates.",
            no_execution_candidates=True,
            execution_candidate_count=0,
            plan_candidate_source="export_evidence",
            candidate_count_rule=CANDIDATE_COUNT_RULE,
            evidence=evidence
        )

    extra_kwargs = {
        "execution_candidate_count": candidate_count,
        "plan_candidate_source": "daily_plan_json" if candidate_count is not None else "unknown",
        "no_execution_candidates": False,
        "candidate_count_rule": CANDIDATE_COUNT_RULE,
    }

    if evidence.checked:
        return _stage(
            "MANUAL_EXECUTION_TEMPLATE",
            evidence.stage_status or UNKNOWN,
            blockers=list(evidence.blockers),
            warnings=list(evidence.warnings),
            evidence=evidence,
            note="Local Notion evidence sidecar was evaluated.",
            **extra_kwargs
        )
    return _stage(
        "MANUAL_EXECUTION_TEMPLATE",
        UNKNOWN,
        next_command=command,
        evidence=evidence,
        note="No local export sidecar proves Manual Execution DRAFT rows were exported.",
        **extra_kwargs
    )


def _stage_manual_execution_preview(ctx: dict[str, Any]) -> dict[str, Any]:
    artifacts = ctx["artifacts"]
    required = [artifacts["execution_preview_json"]]
    if artifacts["execution_preview_json"].exists():
        payload = _read_json(artifacts["execution_preview_json"])
        issues = _validate_preview_payload(payload, date_key="execution_date", expected_date=ctx["trade_date"], account_id=ctx["account_id"])
        if issues:
            return _stage("MANUAL_EXECUTION_PREVIEW", BLOCKED, required=required, blockers=issues)
        warnings = []
        if str(payload.get("commit_allowed") or "").lower() == "true_with_warnings":
            warnings.append("Preview contains warnings; commit would require --allow-warnings.")
        status = WARNING if warnings else DONE
        return _stage("MANUAL_EXECUTION_PREVIEW", status, required=required, warnings=warnings)
    if _has_legacy_for(ctx, ["execution_preview_json"]):
        return _stage("MANUAL_EXECUTION_PREVIEW", BLOCKED, required=required, blockers=["Legacy paper_test preview exists but cannot be used."])
    template = _stage_manual_execution_template(ctx)
    if template.get("no_execution_candidates"):
        return _stage(
            "MANUAL_EXECUTION_PREVIEW",
            DONE,
            required=[],
            note="Skipped: No execution candidates.",
            no_execution_candidates=True,
            candidate_count_rule=template.get("candidate_count_rule"),
        )
    return _stage(
        "MANUAL_EXECUTION_PREVIEW",
        READY,
        required=required,
        next_command=f"python scripts\\import_notion_executions.py --date {ctx['trade_date']} --account-id {ctx['account_id']} --preview --json",
    )


def _stage_manual_execution_commit(ctx: dict[str, Any]) -> dict[str, Any]:
    artifacts = ctx["artifacts"]
    required = [artifacts["execution_commit_json"]]
    commit_exists = artifacts["execution_commit_json"].exists()
    ledger_rows = _execution_rows_for_date(artifacts["execution_log"], ctx["trade_date"])
    snapshots_exist = _snapshots_exist(artifacts, ctx["trade_date"])
    if commit_exists:
        return _stage("MANUAL_EXECUTION_COMMIT", DONE, required=required, note="Commit report exists; commit is not recommended again.")
    if ledger_rows or snapshots_exist:
        return _stage(
            "MANUAL_EXECUTION_COMMIT",
            WARNING,
            required=required,
            warnings=["Execution ledger or snapshot evidence exists without a matching commit report; commit is not recommended."],
        )
    template = _stage_manual_execution_template(ctx)
    if template.get("no_execution_candidates"):
        return _stage(
            "MANUAL_EXECUTION_COMMIT",
            DONE,
            required=[],
            note="Skipped: No execution candidates.",
            no_execution_candidates=True,
            candidate_count_rule=template.get("candidate_count_rule"),
        )
    preview = _stage_manual_execution_preview(ctx)
    if preview["status"] not in {DONE, WARNING}:
        return _stage("MANUAL_EXECUTION_COMMIT", BLOCKED, required=required, blockers=["Execution preview JSON is required before commit recommendation."])
    return _stage(
        "MANUAL_EXECUTION_COMMIT",
        READY,
        required=required,
        next_command=(
            f"python scripts\\import_notion_executions.py --date {ctx['trade_date']} --account-id {ctx['account_id']} "
            f"--commit --preview-json \"{_path_str(artifacts['execution_preview_json'])}\" --json"
        ),
    )


def _stage_manual_execution_status_sync(ctx: dict[str, Any]) -> dict[str, Any]:
    artifacts = ctx["artifacts"]
    if not artifacts["execution_commit_json"].exists():
        template = _stage_manual_execution_template(ctx)
        if template.get("no_execution_candidates"):
            return _stage(
                "MANUAL_EXECUTION_STATUS_SYNC",
                DONE,
                required=[],
                note="Skipped: No execution candidates.",
                no_execution_candidates=True,
                candidate_count_rule=template.get("candidate_count_rule"),
            )
        return _stage("MANUAL_EXECUTION_STATUS_SYNC", BLOCKED, required=[artifacts["execution_commit_json"]], blockers=["Execution commit report is required for status sync."])
    command = (
        f"python scripts\\sync_notion_execution_status.py --date {ctx['trade_date']} --account-id {ctx['account_id']} "
        f"--commit-report \"{_path_str(artifacts['execution_commit_json'])}\" --json"
    )
    evidence = _notion_evidence(ctx, EVIDENCE_MANUAL_EXECUTION_STATUS_SYNC)
    if evidence.checked:
        return _stage(
            "MANUAL_EXECUTION_STATUS_SYNC",
            evidence.stage_status or UNKNOWN,
            required=[artifacts["execution_commit_json"]],
            blockers=list(evidence.blockers),
            warnings=list(evidence.warnings),
            evidence=evidence,
            note="Local Notion evidence sidecar was evaluated.",
        )
    return _stage(
        "MANUAL_EXECUTION_STATUS_SYNC",
        UNKNOWN,
        required=[artifacts["execution_commit_json"]],
        next_command=command,
        evidence=evidence,
        note="No local sync sidecar proves this Notion sync stage.",
    )


def _stage_daily_review(ctx: dict[str, Any]) -> dict[str, Any]:
    artifacts = ctx["artifacts"]
    trade_date = ctx["trade_date"]
    template = _stage_manual_execution_template(ctx)
    no_candidates = bool(template.get("no_execution_candidates"))
    required = [
        artifacts["daily_review_summary"],
        artifacts["performance_summary"],
        artifacts["review_template_csv"],
        artifacts["review_validation_report"],
    ]
    if all(path.exists() for path in required):
        date_blockers = []
        date_warnings = []

        template_dates = _get_csv_dates(artifacts["review_template_csv"], "review_date")
        if not template_dates:
            date_blockers.append("Review template CSV has no review_date column or is empty.")
        elif any(d != trade_date for d in template_dates):
            date_blockers.append(f"Review template CSV date mismatch: {sorted(list(template_dates))} != {trade_date}")

        if not _validation_passed(artifacts["review_validation_report"]):
            date_blockers.append("Review validation report did not PASS.")

        summary_date = _get_markdown_date(artifacts["daily_review_summary"], ["Latest snapshot date"])
        if summary_date != trade_date:
            message = f"Daily review summary date mismatch: {summary_date} != {trade_date}"
            if no_candidates:
                date_warnings.append(message)
            else:
                date_blockers.append(message)

        perf_date = _get_markdown_date(
            artifacts["performance_summary"], ["Latest Snapshot Date", "Latest Date", "Snapshot Date"]
        )
        if perf_date != trade_date:
            date_warnings.append(f"Performance summary date mismatch: {perf_date} != {trade_date}")

        review_template_current = bool(template_dates) and all(d == trade_date for d in template_dates)
        snapshot_mismatch_allowed = no_candidates and summary_date != trade_date
        date_scope = {
            "no_action_day_review_guard": no_candidates,
            "review_template_date_current": review_template_current,
            "snapshot_date_mismatch_allowed": snapshot_mismatch_allowed,
            "daily_review_snapshot_date": summary_date,
            "performance_snapshot_date": perf_date,
        }
        if not date_blockers:
            return _stage("DAILY_REVIEW", DONE, required=required, warnings=date_warnings, **date_scope)

        return _stage(
            "DAILY_REVIEW",
            READY,
            required=required,
            blockers=date_blockers,
            warnings=date_warnings,
            next_command=f"python scripts\\paper.py review --account-id {ctx['account_id']} --date {trade_date}",
            note="Existing review artifacts are stale or invalid; review generation is recommended.",
            **date_scope,
        )

    if not artifacts["execution_commit_json"].exists() and not _snapshots_exist(artifacts, trade_date) and not no_candidates:
        return _stage(
            "DAILY_REVIEW",
            BLOCKED,
            required=required,
            blockers=["Execution commit evidence is required before review generation."],
        )
    return _stage(
        "DAILY_REVIEW",
        READY,
        required=required,
        next_command=f"python scripts\\paper.py review --account-id {ctx['account_id']} --date {trade_date}",
    )


def _stage_manual_review_template(ctx: dict[str, Any]) -> dict[str, Any]:
    path = ctx["artifacts"]["review_template_csv"]
    trade_date = ctx["trade_date"]
    if not path.exists():
        return _stage(
            "MANUAL_REVIEW_TEMPLATE", BLOCKED, required=[path], blockers=["Review template CSV is required."]
        )

    template_dates = _get_csv_dates(path, "review_date")
    if not template_dates:
        return _stage(
            "MANUAL_REVIEW_TEMPLATE",
            BLOCKED,
            required=[path],
            blockers=["Review template CSV has no review_date column or is empty."],
        )
    if any(d != trade_date for d in template_dates):
        return _stage(
            "MANUAL_REVIEW_TEMPLATE",
            BLOCKED,
            required=[path],
            blockers=[f"Review template CSV date mismatch: {sorted(list(template_dates))} != {trade_date}"],
        )

    command = (
        f"python scripts\\export_paper_to_notion.py --manual-review-template --account-id {ctx['account_id']} "
        f"--date {trade_date} --confirm-actual --json"
    )
    evidence = _notion_evidence(ctx, EVIDENCE_MANUAL_REVIEW_TEMPLATE)
    if evidence.checked:
        return _stage(
            "MANUAL_REVIEW_TEMPLATE",
            evidence.stage_status or UNKNOWN,
            required=[ctx["artifacts"]["review_template_csv"]],
            blockers=list(evidence.blockers),
            warnings=list(evidence.warnings),
            evidence=evidence,
            note="Local Notion evidence sidecar was evaluated.",
        )
    return _stage(
        "MANUAL_REVIEW_TEMPLATE",
        UNKNOWN,
        required=[ctx["artifacts"]["review_template_csv"]],
        next_command=command,
        evidence=evidence,
        note="No local export sidecar proves Manual Review rows were exported.",
    )


def _stage_manual_review_preview(ctx: dict[str, Any]) -> dict[str, Any]:
    artifacts = ctx["artifacts"]
    required = [artifacts["review_preview_json"]]
    if artifacts["review_preview_json"].exists():
        payload = _read_json(artifacts["review_preview_json"])
        issues = _validate_preview_payload(payload, date_key="review_date", expected_date=ctx["trade_date"], account_id=ctx["account_id"])
        if issues:
            return _stage("MANUAL_REVIEW_PREVIEW", BLOCKED, required=required, blockers=issues)
        warnings = []
        if str(payload.get("append_allowed") or "").lower() == "true_with_warnings":
            warnings.append("Preview contains warnings; append would require --allow-warnings.")
        if payload.get("duplicate_candidates"):
            warnings.append("Preview reports duplicate candidates.")
        status = WARNING if warnings else DONE
        return _stage("MANUAL_REVIEW_PREVIEW", status, required=required, warnings=warnings)
    if _has_legacy_for(ctx, ["review_preview_json"]):
        return _stage("MANUAL_REVIEW_PREVIEW", BLOCKED, required=required, blockers=["Legacy paper_test review preview exists but cannot be used."])
    return _stage(
        "MANUAL_REVIEW_PREVIEW",
        READY,
        required=required,
        next_command=f"python scripts\\import_notion_reviews.py --date {ctx['trade_date']} --account-id {ctx['account_id']} --preview --json",
    )


def _stage_manual_review_append(ctx: dict[str, Any]) -> dict[str, Any]:
    artifacts = ctx["artifacts"]
    required = [artifacts["review_commit_json"]]
    if artifacts["review_commit_json"].exists():
        return _stage("MANUAL_REVIEW_APPEND", DONE, required=required, note="Review commit report exists; append is not recommended again.")
    if _review_log_has_rows_for_date(artifacts["review_log"], ctx["trade_date"]):
        return _stage(
            "MANUAL_REVIEW_APPEND",
            WARNING,
            required=required,
            warnings=["Review log rows exist without a matching review commit report; append is not recommended."],
        )
    preview = _stage_manual_review_preview(ctx)
    if preview["status"] not in {DONE, WARNING}:
        return _stage("MANUAL_REVIEW_APPEND", BLOCKED, required=required, blockers=["Review preview JSON is required before append recommendation."])
    return _stage(
        "MANUAL_REVIEW_APPEND",
        READY,
        required=required,
        next_command=(
            f"python scripts\\import_notion_reviews.py --date {ctx['trade_date']} --account-id {ctx['account_id']} "
            f"--commit --preview-json \"{_path_str(artifacts['review_preview_json'])}\" --json"
        ),
    )


def _stage_manual_review_status_sync(ctx: dict[str, Any]) -> dict[str, Any]:
    artifacts = ctx["artifacts"]
    if not artifacts["review_commit_json"].exists():
        return _stage("MANUAL_REVIEW_STATUS_SYNC", BLOCKED, required=[artifacts["review_commit_json"]], blockers=["Review commit report is required for status sync."])
    command = (
        f"python scripts\\sync_notion_review_status.py --date {ctx['trade_date']} --account-id {ctx['account_id']} "
        f"--commit-report \"{_path_str(artifacts['review_commit_json'])}\" --json"
    )
    evidence = _notion_evidence(ctx, EVIDENCE_MANUAL_REVIEW_STATUS_SYNC)
    if evidence.checked:
        return _stage(
            "MANUAL_REVIEW_STATUS_SYNC",
            evidence.stage_status or UNKNOWN,
            required=[artifacts["review_commit_json"]],
            blockers=list(evidence.blockers),
            warnings=list(evidence.warnings),
            evidence=evidence,
            note="Local Notion evidence sidecar was evaluated.",
        )
    return _stage(
        "MANUAL_REVIEW_STATUS_SYNC",
        UNKNOWN,
        required=[artifacts["review_commit_json"]],
        next_command=command,
        evidence=evidence,
        note="No local sync sidecar proves this Notion sync stage.",
    )


def _stage_final_status(ctx: dict[str, Any]) -> dict[str, Any]:
    workflow_status = _safe_workflow_status(ctx["root"], ctx["trade_date"])
    if workflow_status == WORKFLOW_REVIEW_DONE:
        return _stage("FINAL_STATUS", DONE, note="paper.py status local workflow_status is REVIEW_DONE.")
    if workflow_status:
        return _stage(
            "FINAL_STATUS",
            WARNING,
            warnings=[f"paper.py status workflow_status is {workflow_status}."],
            next_command=f"python scripts\\paper.py status --account-id {ctx['account_id']} --date {ctx['trade_date']} --json",
        )
    return _stage("FINAL_STATUS", UNKNOWN, next_command=f"python scripts\\paper.py status --account-id {ctx['account_id']} --date {ctx['trade_date']} --json")


def _notion_evidence(ctx: dict[str, Any], evidence_type: str) -> EvidenceEvaluation:
    return evaluate_notion_evidence(
        account_root=ctx["root"],
        legacy_root=ctx["legacy_root"],
        account_id=ctx["account_id"],
        trade_date=ctx["trade_date"],
        data_date=ctx["data_date"],
        evidence_type=evidence_type,
    )


def _build_notion_report(
    *,
    include_notion_read: bool,
    notion_timeout_seconds: int,
    notion_status_report: dict[str, Any] | None,
    account_id: str,
    data_date: str,
    trade_date: str,
) -> dict[str, Any]:
    if notion_status_report is not None:
        return notion_status_report
    if not include_notion_read:
        return skipped_notion_live_read_status()
    return build_notion_live_read_status(
        account_id=account_id,
        data_date=data_date,
        trade_date=trade_date,
        timeout_seconds=notion_timeout_seconds,
    )


def _apply_notion_report(stages: list[dict[str, Any]], notion_report: dict[str, Any]) -> None:
    stage_reports = notion_report.get("stages") or {}
    if not isinstance(stage_reports, dict):
        return
    by_name = {stage["stage_name"]: stage for stage in stages}
    for stage_name, stage_report in stage_reports.items():
        stage = by_name.get(stage_name)
        if not stage or not isinstance(stage_report, dict):
            continue
        _attach_notion_fields(stage, stage_report)


def _attach_notion_fields(stage: dict[str, Any], stage_report: dict[str, Any]) -> None:
    stage["notion_checked"] = True
    stage["notion_status"] = str(stage_report.get("status") or NOTION_UNKNOWN)
    stage["notion_row_count"] = int(stage_report.get("row_count") or 0)
    stage["notion_status_counts"] = dict(stage_report.get("status_counts") or {})
    stage["notion_errors"] = list(stage_report.get("errors") or [])
    stage["notion_warnings"] = list(stage_report.get("warnings") or [])
    stage["notion_details"] = dict(stage_report.get("details") or {})


def _safe_workflow_status(root: Path, trade_date: str) -> str | None:
    try:
        return str(run_paper_status(trade_date, paper_root=root).get("workflow_status") or "")
    except Exception:
        return None


def _has_legacy_for(ctx: dict[str, Any], keys: list[str]) -> bool:
    if ctx["account_id"] == "paper_default":
        return False
    return any(ctx["legacy_artifacts"][key].exists() and not ctx["artifacts"][key].exists() for key in keys)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _validate_preview_payload(
    payload: dict[str, Any] | None,
    *,
    date_key: str,
    expected_date: str,
    account_id: str,
) -> list[str]:
    if payload is None:
        return ["Preview JSON could not be parsed."]
    issues: list[str] = []
    if str(payload.get(date_key) or "").strip() != expected_date:
        issues.append(f"Preview {date_key} mismatch.")
    if str(payload.get("account_id") or "").strip() != account_id:
        issues.append("Preview account_id mismatch.")
    if int(payload.get("fail_count") or 0) > 0:
        issues.append("Preview contains FAIL rows.")
    allowed_key = "commit_allowed" if date_key == "execution_date" else "append_allowed"
    if str(payload.get(allowed_key) or "").strip().lower() not in {"true", "true_with_warnings"}:
        issues.append(f"Preview {allowed_key} does not allow the next stage.")
    return issues


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [{(key or "").strip(): value or "" for key, value in row.items()} for row in csv.DictReader(handle)]


def _execution_rows_for_date(path: Path, trade_date: str) -> list[dict[str, str]]:
    return [
        row
        for row in _read_csv_rows(path)
        if str(row.get("date") or "").strip() == trade_date
        and str(row.get("source") or "").strip() == "notion_manual_execution"
    ]


def _review_log_has_rows_for_date(path: Path, trade_date: str) -> bool:
    return any(str(row.get("review_date") or "").strip() == trade_date for row in _read_csv_rows(path))


def _snapshots_exist(artifacts: dict[str, Path], trade_date: str) -> bool:
    return (
        artifacts["current_state"].exists()
        or _csv_has_date(artifacts["account_snapshot"], "snapshot_date", trade_date)
        or _csv_has_date(artifacts["position_snapshot"], "snapshot_date", trade_date)
    )


def _csv_has_date(path: Path, column: str, value: str) -> bool:
    return any(str(row.get(column) or "").strip() == value for row in _read_csv_rows(path))


def _validation_passed(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        return "Validation result: PASS" in path.read_text(encoding="utf-8")
    except Exception:
        return False


def _derive_overall_status(blockers: list[str], warnings: list[str], stages: list[dict[str, Any]]) -> str:
    if blockers or any(stage["status"] == BLOCKED for stage in stages):
        return BLOCKED
    if warnings or any(stage["status"] == WARNING for stage in stages):
        return WARNING
    if any(stage["status"] == UNKNOWN for stage in stages):
        return UNKNOWN
    return "PASS"


def _first_next_command(stages: list[dict[str, Any]], *, workflow_status: str | None = None) -> str | None:
    if _has_manual_execution_input_wait(stages):
        return None
    if _has_manual_review_input_wait(stages):
        return None
    for stage in stages:
        if _is_stale_next_command_stage(stage, stages=stages, workflow_status=workflow_status):
            continue
        if stage.get("status") in {READY, WARNING, UNKNOWN} and stage.get("next_command"):
            return str(stage["next_command"])
    return None


def _ensure_ready_stage_commands(stages: list[dict[str, Any]], ctx: dict[str, Any]) -> None:
    for stage in stages:
        if stage.get("status") != READY or stage.get("next_command"):
            continue
        command = _default_ready_command(str(stage.get("stage_name") or ""), ctx)
        if command:
            stage["next_command"] = command
            stage["next_action"] = _next_action(command)


def _suppress_manual_execution_no_candidate_skips_when_notion_rows_exist(stages: list[dict[str, Any]]) -> None:
    if not _manual_execution_notion_rows_exist(stages):
        return
    warning = "Manual Execution Notion rows exist; no-candidates skip was suppressed."
    for stage in stages:
        if stage.get("stage_name") not in {
            "MANUAL_EXECUTION_TEMPLATE",
            "MANUAL_EXECUTION_PREVIEW",
            "MANUAL_EXECUTION_COMMIT",
            "MANUAL_EXECUTION_STATUS_SYNC",
        }:
            continue
        if not stage.get("no_execution_candidates"):
            continue
        stage["no_execution_candidates"] = False
        warnings = list(stage.get("warnings") or [])
        if warning not in warnings:
            warnings.append(warning)
        stage["warnings"] = warnings
        if stage.get("stage_name") == "MANUAL_EXECUTION_PREVIEW" and _is_no_candidate_skip(stage):
            stage["status"] = READY
            stage["note"] = "Manual Execution Notion rows exist; run execution preview instead of no-op skip."
        elif stage.get("stage_name") == "MANUAL_EXECUTION_COMMIT" and _is_no_candidate_skip(stage):
            stage["status"] = BLOCKED
            stage["blockers"] = ["Execution preview JSON is required before commit recommendation."]
            stage["note"] = "Manual Execution Notion rows exist; commit cannot be skipped as no-action."
        elif stage.get("stage_name") == "MANUAL_EXECUTION_STATUS_SYNC" and _is_no_candidate_skip(stage):
            stage["status"] = BLOCKED
            stage["blockers"] = ["Execution commit report is required for status sync."]
            stage["note"] = "Manual Execution Notion rows exist; status sync cannot be skipped as no-action."


def _manual_execution_notion_rows_exist(stages: list[dict[str, Any]]) -> bool:
    return any(
        stage.get("stage_name")
        in {
            "MANUAL_EXECUTION_TEMPLATE",
            "MANUAL_EXECUTION_PREVIEW",
            "MANUAL_EXECUTION_COMMIT",
            "MANUAL_EXECUTION_STATUS_SYNC",
        }
        and int(stage.get("notion_row_count") or 0) > 0
        for stage in stages
    )


def _is_no_candidate_skip(stage: dict[str, Any]) -> bool:
    return (
        stage.get("status") == DONE
        and str(stage.get("note") or "").lower().startswith("skipped: no execution candidates")
    )


def _default_ready_command(stage_name: str, ctx: dict[str, Any]) -> str | None:
    artifacts = ctx["artifacts"]
    account_id = ctx["account_id"]
    data_date = ctx["data_date"]
    trade_date = ctx["trade_date"]
    if stage_name == "DATA_FRESHNESS":
        return f"python scripts\\paper.py data-freshness --date {data_date}"
    if stage_name == "DAILY_PLAN":
        return f"python scripts\\paper.py plan --data-date {data_date} --trade-date {trade_date} --account-id {account_id}"
    if stage_name == "DAILY_PLAN_NOTION_EXPORT":
        return (
            f"python scripts\\export_paper_to_notion.py --daily-plan --account-id {account_id} "
            f"--date {trade_date} --confirm-actual --json"
        )
    if stage_name == "MANUAL_EXECUTION_TEMPLATE":
        return (
            f"python scripts\\export_paper_to_notion.py --manual-execution-template --account-id {account_id} "
            f"--date {trade_date} --confirm-actual --json"
        )
    if stage_name == "MANUAL_EXECUTION_PREVIEW":
        return f"python scripts\\import_notion_executions.py --date {trade_date} --account-id {account_id} --preview --json"
    if stage_name == "MANUAL_EXECUTION_COMMIT":
        return (
            f"python scripts\\import_notion_executions.py --date {trade_date} --account-id {account_id} "
            f"--commit --preview-json \"{_path_str(artifacts['execution_preview_json'])}\" --json"
        )
    if stage_name == "MANUAL_EXECUTION_STATUS_SYNC":
        return (
            f"python scripts\\sync_notion_execution_status.py --date {trade_date} --account-id {account_id} "
            f"--commit-report \"{_path_str(artifacts['execution_commit_json'])}\" --json"
        )
    if stage_name == "DAILY_REVIEW":
        return f"python scripts\\paper.py review --account-id {account_id} --date {trade_date}"
    if stage_name == "MANUAL_REVIEW_TEMPLATE":
        return (
            f"python scripts\\export_paper_to_notion.py --manual-review-template --account-id {account_id} "
            f"--date {trade_date} --confirm-actual --json"
        )
    if stage_name == "MANUAL_REVIEW_PREVIEW":
        return f"python scripts\\import_notion_reviews.py --date {trade_date} --account-id {account_id} --preview --json"
    if stage_name == "MANUAL_REVIEW_APPEND":
        return (
            f"python scripts\\import_notion_reviews.py --date {trade_date} --account-id {account_id} "
            f"--commit --preview-json \"{_path_str(artifacts['review_preview_json'])}\" --json"
        )
    if stage_name == "MANUAL_REVIEW_STATUS_SYNC":
        return (
            f"python scripts\\sync_notion_review_status.py --date {trade_date} --account-id {account_id} "
            f"--commit-report \"{_path_str(artifacts['review_commit_json'])}\" --json"
        )
    return None


def _is_stale_next_command_stage(
    stage: dict[str, Any],
    *,
    stages: list[dict[str, Any]],
    workflow_status: str | None,
) -> bool:
    stage_name = str(stage.get("stage_name") or "")
    daily_plan_done = _stage_status(stages, "DAILY_PLAN") == DONE
    execution_template_done = _stage_status(stages, "MANUAL_EXECUTION_TEMPLATE") == DONE
    execution_preview_done = _stage_status(stages, "MANUAL_EXECUTION_PREVIEW") in {DONE, WARNING}
    execution_commit_done = _stage_status(stages, "MANUAL_EXECUTION_COMMIT") in {DONE, WARNING}
    execution_sync_done = _stage_status(stages, "MANUAL_EXECUTION_STATUS_SYNC") == DONE
    daily_review_done = _stage_status(stages, "DAILY_REVIEW") == DONE
    review_template_done = _stage_status(stages, "MANUAL_REVIEW_TEMPLATE") == DONE
    review_preview_done = _stage_status(stages, "MANUAL_REVIEW_PREVIEW") in {DONE, WARNING}
    review_append_done = _stage_status(stages, "MANUAL_REVIEW_APPEND") in {DONE, WARNING}
    review_sync_done = _stage_status(stages, "MANUAL_REVIEW_STATUS_SYNC") == DONE
    if stage_name == "DATA_FRESHNESS":
        return daily_plan_done or str(workflow_status or "") not in {"", "NO_PLAN", "UNKNOWN_OR_INCOMPLETE"}
    if stage_name == "DAILY_PLAN":
        return daily_plan_done or str(workflow_status or "") not in {"", "NO_PLAN", "UNKNOWN_OR_INCOMPLETE"}
    if stage_name in {
        "DAILY_PLAN_NOTION_EXPORT",
        "MANUAL_EXECUTION_TEMPLATE",
        "MANUAL_EXECUTION_PREVIEW",
        "MANUAL_EXECUTION_COMMIT",
        "MANUAL_EXECUTION_STATUS_SYNC",
        "DAILY_REVIEW",
        "MANUAL_REVIEW_TEMPLATE",
        "MANUAL_REVIEW_PREVIEW",
        "MANUAL_REVIEW_APPEND",
        "MANUAL_REVIEW_STATUS_SYNC",
    } and not daily_plan_done:
        return True
    if stage_name == "DAILY_PLAN_NOTION_EXPORT":
        return execution_template_done or execution_commit_done or daily_review_done
    if stage_name == "MANUAL_EXECUTION_TEMPLATE":
        return execution_commit_done or execution_sync_done or daily_review_done
    if stage_name == "MANUAL_EXECUTION_PREVIEW":
        return execution_commit_done or execution_sync_done or daily_review_done
    if stage_name == "MANUAL_EXECUTION_COMMIT":
        return execution_sync_done or daily_review_done
    if stage_name == "MANUAL_EXECUTION_STATUS_SYNC":
        return daily_review_done
    if stage_name == "DAILY_REVIEW":
        return review_template_done or review_preview_done or review_append_done
    if stage_name == "MANUAL_REVIEW_TEMPLATE":
        return review_preview_done or review_append_done or review_sync_done
    if stage_name == "MANUAL_REVIEW_PREVIEW":
        return review_append_done or review_sync_done
    if stage_name == "MANUAL_REVIEW_APPEND":
        return review_sync_done or str(workflow_status or "") == WORKFLOW_REVIEW_DONE
    if stage_name == "MANUAL_REVIEW_STATUS_SYNC":
        return str(workflow_status or "") == WORKFLOW_REVIEW_DONE and stage.get("status") != READY
    return False


def _stage_status(stages: list[dict[str, Any]], stage_name: str) -> str | None:
    for stage in stages:
        if stage.get("stage_name") == stage_name:
            return str(stage.get("status") or "")
    return None


def _has_manual_execution_input_wait(stages: list[dict[str, Any]]) -> bool:
    if _stage_status(stages, "DAILY_PLAN_NOTION_EXPORT") != DONE:
        return False
    stage = next((item for item in stages if item.get("stage_name") == "MANUAL_EXECUTION_TEMPLATE"), None)
    if not stage or stage.get("status") != DONE or int(stage.get("notion_row_count") or 0) <= 0:
        return False
    counts = stage.get("notion_status_counts") or {}
    draft_count = int(counts.get("DRAFT") or counts.get("draft") or 0)
    ready_count = int(counts.get("READY") or counts.get("ready") or 0)
    missing_price = int((stage.get("notion_details") or {}).get("missing_actual_price_count") or 0)
    return draft_count > 0 and ready_count == 0 and missing_price > 0


def _has_manual_review_input_wait(stages: list[dict[str, Any]]) -> bool:
    if _stage_status(stages, "MANUAL_REVIEW_TEMPLATE") != DONE:
        return False
    preview = next((item for item in stages if item.get("stage_name") == "MANUAL_REVIEW_PREVIEW"), None)
    if not preview or int(preview.get("notion_row_count") or 0) <= 0:
        return False
    if preview.get("status") in {DONE, WARNING}:
        return False
    counts = preview.get("notion_status_counts") or {}
    pending_count = int(counts.get("PENDING") or counts.get("pending") or 0)
    draft_count = int(counts.get("DRAFT") or counts.get("draft") or 0)
    ready_count = int(counts.get("READY") or counts.get("ready") or 0)
    reviewed_count = int(counts.get("REVIEWED") or counts.get("reviewed") or 0)
    answered_count = int(counts.get("ANSWERED") or counts.get("answered") or 0)
    return (pending_count > 0 or draft_count > 0) and ready_count == 0 and reviewed_count == 0 and answered_count == 0


def _is_terminal_workflow(
    workflow_status: str | None,
    stages: list[dict[str, Any]],
    *,
    completion_mode: str = COMPLETION_MODE_STANDARD,
) -> bool:
    if completion_mode == COMPLETION_MODE_NO_ACTION:
        return not _has_required_status_sync(stages)
    return workflow_status == WORKFLOW_REVIEW_DONE and not _has_required_status_sync(stages)


def _has_required_status_sync(stages: list[dict[str, Any]]) -> bool:
    return any(
        stage.get("stage_name") in {"MANUAL_EXECUTION_STATUS_SYNC", "MANUAL_REVIEW_STATUS_SYNC"}
        and stage.get("reconciliation_checked")
        and stage.get("status") == READY
        and bool(stage.get("next_command"))
        for stage in stages
    )


def _stage_counts(stages: list[dict[str, Any]]) -> dict[str, int]:
    counts = {status: 0 for status in (DONE, READY, BLOCKED, WARNING, UNKNOWN, NOT_STARTED)}
    for stage in stages:
        status = str(stage.get("status") or "")
        if status in counts:
            counts[status] += 1
    return counts


def _summary(
    *,
    workflow_status: str | None,
    terminal: bool,
    blockers: list[str],
    warnings: list[str],
    stages: list[dict[str, Any]],
    next_command: str | None,
) -> dict[str, Any]:
    has_blockers = bool(blockers) or any(stage.get("status") == BLOCKED for stage in stages)
    has_warnings = bool(warnings) or any(stage.get("status") == WARNING for stage in stages)
    has_unknowns = any(stage.get("status") == UNKNOWN for stage in stages)
    if terminal:
        recommended = RECOMMENDED_ACTION_NONE
    elif has_blockers:
        recommended = RECOMMENDED_ACTION_RESOLVE_BLOCKERS
    elif has_warnings:
        recommended = RECOMMENDED_ACTION_REVIEW_WARNINGS
    elif has_unknowns:
        recommended = RECOMMENDED_ACTION_CHECK_NOTION
    elif next_command:
        recommended = RECOMMENDED_ACTION_RUN_NEXT_COMMAND
    else:
        recommended = RECOMMENDED_ACTION_NONE
    return {
        "terminal": terminal,
        "needs_attention": False if terminal else has_blockers or has_warnings or has_unknowns,
        "has_blockers": has_blockers,
        "has_warnings": has_warnings,
        "has_unknowns": has_unknowns,
        "recommended_operator_action": recommended,
    }


def _next_action(command: str | None) -> dict[str, Any] | None:
    if not command:
        return None
    command_text = str(command)
    lowered = command_text.lower()
    calls_broker = any(token in lowered for token in ("broker", "order placement", "place-order", "live-order"))
    if calls_broker:
        return {
            "command": command_text,
            "command_type": COMMAND_TYPE_UNKNOWN,
            "risk_level": RISK_DANGEROUS,
            "requires_manual_approval": True,
            "writes_notion": False,
            "writes_ledger": False,
            "calls_broker": True,
            "reason": "Broker/API command classes are forbidden for Daily Ops Orchestrator recommendations.",
        }
    if "--commit" in lowered and (
        "import_notion_executions.py" in lowered or "import_notion_reviews.py" in lowered
    ):
        return {
            "command": command_text,
            "command_type": COMMAND_TYPE_LEDGER_WRITE,
            "risk_level": RISK_REQUIRES_MANUAL_REVIEW,
            "requires_manual_approval": True,
            "writes_notion": False,
            "writes_ledger": True,
            "calls_broker": False,
            "reason": "Commit/append commands mutate local source-of-truth artifacts and require operator review.",
        }
    if "--confirm-actual" in lowered or "sync_notion_" in lowered:
        return {
            "command": command_text,
            "command_type": COMMAND_TYPE_NOTION_WRITE,
            "risk_level": RISK_REQUIRES_MANUAL_REVIEW,
            "requires_manual_approval": True,
            "writes_notion": True,
            "writes_ledger": False,
            "calls_broker": False,
            "reason": "Notion export/sync commands can write Notion state and require manual review.",
        }
    if "import_notion_" in lowered and "--preview" in lowered:
        return {
            "command": command_text,
            "command_type": COMMAND_TYPE_READ_ONLY,
            "risk_level": RISK_SAFE,
            "requires_manual_approval": False,
            "writes_notion": False,
            "writes_ledger": False,
            "calls_broker": False,
            "reason": "Preview command is read-only and does not commit local or Notion state.",
        }
    if (
        "scripts\\paper.py data-freshness" in lowered
        or "scripts/paper.py data-freshness" in lowered
        or "scripts\\paper.py status" in lowered
        or "scripts/paper.py status" in lowered
    ):
        return {
            "command": command_text,
            "command_type": COMMAND_TYPE_READ_ONLY,
            "risk_level": RISK_SAFE,
            "requires_manual_approval": False,
            "writes_notion": False,
            "writes_ledger": False,
            "calls_broker": False,
            "reason": "Recommended paper.py command is treated as local/read-only in this status contract.",
        }
    return {
        "command": command_text,
        "command_type": COMMAND_TYPE_UNKNOWN,
        "risk_level": RISK_REQUIRES_MANUAL_REVIEW,
        "requires_manual_approval": True,
        "writes_notion": False,
        "writes_ledger": False,
        "calls_broker": False,
        "reason": "Command class is not recognized by the Daily Ops Orchestrator contract.",
    }


def _path_str(path: Path) -> str:
    return str(path).replace("/", "\\")


def _get_csv_dates(path: Path, column: str) -> set[str]:
    return {str(row.get(column) or "").strip() for row in _read_csv_rows(path) if column in row}


def _get_markdown_date(path: Path, labels: list[str]) -> str | None:
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
        for label in labels:
            # Look for "Label: YYYY-MM-DD" or "Label:YYYY-MM-DD"
            pattern = rf"{re.escape(label)}\s*[:]?\s*(\d{{4}}-\d{{2}}-\d{{2}})"
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
    except Exception:
        pass
    return None


def _daily_plan_execution_candidate_count(plan_json_path: Path) -> int | None:
    if not plan_json_path.exists():
        return None
    try:
        payload = json.loads(plan_json_path.read_text(encoding="utf-8"))
        if "items" not in payload:
            return None
        items = payload["items"]
        if not isinstance(items, list):
            return None
        return count_daily_plan_execution_candidates(payload)
    except Exception:
        return None

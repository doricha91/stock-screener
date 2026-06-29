from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_WORKSPACE = Path(r"D:\n8n\workspace\stock_screener_ops")
STATE_FILENAME = "runbook_state.json"
# runbook_state.json is a new controller-owned state contract for
# Phase 1 scheduled runbook automation.
# It does not replace the existing n8n runner context.json contract.
# It shares account_id/data_date/trade_date concepts but owns controller state.
SCHEMA_VERSION = "runbook_state.v1"
STAGE_IDS = ("A", "GATE1", "B", "GATE2", "C")
ALLOWED_STATUSES = {"READY", "PENDING", "RUNNING", "WAIT", "PASS", "BLOCKED", "FAILED", "DONE"}
ALLOWED_IDEMPOTENCY_STATUSES = {"RECORDED", "BLOCKED", "CONSUMED", "PASS", "FAILED"}


@dataclass(frozen=True)
class FrozenRunbookContext:
    account_id: str
    data_date: str
    trade_date: str


@dataclass(frozen=True)
class RunbookState:
    schema_version: str
    runbook_day_id: str
    created_at: str
    updated_at: str
    timezone: str
    frozen_context: FrozenRunbookContext
    current_stage: str
    current_status: str
    last_completed_step: int | None
    last_completed_stage: str | None
    stage_status: dict[str, str]
    artifacts: dict[str, Any] = field(default_factory=dict)
    idempotency_records: dict[str, Any] = field(default_factory=dict)
    last_error: dict[str, Any] | None = None
    history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize_date(value: str, field_name: str) -> str:
    clean = str(value or "").strip().replace("-", "")
    if len(clean) != 8 or not clean.isdigit():
        raise ValueError(f"{field_name} must be YYYY-MM-DD or YYYYMMDD: {value}")
    return datetime.strptime(clean, "%Y%m%d").strftime("%Y-%m-%d")


def _safe_id_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value).strip())
    return cleaned.strip("_") or "unknown"


def get_runbook_day_id(account_id: str, data_date: str, trade_date: str) -> str:
    data_date_norm = _normalize_date(data_date, "data_date")
    trade_date_norm = _normalize_date(trade_date, "trade_date")
    return f"{_safe_id_part(account_id)}_{data_date_norm}_{trade_date_norm}"


def _now_iso(timezone: str) -> str:
    try:
        tz = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown timezone: {timezone}") from exc
    return datetime.now(tz).isoformat(timespec="seconds")


def create_initial_state(
    account_id: str,
    data_date: str,
    trade_date: str,
    timezone: str = "Asia/Seoul",
) -> RunbookState:
    account_id = str(account_id or "").strip()
    if not account_id:
        raise ValueError("account_id is required")
    data_date_norm = _normalize_date(data_date, "data_date")
    trade_date_norm = _normalize_date(trade_date, "trade_date")
    timestamp = _now_iso(timezone)
    context = FrozenRunbookContext(
        account_id=account_id,
        data_date=data_date_norm,
        trade_date=trade_date_norm,
    )
    return RunbookState(
        schema_version=SCHEMA_VERSION,
        runbook_day_id=get_runbook_day_id(account_id, data_date_norm, trade_date_norm),
        created_at=timestamp,
        updated_at=timestamp,
        timezone=timezone,
        frozen_context=context,
        current_stage="A",
        current_status="READY",
        last_completed_step=None,
        last_completed_stage=None,
        stage_status={stage_id: "PENDING" for stage_id in STAGE_IDS},
        artifacts={},
        idempotency_records={},
        last_error=None,
        history=[],
    )


def _state_from_dict(data: dict[str, Any]) -> RunbookState:
    frozen_context_data = data.get("frozen_context")
    if not isinstance(frozen_context_data, dict):
        frozen_context_data = {}
    return RunbookState(
        schema_version=str(data.get("schema_version", "")),
        runbook_day_id=str(data.get("runbook_day_id", "")),
        created_at=str(data.get("created_at", "")),
        updated_at=str(data.get("updated_at", "")),
        timezone=str(data.get("timezone", "")),
        frozen_context=FrozenRunbookContext(
            account_id=str(frozen_context_data.get("account_id", "")),
            data_date=str(frozen_context_data.get("data_date", "")),
            trade_date=str(frozen_context_data.get("trade_date", "")),
        ),
        current_stage=str(data.get("current_stage", "")),
        current_status=str(data.get("current_status", "")),
        last_completed_step=data.get("last_completed_step"),
        last_completed_stage=data.get("last_completed_stage"),
        stage_status=dict(data.get("stage_status", {})) if isinstance(data.get("stage_status"), dict) else {},
        artifacts=dict(data.get("artifacts", {})) if isinstance(data.get("artifacts"), dict) else {},
        idempotency_records=(
            dict(data.get("idempotency_records", {}))
            if isinstance(data.get("idempotency_records", {}), dict)
            else {}
        ),
        last_error=data.get("last_error") if isinstance(data.get("last_error"), dict) or data.get("last_error") is None else {"value": data.get("last_error")},
        history=list(data.get("history", [])) if isinstance(data.get("history"), list) else [],
    )


def load_state(path: Path) -> RunbookState:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("runbook_state.json must contain a JSON object")
    return _state_from_dict(data)


def save_state(state: RunbookState, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(
        json.dumps(state.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)


def context_matches_state(
    state: RunbookState,
    account_id: str,
    data_date: str,
    trade_date: str,
) -> bool:
    try:
        data_date_norm = _normalize_date(data_date, "data_date")
        trade_date_norm = _normalize_date(trade_date, "trade_date")
    except ValueError:
        return False
    return (
        state.frozen_context.account_id == str(account_id or "").strip()
        and state.frozen_context.data_date == data_date_norm
        and state.frozen_context.trade_date == trade_date_norm
    )


def validate_state(state: RunbookState) -> list[str]:
    errors: list[str] = []
    if state.schema_version != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if not state.frozen_context.account_id:
        errors.append("frozen_context.account_id is required")
    if not state.frozen_context.data_date:
        errors.append("frozen_context.data_date is required")
    if not state.frozen_context.trade_date:
        errors.append("frozen_context.trade_date is required")
    try:
        expected_runbook_day_id = get_runbook_day_id(
            state.frozen_context.account_id,
            state.frozen_context.data_date,
            state.frozen_context.trade_date,
        )
        if state.runbook_day_id != expected_runbook_day_id:
            errors.append("runbook_day_id does not match frozen_context")
    except ValueError as exc:
        errors.append(str(exc))
    if state.current_stage not in STAGE_IDS:
        errors.append("current_stage must be one of A/GATE1/B/GATE2/C")
    if state.current_status not in ALLOWED_STATUSES:
        errors.append("current_status is not allowed")
    missing_stage_status = [stage_id for stage_id in STAGE_IDS if stage_id not in state.stage_status]
    if missing_stage_status:
        errors.append(f"stage_status missing stages: {', '.join(missing_stage_status)}")
    for stage_id, status in state.stage_status.items():
        if stage_id not in STAGE_IDS:
            errors.append(f"stage_status has unknown stage: {stage_id}")
        if status not in ALLOWED_STATUSES:
            errors.append(f"stage_status.{stage_id} has invalid status: {status}")
    if state.last_completed_step is not None:
        if not isinstance(state.last_completed_step, int) or not 0 <= state.last_completed_step <= 18:
            errors.append("last_completed_step must be null or 0..18")
    if state.last_completed_stage is not None and state.last_completed_stage not in STAGE_IDS:
        errors.append("last_completed_stage must be null or one of A/GATE1/B/GATE2/C")
    if not isinstance(state.artifacts, dict):
        errors.append("artifacts must be an object")
    if not isinstance(state.idempotency_records, dict):
        errors.append("idempotency_records must be an object")
    else:
        for record_key, record in state.idempotency_records.items():
            if not isinstance(record, dict):
                errors.append(f"idempotency_records.{record_key} must be an object")
                continue
            record_idempotency_key = record.get("idempotency_key")
            if record_idempotency_key != record_key:
                errors.append(f"idempotency_records.{record_key}.idempotency_key must match record key")
            for field_name in ("idempotency_key", "command_key", "step_id", "stage_id", "status"):
                if field_name not in record:
                    errors.append(f"idempotency_records.{record_key}.{field_name} is required")
            step_id = record.get("step_id")
            if not isinstance(step_id, int) or not 0 <= step_id <= 18:
                errors.append(f"idempotency_records.{record_key}.step_id must be 0..18")
            stage_id = record.get("stage_id")
            if stage_id not in STAGE_IDS:
                errors.append(f"idempotency_records.{record_key}.stage_id is invalid")
            status = record.get("status")
            if status not in ALLOWED_IDEMPOTENCY_STATUSES:
                errors.append(f"idempotency_records.{record_key}.status is invalid")
            artifact_refs = record.get("artifact_refs", {})
            if artifact_refs is not None and not isinstance(artifact_refs, dict):
                errors.append(f"idempotency_records.{record_key}.artifact_refs must be an object")
    if not isinstance(state.history, list):
        errors.append("history must be a list")
    return errors


def build_idempotency_key(
    state: RunbookState,
    command_key: str,
    artifact_refs: dict[str, str] | None = None,
) -> str:
    parts = [state.runbook_day_id, str(command_key)]
    for artifact_name, artifact_ref in sorted((artifact_refs or {}).items()):
        parts.append(f"{_safe_id_part(artifact_name)}={_safe_id_part(artifact_ref)}")
    return ":".join(parts)


def has_idempotency_record(state: RunbookState, idempotency_key: str) -> bool:
    return idempotency_key in state.idempotency_records


def assert_not_duplicate(state: RunbookState, idempotency_key: str) -> None:
    if has_idempotency_record(state, idempotency_key):
        raise ValueError("duplicate_idempotency_key")


def record_idempotency_key(
    state: RunbookState,
    command_key: str,
    step_id: int,
    stage_id: str,
    artifact_refs: dict[str, str] | None = None,
    status: str = "RECORDED",
    result_ref: str | None = None,
    notes: str = "Reserved/recorded before duplicate-sensitive command execution.",
) -> RunbookState:
    if stage_id not in STAGE_IDS:
        raise ValueError(f"invalid stage_id: {stage_id}")
    if status not in ALLOWED_IDEMPOTENCY_STATUSES:
        raise ValueError(f"invalid idempotency status: {status}")
    idempotency_key = build_idempotency_key(state, command_key, artifact_refs)
    assert_not_duplicate(state, idempotency_key)
    record = {
        "idempotency_key": idempotency_key,
        "command_key": command_key,
        "step_id": step_id,
        "stage_id": stage_id,
        "status": status,
        "created_at": _now_iso(state.timezone),
        "artifact_refs": dict(artifact_refs or {}),
        "result_ref": result_ref,
        "notes": notes,
    }
    next_records = dict(state.idempotency_records)
    next_records[idempotency_key] = record
    return replace(state, updated_at=record["created_at"], idempotency_records=next_records)


def get_state_path(workspace: Path) -> Path:
    return workspace / STATE_FILENAME


def init_state_file(
    workspace: Path,
    account_id: str,
    data_date: str,
    trade_date: str,
    timezone: str = "Asia/Seoul",
) -> tuple[str, RunbookState]:
    path = get_state_path(workspace)
    requested_state = create_initial_state(account_id, data_date, trade_date, timezone)
    if not path.exists():
        save_state(requested_state, path)
        return "CREATED", requested_state

    existing_state = load_state(path)
    if context_matches_state(existing_state, account_id, data_date, trade_date):
        return "EXISTING", existing_state
    raise ValueError("context_mismatch_existing_runbook_state")


def _print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _parse_artifact_refs(values: Sequence[str] | None) -> dict[str, str]:
    artifact_refs: dict[str, str] = {}
    for value in values or ():
        if "=" not in value:
            raise ValueError(f"artifact must be name=value: {value}")
        name, artifact_ref = value.split("=", 1)
        if not name or not artifact_ref:
            raise ValueError(f"artifact must be name=value: {value}")
        artifact_refs[name] = artifact_ref
    return artifact_refs


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only runbook_state schema utility")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create an initial runbook_state.json if absent")
    init_parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    init_parser.add_argument("--account-id", required=True)
    init_parser.add_argument("--data-date", required=True)
    init_parser.add_argument("--trade-date", required=True)
    init_parser.add_argument("--timezone", default="Asia/Seoul")

    show_parser = subparsers.add_parser("show", help="Show current runbook_state.json")
    show_parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)

    validate_parser = subparsers.add_parser("validate", help="Validate current runbook_state.json")
    validate_parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)

    key_parser = subparsers.add_parser("idempotency-key", help="Build an idempotency key")
    key_parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    key_parser.add_argument("--command-key", required=True)
    key_parser.add_argument("--artifact", action="append", default=[])

    check_parser = subparsers.add_parser("check-idempotency", help="Check whether an idempotency key exists")
    check_parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    check_parser.add_argument("--command-key", required=True)
    check_parser.add_argument("--artifact", action="append", default=[])

    record_parser = subparsers.add_parser("record-idempotency", help="Record an idempotency key without command execution")
    record_parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    record_parser.add_argument("--command-key", required=True)
    record_parser.add_argument("--step-id", type=int, required=True)
    record_parser.add_argument("--stage-id", required=True)
    record_parser.add_argument("--artifact", action="append", default=[])

    args = parser.parse_args(argv)
    if args.command == "init":
        try:
            result, state = init_state_file(
                args.workspace,
                args.account_id,
                args.data_date,
                args.trade_date,
                args.timezone,
            )
        except ValueError as exc:
            _print_json({"runner_result": "BLOCKED", "reason": str(exc)})
            return 1
        errors = validate_state(state)
        if errors:
            _print_json({"runner_result": "FAIL", "result": result, "errors": errors})
            return 1
        _print_json({"runner_result": "PASS", "result": result, "state": state.to_dict()})
        return 0
    if args.command == "show":
        state = load_state(get_state_path(args.workspace))
        _print_json(state.to_dict())
        return 0
    if args.command == "validate":
        state = load_state(get_state_path(args.workspace))
        errors = validate_state(state)
        if errors:
            _print_json({"runner_result": "FAIL", "errors": errors})
            return 1
        _print_json({"runner_result": "PASS", "runbook_day_id": state.runbook_day_id})
        return 0
    if args.command == "idempotency-key":
        state = load_state(get_state_path(args.workspace))
        try:
            artifact_refs = _parse_artifact_refs(args.artifact)
        except ValueError as exc:
            _print_json({"runner_result": "FAIL", "reason": str(exc)})
            return 1
        key = build_idempotency_key(state, args.command_key, artifact_refs)
        _print_json({"runner_result": "PASS", "idempotency_key": key})
        return 0
    if args.command == "check-idempotency":
        state = load_state(get_state_path(args.workspace))
        try:
            artifact_refs = _parse_artifact_refs(args.artifact)
        except ValueError as exc:
            _print_json({"runner_result": "FAIL", "reason": str(exc)})
            return 1
        key = build_idempotency_key(state, args.command_key, artifact_refs)
        exists = has_idempotency_record(state, key)
        _print_json(
            {
                "runner_result": "BLOCKED" if exists else "PASS",
                "reason": "duplicate_idempotency_key" if exists else "idempotency_key_available",
                "idempotency_key": key,
            }
        )
        return 1 if exists else 0
    if args.command == "record-idempotency":
        path = get_state_path(args.workspace)
        state = load_state(path)
        try:
            artifact_refs = _parse_artifact_refs(args.artifact)
        except ValueError as exc:
            _print_json({"runner_result": "FAIL", "reason": str(exc)})
            return 1
        key = build_idempotency_key(state, args.command_key, artifact_refs)
        try:
            next_state = record_idempotency_key(
                state,
                args.command_key,
                args.step_id,
                args.stage_id,
                artifact_refs,
            )
        except ValueError as exc:
            _print_json({"runner_result": "BLOCKED", "reason": str(exc), "idempotency_key": key})
            return 1
        save_state(next_state, path)
        _print_json({"runner_result": "PASS", "idempotency_key": key})
        return 0
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

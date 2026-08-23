from __future__ import annotations

import csv
import hashlib
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from core.paper_account_paths import build_paper_account_paths
from core.runbook_calendar import (
    CALENDAR_SCHEMA_VERSION,
    DEFAULT_CALENDAR_PATH,
    CalendarCoverageError,
    MarketCalendar,
    load_market_calendar,
)
from core import runbook_retirement
from scripts import runbook_state


SCHEMA_VERSION = "runbook_recovery.v1"
RECOVERY_DIRNAME = "runbook_recoveries"
DISPOSITION = "RECOVERY_EXCLUDED"
TARGET_EVIDENCE_DIRS = (
    "artifacts",
    "command_runs",
    "stage_runs",
    "gate_runs",
    "reconciliation_runs",
    "verification_runs",
    "completion_manifests",
    "no_action_runs",
)


def default_calendar() -> MarketCalendar:
    return load_market_calendar()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def recovery_path(workspace: Path, source_runbook_day_id: str) -> Path:
    return Path(workspace) / RECOVERY_DIRNAME / f"{source_runbook_day_id}.json"


def _blocked(reason: str, blockers: list[str] | None = None, *, mode: str) -> dict[str, Any]:
    return {
        "runner_result": "BLOCKED",
        "mode": mode,
        "reason": reason,
        "blockers": blockers or [reason],
        "eligible": False,
        "next_required_action": "Resolve every blocker before continuing recovery.",
    }


def _is_paper_test(account_id: str) -> bool:
    lowered = account_id.lower()
    return "paper" in lowered or "test" in lowered


def _target_exists(workspace: Path, runbook_day_id: str) -> bool:
    if runbook_state.get_state_path_for_runbook_day_id(workspace, runbook_day_id).exists():
        return True
    return any((workspace / dirname / runbook_day_id).exists() for dirname in TARGET_EVIDENCE_DIRS)


def _target_state_status(
    workspace: Path,
    account_id: str,
    data_date: str,
    trade_date: str,
    runbook_day_id: str,
) -> tuple[str, list[str]]:
    state_path = runbook_state.get_state_path_for_runbook_day_id(workspace, runbook_day_id)
    evidence_exists = any(
        (workspace / dirname / runbook_day_id).exists() for dirname in TARGET_EVIDENCE_DIRS
    )
    if not state_path.exists():
        return ("CONFLICT", ["target_artifact_exists_without_state"]) if evidence_exists else ("ABSENT", [])
    try:
        state = runbook_state.load_state(state_path)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        return "CONFLICT", [f"target_state_invalid:{type(exc).__name__}"]
    if not runbook_state.context_matches_state(state, account_id, data_date, trade_date):
        return "CONFLICT", ["target_state_context_mismatch"]
    return "PRESENT", []


def _calendar_gap(calendar: MarketCalendar, start: date, end: date) -> list[str]:
    if end < start:
        raise ValueError("restart_data_date_precedes_source_trade_date")
    values: list[str] = []
    current = start
    while current <= end:
        if calendar.is_trading_day(current):
            values.append(current.isoformat())
        current += timedelta(days=1)
    return values


def _execution_gap(
    account_id: str,
    gap_dates: list[str],
) -> tuple[Path, str, list[dict[str, str]], list[str]]:
    blockers: list[str] = []
    try:
        paths = build_paper_account_paths(account_id, create=False)
        ledger_path = paths.execution_log_path.resolve(strict=False)
    except (OSError, ValueError) as exc:
        return Path("."), "", [], [f"execution_ledger_path_invalid:{type(exc).__name__}"]
    if not ledger_path.is_file():
        return ledger_path, "", [], ["execution_ledger_missing"]
    try:
        with ledger_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or "date" not in reader.fieldnames:
                return ledger_path, sha256_file(ledger_path), [], ["execution_ledger_date_column_missing"]
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        return ledger_path, "", [], [f"execution_ledger_invalid:{type(exc).__name__}"]
    gap_set = set(gap_dates)
    conflicts: list[dict[str, str]] = []
    for index, row in enumerate(rows, start=2):
        value = str(row.get("date") or "").strip()
        try:
            normalized = date.fromisoformat(value).isoformat()
        except ValueError:
            blockers.append(f"execution_ledger_invalid_date:row_{index}")
            continue
        if normalized in gap_set:
            conflicts.append(dict(row))
    if conflicts:
        blockers.append(f"execution_gap_not_empty:{len(conflicts)}")
    return ledger_path, sha256_file(ledger_path), conflicts, blockers


def _raw_classification(workspace: Path, record: Any) -> str:
    from core import runbook_day_rollover

    if runbook_day_rollover._is_standard_completed(workspace, record.state):
        return "STANDARD_COMPLETED"
    if runbook_day_rollover._is_legacy_completed(workspace, record):
        return "LEGACY_COMPLETED"
    retirement = runbook_retirement.validate_retirement_evidence(
        workspace, record.path, record.state
    )
    return "RETIRED" if retirement["valid"] else "ACTIVE_INCOMPLETE"


def _load_recovery_context(
    workspace: Path,
    account_id: str,
    source_runbook_day_id: str,
) -> tuple[Any | None, list[Any], list[Any], list[str]]:
    from core import runbook_day_rollover

    records, blockers = runbook_day_rollover._load_account_states(workspace, account_id)
    if blockers:
        return None, [], [], blockers
    source = next(
        (record for record in records if record.state.runbook_day_id == source_runbook_day_id),
        None,
    )
    raw = [(record, _raw_classification(workspace, record)) for record in records]
    active = [record for record, classification in raw if classification == "ACTIVE_INCOMPLETE"]
    completed = [
        record
        for record, classification in raw
        if classification in {"STANDARD_COMPLETED", "LEGACY_COMPLETED"}
    ]
    return source, active, completed, []


def _latest_completed(completed: list[Any]) -> tuple[Any | None, list[str]]:
    if not completed:
        return None, ["completed_runbook_day_not_found"]
    latest_date = max(record.state.frozen_context.trade_date for record in completed)
    latest = [record for record in completed if record.state.frozen_context.trade_date == latest_date]
    if len(latest) != 1:
        return None, [
            "latest_completed_runbook_day_ambiguous",
            *(f"candidate:{record.state.runbook_day_id}" for record in latest),
        ]
    return latest[0], []


def preview_recovery(
    workspace: str | Path,
    *,
    account_id: str,
    source_runbook_day_id: str,
    restart_data_date: str,
    restart_trade_date: str,
    reason: str,
    calendar: MarketCalendar,
    confirm_paper_test: bool,
    confirm_contaminated_incomplete: bool,
    confirm_no_real_trades: bool,
    confirm_gap_without_backfill: bool,
) -> dict[str, Any]:
    mode = "RECOVERY_PREVIEW"
    workspace_path = Path(workspace).resolve(strict=False)
    account_id = str(account_id or "").strip()
    source_runbook_day_id = str(source_runbook_day_id or "").strip()
    reason = str(reason or "").strip()
    blockers: list[str] = []
    if not workspace_path.is_dir():
        blockers.append("invalid_workspace")
    if not confirm_paper_test:
        blockers.append("paper_test_confirmation_required")
    if not _is_paper_test(account_id):
        blockers.append("paper_account_required")
    if not confirm_contaminated_incomplete:
        blockers.append("contaminated_incomplete_confirmation_required")
    if not confirm_no_real_trades:
        blockers.append("no_real_trades_confirmation_required")
    if not confirm_gap_without_backfill:
        blockers.append("gap_without_backfill_confirmation_required")
    if not reason:
        blockers.append("recovery_reason_required")
    try:
        restart_data = date.fromisoformat(str(restart_data_date))
        restart_trade = date.fromisoformat(str(restart_trade_date))
    except ValueError:
        return _blocked("recovery_context_invalid", [*blockers, "restart_date_invalid"], mode=mode)
    if blockers:
        return _blocked("recovery_confirmation_or_input_invalid", blockers, mode=mode)
    if recovery_path(workspace_path, source_runbook_day_id).exists():
        return _blocked("recovery_authorization_already_exists", mode=mode)

    source, active, completed, state_blockers = _load_recovery_context(
        workspace_path, account_id, source_runbook_day_id
    )
    blockers.extend(state_blockers)
    if source is None:
        blockers.append("source_runbook_not_found")
    if len(active) != 1:
        blockers.append("active_runbook_day_count_must_equal_one")
    elif source is not None and active[0].state.runbook_day_id != source_runbook_day_id:
        blockers.append("source_is_not_the_only_active_runbook")
    latest, latest_blockers = _latest_completed(completed)
    blockers.extend(latest_blockers)
    if source is not None:
        if source.state.frozen_context.account_id != account_id:
            blockers.append("source_account_mismatch")
        if _raw_classification(workspace_path, source) != "ACTIVE_INCOMPLETE":
            blockers.append("source_not_active_incomplete")
        zero_progress = runbook_retirement.assess_zero_progress(
            workspace_path, source.path, source.state
        )
        if zero_progress["eligible"]:
            blockers.append("source_is_zero_progress_retirement_candidate")
    try:
        if not calendar.is_trading_day(restart_data):
            blockers.append("restart_data_date_not_trading_day")
        if not calendar.is_trading_day(restart_trade):
            blockers.append("restart_trade_date_not_trading_day")
        if calendar.next_trading_day(restart_data) != restart_trade:
            blockers.append("restart_trade_date_not_next_trading_day")
    except CalendarCoverageError as exc:
        blockers.append(str(exc))
    if source is not None and restart_data <= date.fromisoformat(source.state.frozen_context.trade_date):
        blockers.append("restart_data_date_not_after_source_trade_date")
    if latest is not None and restart_data <= date.fromisoformat(latest.state.frozen_context.trade_date):
        blockers.append("restart_data_date_not_after_latest_completed_trade_date")
    try:
        gap_dates = (
            _calendar_gap(
                calendar,
                date.fromisoformat(source.state.frozen_context.trade_date),
                restart_data,
            )
            if source is not None
            else []
        )
    except (ValueError, CalendarCoverageError) as exc:
        blockers.append(str(exc))
        gap_dates = []
    ledger_path, ledger_sha256, conflicts, ledger_blockers = _execution_gap(account_id, gap_dates)
    blockers.extend(ledger_blockers)
    target_id = runbook_state.get_runbook_day_id(
        account_id, restart_data.isoformat(), restart_trade.isoformat()
    )
    if _target_exists(workspace_path, target_id):
        blockers.append("recovery_target_already_exists")
    if blockers:
        return _blocked("recovery_not_eligible", blockers, mode=mode)

    assert source is not None and latest is not None
    return {
        "runner_result": "PASS",
        "mode": mode,
        "eligible": True,
        "account_id": account_id,
        "source_runbook_day_id": source_runbook_day_id,
        "source_frozen_context": source.state.to_dict()["frozen_context"],
        "source_state_ref": source.path.relative_to(workspace_path).as_posix(),
        "source_state_sha256": sha256_file(source.path),
        "latest_completed": {
            "runbook_day_id": latest.state.runbook_day_id,
            "frozen_context": latest.state.to_dict()["frozen_context"],
            "state_ref": latest.path.relative_to(workspace_path).as_posix(),
            "state_sha256": sha256_file(latest.path),
        },
        "no_trade_interval": {
            "start_date": gap_dates[0],
            "end_date": gap_dates[-1],
            "trading_dates": gap_dates,
            "execution_count": len(conflicts),
            "ledger_ref": str(ledger_path),
            "ledger_sha256_at_authorization": ledger_sha256,
        },
        "restart": {
            "data_date": restart_data.isoformat(),
            "trade_date": restart_trade.isoformat(),
            "runbook_day_id": target_id,
        },
        "calendar": {
            "schema_version": CALENDAR_SCHEMA_VERSION,
            "market": calendar.market,
            "timezone": calendar.timezone,
            "coverage_start": calendar.coverage_start.isoformat(),
            "coverage_end": calendar.coverage_end.isoformat(),
            "calendar_ref": str(Path(DEFAULT_CALENDAR_PATH).resolve(strict=False)),
            "calendar_sha256": sha256_file(Path(DEFAULT_CALENDAR_PATH)),
        },
        "reason": reason,
        "required_confirmations": {
            "paper_test": True,
            "contaminated_incomplete": True,
            "no_real_trades": True,
            "gap_without_backfill": True,
        },
        "blockers": [],
        "next_required_action": "Review the preview, then run authorize with the exact same inputs.",
    }


def _evidence_from_preview(preview: dict[str, Any], timezone: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "account_id": preview["account_id"],
        "source_runbook_day_id": preview["source_runbook_day_id"],
        "source_frozen_context": preview["source_frozen_context"],
        "source_state_ref": preview["source_state_ref"],
        "source_state_sha256": preview["source_state_sha256"],
        "disposition": DISPOSITION,
        "reason": preview["reason"],
        "latest_completed": preview["latest_completed"],
        "no_trade_interval": preview["no_trade_interval"],
        "restart": preview["restart"],
        "calendar": preview["calendar"],
        "operator_confirmations": preview["required_confirmations"],
        "authorized_at": datetime.now(ZoneInfo(timezone)).isoformat(),
    }


def authorize_recovery(workspace: str | Path, **kwargs: Any) -> dict[str, Any]:
    workspace_path = Path(workspace).resolve(strict=False)
    preview = preview_recovery(workspace_path, **kwargs)
    if preview["runner_result"] != "PASS":
        return {**preview, "mode": "RECOVERY_AUTHORIZE", "authorized": False}
    state_path = workspace_path / preview["source_state_ref"]
    if sha256_file(state_path) != preview["source_state_sha256"]:
        return _blocked(
            "source_state_changed_before_authorization",
            mode="RECOVERY_AUTHORIZE",
        )
    state = runbook_state.load_state(state_path)
    evidence = _evidence_from_preview(preview, state.timezone)
    path = recovery_path(workspace_path, preview["source_runbook_day_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        return _blocked("recovery_authorization_already_exists", mode="RECOVERY_AUTHORIZE")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(evidence, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            path.unlink()
        except OSError:
            pass
        raise
    return {
        "runner_result": "PASS",
        "mode": "RECOVERY_AUTHORIZE",
        "eligible": True,
        "authorized": True,
        "source_runbook_day_id": preview["source_runbook_day_id"],
        "disposition": DISPOSITION,
        "restart": preview["restart"],
        "evidence_path": str(path),
        "evidence_sha256": sha256_file(path),
        "blockers": [],
        "next_required_action": "Run recovery status, then the read-only rollover preview.",
    }


def _load_json_object(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, [f"recovery_evidence_invalid_json:{type(exc).__name__}"]
    if not isinstance(value, dict):
        return None, ["recovery_evidence_must_be_object"]
    return value, []


def validate_recovery_evidence(
    workspace: str | Path,
    source_state_path: Path,
    source_state: runbook_state.RunbookState,
    calendar: MarketCalendar,
) -> dict[str, Any]:
    from core import runbook_day_rollover

    workspace_path = Path(workspace).resolve(strict=False)
    path = recovery_path(workspace_path, source_state.runbook_day_id)
    if not path.is_file():
        return {"valid": False, "exists": False, "path": path, "blockers": ["recovery_evidence_missing"]}
    payload, blockers = _load_json_object(path)
    if payload is None:
        return {"valid": False, "exists": True, "path": path, "blockers": blockers}
    expected_context = source_state.to_dict()["frozen_context"]
    expected_ref = source_state_path.relative_to(workspace_path).as_posix()
    expected_values = {
        "schema_version": SCHEMA_VERSION,
        "account_id": source_state.frozen_context.account_id,
        "source_runbook_day_id": source_state.runbook_day_id,
        "source_frozen_context": expected_context,
        "source_state_ref": expected_ref,
        "disposition": DISPOSITION,
    }
    for field, expected in expected_values.items():
        if payload.get(field) != expected:
            blockers.append(f"recovery_{field}_mismatch")
    if payload.get("source_state_sha256") != sha256_file(source_state_path):
        blockers.append("recovery_source_state_sha256_mismatch")
    if not isinstance(payload.get("reason"), str) or not payload["reason"].strip():
        blockers.append("recovery_reason_missing")
    confirmations = payload.get("operator_confirmations")
    required = {"paper_test", "contaminated_incomplete", "no_real_trades", "gap_without_backfill"}
    if not isinstance(confirmations, dict) or any(confirmations.get(key) is not True for key in required):
        blockers.append("recovery_confirmations_invalid")
    try:
        authorized_at = datetime.fromisoformat(str(payload.get("authorized_at") or ""))
        if authorized_at.tzinfo is None:
            raise ValueError
    except ValueError:
        blockers.append("recovery_authorized_at_invalid")
    calendar_payload = payload.get("calendar")
    if not isinstance(calendar_payload, dict):
        blockers.append("recovery_calendar_invalid")
    else:
        expected_calendar = {
            "schema_version": CALENDAR_SCHEMA_VERSION,
            "market": calendar.market,
            "timezone": calendar.timezone,
            "coverage_start": calendar.coverage_start.isoformat(),
            "coverage_end": calendar.coverage_end.isoformat(),
        }
        for field, expected in expected_calendar.items():
            if calendar_payload.get(field) != expected:
                blockers.append(f"recovery_calendar_{field}_mismatch")
        if calendar_payload.get("calendar_sha256") != sha256_file(Path(DEFAULT_CALENDAR_PATH)):
            blockers.append("recovery_calendar_sha256_mismatch")
    latest = payload.get("latest_completed")
    if not isinstance(latest, dict):
        blockers.append("recovery_latest_completed_invalid")
    else:
        latest_ref = latest.get("state_ref")
        if not isinstance(latest_ref, str):
            blockers.append("recovery_latest_completed_state_ref_invalid")
        else:
            latest_path = workspace_path / latest_ref
            try:
                latest_state = runbook_state.load_state(latest_path)
                raw = json.loads(latest_path.read_text(encoding="utf-8"))
                record = runbook_day_rollover.StateRecord(
                    latest_path, latest_state, dict(raw.get("stage_status") or {})
                )
                completed_valid = (
                    runbook_day_rollover._is_standard_completed(workspace_path, latest_state)
                    or runbook_day_rollover._is_legacy_completed(workspace_path, record)
                )
                if not completed_valid:
                    blockers.append("recovery_latest_completed_no_longer_valid")
                if latest.get("runbook_day_id") != latest_state.runbook_day_id:
                    blockers.append("recovery_latest_completed_id_mismatch")
                if latest.get("frozen_context") != latest_state.to_dict()["frozen_context"]:
                    blockers.append("recovery_latest_completed_context_mismatch")
                if latest.get("state_sha256") != sha256_file(latest_path):
                    blockers.append("recovery_latest_completed_sha256_mismatch")
            except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
                blockers.append("recovery_latest_completed_state_invalid")
    restart = payload.get("restart")
    if not isinstance(restart, dict):
        blockers.append("recovery_restart_invalid")
        restart = {}
    try:
        restart_data = date.fromisoformat(str(restart.get("data_date") or ""))
        restart_trade = date.fromisoformat(str(restart.get("trade_date") or ""))
        expected_target_id = runbook_state.get_runbook_day_id(
            source_state.frozen_context.account_id,
            restart_data.isoformat(),
            restart_trade.isoformat(),
        )
        if restart.get("runbook_day_id") != expected_target_id:
            blockers.append("recovery_restart_runbook_day_id_mismatch")
        if not calendar.is_trading_day(restart_data):
            blockers.append("recovery_restart_data_date_not_trading_day")
        if not calendar.is_trading_day(restart_trade):
            blockers.append("recovery_restart_trade_date_not_trading_day")
        if calendar.next_trading_day(restart_data) != restart_trade:
            blockers.append("recovery_restart_pair_invalid")
    except (ValueError, CalendarCoverageError):
        blockers.append("recovery_restart_dates_invalid")
        restart_data = restart_trade = None
        expected_target_id = str(restart.get("runbook_day_id") or "")
    interval = payload.get("no_trade_interval")
    if not isinstance(interval, dict) or not isinstance(interval.get("trading_dates"), list):
        blockers.append("recovery_no_trade_interval_invalid")
        gap_dates: list[str] = []
    else:
        gap_dates = [str(item) for item in interval["trading_dates"]]
        try:
            expected_gap = _calendar_gap(
                calendar,
                date.fromisoformat(source_state.frozen_context.trade_date),
                restart_data,
            ) if restart_data is not None else []
        except (ValueError, CalendarCoverageError):
            expected_gap = []
        if gap_dates != expected_gap:
            blockers.append("recovery_gap_dates_mismatch")
        if gap_dates and (
            interval.get("start_date") != gap_dates[0]
            or interval.get("end_date") != gap_dates[-1]
        ):
            blockers.append("recovery_gap_bounds_mismatch")
        if interval.get("execution_count") != 0:
            blockers.append("recovery_execution_count_invalid")
    _, _, conflicts, ledger_blockers = _execution_gap(
        source_state.frozen_context.account_id, gap_dates
    )
    blockers.extend(f"recovery_{item}" for item in ledger_blockers)
    if conflicts:
        blockers.append("recovery_execution_contradiction")
    target_status, target_blockers = _target_state_status(
        workspace_path,
        source_state.frozen_context.account_id,
        restart_data.isoformat() if restart_data else "",
        restart_trade.isoformat() if restart_trade else "",
        expected_target_id,
    )
    blockers.extend(f"recovery_{item}" for item in target_blockers)
    return {
        "valid": not blockers,
        "exists": True,
        "path": path,
        "payload": payload,
        "blockers": blockers,
        "consumed": target_status == "PRESENT",
        "target_status": target_status,
    }


def recovery_status(
    workspace: str | Path,
    *,
    account_id: str,
    source_runbook_day_id: str,
    calendar: MarketCalendar,
) -> dict[str, Any]:
    workspace_path = Path(workspace).resolve(strict=False)
    source, _, _, blockers = _load_recovery_context(
        workspace_path, account_id, source_runbook_day_id
    )
    if source is None:
        return _blocked("source_runbook_not_found", blockers or None, mode="RECOVERY_STATUS")
    validation = validate_recovery_evidence(
        workspace_path, source.path, source.state, calendar
    )
    classification = DISPOSITION if validation["valid"] else _raw_classification(workspace_path, source)
    payload = validation.get("payload") or {}
    return {
        "runner_result": "PASS" if not validation["exists"] or validation["valid"] else "BLOCKED",
        "mode": "RECOVERY_STATUS",
        "account_id": account_id,
        "source_runbook_day_id": source_runbook_day_id,
        "source_state_sha256": sha256_file(source.path),
        "current_classification": classification,
        "sidecar_exists": validation["exists"],
        "sidecar_valid": validation["valid"],
        "disposition": payload.get("disposition"),
        "restart": payload.get("restart"),
        "consumed": bool(validation.get("consumed")),
        "blockers": validation["blockers"] if validation["exists"] else [],
        "next_required_action": (
            "Run a recovery preview."
            if not validation["exists"]
            else "Use the exact authorized restart pair." if not validation.get("consumed")
            else "Continue the existing target lifecycle; do not reuse the authorization."
        ),
    }


def assert_initialization_allowed(
    workspace: str | Path,
    account_id: str,
    data_date: str,
    trade_date: str,
    calendar: MarketCalendar,
) -> None:
    from core import runbook_day_rollover

    workspace_path = Path(workspace).resolve(strict=False)
    records, blockers = runbook_day_rollover._load_account_states(workspace_path, account_id)
    if blockers == ["runbook_states_directory_not_found"]:
        return
    if blockers:
        raise ValueError("initialization_invalid_runbook_state")
    if not records:
        return
    classified = [
        (record, runbook_day_rollover.classify_state(workspace_path, record, calendar))
        for record in records
    ]
    active = [record for record, item in classified if item["classification"] == "ACTIVE_INCOMPLETE"]
    progressed_active = [
        record
        for record in active
        if not runbook_retirement.assess_zero_progress(workspace_path, record.path, record.state)["eligible"]
    ]
    recovery_items = [
        (record, item)
        for record, item in classified
        if item["classification"] == DISPOSITION
    ]
    requested_id = runbook_state.get_runbook_day_id(account_id, data_date, trade_date)
    if progressed_active:
        raise ValueError("active_runbook_day_exists")
    if not recovery_items:
        return
    if len(recovery_items) != 1:
        raise ValueError("multiple_recovery_authorizations")
    source = recovery_items[0][0]
    validation = validate_recovery_evidence(
        workspace_path, source.path, source.state, calendar
    )
    if not validation["valid"]:
        raise ValueError("recovery_authorization_invalid")
    if validation["consumed"]:
        if active:
            raise ValueError("active_runbook_day_exists")
        rollover = runbook_day_rollover.preview_rollover(
            workspace_path,
            account_id,
            calendar,
            confirm_paper_test=True,
        )
        if (
            rollover.get("runner_result") != "PASS"
            or rollover.get("rollover_mode") == "RECOVERY"
        ):
            raise ValueError("recovery_authorization_already_consumed")
        requested_context = {
            "account_id": account_id,
            "data_date": data_date,
            "trade_date": trade_date,
            "runbook_day_id": requested_id,
        }
        normal_next_context = {
            "account_id": rollover.get("account_id"),
            "data_date": rollover.get("next_data_date"),
            "trade_date": rollover.get("next_trade_date"),
            "runbook_day_id": rollover.get("next_runbook_day_id"),
        }
        if requested_context != normal_next_context:
            raise ValueError("recovery_target_mismatch")
        return
    if validation["payload"]["restart"]["runbook_day_id"] != requested_id:
        raise ValueError("recovery_target_mismatch")

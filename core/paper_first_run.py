from __future__ import annotations

import copy
import hashlib
import json
import os
import stat
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from core.paper_account_binding import assert_binding_matches
from core.paper_account_fresh import validate_prepare_first_request
from core.paper_account_paths import PaperAccountPaths, build_paper_account_paths
from core.paper_account_profile import (
    VERSIONED_ACCOUNT_PROFILE_SCHEMA,
    load_paper_account_profiles,
    resolve_paper_account_profile,
)
from core.paper_account_bootstrap import normalize_bootstrap_date
from core.runbook_calendar import MarketCalendar, load_market_calendar
from core.runbook_day_prep import read_account_local, read_runbook_day_local, write_runbook_day_local_exact
from core.stage_a_asof_contract import sha256_payload
from scripts import runbook_state


PREPARE_EVIDENCE_SCHEMA = "paper_first_run_prepare.v1"
PREPARE_IDENTITY_SCHEMA = "paper_first_run_identity.v1"
PREPARE_LIFECYCLE_DIRNAME = "lifecycle"
PREPARE_EVIDENCE_FILENAME = "prepare_first_run.json"
PREPARE_LOCK_FILENAME = ".prepare_first_run.lock"


def _assert_regular_path(path: Path) -> None:
    """Inspect lexical ancestors before resolving or reading any artifact."""
    for part in reversed((path.absolute(), *path.absolute().parents)):
        if part.is_symlink():
            raise ValueError(f"prepare_path_link:{part.name}")
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if (getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
                or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode))):
            raise ValueError(f"prepare_path_unsafe:{part.name}")


def _check_tree_paths(root: Path) -> None:
    _assert_regular_path(root)
    if root.is_dir():
        for child in root.iterdir():
            _check_tree_paths(child)


def _check_prepare_paths(workspace: Path, account_paths: PaperAccountPaths,
                         day_path: Path | None = None) -> None:
    from core import failed_no_trade_closure, operational_gap_recovery, runbook_recovery, runbook_retirement
    from core.runbook_day_rollover import DUPLICATE_DIRS

    _assert_regular_path(workspace)
    _check_tree_paths(account_paths.root)
    directories = set(DUPLICATE_DIRS) | set(runbook_recovery.TARGET_EVIDENCE_DIRS) | {
        runbook_state.STATE_DIRNAME, runbook_recovery.RECOVERY_DIRNAME,
        runbook_retirement.RETIREMENT_DIRNAME, failed_no_trade_closure.CLOSURE_DIRNAME,
        operational_gap_recovery.GENERIC_EVIDENCE_DIRNAME,
    }
    for dirname in directories:
        directory = workspace / dirname
        _check_tree_paths(directory)
        if directory.exists() and not directory.is_dir():
            raise ValueError(f"prepare_history_directory_invalid:{dirname}")
    _assert_regular_path(workspace / runbook_state.STATE_FILENAME)
    state_dir = workspace / runbook_state.STATE_DIRNAME
    if state_dir.exists():
        if not state_dir.is_dir():
            raise ValueError("prepare_state_directory_invalid")
        for item in state_dir.iterdir():
            if not item.is_file() or item.suffix != ".json":
                raise ValueError("prepare_unexpected_state_artifact")
            payload = json.loads(item.read_text(encoding="utf-8-sig"))
            if not isinstance(payload, dict) or not isinstance(payload.get("frozen_context"), dict):
                raise ValueError("prepare_unattributable_state")
            if not payload["frozen_context"].get("account_id"):
                raise ValueError("prepare_unattributable_state")
    evidence = prepare_evidence_path(account_paths)
    if evidence.parent.exists():
        if not evidence.parent.is_dir():
            raise ValueError("prepare_lifecycle_directory_invalid")
        if any(p != evidence or not p.is_file() for p in evidence.parent.iterdir()):
            raise ValueError("prepare_unexpected_lifecycle_artifact")
    if day_path is not None:
        _assert_regular_path(day_path)
        temp = day_path.with_name(day_path.name + ".tmp")
        _assert_regular_path(temp)
        if temp.exists():
            raise ValueError("prepare_context_temp_residue")


@contextmanager
def _prepare_write_lock(account_paths: PaperAccountPaths):
    """Account-local OS lifetime lock; no timeout or stale-file reclamation."""
    path = account_paths.root / PREPARE_LOCK_FILENAME
    _assert_regular_path(path)
    if os.name == "nt":
        # Exclusive create, as in recovery authorization. O_TEMPORARY makes the
        # kernel remove only our own lock when the handle closes, even on crash.
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_TEMPORARY, 0o600)
    else:
        import fcntl

        # Lock the existing canonical directory, avoiding persistent lock-file
        # artifacts or unlink/inode races. The OS releases flock on process exit.
        descriptor = os.open(account_paths.root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            os.close(descriptor)
            raise
    try:
        yield
    finally:
        os.close(descriptor)


def _has_lifecycle_disposition(workspace: Path, account_id: str, day_id: str) -> bool:
    from core import failed_no_trade_closure, operational_gap_recovery, runbook_recovery, runbook_retirement
    from core.paper_account_fresh import _account_ids
    for directory in (runbook_retirement.RETIREMENT_DIRNAME, runbook_recovery.RECOVERY_DIRNAME,
                      failed_no_trade_closure.CLOSURE_DIRNAME, operational_gap_recovery.GENERIC_EVIDENCE_DIRNAME):
        root = workspace / directory
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            # A disposition is owned by its existing lifecycle. Prepare never
            # reactivates it, including malformed or unattributable evidence.
            if path.stem == day_id or path.suffix != ".json":
                return True
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            owners = _account_ids(payload)
            if not owners or account_id in owners:
                return True
    return False


def prepare_evidence_path(account_paths: PaperAccountPaths) -> Path:
    return account_paths.root / PREPARE_LIFECYCLE_DIRNAME / PREPARE_EVIDENCE_FILENAME


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _binding_refs(binding: dict[str, Any]) -> dict[str, dict[str, str]]:
    semantics = binding["semantics"]
    return {
        kind: copy.deepcopy(semantics[kind]["reference"])
        for kind in ("strategy", "universe")
    }


def build_prepare_identity(
    *,
    account_id: str,
    data_date: str,
    trade_date: str,
    runbook_day_id: str,
    binding: dict[str, Any],
    bootstrap: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": PREPARE_IDENTITY_SCHEMA,
        "account_id": account_id,
        "data_date": data_date,
        "trade_date": trade_date,
        "runbook_day_id": runbook_day_id,
        "binding_refs": _binding_refs(binding),
        "binding_digest": binding["digest"],
        "bootstrap_identity_summary": {
            "currency": bootstrap["currency"],
            "initial_cash": bootstrap["initial_cash"],
            "initial_positions_identity": bootstrap["initial_positions_identity"],
        },
        "bootstrap_hashes": dict(bootstrap["artifact_hashes"]),
    }


def _evidence_payload(
    identity: dict[str, Any],
    *,
    state_ref: str,
    timezone: str,
) -> dict[str, Any]:
    return {
        "schema_version": PREPARE_EVIDENCE_SCHEMA,
        "account_id": identity["account_id"],
        "data_date": identity["data_date"],
        "trade_date": identity["trade_date"],
        "runbook_day_id": identity["runbook_day_id"],
        "binding_refs": copy.deepcopy(identity["binding_refs"]),
        "binding_digest": identity["binding_digest"],
        "bootstrap_identity_summary": copy.deepcopy(identity["bootstrap_identity_summary"]),
        "bootstrap_hashes": dict(identity["bootstrap_hashes"]),
        "prepare_identity": copy.deepcopy(identity),
        "prepare_identity_digest": sha256_payload(identity),
        "state_ref": state_ref,
        "created_at": datetime.now(ZoneInfo(timezone)).isoformat(),
    }


def _load_valid_evidence(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    required = {
        "schema_version", "account_id", "data_date", "trade_date", "runbook_day_id",
        "binding_refs", "binding_digest", "bootstrap_identity_summary", "bootstrap_hashes",
        "prepare_identity", "prepare_identity_digest", "state_ref", "created_at",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise ValueError("prepare_evidence_contract_invalid")
    if payload["schema_version"] != PREPARE_EVIDENCE_SCHEMA:
        raise ValueError("prepare_evidence_schema_invalid")
    identity = payload["prepare_identity"]
    if not isinstance(identity, dict) or identity.get("schema_version") != PREPARE_IDENTITY_SCHEMA:
        raise ValueError("prepare_identity_contract_invalid")
    if payload["prepare_identity_digest"] != sha256_payload(identity):
        raise ValueError("prepare_identity_digest_mismatch")
    mirrored = {
        "account_id", "data_date", "trade_date", "runbook_day_id", "binding_refs",
        "binding_digest", "bootstrap_identity_summary", "bootstrap_hashes",
    }
    if any(payload[field] != identity.get(field) for field in mirrored):
        raise ValueError("prepare_evidence_identity_mismatch")
    created_at = datetime.fromisoformat(str(payload["created_at"]))
    if created_at.tzinfo is None:
        raise ValueError("prepare_evidence_created_at_invalid")
    return payload


def _current_hashes(account_paths: PaperAccountPaths, names: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in names:
        candidate = account_paths.root / name
        if candidate.parent.resolve() != account_paths.root.resolve() or not candidate.is_file() or candidate.is_symlink():
            raise ValueError(f"bootstrap_artifact_invalid:{name}")
        result[name] = _sha256_file(candidate)
    return result


def _is_initial_ready(state: runbook_state.RunbookState) -> bool:
    return (
        state.current_stage == "A"
        and state.current_status == "READY"
        and state.last_completed_stage is None
        and state.last_completed_step is None
        and all(state.stage_status.get(stage_id) == "PENDING" for stage_id in runbook_state.STAGE_IDS)
        and not state.artifacts
        and not state.idempotency_records
        and not state.recovery_authorizations
        and not state.history
        and state.last_error is None
    )


def _matching_states(workspace: Path, account_id: str) -> tuple[list[Any], list[str]]:
    from core.runbook_day_rollover import _load_account_states

    records, errors = _load_account_states(workspace, account_id)
    return records, [error for error in errors if error != "runbook_states_directory_not_found"]


def _blocked(
    result: str,
    reason: str,
    *,
    account_id: str,
    data_date: str,
    trade_date: str | None,
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "runner_result": "BLOCKED",
        "result": result,
        "reason": reason,
        "blockers": blockers or [reason],
        "account_id": account_id,
        "data_date": data_date,
        "trade_date": trade_date,
    }


def _pass(
    result: str,
    identity: dict[str, Any],
    *,
    evidence_path: Path,
    state_path: Path,
    runbook_day_local_path: Path,
) -> dict[str, Any]:
    digest = (
        sha256_payload(identity)
        if identity.get("schema_version") == PREPARE_IDENTITY_SCHEMA
        else None
    )
    return {
        "runner_result": "PASS",
        "result": result,
        "account_id": identity["account_id"],
        "data_date": identity["data_date"],
        "trade_date": identity["trade_date"],
        "runbook_day_id": identity["runbook_day_id"],
        "prepare_identity_digest": digest,
        "prepare_evidence_path": str(evidence_path),
        "state_path": str(state_path),
        "runbook_day_local_path": str(runbook_day_local_path),
    }


def _validate_existing_prepared(
    *,
    account_id: str,
    data_date: str,
    trade_date: str,
    workspace: Path,
    account_paths: PaperAccountPaths,
    state_path: Path,
    evidence_path: Path,
    runbook_day_local_path: Path | None,
) -> tuple[dict[str, Any], runbook_state.RunbookState]:
    _check_prepare_paths(workspace, account_paths, runbook_day_local_path)
    state = runbook_state.load_state(state_path)
    if runbook_state.validate_state(state):
        raise ValueError("prepared_state_invalid")
    if not runbook_state.context_matches_state(state, account_id, data_date, trade_date):
        raise ValueError("prepared_state_context_mismatch")
    runbook_state.assert_current_binding(state)
    if _has_lifecycle_disposition(workspace, account_id, state.runbook_day_id):
        raise ValueError("existing_lifecycle_disposition")
    evidence = _load_valid_evidence(evidence_path)
    expected_ref = state_path.relative_to(workspace).as_posix()
    if evidence["state_ref"] != expected_ref:
        raise ValueError("prepare_state_ref_mismatch")
    if runbook_day_local_path is not None:
        values = read_runbook_day_local(runbook_day_local_path, account_id=account_id)
        if values != {
            "DATA_DATE": data_date,
            "TRADE_DATE": trade_date,
            "RUNBOOK_DAY_ID": state.runbook_day_id,
        }:
            raise ValueError("runbook_day_local_conflict")
    identity = evidence["prepare_identity"]
    expected_identity_context = {
        "account_id": account_id,
        "data_date": data_date,
        "trade_date": trade_date,
        "runbook_day_id": state.runbook_day_id,
    }
    if any(identity.get(field) != value for field, value in expected_identity_context.items()):
        raise ValueError("prepare_identity_context_mismatch")
    binding = getattr(state.frozen_context, "binding", None)
    if binding is None:
        raise ValueError("prepared_binding_missing")
    if identity["binding_digest"] != binding["digest"] or identity["binding_refs"] != _binding_refs(binding):
        raise ValueError("prepare_binding_mismatch")
    actual_hashes = _current_hashes(account_paths, list(identity["bootstrap_hashes"]))
    if actual_hashes != identity["bootstrap_hashes"]:
        raise ValueError("bootstrap_identity_mismatch")
    return evidence, state


def prepare_first_run(
    *,
    account_id: str,
    data_date: str,
    workspace: str | Path,
    account_local_path: str | Path,
    runbook_day_local_path: str | Path,
    calendar: MarketCalendar | None = None,
    timezone: str = "Asia/Seoul",
) -> dict[str, Any]:
    normalized_data_date = normalize_bootstrap_date(data_date)
    resolved_trade_date: str | None = None
    try:
        calendar = calendar or load_market_calendar()
        data_value = datetime.strptime(normalized_data_date, "%Y-%m-%d").date()
        calendar.require_coverage(data_value)
        resolved_trade_date = calendar.next_trading_day(data_value).isoformat()
        _assert_regular_path(Path(workspace))
        workspace_path = Path(workspace).resolve(strict=False)
        if not workspace_path.is_dir() or workspace_path.is_symlink():
            raise ValueError("workspace_missing_or_unsafe")
        _assert_regular_path(Path(account_local_path))
        _assert_regular_path(Path(runbook_day_local_path))
        if Path(runbook_day_local_path).absolute().parent != Path(account_local_path).absolute().parent:
            raise ValueError("prepare_context_root_mismatch")
        account_values = read_account_local(account_local_path)
        if account_values["ACCOUNT_ID"] != account_id:
            raise ValueError("account_local_mismatch")
        account_paths = build_paper_account_paths(account_id, create=False)
        evidence_path = prepare_evidence_path(account_paths)
        day_path = Path(runbook_day_local_path)
        runbook_day_id = runbook_state.get_runbook_day_id(account_id, normalized_data_date, resolved_trade_date)
        state_path = runbook_state.get_state_path_for_runbook_day_id(workspace_path, runbook_day_id)

        _check_prepare_paths(workspace_path, account_paths, day_path)
        if (account_paths.root / PREPARE_LOCK_FILENAME).exists():
            return _blocked("CONFLICT", "prepare_lock_present", account_id=account_id,
                            data_date=normalized_data_date, trade_date=resolved_trade_date)

        records, state_errors = _matching_states(workspace_path, account_id)
        if state_errors:
            return _blocked("CONFLICT", "runbook_history_invalid", account_id=account_id,
                            data_date=normalized_data_date, trade_date=resolved_trade_date,
                            blockers=state_errors)
        if len(records) > 1:
            return _blocked("CONFLICT", "multiple_states", account_id=account_id,
                            data_date=normalized_data_date, trade_date=resolved_trade_date)
        if records:
            record = records[0]
            if record.path.resolve() != state_path.resolve():
                return _blocked("CONFLICT", "different_runbook_context", account_id=account_id,
                                data_date=normalized_data_date, trade_date=resolved_trade_date)
            state = record.state
            if _has_lifecycle_disposition(workspace_path, account_id, runbook_day_id):
                return _blocked("RECOVERY_REQUIRED", "existing_lifecycle_disposition", account_id=account_id,
                                data_date=normalized_data_date, trade_date=resolved_trade_date)
            if not runbook_state.context_matches_state(state, account_id, normalized_data_date, resolved_trade_date):
                return _blocked("CONFLICT", "different_runbook_context", account_id=account_id,
                                data_date=normalized_data_date, trade_date=resolved_trade_date)
            if not _is_initial_ready(state) and not evidence_path.exists():
                identity = {
                    "account_id": account_id, "data_date": normalized_data_date,
                    "trade_date": resolved_trade_date, "runbook_day_id": runbook_day_id,
                }
                return _pass("RESUME_EXISTING_RUN", identity, evidence_path=evidence_path,
                             state_path=state_path, runbook_day_local_path=day_path)
            if not evidence_path.is_file() or not day_path.is_file():
                return _blocked("RECOVERY_REQUIRED", "partial_prepare_artifacts", account_id=account_id,
                                data_date=normalized_data_date, trade_date=resolved_trade_date)
            evidence, loaded_state = _validate_existing_prepared(
                account_id=account_id, data_date=normalized_data_date, trade_date=resolved_trade_date,
                workspace=workspace_path, account_paths=account_paths, state_path=state_path,
                evidence_path=evidence_path, runbook_day_local_path=day_path,
            )
            result = "REUSE" if _is_initial_ready(loaded_state) else "RESUME_EXISTING_RUN"
            return _pass(result, evidence["prepare_identity"], evidence_path=evidence_path,
                         state_path=state_path, runbook_day_local_path=day_path)

        if evidence_path.exists():
            try:
                _load_valid_evidence(evidence_path)
            except (OSError, UnicodeError, ValueError, TypeError) as exc:
                return _blocked("CONFLICT", "prepare_evidence_invalid", account_id=account_id,
                                data_date=normalized_data_date, trade_date=resolved_trade_date,
                                blockers=[str(exc)])
            return _blocked("RECOVERY_REQUIRED", "prepare_state_missing", account_id=account_id,
                            data_date=normalized_data_date, trade_date=resolved_trade_date)
        if day_path.exists():
            try:
                values = read_runbook_day_local(day_path, account_id=account_id)
            except (OSError, UnicodeError, ValueError) as exc:
                return _blocked("CONFLICT", "runbook_day_local_invalid", account_id=account_id,
                                data_date=normalized_data_date, trade_date=resolved_trade_date,
                                blockers=[str(exc)])
            expected_values = {"DATA_DATE": normalized_data_date, "TRADE_DATE": resolved_trade_date,
                               "RUNBOOK_DAY_ID": runbook_day_id}
            result = "RECOVERY_REQUIRED" if values == expected_values else "CONFLICT"
            return _blocked(result, "orphan_runbook_day_local" if result == "RECOVERY_REQUIRED" else "runbook_day_local_conflict",
                            account_id=account_id, data_date=normalized_data_date, trade_date=resolved_trade_date)

        validation = validate_prepare_first_request(
            account_id=account_id,
            account_paths=account_paths,
            workspace=workspace_path,
            authoritative_workspace=workspace_path,
            data_date=normalized_data_date,
            trade_date=resolved_trade_date,
            calendar=calendar,
        )
        if not validation["eligible"]:
            return _blocked("CONFLICT", "fresh_validation_failed", account_id=account_id,
                            data_date=normalized_data_date, trade_date=resolved_trade_date,
                            blockers=list(validation["blockers"]))
        binding = validation["binding"]
        bootstrap = validation["bootstrap"]
        if binding is None or bootstrap is None:
            raise ValueError("fresh_validation_evidence_missing")
        state = runbook_state.create_initial_state(
            account_id, normalized_data_date, resolved_trade_date, timezone
        )
        assert_binding_matches(binding, getattr(state.frozen_context, "binding", None))
        runbook_state.assert_initial_state_creation_allowed(workspace_path, state)
        identity = build_prepare_identity(
            account_id=account_id,
            data_date=normalized_data_date,
            trade_date=resolved_trade_date,
            runbook_day_id=runbook_day_id,
            binding=binding,
            bootstrap=bootstrap,
        )
        state_ref = state_path.relative_to(workspace_path).as_posix()
        evidence = _evidence_payload(identity, state_ref=state_ref, timezone=timezone)
        values = {"DATA_DATE": normalized_data_date, "TRADE_DATE": resolved_trade_date,
                  "RUNBOOK_DAY_ID": runbook_day_id}

        with _prepare_write_lock(account_paths):
            # Validation occurred before acquisition. Recheck publication and
            # history so a just-finished competing invocation cannot be replaced.
            _check_prepare_paths(workspace_path, account_paths, day_path)
            records, errors = _matching_states(workspace_path, account_id)
            if records or errors or evidence_path.exists() or day_path.exists():
                raise ValueError("prepare_changed_before_write")
            write_runbook_day_local_exact(day_path, account_id=account_id, values=values)
            evidence_path.parent.mkdir(parents=True, exist_ok=False)
            temp_path = evidence_path.with_name(f"{evidence_path.name}.tmp")
            try:
                temp_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                if _load_valid_evidence(temp_path) != evidence:
                    raise ValueError("prepare_evidence_temp_validation_failed")
                temp_path.replace(evidence_path)
            finally:
                if temp_path.exists():
                    temp_path.unlink()
            runbook_state.save_state(state, state_path)

            checked, checked_state = _validate_existing_prepared(
                account_id=account_id, data_date=normalized_data_date, trade_date=resolved_trade_date,
                workspace=workspace_path, account_paths=account_paths, state_path=state_path,
                evidence_path=evidence_path, runbook_day_local_path=day_path,
            )
            if not _is_initial_ready(checked_state) or checked["prepare_identity"] != identity:
                raise ValueError("prepared_final_validation_failed")
            return _pass("PREPARED", identity, evidence_path=evidence_path, state_path=state_path,
                         runbook_day_local_path=day_path)
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, RuntimeError, json.JSONDecodeError) as exc:
        return _blocked("CONFLICT", "prepare_first_run_failed", account_id=account_id,
                        data_date=normalized_data_date, trade_date=resolved_trade_date,
                        blockers=[f"{type(exc).__name__}:{exc}"])


def stage_a_prepare_guard(
    workspace: str | Path,
    account_id: str,
    data_date: str,
    trade_date: str,
) -> str | None:
    """Return a blocking reason only for versioned, no-history fresh accounts."""
    try:
        profiles = load_paper_account_profiles(allow_missing=True)
        if profiles.schema_version != VERSIONED_ACCOUNT_PROFILE_SCHEMA:
            return None
        _assert_regular_path(Path(workspace))
        workspace_path = Path(workspace).resolve(strict=False)
        resolve_paper_account_profile(account_id, config=profiles)
        account_paths = build_paper_account_paths(account_id, create=False)
        _check_prepare_paths(workspace_path, account_paths)
        if (account_paths.root / PREPARE_LOCK_FILENAME).exists():
            return "prepare_lock_present"
        if not account_paths.root.is_dir():
            return None
        state_path = runbook_state.get_state_path_for_context(workspace_path, account_id, data_date, trade_date)
        if state_path.is_file():
            state = runbook_state.load_state(state_path)
            if not _is_initial_ready(state):
                return None
            evidence_path = prepare_evidence_path(account_paths)
            if not evidence_path.is_file():
                return "prepare_first_run_required"
            _validate_existing_prepared(
                account_id=account_id,
                data_date=normalize_bootstrap_date(data_date),
                trade_date=normalize_bootstrap_date(trade_date),
                workspace=workspace_path,
                account_paths=account_paths,
                state_path=state_path,
                evidence_path=evidence_path,
                runbook_day_local_path=None,
            )
            return None
        records, errors = _matching_states(workspace_path, account_id)
        if errors:
            return "prepare_first_run_history_invalid"
        if records:
            return None
        return "prepare_first_run_required"
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, RuntimeError, json.JSONDecodeError) as exc:
        return f"prepare_first_run_guard_failed:{exc}"

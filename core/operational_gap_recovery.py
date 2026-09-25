from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from zoneinfo import ZoneInfo

from core import failed_no_trade_closure, runbook_recovery, runbook_retirement
from core.operational_no_trade_gap import (
    CONSUMPTION_MODE,
    SCHEMA_VERSION,
    CollisionState,
    ConsumptionState,
    PolicyAssessment,
    SourcePolicyRegistry,
    assess_gap_collisions,
    calendar_projection_sha256,
    derive_canonical_gap_resume,
    canonical_json_sha256,
    derive_consumption_state,
    parse_evidence,
    render_evidence,
    resolve_authoritative_account_mode,
    scan_domain_no_write,
    seal_evidence,
    sha256_file,
    validate_evidence,
)
from core.paper_account_paths import build_paper_account_paths
from core.runbook_calendar import CALENDAR_SCHEMA_VERSION, MarketCalendar
from scripts import runbook_state


GENERIC_EVIDENCE_DIRNAME = "operational_no_trade_gaps"
PROGRESSED_POLICY_TYPE = "PROGRESSED_ACTIVE_NO_TRADE"
PROGRESSED_POLICY_VERSION = 1
TERMINAL_POLICY_TYPE = "TERMINAL_PROVEN_NO_TRADE"
TERMINAL_POLICY_VERSION = 1
PRODUCTION_ACTIVATION_ENABLED = False
GUARD_ALLOW = "ALLOW"
GUARD_BLOCKED = "BLOCKED"
GUARD_NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class ProgressedActiveAssessment:
    eligible: bool
    blockers: tuple[str, ...]
    parity: str
    preview: dict[str, Any] | None = None
    evidence: dict[str, Any] | None = None


@dataclass(frozen=True)
class TerminalProvenAssessment:
    eligible: bool
    blockers: tuple[str, ...]
    evidence: dict[str, Any] | None = None


def generic_evidence_dir(workspace: str | Path) -> Path:
    return Path(workspace).resolve(strict=False) / GENERIC_EVIDENCE_DIRNAME


def generic_evidence_path(workspace: str | Path, gap_id: str) -> Path:
    digest = str(gap_id or "").removeprefix("sha256:")
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ValueError("invalid_gap_id")
    return generic_evidence_dir(workspace) / f"{digest}.json"


def _blocked(reason: str, blockers: Sequence[str] = (), *, mode: str) -> dict[str, Any]:
    return {
        "runner_result": "BLOCKED",
        "mode": mode,
        "reason": reason,
        "eligible": False,
        "authorized": False,
        "blockers": list(blockers) or [reason],
    }


def _workspace_ref(workspace: Path, path: Path) -> str:
    resolved_workspace = workspace.resolve(strict=False)
    resolved = path.resolve(strict=False)
    try:
        return resolved.relative_to(resolved_workspace).as_posix()
    except ValueError as exc:
        raise ValueError("source_ref_outside_workspace") from exc


def _resolve_workspace_ref(workspace: Path, ref: str) -> Path:
    relative = Path(str(ref or ""))
    if relative.is_absolute():
        raise ValueError("source_ref_must_be_relative")
    resolved_workspace = workspace.resolve(strict=False)
    resolved = (resolved_workspace / relative).resolve(strict=False)
    try:
        resolved.relative_to(resolved_workspace)
    except ValueError as exc:
        raise ValueError("source_ref_outside_workspace") from exc
    return resolved


@dataclass(frozen=True)
class ProgressedActiveNoTradePolicy:
    workspace: Path
    calendar: MarketCalendar
    account_mode_resolver: Callable[[str], str] = resolve_authoritative_account_mode
    policy_type: str = PROGRESSED_POLICY_TYPE
    policy_version: int = PROGRESSED_POLICY_VERSION

    def assess_eligibility(self, source: Mapping[str, Any]) -> PolicyAssessment:
        assessment = self._validate(source)
        if not assessment.eligible:
            return assessment
        account_id = str(source.get("account_id") or "").strip()
        identity = str(source.get("identity") or "").strip()
        _, active, _, context_blockers = runbook_recovery._load_recovery_context(
            self.workspace,
            account_id,
            identity,
            self.calendar,
        )
        blockers = list(context_blockers)
        if len(active) != 1:
            blockers.append("active_runbook_day_count_must_equal_one")
        elif active[0].state.runbook_day_id != identity:
            blockers.append("source_is_not_the_only_active_runbook")
        return PolicyAssessment(not blockers, tuple(dict.fromkeys(blockers)))

    def bind_source_evidence(self, source: Mapping[str, Any]) -> dict[str, Any]:
        assessment = self.assess_eligibility(source)
        if not assessment.eligible:
            raise ValueError("source_not_eligible:" + ",".join(assessment.blockers))
        return json.loads(json.dumps(dict(source)))

    def validate_source_still_valid(self, source: Mapping[str, Any]) -> PolicyAssessment:
        return self._validate(source)

    def _validate(self, source: Mapping[str, Any]) -> PolicyAssessment:
        blockers: list[str] = []
        account_id = str(source.get("account_id") or "").strip()
        identity = str(source.get("identity") or "").strip()
        state_ref = str(source.get("state_ref") or "").strip()
        lifecycle = str(source.get("lifecycle") or "").strip()
        first_legal_gap_date = str(source.get("first_legal_gap_date") or "").strip()
        if lifecycle != "ACTIVE_INCOMPLETE":
            blockers.append("source_lifecycle_not_accepted")
        try:
            mode = str(self.account_mode_resolver(account_id) or "").strip().upper()
        except (OSError, UnicodeError, ValueError, RuntimeError):
            mode = ""
            blockers.append("authoritative_account_mode_unavailable")
        if mode not in {"PAPER", "TEST"}:
            blockers.append("paper_or_test_account_required")
        try:
            state_path = _resolve_workspace_ref(self.workspace, state_ref)
            state = runbook_state.load_state(state_path)
            raw = json.loads(state_path.read_text(encoding="utf-8"))
            from core import runbook_day_rollover

            record = runbook_day_rollover.StateRecord(
                state_path,
                state,
                dict(raw.get("stage_status") or {}),
            )
            if state.runbook_day_id != identity:
                blockers.append("source_identity_mismatch")
            if state.frozen_context.account_id != account_id:
                blockers.append("source_account_mismatch")
            if runbook_recovery._base_classification(self.workspace, record) != "ACTIVE_INCOMPLETE":
                blockers.append("source_not_active_incomplete")
            retirement = runbook_retirement.assess_zero_progress(
                self.workspace, state_path, state
            )
            if retirement["eligible"]:
                blockers.append("source_is_zero_progress_retirement_candidate")
            if first_legal_gap_date != state.frozen_context.trade_date:
                blockers.append("source_first_legal_gap_date_mismatch")
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            blockers.append("source_state_invalid")
        return PolicyAssessment(not blockers, tuple(dict.fromkeys(blockers)))


@dataclass(frozen=True)
class TerminalProvenNoTradePolicy:
    workspace: Path
    calendar: MarketCalendar
    account_mode_resolver: Callable[[str], str] = resolve_authoritative_account_mode
    policy_type: str = TERMINAL_POLICY_TYPE
    policy_version: int = TERMINAL_POLICY_VERSION

    def assess_eligibility(self, source: Mapping[str, Any]) -> PolicyAssessment:
        return self._validate(source)

    def bind_source_evidence(self, source: Mapping[str, Any]) -> dict[str, Any]:
        assessment = self._validate(source)
        if not assessment.eligible:
            raise ValueError("source_not_eligible:" + ",".join(assessment.blockers))
        return json.loads(json.dumps(dict(source)))

    def validate_source_still_valid(self, source: Mapping[str, Any]) -> PolicyAssessment:
        return self._validate(source)

    def _validate(self, source: Mapping[str, Any]) -> PolicyAssessment:
        blockers: list[str] = []
        account_id = str(source.get("account_id") or "").strip()
        identity = str(source.get("identity") or "").strip()
        state_ref = str(source.get("state_ref") or "").strip()
        closure_ref = str(source.get("closure_ref") or "").strip()
        lifecycle = str(source.get("lifecycle") or "").strip()
        source_trade_date = str(source.get("source_trade_date") or "").strip()
        first_legal_gap_date = str(source.get("first_legal_gap_date") or "").strip()
        if lifecycle != failed_no_trade_closure.TERMINAL_CLASSIFICATION:
            blockers.append("source_lifecycle_not_accepted")
        try:
            mode = str(self.account_mode_resolver(account_id) or "").strip().upper()
        except (OSError, UnicodeError, ValueError, RuntimeError):
            mode = ""
            blockers.append("authoritative_account_mode_unavailable")
        if mode not in {"PAPER", "TEST"}:
            blockers.append("paper_or_test_account_required")
        try:
            state_path = _resolve_workspace_ref(self.workspace, state_ref)
            closure_path = _resolve_workspace_ref(self.workspace, closure_ref)
            state = runbook_state.load_state(state_path)
            if state.runbook_day_id != identity:
                blockers.append("source_identity_mismatch")
            if state.frozen_context.account_id != account_id:
                blockers.append("source_account_mismatch")
            if state.frozen_context.trade_date != source_trade_date:
                blockers.append("source_trade_date_mismatch")
            expected_first = self.calendar.next_trading_day(
                date.fromisoformat(state.frozen_context.trade_date)
            ).isoformat()
            if first_legal_gap_date != expected_first:
                blockers.append("source_first_legal_gap_date_mismatch")
            validation = failed_no_trade_closure.validate_closure_evidence(
                self.workspace, state_path, state
            )
            if not validation["exists"]:
                blockers.append("source_closure_missing")
            elif not validation["valid"]:
                blockers.extend(
                    ["source_closure_invalid", *validation.get("blockers", [])]
                )
            else:
                payload = validation["payload"]
                if closure_path != Path(validation["path"]).resolve(strict=False):
                    blockers.append("source_closure_ref_mismatch")
                if payload.get("schema_version") != failed_no_trade_closure.SCHEMA_VERSION:
                    blockers.append("source_closure_schema_mismatch")
                if (
                    payload.get("terminal_classification")
                    != failed_no_trade_closure.TERMINAL_CLASSIFICATION
                ):
                    blockers.append("source_closure_lifecycle_mismatch")
                if payload.get("runbook_day_id") != identity:
                    blockers.append("source_closure_identity_mismatch")
                context = payload.get("frozen_context")
                if not isinstance(context, Mapping) or context.get("account_id") != account_id:
                    blockers.append("source_closure_account_mismatch")
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            blockers.append("source_state_or_closure_invalid")
        return PolicyAssessment(not blockers, tuple(dict.fromkeys(blockers)))

def build_recovery_policy_registry(
    workspace: str | Path,
    *,
    calendar: MarketCalendar,
    account_mode_resolver: Callable[[str], str] = resolve_authoritative_account_mode,
) -> SourcePolicyRegistry:
    registry = SourcePolicyRegistry()
    registry.register(
        ProgressedActiveNoTradePolicy(
            Path(workspace).resolve(strict=False),
            calendar=calendar,
            account_mode_resolver=account_mode_resolver,
        )
    )
    registry.register(
        TerminalProvenNoTradePolicy(
            Path(workspace).resolve(strict=False),
            calendar=calendar,
            account_mode_resolver=account_mode_resolver,
        )
    )
    return registry


def _preview_binding_payload(evidence: Mapping[str, Any]) -> dict[str, Any]:
    payload = json.loads(json.dumps(dict(evidence)))
    payload.pop("created_at", None)
    payload.pop("content_sha256", None)
    return payload


def preview_binding_sha256(evidence: Mapping[str, Any]) -> str:
    return canonical_json_sha256(_preview_binding_payload(evidence))


def _build_generic_evidence(
    *,
    workspace: Path,
    legacy_preview: Mapping[str, Any],
    calendar: MarketCalendar,
    account_mode: str,
    account_root: Path,
    operator: str,
) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    gap = legacy_preview["no_trade_interval"]
    restart = legacy_preview["restart"]
    source_state_path = _resolve_workspace_ref(workspace, legacy_preview["source_state_ref"])
    latest_path = _resolve_workspace_ref(
        workspace, legacy_preview["latest_completed"]["state_ref"]
    )
    domain = scan_domain_no_write(
        account_id=str(legacy_preview["account_id"]),
        trading_dates=gap["trading_dates"],
        expected_trade_ids=(),
        account_root=account_root,
    )
    if not domain["valid"]:
        return None, tuple(domain["blockers"])
    source = {
        "account_id": legacy_preview["account_id"],
        "identity": legacy_preview["source_runbook_day_id"],
        "lifecycle": "ACTIVE_INCOMPLETE",
        "state_ref": legacy_preview["source_state_ref"],
        "first_legal_gap_date": gap["start_date"],
        "refs": [
            {
                "path": _workspace_ref(workspace, source_state_path),
                "sha256": sha256_file(source_state_path),
            },
            {
                "path": _workspace_ref(workspace, latest_path),
                "sha256": sha256_file(latest_path),
            },
        ],
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "account_id": legacy_preview["account_id"],
        "account_mode": account_mode,
        "source_policy": {
            "type": PROGRESSED_POLICY_TYPE,
            "version": PROGRESSED_POLICY_VERSION,
        },
        "source": source,
        "incident": {
            "reason_code": "LEGACY_RECOVERY_COMPAT",
            "reason_text": legacy_preview["reason"],
        },
        "gap": {
            "start_date": gap["start_date"],
            "end_date": gap["end_date"],
            "trading_dates": list(gap["trading_dates"]),
        },
        "calendar": {
            "schema_version": CALENDAR_SCHEMA_VERSION,
            "market": calendar.market,
            "timezone": calendar.timezone,
            "projection_sha256": calendar_projection_sha256(
                calendar, gap["start_date"], restart["trade_date"]
            ),
        },
        "no_trade": domain["no_trade"],
        "domain_no_write": domain["domain_no_write"],
        "no_backfill": {"confirmed": True},
        "resume": dict(restart),
        "operator": str(operator or "recovery-cli").strip() or "recovery-cli",
        "created_at": datetime.now(ZoneInfo(calendar.timezone)).isoformat(),
        "consumption": {
            "mode": CONSUMPTION_MODE,
            "target_state_ref": (
                Path(runbook_state.STATE_DIRNAME)
                / f"{restart['runbook_day_id']}.json"
            ).as_posix(),
        },
    }
    return seal_evidence(payload), ()


def assess_progressed_active_recovery(
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
    account_root: str | Path | None = None,
    account_mode_resolver: Callable[[str], str] = resolve_authoritative_account_mode,
    operator: str = "recovery-cli",
) -> ProgressedActiveAssessment:
    legacy_preview = runbook_recovery.preview_recovery(
        workspace,
        account_id=account_id,
        source_runbook_day_id=source_runbook_day_id,
        restart_data_date=restart_data_date,
        restart_trade_date=restart_trade_date,
        reason=reason,
        calendar=calendar,
        confirm_paper_test=confirm_paper_test,
        confirm_contaminated_incomplete=confirm_contaminated_incomplete,
        confirm_no_real_trades=confirm_no_real_trades,
        confirm_gap_without_backfill=confirm_gap_without_backfill,
    )
    if legacy_preview["runner_result"] != "PASS":
        return ProgressedActiveAssessment(
            False,
            tuple(legacy_preview.get("blockers") or ()),
            "IDENTICAL",
            preview=dict(legacy_preview),
        )
    try:
        account_mode = str(account_mode_resolver(account_id) or "").strip().upper()
    except (OSError, UnicodeError, ValueError, RuntimeError):
        return ProgressedActiveAssessment(
            False,
            ("authoritative_account_mode_unavailable",),
            "MISMATCH",
            preview=dict(legacy_preview),
        )
    if account_mode not in {"PAPER", "TEST"}:
        return ProgressedActiveAssessment(
            False,
            ("paper_or_test_account_required",),
            "IDENTICAL",
            preview=dict(legacy_preview),
        )
    resolved_root = (
        Path(account_root)
        if account_root is not None
        else build_paper_account_paths(account_id, create=False).root
    )
    evidence, domain_blockers = _build_generic_evidence(
        workspace=Path(workspace).resolve(strict=False),
        legacy_preview=legacy_preview,
        calendar=calendar,
        account_mode=account_mode,
        account_root=resolved_root,
        operator=operator,
    )
    if evidence is None:
        return ProgressedActiveAssessment(
            False,
            domain_blockers,
            "INTENTIONAL_GENERIC_HARDENING",
            preview=dict(legacy_preview),
        )
    registry = build_recovery_policy_registry(
        workspace,
        calendar=calendar,
        account_mode_resolver=account_mode_resolver,
    )
    eligibility = registry.resolve(
        PROGRESSED_POLICY_TYPE, PROGRESSED_POLICY_VERSION
    ).assess_eligibility(evidence["source"])
    if not eligibility.eligible:
        return ProgressedActiveAssessment(
            False,
            eligibility.blockers,
            "MISMATCH",
            preview=dict(legacy_preview),
            evidence=evidence,
        )
    validation = validate_evidence(
        evidence,
        calendar=calendar,
        workspace=workspace,
        account_root=resolved_root,
        registry=registry,
        account_mode_resolver=account_mode_resolver,
    )
    if not validation.valid:
        return ProgressedActiveAssessment(
            False,
            validation.blockers,
            "MISMATCH",
            preview=dict(legacy_preview),
            evidence=evidence,
        )
    return ProgressedActiveAssessment(
        True,
        (),
        "IDENTICAL",
        preview=dict(legacy_preview),
        evidence=evidence,
    )


def preview_progressed_active_recovery(*args: Any, **kwargs: Any) -> dict[str, Any]:
    assessment = assess_progressed_active_recovery(*args, **kwargs)
    if not assessment.eligible or assessment.evidence is None:
        return _blocked(
            "generic_recovery_not_eligible",
            assessment.blockers,
            mode="RECOVERY_PREVIEW",
        ) | {"parity": assessment.parity}
    return {
        "runner_result": "PASS",
        "mode": "RECOVERY_PREVIEW",
        "eligible": True,
        "authorized": False,
        "producer": f"{SCHEMA_VERSION}:{PROGRESSED_POLICY_TYPE}:v1",
        "parity": assessment.parity,
        "preview_sha256": preview_binding_sha256(assessment.evidence),
        "evidence": assessment.evidence,
        "blockers": [],
    }


def assess_terminal_proven_no_trade_recovery(
    workspace: str | Path,
    *,
    account_id: str,
    source_runbook_day_id: str,
    resume_data_date: str,
    reason: str,
    calendar: MarketCalendar,
    confirm_paper_test: bool,
    confirm_no_real_trades: bool,
    confirm_gap_without_backfill: bool,
    account_root: str | Path | None = None,
    account_mode_resolver: Callable[[str], str] = resolve_authoritative_account_mode,
    operator: str = "recovery-cli",
) -> TerminalProvenAssessment:
    blockers: list[str] = []
    workspace_path = Path(workspace).resolve(strict=False)
    account_id = str(account_id or "").strip()
    source_runbook_day_id = str(source_runbook_day_id or "").strip()
    reason = str(reason or "").strip()
    operator = str(operator or "").strip()
    if not confirm_paper_test:
        blockers.append("paper_test_confirmation_required")
    if not confirm_no_real_trades:
        blockers.append("no_real_trades_confirmation_required")
    if not confirm_gap_without_backfill:
        blockers.append("gap_without_backfill_confirmation_required")
    if not reason:
        blockers.append("recovery_reason_required")
    if not operator:
        blockers.append("operator_required")
    try:
        account_mode = str(account_mode_resolver(account_id) or "").strip().upper()
    except (OSError, UnicodeError, ValueError, RuntimeError):
        account_mode = ""
        blockers.append("authoritative_account_mode_unavailable")
    if account_mode not in {"PAPER", "TEST"}:
        blockers.append("paper_or_test_account_required")

    state_path = runbook_state.get_state_path_for_runbook_day_id(
        workspace_path, source_runbook_day_id
    )
    try:
        state = runbook_state.load_state(state_path)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        return TerminalProvenAssessment(
            False,
            tuple(dict.fromkeys([*blockers, "source_state_invalid"])),
        )
    if state.runbook_day_id != source_runbook_day_id:
        blockers.append("source_identity_mismatch")
    if state.frozen_context.account_id != account_id:
        blockers.append("source_account_mismatch")
    closure = failed_no_trade_closure.validate_closure_evidence(
        workspace_path, state_path, state
    )
    if not closure["exists"]:
        blockers.append("source_closure_missing")
    elif not closure["valid"]:
        blockers.extend(["source_closure_invalid", *closure.get("blockers", [])])
    try:
        gap_start = calendar.next_trading_day(
            date.fromisoformat(state.frozen_context.trade_date)
        ).isoformat()
        gap_dates, resume = derive_canonical_gap_resume(
            account_id=account_id,
            gap_start_date=gap_start,
            resume_data_date=str(resume_data_date),
            calendar=calendar,
        )
    except (ValueError, RuntimeError) as exc:
        blockers.append(str(exc))
        gap_start = ""
        gap_dates = ()
        resume = {}
    if blockers:
        return TerminalProvenAssessment(False, tuple(dict.fromkeys(blockers)))

    closure_path = Path(closure["path"]).resolve(strict=False)
    closure_payload = closure["payload"]
    expected_trade_ids = [
        str(item) for item in closure_payload.get("expected_trade_ids", [])
    ]
    resolved_root = (
        Path(account_root)
        if account_root is not None
        else build_paper_account_paths(account_id, create=False).root
    )
    domain = scan_domain_no_write(
        account_id=account_id,
        trading_dates=gap_dates,
        expected_trade_ids=expected_trade_ids,
        account_root=resolved_root,
    )
    if not domain["valid"]:
        return TerminalProvenAssessment(False, tuple(domain["blockers"]))
    source = {
        "account_id": account_id,
        "identity": source_runbook_day_id,
        "lifecycle": failed_no_trade_closure.TERMINAL_CLASSIFICATION,
        "state_ref": _workspace_ref(workspace_path, state_path),
        "closure_ref": _workspace_ref(workspace_path, closure_path),
        "source_trade_date": state.frozen_context.trade_date,
        "first_legal_gap_date": gap_start,
        "refs": [
            {
                "path": _workspace_ref(workspace_path, state_path),
                "sha256": sha256_file(state_path),
            },
            {
                "path": _workspace_ref(workspace_path, closure_path),
                "sha256": sha256_file(closure_path),
            },
        ],
    }
    registry = build_recovery_policy_registry(
        workspace_path,
        calendar=calendar,
        account_mode_resolver=account_mode_resolver,
    )
    eligibility = registry.resolve(
        TERMINAL_POLICY_TYPE, TERMINAL_POLICY_VERSION
    ).assess_eligibility(source)
    if not eligibility.eligible:
        return TerminalProvenAssessment(False, eligibility.blockers)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "account_id": account_id,
        "account_mode": account_mode,
        "source_policy": {
            "type": TERMINAL_POLICY_TYPE,
            "version": TERMINAL_POLICY_VERSION,
        },
        "source": source,
        "incident": {
            "reason_code": "FAILED_NO_TRADE_CLOSED_GAP",
            "reason_text": reason,
        },
        "gap": {
            "start_date": gap_start,
            "end_date": str(resume_data_date),
            "trading_dates": list(gap_dates),
        },
        "calendar": {
            "schema_version": CALENDAR_SCHEMA_VERSION,
            "market": calendar.market,
            "timezone": calendar.timezone,
            "projection_sha256": calendar_projection_sha256(
                calendar, gap_start, resume["trade_date"]
            ),
        },
        "no_trade": domain["no_trade"],
        "domain_no_write": domain["domain_no_write"],
        "no_backfill": {"confirmed": True},
        "resume": resume,
        "operator": operator,
        "created_at": datetime.now(ZoneInfo(calendar.timezone)).isoformat(),
        "consumption": {
            "mode": CONSUMPTION_MODE,
            "target_state_ref": (
                Path(runbook_state.STATE_DIRNAME) / f"{resume['runbook_day_id']}.json"
            ).as_posix(),
        },
    }
    evidence = seal_evidence(payload)
    validation = validate_evidence(
        evidence,
        calendar=calendar,
        workspace=workspace_path,
        account_root=resolved_root,
        registry=registry,
        account_mode_resolver=account_mode_resolver,
    )
    if not validation.valid:
        return TerminalProvenAssessment(False, validation.blockers, evidence)
    return TerminalProvenAssessment(True, (), evidence)


def preview_terminal_proven_no_trade_recovery(
    *args: Any, **kwargs: Any
) -> dict[str, Any]:
    assessment = assess_terminal_proven_no_trade_recovery(*args, **kwargs)
    if not assessment.eligible or assessment.evidence is None:
        return _blocked(
            "terminal_generic_recovery_not_eligible",
            assessment.blockers,
            mode="RECOVERY_PREVIEW",
        )
    return {
        "runner_result": "PASS",
        "mode": "RECOVERY_PREVIEW",
        "eligible": True,
        "authorized": False,
        "producer": f"{SCHEMA_VERSION}:{TERMINAL_POLICY_TYPE}:v1",
        "preview_sha256": preview_binding_sha256(assessment.evidence),
        "evidence": assessment.evidence,
        "blockers": [],
    }


def _load_generic_payloads(directory: Path) -> tuple[list[dict[str, Any]], list[str]]:
    payloads: list[dict[str, Any]] = []
    blockers: list[str] = []
    if not directory.exists():
        return payloads, blockers
    for path in sorted(directory.glob("*.json")):
        try:
            payloads.append(parse_evidence(path.read_bytes()).to_mapping())
        except (OSError, ValueError):
            blockers.append(f"generic_evidence_invalid:{path.name}")
    return payloads, blockers


def _legacy_authorizations(
    workspace: Path,
    account_id: str,
    calendar: MarketCalendar,
) -> tuple[list[dict[str, Any]], list[str]]:
    directory = workspace / runbook_recovery.RECOVERY_DIRNAME
    records: list[dict[str, Any]] = []
    blockers: list[str] = []
    if not directory.exists():
        return records, blockers
    for path in sorted(directory.glob("*.json")):
        source_id = path.stem
        state_path = runbook_state.get_state_path_for_runbook_day_id(workspace, source_id)
        try:
            source_state = runbook_state.load_state(state_path)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            if source_id.startswith(f"{account_id}_"):
                blockers.append(f"legacy_source_state_invalid:{source_id}")
            continue
        if source_state.frozen_context.account_id != account_id:
            continue
        validation = runbook_recovery.validate_recovery_evidence(
            workspace, state_path, source_state, calendar
        )
        if not validation["valid"]:
            blockers.extend(
                [f"legacy_recovery_invalid:{source_id}", *validation["blockers"]]
            )
            continue
        payload = validation["payload"]
        records.append(
            {
                "evidence_kind": runbook_recovery.SCHEMA_VERSION,
                "evidence_id": source_id,
                "account_id": account_id,
                "source_identity": source_id,
                "gap": {
                    "trading_dates": list(
                        payload["no_trade_interval"]["trading_dates"]
                    )
                },
                "resume": dict(payload["restart"]),
                "status": "CONSUMED" if validation["consumed"] else "UNCONSUMED",
            }
        )
    return records, blockers


def resolve_operational_gap_authorizations(
    workspace: str | Path,
    *,
    account_id: str,
    calendar: MarketCalendar,
    account_root: str | Path | None = None,
    account_mode_resolver: Callable[[str], str] = resolve_authoritative_account_mode,
) -> dict[str, Any]:
    workspace_path = Path(workspace).resolve(strict=False)
    legacy, blockers = _legacy_authorizations(workspace_path, account_id, calendar)
    generic_payloads, load_blockers = _load_generic_payloads(
        generic_evidence_dir(workspace_path)
    )
    blockers.extend(load_blockers)
    generic_records: list[dict[str, Any]] = []
    account_payloads = [
        payload for payload in generic_payloads if payload.get("account_id") == account_id
    ]
    root = (
        Path(account_root)
        if account_root is not None
        else build_paper_account_paths(account_id, create=False).root
        if account_payloads
        else None
    )
    registry = build_recovery_policy_registry(
        workspace_path,
        calendar=calendar,
        account_mode_resolver=account_mode_resolver,
    )
    for payload in account_payloads:
        validation = validate_evidence(
            payload,
            calendar=calendar,
            workspace=workspace_path,
            account_root=root,
            registry=registry,
            account_mode_resolver=account_mode_resolver,
        )
        if not validation.valid:
            blockers.extend(
                [
                    f"generic_evidence_invalid:{payload.get('gap_id')}",
                    *validation.blockers,
                ]
            )
            continue
        consumption = derive_consumption_state(
            payload,
            workspace=workspace_path,
            all_evidence=account_payloads,
        )
        if consumption.state is ConsumptionState.INVALID:
            blockers.extend(consumption.blockers)
            continue
        generic_records.append(
            {
                "evidence_kind": SCHEMA_VERSION,
                "evidence_id": payload["gap_id"],
                "account_id": account_id,
                "source_identity": payload["source"]["identity"],
                "gap": {"trading_dates": list(payload["gap"]["trading_dates"])},
                "resume": dict(payload["resume"]),
                "status": consumption.state.value,
            }
        )
    if blockers:
        return {
            "state": "BLOCKED",
            "account_id": account_id,
            "authorizations": [*legacy, *generic_records],
            "blockers": list(dict.fromkeys(blockers)),
        }
    all_records = [*legacy, *generic_records]
    cross_kind_conflict = any(
        (
            set(legacy_item["gap"]["trading_dates"]).intersection(
                generic_item["gap"]["trading_dates"]
            )
            or legacy_item["resume"]["runbook_day_id"]
            == generic_item["resume"]["runbook_day_id"]
        )
        for legacy_item in legacy
        for generic_item in generic_records
    )
    if cross_kind_conflict:
        return {
            "state": "BLOCKED",
            "account_id": account_id,
            "authorizations": all_records,
            "blockers": ["legacy_generic_authorization_conflict"],
        }
    unconsumed = [item for item in all_records if item["status"] == "UNCONSUMED"]
    if len(unconsumed) > 1:
        kinds = {item["evidence_kind"] for item in unconsumed}
        reasons = ["multiple_unconsumed_authorizations"]
        if len(kinds) > 1:
            reasons.append("legacy_generic_authorization_conflict")
        return {
            "state": "BLOCKED",
            "account_id": account_id,
            "authorizations": all_records,
            "blockers": reasons,
        }
    if unconsumed:
        return {
            "state": "UNCONSUMED",
            "account_id": account_id,
            "authorization": unconsumed[0],
            "authorizations": all_records,
            "blockers": [],
        }
    if all_records:
        return {
            "state": "CONSUMED",
            "account_id": account_id,
            "authorizations": all_records,
            "blockers": [],
        }
    return {
        "state": "NONE",
        "account_id": account_id,
        "authorizations": [],
        "blockers": [],
    }


def guard_operational_gap_boundary(
    workspace: str | Path,
    *,
    account_id: str,
    data_date: str,
    trade_date: str,
    runbook_day_id: str | None = None,
    calendar: MarketCalendar,
    account_root: str | Path | None = None,
    account_mode_resolver: Callable[[str], str] = resolve_authoritative_account_mode,
    boundary: str,
) -> dict[str, Any]:
    """Revalidate NTG authorization and bind a lifecycle/write boundary to its target."""
    requested_target = {
        "account_id": str(account_id or "").strip(),
        "data_date": str(data_date or "").strip(),
        "trade_date": str(trade_date or "").strip(),
        "runbook_day_id": str(runbook_day_id or "").strip()
        or runbook_state.get_runbook_day_id(account_id, data_date, trade_date),
    }
    resolved = resolve_operational_gap_authorizations(
        workspace,
        account_id=requested_target["account_id"],
        calendar=calendar,
        account_root=account_root,
        account_mode_resolver=account_mode_resolver,
    )
    resolver_state = str(resolved.get("state") or "BLOCKED")
    boundary_name = str(boundary or "").strip()
    base = {
        "boundary": boundary_name,
        "resolver_state": resolver_state,
        "requested_target": requested_target,
        "authorizations": list(resolved.get("authorizations") or []),
    }
    if resolver_state == "BLOCKED":
        return {
            **base,
            "decision": GUARD_BLOCKED,
            "reason": "operational_gap_authorization_invalid",
            "blockers": list(resolved.get("blockers") or ["operational_gap_authorization_invalid"]),
        }
    if resolver_state == "NONE":
        return {
            **base,
            "decision": GUARD_NOT_APPLICABLE,
            "reason": "operational_gap_not_applicable",
            "blockers": [],
        }

    matching = [
        item
        for item in resolved.get("authorizations") or []
        if item.get("account_id") == requested_target["account_id"]
        and item.get("resume") == {
            "data_date": requested_target["data_date"],
            "trade_date": requested_target["trade_date"],
            "runbook_day_id": requested_target["runbook_day_id"],
        }
    ]
    if (
        resolver_state == "UNCONSUMED"
        and matching
        and boundary_name
        in {"LIFECYCLE_ENTRY", "EXECUTION_COMMIT", "EOD_SNAPSHOT_WRITE"}
    ):
        return {
            **base,
            "decision": GUARD_BLOCKED,
            "reason": "operational_gap_target_not_initialized",
            "authorization": matching[0],
            "blockers": ["operational_gap_target_not_initialized"],
        }
    if matching:
        return {
            **base,
            "decision": GUARD_ALLOW,
            "reason": "operational_gap_exact_target_valid",
            "authorization": matching[0],
            "blockers": [],
        }
    if resolver_state == "UNCONSUMED":
        return {
            **base,
            "decision": GUARD_BLOCKED,
            "reason": "operational_gap_target_mismatch",
            "authorization": resolved.get("authorization"),
            "blockers": ["operational_gap_target_mismatch"],
        }
    return {
        **base,
        "decision": GUARD_NOT_APPLICABLE,
        "reason": "operational_gap_target_not_bound",
        "blockers": [],
    }


def write_generic_authorization(
    workspace: str | Path,
    *,
    evidence: Mapping[str, Any],
    expected_preview_sha256: str,
    calendar: MarketCalendar,
    account_root: str | Path | None = None,
    account_mode_resolver: Callable[[str], str] = resolve_authoritative_account_mode,
) -> dict[str, Any]:
    workspace_path = Path(workspace).resolve(strict=False)
    account_id = str(evidence.get("account_id") or "")
    if preview_binding_sha256(evidence) != expected_preview_sha256:
        return _blocked(
            "preview_evidence_binding_mismatch",
            mode="GENERIC_RECOVERY_AUTHORIZE",
        )
    root = (
        Path(account_root)
        if account_root is not None
        else build_paper_account_paths(account_id, create=False).root
    )
    registry = build_recovery_policy_registry(
        workspace_path,
        calendar=calendar,
        account_mode_resolver=account_mode_resolver,
    )
    validation = validate_evidence(
        evidence,
        calendar=calendar,
        workspace=workspace_path,
        account_root=root,
        registry=registry,
        account_mode_resolver=account_mode_resolver,
    )
    if not validation.valid:
        return _blocked(
            "generic_evidence_invalid",
            validation.blockers,
            mode="GENERIC_RECOVERY_AUTHORIZE",
        )
    path = generic_evidence_path(workspace_path, str(evidence.get("gap_id") or ""))
    if path.is_file():
        try:
            existing = parse_evidence(path.read_bytes()).to_mapping()
        except (OSError, ValueError):
            return _blocked(
                "existing_generic_evidence_invalid",
                mode="GENERIC_RECOVERY_AUTHORIZE",
            )
        existing_validation = validate_evidence(
            existing,
            calendar=calendar,
            workspace=workspace_path,
            account_root=root,
            registry=registry,
            account_mode_resolver=account_mode_resolver,
        )
        if not existing_validation.valid:
            return _blocked(
                "existing_generic_evidence_invalid",
                ["existing_generic_evidence_invalid", *existing_validation.blockers],
                mode="GENERIC_RECOVERY_AUTHORIZE",
            )
        if (
            existing.get("gap_id") == evidence.get("gap_id")
            and preview_binding_sha256(existing) == preview_binding_sha256(evidence)
        ):
            return {
                "runner_result": "PASS",
                "mode": "GENERIC_RECOVERY_AUTHORIZE",
                "authorized": True,
                "write_result": "IDEMPOTENT",
                "evidence_path": str(path),
                "gap_id": evidence["gap_id"],
                "blockers": [],
            }
        return _blocked(
            "existing_gap_id_content_conflict",
            mode="GENERIC_RECOVERY_AUTHORIZE",
        )
    existing_payloads, blockers = _load_generic_payloads(path.parent)
    if blockers:
        return _blocked(
            "existing_generic_evidence_invalid",
            blockers,
            mode="GENERIC_RECOVERY_AUTHORIZE",
        )
    collision = assess_gap_collisions(evidence, existing_payloads)
    if collision.state is not CollisionState.NONE:
        return _blocked(
            "generic_gap_collision",
            collision.relationships,
            mode="GENERIC_RECOVERY_AUTHORIZE",
        )
    legacy, legacy_blockers = _legacy_authorizations(
        workspace_path, account_id, calendar
    )
    if legacy_blockers:
        return _blocked(
            "legacy_recovery_invalid",
            legacy_blockers,
            mode="GENERIC_RECOVERY_AUTHORIZE",
        )
    candidate_dates = set(evidence["gap"]["trading_dates"])
    if any(
        candidate_dates.intersection(item["gap"]["trading_dates"])
        or item["resume"]["runbook_day_id"] == evidence["resume"]["runbook_day_id"]
        for item in legacy
    ):
        return _blocked(
            "legacy_generic_authorization_conflict",
            mode="GENERIC_RECOVERY_AUTHORIZE",
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        return _blocked(
            "generic_evidence_create_race",
            mode="GENERIC_RECOVERY_AUTHORIZE",
        )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(render_evidence(evidence))
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
        "mode": "GENERIC_RECOVERY_AUTHORIZE",
        "authorized": True,
        "write_result": "CREATED",
        "evidence_path": str(path),
        "gap_id": evidence["gap_id"],
        "blockers": [],
    }


def authorize_progressed_active_recovery(
    *args: Any,
    allow_test_write: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    preview = preview_progressed_active_recovery(*args, **kwargs)
    if preview["runner_result"] != "PASS":
        return preview | {"mode": "RECOVERY_AUTHORIZE"}
    if not PRODUCTION_ACTIVATION_ENABLED and not allow_test_write:
        return _blocked(
            "ntg_production_activation_disabled",
            mode="RECOVERY_AUTHORIZE",
        ) | {
            "producer": preview["producer"],
            "preview_sha256": preview["preview_sha256"],
        }
    return write_generic_authorization(
        kwargs.get("workspace", args[0] if args else None),
        evidence=preview["evidence"],
        expected_preview_sha256=preview["preview_sha256"],
        calendar=kwargs["calendar"],
        account_root=kwargs.get("account_root"),
        account_mode_resolver=kwargs.get(
            "account_mode_resolver", resolve_authoritative_account_mode
        ),
    )


def authorize_terminal_proven_no_trade_recovery(
    *args: Any,
    allow_test_write: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    preview = preview_terminal_proven_no_trade_recovery(*args, **kwargs)
    if preview["runner_result"] != "PASS":
        return preview | {"mode": "RECOVERY_AUTHORIZE"}
    if not PRODUCTION_ACTIVATION_ENABLED and not allow_test_write:
        return _blocked(
            "ntg_production_activation_disabled",
            mode="RECOVERY_AUTHORIZE",
        ) | {
            "producer": preview["producer"],
            "preview_sha256": preview["preview_sha256"],
        }
    return write_generic_authorization(
        kwargs.get("workspace", args[0] if args else None),
        evidence=preview["evidence"],
        expected_preview_sha256=preview["preview_sha256"],
        calendar=kwargs["calendar"],
        account_root=kwargs.get("account_root"),
        account_mode_resolver=kwargs.get(
            "account_mode_resolver", resolve_authoritative_account_mode
        ),
    )

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

from core.paper_account_paths import build_paper_account_paths
from core.paper_account_profile import resolve_paper_account_profile
from core.runbook_calendar import CALENDAR_SCHEMA_VERSION, CalendarCoverageError, MarketCalendar
from scripts import runbook_state


SCHEMA_VERSION = "operational_no_trade_gap.v1"
CONSUMPTION_MODE = "EXACT_TARGET_STATE_EXISTENCE"
INITIAL_POLICY_KEYS = (
    ("PROGRESSED_ACTIVE_NO_TRADE", 1),
    ("TERMINAL_PROVEN_NO_TRADE", 1),
)
FORBIDDEN_POLICY_TYPES = frozenset({"OTHER", "GENERIC_ANY_REASON"})
POLICY_TYPE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
TARGET_ARTIFACT_DIRS = (
    "artifacts",
    "command_runs",
    "stage_runs",
    "gate_runs",
    "reconciliation_runs",
    "verification_runs",
    "completion_manifests",
    "no_action_runs",
)
SUPPORTED_ACCOUNT_MODES = frozenset({"PAPER", "TEST"})


def resolve_authoritative_account_mode(account_id: str) -> str:
    """Resolve account mode from the canonical account profile, never its ID text."""

    return resolve_paper_account_profile(account_id).account_type.upper()


def _canonical_json_text(payload: Any) -> str:
    return json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_json_sha256(payload: Any) -> str:
    return hashlib.sha256(_canonical_json_text(payload).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class OperationalNoTradeGapEvidence:
    """Immutable, data-only representation of one generic gap evidence payload."""

    _canonical_json: str

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "OperationalNoTradeGapEvidence":
        if not isinstance(payload, Mapping):
            raise ValueError("evidence_payload_must_be_object")
        try:
            canonical = _canonical_json_text(dict(payload))
        except (TypeError, ValueError) as exc:
            raise ValueError("evidence_payload_not_json_serializable") from exc
        return cls(canonical)

    @classmethod
    def parse(cls, raw: str | bytes) -> "OperationalNoTradeGapEvidence":
        try:
            text = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
            payload = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid_evidence_json") from exc
        if not isinstance(payload, dict):
            raise ValueError("evidence_payload_must_be_object")
        return cls.from_mapping(payload)

    def to_mapping(self) -> dict[str, Any]:
        return json.loads(self._canonical_json)

    def render(self) -> str:
        return json.dumps(
            self.to_mapping(),
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n"


def parse_evidence(raw: str | bytes) -> OperationalNoTradeGapEvidence:
    return OperationalNoTradeGapEvidence.parse(raw)


def render_evidence(payload: Mapping[str, Any] | OperationalNoTradeGapEvidence) -> str:
    model = (
        payload
        if isinstance(payload, OperationalNoTradeGapEvidence)
        else OperationalNoTradeGapEvidence.from_mapping(payload)
    )
    return model.render()


@dataclass(frozen=True)
class PolicyAssessment:
    eligible: bool
    blockers: tuple[str, ...] = ()


class GapSourcePolicy(Protocol):
    policy_type: str
    policy_version: int

    def assess_eligibility(self, source: Mapping[str, Any]) -> PolicyAssessment: ...

    def bind_source_evidence(self, source: Mapping[str, Any]) -> dict[str, Any]: ...

    def validate_source_still_valid(self, source: Mapping[str, Any]) -> PolicyAssessment: ...


@dataclass(frozen=True)
class ContractSourcePolicy:
    policy_type: str
    policy_version: int
    accepted_lifecycles: frozenset[str]

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
        identity = str(source.get("identity") or "").strip()
        lifecycle = str(source.get("lifecycle") or "").strip()
        refs = source.get("refs")
        if not identity:
            blockers.append("source_identity_required")
        if lifecycle not in self.accepted_lifecycles:
            blockers.append("source_lifecycle_not_accepted")
        if not isinstance(refs, list) or not refs:
            blockers.append("source_refs_required")
        return PolicyAssessment(not blockers, tuple(blockers))


class SourcePolicyRegistry:
    def __init__(self) -> None:
        self._policies: dict[tuple[str, int], GapSourcePolicy] = {}

    def register(self, policy: GapSourcePolicy) -> None:
        policy_type = str(policy.policy_type or "").strip()
        policy_version = policy.policy_version
        if (
            not POLICY_TYPE_PATTERN.fullmatch(policy_type)
            or policy_type in FORBIDDEN_POLICY_TYPES
        ):
            raise ValueError("invalid_source_policy_type")
        if isinstance(policy_version, bool) or not isinstance(policy_version, int) or policy_version <= 0:
            raise ValueError("invalid_source_policy_version")
        key = (policy_type, policy_version)
        if key in self._policies:
            raise ValueError("duplicate_source_policy")
        self._policies[key] = policy

    def resolve(self, policy_type: str, policy_version: int) -> GapSourcePolicy | None:
        if isinstance(policy_version, bool) or not isinstance(policy_version, int):
            return None
        return self._policies.get((str(policy_type or "").strip(), policy_version))

    @property
    def keys(self) -> tuple[tuple[str, int], ...]:
        return tuple(sorted(self._policies))


def build_default_policy_registry() -> SourcePolicyRegistry:
    registry = SourcePolicyRegistry()
    registry.register(
        ContractSourcePolicy(
            "PROGRESSED_ACTIVE_NO_TRADE",
            1,
            frozenset({"ACTIVE_INCOMPLETE"}),
        )
    )
    registry.register(
        ContractSourcePolicy(
            "TERMINAL_PROVEN_NO_TRADE",
            1,
            frozenset({"FAILED_NO_TRADE_CLOSED"}),
        )
    )
    return registry


DEFAULT_POLICY_REGISTRY = build_default_policy_registry()


def _parse_iso_date(value: Any, field: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"invalid_{field}") from exc


def canonical_gap_trading_dates(
    calendar: MarketCalendar,
    start_date: str,
    end_date: str,
) -> tuple[str, ...]:
    start = _parse_iso_date(start_date, "gap_start_date")
    end = _parse_iso_date(end_date, "gap_end_date")
    if end < start:
        raise ValueError("gap_end_precedes_start")
    if not calendar.is_trading_day(start):
        raise ValueError("gap_start_not_trading_day")
    if not calendar.is_trading_day(end):
        raise ValueError("gap_end_not_trading_day")
    values: list[str] = []
    current = start
    while current <= end:
        if calendar.is_trading_day(current):
            values.append(current.isoformat())
        current += timedelta(days=1)
    if not values:
        raise ValueError("gap_interval_empty")
    return tuple(values)


def derive_canonical_gap_resume(
    *,
    account_id: str,
    gap_start_date: str,
    resume_data_date: str,
    calendar: MarketCalendar,
) -> tuple[tuple[str, ...], dict[str, str]]:
    """Derive the canonical gap interval and exact resume target."""

    gap_dates = canonical_gap_trading_dates(
        calendar, gap_start_date, resume_data_date
    )
    resume_trade_date = calendar.next_trading_day(
        _parse_iso_date(resume_data_date, "resume_data_date")
    ).isoformat()
    return gap_dates, {
        "data_date": resume_data_date,
        "trade_date": resume_trade_date,
        "runbook_day_id": runbook_state.get_runbook_day_id(
            account_id, resume_data_date, resume_trade_date
        ),
    }


def build_calendar_projection(
    calendar: MarketCalendar,
    start_date: str,
    resume_trade_date: str,
) -> dict[str, Any]:
    start = _parse_iso_date(start_date, "gap_start_date")
    end = _parse_iso_date(resume_trade_date, "resume_trade_date")
    if end < start:
        raise ValueError("calendar_projection_reversed")
    dated_results: list[dict[str, Any]] = []
    current = start
    while current <= end:
        dated_results.append(
            {
                "date": current.isoformat(),
                "is_trading_day": calendar.is_trading_day(current),
            }
        )
        current += timedelta(days=1)
    return {
        "schema_version": CALENDAR_SCHEMA_VERSION,
        "market": calendar.market,
        "timezone": calendar.timezone,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "dated_results": dated_results,
    }


def calendar_projection_sha256(
    calendar: MarketCalendar,
    start_date: str,
    resume_trade_date: str,
) -> str:
    return canonical_json_sha256(
        build_calendar_projection(calendar, start_date, resume_trade_date)
    )


def _read_csv_rows(path: Path, required_columns: set[str]) -> tuple[list[dict[str, str]], list[str]]:
    if not path.is_file():
        return [], [f"domain_file_missing:{path.name}"]
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            columns = set(reader.fieldnames or ())
            missing = sorted(required_columns - columns)
            if missing:
                return [], [f"domain_columns_missing:{path.name}:{','.join(missing)}"]
            return [dict(row) for row in reader], []
    except (OSError, UnicodeError, csv.Error) as exc:
        return [], [f"domain_file_invalid:{path.name}:{type(exc).__name__}"]


def _date_row_count(
    rows: Sequence[Mapping[str, str]],
    column: str,
    protected_dates: set[str],
) -> tuple[int, list[str]]:
    count = 0
    blockers: list[str] = []
    for index, row in enumerate(rows, start=2):
        raw = str(row.get(column) or "").strip()
        try:
            normalized = date.fromisoformat(raw).isoformat()
        except ValueError:
            blockers.append(f"domain_invalid_date:{column}:row_{index}")
            continue
        if normalized in protected_dates:
            count += 1
    return count, blockers


def scan_domain_no_write(
    *,
    account_id: str,
    trading_dates: Sequence[str],
    expected_trade_ids: Sequence[str],
    account_root: str | Path,
) -> dict[str, Any]:
    protected_dates = {date.fromisoformat(str(item)).isoformat() for item in trading_dates}
    expected_ids = tuple(dict.fromkeys(str(item).strip() for item in expected_trade_ids if str(item).strip()))
    paths = build_paper_account_paths(
        account_id=account_id,
        account_root=Path(account_root),
        create=False,
    )
    blockers: list[str] = []

    execution_rows, errors = _read_csv_rows(paths.execution_log_path, {"date", "trade_id"})
    blockers.extend(errors)
    execution_count, errors = _date_row_count(execution_rows, "date", protected_dates)
    blockers.extend(errors)
    ledger_ids = {str(row.get("trade_id") or "").strip() for row in execution_rows}
    present_expected = [item for item in expected_ids if item in ledger_ids]
    if execution_count:
        blockers.append(f"gap_execution_rows_present:{execution_count}")
    if present_expected:
        blockers.append(f"expected_trade_ids_present:{','.join(present_expected)}")

    account_rows, errors = _read_csv_rows(paths.account_snapshot_path, {"snapshot_date"})
    blockers.extend(errors)
    account_count, errors = _date_row_count(account_rows, "snapshot_date", protected_dates)
    blockers.extend(errors)
    if account_count:
        blockers.append(f"gap_account_snapshot_rows_present:{account_count}")

    position_rows, errors = _read_csv_rows(paths.position_snapshot_path, {"snapshot_date"})
    blockers.extend(errors)
    position_count, errors = _date_row_count(position_rows, "snapshot_date", protected_dates)
    blockers.extend(errors)
    if position_count:
        blockers.append(f"gap_position_snapshot_rows_present:{position_count}")

    current_state_paths = [paths.current_state_snapshot_path(item) for item in sorted(protected_dates)]
    current_state_present = [str(path.resolve(strict=False)) for path in current_state_paths if path.is_file()]
    if current_state_present:
        blockers.append(f"gap_current_state_files_present:{len(current_state_present)}")

    def file_proof(path: Path, count: int) -> dict[str, Any]:
        return {
            "path": str(path.resolve(strict=False)),
            "exists": path.is_file(),
            "sha256_at_scan": sha256_file(path) if path.is_file() else None,
            "protected_date_row_count": count,
        }

    return {
        "valid": not blockers,
        "blockers": tuple(dict.fromkeys(blockers)),
        "no_trade": {
            "execution": {
                **file_proof(paths.execution_log_path, execution_count),
                "expected_trade_ids_present": present_expected,
            },
            "expected_trade_ids": list(expected_ids),
        },
        "domain_no_write": {
            "account": file_proof(paths.account_snapshot_path, account_count),
            "position": file_proof(paths.position_snapshot_path, position_count),
            "current_state": {
                "paths": [str(path.resolve(strict=False)) for path in current_state_paths],
                "present_paths": current_state_present,
            },
        },
    }


def source_assessment_sha256(source: Mapping[str, Any]) -> str:
    bound = {
        "identity": source.get("identity"),
        "lifecycle": source.get("lifecycle"),
        "refs": source.get("refs"),
    }
    return canonical_json_sha256(bound)


def gap_identity_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    source = payload.get("source") if isinstance(payload.get("source"), Mapping) else {}
    no_trade = payload.get("no_trade") if isinstance(payload.get("no_trade"), Mapping) else {}
    return {
        "schema_version": payload.get("schema_version"),
        "account_id": payload.get("account_id"),
        "account_mode": payload.get("account_mode"),
        "source_policy": payload.get("source_policy"),
        "source": {
            "identity": source.get("identity"),
            "lifecycle": source.get("lifecycle"),
            "refs": source.get("refs"),
            "assessment_sha256": source.get("assessment_sha256"),
        },
        "gap": payload.get("gap"),
        "expected_trade_ids": no_trade.get("expected_trade_ids"),
        "resume": payload.get("resume"),
    }


def compute_gap_id(payload: Mapping[str, Any]) -> str:
    return "sha256:" + canonical_json_sha256(gap_identity_payload(payload))


def seal_evidence(payload: Mapping[str, Any]) -> dict[str, Any]:
    sealed = json.loads(json.dumps(dict(payload)))
    sealed.pop("gap_id", None)
    sealed.pop("content_sha256", None)
    source = sealed.get("source")
    if not isinstance(source, dict):
        raise ValueError("source_required")
    source["assessment_sha256"] = source_assessment_sha256(source)
    sealed["gap_id"] = compute_gap_id(sealed)
    sealed["content_sha256"] = canonical_json_sha256(sealed)
    return sealed


def _validate_source_refs(source: Mapping[str, Any], workspace: Path) -> list[str]:
    refs = source.get("refs")
    if not isinstance(refs, list) or not refs:
        return ["source_refs_required"]
    blockers: list[str] = []
    workspace = workspace.resolve(strict=False)
    for index, item in enumerate(refs):
        if not isinstance(item, Mapping):
            blockers.append(f"source_ref_invalid:{index}")
            continue
        ref = str(item.get("path") or "").strip()
        expected_sha = str(item.get("sha256") or "").strip().lower()
        path = Path(ref)
        if path.is_absolute():
            blockers.append(f"source_ref_must_be_relative:{index}")
            continue
        resolved = (workspace / path).resolve(strict=False)
        try:
            resolved.relative_to(workspace)
        except ValueError:
            blockers.append(f"source_ref_outside_workspace:{index}")
            continue
        if not resolved.is_file():
            blockers.append(f"source_ref_missing:{index}")
        elif not SHA256_PATTERN.fullmatch(expected_sha) or sha256_file(resolved) != expected_sha:
            blockers.append(f"source_ref_sha256_mismatch:{index}")
    return blockers


def _proof_shape_matches(stored: Any, current: Mapping[str, Any], kind: str) -> bool:
    if not isinstance(stored, Mapping):
        return False
    if kind == "current_state":
        return (
            stored.get("paths") == current.get("paths")
            and stored.get("present_paths") == []
            and current.get("present_paths") == []
        )
    return (
        stored.get("path") == current.get("path")
        and stored.get("exists") is True
        and stored.get("protected_date_row_count") == 0
        and current.get("protected_date_row_count") == 0
    )


@dataclass(frozen=True)
class EvidenceValidation:
    valid: bool
    blockers: tuple[str, ...]
    policy_key: tuple[str, int] | None


def validate_evidence(
    payload: Mapping[str, Any] | OperationalNoTradeGapEvidence,
    *,
    calendar: MarketCalendar,
    workspace: str | Path,
    account_root: str | Path,
    registry: SourcePolicyRegistry = DEFAULT_POLICY_REGISTRY,
    account_mode_resolver: Callable[[str], str] = resolve_authoritative_account_mode,
) -> EvidenceValidation:
    if isinstance(payload, OperationalNoTradeGapEvidence):
        payload = payload.to_mapping()
    blockers: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        blockers.append("unsupported_schema_version")

    policy_data = payload.get("source_policy")
    policy_key: tuple[str, int] | None = None
    policy: GapSourcePolicy | None = None
    if not isinstance(policy_data, Mapping):
        blockers.append("source_policy_required")
    else:
        policy_type = str(policy_data.get("type") or "").strip()
        policy_version = policy_data.get("version")
        if isinstance(policy_version, int) and not isinstance(policy_version, bool):
            policy_key = (policy_type, policy_version)
            policy = registry.resolve(policy_type, policy_version)
        if policy is None:
            blockers.append("unsupported_source_policy")

    account_id = str(payload.get("account_id") or "").strip()
    account_mode = str(payload.get("account_mode") or "").strip().upper()
    try:
        authoritative_mode = str(account_mode_resolver(account_id) or "").strip().upper()
    except (OSError, UnicodeError, ValueError, RuntimeError):
        authoritative_mode = ""
        blockers.append("authoritative_account_mode_unavailable")
    if authoritative_mode and authoritative_mode != account_mode:
        blockers.append("account_mode_mismatch")
    if account_mode not in SUPPORTED_ACCOUNT_MODES or (
        authoritative_mode and authoritative_mode not in SUPPORTED_ACCOUNT_MODES
    ):
        blockers.append("paper_or_test_account_required")

    source = payload.get("source")
    if not isinstance(source, Mapping):
        blockers.append("source_required")
        source = {}
    if policy is not None:
        blockers.extend(policy.validate_source_still_valid(source).blockers)
    try:
        expected_assessment = source_assessment_sha256(source)
        if source.get("assessment_sha256") != expected_assessment:
            blockers.append("source_assessment_sha256_mismatch")
    except (TypeError, ValueError):
        blockers.append("source_assessment_invalid")
    blockers.extend(_validate_source_refs(source, Path(workspace)))

    incident = payload.get("incident")
    if not isinstance(incident, Mapping):
        blockers.append("incident_required")
    else:
        if not str(incident.get("reason_code") or "").strip():
            blockers.append("incident_reason_code_required")
        if not str(incident.get("reason_text") or "").strip():
            blockers.append("incident_reason_text_required")

    gap = payload.get("gap")
    resume = payload.get("resume")
    calendar_data = payload.get("calendar")
    gap_dates: tuple[str, ...] = ()
    if not isinstance(gap, Mapping) or not isinstance(resume, Mapping):
        blockers.append("gap_and_resume_required")
    else:
        start_date = str(gap.get("start_date") or "")
        end_date = str(gap.get("end_date") or "")
        data_date = str(resume.get("data_date") or "")
        trade_date = str(resume.get("trade_date") or "")
        if end_date != data_date:
            blockers.append("resume_data_date_must_equal_gap_end")
        try:
            gap_dates, expected_resume = derive_canonical_gap_resume(
                account_id=account_id,
                gap_start_date=start_date,
                resume_data_date=data_date,
                calendar=calendar,
            )
            if list(gap_dates) != gap.get("trading_dates"):
                blockers.append("gap_trading_dates_mismatch")
            if expected_resume["trade_date"] != trade_date:
                blockers.append("resume_trade_date_not_next_trading_day")
            if resume.get("runbook_day_id") != expected_resume["runbook_day_id"]:
                blockers.append("resume_runbook_day_id_mismatch")
            expected_projection = calendar_projection_sha256(calendar, start_date, trade_date)
            if not isinstance(calendar_data, Mapping):
                blockers.append("calendar_required")
            else:
                expected_calendar = {
                    "schema_version": CALENDAR_SCHEMA_VERSION,
                    "market": calendar.market,
                    "timezone": calendar.timezone,
                    "projection_sha256": expected_projection,
                }
                for field, expected in expected_calendar.items():
                    if calendar_data.get(field) != expected:
                        blockers.append(f"calendar_{field}_mismatch")
        except (ValueError, CalendarCoverageError) as exc:
            blockers.append(str(exc))

    no_trade = payload.get("no_trade")
    expected_trade_ids: list[str] = []
    if not isinstance(no_trade, Mapping):
        blockers.append("no_trade_required")
    else:
        values = no_trade.get("expected_trade_ids")
        if not isinstance(values, list):
            blockers.append("expected_trade_ids_must_be_list")
        else:
            expected_trade_ids = [str(item) for item in values]

    if gap_dates:
        try:
            domain = scan_domain_no_write(
                account_id=account_id,
                trading_dates=gap_dates,
                expected_trade_ids=expected_trade_ids,
                account_root=account_root,
            )
            blockers.extend(domain["blockers"])
            stored_domain = payload.get("domain_no_write")
            current_domain = domain["domain_no_write"]
            stored_execution = no_trade.get("execution") if isinstance(no_trade, Mapping) else None
            current_execution = domain["no_trade"]["execution"]
            if not _proof_shape_matches(stored_execution, current_execution, "execution"):
                blockers.append("execution_proof_mismatch")
            if isinstance(stored_execution, Mapping) and stored_execution.get("expected_trade_ids_present") != []:
                blockers.append("execution_expected_ids_not_absent")
            if not isinstance(stored_domain, Mapping):
                blockers.append("domain_no_write_required")
            else:
                for kind in ("account", "position", "current_state"):
                    if not _proof_shape_matches(stored_domain.get(kind), current_domain[kind], kind):
                        blockers.append(f"{kind}_proof_mismatch")
        except (OSError, ValueError) as exc:
            blockers.append(f"domain_scan_invalid:{type(exc).__name__}")

    no_backfill = payload.get("no_backfill")
    if not isinstance(no_backfill, Mapping) or no_backfill.get("confirmed") is not True:
        blockers.append("no_backfill_confirmation_required")
    if not str(payload.get("operator") or "").strip():
        blockers.append("operator_required")
    try:
        created_at = datetime.fromisoformat(str(payload.get("created_at") or ""))
        if created_at.tzinfo is None:
            raise ValueError
    except ValueError:
        blockers.append("created_at_invalid")
    consumption = payload.get("consumption")
    if not isinstance(consumption, Mapping) or consumption.get("mode") != CONSUMPTION_MODE:
        blockers.append("consumption_mode_invalid")
    elif isinstance(resume, Mapping):
        expected_ref = (
            Path(runbook_state.STATE_DIRNAME) / f"{resume.get('runbook_day_id')}.json"
        ).as_posix()
        if consumption.get("target_state_ref") != expected_ref:
            blockers.append("consumption_target_state_ref_mismatch")

    try:
        expected_gap_id = compute_gap_id(payload)
        if payload.get("gap_id") != expected_gap_id:
            blockers.append("gap_id_mismatch")
    except (TypeError, ValueError):
        blockers.append("gap_identity_invalid")
    content = dict(payload)
    stored_content_sha = str(content.pop("content_sha256", ""))
    try:
        if stored_content_sha != canonical_json_sha256(content):
            blockers.append("content_sha256_mismatch")
    except (TypeError, ValueError):
        blockers.append("content_payload_invalid")
    return EvidenceValidation(
        valid=not blockers,
        blockers=tuple(dict.fromkeys(blockers)),
        policy_key=policy_key,
    )


class CollisionState(str, Enum):
    NONE = "NONE"
    CONFLICT = "CONFLICT"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True)
class CollisionResult:
    state: CollisionState
    conflict_gap_ids: tuple[str, ...]
    relationships: tuple[str, ...]


def _interval_relationship(candidate: Mapping[str, Any], existing: Mapping[str, Any]) -> str | None:
    candidate_gap = candidate.get("gap") if isinstance(candidate.get("gap"), Mapping) else {}
    existing_gap = existing.get("gap") if isinstance(existing.get("gap"), Mapping) else {}
    candidate_dates = set(candidate_gap.get("trading_dates") or ())
    existing_dates = set(existing_gap.get("trading_dates") or ())
    if not candidate_dates.intersection(existing_dates):
        return None
    if candidate_dates == existing_dates:
        return "IDENTICAL"
    if candidate_dates < existing_dates:
        return "NESTED"
    if candidate_dates > existing_dates:
        return "CONTAINING"
    return "PARTIAL_OVERLAP"


def assess_gap_collisions(
    candidate: Mapping[str, Any],
    existing_evidence: Sequence[Mapping[str, Any]],
) -> CollisionResult:
    account_id = candidate.get("account_id")
    conflict_ids: list[str] = []
    relationships: list[str] = []
    for existing in existing_evidence:
        if existing.get("account_id") != account_id:
            continue
        relationship = _interval_relationship(candidate, existing)
        if relationship is None:
            continue
        conflict_ids.append(str(existing.get("gap_id") or ""))
        relationships.append(relationship)
    state = (
        CollisionState.NONE
        if not conflict_ids
        else CollisionState.CONFLICT
        if len(conflict_ids) == 1
        else CollisionState.AMBIGUOUS
    )
    return CollisionResult(state, tuple(conflict_ids), tuple(relationships))


class ConsumptionState(str, Enum):
    UNCONSUMED = "UNCONSUMED"
    CONSUMED = "CONSUMED"
    INVALID = "INVALID"


@dataclass(frozen=True)
class ConsumptionResult:
    state: ConsumptionState
    blockers: tuple[str, ...]
    target_state_path: Path


def derive_consumption_state(
    evidence: Mapping[str, Any],
    *,
    workspace: str | Path,
    all_evidence: Sequence[Mapping[str, Any]] = (),
    artifact_dirnames: Sequence[str] = TARGET_ARTIFACT_DIRS,
) -> ConsumptionResult:
    workspace_path = Path(workspace).resolve(strict=False)
    resume = evidence.get("resume") if isinstance(evidence.get("resume"), Mapping) else {}
    target_id = str(resume.get("runbook_day_id") or "")
    target_path = runbook_state.get_state_path_for_runbook_day_id(workspace_path, target_id)
    blockers: list[str] = []
    same_target = [
        item
        for item in all_evidence
        if isinstance(item.get("resume"), Mapping)
        and item["resume"].get("runbook_day_id") == target_id
        and item.get("account_id") == evidence.get("account_id")
    ]
    if len(same_target) > 1:
        blockers.append("multiple_evidence_bind_same_target")

    artifact_exists = any(
        (workspace_path / dirname / target_id).exists() for dirname in artifact_dirnames
    )
    if not target_path.is_file():
        if artifact_exists:
            blockers.append("target_artifact_exists_without_state")
        return ConsumptionResult(
            ConsumptionState.INVALID if blockers else ConsumptionState.UNCONSUMED,
            tuple(blockers),
            target_path,
        )
    try:
        state = runbook_state.load_state(target_path)
        if not runbook_state.context_matches_state(
            state,
            str(evidence.get("account_id") or ""),
            str(resume.get("data_date") or ""),
            str(resume.get("trade_date") or ""),
        ) or state.runbook_day_id != target_id:
            blockers.append("target_state_context_mismatch")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        blockers.append("target_state_invalid")
    return ConsumptionResult(
        ConsumptionState.INVALID if blockers else ConsumptionState.CONSUMED,
        tuple(blockers),
        target_path,
    )

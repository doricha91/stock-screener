from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping

import pytest

from core.operational_no_trade_gap import (
    CollisionState,
    ConsumptionState,
    ContractSourcePolicy,
    OperationalNoTradeGapEvidence,
    PolicyAssessment,
    SCHEMA_VERSION,
    SourcePolicyRegistry,
    assess_gap_collisions,
    build_calendar_projection,
    build_default_policy_registry,
    calendar_projection_sha256,
    canonical_gap_trading_dates,
    derive_consumption_state,
    parse_evidence,
    render_evidence,
    seal_evidence,
    scan_domain_no_write,
    sha256_file,
    validate_evidence,
)
from core.runbook_calendar import MarketCalendar
from scripts import runbook_state


ACCOUNT_ID = "paper_ntg2"
GAP_START = "2026-07-02"
GAP_END = "2026-07-06"
RESUME_TRADE_DATE = "2026-07-07"
EXPECTED_ID = "trade:expected"


def _calendar(*, coverage_end: date = date(2026, 7, 31), extra_holidays: set[date] | None = None) -> MarketCalendar:
    return MarketCalendar(
        market="NYSE",
        timezone="America/New_York",
        coverage_start=date(2026, 7, 1),
        coverage_end=coverage_end,
        holidays=frozenset({date(2026, 7, 3), *(extra_holidays or set())}),
    )


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows or [])


def _append_csv(path: Path, row: dict[str, str]) -> None:
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writerow(row)


def _seed_domain(root: Path) -> None:
    _write_csv(root / "paper_execution_log.csv", ["date", "trade_id"])
    _write_csv(root / "paper_account_snapshot.csv", ["snapshot_date"])
    _write_csv(root / "paper_position_snapshot.csv", ["snapshot_date"])


def _build_evidence(
    tmp_path: Path,
    *,
    policy_type: str = "PROGRESSED_ACTIVE_NO_TRADE",
    policy_version: int = 1,
    lifecycle: str = "ACTIVE_INCOMPLETE",
    reason_code: str = "NOTION_OUTAGE",
    reason_text: str = "Notion was unavailable.",
    calendar: MarketCalendar | None = None,
) -> tuple[dict[str, Any], Path, Path, MarketCalendar]:
    workspace = tmp_path / "workspace"
    source_path = workspace / "sources" / "source.json"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text('{"source":"pinned"}\n', encoding="utf-8")
    account_root = tmp_path / "account"
    _seed_domain(account_root)
    calendar = calendar or _calendar()
    trading_dates = canonical_gap_trading_dates(calendar, GAP_START, GAP_END)
    domain = scan_domain_no_write(
        account_id=ACCOUNT_ID,
        trading_dates=trading_dates,
        expected_trade_ids=[EXPECTED_ID],
        account_root=account_root,
    )
    assert domain["valid"] is True
    runbook_day_id = runbook_state.get_runbook_day_id(
        ACCOUNT_ID, GAP_END, RESUME_TRADE_DATE
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "account_id": ACCOUNT_ID,
        "account_mode": "PAPER",
        "source_policy": {"type": policy_type, "version": policy_version},
        "source": {
            "identity": "source:runbook:2026-07-02",
            "lifecycle": lifecycle,
            "refs": [
                {
                    "path": "sources/source.json",
                    "sha256": sha256_file(source_path),
                }
            ],
        },
        "incident": {"reason_code": reason_code, "reason_text": reason_text},
        "gap": {
            "start_date": GAP_START,
            "end_date": GAP_END,
            "trading_dates": list(trading_dates),
        },
        "calendar": {
            "schema_version": "us_market_holidays.v1",
            "market": calendar.market,
            "timezone": calendar.timezone,
            "projection_sha256": calendar_projection_sha256(
                calendar, GAP_START, RESUME_TRADE_DATE
            ),
        },
        "no_trade": domain["no_trade"],
        "domain_no_write": domain["domain_no_write"],
        "no_backfill": {"confirmed": True},
        "resume": {
            "data_date": GAP_END,
            "trade_date": RESUME_TRADE_DATE,
            "runbook_day_id": runbook_day_id,
        },
        "operator": "ntg2-test",
        "created_at": "2026-09-15T10:00:00+09:00",
        "consumption": {
            "mode": "EXACT_TARGET_STATE_EXISTENCE",
            "target_state_ref": f"runbook_states/{runbook_day_id}.json",
        },
    }
    return seal_evidence(payload), workspace, account_root, calendar


def _validate(
    evidence: Mapping[str, Any],
    workspace: Path,
    account_root: Path,
    calendar: MarketCalendar,
    *,
    registry: SourcePolicyRegistry | None = None,
):
    kwargs: dict[str, Any] = {}
    if registry is not None:
        kwargs["registry"] = registry
    kwargs["account_mode_resolver"] = lambda _account_id: evidence.get(
        "account_mode", ""
    )
    return validate_evidence(
        evidence,
        calendar=calendar,
        workspace=workspace,
        account_root=account_root,
        **kwargs,
    )


@pytest.mark.parametrize(
    ("account_id", "stored_mode", "authoritative_mode", "expected_valid"),
    [
        ("qa_ntg_01", "TEST", "TEST", True),
        ("paper_live_money", "PAPER", "LIVE", False),
    ],
)
def test_account_scope_uses_authoritative_mode_not_account_id_naming(
    tmp_path: Path,
    account_id: str,
    stored_mode: str,
    authoritative_mode: str,
    expected_valid: bool,
) -> None:
    evidence, workspace, account_root, calendar = _build_evidence(tmp_path)
    evidence["account_id"] = account_id
    evidence["account_mode"] = stored_mode
    runbook_day_id = runbook_state.get_runbook_day_id(
        account_id, GAP_END, RESUME_TRADE_DATE
    )
    evidence["resume"]["runbook_day_id"] = runbook_day_id
    evidence["consumption"]["target_state_ref"] = (
        f"runbook_states/{runbook_day_id}.json"
    )
    evidence = seal_evidence(evidence)

    result = validate_evidence(
        evidence,
        calendar=calendar,
        workspace=workspace,
        account_root=account_root,
        account_mode_resolver=lambda _account_id: authoritative_mode,
    )

    assert result.valid is expected_valid
    if expected_valid:
        assert result.blockers == ()
    else:
        assert "account_mode_mismatch" in result.blockers
        assert "paper_or_test_account_required" in result.blockers


@pytest.mark.parametrize(
    ("policy_type", "lifecycle"),
    [
        ("PROGRESSED_ACTIVE_NO_TRADE", "ACTIVE_INCOMPLETE"),
        ("TERMINAL_PROVEN_NO_TRADE", "FAILED_NO_TRADE_CLOSED"),
    ],
)
def test_initial_policy_contract_fixtures_pass_shared_validation(
    tmp_path: Path, policy_type: str, lifecycle: str
) -> None:
    evidence, workspace, account_root, calendar = _build_evidence(
        tmp_path, policy_type=policy_type, lifecycle=lifecycle
    )

    result = _validate(evidence, workspace, account_root, calendar)

    assert result.valid is True
    assert result.policy_key == (policy_type, 1)
    assert build_default_policy_registry().keys == (
        ("PROGRESSED_ACTIVE_NO_TRADE", 1),
        ("TERMINAL_PROVEN_NO_TRADE", 1),
    )


def test_immutable_evidence_model_parse_render_round_trip(tmp_path: Path) -> None:
    evidence, workspace, account_root, calendar = _build_evidence(tmp_path)

    model = OperationalNoTradeGapEvidence.from_mapping(evidence)
    parsed = parse_evidence(render_evidence(model))
    detached = parsed.to_mapping()
    detached["incident"]["reason_text"] = "mutated copy"

    assert parsed == model
    assert parsed.to_mapping() == evidence
    assert parsed.to_mapping()["incident"]["reason_text"] != "mutated copy"
    assert _validate(parsed.to_mapping(), workspace, account_root, calendar).valid


@pytest.mark.parametrize("raw", ["not-json", "[]", b"\xff"])
def test_evidence_model_parse_rejects_invalid_payload(raw: str | bytes) -> None:
    with pytest.raises(ValueError):
        parse_evidence(raw)


def test_mapping_validator_fails_closed_on_non_json_payload(tmp_path: Path) -> None:
    evidence, workspace, account_root, calendar = _build_evidence(tmp_path)
    evidence["source"]["refs"][0]["sha256"] = {"not-json"}

    result = _validate(evidence, workspace, account_root, calendar)

    assert result.valid is False
    assert "source_assessment_invalid" in result.blockers
    assert "gap_identity_invalid" in result.blockers
    assert "content_payload_invalid" in result.blockers


def test_unknown_schema_and_content_tamper_fail_closed(tmp_path: Path) -> None:
    evidence, workspace, account_root, calendar = _build_evidence(tmp_path)
    evidence["schema_version"] = "operational_no_trade_gap.v2"

    result = _validate(evidence, workspace, account_root, calendar)

    assert "unsupported_schema_version" in result.blockers
    assert "content_sha256_mismatch" in result.blockers


def test_gap_identity_excludes_incident_reason_but_content_binds_it(tmp_path: Path) -> None:
    first, _, _, _ = _build_evidence(tmp_path / "first")
    second, _, _, _ = _build_evidence(
        tmp_path / "second",
        reason_code="NETWORK_OUTAGE",
        reason_text="The workstation network was unavailable.",
    )

    assert first["gap_id"] == second["gap_id"]
    assert first["content_sha256"] != second["content_sha256"]


def test_source_ref_tamper_fails_closed(tmp_path: Path) -> None:
    evidence, workspace, account_root, calendar = _build_evidence(tmp_path)
    (workspace / "sources" / "source.json").write_text("tampered", encoding="utf-8")

    result = _validate(evidence, workspace, account_root, calendar)

    assert "source_ref_sha256_mismatch:0" in result.blockers


@dataclass
class SpyPolicy:
    policy_type: str
    policy_version: int
    calls: list[int]

    def assess_eligibility(self, source: Mapping[str, Any]) -> PolicyAssessment:
        return PolicyAssessment(True)

    def bind_source_evidence(self, source: Mapping[str, Any]) -> dict[str, Any]:
        return dict(source)

    def validate_source_still_valid(self, source: Mapping[str, Any]) -> PolicyAssessment:
        self.calls.append(self.policy_version)
        return PolicyAssessment(True)


def test_registry_uses_exact_historical_policy_version(tmp_path: Path) -> None:
    calls: list[int] = []
    registry = SourcePolicyRegistry()
    registry.register(SpyPolicy("PROGRESSED_ACTIVE_NO_TRADE", 1, calls))
    registry.register(SpyPolicy("PROGRESSED_ACTIVE_NO_TRADE", 2, calls))
    evidence, workspace, account_root, calendar = _build_evidence(tmp_path)

    result = _validate(evidence, workspace, account_root, calendar, registry=registry)

    assert result.valid is True
    assert calls == [1]


@pytest.mark.parametrize(
    "policy_data",
    [
        {"type": "UNKNOWN_POLICY", "version": 1},
        {"type": "PROGRESSED_ACTIVE_NO_TRADE", "version": 3},
    ],
)
def test_unknown_policy_type_or_version_has_no_fallback(
    tmp_path: Path, policy_data: dict[str, Any]
) -> None:
    evidence, workspace, account_root, calendar = _build_evidence(tmp_path)
    evidence["source_policy"] = policy_data
    evidence = seal_evidence(evidence)

    result = _validate(evidence, workspace, account_root, calendar)

    assert "unsupported_source_policy" in result.blockers


def test_incident_reason_never_changes_registry_dispatch(tmp_path: Path) -> None:
    calls: list[int] = []
    registry = SourcePolicyRegistry()
    registry.register(SpyPolicy("PROGRESSED_ACTIVE_NO_TRADE", 1, calls))
    first, first_workspace, first_root, calendar = _build_evidence(tmp_path / "first")
    second, second_workspace, second_root, _ = _build_evidence(
        tmp_path / "second", reason_code="DEPLOYMENT_FAILURE", reason_text="Deploy failed."
    )

    assert _validate(first, first_workspace, first_root, calendar, registry=registry).valid
    assert _validate(second, second_workspace, second_root, calendar, registry=registry).valid
    assert calls == [1, 1]
    assert first["gap_id"] == second["gap_id"]


@pytest.mark.parametrize("policy_type", ["OTHER", "GENERIC_ANY_REASON"])
def test_catch_all_policy_registration_is_forbidden(policy_type: str) -> None:
    registry = SourcePolicyRegistry()
    with pytest.raises(ValueError, match="invalid_source_policy_type"):
        registry.register(ContractSourcePolicy(policy_type, 1, frozenset({"ANY"})))


def test_calendar_projection_excludes_weekend_and_holiday() -> None:
    calendar = _calendar()

    assert canonical_gap_trading_dates(calendar, GAP_START, GAP_END) == (
        "2026-07-02",
        "2026-07-06",
    )
    projection = build_calendar_projection(calendar, GAP_START, RESUME_TRADE_DATE)
    by_date = {item["date"]: item["is_trading_day"] for item in projection["dated_results"]}
    assert by_date["2026-07-03"] is False
    assert by_date["2026-07-04"] is False
    assert by_date["2026-07-05"] is False


@pytest.mark.parametrize(
    ("gap_end_date", "resume_trade_date"),
    [
        ("2026-07-05", "2026-07-06"),
        ("2026-07-03", "2026-07-06"),
    ],
    ids=["weekend-end", "holiday-end"],
)
def test_gap_end_boundary_must_be_trading_day(
    tmp_path: Path, gap_end_date: str, resume_trade_date: str
) -> None:
    calendar = _calendar()
    with pytest.raises(ValueError, match="gap_end_not_trading_day"):
        canonical_gap_trading_dates(calendar, GAP_START, gap_end_date)

    evidence, workspace, account_root, _ = _build_evidence(tmp_path, calendar=calendar)
    evidence["gap"]["end_date"] = gap_end_date
    evidence["gap"]["trading_dates"] = [GAP_START]
    evidence["resume"]["data_date"] = gap_end_date
    evidence["resume"]["trade_date"] = resume_trade_date
    evidence["resume"]["runbook_day_id"] = runbook_state.get_runbook_day_id(
        ACCOUNT_ID, gap_end_date, resume_trade_date
    )
    evidence["consumption"]["target_state_ref"] = (
        f"runbook_states/{evidence['resume']['runbook_day_id']}.json"
    )
    evidence["calendar"]["projection_sha256"] = calendar_projection_sha256(
        calendar, GAP_START, resume_trade_date
    )
    evidence = seal_evidence(evidence)

    result = _validate(evidence, workspace, account_root, calendar)

    assert result.valid is False
    assert "gap_end_not_trading_day" in result.blockers


def test_calendar_out_of_coverage_and_empty_list_fail(tmp_path: Path) -> None:
    evidence, workspace, account_root, calendar = _build_evidence(tmp_path)
    evidence["gap"]["start_date"] = "2026-06-30"
    evidence = seal_evidence(evidence)
    outside = _validate(evidence, workspace, account_root, calendar)
    assert any("calendar_coverage_exceeded" in item for item in outside.blockers)

    evidence, workspace, account_root, calendar = _build_evidence(tmp_path / "empty")
    evidence["gap"]["trading_dates"] = []
    evidence = seal_evidence(evidence)
    empty = _validate(evidence, workspace, account_root, calendar)
    assert "gap_trading_dates_mismatch" in empty.blockers


def test_wrong_resume_next_day_fails(tmp_path: Path) -> None:
    evidence, workspace, account_root, calendar = _build_evidence(tmp_path)
    evidence["resume"]["trade_date"] = "2026-07-08"
    evidence["resume"]["runbook_day_id"] = runbook_state.get_runbook_day_id(
        ACCOUNT_ID, GAP_END, "2026-07-08"
    )
    evidence["consumption"]["target_state_ref"] = (
        f"runbook_states/{evidence['resume']['runbook_day_id']}.json"
    )
    evidence["calendar"]["projection_sha256"] = calendar_projection_sha256(
        calendar, GAP_START, "2026-07-08"
    )
    evidence = seal_evidence(evidence)

    result = _validate(evidence, workspace, account_root, calendar)

    assert "resume_trade_date_not_next_trading_day" in result.blockers


def test_projection_drift_fails_but_unrelated_extension_does_not(tmp_path: Path) -> None:
    evidence, workspace, account_root, calendar = _build_evidence(tmp_path)
    extended_gap_end = "2026-07-07"
    extended_resume_trade_date = "2026-07-08"
    extended_gap_dates = canonical_gap_trading_dates(calendar, GAP_START, extended_gap_end)
    domain = scan_domain_no_write(
        account_id=ACCOUNT_ID,
        trading_dates=extended_gap_dates,
        expected_trade_ids=[EXPECTED_ID],
        account_root=account_root,
    )
    evidence["gap"] = {
        "start_date": GAP_START,
        "end_date": extended_gap_end,
        "trading_dates": list(extended_gap_dates),
    }
    evidence["resume"] = {
        "data_date": extended_gap_end,
        "trade_date": extended_resume_trade_date,
        "runbook_day_id": runbook_state.get_runbook_day_id(
            ACCOUNT_ID, extended_gap_end, extended_resume_trade_date
        ),
    }
    evidence["no_trade"] = domain["no_trade"]
    evidence["domain_no_write"] = domain["domain_no_write"]
    evidence["consumption"]["target_state_ref"] = (
        f"runbook_states/{evidence['resume']['runbook_day_id']}.json"
    )
    evidence["calendar"]["projection_sha256"] = calendar_projection_sha256(
        calendar, GAP_START, extended_resume_trade_date
    )
    evidence = seal_evidence(evidence)

    drifted = _calendar(extra_holidays={date(2026, 7, 6)})
    extended = _calendar(coverage_end=date(2026, 12, 31))

    drift = _validate(evidence, workspace, account_root, drifted)
    extension = _validate(evidence, workspace, account_root, extended)

    assert "calendar_projection_sha256_mismatch" in drift.blockers
    assert extension.valid is True
    assert calendar_projection_sha256(calendar, GAP_START, extended_resume_trade_date) == (
        calendar_projection_sha256(
            extended, GAP_START, extended_resume_trade_date
        )
    )


@pytest.mark.parametrize(
    ("filename", "field", "blocker"),
    [
        ("paper_execution_log.csv", "date", "gap_execution_rows_present:1"),
        ("paper_account_snapshot.csv", "snapshot_date", "gap_account_snapshot_rows_present:1"),
        ("paper_position_snapshot.csv", "snapshot_date", "gap_position_snapshot_rows_present:1"),
    ],
)
def test_gap_date_domain_row_fails(
    tmp_path: Path, filename: str, field: str, blocker: str
) -> None:
    evidence, workspace, account_root, calendar = _build_evidence(tmp_path)
    row = {field: GAP_START}
    if filename == "paper_execution_log.csv":
        row["trade_id"] = "trade:other"
    _append_csv(account_root / filename, row)

    result = _validate(evidence, workspace, account_root, calendar)

    assert blocker in result.blockers


def test_expected_trade_id_anywhere_in_ledger_fails(tmp_path: Path) -> None:
    evidence, workspace, account_root, calendar = _build_evidence(tmp_path)
    _append_csv(
        account_root / "paper_execution_log.csv",
        {"date": "2026-07-20", "trade_id": EXPECTED_ID},
    )

    result = _validate(evidence, workspace, account_root, calendar)

    assert f"expected_trade_ids_present:{EXPECTED_ID}" in result.blockers


def test_gap_date_current_state_fails(tmp_path: Path) -> None:
    evidence, workspace, account_root, calendar = _build_evidence(tmp_path)
    (account_root / "paper_current_state_20260702.json").write_text("{}", encoding="utf-8")

    result = _validate(evidence, workspace, account_root, calendar)

    assert "gap_current_state_files_present:1" in result.blockers


def test_unrelated_later_domain_writes_do_not_invalidate(tmp_path: Path) -> None:
    evidence, workspace, account_root, calendar = _build_evidence(tmp_path)
    _append_csv(
        account_root / "paper_execution_log.csv",
        {"date": "2026-07-20", "trade_id": "trade:later"},
    )
    _append_csv(account_root / "paper_account_snapshot.csv", {"snapshot_date": "2026-07-20"})
    _append_csv(account_root / "paper_position_snapshot.csv", {"snapshot_date": "2026-07-20"})
    (account_root / "paper_current_state_20260720.json").write_text("{}", encoding="utf-8")

    result = _validate(evidence, workspace, account_root, calendar)

    assert result.valid is True


def _collision_payload(account_id: str, gap_id: str, dates: list[str]) -> dict[str, Any]:
    return {"account_id": account_id, "gap_id": gap_id, "gap": {"trading_dates": dates}}


@pytest.mark.parametrize(
    ("candidate_dates", "existing_dates", "relationship"),
    [
        (["2026-07-02", "2026-07-06"], ["2026-07-02", "2026-07-06"], "IDENTICAL"),
        (["2026-07-06"], ["2026-07-02", "2026-07-06"], "NESTED"),
        (["2026-07-02", "2026-07-06"], ["2026-07-06"], "CONTAINING"),
        (["2026-07-02", "2026-07-06"], ["2026-07-06", "2026-07-07"], "PARTIAL_OVERLAP"),
    ],
)
def test_all_overlap_shapes_conflict(
    candidate_dates: list[str], existing_dates: list[str], relationship: str
) -> None:
    result = assess_gap_collisions(
        _collision_payload(ACCOUNT_ID, "candidate", candidate_dates),
        [_collision_payload(ACCOUNT_ID, "existing", existing_dates)],
    )
    assert result.state == CollisionState.CONFLICT
    assert result.relationships == (relationship,)


def test_non_overlap_and_other_account_pass_while_multiple_conflicts_are_ambiguous() -> None:
    candidate = _collision_payload(ACCOUNT_ID, "candidate", ["2026-07-06"])
    clean = assess_gap_collisions(
        candidate,
        [
            _collision_payload(ACCOUNT_ID, "past", ["2026-07-02"]),
            _collision_payload("paper_other", "other", ["2026-07-06"]),
        ],
    )
    ambiguous = assess_gap_collisions(
        candidate,
        [
            _collision_payload(ACCOUNT_ID, "one", ["2026-07-06"]),
            _collision_payload(ACCOUNT_ID, "two", ["2026-07-02", "2026-07-06"]),
        ],
    )
    assert clean.state == CollisionState.NONE
    assert ambiguous.state == CollisionState.AMBIGUOUS


def test_consumption_is_purely_derived_from_exact_target(tmp_path: Path) -> None:
    evidence, workspace, _, _ = _build_evidence(tmp_path)

    before = derive_consumption_state(evidence, workspace=workspace)
    state = runbook_state.create_initial_state(
        ACCOUNT_ID, GAP_END, RESUME_TRADE_DATE
    )
    target_path = runbook_state.get_state_path_for_runbook_day_id(
        workspace, state.runbook_day_id
    )
    runbook_state.save_state(state, target_path)
    after = derive_consumption_state(evidence, workspace=workspace)

    assert before.state == ConsumptionState.UNCONSUMED
    assert after.state == ConsumptionState.CONSUMED
    assert "consumed" not in evidence


def test_partial_target_artifacts_and_context_mismatch_are_invalid(tmp_path: Path) -> None:
    evidence, workspace, _, _ = _build_evidence(tmp_path)
    target_id = evidence["resume"]["runbook_day_id"]
    (workspace / "artifacts" / target_id).mkdir(parents=True)
    partial = derive_consumption_state(evidence, workspace=workspace)
    assert partial.state == ConsumptionState.INVALID
    assert "target_artifact_exists_without_state" in partial.blockers

    mismatched = runbook_state.create_initial_state(
        ACCOUNT_ID, "2026-07-07", "2026-07-08"
    )
    runbook_state.save_state(mismatched, partial.target_state_path)
    mismatch = derive_consumption_state(evidence, workspace=workspace)
    assert mismatch.state == ConsumptionState.INVALID
    assert "target_state_context_mismatch" in mismatch.blockers


def test_multiple_evidence_binding_same_target_is_invalid(tmp_path: Path) -> None:
    evidence, workspace, _, _ = _build_evidence(tmp_path)
    other = json.loads(json.dumps(evidence))
    other["gap_id"] = "sha256:" + "0" * 64

    result = derive_consumption_state(
        evidence,
        workspace=workspace,
        all_evidence=[evidence, other],
    )

    assert result.state == ConsumptionState.INVALID
    assert "multiple_evidence_bind_same_target" in result.blockers

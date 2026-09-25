from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import core.paper_manual_execution_commit as commit_module
from core import (
    operational_gap_recovery,
    operational_no_trade_gap,
    runbook_day_rollover,
    runbook_recovery,
)
from core.notion_account_keys import build_manual_execution_canonical_key
from core.operational_gap_recovery import (
    ProgressedActiveNoTradePolicy,
    assess_progressed_active_recovery,
    authorize_progressed_active_recovery,
    generic_evidence_dir,
    generic_evidence_path,
    preview_binding_sha256,
    resolve_operational_gap_authorizations,
    write_generic_authorization,
)
from core.operational_no_trade_gap import render_evidence, seal_evidence
from core.paper_account_paths import build_paper_account_paths as real_account_paths
from core.paper_manual_execution_commit import (
    ManualExecutionCommitError,
    commit_manual_execution_preview,
)
from core.runbook_calendar import load_market_calendar
from scripts import runbook_state
from tests.test_failed_no_trade_closure import (
    ACCOUNT_ID as CLOSED_ACCOUNT_ID,
    DATA_DATE as CLOSED_DATA_DATE,
    RUNBOOK_DAY_ID as CLOSED_RUNBOOK_DAY_ID,
    TRADE_DATE as CLOSED_TRADE_DATE,
    _close,
    _seed_failed_attempt,
)
from tests.test_runbook_day_rollover import _complete_state
from tests.test_runbook_recovery import (
    ACCOUNT_ID,
    AUDIT_RESTART_DATA_DATE,
    AUDIT_RESTART_TRADE_DATE,
    MISSED_SOURCE_DATA_DATE,
    MISSED_SOURCE_ID,
    MISSED_SOURCE_TRADE_DATE,
    RESTART_DATA_DATE,
    RESTART_TRADE_DATE,
    SOURCE_DATA_DATE,
    SOURCE_ID,
    SOURCE_TRADE_DATE,
    _arguments,
    _mark_active_incident,
    _seed_incident,
)
from tests.paper_account_test_support import ensure_initialized_account_paths
from tests.test_paper_manual_execution_commit import (
    _candidate,
    _execution_row,
    _fake_valuation,
    _preview_payload,
)


@pytest.fixture(autouse=True)
def _isolated_account_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> dict[str, str]:
    mode = {"value": "PAPER", "base": str(tmp_path)}

    def fake_paths(account_id: str, create: bool = False) -> object:
        return real_account_paths(
            account_id,
            account_root=(
                Path(mode["base"])
                / "outputs"
                / "paper_accounts"
                / account_id
            ),
            create=create,
        )

    resolver = lambda _account_id: mode["value"]
    monkeypatch.setattr(runbook_day_rollover, "build_paper_account_paths", fake_paths)
    monkeypatch.setattr(runbook_recovery, "build_paper_account_paths", fake_paths)
    monkeypatch.setattr(
        operational_gap_recovery, "build_paper_account_paths", fake_paths
    )
    monkeypatch.setattr(
        runbook_recovery, "resolve_authoritative_account_mode", resolver
    )
    return mode


def _account_root(tmp_path: Path, account_id: str = ACCOUNT_ID) -> Path:
    return tmp_path / "outputs" / "paper_accounts" / account_id


def _adapter_arguments(
    tmp_path: Path,
    workspace: Path,
    mode: dict[str, str],
    **overrides: object,
) -> dict[str, object]:
    values = _arguments(
        workspace,
        account_root=_account_root(tmp_path),
        account_mode_resolver=lambda _account_id: mode["value"],
    )
    values.update(overrides)
    return values


def _preview(
    tmp_path: Path,
    workspace: Path,
    mode: dict[str, str],
) -> dict[str, object]:
    result = operational_gap_recovery.preview_progressed_active_recovery(
        **_adapter_arguments(tmp_path, workspace, mode)
    )
    assert result["runner_result"] == "PASS", result
    return result


def _save_target(workspace: Path, evidence: dict[str, object]) -> None:
    resume = evidence["resume"]
    assert isinstance(resume, dict)
    state = runbook_state.create_initial_state(
        str(evidence["account_id"]),
        str(resume["data_date"]),
        str(resume["trade_date"]),
    )
    path = runbook_state.get_state_path_for_runbook_day_id(
        workspace, str(resume["runbook_day_id"])
    )
    runbook_state.save_state(state, path)


def test_progressed_active_adapter_and_authoritative_paper_test_modes_pass(
    tmp_path: Path, _isolated_account_context: dict[str, str]
) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    for account_mode in ("PAPER", "TEST"):
        _isolated_account_context["value"] = account_mode
        assessment = assess_progressed_active_recovery(
            **_adapter_arguments(
                tmp_path, workspace, _isolated_account_context
            )
        )
        assert assessment.eligible is True
        assert assessment.parity == "IDENTICAL"
        assert assessment.blockers == ()
        assert assessment.evidence is not None
        assert assessment.evidence["account_mode"] == account_mode
        assert assessment.evidence["source_policy"] == {
            "type": "PROGRESSED_ACTIVE_NO_TRADE",
            "version": 1,
        }
        assert assessment.evidence["gap"]["start_date"] == SOURCE_TRADE_DATE


def test_adapter_rejects_retireable_and_multiple_active_sources_with_parity(
    tmp_path: Path, _isolated_account_context: dict[str, str]
) -> None:
    calendar = load_market_calendar()

    retire_workspace = tmp_path / "retire_workspace"
    retire_workspace.mkdir()
    _complete_state(retire_workspace, "2026-08-12", "2026-08-13")
    source = runbook_state.create_initial_state(
        ACCOUNT_ID, SOURCE_DATA_DATE, SOURCE_TRADE_DATE
    )
    runbook_state.save_state(
        source,
        runbook_state.get_state_path_for_runbook_day_id(
            retire_workspace, SOURCE_ID
        ),
    )
    retireable = assess_progressed_active_recovery(
        **_adapter_arguments(
            tmp_path,
            retire_workspace,
            _isolated_account_context,
            calendar=calendar,
        )
    )
    assert retireable.eligible is False
    assert retireable.parity == "IDENTICAL"
    assert "source_is_zero_progress_retirement_candidate" in retireable.blockers

    multiple_root = tmp_path / "multiple"
    multiple_root.mkdir()
    _isolated_account_context["base"] = str(multiple_root)
    multiple_workspace, _, _ = _seed_incident(multiple_root)
    other = runbook_state.create_initial_state(
        ACCOUNT_ID, "2026-08-18", "2026-08-19"
    )
    runbook_state.save_state(
        other,
        runbook_state.get_state_path_for_context(
            multiple_workspace, ACCOUNT_ID, "2026-08-18", "2026-08-19"
        ),
    )
    multiple = assess_progressed_active_recovery(
        **_adapter_arguments(
            multiple_root,
            multiple_workspace,
            _isolated_account_context,
            calendar=calendar,
        )
    )
    assert multiple.eligible is False
    assert multiple.parity == "IDENTICAL"
    assert "active_runbook_day_count_must_equal_one" in multiple.blockers


def test_adapter_rejects_closed_tampered_live_and_calendar_invalid_sources(
    tmp_path: Path, _isolated_account_context: dict[str, str]
) -> None:
    calendar = load_market_calendar()
    closed_root = tmp_path / "closed"
    closed_root.mkdir()
    _isolated_account_context["base"] = str(closed_root)
    closed_fixture = _seed_failed_attempt(closed_root)
    assert _close(closed_fixture)["runner_result"] == "PASS"
    closed_workspace = closed_fixture["workspace"]
    closed_path = closed_fixture["state_path"]
    assert isinstance(closed_workspace, Path)
    assert isinstance(closed_path, Path)
    policy = ProgressedActiveNoTradePolicy(
        closed_workspace,
        calendar,
        account_mode_resolver=lambda _account_id: "PAPER",
    )
    closed = policy.assess_eligibility(
        {
            "account_id": CLOSED_ACCOUNT_ID,
            "identity": CLOSED_RUNBOOK_DAY_ID,
            "lifecycle": "ACTIVE_INCOMPLETE",
            "state_ref": closed_path.relative_to(closed_workspace).as_posix(),
            "first_legal_gap_date": CLOSED_TRADE_DATE,
        }
    )
    assert closed.eligible is False
    assert "source_not_active_incomplete" in closed.blockers
    closed_parity = assess_progressed_active_recovery(
        workspace=closed_workspace,
        account_id=CLOSED_ACCOUNT_ID,
        source_runbook_day_id=CLOSED_RUNBOOK_DAY_ID,
        restart_data_date="2026-08-12",
        restart_trade_date="2026-08-13",
        reason="closed source must remain terminal",
        calendar=calendar,
        confirm_paper_test=True,
        confirm_contaminated_incomplete=True,
        confirm_no_real_trades=True,
        confirm_gap_without_backfill=True,
        account_root=closed_fixture["account_root"],
        account_mode_resolver=lambda _account_id: "PAPER",
    )
    assert closed_parity.eligible is False
    assert closed_parity.parity == "IDENTICAL"
    assert "failed_no_trade_closure_terminal" in closed_parity.blockers

    matrix_root = tmp_path / "matrix"
    matrix_root.mkdir()
    _isolated_account_context["base"] = str(matrix_root)
    workspace, state_path, _ = _seed_incident(matrix_root)
    state_path.write_text("{invalid", encoding="utf-8")
    tampered = assess_progressed_active_recovery(
        **_adapter_arguments(matrix_root, workspace, _isolated_account_context)
    )
    assert tampered.eligible is False and tampered.parity == "IDENTICAL"
    assert "invalid_state_file" in ",".join(tampered.blockers)

    live_root = tmp_path / "live"
    live_root.mkdir()
    _isolated_account_context["base"] = str(live_root)
    live_workspace, _, _ = _seed_incident(live_root)
    _isolated_account_context["value"] = "LIVE"
    live = assess_progressed_active_recovery(
        **_adapter_arguments(
            live_root, live_workspace, _isolated_account_context
        )
    )
    assert live.eligible is False and live.parity == "IDENTICAL"
    assert "paper_account_required" in live.blockers

    _isolated_account_context["value"] = "PAPER"
    calendar_root = tmp_path / "calendar"
    calendar_root.mkdir()
    _isolated_account_context["base"] = str(calendar_root)
    invalid_calendar_workspace, _, _ = _seed_incident(calendar_root)
    invalid_calendar = assess_progressed_active_recovery(
        **_adapter_arguments(
            calendar_root,
            invalid_calendar_workspace,
            _isolated_account_context,
            restart_data_date="2026-08-22",
            restart_trade_date="2026-08-23",
        )
    )
    assert invalid_calendar.eligible is False
    assert invalid_calendar.parity == "IDENTICAL"
    assert any("trading_day" in item for item in invalid_calendar.blockers)


def test_strict_domain_contradiction_is_intentional_generic_hardening(
    tmp_path: Path, _isolated_account_context: dict[str, str]
) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    snapshot = _account_root(tmp_path) / "paper_account_snapshot.csv"
    with snapshot.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["account_id", "snapshot_date", "total_equity_market_value"],
        )
        writer.writerow(
            {
                "account_id": ACCOUNT_ID,
                "snapshot_date": SOURCE_TRADE_DATE,
                "total_equity_market_value": "100000",
            }
        )

    assessment = assess_progressed_active_recovery(
        **_adapter_arguments(tmp_path, workspace, _isolated_account_context)
    )
    assert assessment.eligible is False
    assert assessment.parity == "INTENTIONAL_GENERIC_HARDENING"
    assert "gap_account_snapshot_rows_present:1" in assessment.blockers


def test_generic_writer_create_idempotency_conflict_and_preview_binding(
    tmp_path: Path, _isolated_account_context: dict[str, str]
) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    preview = _preview(tmp_path, workspace, _isolated_account_context)
    evidence = preview["evidence"]
    assert isinstance(evidence, dict)
    writer_args = {
        "workspace": workspace,
        "calendar": load_market_calendar(),
        "account_root": _account_root(tmp_path),
        "account_mode_resolver": lambda _account_id: "PAPER",
    }
    first = write_generic_authorization(
        evidence=evidence,
        expected_preview_sha256=str(preview["preview_sha256"]),
        **writer_args,
    )
    retry = write_generic_authorization(
        evidence=evidence,
        expected_preview_sha256=str(preview["preview_sha256"]),
        **writer_args,
    )
    assert first["runner_result"] == "PASS" and first["write_result"] == "CREATED"
    assert retry["runner_result"] == "PASS" and retry["write_result"] == "IDEMPOTENT"

    binding_failure = write_generic_authorization(
        evidence=evidence,
        expected_preview_sha256="0" * 64,
        **writer_args,
    )
    assert binding_failure["reason"] == "preview_evidence_binding_mismatch"

    conflict = json.loads(json.dumps(evidence))
    conflict["incident"]["reason_text"] = "conflicting retry"
    conflict = seal_evidence(conflict)
    assert conflict["gap_id"] == evidence["gap_id"]
    overwrite = write_generic_authorization(
        evidence=conflict,
        expected_preview_sha256=preview_binding_sha256(conflict),
        **writer_args,
    )
    assert overwrite["runner_result"] == "BLOCKED"
    assert overwrite["reason"] == "existing_gap_id_content_conflict"


def test_generic_writer_regenerated_preview_retry_is_idempotent_and_immutable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _isolated_account_context: dict[str, str],
) -> None:
    workspace, _, _ = _seed_incident(tmp_path)

    class _Clock:
        current = datetime(2026, 9, 23, 9, 0, tzinfo=timezone.utc)

        @classmethod
        def now(cls, tz: object | None = None) -> datetime:
            assert tz is not None
            return cls.current.astimezone(tz)

    monkeypatch.setattr(operational_gap_recovery, "datetime", _Clock)
    preview_a = _preview(tmp_path, workspace, _isolated_account_context)
    evidence_a = preview_a["evidence"]
    assert isinstance(evidence_a, dict)
    writer_args = {
        "workspace": workspace,
        "calendar": load_market_calendar(),
        "account_root": _account_root(tmp_path),
        "account_mode_resolver": lambda _account_id: "PAPER",
    }
    created = write_generic_authorization(
        evidence=evidence_a,
        expected_preview_sha256=str(preview_a["preview_sha256"]),
        **writer_args,
    )
    assert created["runner_result"] == "PASS"
    assert created["write_result"] == "CREATED"
    path = Path(created["evidence_path"])
    stored_before = path.read_bytes()

    _Clock.current = datetime(2026, 9, 23, 9, 1, tzinfo=timezone.utc)
    preview_b = _preview(tmp_path, workspace, _isolated_account_context)
    evidence_b = preview_b["evidence"]
    assert isinstance(evidence_b, dict)
    assert evidence_a["created_at"] != evidence_b["created_at"]
    assert evidence_a["content_sha256"] != evidence_b["content_sha256"]
    assert evidence_a["gap_id"] == evidence_b["gap_id"]
    assert preview_binding_sha256(evidence_a) == preview_binding_sha256(evidence_b)

    retried = write_generic_authorization(
        evidence=evidence_b,
        expected_preview_sha256=str(preview_b["preview_sha256"]),
        **writer_args,
    )
    assert retried["runner_result"] == "PASS"
    assert retried["write_result"] == "IDEMPOTENT"
    assert path.read_bytes() == stored_before


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("content_sha256", "0" * 64),
        ("created_at", "2026-09-23T09:01:00+00:00"),
    ],
)
def test_generic_writer_rejects_tampered_existing_evidence_without_rewrite(
    tmp_path: Path,
    _isolated_account_context: dict[str, str],
    field: str,
    value: str,
) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    preview = _preview(tmp_path, workspace, _isolated_account_context)
    evidence = preview["evidence"]
    assert isinstance(evidence, dict)
    writer_args = {
        "workspace": workspace,
        "calendar": load_market_calendar(),
        "account_root": _account_root(tmp_path),
        "account_mode_resolver": lambda _account_id: "PAPER",
    }
    created = write_generic_authorization(
        evidence=evidence,
        expected_preview_sha256=str(preview["preview_sha256"]),
        **writer_args,
    )
    assert created["write_result"] == "CREATED"
    path = Path(created["evidence_path"])
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[field] = value
    path.write_text(json.dumps(payload), encoding="utf-8")
    tampered_bytes = path.read_bytes()

    retried = write_generic_authorization(
        evidence=evidence,
        expected_preview_sha256=str(preview["preview_sha256"]),
        **writer_args,
    )
    assert retried["runner_result"] == "BLOCKED"
    assert retried["reason"] == "existing_generic_evidence_invalid"
    assert "existing_generic_evidence_invalid" in retried["blockers"]
    assert "content_sha256_mismatch" in retried["blockers"]
    assert path.read_bytes() == tampered_bytes


def test_generic_writer_keeps_malformed_existing_evidence_unchanged(
    tmp_path: Path, _isolated_account_context: dict[str, str]
) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    preview = _preview(tmp_path, workspace, _isolated_account_context)
    evidence = preview["evidence"]
    assert isinstance(evidence, dict)
    writer_args = {
        "workspace": workspace,
        "calendar": load_market_calendar(),
        "account_root": _account_root(tmp_path),
        "account_mode_resolver": lambda _account_id: "PAPER",
    }
    created = write_generic_authorization(
        evidence=evidence,
        expected_preview_sha256=str(preview["preview_sha256"]),
        **writer_args,
    )
    path = Path(created["evidence_path"])
    path.write_text("{invalid", encoding="utf-8")
    malformed_bytes = path.read_bytes()

    retried = write_generic_authorization(
        evidence=evidence,
        expected_preview_sha256=str(preview["preview_sha256"]),
        **writer_args,
    )
    assert retried["runner_result"] == "BLOCKED"
    assert retried["reason"] == "existing_generic_evidence_invalid"
    assert path.read_bytes() == malformed_bytes


def test_activation_gate_writes_nothing_and_test_only_path_creates_evidence(
    tmp_path: Path, _isolated_account_context: dict[str, str]
) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    arguments = _adapter_arguments(
        tmp_path, workspace, _isolated_account_context
    )
    blocked = authorize_progressed_active_recovery(**arguments)
    assert blocked["runner_result"] == "BLOCKED"
    assert blocked["reason"] == "ntg_production_activation_disabled"
    assert not generic_evidence_dir(workspace).exists()

    created = authorize_progressed_active_recovery(
        **arguments, allow_test_write=True
    )
    assert created["runner_result"] == "PASS"
    assert created["write_result"] == "CREATED"
    assert Path(created["evidence_path"]).is_file()


def test_combined_resolver_handles_legacy_and_generic_consumption(
    tmp_path: Path, _isolated_account_context: dict[str, str]
) -> None:
    calendar = load_market_calendar()

    legacy_root = tmp_path / "legacy"
    legacy_root.mkdir()
    _isolated_account_context["base"] = str(legacy_root)
    legacy_workspace, _, _ = _seed_incident(legacy_root)
    assert runbook_recovery.authorize_recovery(
        **_arguments(legacy_workspace, calendar=calendar)
    )["runner_result"] == "PASS"
    legacy_unconsumed = resolve_operational_gap_authorizations(
        legacy_workspace,
        account_id=ACCOUNT_ID,
        calendar=calendar,
        account_root=_account_root(legacy_root),
        account_mode_resolver=lambda _account_id: "PAPER",
    )
    assert legacy_unconsumed["state"] == "UNCONSUMED"
    assert legacy_unconsumed["authorization"]["evidence_kind"] == "runbook_recovery.v1"
    legacy_payload = runbook_recovery.validate_recovery_evidence(
        legacy_workspace,
        runbook_state.get_state_path_for_runbook_day_id(
            legacy_workspace, SOURCE_ID
        ),
        runbook_state.load_state(
            runbook_state.get_state_path_for_runbook_day_id(
                legacy_workspace, SOURCE_ID
            )
        ),
        calendar,
    )["payload"]
    _save_target(
        legacy_workspace,
        {
            "account_id": ACCOUNT_ID,
            "resume": legacy_payload["restart"],
        },
    )
    legacy_consumed = resolve_operational_gap_authorizations(
        legacy_workspace,
        account_id=ACCOUNT_ID,
        calendar=calendar,
        account_root=_account_root(legacy_root),
        account_mode_resolver=lambda _account_id: "PAPER",
    )
    assert legacy_consumed["state"] == "CONSUMED"

    generic_root = tmp_path / "generic"
    generic_root.mkdir()
    _isolated_account_context["base"] = str(generic_root)
    generic_workspace, _, _ = _seed_incident(generic_root)
    preview = _preview(
        generic_root, generic_workspace, _isolated_account_context
    )
    evidence = preview["evidence"]
    assert isinstance(evidence, dict)
    created = write_generic_authorization(
        generic_workspace,
        evidence=evidence,
        expected_preview_sha256=str(preview["preview_sha256"]),
        calendar=calendar,
        account_root=_account_root(generic_root),
        account_mode_resolver=lambda _account_id: "PAPER",
    )
    assert created["runner_result"] == "PASS"
    generic_unconsumed = resolve_operational_gap_authorizations(
        generic_workspace,
        account_id=ACCOUNT_ID,
        calendar=calendar,
        account_root=_account_root(generic_root),
        account_mode_resolver=lambda _account_id: "PAPER",
    )
    assert generic_unconsumed["state"] == "UNCONSUMED"
    assert generic_unconsumed["authorization"]["evidence_kind"] == "operational_no_trade_gap.v1"
    _save_target(generic_workspace, evidence)
    generic_consumed = resolve_operational_gap_authorizations(
        generic_workspace,
        account_id=ACCOUNT_ID,
        calendar=calendar,
        account_root=_account_root(generic_root),
        account_mode_resolver=lambda _account_id: "PAPER",
    )
    assert generic_consumed["state"] == "CONSUMED"


def test_combined_resolver_blocks_cross_kind_multiple_and_invalid_evidence(
    tmp_path: Path, _isolated_account_context: dict[str, str]
) -> None:
    calendar = load_market_calendar()
    workspace, _, _ = _seed_incident(tmp_path)
    preview = _preview(tmp_path, workspace, _isolated_account_context)
    evidence = preview["evidence"]
    assert isinstance(evidence, dict)

    assert runbook_recovery.authorize_recovery(
        **_arguments(workspace, calendar=calendar)
    )["runner_result"] == "PASS"
    path = generic_evidence_path(workspace, str(evidence["gap_id"]))
    path.parent.mkdir(parents=True)
    path.write_text(render_evidence(evidence), encoding="utf-8")
    conflict = resolve_operational_gap_authorizations(
        workspace,
        account_id=ACCOUNT_ID,
        calendar=calendar,
        account_root=_account_root(tmp_path),
        account_mode_resolver=lambda _account_id: "PAPER",
    )
    assert conflict["state"] == "BLOCKED"
    assert "legacy_generic_authorization_conflict" in conflict["blockers"]

    runbook_recovery.recovery_path(workspace, SOURCE_ID).unlink()
    duplicate = path.parent / "duplicate.json"
    duplicate.write_text(render_evidence(evidence), encoding="utf-8")
    multiple = resolve_operational_gap_authorizations(
        workspace,
        account_id=ACCOUNT_ID,
        calendar=calendar,
        account_root=_account_root(tmp_path),
        account_mode_resolver=lambda _account_id: "PAPER",
    )
    assert multiple["state"] == "BLOCKED"
    assert "multiple_evidence_bind_same_target" in multiple["blockers"]

    duplicate.write_text("{invalid", encoding="utf-8")
    invalid = resolve_operational_gap_authorizations(
        workspace,
        account_id=ACCOUNT_ID,
        calendar=calendar,
        account_root=_account_root(tmp_path),
        account_mode_resolver=lambda _account_id: "PAPER",
    )
    assert invalid["state"] == "BLOCKED"
    assert any(
        item.startswith("generic_evidence_invalid:duplicate.json")
        for item in invalid["blockers"]
    )


def test_combined_resolver_blocks_multiple_valid_unconsumed_authorizations(
    tmp_path: Path, _isolated_account_context: dict[str, str]
) -> None:
    calendar = load_market_calendar()
    workspace, _, _ = _seed_incident(tmp_path)
    assert runbook_recovery.authorize_recovery(
        **_arguments(workspace, calendar=calendar)
    )["runner_result"] == "PASS"

    second = runbook_state.create_initial_state(
        ACCOUNT_ID, MISSED_SOURCE_DATA_DATE, MISSED_SOURCE_TRADE_DATE
    )
    second_path = runbook_state.get_state_path_for_context(
        workspace,
        ACCOUNT_ID,
        MISSED_SOURCE_DATA_DATE,
        MISSED_SOURCE_TRADE_DATE,
    )
    _mark_active_incident(workspace, second_path, second)
    assert runbook_recovery.authorize_recovery(
        **_arguments(
            workspace,
            source_runbook_day_id=MISSED_SOURCE_ID,
            restart_data_date=AUDIT_RESTART_DATA_DATE,
            restart_trade_date=AUDIT_RESTART_TRADE_DATE,
            calendar=calendar,
        )
    )["runner_result"] == "PASS"

    result = resolve_operational_gap_authorizations(
        workspace,
        account_id=ACCOUNT_ID,
        calendar=calendar,
        account_root=_account_root(tmp_path),
        account_mode_resolver=lambda _account_id: "PAPER",
    )
    assert result["state"] == "BLOCKED"
    assert result["blockers"] == ["multiple_unconsumed_authorizations"]


def test_generic_authorization_drives_exact_rollover_initialization_and_consumption(
    tmp_path: Path, _isolated_account_context: dict[str, str]
) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    calendar = load_market_calendar()
    preview = _preview(tmp_path, workspace, _isolated_account_context)
    evidence = preview["evidence"]
    assert isinstance(evidence, dict)
    created = write_generic_authorization(
        workspace,
        evidence=evidence,
        expected_preview_sha256=str(preview["preview_sha256"]),
        calendar=calendar,
        account_root=_account_root(tmp_path),
        account_mode_resolver=lambda _account_id: "PAPER",
    )
    assert created["runner_result"] == "PASS"

    rollover = runbook_day_rollover.preview_rollover(
        workspace, ACCOUNT_ID, calendar, confirm_paper_test=True
    )
    assert rollover["runner_result"] == "PASS"
    assert rollover["rollover_mode"] == "RECOVERY"
    assert rollover["operational_gap_evidence_kind"] == "operational_no_trade_gap.v1"
    assert {
        "data_date": rollover["next_data_date"],
        "trade_date": rollover["next_trade_date"],
        "runbook_day_id": rollover["next_runbook_day_id"],
    } == evidence["resume"]

    with pytest.raises(ValueError, match="recovery_target_mismatch"):
        runbook_state.init_state_file_for_context(
            workspace, ACCOUNT_ID, "2026-08-20", "2026-08-21"
        )
    wrong_id_guard = operational_gap_recovery.guard_operational_gap_boundary(
        workspace,
        account_id=ACCOUNT_ID,
        data_date=str(evidence["resume"]["data_date"]),
        trade_date=str(evidence["resume"]["trade_date"]),
        runbook_day_id="wrong_target_id",
        calendar=calendar,
        account_root=_account_root(tmp_path),
        account_mode_resolver=lambda _account_id: "PAPER",
        boundary="INITIALIZATION",
    )
    assert wrong_id_guard["decision"] == operational_gap_recovery.GUARD_BLOCKED
    assert wrong_id_guard["reason"] == "operational_gap_target_mismatch"

    uninitialized_lifecycle = operational_gap_recovery.guard_operational_gap_boundary(
        workspace,
        account_id=ACCOUNT_ID,
        data_date=str(evidence["resume"]["data_date"]),
        trade_date=str(evidence["resume"]["trade_date"]),
        calendar=calendar,
        account_root=_account_root(tmp_path),
        account_mode_resolver=lambda _account_id: "PAPER",
        boundary="LIFECYCLE_ENTRY",
    )
    assert uninitialized_lifecycle["decision"] == operational_gap_recovery.GUARD_BLOCKED
    assert uninitialized_lifecycle["reason"] == "operational_gap_target_not_initialized"

    result, target_path, target = runbook_state.init_state_file_for_context(
        workspace,
        ACCOUNT_ID,
        str(evidence["resume"]["data_date"]),
        str(evidence["resume"]["trade_date"]),
    )
    assert result == "CREATED"
    assert target.runbook_day_id == evidence["resume"]["runbook_day_id"]
    assert target_path.is_file()
    consumed = resolve_operational_gap_authorizations(
        workspace,
        account_id=ACCOUNT_ID,
        calendar=calendar,
        account_root=_account_root(tmp_path),
        account_mode_resolver=lambda _account_id: "PAPER",
    )
    assert consumed["state"] == "CONSUMED"
    initialized_lifecycle = operational_gap_recovery.guard_operational_gap_boundary(
        workspace,
        account_id=ACCOUNT_ID,
        data_date=str(evidence["resume"]["data_date"]),
        trade_date=str(evidence["resume"]["trade_date"]),
        calendar=calendar,
        account_root=_account_root(tmp_path),
        account_mode_resolver=lambda _account_id: "PAPER",
        boundary="LIFECYCLE_ENTRY",
    )
    assert initialized_lifecycle["decision"] == operational_gap_recovery.GUARD_ALLOW
    existing, _, _ = runbook_state.init_state_file_for_context(
        workspace,
        ACCOUNT_ID,
        str(evidence["resume"]["data_date"]),
        str(evidence["resume"]["trade_date"]),
    )
    assert existing == "EXISTING"
    with pytest.raises(ValueError, match="active_runbook_day_exists"):
        runbook_state.init_state_file_for_context(
            workspace, ACCOUNT_ID, "2026-08-24", "2026-08-25"
        )


@pytest.mark.parametrize(
    ("consumed", "boundary", "expected_decision"),
    [
        (False, "ROLLOVER", operational_gap_recovery.GUARD_ALLOW),
        (False, "INITIALIZATION", operational_gap_recovery.GUARD_ALLOW),
        (False, "LIFECYCLE_ENTRY", operational_gap_recovery.GUARD_BLOCKED),
        (False, "EXECUTION_COMMIT", operational_gap_recovery.GUARD_BLOCKED),
        (True, "INITIALIZATION", operational_gap_recovery.GUARD_ALLOW),
        (True, "LIFECYCLE_ENTRY", operational_gap_recovery.GUARD_ALLOW),
        (True, "EXECUTION_COMMIT", operational_gap_recovery.GUARD_ALLOW),
    ],
)
def test_operational_gap_guard_enforces_consumption_state_by_boundary(
    tmp_path: Path,
    _isolated_account_context: dict[str, str],
    consumed: bool,
    boundary: str,
    expected_decision: str,
) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    calendar = load_market_calendar()
    preview = _preview(tmp_path, workspace, _isolated_account_context)
    evidence = preview["evidence"]
    assert isinstance(evidence, dict)
    assert write_generic_authorization(
        workspace,
        evidence=evidence,
        expected_preview_sha256=str(preview["preview_sha256"]),
        calendar=calendar,
        account_root=_account_root(tmp_path),
        account_mode_resolver=lambda _account_id: "PAPER",
    )["runner_result"] == "PASS"
    if consumed:
        _save_target(workspace, evidence)

    resume = evidence["resume"]
    assert isinstance(resume, dict)
    result = operational_gap_recovery.guard_operational_gap_boundary(
        workspace,
        account_id=ACCOUNT_ID,
        data_date=str(resume["data_date"]),
        trade_date=str(resume["trade_date"]),
        calendar=calendar,
        account_root=_account_root(tmp_path),
        account_mode_resolver=lambda _account_id: "PAPER",
        boundary=boundary,
    )

    assert result["resolver_state"] == ("CONSUMED" if consumed else "UNCONSUMED")
    assert result["decision"] == expected_decision
    if expected_decision == operational_gap_recovery.GUARD_BLOCKED:
        assert result["reason"] == "operational_gap_target_not_initialized"


def test_execution_commit_requires_consumed_exact_target_before_domain_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _isolated_account_context: dict[str, str],
) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    account_paths = ensure_initialized_account_paths(
        _account_root(tmp_path),
        account_id=ACCOUNT_ID,
        date_str=SOURCE_DATA_DATE,
    )
    calendar = load_market_calendar()
    authorization_preview = _preview(tmp_path, workspace, _isolated_account_context)
    evidence = authorization_preview["evidence"]
    assert isinstance(evidence, dict)
    assert write_generic_authorization(
        workspace,
        evidence=evidence,
        expected_preview_sha256=str(authorization_preview["preview_sha256"]),
        calendar=calendar,
        account_root=account_paths.root,
        account_mode_resolver=lambda _account_id: "PAPER",
    )["runner_result"] == "PASS"
    historical_row = _execution_row(
        date=SOURCE_DATA_DATE,
        symbol="AAPL",
        side="BUY",
        shares=1,
        price=10.0,
    )
    historical_row["status"] = "COMMITTED"
    with account_paths.execution_log_path.open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(historical_row))
        writer.writeheader()
        writer.writerow(historical_row)
    assert resolve_operational_gap_authorizations(
        workspace,
        account_id=ACCOUNT_ID,
        calendar=calendar,
        account_root=account_paths.root,
        account_mode_resolver=lambda _account_id: "PAPER",
    )["state"] == "UNCONSUMED"

    candidate = _candidate(
        symbol="AAPL",
        side="BUY",
        quantity=1,
        actual_price=100.0,
    )
    candidate.update(
        execution_date=RESTART_TRADE_DATE,
        plan_date=RESTART_TRADE_DATE,
        canonical_key=build_manual_execution_canonical_key(
            ACCOUNT_ID,
            RESTART_TRADE_DATE,
            "AAPL",
            "BUY",
            1,
        ),
    )
    payload = _preview_payload(
        date=RESTART_TRADE_DATE,
        commit_allowed="true",
        fail_count=0,
        warning_count=0,
        candidates=[candidate],
    )
    payload["account_id"] = ACCOUNT_ID
    preview_path = account_paths.reports_dir / "manual_execution_preview.json"
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    preview_path.write_text(json.dumps(payload), encoding="utf-8")
    domain_paths = (
        account_paths.execution_log_path,
        account_paths.account_snapshot_path,
        account_paths.position_snapshot_path,
        account_paths.current_state_snapshot_path(SOURCE_DATA_DATE),
    )
    before = {path: path.read_bytes() for path in domain_paths}
    writer_calls: list[str] = []

    def unexpected_write(*args: object, **kwargs: object) -> None:
        writer_calls.append("called")
        raise AssertionError("pre-initialization commit reached a domain writer")

    monkeypatch.setattr(
        operational_no_trade_gap,
        "resolve_paper_account_profile",
        lambda _account_id: SimpleNamespace(account_type="PAPER"),
    )
    with monkeypatch.context() as write_guard:
        for writer_name in (
            "append_paper_execution_log",
            "save_paper_current_state",
            "save_paper_account_snapshot",
            "save_paper_position_snapshot",
        ):
            write_guard.setattr(commit_module, writer_name, unexpected_write)
        with pytest.raises(
            ManualExecutionCommitError,
            match="operational_gap_target_not_initialized",
        ):
            commit_manual_execution_preview(
                execution_date=RESTART_TRADE_DATE,
                data_date=RESTART_DATA_DATE,
                workspace=workspace,
                preview_json_path=preview_path,
                account_paths=account_paths,
            )

    assert writer_calls == []
    assert {path: path.read_bytes() for path in domain_paths} == before

    created, _, _ = runbook_state.init_state_file_for_context(
        workspace,
        ACCOUNT_ID,
        RESTART_DATA_DATE,
        RESTART_TRADE_DATE,
    )
    assert created == "CREATED"
    assert resolve_operational_gap_authorizations(
        workspace,
        account_id=ACCOUNT_ID,
        calendar=calendar,
        account_root=account_paths.root,
        account_mode_resolver=lambda _account_id: "PAPER",
    )["state"] == "CONSUMED"

    monkeypatch.setattr(commit_module, "market_db_path", lambda: str(tmp_path / "unused.db"))
    monkeypatch.setattr(commit_module, "value_paper_account_state", _fake_valuation)
    committed = commit_manual_execution_preview(
        execution_date=RESTART_TRADE_DATE,
        data_date=RESTART_DATA_DATE,
        workspace=workspace,
        preview_json_path=preview_path,
        account_paths=account_paths,
    )
    assert committed.committed_row_count == 1
    assert committed.current_state_written is True
    assert committed.account_snapshot_written is True
    assert committed.position_snapshot_written is True


def _append_domain_row(path: Path, required_values: dict[str, str]) -> None:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        fieldnames = list(csv.DictReader(handle).fieldnames or [])
    with path.open("a", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writerow({name: required_values.get(name, "") for name in fieldnames})


@pytest.mark.parametrize(
    "contradiction",
    ["execution", "account", "position", "current_state", "evidence_tamper"],
)
def test_late_contradiction_blocks_next_protected_boundary(
    tmp_path: Path,
    _isolated_account_context: dict[str, str],
    contradiction: str,
) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    calendar = load_market_calendar()
    preview = _preview(tmp_path, workspace, _isolated_account_context)
    evidence = preview["evidence"]
    assert isinstance(evidence, dict)
    assert write_generic_authorization(
        workspace,
        evidence=evidence,
        expected_preview_sha256=str(preview["preview_sha256"]),
        calendar=calendar,
        account_root=_account_root(tmp_path),
        account_mode_resolver=lambda _account_id: "PAPER",
    )["runner_result"] == "PASS"
    resume = evidence["resume"]
    before = operational_gap_recovery.guard_operational_gap_boundary(
        workspace,
        account_id=ACCOUNT_ID,
        data_date=str(resume["data_date"]),
        trade_date=str(resume["trade_date"]),
        calendar=calendar,
        account_root=_account_root(tmp_path),
        account_mode_resolver=lambda _account_id: "PAPER",
        boundary="ROLLOVER",
    )
    assert before["decision"] == operational_gap_recovery.GUARD_ALLOW

    paths = real_account_paths(
        ACCOUNT_ID, account_root=_account_root(tmp_path), create=False
    )
    gap_date = str(evidence["gap"]["trading_dates"][0])
    if contradiction == "execution":
        _append_domain_row(
            paths.execution_log_path,
            {"date": gap_date, "trade_id": "late-gap-trade"},
        )
    elif contradiction == "account":
        _append_domain_row(paths.account_snapshot_path, {"snapshot_date": gap_date})
    elif contradiction == "position":
        _append_domain_row(paths.position_snapshot_path, {"snapshot_date": gap_date})
    elif contradiction == "current_state":
        paths.current_state_snapshot_path(gap_date).write_text("{}", encoding="utf-8")
    else:
        evidence_path = generic_evidence_path(workspace, str(evidence["gap_id"]))
        tampered = json.loads(evidence_path.read_text(encoding="utf-8"))
        tampered["created_at"] = "2099-01-01T00:00:00+00:00"
        evidence_path.write_text(json.dumps(tampered), encoding="utf-8")

    after = operational_gap_recovery.guard_operational_gap_boundary(
        workspace,
        account_id=ACCOUNT_ID,
        data_date=str(resume["data_date"]),
        trade_date=str(resume["trade_date"]),
        calendar=calendar,
        account_root=_account_root(tmp_path),
        account_mode_resolver=lambda _account_id: "PAPER",
        boundary="EXECUTION_COMMIT",
    )
    assert after["decision"] == operational_gap_recovery.GUARD_BLOCKED
    rollover = runbook_day_rollover.preview_rollover(
        workspace, ACCOUNT_ID, calendar, confirm_paper_test=True
    )
    assert rollover["runner_result"] == "BLOCKED"


def test_initialized_target_lifecycle_entry_revalidates_evidence(
    tmp_path: Path, _isolated_account_context: dict[str, str]
) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    calendar = load_market_calendar()
    preview = _preview(tmp_path, workspace, _isolated_account_context)
    evidence = preview["evidence"]
    assert isinstance(evidence, dict)
    assert write_generic_authorization(
        workspace,
        evidence=evidence,
        expected_preview_sha256=str(preview["preview_sha256"]),
        calendar=calendar,
        account_root=_account_root(tmp_path),
        account_mode_resolver=lambda _account_id: "PAPER",
    )["runner_result"] == "PASS"
    resume = evidence["resume"]
    assert runbook_state.init_state_file_for_context(
        workspace,
        ACCOUNT_ID,
        str(resume["data_date"]),
        str(resume["trade_date"]),
    )[0] == "CREATED"

    evidence_path = generic_evidence_path(workspace, str(evidence["gap_id"]))
    tampered = json.loads(evidence_path.read_text(encoding="utf-8"))
    tampered["created_at"] = "2099-01-01T00:00:00+00:00"
    evidence_path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="operational_gap_lifecycle_blocked"):
        runbook_state.init_state_file_for_context(
            workspace,
            ACCOUNT_ID,
            str(resume["data_date"]),
            str(resume["trade_date"]),
        )

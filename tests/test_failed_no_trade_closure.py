from __future__ import annotations

import csv
import json
from dataclasses import replace
from pathlib import Path

import pytest

from core import failed_no_trade_closure, runbook_day_rollover, runbook_recovery, runbook_retirement
from scripts import runbook_stage_b_recovery, runbook_stage_runner, runbook_state


ACCOUNT_ID = "paper_closure_test"
DATA_DATE = "2026-08-10"
TRADE_DATE = "2026-08-11"
RUNBOOK_DAY_ID = f"{ACCOUNT_ID}_{DATA_DATE}_{TRADE_DATE}"
OPERATOR = "test-operator"
REASON = "operator confirmed that the failed attempt produced no actual trade"


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows or [])


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _seed_failed_attempt(tmp_path: Path) -> dict[str, object]:
    workspace = tmp_path / "workspace"
    account_root = tmp_path / "outputs" / "paper_accounts" / ACCOUNT_ID
    workspace.mkdir()
    account_root.mkdir(parents=True)
    execution_path = account_root / "paper_execution_log.csv"
    account_path = account_root / "paper_account_snapshot.csv"
    position_path = account_root / "paper_position_snapshot.csv"
    _write_csv(execution_path, ["trade_id", "date"])
    _write_csv(account_path, ["account_id", "snapshot_date"])
    _write_csv(position_path, ["account_id", "snapshot_date", "symbol"])

    candidate = {
        "account_id": ACCOUNT_ID,
        "execution_date": TRADE_DATE,
        "symbol": "AMD",
        "side": "BUY",
        "quantity": 2,
        "actual_price": 100.0,
        "note": "fixture",
    }
    plan_path = _write_json(
        workspace / "artifacts" / RUNBOOK_DAY_ID / "stage_a" / "daily_plan.json",
        {
            "schema_version": "paper_daily_plan.v1",
            "account_id": ACCOUNT_ID,
            "data_date": DATA_DATE,
            "trade_date": TRADE_DATE,
            "items": [{"symbol": "AMD", "action": "BUY", "quantity": 2, "price": 100.0}],
        },
    )
    preview_path = _write_json(
        workspace / "artifacts" / RUNBOOK_DAY_ID / "stage_b" / "preview.json",
        {
            "account_id": ACCOUNT_ID,
            "execution_date": TRADE_DATE,
            "candidate_count": 1,
            "candidates": [candidate],
        },
    )
    reconciliation_path = _write_json(
        workspace / "reconciliation_runs" / RUNBOOK_DAY_ID / "preview.json",
        {
            "schema_version": "execution_reconciliation_preview.v1",
            "runner_result": "PASS",
            "account_id": ACCOUNT_ID,
            "data_date": DATA_DATE,
            "trade_date": TRADE_DATE,
            "notion_row_count": 1,
            "actual_count": 1,
            "planned_count": 1,
            "matched_count": 1,
            "deviated_count": 0,
            "missing_count": 0,
            "extra_count": 0,
            "warning_count": 0,
            "needs_review_count": 0,
            "blocked_count": 0,
            "rows": [
                {
                    "plan_external_key": "plan:1",
                    "manual_execution_external_key": "execution:1",
                    "symbol": "AMD",
                    "side": "BUY",
                    "planned_quantity": 2,
                    "actual_quantity": 2,
                    "planned_price": 100.0,
                    "actual_price": 100.0,
                    "reconciliation_status": "MATCHED",
                    "deviation_type": "NONE",
                    "severity": "INFO",
                }
            ],
        },
    )

    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    state = runbook_state.complete_stage(state, "A")
    state = runbook_state.complete_stage(state, "GATE1")
    for name, path in (
        ("daily_plan_json", plan_path),
        ("execution_preview_json", preview_path),
        ("execution_reconciliation_preview_json", reconciliation_path),
    ):
        state = runbook_state.record_artifact(state, name, str(path), workspace)
    state = runbook_state.start_stage(state, "B")
    state = runbook_state.complete_step(state, 7, "B")
    state_path = runbook_state.get_state_path_for_context(
        workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE
    )
    runbook_state.save_state(state, state_path)
    logical = runbook_stage_b_recovery.build_stage_b_logical_operation(state, workspace)
    preseal_path, preseal_ref = runbook_stage_b_recovery.write_precommit_evidence(
        workspace=workspace,
        state_path=state_path,
        state=state,
        logical=logical,
        attempt_id="failed-attempt-1",
        account_root=account_root,
    )
    state, failed_key = runbook_state.reserve_stage_b_execution_attempt(
        state,
        logical_operation_id=logical["logical_operation_id"],
        attempt_id="failed-attempt-1",
        precommit_evidence_ref=preseal_ref,
    )
    command_path = _write_json(
        workspace / "command_runs" / RUNBOOK_DAY_ID / "execution_commit.json",
        {
            "schema_version": "runbook_command_result.v1",
            "runner_result": "FAILED",
            "runbook_day_id": RUNBOOK_DAY_ID,
            "frozen_context": {
                "account_id": ACCOUNT_ID,
                "data_date": DATA_DATE,
                "trade_date": TRADE_DATE,
            },
            "stage_id": "B",
            "step_id": 8,
            "command_key": "execution_commit",
            "command_type": "LEDGER_WRITE",
            "created_at": "2026-08-10T20:00:00+09:00",
            "process": {
                "executed": True,
                "exit_code": 1,
                "duration_ms": 5,
                "timed_out": False,
            },
            "raw_payload": {
                "status": "FAILED",
                "error": "commit transaction rolled back",
            },
        },
    )
    state = runbook_state.mark_idempotency_failed(
        state, failed_key, "execution_commit_failed"
    )
    state = runbook_state.fail_stage(
        state,
        "B",
        "stage_b_step_failed:execution_commit",
        {"command_result_json": str(command_path)},
    )
    runbook_state.save_state(state, state_path)
    return {
        "workspace": workspace,
        "account_root": account_root,
        "state_path": state_path,
        "failed_key": failed_key,
        "logical": logical,
        "preseal_path": preseal_path,
        "preview_path": preview_path,
        "reconciliation_path": reconciliation_path,
        "command_path": command_path,
        "execution_path": execution_path,
        "account_path": account_path,
        "position_path": position_path,
    }


def _close(fixture: dict[str, object], **overrides: object) -> dict[str, object]:
    values = {
        "workspace": fixture["workspace"],
        "account_id": ACCOUNT_ID,
        "data_date": DATA_DATE,
        "trade_date": TRADE_DATE,
        "failed_idempotency_key": fixture["failed_key"],
        "operator": OPERATOR,
        "reason": REASON,
        "confirm_no_actual_trades": True,
        "confirm_no_reexecution": True,
        "account_root": fixture["account_root"],
    }
    values.update(overrides)
    return failed_no_trade_closure.close_failed_no_trade(**values)


def test_failed_zero_write_closure_is_immutable_terminal_and_blocks_retry(tmp_path: Path) -> None:
    fixture = _seed_failed_attempt(tmp_path)
    state_path = fixture["state_path"]
    assert isinstance(state_path, Path)
    state_before = state_path.read_bytes()
    domain_before = {
        name: fixture[name].read_bytes()
        for name in ("execution_path", "account_path", "position_path")
        if isinstance(fixture[name], Path)
    }
    failed_record_before = runbook_state.load_state(state_path).idempotency_records[
        str(fixture["failed_key"])
    ]

    result = _close(fixture)
    state = runbook_state.load_state(state_path)
    validation = failed_no_trade_closure.validate_closure_evidence(
        fixture["workspace"], state_path, state
    )
    classification = runbook_day_rollover.classify_account_runbooks(
        fixture["workspace"], ACCOUNT_ID
    )["classifications"][0]
    rollover = runbook_day_rollover.preview_rollover(
        fixture["workspace"],
        ACCOUNT_ID,
        runbook_recovery.default_calendar(),
        confirm_paper_test=True,
    )
    retry = runbook_stage_runner.run_stage_b(
        fixture["workspace"],
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )
    recovery = runbook_recovery.recovery_status(
        workspace=fixture["workspace"],
        account_id=ACCOUNT_ID,
        source_runbook_day_id=RUNBOOK_DAY_ID,
        calendar=runbook_recovery.default_calendar(),
    )

    assert result["runner_result"] == "PASS" and result["closed"] is True
    assert validation["valid"] is True
    assert classification["classification"] == "FAILED_NO_TRADE_CLOSED"
    assert rollover["runner_result"] == "PASS"
    assert rollover["previous_runbook_day_id"] == RUNBOOK_DAY_ID
    assert retry["runner_result"] == "BLOCKED"
    assert retry["reason"] == "failed_no_trade_closure_terminal"
    assert recovery["runner_result"] == "BLOCKED"
    assert recovery["reason"] == "failed_no_trade_closure_terminal"
    assert state_path.read_bytes() == state_before
    assert state.idempotency_records[str(fixture["failed_key"])] == failed_record_before
    assert all(state.stage_status[stage] == "PENDING" for stage in ("C", "GATE2", "D", "E", "F"))
    assert {
        name: fixture[name].read_bytes()
        for name in ("execution_path", "account_path", "position_path")
        if isinstance(fixture[name], Path)
    } == domain_before


def test_closed_attempt_cannot_receive_stage_b_retry_authorization(tmp_path: Path) -> None:
    fixture = _seed_failed_attempt(tmp_path)
    assessment = runbook_stage_b_recovery.assess_stage_b_recovery(
        workspace=fixture["workspace"],
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        failed_idempotency_key=str(fixture["failed_key"]),
        account_root=fixture["account_root"],
    )
    assessment_path = fixture["workspace"] / "stage_b_recovery_assessment.json"
    runbook_stage_b_recovery.write_json_atomic(assessment_path, assessment)
    _close(fixture)

    with pytest.raises(ValueError, match="failed_no_trade_closure_terminal"):
        runbook_stage_b_recovery.authorize_stage_b_recovery(
            workspace=fixture["workspace"],
            account_id=ACCOUNT_ID,
            data_date=DATA_DATE,
            trade_date=TRADE_DATE,
            assessment_path=assessment_path,
            operator=OPERATOR,
            reason="retry must be blocked after closure",
            confirm_rollback_proven=True,
        )


@pytest.mark.parametrize("contradiction", ["trade_id", "account", "position", "current_state"])
def test_domain_write_contradiction_blocks_closure(tmp_path: Path, contradiction: str) -> None:
    fixture = _seed_failed_attempt(tmp_path)
    if contradiction == "trade_id":
        _write_csv(
            fixture["execution_path"],
            ["trade_id", "date"],
            [{"trade_id": fixture["logical"]["expected_trade_ids"][0], "date": TRADE_DATE}],
        )
    elif contradiction == "account":
        _write_csv(
            fixture["account_path"],
            ["account_id", "snapshot_date"],
            [{"account_id": ACCOUNT_ID, "snapshot_date": TRADE_DATE}],
        )
    elif contradiction == "position":
        _write_csv(
            fixture["position_path"],
            ["account_id", "snapshot_date", "symbol"],
            [{"account_id": ACCOUNT_ID, "snapshot_date": TRADE_DATE, "symbol": "AMD"}],
        )
    else:
        _write_json(
            fixture["account_root"] / "paper_current_state_20260811.json",
            {"account_id": ACCOUNT_ID},
        )

    result = _close(fixture)

    assert result["runner_result"] == "BLOCKED"
    assert not failed_no_trade_closure.closure_path(
        fixture["workspace"], RUNBOOK_DAY_ID
    ).exists()


@pytest.mark.parametrize("drift", ["preseal", "preview", "reconciliation", "failed_binding"])
def test_pinned_or_failed_attempt_drift_blocks_closure(tmp_path: Path, drift: str) -> None:
    fixture = _seed_failed_attempt(tmp_path)
    if drift == "preseal":
        payload = json.loads(fixture["preseal_path"].read_text(encoding="utf-8"))
        payload["attempt_id"] = "other"
        _write_json(fixture["preseal_path"], payload)
    elif drift == "preview":
        payload = json.loads(fixture["preview_path"].read_text(encoding="utf-8"))
        payload["candidates"][0]["actual_price"] = 101.0
        _write_json(fixture["preview_path"], payload)
    elif drift == "reconciliation":
        payload = json.loads(fixture["reconciliation_path"].read_text(encoding="utf-8"))
        payload["rows"][0]["actual_price"] = 101.0
        _write_json(fixture["reconciliation_path"], payload)
    else:
        state = runbook_state.load_state(fixture["state_path"])
        records = dict(state.idempotency_records)
        record = dict(records[str(fixture["failed_key"])])
        record["attempt_id"] = "other"
        records[str(fixture["failed_key"])] = record
        runbook_state.save_state(replace(state, idempotency_records=records), fixture["state_path"])

    result = _close(fixture)

    assert result["runner_result"] == "BLOCKED"


@pytest.mark.parametrize(
    ("overrides", "blocker"),
    [
        ({"operator": ""}, "operator_required"),
        ({"reason": ""}, "closure_reason_required"),
        ({"confirm_no_actual_trades": False}, "no_actual_trades_confirmation_required"),
        ({"confirm_no_reexecution": False}, "no_reexecution_confirmation_required"),
    ],
)
def test_operator_contract_is_required(
    tmp_path: Path, overrides: dict[str, object], blocker: str
) -> None:
    result = _close(_seed_failed_attempt(tmp_path), **overrides)

    assert result["runner_result"] == "BLOCKED"
    assert blocker in result["blockers"]


def test_nonfailed_historical_state_cannot_be_closed(tmp_path: Path) -> None:
    fixture = _seed_failed_attempt(tmp_path)
    state = runbook_state.load_state(fixture["state_path"])
    runbook_state.save_state(
        replace(state, current_status="IN_PROGRESS", stage_status={**state.stage_status, "B": "IN_PROGRESS"}),
        fixture["state_path"],
    )

    result = _close(fixture)

    assert result["runner_result"] == "BLOCKED"
    assert "stage_b_failed_state_required" in result["blockers"]


def test_closure_is_idempotent_and_conflicting_rewrite_is_blocked(tmp_path: Path) -> None:
    fixture = _seed_failed_attempt(tmp_path)
    first = _close(fixture)
    evidence_path = Path(str(first["evidence_path"]))
    before = evidence_path.read_bytes()

    same = _close(fixture)
    different = _close(fixture, reason="different reason")

    assert same["runner_result"] == "PASS" and same["already_closed"] is True
    assert different["runner_result"] == "BLOCKED"
    assert different["reason"] == "existing_closure_evidence_conflict"
    assert evidence_path.read_bytes() == before


def test_tamper_or_state_drift_invalidates_terminal_and_recovery(tmp_path: Path) -> None:
    fixture = _seed_failed_attempt(tmp_path)
    result = _close(fixture)
    evidence_path = Path(str(result["evidence_path"]))
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["reason"] = "tampered"
    _write_json(evidence_path, payload)
    state = runbook_state.load_state(fixture["state_path"])

    validation = failed_no_trade_closure.validate_closure_evidence(
        fixture["workspace"], fixture["state_path"], state
    )
    classification = runbook_day_rollover.classify_account_runbooks(
        fixture["workspace"], ACCOUNT_ID
    )["classifications"][0]
    recovery = runbook_recovery.preview_recovery(
        workspace=fixture["workspace"],
        account_id=ACCOUNT_ID,
        source_runbook_day_id=RUNBOOK_DAY_ID,
        restart_data_date=TRADE_DATE,
        restart_trade_date="2026-08-12",
        reason="recovery should be blocked",
        calendar=runbook_recovery.default_calendar(),
        confirm_paper_test=True,
        confirm_contaminated_incomplete=True,
        confirm_no_real_trades=True,
        confirm_gap_without_backfill=True,
    )

    assert validation["valid"] is False
    assert "closure_content_sha256_mismatch" in validation["blockers"]
    assert classification["classification"] == "ACTIVE_INCOMPLETE"
    assert "closure_content_sha256_mismatch" in classification["blockers"]
    assert "failed_no_trade_closure_invalid" in recovery["blockers"]


def test_source_state_drift_invalidates_existing_closure(tmp_path: Path) -> None:
    fixture = _seed_failed_attempt(tmp_path)
    _close(fixture)
    state = runbook_state.load_state(fixture["state_path"])
    runbook_state.save_state(replace(state, updated_at="2099-01-01T00:00:00+09:00"), fixture["state_path"])
    changed = runbook_state.load_state(fixture["state_path"])

    validation = failed_no_trade_closure.validate_closure_evidence(
        fixture["workspace"], fixture["state_path"], changed
    )

    assert validation["valid"] is False
    assert "closure_source_state_sha256_mismatch" in validation["blockers"]


def test_retirement_status_reports_failed_no_trade_terminal(tmp_path: Path) -> None:
    fixture = _seed_failed_attempt(tmp_path)
    _close(fixture)

    result = runbook_retirement.retirement_status(
        fixture["workspace"],
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        runbook_day_id=RUNBOOK_DAY_ID,
    )

    assert result["runner_result"] == "PASS"
    assert result["retirement_status"] == "FAILED_NO_TRADE_CLOSED"

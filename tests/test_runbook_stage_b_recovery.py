from __future__ import annotations

import csv
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from scripts import runbook_stage_b_recovery as recovery
from scripts import runbook_state


ACCOUNT_ID = "paper_pilot_202606"
DATA_DATE = "2026-08-07"
TRADE_DATE = "2026-08-10"


def _candidates() -> list[dict]:
    return [
        {
            "account_id": ACCOUNT_ID,
            "execution_date": TRADE_DATE,
            "symbol": symbol,
            "side": "SELL",
            "quantity": index + 1,
            "actual_price": 30.0 + index,
            "note": "generated_from_daily_plan",
        }
        for index, symbol in enumerate(("CMG", "EIX", "EQR", "KHC", "MAA", "UDR"))
    ]


def _reconciliation(*, generated_at: str = "2026-08-08T21:00:55+09:00") -> dict:
    rows = [
        {
            "plan_external_key": f"plan:{index}",
            "manual_execution_external_key": f"execution:{index}",
            "symbol": candidate["symbol"],
            "side": candidate["side"],
            "planned_quantity": candidate["quantity"],
            "actual_quantity": candidate["quantity"],
            "planned_price": candidate["actual_price"],
            "actual_price": candidate["actual_price"],
            "page_id": f"page-{index}",
            "reconciliation_status": "MATCHED",
            "deviation_type": "NONE",
            "severity": "INFO",
        }
        for index, candidate in enumerate(_candidates())
    ]
    return {
        "schema_version": "execution_reconciliation_preview.v1",
        "generated_at": generated_at,
        "runner_result": "PASS",
        "account_id": ACCOUNT_ID,
        "data_date": DATA_DATE,
        "trade_date": TRADE_DATE,
        "daily_plan_path": "ignored/timestamped/path.json",
        "notion_row_count": 6,
        "actual_count": 6,
        "planned_count": 6,
        "matched_count": 6,
        "deviated_count": 0,
        "missing_count": 0,
        "extra_count": 0,
        "warning_count": 0,
        "needs_review_count": 0,
        "blocked_count": 0,
        "rows": rows,
    }


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows or [])


def _incident_fixture(tmp_path: Path, *, exit_code: int = 1) -> dict:
    workspace = tmp_path / "workspace"
    account_root = tmp_path / "account"
    workspace.mkdir()
    account_root.mkdir()
    plan_path = workspace / "daily_plan.json"
    preview_path = workspace / "preview.json"
    recon_path = workspace / "reconciliation_20260808_210055.json"
    plan_path.write_text(
        json.dumps(
            {
                "schema_version": "paper_daily_plan.v1",
                "account_id": ACCOUNT_ID,
                "data_date": DATA_DATE,
                "trade_date": TRADE_DATE,
                "items": [
                    {
                        "symbol": item["symbol"],
                        "action": item["side"],
                        "quantity": item["quantity"],
                        "price": item["actual_price"],
                    }
                    for item in _candidates()
                ],
            }
        ),
        encoding="utf-8",
    )
    preview_path.write_text(
        json.dumps(
            {
                "account_id": ACCOUNT_ID,
                "execution_date": TRADE_DATE,
                "candidate_count": 6,
                "candidates": _candidates(),
            }
        ),
        encoding="utf-8",
    )
    recon_path.write_text(json.dumps(_reconciliation()), encoding="utf-8")

    execution = account_root / "paper_execution_log.csv"
    account = account_root / "paper_account_snapshot.csv"
    position = account_root / "paper_position_snapshot.csv"
    _write_csv(execution, ["trade_id", "date"])
    _write_csv(account, ["snapshot_date", "account_id"])
    _write_csv(position, ["snapshot_date", "account_id", "symbol"])
    backup_root = account_root / "archive" / "dev_backups"
    backup_root.mkdir(parents=True)
    for source in (execution, account, position):
        target = backup_root / f"{source.stem}_before_manual_execution_commit_20260810_20260808_210057.csv"
        target.write_bytes(source.read_bytes())

    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    state = runbook_state.complete_stage(state, "A")
    state = runbook_state.complete_stage(state, "GATE1")
    for name, path in (
        ("daily_plan_json", plan_path),
        ("execution_preview_json", preview_path),
        ("execution_reconciliation_preview_json", recon_path),
    ):
        state = runbook_state.record_artifact(state, name, str(path), workspace)
    state = runbook_state.start_stage(state, "B")
    state, failed_key = runbook_state.reserve_idempotency(
        state,
        "execution_commit",
        8,
        "B",
        {
            "execution_preview_json": str(preview_path),
            "execution_reconciliation_preview_json": str(recon_path),
        },
        workspace,
    )
    state = runbook_state.mark_idempotency_running(state, failed_key)
    command_path = workspace / "command_runs" / "failed_execution_commit.json"
    command_path.parent.mkdir(parents=True)
    command_path.write_text(
        json.dumps(
            {
                "schema_version": "runbook_command_result.v1",
                "runner_result": "FAILED",
                "created_at": "2026-08-08T21:00:57+09:00",
                "process": {
                    "executed": True,
                    "exit_code": exit_code,
                    "duration_ms": 10,
                    "timed_out": exit_code == 124,
                },
                "raw_payload": {
                    "status": "FAIL",
                    "error": "Manual execution commit failed and was rolled back: fixture failure",
                },
            }
        ),
        encoding="utf-8",
    )
    state = runbook_state.mark_idempotency_failed(state, failed_key, "execution_commit_failed")
    state = runbook_state.fail_stage(
        state,
        "B",
        "stage_b_step_failed:execution_commit",
        {"command_result_json": str(command_path)},
    )
    state_path = runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    runbook_state.save_state(state, state_path)
    return {
        "workspace": workspace,
        "account_root": account_root,
        "state_path": state_path,
        "failed_key": failed_key,
        "plan_path": plan_path,
        "preview_path": preview_path,
        "recon_path": recon_path,
        "execution_path": execution,
        "account_path": account,
        "position_path": position,
    }


def _assess(fixture: dict) -> dict:
    return recovery.assess_stage_b_recovery(
        workspace=fixture["workspace"],
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        failed_idempotency_key=fixture["failed_key"],
        account_root=fixture["account_root"],
    )


def _write_assessment(fixture: dict, assessment: dict) -> Path:
    path = fixture["workspace"] / "assessment.json"
    recovery.write_json_atomic(path, assessment)
    return path


def _authorize(fixture: dict, assessment: dict) -> dict:
    return recovery.authorize_stage_b_recovery(
        workspace=fixture["workspace"],
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        assessment_path=_write_assessment(fixture, assessment),
        operator="test-operator",
        reason="rollback independently corroborated",
        confirm_rollback_proven=True,
    )


def test_rollback_proven_assess_is_read_only_and_human_retry_eligible(tmp_path: Path) -> None:
    fixture = _incident_fixture(tmp_path)
    before = recovery.sha256_file(fixture["state_path"])

    assessment = _assess(fixture)

    assert assessment["human_retry_eligible"] is True
    assert assessment["recovery_classification"] == "HUMAN_RECOVERY_ELIGIBLE"
    assert assessment["evidence_mode"] == "LEGACY_BACKUP_CORROBORATED"
    assert len(assessment["expected_trade_ids"]) == 6
    assert assessment["same_operation_trade_ids_present"] == []
    assert recovery.sha256_file(fixture["state_path"]) == before


def test_recovery_cli_assess_then_authorize_temp_fixture(tmp_path: Path) -> None:
    fixture = _incident_fixture(tmp_path)
    assessment_path = fixture["workspace"] / "cli_assessment.json"
    common = [
        "--workspace",
        str(fixture["workspace"]),
        "--account-id",
        ACCOUNT_ID,
        "--data-date",
        DATA_DATE,
        "--trade-date",
        TRADE_DATE,
    ]
    assess = subprocess.run(
        [
            sys.executable,
            "scripts\\runbook_stage_b_recovery.py",
            "assess",
            *common,
            "--failed-idempotency-key",
            fixture["failed_key"],
            "--account-root",
            str(fixture["account_root"]),
            "--output",
            str(assessment_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )
    authorize = subprocess.run(
        [
            sys.executable,
            "scripts\\runbook_stage_b_recovery.py",
            "authorize",
            *common,
            "--assessment-json",
            str(assessment_path),
            "--operator",
            "cli-test",
            "--reason",
            "rollback corroborated",
            "--confirm-rollback-proven",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )

    assert assess.returncode == 0, assess.stderr
    assert json.loads(assess.stdout)["human_retry_eligible"] is True
    assert authorize.returncode == 0, authorize.stderr
    assert json.loads(authorize.stdout)["runner_result"] == "PASS"
    assert runbook_state.load_state(fixture["state_path"]).current_status == "PENDING"


def test_authorize_transitions_only_stage_b_and_preserves_failed_record(tmp_path: Path) -> None:
    fixture = _incident_fixture(tmp_path)
    result = _authorize(fixture, _assess(fixture))
    state = runbook_state.load_state(fixture["state_path"])

    assert result["runner_result"] == "PASS"
    assert state.current_stage == "B" and state.current_status == "PENDING"
    assert state.stage_status["A"] == "PASS" and state.stage_status["GATE1"] == "PASS"
    assert state.stage_status["B"] == "PENDING" and state.last_error is None
    assert state.idempotency_records[fixture["failed_key"]]["status"] == "FAILED"
    assert [event["event_type"] for event in state.history[-2:]] == [
        "stage_b_recovery_assessed",
        "stage_b_retry_authorized",
    ]


def test_authorization_consumption_and_attempt_are_atomic_and_exactly_once(tmp_path: Path) -> None:
    fixture = _incident_fixture(tmp_path)
    assessment = _assess(fixture)
    _authorize(fixture, assessment)
    state = runbook_state.load_state(fixture["state_path"])
    logical = recovery.build_stage_b_logical_operation(state, fixture["workspace"])
    preseal_path, preseal_ref = recovery.write_precommit_evidence(
        workspace=fixture["workspace"],
        state_path=fixture["state_path"],
        state=state,
        logical=logical,
        attempt_id="attempt-2",
        account_root=fixture["account_root"],
    )

    consumed, key = runbook_state.reserve_stage_b_execution_attempt(
        state,
        logical_operation_id=logical["logical_operation_id"],
        attempt_id="attempt-2",
        precommit_evidence_ref=preseal_ref,
    )

    authorization = next(iter(consumed.recovery_authorizations.values()))
    assert authorization["status"] == "CONSUMED"
    assert consumed.idempotency_records[key]["status"] == "RUNNING"
    assert consumed.idempotency_records[key]["recovery_authorization_id"] == authorization["authorization_id"]
    assert preseal_path.exists()
    with pytest.raises(ValueError, match="logical_execution_operation_needs_recovery"):
        runbook_state.reserve_stage_b_execution_attempt(
            consumed,
            logical_operation_id=logical["logical_operation_id"],
            attempt_id="attempt-3",
            precommit_evidence_ref=preseal_ref,
        )


def test_logical_operation_pass_forbids_any_additional_attempt(tmp_path: Path) -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    logical_id = "sha256:" + "b" * 64
    state, key = runbook_state.reserve_stage_b_execution_attempt(
        state,
        logical_operation_id=logical_id,
        attempt_id="attempt-1",
        precommit_evidence_ref="preseal-1.json",
    )
    state = runbook_state.mark_idempotency_pass(state, key, result_ref="commit.json")

    with pytest.raises(ValueError, match="duplicate_logical_execution_operation"):
        runbook_state.reserve_stage_b_execution_attempt(
            state,
            logical_operation_id=logical_id,
            attempt_id="attempt-2",
            precommit_evidence_ref="preseal-2.json",
        )


def test_same_assessment_cannot_be_authorized_twice(tmp_path: Path) -> None:
    fixture = _incident_fixture(tmp_path)
    assessment = _assess(fixture)
    _authorize(fixture, assessment)
    with pytest.raises(ValueError):
        _authorize(fixture, assessment)


@pytest.mark.parametrize("drift", ["candidate", "candidate_order"])
def test_candidate_sequence_or_order_change_changes_logical_id(tmp_path: Path, drift: str) -> None:
    fixture = _incident_fixture(tmp_path)
    state = runbook_state.load_state(fixture["state_path"])
    before = recovery.build_stage_b_logical_operation(state, fixture["workspace"])["logical_operation_id"]
    preview = json.loads(fixture["preview_path"].read_text(encoding="utf-8"))
    if drift == "candidate":
        preview["candidates"][0]["actual_price"] = 999.0
    else:
        preview["candidates"][0], preview["candidates"][1] = preview["candidates"][1], preview["candidates"][0]
    fixture["preview_path"].write_text(json.dumps(preview), encoding="utf-8")

    after = recovery.build_stage_b_logical_operation(state, fixture["workspace"])["logical_operation_id"]

    assert after != before


def test_reconciliation_filename_and_metadata_do_not_change_logical_id(tmp_path: Path) -> None:
    fixture = _incident_fixture(tmp_path)
    state = runbook_state.load_state(fixture["state_path"])
    first = recovery.build_stage_b_logical_operation(state, fixture["workspace"])["logical_operation_id"]
    second_path = fixture["workspace"] / "reconciliation_20990101_000000.json"
    second_path.write_text(json.dumps(_reconciliation(generated_at="2099-01-01T00:00:00Z")), encoding="utf-8")
    artifacts = dict(state.artifacts)
    artifacts["execution_reconciliation_preview_json"] = runbook_state.canonicalize_artifact_ref(
        str(second_path), fixture["workspace"]
    )
    second_state = replace(state, artifacts=artifacts)

    second = recovery.build_stage_b_logical_operation(second_state, fixture["workspace"])["logical_operation_id"]

    assert second == first


def test_candidate_drift_rejects_authorized_retry(tmp_path: Path) -> None:
    fixture = _incident_fixture(tmp_path)
    assessment = _assess(fixture)
    _authorize(fixture, assessment)
    state = runbook_state.load_state(fixture["state_path"])
    preview = json.loads(fixture["preview_path"].read_text(encoding="utf-8"))
    preview["candidates"][0]["quantity"] += 1
    fixture["preview_path"].write_text(json.dumps(preview), encoding="utf-8")
    logical = recovery.build_stage_b_logical_operation(state, fixture["workspace"])

    with pytest.raises(ValueError, match="recovery_authorization_logical_operation_mismatch"):
        runbook_state.reserve_stage_b_execution_attempt(
            state,
            logical_operation_id=logical["logical_operation_id"],
            attempt_id="drifted",
            precommit_evidence_ref="preseal.json",
        )


@pytest.mark.parametrize("drift", ["daily_plan", "state"])
def test_authorize_rejects_plan_or_state_sha_drift(tmp_path: Path, drift: str) -> None:
    fixture = _incident_fixture(tmp_path)
    assessment = _assess(fixture)
    assessment_path = _write_assessment(fixture, assessment)
    if drift == "daily_plan":
        fixture["plan_path"].write_text(fixture["plan_path"].read_text(encoding="utf-8") + "\n", encoding="utf-8")
    else:
        state = runbook_state.load_state(fixture["state_path"])
        state = runbook_state.record_artifact(state, "drift", "drift.json", fixture["workspace"])
        runbook_state.save_state(state, fixture["state_path"])

    with pytest.raises(ValueError, match="drift"):
        recovery.authorize_stage_b_recovery(
            workspace=fixture["workspace"],
            account_id=ACCOUNT_ID,
            data_date=DATA_DATE,
            trade_date=TRADE_DATE,
            assessment_path=assessment_path,
            operator="operator",
            reason="reason",
            confirm_rollback_proven=True,
        )


def test_existing_expected_trade_id_rejects_assessment(tmp_path: Path) -> None:
    fixture = _incident_fixture(tmp_path)
    expected = _assess(fixture)["expected_trade_ids"][0]
    _write_csv(fixture["execution_path"], ["trade_id", "date"], [{"trade_id": expected, "date": TRADE_DATE}])

    assessment = _assess(fixture)

    assert assessment["human_retry_eligible"] is False
    assert "expected_trade_id_already_present" in assessment["blockers"]


@pytest.mark.parametrize("mutation", ["backup_mismatch", "same_date_snapshot"])
def test_backup_mismatch_or_partial_write_rejects_assessment(tmp_path: Path, mutation: str) -> None:
    fixture = _incident_fixture(tmp_path)
    if mutation == "backup_mismatch":
        fixture["account_path"].write_text("snapshot_date,account_id\n2026-07-01,x\n", encoding="utf-8")
    else:
        _write_csv(
            fixture["position_path"],
            ["snapshot_date", "account_id", "symbol"],
            [{"snapshot_date": TRADE_DATE, "account_id": ACCOUNT_ID, "symbol": "CMG"}],
        )

    assessment = _assess(fixture)

    assert assessment["human_retry_eligible"] is False
    assert assessment["recovery_classification"] in {"PARTIAL_WRITE", "FORENSIC_RECOVERY_REQUIRED"}


@pytest.mark.parametrize("evidence", ["commit_report", "pass_record"])
def test_successful_commit_evidence_rejects_failed_retry_assessment(tmp_path: Path, evidence: str) -> None:
    fixture = _incident_fixture(tmp_path)
    state = runbook_state.load_state(fixture["state_path"])
    if evidence == "commit_report":
        report = fixture["workspace"] / "commit.json"
        report.write_text("{}", encoding="utf-8")
        state = runbook_state.record_artifact(state, "execution_commit_report_json", str(report), fixture["workspace"])
    else:
        records = dict(state.idempotency_records)
        records[fixture["failed_key"]] = {**records[fixture["failed_key"]], "status": "PASS"}
        state = replace(state, idempotency_records=records)
    runbook_state.save_state(state, fixture["state_path"])

    assessment = _assess(fixture)

    assert assessment["human_retry_eligible"] is False
    assert "successful_execution_commit_evidence_present" in assessment["blockers"]


def test_timeout_is_ambiguous_and_not_human_retry_eligible(tmp_path: Path) -> None:
    fixture = _incident_fixture(tmp_path, exit_code=124)

    assessment = _assess(fixture)

    assert assessment["recovery_classification"] == "AMBIGUOUS_OUTCOME"
    assert assessment["human_retry_eligible"] is False


def test_sync_only_commit_proof_rejects_missing_report(tmp_path: Path) -> None:
    fixture = _incident_fixture(tmp_path)
    state = runbook_state.load_state(fixture["state_path"])
    records = dict(state.idempotency_records)
    records[fixture["failed_key"]] = {**records[fixture["failed_key"]], "status": "PASS", "result_ref": None}
    state = replace(state, idempotency_records=records)

    proof = recovery.validate_stage_b_commit_proof(
        state=state,
        workspace=fixture["workspace"],
        account_root=fixture["account_root"],
    )

    assert proof == {"valid": False, "reason": "execution_commit_report_required"}


def test_sync_only_commit_proof_rejects_ledger_mismatch(tmp_path: Path) -> None:
    fixture = _incident_fixture(tmp_path)
    state = runbook_state.load_state(fixture["state_path"])
    report = fixture["workspace"] / "commit.json"
    report.write_text(
        json.dumps(
            {
                "status": "COMMITTED",
                "account_id": ACCOUNT_ID,
                "execution_date": TRADE_DATE,
                "committed_row_count": 1,
                "committed_trade_ids": ["missing-trade-id"],
            }
        ),
        encoding="utf-8",
    )
    records = dict(state.idempotency_records)
    records[fixture["failed_key"]] = {
        **records[fixture["failed_key"]],
        "status": "PASS",
        "result_ref": runbook_state.canonicalize_artifact_ref(str(report), fixture["workspace"]),
    }
    artifacts = dict(state.artifacts)
    artifacts["execution_commit_report_json"] = runbook_state.canonicalize_artifact_ref(
        str(report), fixture["workspace"]
    )
    state = replace(state, idempotency_records=records, artifacts=artifacts)

    proof = recovery.validate_stage_b_commit_proof(
        state=state,
        workspace=fixture["workspace"],
        account_root=fixture["account_root"],
    )

    assert proof == {"valid": False, "reason": "execution_commit_ledger_proof_mismatch"}


def test_context_mismatch_rejects_assessment_and_authorize(tmp_path: Path) -> None:
    fixture = _incident_fixture(tmp_path)
    with pytest.raises(FileNotFoundError):
        recovery.assess_stage_b_recovery(
            workspace=fixture["workspace"],
            account_id="paper_other",
            data_date=DATA_DATE,
            trade_date=TRADE_DATE,
            failed_idempotency_key=fixture["failed_key"],
            account_root=fixture["account_root"],
        )


def test_legacy_state_without_authorizations_loads_and_validates(tmp_path: Path) -> None:
    state = runbook_state.create_initial_state("paper_default", DATA_DATE, TRADE_DATE)
    payload = state.to_dict()
    payload.pop("recovery_authorizations")
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = runbook_state.load_state(path)

    assert loaded.recovery_authorizations == {}
    assert runbook_state.validate_state(loaded) == []


@pytest.mark.parametrize("account_id", ["paper_default", "paper_growth"])
def test_logical_identity_supports_default_and_non_default_accounts(tmp_path: Path, account_id: str) -> None:
    state = runbook_state.create_initial_state(account_id, DATA_DATE, TRADE_DATE)
    preview = {"candidates": [{**_candidates()[0], "account_id": account_id}]}

    sequence = recovery.normalize_candidate_sequence(preview, state)

    assert sequence[0]["account_id"] == account_id

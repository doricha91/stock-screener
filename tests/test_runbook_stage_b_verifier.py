from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from scripts import runbook_stage_b_verifier as verifier
from scripts import runbook_state
from scripts.runbook_no_action import sha256_file, write_stage_b_no_action_evidence
from core.paper_execution_intent import build_execution_intent


ACCOUNT_ID = "paper_pilot_202606"
DATA_DATE = "2026-06-30"
TRADE_DATE = "2026-07-01"


def _commit_report(**overrides) -> dict:
    payload = {
        "status": "COMMITTED",
        "account_id": ACCOUNT_ID,
        "execution_date": TRADE_DATE,
        "committed_row_count": 2,
        "committed_trade_ids": ["trade-1", "trade-2"],
        "current_state_written": True,
        "account_snapshot_written": True,
        "position_snapshot_written": True,
        "committed_rows": [
            {"commit_status": "COMMITTED", "committed_trade_id": "trade-1"},
            {"commit_status": "COMMITTED", "committed_trade_id": "trade-2"},
        ],
    }
    payload.update(overrides)
    return payload


def _sync_report(**overrides) -> dict:
    payload = {
        "overall_status": "SUCCESS",
        "account_id": ACCOUNT_ID,
        "execution_date": TRADE_DATE,
        "candidate_count": 2,
        "updated_count": 2,
        "failed_count": 0,
        "rows": [
            {"committed_trade_id": "trade-1", "status": "UPDATED"},
            {"committed_trade_id": "trade-2", "status": "UPDATED"},
        ],
    }
    payload.update(overrides)
    return payload


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _reports(tmp_path: Path, commit_payload: dict | None = None, sync_payload: dict | None = None) -> tuple[Path, Path]:
    commit_path = tmp_path / "commit.json"
    sync_path = tmp_path / "sync.json"
    if commit_payload is not None:
        _write_json(commit_path, commit_payload)
    if sync_payload is not None:
        _write_json(sync_path, sync_payload)
    return commit_path, sync_path


def _v2_reports(tmp_path: Path, outcomes: list[str]) -> tuple[Path, Path]:
    rows = []
    committed_rows = []
    committed_trade_ids = []
    for index, outcome in enumerate(outcomes, start=1):
        symbol = f"TEST{index}"
        key = f"manual_execution:{ACCOUNT_ID}:{TRADE_DATE}:{symbol}:BUY:{index:02d}"
        rows.append({"candidate_key": key, "outcome": outcome})
        if outcome in {"EXECUTED", "PARTIAL"}:
            trade_id = f"trade-{index}"
            committed_trade_ids.append(trade_id)
            committed_rows.append(
                {
                    "account_id": ACCOUNT_ID,
                    "canonical_key": key,
                    "symbol": symbol,
                    "commit_status": "COMMITTED",
                    "committed_trade_id": trade_id,
                }
            )
    preview = {
        "schema_version": runbook_state.EXECUTION_CONTRACT_V2,
        "reconciliation_contract_version": runbook_state.EXECUTION_CONTRACT_V2,
        "runner_result": "PASS",
        "account_id": ACCOUNT_ID,
        "data_date": DATA_DATE,
        "trade_date": TRADE_DATE,
        "input_finalized": True,
        "planned_count": len(rows),
        "executed_count": outcomes.count("EXECUTED"),
        "partial_count": outcomes.count("PARTIAL"),
        "not_executed_count": outcomes.count("NOT_EXECUTED"),
        "count_invariant_satisfied": True,
        "rows": rows,
    }
    preview_path = _write_json(tmp_path / "reconciliation.json", preview)
    zero_write = not committed_rows
    commit = {
        "schema_version": "execution_commit.v2",
        "execution_contract_version": runbook_state.EXECUTION_CONTRACT_V2,
        "status": "COMMITTED",
        "zero_write": zero_write,
        "account_id": ACCOUNT_ID,
        "data_date": DATA_DATE,
        "execution_date": TRADE_DATE,
        "reconciliation_preview_json_path": str(preview_path),
        "reconciliation_preview_sha256": sha256_file(preview_path),
        "committed_row_count": len(committed_rows),
        "committed_trade_ids": committed_trade_ids,
        "current_state_written": not zero_write,
        "account_snapshot_written": not zero_write,
        "position_snapshot_written": not zero_write,
        "committed_rows": committed_rows,
    }
    return _write_json(tmp_path / "commit-v2.json", commit), preview_path


def _explicit_v1_state() -> runbook_state.RunbookState:
    return replace(
        runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE),
        execution_contract={
            "version": runbook_state.EXECUTION_CONTRACT_V1,
            "input_finalized": False,
            "finalized_at": None,
        },
    )


def _seed_stage_b_state(
    workspace: Path,
    commit_path: Path | None,
    sync_path: Path | None,
    *,
    sync_key: str = "execution_status_sync_report_json",
    stage_b_pass: bool = True,
) -> Path:
    state = _explicit_v1_state()
    state = runbook_state.complete_stage(state, "A")
    state = runbook_state.complete_stage(state, "GATE1")
    if stage_b_pass:
        state = runbook_state.complete_stage(state, "B")
    if commit_path is not None:
        state = runbook_state.record_artifact(state, "execution_commit_report_json", str(commit_path), workspace)
    if sync_path is not None:
        state = runbook_state.record_artifact(state, sync_key, str(sync_path), workspace)
    state_path = runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    runbook_state.save_state(state, state_path)
    return state_path


def _seed_no_action_state(workspace: Path) -> tuple[Path, Path, Path]:
    state = _explicit_v1_state()
    state = runbook_state.complete_stage(state, "A")
    state = runbook_state.complete_stage(state, "GATE1")
    state = runbook_state.complete_stage(state, "B")
    plan_path = _write_json(
        workspace / "daily_plan_no_action.json",
        {
            "schema_version": "paper_daily_plan.v1",
            "account_id": ACCOUNT_ID,
            "data_date": DATA_DATE,
            "trade_date": TRADE_DATE,
            "plan_date": TRADE_DATE,
            "run_mode": "official",
            "official_run": True,
            "generated_at": "2026-06-30T12:00:00Z",
            "items": [],
            "execution_intent": build_execution_intent([]),
            "fingerprints": {"generator_version": "paper_daily_plan.v1"},
        },
    )
    gate_path = _write_json(
        workspace / "gate1_no_action.json",
        {
            "schema_version": "runbook_gate_result.v1",
            "runner_result": "PASS",
            "gate_id": "GATE1",
            "frozen_context": {
                "account_id": ACCOUNT_ID,
                "data_date": DATA_DATE,
                "trade_date": TRADE_DATE,
            },
            "action_mode": "NO_ACTION",
            "execution_required": False,
            "candidate_execution_count": 0,
            "manual_execution_row_count": 0,
            "daily_plan_sha256": sha256_file(plan_path),
        },
    )
    state = runbook_state.record_artifact(state, "daily_plan_json", str(plan_path), workspace)
    state = runbook_state.record_artifact(state, "gate1_readiness_json", str(gate_path), workspace)
    _, evidence_path, evidence_md = write_stage_b_no_action_evidence(
        workspace,
        state,
        daily_plan_path=plan_path,
        gate1_path=gate_path,
    )
    state = runbook_state.record_artifact(state, "stage_b_no_action_json", str(evidence_path), workspace)
    state = runbook_state.record_artifact(state, "stage_b_no_action_md", str(evidence_md), workspace)
    state_path = runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    runbook_state.save_state(state, state_path)
    return state_path, plan_path, evidence_path


def test_stage_b_verifier_passes_normal_reports_and_writes_artifacts(tmp_path: Path) -> None:
    commit_path, sync_path = _reports(tmp_path, _commit_report(), _sync_report())

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        commit_report=commit_path,
        sync_report=sync_path,
    )

    assert result["runner_result"] == "PASS"
    assert result["committed_row_count"] == 2
    assert result["updated_count"] == 2
    assert Path(result["verification_json"]).exists()
    assert Path(result["verification_md"]).exists()
    assert Path(result["latest_verification_json"]).exists()
    assert "Proceed to Stage C" in Path(result["verification_md"]).read_text(encoding="utf-8")


def test_stage_b_verifier_passes_valid_no_action_evidence(tmp_path: Path) -> None:
    state_path, _, evidence_path = _seed_no_action_state(tmp_path)

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
    )

    assert result["runner_result"] == "PASS"
    assert result["action_mode"] == "NO_ACTION"
    assert result["verified_no_action"] is True
    assert result["committed_row_count"] == 0
    assert result["updated_count"] == 0
    assert result["failed_count"] == 0
    assert result["commit_report_json"] is None
    assert result["sync_report_json"] is None
    assert result["stage_b_no_action_json"] == str(evidence_path)
    loaded = runbook_state.load_state(state_path)
    assert "stage_b_verification_json" in loaded.artifacts


def test_stage_b_verifier_blocks_no_action_daily_plan_hash_mismatch(tmp_path: Path) -> None:
    _, plan_path, _ = _seed_no_action_state(tmp_path)
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    payload["generated_at"] = "2026-06-30T13:00:00Z"
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path, account_id=ACCOUNT_ID, data_date=DATA_DATE, trade_date=TRADE_DATE
    )

    assert result["runner_result"] == "BLOCKED"
    assert any(check["reason_code"] == "daily_plan_hash_mismatch" for check in result["checks"])


def test_stage_b_verifier_blocks_no_action_context_mismatch(tmp_path: Path) -> None:
    _, _, evidence_path = _seed_no_action_state(tmp_path)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["trade_date"] = "2026-07-02"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path, account_id=ACCOUNT_ID, data_date=DATA_DATE, trade_date=TRADE_DATE
    )

    assert result["runner_result"] == "BLOCKED"
    assert any(check["reason_code"] == "no_action_evidence_context_mismatch" for check in result["checks"])


def test_stage_b_verifier_blocks_explicit_report_for_no_action(tmp_path: Path) -> None:
    _seed_no_action_state(tmp_path)
    commit_path = _write_json(tmp_path / "unexpected_commit.json", _commit_report())

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        commit_report=commit_path,
    )

    assert result["runner_result"] == "BLOCKED"
    assert any(
        check["reason_code"] == "unexpected_execution_report_for_no_action" for check in result["checks"]
    )


def test_stage_b_verifier_blocks_explicit_sync_report_for_no_action(tmp_path: Path) -> None:
    _seed_no_action_state(tmp_path)
    sync_path = _write_json(tmp_path / "unexpected_sync.json", _sync_report())

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        sync_report=sync_path,
    )

    assert result["runner_result"] == "BLOCKED"
    assert any(
        check["reason_code"] == "unexpected_execution_report_for_no_action" for check in result["checks"]
    )


def test_stage_b_verifier_blocks_no_action_execution_commit_idempotency(tmp_path: Path) -> None:
    state_path, _, _ = _seed_no_action_state(tmp_path)
    state = runbook_state.load_state(state_path)
    state, key = runbook_state.reserve_idempotency(state, "execution_commit", 8, "B", {}, tmp_path)
    state = runbook_state.mark_idempotency_pass(state, key)
    runbook_state.save_state(state, state_path)

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path, account_id=ACCOUNT_ID, data_date=DATA_DATE, trade_date=TRADE_DATE
    )

    assert result["runner_result"] == "BLOCKED"
    assert any(
        check["reason_code"] == "unexpected_execution_idempotency_for_no_action"
        for check in result["checks"]
    )


def test_stage_b_verifier_blocks_missing_no_action_artifact(tmp_path: Path) -> None:
    state_path, _, _ = _seed_no_action_state(tmp_path)
    state = runbook_state.load_state(state_path)
    artifacts = dict(state.artifacts)
    artifacts.pop("stage_b_no_action_json")
    state = replace(state, artifacts=artifacts)
    runbook_state.save_state(state, state_path)

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path, account_id=ACCOUNT_ID, data_date=DATA_DATE, trade_date=TRADE_DATE
    )

    assert result["runner_result"] == "BLOCKED"
    assert any(check["reason_code"] == "missing_no_action_artifact" for check in result["checks"])


def test_stage_b_verifier_prefers_cli_paths_when_both_are_provided(tmp_path: Path) -> None:
    state_commit, state_sync = _reports(tmp_path / "state", _commit_report(committed_row_count=1), _sync_report())
    cli_commit, cli_sync = _reports(tmp_path / "cli", _commit_report(), _sync_report())
    _seed_stage_b_state(tmp_path, state_commit, state_sync)

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        commit_report=cli_commit,
        sync_report=cli_sync,
    )

    assert result["runner_result"] == "PASS"
    assert result["resolved_from_state"] is False
    assert result["resolved_commit_report_json"] == str(cli_commit)
    assert result["resolved_sync_report_json"] == str(cli_sync)


def test_stage_b_verifier_auto_resolves_reports_from_state(tmp_path: Path) -> None:
    commit_path, sync_path = _reports(tmp_path, _commit_report(), _sync_report())
    _seed_stage_b_state(tmp_path, commit_path, sync_path)

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
    )

    assert result["runner_result"] == "PASS"
    assert result["resolved_from_state"] is True
    assert result["resolved_commit_report_json"] == str(commit_path)
    assert result["resolved_sync_report_json"] == str(sync_path)
    loaded = runbook_state.load_state(runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE))
    assert "stage_b_verification_json" in loaded.artifacts


def test_stage_b_verifier_prefers_sync_json_key_over_fallback(tmp_path: Path) -> None:
    commit_path = _write_json(tmp_path / "commit.json", _commit_report())
    preferred_sync = _write_json(tmp_path / "sync_preferred.json", _sync_report())
    fallback_sync = _write_json(tmp_path / "sync_fallback.json", _sync_report(updated_count=1))
    state = _explicit_v1_state()
    state = runbook_state.complete_stage(state, "A")
    state = runbook_state.complete_stage(state, "GATE1")
    state = runbook_state.complete_stage(state, "B")
    state = runbook_state.record_artifact(state, "execution_commit_report_json", str(commit_path), tmp_path)
    state = runbook_state.record_artifact(state, "execution_status_sync_report", str(fallback_sync), tmp_path)
    state = runbook_state.record_artifact(state, "execution_status_sync_report_json", str(preferred_sync), tmp_path)
    state_path = runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    runbook_state.save_state(state, state_path)

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
    )

    assert result["runner_result"] == "PASS"
    assert result["resolved_sync_report_json"] == str(preferred_sync)


def test_stage_b_verifier_uses_sync_report_fallback_key(tmp_path: Path) -> None:
    commit_path, sync_path = _reports(tmp_path, _commit_report(), _sync_report())
    _seed_stage_b_state(tmp_path, commit_path, sync_path, sync_key="execution_status_sync_report")

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
    )

    assert result["runner_result"] == "PASS"
    assert result["resolved_sync_report_json"] == str(sync_path)


def test_stage_b_verifier_blocks_when_state_is_missing(tmp_path: Path) -> None:
    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
    )

    assert result["runner_result"] == "BLOCKED"
    assert any(check["reason_code"] == "runbook_state_missing" for check in result["checks"])


def test_stage_b_verifier_blocks_when_stage_b_not_pass(tmp_path: Path) -> None:
    commit_path, sync_path = _reports(tmp_path, _commit_report(), _sync_report())
    _seed_stage_b_state(tmp_path, commit_path, sync_path, stage_b_pass=False)

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
    )

    assert result["runner_result"] == "BLOCKED"
    assert any(check["reason_code"] == "stage_b_not_pass" for check in result["checks"])


def test_stage_b_verifier_blocks_when_artifact_ref_missing(tmp_path: Path) -> None:
    _, sync_path = _reports(tmp_path, _commit_report(), _sync_report())
    _seed_stage_b_state(tmp_path, None, sync_path)

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
    )

    assert result["runner_result"] == "BLOCKED"
    assert any(check["reason_code"] == "missing_stage_b_artifact_ref" for check in result["checks"])


def test_stage_b_verifier_fails_when_pinned_file_is_missing(tmp_path: Path) -> None:
    commit_path, sync_path = _reports(tmp_path, _commit_report(), _sync_report())
    missing_commit = tmp_path / "missing_commit.json"
    _seed_stage_b_state(tmp_path, missing_commit, sync_path)

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
    )

    assert result["runner_result"] == "FAILED"
    assert any(check["reason_code"] == "stage_b_artifact_file_missing" for check in result["checks"])


def test_stage_b_verifier_resolves_workspace_relative_paths(tmp_path: Path) -> None:
    commit_path = tmp_path / "artifacts" / "commit.json"
    sync_path = tmp_path / "artifacts" / "sync.json"
    commit_path.parent.mkdir(parents=True)
    _write_json(commit_path, _commit_report())
    _write_json(sync_path, _sync_report())
    _seed_stage_b_state(tmp_path, commit_path, sync_path)

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
    )

    assert result["runner_result"] == "PASS"
    assert result["resolved_commit_report_json"] == str(commit_path)
    assert result["resolved_sync_report_json"] == str(sync_path)


def test_stage_b_verifier_pins_artifact_to_existing_state(tmp_path: Path) -> None:
    state = _explicit_v1_state()
    state = runbook_state.complete_stage(state, "A")
    state = runbook_state.complete_stage(state, "GATE1")
    state = runbook_state.complete_stage(state, "B")
    state_path = runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    runbook_state.save_state(state, state_path)
    commit_path, sync_path = _reports(tmp_path, _commit_report(), _sync_report())

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        commit_report=commit_path,
        sync_report=sync_path,
    )

    assert result["state_updated"] is True
    loaded = runbook_state.load_state(state_path)
    assert loaded.artifacts["stage_b_verification_json"].endswith("stage_b_verification.json")
    assert loaded.artifacts["stage_b_verification_md"].endswith("stage_b_verification.md")


def test_stage_b_verifier_blocks_when_commit_status_is_not_committed(tmp_path: Path) -> None:
    commit_path, sync_path = _reports(tmp_path, _commit_report(status="FAILED"), _sync_report())

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        trade_date=TRADE_DATE,
        commit_report=commit_path,
        sync_report=sync_path,
    )

    assert result["runner_result"] == "BLOCKED"
    assert any(check["reason_code"] == "commit_status_not_committed" for check in result["checks"])


def test_stage_b_verifier_execution_path_still_blocks_zero_committed_rows(tmp_path: Path) -> None:
    commit_path, sync_path = _reports(
        tmp_path,
        _commit_report(committed_row_count=0, committed_trade_ids=[], committed_rows=[]),
        _sync_report(candidate_count=0, updated_count=0, rows=[]),
    )

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        trade_date=TRADE_DATE,
        commit_report=commit_path,
        sync_report=sync_path,
    )

    assert result["runner_result"] == "BLOCKED"
    assert result["action_mode"] == "EXECUTION"
    assert any(check["reason_code"] == "committed_row_count_zero" for check in result["checks"])


def test_stage_b_verifier_blocks_count_mismatch(tmp_path: Path) -> None:
    commit_path, sync_path = _reports(tmp_path, _commit_report(), _sync_report(updated_count=1))

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        trade_date=TRADE_DATE,
        commit_report=commit_path,
        sync_report=sync_path,
    )

    assert result["runner_result"] == "BLOCKED"
    assert any(check["reason_code"] == "sync_updated_count_mismatch" for check in result["checks"])


def test_stage_b_verifier_blocks_failed_sync_count(tmp_path: Path) -> None:
    commit_path, sync_path = _reports(tmp_path, _commit_report(), _sync_report(failed_count=1))

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        trade_date=TRADE_DATE,
        commit_report=commit_path,
        sync_report=sync_path,
    )

    assert result["runner_result"] == "BLOCKED"
    assert any(check["reason_code"] == "sync_failed_count_nonzero" for check in result["checks"])


def test_stage_b_verifier_blocks_trade_id_set_mismatch(tmp_path: Path) -> None:
    commit_path, sync_path = _reports(
        tmp_path,
        _commit_report(),
        _sync_report(rows=[{"committed_trade_id": "trade-1"}, {"committed_trade_id": "trade-x"}]),
    )

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        trade_date=TRADE_DATE,
        commit_report=commit_path,
        sync_report=sync_path,
    )

    assert result["runner_result"] == "BLOCKED"
    assert any(check["reason_code"] == "committed_trade_id_set_mismatch" for check in result["checks"])


def test_stage_b_verifier_blocks_account_mismatch(tmp_path: Path) -> None:
    commit_path, sync_path = _reports(tmp_path, _commit_report(account_id="paper_other"), _sync_report())

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        trade_date=TRADE_DATE,
        commit_report=commit_path,
        sync_report=sync_path,
    )

    assert result["runner_result"] == "BLOCKED"
    assert any(check["reason_code"] == "account_id_mismatch" for check in result["checks"])


def test_stage_b_verifier_blocks_trade_date_mismatch(tmp_path: Path) -> None:
    commit_path, sync_path = _reports(tmp_path, _commit_report(execution_date="2026-07-02"), _sync_report())

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        trade_date=TRADE_DATE,
        commit_report=commit_path,
        sync_report=sync_path,
    )

    assert result["runner_result"] == "BLOCKED"
    assert any(check["reason_code"] == "trade_date_mismatch" for check in result["checks"])


def test_stage_b_verifier_fails_missing_report_file(tmp_path: Path) -> None:
    commit_path, sync_path = _reports(tmp_path, None, _sync_report())

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        trade_date=TRADE_DATE,
        commit_report=commit_path,
        sync_report=sync_path,
    )

    assert result["runner_result"] == "FAILED"
    assert any(check["reason_code"] == "missing_report_file" for check in result["checks"])


def test_v2_verifier_pins_preview_count_identity_and_digest(tmp_path: Path) -> None:
    commit_path, preview_path = _v2_reports(tmp_path, ["EXECUTED", "PARTIAL", "NOT_EXECUTED"])

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        commit_report=commit_path,
    )

    assert result["runner_result"] == "PASS"
    assert result["reconciliation_preview_json"] == str(preview_path)
    assert result["reconciliation_preview_sha256"] == sha256_file(preview_path)
    assert (result["planned_count"], result["executed_count"], result["partial_count"], result["not_executed_count"]) == (3, 1, 1, 1)
    assert any(check["reason_code"] == "v2_candidate_key_set_match" for check in result["checks"])


def test_v2_verifier_rerun_has_deterministic_decision(tmp_path: Path) -> None:
    commit_path, _ = _v2_reports(tmp_path, ["EXECUTED", "NOT_EXECUTED"])

    first = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        commit_report=commit_path,
    )
    second = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        commit_report=commit_path,
    )

    decision = lambda payload: (
        payload["runner_result"],
        payload["planned_count"],
        payload["committed_row_count"],
        [(item["name"], item["status"], item["reason_code"]) for item in payload["checks"]],
    )
    assert decision(first) == decision(second)


def test_v2_verifier_blocks_tampered_pinned_preview(tmp_path: Path) -> None:
    commit_path, preview_path = _v2_reports(tmp_path, ["EXECUTED"])
    preview = json.loads(preview_path.read_text(encoding="utf-8"))
    preview["rows"][0]["outcome"] = "NOT_EXECUTED"
    _write_json(preview_path, preview)

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        commit_report=commit_path,
    )

    assert result["runner_result"] == "BLOCKED"
    assert any(check["reason_code"] == "v2_preview_digest_mismatch" for check in result["checks"])


def test_v2_verifier_blocks_duplicate_committed_candidate_key(tmp_path: Path) -> None:
    commit_path, _ = _v2_reports(tmp_path, ["EXECUTED", "PARTIAL"])
    commit = json.loads(commit_path.read_text(encoding="utf-8"))
    commit["committed_rows"][1]["canonical_key"] = commit["committed_rows"][0]["canonical_key"]
    _write_json(commit_path, commit)

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        commit_report=commit_path,
    )

    assert result["runner_result"] == "BLOCKED"
    assert any(check["reason_code"] == "v2_candidate_key_set_mismatch" for check in result["checks"])


def test_v2_verifier_blocks_extra_and_missing_committed_candidate_key(tmp_path: Path) -> None:
    commit_path, _ = _v2_reports(tmp_path, ["EXECUTED"])
    commit = json.loads(commit_path.read_text(encoding="utf-8"))
    commit["committed_rows"][0]["canonical_key"] = (
        f"manual_execution:{ACCOUNT_ID}:{TRADE_DATE}:EXTRA:BUY:99"
    )
    _write_json(commit_path, commit)

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        commit_report=commit_path,
    )

    assert result["runner_result"] == "BLOCKED"
    assert any(check["reason_code"] == "v2_candidate_key_set_mismatch" for check in result["checks"])


def test_v2_verifier_blocks_missing_preview_binding(tmp_path: Path) -> None:
    commit_path, _ = _v2_reports(tmp_path, ["EXECUTED"])
    commit = json.loads(commit_path.read_text(encoding="utf-8"))
    commit.pop("reconciliation_preview_sha256")
    _write_json(commit_path, commit)

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        commit_report=commit_path,
    )

    assert result["runner_result"] == "BLOCKED"
    assert any(check["reason_code"] == "v2_preview_binding_missing" for check in result["checks"])


def test_v2_verifier_blocks_data_date_context_mismatch(tmp_path: Path) -> None:
    commit_path, _ = _v2_reports(tmp_path, ["EXECUTED"])
    commit = json.loads(commit_path.read_text(encoding="utf-8"))
    commit["data_date"] = "2026-06-29"
    _write_json(commit_path, commit)

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        commit_report=commit_path,
    )

    assert result["runner_result"] == "BLOCKED"
    assert any(check["reason_code"] == "v2_commit_context_mismatch" for check in result["checks"])


def test_v2_verifier_blocks_count_mismatch_even_with_matching_digest(tmp_path: Path) -> None:
    commit_path, preview_path = _v2_reports(tmp_path, ["EXECUTED", "NOT_EXECUTED"])
    preview = json.loads(preview_path.read_text(encoding="utf-8"))
    preview["not_executed_count"] = 0
    _write_json(preview_path, preview)
    commit = json.loads(commit_path.read_text(encoding="utf-8"))
    commit["reconciliation_preview_sha256"] = sha256_file(preview_path)
    _write_json(commit_path, commit)

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        commit_report=commit_path,
    )

    assert result["runner_result"] == "BLOCKED"
    assert any(check["reason_code"] == "v2_outcome_count_invariants_mismatch" for check in result["checks"])


def test_v2_all_not_executed_is_verified_zero_write(tmp_path: Path) -> None:
    commit_path, _ = _v2_reports(tmp_path, ["NOT_EXECUTED", "NOT_EXECUTED"])

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        commit_report=commit_path,
    )

    assert result["runner_result"] == "PASS"
    assert result["verified_zero_write"] is True
    assert result["committed_row_count"] == 0
    assert result["not_executed_count"] == 2


def test_verifier_blocks_unknown_execution_contract_version(tmp_path: Path) -> None:
    commit_path = _write_json(
        tmp_path / "commit-unknown.json",
        _commit_report(execution_contract_version="execution_reconciliation_preview.v999"),
    )

    result = verifier.verify_stage_b_completion(
        workspace=tmp_path,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        commit_report=commit_path,
    )

    assert result["runner_result"] == "BLOCKED"
    assert any(check["reason_code"] == "unsupported_execution_contract_version" for check in result["checks"])

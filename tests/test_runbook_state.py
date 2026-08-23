from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from scripts import runbook_state


ACCOUNT_ID = "paper_pilot_202606"
DATA_DATE = "2026-06-12"
TRADE_DATE = "2026-06-15"


def test_initial_state_has_frozen_context() -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)

    assert state.frozen_context.account_id == ACCOUNT_ID
    assert state.frozen_context.data_date == DATA_DATE
    assert state.frozen_context.trade_date == TRADE_DATE
    assert state.timezone == "Asia/Seoul"


def test_runbook_day_id_uses_account_data_date_and_trade_date() -> None:
    assert (
        runbook_state.get_runbook_day_id(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
        == "paper_pilot_202606_2026-06-12_2026-06-15"
    )


def test_legacy_and_multi_account_state_paths(tmp_path: Path) -> None:
    runbook_day_id = runbook_state.get_runbook_day_id(ACCOUNT_ID, DATA_DATE, TRADE_DATE)

    assert runbook_state.get_state_path(tmp_path) == tmp_path / "runbook_state.json"
    assert runbook_state.get_state_dir(tmp_path) == tmp_path / "runbook_states"
    assert (
        runbook_state.get_state_path_for_runbook_day_id(tmp_path, runbook_day_id)
        == tmp_path / "runbook_states" / f"{runbook_day_id}.json"
    )
    assert (
        runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
        == tmp_path / "runbook_states" / f"{runbook_day_id}.json"
    )


def test_context_state_files_are_separate_per_account(tmp_path: Path) -> None:
    result_a, path_a, state_a = runbook_state.init_state_file_for_context(
        tmp_path,
        "paper_A",
        DATA_DATE,
        TRADE_DATE,
    )
    result_b, path_b, state_b = runbook_state.init_state_file_for_context(
        tmp_path,
        "paper_B",
        DATA_DATE,
        TRADE_DATE,
    )

    assert result_a == "CREATED"
    assert result_b == "CREATED"
    assert path_a == tmp_path / "runbook_states" / "paper_A_2026-06-12_2026-06-15.json"
    assert path_b == tmp_path / "runbook_states" / "paper_B_2026-06-12_2026-06-15.json"
    assert state_a.frozen_context.account_id == "paper_A"
    assert state_b.frozen_context.account_id == "paper_B"
    assert runbook_state.load_state_for_context(tmp_path, "paper_A", DATA_DATE, TRADE_DATE) == state_a
    assert runbook_state.load_state_for_context(tmp_path, "paper_B", DATA_DATE, TRADE_DATE) == state_b


def test_initial_state_defaults() -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)

    assert state.current_stage == "A"
    assert state.current_status in {"READY", "PENDING"}
    assert state.last_completed_step is None
    assert state.last_completed_stage is None
    assert set(state.stage_status) == {"A", "GATE1", "B", "C", "GATE2", "D", "E", "F"}
    assert all(status == "PENDING" for status in state.stage_status.values())
    assert state.execution_contract == {
        "version": runbook_state.EXECUTION_CONTRACT_V2,
        "input_finalized": False,
        "finalized_at": None,
    }
    assert state.idempotency_records == {}


def test_validate_initial_state_returns_no_errors() -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)

    assert runbook_state.validate_state(state) == []


def test_save_state_then_load_state_round_trips(tmp_path: Path) -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    path = tmp_path / "runbook_state.json"

    runbook_state.save_state(state, path)
    loaded = runbook_state.load_state(path)

    assert loaded == state


def test_new_context_state_file_persists_v2_contract(tmp_path: Path) -> None:
    result, path, state = runbook_state.init_state_file_for_context(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
    )

    loaded = runbook_state.load_state(path)

    assert result == "CREATED"
    assert state.execution_contract["version"] == runbook_state.EXECUTION_CONTRACT_V2
    assert loaded.execution_contract == state.execution_contract


def test_new_v2_state_finalizes_without_activation_and_activation_is_exact_no_op() -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)

    assert runbook_state.activate_execution_outcome_v2(state) is state

    finalized = runbook_state.finalize_execution_input(state)

    assert finalized.execution_contract["version"] == runbook_state.EXECUTION_CONTRACT_V2
    assert finalized.execution_contract["input_finalized"] is True
    assert finalized.execution_contract["finalized_at"] is not None


def test_existing_explicit_v1_state_remains_v1(tmp_path: Path) -> None:
    state = replace(
        runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE),
        execution_contract={
            "version": runbook_state.EXECUTION_CONTRACT_V1,
            "input_finalized": False,
            "finalized_at": None,
        },
    )
    path = runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    runbook_state.save_state(state, path)

    result, loaded_path, loaded = runbook_state.init_state_file_for_context(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
    )

    assert result == "EXISTING"
    assert loaded_path == path
    assert runbook_state.get_execution_contract(loaded)["version"] == runbook_state.EXECUTION_CONTRACT_V1


def test_legacy_missing_execution_contract_remains_effective_v1(tmp_path: Path) -> None:
    payload = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE).to_dict()
    payload.pop("execution_contract")
    path = runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")

    result, _, loaded = runbook_state.init_state_file_for_context(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
    )

    assert result == "EXISTING"
    assert loaded.execution_contract == {}
    assert runbook_state.get_execution_contract(loaded) == {
        "version": runbook_state.EXECUTION_CONTRACT_V1,
        "input_finalized": False,
        "finalized_at": None,
    }


def test_load_legacy_state_without_stage_f_treats_it_as_pending(tmp_path: Path) -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    payload = state.to_dict()
    payload["stage_status"].pop("F")
    path = tmp_path / "legacy_runbook_state.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = runbook_state.load_state(path)

    assert loaded.stage_status["F"] == "PENDING"
    assert runbook_state.validate_state(loaded) == []


def test_save_load_preserves_idempotency_records(tmp_path: Path) -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    state, _ = runbook_state.reserve_idempotency(
        state,
        "execution_commit",
        8,
        "B",
        {"execution_preview_json": "outputs/preview.json"},
    )
    path = tmp_path / "runbook_state.json"

    runbook_state.save_state(state, path)
    loaded = runbook_state.load_state(path)

    assert loaded.idempotency_records == state.idempotency_records


def test_same_context_init_keeps_existing_state(tmp_path: Path) -> None:
    result, state = runbook_state.init_state_file(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    modified_state = replace(state, current_status="WAIT")
    runbook_state.save_state(modified_state, tmp_path / "runbook_state.json")

    second_result, second_state = runbook_state.init_state_file(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)

    assert result == "CREATED"
    assert second_result == "EXISTING"
    assert second_state.current_status == "WAIT"


def test_different_context_init_does_not_overwrite(tmp_path: Path) -> None:
    _, state = runbook_state.init_state_file(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    path = tmp_path / "runbook_state.json"

    try:
        runbook_state.init_state_file(tmp_path, ACCOUNT_ID, "2026-06-13", TRADE_DATE)
    except ValueError as exc:
        assert str(exc) == "context_mismatch_existing_runbook_state"
    else:
        raise AssertionError("expected context mismatch to raise")

    assert runbook_state.load_state(path) == state


def test_context_matches_state() -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)

    assert runbook_state.context_matches_state(state, ACCOUNT_ID, DATA_DATE, TRADE_DATE) is True
    assert runbook_state.context_matches_state(state, ACCOUNT_ID, "2026-06-13", TRADE_DATE) is False
    assert runbook_state.context_matches_state(state, "other_account", DATA_DATE, TRADE_DATE) is False


def test_validate_state_reports_schema_errors() -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    broken = replace(state, schema_version="bad", current_stage="Z", last_completed_step=99)

    errors = runbook_state.validate_state(broken)

    assert "schema_version must be runbook_state.v1" in errors
    assert "current_stage must be one of A/GATE1/B/C/GATE2/D/E/F" in errors
    assert "last_completed_step must be null or 0..21" in errors


def test_build_idempotency_key_includes_runbook_day_and_command_key() -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)

    key = runbook_state.build_idempotency_key(state, "status")

    assert key == "paper_pilot_202606_2026-06-12_2026-06-15:status"


def test_build_idempotency_key_includes_sorted_artifact_refs() -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)

    key = runbook_state.build_idempotency_key(
        state,
        "execution_commit",
        {
            "z_artifact": "outputs/z.json",
            "execution_preview_json": "outputs/preview.json",
        },
    )

    assert key == (
        "paper_pilot_202606_2026-06-12_2026-06-15:"
        "execution_commit:"
        "execution_preview_json=outputs_preview.json:"
        "z_artifact=outputs_z.json"
    )


def test_artifact_ref_canonicalization(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    absolute_inside = workspace / "outputs" / "preview.json"
    absolute_outside = tmp_path / "other" / "preview.json"

    assert runbook_state.canonicalize_artifact_ref(r"outputs\preview.json") == "outputs/preview.json"
    assert runbook_state.canonicalize_artifact_ref(r".\outputs\preview.json") == "outputs/preview.json"
    assert runbook_state.canonicalize_artifact_ref(str(absolute_inside), workspace) == "outputs/preview.json"
    try:
        runbook_state.canonicalize_artifact_ref(str(absolute_outside), workspace)
    except ValueError as exc:
        assert str(exc) == "artifact_ref_outside_workspace"
    else:
        raise AssertionError("expected outside workspace artifact to raise")


def test_idempotency_key_uses_canonical_artifact_refs(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)

    relative = runbook_state.build_idempotency_key(
        state,
        "execution_commit",
        {"execution_preview_json": r".\outputs\preview.json"},
        workspace,
    )
    absolute = runbook_state.build_idempotency_key(
        state,
        "execution_commit",
        {"execution_preview_json": str(workspace / "outputs" / "preview.json")},
        workspace,
    )

    assert relative == absolute
    assert relative.endswith("execution_preview_json=outputs_preview.json")


def test_record_idempotency_key_adds_record_without_mutating_original_state() -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)

    next_state = runbook_state.record_idempotency_key(
        state,
        "execution_commit",
        8,
        "B",
        {"execution_preview_json": "outputs/preview.json"},
    )
    key = runbook_state.build_idempotency_key(
        state,
        "execution_commit",
        {"execution_preview_json": "outputs/preview.json"},
    )

    assert state.idempotency_records == {}
    assert key in next_state.idempotency_records
    record = next_state.idempotency_records[key]
    assert record["command_key"] == "execution_commit"
    assert record["step_id"] == 8
    assert record["stage_id"] == "B"
    assert record["status"] == "RECORDED"


def test_duplicate_idempotency_key_is_detected() -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    artifact_refs = {"execution_preview_json": "outputs/preview.json"}
    state = runbook_state.record_idempotency_key(state, "execution_commit", 8, "B", artifact_refs)
    key = runbook_state.build_idempotency_key(state, "execution_commit", artifact_refs)

    assert runbook_state.has_idempotency_record(state, key) is True
    try:
        runbook_state.assert_not_duplicate(state, key)
    except ValueError as exc:
        assert str(exc) == "duplicate_idempotency_key"
    else:
        raise AssertionError("expected duplicate idempotency key to raise")

    try:
        runbook_state.record_idempotency_key(state, "execution_commit", 8, "B", artifact_refs)
    except ValueError as exc:
        assert str(exc) == "duplicate_idempotency_key"
    else:
        raise AssertionError("expected duplicate record to raise")


def test_idempotency_lifecycle_updates_existing_record() -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    refs = {"execution_preview_json": "outputs/preview.json"}
    state, key = runbook_state.reserve_idempotency(state, "execution_commit", 8, "B", refs)
    key = runbook_state.build_idempotency_key(state, "execution_commit", refs)

    running = runbook_state.mark_idempotency_running(state, key)
    passed = runbook_state.mark_idempotency_pass(running, key, result_ref="outputs/commit_report.json")
    failed = runbook_state.mark_idempotency_failed(running, key, reason="process_failed", result_ref="outputs/failed_report.json")
    blocked = runbook_state.mark_idempotency_blocked(state, key, reason="duplicate")

    assert state.idempotency_records[key]["status"] == "RESERVED"
    assert state.history[-1]["event_type"] == "idempotency_reserved"
    assert running.idempotency_records[key]["status"] == "RUNNING"
    assert running.history[-1]["event_type"] == "idempotency_running"
    assert passed.idempotency_records[key]["status"] == "PASS"
    assert passed.idempotency_records[key]["result_ref"] == "outputs/commit_report.json"
    assert passed.history[-1]["event_type"] == "idempotency_pass"
    assert failed.idempotency_records[key]["status"] == "FAILED"
    assert failed.idempotency_records[key]["notes"] == "process_failed"
    assert failed.history[-1]["event_type"] == "idempotency_failed"
    assert blocked.idempotency_records[key]["status"] == "BLOCKED"
    assert blocked.idempotency_records[key]["notes"] == "duplicate"
    assert blocked.history[-1]["event_type"] == "idempotency_blocked"


def test_idempotency_lifecycle_requires_existing_record() -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)

    try:
        runbook_state.update_idempotency_record(state, "missing", "PASS")
    except ValueError as exc:
        assert str(exc) == "missing_idempotency_key"
    else:
        raise AssertionError("expected missing idempotency record to raise")


def test_reserve_idempotency_blocks_existing_lifecycle_statuses() -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    refs = {"execution_preview_json": "outputs/preview.json"}
    reserved, key = runbook_state.reserve_idempotency(state, "execution_commit", 8, "B", refs)

    try:
        runbook_state.reserve_idempotency(reserved, "execution_commit", 8, "B", refs)
    except ValueError as exc:
        assert str(exc) == "idempotency_key_needs_recovery"
    else:
        raise AssertionError("expected RESERVED duplicate to require recovery")

    passed = runbook_state.mark_idempotency_pass(reserved, key)
    try:
        runbook_state.reserve_idempotency(passed, "execution_commit", 8, "B", refs)
    except ValueError as exc:
        assert str(exc) == "duplicate_idempotency_key"
    else:
        raise AssertionError("expected PASS duplicate to block")

    failed = runbook_state.mark_idempotency_failed(reserved, key, "process_failed")
    try:
        runbook_state.reserve_idempotency(failed, "execution_commit", 8, "B", refs)
    except ValueError as exc:
        assert str(exc) == "idempotency_key_failed_requires_manual_recovery"
    else:
        raise AssertionError("expected FAILED duplicate to require manual recovery")


def test_validate_state_checks_idempotency_record_shape() -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    malformed = replace(
        state,
        idempotency_records={
            "bad-key": {
                "idempotency_key": "other-key",
                "command_key": "execution_commit",
                "step_id": 99,
                "stage_id": "BAD",
                "status": "BAD",
                "artifact_refs": "not-a-dict",
            }
        },
    )

    errors = runbook_state.validate_state(malformed)

    assert "idempotency_records.bad-key.idempotency_key must match record key" in errors
    assert "idempotency_records.bad-key.step_id must be 0..21" in errors
    assert "idempotency_records.bad-key.stage_id is invalid" in errors
    assert "idempotency_records.bad-key.status is invalid" in errors
    assert "idempotency_records.bad-key.artifact_refs must be an object" in errors


def test_start_and_complete_stage_transitions() -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)

    running = runbook_state.start_stage(state, "A")
    completed = runbook_state.complete_stage(running, "A")

    assert running.current_stage == "A"
    assert running.current_status == "RUNNING"
    assert running.stage_status["A"] == "RUNNING"
    assert running.updated_at != state.updated_at
    assert running.history[-1]["event_type"] == "stage_started"
    assert running.history[-1]["status"] == "RUNNING"
    assert completed.current_status == "PASS"
    assert completed.stage_status["A"] == "PASS"
    assert completed.last_completed_stage == "A"
    assert completed.updated_at != running.updated_at
    assert completed.history[-1]["event_type"] == "stage_completed"
    assert completed.history[-1]["status"] == "PASS"
    assert runbook_state.validate_state(completed) == []


def test_fail_block_and_wait_transitions() -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)

    failed = runbook_state.fail_stage(state, "A", "stage_failed", {"detail": "boom"})
    blocked = runbook_state.block_stage(state, "B", "blocked_reason")
    waiting = runbook_state.wait_gate(state, "GATE1", "not_ready", "2026-06-29T22:00:00+09:00")

    assert failed.current_status == "FAILED"
    assert failed.stage_status["A"] == "FAILED"
    assert failed.last_error == {"stage_id": "A", "reason": "stage_failed", "error": {"detail": "boom"}}
    assert blocked.current_status == "BLOCKED"
    assert blocked.stage_status["B"] == "BLOCKED"
    assert blocked.last_error["reason"] == "blocked_reason"
    assert waiting.current_status == "WAIT"
    assert waiting.stage_status["GATE1"] == "WAIT"
    assert waiting.last_error["next_poll_time"] == "2026-06-29T22:00:00+09:00"
    assert failed.history[-1]["event_type"] == "stage_failed"
    assert blocked.history[-1]["event_type"] == "stage_blocked"
    assert waiting.history[-1]["event_type"] == "gate_wait"


def test_complete_step_and_record_artifact_merge_artifacts() -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)

    with_artifact = runbook_state.record_artifact(state, "daily_plan_json", "outputs/plan.json")
    completed = runbook_state.complete_step(
        with_artifact,
        7,
        "B",
        {"execution_preview_json": "outputs/preview.json"},
    )

    assert completed.last_completed_step == 7
    assert completed.current_stage == "B"
    assert completed.artifacts == {
        "daily_plan_json": "outputs/plan.json",
        "execution_preview_json": "outputs/preview.json",
    }
    assert with_artifact.history[-1]["event_type"] == "artifact_recorded"
    assert completed.history[-1]["event_type"] == "step_completed"


def test_transition_helpers_validate_stage_and_step() -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)

    for call in (
        lambda: runbook_state.start_stage(state, "BAD"),
        lambda: runbook_state.wait_gate(state, "A", "not_gate"),
        lambda: runbook_state.complete_step(state, 99, "A"),
    ):
        try:
            call()
        except ValueError:
            pass
        else:
            raise AssertionError("expected invalid transition input to raise")


def test_strict_once_command_idempotency_key_examples() -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)

    assert runbook_state.build_idempotency_key(
        state,
        "execution_commit",
        {"execution_preview_json": "outputs/execution_preview.json"},
    ) == (
        "paper_pilot_202606_2026-06-12_2026-06-15:"
        "execution_commit:"
        "execution_preview_json=outputs_execution_preview.json"
    )
    assert runbook_state.build_idempotency_key(
        state,
        "review_append",
        {"review_preview_json": "outputs/review_preview.json"},
    ) == (
        "paper_pilot_202606_2026-06-12_2026-06-15:"
        "review_append:"
        "review_preview_json=outputs_review_preview.json"
    )
    assert runbook_state.build_idempotency_key(
        state,
        "eod_commit",
        {"eod_dryrun_result": "outputs/eod_dryrun.json"},
    ) == (
        "paper_pilot_202606_2026-06-12_2026-06-15:"
        "eod_commit:"
        "eod_dryrun_result=outputs_eod_dryrun.json"
    )


def test_init_cli_creates_state_file(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts\\runbook_state.py",
            "init",
            "--workspace",
            str(tmp_path),
            "--account-id",
            ACCOUNT_ID,
            "--data-date",
            DATA_DATE,
            "--trade-date",
            TRADE_DATE,
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )

    assert completed.returncode == 0
    assert (tmp_path / "runbook_state.json").exists()
    assert json.loads(completed.stdout)["runner_result"] == "PASS"


def test_show_and_validate_cli(tmp_path: Path) -> None:
    runbook_state.init_state_file(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    root = Path(__file__).resolve().parents[1]

    show = subprocess.run(
        [sys.executable, "scripts\\runbook_state.py", "show", "--workspace", str(tmp_path)],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )
    validate = subprocess.run(
        [sys.executable, "scripts\\runbook_state.py", "validate", "--workspace", str(tmp_path)],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )

    assert show.returncode == 0
    assert json.loads(show.stdout)["runbook_day_id"] == "paper_pilot_202606_2026-06-12_2026-06-15"
    assert validate.returncode == 0
    assert json.loads(validate.stdout)["runner_result"] == "PASS"


def test_context_mismatch_init_cli_returns_nonzero_and_does_not_overwrite(tmp_path: Path) -> None:
    runbook_state.init_state_file(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts\\runbook_state.py",
            "init",
            "--workspace",
            str(tmp_path),
            "--account-id",
            ACCOUNT_ID,
            "--data-date",
            "2026-06-13",
            "--trade-date",
            TRADE_DATE,
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )

    assert completed.returncode == 1
    assert json.loads(completed.stdout) == {
        "runner_result": "BLOCKED",
        "reason": "context_mismatch_existing_runbook_state",
    }
    loaded = runbook_state.load_state(tmp_path / "runbook_state.json")
    assert loaded.frozen_context.data_date == DATA_DATE


def test_complete_stage_clears_active_last_error_but_keeps_history() -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    failed = runbook_state.fail_stage(state, "A", "stage_a_step_failed:data_prepare")

    assert failed.current_status == "FAILED"
    assert failed.last_error is not None
    assert failed.last_error["reason"] == "stage_a_step_failed:data_prepare"

    completed = runbook_state.complete_stage(failed, "A")

    assert completed.current_status == "PASS"
    assert completed.stage_status["A"] == "PASS"
    assert completed.last_completed_stage == "A"
    assert completed.last_error is None
    assert any(
        event["event_type"] == "stage_failed"
        and event["reason"] == "stage_a_step_failed:data_prepare"
        for event in completed.history
    )


def test_idempotency_cli_records_and_blocks_duplicate(tmp_path: Path) -> None:
    runbook_state.init_state_file(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    root = Path(__file__).resolve().parents[1]
    command = [
        sys.executable,
        "scripts\\runbook_state.py",
        "record-idempotency",
        "--workspace",
        str(tmp_path),
        "--command-key",
        "execution_commit",
        "--step-id",
        "8",
        "--stage-id",
        "B",
        "--artifact",
        "execution_preview_json=outputs\\preview.json",
    ]

    first = subprocess.run(command, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    second = subprocess.run(command, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)

    assert first.returncode == 0
    assert json.loads(first.stdout)["runner_result"] == "PASS"
    assert second.returncode == 1
    assert json.loads(second.stdout)["runner_result"] == "BLOCKED"
    assert json.loads(second.stdout)["reason"] == "duplicate_idempotency_key"


def test_idempotency_cli_check_reports_duplicate(tmp_path: Path) -> None:
    runbook_state.init_state_file(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    state = runbook_state.load_state(tmp_path / "runbook_state.json")
    state = runbook_state.record_idempotency_key(
        state,
        "eod_commit",
        17,
        "C",
        {"eod_dryrun_result": "outputs/eod_dryrun.json"},
    )
    runbook_state.save_state(state, tmp_path / "runbook_state.json")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts\\runbook_state.py",
            "check-idempotency",
            "--workspace",
            str(tmp_path),
            "--command-key",
            "eod_commit",
            "--artifact",
            "eod_dryrun_result=outputs\\eod_dryrun.json",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )

    assert completed.returncode == 1
    assert json.loads(completed.stdout)["runner_result"] == "BLOCKED"

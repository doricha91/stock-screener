from __future__ import annotations

import json
from pathlib import Path

from scripts import runbook_stage_b_verifier as verifier
from scripts import runbook_state


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


def test_stage_b_verifier_pins_artifact_to_existing_state(tmp_path: Path) -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
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

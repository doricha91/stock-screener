from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from core import runbook_retirement
from scripts import runbook_retirement as retirement_cli
from scripts import runbook_state


ACCOUNT_ID = "paper_pilot_202606"
DATA_DATE = "2026-07-06"
TRADE_DATE = "2026-07-07"
RUNBOOK_DAY_ID = f"{ACCOUNT_ID}_{DATA_DATE}_{TRADE_DATE}"
REASON = "Unused runbook created before initial-cash correction"


def _initial_state(workspace: Path) -> tuple[Path, runbook_state.RunbookState]:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    path = runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    runbook_state.save_state(state, path)
    return path, state


def _retire(workspace: Path, **overrides: object) -> dict[str, object]:
    values = {
        "account_id": ACCOUNT_ID,
        "data_date": DATA_DATE,
        "trade_date": TRADE_DATE,
        "runbook_day_id": RUNBOOK_DAY_ID,
        "reason": REASON,
        "confirm_paper_test": True,
        "confirm_retire_zero_progress": True,
    }
    values.update(overrides)
    return runbook_retirement.retire_runbook(workspace, **values)


def test_exact_zero_progress_retire_is_auditable_and_idempotent(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state_path, state = _initial_state(workspace)
    state_before = state_path.read_bytes()

    first = _retire(workspace)
    evidence_path = Path(first["evidence_path"])
    evidence_before = evidence_path.read_bytes()
    second = _retire(workspace)
    validation = runbook_retirement.validate_retirement_evidence(workspace, state_path, state)

    assert first["runner_result"] == "PASS" and first["already_retired"] is False
    assert second["runner_result"] == "PASS" and second["already_retired"] is True
    assert validation["valid"] is True
    assert evidence_path.read_bytes() == evidence_before
    assert state_path.read_bytes() == state_before
    payload = json.loads(evidence_before)
    assert payload["schema_version"] == runbook_retirement.SCHEMA_VERSION
    assert payload["state_sha256"] == runbook_retirement.sha256_file(state_path)
    assert payload["frozen_context"] == state.to_dict()["frozen_context"]
    assert payload["reason"] == REASON


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"confirm_paper_test": False}, "paper_test_confirmation_required"),
        ({"confirm_retire_zero_progress": False}, "retirement_confirmation_required"),
        ({"reason": ""}, "retirement_reason_required"),
        ({"account_id": "paper_other"}, "runbook_day_id_mismatch"),
        ({"data_date": "2026-07-05"}, "runbook_day_id_mismatch"),
        ({"runbook_day_id": "paper_pilot_202606_2026-07-06_2026-07-08"}, "runbook_day_id_mismatch"),
    ],
)
def test_retire_requires_exact_context_reason_and_confirmations(
    tmp_path: Path,
    overrides: dict[str, object],
    reason: str,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _initial_state(workspace)

    result = _retire(workspace, **overrides)

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == reason
    assert not runbook_retirement.retirement_path(workspace, RUNBOOK_DAY_ID).exists()


@pytest.mark.parametrize(
    "progress",
    ["step", "stage", "artifact", "command", "history", "recovery", "error", "workspace_evidence"],
)
def test_retire_rejects_any_progress_or_operational_evidence(tmp_path: Path, progress: str) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state_path, state = _initial_state(workspace)
    if progress == "step":
        state = replace(state, last_completed_step=1)
    elif progress == "stage":
        statuses = dict(state.stage_status)
        statuses["A"] = "PASS"
        state = replace(state, stage_status=statuses)
    elif progress == "artifact":
        state = replace(state, artifacts={"daily_plan_json": "artifact.json"})
    elif progress == "command":
        state = replace(state, idempotency_records={"command": {"status": "PASS"}})
    elif progress == "history":
        state = replace(state, history=[{"event": "started"}])
    elif progress == "recovery":
        state = replace(state, recovery_authorizations={"authorization": {}})
    elif progress == "error":
        state = replace(state, last_error={"reason": "failed"})
    else:
        evidence = workspace / "command_runs" / RUNBOOK_DAY_ID / "result.json"
        evidence.parent.mkdir(parents=True)
        evidence.write_text("{}", encoding="utf-8")
    if progress != "workspace_evidence":
        runbook_state.save_state(state, state_path)

    result = _retire(workspace)

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "runbook_not_zero_progress"
    assert not runbook_retirement.retirement_path(workspace, RUNBOOK_DAY_ID).exists()


def test_retirement_hash_or_context_mutation_fails_closed(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state_path, state = _initial_state(workspace)
    assert _retire(workspace)["runner_result"] == "PASS"
    evidence_path = runbook_retirement.retirement_path(workspace, RUNBOOK_DAY_ID)
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["frozen_context"]["trade_date"] = "2026-07-08"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    context_validation = runbook_retirement.validate_retirement_evidence(workspace, state_path, state)
    evidence["frozen_context"]["trade_date"] = TRADE_DATE
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    state_path.write_bytes(state_path.read_bytes() + b" ")
    hash_validation = runbook_retirement.validate_retirement_evidence(workspace, state_path, state)

    assert context_validation["valid"] is False
    assert "retirement_frozen_context_mismatch" in context_validation["blockers"]
    assert hash_validation["valid"] is False
    assert "retirement_state_sha256_mismatch" in hash_validation["blockers"]


@pytest.mark.parametrize("mutation", ["invalid_json", "missing_timestamp", "wrong_state_ref"])
def test_malformed_retirement_evidence_fails_closed(tmp_path: Path, mutation: str) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state_path, state = _initial_state(workspace)
    assert _retire(workspace)["runner_result"] == "PASS"
    evidence_path = runbook_retirement.retirement_path(workspace, RUNBOOK_DAY_ID)
    if mutation == "invalid_json":
        evidence_path.write_text("{invalid", encoding="utf-8")
    else:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        if mutation == "missing_timestamp":
            evidence.pop("created_at")
        else:
            evidence["state_ref"] = "runbook_states/other.json"
        evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    validation = runbook_retirement.validate_retirement_evidence(workspace, state_path, state)
    retry = _retire(workspace)

    assert validation["valid"] is False
    assert retry["runner_result"] == "BLOCKED"
    assert retry["reason"] == "existing_retirement_evidence_invalid"


def test_existing_retirement_with_different_reason_is_rejected(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _initial_state(workspace)
    assert _retire(workspace)["runner_result"] == "PASS"

    result = _retire(workspace, reason="different reason")

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "retirement_reason_mismatch"


def test_status_and_cli_are_readable_operator_contracts(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _initial_state(workspace)
    before = runbook_retirement.retirement_status(
        workspace,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        runbook_day_id=RUNBOOK_DAY_ID,
    )
    code = retirement_cli.main([
        "retire", "--workspace", str(workspace), "--account-id", ACCOUNT_ID,
        "--data-date", DATA_DATE, "--trade-date", TRADE_DATE,
        "--runbook-day-id", RUNBOOK_DAY_ID, "--reason", REASON,
        "--confirm-paper-test", "--confirm-retire-zero-progress",
    ])
    payload = json.loads(capsys.readouterr().out)
    after = runbook_retirement.retirement_status(
        workspace,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        runbook_day_id=RUNBOOK_DAY_ID,
    )

    assert before["retirement_status"] == "NOT_RETIRED" and before["retire_eligible"] is True
    assert code == 0 and payload["retired"] is True
    assert after["retirement_status"] == "RETIRED"

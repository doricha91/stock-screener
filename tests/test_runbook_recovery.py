from __future__ import annotations

import csv
import json
from dataclasses import replace
from pathlib import Path

import pytest

from core import runbook_day_rollover, runbook_recovery
from core.paper_execution_log import PAPER_EXECUTION_LOG_COLUMNS
from core.runbook_calendar import load_market_calendar
from core.runbook_day_prep import prepare_runbook_day_local, read_runbook_day_local
from scripts import runbook_recovery as recovery_cli
from scripts import runbook_state
from tests.test_runbook_day_rollover import _complete_state


ACCOUNT_ID = "paper_pilot_202606"
SOURCE_DATA_DATE = "2026-08-13"
SOURCE_TRADE_DATE = "2026-08-14"
SOURCE_ID = f"{ACCOUNT_ID}_{SOURCE_DATA_DATE}_{SOURCE_TRADE_DATE}"
RESTART_DATA_DATE = "2026-08-21"
RESTART_TRADE_DATE = "2026-08-24"
TARGET_ID = f"{ACCOUNT_ID}_{RESTART_DATA_DATE}_{RESTART_TRADE_DATE}"
REASON = "Stage A look-ahead contaminated; no real trades; gap accepted"
CONFIRMATIONS = {
    "confirm_paper_test": True,
    "confirm_contaminated_incomplete": True,
    "confirm_no_real_trades": True,
    "confirm_gap_without_backfill": True,
}


@pytest.fixture(autouse=True)
def _patch_account_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_paths(account_id: str, create: bool = False) -> object:
        account_root = tmp_path / "outputs" / "paper_accounts" / account_id
        if create:
            account_root.mkdir(parents=True, exist_ok=True)
        return type(
            "Paths",
            (),
            {
                "root": account_root,
                "execution_log_path": account_root / "paper_execution_log.csv",
            },
        )()

    monkeypatch.setattr(runbook_day_rollover, "build_paper_account_paths", fake_paths)
    monkeypatch.setattr(runbook_recovery, "build_paper_account_paths", fake_paths)


def _seed_incident(tmp_path: Path) -> tuple[Path, Path, Path]:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _complete_state(workspace, "2026-08-12", "2026-08-13")
    state = runbook_state.create_initial_state(ACCOUNT_ID, SOURCE_DATA_DATE, SOURCE_TRADE_DATE)
    statuses = dict(state.stage_status)
    statuses["A"] = "PASS"
    artifact = workspace / "artifacts" / SOURCE_ID / "stage_a" / "daily_action_plan_20260814.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text('{"contaminated": true}\n', encoding="utf-8")
    state = replace(
        state,
        current_stage="A",
        current_status="PASS",
        last_completed_step=5,
        last_completed_stage="A",
        stage_status=statuses,
        artifacts={"daily_plan_json": artifact.relative_to(workspace).as_posix()},
        history=[{"event_type": "stage_completed", "stage_id": "A", "status": "PASS"}],
    )
    state_path = runbook_state.get_state_path_for_context(
        workspace, ACCOUNT_ID, SOURCE_DATA_DATE, SOURCE_TRADE_DATE
    )
    runbook_state.save_state(state, state_path)
    return workspace, state_path, artifact


def _arguments(workspace: Path, **overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "workspace": workspace,
        "account_id": ACCOUNT_ID,
        "source_runbook_day_id": SOURCE_ID,
        "restart_data_date": RESTART_DATA_DATE,
        "restart_trade_date": RESTART_TRADE_DATE,
        "reason": REASON,
        "calendar": load_market_calendar(),
        **CONFIRMATIONS,
    }
    values.update(overrides)
    return values


def _hash_tree(workspace: Path, state_path: Path, artifact: Path) -> dict[str, str]:
    ledger = workspace.parent / "outputs" / "paper_accounts" / ACCOUNT_ID / "paper_execution_log.csv"
    return {
        "state": runbook_recovery.sha256_file(state_path),
        "artifact": runbook_recovery.sha256_file(artifact),
        "ledger": runbook_recovery.sha256_file(ledger),
    }


def _mark_recovery_target_standard_completed(
    workspace: Path,
    target_path: Path,
    target: runbook_state.RunbookState,
    monkeypatch: pytest.MonkeyPatch,
) -> runbook_state.RunbookState:
    completed = replace(
        target,
        current_stage="F",
        current_status="PASS",
        last_completed_step=21,
        last_completed_stage="F",
        stage_status={stage: "PASS" for stage in runbook_state.STAGE_IDS},
    )
    runbook_state.save_state(completed, target_path)
    original = runbook_day_rollover._is_standard_completed

    def classify_standard(workspace_arg: Path, state: runbook_state.RunbookState) -> bool:
        return state.runbook_day_id == TARGET_ID or original(workspace_arg, state)

    monkeypatch.setattr(runbook_day_rollover, "_is_standard_completed", classify_standard)
    return completed


def test_current_incident_blocks_rollover_and_eligible_preview_is_read_only(tmp_path: Path) -> None:
    workspace, state_path, artifact = _seed_incident(tmp_path)
    before = _hash_tree(workspace, state_path, artifact)

    rollover = runbook_day_rollover.preview_rollover(
        workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True
    )
    preview = runbook_recovery.preview_recovery(**_arguments(workspace))

    assert rollover["reason"] == "active_runbook_day_exists"
    source = runbook_state.load_state(state_path)
    retirement = runbook_recovery.runbook_retirement.assess_zero_progress(
        workspace, state_path, source
    )
    assert retirement["eligible"] is False
    assert preview["runner_result"] == "PASS" and preview["eligible"] is True
    assert preview["restart"] == {
        "data_date": RESTART_DATA_DATE,
        "trade_date": RESTART_TRADE_DATE,
        "runbook_day_id": TARGET_ID,
    }
    assert preview["no_trade_interval"]["trading_dates"] == [
        "2026-08-14", "2026-08-17", "2026-08-18",
        "2026-08-19", "2026-08-20", "2026-08-21",
    ]
    assert preview["no_trade_interval"]["execution_count"] == 0
    assert not runbook_recovery.recovery_path(workspace, SOURCE_ID).exists()
    assert _hash_tree(workspace, state_path, artifact) == before


def test_authorize_creates_immutable_sidecar_and_exact_recovery_rollover(tmp_path: Path) -> None:
    workspace, state_path, artifact = _seed_incident(tmp_path)
    before = _hash_tree(workspace, state_path, artifact)

    result = runbook_recovery.authorize_recovery(**_arguments(workspace))
    evidence_path = runbook_recovery.recovery_path(workspace, SOURCE_ID)
    evidence_before = evidence_path.read_bytes()
    source = runbook_state.load_state(state_path)
    validation = runbook_recovery.validate_recovery_evidence(
        workspace, state_path, source, load_market_calendar()
    )
    classification = runbook_day_rollover.classify_account_runbooks(workspace, ACCOUNT_ID)
    rollover = runbook_day_rollover.preview_rollover(
        workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True
    )

    assert result["runner_result"] == "PASS" and result["authorized"] is True
    assert evidence_path.read_bytes() == evidence_before
    assert validation["valid"] is True and validation["consumed"] is False
    assert classification["classifications"][-1]["classification"] == "RECOVERY_EXCLUDED"
    assert rollover["rollover_mode"] == "RECOVERY"
    assert rollover["next_data_date"] == RESTART_DATA_DATE
    assert rollover["next_trade_date"] == RESTART_TRADE_DATE
    assert rollover["previous_runbook_day_id"] == f"{ACCOUNT_ID}_2026-08-12_2026-08-13"
    assert _hash_tree(workspace, state_path, artifact) == before


@pytest.mark.parametrize("missing", list(CONFIRMATIONS))
def test_missing_confirmation_blocks_without_sidecar(tmp_path: Path, missing: str) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    result = runbook_recovery.authorize_recovery(
        **_arguments(workspace, **{missing: False})
    )
    assert result["runner_result"] == "BLOCKED"
    assert not runbook_recovery.recovery_path(workspace, SOURCE_ID).exists()


def test_duplicate_authorization_is_blocked_without_overwrite(tmp_path: Path) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    assert runbook_recovery.authorize_recovery(**_arguments(workspace))["runner_result"] == "PASS"
    path = runbook_recovery.recovery_path(workspace, SOURCE_ID)
    before = path.read_bytes()

    duplicate = runbook_recovery.authorize_recovery(**_arguments(workspace))
    status = runbook_recovery.recovery_status(
        workspace,
        account_id=ACCOUNT_ID,
        source_runbook_day_id=SOURCE_ID,
        calendar=load_market_calendar(),
    )

    assert duplicate["runner_result"] == "BLOCKED"
    assert duplicate["reason"] == "recovery_authorization_already_exists"
    assert path.read_bytes() == before
    assert status["runner_result"] == "PASS" and status["sidecar_valid"] is True


def test_source_hash_mutation_invalidates_exclusion_and_blocks_rollover(tmp_path: Path) -> None:
    workspace, state_path, _ = _seed_incident(tmp_path)
    assert runbook_recovery.authorize_recovery(**_arguments(workspace))["runner_result"] == "PASS"
    state_path.write_bytes(state_path.read_bytes() + b" ")

    classified = runbook_day_rollover.classify_account_runbooks(workspace, ACCOUNT_ID)
    rollover = runbook_day_rollover.preview_rollover(
        workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True
    )

    source_item = next(item for item in classified["classifications"] if item["runbook_day_id"] == SOURCE_ID)
    assert source_item["classification"] == "ACTIVE_INCOMPLETE"
    assert "recovery_source_state_sha256_mismatch" in source_item["blockers"]
    assert rollover["reason"] == "active_runbook_day_exists"


def test_execution_contradiction_before_and_after_authorization_fails_closed(tmp_path: Path) -> None:
    workspace, state_path, _ = _seed_incident(tmp_path)
    ledger = workspace.parent / "outputs" / "paper_accounts" / ACCOUNT_ID / "paper_execution_log.csv"
    with ledger.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_EXECUTION_LOG_COLUMNS)
        writer.writerow({"date": "2026-08-20", "symbol": "AAPL", "status": "COMMITTED"})
    preview = runbook_recovery.preview_recovery(**_arguments(workspace))
    assert preview["runner_result"] == "BLOCKED"
    assert any(item.startswith("execution_gap_not_empty") for item in preview["blockers"])

    rows = list(csv.DictReader(ledger.open("r", encoding="utf-8")))
    with ledger.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_EXECUTION_LOG_COLUMNS)
        writer.writeheader()
        writer.writerows(row for row in rows if row["date"] != "2026-08-20")
    assert runbook_recovery.authorize_recovery(**_arguments(workspace))["runner_result"] == "PASS"
    with ledger.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_EXECUTION_LOG_COLUMNS)
        writer.writerow({"date": "2026-08-20", "symbol": "AAPL", "status": "COMMITTED"})
    source = runbook_state.load_state(state_path)
    validation = runbook_recovery.validate_recovery_evidence(
        workspace, state_path, source, load_market_calendar()
    )
    assert validation["valid"] is False
    assert "recovery_execution_contradiction" in validation["blockers"]


def test_multiple_active_and_missing_completed_block(tmp_path: Path) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    extra = runbook_state.create_initial_state(ACCOUNT_ID, "2026-08-18", "2026-08-19")
    runbook_state.save_state(
        extra,
        runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, "2026-08-18", "2026-08-19"),
    )
    multiple = runbook_recovery.preview_recovery(**_arguments(workspace))
    assert multiple["runner_result"] == "BLOCKED"
    assert "active_runbook_day_count_must_equal_one" in multiple["blockers"]

    empty_workspace = tmp_path / "empty_workspace"
    empty_workspace.mkdir()
    source = runbook_state.create_initial_state(ACCOUNT_ID, SOURCE_DATA_DATE, SOURCE_TRADE_DATE)
    source = replace(source, current_status="PASS", last_completed_step=5, last_completed_stage="A")
    runbook_state.save_state(
        source,
        runbook_state.get_state_path_for_context(
            empty_workspace, ACCOUNT_ID, SOURCE_DATA_DATE, SOURCE_TRADE_DATE
        ),
    )
    missing = runbook_recovery.preview_recovery(**_arguments(empty_workspace))
    assert missing["runner_result"] == "BLOCKED"
    assert "completed_runbook_day_not_found" in missing["blockers"]


def test_context_account_mismatch_and_ambiguous_latest_completed_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    wrong_account = runbook_recovery.preview_recovery(
        **_arguments(workspace, account_id="paper_other")
    )
    wrong_id = runbook_recovery.preview_recovery(
        **_arguments(workspace, source_runbook_day_id=f"{ACCOUNT_ID}_2026-08-12_2026-08-14")
    )
    assert wrong_account["runner_result"] == "BLOCKED"
    assert "source_runbook_not_found" in wrong_account["blockers"]
    assert wrong_id["runner_result"] == "BLOCKED"
    assert "source_runbook_not_found" in wrong_id["blockers"]

    duplicate = runbook_state.create_initial_state(ACCOUNT_ID, "2026-08-11", "2026-08-13")
    duplicate_path = runbook_state.get_state_path_for_context(
        workspace, ACCOUNT_ID, "2026-08-11", "2026-08-13"
    )
    runbook_state.save_state(duplicate, duplicate_path)
    original = runbook_recovery._raw_classification

    def classify(workspace_arg: Path, record: object) -> str:
        if record.state.runbook_day_id == duplicate.runbook_day_id:
            return "STANDARD_COMPLETED"
        return original(workspace_arg, record)

    monkeypatch.setattr(runbook_recovery, "_raw_classification", classify)
    ambiguous = runbook_recovery.preview_recovery(**_arguments(workspace))
    assert ambiguous["runner_result"] == "BLOCKED"
    assert "latest_completed_runbook_day_ambiguous" in ambiguous["blockers"]


@pytest.mark.parametrize(
    ("data_date", "trade_date", "blocker"),
    [
        ("2026-08-22", "2026-08-24", "restart_data_date_not_trading_day"),
        ("2026-08-21", "2026-08-25", "restart_trade_date_not_next_trading_day"),
        ("2028-01-03", "2028-01-04", "calendar_coverage_exceeded"),
    ],
)
def test_calendar_validation_blocks_invalid_pairs(
    tmp_path: Path, data_date: str, trade_date: str, blocker: str
) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    result = runbook_recovery.preview_recovery(
        **_arguments(
            workspace,
            restart_data_date=data_date,
            restart_trade_date=trade_date,
        )
    )
    assert result["runner_result"] == "BLOCKED"
    assert any(blocker in item for item in result["blockers"])


def test_target_conflict_blocks_authorization(tmp_path: Path) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    conflict = workspace / "artifacts" / TARGET_ID / "unexpected.json"
    conflict.parent.mkdir(parents=True)
    conflict.write_text("{}", encoding="utf-8")
    result = runbook_recovery.authorize_recovery(**_arguments(workspace))
    assert result["runner_result"] == "BLOCKED"
    assert "recovery_target_already_exists" in result["blockers"]


def test_sidecar_pair_cannot_be_overridden_and_calendar_evidence_is_fail_closed(tmp_path: Path) -> None:
    workspace, state_path, _ = _seed_incident(tmp_path)
    assert runbook_recovery.authorize_recovery(**_arguments(workspace))["runner_result"] == "PASS"
    different = runbook_recovery.preview_recovery(
        **_arguments(
            workspace,
            restart_data_date="2026-08-20",
            restart_trade_date="2026-08-21",
        )
    )
    assert different["runner_result"] == "BLOCKED"
    assert different["reason"] == "recovery_authorization_already_exists"

    path = runbook_recovery.recovery_path(workspace, SOURCE_ID)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["calendar"]["calendar_sha256"] = "0" * 64
    path.write_text(json.dumps(payload), encoding="utf-8")
    source = runbook_state.load_state(state_path)
    validation = runbook_recovery.validate_recovery_evidence(
        workspace, state_path, source, load_market_calendar()
    )
    assert validation["valid"] is False
    assert "recovery_calendar_sha256_mismatch" in validation["blockers"]
    rollover = runbook_day_rollover.preview_rollover(
        workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True
    )
    assert rollover["reason"] == "active_runbook_day_exists"


@pytest.mark.parametrize("mutation", ["malformed", "account", "context", "disposition"])
def test_malformed_or_mismatched_sidecar_restores_active_blocker(
    tmp_path: Path, mutation: str
) -> None:
    workspace, state_path, _ = _seed_incident(tmp_path)
    assert runbook_recovery.authorize_recovery(**_arguments(workspace))["runner_result"] == "PASS"
    path = runbook_recovery.recovery_path(workspace, SOURCE_ID)
    if mutation == "malformed":
        path.write_text("{invalid", encoding="utf-8")
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if mutation == "account":
            payload["account_id"] = "paper_other"
        elif mutation == "context":
            payload["source_frozen_context"]["trade_date"] = "2026-08-15"
        else:
            payload["disposition"] = "STANDARD_COMPLETED"
        path.write_text(json.dumps(payload), encoding="utf-8")
    source = runbook_state.load_state(state_path)
    validation = runbook_recovery.validate_recovery_evidence(
        workspace, state_path, source, load_market_calendar()
    )
    assert validation["valid"] is False
    classified = runbook_day_rollover.classify_account_runbooks(workspace, ACCOUNT_ID)
    source_item = next(item for item in classified["classifications"] if item["runbook_day_id"] == SOURCE_ID)
    assert source_item["classification"] == "ACTIVE_INCOMPLETE"
    rollover = runbook_day_rollover.preview_rollover(
        workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True
    )
    assert rollover["reason"] == "active_runbook_day_exists"


def test_initialization_requires_exact_authorized_target_and_reapplies_active_guard(tmp_path: Path) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    with pytest.raises(ValueError, match="active_runbook_day_exists"):
        runbook_state.init_state_file_for_context(
            workspace, ACCOUNT_ID, RESTART_DATA_DATE, RESTART_TRADE_DATE
        )
    assert runbook_recovery.authorize_recovery(**_arguments(workspace))["runner_result"] == "PASS"
    with pytest.raises(ValueError, match="recovery_target_mismatch"):
        runbook_state.init_state_file_for_context(
            workspace, ACCOUNT_ID, "2026-08-20", "2026-08-21"
        )

    created, target_path, target = runbook_state.init_state_file_for_context(
        workspace, ACCOUNT_ID, RESTART_DATA_DATE, RESTART_TRADE_DATE
    )
    assert created == "CREATED" and target.runbook_day_id == TARGET_ID
    rollover = runbook_day_rollover.preview_rollover(
        workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True
    )
    assert rollover["reason"] == "active_runbook_day_exists"
    assert f"active_runbook_day:{TARGET_ID}" in rollover["blockers"]
    with pytest.raises(ValueError, match="active_runbook_day_exists"):
        runbook_state.init_state_file_for_context(
            workspace, ACCOUNT_ID, "2026-08-24", "2026-08-25"
        )
    assert target_path.exists()


def test_prep_consumes_only_the_authorized_exact_pair(tmp_path: Path) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    assert runbook_recovery.authorize_recovery(**_arguments(workspace))["runner_result"] == "PASS"
    wrapper_dir = tmp_path / "wrappers"
    wrapper_dir.mkdir()
    account_local = wrapper_dir / "_account.local.cmd"
    account_local.write_text(
        f'@echo off\nset "ACCOUNT_ID={ACCOUNT_ID}"\nset "ACCOUNT_MODE=PAPER"\nexit /b 0\n',
        encoding="ascii",
    )
    day_local = wrapper_dir / "_runbook_day.local.cmd"
    result = prepare_runbook_day_local(
        workspace,
        ACCOUNT_ID,
        account_local,
        day_local,
        load_market_calendar(),
        write_env_local=True,
        confirm_paper_test=True,
    )
    assert result["runner_result"] == "PASS"
    assert read_runbook_day_local(day_local, account_id=ACCOUNT_ID) == {
        "DATA_DATE": RESTART_DATA_DATE,
        "TRADE_DATE": RESTART_TRADE_DATE,
        "RUNBOOK_DAY_ID": TARGET_ID,
    }


def test_target_standard_completion_returns_to_normal_sequential_rollover(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    assert runbook_recovery.authorize_recovery(**_arguments(workspace))["runner_result"] == "PASS"
    _, target_path, target = runbook_state.init_state_file_for_context(
        workspace, ACCOUNT_ID, RESTART_DATA_DATE, RESTART_TRADE_DATE
    )
    _mark_recovery_target_standard_completed(workspace, target_path, target, monkeypatch)
    result = runbook_day_rollover.preview_rollover(
        workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True
    )
    assert result["runner_result"] == "PASS"
    assert result.get("rollover_mode") != "RECOVERY"
    assert result["previous_runbook_day_id"] == TARGET_ID
    assert result["next_data_date"] == "2026-08-24"
    assert result["next_trade_date"] == "2026-08-25"


def test_consumed_recovery_full_lifecycle_returns_to_exact_normal_initialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    assert runbook_recovery.authorize_recovery(**_arguments(workspace))["runner_result"] == "PASS"
    sidecar_path = runbook_recovery.recovery_path(workspace, SOURCE_ID)
    sidecar_before = sidecar_path.read_bytes()

    created, target_path, target = runbook_state.init_state_file_for_context(
        workspace, ACCOUNT_ID, RESTART_DATA_DATE, RESTART_TRADE_DATE
    )
    assert created == "CREATED" and target.runbook_day_id == TARGET_ID
    with pytest.raises(ValueError, match="active_runbook_day_exists"):
        runbook_state.init_state_file_for_context(
            workspace, ACCOUNT_ID, "2026-08-24", "2026-08-25"
        )

    _mark_recovery_target_standard_completed(workspace, target_path, target, monkeypatch)
    rollover = runbook_day_rollover.preview_rollover(
        workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True
    )
    assert rollover["runner_result"] == "PASS"
    assert rollover.get("rollover_mode") != "RECOVERY"
    assert rollover["next_runbook_day_id"] == f"{ACCOUNT_ID}_2026-08-24_2026-08-25"

    for data_date, trade_date in (
        ("2026-08-24", "2026-08-26"),
        ("2026-08-25", "2026-08-26"),
        ("2026-08-30", "2026-08-31"),
    ):
        with pytest.raises(ValueError, match="recovery_target_mismatch"):
            runbook_state.init_state_file_for_context(
                workspace, ACCOUNT_ID, data_date, trade_date
            )

    existing, existing_path, existing_target = runbook_state.init_state_file_for_context(
        workspace, ACCOUNT_ID, RESTART_DATA_DATE, RESTART_TRADE_DATE
    )
    assert existing == "EXISTING"
    assert existing_path == target_path
    assert existing_target.runbook_day_id == TARGET_ID

    def fail_if_default_calendar_is_reloaded() -> object:
        raise AssertionError("caller calendar was not propagated")

    monkeypatch.setattr(runbook_recovery, "default_calendar", fail_if_default_calendar_is_reloaded)
    normal_created, normal_path, normal_state = runbook_state.init_state_file_for_context(
        workspace, ACCOUNT_ID, "2026-08-24", "2026-08-25"
    )
    assert normal_created == "CREATED"
    assert normal_state.runbook_day_id == f"{ACCOUNT_ID}_2026-08-24_2026-08-25"
    assert normal_path.exists()
    assert sidecar_path.read_bytes() == sidecar_before

    with pytest.raises(ValueError, match="active_runbook_day_exists"):
        runbook_state.init_state_file_for_context(
            workspace, ACCOUNT_ID, "2026-08-25", "2026-08-26"
        )


def test_invalid_consumed_sidecar_keeps_normal_initialization_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    assert runbook_recovery.authorize_recovery(**_arguments(workspace))["runner_result"] == "PASS"
    _, target_path, target = runbook_state.init_state_file_for_context(
        workspace, ACCOUNT_ID, RESTART_DATA_DATE, RESTART_TRADE_DATE
    )
    _mark_recovery_target_standard_completed(workspace, target_path, target, monkeypatch)
    sidecar_path = runbook_recovery.recovery_path(workspace, SOURCE_ID)
    payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
    payload["calendar"]["calendar_sha256"] = "0" * 64
    sidecar_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="active_runbook_day_exists"):
        runbook_state.init_state_file_for_context(
            workspace, ACCOUNT_ID, "2026-08-24", "2026-08-25"
        )


def test_no_sidecar_normal_preview_and_exact_initialization_are_preserved(tmp_path: Path) -> None:
    workspace = tmp_path / "normal_workspace"
    workspace.mkdir()
    _complete_state(workspace, "2026-08-12", "2026-08-13")

    rollover = runbook_day_rollover.preview_rollover(
        workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True
    )
    assert rollover["runner_result"] == "PASS"
    assert rollover.get("rollover_mode") != "RECOVERY"
    assert rollover["next_data_date"] == "2026-08-13"
    assert rollover["next_trade_date"] == "2026-08-14"

    created, _, state = runbook_state.init_state_file_for_context(
        workspace, ACCOUNT_ID, "2026-08-13", "2026-08-14"
    )
    assert created == "CREATED"
    assert state.runbook_day_id == f"{ACCOUNT_ID}_2026-08-13_2026-08-14"


def test_cli_preview_and_status_are_readable(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    common = [
        "--workspace", str(workspace), "--account-id", ACCOUNT_ID,
        "--runbook-day-id", SOURCE_ID,
    ]
    preview_code = recovery_cli.main([
        "preview", *common,
        "--restart-data-date", RESTART_DATA_DATE,
        "--restart-trade-date", RESTART_TRADE_DATE,
        "--reason", REASON,
        "--confirm-paper-test", "--confirm-contaminated-incomplete",
        "--confirm-no-real-trades", "--confirm-gap-without-backfill",
    ])
    preview = json.loads(capsys.readouterr().out)
    status_code = recovery_cli.main(["status", *common])
    status = json.loads(capsys.readouterr().out)
    assert preview_code == 0 and preview["eligible"] is True
    assert status_code == 0 and status["current_classification"] == "ACTIVE_INCOMPLETE"
    assert status["sidecar_exists"] is False

    authorize_code = recovery_cli.main([
        "authorize", *common,
        "--restart-data-date", RESTART_DATA_DATE,
        "--restart-trade-date", RESTART_TRADE_DATE,
        "--reason", REASON,
        "--confirm-paper-test", "--confirm-contaminated-incomplete",
        "--confirm-no-real-trades", "--confirm-gap-without-backfill",
    ])
    authorized = json.loads(capsys.readouterr().out)
    assert authorize_code == 0 and authorized["authorized"] is True

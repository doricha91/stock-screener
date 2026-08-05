from __future__ import annotations

import json
import csv
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from core import runbook_day_rollover as rollover_core
from core.paper_account_snapshot import PAPER_ACCOUNT_SNAPSHOT_COLUMNS
from core.paper_execution_intent import build_execution_intent
from core.paper_execution_log import PAPER_EXECUTION_LOG_COLUMNS
from core.paper_manual_review_log_template import PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS
from core.paper_position_snapshot import PAPER_POSITION_SNAPSHOT_COLUMNS
from core.runbook_calendar import CalendarCoverageError, load_market_calendar
from core.runbook_day_rollover import preview_rollover
from scripts import runbook_day_rollover as runbook_day_rollover_cli
from scripts import runbook_completion_evidence
from scripts import runbook_stage_e_evidence
from scripts import runbook_state


ACCOUNT_ID = "paper_pilot_202606"


@pytest.fixture(autouse=True)
def _patch_account_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    account_root = tmp_path / "outputs" / "paper_accounts" / ACCOUNT_ID
    monkeypatch.setattr(
        rollover_core,
        "build_paper_account_paths",
        lambda account_id, create=False: type("Paths", (), {"root": account_root})(),
    )


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _command_result(
    state: runbook_state.RunbookState,
    command_key: str,
    step_id: int,
    raw_payload: dict[str, object],
    *,
    stage_id: str = "F",
) -> dict[str, object]:
    timestamp = "2026-07-02T18:00:00+09:00"
    return {
        "schema_version": "runbook_command_result.v1",
        "runner_result": "PASS",
        "created_at": timestamp,
        "updated_at": timestamp,
        "runbook_day_id": state.runbook_day_id,
        "frozen_context": {
            "account_id": state.frozen_context.account_id,
            "data_date": state.frozen_context.data_date,
            "trade_date": state.frozen_context.trade_date,
        },
        "stage_id": stage_id,
        "step_id": step_id,
        "command_key": command_key,
        "command_type": "NOTION_WRITE",
        "process": {"executed": True, "exit_code": 0, "duration_ms": 1},
        "outputs": {"json_ref": None, "txt_ref": None, "log_ref": None, "artifact_refs": {}},
        "summary": {"title": command_key, "message": "PASS", "warnings": [], "blockers": []},
        "raw_payload": raw_payload,
    }


def _complete_state(workspace: Path, data_date: str, trade_date: str) -> Path:
    state = runbook_state.create_initial_state(ACCOUNT_ID, data_date, trade_date)
    account_root = workspace.parent / "outputs" / "paper_accounts" / ACCOUNT_ID
    snapshot_path = account_root / "paper_account_snapshot.csv"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    (account_root / "reviews").mkdir(parents=True, exist_ok=True)
    with snapshot_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_ACCOUNT_SNAPSHOT_COLUMNS)
        writer.writeheader()
        writer.writerow({"account_id": ACCOUNT_ID, "snapshot_date": trade_date, "total_equity_market_value": 100000})
    with (account_root / "paper_position_snapshot.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_POSITION_SNAPSHOT_COLUMNS)
        writer.writeheader()
        writer.writerow({"account_id": ACCOUNT_ID, "snapshot_date": trade_date, "symbol": "AAPL", "shares": 1})
    with (account_root / "paper_execution_log.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_EXECUTION_LOG_COLUMNS)
        writer.writeheader()
        writer.writerow({"date": trade_date, "symbol": "AAPL", "status": "COMMITTED"})
    with (account_root / "reviews" / "paper_manual_review_log.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS)
        writer.writeheader()
        writer.writerow({"review_date": trade_date, "symbol": "AAPL", "question_id": "Q1", "question_text": "review", "is_actionable": "false", "manual_answer": "done", "review_status": "reviewed", "follow_up_needed": "false"})
    items = [{"symbol": "AAPL", "action": "BUY", "quantity": 1}]
    plan_payload = {
        "schema_version": "paper_daily_plan.v1", "account_id": ACCOUNT_ID,
        "data_date": data_date, "trade_date": trade_date, "plan_date": trade_date,
        "run_mode": "official", "official_run": True,
        "generated_at": f"{data_date}T18:00:00+09:00", "fingerprints": {},
        "items": items, "execution_intent": build_execution_intent(items),
    }
    plan_path = _write_json(workspace / "artifacts" / state.runbook_day_id / "daily_plan.json", plan_payload)
    _write_json(account_root / f"daily_action_plan_{trade_date.replace('-', '')}.json", plan_payload)
    state = runbook_state.record_artifact(state, "daily_plan_json", str(plan_path), workspace)
    benchmark_source = _write_json(
        account_root / "reports" / "paper_benchmark_comparison.json",
        {"account_id": ACCOUNT_ID, "latest_snapshot_date": trade_date, "run_mode": "exploratory"},
    )
    benchmark_artifact = _write_json(
        workspace / "artifacts" / state.runbook_day_id / "stage_f" / "paper_benchmark_comparison.json",
        {"account_id": ACCOUNT_ID, "latest_snapshot_date": trade_date, "run_mode": "exploratory"},
    )
    account_notion = _write_json(
        workspace / "command_runs" / state.runbook_day_id / "account_snapshot_notion.json",
        _command_result(
            state,
            "account_snapshot_notion_upsert",
            20,
            {
                "json": [{
                    "account_id": ACCOUNT_ID,
                    "external_key": f"account_snapshot:{ACCOUNT_ID}:{trade_date}",
                    "action": "created",
                    "source_path": str(snapshot_path),
                    "failed_count": 0,
                }]
            },
        ),
    )
    benchmark_notion = _write_json(
        workspace / "command_runs" / state.runbook_day_id / "benchmark_notion.json",
        _command_result(
            state,
            "benchmark_report_notion_upsert",
            21,
            {
                "json": [{
                    "account_id": ACCOUNT_ID,
                    "external_key": f"benchmark:{ACCOUNT_ID}:{trade_date}:exploratory",
                    "action": "created",
                    "source_path": str(benchmark_source),
                    "failed_count": 0,
                }]
            },
        ),
    )
    eod_commit = _write_json(
        workspace / "command_runs" / state.runbook_day_id / "eod_commit.json",
        {
            "runner_result": "PASS",
            "status": "COMMITTED",
            "mode": "commit",
            "account_id": ACCOUNT_ID,
            "date": trade_date,
            "trade_date": trade_date,
            "failed_count": 0,
            "blocked_count": 0,
            "current_state_written": True,
            "account_snapshot_written": True,
            "position_snapshot_written": True,
            "market_valuation_status": "success",
        },
    )
    state = runbook_state.record_artifact(state, "eod_commit_report_json", str(eod_commit), workspace)
    state = runbook_state.complete_stage(state, "D")
    manifest = runbook_completion_evidence.build_runbook_completion_manifest(workspace, state, account_root)
    completion_manifest = _write_json(
        workspace / "completion_manifests" / f"{state.runbook_day_id}.json", manifest
    )
    final_status = _write_json(
        workspace / "command_runs" / state.runbook_day_id / "final_status.json",
        _command_result(
            state,
            "final_status",
            18,
            {
                "schema_version": "mfu_oper9_daily_ops_status.v1",
                "overall_status": "PASS",
                "account_id": ACCOUNT_ID,
                "data_date": data_date,
                "trade_date": trade_date,
                "workflow_status": "REVIEW_DONE",
                "completion_mode": "STANDARD",
                "completion_proof": None,
                "completion_manifest": manifest,
                "read_only": True,
                "write_executed": False,
                "operation_write_executed": False,
                "notion_api_called": False,
                "notion_live_read_enabled": False,
                "notion_live_read_called": False,
                "commit_append_executed": False,
                "blockers": [],
                "warnings": [],
                "next_command": None,
                "next_action": None,
                "summary": {"terminal": True, "needs_attention": False},
                "stage_counts": {},
                "stages": [],
                "operator_summary": {},
            },
            stage_id="E",
        ),
    )
    state = replace(
        state,
        current_stage="F",
        current_status="PASS",
        last_completed_step=21,
        last_completed_stage="F",
        stage_status={stage_id: "PASS" for stage_id in runbook_state.STAGE_IDS},
        artifacts={
            "daily_plan_json": str(plan_path.relative_to(workspace)),
            "eod_commit_report_json": str(eod_commit.relative_to(workspace)),
            "completion_manifest_json": str(completion_manifest.relative_to(workspace)),
            "final_status_report_json": str(final_status.relative_to(workspace)),
            "benchmark_report_json": str(benchmark_artifact.relative_to(workspace)),
            "account_snapshot_notion_report_json": str(account_notion.relative_to(workspace)),
            "benchmark_notion_report_json": str(benchmark_notion.relative_to(workspace)),
        },
    )
    path = runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, data_date, trade_date)
    runbook_state.save_state(state, path)
    return path


def _active_state(workspace: Path, data_date: str, trade_date: str) -> Path:
    state = runbook_state.create_initial_state(ACCOUNT_ID, data_date, trade_date)
    path = runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, data_date, trade_date)
    runbook_state.save_state(state, path)
    return path


def test_calendar_returns_next_ordinary_weekday() -> None:
    calendar = load_market_calendar()
    assert calendar.next_trading_day(date(2026, 7, 6)) == date(2026, 7, 7)


def test_calendar_skips_friday_to_monday() -> None:
    calendar = load_market_calendar()
    assert calendar.next_trading_day(date(2026, 7, 10)) == date(2026, 7, 13)


def test_calendar_skips_weekend() -> None:
    calendar = load_market_calendar()
    assert calendar.is_trading_day(date(2026, 7, 11)) is False
    assert calendar.is_trading_day(date(2026, 7, 12)) is False


def test_calendar_skips_us_market_holiday() -> None:
    calendar = load_market_calendar()
    assert calendar.next_trading_day(date(2026, 7, 2)) == date(2026, 7, 6)


def test_previous_trade_date_becomes_next_data_date(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _complete_state(workspace, "2026-07-01", "2026-07-02")

    result = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)

    assert result == {
        "runner_result": "PASS",
        "mode": "PREVIEW",
        "account_id": ACCOUNT_ID,
        "previous_runbook_day_id": f"{ACCOUNT_ID}_2026-07-01_2026-07-02",
        "next_data_date": "2026-07-02",
        "next_trade_date": "2026-07-06",
        "next_runbook_day_id": f"{ACCOUNT_ID}_2026-07-02_2026-07-06",
        "already_exists": False,
        "safe_to_prepare": True,
        "next_required_action": "Run 6-4C to prepare the local runbook environment.",
    }


def test_active_incomplete_day_blocks_rollover(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _complete_state(workspace, "2026-07-01", "2026-07-02")
    _active_state(workspace, "2026-07-02", "2026-07-06")

    result = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "active_runbook_day_exists"
    assert result["safe_to_prepare"] is False


def test_missing_completed_day_blocks_without_bootstrap(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / runbook_state.STATE_DIRNAME).mkdir()

    result = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "completed_runbook_day_not_found"


def test_multiple_active_days_are_blocked(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _complete_state(workspace, "2026-07-01", "2026-07-02")
    _active_state(workspace, "2026-07-02", "2026-07-06")
    _active_state(workspace, "2026-07-06", "2026-07-07")

    result = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "multiple_active_runbook_days"
    assert len(result["blockers"]) == 2


def test_tied_latest_completed_days_are_blocked(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _complete_state(workspace, "2026-06-30", "2026-07-02")
    _complete_state(workspace, "2026-07-01", "2026-07-02")

    result = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "active_runbook_day_exists"


def test_calculated_data_date_cannot_move_backward(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _complete_state(workspace, "2026-07-03", "2026-07-02")

    result = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "calculated_dates_move_backward"


def test_target_account_state_filename_mismatch_blocks_rollover(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    valid_path = _complete_state(workspace, "2026-07-01", "2026-07-02")
    mismatched_path = valid_path.with_name("wrong_filename.json")
    valid_path.replace(mismatched_path)

    result = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "invalid_runbook_state"
    assert result["blockers"] == ["state_filename_mismatch:wrong_filename.json"]


def test_existing_next_runbook_artifact_is_detected(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _complete_state(workspace, "2026-07-01", "2026-07-02")
    duplicate_dir = workspace / "artifacts" / f"{ACCOUNT_ID}_2026-07-02_2026-07-06"
    duplicate_dir.mkdir(parents=True)

    result = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)

    assert result["runner_result"] == "PASS"
    assert result["already_exists"] is True
    assert result["safe_to_prepare"] is False


def test_calendar_coverage_exceeded_blocks_rollover(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _complete_state(workspace, "2027-12-30", "2027-12-31")

    result = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "calendar_coverage_exceeded"


def test_calendar_rejects_direct_out_of_coverage_query() -> None:
    calendar = load_market_calendar()
    try:
        calendar.is_trading_day(date(2028, 1, 3))
    except CalendarCoverageError as exc:
        assert "calendar_coverage_exceeded" in str(exc)
    else:
        raise AssertionError("Expected CalendarCoverageError")


def test_invalid_workspace_and_account_are_blocked(tmp_path: Path) -> None:
    calendar = load_market_calendar()
    invalid_workspace = preview_rollover(
        tmp_path / "missing",
        ACCOUNT_ID,
        calendar,
        confirm_paper_test=True,
    )
    invalid_account = preview_rollover(
        tmp_path,
        "live_account",
        calendar,
        confirm_paper_test=True,
    )

    assert invalid_workspace["reason"] == "invalid_workspace"
    assert invalid_account["reason"] == "paper_account_required"


def test_repeated_preview_is_identical_and_read_only(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state_path = _complete_state(workspace, "2026-07-01", "2026-07-02")
    artifact = workspace / "existing_artifact.json"
    artifact.write_text('{"unchanged": true}\n', encoding="utf-8")
    before_state = state_path.read_bytes()
    before_artifact = artifact.read_bytes()
    before_files = {path.relative_to(workspace): path.read_bytes() for path in workspace.rglob("*") if path.is_file()}

    first = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)
    second = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)

    assert first == second
    assert state_path.read_bytes() == before_state
    assert artifact.read_bytes() == before_artifact
    assert {path.relative_to(workspace): path.read_bytes() for path in workspace.rglob("*") if path.is_file()} == before_files


def test_cli_exit_codes_match_pass_and_blocked(tmp_path: Path, capsys) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _complete_state(workspace, "2026-07-01", "2026-07-02")

    pass_code = runbook_day_rollover_cli.main(
        ["--workspace", str(workspace), "--account-id", ACCOUNT_ID, "--confirm-paper-test"]
    )
    pass_payload = json.loads(capsys.readouterr().out)
    blocked_code = runbook_day_rollover_cli.main(
        ["--workspace", str(workspace), "--account-id", ACCOUNT_ID]
    )
    blocked_payload = json.loads(capsys.readouterr().out)

    assert pass_code == 0
    assert pass_payload["runner_result"] == "PASS"
    assert blocked_code == 2
    assert blocked_payload["reason"] == "paper_test_confirmation_required"


@pytest.mark.parametrize(
    "artifact_name",
    ["account_snapshot_notion_report_json", "benchmark_notion_report_json"],
)
def test_missing_either_notion_result_blocks_rollover(tmp_path: Path, artifact_name: str) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state_path = _complete_state(workspace, "2026-07-01", "2026-07-02")
    state = runbook_state.load_state(state_path)
    artifacts = dict(state.artifacts)
    artifacts.pop(artifact_name)
    runbook_state.save_state(replace(state, artifacts=artifacts), state_path)

    result = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "active_runbook_day_exists"


@pytest.mark.parametrize("f_status", ["FAILED", "BLOCKED"])
def test_failed_or_blocked_stage_f_blocks_rollover(tmp_path: Path, f_status: str) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state_path = _complete_state(workspace, "2026-07-01", "2026-07-02")
    state = runbook_state.load_state(state_path)
    statuses = dict(state.stage_status)
    statuses["F"] = f_status
    runbook_state.save_state(
        replace(state, current_status=f_status, stage_status=statuses, last_error={"stage_id": "F"}),
        state_path,
    )

    result = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "active_runbook_day_exists"


def test_missing_notion_evidence_file_blocks_rollover(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state_path = _complete_state(workspace, "2026-07-01", "2026-07-02")
    state = runbook_state.load_state(state_path)
    evidence_path = workspace / state.artifacts["account_snapshot_notion_report_json"]
    evidence_path.unlink()

    result = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "active_runbook_day_exists"


_MISSING = object()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("runner_result", "FAILED"),
        ("status", "PASS"),
        ("mode", "dry_run"),
        ("account_id", "paper_other"),
        ("date", "2026-07-01"),
        ("trade_date", "2026-07-01"),
        ("failed_count", _MISSING),
        ("failed_count", None),
        ("failed_count", "0"),
        ("failed_count", False),
        ("failed_count", 1),
        ("blocked_count", _MISSING),
        ("blocked_count", "0"),
        ("blocked_count", 1),
        ("current_state_written", _MISSING),
        ("current_state_written", False),
        ("current_state_written", 1),
        ("account_snapshot_written", "true"),
        ("position_snapshot_written", False),
        ("market_valuation_status", "failed"),
    ],
)
def test_invalid_eod_commit_semantics_block_rollover(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state_path = _complete_state(workspace, "2026-07-01", "2026-07-02")
    state = runbook_state.load_state(state_path)
    evidence_path = workspace / state.artifacts["eod_commit_report_json"]
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    if value is _MISSING:
        payload.pop(field)
    else:
        payload[field] = value
    _write_json(evidence_path, payload)

    validation = runbook_stage_e_evidence.validate_stage_e_completion_evidence(
        workspace, state, workspace.parent / "outputs" / "paper_accounts" / ACCOUNT_ID
    )
    result = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)

    assert validation["valid"] is False
    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "active_runbook_day_exists"


@pytest.mark.parametrize(
    ("location", "field", "value"),
    [
        ("wrapper", "schema_version", "invalid"),
        ("wrapper", "runner_result", "FAILED"),
        ("wrapper", "runner_result", "BLOCKED"),
        ("wrapper", "runner_result", "WARNING"),
        ("wrapper", "stage_id", "F"),
        ("wrapper", "step_id", 17),
        ("wrapper", "command_key", "eod_commit"),
        ("raw", "account_id", "paper_other"),
        ("raw", "trade_date", "2026-07-01"),
        ("raw", "data_date", _MISSING),
        ("raw", "data_date", "2026-07-03"),
        ("raw", "write_executed", True),
        ("raw", "blockers", ["unresolved blocker"]),
        ("raw", "overall_status", "WARNING"),
        ("raw", "overall_status", "FAILED"),
    ],
)
def test_invalid_final_status_semantics_block_rollover(
    tmp_path: Path,
    location: str,
    field: str,
    value: object,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state_path = _complete_state(workspace, "2026-07-01", "2026-07-02")
    state = runbook_state.load_state(state_path)
    evidence_path = workspace / state.artifacts["final_status_report_json"]
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    target = payload if location == "wrapper" else payload["raw_payload"]
    if value is _MISSING:
        target.pop(field)
    else:
        target[field] = value
    _write_json(evidence_path, payload)

    validation = runbook_stage_e_evidence.validate_stage_e_completion_evidence(
        workspace, state, workspace.parent / "outputs" / "paper_accounts" / ACCOUNT_ID
    )
    result = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)

    assert validation["valid"] is False
    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "active_runbook_day_exists"


@pytest.mark.parametrize("artifact_name", ["eod_commit_report_json", "final_status_report_json"])
@pytest.mark.parametrize("failure", ["missing_ref", "missing_file", "outside_workspace", "invalid_json", "empty_object"])
def test_invalid_stage_e_artifact_storage_blocks_rollover(
    tmp_path: Path,
    artifact_name: str,
    failure: str,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state_path = _complete_state(workspace, "2026-07-01", "2026-07-02")
    state = runbook_state.load_state(state_path)
    artifacts = dict(state.artifacts)
    evidence_path = workspace / artifacts[artifact_name]
    if failure == "missing_ref":
        artifacts.pop(artifact_name)
        state = replace(state, artifacts=artifacts)
        runbook_state.save_state(state, state_path)
    elif failure == "missing_file":
        evidence_path.unlink()
    elif failure == "outside_workspace":
        outside = tmp_path / "outside.json"
        _write_json(outside, {"runner_result": "PASS"})
        artifacts[artifact_name] = str(outside)
        state = replace(state, artifacts=artifacts)
        runbook_state.save_state(state, state_path)
    elif failure == "invalid_json":
        evidence_path.write_text("{invalid", encoding="utf-8")
    else:
        _write_json(evidence_path, {})

    validation = runbook_stage_e_evidence.validate_stage_e_completion_evidence(
        workspace, state, workspace.parent / "outputs" / "paper_accounts" / ACCOUNT_ID
    )
    result = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)

    assert validation["valid"] is False
    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "active_runbook_day_exists"


@pytest.mark.parametrize(
    ("artifact_name", "field", "value"),
    [
        ("account_snapshot_notion_report_json", "external_key", "arbitrary"),
        ("benchmark_notion_report_json", "external_key", "benchmark:legacy"),
        ("account_snapshot_notion_report_json", "failed_count", _MISSING),
        ("benchmark_notion_report_json", "failed_count", False),
    ],
)
def test_strict_stage_f_evidence_blocks_rollover(
    tmp_path: Path,
    artifact_name: str,
    field: str,
    value: object,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state_path = _complete_state(workspace, "2026-07-01", "2026-07-02")
    state = runbook_state.load_state(state_path)
    evidence_path = workspace / state.artifacts[artifact_name]
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    item = payload["raw_payload"]["json"][0]
    if value is _MISSING:
        item.pop(field)
    else:
        item[field] = value
    _write_json(evidence_path, payload)

    result = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "active_runbook_day_exists"

from __future__ import annotations

import json
import csv
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.notion_account_keys import (
    build_account_snapshot_external_key,
    build_benchmark_report_external_key,
)
from core.paper_account_snapshot import PAPER_ACCOUNT_SNAPSHOT_COLUMNS
from core.paper_execution_intent import build_execution_intent
from core.paper_execution_log import PAPER_EXECUTION_LOG_COLUMNS
from core.paper_manual_review_log_template import PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS
from core.paper_position_snapshot import PAPER_POSITION_SNAPSHOT_COLUMNS
from scripts import runbook_completion_evidence
from scripts import runbook_stage_runner
from scripts import runbook_command_registry
from scripts import runbook_result
from scripts import runbook_state
from tests.runbook_standard_evidence_fixtures import seed_standard_export_evidence


ACCOUNT_ID = "paper_pilot_202606"
DATA_DATE = "2026-07-01"
TRADE_DATE = "2026-07-02"


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _seed_stage_e_pass(workspace: Path, account_root: Path, *, omit_f: bool = False) -> Path:
    account_root.mkdir(parents=True, exist_ok=True)
    (account_root / "reports").mkdir(parents=True, exist_ok=True)
    (account_root / "reviews").mkdir(parents=True, exist_ok=True)
    with (account_root / "paper_account_snapshot.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_ACCOUNT_SNAPSHOT_COLUMNS)
        writer.writeheader()
        writer.writerow({"account_id": ACCOUNT_ID, "snapshot_date": TRADE_DATE, "total_equity_market_value": 100000})
    with (account_root / "paper_position_snapshot.csv").open("w", encoding="utf-8", newline="") as handle:
        csv.DictWriter(handle, fieldnames=PAPER_POSITION_SNAPSHOT_COLUMNS).writeheader()
    with (account_root / "paper_execution_log.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_EXECUTION_LOG_COLUMNS)
        writer.writeheader()
        writer.writerow({"date": TRADE_DATE, "symbol": "AAPL", "status": "COMMITTED"})
    with (account_root / "reviews" / "paper_manual_review_log.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS)
        writer.writeheader()
        writer.writerow({"review_date": TRADE_DATE, "symbol": "AAPL", "question_id": "Q1", "question_text": "review", "is_actionable": "false", "manual_answer": "done", "review_status": "reviewed", "follow_up_needed": "false"})
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    for stage_id in ("A", "GATE1", "B", "C", "GATE2", "D"):
        state = runbook_state.complete_stage(state, stage_id)
    items = [{"symbol": "AAPL", "action": "BUY", "quantity": 1}]
    plan_payload = {
        "schema_version": "paper_daily_plan.v1", "account_id": ACCOUNT_ID,
        "data_date": DATA_DATE, "trade_date": TRADE_DATE, "plan_date": TRADE_DATE,
        "run_mode": "official", "official_run": True,
        "generated_at": "2026-07-01T18:00:00+09:00", "fingerprints": {},
        "items": items, "execution_intent": build_execution_intent(items),
    }
    plan_path = _write_json(workspace / "artifacts" / state.runbook_day_id / "daily_plan.json", plan_payload)
    _write_json(account_root / "daily_action_plan_20260702.json", plan_payload)
    state = runbook_state.record_artifact(state, "daily_plan_json", str(plan_path), workspace)
    commit_path = _write_json(
        workspace / "artifacts" / state.runbook_day_id / "stage_e" / "paper_eod_commit_20260702.json",
        {
            "runner_result": "PASS",
            "status": "COMMITTED",
            "mode": "commit",
            "account_id": ACCOUNT_ID,
            "date": TRADE_DATE,
            "trade_date": TRADE_DATE,
            "failed_count": 0,
            "blocked_count": 0,
            "current_state_written": True,
            "account_snapshot_written": True,
            "position_snapshot_written": True,
            "market_valuation_status": "success",
        },
    )
    state = runbook_state.record_artifact(state, "eod_commit_report_json", str(commit_path), workspace)
    state = seed_standard_export_evidence(workspace, state)
    manifest = runbook_completion_evidence.build_runbook_completion_manifest(workspace, state, account_root)
    manifest_path = _write_json(
        workspace / "completion_manifests" / f"{state.runbook_day_id}.json", manifest
    )
    state = runbook_state.record_artifact(state, "completion_manifest_json", str(manifest_path), workspace)
    final_status_path = _write_json(
        workspace / "command_runs" / state.runbook_day_id / "final_status.json",
        runbook_result.create_command_result(
            state,
            runbook_command_registry.get_command("final_status"),
            "PASS",
            "Final status is PASS.",
            raw_payload={
                "schema_version": "mfu_oper9_daily_ops_status.v1",
                "overall_status": "PASS",
                "account_id": ACCOUNT_ID,
                "data_date": DATA_DATE,
                "trade_date": TRADE_DATE,
                "workflow_status": "REVIEW_DONE",
                "completion_mode": "STANDARD",
                "completion_proof": None,
                "runbook_completion_evidence": (
                    runbook_completion_evidence.build_standard_completion_context(workspace, state)
                ),
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
            process={"executed": True, "exit_code": 0, "duration_ms": 1},
            workspace=workspace,
        ),
    )
    state = runbook_state.record_artifact(state, "final_status_report_json", str(final_status_path), workspace)
    state = runbook_state.complete_step(state, 18, "E")
    state = runbook_state.complete_stage(state, "E")
    state_path = runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    if omit_f:
        payload = state.to_dict()
        payload["stage_status"].pop("F")
        _write_json(state_path, payload)
    else:
        runbook_state.save_state(state, state_path)
    return state_path


def _patch_account_root(monkeypatch: pytest.MonkeyPatch, account_root: Path) -> None:
    monkeypatch.setattr(
        runbook_stage_runner,
        "build_paper_account_paths",
        lambda account_id, create=False: SimpleNamespace(account_id=account_id, root=account_root),
    )


def _fake_stage_f_run(
    account_root: Path,
    calls: list[list[str]],
    *,
    fail_command: str | None = None,
    benchmark_account_id: str = ACCOUNT_ID,
    benchmark_date: str = TRADE_DATE,
    account_action: str = "created",
    benchmark_action: str = "created",
):
    def fake_run(argv, cwd, timeout_sec):
        calls.append(list(argv))
        joined = " ".join(argv)
        if "paper.py" in joined and "benchmark" in argv:
            report_json = account_root / "reports" / "paper_benchmark_comparison.json"
            report_md = account_root / "reports" / "paper_benchmark_comparison.md"
            payload = {
                "account_id": benchmark_account_id,
                "latest_snapshot_date": benchmark_date,
                "run_mode": "exploratory",
                "availability_status": "AVAILABLE",
            }
            _write_json(report_json, payload)
            report_md.write_text("# benchmark\n", encoding="utf-8")
            payload.update({"json_path": str(report_json), "markdown_path": str(report_md)})
            command_key = "benchmark_generate"
        elif "--account-snapshot" in argv:
            payload = [
                {
                    "account_id": ACCOUNT_ID,
                    "target": "account_snapshots",
                    "external_key": f"account_snapshot:{ACCOUNT_ID}:{TRADE_DATE}",
                    "action": account_action,
                    "source_path": str(account_root / "paper_account_snapshot.csv"),
                    "failed_count": 0,
                }
            ]
            command_key = "account_snapshot_notion_upsert"
        elif "--benchmark" in argv:
            payload = [
                {
                    "account_id": ACCOUNT_ID,
                    "target": "benchmark_reports",
                    "external_key": f"benchmark:{ACCOUNT_ID}:{TRADE_DATE}:exploratory",
                    "action": benchmark_action,
                    "source_path": str(account_root / "reports" / "paper_benchmark_comparison.json"),
                    "failed_count": 0,
                }
            ]
            command_key = "benchmark_report_notion_upsert"
        else:
            raise AssertionError(f"unexpected Stage F argv: {argv}")
        failed = command_key == fail_command
        return {
            "exit_code": 1 if failed else 0,
            "duration_ms": 10,
            "stdout": json.dumps(payload, ensure_ascii=False),
            "stderr": "simulated failure" if failed else "",
        }

    return fake_run


def _run_stage_f(workspace: Path, **kwargs):
    return runbook_stage_runner.run_stage_f(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
        **kwargs,
    )


def _complete_stage_f(
    workspace: Path,
    account_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, list[list[str]]]:
    state_path = _seed_stage_e_pass(workspace, account_root)
    _patch_account_root(monkeypatch, account_root)
    calls: list[list[str]] = []
    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", _fake_stage_f_run(account_root, calls))
    result = _run_stage_f(workspace)
    assert result["runner_result"] == "PASS"
    return state_path, calls


def test_stage_f_blocks_before_stage_e_without_subprocess(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    runbook_state.init_state_file_for_context(workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    calls: list[list[str]] = []
    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", lambda *args, **kwargs: calls.append(args))

    result = _run_stage_f(workspace)

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "stage_e_not_pass"
    assert calls == []


def test_stage_f_runs_19_to_21_with_frozen_account_and_date(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    account_root = tmp_path / "outputs" / "paper_accounts" / ACCOUNT_ID
    workspace.mkdir()
    state_path = _seed_stage_e_pass(workspace, account_root)
    _patch_account_root(monkeypatch, account_root)
    calls: list[list[str]] = []
    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", _fake_stage_f_run(account_root, calls))

    result = _run_stage_f(workspace)

    assert result["runner_result"] == "PASS"
    assert [item["command_key"] for item in result["rendered_commands"]] == [
        "benchmark_generate",
        "account_snapshot_notion_upsert",
        "benchmark_report_notion_upsert",
    ]
    assert len(calls) == 3
    assert all(ACCOUNT_ID in argv for argv in calls)
    assert all(TRADE_DATE in argv for argv in calls[1:])
    assert not any("eod" in argv for call in calls for argv in call)
    state = runbook_state.load_state(state_path)
    assert state.stage_status["E"] == "PASS"
    assert state.stage_status["F"] == "PASS"
    assert state.last_completed_stage == "F"
    assert state.last_completed_step == 21


@pytest.mark.parametrize(
    ("actual_account", "actual_date"),
    [("paper_other", TRADE_DATE), (ACCOUNT_ID, "2026-07-01")],
)
def test_stage_f_blocks_benchmark_context_mismatch_and_stops_followups(
    tmp_path: Path,
    monkeypatch,
    actual_account: str,
    actual_date: str,
) -> None:
    workspace = tmp_path / "workspace"
    account_root = tmp_path / "outputs" / "paper_accounts" / ACCOUNT_ID
    workspace.mkdir()
    state_path = _seed_stage_e_pass(workspace, account_root)
    _patch_account_root(monkeypatch, account_root)
    calls: list[list[str]] = []
    monkeypatch.setattr(
        runbook_stage_runner,
        "run_allowlisted_command",
        _fake_stage_f_run(
            account_root,
            calls,
            benchmark_account_id=actual_account,
            benchmark_date=actual_date,
        ),
    )

    result = _run_stage_f(workspace)

    assert result["runner_result"] == "BLOCKED"
    assert len(calls) == 1
    state = runbook_state.load_state(state_path)
    assert state.stage_status["E"] == "PASS"
    assert state.stage_status["F"] == "BLOCKED"
    assert state.last_completed_stage == "E"


def test_stage_f_failure_preserves_e_and_retry_runs_stage_f_only(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    account_root = tmp_path / "outputs" / "paper_accounts" / ACCOUNT_ID
    workspace.mkdir()
    state_path = _seed_stage_e_pass(workspace, account_root)
    _patch_account_root(monkeypatch, account_root)
    first_calls: list[list[str]] = []
    monkeypatch.setattr(
        runbook_stage_runner,
        "run_allowlisted_command",
        _fake_stage_f_run(account_root, first_calls, fail_command="benchmark_report_notion_upsert"),
    )

    first = _run_stage_f(workspace)
    failed_state = runbook_state.load_state(state_path)

    assert first["runner_result"] == "FAILED"
    assert failed_state.stage_status["E"] == "PASS"
    assert failed_state.stage_status["F"] == "FAILED"
    assert failed_state.last_completed_stage == "E"
    assert failed_state.last_error and failed_state.last_error["stage_id"] == "F"

    second_calls: list[list[str]] = []
    monkeypatch.setattr(
        runbook_stage_runner,
        "run_allowlisted_command",
        _fake_stage_f_run(
            account_root,
            second_calls,
            account_action="updated",
            benchmark_action="skipped",
        ),
    )
    second = _run_stage_f(workspace)

    assert second["runner_result"] == "PASS"
    assert [item["command_key"] for item in second["rendered_commands"]] == [
        "benchmark_generate",
        "account_snapshot_notion_upsert",
        "benchmark_report_notion_upsert",
    ]
    assert not any("eod" in argv for call in second_calls for argv in call)
    assert len(second_calls) == 3
    final_state = runbook_state.load_state(state_path)
    assert final_state.stage_status["E"] == "PASS"
    assert final_state.stage_status["F"] == "PASS"


def test_stage_f_already_pass_skips_all_actual_work(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    account_root = tmp_path / "outputs" / "paper_accounts" / ACCOUNT_ID
    workspace.mkdir()
    state_path, first_calls = _complete_stage_f(workspace, account_root, monkeypatch)
    before = state_path.read_bytes()
    calls: list[list[str]] = []
    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", lambda *args, **kwargs: calls.append(args))

    result = _run_stage_f(workspace)

    assert result["runner_result"] == "SKIPPED"
    assert result["reason"] == "stage_f_already_pass"
    assert result["rendered_commands"] == []
    assert len(first_calls) == 3
    assert calls == []
    assert state_path.read_bytes() == before


@pytest.mark.parametrize(
    "artifact_name",
    ["account_snapshot_notion_report_json", "benchmark_notion_report_json"],
)
def test_stage_f_pass_missing_notion_evidence_self_heals(
    tmp_path: Path,
    monkeypatch,
    artifact_name: str,
) -> None:
    workspace = tmp_path / "workspace"
    account_root = tmp_path / "outputs" / "paper_accounts" / ACCOUNT_ID
    workspace.mkdir()
    state_path, _ = _complete_stage_f(workspace, account_root, monkeypatch)
    state = runbook_state.load_state(state_path)
    artifacts = dict(state.artifacts)
    artifacts.pop(artifact_name)
    runbook_state.save_state(replace(state, artifacts=artifacts), state_path)
    calls: list[list[str]] = []
    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", _fake_stage_f_run(account_root, calls))

    result = _run_stage_f(workspace)

    assert result["runner_result"] == "PASS"
    assert result["stage_f_evidence_repair"] is True
    assert any(artifact_name in blocker for blocker in result["stage_f_evidence_blockers"])
    assert len(calls) == 3
    assert not any("eod" in part for call in calls for part in call)
    repaired = runbook_state.load_state(state_path)
    assert repaired.stage_status["E"] == "PASS"
    assert repaired.stage_status["F"] == "PASS"
    assert repaired.artifacts["account_snapshot_notion_report_json"]
    assert repaired.artifacts["benchmark_notion_report_json"]


def test_stage_f_pass_corrupt_evidence_repairs_fail_closed(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    account_root = tmp_path / "outputs" / "paper_accounts" / ACCOUNT_ID
    workspace.mkdir()
    state_path, _ = _complete_stage_f(workspace, account_root, monkeypatch)
    state = runbook_state.load_state(state_path)
    evidence_path = workspace / state.artifacts["benchmark_notion_report_json"]
    evidence_path.write_text("{not-json", encoding="utf-8")
    calls: list[list[str]] = []
    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", _fake_stage_f_run(account_root, calls))

    result = _run_stage_f(workspace)

    assert result["runner_result"] == "PASS"
    assert result["stage_f_evidence_repair"] is True
    assert "benchmark_notion_report_json:artifact_json_invalid" in result["stage_f_evidence_blockers"]
    assert len(calls) == 3


def test_stage_f_evidence_repair_failure_preserves_stage_e(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    account_root = tmp_path / "outputs" / "paper_accounts" / ACCOUNT_ID
    workspace.mkdir()
    state_path, _ = _complete_stage_f(workspace, account_root, monkeypatch)
    state = runbook_state.load_state(state_path)
    commit_path = workspace / state.artifacts["eod_commit_report_json"]
    commit_before = commit_path.read_bytes()
    artifacts = dict(state.artifacts)
    artifacts.pop("account_snapshot_notion_report_json")
    runbook_state.save_state(replace(state, artifacts=artifacts), state_path)
    calls: list[list[str]] = []
    monkeypatch.setattr(
        runbook_stage_runner,
        "run_allowlisted_command",
        _fake_stage_f_run(account_root, calls, fail_command="account_snapshot_notion_upsert"),
    )

    result = _run_stage_f(workspace)

    assert result["runner_result"] == "FAILED"
    assert result["stage_f_evidence_repair"] is True
    assert len(calls) == 2
    assert not any("eod" in part for call in calls for part in call)
    failed = runbook_state.load_state(state_path)
    assert failed.stage_status["E"] == "PASS"
    assert failed.stage_status["F"] == "FAILED"
    assert failed.last_completed_stage == "E"
    assert commit_path.read_bytes() == commit_before


def test_stage_f_incomplete_evidence_dry_run_is_byte_read_only(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    account_root = tmp_path / "outputs" / "paper_accounts" / ACCOUNT_ID
    workspace.mkdir()
    state_path, _ = _complete_stage_f(workspace, account_root, monkeypatch)
    state = runbook_state.load_state(state_path)
    artifacts = dict(state.artifacts)
    artifacts.pop("benchmark_notion_report_json")
    runbook_state.save_state(replace(state, artifacts=artifacts), state_path)
    before = {path.relative_to(workspace): path.read_bytes() for path in workspace.rglob("*") if path.is_file()}
    calls: list[list[str]] = []
    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", lambda *args, **kwargs: calls.append(args))

    result = _run_stage_f(workspace, dry_run=True)

    after = {path.relative_to(workspace): path.read_bytes() for path in workspace.rglob("*") if path.is_file()}
    assert result["runner_result"] == "PASS"
    assert result["stage_f_evidence_repair"] is True
    assert any("benchmark_notion_report_json" in item for item in result["stage_f_evidence_blockers"])
    assert [item["command_key"] for item in result["rendered_commands"]] == [
        "benchmark_generate",
        "account_snapshot_notion_upsert",
        "benchmark_report_notion_upsert",
    ]
    assert calls == []
    assert after == before


def test_legacy_state_without_f_can_run_stage_f_after_e_pass(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    account_root = tmp_path / "outputs" / "paper_accounts" / ACCOUNT_ID
    workspace.mkdir()
    _seed_stage_e_pass(workspace, account_root, omit_f=True)
    _patch_account_root(monkeypatch, account_root)
    calls: list[list[str]] = []
    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", _fake_stage_f_run(account_root, calls))

    result = _run_stage_f(workspace)

    assert result["runner_result"] == "PASS"
    assert len(calls) == 3


def test_partial_no_action_marker_cannot_reclassify_standard_completion(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    account_root = tmp_path / "outputs" / "paper_accounts" / ACCOUNT_ID
    workspace.mkdir()
    state_path = _seed_stage_e_pass(workspace, account_root)
    state = runbook_state.load_state(state_path)
    no_action_path = _write_json(
        workspace / "artifacts" / state.runbook_day_id / "stage_d" / "stage_d_no_action.json",
        {"action_mode": "NO_ACTION", "verified_no_action": True},
    )
    state = runbook_state.record_artifact(state, "stage_d_no_action_json", str(no_action_path), workspace)
    runbook_state.save_state(state, state_path)
    _patch_account_root(monkeypatch, account_root)
    calls: list[list[str]] = []
    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", _fake_stage_f_run(account_root, calls))

    result = _run_stage_f(workspace)

    assert result["runner_result"] == "BLOCKED"
    assert calls == []


def test_stage_f_dry_run_renders_only_stage_f_commands_without_subprocess(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    account_root = tmp_path / "outputs" / "paper_accounts" / ACCOUNT_ID
    workspace.mkdir()
    state_path = _seed_stage_e_pass(workspace, account_root)
    _patch_account_root(monkeypatch, account_root)
    before = runbook_state.load_state(state_path)
    calls: list[list[str]] = []
    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", lambda *args, **kwargs: calls.append(args))

    result = _run_stage_f(workspace, dry_run=True)

    assert result["runner_result"] == "PASS"
    assert [item["command_key"] for item in result["rendered_commands"]] == [
        "benchmark_generate",
        "account_snapshot_notion_upsert",
        "benchmark_report_notion_upsert",
    ]
    assert calls == []
    assert runbook_state.load_state(state_path) == before


def test_non_default_account_source_never_uses_paper_test(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    account_root = tmp_path / "outputs" / "paper_accounts" / ACCOUNT_ID
    fallback_root = tmp_path / "outputs" / "paper_test"
    workspace.mkdir()
    fallback_root.mkdir(parents=True)
    (fallback_root / "paper_account_snapshot.csv").write_text("wrong fallback\n", encoding="utf-8")
    _seed_stage_e_pass(workspace, account_root)
    _patch_account_root(monkeypatch, account_root)
    calls: list[list[str]] = []
    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", _fake_stage_f_run(account_root, calls))

    result = _run_stage_f(workspace)

    assert result["runner_result"] == "PASS"
    assert Path(result["account_root"]).resolve() == account_root.resolve()
    assert all("paper_test" not in part for call in calls for part in call)


def test_stage_f_export_failure_does_not_modify_legacy_snapshot_or_run_benchmark_sync(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path / "workspace"
    account_root = tmp_path / "outputs" / "paper_accounts" / ACCOUNT_ID
    workspace.mkdir()
    state_path = _seed_stage_e_pass(workspace, account_root)
    snapshot_path = account_root / "paper_account_snapshot.csv"
    snapshot_path.write_text("snapshot_date,total_equity\n2026-07-02,100000\n", encoding="utf-8")
    before = snapshot_path.read_bytes()
    _patch_account_root(monkeypatch, account_root)
    calls: list[list[str]] = []
    monkeypatch.setattr(
        runbook_stage_runner,
        "run_allowlisted_command",
        _fake_stage_f_run(account_root, calls, fail_command="account_snapshot_notion_upsert"),
    )

    result = _run_stage_f(workspace)

    assert result["runner_result"] == "BLOCKED"
    assert calls == []
    assert snapshot_path.read_bytes() == before
    state = runbook_state.load_state(state_path)
    assert state.stage_status["E"] == "PASS"
    assert state.stage_status["F"] == "BLOCKED"


def test_stage_f_account_roots_and_artifacts_are_isolated(tmp_path: Path, monkeypatch) -> None:
    account_a = "paper_a"
    account_b = "paper_b"
    root_a = tmp_path / "outputs" / "paper_accounts" / account_a
    root_b = tmp_path / "outputs" / "paper_accounts" / account_b
    source_a = root_a / "paper_account_snapshot.csv"
    source_b = root_b / "paper_account_snapshot.csv"
    source_a.parent.mkdir(parents=True)
    source_b.parent.mkdir(parents=True)
    source_a.write_text(f"account_id,snapshot_date\n{account_a},{TRADE_DATE}\n", encoding="utf-8")
    source_b.write_text(f"account_id,snapshot_date\n{account_b},{TRADE_DATE}\n", encoding="utf-8")
    state_a = runbook_state.create_initial_state(account_a, DATA_DATE, TRADE_DATE)
    state_b = runbook_state.create_initial_state(account_b, DATA_DATE, TRADE_DATE)
    payload_a = {
        "json": [
            {
                "account_id": account_a,
                "external_key": f"account_snapshot:{account_a}:{TRADE_DATE}",
                "action": "created",
                "source_path": str(source_a),
                "failed_count": 0,
            }
        ]
    }

    valid_a = runbook_stage_runner._validate_stage_f_export_payload(
        payload_a,
        state_a,
        root_a,
        expected_source=source_a,
        label="Account Snapshot",
    )
    invalid_b = runbook_stage_runner._validate_stage_f_export_payload(
        payload_a,
        state_b,
        root_b,
        expected_source=source_b,
        label="Account Snapshot",
    )

    assert valid_a["runner_result"] == "PASS"
    assert invalid_b["runner_result"] == "BLOCKED"
    assert any("account_id" in blocker or "source_path" in blocker for blocker in invalid_b["blockers"])


_MISSING = object()


@pytest.mark.parametrize(
    ("external_key", "expected_blocker"),
    [
        (_MISSING, "external_key_missing"),
        ("", "external_key_missing"),
        (123, "external_key_type_invalid"),
        (f"account_snapshot:paper_other:{TRADE_DATE}", "external_key_mismatch"),
        (f"account_snapshot:{ACCOUNT_ID}:2026-07-01", "external_key_mismatch"),
        (f"account_snapshot:{TRADE_DATE}", "external_key_mismatch"),
        ("arbitrary-non-empty", "external_key_mismatch"),
    ],
)
def test_account_snapshot_external_key_is_exact(
    tmp_path: Path,
    external_key: object,
    expected_blocker: str,
) -> None:
    root = tmp_path / "outputs" / "paper_accounts" / ACCOUNT_ID
    source = root / "paper_account_snapshot.csv"
    source.parent.mkdir(parents=True)
    source.write_text(f"account_id,snapshot_date\n{ACCOUNT_ID},{TRADE_DATE}\n", encoding="utf-8")
    item: dict[str, object] = {
        "account_id": ACCOUNT_ID,
        "action": "created",
        "source_path": str(source),
        "failed_count": 0,
    }
    if external_key is not _MISSING:
        item["external_key"] = external_key

    result = runbook_stage_runner._validate_stage_f_export_payload(
        {"json": [item]},
        runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE),
        root,
        expected_source=source,
        label="Account Snapshot",
    )

    assert result["runner_result"] == "BLOCKED"
    assert expected_blocker in result["blockers"]


def test_account_snapshot_official_external_key_passes(tmp_path: Path) -> None:
    root = tmp_path / "outputs" / "paper_accounts" / ACCOUNT_ID
    source = root / "paper_account_snapshot.csv"
    source.parent.mkdir(parents=True)
    source.write_text(f"account_id,snapshot_date\n{ACCOUNT_ID},{TRADE_DATE}\n", encoding="utf-8")
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    result = runbook_stage_runner._validate_stage_f_export_payload(
        {"json": [{
            "account_id": ACCOUNT_ID,
            "external_key": build_account_snapshot_external_key(ACCOUNT_ID, TRADE_DATE),
            "action": "created",
            "source_path": str(source),
            "failed_count": 0,
        }]},
        state,
        root,
        expected_source=source,
        label="Account Snapshot",
    )
    assert result["runner_result"] == "PASS"


@pytest.mark.parametrize("failed_count", [_MISSING, None, "0", "invalid", False, True, {}, [], -1, 1])
def test_stage_f_failed_count_requires_integer_zero(tmp_path: Path, failed_count: object) -> None:
    root = tmp_path / "outputs" / "paper_accounts" / ACCOUNT_ID
    source = root / "paper_account_snapshot.csv"
    source.parent.mkdir(parents=True)
    source.write_text(f"account_id,snapshot_date\n{ACCOUNT_ID},{TRADE_DATE}\n", encoding="utf-8")
    item: dict[str, object] = {
        "account_id": ACCOUNT_ID,
        "external_key": build_account_snapshot_external_key(ACCOUNT_ID, TRADE_DATE),
        "action": "created",
        "source_path": str(source),
    }
    if failed_count is not _MISSING:
        item["failed_count"] = failed_count

    result = runbook_stage_runner._validate_stage_f_export_payload(
        {"json": [item]},
        runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE),
        root,
        expected_source=source,
        label="Account Snapshot",
    )

    assert result["runner_result"] == "BLOCKED"
    assert any(blocker.startswith("failed_count_") for blocker in result["blockers"])


@pytest.mark.parametrize(
    "source_patch",
    [
        {"account_id": "paper_other"},
        {"latest_snapshot_date": "2026-07-01"},
        {"run_mode": "official"},
        {"run_mode": _MISSING},
        {"run_mode": 123},
    ],
)
def test_benchmark_external_key_uses_validated_source(
    tmp_path: Path,
    source_patch: dict[str, object],
) -> None:
    root = tmp_path / "outputs" / "paper_accounts" / ACCOUNT_ID
    source = root / "reports" / "paper_benchmark_comparison.json"
    source.parent.mkdir(parents=True)
    benchmark: dict[str, object] = {
        "account_id": ACCOUNT_ID,
        "latest_snapshot_date": TRADE_DATE,
        "run_mode": "exploratory",
    }
    for field, value in source_patch.items():
        if value is _MISSING:
            benchmark.pop(field, None)
        else:
            benchmark[field] = value
    _write_json(source, benchmark)
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    result = runbook_stage_runner._validate_stage_f_export_payload(
        {"json": [{
            "account_id": ACCOUNT_ID,
            "external_key": build_benchmark_report_external_key(ACCOUNT_ID, TRADE_DATE, "exploratory"),
            "action": "created",
            "source_path": str(source),
            "failed_count": 0,
        }]},
        state,
        root,
        expected_source=source,
        label="Benchmark Report",
    )
    assert result["runner_result"] == "BLOCKED"


def test_benchmark_official_external_key_passes(tmp_path: Path) -> None:
    root = tmp_path / "outputs" / "paper_accounts" / ACCOUNT_ID
    source = root / "reports" / "paper_benchmark_comparison.json"
    _write_json(source, {"account_id": ACCOUNT_ID, "latest_snapshot_date": TRADE_DATE, "run_mode": "exploratory"})
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    result = runbook_stage_runner._validate_stage_f_export_payload(
        {"json": [{
            "account_id": ACCOUNT_ID,
            "external_key": build_benchmark_report_external_key(ACCOUNT_ID, TRADE_DATE, "exploratory"),
            "action": "created",
            "source_path": str(source),
            "failed_count": 0,
        }]},
        state,
        root,
        expected_source=source,
        label="Benchmark Report",
    )
    assert result["runner_result"] == "PASS"


@pytest.mark.parametrize(
    "external_key",
    [
        f"benchmark:{TRADE_DATE}:exploratory",
        f"benchmark:{ACCOUNT_ID}:{TRADE_DATE}:official",
        "arbitrary-non-empty",
    ],
)
def test_benchmark_external_key_rejects_legacy_or_arbitrary_values(
    tmp_path: Path,
    external_key: str,
) -> None:
    root = tmp_path / "outputs" / "paper_accounts" / ACCOUNT_ID
    source = root / "reports" / "paper_benchmark_comparison.json"
    _write_json(source, {"account_id": ACCOUNT_ID, "latest_snapshot_date": TRADE_DATE, "run_mode": "exploratory"})
    result = runbook_stage_runner._validate_stage_f_export_payload(
        {"json": [{
            "account_id": ACCOUNT_ID,
            "external_key": external_key,
            "action": "created",
            "source_path": str(source),
            "failed_count": 0,
        }]},
        runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE),
        root,
        expected_source=source,
        label="Benchmark Report",
    )
    assert result["runner_result"] == "BLOCKED"
    assert "external_key_mismatch" in result["blockers"]


@pytest.mark.parametrize(
    ("artifact_name", "field", "value"),
    [
        ("account_snapshot_notion_report_json", "external_key", "arbitrary"),
        ("benchmark_notion_report_json", "external_key", "benchmark:legacy"),
        ("account_snapshot_notion_report_json", "failed_count", _MISSING),
        ("benchmark_notion_report_json", "failed_count", "0"),
    ],
)
def test_strict_stage_f_evidence_mismatch_self_heals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    artifact_name: str,
    field: str,
    value: object,
) -> None:
    workspace = tmp_path / "workspace"
    account_root = tmp_path / "outputs" / "paper_accounts" / ACCOUNT_ID
    workspace.mkdir()
    state_path, _ = _complete_stage_f(workspace, account_root, monkeypatch)
    state = runbook_state.load_state(state_path)
    evidence_path = workspace / state.artifacts[artifact_name]
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    item = evidence["raw_payload"]["json"][0]
    if value is _MISSING:
        item.pop(field)
    else:
        item[field] = value
    _write_json(evidence_path, evidence)
    calls: list[list[str]] = []
    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", _fake_stage_f_run(account_root, calls))

    result = _run_stage_f(workspace)

    assert result["runner_result"] == "PASS"
    assert result["stage_f_evidence_repair"] is True
    assert len(calls) == 3
    assert not any("eod" in part for call in calls for part in call)


@pytest.mark.parametrize("artifact_name", ["eod_commit_report_json", "final_status_report_json"])
def test_invalid_stage_e_evidence_blocks_stage_f_without_subprocess(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    artifact_name: str,
) -> None:
    workspace = tmp_path / "workspace"
    account_root = tmp_path / "outputs" / "paper_accounts" / ACCOUNT_ID
    workspace.mkdir()
    state_path, _ = _complete_stage_f(workspace, account_root, monkeypatch)
    state = runbook_state.load_state(state_path)
    evidence_path = workspace / state.artifacts[artifact_name]
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    if artifact_name == "eod_commit_report_json":
        evidence["current_state_written"] = False
    else:
        evidence["raw_payload"]["overall_status"] = "FAILED"
    before = evidence_path.read_bytes()
    _write_json(evidence_path, evidence)
    before = evidence_path.read_bytes()
    calls: list[list[str]] = []
    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", lambda *args, **kwargs: calls.append(args))

    result = _run_stage_f(workspace)

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "stage_e_completion_evidence_invalid"
    assert result["rendered_commands"] == []
    assert calls == []
    assert evidence_path.read_bytes() == before
    blocked = runbook_state.load_state(state_path)
    assert blocked.stage_status["E"] == "PASS"
    assert blocked.stage_status["F"] == "BLOCKED"

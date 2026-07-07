from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from scripts import runbook_stage_runner
from scripts import runbook_state


ACCOUNT_ID = "paper_pilot_202606"
DATA_DATE = "2026-07-01"
TRADE_DATE = "2026-07-02"


def _write_json(path: Path, payload: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _seed_stage_d_preview_state(
    workspace: Path,
    *,
    gate2_pass: bool = True,
    preview_artifact: bool = True,
    append_allowed: str = "true",
    preview_fail_count: int = 0,
) -> runbook_state.RunbookState:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    state = runbook_state.complete_stage(state, "A")
    state = runbook_state.complete_stage(state, "GATE1")
    state = runbook_state.complete_stage(state, "B")
    verification = _write_json(
        workspace / "verification_runs" / state.runbook_day_id / "latest_stage_b_verification.json",
        {
            "schema_version": "stage_b_verification.v1",
            "runner_result": "PASS",
            "committed_row_count": 5,
            "failed_count": 0,
        },
    )
    state = runbook_state.record_artifact(state, "stage_b_verification_json", verification, workspace)
    state = runbook_state.complete_stage(state, "C")
    if gate2_pass:
        state = runbook_state.complete_step(state, 12, "GATE2")
        state = runbook_state.complete_stage(state, "GATE2")
    gate2 = _write_json(
        workspace / "gate_runs" / state.runbook_day_id / "latest_GATE2.json",
        {
            "schema_version": "gate2_review_readiness.v1",
            "runner_result": "PASS" if gate2_pass else "WAIT",
            "gate_id": "GATE2",
        },
    )
    state = runbook_state.record_artifact(state, "gate2_readiness_json", gate2, workspace)
    template_csv = workspace / "artifacts" / state.runbook_day_id / "review_prep" / "paper_manual_review_log_template.csv"
    template_csv.parent.mkdir(parents=True, exist_ok=True)
    template_csv.write_text("review_date,symbol,question_id,manual_answer,review_status\n", encoding="utf-8")
    state = runbook_state.record_artifact(state, "manual_review_template_csv", str(template_csv), workspace)
    if preview_artifact:
        preview = workspace / "artifacts" / state.runbook_day_id / "stage_d" / "manual_review_import_preview_20260702.json"
        preview_md = preview.with_suffix(".md")
        preview_payload = {
            "account_id": ACCOUNT_ID,
            "review_date": TRADE_DATE,
            "candidate_count": 21,
            "pass_count": 21 - preview_fail_count,
            "warning_count": 0,
            "fail_count": preview_fail_count,
            "append_allowed": append_allowed,
            "duplicate_candidates": [],
        }
        _write_json(preview, preview_payload)
        preview_md.write_text("# preview\n", encoding="utf-8")
        state = runbook_state.complete_step(
            state,
            13,
            "D",
            {"review_preview_json": str(preview), "review_preview_md": str(preview_md)},
            workspace,
        )
        state = replace(state, current_status="PASS", last_error=None)
        latest_preview = workspace / "stage_runs" / state.runbook_day_id / "latest_D_PREVIEW.json"
        _write_json(latest_preview, {"stage_id": "D_PREVIEW", "runner_result": "PASS"})
    state_path = runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    runbook_state.save_state(state, state_path)
    return state


def _fake_stage_d_append_run(
    repo_outputs: Path,
    calls: list[list[str]],
    *,
    append_failed_count: int = 0,
    sync_failed: bool = False,
):
    def fake_run(argv, cwd, timeout_sec):
        calls.append(list(argv))
        compact = TRADE_DATE.replace("-", "")
        joined = " ".join(argv)
        if "import_notion_reviews.py" in joined and "--commit" in argv:
            assert "--preview-json" in argv
            assert any("workspace" in part and "manual_review_import_preview_20260702.json" in part for part in argv)
            commit_json = repo_outputs / "reports" / f"manual_review_import_commit_{compact}.json"
            commit_md = repo_outputs / "reports" / f"manual_review_import_commit_{compact}.md"
            commit_json.parent.mkdir(parents=True, exist_ok=True)
            commit_json.write_text("{}", encoding="utf-8")
            commit_md.write_text("# commit\n", encoding="utf-8")
            payload = {
                "status": "COMMITTED",
                "account_id": ACCOUNT_ID,
                "review_date": TRADE_DATE,
                "appended_count": 21,
                "skipped_count": 0,
                "failed_count": append_failed_count,
                "commit_json_path": str(commit_json),
                "commit_markdown_path": str(commit_md),
            }
        elif "sync_notion_review_status.py" in joined:
            assert any("workspace" in part and "manual_review_import_commit_20260702.json" in part for part in argv)
            sync_json = repo_outputs / "reports" / f"manual_review_status_sync_{compact}.json"
            sync_md = repo_outputs / "reports" / f"manual_review_status_sync_{compact}.md"
            sync_json.parent.mkdir(parents=True, exist_ok=True)
            sync_json.write_text("{}", encoding="utf-8")
            sync_md.write_text("# sync\n", encoding="utf-8")
            payload = {
                "overall_status": "PARTIAL_SUCCESS" if sync_failed else "SUCCESS",
                "account_id": ACCOUNT_ID,
                "review_date": TRADE_DATE,
                "candidate_count": 21,
                "updated_count": 20 if sync_failed else 21,
                "failed_count": 1 if sync_failed else 0,
                "sync_json_path": str(sync_json),
                "sync_markdown_path": str(sync_md),
            }
        else:
            raise AssertionError(f"unexpected argv: {argv}")
        return {"exit_code": 0, "duration_ms": 10, "stdout": json.dumps(payload), "stderr": ""}

    return fake_run


def test_stage_d_append_success_completes_stage_d(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    repo_outputs = tmp_path / "repo_outputs"
    workspace.mkdir()
    state = _seed_stage_d_preview_state(workspace)
    calls: list[list[str]] = []
    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", _fake_stage_d_append_run(repo_outputs, calls))

    result = runbook_stage_runner.run_stage_d_append(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "PASS"
    assert [item["command_key"] for item in result["rendered_commands"]] == ["review_append", "sync_review_status"]
    loaded = runbook_state.load_state(runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE))
    assert loaded.stage_status["D"] == "PASS"
    assert loaded.last_completed_step == 15
    assert loaded.last_completed_stage == "D"
    assert loaded.artifacts["review_append_report_json"].startswith(f"artifacts/{state.runbook_day_id}/stage_d/")
    assert loaded.artifacts["review_status_sync_report_json"].startswith(f"artifacts/{state.runbook_day_id}/stage_d/")
    assert (workspace / "stage_runs" / state.runbook_day_id / "latest_D.json").exists()
    assert (workspace / "stage_runs" / state.runbook_day_id / "latest_D_PREVIEW.json").exists()


def test_stage_d_append_blocks_when_gate2_not_pass(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _seed_stage_d_preview_state(workspace, gate2_pass=False)

    result = runbook_stage_runner.run_stage_d_append(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "gate2_required"


def test_stage_d_append_blocks_when_review_preview_missing(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _seed_stage_d_preview_state(workspace, preview_artifact=False)

    result = runbook_stage_runner.run_stage_d_append(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "review_preview_required"


def test_stage_d_append_blocks_when_append_allowed_false(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _seed_stage_d_preview_state(workspace, append_allowed="false")

    result = runbook_stage_runner.run_stage_d_append(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "review_preview_not_append_ready"


def test_stage_d_append_blocks_when_append_allowed_true_with_warnings(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _seed_stage_d_preview_state(workspace, append_allowed="true_with_warnings")

    result = runbook_stage_runner.run_stage_d_append(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "review_preview_not_append_ready"


def test_stage_d_append_failed_count_blocks_before_append(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _seed_stage_d_preview_state(workspace, preview_fail_count=1)

    result = runbook_stage_runner.run_stage_d_append(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "review_preview_not_append_ready"


def test_stage_d_append_pass_then_sync_fail_can_retry_sync_without_reappend(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    repo_outputs = tmp_path / "repo_outputs"
    workspace.mkdir()
    _seed_stage_d_preview_state(workspace)
    first_calls: list[list[str]] = []
    monkeypatch.setattr(
        runbook_stage_runner,
        "run_allowlisted_command",
        _fake_stage_d_append_run(repo_outputs, first_calls, sync_failed=True),
    )

    first = runbook_stage_runner.run_stage_d_append(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert first["runner_result"] == "BLOCKED"
    assert [item["command_key"] for item in first["rendered_commands"]] == ["review_append", "sync_review_status"]
    second_calls: list[list[str]] = []
    monkeypatch.setattr(
        runbook_stage_runner,
        "run_allowlisted_command",
        _fake_stage_d_append_run(repo_outputs, second_calls),
    )

    second = runbook_stage_runner.run_stage_d_append(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert second["runner_result"] == "PASS"
    assert [item["command_key"] for item in second["rendered_commands"]] == ["review_append", "sync_review_status"]
    assert second["rendered_commands"][0]["argv"] == []
    assert len(second_calls) == 1
    assert "sync_notion_review_status.py" in " ".join(second_calls[0])


def test_stage_d_append_same_preview_rerun_after_pass_is_blocked(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    repo_outputs = tmp_path / "repo_outputs"
    workspace.mkdir()
    _seed_stage_d_preview_state(workspace)
    calls: list[list[str]] = []
    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", _fake_stage_d_append_run(repo_outputs, calls))

    first = runbook_stage_runner.run_stage_d_append(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )
    second = runbook_stage_runner.run_stage_d_append(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert first["runner_result"] == "PASS"
    assert second["runner_result"] == "BLOCKED"
    assert second["reason"] == "stage_d_already_pass"

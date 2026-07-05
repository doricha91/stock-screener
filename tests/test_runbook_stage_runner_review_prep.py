from __future__ import annotations

import json
from pathlib import Path

from scripts import runbook_stage_runner
from scripts import runbook_state


ACCOUNT_ID = "paper_A"
DATA_DATE = "2026-06-12"
TRADE_DATE = "2026-06-15"


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _seed_stage_b_verified_state(
    workspace: Path,
    *,
    verification_runner_result: str = "PASS",
    stage_b_pass: bool = True,
) -> Path:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    state = runbook_state.complete_stage(state, "A")
    state = runbook_state.complete_stage(state, "GATE1")
    if stage_b_pass:
        state = runbook_state.complete_stage(state, "B")
    commit_report = _write_json(
        workspace / "artifacts" / state.runbook_day_id / "stage_b" / "commit.json",
        {"status": "COMMITTED"},
    )
    verification = _write_json(
        workspace / "verification_runs" / state.runbook_day_id / "latest_stage_b_verification.json",
        {
            "schema_version": "stage_b_verification.v1",
            "runner_result": verification_runner_result,
            "committed_row_count": 2,
            "failed_count": 0,
        },
    )
    state = runbook_state.record_artifact(state, "execution_commit_report_json", str(commit_report), workspace)
    state = runbook_state.record_artifact(state, "stage_b_verification_json", str(verification), workspace)
    state_path = runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    runbook_state.save_state(state, state_path)
    return state_path


def _fake_review_prep_run(repo_outputs: Path, calls: list[list[str]], *, step11_failed_count: int = 0, update_only: bool = False):
    review_report_md = repo_outputs / "reports" / "paper_daily_review_summary.md"
    report_index_md = repo_outputs / "reports" / "paper_report_index.md"
    template_csv = repo_outputs / "reviews" / "paper_manual_review_log_template.csv"
    template_md = repo_outputs / "reviews" / "paper_manual_review_log_template.md"
    validation_report = repo_outputs / "reviews" / "paper_manual_review_log_validation_report.md"
    validation_issues = repo_outputs / "reviews" / "paper_manual_review_log_validation_issues.csv"

    def fake_run(argv: list[str], cwd: Path, timeout_sec: int = 1800) -> dict[str, object]:
        calls.append(argv)
        joined = " ".join(argv)
        if "paper.py" in joined and "review" in argv:
            for path, text in (
                (review_report_md, "review"),
                (report_index_md, "index"),
                (template_csv, "review_date,symbol\n2026-06-15,ABC\n"),
                (template_md, "template"),
                (validation_report, "validation"),
                (validation_issues, "issue\n"),
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            payload = {
                "status": "PASS",
                "account_id": ACCOUNT_ID,
                "review_date": TRADE_DATE,
                "validation_result": "PASS",
                "daily_review_report_md": str(review_report_md),
                "report_index_md": str(report_index_md),
                "manual_review_template_csv": str(template_csv),
                "manual_review_template_md": str(template_md),
                "validation_report_md": str(validation_report),
                "validation_issues_csv": str(validation_issues),
            }
        elif "export_paper_to_notion.py" in joined and "--manual-review-template" in argv:
            assert any("review_prep" in part and template_csv.name in part for part in argv) is False
            payload = {
                "target": "manual_review_template",
                "account_id": ACCOUNT_ID,
                "review_date": TRADE_DATE,
                "candidate_count": 2,
                "create_count": 0 if update_only else 2,
                "update_count": 2 if update_only else 0,
                "skip_count": 0,
                "failed_count": step11_failed_count,
                "source_template_path": str(template_csv),
            }
        else:
            raise AssertionError(f"unexpected argv: {argv}")
        return {
            "executed": True,
            "exit_code": 0,
            "duration_ms": 1,
            "stdout": json.dumps(payload),
            "stderr": "",
        }

    return fake_run


def test_stage_b_review_runs_step_10_11_after_stage_b_verify_pass(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    repo_outputs = tmp_path / "repo_outputs"
    workspace.mkdir()
    _seed_stage_b_verified_state(workspace)
    calls: list[list[str]] = []
    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", _fake_review_prep_run(repo_outputs, calls))

    result = runbook_stage_runner.run_stage_b_review(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "PASS"
    assert [item["command_key"] for item in result["rendered_commands"]] == ["daily_review", "export_review_template"]
    assert "--json" in result["rendered_commands"][0]["argv"]
    assert len(calls) == 2
    state = runbook_state.load_state(Path(result["state_path"]))
    assert state.stage_status["B"] == "PASS"
    assert state.last_completed_step == 11
    assert state.artifacts["manual_review_template_csv"].startswith(f"artifacts/{state.runbook_day_id}/review_prep/")
    assert state.artifacts["manual_review_template_md"].startswith(f"artifacts/{state.runbook_day_id}/review_prep/")
    assert state.artifacts["notion_review_template_report_json"].startswith("command_runs/")
    assert (workspace / state.artifacts["manual_review_template_csv"]).exists()
    assert "Gate 2" in result["next_required_action"]


def test_stage_b_review_missing_verification_is_blocked(tmp_path: Path) -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    state = runbook_state.complete_stage(state, "A")
    state = runbook_state.complete_stage(state, "GATE1")
    state = runbook_state.complete_stage(state, "B")
    commit_report = _write_json(tmp_path / "commit.json", {"status": "COMMITTED"})
    state = runbook_state.record_artifact(state, "execution_commit_report_json", str(commit_report), tmp_path)
    state_path = runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    runbook_state.save_state(state, state_path)

    result = runbook_stage_runner.run_stage_b_review(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        dry_run=True,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "stage_b_verification_required"


def test_stage_b_review_verification_not_pass_is_blocked(tmp_path: Path) -> None:
    _seed_stage_b_verified_state(tmp_path, verification_runner_result="BLOCKED")

    result = runbook_stage_runner.run_stage_b_review(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        dry_run=True,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "stage_b_verification_required"


def test_stage_b_review_step_11_failed_count_fails(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    repo_outputs = tmp_path / "repo_outputs"
    workspace.mkdir()
    _seed_stage_b_verified_state(workspace)
    calls: list[list[str]] = []
    monkeypatch.setattr(
        runbook_stage_runner,
        "run_allowlisted_command",
        _fake_review_prep_run(repo_outputs, calls, step11_failed_count=1),
    )

    result = runbook_stage_runner.run_stage_b_review(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "FAILED"
    assert len(calls) == 2
    state = runbook_state.load_state(Path(result["state_path"]))
    assert state.stage_status["B"] == "PASS"
    assert state.artifacts["stage_b_review_prep_error_result_json"].startswith("command_runs/")


def test_stage_b_review_update_only_export_is_pass(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    repo_outputs = tmp_path / "repo_outputs"
    workspace.mkdir()
    _seed_stage_b_verified_state(workspace)
    calls: list[list[str]] = []
    monkeypatch.setattr(
        runbook_stage_runner,
        "run_allowlisted_command",
        _fake_review_prep_run(repo_outputs, calls, update_only=True),
    )

    result = runbook_stage_runner.run_stage_b_review(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "PASS"
    assert len(calls) == 2

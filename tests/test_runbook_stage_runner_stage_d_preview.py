from __future__ import annotations

import json
import hashlib
from pathlib import Path

from scripts import runbook_stage_runner
from scripts import runbook_state
from core.notion_account_keys import build_manual_review_canonical_key


ACCOUNT_ID = "paper_pilot_202606"
DATA_DATE = "2026-07-01"
TRADE_DATE = "2026-07-02"


def _write_json(path: Path, payload: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _seed_gate2_pass_state(
    workspace: Path,
    *,
    gate2_pass: bool = True,
    gate2_artifact: bool = True,
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
    template_csv = workspace / "artifacts" / state.runbook_day_id / "review_prep" / "paper_manual_review_log_template.csv"
    template_csv.parent.mkdir(parents=True, exist_ok=True)
    template_csv.write_text("review_date,symbol,question_id,manual_answer,review_status\n", encoding="utf-8")
    state = runbook_state.record_artifact(state, "stage_b_verification_json", verification, workspace)
    state = runbook_state.record_artifact(state, "manual_review_template_csv", str(template_csv), workspace)
    symbols = ["A", "B", "C", "D", "E"]
    scope_rows = [
        {
            "account_id": ACCOUNT_ID, "review_date": TRADE_DATE, "symbol": symbol,
            "question_id": "execution_review_1", "question_text": "Review execution.",
            "question_category": "execution_review", "review_tag": "execution_quality",
            "canonical_key": build_manual_review_canonical_key(ACCOUNT_ID, TRADE_DATE, symbol, "execution_review_1"),
        }
        for symbol in symbols
    ]
    basis = {
        "schema_version": "paper_daily_manual_review_scope.v1",
        "frozen_context": {"runbook_day_id": state.runbook_day_id, "account_id": ACCOUNT_ID,
                           "data_date": DATA_DATE, "trade_date": TRADE_DATE},
        "action_mode": "EXECUTION", "sources": {}, "manual_review_symbols": [],
        "current_open_symbols": [], "position_symbols": [], "execution_symbols": symbols,
        "canonical_keys": [row["canonical_key"] for row in scope_rows], "rows": scope_rows,
    }
    scope_sha = hashlib.sha256(
        json.dumps(basis, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    scope_path = _write_json(
        workspace / "artifacts" / state.runbook_day_id / "stage_c" / "manual_review_scope.json",
        {**basis, "generated_at": "2026-07-02T00:00:00", "counts": {"total": 5}, "scope_sha256": scope_sha},
    )
    state = runbook_state.record_artifact(state, "manual_review_scope_json", scope_path, workspace)
    state = runbook_state.complete_stage(state, "C")
    if gate2_pass:
        state = runbook_state.complete_step(state, 12, "GATE2")
        state = runbook_state.complete_stage(state, "GATE2")
    if gate2_artifact:
        gate2 = _write_json(
            workspace / "gate_runs" / state.runbook_day_id / "latest_GATE2.json",
            {
                "schema_version": "gate2_review_readiness.v1",
                "runner_result": "PASS" if gate2_pass else "WAIT",
                "gate_id": "GATE2",
                "manual_review_scope_sha256": scope_sha,
            },
        )
        state = runbook_state.record_artifact(state, "gate2_readiness_json", gate2, workspace)
    path = runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    runbook_state.save_state(state, path)
    return state


def _fake_review_preview_run(repo_outputs: Path, calls: list[list[str]], *, fail_count: int = 0, missing_artifact: bool = False):
    def fake_run(argv, cwd, timeout_sec):
        calls.append(list(argv))
        compact = TRADE_DATE.replace("-", "")
        json_path = repo_outputs / "reports" / f"manual_review_import_preview_{compact}.json"
        md_path = repo_outputs / "reports" / f"manual_review_import_preview_{compact}.md"
        if not missing_artifact:
            json_path.parent.mkdir(parents=True, exist_ok=True)
            json_path.write_text("{}", encoding="utf-8")
            md_path.write_text("# preview\n", encoding="utf-8")
        payload = {
            "account_id": ACCOUNT_ID,
            "review_date": TRADE_DATE,
            "candidate_count": 5,
            "pass_count": 5 - fail_count,
            "warning_count": 0,
            "fail_count": fail_count,
            "append_allowed": "false" if fail_count else "true",
            "json_path": str(json_path),
            "markdown_path": str(md_path),
            "candidates": [
                {
                    "canonical_key": build_manual_review_canonical_key(
                        ACCOUNT_ID, TRADE_DATE, symbol, "execution_review_1"
                    )
                }
                for symbol in ["A", "B", "C", "D", "E"]
            ],
        }
        return {
            "exit_code": 0,
            "duration_ms": 10,
            "stdout": "MANUAL REVIEW IMPORT PREVIEW\n" + json.dumps(payload),
            "stderr": "",
        }

    return fake_run


def test_stage_d_preview_pins_review_preview_artifacts(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    repo_outputs = tmp_path / "repo_outputs"
    workspace.mkdir()
    state = _seed_gate2_pass_state(workspace)
    calls: list[list[str]] = []
    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", _fake_review_preview_run(repo_outputs, calls))

    result = runbook_stage_runner.run_stage_d_preview(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "PASS"
    assert result["stage_id"] == "D_PREVIEW"
    assert result["canonical_stage_id"] == "D"
    assert [item["command_key"] for item in result["rendered_commands"]] == ["review_preview"]
    assert len(calls) == 1
    assert "import_notion_reviews.py" in " ".join(calls[0])
    loaded = runbook_state.load_state(runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE))
    assert loaded.stage_status["B"] == "PASS"
    assert loaded.stage_status["C"] == "PASS"
    assert loaded.stage_status["GATE2"] == "PASS"
    assert loaded.stage_status["D"] == "PENDING"
    assert loaded.current_stage == "D"
    assert loaded.current_status == "PASS"
    assert loaded.last_completed_step == 13
    assert loaded.last_completed_stage == "GATE2"
    assert loaded.artifacts["review_preview_json"].startswith(f"artifacts/{state.runbook_day_id}/stage_d/")
    assert loaded.artifacts["review_preview_md"].startswith(f"artifacts/{state.runbook_day_id}/stage_d/")
    assert (workspace / loaded.artifacts["review_preview_json"]).exists()
    latest = workspace / "stage_runs" / state.runbook_day_id / "latest_D_PREVIEW.json"
    assert latest.exists()
    latest_payload = json.loads(latest.read_text(encoding="utf-8"))
    assert latest_payload["stage_id"] == "D_PREVIEW"
    assert latest_payload["canonical_stage_id"] == "D"
    assert "Review preview artifact" in result["next_required_action"]


def test_stage_d_preview_blocks_extra_stale_canonical_key(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = _seed_gate2_pass_state(workspace)
    json_path = tmp_path / "preview.json"
    md_path = tmp_path / "preview.md"
    json_path.write_text("{}", encoding="utf-8")
    md_path.write_text("# preview", encoding="utf-8")
    candidates = [
        {"canonical_key": build_manual_review_canonical_key(ACCOUNT_ID, TRADE_DATE, symbol, "execution_review_1")}
        for symbol in ["A", "B", "C", "D", "E", "STALE"]
    ]
    validation = runbook_stage_runner._validate_review_preview_payload(
        {
            "account_id": ACCOUNT_ID,
            "review_date": TRADE_DATE,
            "candidate_count": 6,
            "fail_count": 0,
            "blocked_count": 0,
            "append_allowed": "true",
            "json_path": str(json_path),
            "markdown_path": str(md_path),
            "candidates": candidates,
        },
        state,
        workspace,
    )
    assert validation["runner_result"] == "BLOCKED"
    assert any("extra canonical keys" in blocker for blocker in validation["blockers"])


def test_stage_d_preview_blocks_when_gate2_not_pass(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _seed_gate2_pass_state(workspace, gate2_pass=False)

    result = runbook_stage_runner.run_stage_d_preview(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "gate2_required"
    assert "Gate 2" in result["next_required_action"]


def test_stage_d_preview_blocks_when_gate2_artifact_missing(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _seed_gate2_pass_state(workspace, gate2_artifact=False)

    result = runbook_stage_runner.run_stage_d_preview(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "gate2_required"


def test_stage_d_preview_blocks_when_fail_count_nonzero(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    repo_outputs = tmp_path / "repo_outputs"
    workspace.mkdir()
    _seed_gate2_pass_state(workspace)
    calls: list[list[str]] = []
    monkeypatch.setattr(
        runbook_stage_runner,
        "run_allowlisted_command",
        _fake_review_preview_run(repo_outputs, calls, fail_count=1),
    )

    result = runbook_stage_runner.run_stage_d_preview(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "BLOCKED"
    loaded = runbook_state.load_state(runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE))
    assert "review_preview_json" not in loaded.artifacts
    assert loaded.artifacts["stage_d_preview_error_result_json"].startswith("command_runs/")


def test_stage_d_preview_fails_when_preview_artifact_missing(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    repo_outputs = tmp_path / "repo_outputs"
    workspace.mkdir()
    _seed_gate2_pass_state(workspace)
    calls: list[list[str]] = []
    monkeypatch.setattr(
        runbook_stage_runner,
        "run_allowlisted_command",
        _fake_review_preview_run(repo_outputs, calls, missing_artifact=True),
    )

    result = runbook_stage_runner.run_stage_d_preview(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "FAILED"
    loaded = runbook_state.load_state(runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE))
    assert "review_preview_json" not in loaded.artifacts
    assert loaded.artifacts["stage_d_preview_error_result_json"].startswith("command_runs/")


def test_stage_d_preview_dry_run_does_not_execute_append(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _seed_gate2_pass_state(workspace)

    result = runbook_stage_runner.run_stage_d_preview(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
        dry_run=True,
    )

    assert result["runner_result"] == "PASS"
    assert [item["command_key"] for item in result["rendered_commands"]] == ["review_preview"]
    assert result["review_preview_json"] == "dry_run/manual_review_import_preview.json"

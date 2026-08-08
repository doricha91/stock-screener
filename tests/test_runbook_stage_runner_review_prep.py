from __future__ import annotations

import json
from pathlib import Path

from core.paper_execution_intent import build_execution_intent
from scripts import runbook_stage_runner
from scripts import runbook_state
from scripts.runbook_no_action import sha256_file


ACCOUNT_ID = "paper_a"
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
    action_mode: str = "EXECUTION",
    verified_no_action: bool | None = None,
    committed_row_count: int | None = None,
    updated_count: int = 2,
    failed_count: int = 0,
    include_commit_report: bool | None = None,
) -> Path:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    state = runbook_state.complete_stage(state, "A")
    state = runbook_state.complete_stage(state, "GATE1")
    if stage_b_pass:
        state = runbook_state.complete_stage(state, "B")
        latest_b = workspace / "stage_runs" / state.runbook_day_id / "latest_B.json"
        _write_json(latest_b, {"stage_id": "B", "marker": "original-stage-b-summary"})
    items = [] if action_mode == "NO_ACTION" else [{"symbol": "ABC", "action": "BUY", "quantity": 2}]
    daily_plan = _write_json(
        workspace / "artifacts" / state.runbook_day_id / "daily_plan.json",
        {
            "schema_version": "paper_daily_plan.v1",
            "account_id": ACCOUNT_ID,
            "data_date": DATA_DATE,
            "trade_date": TRADE_DATE,
            "plan_date": TRADE_DATE,
            "run_mode": "official",
            "official_run": True,
            "generated_at": "2026-06-15T00:00:00Z",
            "items": items,
            "execution_intent": build_execution_intent(items),
            "fingerprints": {},
        },
    )
    state = runbook_state.record_artifact(state, "daily_plan_json", str(daily_plan), workspace)
    current_state = _write_json(
        workspace / "artifacts" / state.runbook_day_id / "stage_b" / "paper_current_state_20260615.json",
        {"current_symbols": [], "shares": {}},
    )
    state = runbook_state.record_artifact(state, "paper_current_state_json", str(current_state), workspace)
    if action_mode == "NO_ACTION":
        gate1 = _write_json(
            workspace / "gate_runs" / state.runbook_day_id / "gate1.json",
            {
                "runner_result": "PASS",
                "action_mode": "NO_ACTION",
                "execution_required": False,
                "candidate_execution_count": 0,
                "manual_execution_row_count": 0,
                "daily_plan_sha256": sha256_file(daily_plan),
                "frozen_context": {
                    "account_id": ACCOUNT_ID,
                    "data_date": DATA_DATE,
                    "trade_date": TRADE_DATE,
                },
            },
        )
        state = runbook_state.record_artifact(state, "gate1_readiness_json", str(gate1), workspace)
        no_action = _write_json(
            workspace / "no_action_runs" / state.runbook_day_id / "stage_b_no_action.json",
            {
                "schema_version": "stage_b_no_action.v1",
                "runner_result": "PASS",
                "runbook_day_id": state.runbook_day_id,
                "account_id": ACCOUNT_ID,
                "data_date": DATA_DATE,
                "trade_date": TRADE_DATE,
                "action_mode": "NO_ACTION",
                "execution_required": False,
                "candidate_execution_count": 0,
                "manual_execution_row_count": 0,
                "daily_plan_json": state.artifacts["daily_plan_json"],
                "daily_plan_sha256": sha256_file(daily_plan),
                "gate1_readiness_json": state.artifacts["gate1_readiness_json"],
                "skipped_command_keys": [
                    "execution_preview",
                    "execution_reconciliation_preview",
                    "execution_commit",
                    "sync_execution_status",
                ],
                "ledger_write_performed": False,
                "notion_write_performed": False,
                "idempotency_record_created": False,
            },
        )
        state = runbook_state.record_artifact(state, "stage_b_no_action_json", str(no_action), workspace)
    if include_commit_report is None:
        include_commit_report = action_mode == "EXECUTION"
    if include_commit_report:
        trade_ids = ["trade-abc", "trade-xyz"]
        committed_rows = [
            {
                "account_id": ACCOUNT_ID,
                "canonical_key": f"manual_execution:{ACCOUNT_ID}:{TRADE_DATE}:{symbol}:BUY:01",
                "symbol": symbol,
                "commit_status": "COMMITTED",
                "committed_trade_id": trade_id,
            }
            for symbol, trade_id in zip(("ABC", "XYZ"), trade_ids)
        ]
        commit_report = _write_json(
            workspace / "artifacts" / state.runbook_day_id / "stage_b" / "commit.json",
            {
                "status": "COMMITTED",
                "account_id": ACCOUNT_ID,
                "execution_date": TRADE_DATE,
                "committed_row_count": 2,
                "committed_trade_ids": trade_ids,
                "committed_rows": committed_rows,
            },
        )
        state = runbook_state.record_artifact(state, "execution_commit_report_json", str(commit_report), workspace)
    if verified_no_action is None:
        verified_no_action = action_mode == "NO_ACTION"
    if committed_row_count is None:
        committed_row_count = 0 if action_mode == "NO_ACTION" else 2
    if action_mode == "NO_ACTION" and updated_count == 2:
        updated_count = 0
    verification = _write_json(
        workspace / "verification_runs" / state.runbook_day_id / "latest_stage_b_verification.json",
        {
            "schema_version": "stage_b_verification.v1",
            "runner_result": verification_runner_result,
            "runbook_day_id": state.runbook_day_id,
            "account_id": ACCOUNT_ID,
            "data_date": DATA_DATE,
            "trade_date": TRADE_DATE,
            "action_mode": action_mode,
            "verified_no_action": verified_no_action,
            "committed_row_count": committed_row_count,
            "updated_count": updated_count,
            "failed_count": failed_count,
        },
    )
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
            scope_path = Path(argv[argv.index("--scope-manifest") + 1])
            scope = json.loads(scope_path.read_text(encoding="utf-8"))
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
                "manual_review_scope_sha256": scope["scope_sha256"],
                "manual_review_scope_count": scope["counts"]["total"],
                "manual_review_scope_canonical_keys": scope["canonical_keys"],
            }
        elif "export_paper_to_notion.py" in joined and "--manual-review-template" in argv:
            assert any("review_prep" in part and template_csv.name in part for part in argv) is False
            scope_path = next(
                Path(part) for part in calls[0] if str(part).endswith("manual_review_scope_20260615.json")
            )
            scope = json.loads(scope_path.read_text(encoding="utf-8"))
            candidate_count = scope["counts"]["total"]
            payload = {
                "target": "manual_review_template",
                "account_id": ACCOUNT_ID,
                "review_date": TRADE_DATE,
                "candidate_count": candidate_count,
                "create_count": 0 if update_only else candidate_count,
                "update_count": candidate_count if update_only else 0,
                "skip_count": 0,
                "failed_count": step11_failed_count,
                "source_template_path": str(template_csv),
                "candidates": [{"external_key": key} for key in scope["canonical_keys"]],
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


def test_stage_c_runs_step_10_11_after_stage_b_verify_pass_without_overwriting_latest_b(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    repo_outputs = tmp_path / "repo_outputs"
    workspace.mkdir()
    _seed_stage_b_verified_state(workspace)
    calls: list[list[str]] = []
    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", _fake_review_prep_run(repo_outputs, calls))

    result = runbook_stage_runner.run_stage_c(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "PASS"
    assert result["stage_id"] == "C"
    assert result["canonical_stage_id"] == "C"
    assert [item["command_key"] for item in result["rendered_commands"]] == ["daily_review", "export_review_template"]
    assert "--json" in result["rendered_commands"][0]["argv"]
    assert len(calls) == 2
    state = runbook_state.load_state(Path(result["state_path"]))
    assert state.stage_status["B"] == "PASS"
    assert state.stage_status["C"] == "PASS"
    assert state.last_completed_stage == "C"
    assert state.last_completed_step == 11
    assert [
        event["stage_id"]
        for event in state.history
        if event.get("event_type") == "step_completed" and event.get("step_id") in {10, 11}
    ] == ["C", "C"]
    assert state.artifacts["manual_review_template_csv"].startswith(f"artifacts/{state.runbook_day_id}/review_prep/")
    assert state.artifacts["manual_review_template_md"].startswith(f"artifacts/{state.runbook_day_id}/review_prep/")
    assert state.artifacts["notion_review_template_report_json"].startswith("command_runs/")
    assert state.artifacts["stage_c_summary_json"].startswith(f"stage_runs/{state.runbook_day_id}/")
    assert (workspace / state.artifacts["manual_review_template_csv"]).exists()
    latest_c = workspace / "stage_runs" / state.runbook_day_id / "latest_C.json"
    latest_b = workspace / "stage_runs" / state.runbook_day_id / "latest_B.json"
    assert latest_c.exists()
    assert json.loads(latest_c.read_text(encoding="utf-8"))["stage_id"] == "C"
    assert json.loads(latest_b.read_text(encoding="utf-8")) == {"stage_id": "B", "marker": "original-stage-b-summary"}
    assert "Gate 2" in result["next_required_action"]


def test_stage_c_missing_verification_is_blocked(tmp_path: Path) -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    state = runbook_state.complete_stage(state, "A")
    state = runbook_state.complete_stage(state, "GATE1")
    state = runbook_state.complete_stage(state, "B")
    items = [{"symbol": "ABC", "action": "BUY", "quantity": 1}]
    daily_plan = _write_json(
        tmp_path / "daily_plan.json",
        {
            "schema_version": "paper_daily_plan.v1",
                "account_id": ACCOUNT_ID,
                "data_date": DATA_DATE,
                "trade_date": TRADE_DATE,
                "plan_date": TRADE_DATE,
                "run_mode": "official",
                "official_run": True,
                "generated_at": "2026-06-15T00:00:00Z",
                "items": items,
                "execution_intent": build_execution_intent(items),
                "fingerprints": {},
        },
    )
    commit_report = _write_json(tmp_path / "commit.json", {"status": "COMMITTED"})
    state = runbook_state.record_artifact(state, "daily_plan_json", str(daily_plan), tmp_path)
    state = runbook_state.record_artifact(state, "execution_commit_report_json", str(commit_report), tmp_path)
    state_path = runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    runbook_state.save_state(state, state_path)

    result = runbook_stage_runner.run_stage_c(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        dry_run=True,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "BLOCKED"
    assert result["canonical_stage_id"] == "C"
    assert result["reason"] == "stage_b_verification_required"


def test_stage_c_verification_not_pass_is_blocked(tmp_path: Path) -> None:
    _seed_stage_b_verified_state(tmp_path, verification_runner_result="BLOCKED")

    result = runbook_stage_runner.run_stage_c(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        dry_run=True,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "stage_b_verification_required"


def test_stage_c_step_11_failed_count_fails(tmp_path: Path, monkeypatch) -> None:
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

    result = runbook_stage_runner.run_stage_c(
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
    assert state.stage_status["C"] == "PENDING"
    assert state.artifacts["stage_c_error_result_json"].startswith("command_runs/")


def test_stage_c_update_only_export_is_pass(tmp_path: Path, monkeypatch) -> None:
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

    result = runbook_stage_runner.run_stage_c(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "PASS"
    assert len(calls) == 2


def test_stage_c_valid_no_action_runs_review_prep_without_commit_report(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    repo_outputs = tmp_path / "repo_outputs"
    workspace.mkdir()
    _seed_stage_b_verified_state(workspace, action_mode="NO_ACTION")
    calls: list[list[str]] = []
    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", _fake_review_prep_run(repo_outputs, calls))

    result = runbook_stage_runner.run_stage_c(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "PASS"
    assert result["action_mode"] == "NO_ACTION"
    assert result["verified_no_action"] is True
    assert result["candidate_execution_count"] == 0
    assert result["execution_commit_report_json"] is None
    assert result["stage_b_no_action_json"]
    assert result["stage_b_verification_json"]
    assert len(calls) == 2
    summary = json.loads(Path(result["stage_summary_json"]).read_text(encoding="utf-8"))
    assert summary["raw_payload"]["action_mode"] == "NO_ACTION"
    expected_action = "No Manual Review input is required. Run Gate 2 to validate the pinned no-action review state."
    assert result["next_required_action"] == expected_action
    assert summary["summary"]["next_required_action"] == expected_action
    assert summary["raw_payload"]["next_required_action"] == expected_action
    latest_summary = json.loads(Path(result["latest_stage_summary_json"]).read_text(encoding="utf-8"))
    assert latest_summary["summary"]["next_required_action"] == expected_action
    state = runbook_state.load_state(Path(result["state_path"]))
    assert state.artifacts["stage_c_summary_json"].startswith(f"stage_runs/{state.runbook_day_id}/")


def test_stage_c_execution_retains_manual_review_message(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _seed_stage_b_verified_state(workspace)
    calls: list[list[str]] = []
    monkeypatch.setattr(
        runbook_stage_runner,
        "run_allowlisted_command",
        _fake_review_prep_run(tmp_path / "repo_outputs", calls),
    )

    result = runbook_stage_runner.run_stage_c(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "PASS"
    assert result["action_mode"] == "EXECUTION"
    assert result["next_required_action"] == "Fill Manual Review in Notion, then run Gate 2."


def test_stage_c_evidence_error_returns_blocked_without_second_read(tmp_path: Path, monkeypatch) -> None:
    state_path = _seed_stage_b_verified_state(tmp_path, action_mode="NO_ACTION")
    calls = 0

    def fail_evidence(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise runbook_stage_runner.EvidenceError("no_action_evidence_invalid", "fixture read error")

    monkeypatch.setattr(runbook_stage_runner, "_stage_c_evidence_context", fail_evidence)
    result = runbook_stage_runner.run_stage_c(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "no_action_evidence_invalid"
    assert result["state_path"] == str(state_path)
    assert calls == 1


def test_stage_c_execution_requires_positive_commit_verification(tmp_path: Path) -> None:
    _seed_stage_b_verified_state(tmp_path, committed_row_count=0)
    state_path = runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    state = runbook_state.load_state(state_path)

    assert runbook_stage_runner._stage_c_precondition_error(state, tmp_path) == "stage_b_verification_required"


def test_stage_c_execution_requires_commit_report(tmp_path: Path) -> None:
    _seed_stage_b_verified_state(tmp_path, include_commit_report=False)
    state_path = runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    state = runbook_state.load_state(state_path)

    assert runbook_stage_runner._stage_c_precondition_error(state, tmp_path) == "execution_commit_report_required"


def test_stage_c_no_action_requires_verified_zero_counts(tmp_path: Path) -> None:
    _seed_stage_b_verified_state(tmp_path, action_mode="NO_ACTION", verified_no_action=False)
    state_path = runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    state = runbook_state.load_state(state_path)

    assert (
        runbook_stage_runner._stage_c_precondition_error(state, tmp_path)
        == "stage_b_no_action_verification_required"
    )


def test_stage_c_no_action_blocks_positive_committed_count(tmp_path: Path) -> None:
    _seed_stage_b_verified_state(tmp_path, action_mode="NO_ACTION", committed_row_count=1)
    state_path = runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    state = runbook_state.load_state(state_path)

    assert (
        runbook_stage_runner._stage_c_precondition_error(state, tmp_path)
        == "stage_b_no_action_verification_required"
    )


def test_stage_c_no_action_requires_verification_artifact(tmp_path: Path) -> None:
    state_path = _seed_stage_b_verified_state(tmp_path, action_mode="NO_ACTION")
    state = runbook_state.load_state(state_path)
    state.artifacts.pop("stage_b_verification_json")
    runbook_state.save_state(state, state_path)

    assert runbook_stage_runner._stage_c_precondition_error(state, tmp_path) == "stage_b_verification_required"


def test_stage_c_no_action_blocks_unexpected_execution_artifact(tmp_path: Path) -> None:
    state_path = _seed_stage_b_verified_state(tmp_path, action_mode="NO_ACTION")
    state = runbook_state.load_state(state_path)
    report = _write_json(tmp_path / "unexpected_commit.json", {"status": "COMMITTED"})
    state = runbook_state.record_artifact(state, "execution_commit_report_json", str(report), tmp_path)
    runbook_state.save_state(state, state_path)

    assert (
        runbook_stage_runner._stage_c_precondition_error(state, tmp_path)
        == "no_action_write_artifact_present"
    )


def test_stage_c_no_action_blocks_execution_commit_pass_idempotency(tmp_path: Path) -> None:
    state_path = _seed_stage_b_verified_state(tmp_path, action_mode="NO_ACTION")
    state = runbook_state.load_state(state_path)
    state, key = runbook_state.reserve_idempotency(state, "execution_commit", 8, "B", workspace=tmp_path)
    state = runbook_state.mark_idempotency_pass(state, key)
    runbook_state.save_state(state, state_path)

    assert (
        runbook_stage_runner._stage_c_precondition_error(state, tmp_path)
        == "no_action_write_idempotency_present"
    )


def test_stage_c_blocks_action_mode_and_context_mismatch(tmp_path: Path) -> None:
    state_path = _seed_stage_b_verified_state(tmp_path, action_mode="NO_ACTION")
    state = runbook_state.load_state(state_path)
    verification_path = tmp_path / state.artifacts["stage_b_verification_json"]
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    verification["action_mode"] = "EXECUTION"
    _write_json(verification_path, verification)
    assert runbook_stage_runner._stage_c_precondition_error(state, tmp_path) == "action_mode_mismatch"

    verification["action_mode"] = "NO_ACTION"
    verification["account_id"] = "paper_other"
    _write_json(verification_path, verification)
    assert (
        runbook_stage_runner._stage_c_precondition_error(state, tmp_path)
        == "stage_b_verification_context_mismatch"
    )


def test_stage_c_no_action_blocks_daily_plan_hash_mismatch(tmp_path: Path) -> None:
    state_path = _seed_stage_b_verified_state(tmp_path, action_mode="NO_ACTION")
    state = runbook_state.load_state(state_path)
    daily_plan_path = tmp_path / state.artifacts["daily_plan_json"]
    payload = json.loads(daily_plan_path.read_text(encoding="utf-8"))
    payload["generated_at"] = "2026-06-15T01:00:00Z"
    _write_json(daily_plan_path, payload)

    assert runbook_stage_runner._stage_c_precondition_error(state, tmp_path) == "daily_plan_hash_mismatch"


def test_stage_b_review_alias_reports_canonical_stage_c(tmp_path: Path) -> None:
    _seed_stage_b_verified_state(tmp_path)

    result = runbook_stage_runner.run_stage_b_review(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        dry_run=True,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "PASS"
    assert result["stage_id"] == "C"
    assert result["canonical_stage_id"] == "C"
    assert result["deprecated_alias"] == "stage-b-review"


def test_stage_c_rebuild_is_allowed_only_while_gate2_and_downstream_are_pending(tmp_path: Path) -> None:
    state_path = _seed_stage_b_verified_state(tmp_path)
    state = runbook_state.load_state(state_path)
    state = runbook_state.complete_stage(state, "C")
    runbook_state.save_state(state, state_path)
    assert runbook_stage_runner._stage_c_precondition_error(state, tmp_path) is None


def test_stage_c_rebuild_is_forbidden_after_gate2_pass(tmp_path: Path) -> None:
    state_path = _seed_stage_b_verified_state(tmp_path)
    state = runbook_state.load_state(state_path)
    state = runbook_state.complete_stage(state, "C")
    state = runbook_state.complete_stage(state, "GATE2")
    runbook_state.save_state(state, state_path)
    assert (
        runbook_stage_runner._stage_c_precondition_error(state, tmp_path)
        == "stage_c_rebuild_forbidden_after_gate2_pass"
    )


def test_stage_c_rebuild_requires_explicit_authorization_flag(tmp_path: Path) -> None:
    state_path = _seed_stage_b_verified_state(tmp_path)
    state = runbook_state.load_state(state_path)
    state = runbook_state.complete_stage(state, "C")
    runbook_state.save_state(state, state_path)
    blocked = runbook_stage_runner.run_stage_c(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, dry_run=True, confirm_paper_test=True
    )
    assert blocked["reason"] == "stage_c_rebuild_authorization_required"
    allowed = runbook_stage_runner.run_stage_c(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        dry_run=True,
        confirm_paper_test=True,
        allow_rebuild=True,
    )
    assert allowed["runner_result"] == "PASS"

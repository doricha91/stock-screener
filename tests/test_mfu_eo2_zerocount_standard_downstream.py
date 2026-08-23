from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import paper_daily_ops_orchestrator
from core import runbook_day_rollover
from core.paper_execution_intent import build_execution_intent
from core.paper_execution_log import PAPER_EXECUTION_LOG_COLUMNS
from core.paper_manual_review_log_template import PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS
from core.paper_account_paths import build_paper_account_paths
from core.paper_manual_review_append_commit import commit_manual_review_preview
from core.notion_manual_review_status_sync import sync_manual_review_status
from scripts import (
    runbook_command_registry,
    runbook_completion_evidence,
    runbook_gate_checker,
    runbook_result,
    runbook_stage_e_evidence,
    runbook_stage_runner,
    runbook_state,
)
from tests.runbook_standard_evidence_fixtures import seed_standard_export_evidence
from tests import test_runbook_stage_e_evidence as stage_e_fixtures
from tests import test_runbook_stage_runner_stage_f as stage_f_fixtures
from core.runbook_calendar import load_market_calendar


ACCOUNT_ID = "paper_zero"
DATA_DATE = "2026-07-10"
TRADE_DATE = "2026-07-13"


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _scope_payload(state: runbook_state.RunbookState, rows: list[dict]) -> dict:
    basis = {
        "schema_version": "paper_daily_manual_review_scope.v1",
        "frozen_context": {
            "runbook_day_id": state.runbook_day_id,
            "account_id": state.frozen_context.account_id,
            "data_date": state.frozen_context.data_date,
            "trade_date": state.frozen_context.trade_date,
        },
        "action_mode": "EXECUTION",
        "sources": {},
        "manual_review_symbols": [],
        "current_open_symbols": [],
        "position_symbols": [],
        "execution_symbols": [],
        "canonical_keys": [row["canonical_key"] for row in rows],
        "rows": rows,
    }
    digest = hashlib.sha256(
        json.dumps(basis, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        **basis,
        "generated_at": "2026-07-13T00:00:00",
        "counts": {"total": len(rows)},
        "scope_sha256": digest,
    }


def _seed_zero_write_state(workspace: Path) -> Path:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    for stage_id in ("A", "GATE1", "B"):
        state = runbook_state.complete_stage(state, stage_id)
    items = [
        {"symbol": "NVDA", "action": "BUY", "quantity": 1},
        {"symbol": "TSLA", "action": "BUY", "quantity": 1},
    ]
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
            "generated_at": "2026-07-13T00:00:00Z",
            "items": items,
            "execution_intent": build_execution_intent(items),
            "fingerprints": {},
        },
    )
    commit = _write_json(
        workspace / "artifacts" / state.runbook_day_id / "stage_b" / "commit.json",
        {
            "status": "COMMITTED",
            "account_id": ACCOUNT_ID,
            "execution_date": TRADE_DATE,
            "execution_contract_version": runbook_state.EXECUTION_CONTRACT_V2,
            "committed_row_count": 0,
            "committed_trade_ids": [],
            "committed_rows": [],
        },
    )
    verification = _write_json(
        workspace / "verification_runs" / state.runbook_day_id / "latest_stage_b_verification.json",
        {
            "schema_version": "stage_b_verification.v1",
            "runner_result": "PASS",
            "runbook_day_id": state.runbook_day_id,
            "account_id": ACCOUNT_ID,
            "data_date": DATA_DATE,
            "trade_date": TRADE_DATE,
            "action_mode": "EXECUTION",
            "execution_contract_version": runbook_state.EXECUTION_CONTRACT_V2,
            "verified_no_action": False,
            "verified_zero_write": True,
            "planned_count": 2,
            "executed_count": 0,
            "partial_count": 0,
            "not_executed_count": 2,
            "committed_row_count": 0,
            "updated_count": 2,
            "failed_count": 0,
            "current_state_written": False,
            "account_snapshot_written": False,
            "position_snapshot_written": False,
        },
    )
    for name, path in (
        ("daily_plan_json", daily_plan),
        ("execution_commit_report_json", commit),
        ("stage_b_verification_json", verification),
    ):
        state = runbook_state.record_artifact(state, name, str(path), workspace)
    state_path = runbook_state.get_state_path_for_context(
        workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE
    )
    runbook_state.save_state(state, state_path)
    return state_path


def _pin_zero_review_completion_evidence(
    workspace: Path,
    state: runbook_state.RunbookState,
) -> runbook_state.RunbookState:
    scope = _scope_payload(state, [])
    scope_path = _write_json(workspace / "artifacts" / state.runbook_day_id / "stage_c" / "scope.json", scope)
    latest_c = workspace / "stage_runs" / state.runbook_day_id / "latest_C.json"
    stage_c = json.loads(latest_c.read_text(encoding="utf-8"))
    review_step = next(
        step for step in stage_c["steps"] if step["command_key"] == "export_review_template"
    )
    review_result_path = workspace / review_step["result_json_ref"]
    review_result = json.loads(review_result_path.read_text(encoding="utf-8"))
    review_result["raw_payload"].update(
        {"candidate_count": 0, "create_count": 0, "would_write": False}
    )
    review_result_path.write_text(json.dumps(review_result), encoding="utf-8")
    stage_c["raw_payload"] = {
        "action_mode": "EXECUTION",
        "verified_no_action": False,
        "verified_zero_write": True,
        "manual_review_scope_sha256": scope["scope_sha256"],
        "manual_review_scope_count": 0,
    }
    latest_c.write_text(json.dumps(stage_c), encoding="utf-8")
    verification = _write_json(
        workspace / "verification_runs" / state.runbook_day_id / "stage_b.json",
        {
            "schema_version": "stage_b_verification.v1",
            "runner_result": "PASS",
            "action_mode": "EXECUTION",
            "execution_contract_version": runbook_state.EXECUTION_CONTRACT_V2,
            "verified_no_action": False,
            "verified_zero_write": True,
            "planned_count": 2,
            "executed_count": 0,
            "partial_count": 0,
            "not_executed_count": 2,
            "committed_row_count": 0,
        },
    )
    gate = _write_json(
        workspace / "gate_runs" / state.runbook_day_id / "latest_GATE2.json",
        {
            "schema_version": "gate2_review_readiness.v1",
            "runner_result": "PASS",
            "action_mode": "EXECUTION",
            "manual_review_scope_sha256": scope["scope_sha256"],
            "manual_review_scope_count": 0,
            "candidate_count": 0,
            "required_count": 0,
            "manual_review_row_count": 0,
        },
    )
    payloads = {
        "review_preview_json": {
            "account_id": state.frozen_context.account_id,
            "review_date": state.frozen_context.trade_date,
            "candidate_count": 0,
            "fail_count": 0,
            "blocked_count": 0,
            "append_allowed": "true",
            "candidates": [],
        },
        "review_append_report_json": {
            "account_id": state.frozen_context.account_id,
            "review_date": state.frozen_context.trade_date,
            "candidate_count": 0,
            "appended_count": 0,
            "failed_count": 0,
            "rows": [],
        },
        "review_status_sync_report_json": {
            "overall_status": "SUCCESS",
            "account_id": state.frozen_context.account_id,
            "review_date": state.frozen_context.trade_date,
            "candidate_count": 0,
            "updated_count": 0,
            "failed_count": 0,
            "rows": [],
        },
    }
    artifacts = {
        "manual_review_scope_json": scope_path,
        "stage_b_verification_json": verification,
        "gate2_readiness_json": gate,
    }
    for name, payload in payloads.items():
        artifacts[name] = _write_json(
            workspace / "artifacts" / state.runbook_day_id / "stage_d" / f"{name}.json",
            payload,
        )
    for name, path in artifacts.items():
        state = runbook_state.record_artifact(state, name, str(path), workspace)

    command_results = []
    for command_key in ("review_append", "sync_review_status"):
        command = runbook_command_registry.get_command(command_key)
        result = runbook_result.create_command_result(
            state,
            command,
            "PASS",
            "PASS",
            raw_payload={"candidate_count": 0, "updated_count": 0, "appended_count": 0},
            process={"executed": True, "exit_code": 0, "duration_ms": 1},
            workspace=workspace,
        )
        result_path, _ = runbook_result.write_command_result(workspace, state, command, result)
        command_results.append(json.loads(result_path.read_text(encoding="utf-8")))
    runbook_result.write_stage_summary(
        workspace,
        state,
        runbook_result.create_stage_summary(state, "D", command_results),
    )
    return state


def test_stage_c_accepts_verified_v2_zero_write_and_uses_prior_current_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state_path = _seed_zero_write_state(workspace)
    account_root = tmp_path / "account"
    prior_state = _write_json(
        account_root / "paper_current_state_20260710.json",
        {
            "current_symbols": ["AAPL", "MSFT"],
            "shares": {"AAPL": 3, "MSFT": 4},
        },
    )
    account_paths = SimpleNamespace(
        account_id=ACCOUNT_ID,
        root=account_root,
        execution_log_path=account_root / "paper_execution_log.csv",
        current_state_snapshot_path=lambda date: account_root / f"paper_current_state_{str(date).replace('-', '')}.json",
    )
    monkeypatch.setattr(runbook_stage_runner, "build_paper_account_paths", lambda *args, **kwargs: account_paths)

    state = runbook_state.load_state(state_path)
    evidence = runbook_stage_runner._stage_c_evidence_context(state, workspace)
    scope = runbook_stage_runner._build_stage_c_scope(workspace, state)

    assert evidence["verified_zero_write"] is True
    assert scope["position_symbols"] == ["AAPL", "MSFT"]
    assert scope["execution_symbols"] == []
    assert scope["counts"]["total"] == 2
    assert scope["sources"]["current_state_json"]["path"] == str(prior_state)


def test_stage_c_runs_for_verified_zero_write_with_empty_holdings(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state_path = _seed_zero_write_state(workspace)
    account_root = tmp_path / "account"
    _write_json(
        account_root / "paper_current_state_20260710.json",
        {"current_symbols": [], "shares": {}},
    )
    account_paths = SimpleNamespace(account_id=ACCOUNT_ID, root=account_root)
    monkeypatch.setattr(
        runbook_stage_runner,
        "build_paper_account_paths",
        lambda *args, **kwargs: account_paths,
    )

    scope_cache: dict = {}

    def fake_run(argv, cwd, timeout_sec):
        output_root = tmp_path / "repo_outputs"
        if "paper.py" in " ".join(argv):
            scope_path = Path(argv[argv.index("--scope-manifest") + 1])
            scope_cache.update(json.loads(scope_path.read_text(encoding="utf-8")))
            paths = {
                "daily_review_report_md": output_root / "reports" / "review.md",
                "report_index_md": output_root / "reports" / "index.md",
                "manual_review_template_csv": output_root / "reviews" / "template.csv",
                "manual_review_template_md": output_root / "reviews" / "template.md",
                "validation_report_md": output_root / "reviews" / "validation.md",
                "validation_issues_csv": output_root / "reviews" / "issues.csv",
            }
            for name, path in paths.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    "review_date,symbol,question_id\n" if name.endswith("csv") else name + "\n",
                    encoding="utf-8",
                )
            payload = {
                "status": "PASS",
                "validation_result": "PASS",
                **{key: str(path) for key, path in paths.items()},
                "manual_review_scope_sha256": scope_cache["scope_sha256"],
                "manual_review_scope_count": 0,
            }
        else:
            template = output_root / "reviews" / "template.csv"
            payload = {
                "target": "manual_review_template",
                "account_id": ACCOUNT_ID,
                "review_date": TRADE_DATE,
                "candidate_count": 0,
                "create_count": 0,
                "update_count": 0,
                "skip_count": 0,
                "failed_count": 0,
                "dry_run": False,
                "would_write": False,
                "source_template_path": str(template),
                "candidates": [],
            }
        return {
            "executed": True,
            "exit_code": 0,
            "duration_ms": 1,
            "stdout": json.dumps(payload),
            "stderr": "",
        }

    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", fake_run)
    result = runbook_stage_runner.run_stage_c(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    details = [
        json.loads((workspace / ref).read_text(encoding="utf-8"))
        for ref in result["command_results"]
    ]
    assert result["runner_result"] == "PASS", [
        (item["command_key"], item["runner_result"], item["summary"], item["raw_payload"])
        for item in details
    ]
    state = runbook_state.load_state(state_path)
    scope = json.loads((workspace / state.artifacts["manual_review_scope_json"]).read_text(encoding="utf-8"))
    assert scope["counts"]["total"] == 0
    assert scope["rows"] == []
    assert state.stage_status["C"] == "PASS"


@pytest.mark.parametrize(
    "mutation",
    ("not_verified", "count_mismatch", "unsupported_contract"),
)
def test_stage_c_zero_write_evidence_fails_closed(tmp_path: Path, mutation: str) -> None:
    state_path = _seed_zero_write_state(tmp_path)
    state = runbook_state.load_state(state_path)
    verification_path = tmp_path / state.artifacts["stage_b_verification_json"]
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    if mutation == "not_verified":
        verification["verified_zero_write"] = False
    elif mutation == "count_mismatch":
        verification["not_executed_count"] = 1
    else:
        verification["execution_contract_version"] = "execution_reconciliation_preview.v999"
    verification_path.write_text(json.dumps(verification), encoding="utf-8")

    assert (
        runbook_stage_runner._stage_c_precondition_error(state, tmp_path)
        == "stage_b_verification_required"
    )


def test_gate2_passes_verified_empty_standard_scope(tmp_path: Path) -> None:
    state_path = _seed_zero_write_state(tmp_path)
    state = runbook_state.load_state(state_path)
    state = runbook_state.complete_stage(state, "C")
    scope = _scope_payload(state, [])
    scope_path = _write_json(tmp_path / "artifacts" / state.runbook_day_id / "stage_c" / "scope.json", scope)
    template = tmp_path / "artifacts" / state.runbook_day_id / "review_prep" / "template.csv"
    template.parent.mkdir(parents=True, exist_ok=True)
    template.write_text("review_date,symbol,question_id\n", encoding="utf-8")
    stage_c_summary = _write_json(
        tmp_path / "stage_runs" / state.runbook_day_id / "stage_c.json",
        {
            "schema_version": "runbook_stage_summary.v1",
            "runner_result": "PASS",
            "stage_id": "C",
            "runbook_day_id": state.runbook_day_id,
            "frozen_context": {
                "account_id": ACCOUNT_ID,
                "data_date": DATA_DATE,
                "trade_date": TRADE_DATE,
            },
            "raw_payload": {
                "action_mode": "EXECUTION",
                "verified_no_action": False,
                "manual_review_scope_sha256": scope["scope_sha256"],
                "manual_review_scope_count": 0,
            },
        },
    )
    for name, path in (
        ("manual_review_scope_json", scope_path),
        ("manual_review_template_csv", template),
        ("stage_c_summary_json", stage_c_summary),
    ):
        state = runbook_state.record_artifact(state, name, str(path), tmp_path)
    runbook_state.save_state(state, state_path)

    result = runbook_gate_checker.check_gate2_readiness(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, row_fetcher=lambda _: []
    )

    assert result["runner_result"] == "PASS"
    assert result["action_mode"] == "EXECUTION"
    assert result["manual_review_scope_count"] == 0
    assert result["manual_review_scope_sha256"] == scope["scope_sha256"]


def test_stage_d_zero_preview_validator_requires_and_accepts_pinned_empty_scope(tmp_path: Path) -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    scope = _scope_payload(state, [])
    scope_path = _write_json(tmp_path / "scope.json", scope)
    state = runbook_state.record_artifact(state, "manual_review_scope_json", str(scope_path), tmp_path)
    preview_json = _write_json(tmp_path / "preview.json", {})
    preview_md = tmp_path / "preview.md"
    preview_md.write_text("zero review preview\n", encoding="utf-8")
    payload = {
        "account_id": ACCOUNT_ID,
        "review_date": TRADE_DATE,
        "candidate_count": 0,
        "fail_count": 0,
        "blocked_count": 0,
        "append_allowed": "true",
        "candidates": [],
        "json_path": str(preview_json),
        "markdown_path": str(preview_md),
    }

    assert runbook_stage_runner._validate_review_preview_payload(
        payload, state, tmp_path
    )["runner_result"] == "PASS"


def test_zero_review_commit_writes_only_evidence_and_is_deterministic(tmp_path: Path) -> None:
    preview = _write_json(
        tmp_path / "preview.json",
        {
            "account_id": ACCOUNT_ID,
            "review_date": TRADE_DATE,
            "candidate_count": 0,
            "fail_count": 0,
            "append_allowed": "true",
            "candidates": [],
        },
    )
    review_log = tmp_path / "paper_manual_review_log.csv"
    review_log.write_text("review_date,symbol,question_id\n", encoding="utf-8")
    before = review_log.read_bytes()
    account_paths = build_paper_account_paths(
        ACCOUNT_ID,
        account_root=tmp_path / "account",
        create=True,
    )

    first = commit_manual_review_preview(
        review_date=TRADE_DATE,
        preview_json_path=preview,
        review_log_path=review_log,
        reports_dir=tmp_path / "reports",
        account_paths=account_paths,
    )
    first_payload = Path(first.commit_json_path).read_bytes()
    second = commit_manual_review_preview(
        review_date=TRADE_DATE,
        preview_json_path=preview,
        review_log_path=review_log,
        reports_dir=tmp_path / "reports",
        account_paths=account_paths,
    )

    assert first.appended_count == second.appended_count == 0
    assert review_log.read_bytes() == before
    assert Path(second.commit_json_path).read_bytes() == first_payload


def test_zero_review_status_sync_makes_no_notion_calls(tmp_path: Path) -> None:
    report = _write_json(
        tmp_path / "commit.json",
        {
            "account_id": ACCOUNT_ID,
            "review_date": TRADE_DATE,
            "candidate_count": 0,
            "appended_count": 0,
            "failed_count": 0,
            "rows": [],
        },
    )

    result = sync_manual_review_status(
        client=None,
        mapping_root={"manual_reviews": {}},
        review_date=TRADE_DATE,
        commit_report_path=report,
        dry_run=False,
        account_id=ACCOUNT_ID,
    )

    assert result.overall_status == "SUCCESS"
    assert result.candidate_count == 0
    assert result.updated_count == 0
    assert result.failed_count == 0
    assert result.rows == []


def test_standard_completion_context_requires_positive_zero_review_evidence(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    state = seed_standard_export_evidence(
        workspace,
        state,
        review_candidate_count=0,
    )
    scope = _scope_payload(state, [])
    scope_path = _write_json(workspace / "artifacts" / state.runbook_day_id / "stage_c" / "scope.json", scope)
    stage_c_summary_path = workspace / "stage_runs" / state.runbook_day_id / "latest_C.json"
    stage_c_summary = json.loads(stage_c_summary_path.read_text(encoding="utf-8"))
    stage_c_summary["raw_payload"] = {
        "action_mode": "EXECUTION",
        "verified_no_action": False,
        "verified_zero_write": True,
        "manual_review_scope_sha256": scope["scope_sha256"],
        "manual_review_scope_count": 0,
    }
    stage_c_summary_path.write_text(json.dumps(stage_c_summary), encoding="utf-8")
    verification = _write_json(
        workspace / "verification_runs" / state.runbook_day_id / "stage_b.json",
        {
            "schema_version": "stage_b_verification.v1",
            "runner_result": "PASS",
            "action_mode": "EXECUTION",
            "execution_contract_version": runbook_state.EXECUTION_CONTRACT_V2,
            "verified_no_action": False,
            "verified_zero_write": True,
            "planned_count": 2,
            "executed_count": 0,
            "partial_count": 0,
            "not_executed_count": 2,
            "committed_row_count": 0,
        },
    )
    gate = _write_json(
        workspace / "gate_runs" / state.runbook_day_id / "latest_GATE2.json",
        {
            "schema_version": "gate2_review_readiness.v1",
            "runner_result": "PASS",
            "action_mode": "EXECUTION",
            "manual_review_scope_sha256": scope["scope_sha256"],
            "manual_review_scope_count": 0,
            "candidate_count": 0,
            "required_count": 0,
            "manual_review_row_count": 0,
        },
    )
    preview = _write_json(
        workspace / "artifacts" / state.runbook_day_id / "stage_d" / "preview.json",
        {
            "account_id": ACCOUNT_ID,
            "review_date": TRADE_DATE,
            "candidate_count": 0,
            "fail_count": 0,
            "blocked_count": 0,
            "append_allowed": "true",
            "candidates": [],
        },
    )
    append = _write_json(
        workspace / "artifacts" / state.runbook_day_id / "stage_d" / "append.json",
        {
            "account_id": ACCOUNT_ID,
            "review_date": TRADE_DATE,
            "candidate_count": 0,
            "appended_count": 0,
            "failed_count": 0,
            "rows": [],
        },
    )
    sync = _write_json(
        workspace / "artifacts" / state.runbook_day_id / "stage_d" / "sync.json",
        {
            "overall_status": "SUCCESS",
            "account_id": ACCOUNT_ID,
            "review_date": TRADE_DATE,
            "candidate_count": 0,
            "updated_count": 0,
            "failed_count": 0,
            "rows": [],
        },
    )
    for name, path in (
        ("manual_review_scope_json", scope_path),
        ("stage_b_verification_json", verification),
        ("gate2_readiness_json", gate),
        ("review_preview_json", preview),
        ("review_append_report_json", append),
        ("review_status_sync_report_json", sync),
    ):
        state = runbook_state.record_artifact(state, name, str(path), workspace)

    command_results = []
    for command_key, payload in (
        ("review_append", {"appended_count": 0}),
        ("sync_review_status", {"candidate_count": 0, "updated_count": 0}),
    ):
        command = runbook_command_registry.get_command(command_key)
        result = runbook_result.create_command_result(
            state,
            command,
            "PASS",
            "PASS",
            raw_payload=payload,
            process={"executed": True, "exit_code": 0, "duration_ms": 1},
            workspace=workspace,
        )
        result_path, _ = runbook_result.write_command_result(workspace, state, command, result)
        command_results.append(json.loads(result_path.read_text(encoding="utf-8")))
    summary = runbook_result.create_stage_summary(state, "D", command_results)
    runbook_result.write_stage_summary(workspace, state, summary)

    context = runbook_completion_evidence.build_standard_completion_context(workspace, state)

    assert context["action_mode"] == "STANDARD"
    assert context["zero_review_evidence"]["required_review_count"] == 0
    assert context["zero_review_evidence"]["verified_zero_review"] is True

    gate_payload = json.loads(gate.read_text(encoding="utf-8"))
    gate_payload["manual_review_scope_sha256"] = "0" * 64
    gate.write_text(json.dumps(gate_payload), encoding="utf-8")
    try:
        runbook_completion_evidence.build_standard_completion_context(workspace, state)
    except runbook_completion_evidence.CompletionEvidenceError as exc:
        assert exc.reason == "standard_zero_review_gate2_invalid"
    else:
        raise AssertionError("mismatched Gate 2 evidence must fail closed")


def test_zero_required_review_standard_is_review_done_only_with_completion_evidence(
    tmp_path: Path,
) -> None:
    account_root, legacy_root = stage_e_fixtures._build_terminal_account(tmp_path)
    for path in (
        account_root / "reviews" / "paper_manual_review_log_template.csv",
        account_root / "reviews" / "paper_manual_review_log.csv",
    ):
        header = path.read_text(encoding="utf-8-sig").splitlines()[0]
        path.write_text(header + "\n", encoding="utf-8")

    baseline = paper_daily_ops_orchestrator.build_daily_ops_status(
        account_id=stage_e_fixtures.ACCOUNT_ID,
        data_date=stage_e_fixtures.DATA_DATE,
        trade_date=stage_e_fixtures.TRADE_DATE,
        account_root=account_root,
        legacy_root=legacy_root,
    )
    assert baseline["workflow_status"] != "REVIEW_DONE"

    digest = "a" * 64
    authoritative = {
        name: {
            "stage_id": stage_id,
            "step_id": step_id,
            "command_key": command_key,
            "summary_ref": f"stage_runs/{stage_id}.json",
            "summary_sha256": digest,
            "result_ref": f"command_runs/{command_key}.json",
            "result_sha256": digest,
        }
        for name, (stage_id, step_id, command_key) in runbook_completion_evidence.STANDARD_EXPORT_COMMANDS.items()
    }
    completion_context = {
        "schema_version": runbook_completion_evidence.STANDARD_COMPLETION_SCHEMA_VERSION,
        "runbook_day_id": (
            f"{stage_e_fixtures.ACCOUNT_ID}_{stage_e_fixtures.DATA_DATE}_{stage_e_fixtures.TRADE_DATE}"
        ),
        "account_id": stage_e_fixtures.ACCOUNT_ID,
        "data_date": stage_e_fixtures.DATA_DATE,
        "trade_date": stage_e_fixtures.TRADE_DATE,
        "action_mode": "STANDARD",
        "authoritative_stages": authoritative,
        "zero_review_evidence": {
            "required_review_count": 0,
            "verified_zero_review": True,
            "manual_review_scope_ref": "artifacts/scope.json",
            "manual_review_scope_sha256": digest,
            "stage_b_verification_ref": "verification_runs/stage_b.json",
            "stage_b_verification_sha256": digest,
            "stage_c_summary_ref": "stage_runs/C.json",
            "stage_c_summary_sha256": digest,
            "gate2_ref": "gate_runs/gate2.json",
            "gate2_sha256": digest,
            "stage_d_summary_ref": "stage_runs/D.json",
            "stage_d_summary_sha256": digest,
            "artifacts": {
                name: {"ref": f"artifacts/{name}.json", "sha256": digest}
                for name in ("review_preview", "review_append", "review_status_sync")
            },
        },
    }
    result = paper_daily_ops_orchestrator.build_daily_ops_status(
        account_id=stage_e_fixtures.ACCOUNT_ID,
        data_date=stage_e_fixtures.DATA_DATE,
        trade_date=stage_e_fixtures.TRADE_DATE,
        account_root=account_root,
        legacy_root=legacy_root,
        completion_context=completion_context,
    )

    assert result["completion_mode"] == "STANDARD"
    assert result["workflow_status"] == "REVIEW_DONE"
    assert result["overall_status"] == "PASS"
    assert result["summary"]["terminal"] is True
    assert result["next_command"] is None


def test_stage_d_zero_review_preview_append_sync_pass_and_rerun_writes_nothing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state_path = _seed_zero_write_state(workspace)
    state = runbook_state.load_state(state_path)
    state = runbook_state.complete_stage(state, "C")
    state = runbook_state.complete_stage(state, "GATE2")
    scope = _scope_payload(state, [])
    scope_path = _write_json(workspace / "artifacts" / state.runbook_day_id / "stage_c" / "scope.json", scope)
    gate = _write_json(
        workspace / "gate_runs" / state.runbook_day_id / "latest_GATE2.json",
        {
            "schema_version": "gate2_review_readiness.v1",
            "runner_result": "PASS",
            "action_mode": "EXECUTION",
            "manual_review_scope_sha256": scope["scope_sha256"],
            "manual_review_scope_count": 0,
            "candidate_count": 0,
            "required_count": 0,
            "manual_review_row_count": 0,
        },
    )
    template = workspace / "artifacts" / state.runbook_day_id / "review_prep" / "template.csv"
    template.parent.mkdir(parents=True, exist_ok=True)
    template.write_text("review_date,symbol,question_id\n", encoding="utf-8")
    for name, path in (
        ("manual_review_scope_json", scope_path),
        ("gate2_readiness_json", gate),
        ("manual_review_template_csv", template),
    ):
        state = runbook_state.record_artifact(state, name, str(path), workspace)
    runbook_state.save_state(state, state_path)

    calls: list[str] = []

    def fake_run(argv, cwd, timeout_sec):
        joined = " ".join(argv)
        if "--preview" in argv:
            command_key = "preview"
            json_path = tmp_path / "repo" / "preview.json"
            md_path = tmp_path / "repo" / "preview.md"
            payload = {
                "account_id": ACCOUNT_ID,
                "review_date": TRADE_DATE,
                "candidate_count": 0,
                "pass_count": 0,
                "warning_count": 0,
                "fail_count": 0,
                "blocked_count": 0,
                "append_allowed": "true",
                "duplicate_candidates": [],
                "candidates": [],
                "json_path": str(json_path),
                "markdown_path": str(md_path),
            }
        elif "--commit" in argv:
            command_key = "append"
            json_path = tmp_path / "repo" / "append.json"
            md_path = tmp_path / "repo" / "append.md"
            payload = {
                "status": "COMMITTED",
                "account_id": ACCOUNT_ID,
                "review_date": TRADE_DATE,
                "appended_count": 0,
                "skipped_count": 0,
                "failed_count": 0,
                "commit_json_path": str(json_path),
                "commit_markdown_path": str(md_path),
            }
        elif "sync_notion_review_status.py" in joined:
            command_key = "sync"
            json_path = tmp_path / "repo" / "sync.json"
            md_path = tmp_path / "repo" / "sync.md"
            payload = {
                "overall_status": "SUCCESS",
                "account_id": ACCOUNT_ID,
                "review_date": TRADE_DATE,
                "candidate_count": 0,
                "updated_count": 0,
                "skipped_count": 0,
                "failed_count": 0,
                "sync_json_path": str(json_path),
                "sync_markdown_path": str(md_path),
            }
        else:
            raise AssertionError(f"unexpected command: {joined}")
        calls.append(command_key)
        _write_json(json_path, {**payload, "rows": []})
        md_path.write_text(command_key + "\n", encoding="utf-8")
        return {
            "executed": True,
            "exit_code": 0,
            "duration_ms": 1,
            "stdout": json.dumps(payload),
            "stderr": "",
        }

    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", fake_run)
    preview_result = runbook_stage_runner.run_stage_d_preview(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )
    append_result = runbook_stage_runner.run_stage_d_append(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )
    call_count = len(calls)
    rerun = runbook_stage_runner.run_stage_d_append(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert preview_result["runner_result"] == "PASS"
    assert append_result["runner_result"] == "PASS"
    assert calls == ["preview", "append", "sync"]
    assert len(calls) == call_count
    assert rerun["runner_result"] == "BLOCKED"
    assert rerun["reason"] == "stage_d_already_pass"
    loaded = runbook_state.load_state(state_path)
    assert loaded.stage_status["D"] == "PASS"
    assert loaded.artifacts.get("stage_d_no_action_json") is None


def test_zero_review_standard_stage_e_evidence_stage_f_and_rollover_pass(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    account_root = tmp_path / "account"
    workspace.mkdir()
    state_path = stage_f_fixtures._seed_stage_e_pass(workspace, account_root)
    state = runbook_state.load_state(state_path)
    state = _pin_zero_review_completion_evidence(workspace, state)

    with (account_root / "paper_execution_log.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        csv.DictWriter(handle, fieldnames=PAPER_EXECUTION_LOG_COLUMNS).writeheader()
    with (account_root / "reviews" / "paper_manual_review_log.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        csv.DictWriter(handle, fieldnames=PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS).writeheader()

    manifest = runbook_completion_evidence.build_runbook_completion_manifest(
        workspace,
        state,
        account_root,
    )
    manifest_path = workspace / state.artifacts["completion_manifest_json"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    final_path = workspace / state.artifacts["final_status_report_json"]
    final_wrapper = json.loads(final_path.read_text(encoding="utf-8"))
    final_wrapper["raw_payload"]["runbook_completion_evidence"] = (
        runbook_completion_evidence.build_standard_completion_context(workspace, state)
    )
    final_wrapper["raw_payload"]["completion_manifest"] = manifest
    final_path.write_text(json.dumps(final_wrapper), encoding="utf-8")
    runbook_state.save_state(state, state_path)

    assert runbook_stage_e_evidence.validate_stage_e_completion_evidence(
        workspace,
        state,
        account_root,
    )["valid"] is True

    stage_f_fixtures._patch_account_root(monkeypatch, account_root)
    calls: list[list[str]] = []
    monkeypatch.setattr(
        runbook_stage_runner,
        "run_allowlisted_command",
        stage_f_fixtures._fake_stage_f_run(account_root, calls),
    )
    stage_f = runbook_stage_runner.run_stage_f(
        workspace,
        stage_f_fixtures.ACCOUNT_ID,
        stage_f_fixtures.DATA_DATE,
        stage_f_fixtures.TRADE_DATE,
        confirm_paper_test=True,
    )
    assert stage_f["runner_result"] == "PASS"

    monkeypatch.setattr(
        runbook_day_rollover,
        "build_paper_account_paths",
        lambda account_id, create=False: SimpleNamespace(account_id=account_id, root=account_root),
    )
    rollover = runbook_day_rollover.preview_rollover(
        workspace,
        stage_f_fixtures.ACCOUNT_ID,
        load_market_calendar(),
        confirm_paper_test=True,
    )
    assert rollover["runner_result"] == "PASS"

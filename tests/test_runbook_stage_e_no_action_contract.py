from __future__ import annotations

from contextlib import redirect_stdout
import csv
import io
import json
from pathlib import Path

import pytest

from core import runbook_day_rollover as rollover_core
from core.paper_execution_intent import build_execution_intent
from core.paper_account_snapshot import PAPER_ACCOUNT_SNAPSHOT_COLUMNS
from core.paper_execution_log import PAPER_EXECUTION_LOG_COLUMNS
from core.paper_manual_review_log_template import PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS
from core.paper_position_snapshot import PAPER_POSITION_SNAPSHOT_COLUMNS
from core.paper_daily_ops_orchestrator import build_daily_ops_status
from core.runbook_calendar import load_market_calendar
from core.runbook_day_rollover import preview_rollover
from scripts import paper_daily_ops
from scripts import runbook_command_registry
from scripts import runbook_completion_evidence
from scripts import runbook_result
from scripts import runbook_stage_e_evidence
from scripts import runbook_state
from scripts.runbook_no_action import build_no_action_completion_context
from tests import test_runbook_stage_runner_stage_d_no_action as no_action_fixtures
from tests import test_runbook_stage_runner_stage_f as stage_f_fixtures


ACCOUNT_ID = no_action_fixtures.ACCOUNT_ID
DATA_DATE = no_action_fixtures.DATA_DATE
TRADE_DATE = no_action_fixtures.TRADE_DATE


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, object]] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows or [])


def _build_actual_no_action_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    workspace = tmp_path / "workspace"
    account_root = tmp_path / "paper_accounts" / ACCOUNT_ID
    legacy_root = tmp_path / "paper_test"
    workspace.mkdir()
    for root in (account_root, legacy_root):
        (root / "reports").mkdir(parents=True)
        (root / "reviews").mkdir()
        (root / "config_snapshots").mkdir()

    state = no_action_fixtures._complete_no_action_stage_d(workspace)
    daily_plan_source = workspace / state.artifacts["daily_plan_json"]
    daily_plan_json = account_root / "daily_action_plan_20260702.json"
    daily_plan_json.write_bytes(daily_plan_source.read_bytes())
    _write(account_root / "daily_action_plan_20260702.md", "# verified no action plan\n")
    _write(account_root / "paper_current_state_20260702.json", json.dumps({"positions": {}}))
    _write_csv(
        account_root / "paper_account_snapshot.csv",
        PAPER_ACCOUNT_SNAPSHOT_COLUMNS,
        [{"account_id": ACCOUNT_ID, "snapshot_date": TRADE_DATE, "cash": 100, "total_equity_market_value": 100, "unrealized_pnl": 0, "position_count": 0}],
    )
    _write_csv(account_root / "paper_position_snapshot.csv", PAPER_POSITION_SNAPSHOT_COLUMNS)
    _write_csv(account_root / "paper_execution_log.csv", PAPER_EXECUTION_LOG_COLUMNS)
    _write_csv(account_root / "reviews" / "paper_manual_review_log.csv", PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS)
    eod_path = workspace / "artifacts" / state.runbook_day_id / "stage_e" / "eod_commit.json"
    eod_path.parent.mkdir(parents=True, exist_ok=True)
    eod_path.write_text(
        json.dumps(
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
            }
        ),
        encoding="utf-8",
    )
    state = runbook_state.record_artifact(state, "eod_commit_report_json", str(eod_path), workspace)
    runbook_state.save_state(
        state,
        runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE),
    )
    return workspace, account_root, legacy_root


def test_actual_no_action_without_verified_completion_context_is_not_terminal(tmp_path: Path) -> None:
    _, account_root, legacy_root = _build_actual_no_action_fixture(tmp_path)

    payload = build_daily_ops_status(
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        account_root=account_root,
        legacy_root=legacy_root,
    )

    characterization = {
        "overall_status": payload["overall_status"],
        "workflow_status": payload["workflow_status"],
        "summary": payload["summary"],
        "blockers": payload["blockers"],
        "warnings": payload["warnings"],
        "stage_counts": payload["stage_counts"],
        "stages": {stage["stage_name"]: stage["status"] for stage in payload["stages"]},
        "next_command": payload["next_command"],
        "next_action": payload["next_action"],
    }
    print(json.dumps(characterization, ensure_ascii=False, sort_keys=True))
    assert payload["workflow_status"] == "UNKNOWN_OR_INCOMPLETE"
    assert payload["summary"]["terminal"] is False
    assert payload["summary"]["needs_attention"] is True
    assert payload["overall_status"] == "BLOCKED"


def _state(workspace: Path) -> runbook_state.RunbookState:
    return runbook_state.load_state(
        runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    )


def test_actual_no_action_producer_cli_wrapper_and_stored_validator_pass(tmp_path: Path) -> None:
    workspace, account_root, legacy_root = _build_actual_no_action_fixture(tmp_path)
    state = _state(workspace)
    context = build_no_action_completion_context(workspace, state, account_root=account_root)

    direct = build_daily_ops_status(
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        account_root=account_root,
        legacy_root=legacy_root,
        completion_context=context,
    )
    direct["completion_manifest"] = runbook_completion_evidence.build_runbook_completion_manifest(
        workspace, state, account_root
    )
    assert direct["overall_status"] == "PASS"
    assert direct["workflow_status"] == "UNKNOWN_OR_INCOMPLETE"
    assert direct["completion_mode"] == "NO_ACTION"
    assert direct["completion_proof"] == context
    assert direct["summary"]["terminal"] is True
    assert direct["summary"]["needs_attention"] is False
    assert direct["blockers"] == direct["warnings"] == []
    assert direct["next_command"] is direct["next_action"] is None
    assert all(stage["status"] == "DONE" for stage in direct["stages"])
    assert direct["reconciliation_summary"]["conflict_count"] == 0
    assert direct["operator_summary"]["terminal"] is True
    assert direct["operator_summary"]["recommended_operator_action"] == "NONE"
    assert runbook_stage_e_evidence.validate_final_status_payload(direct, state, workspace, account_root) == []

    stdout = io.StringIO()
    state_path = runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    with redirect_stdout(stdout):
        exit_code = paper_daily_ops.main(
            [
                "status",
                "--account-id",
                ACCOUNT_ID,
                "--data-date",
                DATA_DATE,
                "--trade-date",
                TRADE_DATE,
                "--account-root",
                str(account_root),
                "--legacy-root",
                str(legacy_root),
                "--runbook-workspace",
                str(workspace),
                "--runbook-state-json",
                str(state_path),
                "--json",
            ]
        )
    assert exit_code == 0
    cli_payload = json.loads(stdout.getvalue())
    assert cli_payload == direct

    wrapper = runbook_result.create_command_result(
        state,
        runbook_command_registry.get_command("final_status"),
        "PASS",
        "Final status is PASS.",
        raw_payload=cli_payload,
        process={"executed": True, "exit_code": 0, "duration_ms": 1},
        workspace=workspace,
    )
    final_path = workspace / "command_runs" / state.runbook_day_id / "final_status.json"
    final_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.write_text(json.dumps(wrapper), encoding="utf-8")
    state = runbook_state.record_artifact(state, "final_status_report_json", str(final_path), workspace)
    manifest_path = workspace / "completion_manifests" / f"{state.runbook_day_id}.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(cli_payload["completion_manifest"]), encoding="utf-8")
    state = runbook_state.record_artifact(state, "completion_manifest_json", str(manifest_path), workspace)
    assert runbook_stage_e_evidence.validate_stored_final_status(workspace, state, account_root) == {
        "valid": True,
        "blockers": [],
    }


def test_actual_no_action_stage_e_stage_f_and_rollover_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    account_root = tmp_path / "paper_account"
    workspace.mkdir()
    no_action_fixtures._complete_no_action_stage_d(workspace)
    stage_e_calls: list[list[str]] = []
    monkeypatch.setattr(
        no_action_fixtures.runbook_stage_runner,
        "build_paper_account_paths",
        lambda account_id, create=False: type("Paths", (), {"account_id": account_id, "root": account_root})(),
    )
    monkeypatch.setattr(
        no_action_fixtures.runbook_stage_runner,
        "run_allowlisted_command",
        no_action_fixtures._fake_no_action_stage_e_run(
            workspace,
            account_root,
            stage_e_calls,
            position_count=0,
        ),
    )

    stage_e = no_action_fixtures.runbook_stage_runner.run_stage_e(
        workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True
    )
    assert stage_e["runner_result"] == "PASS"
    assert len(stage_e_calls) == 3
    state = _state(workspace)
    final_wrapper = json.loads((workspace / state.artifacts["final_status_report_json"]).read_text(encoding="utf-8"))
    assert final_wrapper["raw_payload"]["completion_mode"] == "NO_ACTION"
    assert final_wrapper["raw_payload"]["summary"]["terminal"] is True

    monkeypatch.setattr(stage_f_fixtures, "ACCOUNT_ID", ACCOUNT_ID)
    monkeypatch.setattr(
        rollover_core,
        "build_paper_account_paths",
        lambda account_id, create=False: type("Paths", (), {"root": account_root})(),
    )
    stage_f_calls: list[list[str]] = []
    monkeypatch.setattr(
        no_action_fixtures.runbook_stage_runner,
        "run_allowlisted_command",
        stage_f_fixtures._fake_stage_f_run(
            account_root,
            stage_f_calls,
            benchmark_account_id=ACCOUNT_ID,
            benchmark_date=TRADE_DATE,
        ),
    )
    stage_f = no_action_fixtures.runbook_stage_runner.run_stage_f(
        workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True
    )
    assert stage_f["runner_result"] == "PASS", stage_f
    assert [item["command_key"] for item in stage_f["rendered_commands"]] == [
        "benchmark_generate",
        "account_snapshot_notion_upsert",
        "benchmark_report_notion_upsert",
    ]
    assert len(stage_f_calls) == 3
    assert all("paper.py eod" not in " ".join(call) for call in stage_f_calls)

    before = {path: path.read_bytes() for path in workspace.rglob("*") if path.is_file()}
    rollover = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)
    assert rollover["runner_result"] == "PASS"
    assert rollover["safe_to_prepare"] is True
    assert {path: path.read_bytes() for path in workspace.rglob("*") if path.is_file()} == before


@pytest.mark.parametrize(
    ("artifact", "field", "value"),
    [
        ("stage_d_no_action_json", "schema_version", "stage_d_no_action.v0"),
        ("stage_d_no_action_json", "runbook_day_id", "wrong_day"),
        ("stage_d_no_action_json", "account_id", "paper_other"),
        ("stage_d_no_action_json", "data_date", "2026-06-30"),
        ("stage_d_no_action_json", "trade_date", "2026-07-03"),
        ("stage_d_no_action_json", "verified_no_action", False),
        ("stage_d_no_action_json", "action_mode", "EXECUTION"),
        ("stage_d_no_action_json", "candidate_count", 1),
        ("gate2_readiness_json", "review_required", True),
        ("gate2_readiness_json", "manual_review_row_count", 1),
        ("stage_b_no_action_json", "candidate_execution_count", 1),
        ("stage_b_no_action_json", "execution_required", True),
    ],
)
def test_invalid_no_action_proof_fails_closed(
    tmp_path: Path,
    artifact: str,
    field: str,
    value: object,
) -> None:
    workspace, account_root, _ = _build_actual_no_action_fixture(tmp_path)
    state = _state(workspace)
    path = workspace / state.artifacts[artifact]
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[field] = value
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        build_no_action_completion_context(workspace, state, account_root=account_root)


def test_missing_malformed_outside_and_hash_mismatched_proof_fail_closed(tmp_path: Path) -> None:
    workspace, account_root, _ = _build_actual_no_action_fixture(tmp_path)
    state = _state(workspace)

    missing_state = runbook_state.load_state(
        runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    )
    missing_state.artifacts.pop("stage_d_no_action_json")
    with pytest.raises(ValueError):
        build_no_action_completion_context(workspace, missing_state, account_root=account_root)

    evidence_path = workspace / state.artifacts["stage_d_no_action_json"]
    original = evidence_path.read_bytes()
    evidence_path.write_text("{invalid", encoding="utf-8")
    with pytest.raises(ValueError):
        build_no_action_completion_context(workspace, state, account_root=account_root)
    evidence_path.write_bytes(original)

    outside_state = _state(workspace)
    outside_state.artifacts["stage_d_no_action_json"] = str(tmp_path / "outside.json")
    with pytest.raises(ValueError, match="outside workspace"):
        build_no_action_completion_context(workspace, outside_state, account_root=account_root)

    account_plan = account_root / "daily_action_plan_20260702.json"
    account_plan.write_text(account_plan.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        build_no_action_completion_context(workspace, state, account_root=account_root)


def test_required_sync_artifact_prevents_no_action_completion(tmp_path: Path) -> None:
    workspace, account_root, _ = _build_actual_no_action_fixture(tmp_path)
    state = _state(workspace)
    state.artifacts["review_status_sync_report_json"] = "command_runs/required_sync.json"
    with pytest.raises(ValueError):
        build_no_action_completion_context(workspace, state, account_root=account_root)


def test_ordinary_committed_incomplete_path_is_not_no_action_terminal(tmp_path: Path) -> None:
    _, account_root, legacy_root = _build_actual_no_action_fixture(tmp_path)
    plan_path = account_root / "daily_action_plan_20260702.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["items"] = [{"symbol": "AAPL", "action": "BUY", "quantity": 1}]
    plan["execution_intent"] = build_execution_intent(plan["items"])
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    _write(account_root / "paper_position_snapshot.csv", "snapshot_date,symbol,shares\n2026-07-02,AAPL,1\n")

    payload = build_daily_ops_status(
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        account_root=account_root,
        legacy_root=legacy_root,
    )

    assert payload["workflow_status"] == "COMMITTED"
    assert payload["completion_mode"] == "STANDARD"
    assert payload["overall_status"] != "PASS"
    assert payload["summary"]["terminal"] is False
    assert runbook_stage_e_evidence.validate_final_status_payload(payload, _state(tmp_path / "workspace"))

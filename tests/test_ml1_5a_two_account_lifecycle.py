from pathlib import Path
import json
import csv
import hashlib
import os
import copy

import pytest

from core.runbook_day_prep import read_account_local
from tests.ml1_5a_lifecycle_support import Lifecycle, IDS, DATA_DATE, TRADE_DATE
from scripts import runbook_primary_flow as flow
from scripts import runbook_state, runbook_stage_runner as runner, runbook_gate_checker as gates
from scripts.runbook_stage_b_recovery import (
    assess_stage_b_recovery,
    authorize_stage_b_recovery,
    build_stage_b_logical_operation,
    write_json_atomic,
)


def inventory(root, account=None):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()
            and (account is None or any(part == account or part.startswith(account + "_")
                                       for part in p.relative_to(root).parts))}


def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_shared_participant_account_template_is_readable(tmp_path):
    template = Path(__file__).resolve().parents[1] / "ops/runbook_wrappers/_account.template.cmd"
    local = tmp_path / "_account.local.cmd"
    local.write_bytes(template.read_bytes())
    values = read_account_local(local)
    assert values["ACCOUNT_ID"] == "paper_pilot_202606"
    assert values["SHARED_PARTICIPANT_ACCOUNT_IDS"] == "account_a,account_b"


@pytest.mark.parametrize("order", [IDS, list(reversed(IDS))], ids=["A_then_B", "B_then_A"])
def test_two_account_full_lifecycle(tmp_path, monkeypatch, order):
    env = Lifecycle(tmp_path, monkeypatch)
    legacy_before = inventory(env.legacy_root)
    shared_pin = None
    completed = {}
    for index, account in enumerate(order):
        other = next(value for value in IDS if value != account)
        other_before = inventory(env.paths[other].root)
        prepared = env.prepare(account)
        assert prepared["runner_result"] == "PASS", prepared
        assert inventory(env.paths[other].root) == other_before
        first_command = len(env.commands)
        result = env.stage_a(account)
        assert result["runner_result"] == "PASS", result
        assert result["shared_result"] == ("PREPARED" if index == 0 else "REUSE")
        pin = result["shared_input"]
        assert pin["participant_account_ids"] == IDS
        if shared_pin is None:
            shared_pin = pin
            shared_bytes = inventory(env.market["package"])
        assert pin == shared_pin
        assert all(cmd["db"] == pin["snapshot"]["path"] for cmd in env.commands[first_command:])
        later_command = len(env.commands)
        ledger_before = env.paths[account].execution_log_path.read_bytes()
        count = env.notion.complete_execution_input(account)
        assert (count > 0) == (account == IDS[0]), result
        for step in (flow.run_execution_to_review_prep, flow.run_review_preview, flow.run_close_day):
            if step == flow.run_review_preview:
                env.notion.complete_review_input(account)
            result = step(env.workspace, account, DATA_DATE, TRADE_DATE, confirm_paper_test=True)
            if result["runner_result"] != "PASS":
                print(json.dumps({k: v for k, v in result.items() if k != "frozen_context"}, indent=2))
                for artifact in (env.workspace / "command_runs" / env.state(account).runbook_day_id).glob("*.json"):
                    payload = json.loads(artifact.read_text(encoding="utf-8"))
                    if payload.get("runner_result") != "PASS":
                        print(artifact.name, payload.get("summary"))
            assert result["runner_result"] == "PASS", result
        assert all(cmd["db"] == env.parent_db for cmd in env.commands[later_command:])
        for command in env.commands[first_command:]:
            assert command["args"][command["args"].index("--account-id") + 1] == account
        assert os.environ["STOCK_SCREENER_MARKET_DB"] == env.parent_db
        state = env.state(account)
        assert all(state.stage_status[key] == "PASS" for key in (*"ABCDEF", "GATE1", "GATE2"))
        assert state.last_completed_step == 21
        assert state.last_error is None
        assert not env.paths[account].legacy_default_used
        assert all(account in key for key in state.idempotency_records)
        assert not state.recovery_authorizations
        manifest = json.loads((env.workspace / state.artifacts["completion_manifest_json"]).read_text(encoding="utf-8"))
        assert manifest["account_id"] == account
        assert manifest["completion_mode"] == ("STANDARD" if account == IDS[0] else "NO_ACTION")
        rows = read_rows(env.paths[account].execution_log_path)
        assert len(rows) == (1 if account == IDS[0] else 0)
        snapshots = read_rows(env.paths[account].account_snapshot_path)
        assert {row["account_id"] for row in snapshots} == {account}
        assert snapshots[-1]["snapshot_date"] == TRADE_DATE
        assert float(snapshots[-1]["initial_cash"]) == (100000 if account == IDS[0] else 112345)
        if account == IDS[1]:
            assert env.paths[account].execution_log_path.read_bytes() == ledger_before
            assert float(snapshots[-1]["cash"]) == 112345
            assert float(snapshots[-1]["total_equity_market_value"]) == 112345
            assert manifest["sources"]["review_ledger"]["record_count"] == 0
        else:
            assert float(snapshots[-1]["cash"]) == 100000 - 71 * 140
            assert float(snapshots[-1]["total_equity_market_value"]) == 99978.7
            assert manifest["sources"]["execution_ledger"]["record_count"] == 1
            assert manifest["sources"]["review_ledger"]["record_count"] > 0
            logical = build_stage_b_logical_operation(state, env.workspace)
            assert logical["logical_operation_payload"]["account_id"] == account
        assert inventory(env.market["package"]) == shared_bytes
        assert inventory(env.paths[other].root) == other_before
        if completed:
            assert inventory(env.workspace, other) == completed[other][1]
        # The completed primary flow is an idempotent retry: no new child work
        # and no account-local financial artifacts are rewritten.
        before_retry = inventory(env.paths[account].root)
        command_count = len(env.commands)
        retry = flow.run_close_day(env.workspace, account, DATA_DATE, TRADE_DATE, confirm_paper_test=True)
        assert retry["runner_result"] == "PASS", retry
        assert len(env.commands) == command_count
        assert inventory(env.paths[account].root) == before_retry
        completed[account] = (before_retry, inventory(env.workspace, account))
    assert len(env.market["calls"]) == 1
    assert (env.legacy_root / "sentinel.txt").read_bytes() == b"must remain untouched"
    assert inventory(env.legacy_root) == legacy_before
    states = [env.state(account) for account in IDS]
    assert states[0].runbook_day_id != states[1].runbook_day_id
    assert set(states[0].idempotency_records).isdisjoint(states[1].idempotency_records)
    assert runbook_state.build_idempotency_key(states[0], "eod_commit") != runbook_state.build_idempotency_key(states[1], "eod_commit")
    for account, paths in env.paths.items():
        other = next(value for value in IDS if value != account)
        for path in paths.root.rglob("*"):
            if path.is_file():
                assert str(env.paths[other].root).encode() not in path.read_bytes()
    assert_cross_account_blocked(env)


def assert_cross_account_blocked(env):
    a, b = [env.state(account) for account in IDS]
    path = runbook_state.get_state_path_for_context(env.workspace, IDS[1], DATA_DATE, TRADE_DATE)
    original = path.read_bytes()
    a_before = inventory(env.paths[IDS[0]].root), inventory(env.workspace, IDS[0])
    count = len(env.commands)
    try:
        with pytest.raises(ValueError, match="existing_frozen_binding_rewrite_forbidden"):
            runbook_state.save_state(a, path)
        source = runbook_state.get_state_path_for_context(env.workspace, IDS[0], DATA_DATE, TRADE_DATE)
        path.write_bytes(source.read_bytes())  # Adversarial file injection, not a lifecycle transition.
        result = flow.run_close_day(env.workspace, IDS[1], DATA_DATE, TRADE_DATE, confirm_paper_test=True)
        assert result["runner_result"] == "BLOCKED", result
        path.write_bytes(original)
        for artifact in ("daily_plan_json", "execution_commit_report_json", "review_append_report_json"):
            injected = copy.deepcopy(b)
            injected.artifacts[artifact] = a.artifacts[artifact]
            runbook_state.save_state(injected, path)
            if artifact == "daily_plan_json":
                result = gates.check_gate1_execution_input(env.workspace, IDS[1], DATA_DATE, TRADE_DATE)
            else:
                result = runner.run_stage_f(env.workspace, IDS[1], DATA_DATE, TRADE_DATE, confirm_paper_test=True)
            assert result["runner_result"] == "BLOCKED", (artifact, result)
            path.write_bytes(original)
        assert len(env.commands) == count
        assert (inventory(env.paths[IDS[0]].root), inventory(env.workspace, IDS[0])) == a_before
    finally:
        path.write_bytes(original)
    # Recovery assessments are bound to their frozen account context. An
    # assessment created from either account cannot authorize the other.
    for source_account, target_account in ((IDS[0], IDS[1]), (IDS[1], IDS[0])):
        source_state = env.state(source_account)
        failed_key = next(
            (key for key, record in source_state.idempotency_records.items()
             if record.get("command_key") == "execution_commit"),
            "missing-execution-commit",
        )
        assessment = assess_stage_b_recovery(
            workspace=env.workspace,
            account_id=source_account,
            data_date=DATA_DATE,
            trade_date=TRADE_DATE,
            failed_idempotency_key=failed_key,
            account_root=env.paths[source_account].root,
        )
        assessment_path = env.workspace / f"{source_account}_cross_account_assessment.json"
        write_json_atomic(assessment_path, assessment)
        target_before = runbook_state.get_state_path_for_context(
            env.workspace, target_account, DATA_DATE, TRADE_DATE,
        ).read_bytes()
        with pytest.raises(ValueError, match="assessment_context_mismatch"):
            authorize_stage_b_recovery(
                workspace=env.workspace,
                account_id=target_account,
                data_date=DATA_DATE,
                trade_date=TRADE_DATE,
                assessment_path=assessment_path,
                operator="synthetic-test",
                reason="cross-account evidence must fail closed",
                confirm_rollback_proven=True,
            )
        assert runbook_state.get_state_path_for_context(
            env.workspace, target_account, DATA_DATE, TRADE_DATE,
        ).read_bytes() == target_before

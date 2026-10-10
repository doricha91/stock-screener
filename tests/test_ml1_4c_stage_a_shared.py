from __future__ import annotations

import copy
import json
import os
import sqlite3
from functools import wraps
from pathlib import Path

import pytest

from core import daily_plan_generator as plan
from core import paper_shared_market_prepare as shared
from core.paper_data_freshness import run_paper_data_freshness_check
from screener.data_manager import DataManager
from scripts import run_paper_daily_plan, runbook_state, runbook_stage_runner as runner
from tests import test_ml1_4b_shared_market_prepare as fixtures

DATA_DATE = fixtures.DATA_DATE
TRADE_DATE = "2026-10-02"
IDS = ["paper_test_a", "paper_test_b"]


@pytest.fixture
def harness(tmp_path, monkeypatch):
    monkeypatch.setattr(fixtures, "PARTICIPANTS", IDS)
    env = fixtures.environment.__wrapped__(tmp_path, monkeypatch)
    env["workspace"] = tmp_path / "workspace"
    env["registry"]["universe"][1]["content"] = {"kind": "shared_snapshot"}
    fixtures.write_json(env["registry_path"], env["registry"])
    # First-run lifecycle itself has its own regression suite. Here accounts
    # model already-admitted accounts while the real shared/state/Plan path runs.
    monkeypatch.setattr(runner, "stage_a_prepare_guard", lambda *a: None)
    env["commands"] = []
    env["plans"] = []
    env["source_hashes"] = []
    original_refresh = env["refresh"]
    def refresh(*args, **kwargs):
        result = original_refresh(*args, **kwargs)
        # Future rows must remain in the snapshot but never enter calculations.
        with sqlite3.connect(env["db"]) as conn:
            conn.execute("INSERT INTO daily_price VALUES ('META','2026-10-05',900,999,800,999,999,1000000)")
            conn.execute("INSERT INTO daily_indicators VALUES ('META','2026-10-05',999,90,99)")
            conn.execute("INSERT INTO market_index VALUES ('SPY','2026-10-05',999)")
        env["source_hashes"].append(shared.sha256_file(env["db"]))
        return result
    monkeypatch.setattr(shared, "run_paper_prepare_data", refresh)
    def execute(argv, cwd, timeout_sec, *, env=None):
        harness_env = harness_data
        harness_env["commands"].append(argv)
        assert "prepare-data" not in argv
        assert env["STOCK_SCREENER_MARKET_DB"] == str(harness_env["package"] / shared.SNAPSHOT)
        output = "{}"
        if "validate-shared-data" in argv or "data-freshness" in argv or "plan" in argv:
            state_path = Path(argv[argv.index("--runbook-state-json") + 1])
            state = runbook_state.load_state(state_path)
            pin = shared.load_pinned_shared_input(state_path, account_id=state.frozen_context.account_id, data_date=DATA_DATE)
            if "data-freshness" in argv:
                result = run_paper_data_freshness_check(date_str=DATA_DATE, strict=True, shared_input=pin)
                assert result["market_db_path"] == pin["snapshot"]["path"]
                assert result["result"] == "PASS"
            if "plan" in argv:
                path = run_paper_daily_plan.run_paper_daily_plan(
                    account_paths=harness_env["paths"][state.frozen_context.account_id],
                    data_date=DATA_DATE, trade_date=TRADE_DATE, enforce_asof_contract=True,
                    observed_at="2026-10-02T08:00:00+09:00", runbook_state_path=state_path)
                payload = json.loads(Path(path).with_suffix(".json").read_text(encoding="utf-8"))
                harness_env["plans"].append(payload)
                output = f"Official paper daily plan is ready at:\n{path}\n"
        return {"exit_code": 0, "stdout": output, "stderr": "", "duration_ms": 1}
    harness_data = env
    monkeypatch.setattr(runner, "run_allowlisted_command", execute)
    # Detect accidental returns to the legacy/canonical reader or live universe.
    monkeypatch.setattr(plan.data_manager, "get_price_data", lambda *a, **k: pytest.fail("canonical price reader"))
    monkeypatch.setattr(plan, "load_universe_snapshot_as_of_quarter", lambda *a, **k: pytest.fail("live universe selector"))
    monkeypatch.setattr(plan.market_analyzer, "_upsert_market_status_log", lambda *a, **k: pytest.fail("market writer"))
    return env


def stage(env, account=IDS[0], **kwargs):
    return runner.run_stage_a(env["workspace"], account, DATA_DATE, TRADE_DATE,
                             shared_participant_account_ids=kwargs.pop("participants", ",".join(IDS)),
                             confirm_paper_test=True, **kwargs)


@pytest.mark.parametrize("order", [IDS, list(reversed(IDS))], ids=["A_then_B", "B_then_A"])
def test_real_stage_a_frozen_plan_and_one_refresh(harness, monkeypatch, order):
    old_env = os.environ.get("STOCK_SCREENER_MARKET_DB")
    first = stage(harness, order[0])
    assert first["runner_result"] == "PASS", first
    assert first["shared_result"] == "PREPARED"
    pin = first["shared_input"]
    before = fixtures.package_bytes(harness["package"])
    assert shared.sha256_file(harness["db"]) == harness["source_hashes"][0]
    # Poison canonical sources after publication; all subsequent readers must
    # use the frozen package and account binding, including freshness and HWM.
    with sqlite3.connect(harness["db"]) as conn:
        conn.execute("DELETE FROM market_index")
        conn.execute("DELETE FROM daily_price")
    harness["universe"].write_text("unusable live universe", encoding="utf-8")
    source_after_poison = shared.sha256_file(harness["db"])
    monkeypatch.setattr(shared, "run_paper_prepare_data", lambda *a, **k: pytest.fail("second refresh"))
    second = stage(harness, order[1], participants=" , ".join(reversed(IDS)))
    assert second["runner_result"] == "PASS", second
    assert second["shared_result"] == "REUSE"
    assert second["shared_input"] == pin
    assert len(harness["calls"]) == 1
    assert fixtures.package_bytes(harness["package"]) == before
    assert shared.sha256_file(harness["db"]) == source_after_poison
    assert os.environ.get("STOCK_SCREENER_MARKET_DB") == old_env
    for payload in harness["plans"]:
        assert payload["shared_input"] == pin
        for name in ("market", "indicator", "rs"):
            assert payload["as_of_lineage"][name]["selected_max_date"] <= DATA_DATE
            assert payload["as_of_lineage"][name]["source"] == pin["snapshot"]["path"]
        if payload["account_id"] == IDS[1]:
            assert payload["as_of_lineage"]["universe"]["source"] == pin["universe"]["path"]
    for result in (first, second):
        assert runbook_state.load_state(Path(result["state_path"])).artifacts["shared_input"] == pin
    retry = stage(harness, order[0])
    assert retry["runner_result"] == "PASS", retry
    assert retry["shared_input"] == pin


@pytest.mark.parametrize("participants", [None, "", IDS[1], ",".join([IDS[0], IDS[0]]), "bad/id", [None]])
def test_bad_participants_block_without_state_or_refresh(harness, participants):
    result = stage(harness, participants=participants)
    assert result["runner_result"] == "BLOCKED"
    assert not harness["workspace"].exists()
    assert not harness["calls"] and not harness["commands"]


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("failure", ["prepare", "consumer", "participant_conflict"])
def test_shared_failure_preserves_absent_or_ready_state(harness, monkeypatch, existing, failure):
    if existing:
        runbook_state.init_state_file_for_context(harness["workspace"], IDS[0], DATA_DATE, TRADE_DATE)
    before = fixtures.package_bytes(harness["workspace"])
    if failure == "prepare":
        monkeypatch.setattr(runner, "run_shared_market_prepare", lambda **k: {"result": "BLOCKED", "reason": "injected"})
    elif failure == "consumer":
        monkeypatch.setattr(runner, "validate_shared_market_input", lambda **k: (_ for _ in ()).throw(ValueError("unsafe publication")))
    else:
        assert fixtures.run()["result"] == "PREPARED"
    result = stage(harness, participants=IDS[0] if failure == "participant_conflict" else ",".join(IDS))
    assert result["runner_result"] == "BLOCKED", result
    assert fixtures.package_bytes(harness["workspace"]) == before
    assert not harness["commands"]
    assert not harness["plans"]


def test_dry_run_requires_existing_package_and_never_mutates(harness):
    absent = stage(harness, dry_run=True)
    assert absent["runner_result"] == "BLOCKED"
    assert not harness["calls"] and not harness["workspace"].exists()
    assert fixtures.run()["result"] == "PREPARED"
    for existing in (False, True):
        if existing:
            runbook_state.init_state_file_for_context(harness["workspace"], IDS[0], DATA_DATE, TRADE_DATE)
        before = fixtures.package_bytes(harness["workspace"])
        package_before = fixtures.package_bytes(harness["package"])
        result = stage(harness, dry_run=True)
        assert result["runner_result"] == "PASS", result
        assert len(result["commands"]) == 6
        assert fixtures.package_bytes(harness["workspace"]) == before
        assert fixtures.package_bytes(harness["package"]) == package_before
        assert len(harness["calls"]) == 1 and not harness["commands"]


def test_pin_rewrite_and_plan_mismatch_are_blocked(harness, monkeypatch):
    first = stage(harness)
    assert first["runner_result"] == "PASS", first
    path = Path(first["state_path"])
    before = path.read_bytes()
    state = runbook_state.load_state(path)
    other = copy.deepcopy(first["shared_input"])
    other["shared_preparation_id"] = "different"
    with pytest.raises(ValueError, match="rewrite_forbidden"):
        runbook_state.pin_shared_input(state, other)
    state.artifacts["shared_input"] = other
    with pytest.raises(ValueError, match="rewrite_forbidden"):
        runbook_state.save_state(state, path)
    monkeypatch.setattr(runner, "validate_shared_market_input", lambda **k: other)
    assert stage(harness)["runner_result"] == "BLOCKED"
    assert path.read_bytes() == before
    payload = copy.deepcopy(harness["plans"][0])
    payload["shared_input"] = other
    plan_path = harness["workspace"] / "wrong_plan.json"
    plan_path.write_text(json.dumps(payload), encoding="utf-8")
    _, error = runner._validate_stage_a_daily_plan(
        {"outputs": {"artifact_refs": {"daily_plan_json": str(plan_path)}}},
        runbook_state.load_state(path), harness["workspace"])
    assert error["reason"] == "daily_plan_shared_input_mismatch"


def test_snapshot_connections_deny_writes_and_preserve_cutoff(harness):
    assert fixtures.run()["result"] == "PREPARED"
    snapshot = harness["package"] / shared.SNAPSHOT
    before = shared.sha256_file(snapshot)
    reader = DataManager(snapshot, read_only=True)
    for connection in (reader.get_connection(), plan.market_analyzer.get_db_connection(snapshot, read_only=True)):
        try:
            with pytest.raises(sqlite3.OperationalError, match="readonly"):
                connection.execute("DELETE FROM daily_price")
        finally:
            connection.close()
    frame = reader.get_price_data("META", end_date=DATA_DATE)
    assert str(frame.index.max().date()) == DATA_DATE
    assert frame.iloc[-1]["close"] == 110
    series = plan.load_market_index_series("SPY", DATA_DATE, db_path=snapshot, read_only=True)
    assert series.iloc[-1] == 100
    assert shared.sha256_file(snapshot) == before


def test_consumer_never_creates_missing_publication(harness):
    with pytest.raises(shared.SharedPreparationError, match="missing"):
        shared.validate_shared_market_input(data_date=DATA_DATE, participant_account_ids=IDS)
    assert not harness["root"].exists() and not harness["calls"]


def test_stage_a_registry_has_no_market_writer():
    commands = runner.get_stage_a_commands()
    assert [c.step_id for c in commands] == list(range(6))
    assert commands[1].command_key == "shared_data_validate"
    assert commands[1].command_type == "READ_ONLY"
    assert all("prepare-data" not in c.argv_template for c in commands)


def test_frozen_universe_lineage_mismatch_is_blocked(harness):
    result = stage(harness, IDS[1])
    assert result["runner_result"] == "PASS", result
    state = runbook_state.load_state(Path(result["state_path"]))
    payload = copy.deepcopy(harness["plans"][0])
    payload["as_of_lineage"]["universe"]["source"] = str(harness["universe"])
    path = harness["workspace"] / "wrong_universe.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    _, error = runner._validate_stage_a_daily_plan(
        {"outputs": {"artifact_refs": {"daily_plan_json": str(path)}}}, state, harness["workspace"])
    assert error["reason"] == "daily_plan_shared_input_mismatch"
    assert error["detail"] == "daily_plan_frozen_universe_mismatch"


def test_shared_generator_requires_binding_before_reading(harness):
    with pytest.raises(ValueError, match="shared_input_requires_account_binding"):
        plan.generate_daily_plan(date_str=TRADE_DATE, data_date=DATA_DATE, shared_input={})


def test_paper_cli_consumes_pinned_package(harness, monkeypatch):
    from scripts import paper

    first = stage(harness, IDS[1])
    assert first["runner_result"] == "PASS", first
    before = fixtures.package_bytes(harness["package"])
    source_hash = shared.sha256_file(harness["db"])
    # Model the Stage A child environment; run real parser/handlers/preflight.
    monkeypatch.setenv("STOCK_SCREENER_MARKET_DB", first["shared_input"]["snapshot"]["path"])
    original = paper.run_paper_daily_plan
    @wraps(original)
    def plan_at_operation_time(*args, **kwargs):
        return original(*args, observed_at="2026-10-02T08:00:00+09:00", **kwargs)
    monkeypatch.setattr(paper, "run_paper_daily_plan", plan_at_operation_time)
    common = ["--account-id", IDS[1], "--runbook-state-json", first["state_path"]]
    assert paper.main(["validate-shared-data", "--data-date", DATA_DATE, *common]) == 0
    assert paper.main(["data-freshness", "--date", DATA_DATE, *common]) == 0
    assert paper.main(["plan", "--data-date", DATA_DATE, "--trade-date", TRADE_DATE,
                       "--enforce-asof-contract", *common]) == 0
    assert fixtures.package_bytes(harness["package"]) == before
    assert shared.sha256_file(harness["db"]) == source_hash
    assert len(harness["calls"]) == 1

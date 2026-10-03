from __future__ import annotations

import copy
import csv
import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from core import paper_account_binding as binding
from core import paper_account_profile as profiles
from core import paper_account_paths as paths
from core.paper_account_bootstrap import initialize_paper_account
from core.paper_account_fresh import validate_prepare_first_request
from core.runbook_calendar import MarketCalendar
from scripts import runbook_state as states


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def environment(tmp_path, monkeypatch):
    account_file = tmp_path / "profiles.json"
    registry_file = tmp_path / "registry.json"
    account = {"account_id": "synthetic_a", "display_name": "Synthetic A", "currency": "USD",
               "initial_cash": 12345, "account_type": "paper", "is_default": True,
               "strategy_profile": "synthetic_strategy", "strategy_version": "v1",
               "universe_profile": "synthetic_universe", "universe_version": "v1"}
    account_config = {"schema_version": profiles.VERSIONED_ACCOUNT_PROFILE_SCHEMA,
                      "default_account_id": "synthetic_a", "accounts": [account]}
    registry = {"schema_version": binding.REGISTRY_SCHEMA,
                "strategy": [{"id": "synthetic_strategy", "version": "v1",
                              "content": {"parameters": {"entry_period": 12, "rsi_weight": 1.0}}}],
                "universe": [{"id": "synthetic_universe", "version": "v1",
                              "content": {"kind": "symbols", "symbols": ["BBB", "AAA"]}}]}
    write_json(account_file, account_config)
    write_json(registry_file, registry)
    monkeypatch.setattr(profiles, "_default_settings_path", lambda: account_file)
    monkeypatch.setattr(binding, "paper_binding_registry_path", lambda: registry_file)
    monkeypatch.setattr(paths, "PAPER_ACCOUNTS_ROOT", tmp_path / "accounts")
    return account_file, registry_file, account_config, registry


def resolve():
    return binding.resolve_account_binding("synthetic_a")


def test_exact_resolve_and_evidence(environment):
    result = resolve()
    binding.validate_binding(result)
    assert result["semantics"]["strategy"]["reference"] == {"id": "synthetic_strategy", "version": "v1"}
    assert result["semantics"]["universe"]["content"]["symbols"] == ["AAA", "BBB"]
    assert result["semantics"]["shared_policy"]["max_long_positions"] == 10
    assert result["semantics"]["effective_strategy_base"]["entry_period"] == 12
    assert "REGIME_RULES" in result["semantics"]["regime_policy"]
    assert not (binding.STRATEGY_PARAMETERS & set(result["semantics"]["shared_policy"]))
    assert not (binding.REGIME_POLICY_KEYS & set(result["semantics"]["shared_policy"]))
    assert "initial_capital" not in result["semantics"]["shared_policy"]
    assert "account_id" not in result["semantics"]


@pytest.mark.parametrize("field,value", [
    ("strategy_profile", "unknown"), ("strategy_version", "unknown"),
    ("universe_profile", "unknown"), ("universe_version", "unknown"),
    ("strategy_version", None), ("universe_version", ""), ("strategy_profile", {"id": "bad"}),
    ("strategy_version", 1), ("strategy_profile", "../bad"),
])
def test_invalid_reference_no_fallback(environment, field, value):
    path, _, payload, _ = environment
    payload["accounts"][0][field] = value
    write_json(path, payload)
    with pytest.raises((ValueError, profiles.PaperAccountProfileError)):
        resolve()


def test_missing_registry_unknown_account(environment):
    with pytest.raises(profiles.PaperAccountProfileError):
        binding.resolve_account_binding("unknown_account")
    environment[0].unlink()
    with pytest.raises(profiles.PaperAccountProfileError):
        resolve()
    assert profiles.load_paper_account_profiles().default_account_id == "paper_default"


@pytest.mark.parametrize("key", ["max_long_positions", "risk_per_trade", "USE_HEDGE_MODE",
                                  "BULL_hedge_ratio", "runtime_overrides", "unknown"])
def test_safety_and_unknown_parameters_blocked(environment, key):
    _, path, _, registry = environment
    registry["strategy"][0]["content"]["parameters"][key] = 100
    write_json(path, registry)
    with pytest.raises(binding.BindingError, match="unsupported|safety"):
        resolve()


def test_digest_metadata_order_and_account_nonimpact(environment):
    account_path, registry_path, account_config, registry = environment
    before = resolve()
    account_config["accounts"][0].update(display_name="Renamed", initial_cash=99999, notion_profile="other")
    other = {**account_config["accounts"][0], "account_id": "synthetic_b", "is_default": False}
    account_config["accounts"].insert(0, other)
    write_json(account_path, account_config)
    registry["strategy"].insert(0, {"id": "other_strategy", "version": "v9", "content": {"parameters": {}}})
    registry["universe"][0]["content"]["symbols"].reverse()
    registry["strategy"][1]["content"]["parameters"]["rsi_weight"] = 1
    write_json(registry_path, registry)
    assert resolve() == before
    assert binding.resolve_account_binding("synthetic_b") == before


@pytest.mark.parametrize("kind", ["strategy", "universe", "policy"])
def test_semantic_change_changes_digest(environment, monkeypatch, kind):
    before = resolve()
    if kind == "policy":
        original = binding.make_config
        def changed_policy(*args, **kwargs):
            result = original(*args, **kwargs)
            result["MARKET_BENCHMARK_SYMBOL"] = "QQQ"
            return result
        monkeypatch.setattr(binding, "make_config", changed_policy)
    else:
        _, path, _, registry = environment
        if kind == "strategy":
            registry[kind][0]["content"]["parameters"]["entry_period"] = 20
        else:
            registry[kind][0]["content"]["symbols"].append("CCC")
        write_json(path, registry)
    current = resolve()
    assert current["digest"] != before["digest"]
    with pytest.raises(binding.BindingError, match="drift"):
        binding.assert_binding_matches(before, current)


def test_strategy_override_prevents_default_only_false_drift(environment, monkeypatch):
    before = resolve()
    original = binding.make_config

    def changed_default(*args, **kwargs):
        result = original(*args, **kwargs)
        result["entry_period"] = 20
        return result

    monkeypatch.setattr(binding, "make_config", changed_default)
    current = resolve()
    assert current["semantics"]["effective_strategy_base"]["entry_period"] == 12
    assert current["digest"] == before["digest"]
    binding.assert_binding_matches(before, current)


def test_unoverridden_strategy_default_change_is_semantic_drift(environment, monkeypatch):
    _, registry_path, _, registry = environment
    registry["strategy"][0]["content"]["parameters"].pop("entry_period")
    write_json(registry_path, registry)
    before = resolve()
    original = binding.make_config

    def changed_default(*args, **kwargs):
        result = original(*args, **kwargs)
        result["entry_period"] = 20
        return result

    monkeypatch.setattr(binding, "make_config", changed_default)
    current = resolve()
    assert current["digest"] != before["digest"]
    with pytest.raises(binding.BindingError, match="drift"):
        binding.assert_binding_matches(before, current)


@pytest.mark.parametrize("policy_key,new_value", [
    ("REGIME_ADX_THRESHOLD", 30),
    ("risk_per_trade", 0.08),
])
def test_regime_and_shared_policy_changes_are_semantic_drift(
    environment, monkeypatch, policy_key, new_value,
):
    before = resolve()
    original = binding.make_config

    def changed_policy(*args, **kwargs):
        result = original(*args, **kwargs)
        result[policy_key] = new_value
        return result

    monkeypatch.setattr(binding, "make_config", changed_policy)
    current = resolve()
    assert current["digest"] != before["digest"]


def test_regime_policy_rejects_unapproved_overlay(environment, monkeypatch):
    original = binding.make_config

    def unsafe_overlay(*args, **kwargs):
        result = original(*args, **kwargs)
        result["REGIME_RULES"]["BULL"]["risk_per_trade"] = 1
        return result

    monkeypatch.setattr(binding, "make_config", unsafe_overlay)
    with pytest.raises(binding.BindingError, match="unsupported regime overlay"):
        resolve()


def test_reference_change_is_identity_drift_even_with_same_semantics(environment):
    account_path, registry_path, account_config, registry = environment
    duplicate = copy.deepcopy(registry["strategy"][0])
    duplicate["version"] = "v2"
    registry["strategy"].append(duplicate)
    write_json(registry_path, registry)
    before = resolve()
    account_config["accounts"][0]["strategy_version"] = "v2"
    write_json(account_path, account_config)
    current = resolve()
    assert current["digest"] == before["digest"]
    with pytest.raises(binding.BindingError, match="identity drift"):
        binding.assert_binding_matches(before, current)


@pytest.mark.parametrize("field", ["risk_per_trade", "strategy_verison", "unexpected"])
def test_v2_account_unknown_fields_fail_closed(environment, field):
    account_path, _, account_config, _ = environment
    account_config["accounts"][0][field] = 1
    write_json(account_path, account_config)
    with pytest.raises(profiles.PaperAccountProfileError, match="unknown v2 account fields"):
        profiles.load_paper_account_profiles()


def test_v1_account_unknown_fields_remain_compatible(environment):
    account_path, _, account_config, _ = environment
    account_config["schema_version"] = profiles.ACCOUNT_PROFILE_SCHEMA_VERSION
    account_config["accounts"][0].pop("strategy_version")
    account_config["accounts"][0].pop("universe_version")
    account_config["accounts"][0]["legacy_extra"] = "retained compatibility"
    write_json(account_path, account_config)
    assert profiles.load_paper_account_profiles().schema_version == profiles.ACCOUNT_PROFILE_SCHEMA_VERSION


def test_state_round_trip_unchanged_identity(environment, tmp_path):
    state = states.create_initial_state("synthetic_a", "2026-09-28", "2026-09-29")
    assert state.schema_version == states.BINDING_STATE_SCHEMA_VERSION
    assert state.runbook_day_id == "synthetic_a_2026-09-28_2026-09-29"
    path = tmp_path / "state.json"
    states.save_state(state, path)
    first = path.read_bytes()
    reloaded = states.load_state(path)
    assert not states.validate_state(reloaded)
    states.save_state(reloaded, path)
    assert path.read_bytes() == first
    assert states.load_state(path) == state


def test_legacy_omission_and_no_migration(environment, tmp_path):
    path, _, payload, _ = environment
    payload["schema_version"] = profiles.ACCOUNT_PROFILE_SCHEMA_VERSION
    for key in ("strategy_version", "universe_version"):
        payload["accounts"][0].pop(key)
    write_json(path, payload)
    state = states.create_initial_state("synthetic_a", "2026-09-28", "2026-09-29")
    assert state.schema_version == states.SCHEMA_VERSION
    assert "binding" not in state.to_dict()["frozen_context"]
    target = tmp_path / "legacy.json"
    states.save_state(state, target)
    original = target.read_bytes()
    assert states.load_state(target) == state
    assert target.read_bytes() == original
    states.save_state(states.load_state(target), target)
    assert target.read_bytes() == original


def test_drift_blocks_save_and_stage_start_without_write(environment, tmp_path):
    state = states.create_initial_state("synthetic_a", "2026-09-28", "2026-09-29")
    path = tmp_path / "state.json"
    states.save_state(state, path)
    original = path.read_bytes()
    _, registry_path, _, registry = environment
    registry["strategy"][0]["content"]["parameters"]["entry_period"] = 20
    write_json(registry_path, registry)
    for operation in (lambda: states.save_state(state, path), lambda: states.start_stage(state, "A")):
        with pytest.raises(binding.BindingError, match="drift"):
            operation()
    assert path.read_bytes() == original
    # Historical evidence remains readable, independently from live registry drift.
    assert states.load_state(path) == state


@pytest.mark.parametrize("mutation", ["missing", "tamper", "downgrade"])
def test_frozen_missing_tamper_and_schema_downgrade_blocked(environment, tmp_path, mutation):
    state = states.create_initial_state("synthetic_a", "2026-09-28", "2026-09-29")
    payload = state.to_dict()
    if mutation == "missing":
        payload["frozen_context"].pop("binding")
    elif mutation == "downgrade":
        payload["schema_version"] = states.SCHEMA_VERSION
    else:
        payload["frozen_context"]["binding"]["semantics"]["currency"] = "EUR"
    path = tmp_path / "bad.json"
    write_json(path, payload)
    with pytest.raises(binding.BindingError):
        states.load_state(path)


def edit_csv(path, mutator):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames
        rows = list(reader)
    mutator(rows)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def fresh(environment, tmp_path):
    account_paths = paths.build_paper_account_paths("synthetic_a")
    # Only synthetic tmp artifacts. The production seed writer is deliberately unchanged.
    initialize_paper_account(account_id="synthetic_a", initial_cash=12345, currency="USD",
                             date_str="2026-09-28", confirm_create=True, account_root=account_paths.root)
    edit_csv(account_paths.account_snapshot_path, lambda rows: rows[0].update(account_id="synthetic_a"))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return dict(account_id="synthetic_a", account_paths=account_paths, workspace=workspace,
                authoritative_workspace=workspace, data_date="2026-09-28", trade_date="2026-09-29",
                calendar=MarketCalendar("US", "America/New_York", date(2026, 1, 1), date(2026, 12, 31), frozenset()))


def tree_bytes(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_fresh_eligible_no_mutation(fresh, tmp_path):
    before = tree_bytes(tmp_path)
    result = validate_prepare_first_request(**fresh)
    assert result["eligible"], result
    assert result["next_action"] == "VALIDATED_NOT_PREPARED"
    assert tree_bytes(tmp_path) == before


@pytest.mark.parametrize("field,value", [("account_id", ""), ("account_id", "synthetic_b"),
    ("currency", "EUR"), ("cash", "12344"), ("initial_cash", "999"),
    ("snapshot_date", "2026-09-27"), ("cash", "nan"), ("position_count", "1")])
def test_invalid_bootstrap_blocked(fresh, field, value):
    edit_csv(fresh["account_paths"].account_snapshot_path, lambda rows: rows[0].update({field: value}))
    assert not validate_prepare_first_request(**fresh)["eligible"]


@pytest.mark.parametrize("artifact", ["execution_log_path", "position_snapshot_path"])
def test_execution_or_position_history_blocked(fresh, artifact):
    path = getattr(fresh["account_paths"], artifact)
    def add(rows):
        with path.open(encoding="utf-8-sig") as handle:
            columns = next(csv.reader(handle))
        rows.append({key: "old" for key in columns})
    edit_csv(path, add)
    result = validate_prepare_first_request(**fresh)
    assert not result["eligible"]
    assert any("history_present" in reason for reason in result["blockers"])


@pytest.mark.parametrize("kind", ["completed", "no_action", "failed", "recovery", "gap", "prepared"])
def test_run_and_recovery_history_never_fresh(fresh, kind):
    workspace = fresh["workspace"]
    state = states.create_initial_state("synthetic_a", "2026-09-28", "2026-09-29")
    if kind in ("completed", "no_action", "failed", "prepared"):
        payload = state.to_dict()
        if kind == "failed":
            payload["current_status"] = "FAILED"
        elif kind in ("completed", "no_action"):
            payload.update(current_stage="F", current_status="PASS", last_completed_step=21,
                           last_completed_stage="F", stage_status={k: "PASS" for k in states.STAGE_IDS})
        write_json(states.get_state_path_for_context(workspace, "synthetic_a", "2026-09-28", "2026-09-29"), payload)
    else:
        dirname = "operational_no_trade_gaps" if kind == "gap" else "runbook_recoveries"
        write_json(workspace / dirname / "hash.json", {"account_id": "synthetic_a"})
    assert not validate_prepare_first_request(**fresh)["eligible"]


@pytest.mark.parametrize("kind", ["missing", "extra", "wrong_workspace", "wrong_root", "wrong_date", "binding", "current"])
def test_partial_and_context_conflicts_blocked(fresh, tmp_path, kind):
    if kind == "missing":
        fresh["account_paths"].execution_log_path.unlink()
    elif kind == "extra":
        (fresh["account_paths"].root / "partial.tmp").write_text("partial")
    elif kind == "wrong_workspace":
        fresh["authoritative_workspace"] = tmp_path / "other_workspace"
    elif kind == "wrong_root":
        fresh["account_paths"] = replace(fresh["account_paths"], root=tmp_path / "other_account")
    elif kind == "wrong_date":
        fresh["trade_date"] = "2026-09-30"
    elif kind == "binding":
        fresh["expected_binding"] = resolve()
        fresh["expected_binding"]["digest"] = "bad"
    else:
        path = fresh["account_paths"].current_state_snapshot_path(fresh["data_date"])
        payload = json.loads(path.read_text())
        payload["applied_trade_ids"] = ["old"]
        write_json(path, payload)
    assert not validate_prepare_first_request(**fresh)["eligible"]

@pytest.mark.parametrize("kind", ["duplicate", "unknown_schema", "noninteger", "nan", "universe_extra"])
def test_registry_contract_rejects_malformed_content(environment, kind):
    _, path, _, registry = environment
    if kind == "duplicate":
        registry["strategy"].append(copy.deepcopy(registry["strategy"][0]))
    elif kind == "unknown_schema":
        registry["schema_version"] = "unknown"
    elif kind == "universe_extra":
        registry["universe"][0]["content"]["safety_override"] = True
    else:
        registry["strategy"][0]["content"]["parameters"]["entry_period"] = 1.5 if kind == "noninteger" else float("nan")
    write_json(path, registry)
    with pytest.raises(binding.BindingError):
        resolve()


def test_existing_frozen_state_cannot_be_replaced_after_profile_change(environment, tmp_path):
    first = states.create_initial_state("synthetic_a", "2026-09-28", "2026-09-29")
    path = tmp_path / "state.json"
    states.save_state(first, path)
    before = path.read_bytes()
    _, registry_path, _, registry = environment
    registry["strategy"][0]["content"]["parameters"]["entry_period"] = 22
    write_json(registry_path, registry)
    replacement = states.create_initial_state("synthetic_a", "2026-09-28", "2026-09-29")
    with pytest.raises(ValueError, match="rewrite_forbidden"):
        states.save_state(replacement, path)
    assert path.read_bytes() == before


def test_bound_state_requires_binding_at_save(environment, tmp_path):
    state = states.create_initial_state("synthetic_a", "2026-09-28", "2026-09-29")
    state = replace(state, frozen_context=replace(state.frozen_context, binding=None))
    with pytest.raises(binding.BindingError):
        states.save_state(state, tmp_path / "missing" / "state.json")
    assert not (tmp_path / "missing").exists()


def test_fresh_other_account_history_nonimpact(fresh):
    write_json(fresh["workspace"] / "runbook_recoveries" / "other.json", {"account_id": "synthetic_b"})
    assert validate_prepare_first_request(**fresh)["eligible"]


@pytest.mark.parametrize("target_exists", [False, True], ids=["dangling", "live"])
def test_lifecycle_root_symlink_fails_closed(fresh, monkeypatch, target_exists):
    target = fresh["workspace"] / "operational_no_trade_gaps"
    original_exists = Path.exists
    original_is_symlink = Path.is_symlink

    def modeled_exists(path):
        return target_exists if path == target else original_exists(path)

    def modeled_is_symlink(path):
        return True if path == target else original_is_symlink(path)

    monkeypatch.setattr(Path, "exists", modeled_exists)
    monkeypatch.setattr(Path, "is_symlink", modeled_is_symlink)
    assert target.exists() is target_exists

    result = validate_prepare_first_request(**fresh)
    assert not result["eligible"]
    assert "unreadable_history:operational_no_trade_gaps" in result["blockers"]


@pytest.mark.parametrize("name,content", [
    ("orphan.txt", "unknown"),
    ("hash.json.tmp", '{"account_id":"synthetic_a"}'),
    ("broken.json", "{"),
    ("unattributed.json", '{"status":"FAILED"}'),
])
def test_unattributable_lifecycle_artifacts_fail_closed(fresh, name, content):
    path = fresh["workspace"] / "operational_no_trade_gaps" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    result = validate_prepare_first_request(**fresh)
    assert not result["eligible"]
    assert any(
        marker in blocker
        for blocker in result["blockers"]
        for marker in ("unexplained_history", "unreadable_history", "unattributable_history")
    )


def test_unmodified_bootstrap_blank_seed_is_rejected(environment, tmp_path):
    ap = paths.build_paper_account_paths("synthetic_a")
    initialize_paper_account(account_id="synthetic_a", initial_cash=12345, currency="USD",
                             date_str="2026-09-28", confirm_create=True, account_root=ap.root)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    result = validate_prepare_first_request(
        account_id="synthetic_a", account_paths=ap, workspace=workspace, authoritative_workspace=workspace,
        data_date="2026-09-28", trade_date="2026-09-29",
        calendar=MarketCalendar("US", "America/New_York", date(2026, 1, 1), date(2026, 12, 31), frozenset()),
    )
    assert not result["eligible"]
    assert any("blank_account_id" in e for e in result["blockers"])


def test_binding_aware_recovery_preserves_evidence(environment, tmp_path, monkeypatch):
    from core import runbook_recovery, runbook_day_rollover
    from tests.test_runbook_recovery import _seed_incident, _arguments, ACCOUNT_ID
    account_path, _, payload, _ = environment
    payload["accounts"][0]["account_id"] = ACCOUNT_ID
    payload["default_account_id"] = ACCOUNT_ID
    write_json(account_path, payload)
    monkeypatch.setattr(paths, "PAPER_ACCOUNTS_ROOT", tmp_path / "outputs" / "paper_accounts")
    workspace, state_path, _ = _seed_incident(tmp_path)
    state = states.load_state(state_path)
    assert state.schema_version == states.BINDING_STATE_SCHEMA_VERSION
    source_bytes = state_path.read_bytes()
    result = runbook_recovery.authorize_recovery(**_arguments(workspace))
    assert result["runner_result"] == "PASS", result
    validation = runbook_recovery.validate_recovery_evidence(workspace, state_path, state, _arguments(workspace)["calendar"])
    assert validation["valid"], validation
    assert state_path.read_bytes() == source_bytes
    assert validation["payload"]["source_frozen_context"]["binding"] == state.frozen_context.binding
    rollover = runbook_day_rollover.preview_rollover(workspace, ACCOUNT_ID, _arguments(workspace)["calendar"], confirm_paper_test=True)
    assert rollover["runner_result"] == "PASS", rollover

@pytest.mark.parametrize("field,value", [("cash_ratio_cost_basis", "0.5"), ("cash_ratio_market_value", "0"),
                                          ("realized_pnl_by_symbol", '{"AAA":1}'), ("unrealized_pnl_pct", "0.1")])
def test_bootstrap_initial_metrics_must_agree(fresh, field, value):
    edit_csv(fresh["account_paths"].account_snapshot_path, lambda rows: rows[0].update({field: value}))
    assert not validate_prepare_first_request(**fresh)["eligible"]


def test_live_account_not_fresh_paper_eligible(fresh, environment):
    path, _, payload, _ = environment
    payload["accounts"][0]["account_type"] = "live"
    write_json(path, payload)
    assert "fresh_paper_account_mode_required" in validate_prepare_first_request(**fresh)["blockers"]


def test_legacy_context_dict_and_asdict_have_no_new_field():
    from dataclasses import asdict
    context = states.FrozenRunbookContext("synthetic_a", "2026-09-28", "2026-09-29")
    expected = {"account_id": "synthetic_a", "data_date": "2026-09-28", "trade_date": "2026-09-29"}
    assert context.__dict__ == expected
    assert asdict(context) == expected


def test_unknown_new_account_state_cannot_fall_back(environment):
    with pytest.raises(profiles.PaperAccountProfileError):
        states.create_initial_state("unknown_account", "2026-09-28", "2026-09-29")

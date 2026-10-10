from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from core import paper_first_run as first_run_module
from core import paper_account_binding as binding
from core import paper_account_paths as paths
from core import paper_account_profile as profiles
from core.paper_account_bootstrap import initialize_paper_account
from core.paper_first_run import prepare_first_run, prepare_evidence_path
from core.runbook_calendar import MarketCalendar
from core.runbook_day_prep import read_runbook_day_local
from core.stage_a_asof_contract import sha256_payload
from scripts import runbook_stage_runner, runbook_state


ACCOUNT_ID = "paper_fresh"
DATA_DATE = "2026-10-02"
TRADE_DATE = "2026-10-05"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def first_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    account_file = tmp_path / "config" / "paper_account_profiles.json"
    registry_file = tmp_path / "config" / "paper_binding_profiles.json"
    account_config = {
        "schema_version": profiles.VERSIONED_ACCOUNT_PROFILE_SCHEMA,
        "default_account_id": ACCOUNT_ID,
        "accounts": [{
            "account_id": ACCOUNT_ID,
            "display_name": "Fresh Paper",
            "currency": "USD",
            "initial_cash": 12345,
            "account_type": "paper",
            "is_default": True,
            "strategy_profile": "strategy_a",
            "strategy_version": "v1",
            "universe_profile": "universe_a",
            "universe_version": "v1",
        }],
    }
    registry = {
        "schema_version": binding.REGISTRY_SCHEMA,
        "strategy": [{
            "id": "strategy_a",
            "version": "v1",
            "content": {"parameters": {"entry_period": 12}},
        }],
        "universe": [{
            "id": "universe_a",
            "version": "v1",
            "content": {"kind": "symbols", "symbols": ["AAA", "BBB"]},
        }],
    }
    _write_json(account_file, account_config)
    _write_json(registry_file, registry)
    monkeypatch.setattr(profiles, "_default_settings_path", lambda: account_file)
    monkeypatch.setattr(binding, "paper_binding_registry_path", lambda: registry_file)
    monkeypatch.setattr(paths, "PAPER_ACCOUNTS_ROOT", tmp_path / "accounts")

    account_paths = paths.build_paper_account_paths(ACCOUNT_ID)
    initialize_paper_account(
        account_id=ACCOUNT_ID,
        initial_cash=12345,
        currency="USD",
        date_str=DATA_DATE,
        confirm_create=True,
        account_root=account_paths.root,
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    wrappers = tmp_path / "wrappers"
    wrappers.mkdir()
    account_local = wrappers / "_account.local.cmd"
    account_local.write_bytes(
        b'@echo off\r\nset "ACCOUNT_ID=paper_fresh"\r\nset "ACCOUNT_MODE=PAPER"\r\nexit /b 0\r\n'
    )
    calendar = MarketCalendar(
        "US",
        "America/New_York",
        date(2026, 1, 1),
        date(2026, 12, 31),
        frozenset({date(2026, 7, 3)}),
    )
    return {
        "account_file": account_file,
        "account_config": account_config,
        "registry_file": registry_file,
        "registry": registry,
        "account_paths": account_paths,
        "workspace": workspace,
        "account_local": account_local,
        "day_local": wrappers / "_runbook_day.local.cmd",
        "calendar": calendar,
    }


def _prepare(env: dict, data_date: str = DATA_DATE) -> dict:
    return prepare_first_run(
        account_id=ACCOUNT_ID,
        data_date=data_date,
        workspace=env["workspace"],
        account_local_path=env["account_local"],
        runbook_day_local_path=env["day_local"],
        calendar=env["calendar"],
    )


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def _prepare_artifact_paths(env: dict) -> tuple[Path, Path, Path]:
    evidence_path = prepare_evidence_path(env["account_paths"])
    state_path = runbook_state.get_state_path_for_context(
        env["workspace"], ACCOUNT_ID, DATA_DATE, TRADE_DATE
    )
    return env["day_local"], evidence_path, state_path


def _assert_recovery_retry_is_byte_stable(env: dict) -> None:
    before = _tree_bytes(env["workspace"].parent)
    retry = _prepare(env)
    assert retry["runner_result"] == "BLOCKED", retry
    assert retry["result"] == "RECOVERY_REQUIRED", retry
    assert _tree_bytes(env["workspace"].parent) == before


def test_prepare_first_run_creates_ready_last_contract(first_run: dict) -> None:
    result = _prepare(first_run)
    assert result["runner_result"] == "PASS", result
    assert result["result"] == "PREPARED"
    assert result["trade_date"] == TRADE_DATE
    assert result["prepare_identity_digest"].startswith("sha256:")
    assert len(result["prepare_identity_digest"]) == 71
    assert read_runbook_day_local(first_run["day_local"], account_id=ACCOUNT_ID) == {
        "DATA_DATE": DATA_DATE,
        "TRADE_DATE": TRADE_DATE,
        "RUNBOOK_DAY_ID": result["runbook_day_id"],
    }
    evidence = json.loads(prepare_evidence_path(first_run["account_paths"]).read_text(encoding="utf-8"))
    assert evidence["prepare_identity_digest"] == result["prepare_identity_digest"]
    assert evidence["bootstrap_identity_summary"]["initial_cash"] == 12345.0
    state = runbook_state.load_state(Path(result["state_path"]))
    assert state.current_stage == "A"
    assert state.current_status == "READY"
    assert set(state.stage_status.values()) == {"PENDING"}
    assert state.execution_contract["version"] == runbook_state.EXECUTION_CONTRACT_V3


def test_exact_retry_reuses_without_rewrite(first_run: dict) -> None:
    first = _prepare(first_run)
    assert first["result"] == "PREPARED"
    before = _tree_bytes(first_run["workspace"].parent)
    second = _prepare(first_run)
    assert second["result"] == "REUSE", second
    assert second["prepare_identity_digest"] == first["prepare_identity_digest"]
    assert _tree_bytes(first_run["workspace"].parent) == before


def test_fault_before_context_leaves_no_prepare_artifact_and_retry_prepares(
    first_run: dict, monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_write = first_run_module.write_runbook_day_local_exact

    def fail_before_context(*args, **kwargs):
        raise OSError("fault_before_context")

    monkeypatch.setattr(first_run_module, "write_runbook_day_local_exact", fail_before_context)
    failed = _prepare(first_run)
    assert failed["runner_result"] == "BLOCKED", failed
    day_path, evidence_path, state_path = _prepare_artifact_paths(first_run)
    assert not day_path.exists()
    assert not evidence_path.exists()
    assert not state_path.exists()

    monkeypatch.setattr(first_run_module, "write_runbook_day_local_exact", original_write)
    assert _prepare(first_run)["result"] == "PREPARED"


def test_fault_after_context_requires_recovery_without_rewrite(
    first_run: dict, monkeypatch: pytest.MonkeyPatch,
) -> None:
    day_path, evidence_path, state_path = _prepare_artifact_paths(first_run)
    lifecycle_dir = evidence_path.parent
    original_mkdir = Path.mkdir

    def fail_after_context(path: Path, *args, **kwargs):
        if path == lifecycle_dir:
            raise OSError("fault_after_context")
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fail_after_context)
    failed = _prepare(first_run)
    assert failed["runner_result"] == "BLOCKED", failed
    assert day_path.is_file()
    assert not evidence_path.exists()
    assert not state_path.exists()

    monkeypatch.setattr(Path, "mkdir", original_mkdir)
    _assert_recovery_retry_is_byte_stable(first_run)


def test_fault_before_evidence_durable_requires_recovery_without_rewrite(
    first_run: dict, monkeypatch: pytest.MonkeyPatch,
) -> None:
    day_path, evidence_path, state_path = _prepare_artifact_paths(first_run)
    temp_path = evidence_path.with_name(f"{evidence_path.name}.tmp")
    original_write_text = Path.write_text

    def fail_before_evidence(path: Path, *args, **kwargs):
        if path == temp_path:
            raise OSError("fault_before_evidence")
        return original_write_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_before_evidence)
    failed = _prepare(first_run)
    assert failed["runner_result"] == "BLOCKED", failed
    assert day_path.is_file()
    assert not evidence_path.exists()
    assert not temp_path.exists()
    assert not state_path.exists()

    monkeypatch.setattr(Path, "write_text", original_write_text)
    _assert_recovery_retry_is_byte_stable(first_run)


def test_fault_immediately_after_evidence_requires_recovery_without_rewrite(
    first_run: dict, monkeypatch: pytest.MonkeyPatch,
) -> None:
    day_path, evidence_path, state_path = _prepare_artifact_paths(first_run)
    original_replace = Path.replace

    def fail_after_evidence(path: Path, target: Path):
        result = original_replace(path, target)
        if Path(target) == evidence_path:
            raise OSError("fault_after_evidence")
        return result

    monkeypatch.setattr(Path, "replace", fail_after_evidence)
    failed = _prepare(first_run)
    assert failed["runner_result"] == "BLOCKED", failed
    assert day_path.is_file()
    assert evidence_path.is_file()
    assert not state_path.exists()

    monkeypatch.setattr(Path, "replace", original_replace)
    _assert_recovery_retry_is_byte_stable(first_run)


def test_fault_immediately_before_state_requires_recovery_without_rewrite(
    first_run: dict, monkeypatch: pytest.MonkeyPatch,
) -> None:
    day_path, evidence_path, state_path = _prepare_artifact_paths(first_run)
    original_save = runbook_state.save_state

    def fail_before_state(*args, **kwargs):
        raise OSError("fault_before_state")

    monkeypatch.setattr(runbook_state, "save_state", fail_before_state)
    failed = _prepare(first_run)
    assert failed["runner_result"] == "BLOCKED", failed
    assert day_path.is_file()
    assert evidence_path.is_file()
    assert not state_path.exists()

    monkeypatch.setattr(runbook_state, "save_state", original_save)
    _assert_recovery_retry_is_byte_stable(first_run)


def test_fault_immediately_after_state_retries_as_byte_stable_reuse(
    first_run: dict, monkeypatch: pytest.MonkeyPatch,
) -> None:
    day_path, evidence_path, state_path = _prepare_artifact_paths(first_run)
    original_validate = first_run_module._validate_existing_prepared

    def fail_after_state(**kwargs):
        assert state_path.is_file()
        raise OSError("fault_after_state")

    monkeypatch.setattr(first_run_module, "_validate_existing_prepared", fail_after_state)
    failed = _prepare(first_run)
    assert failed["runner_result"] == "BLOCKED", failed
    assert day_path.is_file()
    assert evidence_path.is_file()
    assert state_path.is_file()

    monkeypatch.setattr(first_run_module, "_validate_existing_prepared", original_validate)
    before = _tree_bytes(first_run["workspace"].parent)
    retry = _prepare(first_run)
    assert retry["runner_result"] == "PASS", retry
    assert retry["result"] == "REUSE", retry
    assert _tree_bytes(first_run["workspace"].parent) == before


def test_stage_a_progress_then_prepare_returns_resume(first_run: dict) -> None:
    prepared = _prepare(first_run)
    state_path = Path(prepared["state_path"])
    state = runbook_state.start_stage(runbook_state.load_state(state_path), "A")
    runbook_state.save_state(state, state_path)
    before = _tree_bytes(first_run["workspace"].parent)
    retried = _prepare(first_run)
    assert retried["result"] == "RESUME_EXISTING_RUN", retried
    assert _tree_bytes(first_run["workspace"].parent) == before


@pytest.mark.parametrize("missing", ["context", "evidence", "context_and_state", "evidence_and_state"])
def test_inconsistent_partial_combinations_fail_closed_without_write(
    first_run: dict, missing: str,
) -> None:
    prepared = _prepare(first_run)
    assert prepared["result"] == "PREPARED"
    day_path, evidence_path, state_path = _prepare_artifact_paths(first_run)
    if missing in {"context", "context_and_state"}:
        day_path.unlink()
    if missing in {"evidence", "evidence_and_state"}:
        evidence_path.unlink()
    if missing in {"context_and_state", "evidence_and_state"}:
        state_path.unlink()

    _assert_recovery_retry_is_byte_stable(first_run)


def test_materialized_initial_cash_remains_authority(first_run: dict) -> None:
    first_run["account_config"]["accounts"][0]["initial_cash"] = 99999
    _write_json(first_run["account_file"], first_run["account_config"])
    result = _prepare(first_run)
    assert result["result"] == "PREPARED", result
    evidence = json.loads(prepare_evidence_path(first_run["account_paths"]).read_text(encoding="utf-8"))
    assert evidence["bootstrap_identity_summary"]["initial_cash"] == 12345.0


@pytest.mark.parametrize(
    "data_date,expected_trade_date",
    [("2026-10-02", "2026-10-05"), ("2026-10-03", "2026-10-05"), ("2026-07-02", "2026-07-06")],
)
def test_trade_date_is_calendar_derived(first_run: dict, data_date: str, expected_trade_date: str) -> None:
    if data_date != DATA_DATE:
        first_run["account_paths"].account_snapshot_path.write_text(
            first_run["account_paths"].account_snapshot_path.read_text(encoding="utf-8-sig")
            .replace(DATA_DATE, data_date)
            .replace(DATA_DATE.replace("-", ""), data_date.replace("-", "")),
            encoding="utf-8-sig",
        )
        old_state = first_run["account_paths"].current_state_snapshot_path(DATA_DATE)
        new_state = first_run["account_paths"].current_state_snapshot_path(data_date)
        payload = json.loads(old_state.read_text(encoding="utf-8"))
        payload["snapshot_date"] = data_date
        new_state.write_text(json.dumps(payload), encoding="utf-8")
        old_state.unlink()
    result = _prepare(first_run, data_date)
    assert result["runner_result"] == "PASS", result
    assert result["trade_date"] == expected_trade_date


def test_calendar_coverage_failure_is_closed(first_run: dict) -> None:
    outside = MarketCalendar("US", "America/New_York", date(2025, 1, 1), date(2025, 12, 31), frozenset())
    result = prepare_first_run(
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        workspace=first_run["workspace"],
        account_local_path=first_run["account_local"],
        runbook_day_local_path=first_run["day_local"],
        calendar=outside,
    )
    assert result["runner_result"] == "BLOCKED"


def test_different_date_and_binding_drift_fail_closed(first_run: dict) -> None:
    assert _prepare(first_run)["result"] == "PREPARED"
    assert _prepare(first_run, "2026-10-03")["result"] == "CONFLICT"
    first_run["registry"]["strategy"][0]["content"]["parameters"]["entry_period"] = 20
    _write_json(first_run["registry_file"], first_run["registry"])
    drift = _prepare(first_run)
    assert drift["runner_result"] == "BLOCKED"
    assert drift["result"] == "CONFLICT"


def test_partial_prepare_requires_recovery(first_run: dict) -> None:
    result = _prepare(first_run)
    Path(result["state_path"]).unlink()
    retry = _prepare(first_run)
    assert retry["result"] == "RECOVERY_REQUIRED"
    assert not Path(result["state_path"]).exists()


def test_bootstrap_or_evidence_tamper_fails_closed(first_run: dict) -> None:
    prepared = _prepare(first_run)
    snapshot = first_run["account_paths"].account_snapshot_path
    snapshot.write_bytes(snapshot.read_bytes() + b"\n")
    bootstrap_drift = _prepare(first_run)
    assert bootstrap_drift["result"] == "CONFLICT"
    assert any("bootstrap_identity_mismatch" in item for item in bootstrap_drift["blockers"])

    snapshot.write_bytes(snapshot.read_bytes().rstrip(b"\n") + b"\n")
    evidence_path = prepare_evidence_path(first_run["account_paths"])
    evidence_path.write_text("{", encoding="utf-8")
    evidence_drift = _prepare(first_run)
    assert evidence_drift["result"] == "CONFLICT"


def test_multiple_states_fail_closed(first_run: dict) -> None:
    assert _prepare(first_run)["result"] == "PREPARED"
    other = runbook_state.create_initial_state(ACCOUNT_ID, "2026-10-05", "2026-10-06")
    other_path = runbook_state.get_state_path_for_context(
        first_run["workspace"], ACCOUNT_ID, "2026-10-05", "2026-10-06"
    )
    runbook_state.save_state(other, other_path)
    result = _prepare(first_run)
    assert result["result"] == "CONFLICT"
    assert result["reason"] == "multiple_states"


def test_rehashed_evidence_context_tamper_fails_closed(first_run: dict) -> None:
    assert _prepare(first_run)["result"] == "PREPARED"
    evidence_path = prepare_evidence_path(first_run["account_paths"])
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["data_date"] = "2026-10-01"
    payload["prepare_identity"]["data_date"] = "2026-10-01"
    payload["prepare_identity_digest"] = sha256_payload(payload["prepare_identity"])
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")
    result = _prepare(first_run)
    assert result["result"] == "CONFLICT"
    assert any("prepare_identity_context_mismatch" in item for item in result["blockers"])


def test_unprepared_fresh_stage_a_blocked_then_prepared_allowed(first_run: dict) -> None:
    blocked = runbook_stage_runner.run_stage_a(
        first_run["workspace"], ACCOUNT_ID, DATA_DATE, TRADE_DATE, dry_run=True
    )
    assert blocked["runner_result"] == "BLOCKED"
    assert blocked["reason"] == "prepare_first_run_required"
    assert _prepare(first_run)["result"] == "PREPARED"
    assert first_run_module.stage_a_prepare_guard(
        first_run["workspace"], ACCOUNT_ID, DATA_DATE, TRADE_DATE
    ) is None
    before = _tree_bytes(first_run["workspace"].parent)
    allowed = runbook_stage_runner.run_stage_a(
        first_run["workspace"], ACCOUNT_ID, DATA_DATE, TRADE_DATE, dry_run=True
    )
    # Passing the first-run guard is necessary but Stage A now also requires
    # an explicit participant set and an already published package for dry-run.
    assert allowed["runner_result"] == "BLOCKED", allowed
    assert allowed["reason"] == "Explicit participants are required"
    assert _tree_bytes(first_run["workspace"].parent) == before
    assert _prepare(first_run)["result"] == "REUSE"


def test_cli_surface_accepts_only_account_and_data_date(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys,
) -> None:
    market_db = tmp_path / "market_data.db"
    market_db.touch()
    monkeypatch.setenv("STOCK_SCREENER_MARKET_DB", str(market_db))
    from scripts import paper

    captured: dict[str, object] = {}

    def fake_prepare(**kwargs):
        captured.update(kwargs)
        return {
            "runner_result": "PASS", "result": "PREPARED", "account_id": ACCOUNT_ID,
            "data_date": DATA_DATE, "trade_date": TRADE_DATE, "runbook_day_id": "day",
            "prepare_identity_digest": "a" * 64,
        }

    monkeypatch.setattr(paper, "prepare_first_run", fake_prepare)
    monkeypatch.setattr(paper, "runbook_workspace_path", lambda: Path("workspace"))
    monkeypatch.setattr(paper, "runbook_wrappers_dir", lambda: Path("wrappers"))
    assert paper.main(["prepare-first-run", "--account-id", ACCOUNT_ID, "--data-date", DATA_DATE, "--json"]) == 0
    assert captured["account_id"] == ACCOUNT_ID
    assert captured["data_date"] == DATA_DATE
    assert "trade_date" not in captured
    assert json.loads(capsys.readouterr().out)["result"] == "PREPARED"

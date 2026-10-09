from __future__ import annotations

import csv
import json
import os
import sqlite3
import stat
import subprocess
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import paper_account_binding as binding
from core import paper_account_paths as account_paths
from core import paper_account_profile as profiles
from core import paper_prepare_data as prepare
from core import paper_shared_market_prepare as shared
from core.paper_execution_log import PAPER_EXECUTION_LOG_COLUMNS
from tests.paper_account_test_support import create_initialized_account_paths

DATA_DATE = "2026-10-01"
PARTICIPANTS = ["synthetic_a", "synthetic_b"]


def write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def package_bytes(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def seed_market(conn, stocks, indices):
    dates = []
    current = date.fromisoformat(DATA_DATE)
    while len(dates) < 300:
        if current.weekday() < 5:
            dates.append(current.isoformat())
        current -= timedelta(days=1)
    for symbol in stocks:
        conn.execute("INSERT OR IGNORE INTO tickers VALUES (?, ?)", (symbol, "NASDAQ100" if symbol == "BREADTH" else "US_Stock"))
        conn.executemany("INSERT OR IGNORE INTO daily_price VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                         [(symbol, d, 108, 115, 100, 110, 110, 1000000) for d in dates])
        conn.execute("INSERT OR IGNORE INTO daily_indicators VALUES (?, ?, ?, ?, ?)", (symbol, DATA_DATE, 105, 3, 55))
    for symbol in indices:
        conn.executemany("INSERT OR IGNORE INTO market_index VALUES (?, ?, ?)", [(symbol, d, 100) for d in dates])
    conn.commit()


@pytest.fixture
def environment(tmp_path, monkeypatch):
    profile_path, registry_path = tmp_path / "profiles.json", tmp_path / "registry.json"
    profile_payload = {"schema_version": profiles.VERSIONED_ACCOUNT_PROFILE_SCHEMA,
                       "default_account_id": PARTICIPANTS[0], "accounts": [
        {"account_id": account_id, "display_name": account_id, "currency": "USD", "initial_cash": 100000,
         "account_type": "paper", "is_default": i == 0, "strategy_profile": "strategy", "strategy_version": "v1",
         "universe_profile": f"universe_{i}", "universe_version": "v1"}
        for i, account_id in enumerate(PARTICIPANTS)
    ]}
    registry = {"schema_version": binding.REGISTRY_SCHEMA,
                "strategy": [{"id": "strategy", "version": "v1", "content": {"parameters": {}}}],
                "universe": [
                    {"id": "universe_0", "version": "v1", "content": {"kind": "symbols", "symbols": ["AAPL"]}},
                    {"id": "universe_1", "version": "v1", "content": {"kind": "symbols", "symbols": ["META"]}},
                ]}
    write_json(profile_path, profile_payload)
    write_json(registry_path, registry)
    monkeypatch.setattr(profiles, "_default_settings_path", lambda: profile_path)
    monkeypatch.setattr(binding, "paper_binding_registry_path", lambda: registry_path)
    accounts_root = tmp_path / "accounts"
    monkeypatch.setattr(account_paths, "PAPER_ACCOUNTS_ROOT", accounts_root)
    paths = {account_id: create_initialized_account_paths(accounts_root / account_id, account_id=account_id)
             for account_id in PARTICIPANTS}
    with paths[PARTICIPANTS[0]].execution_log_path.open("a", encoding="utf-8", newline="") as handle:
        csv.DictWriter(handle, fieldnames=PAPER_EXECUTION_LOG_COLUMNS).writerow({
            "trade_id": "held-1", "date": "2026-09-01", "symbol": "HOLD", "side": "BUY", "shares": 2, "price": 100,
        })
    universe_path = tmp_path / "universe_snapshot_20261001.json"
    write_json(universe_path, {"active_symbols": ["AAPL", "META", "BREADTH"], "effective_as_of": DATA_DATE,
                              "observed_at": "2026-10-01T08:00:00+09:00", "source": "synthetic_universe",
                              "source_revision": "fixture-v1", "capture_mode": "immutable_fixture"})
    monkeypatch.setattr(shared, "load_universe_snapshot_as_of_quarter",
                        lambda _: {"metadata": {"snapshot_path": str(universe_path)}})
    db = tmp_path / "source.sqlite3"
    with sqlite3.connect(db) as conn:
        conn.executescript("""
            CREATE TABLE tickers(symbol TEXT PRIMARY KEY, listing_board TEXT);
            CREATE TABLE daily_price(symbol TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL, adj_close REAL, volume REAL, UNIQUE(symbol,date));
            CREATE TABLE daily_indicators(symbol TEXT, date TEXT, sma_200 REAL, atr_20 REAL, rsi_14 REAL, UNIQUE(symbol,date));
            CREATE TABLE market_index(symbol TEXT, date TEXT, close REAL, UNIQUE(symbol,date));
            CREATE TABLE market_status_log(date TEXT, status TEXT);
        """)
        seed_market(conn, ["AAPL", "HOLD", "BREADTH"], ["SPY", "QQQ", "^VIX"])
    root = tmp_path / "publications"
    monkeypatch.setattr(shared, "market_db_path", lambda: str(db))
    monkeypatch.setattr(shared, "shared_market_preparations_dir", lambda: root)
    calls = []

    def refresh(date_str, **kwargs):
        # Full B coverage must be known before any write/refresh.
        assert date_str == DATA_DATE
        assert not (root / DATA_DATE / shared.MANIFEST).exists()
        calls.append(kwargs)
        with sqlite3.connect(db) as conn:
            seed_market(conn, kwargs["required_symbols"], kwargs["required_index_symbols"])
        return {"errors": [], "price_update_status": "success", "indicators_update_status": "success"}

    monkeypatch.setattr(shared, "run_paper_prepare_data", refresh)
    return {"db": db, "root": root, "package": root / DATA_DATE, "calls": calls, "refresh": refresh,
            "profiles": profile_payload, "profile_path": profile_path, "registry": registry,
            "registry_path": registry_path, "universe": universe_path, "accounts": accounts_root, "paths": paths}


def run(ids=None):
    return shared.run_shared_market_prepare(data_date=DATA_DATE, participant_account_ids=PARTICIPANTS if ids is None else ids)


def manifest(environment):
    return json.loads((environment["package"] / shared.MANIFEST).read_text(encoding="utf-8"))


def assert_prepared(environment):
    result = run()
    assert result["result"] == "PREPARED", result
    return result


@pytest.mark.parametrize("ids", [[], ["unknown_account"], ["synthetic_a", "synthetic_a"], [" synthetic_a ", "synthetic_a"], ["BAD"]])
def test_invalid_participants_block_before_any_write(environment, ids):
    assert run(ids)["result"] == "BLOCKED"
    assert not environment["root"].exists()
    assert environment["calls"] == []


@pytest.mark.parametrize("failure", ["profile_version", "binding", "bootstrap", "benchmark_profile", "live"])
def test_all_participants_resolved_before_shared_mutation(environment, failure):
    if failure == "profile_version":
        environment["profiles"]["schema_version"] = profiles.ACCOUNT_PROFILE_SCHEMA_VERSION
    elif failure == "binding":
        environment["profiles"]["accounts"][1]["strategy_version"] = "unknown"
    elif failure == "bootstrap":
        environment["paths"][PARTICIPANTS[1]].execution_log_path.unlink()
    elif failure == "benchmark_profile":
        environment["profiles"]["accounts"][1]["benchmark_profile"] = "unresolved"
    else:
        environment["profiles"]["accounts"][1]["account_type"] = "live"
    write_json(environment["profile_path"], environment["profiles"])
    assert run()["result"] == "BLOCKED"
    assert not environment["root"].exists()
    assert environment["calls"] == []


def test_union_before_refresh_includes_b_only_holdings_hedge_and_binding(environment):
    before = package_bytes(environment["accounts"])
    assert_prepared(environment)
    assert len(environment["calls"]) == 1
    assert environment["calls"][0]["required_symbols"] == ["AAPL", "BREADTH", "HOLD", "META"]
    assert {"SPY", "QQQ", "^VIX", "SQQQ", "BIL"} <= set(environment["calls"][0]["required_index_symbols"])
    m = manifest(environment)
    assert m["participant_account_ids"] == PARTICIPANTS
    assert m["participants"][1]["entry_symbols"] == ["META"]
    assert m["participants"][1]["binding"]["semantics"]["universe"]["reference"] == {"id": "universe_1", "version": "v1"}
    with sqlite3.connect(environment["package"] / shared.SNAPSHOT) as conn:
        assert conn.execute("SELECT close FROM daily_price WHERE symbol='META' AND date=?", (DATA_DATE,)).fetchone() == (110,)
    assert package_bytes(environment["accounts"]) == before
    assert not any(p.is_absolute() for p in map(Path, [m["snapshot"]["relative_path"], m["shared_universe_sources"][0]["relative_path"]]))


def test_retry_order_invariant_byte_stable_no_refresh_and_no_source_dependency(environment, monkeypatch):
    first = assert_prepared(environment)
    before = package_bytes(environment["package"])
    with sqlite3.connect(environment["db"]) as conn:
        conn.execute("DELETE FROM daily_price")
        conn.execute("INSERT INTO tickers VALUES ('NEWBREADTH', 'NASDAQ100')")
    environment["universe"].write_text("changed source after publication", encoding="utf-8")
    monkeypatch.setattr(shared, "run_paper_prepare_data", lambda *a, **k: pytest.fail("refresh on reuse"))
    monkeypatch.setattr(shared, "market_db_path", lambda: pytest.fail("source lookup on reuse"))
    retry = run(list(reversed(PARTICIPANTS)))
    assert retry["result"] == "REUSE", retry
    assert retry["shared_preparation_id"] == first["shared_preparation_id"]
    assert retry["preparation_call_count"] == 0
    assert package_bytes(environment["package"]) == before


def test_shared_snapshot_universe_resolved_for_b_before_refresh(environment):
    environment["registry"]["universe"][1]["content"] = {"kind": "shared_snapshot"}
    write_json(environment["registry_path"], environment["registry"])
    assert_prepared(environment)
    assert manifest(environment)["participants"][1]["entry_symbols"] == ["AAPL", "BREADTH", "META"]
    assert (environment["package"] / shared.UNIVERSE).read_bytes() == environment["universe"].read_bytes()


@pytest.mark.parametrize("failure", ["missing_stock", "stale_index", "missing_hedge", "mandatory_history", "missing_indicator", "silent_refresh_failure"])
def test_partial_collection_never_publishes_ready_manifest(environment, monkeypatch, failure):
    def incomplete(date_str, **kwargs):
        summary = environment["refresh"](date_str, **kwargs)
        with sqlite3.connect(environment["db"]) as conn:
            if failure == "missing_stock":
                conn.execute("DELETE FROM daily_price WHERE symbol='META'")
            elif failure == "stale_index":
                conn.execute("DELETE FROM market_index WHERE symbol='SPY' AND date=?", (DATA_DATE,))
            elif failure == "missing_hedge":
                conn.execute("DELETE FROM market_index WHERE symbol='SQQQ'")
            elif failure == "mandatory_history":
                conn.execute("DELETE FROM daily_price WHERE symbol='HOLD' AND date < ?", (DATA_DATE,))
            elif failure == "missing_indicator":
                conn.execute("DELETE FROM daily_indicators WHERE symbol='BREADTH'")
            else:
                summary["errors"] = ["silent collection failure"]
        return summary
    monkeypatch.setattr(shared, "run_paper_prepare_data", incomplete)
    assert run()["result"] == "BLOCKED"
    assert not (environment["package"] / shared.MANIFEST).exists()
    before = package_bytes(environment["package"])
    assert run()["result"] == "BLOCKED"
    assert len(environment["calls"]) == 1
    assert package_bytes(environment["package"]) == before


def test_entry_insufficient_history_exclusion_is_explicit_but_not_a_missing_input(environment, monkeypatch):
    def short_history(date_str, **kwargs):
        summary = environment["refresh"](date_str, **kwargs)
        with sqlite3.connect(environment["db"]) as conn:
            conn.execute("DELETE FROM daily_price WHERE symbol='META' AND date < ?", (DATA_DATE,))
            conn.execute("DELETE FROM daily_indicators WHERE symbol='META'")
        return summary
    monkeypatch.setattr(shared, "run_paper_prepare_data", short_history)
    assert_prepared(environment)
    assert manifest(environment)["validation"]["entry_exclusions"] == [{"symbol": "META", "reason": "missing_market_data", "asof_rows": 1}]


def test_wal_backup_includes_committed_rows_and_validates_snapshot_not_source(environment, monkeypatch):
    with sqlite3.connect(environment["db"]) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
    writer = sqlite3.connect(environment["db"])
    writer.execute("PRAGMA wal_autocheckpoint=0")
    original_validate = shared.validate_shared_snapshot
    validated = []
    def validate(path, coverage):
        assert path != environment["db"]
        assert path.name == shared.SNAPSHOT + ".tmp"
        assert not (environment["package"] / shared.MANIFEST).exists()
        validated.append(path)
        # Destroy source freshness after backup; only frozen data must govern publication.
        writer.execute("DELETE FROM market_index WHERE symbol='SPY'")
        writer.commit()
        return original_validate(path, coverage)
    monkeypatch.setattr(shared, "validate_shared_snapshot", validate)
    try:
        assert_prepared(environment)
        assert len(validated) == 1
        with sqlite3.connect(environment["package"] / shared.SNAPSHOT) as conn:
            assert conn.execute("SELECT COUNT(*) FROM daily_price WHERE symbol='META'").fetchone()[0] == 300
            assert conn.execute("SELECT COUNT(*) FROM market_index WHERE symbol='SPY'").fetchone()[0] == 300
    finally:
        writer.close()


def test_manifest_ready_last(environment, monkeypatch):
    original = shared._write_new
    seen = []
    def write(path, raw):
        seen.append(path.name)
        assert not (environment["package"] / shared.MANIFEST).exists()
        if path.name == shared.MANIFEST + ".tmp":
            m = json.loads(raw)
            assert set(p.name for p in environment["package"].iterdir()) == {shared.SNAPSHOT, shared.UNIVERSE}
            assert m["snapshot"]["sha256"] == shared.sha256_file(environment["package"] / shared.SNAPSHOT)
            assert m["validation"]["result"] == "PASS"
        original(path, raw)
    monkeypatch.setattr(shared, "_write_new", write)
    assert_prepared(environment)
    assert seen == [shared.SNAPSHOT + ".tmp", shared.UNIVERSE + ".tmp", shared.MANIFEST + ".tmp"]


@pytest.mark.parametrize("artifact", ["snapshot_only", "temporary", "empty", "manifest_only", "unknown"])
def test_preexisting_partial_artifacts_are_preserved_without_refresh(environment, artifact):
    package = environment["package"]
    package.mkdir(parents=True)
    filenames = {"snapshot_only": shared.SNAPSHOT, "temporary": shared.SNAPSHOT + ".tmp",
                 "manifest_only": shared.MANIFEST, "unknown": "unexpected"}
    if artifact in filenames:
        (package / filenames[artifact]).write_bytes(b"partial evidence")
    before = package_bytes(package)
    assert run()["result"] == "BLOCKED"
    assert package_bytes(package) == before
    assert not environment["calls"]


@pytest.mark.parametrize("tamper", ["snapshot", "manifest", "universe", "unknown", "temporary", "missing_snapshot", "schema", "validation", "coverage", "path"])
def test_published_tamper_is_fail_closed_without_repair(environment, tamper):
    assert_prepared(environment)
    package = environment["package"]
    m = manifest(environment)
    if tamper in {"snapshot", "manifest", "universe"}:
        target = {"snapshot": shared.SNAPSHOT, "manifest": shared.MANIFEST, "universe": shared.UNIVERSE}[tamper]
        (package / target).write_bytes(b"corrupt")
    elif tamper in {"unknown", "temporary"}:
        (package / ("unknown" if tamper == "unknown" else "manifest.json.tmp")).write_bytes(b"extra")
    elif tamper == "missing_snapshot":
        (package / shared.SNAPSHOT).unlink()
    else:
        if tamper == "schema":
            m["schema_version"] = "future.v9"
        elif tamper == "validation":
            m["validation"]["result"] = "FAIL"
        elif tamper == "coverage":
            m["required_coverage"]["stock_symbols"].append("NEW")
        else:
            m["snapshot"]["relative_path"] = "../escape.sqlite3"
        write_json(package / shared.MANIFEST, m)
    before = package_bytes(package)
    assert run()["result"] == "BLOCKED"
    assert len(environment["calls"]) == 1
    assert package_bytes(package) == before


@pytest.mark.parametrize("change", ["participant", "universe", "strategy", "reference", "holdings"])
def test_publication_cannot_expand_or_change_identity(environment, change):
    assert_prepared(environment)
    before = package_bytes(environment["package"])
    ids = PARTICIPANTS
    if change == "participant":
        ids = [PARTICIPANTS[0]]
    elif change == "holdings":
        with environment["paths"][PARTICIPANTS[1]].execution_log_path.open("a", encoding="utf-8", newline="") as handle:
            csv.DictWriter(handle, fieldnames=PAPER_EXECUTION_LOG_COLUMNS).writerow({
                "trade_id": "new-held", "date": DATA_DATE, "symbol": "NEW", "side": "BUY", "shares": 1, "price": 100,
            })
    else:
        registry = environment["registry"]
        if change == "universe":
            registry["universe"][1]["content"]["symbols"].append("NEW")
        elif change == "strategy":
            registry["strategy"][0]["content"]["parameters"]["entry_period"] = 13
        else:
            registry["universe"][1]["version"] = "v2"
            environment["profiles"]["accounts"][1]["universe_version"] = "v2"
            write_json(environment["profile_path"], environment["profiles"])
        write_json(environment["registry_path"], registry)
    result = run(ids)
    assert result["result"] == "BLOCKED", result
    assert result["reason"] in {"participant_conflict", "coverage_conflict"}
    assert package_bytes(environment["package"]) == before
    assert len(environment["calls"]) == 1


def test_future_rows_retained_but_cannot_satisfy_cutoff(environment, monkeypatch):
    def future(date_str, **kwargs):
        summary = environment["refresh"](date_str, **kwargs)
        with sqlite3.connect(environment["db"]) as conn:
            conn.execute("INSERT INTO daily_price VALUES ('META','2026-10-02',950,1000,900,999,999,1000000)")
        return summary
    monkeypatch.setattr(shared, "run_paper_prepare_data", future)
    assert_prepared(environment)
    with sqlite3.connect(environment["package"] / shared.SNAPSHOT) as conn:
        assert conn.execute("SELECT close FROM daily_price WHERE symbol='META' AND date='2026-10-02'").fetchone() == (999,)
    assert manifest(environment)["validation"]["data_date"] == DATA_DATE


def test_explicit_prepare_extension_reuses_collectors_without_live_universe(monkeypatch):
    calls = []
    monkeypatch.setattr(prepare, "collect_daily_tickers", lambda: pytest.fail("implicit live universe"))
    monkeypatch.setattr(prepare.data_collector, "update_market_indices", lambda **kw: calls.append(("indices", kw)))
    monkeypatch.setattr(prepare.data_collector, "update_tickers_info", lambda symbols: calls.append(("metadata", symbols)))
    monkeypatch.setattr(prepare.data_collector, "update_stock_data", lambda symbols: calls.append(("prices", symbols)))
    monkeypatch.setattr(prepare.data_processor, "update_technical_indicators", lambda: calls.append(("indicators",)))
    result = prepare.run_paper_prepare_data(DATA_DATE, required_symbols=["META", "AAPL"], required_index_symbols=["IWM"])
    assert result["price_update_status"] == "success"
    assert calls == [("indices", {"additional_symbols": ["IWM"]}), ("metadata", ["AAPL", "META"]),
                     ("prices", ["AAPL", "META"]), ("indicators",)]


def test_new_cli_is_explicit_thin_adapter(environment, capsys):
    from scripts import paper
    args = ["prepare-shared-data", "--data-date", DATA_DATE, "--json"]
    with pytest.raises(SystemExit):
        paper.main(args)
    for account_id in PARTICIPANTS:
        args += ["--participant-account-id", account_id]
    assert paper.main(args) == 0
    assert json.loads(capsys.readouterr().out)["result"] == "PREPARED"
    assert paper.main(args) == 0
    assert json.loads(capsys.readouterr().out)["result"] == "REUSE"
    args += ["--participant-account-id", "synthetic_a"]
    assert paper.main(args) == 2
    assert json.loads(capsys.readouterr().out)["result"] == "BLOCKED"


@pytest.mark.parametrize("fault", ["missing", "future", "corrupt"])
def test_unsafe_universe_blocks_before_any_refresh(environment, monkeypatch, fault):
    if fault == "missing":
        monkeypatch.setattr(shared, "load_universe_snapshot_as_of_quarter", lambda _: {"metadata": {}})
    elif fault == "future":
        payload = json.loads(environment["universe"].read_text(encoding="utf-8"))
        payload["effective_as_of"] = "2026-10-02"
        write_json(environment["universe"], payload)
    else:
        environment["universe"].write_bytes(b"corrupt")
    result = run()
    assert result["result"] == "BLOCKED", result
    assert environment["calls"] == []
    assert not environment["root"].exists()


def test_double_invocation_during_refresh_cannot_write_hybrid_package(environment, monkeypatch):
    nested = []
    def refresh(date_str, **kwargs):
        nested.append(run())
        return environment["refresh"](date_str, **kwargs)
    monkeypatch.setattr(shared, "run_paper_prepare_data", refresh)
    assert_prepared(environment)
    assert nested[0]["result"] == "BLOCKED"
    assert nested[0]["preparation_call_count"] == 0
    assert len(environment["calls"]) == 1
    assert run()["result"] == "REUSE"


def test_interrupted_manifest_publication_retains_evidence_and_blocks_retry(environment, monkeypatch):
    original = shared._write_new
    def write(path, raw):
        if path.name == shared.MANIFEST + ".tmp":
            raise OSError("injected before ready marker")
        original(path, raw)
    monkeypatch.setattr(shared, "_write_new", write)
    assert run()["result"] == "BLOCKED"
    assert set(p.name for p in environment["package"].iterdir()) == {shared.SNAPSHOT, shared.UNIVERSE}
    before = package_bytes(environment["package"])
    assert run()["result"] == "BLOCKED"
    assert package_bytes(environment["package"]) == before
    assert len(environment["calls"]) == 1


def test_custom_benchmark_policy_is_covered_and_refreshed(environment, monkeypatch):
    original = binding.make_config
    def custom(*args, **kwargs):
        result = original(*args, **kwargs)
        result["MARKET_BENCHMARK_SYMBOL"] = "IWM"
        return result
    monkeypatch.setattr(binding, "make_config", custom)
    assert_prepared(environment)
    assert "IWM" in environment["calls"][0]["required_index_symbols"]
    assert manifest(environment)["participants"][0]["benchmark_symbol"] == "IWM"


@pytest.mark.parametrize("fault", ["volume", "future_only", "breadth_change", "participant_drift"])
def test_bad_final_inputs_cannot_be_published(environment, monkeypatch, fault):
    def refresh(date_str, **kwargs):
        summary = environment["refresh"](date_str, **kwargs)
        with sqlite3.connect(environment["db"]) as conn:
            if fault == "volume":
                conn.execute("UPDATE daily_price SET volume=NULL WHERE symbol='META' AND date=?", (DATA_DATE,))
            elif fault == "future_only":
                conn.execute("UPDATE daily_price SET date='2026-10-02' WHERE symbol='META' AND date=?", (DATA_DATE,))
            elif fault == "breadth_change":
                conn.execute("INSERT INTO tickers VALUES ('NEW', 'NASDAQ100')")
            else:
                environment["registry"]["strategy"][0]["content"]["parameters"]["entry_period"] = 13
                write_json(environment["registry_path"], environment["registry"])
        return summary
    monkeypatch.setattr(shared, "run_paper_prepare_data", refresh)
    assert run()["result"] == "BLOCKED"
    assert not (environment["package"] / shared.MANIFEST).exists()


def test_collector_additional_index_reaches_existing_download_loop(monkeypatch):
    import pandas as pd

    collector = prepare.data_collector
    symbols = []
    class Cursor:
        def execute(self, *args):
            return self
        def fetchone(self):
            return (None,)
    class Connection:
        def cursor(self):
            return Cursor()
        def close(self):
            pass
    def download(symbol, **kwargs):
        symbols.append(symbol)
        return pd.DataFrame()
    monkeypatch.setattr(collector.sqlite3, "connect", lambda *a, **k: Connection())
    monkeypatch.setattr(collector, "should_skip_download_start_date", lambda *a, **k: (False, "fixture"))
    monkeypatch.setattr(collector.yf, "download", download)
    collector.update_market_indices(additional_symbols=["IWM", "SPY"])
    assert symbols.count("IWM") == 1
    assert symbols.count("SPY") == 1


def test_shared_path_resolver_does_not_create_directory(tmp_path, monkeypatch):
    from core import paths
    monkeypatch.setattr(paths, "OUTPUTS", tmp_path)
    assert paths.shared_market_preparations_dir() == tmp_path / "shared_market_preparations"
    assert not paths.shared_market_preparations_dir().exists()


def test_nonfinite_ledger_blocks_before_shared_write(environment):
    path = environment["paths"][PARTICIPANTS[0]].execution_log_path
    path.write_text(path.read_text(encoding="utf-8-sig").replace(",100,", ",NaN,"), encoding="utf-8-sig")
    result = run()
    assert result["result"] == "BLOCKED", result
    assert not environment["root"].exists()
    assert not environment["calls"]


def test_initial_cash_only_drift_reuses_materialized_account_authority(environment, monkeypatch):
    first = assert_prepared(environment)
    before = package_bytes(environment["package"])
    account_before = package_bytes(environment["accounts"])
    for profile in environment["profiles"]["accounts"]:
        profile["initial_cash"] *= 7
    write_json(environment["profile_path"], environment["profiles"])
    initial_cash_seen = []
    original = shared.build_paper_state_from_trades

    def restore(rows, **kwargs):
        initial_cash_seen.append(kwargs["initial_cash"])
        return original(rows, **kwargs)

    monkeypatch.setattr(shared, "build_paper_state_from_trades", restore)
    monkeypatch.setattr(shared, "run_paper_prepare_data", lambda *a, **k: pytest.fail("refresh on drift retry"))
    retry = run()
    assert retry["result"] == "REUSE", retry
    assert retry["shared_preparation_id"] == first["shared_preparation_id"]
    assert retry["preparation_call_count"] == 0
    expected_cash = []
    for account_id in PARTICIPANTS:
        with environment["paths"][account_id].account_snapshot_path.open(encoding="utf-8-sig") as handle:
            expected_cash.append(float(next(csv.DictReader(handle))["initial_cash"]))
    assert initial_cash_seen == expected_cash
    assert all("initial_cash" not in p["profile"] for p in manifest(environment)["participants"])
    assert package_bytes(environment["package"]) == before
    assert package_bytes(environment["accounts"]) == account_before
    assert len(environment["calls"]) == 1


PUBLICATION_TARGETS = ["ancestor", "root", "package", shared.SNAPSHOT, shared.UNIVERSE,
                       shared.MANIFEST, shared.SNAPSHOT + ".tmp", shared.UNIVERSE + ".tmp",
                       shared.MANIFEST + ".tmp"]


def publication_target(environment, name):
    root, package = environment["root"], environment["package"]
    return {"ancestor": root.parent, "root": root, "package": package}.get(name, package / name)


def forbid_publication_io(monkeypatch, root):
    # Account/profile reads remain permitted. No publication read, open, resolve,
    # write or rename may occur before the unsafe object has been rejected.
    for method in ("read_bytes", "read_text", "open", "resolve", "rename", "unlink"):
        original = getattr(Path, method)

        def guarded(path, *args, _original=original, **kwargs):
            if path == root or root in path.parents:
                pytest.fail(f"publication IO before rejection: {path}")
            return _original(path, *args, **kwargs)

        monkeypatch.setattr(Path, method, guarded)
    monkeypatch.setattr(shared, "market_db_path", lambda: pytest.fail("source lookup before rejection"))
    monkeypatch.setattr(shared, "run_paper_prepare_data", lambda *a, **k: pytest.fail("unsafe refresh"))


@pytest.mark.parametrize("prepared", [False, True], ids=["new", "reuse"])
@pytest.mark.parametrize("target_name", PUBLICATION_TARGETS)
@pytest.mark.parametrize("kind", ["symlink", "dangling", "reparse", "wrong_type", "special"])
def test_publication_unsafe_paths_block_before_io(environment, monkeypatch, prepared, target_name, kind):
    if prepared:
        assert_prepared(environment)
    target = publication_target(environment, target_name)
    directory = target_name in {"ancestor", "root", "package"}
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.mkdir() if directory else target.write_bytes(b"preserve unsafe evidence")
    before = package_bytes(environment["root"])
    original = Path.lstat
    modes = {"symlink": stat.S_IFLNK, "dangling": stat.S_IFLNK,
             "reparse": stat.S_IFDIR if directory else stat.S_IFREG,
             "wrong_type": stat.S_IFREG if directory else stat.S_IFDIR,
             "special": stat.S_IFIFO}

    def modeled_lstat(path, *args, **kwargs):
        if path == target:
            return SimpleNamespace(st_mode=modes[kind], st_file_attributes=(
                stat.FILE_ATTRIBUTE_REPARSE_POINT if kind == "reparse" else 0))
        return original(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "lstat", modeled_lstat)
        if kind == "dangling":
            original_exists = Path.exists
            patch.setattr(Path, "exists", lambda p: False if p == target else original_exists(p))
        forbid_publication_io(patch, environment["root"])
        result = run()
    assert result["result"] == "BLOCKED", result
    assert result["reason"] == "unsafe_artifact", result
    assert result["preparation_call_count"] == 0
    assert len(environment["calls"]) == int(prepared)
    assert package_bytes(environment["root"]) == before


@pytest.mark.parametrize("target_name", PUBLICATION_TARGETS)
@pytest.mark.parametrize("dangling", [False, True])
def test_actual_publication_symlink_preserves_target(environment, monkeypatch, target_name, dangling):
    # Place the ancestor under the fixture root so account inputs remain intact.
    root = environment["root"] / "outputs" / "shared_market_preparations"
    environment.update(root=root, package=root / DATA_DATE)
    monkeypatch.setattr(shared, "shared_market_preparations_dir", lambda: root)
    target = publication_target(environment, target_name)
    target.parent.mkdir(parents=True, exist_ok=True)
    directory = target_name in {"ancestor", "root", "package"}
    outside = environment["db"].parent / "outside_target"
    if not dangling:
        if directory:
            outside.mkdir()
            (outside / "sentinel").write_bytes(b"untouched")
        else:
            outside.write_bytes(b"untouched")
    try:
        target.symlink_to(outside, target_is_directory=directory)
    except OSError as exc:
        pytest.skip(f"actual symlink unavailable: {exc}; modeled matrix runs separately")
    with monkeypatch.context() as patch:
        forbid_publication_io(patch, root)
        result = run()
    assert result["result"] == "BLOCKED", result
    assert result["reason"] == "unsafe_artifact"
    assert result["preparation_call_count"] == 0
    assert target.is_symlink()
    assert not environment["calls"]
    if dangling:
        assert not outside.exists()
    elif directory:
        assert package_bytes(outside) == {"sentinel": b"untouched"}
    else:
        assert outside.read_bytes() == b"untouched"


@pytest.mark.skipif(os.name != "nt", reason="Windows junction test")
@pytest.mark.parametrize("target_name", ["ancestor", "root", "package"])
def test_actual_windows_junction_blocks_without_read_or_mutation(environment, monkeypatch, target_name):
    root = environment["root"] / "outputs" / "shared_market_preparations"
    environment.update(root=root, package=root / DATA_DATE)
    monkeypatch.setattr(shared, "shared_market_preparations_dir", lambda: root)
    target = publication_target(environment, target_name)
    target.parent.mkdir(parents=True, exist_ok=True)
    outside = environment["db"].parent / "junction_target"
    outside.mkdir()
    (outside / "sentinel").write_bytes(b"untouched")
    created = subprocess.run(["cmd", "/c", "mklink", "/J", str(target), str(outside)], capture_output=True)
    if created.returncode:
        pytest.skip(f"junction creation unavailable: {created.stderr!r}; modeled reparse matrix runs separately")
    assert target.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
    with monkeypatch.context() as patch:
        forbid_publication_io(patch, root)
        result = run()
    assert result["result"] == "BLOCKED", result
    assert result["reason"] == "unsafe_artifact"
    assert result["preparation_call_count"] == 0
    assert not environment["calls"]
    assert target.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
    assert package_bytes(outside) == {"sentinel": b"untouched"}


@pytest.mark.parametrize("target_name", ["root", "package", shared.SNAPSHOT, shared.UNIVERSE,
                                       shared.MANIFEST, shared.SNAPSHOT + ".tmp",
                                       shared.UNIVERSE + ".tmp", shared.MANIFEST + ".tmp"])
def test_actual_wrong_publication_type_blocks(environment, monkeypatch, target_name):
    target = publication_target(environment, target_name)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target_name in {"root", "package"}:
        target.write_bytes(b"not a directory")
    else:
        target.mkdir()
        (target / "sentinel").write_bytes(b"not a file")
    before = package_bytes(environment["root"]) if environment["root"].is_dir() else environment["root"].read_bytes()
    with monkeypatch.context() as patch:
        forbid_publication_io(patch, environment["root"])
        result = run()
    assert result["result"] == "BLOCKED", result
    assert result["reason"] == "unsafe_artifact"
    assert not environment["calls"]
    after = package_bytes(environment["root"]) if environment["root"].is_dir() else environment["root"].read_bytes()
    assert after == before


@pytest.mark.parametrize("artifact", [shared.SNAPSHOT + ".tmp", shared.UNIVERSE + ".tmp", shared.MANIFEST + ".tmp"])
def test_unsafe_path_introduced_during_refresh_blocks_before_publication(environment, monkeypatch, artifact):
    def refresh(date_str, **kwargs):
        summary = environment["refresh"](date_str, **kwargs)
        (environment["package"] / artifact).mkdir()
        return summary
    monkeypatch.setattr(shared, "run_paper_prepare_data", refresh)
    result = run()
    assert result["result"] == "BLOCKED", result
    assert result["reason"] == "unsafe_artifact"
    assert result["preparation_call_count"] == 1
    assert (environment["package"] / artifact).is_dir()
    assert not (environment["package"] / shared.MANIFEST).exists()

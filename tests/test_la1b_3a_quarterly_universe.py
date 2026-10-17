from __future__ import annotations

import copy
import hashlib
import json
import stat
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from core import paper_account_binding as binding
from core import paper_runtime_binding as runtime
from core import paper_shared_market_prepare as shared
from core import quarterly_universe as quarterly
from core.paper_account_profile import (
    PaperAccountProfile,
    PaperAccountProfileConfig,
    VERSIONED_ACCOUNT_PROFILE_SCHEMA,
)
from core.paths import quarterly_universe_artifact_path
from core.stage_a_asof_contract import sha256_payload
from tests import test_ml1_4b_shared_market_prepare as shared_fixtures


VERSION = "2026q4"
OBSERVED = "2026-10-01T08:00:00+09:00"
SOURCES = {
    "sp500": {
        "provider": "fixture",
        "url": "https://example.test/sp500",
        "capture_mode": "immutable_fixture",
        "source_revision": "sha256:" + hashlib.sha256(b"sp500-fixture").hexdigest(),
    },
    "nasdaq100": {
        "provider": "fixture",
        "url": "https://example.test/nasdaq100",
        "capture_mode": "immutable_fixture",
        "source_revision": "sha256:" + hashlib.sha256(b"nasdaq100-fixture").hexdigest(),
    },
}


def bundle(*, observed_at: str = OBSERVED, sources: dict | None = None) -> dict:
    return quarterly.build_quarterly_universe_bundle(
        version=VERSION,
        observed_at=observed_at,
        effective_as_of="2026-10-01",
        sp500_symbols=["SPXONLY", "AAPL"],
        nasdaq100_symbols=["META", "AAPL"],
        sources=sources or SOURCES,
    )


def _rehash(payload: dict) -> None:
    payload["artifact_hash"] = sha256_payload({
        key: payload[key]
        for key in (
            "schema_version", "version", "observed_at", "effective_as_of", "capture_id",
            "sources", "universes",
        )
    })


def test_capture_uses_one_observation_and_preserves_all_three_sets(monkeypatch):
    calls: list[str] = []
    sp500_raw = b"raw sp500 response"
    nasdaq100_raw = b"raw nasdaq100 response"
    monkeypatch.setattr(
        quarterly.universe_manager,
        "fetch_sp500_source_capture",
        lambda: calls.append("sp500") or ({"SPXONLY", "AAPL"}, sp500_raw),
    )
    monkeypatch.setattr(
        quarterly.universe_manager,
        "fetch_nasdaq100_source_capture",
        lambda: calls.append("nasdaq100") or ({"AAPL", "META"}, nasdaq100_raw),
    )

    first = quarterly.capture_quarterly_universe_bundle(
        version=VERSION, effective_as_of="2026-10-01", observed_at=OBSERVED
    )
    second = quarterly.capture_quarterly_universe_bundle(
        version=VERSION, effective_as_of="2026-10-01", observed_at=OBSERVED
    )

    assert calls == ["sp500", "nasdaq100", "sp500", "nasdaq100"]
    assert first == second
    assert first["universes"]["sp500"]["symbols"] == ["AAPL", "SPXONLY"]
    assert first["universes"]["nasdaq100"]["symbols"] == ["AAPL", "META"]
    assert first["universes"]["sp500_ex_ndx100"]["symbols"] == ["SPXONLY"]
    assert not (
        set(first["universes"]["nasdaq100"]["symbols"])
        & set(first["universes"]["sp500_ex_ndx100"]["symbols"])
    )
    assert first["artifact_hash"].startswith("sha256:")
    assert first["capture_id"].startswith("sha256:")
    assert first["sources"]["sp500"]["source_revision"] == (
        "sha256:" + hashlib.sha256(sp500_raw).hexdigest()
    )
    assert first["sources"]["nasdaq100"]["source_revision"] == (
        "sha256:" + hashlib.sha256(nasdaq100_raw).hexdigest()
    )
    assert all(first["universes"][name]["symbol_hash"].startswith("sha256:")
               for name in quarterly.SLICE_NAMES)


def test_source_capture_parses_the_same_single_fetch_bytes(monkeypatch):
    raw_by_url = {
        quarterly.universe_manager.SP500_WIKI_URL: b"sp500-http-response",
        quarterly.universe_manager.NASDAQ100_WIKI_URL: b"nasdaq100-http-response",
    }
    calls: list[str] = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        return raw_by_url[url]

    def parse(raw: bytes) -> list[pd.DataFrame]:
        if raw == raw_by_url[quarterly.universe_manager.SP500_WIKI_URL]:
            return [pd.DataFrame({"Symbol": ["AAPL", "BRK.B"]})]
        return [pd.DataFrame({"Ticker": ["AAPL", "META"]})]

    monkeypatch.setattr(quarterly.universe_manager, "_fetch_html_bytes", fetch)
    monkeypatch.setattr(quarterly.universe_manager, "_parse_html_tables", parse)
    sp500_symbols, sp500_raw = quarterly.universe_manager.fetch_sp500_source_capture()
    nasdaq100_symbols, nasdaq100_raw = quarterly.universe_manager.fetch_nasdaq100_source_capture()

    assert calls == [
        quarterly.universe_manager.SP500_WIKI_URL,
        quarterly.universe_manager.NASDAQ100_WIKI_URL,
    ]
    assert sp500_symbols == {"AAPL", "BRK-B"}
    assert nasdaq100_symbols == {"AAPL", "META"}
    assert sp500_raw == raw_by_url[quarterly.universe_manager.SP500_WIKI_URL]
    assert nasdaq100_raw == raw_by_url[quarterly.universe_manager.NASDAQ100_WIKI_URL]


def test_live_capture_cannot_be_backdated(monkeypatch):
    with pytest.raises(quarterly.QuarterlyUniverseError, match="backdated"):
        quarterly.capture_quarterly_universe_bundle(
            version=VERSION,
            effective_as_of="2026-10-01",
            observed_at="2026-10-02T08:00:00+09:00",
        )


def test_builder_rejects_duplicate_normalized_symbols():
    with pytest.raises(quarterly.QuarterlyUniverseError, match="Duplicate"):
        quarterly.build_quarterly_universe_bundle(
            version=VERSION,
            observed_at=OBSERVED,
            effective_as_of="2026-10-01",
            sp500_symbols=["BRK.B", "brk-b", "SPXONLY"],
            nasdaq100_symbols=["AAPL"],
            sources=SOURCES,
        )


@pytest.mark.parametrize(
    "tamper",
    [
        "schema", "version", "source", "duplicate", "unsorted", "slice_hash",
        "set_difference", "intersection", "artifact_hash",
    ],
)
def test_validator_rejects_schema_slice_and_hash_tampering(tamper):
    payload = copy.deepcopy(bundle())
    if tamper == "schema":
        payload["schema_version"] = "future.v9"
    elif tamper == "version":
        payload["version"] = "2026q3"
    elif tamper == "source":
        payload["sources"].pop("nasdaq100")
    elif tamper == "duplicate":
        payload["universes"]["nasdaq100"]["symbols"].append("AAPL")
    elif tamper == "unsorted":
        payload["universes"]["nasdaq100"]["symbols"].reverse()
    elif tamper == "slice_hash":
        payload["universes"]["nasdaq100"]["symbol_hash"] = "sha256:" + "0" * 64
    elif tamper == "set_difference":
        row = payload["universes"]["sp500_ex_ndx100"]
        row["symbols"] = ["AAPL", "SPXONLY"]
        row["symbol_hash"] = sha256_payload(row["symbols"])
        _rehash(payload)
    elif tamper == "intersection":
        row = payload["universes"]["sp500_ex_ndx100"]
        row["symbols"] = ["AAPL", "SPXONLY"]
        row["symbol_hash"] = sha256_payload(row["symbols"])
        _rehash(payload)
    else:
        payload["artifact_hash"] = "sha256:" + "0" * 64

    with pytest.raises(quarterly.QuarterlyUniverseError):
        quarterly.validate_quarterly_universe_bundle(payload)


@pytest.mark.parametrize("revision", [None, "", "fixture-v1", "sha256:" + "A" * 64])
def test_builder_rejects_missing_empty_or_malformed_source_revision(revision):
    sources = copy.deepcopy(SOURCES)
    if revision is None:
        sources["sp500"].pop("source_revision")
    else:
        sources["sp500"]["source_revision"] = revision
    with pytest.raises(quarterly.QuarterlyUniverseError):
        bundle(sources=sources)


def test_capture_id_is_deterministic_and_changes_with_source_revision():
    first = bundle()
    reordered = {"nasdaq100": copy.deepcopy(SOURCES["nasdaq100"]),
                 "sp500": copy.deepcopy(SOURCES["sp500"])}
    assert bundle(sources=reordered)["capture_id"] == first["capture_id"]

    changed = copy.deepcopy(SOURCES)
    changed["nasdaq100"]["source_revision"] = "sha256:" + hashlib.sha256(b"changed").hexdigest()
    assert bundle(sources=changed)["capture_id"] != first["capture_id"]


@pytest.mark.parametrize("field", ["capture_id", "source_metadata"])
def test_validator_rejects_capture_id_and_source_metadata_tampering(field):
    payload = copy.deepcopy(bundle())
    if field == "capture_id":
        payload["capture_id"] = "sha256:" + "0" * 64
    else:
        payload["sources"]["sp500"]["provider"] = "tampered"
    with pytest.raises(quarterly.QuarterlyUniverseError):
        quarterly.validate_quarterly_universe_bundle(payload)


def test_publish_is_ready_last_immutable_and_contained(tmp_path: Path):
    payload = bundle()
    target = quarterly.publish_quarterly_universe_bundle(payload, outputs_root=tmp_path)
    before = target.read_bytes()

    assert target == quarterly_universe_artifact_path(VERSION, outputs_root=tmp_path)
    assert quarterly.load_quarterly_universe_bundle(VERSION, outputs_root=tmp_path) == payload
    assert not target.with_name(target.name + ".tmp").exists()
    with pytest.raises(quarterly.QuarterlyUniverseError, match="already claimed"):
        quarterly.publish_quarterly_universe_bundle(payload, outputs_root=tmp_path)
    assert target.read_bytes() == before
    with pytest.raises(ValueError, match="invalid quarterly universe version"):
        quarterly_universe_artifact_path("../escape", outputs_root=tmp_path)


def test_partial_and_wrong_type_publication_paths_fail_closed(tmp_path: Path):
    partial_root = tmp_path / "partial"
    partial_package = quarterly_universe_artifact_path(VERSION, outputs_root=partial_root).parent
    partial_package.mkdir(parents=True)
    (partial_package / (quarterly.ARTIFACT_NAME + ".tmp")).write_bytes(b"partial")
    with pytest.raises(quarterly.QuarterlyUniverseError, match="partial"):
        quarterly.load_quarterly_universe_bundle(VERSION, outputs_root=partial_root)

    wrong_root = tmp_path / "wrong"
    wrong_type = wrong_root / "universe" / "quarterly"
    wrong_type.parent.mkdir(parents=True)
    wrong_type.write_bytes(b"not a directory")
    with pytest.raises(quarterly.QuarterlyUniverseError, match="Wrong quarterly artifact path type"):
        quarterly.publish_quarterly_universe_bundle(bundle(), outputs_root=wrong_root)

    artifact_dir_root = tmp_path / "artifact-dir"
    artifact_path = quarterly_universe_artifact_path(VERSION, outputs_root=artifact_dir_root)
    artifact_path.mkdir(parents=True)
    with pytest.raises(quarterly.QuarterlyUniverseError, match="Wrong quarterly artifact path type"):
        quarterly.publish_quarterly_universe_bundle(bundle(), outputs_root=artifact_dir_root)


def test_missing_child_beneath_linked_ancestor_is_blocked_before_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    outputs_root = tmp_path / "outputs"
    linked_ancestor = outputs_root / "universe"
    original_lstat = Path.lstat

    def fake_lstat(path: Path):
        if path == linked_ancestor:
            return SimpleNamespace(st_mode=stat.S_IFLNK | 0o777, st_file_attributes=0)
        return original_lstat(path)

    monkeypatch.setattr(Path, "lstat", fake_lstat)
    with pytest.raises(quarterly.QuarterlyUniverseError, match="Linked quarterly artifact path"):
        quarterly.publish_quarterly_universe_bundle(bundle(), outputs_root=outputs_root)
    assert not (outputs_root / "universe" / "quarterly").exists()


def test_missing_version_beneath_reparse_ancestor_is_blocked_before_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    outputs_root = tmp_path / "outputs"
    reparse_ancestor = outputs_root / "universe" / "quarterly"
    original_lstat = Path.lstat

    def fake_lstat(path: Path):
        if path == reparse_ancestor:
            return SimpleNamespace(
                st_mode=stat.S_IFDIR | 0o777,
                st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT,
            )
        return original_lstat(path)

    monkeypatch.setattr(Path, "lstat", fake_lstat)
    with pytest.raises(quarterly.QuarterlyUniverseError, match="Reparse quarterly artifact path"):
        quarterly.publish_quarterly_universe_bundle(bundle(), outputs_root=outputs_root)
    assert not (reparse_ancestor / VERSION).exists()


def _profiles() -> PaperAccountProfileConfig:
    profile = PaperAccountProfile(
        account_id="paper_ndx100",
        display_name="NASDAQ 100 Paper",
        currency="USD",
        initial_cash=10000,
        account_type="paper",
        is_default=True,
        strategy_profile="core_strategy",
        strategy_version="v1",
        universe_profile="nasdaq100",
        universe_version=VERSION,
    )
    return PaperAccountProfileConfig(
        schema_version=VERSIONED_ACCOUNT_PROFILE_SCHEMA,
        default_account_id=profile.account_id,
        accounts=(profile,),
    )


def _registry(symbols: list[str]) -> dict:
    return {
        "schema_version": binding.REGISTRY_SCHEMA,
        "strategy": [{"id": "core_strategy", "version": "v1", "content": {"parameters": {}}}],
        "universe": [{
            "id": "nasdaq100",
            "version": VERSION,
            "content": {"kind": "symbols", "symbols": symbols},
        }],
    }


def test_binding_exact_match_and_runtime_provenance_pin():
    payload = bundle()
    resolved = binding.resolve_account_binding(
        "paper_ndx100",
        profiles=_profiles(),
        registry=_registry(["AAPL", "META"]),
        quarterly_artifact=payload,
    )
    binding.assert_binding_matches_quarterly_artifact(resolved, payload)
    _, evidence = runtime.build_runtime_config(
        resolved, active_regime="BULL", start_date="2026-10-01", end_date="2026-10-01"
    )

    assert resolved["semantics"]["quarterly_universe"]["artifact_hash"] == payload["artifact_hash"]
    assert evidence["universe_profile"] == "nasdaq100"
    assert evidence["universe_version"] == VERSION
    assert evidence["quarterly_artifact"]["artifact_hash"] == payload["artifact_hash"]
    assert evidence["selected_universe_slice"]["symbol_hash"] == payload["universes"]["nasdaq100"]["symbol_hash"]
    changed = copy.deepcopy(evidence)
    changed["selected_universe_slice"]["symbol_hash"] = "sha256:" + "0" * 64
    with pytest.raises(binding.BindingError, match="pinned runtime binding mismatch"):
        runtime.validate_pinned_runtime_evidence(changed, evidence, include_materialization=False)


@pytest.mark.parametrize("symbols", [["AAPL"], ["AAPL", "META", "EXTRA"]])
def test_binding_missing_or_extra_symbol_is_blocked(symbols):
    with pytest.raises(binding.BindingError, match="exactly match"):
        binding.resolve_account_binding(
            "paper_ndx100", profiles=_profiles(), registry=_registry(symbols), quarterly_artifact=bundle()
        )


def test_binding_wrong_version_artifact_and_slice_hash_are_blocked():
    payload = bundle()
    wrong_version = copy.deepcopy(payload)
    wrong_version["version"] = "2026q3"
    with pytest.raises(binding.BindingError, match="invalid quarterly universe artifact"):
        binding.resolve_account_binding(
            "paper_ndx100", profiles=_profiles(), registry=_registry(["AAPL", "META"]),
            quarterly_artifact=wrong_version,
        )

    wrong_hash = copy.deepcopy(payload)
    wrong_hash["artifact_hash"] = "sha256:" + "0" * 64
    with pytest.raises(binding.BindingError, match="invalid quarterly universe artifact"):
        binding.resolve_account_binding(
            "paper_ndx100", profiles=_profiles(), registry=_registry(["AAPL", "META"]),
            quarterly_artifact=wrong_hash,
        )

    resolved = binding.resolve_account_binding(
        "paper_ndx100", profiles=_profiles(), registry=_registry(["AAPL", "META"]),
        quarterly_artifact=payload,
    )
    changed = copy.deepcopy(resolved)
    changed["semantics"]["quarterly_universe"]["slice_hash"] = "sha256:" + "0" * 64
    with pytest.raises(binding.BindingError, match="slice hash"):
        binding.validate_binding(changed)


def test_different_valid_artifact_changes_binding_identity():
    first_artifact = bundle()
    changed_sources = copy.deepcopy(SOURCES)
    changed_sources["nasdaq100"]["source_revision"] = (
        "sha256:" + hashlib.sha256(b"revision-2").hexdigest()
    )
    second_artifact = bundle(observed_at="2026-10-01T09:00:00+09:00", sources=changed_sources)
    frozen = binding.resolve_account_binding(
        "paper_ndx100", profiles=_profiles(), registry=_registry(["AAPL", "META"]),
        quarterly_artifact=first_artifact,
    )
    current = binding.resolve_account_binding(
        "paper_ndx100", profiles=_profiles(), registry=_registry(["AAPL", "META"]),
        quarterly_artifact=second_artifact,
    )
    with pytest.raises(binding.BindingError, match="drift"):
        binding.assert_binding_matches(frozen, current)


@pytest.fixture
def quarterly_shared_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    env = shared_fixtures.environment.__wrapped__(tmp_path, monkeypatch)
    payload = bundle()
    artifact_path = tmp_path / "quarterly" / VERSION / quarterly.ARTIFACT_NAME
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    monkeypatch.setattr(
        quarterly,
        "quarterly_universe_artifact_path",
        lambda version, **kwargs: artifact_path,
    )
    for index, (profile_id, symbols) in enumerate((
        ("nasdaq100", ["AAPL", "META"]),
        ("sp500_ex_ndx100", ["SPXONLY"]),
    )):
        env["profiles"]["accounts"][index]["universe_profile"] = profile_id
        env["profiles"]["accounts"][index]["universe_version"] = VERSION
        env["registry"]["universe"][index] = {
            "id": profile_id,
            "version": VERSION,
            "content": {"kind": "symbols", "symbols": symbols},
        }
    shared_fixtures.write_json(env["profile_path"], env["profiles"])
    shared_fixtures.write_json(env["registry_path"], env["registry"])
    env.update(quarterly_artifact=payload, quarterly_path=artifact_path)
    return env


def test_shared_prepare_uses_frozen_breadth_not_mutable_db_membership(quarterly_shared_environment):
    env = quarterly_shared_environment
    result = shared_fixtures.run()
    assert result["result"] == "PREPARED", result
    assert env["calls"][0]["required_symbols"] == ["AAPL", "HOLD", "META", "SPXONLY"]
    manifest = shared_fixtures.manifest(env)
    coverage = manifest["required_coverage"]
    assert coverage["breadth_symbols"] == ["AAPL", "META"]
    assert coverage["breadth_provenance"] == {
        "kind": "quarterly_universe_bundle",
        "version": VERSION,
        "artifact_hash": env["quarterly_artifact"]["artifact_hash"],
        "slice_name": "nasdaq100",
        "slice_hash": env["quarterly_artifact"]["universes"]["nasdaq100"]["symbol_hash"],
    }
    # The source DB deliberately labels only BREADTH as NASDAQ100. That mutable
    # metadata neither enters the frozen membership nor its identity.
    assert "BREADTH" not in coverage["breadth_symbols"]
    pin = shared.validate_shared_market_input(
        data_date=shared_fixtures.DATA_DATE,
        participant_account_ids=shared_fixtures.PARTICIPANTS,
    )
    assert pin["quarterly_universe"]["artifact_hash"] == env["quarterly_artifact"]["artifact_hash"]
    assert shared_fixtures.run()["result"] == "REUSE"


def test_shared_prepare_blocks_mixed_quarterly_artifact_identity():
    first = bundle()
    second = bundle(observed_at="2026-10-01T09:00:00+09:00")
    participants = [
        {"binding": {"semantics": {"quarterly_universe": {
            "artifact_version": VERSION, "artifact_hash": first["artifact_hash"],
        }}}},
        {"binding": {"semantics": {"quarterly_universe": {
            "artifact_version": VERSION, "artifact_hash": second["artifact_hash"],
        }}}},
    ]
    with pytest.raises(shared.SharedPreparationError) as exc_info:
        shared._quarterly_provenance(participants)
    assert exc_info.value.reason == "quarterly_artifact_conflict"


def test_frozen_breadth_remains_mandatory_coverage(quarterly_shared_environment, monkeypatch):
    env = quarterly_shared_environment

    def incomplete(date_str, **kwargs):
        summary = env["refresh"](date_str, **kwargs)
        import sqlite3
        with sqlite3.connect(env["db"]) as conn:
            conn.execute("DELETE FROM daily_indicators WHERE symbol='META'")
        return summary

    monkeypatch.setattr(shared, "run_paper_prepare_data", incomplete)
    result = shared_fixtures.run()
    assert result["result"] == "BLOCKED", result
    assert result["reason"] == "required_coverage_missing"
    assert not (env["package"] / shared.MANIFEST).exists()

"""Account-independent, ready-last publication of immutable Paper market inputs.

No runbook lifecycle changes belong here. A claimed date directory is retained
on failure: its evidence must be reviewed, never repaired by an exact retry.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import sqlite3
import stat
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from core.paper_account_binding import resolve_account_binding
from core.paper_account_guard import require_initialized_writer_account_paths
from core.paper_account_paths import build_paper_account_paths
from core.paper_account_profile import (
    VERSIONED_ACCOUNT_PROFILE_SCHEMA, load_paper_account_profiles,
    resolve_paper_account_profile, validate_account_id,
)
from core.paper_account_state import build_paper_state_from_trades
from core.paper_high_watermark import filter_execution_rows_on_or_before
from core.paper_prepare_data import normalize_prepare_date, run_paper_prepare_data
from core.paper_state_provider import load_paper_execution_rows_for_state
from core.paths import market_db_path, shared_market_preparations_dir
from core.runbook_calendar import load_market_calendar
from core.stage_a_asof_contract import (
    StageAAsOfContext, sha256_file, sha256_payload, validate_universe_snapshot,
)
from core.universe_manager import load_universe_snapshot_as_of_quarter

SCHEMA = "paper_shared_market_preparation.v1"
IMPLEMENTATION = "MFU-ML1-4B.v1"
VALIDATOR = "paper_shared_coverage.v1"
SNAPSHOT = "market.sqlite3"
MANIFEST = "manifest.json"
UNIVERSE = "universe.json"
IDENTITY_KEYS = (
    "schema_version", "implementation_version", "data_date", "participant_account_ids",
    "participants", "required_coverage", "required_coverage_digest", "shared_universe_sources",
)
MANIFEST_KEYS = {*IDENTITY_KEYS, "request_identity", "shared_preparation_id", "snapshot",
                 "validation", "created_at"}


class SharedPreparationError(ValueError):
    def __init__(self, reason: str, detail: str):
        self.reason = reason
        super().__init__(detail)


def _require(condition: bool, reason: str, detail: str) -> None:
    if not condition:
        raise SharedPreparationError(reason, detail)


def _symbols(values: list[str]) -> list[str]:
    _require(isinstance(values, list), "invalid_coverage", "Symbols must be a list")
    result = []
    for value in values:
        _require(isinstance(value, str) and bool(re.fullmatch(r"[A-Z0-9^][A-Z0-9^_.-]*", value)),
                 "invalid_coverage", f"Noncanonical symbol: {value!r}")
        result.append(value)
    return sorted(set(result))


def _assert_safe_path(path: Path, *, directory: bool = False) -> bool:
    """Inspect lexical ancestors before following any publication path.

    Missing paths are allowed for exclusive creation. Existing ancestors must
    be directories; the leaf must have its expected regular type. This mirrors
    ML1-3's private first-run primitive without importing that lifecycle.
    """
    _require(".." not in path.parts, "unsafe_artifact", "Parent traversal in publication path")
    absolute = path.absolute()  # Deliberately not resolve(): inspect links first.
    for part in reversed((absolute, *absolute.parents)):
        _require(not part.is_symlink(), "unsafe_artifact", f"Linked publication path: {part}")
        try:
            info = part.lstat()
        except FileNotFoundError:
            return False
        _require(not (getattr(info, "st_file_attributes", 0)
                      & stat.FILE_ATTRIBUTE_REPARSE_POINT),
                 "unsafe_artifact", f"Reparse publication path: {part}")
        expected_type = stat.S_ISDIR if part != absolute or directory else stat.S_ISREG
        _require(expected_type(info.st_mode), "unsafe_artifact", f"Invalid publication path type: {part}")
    return True


def _check_publication_paths(package: Path) -> bool:
    exists = _assert_safe_path(package, directory=True)
    for name in (SNAPSHOT, UNIVERSE, MANIFEST):
        _assert_safe_path(package / name)
        _assert_safe_path(package / (name + ".tmp"))
    return exists


def _publish_new(temporary: Path, destination: Path) -> None:
    _require(_assert_safe_path(temporary), "partial_publication", "Temporary artifact missing")
    _require(not _assert_safe_path(destination), "partial_publication", "Publication target already exists")
    temporary.rename(destination)


def _read_only(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)


def _participants(ids: list[str], data_date: str) -> list[dict]:
    _require(isinstance(ids, list) and bool(ids), "participants_required", "Explicit participants are required")
    normalized = [validate_account_id(value) for value in ids]
    _require(len(normalized) == len(set(normalized)), "duplicate_participant", "Duplicate participants")
    profiles = load_paper_account_profiles(allow_missing=False)
    _require(profiles.schema_version == VERSIONED_ACCOUNT_PROFILE_SCHEMA,
             "invalid_profile", "Versioned account profiles are required")
    result = []
    for account_id in sorted(normalized):
        profile = resolve_paper_account_profile(account_id, config=profiles)
        _require(profile.account_type == "paper", "invalid_profile", "Only Paper participants are supported")
        _require(math.isfinite(profile.initial_cash) and profile.initial_cash > 0,
                 "invalid_profile", f"Invalid profile initial cash: {account_id}")
        # benchmark_profile has no canonical resolver in the current runtime.
        _require(profile.benchmark_profile is None, "unresolved_benchmark",
                 f"Unresolved benchmark_profile for {account_id}")
        binding = resolve_account_binding(account_id, profiles=profiles)
        paths = require_initialized_writer_account_paths(
            build_paper_account_paths(account_id, allow_legacy_default=False, create=False),
            command_name="prepare-shared-data participant inspection",
        )
        with paths.account_snapshot_path.open(encoding="utf-8-sig", newline="") as handle:
            initial = next(csv.DictReader(handle), None)
        _require(bool(initial) and initial["account_id"] == account_id
                 and normalize_prepare_date(initial["snapshot_date"]) <= data_date,
                 "invalid_account_state", f"Missing as-of initial account state: {account_id}")
        initial_cash = float(initial["initial_cash"])
        _require(math.isfinite(initial_cash) and initial_cash > 0 and initial["currency"] == profile.currency,
                 "invalid_account_state", f"Invalid initial cash/currency: {account_id}")
        rows = filter_execution_rows_on_or_before(
            load_paper_execution_rows_for_state(account_paths=paths), data_date,
        )
        state = build_paper_state_from_trades(rows, initial_cash=initial_cash, currency=profile.currency)
        _require(math.isfinite(state.cash) and all(
            math.isfinite(position.avg_price) and math.isfinite(position.highest_price)
            for position in state.positions.values()
        ), "invalid_account_state", f"Nonfinite as-of ledger state: {account_id}")
        result.append({
            "account_id": account_id, "profile_schema": profiles.schema_version,
            "profile": {"account_type": profile.account_type, "currency": profile.currency,
                        "benchmark_profile": profile.benchmark_profile},
            "binding": binding, "holdings": _symbols(list(state.positions)),
        })
    return result


def _universe_input(data_date: str, participants: list[dict], frozen: Path | None = None) -> tuple[list[dict], bytes | None]:
    needed = any(p["binding"]["semantics"]["universe"]["content"]["kind"] == "shared_snapshot"
                 or p["binding"]["semantics"]["regime_policy"]["USE_MARKET_BREADTH"] for p in participants)
    if not needed:
        return [], None
    if frozen is None:
        selection = load_universe_snapshot_as_of_quarter(data_date)
        raw_path = selection.get("metadata", {}).get("snapshot_path")
        _require(bool(raw_path), "universe_missing", "No as-of shared universe source exists")
        path = Path(raw_path)
    else:
        path = frozen
        _assert_safe_path(path)
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    trade_date = load_market_calendar().next_trading_day(date.fromisoformat(data_date)).isoformat()
    context = StageAAsOfContext.build(account_id=participants[0]["account_id"],
                                    data_date=data_date, trade_date=trade_date)
    evidence = validate_universe_snapshot(payload, context=context, artifact_path=path)
    symbols = _symbols(payload["active_symbols"])
    _require(bool(symbols), "universe_missing", "Shared universe is empty")
    return [{"relative_path": UNIVERSE, "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(), "symbols": symbols,
             "source": evidence["source"], "source_revision": evidence["revision"],
             "effective_as_of": evidence["effective_as_of"], "observed_at": evidence["observed_at"],
             "capture_mode": evidence["capture_mode"]}], raw


def _coverage(data_date: str, participants: list[dict], sources: list[dict], db_path: Path) -> dict:
    from screener.screener import DEFAULT_SCREEN_START_DATE

    stocks: set[str] = set()
    holdings: set[str] = set()
    indexes = {"SPY": 1, "QQQ": 1, "^VIX": 1}
    breadth_needed = False
    for participant in participants:
        semantics = participant["binding"]["semantics"]
        universe = semantics["universe"]["content"]
        entries = universe.get("symbols") if universe["kind"] == "symbols" else sources[0]["symbols"]
        participant["entry_symbols"] = _symbols(entries)
        stocks.update(participant["entry_symbols"])
        holdings.update(participant["holdings"])
        shared, regime = semantics["shared_policy"], semantics["regime_policy"]
        hedge = _symbols(list(shared["HEDGE_TICKERS"]) + [shared["HEDGE_ASSET"]])
        participant["hedge_symbols"] = hedge
        for symbol in hedge:
            indexes.setdefault(symbol, 1)
        benchmark = _symbols([shared["MARKET_BENCHMARK_SYMBOL"]])[0]
        participant["benchmark_symbol"] = benchmark
        indexes[benchmark] = max(indexes.get(benchmark, 1), int(semantics["effective_strategy_base"]["rs_lookback"]) + 1)
        if regime["use_market_regime"]:
            trend_rows = max(int(regime["REGIME_SMA_PERIOD"]), int(regime["REGIME_SMA_SHORT_PERIOD"]))
            indexes["SPY"] = max(indexes["SPY"], trend_rows)
            indexes["QQQ"] = max(indexes["QQQ"], trend_rows)
            for switch, period in (("USE_MA_CROSS", "MA_CROSS_SLOW"), ("USE_DRAWDOWN_TRIGGER", "DD_LOOKBACK"),
                                   ("USE_CIRCUIT_BREAKER", "CB_COOLDOWN_DAYS")):
                if regime[switch]:
                    indexes["SPY"] = max(indexes["SPY"], int(regime[period]) + 1)
            if regime["USE_VIX_BREAKOUT"]:
                indexes["^VIX"] = max(indexes["^VIX"], int(regime["VIX_MA_PERIOD"]) + 1)
            breadth_needed |= bool(regime["USE_MARKET_BREADTH"])
    with closing(_read_only(db_path)) as conn:
        breadth = _symbols([r[0] for r in conn.execute("SELECT symbol FROM tickers WHERE listing_board='NASDAQ100'")]) if breadth_needed else []
        _require(not breadth_needed or bool(breadth), "breadth_missing", "Required NASDAQ100 breadth membership is empty")
        conn.execute("SELECT date, status FROM market_status_log WHERE date < ? LIMIT 1", (data_date,)).fetchall()
    stocks.update(holdings)
    stocks.update(breadth)
    return {"stock_symbols": sorted(stocks), "mandatory_stock_symbols": sorted(holdings | set(breadth)),
            "breadth_symbols": breadth, "breadth_board": "NASDAQ100" if breadth_needed else None,
            "index_minimum_rows": dict(sorted(indexes.items())),
            "screen_start_date": DEFAULT_SCREEN_START_DATE, "entry_minimum_rows": 200,
            "cutoff": data_date, "regime_history": "market_status_log_before_cutoff_optional_rows"}


def _identity(data_date: str, participants: list[dict], sources: list[dict], coverage: dict) -> dict:
    return {"schema_version": SCHEMA, "implementation_version": IMPLEMENTATION, "data_date": data_date,
            "participant_account_ids": [p["account_id"] for p in participants], "participants": participants,
            "required_coverage": coverage, "required_coverage_digest": sha256_payload(coverage),
            "shared_universe_sources": sources}


def _positive(values: tuple) -> bool:
    return all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in values)


def validate_shared_snapshot(snapshot: Path, coverage: dict) -> dict:
    """Validate the final SQLite snapshot only; future rows are never selected."""
    _assert_safe_path(snapshot)
    cutoff = coverage["cutoff"]
    exclusions = []
    with closing(_read_only(snapshot)) as conn:
        _require(conn.execute("PRAGMA quick_check").fetchall() == [("ok",)], "snapshot_invalid", "SQLite integrity failure")
        breadth = _symbols([r[0] for r in conn.execute("SELECT symbol FROM tickers WHERE listing_board='NASDAQ100'")]) if coverage["breadth_board"] else []
        _require(breadth == coverage["breadth_symbols"], "coverage_conflict", "Breadth membership changed during refresh")
        conn.execute("SELECT date, status FROM market_status_log WHERE date < ? LIMIT 1", (cutoff,)).fetchall()
        for symbol in coverage["stock_symbols"]:
            metadata = conn.execute("SELECT symbol FROM tickers WHERE symbol=?", (symbol,)).fetchone()
            prices = conn.execute("SELECT open, high, low, close, adj_close, volume FROM daily_price WHERE symbol=? AND date=?", (symbol, cutoff)).fetchall()
            _require(bool(metadata) and len(prices) == 1 and _positive(prices[0][:5])
                     and isinstance(prices[0][5], (int, float)) and math.isfinite(prices[0][5]) and prices[0][5] >= 0,
                     "required_coverage_missing", f"Missing/invalid as-of stock data: {symbol}")
            count = conn.execute("SELECT COUNT(DISTINCT date) FROM daily_price WHERE symbol=? AND date BETWEEN ? AND ?",
                                 (symbol, coverage["screen_start_date"], cutoff)).fetchone()[0]
            if count < coverage["entry_minimum_rows"] and symbol not in coverage["mandatory_stock_symbols"]:
                exclusions.append({"symbol": symbol, "reason": "missing_market_data", "asof_rows": count})
                continue
            _require(count >= coverage["entry_minimum_rows"], "required_history_missing", f"Insufficient mandatory stock history: {symbol}")
            indicators = conn.execute("SELECT sma_200, atr_20, rsi_14 FROM daily_indicators WHERE symbol=? AND date=?", (symbol, cutoff)).fetchall()
            _require(len(indicators) == 1 and _positive(indicators[0][:2])
                     and indicators[0][2] is not None and math.isfinite(indicators[0][2]),
                     "required_coverage_missing", f"Missing/invalid as-of indicators: {symbol}")
        for symbol, minimum in coverage["index_minimum_rows"].items():
            rows = conn.execute("SELECT date, close FROM market_index WHERE symbol=? AND date<=? ORDER BY date DESC LIMIT ?",
                                (symbol, cutoff, minimum)).fetchall()
            _require(len(rows) == minimum and rows[0][0] == cutoff and all(_positive((r[1],)) for r in rows),
                     "required_index_missing", f"Missing/stale/insufficient index history: {symbol}")
    return {"schema_version": VALIDATOR, "result": "PASS", "data_date": cutoff,
            "validated_stock_count": len(coverage["stock_symbols"]),
            "validated_index_count": len(coverage["index_minimum_rows"]), "entry_exclusions": exclusions}


def _write_new(path: Path, raw: bytes) -> None:
    _assert_safe_path(path)
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def _json_bytes(payload: dict) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _publication_id(manifest: dict) -> str:
    return sha256_payload({"request_identity": manifest["request_identity"],
                           "snapshot": manifest["snapshot"], "validation": manifest["validation"]})


def _reuse(package: Path, data_date: str, participants: list[dict]) -> dict:
    _check_publication_paths(package)
    _require((package / MANIFEST).is_file(), "partial_publication", "Date directory exists without ready manifest")
    manifest = json.loads((package / MANIFEST).read_text(encoding="utf-8"))
    _require(isinstance(manifest, dict) and set(manifest) == MANIFEST_KEYS,
             "manifest_invalid", "Unexpected manifest schema")
    _require(manifest["schema_version"] == SCHEMA and manifest["implementation_version"] == IMPLEMENTATION,
             "manifest_invalid", "Unsupported publication contract")
    _require(manifest["data_date"] == data_date, "manifest_invalid", "DATA_DATE mismatch")
    _require(manifest["participant_account_ids"] == [p["account_id"] for p in participants],
             "participant_conflict", "Published participant set differs")
    sources = manifest["shared_universe_sources"]
    _require(isinstance(sources, list) and len(sources) <= 1, "manifest_invalid", "Invalid universe source list")
    expected_names = {MANIFEST, SNAPSHOT} | ({UNIVERSE} if sources else set())
    _require({p.name for p in package.iterdir()} == expected_names
             and all(p.is_file() and not p.is_symlink() for p in package.iterdir()),
             "partial_publication", "Missing, temporary, linked or unknown publication artifact")
    _require(manifest["snapshot"] == {"relative_path": SNAPSHOT, "sha256": sha256_file(package / SNAPSHOT)},
             "snapshot_hash_mismatch", "Snapshot identity mismatch")
    frozen_sources, _ = _universe_input(data_date, participants, package / UNIVERSE)
    _require(frozen_sources == sources, "universe_hash_mismatch", "Frozen universe identity mismatch")
    coverage = _coverage(data_date, participants, frozen_sources, package / SNAPSHOT)
    expected = _identity(data_date, participants, frozen_sources, coverage)
    _require({k: manifest[k] for k in IDENTITY_KEYS} == expected,
             "coverage_conflict", "Published participant/binding/coverage identity differs")
    _require(manifest["request_identity"] == sha256_payload(expected)
             and manifest["shared_preparation_id"] == _publication_id(manifest),
             "manifest_invalid", "Manifest semantic/content digest mismatch")
    datetime.fromisoformat(manifest["created_at"])
    _require(manifest["validation"] == validate_shared_snapshot(package / SNAPSHOT, coverage),
             "manifest_invalid", "Published validation evidence mismatch")
    return manifest


def normalize_shared_participants(values: str | list[str] | None, account_id: str) -> list[str]:
    """Normalize an explicit operating-context participant set; never infer it."""
    if isinstance(values, str):
        values = values.split(",")
    _require(isinstance(values, list) and bool(values), "participants_required", "Explicit participants are required")
    _require(all(isinstance(value, str) for value in values), "invalid_participant", "Participant IDs must be strings")
    ids = [validate_account_id(value.strip()) for value in values]
    _require(len(ids) == len(set(ids)), "duplicate_participant", "Duplicate participants")
    _require(validate_account_id(account_id) in ids, "active_account_not_participant", "Active account must be a participant")
    return sorted(ids)


def _validated_shared_market_input(*, data_date: str, participant_account_ids: list[str]) -> dict:
    """Read-only consumer contract: validate a publication, never create/repair it."""
    normalized = normalize_prepare_date(data_date)
    package = shared_market_preparations_dir() / normalized
    _require(_check_publication_paths(package), "publication_missing", "Shared publication is missing")
    manifest = _reuse(package, normalized, _participants(participant_account_ids, normalized))
    def artifact(name: str, digest: str) -> dict:
        return {"path": str((package / name).absolute()), "sha256": digest}
    return {
        "data_date": normalized,
        "participant_account_ids": manifest["participant_account_ids"],
        "shared_preparation_id": manifest["shared_preparation_id"],
        "request_identity": manifest["request_identity"],
        "manifest": artifact(MANIFEST, sha256_file(package / MANIFEST)),
        "snapshot": artifact(SNAPSHOT, manifest["snapshot"]["sha256"]),
        "universe": artifact(UNIVERSE, manifest["shared_universe_sources"][0]["sha256"])
                    if manifest["shared_universe_sources"] else None,
        "validation_result": "PASS",
    }


def validate_shared_market_input(*, data_date: str, participant_account_ids: list[str]) -> dict:
    try:
        return _validated_shared_market_input(data_date=data_date, participant_account_ids=participant_account_ids)
    except SharedPreparationError:
        raise
    except (ValueError, RuntimeError, OSError, sqlite3.Error, KeyError, TypeError, AttributeError) as exc:
        raise SharedPreparationError("invalid_shared_input", str(exc)) from exc


def load_pinned_shared_input(state_path: str | Path, *, account_id: str, data_date: str) -> dict:
    from scripts import runbook_state

    state = runbook_state.load_state(Path(state_path))
    _require(state.frozen_context.account_id == account_id
             and state.frozen_context.data_date == normalize_prepare_date(data_date),
             "shared_context_mismatch", "Shared state context differs")
    runbook_state.assert_current_binding(state)
    pin = state.artifacts.get("shared_input")
    _require(isinstance(pin, dict), "shared_pin_required", "Stage A shared input pin is required")
    ids = normalize_shared_participants(pin.get("participant_account_ids"), account_id)
    current = validate_shared_market_input(data_date=data_date, participant_account_ids=ids)
    _require(current == pin, "shared_pin_mismatch", "Published input differs from pinned input")
    return current


def run_shared_market_prepare(*, data_date: str, participant_account_ids: list[str]) -> dict:
    """PREPARED / REUSE / BLOCKED; never modify a pre-existing date package."""
    calls = 0
    try:
        normalized = normalize_prepare_date(data_date)
        calendar = load_market_calendar()
        _require(calendar.is_trading_day(date.fromisoformat(normalized)), "invalid_data_date", "DATA_DATE must be a trading day")
        package = shared_market_preparations_dir() / normalized
        published = _check_publication_paths(package)
        participants = _participants(participant_account_ids, normalized)
        if published:
            manifest = _reuse(package, normalized, participants)
            return {"result": "REUSE", "shared_preparation_id": manifest["shared_preparation_id"],
                    "manifest_path": str(package / MANIFEST), "preparation_call_count": 0}
        sources, universe_raw = _universe_input(normalized, participants)
        source_db = Path(market_db_path())
        coverage = _coverage(normalized, participants, sources, source_db)
        identity = _identity(normalized, participants, sources, coverage)
        _check_publication_paths(package)
        package.parent.mkdir(parents=True, exist_ok=True)
        _check_publication_paths(package)
        # Exclusive mkdir is the minimal date claim. A second invoker fails closed
        # while the first owns preparation; neither repairs/overwrites the claim.
        try:
            package.mkdir()
        except FileExistsError as exc:
            raise SharedPreparationError("publication_in_progress", "Date was claimed concurrently; retry after completion") from exc
        _check_publication_paths(package)
        calls = 1
        summary = run_paper_prepare_data(normalized, required_symbols=coverage["stock_symbols"],
                                        required_index_symbols=list(coverage["index_minimum_rows"]))
        _require(not summary.get("errors") and summary.get("price_update_status") == "success"
                 and summary.get("indicators_update_status") == "success",
                 "refresh_failed", "Preparation core reported an incomplete refresh")
        _check_publication_paths(package)
        temporary = package / (SNAPSHOT + ".tmp")
        # Reserve exclusively, so an existing temporary artifact is never repaired.
        _write_new(temporary, b"")
        with closing(_read_only(source_db)) as source, closing(sqlite3.connect(temporary)) as destination:
            source.backup(destination)
            destination.execute("PRAGMA journal_mode=DELETE")
        validation = validate_shared_snapshot(temporary, coverage)
        if universe_raw is not None:
            _write_new(package / (UNIVERSE + ".tmp"), universe_raw)
            _publish_new(package / (UNIVERSE + ".tmp"), package / UNIVERSE)
        _assert_safe_path(temporary)
        with temporary.open("rb+") as handle:
            os.fsync(handle.fileno())
        _publish_new(temporary, package / SNAPSHOT)
        _check_publication_paths(package)
        current_participants = _participants(participant_account_ids, normalized)
        current_sources, _ = _universe_input(normalized, current_participants, package / UNIVERSE)
        current_coverage = _coverage(normalized, current_participants, current_sources, package / SNAPSHOT)
        _require(_identity(normalized, current_participants, current_sources, current_coverage) == identity,
                 "coverage_conflict", "Participant or frozen input identity changed during preparation")
        _require({p.name for p in package.iterdir()} == ({SNAPSHOT, UNIVERSE} if sources else {SNAPSHOT}),
                 "partial_publication", "Unexpected artifact before publication")
        manifest = {**identity, "request_identity": sha256_payload(identity),
                    "snapshot": {"relative_path": SNAPSHOT, "sha256": sha256_file(package / SNAPSHOT)},
                    "validation": validation, "created_at": datetime.now(timezone.utc).isoformat()}
        manifest["shared_preparation_id"] = _publication_id(manifest)
        _require(set(manifest) == MANIFEST_KEYS, "manifest_invalid", "Manifest construction error")
        _check_publication_paths(package)
        _write_new(package / (MANIFEST + ".tmp"), _json_bytes(manifest))
        _publish_new(package / (MANIFEST + ".tmp"), package / MANIFEST)
        return {"result": "PREPARED", "shared_preparation_id": manifest["shared_preparation_id"],
                "manifest_path": str(package / MANIFEST), "preparation_call_count": calls}
    except (ValueError, RuntimeError, OSError, sqlite3.Error, KeyError, TypeError, AttributeError) as exc:
        return {"result": "BLOCKED", "reason": getattr(exc, "reason", "invalid_input_or_artifact"),
                "detail": str(exc), "preparation_call_count": calls}

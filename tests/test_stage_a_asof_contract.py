from __future__ import annotations

import json
from pathlib import Path

import pytest

from core import paper_prepare_data
from core.daily_plan_generator import resolve_official_universe_membership
from core.paper_config_snapshot import save_paper_config_snapshot
from core.stage_a_asof_contract import (
    StageAAsOfContext,
    StageAAsOfContractError,
    sha256_payload,
    validate_config_snapshot,
    validate_stage_a_lineage,
)


DATA_DATE = "2026-06-12"
TRADE_DATE = "2026-06-15"
BEFORE_TRADE = "2026-06-15T08:00:00+09:00"
AFTER_TRADE = "2026-06-16T08:00:00+09:00"


def _context(*, observed_at: str = AFTER_TRADE) -> StageAAsOfContext:
    return StageAAsOfContext.build(
        account_id="paper_test",
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        observed_at=observed_at,
    )


def _valid_lineage() -> dict:
    common = {
        "observed_at": AFTER_TRADE,
        "revision": "test:revision",
        "validator_result": "PASS",
    }
    lineage = {
        source: {"source": source, "selected_max_date": DATA_DATE, **common}
        for source in ("market", "indicator", "rs", "account")
    }
    lineage["universe"] = {
        "source": "historical_universe",
        "effective_as_of": DATA_DATE,
        "observed_at": BEFORE_TRADE,
        "revision": "test:universe",
        "validator_result": "PASS",
    }
    lineage["config"] = {
        "source": "historical_config",
        "effective_as_of": TRADE_DATE,
        "observed_at": BEFORE_TRADE,
        "revision": "test:config",
        "validator_result": "PASS",
    }
    return lineage


def _universe_payload() -> dict:
    active = ["MSFT", "AAPL", "MSFT"]
    return {
        "as_of": DATA_DATE,
        "effective_as_of": DATA_DATE,
        "observed_at": BEFORE_TRADE,
        "source": "test_historical_provider",
        "source_revision": sha256_payload(sorted(set(active))),
        "capture_mode": "current_day_live_capture",
        "active_symbols": active,
        "added": [],
        "removed": [],
        "kept": ["AAPL", "MSFT"],
    }


def test_context_marks_delayed_official_run_historical() -> None:
    assert _context().historical is True
    assert _context(observed_at=BEFORE_TRADE).historical is False


def test_future_selected_source_blocks_instead_of_dropping() -> None:
    lineage = _valid_lineage()
    lineage["market"]["selected_max_date"] = "2026-06-13"

    with pytest.raises(StageAAsOfContractError) as exc_info:
        validate_stage_a_lineage(lineage, context=_context())

    assert exc_info.value.reason == "asof_future_source"
    assert exc_info.value.source == "market"


def test_missing_required_source_provenance_blocks() -> None:
    lineage = _valid_lineage()
    del lineage["config"]

    with pytest.raises(StageAAsOfContractError) as exc_info:
        validate_stage_a_lineage(lineage, context=_context())

    assert exc_info.value.reason == "asof_provenance_missing"
    assert exc_info.value.source == "config"


def test_historical_universe_missing_blocks_without_live_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        paper_prepare_data,
        "load_universe_snapshot_as_of_quarter",
        lambda date_str: {"snapshot": {}, "metadata": {}},
    )
    monkeypatch.setattr(
        paper_prepare_data,
        "fetch_live_basket_symbols",
        lambda: pytest.fail("historical run must not fetch live universe"),
    )

    with pytest.raises(StageAAsOfContractError) as exc_info:
        paper_prepare_data.refresh_universe_snapshot_for_date(
            DATA_DATE,
            trade_date=TRADE_DATE,
            account_id="paper_test",
            observed_at=AFTER_TRADE,
        )

    assert exc_info.value.reason == "historical_universe_snapshot_missing"


def test_current_day_universe_capture_records_provenance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target = tmp_path / "universe_snapshot_20260612.json"
    monkeypatch.setattr(
        paper_prepare_data,
        "load_universe_snapshot_as_of_quarter",
        lambda date_str: {"snapshot": {}, "metadata": {}},
    )
    monkeypatch.setattr(paper_prepare_data.data_manager, "get_ticker_list", lambda: ["AAPL"])
    monkeypatch.setattr(paper_prepare_data, "fetch_live_basket_symbols", lambda: {"AAPL", "MSFT"})

    def _save(payload: dict, date_str: str) -> Path:
        target.write_text(json.dumps(payload), encoding="utf-8")
        return target

    monkeypatch.setattr(paper_prepare_data, "save_universe_snapshot", _save)

    saved = paper_prepare_data.refresh_universe_snapshot_for_date(
        DATA_DATE,
        trade_date=TRADE_DATE,
        account_id="paper_test",
        observed_at=BEFORE_TRADE,
    )
    payload = json.loads(saved.read_text(encoding="utf-8"))

    assert payload["effective_as_of"] == DATA_DATE
    assert payload["observed_at"] == BEFORE_TRADE
    assert payload["capture_mode"] == "current_day_live_capture"
    assert payload["source_revision"].startswith("sha256:")


def test_historical_universe_present_is_reused_and_is_membership_ssot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    snapshot_path = tmp_path / "universe_snapshot_20260612.json"
    payload = _universe_payload()
    snapshot_path.write_text(json.dumps(payload), encoding="utf-8")
    metadata = {"snapshot_path": str(snapshot_path)}
    monkeypatch.setattr(
        paper_prepare_data,
        "load_universe_snapshot_as_of_quarter",
        lambda date_str: {"snapshot": payload, "metadata": metadata},
    )
    monkeypatch.setattr(
        paper_prepare_data,
        "fetch_live_basket_symbols",
        lambda: pytest.fail("valid historical snapshot must suppress live fetch"),
    )

    selected = paper_prepare_data.refresh_universe_snapshot_for_date(
        DATA_DATE,
        trade_date=TRADE_DATE,
        account_id="paper_test",
        observed_at=AFTER_TRADE,
    )
    symbols, lineage = resolve_official_universe_membership(payload, metadata, _context())

    assert selected == snapshot_path
    assert symbols == ["AAPL", "MSFT"]
    assert lineage["validator_result"] == "PASS"


def test_current_day_config_snapshot_records_immutable_provenance(tmp_path: Path) -> None:
    context = _context(observed_at=BEFORE_TRADE)
    output_path = tmp_path / "paper_config_snapshot_20260615.json"
    saved = save_paper_config_snapshot(
        plan_date=TRADE_DATE,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        market_state={"date": DATA_DATE, "regime": "BULL"},
        final_config={"max_positions": 10, "score_threshold": 1.5},
        output_path=output_path,
        archive_dir=tmp_path / "archive",
        asof_context=context,
        immutable=True,
    )
    payload = json.loads(saved.read_text(encoding="utf-8"))
    lineage = validate_config_snapshot(payload, context=context, artifact_path=saved)

    assert payload["observed_at"] == BEFORE_TRADE
    assert payload["effective_at"] == TRADE_DATE
    assert payload["full_config"]["max_positions"] == 10
    assert payload["source_revision"].startswith("sha256:")
    assert lineage["validator_result"] == "PASS"


def test_historical_config_with_future_observation_is_rejected(tmp_path: Path) -> None:
    context = _context()
    payload = {
        "data_date": DATA_DATE,
        "trade_date": TRADE_DATE,
        "observed_at": AFTER_TRADE,
        "effective_at": TRADE_DATE,
        "source_revision": "test:config",
        "full_config": {"max_positions": 10},
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(StageAAsOfContractError) as exc_info:
        validate_config_snapshot(payload, context=context, artifact_path=path)

    assert exc_info.value.reason == "asof_future_source"

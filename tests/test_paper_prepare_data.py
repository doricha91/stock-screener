from __future__ import annotations

import json
from pathlib import Path

import pytest

from core import paper_prepare_data
from core.daily_plan_generator import resolve_official_universe_membership
from core.stage_a_asof_contract import StageAAsOfContext, StageAAsOfContractError, sha256_payload


DATA_DATE = "2026-06-12"
TRADE_DATE = "2026-06-15"
BEFORE_TRADE = "2026-06-15T08:00:00+09:00"
AFTER_TRADE = "2026-06-16T08:00:00+09:00"


def _official_universe_payload(*, observed_at: str = BEFORE_TRADE) -> dict:
    symbols = ["MSFT", "AAPL", "MSFT"]
    return {
        "as_of": DATA_DATE,
        "effective_as_of": DATA_DATE,
        "observed_at": observed_at,
        "source": "test_universe",
        "source_revision": sha256_payload(sorted(set(symbols))),
        "capture_mode": "current_day_live_capture",
        "active_symbols": symbols,
        "added": [],
        "removed": [],
        "kept": ["AAPL", "MSFT"],
    }


def _base_summary_assertions(summary: dict) -> None:
    assert summary["date"] == "2026-05-13"
    assert summary["ticker_count"] == 3
    assert summary["market_db_path"] == "outputs/market_data.db"
    assert summary["errors"] == []


def test_prepare_data_calls_price_and_indicator_updates(monkeypatch):
    calls: list[object] = []

    monkeypatch.setattr(paper_prepare_data, "market_db_path", lambda: "outputs/market_data.db")
    monkeypatch.setattr(paper_prepare_data.data_collector, "get_sp500_tickers", lambda: ["MSFT", "AAPL"])
    monkeypatch.setattr(paper_prepare_data.data_collector, "get_nasdaq100_tickers", lambda: ["AAPL", "NVDA"])
    monkeypatch.setattr(paper_prepare_data.data_collector, "update_market_indices", lambda: calls.append("market_index"))
    monkeypatch.setattr(
        paper_prepare_data.data_collector,
        "update_tickers_info",
        lambda tickers: calls.append(("tickers", tickers)),
    )
    monkeypatch.setattr(
        paper_prepare_data.data_collector,
        "update_stock_data",
        lambda tickers: calls.append(("prices", tickers)),
    )
    monkeypatch.setattr(
        paper_prepare_data.data_processor,
        "update_technical_indicators",
        lambda: calls.append("indicators"),
    )

    summary = paper_prepare_data.run_paper_prepare_data("20260513")
    _base_summary_assertions(summary)
    assert summary["price_update_status"] == "success"
    assert summary["indicators_update_status"] == "success"
    assert summary["universe_update_status"] == "skipped"
    assert calls == [
        "market_index",
        ("tickers", ["AAPL", "MSFT", "NVDA"]),
        ("prices", ["AAPL", "MSFT", "NVDA"]),
        "indicators",
    ]


def test_skip_prices_skips_price_updates(monkeypatch):
    calls: list[object] = []

    monkeypatch.setattr(paper_prepare_data, "market_db_path", lambda: "outputs/market_data.db")
    monkeypatch.setattr(paper_prepare_data.data_collector, "get_sp500_tickers", lambda: ["AAPL"])
    monkeypatch.setattr(paper_prepare_data.data_collector, "get_nasdaq100_tickers", lambda: ["MSFT"])
    monkeypatch.setattr(paper_prepare_data.data_collector, "update_market_indices", lambda: calls.append("market_index"))
    monkeypatch.setattr(paper_prepare_data.data_collector, "update_tickers_info", lambda tickers: calls.append("tickers"))
    monkeypatch.setattr(paper_prepare_data.data_collector, "update_stock_data", lambda tickers: calls.append("prices"))
    monkeypatch.setattr(
        paper_prepare_data.data_processor,
        "update_technical_indicators",
        lambda: calls.append("indicators"),
    )

    summary = paper_prepare_data.run_paper_prepare_data("20260513", skip_prices=True)
    assert summary["price_update_status"] == "skipped"
    assert summary["indicators_update_status"] == "success"
    assert calls == ["indicators"]


def test_skip_indicators_skips_indicator_update(monkeypatch):
    calls: list[object] = []

    monkeypatch.setattr(paper_prepare_data, "market_db_path", lambda: "outputs/market_data.db")
    monkeypatch.setattr(paper_prepare_data.data_collector, "get_sp500_tickers", lambda: ["AAPL"])
    monkeypatch.setattr(paper_prepare_data.data_collector, "get_nasdaq100_tickers", lambda: ["MSFT"])
    monkeypatch.setattr(paper_prepare_data.data_collector, "update_market_indices", lambda: calls.append("market_index"))
    monkeypatch.setattr(
        paper_prepare_data.data_collector,
        "update_tickers_info",
        lambda tickers: calls.append(("tickers", tickers)),
    )
    monkeypatch.setattr(
        paper_prepare_data.data_collector,
        "update_stock_data",
        lambda tickers: calls.append(("prices", tickers)),
    )
    monkeypatch.setattr(
        paper_prepare_data.data_processor,
        "update_technical_indicators",
        lambda: calls.append("indicators"),
    )

    summary = paper_prepare_data.run_paper_prepare_data("20260513", skip_indicators=True)
    assert summary["price_update_status"] == "success"
    assert summary["indicators_update_status"] == "skipped"
    assert "indicators" not in calls


def test_universe_disabled_skips_universe(monkeypatch):
    calls: list[object] = []

    monkeypatch.setattr(paper_prepare_data, "market_db_path", lambda: "outputs/market_data.db")
    monkeypatch.setattr(paper_prepare_data.data_collector, "get_sp500_tickers", lambda: ["AAPL"])
    monkeypatch.setattr(paper_prepare_data.data_collector, "get_nasdaq100_tickers", lambda: ["MSFT"])
    monkeypatch.setattr(paper_prepare_data.data_collector, "update_market_indices", lambda: None)
    monkeypatch.setattr(paper_prepare_data.data_collector, "update_tickers_info", lambda tickers: None)
    monkeypatch.setattr(paper_prepare_data.data_collector, "update_stock_data", lambda tickers: None)
    monkeypatch.setattr(paper_prepare_data.data_processor, "update_technical_indicators", lambda: None)
    monkeypatch.setattr(
        paper_prepare_data,
        "refresh_universe_snapshot_for_date",
        lambda date_str: calls.append(date_str),
    )

    summary = paper_prepare_data.run_paper_prepare_data("20260513", include_universe=False)
    assert summary["universe_update_status"] == "skipped"
    assert calls == []


def test_universe_enabled_calls_universe_update(monkeypatch):
    monkeypatch.setattr(paper_prepare_data, "market_db_path", lambda: "outputs/market_data.db")
    monkeypatch.setattr(paper_prepare_data.data_collector, "get_sp500_tickers", lambda: ["AAPL"])
    monkeypatch.setattr(paper_prepare_data.data_collector, "get_nasdaq100_tickers", lambda: ["MSFT"])
    monkeypatch.setattr(paper_prepare_data.data_collector, "update_market_indices", lambda: None)
    monkeypatch.setattr(paper_prepare_data.data_collector, "update_tickers_info", lambda tickers: None)
    monkeypatch.setattr(paper_prepare_data.data_collector, "update_stock_data", lambda tickers: None)
    monkeypatch.setattr(paper_prepare_data.data_processor, "update_technical_indicators", lambda: None)
    monkeypatch.setattr(
        paper_prepare_data,
        "refresh_universe_snapshot_for_date",
        lambda date_str: Path(f"outputs/universe/universe_snapshot_{date_str.replace('-', '')}.json"),
    )

    summary = paper_prepare_data.run_paper_prepare_data("20260513", include_universe=True)
    assert summary["universe_update_status"] == "success"
    assert summary["universe_snapshot_path"].endswith("outputs\\universe\\universe_snapshot_20260513.json") or summary["universe_snapshot_path"].endswith("outputs/universe/universe_snapshot_20260513.json")


def test_refresh_universe_snapshot_uses_existing_helpers(monkeypatch):
    monkeypatch.setattr(paper_prepare_data.data_manager, "get_ticker_list", lambda: ["AAPL", "MSFT"])
    monkeypatch.setattr(paper_prepare_data, "fetch_live_basket_symbols", lambda: {"AAPL", "NVDA"})
    monkeypatch.setattr(
        paper_prepare_data,
        "compare_universe",
        lambda live, local: {"added": {"NVDA"}, "removed": {"MSFT"}, "kept": {"AAPL"}},
    )
    captured: dict[str, object] = {}

    def fake_save(snapshot_data: dict[str, object], date_str: str) -> Path:
        captured["snapshot_data"] = snapshot_data
        captured["date_str"] = date_str
        return Path("outputs/universe/universe_snapshot_20260513.json")

    monkeypatch.setattr(paper_prepare_data, "save_universe_snapshot", fake_save)
    path = paper_prepare_data.refresh_universe_snapshot_for_date("2026-05-13")
    assert path == Path("outputs/universe/universe_snapshot_20260513.json")
    assert captured["date_str"] == "2026-05-13"
    assert captured["snapshot_data"]["added"] == ["NVDA"]


def test_prepare_data_does_not_call_run_screener():
    helper_text = Path("core/paper_prepare_data.py").read_text(encoding="utf-8")
    assert "run_screener" not in helper_text


def test_prepare_data_does_not_call_setup_db():
    helper_text = Path("core/paper_prepare_data.py").read_text(encoding="utf-8")
    assert "setup_db" not in helper_text


def test_historical_official_prepare_uses_snapshot_symbols_without_live_membership(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    snapshot_path = tmp_path / "universe_snapshot_20260612.json"
    payload = _official_universe_payload()
    snapshot_path.write_text(json.dumps(payload), encoding="utf-8")
    captured: dict[str, list[str]] = {}
    monkeypatch.setattr(
        paper_prepare_data,
        "load_universe_snapshot_as_of_quarter",
        lambda date_str: {"snapshot": {}, "metadata": {"snapshot_path": str(snapshot_path)}},
    )
    monkeypatch.setattr(
        paper_prepare_data,
        "collect_daily_tickers",
        lambda: pytest.fail("official preparation must not collect live membership"),
    )
    monkeypatch.setattr(
        paper_prepare_data,
        "fetch_live_basket_symbols",
        lambda: pytest.fail("historical preparation must not fetch live membership"),
    )
    monkeypatch.setattr(paper_prepare_data, "market_db_path", lambda: "outputs/market_data.db")
    monkeypatch.setattr(paper_prepare_data.data_collector, "update_market_indices", lambda: None)
    monkeypatch.setattr(
        paper_prepare_data.data_collector,
        "update_tickers_info",
        lambda tickers: captured.setdefault("metadata", tickers),
    )
    monkeypatch.setattr(
        paper_prepare_data.data_collector,
        "update_stock_data",
        lambda tickers: captured.setdefault("prices", tickers),
    )

    summary = paper_prepare_data.run_paper_prepare_data(
        DATA_DATE,
        include_universe=True,
        trade_date=TRADE_DATE,
        account_id="paper_test",
        observed_at=AFTER_TRADE,
        skip_indicators=True,
    )

    assert summary["ticker_count"] == 2
    assert captured == {"metadata": ["AAPL", "MSFT"], "prices": ["AAPL", "MSFT"]}
    screener_symbols, _ = resolve_official_universe_membership(
        payload,
        {"snapshot_path": str(snapshot_path)},
        StageAAsOfContext.build(
            account_id="paper_test",
            data_date=DATA_DATE,
            trade_date=TRADE_DATE,
            observed_at=AFTER_TRADE,
        ),
    )
    assert captured["prices"] == screener_symbols


def test_current_day_official_prepare_captures_once_and_reuses_snapshot_symbols(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    snapshot_path = tmp_path / "universe_snapshot_20260612.json"
    live_calls = 0
    captured: dict[str, list[str]] = {}
    monkeypatch.setattr(
        paper_prepare_data,
        "load_universe_snapshot_as_of_quarter",
        lambda date_str: {"snapshot": {}, "metadata": {}},
    )
    monkeypatch.setattr(paper_prepare_data.data_manager, "get_ticker_list", lambda: ["AAPL"])

    def _fetch_live() -> set[str]:
        nonlocal live_calls
        live_calls += 1
        return {"MSFT", "AAPL"}

    def _save(payload: dict, date_str: str) -> Path:
        snapshot_path.write_text(json.dumps(payload), encoding="utf-8")
        return snapshot_path

    monkeypatch.setattr(paper_prepare_data, "fetch_live_basket_symbols", _fetch_live)
    monkeypatch.setattr(paper_prepare_data, "save_universe_snapshot", _save)
    monkeypatch.setattr(
        paper_prepare_data,
        "collect_daily_tickers",
        lambda: pytest.fail("official preparation must reuse captured snapshot"),
    )
    monkeypatch.setattr(paper_prepare_data, "market_db_path", lambda: "outputs/market_data.db")
    monkeypatch.setattr(paper_prepare_data.data_collector, "update_market_indices", lambda: None)
    monkeypatch.setattr(
        paper_prepare_data.data_collector,
        "update_tickers_info",
        lambda tickers: captured.setdefault("metadata", tickers),
    )
    monkeypatch.setattr(
        paper_prepare_data.data_collector,
        "update_stock_data",
        lambda tickers: captured.setdefault("prices", tickers),
    )

    paper_prepare_data.run_paper_prepare_data(
        DATA_DATE,
        include_universe=True,
        trade_date=TRADE_DATE,
        account_id="paper_test",
        observed_at=BEFORE_TRADE,
        skip_indicators=True,
    )

    assert live_calls == 1
    assert captured == {"metadata": ["AAPL", "MSFT"], "prices": ["AAPL", "MSFT"]}


def test_historical_official_missing_snapshot_blocks_before_data_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        paper_prepare_data,
        "load_universe_snapshot_as_of_quarter",
        lambda date_str: {"snapshot": {}, "metadata": {}},
    )
    monkeypatch.setattr(
        paper_prepare_data,
        "collect_daily_tickers",
        lambda: pytest.fail("blocked official preparation must not collect live membership"),
    )
    monkeypatch.setattr(
        paper_prepare_data,
        "fetch_live_basket_symbols",
        lambda: pytest.fail("blocked historical preparation must not fetch live membership"),
    )
    monkeypatch.setattr(
        paper_prepare_data.data_collector,
        "update_market_indices",
        lambda: pytest.fail("blocked preparation must not refresh prices"),
    )

    with pytest.raises(StageAAsOfContractError) as exc_info:
        paper_prepare_data.run_paper_prepare_data(
            DATA_DATE,
            include_universe=True,
            trade_date=TRADE_DATE,
            account_id="paper_test",
            observed_at=AFTER_TRADE,
        )

    assert exc_info.value.reason == "historical_universe_snapshot_missing"

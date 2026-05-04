from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable
from urllib.request import Request, urlopen

import pandas as pd

from core.paths import OUTPUTS


SP500_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
NASDAQ100_WIKI_URL = "https://en.wikipedia.org/wiki/Nasdaq-100"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def _normalize_symbol(symbol: object) -> str:
    """Normalize ticker strings to local DB style."""
    text = str(symbol).strip().upper()
    return text.replace(".", "-")


def _extract_symbols_from_tables(tables: list[pd.DataFrame], candidates: Iterable[str]) -> set[str]:
    for table in tables:
        for column in candidates:
            if column in table.columns:
                series = table[column].dropna()
                return {_normalize_symbol(value) for value in series if str(value).strip()}
    raise ValueError(f"Unable to find ticker column in candidate columns: {list(candidates)}")


def _read_html_tables(url: str) -> list[pd.DataFrame]:
    request = Request(url, headers=DEFAULT_HEADERS)
    with urlopen(request) as response:
        html = response.read()
    return pd.read_html(html)


def fetch_live_basket_symbols() -> set[str]:
    """
    Fetch the latest S&P 500 and NASDAQ 100 constituents from Wikipedia and
    return a merged unique symbol set.
    """
    sp500_tables = _read_html_tables(SP500_WIKI_URL)
    nasdaq100_tables = _read_html_tables(NASDAQ100_WIKI_URL)

    sp500_symbols = _extract_symbols_from_tables(sp500_tables, ["Symbol", "Ticker"])
    nasdaq100_symbols = _extract_symbols_from_tables(nasdaq100_tables, ["Ticker", "Symbol"])
    return sp500_symbols | nasdaq100_symbols


def compare_universe(live_symbols: Iterable[str], local_symbols: Iterable[str]) -> dict[str, set[str]]:
    """Compare live index symbols against local DB tickers."""
    live_set = {_normalize_symbol(symbol) for symbol in live_symbols if str(symbol).strip()}
    local_set = {_normalize_symbol(symbol) for symbol in local_symbols if str(symbol).strip()}
    return {
        "added": live_set - local_set,
        "removed": local_set - live_set,
        "kept": live_set & local_set,
    }


def save_universe_snapshot(snapshot_data: dict[str, object], date_str: str) -> Path:
    """Persist a universe dry-run snapshot under outputs/universe/ as JSON."""
    clean_date = date_str.replace("-", "")
    target_dir = OUTPUTS / "universe"
    target_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = target_dir / f"universe_snapshot_{clean_date}.json"

    with snapshot_path.open("w", encoding="utf-8") as handle:
        json.dump(snapshot_data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    return snapshot_path


def load_latest_universe_snapshot() -> dict[str, object]:
    """Load the newest universe snapshot JSON from outputs/universe/."""
    target_dir = OUTPUTS / "universe"
    if not target_dir.exists():
        return {}

    snapshots = sorted(target_dir.glob("universe_snapshot_*.json"))
    if not snapshots:
        return {}

    latest_path = snapshots[-1]
    try:
        return json.loads(latest_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

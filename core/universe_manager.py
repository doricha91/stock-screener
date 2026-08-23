from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable
from urllib.request import Request, urlopen

import pandas as pd

from core.paths import OUTPUTS


SP500_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
NASDAQ100_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_NASDAQ-100_companies"
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


def _normalize_snapshot_date(date_str: str) -> str:
    clean_date = str(date_str).replace("-", "").strip()
    if len(clean_date) != 8 or not clean_date.isdigit():
        raise ValueError(f"Invalid snapshot date: {date_str}")
    return pd.to_datetime(clean_date, format="%Y%m%d").strftime("%Y-%m-%d")


def _snapshot_quarter(date_value: pd.Timestamp) -> str:
    quarter = ((date_value.month - 1) // 3) + 1
    return f"{date_value.year}Q{quarter}"


def _parse_snapshot_date_from_path(path: Path) -> pd.Timestamp | None:
    stem = path.stem
    prefix = "universe_snapshot_"
    if not stem.startswith(prefix):
        return None
    raw = stem[len(prefix):]
    if len(raw) != 8 or not raw.isdigit():
        return None
    return pd.to_datetime(raw, format="%Y%m%d")


def load_universe_snapshot_as_of_quarter(
    plan_date: str,
    snapshots_dir: Path | None = None,
) -> dict[str, object]:
    normalized_plan_date = _normalize_snapshot_date(plan_date)
    plan_ts = pd.Timestamp(normalized_plan_date)
    target_dir = Path(snapshots_dir) if snapshots_dir is not None else (OUTPUTS / "universe")

    metadata = {
        "policy": "quarterly_as_of",
        "snapshot_path": None,
        "snapshot_date": None,
        "snapshot_quarter": None,
        "fallback_used": False,
        "warning": None,
    }
    if not target_dir.exists():
        metadata["fallback_used"] = True
        metadata["warning"] = "Universe snapshot directory does not exist."
        return {"snapshot": {}, "metadata": metadata}

    snapshot_paths = sorted(target_dir.glob("universe_snapshot_*.json"))
    eligible: list[tuple[pd.Timestamp, Path]] = []
    for path in snapshot_paths:
        snapshot_ts = _parse_snapshot_date_from_path(path)
        if snapshot_ts is None or snapshot_ts > plan_ts:
            continue
        eligible.append((snapshot_ts, path))

    if not eligible:
        metadata["fallback_used"] = True
        metadata["warning"] = "No universe snapshot exists on or before plan_date."
        return {"snapshot": {}, "metadata": metadata}

    plan_quarter = _snapshot_quarter(plan_ts)
    same_quarter = [(ts, path) for ts, path in eligible if _snapshot_quarter(ts) == plan_quarter]
    if same_quarter:
        chosen_ts, chosen_path = same_quarter[-1]
    else:
        chosen_ts, chosen_path = eligible[-1]
        metadata["fallback_used"] = True
        metadata["warning"] = (
            f"No universe snapshot found in {plan_quarter} on or before {normalized_plan_date}; "
            f"using latest prior snapshot from {_snapshot_quarter(chosen_ts)}."
        )

    try:
        payload = json.loads(chosen_path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
        metadata["fallback_used"] = True
        metadata["warning"] = f"Failed to read universe snapshot: {chosen_path}"

    metadata.update(
        {
            "snapshot_path": str(chosen_path),
            "snapshot_date": chosen_ts.strftime("%Y-%m-%d"),
            "snapshot_quarter": _snapshot_quarter(chosen_ts),
            "effective_as_of": payload.get("effective_as_of"),
            "observed_at": payload.get("observed_at"),
            "source": payload.get("source"),
            "source_revision": payload.get("source_revision"),
            "artifact_hash": payload.get("artifact_hash"),
            "capture_mode": payload.get("capture_mode"),
        }
    )
    return {"snapshot": payload, "metadata": metadata}

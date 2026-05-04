from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from screener import data_manager
from core.universe_manager import compare_universe, fetch_live_basket_symbols, save_universe_snapshot


def _format_sample(symbols: set[str], limit: int = 15) -> str:
    if not symbols:
        return "-"
    ordered = sorted(symbols)
    sample = ordered[:limit]
    suffix = "" if len(ordered) <= limit else f" ... (+{len(ordered) - limit} more)"
    return ", ".join(sample) + suffix


def main() -> int:
    print("=" * 60)
    print("UNIVERSE REFRESH DRY-RUN")
    print("=" * 60)

    as_of = datetime.now().strftime("%Y-%m-%d")
    local_symbols = set(data_manager.get_ticker_list())
    print(f"Local DB tickers: {len(local_symbols)}")

    try:
        live_symbols = fetch_live_basket_symbols()
    except Exception as exc:
        print(f"[ERROR] Failed to fetch live basket symbols: {exc}")
        return 1

    delta = compare_universe(live_symbols, local_symbols)
    snapshot_data = {
        "as_of": as_of,
        "active_symbols": sorted(live_symbols),
        "added": sorted(delta["added"]),
        "removed": sorted(delta["removed"]),
        "kept": sorted(delta["kept"]),
    }
    snapshot_path = save_universe_snapshot(snapshot_data, as_of)

    print(f"Live target tickers: {len(live_symbols)}")
    print(f"Added candidates   : {len(delta['added'])}")
    print(f"Removed candidates : {len(delta['removed'])}")
    print(f"Kept tickers       : {len(delta['kept'])}")
    print()
    print("[Sample Added]")
    print(_format_sample(delta["added"]))
    print()
    print("[Sample Removed]")
    print(_format_sample(delta["removed"]))
    print()
    print("[Sample Kept]")
    print(_format_sample(delta["kept"]))
    print()
    print(f"Snapshot saved     : {snapshot_path}")
    print("Dry-run only: no database writes were performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

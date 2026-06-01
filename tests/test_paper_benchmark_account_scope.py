from __future__ import annotations

import sqlite3
from pathlib import Path

from core.paper_account_paths import build_paper_account_paths
from core.paper_benchmark_comparison import generate_paper_benchmark_comparison


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_market_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE market_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                date TEXT,
                close REAL,
                adj_close REAL,
                moving_avg_200 REAL
            )
            """
        )
        cur.executemany(
            "INSERT INTO market_index(symbol, date, close, adj_close, moving_avg_200) VALUES (?, ?, ?, ?, ?)",
            [
                ("SPY", "2026-05-09", 100.0, 101.0, None),
                ("SPY", "2026-05-20", 110.0, 111.0, None),
                ("QQQ", "2026-05-09", 200.0, None, None),
                ("QQQ", "2026-05-20", 220.0, None, None),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def test_benchmark_accepts_account_paths_and_writes_under_account_root(tmp_path, monkeypatch):
    accounts_root = tmp_path / "paper_accounts"
    monkeypatch.setattr("core.paper_account_paths.PAPER_ACCOUNTS_ROOT", accounts_root)
    root = accounts_root / "paper_growth"
    _write(
        root / "paper_account_snapshot.csv",
        "snapshot_date,initial_cash,total_equity_market_value,total_equity_cost_basis,market_valuation_status,valuation_price_date\n"
        "2026-05-09,100000,100000,100000,success,2026-05-09\n"
        "2026-05-20,100000,102000,102000,success,2026-05-20\n",
    )
    db_path = tmp_path / "market_data.db"
    _seed_market_db(db_path)

    account_paths = build_paper_account_paths("paper_growth", create=False)
    result = generate_paper_benchmark_comparison(account_paths=account_paths, market_db=db_path)
    assert result["markdown_path"].parent == root / "reports"
    assert result["summary"]["account_id"] == "paper_growth"
    assert result["summary"]["account_root"] == str(root)

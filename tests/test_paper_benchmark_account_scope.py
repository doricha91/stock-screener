from __future__ import annotations

import csv
import io
import sqlite3
from pathlib import Path

import pytest

from core.paper_account_paths import build_paper_account_paths
from core.paper_account_snapshot import PAPER_ACCOUNT_SNAPSHOT_COLUMNS
from core.paper_benchmark_comparison import generate_paper_benchmark_comparison
from core.paper_snapshot_identity import PaperSnapshotIdentityError


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_account_snapshot(path: Path, text: str) -> None:
    reader = csv.DictReader(io.StringIO(text))
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=PAPER_ACCOUNT_SNAPSHOT_COLUMNS)
    writer.writeheader()
    for source_row in reader:
        writer.writerow(
            {
                column: source_row.get(column, "")
                for column in PAPER_ACCOUNT_SNAPSHOT_COLUMNS
            }
        )
    _write(path, output.getvalue())


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
    _write_account_snapshot(
        root / "paper_account_snapshot.csv",
        "account_id,snapshot_date,initial_cash,total_equity_market_value,total_equity_cost_basis,market_valuation_status,valuation_price_date\n"
        "paper_growth,2026-05-09,100000,100000,100000,success,2026-05-09\n"
        "paper_growth,2026-05-20,100000,102000,102000,success,2026-05-20\n",
    )
    db_path = tmp_path / "market_data.db"
    _seed_market_db(db_path)

    account_paths = build_paper_account_paths("paper_growth", create=False)
    result = generate_paper_benchmark_comparison(account_paths=account_paths, market_db=db_path)
    assert result["markdown_path"].parent == root / "reports"
    assert result["summary"]["account_id"] == "paper_growth"
    assert result["summary"]["account_root"] == str(root)


@pytest.mark.parametrize(
    "account_values,reason",
    [
        (["paper_other", "paper_other"], "account_id_mismatch"),
        (["paper_growth", "paper_other"], "mixed_account_ids"),
        (["", "paper_growth"], "blank_account_id"),
    ],
)
def test_benchmark_fails_closed_on_invalid_snapshot_identity(
    tmp_path,
    monkeypatch,
    account_values,
    reason,
):
    accounts_root = tmp_path / "paper_accounts"
    monkeypatch.setattr("core.paper_account_paths.PAPER_ACCOUNTS_ROOT", accounts_root)
    root = accounts_root / "paper_growth"
    _write_account_snapshot(
        root / "paper_account_snapshot.csv",
        "account_id,snapshot_date,initial_cash,total_equity_market_value\n"
        f"{account_values[0]},2026-05-09,100000,100000\n"
        f"{account_values[1]},2026-05-20,100000,102000\n",
    )

    with pytest.raises(PaperSnapshotIdentityError, match=reason):
        generate_paper_benchmark_comparison(
            account_paths=build_paper_account_paths("paper_growth", create=False),
            market_db=tmp_path / "missing.db",
        )

    assert not (root / "reports" / "paper_benchmark_comparison.json").exists()

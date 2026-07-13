from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from core.daily_plan_generator import (
    WARNING_HIGHEST_PRICE_INCONSISTENT,
    check_trailing_stop_manual,
    diagnose_highest_price_state,
)
from core.paper_state_provider import load_official_paper_state_for_daily_plan
from core.paper_account_paths import build_paper_account_paths
from scripts.run_paper_eod_update import build_paper_account_preview_from_log


def write_log(path: Path) -> None:
    rows = [
        {
            "trade_id": "entry",
            "date": "2026-07-01",
            "symbol": "TEST",
            "side": "BUY",
            "shares": 10,
            "price": 100.0,
            "gross_amount": 1000.0,
        },
        {
            "trade_id": "future_add",
            "date": "2026-07-06",
            "symbol": "TEST",
            "side": "BUY",
            "shares": 5,
            "price": 200.0,
            "gross_amount": 1000.0,
        },
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)


def write_market_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "CREATE TABLE daily_price "
            "(symbol TEXT, date TEXT, high REAL, close REAL)"
        )
        conn.executemany(
            "INSERT INTO daily_price VALUES (?, ?, ?, ?)",
            [
                ("TEST", "2026-07-01", 110.0, 105.0),
                ("TEST", "2026-07-02", 120.0, 115.0),
                ("TEST", "2026-07-06", 250.0, 240.0),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def test_provider_uses_data_date_cutoff_and_decision_highest(tmp_path: Path) -> None:
    log_path = tmp_path / "execution.csv"
    db_path = tmp_path / "market.db"
    write_log(log_path)
    write_market_db(db_path)

    state = load_official_paper_state_for_daily_plan(
        "2026-07-02",
        log_path=log_path,
        db_path=db_path,
    )

    assert state.shares == {"TEST": 10}
    assert state.avg_price == {"TEST": 100.0}
    assert state.highest_prices == {"TEST": 100.0}
    assert state.highest_price_meta["TEST"]["updated_highest"] == 120.0
    assert state.highest_price_meta["TEST"]["observed_through"] == "2026-07-02"


def test_daily_plan_uses_decision_highest_without_expected_inconsistency_warning(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "execution.csv"
    db_path = tmp_path / "market.db"
    write_log(log_path)
    write_market_db(db_path)
    state = load_official_paper_state_for_daily_plan(
        "2026-07-02",
        log_path=log_path,
        db_path=db_path,
    )

    highest, source, warnings, _ = diagnose_highest_price_state(
        "TEST",
        "2026-07-02",
        state,
        close=90.0,
        high=120.0,
    )

    assert highest == 100.0
    assert source == "decision_highest"
    assert WARNING_HIGHEST_PRICE_INCONSISTENT not in {
        warning["reason"] for warning in warnings
    }
    triggered, stop = check_trailing_stop_manual("TEST", 90.0, highest, 10.0, 2.5)
    assert stop == 75.0
    assert triggered is False


def test_eod_preview_uses_updated_highest_without_future_trade_or_price(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "execution.csv"
    db_path = tmp_path / "market.db"
    write_log(log_path)
    write_market_db(db_path)

    state = build_paper_account_preview_from_log(
        log_path,
        account_paths=build_paper_account_paths(
            "paper_test_fixture",
            account_root=tmp_path,
            create=False,
        ),
        as_of_date="2026-07-02",
        db_path=db_path,
    )

    assert state.positions["TEST"].shares == 10
    assert state.positions["TEST"].avg_price == 100.0
    assert state.positions["TEST"].highest_price == 120.0
    assert state.highest_price_meta["TEST"] == {
        "updated_at": "2026-07-02",
        "position_open_date": "2026-07-01",
        "observed_through": "2026-07-02",
        "max_high_date": "2026-07-02",
        "decision_highest": 100.0,
        "updated_highest": 120.0,
        "current_high": 120.0,
        "source": "market_data",
        "basis": "position_lifecycle_max_daily_high",
    }


def test_real_incident_pattern_rolls_highs_forward_without_accounting_changes(
    tmp_path: Path,
) -> None:
    symbols = {
        "AMCR": ("2026-06-15", 40.60),
        "AON": ("2026-07-02", 343.56),
        "GPN": ("2026-07-02", 75.05),
        "KHC": ("2026-07-02", 25.01),
        "TEST": ("2026-07-01", 100.00),
    }
    log_path = tmp_path / "incident.csv"
    rows = [
        {
            "trade_id": f"buy_{symbol}",
            "date": open_date,
            "symbol": symbol,
            "side": "BUY",
            "shares": 1,
            "price": price,
            "gross_amount": price,
        }
        for symbol, (open_date, price) in symbols.items()
    ]
    with log_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)

    db_path = tmp_path / "incident.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE daily_price (symbol TEXT, date TEXT, high REAL, close REAL)")
        conn.executemany(
            "INSERT INTO daily_price VALUES (?, ?, ?, ?)",
            [
                ("AMCR", "2026-07-01", 44.29, 43.64),
                ("AMCR", "2026-07-02", 45.03, 45.00),
                ("AMCR", "2026-07-06", 44.92, 44.62),
                ("AON", "2026-07-02", 357.54, 357.46),
                ("AON", "2026-07-03", 360.00, 358.00),
                ("AON", "2026-07-06", 359.00, 356.91),
                ("GPN", "2026-07-02", 78.71, 78.63),
                ("GPN", "2026-07-03", 80.00, 79.00),
                ("GPN", "2026-07-06", 79.00, 77.41),
                ("KHC", "2026-07-02", 25.51, 25.37),
                ("KHC", "2026-07-03", 26.00, 25.80),
                ("KHC", "2026-07-06", 25.90, 24.82),
                ("TEST", "2026-07-02", 130.00, 125.00),
                ("TEST", "2026-07-03", 115.00, 110.00),
                ("TEST", "2026-07-06", 112.00, 108.00),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    july2 = load_official_paper_state_for_daily_plan(
        "2026-07-02",
        log_path=log_path,
        db_path=db_path,
    )
    assert july2.highest_prices == {
        "AMCR": 44.29,
        "AON": 343.56,
        "GPN": 75.05,
        "KHC": 25.01,
        "TEST": 100.0,
    }
    assert july2.highest_price_meta["AMCR"]["updated_highest"] == 45.03
    assert july2.highest_price_meta["AON"]["updated_highest"] == 343.56

    july6 = load_official_paper_state_for_daily_plan(
        "2026-07-06",
        log_path=log_path,
        db_path=db_path,
    )
    assert july6.highest_prices == {
        "AMCR": 45.03,
        "AON": 360.0,
        "GPN": 80.0,
        "KHC": 26.0,
        "TEST": 130.0,
    }
    for symbol, high in {
        "AMCR": 44.92,
        "AON": 359.0,
        "GPN": 79.0,
        "KHC": 25.9,
        "TEST": 112.0,
    }.items():
        _, _, warnings, _ = diagnose_highest_price_state(
            symbol,
            "2026-07-06",
            july6,
            close=high - 0.1,
            high=high,
        )
        assert WARNING_HIGHEST_PRICE_INCONSISTENT not in {
            warning["reason"] for warning in warnings
        }

    expected_cash = 100000.0 - sum(price for _, price in symbols.values())
    assert july2.absolute_cash == expected_cash
    assert july6.absolute_cash == expected_cash
    assert july2.shares == july6.shares == {symbol: 1 for symbol in sorted(symbols)}
    assert july2.avg_price == july6.avg_price == {
        symbol: price for symbol, (_, price) in symbols.items()
    }

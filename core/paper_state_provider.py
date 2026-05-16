from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from core.paper_account_state import build_paper_state_from_trades
from core.paper_current_state_serializer import paper_account_state_to_current_state_dict
from core.paper_safety import assert_paper_path
from core.paths import PAPER_TEST_DIR, paper_execution_log_path
from core.target_portfolio_state import CurrentPortfolioState


def normalize_paper_trade_date(date_str: str) -> str:
    clean_date = str(date_str).replace("-", "").strip()
    if len(clean_date) != 8 or not clean_date.isdigit():
        raise ValueError(f"Invalid date format: {date_str}")
    return datetime.strptime(clean_date, "%Y%m%d").strftime("%Y-%m-%d")


def filter_trade_rows_before_plan_date(trade_rows: list[dict], plan_date: str) -> list[dict]:
    normalized_plan_date = normalize_paper_trade_date(plan_date)
    filtered_rows: list[dict] = []
    for row in trade_rows:
        trade_date = normalize_paper_trade_date(row.get("date", ""))
        if trade_date < normalized_plan_date:
            filtered_rows.append(row)
    return filtered_rows


def load_paper_execution_rows_for_state(log_path: Path | None = None) -> list[dict]:
    if log_path is None:
        target_log_path = paper_execution_log_path()
        assert_paper_path(target_log_path, PAPER_TEST_DIR)
    else:
        target_log_path = log_path

    if not target_log_path.exists():
        return []

    with target_log_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_official_paper_state_for_daily_plan(
    date_str: str,
    log_path: Path | None = None,
) -> CurrentPortfolioState:
    normalized_plan_date = normalize_paper_trade_date(date_str)
    trade_rows = load_paper_execution_rows_for_state(log_path=log_path)
    filtered_trade_rows = filter_trade_rows_before_plan_date(trade_rows, normalized_plan_date)
    paper_state = build_paper_state_from_trades(
        filtered_trade_rows,
        initial_cash=100000.0,
        currency="USD",
    )
    serialized = paper_account_state_to_current_state_dict(paper_state, normalized_plan_date)
    return CurrentPortfolioState(
        current_symbols=serialized["current_symbols"],
        current_cash_ratio=serialized["current_cash_ratio"],
        current_hedge_ratio=serialized["current_hedge_ratio"],
        absolute_cash=serialized["absolute_cash"],
        shares=serialized["shares"],
        avg_price=serialized["avg_price"],
        highest_prices=serialized["highest_prices"],
        highest_price_meta=serialized.get("highest_price_meta", {}),
        hedge_symbols=serialized.get("hedge_symbols", []),
    )

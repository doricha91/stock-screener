from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from core.paper_account_state import build_paper_state_from_trades
from core.paper_account_paths import PaperAccountPaths, resolve_paper_read_account_paths
from core.paper_current_state_serializer import paper_account_state_to_current_state_dict
from core.paper_high_watermark import (
    calculate_paper_high_watermarks,
    filter_execution_rows_on_or_before,
)
from core.paths import market_db_path
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


def load_paper_execution_rows_for_state(
    log_path: Path | None = None,
    *,
    account_paths: PaperAccountPaths | None = None,
) -> list[dict]:
    context = account_paths or resolve_paper_read_account_paths()
    target_log_path = Path(log_path) if log_path is not None else context.execution_log_path
    try:
        target_log_path.resolve(strict=False).relative_to(context.root.resolve(strict=False))
    except ValueError as exc:
        raise ValueError(
            "Paper execution log path is outside the resolved account root: "
            f"account_id={context.account_id} path={target_log_path} root={context.root}"
        ) from exc

    if not target_log_path.exists():
        return []

    with target_log_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_official_paper_state_for_daily_plan(
    date_str: str,
    log_path: Path | None = None,
    initial_cash: float = 100000.0,
    currency: str = "USD",
    db_path: Path | None = None,
    account_paths: PaperAccountPaths | None = None,
) -> CurrentPortfolioState:
    normalized_plan_date = normalize_paper_trade_date(date_str)
    trade_rows = load_paper_execution_rows_for_state(
        log_path=log_path,
        account_paths=account_paths,
    )
    filtered_trade_rows = filter_execution_rows_on_or_before(trade_rows, normalized_plan_date)
    paper_state = build_paper_state_from_trades(
        filtered_trade_rows,
        initial_cash=initial_cash,
        currency=currency,
    )
    high_watermarks = calculate_paper_high_watermarks(
        paper_state,
        filtered_trade_rows,
        normalized_plan_date,
        db_path or Path(market_db_path()),
    )
    paper_state = high_watermarks.decision_state
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

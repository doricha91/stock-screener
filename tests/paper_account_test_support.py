from __future__ import annotations

import csv
import json
from pathlib import Path

from core.paper_account_bootstrap import (
    BOOTSTRAP_CURRENT_STATE_SCHEMA_VERSION,
    BOOTSTRAP_SOURCE,
    initialize_paper_account,
)
from core.paper_account_paths import PaperAccountPaths, build_paper_account_paths
from core.paper_account_snapshot import PAPER_ACCOUNT_SNAPSHOT_COLUMNS
from core.paper_account_state import create_initial_paper_state
from core.paper_current_state_serializer import paper_account_state_to_current_state_dict
from core.paper_execution_log import PAPER_EXECUTION_LOG_COLUMNS
from core.paper_position_snapshot import PAPER_POSITION_SNAPSHOT_COLUMNS


def create_initialized_account_paths(
    root: Path,
    *,
    account_id: str = "paper_test_account",
    date_str: str = "2026-05-01",
    initial_cash: float = 100000.0,
    currency: str = "USD",
) -> PaperAccountPaths:
    if account_id != "paper_default":
        initialize_paper_account(
            account_id=account_id,
            initial_cash=initial_cash,
            currency=currency,
            date_str=date_str,
            confirm_create=True,
            account_root=root,
        )
        return build_paper_account_paths(account_id, account_root=root, create=False)

    return ensure_initialized_account_paths(
        root,
        account_id=account_id,
        date_str=date_str,
        initial_cash=initial_cash,
        currency=currency,
    )


def ensure_initialized_account_paths(
    root: Path,
    *,
    account_id: str,
    date_str: str = "2026-05-01",
    initial_cash: float = 100000.0,
    currency: str = "USD",
) -> PaperAccountPaths:
    """Fill only absent bootstrap artifacts, preserving a test's target artifact."""
    paths = build_paper_account_paths(account_id, account_root=root, create=False)
    root.mkdir(parents=True, exist_ok=True)
    for directory in (
        paths.reports_dir,
        paths.reviews_dir,
        root / "archive",
        paths.config_snapshots_dir,
        paths.replay_diff_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    account_row = {column: "" for column in PAPER_ACCOUNT_SNAPSHOT_COLUMNS}
    account_row.update(
        account_id=account_id,
        snapshot_date=date_str,
        currency=currency,
        initial_cash=f"{initial_cash:.2f}",
        cash=f"{initial_cash:.2f}",
        positions_cost_value="0.00",
        total_equity_cost_basis=f"{initial_cash:.2f}",
        cash_ratio_cost_basis="1.0000000",
        position_count="0",
        applied_trade_count="0",
        valuation_method="init",
        realized_pnl="0.00",
    )
    if not paths.account_snapshot_path.exists():
        _write_csv(paths.account_snapshot_path, PAPER_ACCOUNT_SNAPSHOT_COLUMNS, [account_row])
    if not paths.position_snapshot_path.exists():
        _write_csv(paths.position_snapshot_path, PAPER_POSITION_SNAPSHOT_COLUMNS, [])
    if not paths.execution_log_path.exists():
        _write_csv(paths.execution_log_path, PAPER_EXECUTION_LOG_COLUMNS, [])

    state = create_initial_paper_state(initial_cash=initial_cash, currency=currency)
    payload = paper_account_state_to_current_state_dict(state, date_str)
    payload.update(
        account_id=account_id,
        snapshot_date=date_str,
        source=BOOTSTRAP_SOURCE,
        schema_version=BOOTSTRAP_CURRENT_STATE_SCHEMA_VERSION,
    )
    if not any(paths.root.glob("paper_current_state_*.json")):
        paths.current_state_snapshot_path(date_str).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return paths


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

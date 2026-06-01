from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paper_account_guard import assert_non_default_writer_target, assert_path_under_account_root
from core.paper_account_paths import PAPER_ACCOUNTS_ROOT, PaperAccountPaths, build_paper_account_paths
from core.paper_account_profile import validate_account_id
from core.paper_account_snapshot import PAPER_ACCOUNT_SNAPSHOT_COLUMNS
from core.paper_account_state import create_initial_paper_state
from core.paper_current_state_serializer import paper_account_state_to_current_state_dict
from core.paper_execution_log import PAPER_EXECUTION_LOG_COLUMNS
from core.paper_position_snapshot import PAPER_POSITION_SNAPSHOT_COLUMNS


BOOTSTRAP_CURRENT_STATE_SCHEMA_VERSION = "paper_current_state.init.v1"
BOOTSTRAP_SOURCE = "init-account"


class PaperAccountBootstrapError(RuntimeError):
    pass


@dataclass(frozen=True)
class PaperAccountBootstrapPlan:
    account_id: str
    account_root: Path
    snapshot_date: str
    initial_cash: float
    currency: str
    dry_run: bool
    allow_existing: bool
    blocked_reason: str | None
    existing_root: bool
    existing_core_files: tuple[str, ...]
    would_create_dirs: tuple[str, ...]
    would_create_files: tuple[str, ...]

    def to_summary(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "account_root": str(self.account_root),
            "snapshot_date": self.snapshot_date,
            "initial_cash": self.initial_cash,
            "currency": self.currency,
            "dry_run": self.dry_run,
            "allow_existing": self.allow_existing,
            "blocked_reason": self.blocked_reason,
            "existing_root": self.existing_root,
            "existing_core_files": list(self.existing_core_files),
            "would_create_dirs": list(self.would_create_dirs),
            "would_create_files": list(self.would_create_files),
        }


def normalize_bootstrap_date(date_str: str) -> str:
    value = str(date_str or "").strip().replace("-", "")
    if len(value) != 8 or not value.isdigit():
        raise ValueError(f"Invalid bootstrap date format: {date_str}")
    return f"{value[:4]}-{value[4:6]}-{value[6:]}"


def validate_account_bootstrap_target(
    account_id: str,
    *,
    account_root: Path | None = None,
) -> PaperAccountPaths:
    resolved_account_id = validate_account_id(account_id)
    if resolved_account_id == "paper_default":
        raise PaperAccountBootstrapError("init-account does not allow account_id=paper_default.")

    account_paths = build_paper_account_paths(
        resolved_account_id,
        account_root=account_root,
        allow_legacy_default=False,
        create=False,
    )
    expected_root = (Path(account_root) if account_root is not None else PAPER_ACCOUNTS_ROOT / resolved_account_id).resolve()
    actual_root = account_paths.root.resolve()
    if actual_root != expected_root:
        raise PaperAccountBootstrapError(
            f"Account bootstrap target must resolve under outputs/paper_accounts/{resolved_account_id}: {actual_root}"
        )
    assert_path_under_account_root(account_paths.root, account_paths.root)
    for path in (
        account_paths.execution_log_path,
        account_paths.account_snapshot_path,
        account_paths.position_snapshot_path,
        account_paths.reports_dir,
        account_paths.reviews_dir,
        account_paths.config_snapshots_dir,
        account_paths.config_snapshot_archive_dir,
        account_paths.replay_diff_dir,
        account_paths.replay_diff_config_snapshot_archive_dir,
    ):
        assert_non_default_writer_target(
            path,
            account_id=account_paths.account_id,
            account_root=account_paths.root,
        )
    return account_paths


def build_account_bootstrap_plan(
    *,
    account_id: str,
    initial_cash: float,
    currency: str,
    date_str: str,
    dry_run: bool = True,
    allow_existing: bool = False,
    account_root: Path | None = None,
) -> PaperAccountBootstrapPlan:
    account_paths = validate_account_bootstrap_target(account_id, account_root=account_root)
    normalized_date = normalize_bootstrap_date(date_str)
    normalized_currency = str(currency or "").strip().upper()
    if not normalized_currency:
        raise PaperAccountBootstrapError("currency is required.")
    try:
        normalized_initial_cash = float(initial_cash)
    except Exception as exc:
        raise PaperAccountBootstrapError("initial_cash must be numeric.") from exc
    if normalized_initial_cash <= 0:
        raise PaperAccountBootstrapError("initial_cash must be > 0.")

    current_state_path = account_paths.current_state_snapshot_path(normalized_date)
    core_files = {
        "paper_account_snapshot.csv": account_paths.account_snapshot_path,
        "paper_position_snapshot.csv": account_paths.position_snapshot_path,
        "paper_execution_log.csv": account_paths.execution_log_path,
        current_state_path.name: current_state_path,
    }
    existing_core_files = tuple(name for name, path in core_files.items() if path.exists())
    existing_root = account_paths.root.exists()

    blocked_reason: str | None = None
    if existing_core_files and not allow_existing:
        blocked_reason = (
            "bootstrap target already contains initialized core files: "
            + ", ".join(existing_core_files)
        )
    elif existing_root and not existing_core_files and not allow_existing:
        blocked_reason = (
            "bootstrap target root already exists. Use a fresh account root or --allow-existing for read/validate only."
        )

    would_create_dirs = (
        str(account_paths.root),
        str(account_paths.reports_dir),
        str(account_paths.reviews_dir),
        str(account_paths.root / "archive"),
        str(account_paths.config_snapshots_dir),
        str(account_paths.replay_diff_dir),
    )
    would_create_files = (
        str(account_paths.account_snapshot_path),
        str(account_paths.position_snapshot_path),
        str(account_paths.execution_log_path),
        str(current_state_path),
    )
    return PaperAccountBootstrapPlan(
        account_id=account_paths.account_id,
        account_root=account_paths.root,
        snapshot_date=normalized_date,
        initial_cash=normalized_initial_cash,
        currency=normalized_currency,
        dry_run=bool(dry_run),
        allow_existing=bool(allow_existing),
        blocked_reason=blocked_reason,
        existing_root=existing_root,
        existing_core_files=existing_core_files,
        would_create_dirs=would_create_dirs,
        would_create_files=would_create_files,
    )


def initialize_paper_account(
    *,
    account_id: str,
    initial_cash: float,
    currency: str,
    date_str: str,
    confirm_create: bool = False,
    allow_existing: bool = False,
    account_root: Path | None = None,
) -> dict[str, Any]:
    plan = build_account_bootstrap_plan(
        account_id=account_id,
        initial_cash=initial_cash,
        currency=currency,
        date_str=date_str,
        dry_run=not confirm_create,
        allow_existing=allow_existing,
        account_root=account_root,
    )
    if not confirm_create:
        summary = plan.to_summary()
        summary["created"] = False
        return summary
    if allow_existing:
        raise PaperAccountBootstrapError("--allow-existing cannot be combined with actual create.")
    if plan.blocked_reason:
        raise PaperAccountBootstrapError(plan.blocked_reason)

    account_paths = validate_account_bootstrap_target(plan.account_id, account_root=account_root)
    for path in (
        account_paths.root,
        account_paths.reports_dir,
        account_paths.reviews_dir,
        account_paths.root / "archive",
        account_paths.config_snapshots_dir,
        account_paths.replay_diff_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)

    _write_account_snapshot_seed(
        account_paths.account_snapshot_path,
        snapshot_date=plan.snapshot_date,
        initial_cash=plan.initial_cash,
        currency=plan.currency,
        account_paths=account_paths,
    )
    _write_header_only_csv(
        account_paths.position_snapshot_path,
        PAPER_POSITION_SNAPSHOT_COLUMNS,
        account_paths=account_paths,
    )
    _write_header_only_csv(
        account_paths.execution_log_path,
        PAPER_EXECUTION_LOG_COLUMNS,
        account_paths=account_paths,
    )
    _write_current_state_seed(
        account_paths.current_state_snapshot_path(plan.snapshot_date),
        snapshot_date=plan.snapshot_date,
        initial_cash=plan.initial_cash,
        currency=plan.currency,
        account_id=plan.account_id,
        account_paths=account_paths,
    )

    summary = plan.to_summary()
    summary["created"] = True
    summary["dry_run"] = False
    return summary


def _write_header_only_csv(path: Path, columns: list[str], *, account_paths: PaperAccountPaths) -> None:
    assert_non_default_writer_target(path, account_id=account_paths.account_id, account_root=account_paths.root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()


def _write_account_snapshot_seed(
    path: Path,
    *,
    snapshot_date: str,
    initial_cash: float,
    currency: str,
    account_paths: PaperAccountPaths,
) -> None:
    assert_non_default_writer_target(path, account_id=account_paths.account_id, account_root=account_paths.root)
    row = {column: "" for column in PAPER_ACCOUNT_SNAPSHOT_COLUMNS}
    row.update(
        {
            "snapshot_date": snapshot_date,
            "currency": currency,
            "initial_cash": f"{initial_cash:.2f}",
            "cash": f"{initial_cash:.2f}",
            "positions_cost_value": "0.00",
            "total_equity_cost_basis": f"{initial_cash:.2f}",
            "cash_ratio_cost_basis": "1.0000000",
            "position_count": "0",
            "symbols": "",
            "applied_trade_count": "0",
            "valuation_method": "init",
            "source_execution_log": "",
            "source_current_state": f"paper_current_state_{snapshot_date.replace('-', '')}.json",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "positions_market_value": "0.00",
            "total_equity_market_value": f"{initial_cash:.2f}",
            "cash_ratio_market_value": "1.0000000",
            "unrealized_pnl": "0.00",
            "unrealized_pnl_pct": "0.0000000",
            "realized_pnl": "0.00",
            "realized_pnl_by_symbol": "{}",
            "total_pnl": "0.00",
            "total_pnl_pct": "0.0000000",
            "market_valuation_status": "INIT",
            "market_valuation_error": "",
            "valuation_price_date": "",
            "valuation_price_dates": "",
            "price_staleness_days": "",
            "max_price_staleness_days": "",
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_ACCOUNT_SNAPSHOT_COLUMNS)
        writer.writeheader()
        writer.writerow(row)


def _write_current_state_seed(
    path: Path,
    *,
    snapshot_date: str,
    initial_cash: float,
    currency: str,
    account_id: str,
    account_paths: PaperAccountPaths,
) -> None:
    assert_non_default_writer_target(path, account_id=account_paths.account_id, account_root=account_paths.root)
    state = create_initial_paper_state(initial_cash=initial_cash, currency=currency)
    payload = paper_account_state_to_current_state_dict(state, snapshot_date)
    payload.update(
        {
            "account_id": account_id,
            "snapshot_date": snapshot_date,
            "source": BOOTSTRAP_SOURCE,
            "schema_version": BOOTSTRAP_CURRENT_STATE_SCHEMA_VERSION,
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

"""Read-only first-run eligibility. No bootstrap, prepare, or ready-marker writes."""
from __future__ import annotations

import csv
import json
import math
from datetime import date
from pathlib import Path
from typing import Any

from core.paper_account_binding import assert_binding_matches, resolve_account_binding
from core.paper_account_paths import PaperAccountPaths, build_paper_account_paths
from core.paper_account_profile import load_paper_account_profiles, resolve_paper_account_profile
from core.paper_account_snapshot import PAPER_ACCOUNT_SNAPSHOT_COLUMNS
from core.paper_position_snapshot import PAPER_POSITION_SNAPSHOT_COLUMNS
from core.paper_execution_log import PAPER_EXECUTION_LOG_COLUMNS
from core.paper_snapshot_identity import validate_snapshot_account_identity
from core.runbook_calendar import MarketCalendar


def _rows(path: Path, columns: list[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != columns:
            raise ValueError(f"invalid_bootstrap_header:{path.name}")
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError(f"invalid_bootstrap_row:{path.name}")
    return rows


def _number(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("invalid_bootstrap_number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("invalid_bootstrap_number")
    return result


def _history_blockers(workspace: Path, account_id: str) -> list[str]:
    from core import failed_no_trade_closure, operational_gap_recovery, runbook_recovery, runbook_retirement
    from core.runbook_day_rollover import _load_account_states, DUPLICATE_DIRS
    from scripts import runbook_state

    records, errors = _load_account_states(workspace, account_id)
    blockers = [f"runbook_history_invalid:{e}" for e in errors if e != "runbook_states_directory_not_found"]
    if records:
        # Any run (including READY, NO_ACTION, FAILED or terminal) is non-fresh.
        blockers.append("runbook_history_present")
        if any(r.state.current_status == "FAILED" or r.state.last_error for r in records):
            blockers.append("failed_history_present")
        if any(r.state.recovery_authorizations for r in records):
            blockers.append("recovery_history_present")
    directories = set(DUPLICATE_DIRS) | set(runbook_recovery.TARGET_EVIDENCE_DIRS) | {
        runbook_state.STATE_DIRNAME, runbook_recovery.RECOVERY_DIRNAME,
        runbook_retirement.RETIREMENT_DIRNAME, failed_no_trade_closure.CLOSURE_DIRNAME,
        operational_gap_recovery.GENERIC_EVIDENCE_DIRNAME,
    }
    for dirname in sorted(directories):
        root = workspace / dirname
        if root.is_symlink():
            blockers.append(f"unreadable_history:{dirname}")
            continue
        if not root.exists():
            continue
        if not root.is_dir():
            blockers.append(f"unreadable_history:{dirname}")
            continue
        for path in root.rglob("*"):
            if path.is_symlink():
                blockers.append(f"unexplained_history_link:{dirname}")
                continue
            if any(part.startswith(account_id + "_") or part == account_id for part in path.relative_to(root).parts):
                blockers.append(f"lifecycle_history_present:{dirname}")
            if not path.is_file():
                continue
            if path.suffix != ".json":
                blockers.append(f"unexplained_history:{dirname}")
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                # Hashed evidence cannot be attributed safely when corrupt.
                blockers.append(f"unreadable_history:{dirname}")
                continue
            account_ids = _account_ids(payload)
            if account_id in account_ids:
                blockers.append(f"lifecycle_history_present:{dirname}")
            elif not account_ids:
                blockers.append(f"unattributable_history:{dirname}")
    legacy_state = workspace / runbook_state.STATE_FILENAME
    if legacy_state.exists():
        try:
            if _contains_account(json.loads(legacy_state.read_text(encoding="utf-8-sig")), account_id):
                blockers.append("runbook_history_present")
        except (OSError, ValueError):
            blockers.append("unreadable_legacy_state")
    return blockers


def _contains_account(value: Any, account_id: str) -> bool:
    if isinstance(value, dict):
        return value.get("account_id") == account_id or any(_contains_account(v, account_id) for v in value.values())
    if isinstance(value, list):
        return any(_contains_account(v, account_id) for v in value)
    return False


def _account_ids(value: Any) -> set[str]:
    if isinstance(value, dict):
        found = {
            item.strip() for key, item in value.items()
            if key == "account_id" and isinstance(item, str) and item.strip()
        }
        for item in value.values():
            found.update(_account_ids(item))
        return found
    if isinstance(value, list):
        found: set[str] = set()
        for item in value:
            found.update(_account_ids(item))
        return found
    return set()


def validate_prepare_first_request(
    *, account_id: str, account_paths: PaperAccountPaths, workspace: Path,
    authoritative_workspace: Path, data_date: str, trade_date: str,
    calendar: MarketCalendar, expected_binding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Inspect canonical local evidence without creating, repairing or advancing it.

    Market readiness/actual prepare are later gates (ML1-3/4). An eligible result
    is not a prepared/ready marker and is not authority to execute Stage A.
    """
    blockers: list[str] = []
    binding = None
    context = {"account_id": account_id, "data_date": data_date, "trade_date": trade_date}
    try:
        from scripts.runbook_state import get_runbook_day_id
        profiles = load_paper_account_profiles(allow_missing=False)
        profile = resolve_paper_account_profile(account_id, config=profiles)
        if profile.account_type not in {"paper", "test"}:
            raise ValueError("fresh_paper_account_mode_required")
        binding = resolve_account_binding(account_id, profiles=profiles)
        if expected_binding is not None:
            assert_binding_matches(expected_binding, binding)
        canonical = build_paper_account_paths(account_id, create=False)
        if account_paths.account_id != account_id or account_paths.legacy_default_used:
            raise ValueError("account_context_mismatch")
        if account_paths.root.resolve() != canonical.root.resolve():
            raise ValueError("account_root_mismatch")
        for field in ("execution_log_path", "account_snapshot_path", "position_snapshot_path"):
            if getattr(account_paths, field).resolve() != getattr(canonical, field).resolve():
                raise ValueError("account_artifact_path_mismatch")
        workspace = Path(workspace)
        if workspace.resolve() != Path(authoritative_workspace).resolve() or not workspace.is_dir():
            raise ValueError("workspace_mismatch")
        first_data, first_trade = date.fromisoformat(data_date), date.fromisoformat(trade_date)
        if first_data.isoformat() != data_date or first_trade.isoformat() != trade_date:
            raise ValueError("noncanonical_dates")
        calendar.require_coverage(first_data)
        if calendar.next_trading_day(first_data) != first_trade:
            raise ValueError("first_trade_date_must_be_next_trading_day")
        context["runbook_day_id"] = get_runbook_day_id(account_id, data_date, trade_date)
        current_path = canonical.current_state_snapshot_path(data_date)
        files = [canonical.account_snapshot_path, canonical.position_snapshot_path,
                 canonical.execution_log_path, current_path]
        if not canonical.root.is_dir() or canonical.root.is_symlink():
            raise ValueError("bootstrap_root_missing_or_unsafe")
        if any(not p.is_file() for p in files):
            blockers.append("partial_initialization")
        if any(p.is_symlink() or p.resolve().parent != canonical.root.resolve() for p in files):
            raise ValueError("bootstrap_path_mismatch")
        known = {p.resolve() for p in files}
        from core.paper_account_bootstrap import build_account_bootstrap_plan
        plan = build_account_bootstrap_plan(
            account_id=account_id, initial_cash=profile.initial_cash, currency=profile.currency,
            date_str=data_date, allow_existing=True, account_root=canonical.root,
        )
        known_dirs = {Path(p).resolve() for p in plan.would_create_dirs}
        if any(p.is_symlink() or (p.is_file() and p.resolve() not in known)
               or (p.is_dir() and p.resolve() not in known_dirs) for p in canonical.root.rglob("*")):
            blockers.append("unexplained_account_artifacts")
        blockers.extend(_history_blockers(workspace, account_id))
        if "partial_initialization" not in blockers:
            account_rows = _rows(canonical.account_snapshot_path, PAPER_ACCOUNT_SNAPSHOT_COLUMNS)
            validate_snapshot_account_identity(
                account_rows, fieldnames=PAPER_ACCOUNT_SNAPSHOT_COLUMNS,
                allowed_fieldnames=PAPER_ACCOUNT_SNAPSHOT_COLUMNS,
                expected_account_id=account_id, source_path=canonical.account_snapshot_path,
                account_root=canonical.root,
            )
            if len(account_rows) != 1:
                raise ValueError("bootstrap_account_history_or_missing_seed")
            row = account_rows[0]
            if row["snapshot_date"] != data_date:
                blockers.append("bootstrap_date_mismatch")
            if row["currency"] != profile.currency:
                blockers.append("bootstrap_currency_mismatch")
            initial = _number(profile.initial_cash)
            if initial <= 0 or any(_number(row[k]) != initial for k in
                                  ("initial_cash", "cash", "total_equity_cost_basis", "total_equity_market_value")):
                blockers.append("bootstrap_cash_mismatch")
            if any(_number(row[k]) != 0 for k in
                   ("position_count", "applied_trade_count", "positions_cost_value", "positions_market_value",
                    "unrealized_pnl", "unrealized_pnl_pct", "realized_pnl", "total_pnl", "total_pnl_pct")) or row["symbols"]:
                blockers.append("bootstrap_not_initial")
            if (any(_number(row[k]) != 1 for k in ("cash_ratio_cost_basis", "cash_ratio_market_value"))
                    or json.loads(row["realized_pnl_by_symbol"]) != {}):
                blockers.append("bootstrap_not_initial")
            if row["valuation_method"] != "init" or row["market_valuation_status"] != "INIT":
                blockers.append("bootstrap_source_mismatch")
            if row["source_current_state"] != current_path.name or row["source_execution_log"]:
                blockers.append("bootstrap_source_mismatch")
            if _rows(canonical.execution_log_path, PAPER_EXECUTION_LOG_COLUMNS):
                blockers.append("execution_history_present")
            if _rows(canonical.position_snapshot_path, PAPER_POSITION_SNAPSHOT_COLUMNS):
                blockers.append("position_history_present")
            current = json.loads(current_path.read_text(encoding="utf-8-sig"))
            if not isinstance(current, dict):
                raise ValueError("invalid_current_state")
            from core.paper_account_bootstrap import BOOTSTRAP_CURRENT_STATE_SCHEMA_VERSION, BOOTSTRAP_SOURCE
            if current.get("account_id") != account_id or current.get("snapshot_date") != data_date:
                blockers.append("bootstrap_current_identity_mismatch")
            if current.get("schema_version") != BOOTSTRAP_CURRENT_STATE_SCHEMA_VERSION or current.get("source") != BOOTSTRAP_SOURCE:
                blockers.append("bootstrap_current_source_mismatch")
            if "currency" in current and current["currency"] != profile.currency:
                blockers.append("bootstrap_currency_mismatch")
            if _number(current.get("absolute_cash")) != initial or _number(current.get("current_cash_ratio")) != 1:
                blockers.append("bootstrap_current_cash_mismatch")
            if _number(current.get("current_hedge_ratio")) != 0:
                blockers.append("bootstrap_current_position_mismatch")
            empty_fields = {"current_symbols": [], "shares": {}, "avg_price": {}, "highest_prices": {},
                            "highest_price_meta": {}, "hedge_symbols": [], "applied_trade_ids": []}
            if any(current.get(k) != v for k, v in empty_fields.items()):
                blockers.append("bootstrap_current_history_present")
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        blockers.append(str(exc) or type(exc).__name__)
    return {"eligible": not blockers, "blockers": sorted(set(blockers)),
            "context": context, "binding": binding,
            "next_action": "VALIDATED_NOT_PREPARED" if not blockers else "RESOLVE_BLOCKERS"}

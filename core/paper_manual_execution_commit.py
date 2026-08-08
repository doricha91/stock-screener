from __future__ import annotations

import csv
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from core.notion_manual_execution_importer import (
    FAIL,
    PASS,
    WARNING,
    MANUAL_EXECUTION_REASON,
    MANUAL_EXECUTION_SOURCE,
)
from core.notion_account_keys import (
    build_legacy_manual_execution_canonical_key,
    build_manual_execution_canonical_key,
    normalize_notion_account_id,
)
from core.paper_account_guard import assert_non_default_writer_target
from core.paper_account_snapshot import (
    build_paper_account_snapshot_row,
    save_paper_account_snapshot,
)
from core.paper_account_paths import PaperAccountPaths
from core.paper_account_state import build_paper_state_from_trades
from core.paper_current_state_storage import save_paper_current_state
from core.paper_execution_log import append_paper_execution_log
from core.long_position_policy import DEFAULT_MAX_LONG_POSITIONS, LongPositionAction
from core.manual_execution_long_position_cap import (
    ManualExecutionLongPositionValidation,
    get_configured_manual_execution_hedge_symbols,
    validate_manual_execution_long_position_actions,
)
from core.paper_market_valuation import value_paper_account_state
from core.paper_position_snapshot import (
    build_paper_position_snapshot_rows,
    save_paper_position_snapshot,
)
from core.paper_trade_preview import PaperTradePreview
from core.paths import (
    PAPER_TEST_DIR,
    dev_backups_dir,
    market_db_path,
    paper_account_snapshot_path,
    paper_current_state_snapshot_path,
    paper_execution_log_path,
    paper_position_snapshot_path,
    paper_reports_dir,
)


MANUAL_EXECUTION_REGIME = "MANUAL"


class ManualExecutionCommitError(RuntimeError):
    pass


@dataclass(frozen=True)
class ManualExecutionCommitResult:
    account_id: str
    execution_date: str
    preview_json_path: str
    commit_json_path: str
    commit_markdown_path: str
    committed_row_count: int
    committed_trade_ids: list[str]
    backups: dict[str, str | None]
    current_state_written: bool
    account_snapshot_written: bool
    position_snapshot_written: bool


def commit_manual_execution_preview(
    *,
    execution_date: str,
    preview_json_path: Path,
    allow_warnings: bool = False,
    account_paths: PaperAccountPaths | None = None,
    max_long_positions: int = DEFAULT_MAX_LONG_POSITIONS,
) -> ManualExecutionCommitResult:
    preview_payload = _load_preview_payload(preview_json_path)
    resolved_account_id = _resolve_preview_account_id(preview_payload, account_paths=account_paths)
    _validate_preview_payload(
        preview_payload,
        execution_date=execution_date,
        allow_warnings=allow_warnings,
    )

    candidate_payloads = [
        candidate
        for candidate in preview_payload.get("candidates", [])
        if candidate.get("validation_status") in {PASS, WARNING}
    ]
    if not candidate_payloads:
        raise ManualExecutionCommitError("Preview JSON contains no committable candidates.")
    _normalize_commit_candidate_payloads(candidate_payloads, account_id=resolved_account_id)
    allowed_root = account_paths.root if account_paths is not None and account_paths.account_id != "paper_default" else None

    previews = [_candidate_to_trade_preview(candidate) for candidate in candidate_payloads]
    writer_paths = _resolve_execution_writer_paths(execution_date=execution_date, account_paths=account_paths)
    log_path = writer_paths["paper_execution_log"]
    initial_cash, currency = _load_initial_cash_and_currency(writer_paths["paper_account_snapshot"])
    latest_state = build_paper_state_from_trades(
        _read_csv_rows(log_path),
        initial_cash=initial_cash,
        currency=currency,
    )
    hedge_symbols = get_configured_manual_execution_hedge_symbols()
    long_position_validation = validate_manual_execution_long_position_actions(
        latest_state.positions,
        [
            LongPositionAction(
                symbol=preview.symbol,
                action_type=preview.side,
                quantity=abs(preview.shares),
            )
            for preview in previews
        ],
        max_long_positions=max_long_positions,
        hedge_symbols=hedge_symbols,
    )
    if not long_position_validation.allowed:
        raise ManualExecutionCommitError(
            _format_long_position_cap_error(long_position_validation)
        )

    rows_to_append, append_warnings = append_paper_execution_log(
        previews,
        log_path,
        commit=False,
        allowed_root=allowed_root,
    )
    duplicate_warnings = [
        warning for warning in append_warnings
        if warning.startswith("Skipping duplicate paper trade:")
    ]
    if duplicate_warnings:
        raise ManualExecutionCommitError(
            "Commit blocked because the preview contains rows that already exist in paper_execution_log.csv."
        )
    if append_warnings:
        raise ManualExecutionCommitError(
            "Commit blocked because append pre-check returned warnings: " + "; ".join(append_warnings)
        )
    if len(rows_to_append) != len(previews):
        raise ManualExecutionCommitError("Commit blocked because pre-check row count does not match preview candidate count.")
    current_state_path = writer_paths["paper_state"]
    backup_paths = _create_dev_backups(
        execution_date=execution_date,
        targets={
            "paper_execution_log": log_path,
            "paper_account_snapshot": writer_paths["paper_account_snapshot"],
            "paper_position_snapshot": writer_paths["paper_position_snapshot"],
            "paper_current_state": current_state_path,
        },
        backup_dir=writer_paths["backup_dir"],
    )

    try:
        committed_rows, committed_warnings = append_paper_execution_log(
            previews,
            log_path,
            commit=True,
            allowed_root=allowed_root,
        )
        if committed_warnings:
            raise ManualExecutionCommitError(
                "Commit blocked because execution log append returned warnings: "
                + "; ".join(committed_warnings)
            )
        if len(committed_rows) != len(rows_to_append):
            raise ManualExecutionCommitError("Execution log append count did not match pre-check count.")

        committed_state = build_paper_state_from_trades(
            _read_csv_rows(log_path),
            initial_cash=initial_cash,
            currency=currency,
        )
        try:
            market_valuation = value_paper_account_state(
                committed_state,
                execution_date,
                Path(market_db_path()),
            )
        except Exception as exc:
            raise ManualExecutionCommitError(
                f"Commit blocked because market valuation failed for {execution_date}: {exc}"
            ) from exc

        account_snapshot_row = build_paper_account_snapshot_row(
            committed_state,
            execution_date,
            initial_cash=initial_cash,
            source_execution_log=str(log_path),
            source_current_state=str(current_state_path),
            market_valuation=market_valuation,
            account_id=resolved_account_id,
        )
        position_snapshot_rows = build_paper_position_snapshot_rows(
            committed_state,
            market_valuation,
            execution_date,
            account_id=resolved_account_id,
        )
        save_paper_current_state(
            committed_state,
            execution_date,
            current_state_path,
            writer_paths["archive_dir"],
            account_paths=account_paths,
        )
        save_paper_account_snapshot(
            account_snapshot_row,
            writer_paths["paper_account_snapshot"],
            writer_paths["archive_dir"],
            account_paths=account_paths,
        )
        save_paper_position_snapshot(
            position_snapshot_rows,
            execution_date,
            writer_paths["paper_position_snapshot"],
            writer_paths["archive_dir"],
            account_paths=account_paths,
        )
        sidecar_paths = _write_commit_sidecar(
            account_id=resolved_account_id,
            execution_date=execution_date,
            preview_json_path=preview_json_path,
            candidate_payloads=candidate_payloads,
            committed_rows=committed_rows,
            backup_paths=backup_paths,
            reports_dir=writer_paths["reports_dir"],
        )
    except Exception as exc:
        _restore_from_backups(
            targets={
                "paper_execution_log": log_path,
                "paper_account_snapshot": writer_paths["paper_account_snapshot"],
                "paper_position_snapshot": writer_paths["paper_position_snapshot"],
                "paper_current_state": current_state_path,
            },
            backup_paths=backup_paths,
        )
        if isinstance(exc, ManualExecutionCommitError):
            raise
        raise ManualExecutionCommitError(f"Manual execution commit failed and was rolled back: {exc}") from exc

    return ManualExecutionCommitResult(
        account_id=resolved_account_id,
        execution_date=execution_date,
        preview_json_path=str(preview_json_path),
        commit_json_path=str(sidecar_paths["json"]),
        commit_markdown_path=str(sidecar_paths["markdown"]),
        committed_row_count=len(rows_to_append),
        committed_trade_ids=[str(row.get("trade_id") or "") for row in rows_to_append],
        backups={key: (None if path is None else str(path)) for key, path in backup_paths.items()},
        current_state_written=True,
        account_snapshot_written=True,
        position_snapshot_written=True,
    )


def _format_long_position_cap_error(
    validation: ManualExecutionLongPositionValidation,
) -> str:
    policy = validation.policy
    return (
        "Commit blocked by independent long-position hard-cap validation before any write: "
        f"mode={validation.mode}, current={policy.current_count}, "
        f"projected={policy.projected_count}, max={validation.max_long_positions}, "
        f"error_codes={','.join(validation.error_codes) or 'none'}."
    )


def _load_preview_payload(preview_json_path: Path) -> dict[str, Any]:
    if not preview_json_path.exists():
        raise ManualExecutionCommitError(f"Preview JSON not found: {preview_json_path}")
    with preview_json_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ManualExecutionCommitError("Preview JSON root must be an object.")
    return payload


def _validate_preview_payload(
    payload: dict[str, Any],
    *,
    execution_date: str,
    allow_warnings: bool,
) -> None:
    preview_date = str(payload.get("execution_date") or "").strip()
    if preview_date != execution_date:
        raise ManualExecutionCommitError(
            f"Preview date mismatch: preview={preview_date or 'blank'} expected={execution_date}."
        )
    fail_count = int(payload.get("fail_count") or 0)
    commit_allowed = str(payload.get("commit_allowed") or "").strip().lower()
    if fail_count > 0 or commit_allowed == "false":
        raise ManualExecutionCommitError("Preview contains FAIL rows; commit is blocked.")
    if commit_allowed == "true_with_warnings" and not allow_warnings:
        raise ManualExecutionCommitError(
            "Preview contains WARNING rows; rerun commit with --allow-warnings to proceed."
        )
    if commit_allowed not in {"true", "true_with_warnings"}:
        raise ManualExecutionCommitError(f"Unsupported commit_allowed value: {commit_allowed or 'blank'}.")


def _resolve_preview_account_id(
    payload: dict[str, Any],
    *,
    account_paths: PaperAccountPaths | None = None,
) -> str:
    root_account_id = payload.get("account_id")
    if root_account_id is not None and str(root_account_id).strip():
        resolved_account_id = normalize_notion_account_id(str(root_account_id).strip())
    else:
        resolved_account_id = "paper_default"

    candidate_account_ids = {
        normalize_notion_account_id(str(candidate.get("account_id") or "").strip())
        for candidate in payload.get("candidates", [])
        if str(candidate.get("account_id") or "").strip()
    }
    if len(candidate_account_ids) > 1:
        raise ManualExecutionCommitError("Preview JSON contains mixed account_id values.")
    if candidate_account_ids:
        candidate_account_id = next(iter(candidate_account_ids))
        if resolved_account_id != candidate_account_id:
            raise ManualExecutionCommitError(
                "Preview JSON account_id does not match candidate account_id values."
            )
        resolved_account_id = candidate_account_id
    if account_paths is not None and account_paths.account_id != resolved_account_id:
        raise ManualExecutionCommitError("Provided account_paths.account_id does not match preview account_id.")
    if resolved_account_id != "paper_default" and account_paths is None:
        raise ManualExecutionCommitError(
            "Non-default manual execution commit requires account-aware writer paths."
        )
    return resolved_account_id


def _normalize_commit_candidate_payloads(
    candidate_payloads: list[dict[str, Any]],
    *,
    account_id: str,
) -> None:
    for candidate in candidate_payloads:
        candidate["account_id"] = account_id
        raw_canonical_key = str(candidate.get("canonical_key") or "").strip()
        if not raw_canonical_key:
            raise ManualExecutionCommitError("Preview candidate is missing canonical_key.")
        normalized = _normalize_execution_canonical_key(
            account_id=account_id,
            canonical_key=raw_canonical_key,
        )
        candidate["canonical_key"] = normalized["canonical_key"]
        candidate["legacy_canonical_key"] = normalized["legacy_canonical_key"]
        candidate["legacy_key_compatible"] = normalized["legacy_key_compatible"]


def _normalize_execution_canonical_key(
    *,
    account_id: str,
    canonical_key: str,
) -> dict[str, Any]:
    parts = canonical_key.split(":")
    if len(parts) == 6 and parts[0] == "manual_execution":
        key_account_id = normalize_notion_account_id(parts[1])
        if key_account_id != account_id:
            raise ManualExecutionCommitError(
                f"Preview canonical_key account_id mismatch: {canonical_key} vs {account_id}."
            )
        return {
            "canonical_key": canonical_key,
            "legacy_canonical_key": build_legacy_manual_execution_canonical_key(
                parts[2],
                parts[3],
                parts[4],
                int(parts[5]),
            ) if account_id == "paper_default" else None,
            "legacy_key_compatible": account_id == "paper_default",
        }
    if len(parts) == 5 and parts[0] == "manual_execution":
        if account_id != "paper_default":
            raise ManualExecutionCommitError(
                "Legacy canonical_key is not allowed for non-default manual execution commit."
            )
        normalized_key = build_manual_execution_canonical_key(
            account_id,
            parts[1],
            parts[2],
            parts[3],
            int(parts[4]),
        )
        return {
            "canonical_key": normalized_key,
            "legacy_canonical_key": canonical_key,
            "legacy_key_compatible": True,
        }
    raise ManualExecutionCommitError(f"Unsupported manual execution canonical_key format: {canonical_key}.")


def _candidate_to_trade_preview(candidate: dict[str, Any]) -> PaperTradePreview:
    side = str(candidate.get("side") or "").strip().upper()
    quantity = int(candidate.get("quantity") or 0)
    if side not in {"BUY", "SELL"}:
        raise ManualExecutionCommitError(f"Invalid side in preview candidate: {side or 'blank'}.")
    shares = quantity if side == "BUY" else -quantity
    price = float(candidate.get("actual_price") or 0.0)
    return PaperTradePreview(
        date=str(candidate.get("execution_date") or "").strip(),
        regime=MANUAL_EXECUTION_REGIME,
        symbol=str(candidate.get("symbol") or "").strip().upper(),
        side=side,
        shares=shares,
        price=price,
        gross_amount=shares * price,
        source=MANUAL_EXECUTION_SOURCE,
        status="READY_FOR_PAPER_TRADE",
        reason=MANUAL_EXECUTION_REASON,
        notes=str(candidate.get("note") or "").strip(),
        rec_shares=quantity,
        rec_price=price,
    )


def _load_initial_cash_and_currency(account_snapshot_path: Path) -> tuple[float, str]:
    rows = _read_csv_rows(account_snapshot_path)
    if not rows:
        raise ManualExecutionCommitError("paper_account_snapshot.csv has no rows.")
    latest = max(rows, key=lambda row: str(row.get("snapshot_date") or "").strip())
    return float(latest.get("initial_cash") or 100000.0), str(latest.get("currency") or "USD").strip() or "USD"


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows: list[dict[str, str]] = []
        for row in csv.DictReader(handle):
            normalized: dict[str, str] = {}
            for key, value in row.items():
                normalized[(key or "").replace("\ufeff", "").strip()] = value or ""
            rows.append(normalized)
        return rows


def _create_dev_backups(
    *,
    execution_date: str,
    targets: dict[str, Path],
    backup_dir: Path,
) -> dict[str, Path | None]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backups: dict[str, Path | None] = {}
    compact_date = execution_date.replace("-", "")
    for label, source_path in targets.items():
        if not source_path.exists():
            backups[label] = None
            continue
        backup_path = backup_dir / f"{source_path.stem}_before_manual_execution_commit_{compact_date}_{timestamp}{source_path.suffix}"
        shutil.copy2(source_path, backup_path)
        backups[label] = backup_path
    return backups


def _restore_from_backups(
    *,
    targets: dict[str, Path],
    backup_paths: dict[str, Path | None],
) -> None:
    for label, target_path in targets.items():
        backup_path = backup_paths.get(label)
        if backup_path is None:
            if target_path.exists():
                target_path.unlink()
            continue
        shutil.copy2(backup_path, target_path)


def _write_commit_sidecar(
    *,
    account_id: str,
    execution_date: str,
    preview_json_path: Path,
    candidate_payloads: list[dict[str, Any]],
    committed_rows: list[dict[str, Any]],
    backup_paths: dict[str, Path | None],
    reports_dir: Path,
) -> dict[str, Path]:
    compact_date = execution_date.replace("-", "")
    json_path = reports_dir / f"manual_execution_import_commit_{compact_date}.json"
    markdown_path = reports_dir / f"manual_execution_import_commit_{compact_date}.md"
    reports_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "status": "COMMITTED",
        "account_id": account_id,
        "execution_date": execution_date,
        "preview_json_path": str(preview_json_path),
        "committed_row_count": len(committed_rows),
        "committed_trade_ids": [str(row.get("trade_id") or "").strip() for row in committed_rows],
        "current_state_written": True,
        "account_snapshot_written": True,
        "position_snapshot_written": True,
        "backup_paths": {key: (None if path is None else str(path)) for key, path in backup_paths.items()},
        "committed_rows": [
            {
                "account_id": candidate.get("account_id"),
                "canonical_key": candidate.get("canonical_key"),
                "legacy_canonical_key": candidate.get("legacy_canonical_key"),
                "legacy_key_compatible": bool(candidate.get("legacy_key_compatible")),
                "page_id": candidate.get("page_id"),
                "symbol": candidate.get("symbol"),
                "side": candidate.get("side"),
                "quantity": candidate.get("quantity"),
                "actual_price": candidate.get("actual_price"),
                "commission": candidate.get("commission"),
                "currency": candidate.get("currency"),
                "broker": candidate.get("broker"),
                "validation_status": candidate.get("validation_status"),
                "validation_issues": candidate.get("validation_issues", []),
                "commit_status": "COMMITTED",
                "committed_trade_id": str(row.get("trade_id") or "").strip(),
            }
            for candidate, row in zip(candidate_payloads, committed_rows)
        ],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Manual Execution Commit [{execution_date}]",
        "",
        f"- Preview JSON: {preview_json_path}",
        "",
        "## Rows",
    ]
    for item in payload["committed_rows"]:
        lines.extend(
            [
                f"- {item['symbol']} {item['side']} {item['quantity']} @ {item['actual_price']}",
                f"  - account_id: {item['account_id']}",
                f"  - canonical_key: {item['canonical_key']}",
                f"  - legacy_canonical_key: {item['legacy_canonical_key'] or '-'}",
                f"  - page_id: {item['page_id']}",
                f"  - trade_id: {item['committed_trade_id']}",
                f"  - commission: {item['commission']}",
                f"  - currency: {item['currency']}",
                f"  - broker: {item['broker'] or '-'}",
                f"  - validation_status: {item['validation_status']}",
            ]
        )
    markdown_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path}


def _resolve_execution_writer_paths(
    *,
    execution_date: str,
    account_paths: PaperAccountPaths | None,
) -> dict[str, Path]:
    if account_paths is None or account_paths.account_id == "paper_default":
        return {
            "paper_execution_log": paper_execution_log_path(),
            "paper_account_snapshot": paper_account_snapshot_path(),
            "paper_position_snapshot": paper_position_snapshot_path(),
            "paper_state": paper_current_state_snapshot_path(execution_date),
            "reports_dir": paper_reports_dir(),
            "archive_dir": PAPER_TEST_DIR / "archive",
            "backup_dir": dev_backups_dir(),
        }

    targets = {
        "paper_execution_log": account_paths.execution_log_path,
        "paper_account_snapshot": account_paths.account_snapshot_path,
        "paper_position_snapshot": account_paths.position_snapshot_path,
        "paper_state": account_paths.current_state_snapshot_path(execution_date),
        "reports_dir": account_paths.reports_dir,
        "archive_dir": account_paths.root / "archive",
        "backup_dir": account_paths.root / "archive" / "dev_backups",
    }
    for path in targets.values():
        assert_non_default_writer_target(
            path,
            account_id=account_paths.account_id,
            account_root=account_paths.root,
        )
    return targets

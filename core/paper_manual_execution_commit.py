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
from core.paper_account_snapshot import (
    build_paper_account_snapshot_row,
    save_paper_account_snapshot,
)
from core.paper_account_state import build_paper_state_from_trades
from core.paper_execution_log import append_paper_execution_log
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
    paper_execution_log_path,
    paper_position_snapshot_path,
    paper_reports_dir,
)


MANUAL_EXECUTION_REGIME = "MANUAL"


class ManualExecutionCommitError(RuntimeError):
    pass


@dataclass(frozen=True)
class ManualExecutionCommitResult:
    execution_date: str
    preview_json_path: str
    commit_json_path: str
    commit_markdown_path: str
    committed_row_count: int
    committed_trade_ids: list[str]
    backups: dict[str, str | None]
    account_snapshot_written: bool
    position_snapshot_written: bool


def commit_manual_execution_preview(
    *,
    execution_date: str,
    preview_json_path: Path,
    allow_warnings: bool = False,
) -> ManualExecutionCommitResult:
    preview_payload = _load_preview_payload(preview_json_path)
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

    previews = [_candidate_to_trade_preview(candidate) for candidate in candidate_payloads]
    log_path = paper_execution_log_path()
    rows_to_append, append_warnings = append_paper_execution_log(previews, log_path, commit=False)
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

    existing_rows = _read_csv_rows(log_path)
    combined_rows = existing_rows + rows_to_append
    initial_cash, currency = _load_initial_cash_and_currency()
    state = build_paper_state_from_trades(
        combined_rows,
        initial_cash=initial_cash,
        currency=currency,
    )
    try:
        market_valuation = value_paper_account_state(
            state,
            execution_date,
            Path(market_db_path()),
        )
    except Exception as exc:
        raise ManualExecutionCommitError(
            f"Commit blocked because market valuation failed for {execution_date}: {exc}"
        ) from exc

    account_snapshot_row = build_paper_account_snapshot_row(
        state,
        execution_date,
        initial_cash=initial_cash,
        source_execution_log=str(log_path),
        source_current_state="",
        market_valuation=market_valuation,
    )
    position_snapshot_rows = build_paper_position_snapshot_rows(
        state,
        market_valuation,
        execution_date,
    )

    backup_paths = _create_dev_backups(
        execution_date=execution_date,
        targets={
            "paper_execution_log": log_path,
            "paper_account_snapshot": paper_account_snapshot_path(),
            "paper_position_snapshot": paper_position_snapshot_path(),
        },
    )

    try:
        committed_rows, committed_warnings = append_paper_execution_log(previews, log_path, commit=True)
        if committed_warnings:
            raise ManualExecutionCommitError(
                "Commit blocked because execution log append returned warnings: "
                + "; ".join(committed_warnings)
            )
        if len(committed_rows) != len(rows_to_append):
            raise ManualExecutionCommitError("Execution log append count did not match pre-check count.")

        save_paper_account_snapshot(
            account_snapshot_row,
            paper_account_snapshot_path(),
            PAPER_TEST_DIR / "archive",
        )
        save_paper_position_snapshot(
            position_snapshot_rows,
            execution_date,
            paper_position_snapshot_path(),
            PAPER_TEST_DIR / "archive",
        )
        sidecar_paths = _write_commit_sidecar(
            execution_date=execution_date,
            preview_json_path=preview_json_path,
            candidate_payloads=candidate_payloads,
            committed_rows=committed_rows,
            backup_paths=backup_paths,
        )
    except Exception as exc:
        _restore_from_backups(
            targets={
                "paper_execution_log": log_path,
                "paper_account_snapshot": paper_account_snapshot_path(),
                "paper_position_snapshot": paper_position_snapshot_path(),
            },
            backup_paths=backup_paths,
        )
        if isinstance(exc, ManualExecutionCommitError):
            raise
        raise ManualExecutionCommitError(f"Manual execution commit failed and was rolled back: {exc}") from exc

    return ManualExecutionCommitResult(
        execution_date=execution_date,
        preview_json_path=str(preview_json_path),
        commit_json_path=str(sidecar_paths["json"]),
        commit_markdown_path=str(sidecar_paths["markdown"]),
        committed_row_count=len(rows_to_append),
        committed_trade_ids=[str(row.get("trade_id") or "") for row in rows_to_append],
        backups={key: (None if path is None else str(path)) for key, path in backup_paths.items()},
        account_snapshot_written=True,
        position_snapshot_written=True,
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


def _load_initial_cash_and_currency() -> tuple[float, str]:
    rows = _read_csv_rows(paper_account_snapshot_path())
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
) -> dict[str, Path | None]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = dev_backups_dir()
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
    execution_date: str,
    preview_json_path: Path,
    candidate_payloads: list[dict[str, Any]],
    committed_rows: list[dict[str, Any]],
    backup_paths: dict[str, Path | None],
) -> dict[str, Path]:
    compact_date = execution_date.replace("-", "")
    reports_dir = paper_reports_dir()
    json_path = reports_dir / f"manual_execution_import_commit_{compact_date}.json"
    markdown_path = reports_dir / f"manual_execution_import_commit_{compact_date}.md"

    payload = {
        "execution_date": execution_date,
        "preview_json_path": str(preview_json_path),
        "backup_paths": {key: (None if path is None else str(path)) for key, path in backup_paths.items()},
        "committed_rows": [
            {
                "canonical_key": candidate.get("canonical_key"),
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
                f"  - canonical_key: {item['canonical_key']}",
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

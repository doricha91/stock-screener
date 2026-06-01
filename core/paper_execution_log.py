import csv
import hashlib
from datetime import datetime
from pathlib import Path

from core.paper_account_guard import assert_path_under_account_root
from core.paper_safety import assert_paper_path
from core.paper_trade_preview import PaperTradePreview
from core.paths import PAPER_TEST_DIR


PAPER_EXECUTION_LOG_COLUMNS = [
    "trade_id",
    "date",
    "regime",
    "symbol",
    "side",
    "shares",
    "price",
    "gross_amount",
    "source",
    "status",
    "reason",
    "notes",
    "rec_shares",
    "rec_price",
    "created_at",
]


def build_paper_trade_id(row: dict) -> str:
    trade_id_source = "|".join(
        [
            str(row.get("date", "")).strip(),
            str(row.get("symbol", "")).strip(),
            str(row.get("side", "")).strip().upper(),
            str(row.get("shares", "")).strip(),
            f"{float(row.get('price', 0.0)):.6f}",
            str(row.get("reason", "")).strip(),
            str(row.get("source", "")).strip(),
        ]
    )
    return hashlib.sha256(trade_id_source.encode("utf-8")).hexdigest()


def paper_trade_preview_to_row(preview: PaperTradePreview) -> dict:
    created_at = datetime.now().isoformat(timespec="seconds")
    row = {
        "date": preview.date,
        "regime": preview.regime,
        "symbol": preview.symbol,
        "side": preview.side,
        "shares": preview.shares,
        "price": preview.price,
        "gross_amount": preview.gross_amount,
        "source": preview.source,
        "status": preview.status,
        "reason": preview.reason,
        "notes": preview.notes,
        "rec_shares": preview.rec_shares if preview.rec_shares is not None else "",
        "rec_price": preview.rec_price if preview.rec_price is not None else "",
        "created_at": created_at,
    }
    row["trade_id"] = build_paper_trade_id(row)
    return {column: row.get(column, "") for column in PAPER_EXECUTION_LOG_COLUMNS}


def append_paper_execution_log(
    previews: list[PaperTradePreview],
    log_path: Path,
    commit: bool = False,
    allowed_root: Path | None = None,
) -> tuple[list[dict], list[str]]:
    if allowed_root is None:
        assert_paper_path(log_path, PAPER_TEST_DIR)
    else:
        assert_path_under_account_root(log_path, allowed_root)

    warnings: list[str] = []
    rows_to_append: list[dict] = []

    if not previews:
        warnings.append("No READY_FOR_PAPER_TRADE previews to append")
        return rows_to_append, warnings

    existing_trade_ids: set[str] = set()
    if log_path.exists():
        with log_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                trade_id = str(row.get("trade_id", "")).strip()
                if trade_id:
                    existing_trade_ids.add(trade_id)

    batch_trade_ids: set[str] = set()
    for preview in previews:
        row = paper_trade_preview_to_row(preview)
        trade_id = row["trade_id"]
        if trade_id in existing_trade_ids or trade_id in batch_trade_ids:
            warnings.append(
                f"Skipping duplicate paper trade: {preview.symbol} {preview.side} "
                f"{abs(preview.shares)} @ {preview.price:.2f}"
            )
            continue
        rows_to_append.append(row)
        batch_trade_ids.add(trade_id)

    if commit and rows_to_append:
        file_exists = log_path.exists()
        with log_path.open("a", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=PAPER_EXECUTION_LOG_COLUMNS)
            if not file_exists:
                writer.writeheader()
            writer.writerows(rows_to_append)

    return rows_to_append, warnings

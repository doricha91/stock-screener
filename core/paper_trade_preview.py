from dataclasses import dataclass
from typing import Optional

from core.execution_logger import clean_numeric


@dataclass(frozen=True)
class PaperTradePreview:
    date: str
    regime: str
    symbol: str
    side: str
    shares: int
    price: float
    gross_amount: float
    source: str
    status: str
    reason: str
    notes: str = ""
    rec_shares: Optional[int] = None
    rec_price: Optional[float] = None


def build_paper_trade_previews(
    journal_rows: list[dict],
) -> tuple[list[PaperTradePreview], list[str]]:
    previews: list[PaperTradePreview] = []
    warnings: list[str] = []

    for row in journal_rows:
        symbol = str(row.get("symbol", "")).strip() or "UNKNOWN"
        status = str(row.get("status", "")).strip()
        side = str(row.get("type", "")).strip().upper()
        reason = str(row.get("reason", "")).strip()
        reason_upper = reason.upper()

        if status != "READY_FOR_PAPER_TRADE":
            warnings.append(f"Skipping {symbol}: status={status or 'UNKNOWN'}")
            continue

        if side not in {"BUY", "SELL"}:
            warnings.append(f"Skipping {symbol}: unsupported side={side or 'UNKNOWN'}")
            continue

        if reason_upper.startswith("REVIEW") or reason_upper.startswith("WARNING"):
            warnings.append(f"Skipping {symbol}: reason={reason}")
            continue

        act_shares = str(row.get("act_shares", "")).strip()
        act_price = str(row.get("act_price", "")).strip()
        if not act_shares or not act_price or not reason:
            warnings.append(f"Skipping {symbol}: missing actual fill fields")
            continue

        try:
            shares_abs = int(clean_numeric(act_shares))
            price = float(clean_numeric(act_price))
            if shares_abs <= 0 or price <= 0:
                raise ValueError("shares and price must be > 0")
        except Exception as exc:
            warnings.append(f"Skipping {symbol}: invalid numeric fields ({exc})")
            continue

        rec_shares_val: Optional[int] = None
        rec_price_val: Optional[float] = None
        try:
            rec_shares_raw = str(row.get("rec_shares", "")).strip()
            if rec_shares_raw:
                rec_shares_val = int(clean_numeric(rec_shares_raw))
        except Exception:
            warnings.append(f"{symbol}: rec_shares parse failed")

        try:
            rec_price_raw = str(row.get("rec_price", "")).strip()
            if rec_price_raw:
                rec_price_val = float(clean_numeric(rec_price_raw))
        except Exception:
            warnings.append(f"{symbol}: rec_price parse failed")

        shares = shares_abs if side == "BUY" else -shares_abs
        gross_amount = shares * price

        previews.append(
            PaperTradePreview(
                date=str(row.get("date", "")).strip(),
                regime=str(row.get("regime", "")).strip(),
                symbol=symbol,
                side=side,
                shares=shares,
                price=price,
                gross_amount=gross_amount,
                source="journal_actual_fill",
                status="READY_FOR_PAPER_TRADE",
                reason=reason,
                notes=str(row.get("notes", "")).strip(),
                rec_shares=rec_shares_val,
                rec_price=rec_price_val,
            )
        )

    return previews, warnings

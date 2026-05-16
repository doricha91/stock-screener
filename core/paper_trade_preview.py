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


@dataclass(frozen=True)
class ResolvedPaperFill:
    shares: int
    price: float
    source: str
    reason: str


BLANK_ACTUAL_VALUES = {"", "[]", "[ ]", "[  ]", "n/a", "nan", "none", "null"}
PAPER_VIRTUAL_FILL_REASON = "Act fields blank; used Rec_Shares/Rec_Price as paper fill"


def is_blank_actual_value(value) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    if not text:
        return True
    normalized = text.lower().replace("\u00a0", " ")
    normalized = " ".join(normalized.split())
    return normalized in BLANK_ACTUAL_VALUES


def _parse_positive_int(value, field_name: str) -> int:
    cleaned = clean_numeric(str(value))
    if not cleaned:
        raise ValueError(f"{field_name} is blank")
    parsed = int(float(cleaned))
    if parsed <= 0:
        raise ValueError(f"{field_name} must be > 0")
    return parsed


def _parse_positive_float(value, field_name: str) -> float:
    cleaned = clean_numeric(str(value))
    if not cleaned:
        raise ValueError(f"{field_name} is blank")
    parsed = float(cleaned)
    if parsed <= 0:
        raise ValueError(f"{field_name} must be > 0")
    return parsed


def resolve_paper_actual_fill(row: dict) -> ResolvedPaperFill:
    act_shares_raw = row.get("act_shares", "")
    act_price_raw = row.get("act_price", "")
    rec_shares_raw = row.get("rec_shares", "")
    rec_price_raw = row.get("rec_price", "")

    act_shares_blank = is_blank_actual_value(act_shares_raw)
    act_price_blank = is_blank_actual_value(act_price_raw)
    shares_source = rec_shares_raw if act_shares_blank else act_shares_raw
    price_source = rec_price_raw if act_price_blank else act_price_raw

    shares_abs = _parse_positive_int(shares_source, "shares")
    price = _parse_positive_float(price_source, "price")
    used_fallback = act_shares_blank or act_price_blank
    return ResolvedPaperFill(
        shares=shares_abs,
        price=price,
        source="paper_virtual_fill" if used_fallback else "journal_actual_fill",
        reason=PAPER_VIRTUAL_FILL_REASON if used_fallback else str(row.get("reason", "")).strip(),
    )


def can_resolve_paper_actual_fill(row: dict) -> bool:
    try:
        resolve_paper_actual_fill(row)
        return True
    except Exception:
        return False


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

        if not reason:
            warnings.append(f"Skipping {symbol}: missing actual fill fields")
            continue

        try:
            resolved_fill = resolve_paper_actual_fill(row)
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

        shares = resolved_fill.shares if side == "BUY" else -resolved_fill.shares
        gross_amount = shares * resolved_fill.price

        previews.append(
            PaperTradePreview(
                date=str(row.get("date", "")).strip(),
                regime=str(row.get("regime", "")).strip(),
                symbol=symbol,
                side=side,
                shares=shares,
                price=resolved_fill.price,
                gross_amount=gross_amount,
                source=resolved_fill.source,
                status="READY_FOR_PAPER_TRADE",
                reason=resolved_fill.reason,
                notes=str(row.get("notes", "")).strip(),
                rec_shares=rec_shares_val,
                rec_price=rec_price_val,
            )
        )

    return previews, warnings

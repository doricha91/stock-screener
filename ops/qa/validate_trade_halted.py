# ops/qa/validate_trade_halted.py
# 확장 검증 4종(정책 일치 버전):
# 1) trade_halted=1인 날 신규 심볼(신규 포지션) 추가 금지  [ERROR]
# 2) cash cushion 일관성: available_cash_for_trading == cash - required_cash (허용오차 eps) [WARN]
# 3) cash < required_cash 자체는 정책상 정상 가능 → 기본은 [WARN]
#    단, cash < required_cash 인 날 "신규 심볼 추가"가 있으면 [ERROR]
# 4) 데이터 무결성: 날짜 중복/필수 숫자 NaN/비정상 감지 [ERROR], 일부는 [WARN]

from __future__ import annotations

from pathlib import Path
import sys
import csv
from dataclasses import dataclass
from typing import List, Set, Tuple, Optional
import math

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TRACE_PATH = ROOT / "scripts" / "outputs" / "backtest_daily_trace.csv"

EPS = 1e-6


@dataclass
class DayRow:
    date: str
    trade_halted: int
    regime: str
    positions_count: int
    symbols: Set[str]
    cash: float
    total_equity: float
    required_cash: float
    available_cash_for_trading: float


def _parse_int(x: str, default: int = 0) -> int:
    try:
        return int(float(x))
    except Exception:
        return default


def _parse_float(x: str, default: float = float("nan")) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _parse_symbols(x: str) -> Set[str]:
    x = (x or "").strip()
    if not x:
        return set()
    return {s for s in x.split("|") if s}


def _is_bad_number(x: float) -> bool:
    return x is None or math.isnan(x) or math.isinf(x)


def read_trace(path: Path) -> List[DayRow]:
    if not path.exists():
        raise FileNotFoundError(f"Trace file not found: {path} (CWD={Path.cwd()})")

    rows: List[DayRow] = []
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        required_cols = {
            "date",
            "trade_halted",
            "regime",
            "positions_count",
            "symbols",
            "cash",
            "total_equity",
            "required_cash",
            "available_cash_for_trading",
        }
        missing = required_cols - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing columns in CSV: {sorted(missing)}")

        for r in reader:
            rows.append(
                DayRow(
                    date=(r["date"] or "").strip(),
                    trade_halted=_parse_int(r["trade_halted"]),
                    regime=(r.get("regime") or "").strip(),
                    positions_count=_parse_int(r["positions_count"]),
                    symbols=_parse_symbols(r.get("symbols", "")),
                    cash=_parse_float(r.get("cash", "")),
                    total_equity=_parse_float(r.get("total_equity", "")),
                    required_cash=_parse_float(r.get("required_cash", "")),
                    available_cash_for_trading=_parse_float(r.get("available_cash_for_trading", "")),
                )
            )

    rows.sort(key=lambda x: x.date)
    return rows


def validate(rows: List[DayRow]) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []

    # ---- (검증 4) 데이터 무결성 ----
    seen_dates: Set[str] = set()
    prev_date: Optional[str] = None

    for i, r in enumerate(rows):
        if not r.date:
            errors.append(f"[ERROR] Row {i}: empty date")
            continue

        if r.date in seen_dates:
            errors.append(f"[ERROR] Duplicate date found: {r.date}")
        seen_dates.add(r.date)

        if prev_date is not None and r.date < prev_date:
            errors.append(f"[ERROR] Date order anomaly: {prev_date} -> {r.date}")
        prev_date = r.date

        numeric_fields = {
            "cash": r.cash,
            "total_equity": r.total_equity,
            "required_cash": r.required_cash,
            "available_cash_for_trading": r.available_cash_for_trading,
        }
        for name, val in numeric_fields.items():
            if _is_bad_number(val):
                errors.append(f"[ERROR] {r.date}: {name} is not a valid number ({val})")

        if not _is_bad_number(r.total_equity) and r.total_equity < -EPS:
            errors.append(f"[ERROR] {r.date}: total_equity < 0 ({r.total_equity})")

        if not _is_bad_number(r.cash) and r.cash < -EPS:
            warnings.append(f"[WARN] {r.date}: cash < 0 ({r.cash}) (margin/borrow가 없다면 비정상)")

        if r.positions_count != len(r.symbols):
            warnings.append(
                f"[WARN] {r.date}: positions_count({r.positions_count}) != len(symbols)({len(r.symbols)})"
            )

    # ---- prev/cur 비교 검증 ----
    prev: Optional[DayRow] = None
    for cur in rows:
        if prev is None:
            prev = cur
            continue

        added = cur.symbols - prev.symbols
        delta_cnt = cur.positions_count - prev.positions_count

        # (검증 1) trade_halted=1이면 신규 심볼 추가 금지
        if cur.trade_halted == 1:
            if added:
                errors.append(
                    f"[ERROR] {cur.date}: trade_halted=1 but NEW symbols added: {sorted(added)} "
                    f"(prev={sorted(prev.symbols)} -> cur={sorted(cur.symbols)})"
                )
            if delta_cnt > 0 and not added:
                warnings.append(
                    f"[WARN] {cur.date}: trade_halted=1 and positions_count increased (+{delta_cnt}) "
                    f"but no new symbols detected. Check CSV/symbol encoding."
                )

        # (검증 2) cash cushion 계산 일관성
        if not (_is_bad_number(cur.cash) or _is_bad_number(cur.required_cash) or _is_bad_number(cur.available_cash_for_trading)):
            expected = cur.cash - cur.required_cash
            diff = abs(expected - cur.available_cash_for_trading)
            if diff > max(EPS, 1e-3):
                warnings.append(
                    f"[WARN] {cur.date}: available_cash_for_trading mismatch "
                    f"(cash - required_cash = {expected:.6f}, got {cur.available_cash_for_trading:.6f}, diff={diff:.6f})"
                )

        # (검증 3) 정책 일치 버전:
        # cash < required_cash는 "정상 가능" (강제 청산이 없으므로)
        # 단, 이 상태에서 신규 심볼이 추가되면 정책 위반 → ERROR
        if not (_is_bad_number(cur.cash) or _is_bad_number(cur.required_cash)):
            if cur.cash + EPS < cur.required_cash:
                # 기본은 경고(현금 부족 상태 자체)
                warnings.append(
                    f"[WARN] {cur.date}: under-cushion (cash < required_cash) "
                    f"(cash={cur.cash:.6f}, required_cash={cur.required_cash:.6f})"
                )
                # 그날 신규 심볼이 추가되면 에러(쿠션 부족인데 신규 매수 발생)
                if added:
                    errors.append(
                        f"[ERROR] {cur.date}: under-cushion but NEW symbols added: {sorted(added)}"
                    )

        prev = cur

    return errors, warnings


def summarize(rows: List[DayRow]) -> str:
    total_days = len(rows)
    halted_days = sum(1 for r in rows if r.trade_halted == 1)

    regimes = {}
    for r in rows:
        k = r.regime or "(blank)"
        regimes[k] = regimes.get(k, 0) + 1
    regimes_str = ", ".join(f"{k}:{v}" for k, v in sorted(regimes.items(), key=lambda x: (-x[1], x[0])))

    return (
        f"Days: {total_days}\n"
        f"trade_halted=1 days: {halted_days}\n"
        f"Regime counts: {regimes_str}\n"
        f"Trace file: {TRACE_PATH}"
    )


def main():
    rows = read_trace(TRACE_PATH)
    errors, warnings = validate(rows)

    print("=== Summary ===")
    print(summarize(rows))
    print()

    if warnings:
        print("=== Warnings ===")
        for w in warnings:
            print(w)
        print()

    if errors:
        print("=== Errors ===")
        for e in errors:
            print(e)
        print()
        print("❌ FAIL: errors detected.")
        # 실패를 종료 코드로 반영하고 싶으면 아래 주석 해제
        # raise SystemExit(1)
    else:
        if warnings:
            print("✅ PASS (with warnings): 치명 오류는 없지만 경고가 있습니다.")
        else:
            print("✅ PASS: 모든 검증을 통과했습니다.")


if __name__ == "__main__":
    main()
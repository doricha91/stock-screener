import os
import json
import sqlite3
import numpy as np
from datetime import datetime
from pathlib import Path
import market_analyzer as m


import pandas as pd
import config

# -----------------------------
# DB path resolver (이미 있던 로직 유지/정리)
# -----------------------------

def _project_root() -> Path:
    here = Path(__file__).resolve()
    for p in [here.parent, *here.parents]:
        if (p / "config.py").exists() or (p / ".git").exists():
            return p
    return here.parent

ROOT = _project_root()

def _resolve_market_db() -> Path:
    # 1) 환경변수로 강제 지정 가능
    env = os.getenv("STOCK_SCREENER_MARKET_DB")
    if env:
        return Path(env).expanduser()

    # 2) 후보들: outputs 우선
    candidates = [
        ROOT / "outputs" / "market_data.db",
        ROOT / "data" / "market_data.db",
        ROOT / "market_data.db",
    ]
    for p in candidates:
        if p.exists():
            return p

    raise FileNotFoundError(
        "market_data.db not found. Put it in one of: "
        f"{(ROOT/'outputs')}, {(ROOT/'data')} or set env STOCK_SCREENER_MARKET_DB"
    )

DB_PATH = str(_resolve_market_db())

def get_db_connection():
    return sqlite3.connect(DB_PATH)


# -----------------------------
# Helpers
# -----------------------------

def _coerce_date(target_date: str | None, conn: sqlite3.Connection) -> str:
    """target_date가 없으면 DB에서 가장 최신 daily_indicators 날짜로 고정."""
    cur = conn.cursor()
    if target_date:
        cur.execute("SELECT MAX(date) FROM daily_indicators WHERE date <= ?", (target_date,))
    else:
        cur.execute("SELECT MAX(date) FROM daily_indicators")
    d = cur.fetchone()[0]
    if not d:
        raise ValueError("No dates found in daily_indicators. Run data_processor first.")
    return d

def _get_market_series(conn: sqlite3.Connection, symbol: str, end_date: str | None) -> pd.Series:
    params = []
    date_cond = ""
    if end_date:
        date_cond = "AND date <= ?"
        params.append(end_date)

    q = f"""
        SELECT date, close
        FROM market_index
        WHERE symbol = ? {date_cond}
        ORDER BY date ASC
    """
    df = pd.read_sql(q, conn, params=[symbol, *params])
    if df.empty:
        return pd.Series(dtype="float64")
    df["date"] = pd.to_datetime(df["date"])
    df["close"] = pd.to_numeric(df["close"])
    df = df.set_index("date")
    return df["close"]

def _pct_change(a: float, b: float) -> float:
    # b가 전일 close, a가 당일 close
    if b == 0 or pd.isna(b) or pd.isna(a):
        return 0.0
    return (a / b - 1.0) * 100.0

def _to_jsonable(obj):
    """numpy scalar / pandas scalar 등을 json.dumps 가능한 기본 타입으로 변환."""
    # numpy scalar (np.bool_, np.int64, np.float64 등)
    if isinstance(obj, np.generic):
        return obj.item()
    # pandas Timestamp 등 datetime 계열
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    return obj

def _sanitize_payload(x):
    """dict/list 중첩 구조를 재귀적으로 JSON 직렬화 가능한 타입으로 정규화."""
    if isinstance(x, dict):
        return {str(k): _sanitize_payload(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_sanitize_payload(v) for v in x]
    return _to_jsonable(x)


# -----------------------------
# Existing breadth calc (원형 유지, threshold는 config로 사용)
# -----------------------------

def calculate_breadth(conn, target_date=None, universe="NASDAQ100") -> float:
    cursor = conn.cursor()

    # 1) 기준일 확정
    if target_date:
        cursor.execute("SELECT MAX(date) FROM daily_indicators WHERE date <= ?", (target_date,))
    else:
        cursor.execute("SELECT MAX(date) FROM daily_indicators")
    calc_date = cursor.fetchone()[0]
    # ⚠️ 경고: target_date로 요청했는데 daily_indicators가 누락되어
    # 실제 계산이 더 과거 날짜(calc_date)로 밀리는 경우를 감지 (3일이상)
    if target_date and calc_date != target_date:
        td = pd.to_datetime(target_date)
        cd = pd.to_datetime(calc_date)
        gap_days = (td - cd).days
        if gap_days >= 3:
            print(
                f"⚠️ [Breadth] target_date={target_date} but calc_date={calc_date} "
                f"(gap={gap_days} days)."
            )
    if not calc_date:
        return 50.0

    # 2) 종목군 필터
    if universe == "ALL":
        ticker_condition = ""
    else:
        ticker_condition = f"AND p.symbol IN (SELECT symbol FROM tickers WHERE listing_board = '{universe}')"

    # 3) 비율 계산
    try:
        query = f"""
            SELECT
                COUNT(CASE WHEN p.close > i.sma_200 THEN 1 END) AS bull_count,
                COUNT(*) AS total_count
            FROM daily_price p
            JOIN daily_indicators i
              ON p.symbol = i.symbol AND p.date = i.date
            WHERE p.date = ?
            {ticker_condition}
        """
        cursor.execute(query, (calc_date,))
        bull_count, total_count = cursor.fetchone()
        bull_count = bull_count or 0
        total_count = total_count or 0
        if total_count == 0:
            return 50.0
        return (bull_count / total_count) * 100.0
    except Exception as e:
        print(f"⚠️ Breadth 계산 실패: {e}")
        return 50.0


# -----------------------------
# Option B: triggers + regime + trade gate
# -----------------------------
def _trigger_ma_cross_bearish(conn: sqlite3.Connection, date_str: str) -> bool:
    """
    MA Crossover 트리거 (bearish 여부)

    ✅ 현재 정책: SPY만 사용 (단순/안정)
    - fast_ma(SPY) < slow_ma(SPY) 이면 bearish=True

    🔧 추후 확장(필요 시):
    - SPY + QQQ AND: 두 자산 모두 fast < slow 일 때만 True
    - SPY + QQQ OR : 둘 중 하나라도 fast < slow 이면 True

    구현 팁:
    - 아래 TODO 블록의 주석을 풀고, mode를 config로 받아도 됨.
    """
    if not getattr(config, "USE_MA_CROSS", False):
        return False

    spy = _get_market_series(conn, "SPY", date_str)
    if len(spy) < int(config.MA_CROSS_SLOW):
        return False

    spy_fast = spy.rolling(int(config.MA_CROSS_FAST)).mean().iloc[-1]
    spy_slow = spy.rolling(int(config.MA_CROSS_SLOW)).mean().iloc[-1]
    spy_bear = bool(spy_fast < spy_slow)

    # ------------------------------------------------------------------
    # TODO (미래 확장): QQQ까지 포함하고 싶다면 아래를 사용하세요.
    #
    # qqq = _get_market_series(conn, "QQQ", date_str)
    # if len(qqq) < int(config.MA_CROSS_SLOW):
    #     # QQQ 데이터가 없거나 부족하면 보수적으로 False 또는 spy_bear만 사용 중 선택
    #     return spy_bear
    #
    # qqq_fast = qqq.rolling(int(config.MA_CROSS_FAST)).mean().iloc[-1]
    # qqq_slow = qqq.rolling(int(config.MA_CROSS_SLOW)).mean().iloc[-1]
    # qqq_bear = bool(qqq_fast < qqq_slow)
    #
    # # (1) AND 조건: 둘 다 bearish일 때만 방어
    # return spy_bear and qqq_bear
    #
    # # (2) OR 조건: 하나라도 bearish면 방어(더 민감/오탐 가능 ↑)
    # return spy_bear or qqq_bear
    # ------------------------------------------------------------------

    return spy_bear

def _trigger_circuit_breaker(conn, date_str: str) -> dict:
    """
    옵션 B: 레짐(regime)에는 포함하지 않고 trade gate(trade_halted)로만 사용
    반환: {"cb_trigger": bool, "cb_halt": bool}
    확장 포인트: 쿨다운을 “달력일” 대신 “거래일 N일”로 바꾸기.
    """
    if not getattr(config, "USE_CIRCUIT_BREAKER", False):
        return {"cb_trigger": False, "cb_halt": False}

    spy = _get_market_series(conn, "SPY", date_str)
    if len(spy) < 2:
        return {"cb_trigger": False, "cb_halt": False}

    # 전일 대비 수익률(%)
    ret_pct = (spy.iloc[-1] / spy.iloc[-2] - 1.0) * 100.0
    cb_trigger = bool(ret_pct <= float(config.CB_DROP_THRESHOLD))

    # 쿨다운: 최근 N일 내 trigger가 있었으면 halt
    # (거래일 기반 쿨다운이 더 정확하지만, 현재는 간단/안전한 방식 유지)
    lookback = max(int(config.CB_COOLDOWN_DAYS) + 5, 10)
    tail = spy.tail(lookback)
    rets = tail.pct_change() * 100.0
    triggered_dates = rets[rets <= float(config.CB_DROP_THRESHOLD)].index

    if len(triggered_dates) == 0:
        cb_halt = cb_trigger
    else:
        last_trigger_date = triggered_dates[-1].date()
        today = spy.index[-1].date()
        days_since = (today - last_trigger_date).days
        cb_halt = bool(days_since < int(config.CB_COOLDOWN_DAYS))

    return {"cb_trigger": cb_trigger, "cb_halt": cb_halt}

def _trigger_breadth_low(conn, date_str: str) -> bool:
    """
    확장 포인트: universe를 NASDAQ100 외로 변경(예: ALL, S&P500 proxy 등)
    """
    if not getattr(config, "USE_MARKET_BREADTH", False):
        return False

    # 기존 calculate_breadth(conn, target_date, universe=...) 재사용
    breadth = calculate_breadth(conn, target_date=date_str, universe="NASDAQ100")
    return bool(breadth < float(config.BREADTH_THRESHOLD))

def _trigger_drawdown(conn, date_str: str) -> bool:
    """
    확장 포인트: SPY 대신 “SPY/QQQ 중 더 나쁜 쪽” 사용 등
    """
    if not getattr(config, "USE_DRAWDOWN_TRIGGER", False):
        return False

    spy = _get_market_series(conn, "SPY", date_str)
    lookback = int(config.DD_LOOKBACK)

    if len(spy) < lookback:
        return False

    window = spy.tail(lookback)
    rolling_max = window.max()
    dd_pct = (window.iloc[-1] / rolling_max - 1.0) * 100.0  # (%)

    return bool(dd_pct <= float(config.DD_THRESHOLD))

def _trigger_vix_breakout(conn, date_str: str) -> bool:
    """
    확장 포인트: 절대 임계값(예: VIX>=30)과 병행, 혹은 둘 중 하나만
    """
    if not getattr(config, "USE_VIX_BREAKOUT", False):
        return False

    vix = _get_market_series(conn, "^VIX", date_str)
    ma_period = int(config.VIX_MA_PERIOD)

    if len(vix) < ma_period:
        return False

    vix_ma = vix.rolling(ma_period).mean().iloc[-1]
    return bool(vix.iloc[-1] >= (vix_ma * float(config.VIX_MULTIPLIER)))

def _compute_trend_flags(conn, date_str: str) -> dict:
    """
    trend_bull / trend_bear 플래그만 계산해서 반환.
    (현재 레짐 룰과의 결합은 _decide_regime에서 처리)
    """
    spy = _get_market_series(conn, "SPY", date_str)
    qqq = _get_market_series(conn, "QQQ", date_str)

    p = int(getattr(config, "REGIME_SMA_PERIOD", 200))

    if len(spy) < p or len(qqq) < p:
        return {"trend_bull": False, "trend_bear": False}

    spy_ma = spy.rolling(p).mean().iloc[-1]
    qqq_ma = qqq.rolling(p).mean().iloc[-1]

    trend_bull = bool((spy.iloc[-1] > spy_ma) and (qqq.iloc[-1] > qqq_ma))
    trend_bear = bool((spy.iloc[-1] < spy_ma) and (qqq.iloc[-1] < qqq_ma))

    return {"trend_bull": trend_bull, "trend_bear": trend_bear}

def _compute_triggers(conn, date_str: str) -> dict:
    # 1) trend
    trend = _compute_trend_flags(conn, date_str)

    # 2) safety triggers
    cb = _trigger_circuit_breaker(conn, date_str)
    ma_cross_bearish = _trigger_ma_cross_bearish(conn, date_str)
    breadth_low = _trigger_breadth_low(conn, date_str)
    drawdown = _trigger_drawdown(conn, date_str)
    vix_breakout = _trigger_vix_breakout(conn, date_str)

    return {
        # trade gate related (옵션 B)
        "circuit_breaker_trigger": cb["cb_trigger"],
        "circuit_breaker_halt": cb["cb_halt"],

        # regime signals
        "ma_cross_bearish": ma_cross_bearish,
        "breadth_low": breadth_low,
        "drawdown": drawdown,
        "vix_breakout": vix_breakout,

        # trend flags
        "trend_bull": trend["trend_bull"],
        "trend_bear": trend["trend_bear"],
    }

def _decide_regime(triggers: dict) -> str:
    # 1) PANIC: 공포 시그널(상대 VIX 돌파 or 드로우다운)
    if triggers.get("vix_breakout") or triggers.get("drawdown"):
        return "PANIC"

    # 2) BEAR: 추세 하락(둘 다 200MA 아래)
    if triggers.get("trend_bear"):
        return "BEAR"

    # 3) UNSTABLE: breadth/ma_cross 경고
    if triggers.get("breadth_low") or triggers.get("ma_cross_bearish"):
        return "UNSTABLE"

    # 4) BULL: 추세 상승
    if triggers.get("trend_bull"):
        return "BULL"

    return "UNSTABLE"

def _upsert_market_status_log(conn: sqlite3.Connection, date_str: str, status: str, vix_value: float, payload: dict):
    """
    새 스키마(outputs/market_data.db):
      date UNIQUE
      status, vix_value
      trade_halted + 각 trigger 컬럼들
      description(JSON 원문) + created_at
    """
    # payload 정규화(이미 넣어두신 sanitize 함수 사용)
    payload = _sanitize_payload(payload)

    triggers = payload.get("triggers", {}) or {}
    trade_halted = int(bool(payload.get("trade_halted", False)))

    cb_trigger = int(bool(triggers.get("circuit_breaker_trigger", False)))
    cb_halt = int(bool(triggers.get("circuit_breaker_halt", False)))
    ma_cross_bearish = int(bool(triggers.get("ma_cross_bearish", False)))
    breadth_low = int(bool(triggers.get("breadth_low", False)))
    drawdown = int(bool(triggers.get("drawdown", False)))
    vix_breakout = int(bool(triggers.get("vix_breakout", False)))
    trend_bull = int(bool(triggers.get("trend_bull", False)))
    trend_bear = int(bool(triggers.get("trend_bear", False)))

    desc = json.dumps(payload, ensure_ascii=False)

    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR REPLACE INTO market_status_log
        (date, status, vix_value, trade_halted,
         cb_trigger, cb_halt, ma_cross_bearish, breadth_low, drawdown, vix_breakout, trend_bull, trend_bear,
         description, created_at)
        VALUES
        (?, ?, ?, ?,
         ?, ?, ?, ?, ?, ?, ?, ?,
         ?, datetime('now'))
        """,
        (
            date_str, status, float(vix_value), trade_halted,
            cb_trigger, cb_halt, ma_cross_bearish, breadth_low, drawdown, vix_breakout, trend_bull, trend_bear,
            desc,
        ),
    )
    conn.commit()


def get_market_state(target_date: str | None = None, write_log: bool = True) -> dict:
    """
    옵션 B의 단일 진입점:
      - triggers 계산
      - regime 결정
      - trade_halted 결정 (서킷브레이커 쿨다운)
      - market_status_log에 upsert
    """
    conn = get_db_connection()
    try:
        date_str = _coerce_date(target_date, conn)

        vix_series = _get_market_series(conn, "^VIX", date_str)
        vix_value = float(vix_series.iloc[-1]) if len(vix_series) > 0 else 0.0

        triggers = _compute_triggers(conn, date_str)
        regime = _decide_regime(triggers)
        trade_halted = bool(triggers.get("circuit_breaker_halt", False))  # 옵션 B 핵심

        plan = config.REGIME_RULES.get(regime, config.REGIME_RULES["UNSTABLE"])

        payload = {
            "date": date_str,
            "regime": regime,
            "trade_halted": trade_halted,
            "triggers": triggers,
            "db_path": DB_PATH,
        }
        if write_log:
            _upsert_market_status_log(conn, date_str, regime, vix_value, payload)

        return {
            "date": date_str,
            "regime": regime,
            "plan": plan,
            "vix_value": vix_value,
            "trade_halted": trade_halted,
            "triggers": triggers,
        }
    finally:
        conn.close()


# -----------------------------
# Backward compatibility
# -----------------------------

def get_market_regime(target_date=None):
    """
    기존 코드와 호환:
      return (regime, plan)
    """
    s = get_market_state(target_date, write_log=True)
    return s["regime"], s["plan"]


if __name__ == "__main__":
    s = get_market_state()
    print("\n[The Brain 최종 진단]")
    print(f"date: {s['date']}")
    print(f"regime: {s['regime']}")
    print(f"trade_halted (circuit breaker): {s['trade_halted']}")
    print(f"vix: {s['vix_value']}")
    print(f"triggers: {s['triggers']}")
    print(m.get_market_state("2025-04-01"))
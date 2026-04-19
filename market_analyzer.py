import os
import json
import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
import config

# -------------------------------------------------------------
# [안전화] DB 경로 및 연결 로직
# 메인 로직에서는 테이블을 삭제(DROP)하거나 생성(CREATE)하지 않습니다.
# 초기화가 필요하다면 'scripts/setup_db.py'를 대신 실행하세요.
# -------------------------------------------------------------

def _project_root() -> Path:
    """프로젝트의 최상위 경로(Root)를 찾습니다."""
    here = Path(__file__).resolve()
    for p in [here.parent, *here.parents]:
        if (p / "config.py").exists() or (p / ".git").exists():
            return p
    return here.parent

ROOT = _project_root()

def _resolve_market_db() -> Path:
    """market_data.db 파일의 실제 위치를 찾아 반환합니다."""
    env = os.getenv("STOCK_SCREENER_MARKET_DB")
    if env:
        return Path(env).expanduser()

    candidates = [
        ROOT / "outputs" / "market_data.db",
        ROOT / "data" / "market_data.db",
        ROOT / "market_data.db",
    ]
    for p in candidates:
        if p.exists():
            return p

    raise FileNotFoundError("market_data.db를 찾을 수 없습니다. 경로 설정을 확인하세요.")

DB_PATH = str(_resolve_market_db())

def get_db_connection():
    """시스템 전체에서 데이터베이스 연결 시 사용하는 공용 함수입니다."""
    return sqlite3.connect(DB_PATH)


# -------------------------------------------------------------
# Helpers (정규화 및 유틸리티)
# -------------------------------------------------------------

def _coerce_date(target_date: str | None, conn: sqlite3.Connection) -> str:
    """조회할 날짜가 지정되지 않았다면 DB 내 가장 최신 데이터 날짜를 반환합니다."""
    cur = conn.cursor()
    if target_date:
        cur.execute("SELECT MAX(date) FROM daily_indicators WHERE date <= ?", (target_date,))
    else:
        cur.execute("SELECT MAX(date) FROM daily_indicators")
    d = cur.fetchone()[0]
    if not d:
        raise ValueError("daily_indicators 테이블에 데이터가 없습니다. data_processor를 먼저 실행하세요.")
    return d

def _get_market_series(conn: sqlite3.Connection, symbol: str, end_date: str | None) -> pd.Series:
    """특정 지수(SPY, QQQ, VIX 등)의 종가 시계열 데이터를 가져옵니다."""
    params = [symbol]
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
    df = pd.read_sql(q, conn, params=params)
    if df.empty:
        return pd.Series(dtype="float64")
    df["date"] = pd.to_datetime(df["date"])
    df["close"] = pd.to_numeric(df["close"])
    return df.set_index("date")["close"]

def _sanitize_payload(x):
    """JSON 저장을 위해 numpy/pandas 데이터 타입을 파이썬 기본 타입으로 변환합니다."""
    if isinstance(x, dict):
        return {str(k): _sanitize_payload(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_sanitize_payload(v) for v in x]
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, (pd.Timestamp, datetime)):
        return x.isoformat()
    return x


# -------------------------------------------------------------
# Market Analysis Triggers (트리거 판정 로직)
# -------------------------------------------------------------

def calculate_breadth(conn, target_date=None, universe="NASDAQ100") -> float:
    """이동평균선(SMA 200) 위에 있는 종목의 비율(%)을 계산하여 시장 심리를 측정합니다."""
    cursor = conn.cursor()
    calc_date = _coerce_date(target_date, conn)
    
    ticker_condition = ""
    if universe != "ALL":
        ticker_condition = f"AND p.symbol IN (SELECT symbol FROM tickers WHERE listing_board = '{universe}')"

    try:
        query = f"""
            SELECT
                COUNT(CASE WHEN p.close > i.sma_200 THEN 1 END) AS bull_count,
                COUNT(*) AS total_count
            FROM daily_price p
            JOIN daily_indicators i ON p.symbol = i.symbol AND p.date = i.date
            WHERE p.date = ?
            {ticker_condition}
        """
        cursor.execute(query, (calc_date,))
        bull_count, total_count = cursor.fetchone()
        if not total_count or total_count == 0:
            return 50.0
        return (bull_count / total_count) * 100.0
    except:
        return 50.0

def _trigger_ma_cross_bearish(conn: sqlite3.Connection, date_str: str) -> bool:
    """단기 이평선이 장기 이평선을 하향 돌파(데드크로스) 했는지 확인합니다."""
    if not getattr(config, "USE_MA_CROSS", False):
        return False

    spy = _get_market_series(conn, "SPY", date_str)
    if len(spy) < int(config.MA_CROSS_SLOW):
        return False

    spy_fast = spy.rolling(int(config.MA_CROSS_FAST)).mean().iloc[-1]
    spy_slow = spy.rolling(int(config.MA_CROSS_SLOW)).mean().iloc[-1]
    return bool(spy_fast < spy_slow)

def _trigger_circuit_breaker(conn, date_str: str) -> dict:
    """지수가 급락하거나 최근 급락 이력이 있는지 확인하여 거래 중단 여부를 결정합니다."""
    if not getattr(config, "USE_CIRCUIT_BREAKER", False):
        return {"cb_trigger": False, "cb_halt": False}

    spy = _get_market_series(conn, "SPY", date_str)
    if len(spy) < 2:
        return {"cb_trigger": False, "cb_halt": False}

    # 당일 하락폭 체크
    ret_pct = (spy.iloc[-1] / spy.iloc[-2] - 1.0) * 100.0
    cb_trigger = bool(ret_pct <= float(config.CB_DROP_THRESHOLD))

    # 최근 10일 내 급락 이력 확인 (쿨다운)
    tail = spy.tail(10)
    rets = tail.pct_change() * 100.0
    triggered = rets[rets <= float(config.CB_DROP_THRESHOLD)]
    cb_halt = cb_trigger or (not triggered.empty)

    return {"cb_trigger": cb_trigger, "cb_halt": cb_halt}

def _trigger_breadth_low(conn, date_str: str) -> bool:
    """시장 참여도가 임계치 미만으로 떨어졌는지 확인합니다."""
    if not getattr(config, "USE_MARKET_BREADTH", False):
        return False
    breadth = calculate_breadth(conn, target_date=date_str)
    return bool(breadth < float(config.BREADTH_THRESHOLD))

def _trigger_drawdown(conn, date_str: str) -> bool:
    """최근 고점 대비 낙폭이 과도한지 확인합니다."""
    if not getattr(config, "USE_DRAWDOWN_TRIGGER", False):
        return False

    spy = _get_market_series(conn, "SPY", date_str)
    lookback = int(config.DD_LOOKBACK)
    if len(spy) < lookback:
        return False

    window = spy.tail(lookback)
    dd_pct = (window.iloc[-1] / window.max() - 1.0) * 100.0
    return bool(dd_pct <= float(config.DD_THRESHOLD))

def _trigger_vix_breakout(conn, date_str: str) -> bool:
    """공포 지수(VIX)가 평균 대비 급등했는지 확인합니다."""
    if not getattr(config, "USE_VIX_BREAKOUT", False):
        return False

    vix = _get_market_series(conn, "^VIX", date_str)
    ma_period = int(config.VIX_MA_PERIOD)
    if len(vix) < ma_period:
        return False

    vix_ma = vix.rolling(ma_period).mean().iloc[-1]
    return bool(vix.iloc[-1] >= (vix_ma * float(config.VIX_MULTIPLIER)))

def _compute_trend_flags(conn, date_str: str) -> dict:
    """시장 지수가 이평선 위에 있는지(상승추세) 아래에 있는지(하락추세) 판별합니다."""
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
    """모든 트리거 지표를 계산하여 하나의 딕셔너리로 합칩니다."""
    trend = _compute_trend_flags(conn, date_str)
    cb = _trigger_circuit_breaker(conn, date_str)
    
    return {
        "circuit_breaker_trigger": cb["cb_trigger"],
        "circuit_breaker_halt": cb["cb_halt"],
        "ma_cross_bearish": _trigger_ma_cross_bearish(conn, date_str),
        "breadth_low": _trigger_breadth_low(conn, date_str),
        "drawdown": _trigger_drawdown(conn, date_str),
        "vix_breakout": _trigger_vix_breakout(conn, date_str),
        "trend_bull": trend["trend_bull"],
        "trend_bear": trend["trend_bear"],
        "breadth_val": calculate_breadth(conn, date_str) # 대시보드 출력용 수치
    }

def _decide_regime(triggers: dict) -> str:
    """계산된 트리거들을 바탕으로 최종 시장 국면(Regime)을 결정합니다."""
    if triggers.get("vix_breakout") or triggers.get("drawdown"):
        return "PANIC"
    if triggers.get("trend_bear"):
        return "BEAR"
    if triggers.get("breadth_low") or triggers.get("ma_cross_bearish"):
        return "UNSTABLE"
    if triggers.get("trend_bull"):
        return "BULL"
    return "UNSTABLE"


# -------------------------------------------------------------
# [안전화] 데이터 저장 로직 (INSERT/REPLACE 전용)
# -------------------------------------------------------------

def _upsert_market_status_log(conn: sqlite3.Connection, date_str: str, status: str, vix_value: float, payload: dict):
    """판정된 국면 정보를 DB에 안전하게 기록합니다. 테이블이 없다면 scripts/setup_db.py를 먼저 실행해야 합니다."""
    payload = _sanitize_payload(payload)
    triggers = payload.get("triggers", {}) or {}
    
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT OR REPLACE INTO market_status_log
            (date, status, vix_value, trade_halted,
             cb_trigger, cb_halt, ma_cross_bearish, breadth_low, drawdown, vix_breakout, trend_bull, trend_bear,
             triggers, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            date_str, status, float(vix_value), int(bool(payload.get("trade_halted"))),
            int(bool(triggers.get("circuit_breaker_trigger"))), int(bool(triggers.get("circuit_breaker_halt"))),
            int(bool(triggers.get("ma_cross_bearish"))), int(bool(triggers.get("breadth_low"))),
            int(bool(triggers.get("drawdown"))), int(bool(triggers.get("vix_breakout"))),
            int(bool(triggers.get("trend_bull"))), int(bool(triggers.get("trend_bear"))),
            json.dumps(triggers, ensure_ascii=False), payload.get("description"),
        ))
        conn.commit()
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            print("\n❌ 오류: market_status_log 테이블이 없습니다. 'scripts/setup_db.py'를 먼저 실행해 주세요.")
        else:
            raise e

def get_market_state(target_date: str | None = None, write_log: bool = True) -> dict:
    """메인 시스템(Backtest, Screener 등)에서 시장 상태를 확인할 때 사용하는 유일한 진입점입니다."""
    conn = get_db_connection()
    try:
        date_str = _coerce_date(target_date, conn)
        vix_series = _get_market_series(conn, "^VIX", date_str)
        vix_val = float(vix_series.iloc[-1]) if not vix_series.empty else 0.0

        triggers = _compute_triggers(conn, date_str)
        regime = _decide_regime(triggers)
        trade_halted = bool(triggers.get("circuit_breaker_halt", False))
        plan = config.REGIME_RULES.get(regime, config.REGIME_RULES["UNSTABLE"])

        payload = {
            "date": date_str, "regime": regime, "trade_halted": trade_halted,
            "triggers": triggers, "description": plan.get('description'), "db_path": DB_PATH
        }
        
        if write_log:
            _upsert_market_status_log(conn, date_str, regime, vix_val, payload)

        return {
            "date": date_str, "regime": regime, "plan": plan, 
            "vix_value": vix_val, "trade_halted": trade_halted, "triggers": triggers
        }
    finally:
        conn.close()

def get_market_regime(target_date=None):
    """기존 코드와 호환성을 유지하기 위한 함수입니다."""
    s = get_market_state(target_date, write_log=True)
    return s["regime"], s["plan"]

if __name__ == "__main__":
    # 파일 단독 실행 시 현재 시장 상태를 출력해 봅니다.
    try:
        print("\n[The Brain 시장 국면 진단 결과]")
        state = get_market_state()
        print(f" - 기준일자: {state['date']}")
        print(f" - 현재국면: {state['regime']}")
        print(f" - 매매차단: {'🚨 차단됨' if state['trade_halted'] else '✅ 정상'}")
        print(f" - VIX지수: {state['vix_value']:.2f}")
    except Exception as e:
        print(f"오류: {e}")

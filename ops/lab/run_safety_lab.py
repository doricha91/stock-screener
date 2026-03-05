from __future__ import annotations

"""
ops/lab/run_safety_lab.py

목표
- 안전장치(4개) ON/OFF 조합(총 16개)을 동일한 전략 파라미터로 비교
- "신호 데이터(지표/매수·매도 신호)는 1번만 생성"하고, 조합별로는
  "레짐/게이트만 매일 재계산"하면서 백테스트 daily loop만 재실행
- 결과는 SQLite DB(outputs/safety_lab_results.db)의 safety_lab_runs 테이블에 저장

핵심 속도 개선 포인트
1) prepare_market_data(base_config)를 딱 1번 실행해서 market_data/date_list를 만든다.
2) 조합별 실험에서는 run_backtest_with_prepared_data(...)만 호출한다.
3) 랩 실행 중 market_status_log 기록은 끈다(write_market_log=False).
   - 이유: date UNIQUE라 조합별 로그가 서로 덮어씀
   - 또한 대량 upsert로 속도 저하 가능
"""

import itertools
import json
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Iterable, Optional

# -----------------------------------------------------------------------------
# Repo root 세팅
# - ops/lab/file.py -> repo root를 sys.path에 넣어, 어디서 실행해도 import가 깨지지 않게 함
# -----------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# -----------------------------------------------------------------------------
# 전역 config 패치용
# - market_analyzer가 "import config"로 전역 모듈 값을 참조하므로,
#   조합마다 config 모듈 변수(USE_*)를 런타임에 바꿔끼운다.
# -----------------------------------------------------------------------------
import config as global_config

# -----------------------------------------------------------------------------
# 백테스트 엔진
# - prepare_market_data: 지표 계산/신호 생성/병렬 처리 포함(무거움) -> 1회만 실행
# - run_backtest_with_prepared_data: daily loop만 수행(상대적으로 가벼움)
# -----------------------------------------------------------------------------
from core.backtest_engine import prepare_market_data, run_backtest_with_prepared_data


# -----------------------------------------------------------------------------
# 1) 실험 기간 (원하면 여기만 바꿔서 재실험)
# -----------------------------------------------------------------------------
START_DATE = "2020-01-01"
END_DATE = "2025-12-31"

# -----------------------------------------------------------------------------
# 2) 결과 저장 DB 경로
# -----------------------------------------------------------------------------
RESULT_DB_PATH = ROOT / "outputs" / "safety_lab_results.db"
RESULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# -----------------------------------------------------------------------------
# 3) 전략 파라미터(고정 베이스라인)
# - 안전장치만 바꿔서 비교하기 위해, 전략/자금/포지션 관련 값은 고정한다.
# - 주의: 실제 백테스트에서 쓰는 값과 맞춰야 비교가 의미가 있다.
# -----------------------------------------------------------------------------
BASE_CONFIG: Dict[str, Any] = {
    # (필수) 백테스트 기간
    "start_date": START_DATE,
    "end_date": END_DATE,

    # (필수) 자본/포지션 제한
    "initial_capital": 200_000,
    "max_positions": 10,

    # 시장 레짐 사용 여부 (레짐/게이트 재계산은 항상 켜둠)
    "use_market_regime": True,

    # ensemble 신호 관련(프로젝트에서 사용하는 키)
    "score_threshold": 1.5,
    "rs_lookback": 30,

    # 전략 가중치(예시) - indicator/strategy 쪽에서 context.get(...)로 참조하는 키들
    "turtle_weight": 1.0,
    "rs_weight": 3.0,
    "rsi_weight": 1.0,
    "sma_weight": 1.0,
    "bbands_weight": 1.0,
    "macd_weight": 1.0,
    "bbs_weight": 1.0,
    "dema_weight": 1.0,
    "obv_weight": 0.5,
    "mfi_weight": 0.5,
    "vol_spike_weight": 0.5,

    # (선택) 특정 티커 바스켓 고정
    # "target_tickers": ["AAPL", "MSFT", ...],
}

# -----------------------------------------------------------------------------
# 4) 안전장치 조합(변수)
# - 4개 토글 -> 2^4 = 16 조합
# - Circuit Breaker는 gate 성격이라 이번 랩에서는 고정 ON 권장(해석이 쉬움)
# -----------------------------------------------------------------------------
SAFETY_TOGGLES = [
    ("USE_MA_CROSS", True, False),
    ("USE_MARKET_BREADTH", True, False),
    ("USE_DRAWDOWN_TRIGGER", True, False),
    ("USE_VIX_BREAKOUT", True, False),
]

# CB는 고정 (원하면 SAFETY_TOGGLES에 넣어 32조합으로 확장 가능)
FIXED_GLOBALS = {
    "USE_CIRCUIT_BREAKER": True
}


@contextmanager
def patch_global_config(overrides: Dict[str, Any]):
    """
    config 모듈 전역 변수를 임시로 변경했다가, 실험 1회가 끝나면 원복.

    왜 필요?
    - market_analyzer.py가 'import config'로 전역값(USE_*, THRESHOLD 등)을 읽음
    - 조합별로 안전장치 ON/OFF를 바꿔야 하므로 config 모듈 값을 런타임에 바꿔야 함

    주의:
    - 전역 상태를 바꾸는 방식이므로 병렬 실행(멀티프로세싱/멀티스레드)에는 위험.
      지금은 순차 실행이라 안전.
    """
    old = {}
    try:
        for k, v in overrides.items():
            old[k] = getattr(global_config, k, None)
            setattr(global_config, k, v)
        yield
    finally:
        for k, prev in old.items():
            setattr(global_config, k, prev)


def init_db(conn: sqlite3.Connection):
    """
    결과 테이블 생성(없으면 생성)
    - 조합별 결과를 한 줄씩 저장
    - base_config_json: 어떤 고정 파라미터로 돌렸는지 재현 가능하게 저장
    """
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS safety_lab_runs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created_at TEXT NOT NULL,
      start_date TEXT NOT NULL,
      end_date TEXT NOT NULL,

      use_circuit_breaker INTEGER NOT NULL,
      use_ma_cross INTEGER NOT NULL,
      use_market_breadth INTEGER NOT NULL,
      use_drawdown_trigger INTEGER NOT NULL,
      use_vix_breakout INTEGER NOT NULL,

      status TEXT NOT NULL,          -- OK / ERROR
      error_message TEXT,            -- 실패 시

      total_return REAL,
      cagr REAL,
      mdd REAL,
      sharpe REAL,
      sortino REAL,
      calmar REAL,
      final_equity REAL,
      total_trades INTEGER,
      win_rate REAL,
      profit_factor REAL,

      base_config_json TEXT NOT NULL
    )
    """)
    conn.commit()


def insert_run(
    conn: sqlite3.Connection,
    flags: Dict[str, bool],
    status: str,
    base_config: Dict[str, Any],
    metrics: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
):
    """
    조합 1회 실행 결과를 DB에 저장
    - metrics는 backtest_engine이 반환하는 dict를 그대로 매핑
    """
    cur = conn.cursor()
    m = metrics or {}

    cur.execute("""
    INSERT INTO safety_lab_runs (
      created_at, start_date, end_date,
      use_circuit_breaker, use_ma_cross, use_market_breadth, use_drawdown_trigger, use_vix_breakout,
      status, error_message,
      total_return, cagr, mdd, sharpe, sortino, calmar, final_equity, total_trades, win_rate, profit_factor,
      base_config_json
    ) VALUES (
      ?, ?, ?,
      ?, ?, ?, ?, ?,
      ?, ?,
      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
      ?
    )
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        base_config["start_date"], base_config["end_date"],

        int(flags["USE_CIRCUIT_BREAKER"]),
        int(flags["USE_MA_CROSS"]),
        int(flags["USE_MARKET_BREADTH"]),
        int(flags["USE_DRAWDOWN_TRIGGER"]),
        int(flags["USE_VIX_BREAKOUT"]),

        status,
        error_message,

        m.get("return"),
        m.get("cagr"),
        m.get("mdd"),
        m.get("sharpe"),
        m.get("sortino"),
        m.get("calmar"),
        m.get("final_equity"),
        m.get("total_trades"),
        m.get("win_rate"),
        m.get("profit_factor"),

        json.dumps(base_config, ensure_ascii=False),
    ))
    conn.commit()


def iter_flag_combos() -> Iterable[Dict[str, bool]]:
    """
    SAFETY_TOGGLES에서 16개 조합 생성
    - 각 조합은 {"USE_MA_CROSS": True/False, ...} 형태
    - FIXED_GLOBALS(CB 고정 ON)도 합쳐서 반환
    """
    keys = [k for (k, _, _) in SAFETY_TOGGLES]
    values_product = itertools.product(*[(a, b) for (_, a, b) in SAFETY_TOGGLES])
    for combo in values_product:
        flags = {k: bool(v) for k, v in zip(keys, combo)}
        flags.update({k: bool(v) for k, v in FIXED_GLOBALS.items()})
        yield flags


def main():
    # 베이스라인 config 복사 + 기간 확정
    base_config = dict(BASE_CONFIG)
    base_config["start_date"] = START_DATE
    base_config["end_date"] = END_DATE

    # -------------------------------------------------------------------------
    # ✅ 핵심: 준비 데이터(신호 포함)는 1회만 생성해서 재사용
    # -------------------------------------------------------------------------
    print("⏳ Preparing market_data ONCE (this is the expensive step)...")
    market_data, date_list = prepare_market_data(base_config)
    if not market_data:
        raise RuntimeError("prepare_market_data returned empty market_data")

    # 결과 DB 준비
    conn = sqlite3.connect(str(RESULT_DB_PATH))
    init_db(conn)

    combos = list(iter_flag_combos())
    print(f"Result DB: {RESULT_DB_PATH}")
    print(f"Period: {START_DATE} ~ {END_DATE}")
    print(f"Combos: {len(combos)} (CB fixed={FIXED_GLOBALS.get('USE_CIRCUIT_BREAKER', None)})")

    # -------------------------------------------------------------------------
    # 조합별 실험 실행
    # - 조합마다 config.py의 USE_*만 패치
    # - 신호 데이터는 그대로 두고, 레짐/게이트만 매일 재계산
    # - 랩에서는 market_status_log 기록을 끔(write_market_log=False)
    # -------------------------------------------------------------------------
    for i, flags in enumerate(combos, start=1):
        print(f"[{i}/{len(combos)}] flags={flags}")

        try:
            with patch_global_config(flags):
                metrics = run_backtest_with_prepared_data(
                    base_config,
                    market_data,
                    date_list,
                    verbose=False,
                    prev_trade_halted=None,
                    write_market_log=False,  # ✅ 랩에서는 기록 끔(속도/로그 덮어쓰기 문제 방지)
                )

                if metrics is None:
                    insert_run(
                        conn,
                        flags,
                        status="ERROR",
                        base_config=base_config,
                        metrics=None,
                        error_message="run_backtest_with_prepared_data returned None",
                    )
                else:
                    insert_run(conn, flags, status="OK", base_config=base_config, metrics=metrics)

        except Exception as e:
            insert_run(conn, flags, status="ERROR", base_config=base_config, metrics=None, error_message=str(e))

    conn.close()
    print("✅ Lab finished.")


if __name__ == "__main__":
    main()
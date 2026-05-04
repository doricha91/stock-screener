# scripts/run_front_test.py
import json
import sqlite3
import sys
from pathlib import Path

# 프로젝트 루트 추가
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config
from core.daily_plan_generator import generate_daily_plan
from core.preflight_check import run_preflight_checks


def _configure_console_encoding() -> None:
    """Best-effort UTF-8 console setup for Windows terminals."""
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def display_market_dashboard():
    """
    [MFU4 Step 3] 실전 상황 대시보드를 콘솔에 출력합니다.
    최근 시장 국면 변화와 현재 정책의 근거를 한눈에 보여줍니다.
    """
    print("\n" + "=" * 60)
    print(" [MARKET STATUS DASHBOARD]")
    print("=" * 60)

    try:
        from core.paths import market_db_path

        conn = sqlite3.connect(market_db_path())
        cur = conn.cursor()
        cur.execute(
            """
            SELECT date, status, vix_value, trade_halted, triggers
            FROM market_status_log
            ORDER BY date DESC LIMIT 10
            """
        )
        rows = cur.fetchall()
        conn.close()

        if not rows:
            print(" No recent market regime history found. (DB Empty)")
            return

        latest = rows[0]
        history = [r[1] for r in reversed(rows)]
        transition_str = " -> ".join(history[-5:])

        status = latest[1]
        vix = latest[2]
        halted = "HALTED" if latest[3] else "NORMAL"
        triggers = json.loads(latest[4]) if latest[4] else {}

        print(f" Current Date  : {latest[0]}")
        print(f" Current Regime: [{status}] ({halted})")
        print(f" Recent Flow   : {transition_str}")
        print("-" * 60)

        print(" [Critical Triggers]")
        print(f"  - VIX Index    : {vix:.2f} (Avg: {triggers.get('vix_ma', 0):.2f})")
        print(
            f"  - Market Breadth: {triggers.get('breadth_val', 0):.1f}% "
            f"(Threshold: {config.BREADTH_THRESHOLD}%)"
        )
        print(
            f"  - Trend Status : BULL={triggers.get('trend_bull')}, "
            f"BEAR={triggers.get('trend_bear')}"
        )
        print("-" * 60)

        rule = config.REGIME_RULES.get(status, {})
        print(" [Action Policy]")
        print(f"  - Target Cash Ratio : {rule.get('target_cash_ratio', 0) * 100:.0f}%")
        print(
            f"  - Stop-Loss Tightness: "
            f"{rule.get('trailing_stop_multiplier', 0):.2f}x (ATR)"
        )
        print(
            f"  - Strategy Weights   : "
            f"Turtle({rule.get('weights', {}).get('turtle', 0)}), "
            f"RSI({rule.get('weights', {}).get('rsi', 0)})"
        )
    except Exception as e:
        print(f" Dashboard render error: {e}")

    print("=" * 60 + "\n")


def main():
    _configure_console_encoding()

    print("\n" + "=" * 30)
    print(" STOCK SCREENER - FRONT-TEST PIPELINE")
    print("=" * 30)

    display_market_dashboard()

    if not run_preflight_checks():
        print("[STP] Pipeline stopped due to preflight failure.")
        sys.exit(1)

    try:
        report_path = generate_daily_plan()
        if report_path:
            print("\nDONE! Action Plan is ready at:")
            print(report_path)
        else:
            print("\nFailed to generate Action Plan.")
    except Exception as e:
        print(f"\nUnexpected error during pipeline: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import os
import sys
from contextlib import contextmanager

# 프로젝트 루트 경로를 sys.path에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config as global_config
from core.optimizer_engine import run_optimization

# 기본 설정 (CLI 인자가 없을 경우)
FAST_MODE = False

@contextmanager
def patch_global_config(overrides: dict):
    old = {}
    try:
        for k, v in overrides.items():
            old[k] = getattr(global_config, k, None)
            setattr(global_config, k, v)
        yield
    finally:
        for k, prev in old.items():
            setattr(global_config, k, prev)

def parse_args():
    parser = argparse.ArgumentParser(description="Stock Screener Optimizer")
    parser.add_argument(
        "--hedge", 
        type=str, 
        choices=["on", "off"], 
        default="on",
        help="Hedge Mode ON/OFF (default: on)"
    )
    parser.add_argument(
        "--hedge-bear-ratio",
        type=float,
        default=0.2,
        help="Hedge ratio for BEAR market (default: 0.2)"
    )
    parser.add_argument(
        "--hedge-panic-ratio",
        type=float,
        default=0.5,
        help="Hedge ratio for PANIC market (default: 0.5)"
    )
    parser.add_argument(
        "--min-mode-maintain-days",
        type=int,
        default=5,
        help="Minimum days to maintain HEDGE/LONG mode (default: 5)"
    )
    parser.add_argument(
        "--hedge-liquidation-priority",
        type=str,
        choices=["rs_low", "return_low", "weight_low", "age_high"],
        default="rs_low",
        help="Priority for selling stocks when entering hedge mode (default: rs_low)"
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Run in fast mode (limited tickers and periods)"
    )
    parser.add_argument(
        "--log",
        action="store_true",
        help="Enable detailed decision event logging (CSV)"
    )
    parser.add_argument(
        "--safety",
        type=str,
        choices=["on", "off", "config"],
        default="config",
        help="Force all Safety Mechanisms ON/OFF or use 'config' (default: config)"
    )
    parser.add_argument(
        "--regimes",
        type=str,
        help="Target regimes for optimization, separated by comma (e.g., BULL,UNSTABLE)"
    )
    parser.add_argument(
        "--filter-mode",
        type=str,
        choices=["FREEZE", "EXCLUSIVE"],
        default="FREEZE",
        help="Regime filter mode (default: FREEZE)"
    )
    return parser.parse_args()

if __name__ == "__main__":
    import datetime
    args = parse_args()
    
    # CLI 인자에 따른 설정 구성
    use_hedge = (args.hedge == "on")
    fast_mode = args.fast or FAST_MODE
    enable_log = args.log
    
    # run_id 생성 (타임스탬프 기반 고유 식별자)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    hedge_suffix = "on" if use_hedge else "off"
    run_id = f"run_{timestamp}_h{hedge_suffix}"
    if fast_mode: run_id += "_fast"

    # 국면 필터 파싱
    target_regimes = []
    if args.regimes:
        target_regimes = [r.strip().upper() for r in args.regimes.split(",")]
        run_id += f"_{'_'.join(target_regimes)}"

    # runtime_overrides 초기화
    runtime_overrides = {}
    
    # 안전장치 오버라이드 처리
    if args.safety != "config":
        is_safe = (args.safety == "on")
        safety_keys = [
            "USE_CIRCUIT_BREAKER", "USE_MA_CROSS", "USE_MARKET_BREADTH", 
            "USE_DRAWDOWN_TRIGGER", "USE_VIX_BREAKOUT"
        ]
        for key in safety_keys:
            runtime_overrides[key] = is_safe

    runtime_overrides.update({
        "run_id": run_id,
        "run_name": run_id,
        "USE_HEDGE_MODE": use_hedge,
        "HEDGE_RATIO_BEAR": args.hedge_bear_ratio,
        "HEDGE_RATIO_PANIC": args.hedge_panic_ratio,
        "MIN_MODE_MAINTAIN_DAYS": args.min_mode_maintain_days,
        "HEDGE_LIQUIDATION_PRIORITY": args.hedge_liquidation_priority,
        "enable_decision_logging": enable_log,
        "TARGET_REGIMES": target_regimes,
        "REGIME_FILTER_MODE": args.filter_mode.upper()
    })

    # 런타임 정보 출력
    hedge_status_str = "ON" if use_hedge else "OFF"
    print("\n" + "=" * 60)
    print(f"🚀 [ID: {run_id}] Optimizer 실험을 시작합니다.")
    print("=" * 60)

    print(f"🔹 핵심 설정 요약 (런타임 주입):")
    print(f"  - USE_HEDGE_MODE:      {use_hedge}")
    print(f"  - HEDGE_RATIO_BEAR:    {args.hedge_bear_ratio}")
    print(f"  - HEDGE_RATIO_PANIC:   {args.hedge_panic_ratio}")
    print(f"  - MIN_MODE_MAINTAIN_DAYS: {args.min_mode_maintain_days}")
    print(f"  - HEDGE_LIQUIDATION_PRIORITY: {args.hedge_liquidation_priority}")
    print(f"  - FAST_MODE:           {fast_mode}")
    print(f"  - 기간: {global_config.IN_SAMPLE_START} ~ {global_config.OUT_OF_SAMPLE_END}")
    print(f"  - SAFETY_MODE:         {args.safety.upper()}")
    
    if target_regimes:
        print(f"  - TARGET_REGIMES:      {target_regimes}")
        print(f"  - REGIME_FILTER_MODE:  {args.filter_mode.upper()}")

    if args.safety == "config":
        print(f"\n🔹 안전장치 상태 (config.py 상속):")
        print(f"  - USE_CIRCUIT_BREAKER: {global_config.USE_CIRCUIT_BREAKER}")
        print(f"  - USE_MA_CROSS:        {global_config.USE_MA_CROSS}")
        print(f"  - USE_MARKET_BREADTH:  {global_config.USE_MARKET_BREADTH}")
        print(f"  - USE_DRAWDOWN_TRIGGER: {global_config.USE_DRAWDOWN_TRIGGER}")
        print(f"  - USE_VIX_BREAKOUT:    {global_config.USE_VIX_BREAKOUT}")
    else:
        print(f"\n🔹 안전장치 상태 (런타임 강제 {args.safety.upper()}):")
        for key in ["USE_CIRCUIT_BREAKER", "USE_MA_CROSS", "USE_MARKET_BREADTH", "USE_DRAWDOWN_TRIGGER", "USE_VIX_BREAKOUT"]:
            print(f"  - {key}: {runtime_overrides[key]}")
            
    print("=" * 60 + "\n")

    with patch_global_config(runtime_overrides):
        run_optimization(fast_mode=fast_mode, runtime_overrides=runtime_overrides)

    print(f"\n✅ [HEDGE={hedge_status_str}] Optimizer 실험이 완료되었습니다.")

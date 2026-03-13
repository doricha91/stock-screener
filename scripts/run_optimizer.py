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

# 고정 안전장치 조합 (실험의 일관성을 위해 고정)
SAFETY_FIXED = {
    "USE_CIRCUIT_BREAKER": True,
    "USE_MA_CROSS": False,
    "USE_MARKET_BREADTH": False,
    "USE_DRAWDOWN_TRIGGER": False,
    "USE_VIX_BREAKOUT": False,
}

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
        default="off",
        help="Hedge Mode ON/OFF (default: off)"
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

    # make_config 로직과 동일하게 use_market_regime 결정
    use_market_regime = not fast_mode 
    
    runtime_overrides = SAFETY_FIXED.copy()
    runtime_overrides["run_id"] = run_id
    runtime_overrides["run_name"] = run_id # 기존 run_name 호환성 유지
    runtime_overrides["USE_HEDGE_MODE"] = use_hedge
    runtime_overrides["HEDGE_RATIO_BEAR"] = args.hedge_bear_ratio
    runtime_overrides["HEDGE_RATIO_PANIC"] = args.hedge_panic_ratio
    runtime_overrides["MIN_MODE_MAINTAIN_DAYS"] = args.min_mode_maintain_days
    runtime_overrides["HEDGE_LIQUIDATION_PRIORITY"] = args.hedge_liquidation_priority
    runtime_overrides["enable_decision_logging"] = enable_log

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

    print(f"\n🔹 고정 안전장치 (Fixed Safety):")
    for k, v in SAFETY_FIXED.items():
        print(f"  - {k}: {v}")
    print("=" * 60 + "\n")

    # [설정 전달 설계 설명]
    # 1. runtime_overrides: make_config()를 통해 백테스트 엔진(backtest_engine)에 
    #    직접 주입되는 최우선 설정값입니다. (명시적 주입 방식)
    # 2. patch_global_config: 아직 엔진 내부나 다른 모듈에서 'import config'를 통해 
    #    전역 변수를 직접 참조하는 코드들과의 호환성을 위한 '안전장치'입니다.
    # 3. 결과적으로 두 방식이 병행되어, 엔진 내부의 어떤 경로에서도 동일한 런타임 설정이 
    #    유지되도록 보장합니다.
    with patch_global_config(runtime_overrides):
        run_optimization(fast_mode=fast_mode, runtime_overrides=runtime_overrides)

    print(f"\n✅ [HEDGE={hedge_status_str}] Optimizer 실험이 완료되었습니다.")
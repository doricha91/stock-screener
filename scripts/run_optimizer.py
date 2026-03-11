from __future__ import annotations

import argparse
from contextlib import contextmanager
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
    args = parse_args()
    
    # CLI 인자에 따른 설정 구성
    use_hedge = (args.hedge == "on")
    fast_mode = args.fast or FAST_MODE
    enable_log = args.log
    
    # run_name 생성 (로그 파일명 식별용)
    run_name = f"opt_hedge_{'on' if use_hedge else 'off'}"
    if fast_mode: run_name += "_fast"

    # make_config 로직과 동일하게 use_market_regime 결정
    use_market_regime = not fast_mode 
    
    runtime_overrides = SAFETY_FIXED.copy()
    runtime_overrides["USE_HEDGE_MODE"] = use_hedge
    runtime_overrides["enable_decision_logging"] = enable_log
    runtime_overrides["run_name"] = run_name

    # 런타임 정보 출력
    hedge_status_str = "ON" if use_hedge else "OFF"
    print("\n" + "=" * 60)
    print(f"🚀 [HEDGE={hedge_status_str}] Optimizer 실험을 시작합니다.")
    print("=" * 60)

    print(f"🔹 핵심 설정 요약 (런타임 적용):")
    print(f"  - USE_HEDGE_MODE:      {use_hedge}")
    print(f"  - USE_MARKET_REGIME:   {use_market_regime}")
    print(f"  - HEDGE_RATIO_BEAR:    {getattr(global_config, 'HEDGE_RATIO_BEAR', 'N/A')}")
    print(f"  - HEDGE_RATIO_PANIC:   {getattr(global_config, 'HEDGE_RATIO_PANIC', 'N/A')}")
    print(f"  - FAST_MODE:           {fast_mode}")
    print(f"  - 학습 기간 (Train):   {global_config.IN_SAMPLE_START} ~ {global_config.IN_SAMPLE_END}")
    print(f"  - 검증 기간 (Test):    {global_config.OUT_OF_SAMPLE_START} ~ {global_config.OUT_OF_SAMPLE_END}")

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
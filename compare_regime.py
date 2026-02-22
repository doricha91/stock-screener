# compare_regime.py
import pandas as pd
from scripts.run_portfolio_backtest import run_backtest_with_config, PORTFOLIO_CONFIG
import copy


def compare_results():
    print("⚖️ [A/B Test] 시장 국면 판단 로직 도입 전후 비교\n")

    # 1. Before: 국면 판단 끄기 (Static)
    print("Waiting... [Case 1] 국면 판단 OFF (기존 전략)")
    config_before = copy.deepcopy(PORTFOLIO_CONFIG)
    config_before['use_market_regime'] = False  # 스위치 OFF

    # 2022년 하락장 포함해서 테스트 (차이가 극명하게 드러남)
    config_before['start_date'] = '2018-01-01'
    config_before['end_date'] = '2025-12-31'

    res_before = run_backtest_with_config(config_before, verbose=False)

    # 2. After: 국면 판단 켜기 (Dynamic)
    print("\nWaiting... [Case 2] 국면 판단 ON (The Brain)")
    config_after = copy.deepcopy(PORTFOLIO_CONFIG)
    config_after['use_market_regime'] = True  # 스위치 ON
    config_after['start_date'] = '2018-01-01'
    config_after['end_date'] = '2025-12-31'

    res_after = run_backtest_with_config(config_after, verbose=False)

    # 3. 결과 비교 출력
    print("\n" + "=" * 60)
    print(f"📊 [최종 비교 리포트] (기간: {config_before['start_date']} ~ {config_before['end_date']})")
    print("=" * 60)

    # 데이터프레임으로 보기 좋게 정리
    comparison = pd.DataFrame({
        'Metric': ['Total Return', 'CAGR', 'MDD (방어력)', 'Sharpe Ratio', 'Win Rate'],
        'Before (OFF)': [
            f"{res_before['return']:.2f}%",
            f"{res_before['cagr']:.2f}%",
            f"{res_before['mdd']:.2f}%",
            f"{res_before['sharpe']:.2f}",
            f"{res_before['win_rate']:.2f}%"
        ],
        'After (ON)': [
            f"{res_after['return']:.2f}%",
            f"{res_after['cagr']:.2f}%",
            f"{res_after['mdd']:.2f}%",  # 여기가 핵심
            f"{res_after['sharpe']:.2f}",
            f"{res_after['win_rate']:.2f}%"
        ]
    })

    print(comparison.to_string(index=False))
    print("=" * 60)

    # 간단한 평가
    mdd_diff = res_after['mdd'] - res_before['mdd']
    if mdd_diff > 5.0:
        print(f"✅ MDD가 {mdd_diff:.2f}%p 개선되었습니다. (방어력 상승)")
    else:
        print(f"ℹ️ MDD 변화가 크지 않습니다. ({mdd_diff:.2f}%p)")


if __name__ == "__main__":
    compare_results()
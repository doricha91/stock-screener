# scripts/benchmark_generator.py
import yfinance as yf
import pandas as pd
import numpy as np
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

"""
[AGENTS.md 준수]
범용 벤치마크 데이터 파이프라인 및 동적 비중 조절 포트폴리오 시뮬레이터.
- 월간 리밸런싱 지원
- 적립식(DCA) 및 거치식 지원
- 배당 반영 수정 종가 기준
"""

def fetch_benchmark_data(tickers=["SPY", "QQQ", "TLT", "GLD"], start_date="2000-01-01"):
    """
    주요 자산군의 월봉 수정 종가 데이터를 수집합니다.
    """
    print(f"📥 벤치마크 데이터 수집 중: {tickers} (시작일: {start_date})...")
    
    # auto_adjust=True: 배당/분할이 반영된 수정 주가를 'Close' 컬럼에 가져옴
    raw_data = yf.download(tickers, start=start_date, interval="1mo", auto_adjust=True)['Close']
    
    # 데이터 시작 시점 로깅 및 결측치 처리
    processed_cols = {}
    for ticker in tickers:
        series = raw_data[ticker].dropna()
        if not series.empty:
            print(f"   - {ticker}: {series.index[0].strftime('%Y-%m-%d')} 부터 데이터 존재")
            processed_cols[ticker] = raw_data[ticker].ffill()
        else:
            print(f"   - ⚠️ {ticker}: 데이터가 전혀 존재하지 않습니다.")
            
    data = pd.DataFrame(processed_cols)
    # 인덱스 정규화 (월말 기준으로 통일)
    data.index = data.index.to_period('M').to_timestamp('M')
    return data

def calculate_metrics(equity_series: pd.Series) -> Dict[str, Any]:
    """
    자산 흐름을 바탕으로 CAGR, MDD, 최종 자산을 계산합니다.
    """
    if equity_series.empty:
        return {"final_value": 0, "total_return": 0, "cagr": 0, "mdd": 0}

    # 최종 자산
    final_val = equity_series.iloc[-1]
    
    # CAGR (연평균 수익률)
    # 투입 원금이 계속 늘어나는 DCA 특성을 고려하여, 단순 수익률 대신 내부수수익률(IRR) 개념이 
    # 정확하나 요청하신 대로 자산 흐름 기반의 표준 CAGR 공식을 적용합니다.
    years = (equity_series.index[-1] - equity_series.index[0]).days / 365.25
    total_ret = (equity_series.iloc[-1] / equity_series.iloc[0]) - 1
    cagr = (equity_series.iloc[-1] / equity_series.iloc[0]) ** (1 / years) - 1 if years > 0 else 0
    
    # MDD (최대 낙폭)
    rolling_max = equity_series.cummax()
    drawdown = (equity_series - rolling_max) / rolling_max
    mdd = drawdown.min()
    
    return {
        "final_value": final_val,
        "total_return": total_ret * 100,
        "cagr": cagr * 100,
        "mdd": mdd * 100
    }

def simulate_custom_portfolio(price_df: pd.DataFrame, weights: Dict[str, float], 
                             start_date: str, initial_capital: float, 
                             monthly_contribution: float = 0):
    """
    [핵심] 동적 비중 조절 및 월간 리밸런싱 포트폴리오 시뮬레이터.
    """
    # 1. 대상 기간 및 자산 필터링
    subset = price_df[start_date:].copy()
    target_tickers = list(weights.keys())
    subset = subset[target_tickers].dropna(how='all')
    
    if subset.empty:
        return pd.Series()

    # 가중치 합 검증
    if abs(sum(weights.values()) - 1.0) > 1e-6:
        raise ValueError("❌ 가중치의 합은 반드시 1.0이어야 합니다.")

    equity_history = []
    # 현재 보유 중인 각 자산의 '달러 가치'
    current_values = {ticker: initial_capital * weights[ticker] for ticker in target_tickers}
    
    # 첫 번째 달 (초기 투입)
    total_val = sum(current_values.values())
    equity_history.append(total_val)
    
    # 두 번째 달부터 루프
    for i in range(1, len(subset)):
        prev_prices = subset.iloc[i-1]
        curr_prices = subset.iloc[i]
        
        # 1. 한 달간의 가격 변동 반영
        new_total_val = 0
        for ticker in target_tickers:
            # 해당 시점에 자산 데이터가 아직 없는 경우(나중에 상장 등) 대비
            if pd.isna(prev_prices[ticker]) or pd.isna(curr_prices[ticker]):
                # 가치 변동 없음
                pass
            else:
                ret = curr_prices[ticker] / prev_prices[ticker]
                current_values[ticker] *= ret
            new_total_val += current_values[ticker]
            
        # 2. 매월 말 추가 적립금 투입 및 리밸런싱
        new_total_val += monthly_contribution
        
        # 가중치에 맞춰 전량 재분배 (Monthly Rebalancing)
        for ticker in target_tickers:
            current_values[ticker] = new_total_val * weights[ticker]
            
        equity_history.append(new_total_val)
        
    return pd.Series(equity_history, index=subset.index)

def save_equity_curve(series: pd.Series, filename: str):
    """결과를 CSV로 저장"""
    output_dir = Path("outputs/benchmarks")
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{filename}.csv"
    series.to_csv(path)
    return path

def run_final_report():
    """
    최종 요구사항 테스트: 2000년 1월 시작, $10k 초기자본, $1k 월 적립식
    """
    data = fetch_benchmark_data()
    start_date = "2000-01-01"
    initial_cap = 10000.0
    monthly_add = 1000.0
    
    print(f"\n" + "="*60)
    print(f"📊 벤치마크 시뮬레이션 보고서 ({start_date} ~ 현재)")
    print(f"💰 초기자본: ${initial_cap:,.0f} | 매월적립: ${monthly_add:,.0f} (DCA)")
    print("="*60)

    # 시나리오 1: SPY 100%
    spy_100_weights = {'SPY': 1.0}
    spy_curve = simulate_custom_portfolio(data, spy_100_weights, start_date, initial_cap, monthly_add)
    spy_metrics = calculate_metrics(spy_curve)
    save_equity_curve(spy_curve, "equity_spy_100")

    # 시나리오 2: 혼합 포트폴리오 (SPY 60, TLT 30, GLD 10)
    mix_weights = {'SPY': 0.6, 'TLT': 0.3, 'GLD': 0.1}
    mix_curve = simulate_custom_portfolio(data, mix_weights, start_date, initial_cap, monthly_add)
    mix_metrics = calculate_metrics(mix_curve)
    save_equity_curve(mix_curve, "equity_mix_60_30_10")

    # 결과 출력
    print(f"\n[결과 비교]")
    print(f"{'구분':<20} | {'SPY 100%':>15} | {'SPY/TLT/GLD (60/30/10)':>20}")
    print("-" * 65)
    print(f"{'최종 자산 (Final)':<20} | ${spy_metrics['final_value']:>14,.0f} | ${mix_metrics['final_value']:>19,.0f}")
    print(f"{'연복리 수익률 (CAGR)':<20} | {spy_metrics['cagr']:>14.2f}% | {mix_metrics['cagr']:>19.2f}%")
    print(f"{'최대 낙폭 (MDD)':<20} | {spy_metrics['mdd']:>14.2f}% | {mix_metrics['mdd']:>19.2f}%")
    print("-" * 65)
    print(f"📍 상세 데이터 저장 완료: outputs/benchmarks/")

if __name__ == "__main__":
    run_final_report()

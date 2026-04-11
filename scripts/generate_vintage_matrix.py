# scripts/generate_vintage_matrix.py
import pandas as pd
import numpy as np
import sys
import os
from pathlib import Path
from typing import Dict, List

# 프로젝트 루트 경로 설정
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# MFU-BM 1단계에서 구축한 모듈 임포트
from scripts.benchmark_generator import fetch_benchmark_data, simulate_custom_portfolio, calculate_metrics

"""
[AGENTS.md 준수]
투자 시작 연월(Vintage)별 성과 매트릭스 생성기.
2000년부터 매월 시작 시점을 이동하며 시뮬레이션을 수행하여 전략의 견고함을 평가합니다.
"""

def generate_vintage_matrix():
    # 1. 데이터 수집 (한 번만 수행)
    data = fetch_benchmark_data()
    # 최근 3개월은 통계적 유의성이 낮으므로 제외 (루프 종료 시점 조정 가능)
    vintage_dates = data.index[:-3].tolist() 
    
    results = []
    
    # 2. 테스트 대상 포트폴리오 정의
    portfolios = {
        'SPY': {'SPY': 1.0},
        '60_40': {'SPY': 0.6, 'TLT': 0.4},
        'Mix': {'SPY': 0.6, 'TLT': 0.3, 'GLD': 0.1}
    }
    
    print(f"\n🔄 빈티지 매트릭스 생성 시작 (총 {len(vintage_dates)}개 시작점)...")
    
    # 3. 빈티지 루프 (각 월별 시작 시점 이동)
    for start_dt in vintage_dates:
        start_str = start_dt.strftime('%Y-%m-%d')
        row = {'Vintage': start_dt.strftime('%Y-%m')}
        
        # 각 포트폴리오 조합별 시뮬레이션
        for name, weights in portfolios.items():
            # A. 거치식 (Buy & Hold)
            bh_curve = simulate_custom_portfolio(data, weights, start_str, initial_capital=10000, monthly_contribution=0)
            if not bh_curve.empty:
                bh_metrics = calculate_metrics(bh_curve)
                row[f"{name}_BH_CAGR"] = bh_metrics['cagr']
                row[f"{name}_BH_MDD"] = bh_metrics['mdd']
            
            # B. 적립식 (DCA)
            dca_curve = simulate_custom_portfolio(data, weights, start_str, initial_capital=10000, monthly_contribution=1000)
            if not dca_curve.empty:
                dca_metrics = calculate_metrics(dca_curve)
                row[f"{name}_DCA_CAGR"] = dca_metrics['cagr']
                row[f"{name}_DCA_MDD"] = dca_metrics['mdd']
            
        results.append(row)
        
    # 4. 매트릭스 데이터 구조화 (Pandas DataFrame)
    df = pd.DataFrame(results).set_index('Vintage')
    
    # 5. CSV 저장
    output_path = Path("outputs/benchmarks/vintage_matrix.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path)
    print(f"\n✅ 매트릭스 저장 완료: {output_path}")
    
    # 6. 인사이트 출력
    print("\n" + "="*65)
    print("💡 빈티지 분석 인사이트 (DCA 투자 기준)")
    print("="*65)
    
    # Insight 1: SPY 100% DCA 최악의 시점
    # MDD가 가장 낮은(절댓값이 큰) 순서로 정렬
    worst_spy_dca = df.sort_values(by='SPY_DCA_MDD').head(3)
    print("\n[SPY 100% DCA 투자가 가장 큰 고통을 겪었던 시작 연월 Top 3]")
    for vintage, r in worst_spy_dca.iterrows():
        print(f"   - {vintage} 시작: MDD {r['SPY_DCA_MDD']:>6.2f}% (현재까지 CAGR {r['SPY_DCA_CAGR']:>6.2f}%)")
        
    # Insight 2: 60/40 DCA의 방어 우위 (MDD 차이)
    # 60/40 MDD가 SPY MDD보다 얼마나 덜 하락했는지 (MDD_Diff = 60/40_MDD - SPY_MDD)
    df['MDD_Diff'] = df['60_40_DCA_MDD'] - df['SPY_DCA_MDD']
    best_defense = df.sort_values(by='MDD_Diff', ascending=False).head(3)
    print("\n[60/40 DCA가 SPY 대비 방어력이 가장 압도적이었던 시작 연월 Top 3]")
    for vintage, r in best_defense.iterrows():
        print(f"   - {vintage} 시작: 60/40 MDD {r['60_40_DCA_MDD']:>6.2f}% vs SPY MDD {r['SPY_DCA_MDD']:>6.2f}% (방어우위: {r['MDD_Diff']:>5.2f}%p)")
    print("="*65)

if __name__ == "__main__":
    generate_vintage_matrix()

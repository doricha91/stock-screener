import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path
import sys
import os

# 프로젝트 루트를 path에 추가하여 모듈 참조 가능케 함
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.paths import market_db_path, ROOT

def visualize_regimes(output_path="analysis_results/market_regime_timeline.png"):
    db_path = market_db_path()
    if not Path(db_path).exists():
        print(f"❌ DB 파일을 찾을 수 없습니다: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    
    # 1. 국면 로그 가져오기
    try:
        regime_df = pd.read_sql("SELECT date, status, trade_halted FROM market_status_log ORDER BY date", conn)
    except Exception as e:
        print(f"❌ market_status_log 읽기 실패: {e}")
        conn.close()
        return

    # 2. 벤치마크(SPY) 가격 가져오기 (비교용)
    try:
        spy_df = pd.read_sql("SELECT date, close FROM market_index WHERE symbol = 'SPY' ORDER BY date", conn)
    except Exception as e:
        print(f"⚠️ market_index(SPY) 읽기 실패: {e}. 가격 그래프 없이 진행합니다.")
        spy_df = pd.DataFrame()
        
    conn.close()

    if regime_df.empty:
        print("⚠️ 국면 데이터가 없습니다.")
        return

    regime_df['date'] = pd.to_datetime(regime_df['date'])
    
    # 시각화 설정
    fig, ax1 = plt.subplots(figsize=(16, 8))
    
    # 가격 데이터가 있는 경우 선 그래프 추가
    if not spy_df.empty:
        spy_df['date'] = pd.to_datetime(spy_df['date'])
        # 공통 기간 설정
        start_date = max(regime_df['date'].min(), spy_df['date'].min())
        end_date = min(regime_df['date'].max(), spy_df['date'].max())
        
        regime_df = regime_df[(regime_df['date'] >= start_date) & (regime_df['date'] <= end_date)]
        spy_df = spy_df[(spy_df['date'] >= start_date) & (spy_df['date'] <= end_date)]

        ax1.plot(spy_df['date'], spy_df['close'], color='black', linewidth=1.5, label='SPY Index', alpha=0.8)
        ax1.set_ylabel('SPY Close Price')
    else:
        ax1.set_ylabel('Regime State')
        ax1.set_yticks([])

    ax1.set_xlabel('Date')

    # 3. 국면 배경 색칠
    color_map = {
        'BULL': '#C6F4D6',     # 파스텔 녹색
        'UNSTABLE': '#FFF3CD', # 파스텔 노랑
        'BEAR': '#F8D7DA',     # 파스텔 분홍
        'PANIC': '#F5B7B1'     # 연한 적색
    }
    
    # 국면 변화 구간별 색칠
    for i in range(len(regime_df) - 1):
        d_start = regime_df['date'].iloc[i]
        d_end = regime_df['date'].iloc[i+1]
        status = regime_df['status'].iloc[i]
        
        ax1.axvspan(d_start, d_end, color=color_map.get(status, '#FFFFFF'), alpha=0.6)
        
        # 거래 중단(Halted) 지점 표시
        if regime_df['trade_halted'].iloc[i] == 1:
            ax1.axvline(d_start, color='red', linestyle='--', linewidth=0.5, alpha=0.3)

    # 범례 구성
    regime_patches = [mpatches.Patch(color=color, label=label) for label, color in color_map.items()]
    legend_elements = regime_patches
    if regime_df['trade_halted'].any():
        halt_patch = mpatches.Patch(color='red', label='Trade Halted', alpha=0.3)
        legend_elements.append(halt_patch)
        
    ax1.legend(handles=legend_elements, loc='upper left', title="Market Regimes")

    plt.title(f"Market Regime Analysis (SPY Overlay)\nPeriod: {regime_df['date'].min().date()} ~ {regime_df['date'].max().date()}", fontsize=15)
    plt.grid(axis='y', linestyle=':', alpha=0.5)
    
    # 결과 폴더 확인 및 저장
    save_path = ROOT / output_path
    save_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(save_path, dpi=150)
    plt.close()
    
    print(f"✅ 시각화 완료: {save_path}")

if __name__ == "__main__":
    visualize_regimes()

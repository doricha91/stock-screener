# core/performance_tracker.py
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Optional
from core.paths import FRONT_TEST_DIR
from core.target_portfolio_state import CurrentPortfolioState
from screener import data_manager

PERFORMANCE_LOG_PATH = FRONT_TEST_DIR / "forward_performance.csv"

class PerformanceTracker:
    def __init__(self):
        self.log_path = PERFORMANCE_LOG_PATH

    def update_performance(self, date_str: str, state: CurrentPortfolioState):
        """오늘의 Total Equity를 계산하고 CSV에 누적 기록합니다."""
        print(f"📊 Calculating performance for {date_str}...")
        
        total_stock_value = 0.0
        stale_prices = []

        # 1. 보유 종목 가치 계산 (Neo의 안전장치 반영)
        for symbol in state.current_symbols:
            shares = state.shares.get(symbol, 0)
            if shares <= 0: continue
            
            try:
                df = data_manager.get_price_data(symbol, start_date=date_str)
                if df is not None and not df.empty:
                    # 오늘 종가 사용
                    price = df.iloc[-1]['close']
                else:
                    # 데이터 부재 시 평단가로 대체 (자산 급락 방어)
                    price = state.avg_price.get(symbol, 0)
                    stale_prices.append(symbol)
            except Exception:
                price = state.avg_price.get(symbol, 0)
                stale_prices.append(symbol)
            
            total_stock_value += (shares * price)

        if stale_prices:
            print(f"⚠️  [STALE_PRICE] 종가 데이터 부재로 평단가 대체 사용: {', '.join(stale_prices)}")

        total_equity = state.absolute_cash + total_stock_value
        
        # 2. 신규 데이터 준비
        new_row = {
            "Date": date_str,
            "Cash": round(state.absolute_cash, 2),
            "Stock_Value": round(total_stock_value, 2),
            "Total_Equity": round(total_equity, 2)
        }

        # 3. CSV 업데이트 및 지표 계산
        if self.log_path.exists():
            df = pd.read_csv(self.log_path)
            # 중복 날짜 제거 후 결합
            df = df[df['Date'] != date_str]
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        else:
            df = pd.DataFrame([new_row])

        # 4. 수익률 및 MDD 계산
        df['Daily_Return'] = df['Total_Equity'].pct_change() * 100
        initial_equity = df['Total_Equity'].iloc[0]
        df['Cumulative_Return'] = (df['Total_Equity'] / initial_equity - 1) * 100
        
        # MDD 계산
        rolling_max = df['Total_Equity'].cummax()
        drawdown = (df['Total_Equity'] / rolling_max - 1) * 100
        df['MDD'] = drawdown.cummin()

        df.to_csv(self.log_path, index=False, encoding="utf-8-sig")
        
        print(f"✅ Performance tracked: Equity ${total_equity:,.2f} | Cum.Ret {df['Cumulative_Return'].iloc[-1]:.2f}% | MDD {df['MDD'].iloc[-1]:.2f}%")
        return total_equity

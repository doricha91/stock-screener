# core/review_generator.py
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional
from core.paths import FRONT_TEST_DIR, OUTPUTS

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

EXECUTION_LOG_PATH = FRONT_TEST_DIR / "execution_log.csv"

class ReviewGenerator:
    def __init__(self, days: int = 7):
        self.days = days
        self.log_path = EXECUTION_LOG_PATH
        self.df = None
        self.now_est = datetime.now(ZoneInfo("US/Eastern"))

    def load_data(self) -> bool:
        """데이터를 로드하고 필터링합니다."""
        if not self.log_path.exists():
            return False
        
        self.df = pd.read_csv(self.log_path)
        self.df['Date'] = pd.to_datetime(self.df['Date'])
        
        # 지침 2: EST 기준으로 데이터 필터링
        cutoff_date = self.now_est - timedelta(days=self.days)
        self.df = self.df[self.df['Date'] >= pd.Timestamp(cutoff_date.date())]
        
        return not self.df.empty

    def calculate_metrics(self) -> Dict[str, Any]:
        """핵심 지표를 계산합니다."""
        if self.df is None or self.df.empty:
            return {}

        total_count = len(self.df)
        match_count = len(self.df[self.df['Reason'] == 'MATCH'])
        compliance_rate = (match_count / total_count * 100) if total_count > 0 else 0

        # 괴리 사유 통계
        reason_counts = self.df['Reason'].value_counts()
        reason_pct = (reason_counts / total_count * 100).to_dict()

        # 지침 1: 가중 평균 슬리피지 계산
        valid_trades = self.df[
            (self.df['Act_Price'] > 0) & 
            (self.df['Rec_Price'] > 0) & 
            (self.df['Reason'].isin(['MATCH', 'PARTIAL_FILL']))
        ].copy()

        def calc_slip(row):
            rec = row['Rec_Price']
            act = row['Act_Price']
            if row['Type'].upper() in ['BUY', '매수']:
                return (act - rec) / rec * 100
            else: # SELL
                return (rec - act) / rec * 100

        if not valid_trades.empty:
            valid_trades['Slippage_Pct'] = valid_trades.apply(calc_slip, axis=1)
            # 거래 대금(Rec_Shares * Rec_Price)을 가중치로 사용
            valid_trades['Trade_Value'] = valid_trades['Rec_Shares'] * valid_trades['Rec_Price']
            total_value = valid_trades['Trade_Value'].sum()
            
            if total_value > 0:
                weighted_avg_slippage = (valid_trades['Slippage_Pct'] * valid_trades['Trade_Value']).sum() / total_value
            else:
                weighted_avg_slippage = 0.0
                
            max_slippage = valid_trades['Slippage_Pct'].max()
        else:
            weighted_avg_slippage = 0.0
            max_slippage = 0.0

        return {
            "total_trades": total_count,
            "compliance_rate": compliance_rate,
            "reason_stats": reason_counts.to_dict(),
            "reason_pct": reason_pct,
            "avg_slippage": weighted_avg_slippage, # 이제 가중 평균임
            "max_slippage": max_slippage,
            "days": self.days
        }

    def generate_report(self) -> str:
        """마크다운 리포트를 생성합니다."""
        if not self.load_data():
            return "❌ No execution data found for the given period."

        metrics = self.calculate_metrics()
        date_str = self.now_est.strftime("%Y%m%d")
        report_path = FRONT_TEST_DIR / f"weekly_review_{date_str}.md"

        # 등급 결정 (동일 로직)
        rate = metrics['compliance_rate']
        grade = "S" if rate >= 95 else "A" if rate >= 85 else "B" if rate >= 70 else "F"
        emoji = "🔥" if grade == "S" else "✅" if grade == "A" else "⚠️" if grade == "B" else "🚨"

        content = f"""# 📝 Front-test Review Report [{self.now_est.strftime('%Y-%m-%d')}]
> 분석 기간: 최근 {metrics['days']}일 | 대상 거래 건수: {metrics['total_trades']}건 | 기준 타임존: EST

## 1. 📊 운영 요약 (Executive Summary)
- **규율 준수 등급**: `{grade}` {emoji}
- **시스템 지시 준수율**: **{metrics['compliance_rate']:.1f}%**
- **평균 슬리피지 비용 (가중)**: `{metrics['avg_slippage']:.3f}%` (거래 대금 가중치 반영)
- **최대 슬리피지 충격**: `{metrics['max_slippage']:.3f}%`

## 2. 🧩 괴리 사유 상세 (Deviation Breakdown)
| 사유 코드 | 발생 횟수 | 비중(%) |
| :--- | :---: | :---: |
"""
        for reason, count in metrics['reason_stats'].items():
            content += f"| {reason} | {count} | {metrics['reason_pct'][reason]:.1f}% |\n"

        content += f"""
## 3. 📉 슬리피지 분석 (Execution Friction)
> 슬리피지는 '실제 체결가'가 '시스템 예상가'보다 얼마나 불리했는지를 측정합니다. (매수 시 비싸게, 매도 시 싸게 팔면 양수)

- **평균 마찰 비용**: `{metrics['avg_slippage']:.3f}%`
- **평가**: {"우수 (슬리피지 관리 매우 잘됨)" if metrics['avg_slippage'] < 0.1 else "보통 (시장 마찰 범위 내)" if metrics['avg_slippage'] < 0.5 else "주의 (주문 집행 시 뇌동매매 또는 갭 대응 미흡)"}

## 4. 📝 운영자 메모 (Qualitative Notes)
| Date | Symbol | Reason | Note |
| :--- | :--- | :--- | :--- |
"""
        # 메모가 있는 행만 추출 (최근 5건)
        notes_df = self.df.dropna(subset=['Notes']).tail(5)
        if notes_df.empty:
            content += "| - | - | - | 특이사항 없음 |\n"
        else:
            for _, row in notes_df.iterrows():
                content += f"| {row['Date'].strftime('%Y-%m-%d')} | **{row['Symbol']}** | {row['Reason']} | {row['Notes']} |\n"

        content += f"""
---
**Action Items**:
1. 준수율이 85%(A등급) 미만이라면 `MANUAL_SKIP` 사유를 집중 복기하십시오.
2. 평균 슬리피지가 0.5%를 초과한다면 지정가 주문(Limit Order) 활용을 검토하십시오.
"""
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        return str(report_path)

# scripts/init_front_test_state.py
import sys
import json
from pathlib import Path
from dataclasses import asdict
from datetime import datetime

# 프로젝트 루트 경로 설정 (부모의 부모 디렉토리)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Core 모듈 임포트
from core.target_portfolio_state import CurrentPortfolioState
from core.paths import current_state_snapshot_path

# ==========================================
# [운영자 설정 블록] 본인의 HTS 잔고에 맞게 수정하세요.
# ==========================================
TARGET_DATE = "20260410"  # 시작 날짜 (YYYYMMDD)

MY_CASH = 10000000.0      # 현재 예수금 (총 가용 현금)

# 현재 보유 종목 (롱 포지션 전용)
# 형식: "티커": {"shares": 수량, "avg_price": 평단가}
MY_POSITIONS = {
    "005930": {"shares": 100, "avg_price": 72000.0},  # 예: 삼성전자
    "000660": {"shares": 50, "avg_price": 180000.0},  # 예: SK하이닉스
}
# ==========================================

def main():
    print("\n" + "◈"*40)
    print(" STOCK SCREENER - INITIAL STATE GENERATOR")
    print("◈"*40)

    try:
        # 1. 필드 추출 및 초기화
        current_symbols = list(MY_POSITIONS.keys())
        shares = {s: p["shares"] for s, p in MY_POSITIONS.items()}
        avg_price = {s: p["avg_price"] for s, p in MY_POSITIONS.items()}
        
        # [Fail-safe] 최고가는 최초 진입이므로 평단가로 초기화
        highest_prices = {s: p["avg_price"] for s, p in MY_POSITIONS.items()}
        
        # 2. CurrentPortfolioState 객체 생성 (데이터 검증 수행됨)
        state = CurrentPortfolioState(
            current_symbols=current_symbols,
            current_cash_ratio=0.0,   # 최초 상태이므로 0.0 (시스템에서 추후 업데이트)
            current_hedge_ratio=0.0,  # 최초 상태이므로 0.0
            absolute_cash=MY_CASH,
            shares=shares,
            avg_price=avg_price,
            highest_prices=highest_prices,
            hedge_symbols=[]          # 초기 헤지 종목 없음
        )

        # 3. 저장 경로 확보 및 저장
        file_path = current_state_snapshot_path(TARGET_DATE)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(state), f, indent=4, ensure_ascii=False)

        # 4. 결과 출력
        print(f"\n✅ 최초 스냅샷 생성 완료!")
        print(f"📍 저장 위치: {file_path}")
        print(f"💰 설정 현금: {MY_CASH:,.0f}원")
        print(f"📦 보유 종목: {len(current_symbols)}개 ({', '.join(current_symbols) if current_symbols else '없음'})")
        print(f"📅 기준 날짜: {TARGET_DATE}")
        print("\n" + "◈"*40 + "\n")

    except Exception as e:
        print(f"\n❌ [ERROR] 스냅샷 생성 중 오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

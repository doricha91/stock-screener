import sys
import os
import time
from datetime import datetime

# 모듈 임포트
import database
import data_collector
import market_analyzer
import screener


def print_header():
    print("\n" + "=" * 60)
    print(f"🤖 QUANT SYSTEM v4.0 - AUTO TRADING ASSISTANT")
    print(f"📅 실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


def main():
    print_header()

    # --- 1. 데이터베이스 점검 및 구축 ---
    print("\n[Step 1] 시스템 점검 (Database)")
    if not os.path.exists(database.DB_PATH):
        print(" ⚠️ DB 파일이 없습니다. 새로 구축합니다.")
        database.create_tables()
    else:
        print(f" ✅ DB 연결 확인: {database.DB_PATH}")

    # --- 2. 데이터 업데이트 (수집) ---
    print("\n[Step 2] 데이터 동기화 (Data Collection)")
    print(" ⏳ 최신 데이터를 수집합니다. (시간이 소요될 수 있습니다)")

    try:
        # (1) 종목 리스트 확보
        tickers = data_collector.get_sp500_tickers()

        # (2) 시장 지수(SPY, QQQ, VIX 등) 업데이트
        data_collector.update_market_indices()

        # (3) 종목 상세 정보 업데이트 (가끔 실행해도 되지만, 일단 매번 체크)
        data_collector.update_tickers_info(tickers)

        # (4) 개별 종목 주가 업데이트
        data_collector.update_stock_data(tickers)

    except Exception as e:
        print(f" ❌ 데이터 수집 중 치명적 오류 발생: {e}")
        # 데이터 수집이 실패해도 기존 데이터로 분석을 시도할지 결정해야 함
        # 여기서는 중단하지 않고 진행

    # --- 3. 시장 상황 분석 ---
    print("\n[Step 3] 시장 상황 판단 (Market Analysis)")
    try:
        market_status = market_analyzer.analyze_market_status()
        status = market_status.get('status')
        desc = market_status.get('description')

        print(f" 👉 결과: [{status}] {desc}")

        # VIX 정보 등 추가 출력
        print(f"    (SPY: {market_status.get('spy_close')}, VIX: {market_status.get('vix')})")

    except Exception as e:
        print(f" ❌ 시장 분석 중 오류 발생: {e}")
        return  # 시장 판단 불가 시 종료

    # --- 4. 유망 종목 스크리닝 ---
    print("\n[Step 4] 유망 종목 발굴 (Screener)")

    if status in ['PANIC', 'BEAR']:
        print(" ⛔ 시장 상황이 좋지 않아 스크리닝을 건너뜁니다.")
        print("    (시스템 종료)")
        return

    try:
        # 스크리너 실행 (결과는 내부에서 출력됨)
        results = screener.run_screener()

        if results is not None and not results.empty:
            print(f"\n✅ 오늘의 추천 종목 ({len(results)}개) 생성이 완료되었습니다.")
            # 추후 여기에 텔레그램 전송 코드 등을 추가할 수 있습니다.
        else:
            print("\n🤷 검색된 종목이 없습니다.")

    except Exception as e:
        print(f" ❌ 스크리닝 중 오류 발생: {e}")

    print("\n" + "=" * 60)
    print("🏁 모든 작업이 완료되었습니다. 성투하세요!")
    print("=" * 60)


if __name__ == "__main__":
    main()
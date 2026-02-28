import sqlite3
import pandas as pd
import os
import market_analyzer
import config

# 테스트용 임시 DB 파일명
TEST_DB_NAME = "temp_test_market.db"


def create_mock_data(scenario):
    """
    시나리오에 맞는 가짜 데이터를 생성하여 임시 DB에 저장
    scenario: 'BULL', 'BEAR', 'PANIC', 'UNSTABLE'
    """
    if os.path.exists(TEST_DB_NAME):
        os.remove(TEST_DB_NAME)

    conn = sqlite3.connect(TEST_DB_NAME)
    cursor = conn.cursor()

    # 테이블 생성
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_index (
            date TEXT,
            symbol TEXT,
            close REAL,
            adj_close REAL
        )
    """)

    # 기본 데이터 (200일치)
    dates = pd.date_range(end='2025-01-01', periods=205)

    # 시나리오별 가격 설정
    if scenario == 'BULL':
        # SPY, QQQ가 200일선(100)보다 높음(120), VIX 낮음(15)
        spy_price = 120
        qqq_price = 120
        vix_price = 15
    elif scenario == 'BEAR':
        # SPY, QQQ가 200일선(100)보다 낮음(80), VIX 보통(20)
        spy_price = 80
        qqq_price = 80
        vix_price = 20
    elif scenario == 'PANIC':
        # 가격 상관없이 VIX가 폭발(40)
        spy_price = 80
        qqq_price = 80
        vix_price = 40
    else:  # UNSTABLE
        # SPY는 상승(120), QQQ는 하락(80) (엇갈림)
        spy_price = 120
        qqq_price = 80
        vix_price = 15

    # 데이터 삽입 (200일 전부터 오늘까지)
    data = []
    for i, date in enumerate(dates):
        d_str = date.strftime('%Y-%m-%d')
        # 200일 이동평균을 100으로 만들기 위해 앞부분은 100으로 고정
        price_base = 100

        # 마지막 날(오늘)만 시나리오 가격 적용
        if i == len(dates) - 1:
            data.append((d_str, 'SPY', spy_price, spy_price))
            data.append((d_str, 'QQQ', qqq_price, qqq_price))
            data.append((d_str, '^VIX', vix_price, vix_price))
        else:
            data.append((d_str, 'SPY', price_base, price_base))
            data.append((d_str, 'QQQ', price_base, price_base))
            data.append((d_str, '^VIX', 20, 20))

    cursor.executemany("INSERT INTO market_index VALUES (?, ?, ?, ?)", data)
    conn.commit()
    conn.close()


def run_test():
    print(f"🔬 [검증 시작] market_analyzer 로직 테스트\n")

    # 1. market_analyzer가 테스트 DB를 바라보게 설정
    original_db_path = market_analyzer.DB_PATH
    market_analyzer.DB_PATH = TEST_DB_NAME

    scenarios = ['BULL', 'BEAR', 'PANIC', 'UNSTABLE']

    for sc in scenarios:
        print(f"--- 시나리오: {sc} ---")
        create_mock_data(sc)

        # 분석 실행
        status, plan = market_analyzer.get_market_regime()

        # 결과 검증
        print(f"👉 판정 결과: {status}")
        print(f"👉 현금 비중: {plan['cash_ratio']}")

        # 간단한 일치 여부 확인
        if status == sc:
            print("✅ PASS")
        else:
            print(f"❌ FAIL (Expected {sc}, Got {status})")
        print("")

    # 뒷정리
    market_analyzer.DB_PATH = original_db_path
    if os.path.exists(TEST_DB_NAME):
        os.remove(TEST_DB_NAME)
    print("검증 완료.")


if __name__ == "__main__":
    run_test()
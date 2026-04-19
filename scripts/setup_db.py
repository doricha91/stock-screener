# scripts/setup_db.py
import os
import sys
import sqlite3
from pathlib import Path

# 1. 프로젝트 루트 경로를 시스템 경로에 추가 (PyCharm 참조용)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# 프로젝트 내부의 DB 연결 로직을 그대로 가져옵니다.
from market_analyzer import get_db_connection

def setup_market_status_table():
    """
    [MFU4] 시장 국면 데이터를 저장할 테이블을 '강제 초기화'하고 생성합니다.
    주의: 이 함수를 실행하면 기존에 저장된 모든 시장 국면 로그가 삭제됩니다!
    """
    print("\n" + "="*50)
    print("⚠️  시장 국면 데이터베이스 초기화 작업을 시작합니다...")
    print("="*50)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 2. 기존 테이블 삭제 (DROP)
        print(" - 기존 market_status_log 테이블 삭제 중...")
        cur.execute("DROP TABLE IF EXISTS market_status_log")
        
        # 3. 신규 확장 스키마로 테이블 생성 (CREATE)
        print(" - 신규 확장 스키마 생성 중 (MFU4 규격)...")
        cur.execute("""
            CREATE TABLE market_status_log (
                date TEXT PRIMARY KEY,        -- 날짜 (PK: 중복 저장 방지)
                status TEXT,                  -- 최종 국면 (BULL, BEAR, UNSTABLE, PANIC)
                vix_value REAL,               -- VIX 지수 종가
                trade_halted INTEGER,         -- 거래 중단 여부 (0:정상, 1:중단)
                
                -- [판단 근거 플래그] 0 또는 1로 저장
                cb_trigger INTEGER,           -- 서킷브레이커 발동
                cb_halt INTEGER,              -- 서킷브레이커에 의한 중단
                ma_cross_bearish INTEGER,     -- 이동평균선 역배열
                breadth_low INTEGER,          -- 시장 심리 악화
                drawdown INTEGER,             -- 전고점 대비 급락
                vix_breakout INTEGER,         -- VIX 급등
                trend_bull INTEGER,           -- 상승 추세 조건
                trend_bear INTEGER,           -- 하락 추세 조건
                
                -- [데이터 원문 및 메타 정보]
                triggers TEXT,                -- 판단 근거 원문 (JSON 형식)
                description TEXT,             -- 판정 결과 요약 텍스트
                created_at TEXT               -- 로그 생성 시간
            )
        """)
        
        conn.commit()
        print("\n✅ 테이블 생성이 성공적으로 완료되었습니다.")
        print("📂 DB 위치: outputs/market_data.db")
        print("="*50 + "\n")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    setup_market_status_table()

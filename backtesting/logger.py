# [ 📄 backtesting/logger.py (신규 파일) ]

import sqlite3
import datetime
import pandas as pd
import config  # config.py 임포트

# DB 파일 이름 (프로젝트 루트에 생성됨)
BACKTEST_DB_NAME = config.BACKTEST_DB_NAME # <-- 이렇게 변경
TABLE_NAME = 'results'


def log_backtest_result(strategy_context, metrics_stats):
    """
    백테스트의 '설정값'과 '결과값'을 딕셔너리로 받아
    SQLite DB에 한 줄로 저장(INSERT)합니다.
    테이블에 없는 컬럼(새로운 지표)은 자동으로 추가합니다.

    :param strategy_context: (dict) 전략 설정값 (예: {'symbol': 'AAPL', ...})
    :param metrics_stats: (dict) 성과 지표 (예: {'total_return_pct': 1.52, ...})
    """

    # 1. 두 딕셔너리를 하나로 병합
    log_data = strategy_context.copy()
    log_data.update(metrics_stats)

    # 2. 메타데이터 추가
    log_data['timestamp'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = None
    try:
        # 3. DB 연결 (파일이 없으면 자동 생성)
        conn = sqlite3.connect(BACKTEST_DB_NAME)
        cursor = conn.cursor()

        # 4. 테이블 기본 생성 (id, timestamp 외에는 동적으로 추가됨)
        cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL
        );
        """)

        # 5. (핵심) 스키마 확장성: DB에 없는 새 컬럼(지표) 자동 추가
        # 현재 테이블의 컬럼 정보 가져오기
        cursor.execute(f"PRAGMA table_info({TABLE_NAME});")
        existing_columns = [row[1] for row in cursor.fetchall()]  # row[1]은 컬럼 이름

        for column_name, value in log_data.items():
            if column_name not in existing_columns:
                # 컬럼의 데이터 타입 추론 (간단한 버전)
                col_type = 'REAL'  # 기본값 (대부분의 지표)
                if isinstance(value, str):
                    col_type = 'TEXT'
                elif isinstance(value, int):
                    col_type = 'INTEGER'

                print(f"로그: 새 컬럼 발견. '{column_name}' (Type: {col_type})을/를 DB에 추가합니다.")
                cursor.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN {column_name} {col_type};")

        # 6. 데이터 삽입 (Dynamic INSERT)
        columns = ', '.join(log_data.keys())
        placeholders = ', '.join(['?'] * len(log_data))
        values = list(log_data.values())

        sql = f"INSERT INTO {TABLE_NAME} ({columns}) VALUES ({placeholders});"
        cursor.execute(sql, values)

        # 7. 변경 사항 저장
        conn.commit()
        print(f"로그: 백테스트 결과가 {BACKTEST_DB_NAME}에 성공적으로 저장되었습니다.")

    except sqlite3.Error as e:
        print(f"SQLite 오류: {e}")
    finally:
        if conn:
            conn.close()
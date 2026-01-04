import pandas as pd
import itertools
import time
import sqlite3
import json
from datetime import datetime
from run_portfolio_backtest import run_backtest_with_config, PORTFOLIO_CONFIG

# ==============================================================================
# 🧪 [자유롭게 수정 가능] 테스트할 변수들의 조합 (Grid Search)
# ==============================================================================
# 여기에 변수를 추가하거나 삭제하면, DB 테이블도 자동으로 업데이트됩니다.
# (PORTFOLIO_CONFIG에 있는 변수명과 똑같이 써야 합니다)
params_grid = {
    # # 1. 진입/청산 타임
    # 'entry_period': [20, 50],
    # 'exit_period': [10],
    #
    # # 2. 필터링 기준
    # 'score_threshold': [1.0],  # 낮음(공격적) vs 보통
    # 'rs_lookback': [60],  # 3개월 vs 6개월
    #
    # # 3. 가중치 실험 (0.0은 끄기, 3.0은 강조)
    # 'rs_weight': [1.0],
    #
    # # 4. 자금 관리
    # 'max_positions': [4, 5],

    # 핵심 변수
    'exit_period': [15, 20, 25], #익절/손절 타이밍
    'rs_lookback': [20, 30, 40], #RS 비교 기간
    'entry_period': [20], #진입 타이밍
    'max_positions': [5], #종목 수

    # 필터링 및 가중치 변수
    'score_threshold': [1.0], #진입 점수 문턱
    'rs_weight': [1.0], #RS 점수 비중, 0.0: 절대모멘텀, 5.0: 시장보다 강한놈만 취급
    'turtle_weight': [1.0], #신고가 점수 비중

    # 보조지표 세부 설정
    'atr_period': [20], #변동성 계산 기간, 20
    'rsi_period': [14], #RSI 계산 기간, 14
    'mfi_period': [14], #MFI, 자금 흐름 기간, 14
    'sma_short_period': [50], #단기 이평선, 50
    'sma_long_period': [200], #장기 이평선, 200

    # 보조지표 세부 설정
    # 'atr_period': [14, 20, 30], #변동성 계산 기간, 20
    # 'rsi_period': [9, 14, 21], #RSI 계산 기간, 14
    # 'mfi_period': [10, 14, 20], #MFI, 자금 흐름 기간, 14
    # 'sma_short_period': [20, 50, 60], #단기 이평선, 50
    # 'sma_long_period': [150, 200, 250], #장기 이평선, 200

}

DB_PATH = "backtest_log.db"
TABLE_NAME = "optimization_log"


# ==============================================================================
# 🛠️ 동적 DB 관리 함수 (Dynamic Schema Management)
# ==============================================================================
def ensure_table_exists(conn, param_keys):
    """
    테이블이 없으면 만들고,
    새로운 파라미터(컬럼)가 생겼으면 자동으로 테이블을 확장합니다.
    """
    cursor = conn.cursor()

    # 1. 기본 테이블 생성 (핵심 성과 지표 고정)
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date TEXT,

            -- 성과 지표 (Fixed)
            total_return REAL,
            cagr REAL,
            mdd REAL,
            final_equity REAL,
            sharpe_ratio REAL,
            sortino_ratio REAL,
            calmar_ratio REAL,

            -- 거래 통계 (Fixed)
            win_rate REAL,
            profit_factor REAL,
            total_trades INTEGER,
            avg_win REAL,
            avg_loss REAL,

            -- 연도별 수익률 (JSON)
            yearly_returns TEXT
        )
    ''')

    # 2. 현재 DB에 있는 컬럼 목록 확인
    cursor.execute(f"PRAGMA table_info({TABLE_NAME})")
    existing_columns = {row[1] for row in cursor.fetchall()}

    # 3. params_grid에 있는데 DB에는 없는 컬럼 찾아서 추가 (ALTER TABLE)
    for param in param_keys:
        if param not in existing_columns:
            print(f"🔧 DB 구조 변경: 새로운 컬럼 '{param}' 추가 중...")
            # 실수(REAL) 타입으로 추가 (대부분의 파라미터가 숫자이므로)
            cursor.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN {param} REAL")

    conn.commit()


def save_dynamic_result(conn, params, res):
    """
    파라미터(가변)와 결과(고정)를 합쳐서 DB에 저장
    """
    cursor = conn.cursor()

    # 1. 저장할 전체 데이터 딕셔너리 생성
    record = {
        'run_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        # --- 고정 결과값 매핑 ---
        'total_return': round(res['return'], 2),
        'cagr': round(res['cagr'], 2),
        'mdd': round(res['mdd'], 2),
        'final_equity': round(res['final_equity'], 0),
        'sharpe_ratio': round(res.get('sharpe', 0), 4),
        'sortino_ratio': round(res.get('sortino', 0), 4),
        'calmar_ratio': round(res.get('calmar', 0), 4),
        'win_rate': round(res['win_rate'], 2),
        'profit_factor': round(res['profit_factor'], 2),
        'total_trades': res['total_trades'],
        'avg_win': round(res['avg_win'], 2),
        'avg_loss': round(res['avg_loss'], 2),
        'yearly_returns': res.get('yearly_json', '{}')
    }

    # 2. 파라미터 값 추가 (params 딕셔너리 병합)
    record.update(params)

    # 3. 동적 INSERT 쿼리 생성
    columns = ', '.join(record.keys())
    placeholders = ', '.join(['?'] * len(record))
    values = list(record.values())

    sql = f"INSERT INTO {TABLE_NAME} ({columns}) VALUES ({placeholders})"

    try:
        cursor.execute(sql, values)
        conn.commit()
    except Exception as e:
        print(f"❌ DB 저장 오류: {e}")


# ==============================================================================
# 🚀 최적화 실행 엔진
# ==============================================================================
def run_optimization():
    # 1. 파라미터 조합 생성
    keys, values = zip(*params_grid.items())
    combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]

    print(f"🔬 총 {len(combinations)}개의 파라미터 조합을 테스트합니다.")
    print(f"📂 DB 경로: {DB_PATH}")

    # 2. DB 초기화 및 컬럼 자동 맞춤
    conn = sqlite3.connect(DB_PATH)
    ensure_table_exists(conn, params_grid.keys())

    start_time = time.time()
    results_list = []  # 최종 리포트용

    # 3. 반복 테스트 실행
    for i, params in enumerate(combinations):
        # 기본 설정에 덮어쓰기
        current_config = PORTFOLIO_CONFIG.copy()
        current_config.update(params)

        # 진행 상황 출력 (한 줄에 덮어쓰지 않고 로그 남김)
        param_str = ", ".join([f"{k}={v}" for k, v in params.items()])
        print(f"[{i + 1}/{len(combinations)}] {param_str} ...", end=" ", flush=True)

        try:
            # --- 백테스트 실행 ---
            res = run_backtest_with_config(current_config)

            if res:
                # 결과 요약 출력
                print(f"✅ CAGR: {res['cagr']:.1f}% | MDD: {res['mdd']:.1f}% | Sharpe: {res.get('sharpe', 0):.2f}")

                # DB 저장 (동적)
                save_dynamic_result(conn, params, res)

                # 리포트용 리스트 저장
                combined_record = params.copy()
                combined_record.update({
                    'return': res['return'], 'mdd': res['mdd'], 'sharpe': res.get('sharpe', 0),
                    'profit_factor': res['profit_factor'], 'win_rate': res['win_rate']
                })
                results_list.append(combined_record)
            else:
                print("❌ 결과 없음")

        except Exception as e:
            print(f"❌ 에러 발생: {e}")

    conn.close()

    # 4. 최종 Top 5 리포트 출력
    if results_list:
        df = pd.DataFrame(results_list)

        # 보기 좋게 컬럼 정렬 (파라미터 먼저, 결과 나중)
        param_cols = list(params_grid.keys())
        result_cols = ['return', 'mdd', 'sharpe', 'profit_factor', 'win_rate']
        final_cols = param_cols + result_cols

        print("\n" + "=" * 80)
        print("🏆 샤프 지수(Sharpe) 기준 Top 5 (안정적 고수익)")
        print("-" * 80)
        print(df.sort_values(by='sharpe', ascending=False).head(5)[final_cols].to_string(index=False))

        print("\n" + "=" * 80)
        print("🚀 수익률(Return) 기준 Top 5 (공격적)")
        print("-" * 80)
        print(df.sort_values(by='return', ascending=False).head(5)[final_cols].to_string(index=False))

    print(f"\n⏱️ 총 소요 시간: {time.time() - start_time:.1f}초")


if __name__ == "__main__":
    run_optimization()
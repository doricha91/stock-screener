import pandas as pd
import itertools
import time
import sqlite3
import json
from datetime import datetime
from scripts.run_portfolio_backtest import run_backtest_with_config, PORTFOLIO_CONFIG
import config
from pathlib import Path

# ==============================================================================
# 🧪 [자유롭게 수정 가능] 테스트할 변수들의 조합 (Grid Search)
# ==============================================================================
# 여기에 변수를 추가하거나 삭제하면, DB 테이블도 자동으로 업데이트됩니다.
# (PORTFOLIO_CONFIG에 있는 변수명과 똑같이 써야 합니다)

params_grid = {
    # Best Known Parameter:
    # exit:15, rs_lookback:30, entry_period:20, max_positions:5, rs_weight:1.0, score_threshold:1.5, turtle weight: 1.0

    # [1] 핵심 변수
    'exit_period': [10],  # 익절/손절 기준일 (기본값: 10)
    'rs_lookback': [30],  # RS(상대강도) 비교 기간 (기본값: 120)
    'entry_period': [20],  # 진입(신고가) 기준일 (기본값: 20)
    'max_positions': [5],  # 최대 보유 종목 수 (기본값: 4)

    # [NEW] 트레일링 스탑 설정 (PortfolioDB 기능 활용)
    'trailing_stop_multiplier': [2.5], # ATR의 N배만큼 하락하면 이익 실현/손절

    # [2] 필터링 및 핵심 가중치
    'score_threshold': [1.5],  # 진입 점수 문턱 (기본값: 1.0)
    'rs_weight': [1.0],  # RS 점수 가중치 (기본값: 3.0)
    'turtle_weight': [1.0],  # 터틀(신고가) 전략 가중치 (기본값: 1.0)

    # [3] 추가 전략 가중치 (실험 시 주석 해제하여 사용)
    # -----------------------------------------------------------
    # 'rsi_weight': [1.0],       # RSI(과매도/과매수) 전략 가중치 (기본값: 1.0)
    # 'sma_weight': [1.0],       # SMA(골든크로스) 전략 가중치 (기본값: 1.0)
    # 'bbands_weight': [1.0],    # 볼린저밴드(역추세) 전략 가중치 (기본값: 1.0)
    # 'macd_weight': [1.0],      # MACD(추세반전) 전략 가중치 (기본값: 1.0)
    # 'bbs_weight': [1.0],       # BBS(볼린저 스퀴즈) 전략 가중치 (기본값: 1.0)
    # 'dema_weight': [1.0],      # DEMA(이중지수이동평균) 전략 가중치 (기본값: 1.0)
    # 'obv_weight': [0.5],       # OBV(거래량 추세) 보조점수 (기본값: 0.5)
    # 'mfi_weight': [0.5],       # MFI(자금흐름) 보조점수 (기본값: 0.5)
    # 'vol_spike_weight': [0.5], # 거래량 폭발 보조점수 (기본값: 0.5)
    # -----------------------------------------------------------

    # [4] 보조지표 세부 설정
    'atr_period': [20],  # 변동성(ATR) 계산 기간 (기본값: 20)
    'rsi_period': [14],  # RSI 계산 기간 (기본값: 14)
    'mfi_period': [14],  # MFI 계산 기간 (기본값: 14)
    'sma_short_period': [50],  # 단기 이평선 기간 (기본값: 50)
    'sma_long_period': [200],  # 장기 이평선 기간 (기본값: 200)


    # [5] 최적화 실험용 그리드 (필요시 주석 해제)
    # 'atr_period': [14, 20, 30],
    # 'rsi_period': [9, 14, 21],
    # 'sma_short_period': [20, 50, 60],
    # 'sma_long_period': [150, 200, 250],
}

# [NEW] 커스텀 종목 바스켓 설정 (원하는 종목만 테스트하려면 주석 해제)
PORTFOLIO_CONFIG['target_tickers'] = ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'AMZN', 'GOOGL', 'META']

def _project_root() -> Path:
    here = Path(__file__).resolve()
    for p in [here.parent, *here.parents]:
        if (p / "config.py").exists() or (p / ".git").exists():
            return p
    return here.parent

ROOT = _project_root()
OUTPUTS_DIR = ROOT / "outputs"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = str(OUTPUTS_DIR / "backtest_log.db")

TABLE_NAME = "optimization_log"          # Phase 1: 학습 결과 저장 (기존 기능)
OOS_TABLE_NAME = "oos_validation_log"    # Phase 2: 검증 결과 저장 (신규 기능)


# ==============================================================================
# 🛠️ DB 관리 함수 1: 기존 학습 데이터용 (optimization_log)
# ==============================================================================
def ensure_table_exists(conn, param_keys):
    cursor = conn.cursor()
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date TEXT,
            total_return REAL, cagr REAL, mdd REAL, final_equity REAL,
            sharpe_ratio REAL, sortino_ratio REAL, calmar_ratio REAL,
            win_rate REAL, profit_factor REAL, total_trades INTEGER,
            avg_win REAL, avg_loss REAL, yearly_returns TEXT
        )
    ''')
    cursor.execute(f"PRAGMA table_info({TABLE_NAME})")
    existing_columns = {row[1] for row in cursor.fetchall()}
    for param in param_keys:
        if param not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN {param} REAL")
            except:
                pass  # 이미 존재하거나 에러 발생 시 무시
    conn.commit()


def save_dynamic_result(conn, params, res):
    cursor = conn.cursor()
    record = {
        'run_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
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
    record.update(params)
    columns = ', '.join(record.keys())
    placeholders = ', '.join(['?'] * len(record))
    values = list(record.values())
    try:
        cursor.execute(f"INSERT INTO {TABLE_NAME} ({columns}) VALUES ({placeholders})", values)
        conn.commit()
    except Exception as e:
        print(f"❌ DB 저장 오류 (Train): {e}")


# ==============================================================================
# 🛠️ DB 관리 함수 2: 신규 검증 데이터용 (oos_validation_log)
# ==============================================================================
def ensure_oos_table_exists(conn):
    cursor = conn.cursor()
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {OOS_TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date TEXT,
            params_json TEXT,
            train_cagr REAL, train_mdd REAL, train_sharpe REAL,
            test_cagr REAL, test_mdd REAL, test_sharpe REAL,
            robustness_score REAL 
        )
    ''')
    conn.commit()


def save_oos_result(conn, params, train_res, test_res):
    cursor = conn.cursor()
    params_json = json.dumps(params)
    robustness = 0.0
    if train_res.get('sharpe', 0) != 0:
        robustness = round(test_res.get('sharpe', 0) / train_res['sharpe'], 2)

    sql = f'''
        INSERT INTO {OOS_TABLE_NAME} 
        (run_date, params_json, train_cagr, train_mdd, train_sharpe, test_cagr, test_mdd, test_sharpe, robustness_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    '''
    values = (
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        params_json,
        round(train_res['cagr'], 2), round(train_res['mdd'], 2), round(train_res.get('sharpe', 0), 2),
        round(test_res['cagr'], 2), round(test_res['mdd'], 2), round(test_res.get('sharpe', 0), 2),
        robustness
    )
    try:
        cursor.execute(sql, values)
        conn.commit()
    except Exception as e:
        print(f"❌ DB 저장 오류 (OOS): {e}")


# ==============================================================================
# 🚀 최적화 실행 엔진 (통합 버전)
# ==============================================================================
def run_optimization():
    # 1. 파라미터 조합 생성
    keys, values = zip(*params_grid.items())
    combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]

    # 기간 설정 (config.py 연동)
    TRAIN_START = config.IN_SAMPLE_START
    TRAIN_END = config.IN_SAMPLE_END
    TEST_START = config.OUT_OF_SAMPLE_START
    TEST_END = config.OUT_OF_SAMPLE_END

    print(f"🔬 총 {len(combinations)}개의 파라미터 조합을 테스트합니다.")
    print(f"📅 1단계 학습(Train): {TRAIN_START} ~ {TRAIN_END}")
    print(f"📅 2단계 검증(Test) : {TEST_START} ~ {TEST_END}")
    print(f"📂 DB 경로: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    ensure_table_exists(conn, params_grid.keys())  # 기존 테이블
    ensure_oos_table_exists(conn)  # 신규 OOS 테이블

    start_time = time.time()
    train_results_list = []  # OOS 선발용 리스트

    # ------------------------------------------------------------------
    # [Phase 1] 학습 기간 최적화 (In-Sample)
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("🚀 [Phase 1] 학습 기간 시뮬레이션 시작...")
    print("=" * 60)

    for i, params in enumerate(combinations):
        current_config = PORTFOLIO_CONFIG.copy()
        current_config.update(params)

        # [중요] 학습 기간 주입
        current_config['start_date'] = TRAIN_START
        current_config['end_date'] = TRAIN_END

        # 진행 상황 출력
        param_str = ", ".join([f"{k}={v}" for k, v in params.items()])
        print(f"[{i + 1}/{len(combinations)}] {param_str} ...", end=" ", flush=True)

        try:
            res = run_backtest_with_config(current_config)
            if res:
                print(f"✅ Sharpe: {res.get('sharpe', 0):.2f}")

                # 1. 기존 방식대로 모든 결과 DB 저장
                save_dynamic_result(conn, params, res)

                # 2. OOS 선발을 위해 메모리에 기록
                record = params.copy()
                record.update({
                    'train_cagr': res['cagr'],
                    'train_mdd': res['mdd'],
                    'train_sharpe': res.get('sharpe', 0),
                    'raw_res': res  # OOS 저장용 원본
                })
                train_results_list.append(record)
            else:
                print("❌ 결과 없음")

        except Exception as e:
            print(f"❌ Error: {e}")

    # 기존 기능: Train 기간 Top 5 출력
    if train_results_list:
        df_train = pd.DataFrame(train_results_list)
        print("\n" + "=" * 80)
        print("🏆 [Phase 1 결과] 학습 기간(Train) Sharpe 기준 Top 5")
        print("-" * 80)
        cols_to_show = list(params_grid.keys()) + ['train_cagr', 'train_mdd', 'train_sharpe']
        print(df_train.sort_values(by='train_sharpe', ascending=False).head(5)[cols_to_show].to_string(index=False))

    # ------------------------------------------------------------------
    # [Phase 2] 상위 파라미터 선정 및 검증 (Out-of-Sample)
    # ------------------------------------------------------------------
    if not train_results_list:
        print("❌ 학습 결과가 없어 검증을 진행할 수 없습니다.")
        return

    # 샤프 지수 기준 상위 3개 선정
    top_n = df_train.sort_values(by='train_sharpe', ascending=False).head(3)

    print("\n" + "=" * 80)
    print(f"🏆 [Phase 2] 검증 시작 (Top {len(top_n)} 파라미터 -> OOS 테스트)")
    print("=" * 80)

    final_report = []

    for idx, row in top_n.iterrows():
        best_params = {k: row[k] for k in params_grid.keys()}

        # 검증 기간 설정 주입
        test_config = PORTFOLIO_CONFIG.copy()
        test_config.update(best_params)
        test_config['start_date'] = TEST_START
        test_config['end_date'] = TEST_END

        print(f"🔎 검증 중 (Train Sharpe: {row['train_sharpe']:.2f})...", end=" ")

        try:
            res_test = run_backtest_with_config(test_config)

            if res_test:
                print(f"✅ Test Sharpe: {res_test.get('sharpe', 0):.2f}")

                # 3. 검증 결과 DB 저장 (신규 테이블)
                save_oos_result(conn, best_params, row['raw_res'], res_test)

                # 최종 리포트 데이터 생성
                report_entry = best_params.copy()
                report_entry.update({
                    'Train Sharpe': f"{row['train_sharpe']:.2f}",
                    'Test Sharpe': f"{res_test.get('sharpe', 0):.2f}",
                    'Train CAGR': f"{row['train_cagr']:.1f}%",
                    'Test CAGR': f"{res_test['cagr']:.1f}%",
                    'Train MDD': f"{row['train_mdd']:.1f}%",
                    'Test MDD': f"{res_test['mdd']:.1f}%"
                })
                final_report.append(report_entry)
            else:
                print("❌ 결과 없음")

        except Exception as e:
            print(f"❌ Error: {e}")

    conn.close()

    # ------------------------------------------------------------------
    # [Final] Train vs Test 비교 리포트 출력
    # ------------------------------------------------------------------
    if final_report:
        df_final = pd.DataFrame(final_report)
        key_metrics = ['Train Sharpe', 'Test Sharpe', 'Train CAGR', 'Test CAGR', 'Train MDD', 'Test MDD']
        param_cols = list(params_grid.keys())
        cols = key_metrics + param_cols

        print("\n" + "=" * 100)
        print("📊 [Train vs Test 비교 리포트] 과최적화 여부 확인")
        print("-" * 100)
        print(df_final[cols].to_string(index=False))
        print("=" * 100)
        print(f"💾 검증 결과는 '{OOS_TABLE_NAME}' 테이블에 저장되었습니다.")

    print(f"\n⏱️ 총 소요 시간: {time.time() - start_time:.1f}초")


if __name__ == "__main__":
    run_optimization()
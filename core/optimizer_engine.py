import pandas as pd
import numpy as np
import config
import sqlite3
import itertools
import time
from core.backtest_engine import run_backtest_with_config
from core.portfolio_config import PORTFOLIO_CONFIG
from core.config_factory import make_config
from core.param_grid import params_grid
from core.optimizer_storage import (ensure_table_exists, save_dynamic_result, ensure_oos_table_exists, save_oos_result)
from core.paths import backtest_log_db_path

DB_PATH = backtest_log_db_path()

TABLE_NAME = "optimization_log"          # Phase 1: 학습 결과 저장 (기존 기능)
OOS_TABLE_NAME = "oos_validation_log"    # Phase 2: 검증 결과 저장 (신규 기능)

def run_optimization(fast_mode: bool = False):
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

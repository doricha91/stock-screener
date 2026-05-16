# MFU-PAPER8-3 작업 지시문: paper drawdown / MDD 계산

## 목적

`paper_equity_curve.csv`를 기반으로 paper 계좌의 drawdown 시계열과 MDD를 계산한다.

이번 MFU의 목표는 equity curve 이후 단계로, 계좌가 고점 대비 얼마나 하락했는지 확인할 수 있는 CSV와 요약 리포트를 생성하는 것이다.

공식 기준:

- primary drawdown = primary_equity 기준
- primary_equity = total_equity_market_value
- secondary drawdown = secondary_equity 기준 참고값
- secondary_equity = total_equity_cost_basis

## 기준 브랜치

`gemini_cli_update`

## 배경

PAPER8-1:

- `paper_account_snapshot.csv` audit 통과
- `paper_position_snapshot.csv` audit 통과
- issue 0건

PAPER8-2:

- `paper_equity_curve.csv` 생성 완료
- primary_equity는 market value 기준
- secondary_equity는 cost basis 기준
- drawdown / MDD는 아직 구현하지 않음

이번 PAPER8-3에서는 drawdown / MDD만 추가한다.

## 입력 파일

- `outputs/paper_test/reports/paper_equity_curve.csv`

참고 가능:

- `outputs/paper_test/paper_account_snapshot.csv`
- `outputs/paper_test/reports/paper_equity_curve_summary.md`

## 산출물

핵심 CSV:

- `outputs/paper_test/reports/paper_drawdown.csv`

요약 markdown:

- `outputs/paper_test/reports/paper_drawdown_summary.md`

## drawdown CSV 컬럼

최소 컬럼:

- snapshot_date
- primary_equity
- primary_peak_equity
- primary_drawdown
- primary_drawdown_pct
- secondary_equity
- secondary_peak_equity
- secondary_drawdown
- secondary_drawdown_pct
- market_valuation_status

권장 추가 컬럼:

- is_primary_new_peak
- is_secondary_new_peak
- primary_mdd_to_date_pct
- secondary_mdd_to_date_pct

## 계산식

primary 기준:

- primary_peak_equity = 현재 날짜까지의 primary_equity 누적 최고값
- primary_drawdown = primary_equity - primary_peak_equity
- primary_drawdown_pct = primary_drawdown / primary_peak_equity * 100

secondary 기준:

- secondary_peak_equity = 현재 날짜까지의 secondary_equity 누적 최고값
- secondary_drawdown = secondary_equity - secondary_peak_equity
- secondary_drawdown_pct = secondary_drawdown / secondary_peak_equity * 100

MDD:

- primary_mdd_pct = primary_drawdown_pct의 최소값
- secondary_mdd_pct = secondary_drawdown_pct의 최소값

주의:

- drawdown은 보통 0 또는 음수다.
- primary_mdd_pct도 보통 0 또는 음수다.
- 이번 공식 MDD 기준은 primary_mdd_pct다.

## 구현 범위

권장 새 스크립트:

- `scripts/generate_paper_drawdown.py`

권장 함수:

- `load_equity_curve(path)`
- `build_paper_drawdown(equity_df)`
- `summarize_drawdown(drawdown_df)`
- `save_drawdown(df, output_path)`
- `save_drawdown_summary(summary, output_path)`

기존 equity curve 생성 스크립트를 대규모 리팩토링하지 않는다.

## 처리 정책

### 1. 날짜 처리

- snapshot_date를 datetime으로 변환
- 오름차순 정렬
- 중복 snapshot_date가 있으면 error 또는 명확한 warning
- 임의로 중복 row를 합치지 않는다

### 2. 숫자 처리

아래 컬럼은 숫자로 변환한다.

- primary_equity
- secondary_equity

변환 실패가 있으면 issue로 남기고 조용히 0 처리하지 않는다.

### 3. market valuation status

primary_equity는 market value 기준이므로 `market_valuation_status != success`인 row가 있으면 warning을 남긴다.

단, 이번 MFU에서는 row를 삭제하지 않는다. CSV에는 market_valuation_status를 그대로 보존한다.

### 4. row 수 한계 명시

현재 snapshot row 수가 적을 수 있으므로 summary에는 아래 주의 문구를 포함한다.

- snapshot row 수가 적어 drawdown/MDD 해석은 예비적입니다.

## 절대 금지

- `paper_execution_log.csv` 수정 금지
- `paper_account_snapshot.csv` 수정 금지
- `paper_position_snapshot.csv` 수정 금지
- `paper_equity_curve.csv` 수정 금지
- `outputs/front_test` 수정 금지
- DB 수정 금지
- `--commit` 실행 금지
- benchmark 구현 금지
- Sharpe / Sortino / CAGR 구현 금지
- monthly return 구현 금지
- closed trade 분석 금지
- 대규모 리팩토링 금지

## 테스트

권장 테스트:

- `tests/test_paper_drawdown.py`

필수 테스트:

1. primary_peak_equity가 누적 최고값으로 계산됨
2. primary_drawdown이 equity - peak으로 계산됨
3. primary_drawdown_pct가 올바르게 계산됨
4. secondary drawdown도 동일 방식으로 계산됨
5. primary_mdd_pct가 drawdown_pct의 최소값으로 계산됨
6. 첫 row drawdown은 0이어야 함
7. 날짜가 오름차순 정렬됨
8. 중복 snapshot_date 감지
9. 숫자 변환 불가 값 감지
10. market_valuation_status가 결과 CSV에 보존됨

예시 fixture:

- 2026-05-01 / primary_equity 100
- 2026-05-02 / primary_equity 110
- 2026-05-03 / primary_equity 105
- 2026-05-04 / primary_equity 120
- 2026-05-05 / primary_equity 90

기대:

- peak: 100, 110, 110, 120, 120
- drawdown: 0, 0, -5, 0, -30
- drawdown_pct 마지막: -25.0
- MDD: -25.0

## 검증 명령

- `set PYTHONPATH=.`
- `python -m pytest tests/test_paper_drawdown.py -q`
- `python -m pytest tests/test_paper_equity_curve.py -q`
- `python -m pytest tests/test_paper_performance_input_audit.py -q`
- `python -m py_compile scripts/generate_paper_drawdown.py`
- `python scripts/generate_paper_drawdown.py`

확인:

- `outputs/paper_test/reports/paper_drawdown.csv` 생성
- `outputs/paper_test/reports/paper_drawdown_summary.md` 생성
- equity curve row 수와 drawdown row 수 일치
- primary_mdd_pct 값 확인
- secondary_mdd_pct 값 확인

## 성공 기준

- `paper_drawdown.csv` 생성
- `paper_drawdown_summary.md` 생성
- primary drawdown은 market value 기준으로 계산
- secondary drawdown은 cost basis 기준으로 계산
- primary MDD 계산
- secondary MDD 계산
- market_valuation_status 보존
- 원본 snapshot/equity CSV 수정 없음
- `outputs/front_test` 변경 없음
- benchmark / Sharpe / CAGR 미구현

## 결과 보고 형식

5천자 이내.

포함 항목:

1. Summary
2. 변경 파일
3. 생성된 drawdown CSV 경로
4. 생성된 drawdown summary 경로
5. 입력 equity curve row 수
6. drawdown row 수
7. primary drawdown 기준
8. secondary drawdown 기준
9. latest drawdown
10. primary MDD
11. secondary MDD
12. warning 또는 issue
13. 테스트 결과
14. 원본 snapshot/equity CSV 변경 여부
15. outputs/front_test 변경 여부
16. 다음 단계 제안

반드시 명시:

- primary drawdown이 market value 기준인지
- secondary drawdown이 cost basis 기준인지
- benchmark/Sharpe/CAGR은 이번 범위에서 제외했는지
- PAPER8-4 performance summary markdown으로 넘어가도 되는지
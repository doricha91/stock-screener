# MFU-PAPER8-2 작업 지시문: paper equity curve 생성

## 목적

paper_account_snapshot.csv를 기반으로 paper 계좌의 equity curve를 생성한다.

이번 MFU의 목표는 날짜별 계좌 총자산 흐름을 CSV로 저장하는 것이다.

기준:
- primary_equity = total_equity_market_value
- secondary_equity = total_equity_cost_basis

성과 판단의 주 기준은 market value이고, cost basis는 원가 구조 확인용 보조 기준으로 함께 저장한다.

## 기준 브랜치

gemini_cli_update

## 배경

MFU-PAPER8-1 input audit 결과:
- paper_account_snapshot.csv issue 0건
- paper_position_snapshot.csv issue 0건
- account-position 교차 검증 통과
- execution log reducer와 최신 snapshot 일치

따라서 PAPER8-2에서는 equity curve 생성을 진행한다.

## 입력 파일

- outputs/paper_test/paper_account_snapshot.csv

참고 가능:
- outputs/paper_test/paper_position_snapshot.csv
- outputs/paper_test/reports/paper_performance_input_audit.md

## 산출물

핵심 산출물:
- outputs/paper_test/reports/paper_equity_curve.csv

필요하면 markdown 요약도 생성 가능:
- outputs/paper_test/reports/paper_equity_curve_summary.md

단, 이번 MFU의 핵심 산출물은 CSV다.

## equity curve CSV 컬럼

최소 컬럼:
- snapshot_date
- primary_equity
- secondary_equity
- cash
- positions_market_value
- positions_cost_value
- realized_pnl
- unrealized_pnl
- total_pnl
- market_valuation_status

권장 추가 컬럼:
- primary_return_from_start_pct
- secondary_return_from_start_pct
- cash_ratio_market
- position_ratio_market
- open_position_count

계산식:
- primary_equity = total_equity_market_value
- secondary_equity = total_equity_cost_basis
- primary_return_from_start_pct = (primary_equity / first_primary_equity - 1) * 100
- secondary_return_from_start_pct = (secondary_equity / first_secondary_equity - 1) * 100
- cash_ratio_market = cash / primary_equity
- position_ratio_market = positions_market_value / primary_equity

open_position_count는 가능하면 paper_position_snapshot.csv에서 날짜별 symbol 수를 계산한다.
불가능하면 이번 MFU에서는 생략 가능하다.

## 구현 범위

권장 새 스크립트:
- scripts/generate_paper_equity_curve.py

권장 함수:
- load_account_snapshot(path)
- build_paper_equity_curve(account_df, position_df=None)
- save_equity_curve(df, output_path)

기존 성과 input audit 스크립트와 중복되는 검증 로직은 재사용 가능하면 재사용한다.
단, 대규모 리팩토링은 하지 않는다.

## 처리 정책

### 1. 날짜 처리

- snapshot_date를 datetime으로 변환
- 오름차순 정렬
- 중복 snapshot_date가 있으면 error 또는 명확한 warning
- 중복 row를 임의로 합치지 않는다

### 2. 숫자 처리

아래 컬럼은 숫자로 변환한다.
- cash
- positions_cost_value
- total_equity_cost_basis
- positions_market_value
- total_equity_market_value
- realized_pnl
- unrealized_pnl
- total_pnl

변환 실패가 있으면 issue로 남기고, 조용히 0 처리하지 않는다.

### 3. market valuation status

primary_equity는 market value 기준이므로 market_valuation_status != success인 row가 있으면 warning을 남긴다.

단, 이번 MFU에서는 row를 삭제하지 말고 포함하되, status를 CSV에 남긴다.

### 4. 초기 equity 기준

수익률 계산 기준은 첫 번째 snapshot row다.

- first_primary_equity
- first_secondary_equity

초기값이 0 이하이면 return 계산은 하지 않고 warning 처리한다.

## 절대 금지

- paper_execution_log.csv 수정 금지
- paper_account_snapshot.csv 수정 금지
- paper_position_snapshot.csv 수정 금지
- outputs/front_test 수정 금지
- DB 수정 금지
- --commit 실행 금지
- drawdown / MDD 계산 금지
- benchmark / Sharpe / CAGR 구현 금지
- closed trade 분석 금지
- 대규모 리팩토링 금지

## 테스트

권장 테스트:
- tests/test_paper_equity_curve.py

필수 테스트:
1. primary_equity가 total_equity_market_value로 생성됨
2. secondary_equity가 total_equity_cost_basis로 생성됨
3. 날짜가 오름차순 정렬됨
4. 시작일 대비 수익률이 계산됨
5. cash_ratio_market / position_ratio_market 계산됨
6. market_valuation_status가 CSV에 유지됨
7. 중복 snapshot_date 감지
8. 숫자 변환 불가 값 감지

## 검증 명령

set PYTHONPATH=.

python -m pytest tests/test_paper_equity_curve.py -q
python -m pytest tests/test_paper_performance_input_audit.py -q

python -m py_compile scripts/generate_paper_equity_curve.py

실제 실행:
python scripts/generate_paper_equity_curve.py

확인:
- outputs/paper_test/reports/paper_equity_curve.csv 생성
- snapshot row 수와 equity curve row 수 일치
- primary_equity / secondary_equity 값 확인

## 성공 기준

- paper_equity_curve.csv 생성
- primary_equity = total_equity_market_value
- secondary_equity = total_equity_cost_basis
- 시작일 대비 primary/secondary return 계산
- cash / positions / realized / unrealized / total_pnl 포함
- 원본 snapshot CSV 수정 없음
- outputs/front_test 변경 없음
- drawdown / MDD / benchmark / Sharpe / CAGR 미구현

## 결과 보고 형식

5천자 이내.

포함 항목:
1. Summary
2. 변경 파일
3. 생성된 equity curve 경로
4. 입력 snapshot row 수
5. equity curve row 수
6. primary/secondary equity 기준
7. 최신 primary/secondary equity
8. 시작일 대비 수익률
9. warning 또는 issue
10. 테스트 결과
11. 원본 snapshot 변경 여부
12. outputs/front_test 변경 여부
13. 다음 단계 제안

반드시 명시:
- primary_equity가 market value 기준인지
- secondary_equity가 cost basis 기준인지
- drawdown/MDD는 이번 범위에서 제외했는지
- PAPER8-3 drawdown 계산으로 넘어가도 되는지
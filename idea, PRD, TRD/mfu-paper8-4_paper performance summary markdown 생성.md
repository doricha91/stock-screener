# MFU-PAPER8-4 작업 지시문: paper performance summary markdown 생성

## 목적

PAPER8-1~8-3에서 생성한 audit / equity curve / drawdown 산출물을 바탕으로, paper 계좌 성과를 한눈에 볼 수 있는 markdown summary report를 생성한다.

이번 MFU의 목표는 사람이 읽는 요약 리포트 생성이다.

핵심 산출물:
- outputs/paper_test/reports/paper_performance_summary.md

## 기준 브랜치

gemini_cli_update

## 배경

PAPER8-1:
- paper_account_snapshot.csv audit 통과
- paper_position_snapshot.csv audit 통과
- issue 0건

PAPER8-2:
- paper_equity_curve.csv 생성 완료
- primary_equity = total_equity_market_value
- secondary_equity = total_equity_cost_basis

PAPER8-3:
- paper_drawdown.csv 생성 완료
- primary drawdown = market value 기준
- secondary drawdown = cost basis 기준
- benchmark / Sharpe / CAGR은 아직 제외

이번 PAPER8-4에서는 위 산출물을 통합해 markdown summary를 만든다.

## 입력 파일

필수 입력:
- outputs/paper_test/reports/paper_equity_curve.csv
- outputs/paper_test/reports/paper_drawdown.csv

참고 입력:
- outputs/paper_test/paper_account_snapshot.csv
- outputs/paper_test/paper_position_snapshot.csv
- outputs/paper_test/reports/paper_performance_input_audit.md

## 산출물

생성 파일:
- outputs/paper_test/reports/paper_performance_summary.md

선택적으로 내부 요약 JSON은 만들 수 있으나, 이번 MFU의 핵심은 markdown이다.

## 리포트에 포함할 내용

### 1. Summary

포함:
- latest snapshot date
- primary equity
- secondary equity
- primary return from start
- secondary return from start
- latest primary drawdown
- primary MDD
- cash
- cash ratio
- open position count
- market valuation status

### 2. Equity Summary

표로 정리:
- start date
- latest date
- start primary equity
- latest primary equity
- primary return from start pct
- start secondary equity
- latest secondary equity
- secondary return from start pct

### 3. Drawdown Summary

표로 정리:
- latest primary drawdown pct
- primary MDD pct
- primary MDD date
- latest secondary drawdown pct
- secondary MDD pct
- secondary MDD date

공식 기준은 primary MDD다.

### 4. PnL Summary

최신 account snapshot 기준:
- realized_pnl
- unrealized_pnl
- total_pnl

가능하면 아래 관계도 명시:
- total_pnl = realized_pnl + unrealized_pnl

### 5. Allocation Summary

최신 equity curve 기준:
- cash
- positions_market_value
- cash_ratio_market
- position_ratio_market
- open_position_count

### 6. Open Positions

최신 position snapshot 기준으로 표 생성:
- symbol
- shares
- avg_price
- close_price
- cost_value
- market_value
- unrealized_pnl
- unrealized_return_pct

실제 컬럼명이 다르면 기존 audit에서 확인한 alias를 사용한다.
예:
- cost_basis 대신 cost_value
- market_price 대신 close_price

### 7. Warnings / Limitations

반드시 포함:
- snapshot row 수가 적으면 성과 해석은 예비적임
- benchmark / Sharpe / CAGR은 아직 포함하지 않음
- market_valuation_status가 success가 아닌 row가 있으면 경고
- 이 리포트는 paper-test용이며 실제 투자 성과가 아님

## 숫자 포맷 정책

markdown에서는 사람이 읽기 좋게 포맷한다.

권장:
- 금액: 소수점 둘째 자리, 천 단위 콤마
- 비율: 소수점 둘째 자리
- 주식 수량: 필요 시 정수 또는 소수점 둘째 자리
- NaN / None은 그대로 출력하지 말고 N/A로 표시

예:
- $99,667.06
- -0.33%
- 60.54%

CSV 원시값은 수정하지 않는다. 포맷팅은 markdown에만 적용한다.

## 구현 범위

권장 새 스크립트:
- scripts/generate_paper_performance_summary.py

권장 함수:
- load_equity_curve(path)
- load_drawdown(path)
- load_latest_account_snapshot(path)
- load_latest_position_snapshot(path)
- build_performance_summary(...)
- save_performance_summary(markdown, output_path)

기존 equity curve / drawdown 스크립트를 대규모 리팩토링하지 않는다.

## 처리 정책

### 1. 입력 파일 누락

필수 입력 파일이 없으면 명확한 error를 낸다.

자동으로 equity curve나 drawdown을 생성하지 않는다.
이번 MFU는 summary 생성만 담당한다.

### 2. 날짜 처리

- snapshot_date 기준 오름차순 정렬
- latest row는 가장 최근 snapshot_date 사용
- drawdown과 equity curve의 latest date가 다르면 warning 표시

### 3. market valuation status

- latest market_valuation_status가 success가 아니면 리포트 상단에 warning 표시
- row 삭제는 하지 않는다

### 4. row 수 한계

snapshot row 수가 적으면 limitation에 표시한다.

예:
- 현재 snapshot row 수가 3개뿐이므로 수익률과 MDD 해석은 예비적입니다.

## 절대 금지

- paper_execution_log.csv 수정 금지
- paper_account_snapshot.csv 수정 금지
- paper_position_snapshot.csv 수정 금지
- paper_equity_curve.csv 수정 금지
- paper_drawdown.csv 수정 금지
- outputs/front_test 수정 금지
- DB 수정 금지
- --commit 실행 금지
- benchmark 구현 금지
- Sharpe / Sortino / CAGR 구현 금지
- monthly return 구현 금지
- closed trade 분석 금지
- 대규모 리팩토링 금지

## 테스트

권장 테스트:
- tests/test_paper_performance_summary.py

필수 테스트:
1. performance summary markdown이 생성됨
2. latest primary equity가 리포트에 표시됨
3. primary return from start가 리포트에 표시됨
4. latest primary drawdown과 primary MDD가 표시됨
5. realized / unrealized / total PnL이 표시됨
6. cash ratio와 open position count가 표시됨
7. open positions table이 생성됨
8. 숫자 포맷이 과도한 raw float로 출력되지 않음
9. 입력 파일 누락 시 명확한 error
10. 원본 CSV를 수정하지 않음

## 검증 명령

set PYTHONPATH=.

python -m pytest tests/test_paper_performance_summary.py -q
python -m pytest tests/test_paper_equity_curve.py -q
python -m pytest tests/test_paper_drawdown.py -q
python -m pytest tests/test_paper_performance_input_audit.py -q

python -m py_compile scripts/generate_paper_performance_summary.py

실제 실행:
python scripts/generate_paper_performance_summary.py

확인:
- outputs/paper_test/reports/paper_performance_summary.md 생성
- 최신 equity / return / drawdown / MDD가 표시됨
- open positions 표가 표시됨
- benchmark / Sharpe / CAGR이 포함되지 않음
- 원본 CSV 변경 없음

## 성공 기준

- paper_performance_summary.md 생성
- primary equity는 market value 기준으로 표시
- secondary equity는 cost basis 기준으로 표시
- latest drawdown과 primary MDD 표시
- realized / unrealized / total PnL 표시
- cash ratio / position ratio / open position count 표시
- latest open positions 표시
- 숫자 포맷이 사람이 읽기 좋게 정리됨
- 원본 snapshot/equity/drawdown CSV 수정 없음
- outputs/front_test 변경 없음
- benchmark / Sharpe / CAGR 미구현

## 결과 보고 형식

5천자 이내.

포함 항목:
1. Summary
2. 변경 파일
3. 생성된 performance summary 경로
4. 입력 파일
5. latest equity 요약
6. latest drawdown / MDD 요약
7. PnL 요약
8. allocation 요약
9. open positions 요약
10. warning 또는 issue
11. 테스트 결과
12. 원본 CSV 변경 여부
13. outputs/front_test 변경 여부
14. 다음 단계 제안

반드시 명시:
- primary equity가 market value 기준인지
- secondary equity가 cost basis 기준인지
- benchmark / Sharpe / CAGR은 이번 범위에서 제외했는지
- PAPER8-5 report regeneration safety로 넘어가도 되는지
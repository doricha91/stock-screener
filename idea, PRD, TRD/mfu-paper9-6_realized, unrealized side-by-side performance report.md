# MFU-PAPER9-6 작업 지시문: realized / unrealized side-by-side symbol performance report

## 기준

브랜치: gemini_cli_update  
기준 SHA: c6ed2bce27a8f08afc64c882d8c7abe05849c303

## 목적

PAPER9-6의 목표는 종목별 realized 성과와 unrealized 성과를 **하나의 side-by-side 리포트로 병합**하는 것이다.

단, 이번 단계는 realized와 unrealized를 섞어 해석하지 않는다.  
핵심은 “합치되, 구분해서 보여주는 것”이다.

## 입력

필수 입력:

```text
outputs/paper_test/reports/paper_symbol_realized_performance.csv
outputs/paper_test/reports/paper_symbol_unrealized_performance.csv
```

참고 가능:

```text
outputs/paper_test/reports/paper_realized_ranking.csv
outputs/paper_test/reports/paper_realized_ranking_report.md
outputs/paper_test/reports/paper_symbol_unrealized_performance_summary.md
```

## 산출물

생성 파일:

```text
outputs/paper_test/reports/paper_symbol_side_by_side_performance.csv
outputs/paper_test/reports/paper_symbol_side_by_side_performance_summary.md
```

## 구현 범위

추가 권장 파일:

```text
core/paper_symbol_side_by_side_performance.py
scripts/generate_paper_symbol_side_by_side_performance.py
tests/test_paper_symbol_side_by_side_performance.py
docs/TRD/mfu_paper9_6_symbol_side_by_side_performance.md
```

## 핵심 원칙

### 1. 재계산하지 않는다

이번 단계에서는 realized PnL과 unrealized PnL을 새로 계산하지 않는다.

- realized 값은 `paper_symbol_realized_performance.csv`에서 가져온다.
- unrealized 값은 `paper_symbol_unrealized_performance.csv`에서 가져온다.

`paper_execution_log.csv` replay 금지.  
`paper_position_snapshot.csv` 재집계 금지.

### 2. side-by-side 구조를 유지한다

이번 리포트는 통합 리포트지만, 해석은 분리한다.

포함:
- realized_pnl
- unrealized_pnl
- total_pnl 참고값
- realized_trade_count
- open_shares
- open_market_value
- open_unrealized_return_pct
- realized-only / unrealized-only / both 상태 구분

주의:
`total_pnl = realized_pnl + unrealized_pnl`은 계산하되, main interpretation은 realized/unrealized 분리 기준으로 유지한다.

### 3. symbol universe는 outer join

realized에만 있는 종목, unrealized에만 있는 종목, 둘 다 있는 종목을 모두 포함한다.

상태 컬럼:

```text
symbol_status
```

값:

```text
realized_only
unrealized_only
realized_and_unrealized
```

현재 예시:
- VRSN, CPAY, CF는 realized_only 가능성이 높음
- BRK-B, F, GEN은 unrealized_only 가능성이 높음

## CSV 컬럼

`paper_symbol_side_by_side_performance.csv` 최소 컬럼:

```text
symbol
symbol_status
realized_pnl
unrealized_pnl
total_pnl
realized_trade_count
win_count
loss_count
flat_count
win_rate
avg_realized_return_pct
open_shares
open_market_value
open_cost_basis
open_unrealized_return_pct
position_weight_market
cost_basis_method
entry_basis_type
lot_linking_status
snapshot_date
```

권장 추가 컬럼:

```text
realized_pnl_rank
unrealized_pnl_rank
total_pnl_rank
total_pnl_contribution_pct
risk_note
```

계산 기준:

```text
realized_pnl = 없으면 0
unrealized_pnl = 없으면 0
total_pnl = realized_pnl + unrealized_pnl
```

주의:
- realized 없음과 realized_pnl 0은 구분이 필요하므로 `symbol_status`를 반드시 둔다.
- open position이 없으면 open_shares/open_market_value는 0 또는 blank 중 하나로 통일한다.
- ranking은 total_pnl 기준 보조 지표로만 사용한다.

## Summary markdown 포함 내용

`paper_symbol_side_by_side_performance_summary.md`에 포함:

1. 생성 일시
2. 입력 파일 경로
3. 출력 CSV 경로
4. symbol count
5. realized_only count
6. unrealized_only count
7. realized_and_unrealized count
8. total realized PnL
9. total unrealized PnL
10. total PnL 참고값
11. top total PnL symbols
12. worst total PnL symbols
13. top unrealized PnL symbols
14. worst realized PnL symbols
15. warnings
16. limitations

Limitations에 반드시 포함:

```text
- This report shows realized and unrealized performance side by side.
- total_pnl is a reference metric, not a lot-matched accounting result.
- Realized PnL is average-cost SELL-event based.
- Unrealized PnL is current open-position snapshot based.
- FIFO/LIFO/lot ledger accounting is not implemented.
- open_date and holding_days are intentionally excluded.
- Metrics are preliminary when trade count or snapshot history is small.
```

## 절대 금지

```text
- paper_execution_log.csv 수정 금지
- paper_account_snapshot.csv 수정 금지
- paper_position_snapshot.csv 수정 금지
- 기존 report CSV 수정 금지
- outputs/front_test 수정 금지
- DB 수정 금지
- --commit 실행 금지
- realized PnL 재계산 금지
- unrealized PnL 재계산 금지
- paper_execution_log replay 금지
- FIFO / lot ledger 구현 금지
- open_date / holding_days 계산 금지
- actionable commentary 생성 금지
- 대규모 리팩토링 금지
```

## 테스트

테스트 파일:

```text
tests/test_paper_symbol_side_by_side_performance.py
```

필수 테스트:

1. realized_only symbol 포함
2. unrealized_only symbol 포함
3. realized_and_unrealized symbol 포함
4. outer join 동작 확인
5. total_pnl = realized_pnl + unrealized_pnl
6. symbol_status 계산
7. realized 없는 경우 realized fields 기본값 처리
8. unrealized 없는 경우 open position fields 기본값 처리
9. top/worst total PnL ranking
10. limitations markdown 포함
11. 빈 realized 입력 처리
12. 빈 unrealized 입력 처리
13. 필수 컬럼 누락 감지
14. 숫자 변환 불가 값 감지

## 검증 명령

```bat
set PYTHONPATH=.

python -m pytest tests/test_paper_symbol_side_by_side_performance.py -q
python -m py_compile core/paper_symbol_side_by_side_performance.py
python -m py_compile scripts/generate_paper_symbol_side_by_side_performance.py
python scripts/generate_paper_symbol_side_by_side_performance.py
```

생성 확인:

```text
outputs/paper_test/reports/paper_symbol_side_by_side_performance.csv
outputs/paper_test/reports/paper_symbol_side_by_side_performance_summary.md
```

## 성공 기준

- realized/unrealized side-by-side CSV가 생성된다.
- realized_only / unrealized_only / realized_and_unrealized symbol이 모두 표현된다.
- total_pnl 참고값이 생성된다.
- realized와 unrealized를 재계산하지 않는다.
- 기존 원본 CSV와 기존 report CSV를 수정하지 않는다.
- outputs/front_test는 수정하지 않는다.
- 테스트가 통과한다.

## 결과 보고 형식

5천자 이내.

포함:

1. Summary
2. 변경 파일
3. 생성된 산출물 경로
4. symbol count
5. realized_only / unrealized_only / both count
6. total realized / unrealized / total PnL
7. top/worst total PnL symbols
8. 제외한 항목
9. 테스트 결과
10. 원본 CSV 변경 여부
11. outputs/front_test 변경 여부
12. warning / limitation
13. 다음 단계 제안

반드시 명시:

```text
이번 PAPER9-6은 realized/unrealized side-by-side report이며, actionable commentary는 포함하지 않는다.
```
# MFU-PAPER9-5 작업 지시문: symbol-level open position / unrealized performance 생성

## 기준

브랜치: gemini_cli_update  
기준 SHA: c6ed2bce27a8f08afc64c882d8c7abe05849c303

## 목적

PAPER9-5의 목표는 최신 `paper_position_snapshot.csv`를 기반으로 **현재 보유 중인 open position의 종목별 unrealized performance**를 생성하는 것이다.

이번 단계는 realized 성과와 통합하지 않는다.  
PAPER9-2~9-4가 청산된 SELL-event 성과를 다뤘다면, PAPER9-5는 **현재 보유 중인 포지션의 평가손익**만 다룬다.

## 입력

필수 입력:

```text
outputs/paper_test/paper_position_snapshot.csv
```

참고/검증용 입력:

```text
outputs/paper_test/paper_account_snapshot.csv
```

## 산출물

생성 파일:

```text
outputs/paper_test/reports/paper_symbol_unrealized_performance.csv
outputs/paper_test/reports/paper_symbol_unrealized_performance_summary.md
```

## 구현 범위

추가 권장 파일:

```text
core/paper_symbol_unrealized_performance.py
scripts/generate_paper_symbol_unrealized_performance.py
tests/test_paper_symbol_unrealized_performance.py
docs/TRD/mfu_paper9_5_symbol_unrealized_performance.md
```

## 핵심 원칙

### 1. 최신 snapshot만 사용한다

`paper_position_snapshot.csv`에서 가장 최신 `snapshot_date`를 찾고, 해당 날짜의 open position row만 사용한다.

이전 날짜 position row는 이번 리포트에 포함하지 않는다.

### 2. unrealized 성과만 다룬다

포함:
- 현재 보유 종목
- shares
- avg_price
- market_price 또는 close_price
- cost_basis
- market_value
- unrealized_pnl
- unrealized_return_pct
- position weight

제외:
- realized PnL
- closed trade
- SELL-event journal
- realized ranking
- total PnL 통합
- FIFO / lot ledger
- open_date / holding_days
- benchmark / Sharpe / CAGR / MDD

### 3. account snapshot과 교차 검증한다

가능하면 최신 `paper_account_snapshot.csv`의 같은 날짜 row와 비교한다.

검증:
```text
sum(position.market_value) ≈ account.positions_market_value
sum(position.cost_basis) ≈ account.positions_cost_value
sum(position.unrealized_pnl) ≈ account.unrealized_pnl
```

허용 오차:
```text
tolerance = 0.05
```

불일치가 있으면 summary markdown에 warning으로 남긴다.  
이번 단계에서 원본 CSV를 수정하지 않는다.

## CSV 컬럼

`paper_symbol_unrealized_performance.csv` 최소 컬럼:

```text
snapshot_date
symbol
shares
avg_price
market_price
cost_basis
market_value
unrealized_pnl
unrealized_return_pct
position_weight_market
position_status
```

권장 추가 컬럼:

```text
unrealized_pnl_rank
market_value_rank
unrealized_return_rank
cost_basis_method
valuation_status
```

계산 기준:

```text
position_weight_market = market_value / total_positions_market_value
unrealized_pnl = market_value - cost_basis
unrealized_return_pct = unrealized_pnl / cost_basis * 100
```

단, 입력 CSV에 이미 `unrealized_pnl`, `unrealized_return_pct`가 있으면 기본적으로 입력값을 사용하고, 재계산값과 차이가 크면 warning을 남긴다.

## Summary markdown 포함 내용

`paper_symbol_unrealized_performance_summary.md`에 포함:

1. 생성 일시
2. 입력 파일 경로
3. 출력 CSV 경로
4. latest snapshot_date
5. open symbol count
6. total market value
7. total cost basis
8. total unrealized PnL
9. best unrealized PnL symbols
10. worst unrealized PnL symbols
11. best unrealized return symbols
12. worst unrealized return symbols
13. largest market value symbols
14. account snapshot cross-check 결과
15. warnings
16. limitations

Limitations에 반드시 포함:

```text
- This report summarizes current open-position unrealized performance only.
- Realized PnL and closed trades are not included.
- Total symbol performance will be handled in a later MFU.
- FIFO/LIFO/lot ledger accounting is not implemented.
- open_date and holding_days are intentionally excluded.
```

## 절대 금지

```text
- paper_execution_log.csv 수정 금지
- paper_account_snapshot.csv 수정 금지
- paper_position_snapshot.csv 수정 금지
- paper_realized_trade_journal.csv 수정 금지
- paper_symbol_realized_performance.csv 수정 금지
- outputs/front_test 수정 금지
- DB 수정 금지
- --commit 실행 금지
- realized PnL 통합 금지
- total PnL 통합 금지
- FIFO / lot ledger 구현 금지
- open_date / holding_days 계산 금지
- 기존 reducer / EOD writer 변경 금지
- 대규모 리팩토링 금지
```

## 테스트

테스트 파일:

```text
tests/test_paper_symbol_unrealized_performance.py
```

필수 테스트:

1. 최신 snapshot_date 선택
2. 최신 날짜 row만 포함
3. market_value 기준 position_weight 계산
4. unrealized_pnl 계산 또는 입력값 유지
5. unrealized_return_pct 계산 또는 입력값 유지
6. best/worst unrealized PnL ranking
7. best/worst unrealized return ranking
8. largest market value ranking
9. account snapshot 교차 검증 통과
10. account snapshot 불일치 warning
11. 빈 position snapshot 처리
12. 필수 컬럼 누락 감지
13. 숫자 변환 불가 값 감지
14. summary markdown에 limitations 포함

## 검증 명령

```bat
set PYTHONPATH=.

python -m pytest tests/test_paper_symbol_unrealized_performance.py -q
python -m py_compile core/paper_symbol_unrealized_performance.py
python -m py_compile scripts/generate_paper_symbol_unrealized_performance.py
python scripts/generate_paper_symbol_unrealized_performance.py
```

생성 확인:

```text
outputs/paper_test/reports/paper_symbol_unrealized_performance.csv
outputs/paper_test/reports/paper_symbol_unrealized_performance_summary.md
```

## 성공 기준

- 최신 open position 기준 unrealized performance CSV가 생성된다.
- summary markdown이 생성된다.
- realized PnL과 통합하지 않는다.
- account snapshot과 교차 검증 결과를 남긴다.
- 원본 paper CSV와 기존 report CSV는 수정하지 않는다.
- outputs/front_test는 수정하지 않는다.
- 테스트가 통과한다.

## 결과 보고 형식

5천자 이내.

포함:

1. Summary
2. 변경 파일
3. 생성된 산출물 경로
4. latest snapshot_date
5. open symbol count
6. total market value / cost basis / unrealized PnL
7. best/worst unrealized symbols
8. account snapshot cross-check 결과
9. 제외한 항목
10. 테스트 결과
11. 원본 CSV 변경 여부
12. outputs/front_test 변경 여부
13. warning / limitation
14. 다음 단계 제안

반드시 명시:

```text
이번 PAPER9-5는 current open-position unrealized performance이며, realized PnL과 total PnL은 포함하지 않는다.
```
# MFU-PAPER9-3 작업 지시문: symbol-level realized performance 집계

## 기준

브랜치: gemini_cli_update  
기준 SHA: c6ed2bce27a8f08afc64c882d8c7abe05849c303

## 목적

PAPER9-3의 목표는 PAPER9-2에서 생성한 `paper_realized_trade_journal.csv`를 기반으로 **종목별 realized performance**를 집계하는 것이다.

이번 단계는 **실현손익 기준 종목별 성과 요약**만 만든다.

명확히 제외:
- unrealized PnL 통합 제외
- open position 평가손익 통합 제외
- FIFO / LIFO 제외
- lot ledger 제외
- open_date 제외
- holding_days 제외
- benchmark 비교 제외
- Sharpe / CAGR / MDD 제외

## 배경

PAPER9-2 완료 결과:

- `outputs/paper_test/reports/paper_realized_trade_journal.csv` 생성
- `outputs/paper_test/reports/paper_realized_trade_journal_summary.md` 생성
- realized journal row 수: 3
- total realized PnL: -612.54
- win/loss/flat count: 0 / 3 / 0
- 계산 정책: average_cost
- entry basis: position_avg_price_before_sell
- lot linking: not_applicable

PAPER9-3에서는 이 realized trade journal을 입력으로 사용해 symbol 단위 요약 CSV와 markdown summary를 만든다.

## 구현 범위

추가 권장 파일:

```text
core/paper_symbol_realized_performance.py
scripts/generate_paper_symbol_realized_performance.py
tests/test_paper_symbol_realized_performance.py
```

생성 산출물:

```text
outputs/paper_test/reports/paper_symbol_realized_performance.csv
outputs/paper_test/reports/paper_symbol_realized_performance_summary.md
```

입력 파일:

```text
outputs/paper_test/reports/paper_realized_trade_journal.csv
```

## 핵심 설계 원칙

### 1. PAPER9-2 산출물을 source of truth로 사용한다

이번 단계에서는 `paper_execution_log.csv`를 다시 replay하지 않는다.  
PAPER9-2에서 생성한 realized trade journal을 입력으로 사용한다.

이유:
- realized PnL 계산 정책은 PAPER9-2에서 이미 고정했다.
- PAPER9-3은 계산 재구현이 아니라 집계 단계다.
- 중복 계산 로직을 피한다.

### 2. realized 성과만 집계한다

이번 CSV는 closed/open 통합 성과가 아니다.

포함:
- SELL event 기준 realized PnL
- realized return
- win/loss/flat count
- symbol별 실현손익 합계

제외:
- 현재 보유 중인 open position
- unrealized PnL
- market value
- cost basis
- total PnL

### 3. average-cost 정책을 유지한다

입력 journal의 아래 컬럼이 모두 동일한지 검증한다.

```text
cost_basis_method = average_cost
entry_basis_type = position_avg_price_before_sell
lot_linking_status = not_applicable
```

다른 값이 섞여 있으면 warning 또는 error로 보고한다.  
이번 단계에서는 여러 cost basis method 혼합 집계를 지원하지 않는다.

## CSV 컬럼

`paper_symbol_realized_performance.csv` 최소 컬럼:

```text
symbol
realized_trade_count
total_realized_pnl
win_count
loss_count
flat_count
win_rate
loss_rate
flat_rate
avg_realized_pnl
avg_realized_return_pct
best_trade_pnl
worst_trade_pnl
best_trade_return_pct
worst_trade_return_pct
total_shares_closed
cost_basis_method
entry_basis_type
lot_linking_status
```

권장 추가 컬럼:

```text
first_close_date
last_close_date
positive_realized_pnl
negative_realized_pnl
gross_profit
gross_loss
profit_factor
```

계산 기준:

```text
win_count = realized_pnl > 0
loss_count = realized_pnl < 0
flat_count = realized_pnl == 0

win_rate = win_count / realized_trade_count
loss_rate = loss_count / realized_trade_count
flat_rate = flat_count / realized_trade_count

avg_realized_pnl = total_realized_pnl / realized_trade_count
avg_realized_return_pct = mean(realized_return_pct)

gross_profit = sum(realized_pnl where realized_pnl > 0)
gross_loss = abs(sum(realized_pnl where realized_pnl < 0))
profit_factor = gross_profit / gross_loss
```

주의:
- `gross_loss = 0`이면 profit_factor는 빈값 또는 `N/A`로 둔다.
- `realized_trade_count = 0`인 symbol row는 만들지 않는다.
- 전체 입력 row가 0개면 빈 CSV + warning summary를 생성할지, error 처리할지 명확히 정한다. 권장: 빈 CSV와 warning summary 생성.

## Summary markdown 포함 내용

`paper_symbol_realized_performance_summary.md`에 포함:

1. 생성 일시
2. 입력 파일 경로
3. 출력 CSV 경로
4. symbol count
5. total realized trade count
6. total realized PnL
7. total win/loss/flat count
8. overall win rate
9. top realized PnL symbols
10. worst realized PnL symbols
11. cost basis method
12. entry basis type
13. lot linking status
14. warnings
15. limitations

Limitations에 반드시 명시:

```text
- This report summarizes realized SELL-event performance only.
- Unrealized PnL and current open positions are not included.
- FIFO/LIFO/lot-matched closed trade accounting is not implemented.
- open_date and holding_days are intentionally excluded.
- Metrics are preliminary when realized trade count is small.
```

## 절대 금지

```text
- paper_execution_log.csv 수정 금지
- paper_account_snapshot.csv 수정 금지
- paper_position_snapshot.csv 수정 금지
- paper_realized_trade_journal.csv 수정 금지
- outputs/front_test 수정 금지
- DB 수정 금지
- --commit 실행 금지
- 기존 EOD writer 변경 금지
- 기존 reducer 변경 금지
- realized PnL 계산 로직 재구현 금지
- FIFO 구현 금지
- lot ledger 구현 금지
- open_date / holding_days 계산 금지
- unrealized PnL 통합 금지
- 대규모 리팩토링 금지
```

## 테스트

테스트 파일:

```text
tests/test_paper_symbol_realized_performance.py
```

필수 테스트:

1. 단일 symbol, 단일 realized row 집계
2. 단일 symbol, 여러 realized row 집계
3. 여러 symbol 집계
4. win/loss/flat count 계산
5. win_rate/loss_rate/flat_rate 계산
6. avg_realized_pnl 계산
7. avg_realized_return_pct 계산
8. best/worst trade pnl 계산
9. total_shares_closed 계산
10. gross_profit/gross_loss/profit_factor 계산
11. gross_loss가 0일 때 profit_factor 처리
12. cost_basis_method / entry_basis_type / lot_linking_status 유지
13. 입력 row가 0개일 때 처리
14. 필수 컬럼 누락 감지
15. 숫자 변환 불가 값 감지

## 검증 명령

```bat
set PYTHONPATH=.

python -m pytest tests/test_paper_symbol_realized_performance.py -q
python -m py_compile core/paper_symbol_realized_performance.py
python -m py_compile scripts/generate_paper_symbol_realized_performance.py
python scripts/generate_paper_symbol_realized_performance.py
```

생성 확인:

```text
outputs/paper_test/reports/paper_symbol_realized_performance.csv
outputs/paper_test/reports/paper_symbol_realized_performance_summary.md
```

추가 확인:

```text
outputs/front_test가 변경되지 않았는지 확인
paper_execution_log.csv가 변경되지 않았는지 확인
paper_account_snapshot.csv가 변경되지 않았는지 확인
paper_position_snapshot.csv가 변경되지 않았는지 확인
paper_realized_trade_journal.csv가 변경되지 않았는지 확인
```

## 성공 기준

- symbol-level realized performance CSV가 생성된다.
- 입력은 PAPER9-2의 realized trade journal을 사용한다.
- 종목별 realized PnL, win/loss/flat, win rate, avg return이 계산된다.
- unrealized PnL과 open position은 포함하지 않는다.
- FIFO / lot ledger / open_date / holding_days는 구현하지 않는다.
- 원본 paper CSV와 realized trade journal은 수정하지 않는다.
- outputs/front_test는 수정하지 않는다.
- 테스트가 통과한다.

## 결과 보고 형식

5천자 이내.

포함:

1. Summary
2. 변경 파일
3. 생성된 산출물 경로
4. symbol count
5. total realized trade count
6. total realized PnL
7. top/worst symbols
8. average-cost 정책 유지 여부
9. 제외한 항목: unrealized PnL, FIFO, lot ledger, open_date, holding_days
10. 테스트 결과
11. 원본 CSV 변경 여부
12. outputs/front_test 변경 여부
13. warning / limitation
14. 다음 단계 제안

반드시 명시:

```text
이번 PAPER9-3은 realized SELL-event 기준 symbol performance이며, open position/unrealized PnL은 포함하지 않는다.
```
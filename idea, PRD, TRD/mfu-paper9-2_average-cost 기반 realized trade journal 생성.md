# MFU-PAPER9-2 작업 지시문: average-cost 기반 realized trade journal 생성

## 기준

브랜치: gemini_cli_update  
기준 SHA: c6ed2bce27a8f08afc64c882d8c7abe05849c303

## 목적

PAPER9-2의 목표는 `paper_execution_log.csv`를 replay해서 **SELL 이벤트 기준 realized trade journal**을 생성하는 것이다.

이번 단계는 **average-cost 기반 realized trade journal**만 구현한다.

명확히 제외:
- FIFO 구현 제외
- LIFO 구현 제외
- lot ledger 구현 제외
- open_date 계산 제외
- holding_days 계산 제외
- BUY-SELL lot matching 제외

현재 reducer는 SELL 시점의 `existing.avg_price`를 기준으로 realized PnL을 계산하는 average cost 방식이다.  
따라서 이번 MFU에서는 기존 회계정책과 일치하는 realized trade journal을 만든다.

## 배경

PAPER9-1 조사 결론:

- `paper_execution_log.csv`에는 BUY/SELL 실행 row가 있다.
- BUY shares는 양수, SELL shares는 음수다.
- 현재 reducer는 `paper_execution_log.csv`를 전건 replay해서 현재 cash / positions / cumulative realized_pnl을 계산한다.
- 현재 realized PnL은 FIFO가 아니라 average cost 기준이다.
- `trade_id`는 dedupe용이지 BUY-SELL closed trade linking key가 아니다.
- 거래별 realized ledger는 아직 없다.
- lot ledger가 없으므로 정확한 open_date / holding_days / FIFO matching은 현재 구조로 계산할 수 없다.

따라서 PAPER9-2에서는 **SELL row마다 realized PnL row를 파생 생성**한다.

## 구현 범위

추가 권장 파일:

```text
core/paper_realized_trade_journal.py
scripts/generate_paper_realized_trade_journal.py
tests/test_paper_realized_trade_journal.py
```

생성 산출물:

```text
outputs/paper_test/reports/paper_realized_trade_journal.csv
outputs/paper_test/reports/paper_realized_trade_journal_summary.md
```

이번 단계에서는 `paper_closed_trades.csv`라는 이름은 사용하지 않는다.  
이유: 현재 구현은 엄밀한 closed trade lot matching이 아니라 SELL event 기준 realized journal이기 때문이다.

## 핵심 설계 원칙

### 1. 기존 reducer / EOD writer는 변경하지 않는다

아래 파일은 읽기만 한다.

```text
core/paper_account_state.py
core/paper_execution_log.py
scripts/run_paper_eod_update.py
```

기존 paper EOD 흐름을 바꾸지 않고, realized trade journal은 후처리 report generator로 만든다.

### 2. average-cost 정책을 명시한다

출력 CSV와 summary markdown에 아래 사실을 명확히 남긴다.

```text
cost_basis_method = average_cost
entry_basis_type = position_avg_price_before_sell
lot_linking_status = not_applicable
```

의미:

- `average_cost`: 종목별 평균단가 기준
- `position_avg_price_before_sell`: SELL 직전 보유 포지션의 평균단가를 entry basis로 사용
- `not_applicable`: lot ledger가 없으므로 BUY lot과 SELL row를 연결하지 않음

### 3. SELL row 기준으로 journal row를 만든다

BUY row는 포지션 평균단가 갱신에만 사용한다.  
SELL row가 발생할 때만 realized trade journal row를 생성한다.

SELL row 처리 공식:

```text
shares_closed = abs(sell_shares)
entry_price_basis = position.avg_price before SELL
exit_price = sell_price
realized_pnl = (exit_price - entry_price_basis) * shares_closed
realized_return_pct = (exit_price / entry_price_basis - 1) * 100
```

## CSV 컬럼

최소 컬럼:

```text
close_date
symbol
shares_closed
entry_price_basis
exit_price
realized_pnl
realized_return_pct
close_trade_id
source
reason
cost_basis_method
entry_basis_type
lot_linking_status
```

권장 추가 컬럼:

```text
regime
gross_amount
notes
rec_shares
rec_price
position_shares_before_sell
position_shares_after_sell
avg_price_before_sell
cash_after_trade
realized_pnl_cumulative_after_trade
realized_pnl_by_symbol_after_trade
```

제외 컬럼:

```text
open_date
holding_days
lot_id
matched_buy_trade_id
fifo_entry_price
lifo_entry_price
```

제외 이유:
현재 구조에는 lot ledger가 없고, 평균단가 방식에서는 단일 open_date / holding_days 정의가 애매하다.

## 구현 세부사항

### 1. trade row 로딩

입력:

```text
outputs/paper_test/paper_execution_log.csv
```

기존 `PAPER_EXECUTION_LOG_COLUMNS`와 실제 CSV 컬럼을 기준으로 로딩한다.

필수 검증:

- `trade_id` 존재
- `date` 존재
- `symbol` 존재
- `side` in BUY/SELL
- `shares` 정수 변환 가능
- `price` 숫자 변환 가능
- BUY shares > 0
- SELL shares < 0
- price > 0

### 2. replay 로직

새 helper에서 독립 replay를 수행한다.

권장 함수:

```python
load_paper_execution_rows(path: Path) -> list[dict]
build_average_cost_realized_trade_journal(trade_rows: list[dict]) -> list[dict]
write_realized_trade_journal(rows: list[dict], output_path: Path) -> None
render_realized_trade_journal_summary(rows: list[dict]) -> str
```

replay 중 내부 상태:

```text
cash
positions[symbol].shares
positions[symbol].avg_price
realized_pnl
realized_pnl_by_symbol
applied_trade_ids
```

기존 `PaperAccountState`를 재사용해도 되지만, SELL 직전 avg_price / shares_before / shares_after를 journal에 남겨야 하므로 별도 replay helper가 더 명확하면 새로 작성한다.

### 3. duplicate trade_id 처리

기존 reducer처럼 이미 적용된 `trade_id`는 중복 적용하지 않는다.

중복 발견 시:
- 조용히 두 번 계산하지 않는다.
- summary markdown에 duplicate skipped count를 남긴다.
- 필요하면 warning list에 남긴다.

### 4. error 처리

아래 상황은 명확히 error 처리한다.

```text
SELL인데 보유 수량 없음
SELL 수량이 보유 수량보다 큼
BUY인데 현금 부족
shares 변환 실패
price 변환 실패
unsupported side
```

이번 단계에서는 invalid row를 임의 보정하지 않는다.

## Summary markdown 포함 내용

`paper_realized_trade_journal_summary.md`에 포함:

1. 생성 일시
2. 입력 파일 경로
3. 출력 CSV 경로
4. cost basis method: average_cost
5. entry basis type: position_avg_price_before_sell
6. lot linking status: not_applicable
7. total realized trade count
8. total realized PnL
9. win count / loss count / flat count
10. win rate
11. avg realized return pct
12. total shares closed
13. symbols included
14. duplicate skipped count
15. warnings
16. limitations

Limitations에 반드시 명시:

```text
- This journal is SELL-event based, not lot-matched closed trade accounting.
- open_date and holding_days are intentionally excluded.
- FIFO/LIFO/specific-lot accounting is not implemented.
- entry_price_basis uses average cost immediately before each SELL.
```

## 절대 금지

```text
- paper_execution_log.csv 수정 금지
- paper_account_snapshot.csv 수정 금지
- paper_position_snapshot.csv 수정 금지
- outputs/front_test 수정 금지
- DB 수정 금지
- --commit 실행 금지
- 기존 EOD writer 변경 금지
- 기존 reducer 동작 변경 금지
- FIFO 구현 금지
- lot ledger 구현 금지
- open_date / holding_days 계산 금지
- 대규모 리팩토링 금지
```

## 테스트

테스트 파일:

```text
tests/test_paper_realized_trade_journal.py
```

필수 테스트:

1. BUY만 있으면 realized journal row가 0개
2. 단일 BUY 후 partial SELL 시 realized row 1개 생성
3. 단일 BUY 후 full SELL 시 realized row 1개 생성
4. 여러 BUY 후 SELL 시 평균단가 기준 realized_pnl 계산
5. SELL 후 remaining shares와 avg_price 유지 확인
6. full SELL 후 position 제거 확인
7. duplicate trade_id는 중복 계산하지 않음
8. SELL 수량이 보유 수량보다 크면 error
9. SELL인데 보유 포지션이 없으면 error
10. CSV에 cost_basis_method / entry_basis_type / lot_linking_status 포함
11. open_date / holding_days 컬럼이 생성되지 않음
12. summary markdown에 limitations 포함

## 검증 명령

```bat
set PYTHONPATH=.

python -m pytest tests/test_paper_realized_trade_journal.py -q
python -m py_compile core/paper_realized_trade_journal.py
python -m py_compile scripts/generate_paper_realized_trade_journal.py
python scripts/generate_paper_realized_trade_journal.py
```

생성 확인:

```text
outputs/paper_test/reports/paper_realized_trade_journal.csv
outputs/paper_test/reports/paper_realized_trade_journal_summary.md
```

추가 확인:

```text
outputs/front_test가 변경되지 않았는지 확인
paper_execution_log.csv가 변경되지 않았는지 확인
paper_account_snapshot.csv가 변경되지 않았는지 확인
paper_position_snapshot.csv가 변경되지 않았는지 확인
```

## 성공 기준

- average-cost 기반 realized trade journal CSV가 생성된다.
- SELL event 기준으로 realized PnL이 계산된다.
- 기존 reducer의 average-cost 계산 방식과 일치한다.
- FIFO / lot ledger / open_date / holding_days는 구현하지 않는다.
- cost_basis_method / entry_basis_type / lot_linking_status가 명시된다.
- summary markdown에 한계가 명확히 기록된다.
- 원본 paper CSV는 수정하지 않는다.
- outputs/front_test는 수정하지 않는다.
- 테스트가 통과한다.

## 결과 보고 형식

5천자 이내.

포함:

1. Summary
2. 변경 파일
3. 생성된 산출물 경로
4. realized journal row 수
5. total realized PnL
6. win/loss/flat count
7. average-cost 계산 방식 설명
8. 제외한 항목: FIFO, lot ledger, open_date, holding_days
9. 테스트 결과
10. 원본 CSV 변경 여부
11. outputs/front_test 변경 여부
12. warning / limitation
13. 다음 단계 제안

반드시 명시:

```text
이번 PAPER9-2는 closed trade lot ledger가 아니라 average-cost SELL-event realized trade journal이다.
```
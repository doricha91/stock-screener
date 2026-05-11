# Codex Task: MFU-PAPER4-4B paper_current_state serializer 추가

## 목표

`PaperAccountState`를 기존 front-test `current_state`와 호환되는 JSON dict로 변환하는 helper를 추가한다.

이번 단계는 **serializer 구현 + 테스트**까지만 한다.  
실제 `paper_current_state_YYYYMMDD.json` 저장은 하지 않는다.

## 배경

조사 결과 기존 current_state는 nested positions 구조가 아니다.

필수 호환 필드:

```text
current_symbols
current_cash_ratio
current_hedge_ratio
absolute_cash
shares
avg_price
highest_prices
```

권장 optional 필드:

```text
highest_price_meta
hedge_symbols
```

사용자 결정:

```text
purpose: paper EOD 공식 state
save timing: --commit 이후
path: outputs/paper_test/paper_current_state_YYYYMMDD.json
schema: 기존 front-test current_state 호환
highest_price: trade price 기준
existing file: 백업 후 overwrite, 단 이번 단계에서는 저장 안 함
applied_trade_ids: 저장
validation failure: 저장 중단
```

## 변경 파일

예상 추가:

```text
core/paper_current_state_serializer.py
tests/test_paper_current_state_serializer.py
```

가능하면 수정하지 말 것:

```text
scripts/run_paper_eod_update.py
core/paper_account_state.py
outputs/
DB files
```

## 구현 지시

`core/paper_current_state_serializer.py`를 추가한다.

필수 함수:

```python
def paper_account_state_to_current_state_dict(
    state,
    state_date: str,
) -> dict:
    ...
```

입력:

```text
state: PaperAccountState
state_date: YYYYMMDD 또는 YYYY-MM-DD
```

출력 dict는 기존 current_state 호환 구조여야 한다.

예상 출력:

```python
{
    "current_symbols": ["CPAY", "GEN"],
    "current_cash_ratio": 0.7024595,
    "current_hedge_ratio": 0.0,
    "absolute_cash": 70245.95,
    "shares": {"CPAY": 29, "GEN": 440},
    "avg_price": {"CPAY": 343.99, "GEN": 22.68},
    "highest_prices": {"CPAY": 343.99, "GEN": 22.68},
    "highest_price_meta": {
        "CPAY": {
            "updated_at": "2026-05-09",
            "source": "paper_execution_log",
            "basis": "trade_price"
        }
    },
    "hedge_symbols": [],
    "applied_trade_ids": [...]
}
```

계산 규칙:

```text
current_symbols = positions key list
absolute_cash = state.cash
shares = position.shares
avg_price = position.avg_price
highest_prices = position.highest_price
current_hedge_ratio = 0.0
hedge_symbols = []
total_equity = cash + sum(shares * avg_price)
current_cash_ratio = cash / total_equity
```

주의:

- positions top-level 필드는 만들지 않는다.
- total_equity는 저장하지 않는다.
- initial_cash, currency는 이번 호환 state 필수 필드로 넣지 않는다.
- applied_trade_ids는 사용자 결정에 따라 extra top-level field로 저장한다.
- applied_trade_ids는 정렬해서 list로 저장한다.
- highest_price_meta의 `updated_at`은 state_date를 `YYYY-MM-DD`로 정규화한다.
- total_equity <= 0이면 current_cash_ratio는 0.0으로 처리한다.

## 하지 말 것

이번 단계에서 금지:

```text
paper_current_state_*.json 파일 생성
run_paper_eod_update.py 연결
paper_execution_log.csv 수정
paper_account_snapshot.csv 생성
paper_performance_report 생성
outputs/front_test 수정
DB 수정
paper reducer 로직 변경
```

## 테스트

신규 테스트:

```text
tests/test_paper_current_state_serializer.py
```

필수 테스트:

1. 빈 state 변환
   - current_symbols []
   - shares/avg_price/highest_prices {}
   - absolute_cash 100000
   - current_cash_ratio 1.0

2. BUY 반영 state 변환
   - CPAY 29주, avg_price 343.99
   - top-level shares/avg_price/highest_prices가 맞는지 확인

3. current_cash_ratio 계산
   - cash 70245.95
   - positions 평가액 포함 total_equity 기준 확인

4. highest_price_meta 생성
   - source = paper_execution_log
   - basis = trade_price
   - updated_at = YYYY-MM-DD

5. applied_trade_ids 저장
   - set 입력이 list로 정렬되어 저장되는지 확인

6. positions top-level field가 없는지 확인

## 검증 명령

```powershell
$env:PYTHONPATH="."; python -m pytest tests/test_paper_account_state.py -q
$env:PYTHONPATH="."; python -m pytest tests/test_paper_current_state_serializer.py -q
$env:PYTHONPATH="."; python -m py_compile core/paper_current_state_serializer.py
```

## 완료 기준

1. `paper_account_state_to_current_state_dict()` 추가
2. 기존 current_state 호환 필드 생성
3. `positions` top-level 필드 없음
4. `current_cash_ratio` 계산됨
5. `highest_price_meta` 생성됨
6. `applied_trade_ids` 저장됨
7. 실제 파일 write 없음
8. 테스트 통과

## 보고 형식

```text
1. Summary
2. Changed files
3. Serializer behavior
4. Tests run
5. Files intentionally not changed
6. Risks and limitations
7. Suggested next step
```
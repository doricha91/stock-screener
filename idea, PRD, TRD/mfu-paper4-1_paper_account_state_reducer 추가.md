# Codex Task: MFU-PAPER4-1 Paper Account State Reducer 추가

## 목표

`paper_execution_log.csv` row를 입력으로 받아 paper account state를 계산하는 순수 reducer를 추가한다.

이번 단계는 **계산 로직만 구현**한다.  
파일 저장은 하지 않는다.

초기 paper account 정책:

```text
initial_cash = 100000.0
currency = USD
initial_positions = {}
fee/slippage/tax = 0
```

## 변경 파일

예상 추가:

```text
core/paper_account_state.py
tests/test_paper_account_state.py
```

수정 금지:

```text
scripts/run_paper_eod_update.py
scripts/run_eod_update.py
outputs/
DB files
```

## 구현 지시

`core/paper_account_state.py`에 dataclass와 reducer를 추가한다.

권장 구조:

```python
@dataclass(frozen=True)
class PaperPosition:
    symbol: str
    shares: int
    avg_price: float
    highest_price: float

@dataclass(frozen=True)
class PaperAccountState:
    cash: float
    currency: str
    positions: dict[str, PaperPosition]
    applied_trade_ids: set[str]
```

필수 함수:

```python
def create_initial_paper_state(
    initial_cash: float = 100000.0,
    currency: str = "USD",
) -> PaperAccountState:
    ...

def apply_paper_trade(
    state: PaperAccountState,
    trade_row: dict,
) -> PaperAccountState:
    ...

def build_paper_state_from_trades(
    trade_rows: list[dict],
    initial_cash: float = 100000.0,
    currency: str = "USD",
) -> PaperAccountState:
    ...
```

## trade_row 입력 전제

`paper_execution_log.csv` row 구조를 따른다.

필수 필드:

```text
trade_id
date
symbol
side
shares
price
gross_amount
```

## 처리 규칙

### BUY

- `shares > 0`
- `cash -= shares * price`
- cash 부족이면 `ValueError`
- 신규 position 생성
- 기존 position이면 avg_price 가중평균 갱신
- highest_price는 `max(existing_highest, price)`

### SELL

- PAPER3 기준 SELL shares는 음수
- 보유 수량보다 많이 팔면 `ValueError`
- `cash += abs(shares) * price`
- shares 감소
- 0주가 되면 position 제거

### duplicate

- `trade_id`가 이미 `applied_trade_ids`에 있으면 state 변경 없이 반환

### invalid

다음은 `ValueError`:

```text
missing trade_id
missing symbol
side not BUY/SELL
price <= 0
shares == 0
BUY인데 shares < 0
SELL인데 shares > 0
```

## 하지 말 것

- paper_current_state_*.json 저장 금지
- paper_execution_log.csv 읽기/쓰기 금지
- paper_account_snapshot.csv 생성 금지
- performance 계산 금지
- run_paper_eod_update.py 연결 금지
- live/front-test 파일 수정 금지
- DB schema 수정 금지

## 테스트

`tests/test_paper_account_state.py` 추가.

필수 테스트:

1. 초기 상태
   - cash 100000
   - positions empty
   - currency USD

2. BUY 10 @ 100
   - cash 99000
   - AAPL shares 10
   - avg_price 100

3. 추가 BUY 10 @ 200
   - shares 20
   - avg_price 150

4. SELL 5 @ 300
   - shares 15
   - cash 증가

5. 전량 SELL
   - position 제거

6. 현금 부족 BUY
   - ValueError

7. 보유 수량 초과 SELL
   - ValueError

8. duplicate trade_id
   - 두 번 반영되지 않음

## 검증 명령

```powershell
$env:PYTHONPATH="."; python -m pytest tests/test_paper_account_state.py -q
$env:PYTHONPATH="."; python -m py_compile core/paper_account_state.py
```

전체 테스트는 기존 collection 이슈가 있을 수 있으므로 필요 시만 실행하고, 기존 실패와 구분한다.

## 완료 기준

1. 순수 reducer 구현 완료
2. 초기 cash $100,000 적용
3. BUY/SELL/duplicate/invalid 테스트 통과
4. 어떤 파일 write도 발생하지 않음
5. run_paper_eod_update.py는 수정하지 않음

## 보고 형식

```text
1. Summary
2. Changed files
3. Behavior changes
4. Tests run
5. Tests not run and why
6. Risks and limitations
7. Suggested next step
```
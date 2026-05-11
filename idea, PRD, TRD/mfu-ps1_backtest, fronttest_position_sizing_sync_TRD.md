# MFU-PS1 TRD v1.0
# Backtest / Front-test Position Sizing Synchronization

## 1. 기술 목표

백테스트와 프론트테스트의 일반 신규 BUY 수량 계산을 공용 helper로 통일한다.

이번 작업은 기존 백테스트 로직을 바꾸는 것이 아니라, 기존 공식을 `core/position_sizing.py`로 추출하고 백테스트/프론트테스트에서 함께 사용하게 하는 것이다.

---

## 2. 현재 기준 공식

백테스트의 일반 신규 BUY 수량 계산은 다음 공식을 기준으로 한다.

```python
target_position_value = total_equity / max_positions
allocation = min(target_position_value, available_buying_power)
shares = int(allocation / price)
```

이 공식을 MFU-PS1의 SSOT로 삼는다.

---

## 3. 변경 파일

예상 변경 파일:

```text
core/position_sizing.py
core/backtest_engine.py
core/daily_plan_generator.py
tests/test_position_sizing.py
```

가능하면 변경하지 말아야 할 파일:

```text
scripts/run_eod_update.py
scripts/run_paper_eod_update.py
core/paper_execution_log.py
core/paper_trade_preview.py
core/portfolio_state_manager.py
screener/data_collector.py
config.py
core/portfolio_config.py
```

---

## 4. 신규 파일: core/position_sizing.py

### 4.1 함수 정의

```python
from __future__ import annotations


def calculate_entry_shares(
    total_equity: float,
    available_buying_power: float,
    price: float,
    max_positions: int,
) -> int:
    """
    Calculate entry shares for a normal new BUY order.

    This function intentionally mirrors the existing backtest logic:

        target_position_value = total_equity / max_positions
        allocation = min(target_position_value, available_buying_power)
        shares = int(allocation / price)

    Non-goals:
    - no ATR risk sizing
    - no target_long_slots sizing
    - no commission/slippage
    - no switching-specific logic
    """
    if total_equity <= 0:
        return 0
    if available_buying_power <= 0:
        return 0
    if price <= 0:
        return 0
    if max_positions <= 0:
        return 0

    target_position_value = total_equity / max_positions
    allocation = min(target_position_value, available_buying_power)
    shares = int(allocation / price)

    return max(0, shares)
```

---

## 5. backtest_engine.py 변경

파일:

```text
core/backtest_engine.py
```

### 5.1 import 추가

```python
from core.position_sizing import calculate_entry_shares
```

### 5.2 일반 신규 BUY 수량 계산 교체

기존 유사 로직:

```python
target_pos_value = cp_now['total_equity'] / config['max_positions']
shares = int(min(target_pos_value, remaining_bp) / row['close'])
```

변경:

```python
shares = calculate_entry_shares(
    total_equity=cp_now["total_equity"],
    available_buying_power=remaining_bp,
    price=row["close"],
    max_positions=config["max_positions"],
)
```

주의:

- 기존 일반 신규 BUY 루프에서만 교체한다.
- SWITCH_IN 로직은 이번 작업에서 변경하지 않는다.
- HEDGE 관련 로직은 변경하지 않는다.
- SELL 관련 로직은 변경하지 않는다.
- 로깅 구조는 변경하지 않는다.

---

## 6. daily_plan_generator.py 변경

파일:

```text
core/daily_plan_generator.py
```

### 6.1 import 추가

```python
from core.position_sizing import calculate_entry_shares
```

### 6.2 일반 신규 BUY Rec_Shares 계산 교체

프론트테스트에서 일반 신규 BUY action 또는 journal row를 만들 때 `Rec_Shares`를 계산하는 부분을 찾는다.

기존 로직이 다음과 비슷하면:

```python
rec_shares = int(available_buying_power / price)
```

또는 buying power를 후보에 순차적으로 전부 배분하는 방식이면, 아래 helper로 교체한다.

```python
rec_shares = calculate_entry_shares(
    total_equity=total_equity,
    available_buying_power=available_buying_power,
    price=price,
    max_positions=merged_config["max_positions"],
)
```

주의:

- `total_equity`는 프론트테스트 현재 상태 기준 총자산이어야 한다.
- `available_buying_power`는 기존 cash policy에서 계산된 신규 매수 가능 금액이어야 한다.
- `price`는 기존 `Rec_Price` 산출에 사용하던 가격 기준을 유지한다.
- helper 적용 후에도 매수 후 available buying power 차감은 기존 흐름을 유지한다.
- ACTION / REVIEW / WARNING taxonomy는 변경하지 않는다.
- journal format은 불필요하게 변경하지 않는다.

---

## 7. 테스트

신규 테스트 파일:

```text
tests/test_position_sizing.py
```

### 7.1 정상 계산

```python
def test_calculate_entry_shares_normal_case():
    assert calculate_entry_shares(
        total_equity=100000,
        available_buying_power=30000,
        price=200,
        max_positions=10,
    ) == 50
```

### 7.2 buying power 부족

```python
def test_calculate_entry_shares_limited_by_buying_power():
    assert calculate_entry_shares(
        total_equity=100000,
        available_buying_power=5000,
        price=200,
        max_positions=10,
    ) == 25
```

### 7.3 buying power 0

```python
def test_calculate_entry_shares_zero_buying_power():
    assert calculate_entry_shares(
        total_equity=100000,
        available_buying_power=0,
        price=200,
        max_positions=10,
    ) == 0
```

### 7.4 price 0

```python
def test_calculate_entry_shares_zero_price():
    assert calculate_entry_shares(
        total_equity=100000,
        available_buying_power=30000,
        price=0,
        max_positions=10,
    ) == 0
```

### 7.5 max_positions 0

```python
def test_calculate_entry_shares_zero_max_positions():
    assert calculate_entry_shares(
        total_equity=100000,
        available_buying_power=30000,
        price=200,
        max_positions=0,
    ) == 0
```

### 7.6 기존 백테스트 공식과 동일성

```python
def test_calculate_entry_shares_matches_existing_formula():
    total_equity = 100000
    available_buying_power = 30000
    price = 200
    max_positions = 10

    expected = int(min(total_equity / max_positions, available_buying_power) / price)

    assert calculate_entry_shares(
        total_equity=total_equity,
        available_buying_power=available_buying_power,
        price=price,
        max_positions=max_positions,
    ) == expected
```

---

## 8. 검증 명령

```powershell
$env:PYTHONPATH="."; python -m pytest tests/test_position_sizing.py -q
$env:PYTHONPATH="."; python -m py_compile core/position_sizing.py core/backtest_engine.py core/daily_plan_generator.py
```

가능하면 기존 관련 검증도 실행한다.

```powershell
$env:PYTHONPATH="."; python scripts/check_decision_parity.py --date 2026-05-04 --symbol AAPL
$env:PYTHONPATH="."; python scripts/validate_strategy_sync.py
```

전체 테스트는 기존 import 문제가 있을 수 있으므로, 실행한다면 결과를 구분해서 보고한다.

```powershell
$env:PYTHONPATH="."; python -m pytest tests -q
```

---

## 9. Non-goals

이번 작업에서 하지 말 것:

```text
- switching sizing 변경
- hedge sizing 변경
- sell sizing 변경
- target_long_slots 기반 sizing 변경
- ATR risk-based sizing 추가
- 수수료/슬리피지 추가
- paper current state 생성
- paper execution log 변경
- paper account snapshot 변경
- data collector 변경
- DB schema 변경
- output DB 수정
- generated artifact 수정
```

---

## 10. 리스크

### 10.1 백테스트 결과 변화 가능성

의도는 기존 로직과 동일한 helper 추출이지만, 실수로 입력값이나 rounding 방식이 바뀌면 백테스트 결과가 달라질 수 있다.

방지:

- 기존 공식과 helper 결과 동일성 테스트 추가
- backtest_engine.py에서는 동일 입력값을 helper에 전달

### 10.2 프론트테스트 total_equity 기준 차이

front-test의 total_equity 계산이 backtest의 total_equity와 의미상 다르면 Rec_Shares가 기대와 다를 수 있다.

방지:

- 기존 front-test cash policy / account status 계산 흐름을 최대한 유지
- helper에는 이미 계산된 total_equity와 available_buying_power를 전달

### 10.3 과도한 전략 변경 위험

`target_long_slots`나 ATR risk sizing을 넣으면 이번 작업 범위를 벗어난다.

방지:

- PRD 기준대로 현재 백테스트 공식을 유지

---

## 11. Acceptance Criteria

완료 조건:

1. `core/position_sizing.py`가 추가된다.
2. `calculate_entry_shares()`가 구현된다.
3. helper는 기존 백테스트 일반 신규 BUY 공식과 동일한 결과를 낸다.
4. `core/backtest_engine.py` 일반 신규 BUY 수량 계산이 helper를 사용한다.
5. `core/daily_plan_generator.py` 일반 신규 BUY `Rec_Shares` 계산이 helper를 사용한다.
6. SWITCH_IN / HEDGE / SELL 수량 로직은 변경되지 않는다.
7. 신규 테스트 `tests/test_position_sizing.py`가 통과한다.
8. 기존 strategy / paper / data collector 로직은 변경되지 않는다.
9. generated artifact나 DB 파일은 수정하지 않는다.

---

## 12. 보고 형식

작업 완료 후 아래 형식으로 보고한다.

```text
1. Summary
2. Changed files
3. Behavior changes
4. Tests run
5. Tests not run and why
6. Risks and limitations
7. Suggested next step
```

특히 다음을 명확히 보고한다.

```text
- backtest_engine.py에서 어떤 수량 계산을 helper로 교체했는지
- daily_plan_generator.py에서 어떤 Rec_Shares 계산을 helper로 교체했는지
- helper가 기존 백테스트 공식과 동일한지
- switching/hedge/sell 로직을 건드리지 않았는지
- 백테스트 결과가 바뀔 가능성이 있는지
```
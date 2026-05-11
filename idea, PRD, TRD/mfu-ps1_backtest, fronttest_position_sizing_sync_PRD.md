# MFU-PS1 PRD v1.0
# Backtest / Front-test Position Sizing Synchronization

## 1. 목적

백테스트와 프론트테스트의 일반 신규 BUY 수량 계산을 동일한 로직으로 동기화한다.

현재 목표는 전략 개선이 아니라 정합성 확보다.

---

## 2. 문제

프론트테스트의 `Rec_Shares`가 백테스트의 일반 신규 매수 수량 계산과 동일하다고 보장되지 않으면, 이후 paper-test 성과가 왜곡될 수 있다.

특히 paper execution log가 이미 생성 가능해진 상태에서, 잘못된 `Rec_Shares` 또는 `Act_Shares`가 누적되면 이후 paper current state와 성과 추적이 모두 왜곡된다.

---

## 3. 제품 목표

### 3.1 핵심 목표

```text
동일 입력 조건에서 백테스트 신규 BUY shares와 프론트테스트 Rec_Shares가 동일해야 한다.
```

동일 입력 조건:

- total_equity
- available_buying_power
- price
- max_positions

---

## 4. 정책 결정

### 4.1 기준 로직

이번 MFU에서는 현재 백테스트의 일반 신규 BUY 수량 계산식을 정답으로 삼는다.

```python
target_position_value = total_equity / max_positions
allocation = min(target_position_value, available_buying_power)
shares = int(allocation / price)
```

### 4.2 max_positions 기준 유지

이번 작업에서는 `target_long_slots` 기준으로 바꾸지 않는다.

이유:

- 현재 백테스트 일반 신규 매수는 `max_positions` 기준이다.
- 이번 작업은 전략 개선이 아니라 정합성 작업이다.
- `target_long_slots` 기준 변경은 별도 전략 변경 MFU로 다뤄야 한다.

### 4.3 적용 범위

이번 MFU에서 포함:

- 일반 신규 BUY 수량 계산
- 백테스트 일반 신규 BUY 로직의 helper화
- 프론트테스트 `Rec_Shares` 계산의 helper화

이번 MFU에서 제외:

- SWITCH_IN
- HEDGE BUY
- SELL
- trailing stop
- paper current state
- paper performance
- 수수료/슬리피지
- ATR risk-based sizing
- target_long_slots 기반 sizing

---

## 5. 사용자 시나리오

### 시나리오 1: 백테스트 신규 매수

조건:

```text
total_equity = 100000
available_buying_power = 30000
price = 200
max_positions = 10
```

기대:

```text
target_position_value = 100000 / 10 = 10000
allocation = min(10000, 30000) = 10000
shares = int(10000 / 200) = 50
```

결과:

```text
shares = 50
```

---

### 시나리오 2: buying power 부족

조건:

```text
total_equity = 100000
available_buying_power = 5000
price = 200
max_positions = 10
```

기대:

```text
target_position_value = 10000
allocation = min(10000, 5000) = 5000
shares = int(5000 / 200) = 25
```

결과:

```text
shares = 25
```

---

### 시나리오 3: 매수 불가

조건:

```text
available_buying_power = 0
```

기대:

```text
shares = 0
```

---

## 6. 기능 요구사항

### FR-1. 공용 position sizing helper 추가

신규 파일:

```text
core/position_sizing.py
```

필수 함수:

```python
calculate_entry_shares(
    total_equity: float,
    available_buying_power: float,
    price: float,
    max_positions: int,
) -> int
```

---

### FR-2. 백테스트 일반 신규 BUY가 helper 사용

`core/backtest_engine.py`의 일반 신규 매수 수량 계산을 helper 호출로 교체한다.

단, 결과 수량은 기존과 동일해야 한다.

---

### FR-3. 프론트테스트 Rec_Shares가 helper 사용

`core/daily_plan_generator.py`의 일반 신규 BUY `Rec_Shares` 계산을 helper 호출로 교체한다.

---

### FR-4. 테스트 추가

신규 테스트:

```text
tests/test_position_sizing.py
```

테스트 항목:

- 정상 수량 계산
- buying power 부족
- buying power 0
- price 0
- max_positions 0
- 음수 입력 방어
- 백테스트 기존 공식과 helper 결과 동일성

---

## 7. 비기능 요구사항

- 기존 백테스트 성과가 바뀌면 안 된다.
- 기존 프론트테스트 리포트 형식을 불필요하게 바꾸면 안 된다.
- 기존 paper-test 경로를 수정하면 안 된다.
- 기존 DB schema를 변경하면 안 된다.
- output DB나 generated artifact를 수정하면 안 된다.

---

## 8. Non-goals

이번 MFU에서 하지 말 것:

```text
- ATR risk-based sizing 도입
- target_long_slots 기반 sizing 변경
- switching 수량 계산 변경
- hedge 수량 계산 변경
- SELL 수량 계산 변경
- paper current state 생성
- paper account snapshot 생성
- paper performance 계산
- run_paper_eod_update.py 변경
- DB schema 변경
- data_collector 변경
```

---

## 9. Acceptance Criteria

완료 조건:

1. `core/position_sizing.py`가 추가된다.
2. `calculate_entry_shares()`가 현재 백테스트 일반 신규 BUY 공식을 구현한다.
3. `core/backtest_engine.py`의 일반 신규 BUY 수량 계산이 helper를 사용한다.
4. `core/daily_plan_generator.py`의 일반 신규 BUY `Rec_Shares` 계산이 helper를 사용한다.
5. 동일 입력에서 helper 결과가 기존 백테스트 공식과 동일하다.
6. 신규 테스트가 통과한다.
7. 기존 백테스트 전략 로직이 의도치 않게 바뀌지 않는다.
8. switching / hedge / sell 수량 로직은 변경하지 않는다.
9. paper/live 파일 write는 발생하지 않는다.

---

## 10. 성공 기준

이 작업이 끝난 뒤 다음 문장이 성립해야 한다.

```text
프론트테스트의 일반 신규 BUY Rec_Shares는 백테스트의 일반 신규 BUY shares와 같은 공식으로 계산된다.
```
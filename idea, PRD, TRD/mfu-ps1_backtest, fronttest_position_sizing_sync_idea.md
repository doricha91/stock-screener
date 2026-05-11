# MFU-PS1 Idea v1.0
# Backtest / Front-test Position Sizing Synchronization

## 1. 배경

현재 `stock-screener` 프로젝트는 백테스트 로직과 프론트테스트 로직의 정합성을 맞추는 작업을 진행 중이다.

지금까지 MFU8을 통해 다음 정합성 작업을 진행했다.

- score / rs_val / buy-entry signal parity 검증
- ACTION / REVIEW / WARNING taxonomy 정리
- SELL diagnostics 추가
- TRAILING_STOP ATR 기준 정렬
- highest_price warning 강화
- paper/live state 분리
- paper execution log 기반 마련

하지만 아직 중요한 차이가 남아 있다.

> 프론트테스트의 `Rec_Shares` 계산 방식이 백테스트의 신규 매수 수량 계산 방식과 완전히 동일하다고 보장되지 않는다.

이 상태에서 paper-test를 진행하면, 성과 차이가 전략 로직 때문인지, 수량 계산 차이 때문인지 구분하기 어렵다.

---

## 2. 문제 정의

백테스트의 일반 신규 매수는 대략 다음 방식으로 수량을 계산한다.

```python
target_position_value = total_equity / max_positions
allocation = min(target_position_value, available_buying_power)
shares = int(allocation / price)
```

반면 프론트테스트에서는 `Rec_Shares`가 별도 로직으로 계산될 수 있고, 이 경우 특정 종목에 buying power가 과도하게 몰릴 위험이 있다.

예시:

```text
백테스트: AAPL 50주 매수
프론트테스트: AAPL 500주 매수
페이퍼테스트: AAPL 500주 기준 성과 기록
```

이렇게 되면 백테스트와 페이퍼테스트 성과 비교가 왜곡된다.

---

## 3. 아이디어

백테스트와 프론트테스트가 각각 수량 계산을 하지 말고, 공용 position sizing helper를 사용한다.

예상 파일:

```text
core/position_sizing.py
```

핵심 함수:

```python
calculate_entry_shares(...)
```

이 함수는 현재 백테스트의 일반 신규 BUY 수량 계산식을 그대로 구현한다.

---

## 4. 핵심 방향

이번 작업은 전략 개선이 아니다.

이번 작업의 목표는 다음이다.

```text
기존 백테스트 수량 계산식
=
프론트테스트 Rec_Shares 계산식
```

따라서 이번 MFU에서는 다음을 하지 않는다.

- ATR risk-based sizing 도입
- target_long_slots 기반 sizing 변경
- 수수료/슬리피지 반영
- switching sizing 변경
- hedge sizing 변경
- SELL 수량 변경
- paper current state 생성

---

## 5. 기대 효과

이 작업이 완료되면:

- 프론트테스트의 `Rec_Shares`가 백테스트 신규 BUY 수량 계산과 동일한 기준으로 산출된다.
- paper execution log의 수량이 전략 정합성 검증에 더 적합해진다.
- 이후 paper current state / paper account snapshot을 만들 때 결과 왜곡을 줄일 수 있다.
- position sizing 정책 변경이 필요할 때 한 곳에서 관리할 수 있다.

---

## 6. 한계

이번 작업은 신규 BUY 수량 계산 정합성만 다룬다.

아직 남는 작업:

- SWITCH_IN 수량 정합성
- hedge position sizing 정합성
- SELL 수량 정책 정리
- paper current state 생성
- paper account snapshot / performance 계산
- 전체 테스트 import 문제 정리

---

## 7. 결론

MFU-PS1은 백테스트와 프론트테스트의 신규 매수 수량 계산을 하나의 공용 함수로 통일하는 작업이다.

이번 작업의 기준은 “더 좋은 sizing”이 아니라 “현재 백테스트와 동일한 sizing”이다.
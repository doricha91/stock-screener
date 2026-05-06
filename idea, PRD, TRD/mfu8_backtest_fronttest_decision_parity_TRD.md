## [TRD] MFU8: 기술 설계 및 구현 가이드

**1. 타깃 파일 및 제약사항**

- 수정 허용 파일
  - `core/daily_plan_generator.py`
  - 필요 시 `backtesting/reason_codes.py`의 최소 확장
- 신규 생성 파일
  - `scripts/validate_strategy_sync.py`
  - `scripts/check_decision_parity.py`
  - 필요 시 `core/types.py`는 `ActionType` 같은 front-test 전용 최소 타입에 한해 사용
- 수정 금지
  - `core/backtest_engine.py` 핵심 루프 구조 변경
  - `scripts/run_front_test.py` 구조 변경

**2. Reason / Action 상수 설계**

- 우선 원칙:
  - backtest reason은 기존 `backtesting/reason_codes.py`를 SSOT로 유지
  - front-test에서 필요한 action type만 별도 상수화가 필요하면 `core/types.py`에 `ActionType`만 둔다
- 권장 예시:

```python
from enum import Enum

class ActionType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"
```

- `REVIEW_EXIT` 같은 front-test review reason은 다음 둘 중 하나로 처리한다.
  - 기존 `backtesting/reason_codes.py` 확장
  - front-test local constant로 유지
- 중요한 점:
  - backtest용 `ReasonCode`와 front-test용 새 `ReasonCode`를 이중으로 만들지 않는다.

**3. `validate_strategy_sync.py` 설계**

- `make_config(params={}, start_date, end_date, runtime_overrides=None)`로 `merged_config`를 만든다.
- `merged_config`에서 실제 사용되는 active weight key를 추출한다.
  - 예: `turtle`, `rsi`, `sma`, `bbands`, `macd`, `bbs`, `dema`, `obv`, `mfi`, `vol_spike`
- 아래를 검증한다.
  - 각 key에 대응하는 indicator/strategy 준비 경로가 존재하는지
  - front-test와 backtest가 같은 signal column naming 계약을 사용하는지
  - `compute_candidate_score()`가 기대하는 `signal_*` 컬럼이 실제로 생성 가능한지
- 권장 출력:
  - PASS: 모든 weight key가 유효
  - FAIL: 누락된 weight, 누락된 indicator path, 누락된 signal column contract

**4. `check_decision_parity.py` 설계**

- 입력
  - `--date`
  - `--symbol`
- 날짜 처리
  - `plan_date`를 입력받더라도 내부 비교 기준은 `data_date = market_state['date']`
- 비교 계층
  - backtest 방식:
    - 동일 종목의 price history 로드
    - backtest와 동일한 indicator/strategy/RS 파이프라인 적용
    - 최종 `score`, `rs_val`, `buy_signal` 추출
  - front-test 방식:
    - front-test helper 또는 동등 경로로 동일 종목을 평가
    - 최종 `score`, `rs_val`, `entry_signal` 추출
- assert 기준

```python
assert abs(bt_score - ft_score) < 0.001
assert abs(bt_rs_val - ft_rs_val) < 0.001
assert bool(bt_buy_signal) == bool(ft_entry_signal)
```

- 주의:
  - removed guard, stale guard, review-only formatting은 1차 parity 비교 대상이 아니다.
  - 즉 "산출값 parity"와 "운영 보호 로직 parity"를 분리해야 한다.

**5. 구현 리스크와 방지 규칙**

- `config.py`에 없는 가상의 `active_weights` dict를 SSOT로 가정하지 말 것
- `backtesting/reason_codes.py`와 별개 reason enum을 새로 만들어 이중 SSOT를 만들지 말 것
- front-test와 backtest의 full orchestration 결과를 그대로 assert 하지 말 것
- parity tolerance는 문서/코드에서 모두 `0.001`로 통일할 것

**6. 추천 구현 순서**

1. `validate_strategy_sync.py`
2. `check_decision_parity.py`
3. `daily_plan_generator.py`의 action/reason 문자열 상수화

이 순서가 맞는 이유는, 먼저 동기화/정합성 검증 도구를 만든 뒤에 상수화 리팩토링을 해야 회귀를 잡기 쉽기 때문이다.

# [TRD] MFU8-1: Score / RS / Signal Parity 검증 자동화 기술 설계서 v1.0

## 1. 기술 목표

MFU8-1의 목표는 백테스트와 프론트테스트가 동일한 `data_date`와 동일한 `symbol`에 대해 같은 핵심 산출값을 내는지 검증하는 것이다.

검증 대상은 다음 3가지로 제한한다.

- `score`
- `rs_val`
- `buy_signal` 또는 front-test의 동등 개념인 `entry_signal`

이 단계는 전체 backtest/front-test 아키텍처 통합이 아니다.  
또한 sell policy 통합도 아니다.

MFU8-1은 다음을 명확히 하는 데 집중한다.

- active weight와 signal column 계약이 양쪽 엔진에서 유효한가
- backtest 방식 산출값과 front-test 방식 산출값이 같은가
- reason/action 문자열을 최소한의 상수로 안정화할 수 있는가

## 2. 타깃 파일 및 제약사항

### 수정 허용 파일

- `core/daily_plan_generator.py`
- 필요 시 `backtesting/reason_codes.py`의 최소 확장
- 필요 시 `core/types.py` 신규 생성

### 신규 생성 파일

- `scripts/validate_strategy_sync.py`
- `scripts/check_decision_parity.py`

### 수정 금지

- `core/backtest_engine.py` 핵심 루프 구조 변경
- `scripts/run_front_test.py` 구조 변경
- DB schema 변경
- broker 관련 파일 변경
- strategy policy 변경
- sell policy 변경
- target/rebalance policy 변경

## 3. Reason / Action 상수 설계

### 3.1 원칙

- backtest reason은 기존 `backtesting/reason_codes.py`를 SSOT로 유지한다.
- front-test에서 필요한 action type만 별도 상수화가 필요하면 `core/types.py` 또는 `daily_plan_generator.py` local constants로 둔다.
- backtest용 `ReasonCode`와 front-test용 새 `ReasonCode`를 이중으로 만들지 않는다.
- `REVIEW_EXIT`는 backtest reason과 직접 대응되는 sell reason이 아니므로, 확정 SELL reason처럼 다루지 않는다.

### 3.2 권장 최소안

Small Safe Fix 관점에서는 Enum보다 local constants가 더 작을 수 있다.

```python
ACTION_BUY = "BUY"
ACTION_SELL = "SELL"
REVIEW_EXIT = "REVIEW_EXIT"
```

### 3.3 Enum을 사용할 경우

```python
from enum import Enum

class ActionType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class ReviewReason(str, Enum):
    REVIEW_EXIT = "REVIEW_EXIT"
```

주의:

- `WAIT`는 실제 action item으로 들어가는지 불명확하므로 MFU8-1에서는 기본 ActionType에 포함하지 않는다.
- journal table 값은 기존 문자열과 동일해야 한다.
- markdown report와 journal header는 유지해야 한다.

## 4. `validate_strategy_sync.py` 설계

## 4.1 목적

`validate_strategy_sync.py`는 전략 weight, indicator/strategy pipeline, signal column 계약이 서로 어긋나지 않는지 정적으로 검사한다.

이 스크립트는 실제 backtest나 front-test 전체를 실행하지 않는다.

## 4.2 Config 생성

검증 기준은 `config.py` 단독이 아니다.

실제 실행 설정은 다음 순서로 만든다.

```python
from core.config_factory import make_config, get_regime_config
import market_analyzer

plan_date = args.date or "2026-05-04"
m_state = market_analyzer.get_market_state(target_date=plan_date, write_log=False)
data_date = m_state["date"]
regime = m_state["regime"]

base_config = make_config(
    params={},
    start_date=data_date,
    end_date=data_date,
    fast_mode=False,
    runtime_overrides=None,
)

merged_config = get_regime_config(regime, base_config)
```

실제 `make_config` 시그니처는 다음과 같다.

```python
make_config(
    params: dict,
    start_date: str,
    end_date: str,
    fast_mode: bool = False,
    runtime_overrides: dict = None,
)
```

## 4.3 Active Weight 추출

`merged_config`에서 실제 사용되는 active weight key를 추출한다.

초기 대상:

```python
ACTIVE_WEIGHT_KEYS = [
    "turtle",
    "rsi",
    "sma",
    "bbands",
    "macd",
    "bbs",
    "dema",
    "obv",
    "mfi",
    "vol_spike",
]
```

각 key의 weight는 다음 형식으로 읽는다.

```python
weight = merged_config.get(f"{key}_weight")
```

## 4.4 Signal Column Contract

전략별 signal column 이름이 항상 `signal_{name}`이라고 가정하면 안 된다.

초기 계약은 다음 alias map을 사용한다.

```python
SIGNAL_COLUMN_CONTRACT = {
    "turtle": ["turtle_signal", "signal_turtle"],
    "rsi": ["rsi_signal", "signal_rsi"],
    "sma": ["sma_signal", "signal_sma"],
    "bbands": ["bbands_signal", "signal_bbands"],
    "macd": ["macd_signal", "signal_macd"],
    "bbs": ["bbs_signal", "signal_bbs"],
    "dema": ["dema_signal", "signal_dema"],
    "obv": ["signal_obv"],
    "mfi": ["signal_mfi"],
    "vol_spike": ["signal_vol_spike"],
}
```

검증 기준:

- active weight key가 있으면 대응되는 signal column alias가 있어야 한다.
- alias 중 최소 하나는 backtest/front-test pipeline에서 생성 가능해야 한다.
- alias map에 없는 active weight key가 발견되면 FAIL 처리한다.

## 4.5 Indicator / Strategy Pipeline 검증

검증 대상 파일:

```text
screener/indicator.py
screener/strategy.py
core/backtest_engine.py
core/daily_plan_generator.py
```

검증 방향:

- 각 active weight key에 대응되는 indicator 또는 strategy path가 있는지 확인한다.
- `strategy.apply_ensemble_strategy()`가 해당 signal을 생성하거나 전달하는지 확인한다.
- `compute_candidate_score()`가 해당 signal column을 읽을 수 있는지 확인한다.

주의:

- 정적 검사만으로 모든 동작을 보장할 수 없다.
- 따라서 validate script는 “명백한 누락”을 잡는 용도다.

## 4.6 출력 형식

성공 예시:

```text
PASS validate_strategy_sync
- active weights: turtle,rsi,sma,bbands,macd,bbs,dema,obv,mfi,vol_spike
- signal contract: OK
- indicator/strategy mapping: OK
```

실패 예시:

```text
FAIL validate_strategy_sync
- missing signal contract: adx
- missing weight mapping: adx_weight
- missing strategy signal: signal_adx
```

## 5. `check_decision_parity.py` 설계

## 5.1 목적

동일 `symbol`과 동일 `data_date`에 대해 backtest 방식과 front-test 방식의 핵심 산출값을 비교한다.

비교 대상:

- `score`
- `rs_val`
- `buy_signal` vs `entry_signal`

## 5.2 CLI

```bash
python scripts/check_decision_parity.py --date 2026-05-04 --symbol AAPL
```

인자:

```text
--date      plan_date 입력. 내부에서는 market_state["date"]를 data_date로 사용.
--symbol    비교할 ticker symbol.
```

## 5.3 날짜 처리

입력 날짜는 plan_date일 수 있다.

하지만 실제 계산 기준은 다음이다.

```python
m_state = market_analyzer.get_market_state(target_date=plan_date, write_log=False)
data_date = m_state["date"]
```

주의:

- `plan_date`와 `data_date`를 혼용하지 않는다.
- 모든 price history와 benchmark history는 `data_date` 이하만 사용한다.
- look-ahead bias를 금지한다.

## 5.4 Backtest 방식 산출

backtest 방식은 다음 절차를 따른다.

```text
1. symbol price history를 data_date 이하로 로드
2. 충분한 lookback 확보
3. indicator pipeline 적용
4. strategy.apply_ensemble_strategy() 적용
5. latest row 선택
6. compute_candidate_score() 적용
7. backtest 방식 RS 계산 또는 동등 함수 적용
8. buy_signal = score >= score_threshold and rs_val > 0
```

주의:

- 전체 backtest를 실행하지 않는다.
- 단일 종목 / 단일 기준일 산출값만 계산한다.
- PortfolioDB를 업데이트하지 않는다.

## 5.5 Front-test 방식 산출

front-test 방식은 다음 절차를 따른다.

```text
1. symbol price history를 data_date 이하로 로드
2. front-test helper 또는 동등 경로로 score 계산
3. calculate_candidate_rs_val() 또는 동등 RS 계산
4. entry_signal 계산
```

현재 front-test helper가 `entry_signal`을 직접 반환하지 않을 수 있다.

이 경우 1차 구현에서는 다음 기준으로 재구성한다.

```python
entry_signal = (score >= score_threshold) and (rs_val > 0)
```

주의:

- 이 값은 front-test 전체 orchestration의 모든 filter를 의미하지 않는다.
- universe removed guard, stale filter, review formatting은 1차 parity 비교에서 제외한다.
- 산출값 parity와 운영 보호 로직 parity를 분리한다.

## 5.6 Assert 기준

```python
assert abs(bt_score - ft_score) < 0.001
assert abs(bt_rs_val - ft_rs_val) < 0.001
assert bool(bt_buy_signal) == bool(ft_entry_signal)
```

문서와 코드에서 tolerance는 모두 `0.001`로 통일한다.

## 5.7 SKIP / INCONCLUSIVE / FAIL 기준

### PASS

- score 차이 < 0.001
- rs_val 차이 < 0.001
- buy_signal == entry_signal

### FAIL

- 한쪽은 계산 가능하고 다른 쪽은 계산 불가
- score 또는 rs_val 차이가 tolerance를 초과
- buy_signal과 entry_signal이 다름
- 계산 중 예상하지 못한 예외 발생

### SKIP

- symbol price data가 양쪽 모두 없음
- 비교 대상 symbol이 DB에 없음

### INCONCLUSIVE

- benchmark 데이터 부족
- indicator lookback 부족
- 양쪽 모두 계산 불가이나 원인이 데이터 부족으로 명확함
- rs_val 계산에 필요한 common index가 부족함

## 5.8 출력 형식

예시:

```text
Decision Parity Check
- plan_date: 2026-05-04
- data_date: 2026-05-01
- symbol: AAPL

Backtest-like:
- score: 3.5000
- rs_val: 0.0330
- buy_signal: True

Fronttest-like:
- score: 3.5000
- rs_val: 0.0330
- entry_signal: True

Diff:
- score_diff: 0.0000
- rs_diff: 0.0000
- signal_match: True

RESULT: PASS
```

## 6. 구현 리스크와 방지 규칙

- `config.py`에 없는 가상의 `active_weights` dict를 SSOT로 가정하지 말 것
- `backtesting/reason_codes.py`와 별개 reason enum을 새로 만들어 이중 SSOT를 만들지 말 것
- front-test와 backtest의 full orchestration 결과를 그대로 assert 하지 말 것
- universe snapshot removed guard, stale filter, review-only formatting은 1차 parity에서 제외할 것
- parity tolerance는 문서/코드에서 모두 `0.001`로 통일할 것
- DB write 금지
- look-ahead bias 금지
- 외부 dependency 추가 금지

## 7. 추천 구현 순서

1. `validate_strategy_sync.py`
2. `check_decision_parity.py`
3. `daily_plan_generator.py`의 action/reason 문자열 상수화

이 순서가 맞는 이유:

- 먼저 동기화/정합성 검증 도구를 만든다.
- 그 다음 action/reason 상수화를 한다.
- 그래야 상수화 중 report/journal 회귀가 생겼을 때 잡기 쉽다.

## 8. 검증 명령

```bash
python -m py_compile scripts/validate_strategy_sync.py
python -m py_compile scripts/check_decision_parity.py

python scripts/validate_strategy_sync.py
python scripts/check_decision_parity.py --date 2026-05-04 --symbol AAPL
python scripts/check_decision_parity.py --date 2026-05-04 --symbol TSLA

python scripts/run_front_test.py
```

## 9. 완료 기준

- `validate_strategy_sync.py`가 현재 active weights와 signal column contract를 점검한다.
- `check_decision_parity.py`가 동일 symbol/date 기준 backtest-like와 fronttest-like 산출값을 출력한다.
- tolerance `0.001`이 문서와 코드에서 일관된다.
- SKIP / INCONCLUSIVE / FAIL이 구분된다.
- `run_front_test.py` 실행 후 기존 report section과 journal header가 유지된다.
- `REVIEW_EXIT`는 journal row에 들어가지 않는다.
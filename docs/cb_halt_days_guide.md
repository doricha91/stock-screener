# cb_halt_days Guide

## 목적

이 문서는 백테스트 결과에 포함되는 `cb_halt_days`의 의미와,
어떤 설정값이 이 지표에 영향을 주는지 정리한 참고 문서다.

주요 목적은 다음과 같다.

- `optimization_log` 또는 백테스트 요약 결과에서 `cb_halt_days`를 해석할 때 기준 제공
- circuit breaker 관련 설정을 조정할 때 영향 범위 확인
- 선택적 레짐 백테스트 사용 시 `cb_halt_days` 해석 오류 방지

## 요약

현재 코드 기준 `cb_halt_days`는 이름 그대로의 "circuit breaker 발동 일수"만 의미하지 않는다.

더 정확히는:

- 백테스트 일별 루프에서 `trade_halted=True`였던 날짜 수

이 값은 다음 두 경로로 증가할 수 있다.

1. circuit breaker 로직이 거래 중단을 반환한 경우
2. 선택적 레짐 백테스트에서 `TARGET_REGIMES` / `REGIME_FILTER_MODE` 때문에 강제로 거래 중단한 경우

따라서 `cb_halt_days`는 pure circuit breaker count가 아니라
"실제 백테스트에서 신규 거래가 차단된 날짜 수"에 더 가깝다.

## 코드 경로

### 집계 위치

- [`core/backtest_engine.py`](/D:/python/StockScreener/core/backtest_engine.py)

관련 로직:

- `run_backtest_with_config()`
- `if trade_halted: safety_stats['cb_halt_days'] += 1`

### circuit breaker 판정 위치

- [`market_analyzer.py`](/D:/python/StockScreener/market_analyzer.py)

관련 함수:

- `_trigger_circuit_breaker()`
- `_compute_triggers()`
- `get_market_state()`

### 설정 정의 위치

- [`config.py`](/D:/python/StockScreener/config.py)

관련 설정:

- `USE_CIRCUIT_BREAKER`
- `CB_DROP_THRESHOLD`
- `CB_COOLDOWN_DAYS`
- `TARGET_REGIMES`
- `REGIME_FILTER_MODE`

## cb_halt_days에 직접 영향을 주는 변수

### 1. USE_CIRCUIT_BREAKER

역할:

- circuit breaker 기능 자체를 켜거나 끈다.

영향:

- `False`이면 circuit breaker 경로로는 `trade_halted=True`가 발생하지 않는다.
- 다만 선택적 레짐 백테스트를 사용 중이면 `cb_halt_days`가 0이 아닐 수 있다.

실무 해석:

- circuit breaker 효과만 보고 싶다면 이 값이 `True`인지 먼저 확인해야 한다.

### 2. CB_DROP_THRESHOLD

역할:

- SPY 일간 수익률이 이 임계값 이하일 때 circuit breaker trigger를 발생시킨다.

예:

- `-3.0`: 전일 대비 `-3%` 이상 하락 시 발동

영향 방향:

- 값을 덜 음수로 만들수록 예: `-3.0 -> -2.0`
  - 더 민감해짐
  - `cb_halt_days` 증가 가능성 커짐
- 값을 더 음수로 만들수록 예: `-3.0 -> -4.0`
  - 덜 민감해짐
  - `cb_halt_days` 감소 가능성 커짐

실무 해석:

- circuit breaker 발동 빈도를 가장 직접적으로 바꾸는 기준값 중 하나다.

### 3. CB_COOLDOWN_DAYS

역할:

- 급락 trigger 발생 후 몇 일 동안 거래 중단 상태를 유지할지 결정한다.

영향 방향:

- 값을 키우면
  - 한 번의 급락 이벤트가 더 긴 거래 중단 기간으로 이어진다
  - `cb_halt_days`가 증가하기 쉽다
- 값을 줄이면
  - 중단 기간이 짧아진다
  - `cb_halt_days`가 감소하기 쉽다

실무 해석:

- `CB_DROP_THRESHOLD`가 발동 빈도를 바꾼다면,
  `CB_COOLDOWN_DAYS`는 발동 이후 지속 일수를 바꾼다.

## cb_halt_days에 간접 영향을 주는 변수

### 4. TARGET_REGIMES

역할:

- 특정 레짐에서만 전략이 동작하도록 제한한다.

영향:

- 현재 레짐이 대상 레짐 목록에 없으면 백테스트 엔진에서 `trade_halted=True`로 강제될 수 있다.

주의:

- 이 경우는 circuit breaker가 아니어도 `cb_halt_days`에 포함된다.

### 5. REGIME_FILTER_MODE

역할:

- 선택적 레짐 백테스트에서 대상 레짐 밖일 때 어떻게 행동할지 결정한다.

옵션:

- `FREEZE`
  - 기존 보유는 유지
  - 신규 매수만 차단
- `EXCLUSIVE`
  - 대상 레짐이 아니면 포지션 정리 후 관망

영향:

- 두 모드 모두 백테스트 엔진에서 `trade_halted=True`를 만들 수 있다.
- 따라서 `cb_halt_days`를 증가시킬 수 있다.

## 영향이 없거나 매우 간접적인 변수

다음 변수들은 `cb_halt_days`를 직접 바꾸지 않는다.

- `MIN_MODE_MAINTAIN_DAYS`
- `BULL/BEAR/UNSTABLE/PANIC`의 `target_cash_ratio`
- `score_threshold`
- `switching_premium`
- `trailing_stop_multiplier`
- 각종 전략 weight

이 변수들은 매매 성향이나 레짐 적용 이후 행동을 바꾸지만,
`trade_halted` 플래그 자체를 직접 생성하지는 않는다.

## 주의할 점

### 1. 이름과 실제 의미가 완전히 같지 않다

`cb_halt_days`라는 이름만 보면
"circuit breaker가 발동한 날짜 수"처럼 보일 수 있다.

하지만 현재 구현은:

- `trade_halted=True`인 날짜 수

를 세므로, 선택적 레짐 필터에 의한 중단일까지 포함될 수 있다.

### 2. circuit breaker 기준 지수는 현재 SPY 하드코딩이다

현재 `_trigger_circuit_breaker()`는 SPY를 직접 사용한다.

즉:

- `MARKET_BENCHMARK_SYMBOL`을 바꿔도
- `cb_halt_days` 계산에는 직접 반영되지 않는다

이 점은 추후 코드 해석 시 유의해야 한다.

### 3. 급락 이벤트 수와 cb_halt_days는 다를 수 있다

한 번의 급락 이벤트가 발생해도 `CB_COOLDOWN_DAYS` 동안 여러 일이 누적되므로:

- 급락 횟수 < `cb_halt_days`

가 되는 것이 자연스럽다.

## 백테스트 해석 가이드

### circuit breaker 순수 효과를 보고 싶을 때

다음을 함께 확인한다.

- `USE_CIRCUIT_BREAKER=True`
- `TARGET_REGIMES=[]`
- `REGIME_FILTER_MODE`가 기본 상태인지

이 조건이 아니면 `cb_halt_days`에 레짐 필터 효과가 섞일 수 있다.

### cb_halt_days가 높게 나왔을 때 점검 순서

1. `TARGET_REGIMES`를 사용했는지 확인
2. `REGIME_FILTER_MODE`가 `FREEZE` 또는 `EXCLUSIVE`인지 확인
3. `USE_CIRCUIT_BREAKER`가 켜져 있는지 확인
4. `CB_DROP_THRESHOLD`가 너무 민감하게 잡혀 있지 않은지 확인
5. `CB_COOLDOWN_DAYS`가 너무 길지 않은지 확인

## 추천 실험 순서

`cb_halt_days`를 의도적으로 조정하고 싶다면 다음 순서가 해석하기 쉽다.

1. `CB_COOLDOWN_DAYS`
2. `CB_DROP_THRESHOLD`
3. `USE_CIRCUIT_BREAKER`

선택적 레짐 필터를 같이 쓰는 경우에는:

4. `TARGET_REGIMES`
5. `REGIME_FILTER_MODE`

를 별도 실험으로 분리하는 것이 좋다.

## 결론

현재 코드 기준 `cb_halt_days`는 단순한 circuit breaker event count가 아니다.

정확히는:

- 백테스트에서 거래 차단 상태였던 날짜 수

로 해석하는 것이 안전하다.

실험 시 가장 먼저 조절할 변수는:

- `CB_DROP_THRESHOLD`
- `CB_COOLDOWN_DAYS`
- `USE_CIRCUIT_BREAKER`

이며, 선택적 레짐 백테스트를 사용 중이면:

- `TARGET_REGIMES`
- `REGIME_FILTER_MODE`

도 함께 확인해야 한다.

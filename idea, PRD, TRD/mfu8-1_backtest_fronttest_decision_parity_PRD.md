# [PRD] MFU8-1: Score / RS / Signal Parity 검증 자동화 v1.0

## 0. Context & Status

### 배경

현재 프로젝트는 백테스트와 프론트테스트가 일부 공용 함수를 사용하지만, 아직 같은 엔진을 공유하는 구조는 아니다.

선행 작업으로 다음 개선이 완료되었다.

- front-test stale candidate filter
- candidate filter diagnostics
- holding score recomputation
- `symbol_diff_removed` 기반 `STRATEGY_EXIT`를 immediate SELL에서 `REVIEW_EXIT`로 전환
- journal row와 review item 분리

하지만 다음 문제는 아직 남아 있다.

- 동일 종목 / 동일 기준일에서 backtest와 front-test가 같은 `score`를 내는지 자동 검증하지 않는다.
- 동일 종목 / 동일 기준일에서 backtest와 front-test가 같은 `rs_val`을 내는지 자동 검증하지 않는다.
- `buy_signal`과 front-test `entry_signal`이 같은 의미로 계산되는지 자동 검증하지 않는다.
- 새 전략 weight나 signal column을 추가했을 때 한쪽 엔진에만 반영되는 문제를 자동으로 잡지 못한다.

### MFU8 전체 목표

MFU8의 전체 목표는 백테스트에 추가한 전략, 유니버스, 매매 판단이 프론트테스트에도 누락 없이 반영되는 체계를 만드는 것이다.

### MFU8-1 목표

MFU8-1은 전체 MFU8 중 첫 단계로, 다음을 목표로 한다.

- 동일 `data_date` / 동일 `symbol` 기준으로 backtest와 front-test의 `score`, `rs_val`, `buy/entry signal` 산출값을 비교한다.
- 전략 weight와 signal column 계약이 backtest/front-test 양쪽에서 어긋나지 않는지 정적으로 검증한다.
- front-test action/reason 문자열을 최소 범위에서 상수화하되, 기존 backtest `ReasonCode`와 충돌하지 않게 한다.

## 1. 범위 (Scope)

### In-Scope

- `scripts/check_decision_parity.py` 생성
- `scripts/validate_strategy_sync.py` 생성
- front-test reason/action 문자열의 최소 상수화
- backtest/front-test score 산출값 비교
- backtest/front-test `rs_val` 산출값 비교
- backtest `buy_signal`과 front-test `entry_signal` 비교
- signal column naming 계약 점검
- active weight key와 indicator/strategy pipeline 매핑 점검

### Out-of-Scope

- backtest/front-test 전체 아키텍처 통합
- sell policy 정렬을 위한 전략 정책 변경
- `target_state` / `rebalance` 정책 변경
- broker 주문 연동 추가
- DB 스키마 변경
- PortfolioDB와 current_state snapshot 통합
- full orchestration parity 검증
- universe snapshot / stale guard / review-only formatting의 동작 변경

## 2. 요구사항 (Requirements)

## Req 1. Reason / Action 상수 체계 정리

- 기존 `backtesting/reason_codes.py`가 backtest의 reason SSOT 역할을 하므로, 새 `ReasonCode`를 별도로 이중 정의하지 않는다.
- 필요한 경우 아래 중 하나를 선택한다.
  - 기존 `backtesting/reason_codes.py` 재사용
  - front-test 전용 최소 `ActionType` 또는 local constants만 별도 정의
- `daily_plan_generator.py`의 `"BUY"`, `"SELL"`, `"REVIEW_EXIT"` 같은 하드코딩 문자열은 가능한 범위에서 상수화한다.
- 단, 기존 markdown report와 journal 포맷은 유지해야 한다.
- `WAIT`는 실제 action item으로 쓰이는지 불명확하므로 MFU8-1에서는 기본 ActionType에 포함하지 않는다.

권장 최소 상수 예시:

```python
ACTION_BUY = "BUY"
ACTION_SELL = "SELL"
REVIEW_EXIT = "REVIEW_EXIT"
```

또는 필요 시:

```python
from enum import Enum

class ActionType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class ReviewReason(str, Enum):
    REVIEW_EXIT = "REVIEW_EXIT"
```

## Req 2. 정적 동기화 검증 스크립트: `scripts/validate_strategy_sync.py`

검증 기준은 `config.py` 단독이 아니라 `core.config_factory.make_config(...)`와 `get_regime_config(...)`로 조립한 `merged_config`여야 한다.

검사 대상:

1. active weight key 목록
2. 각 weight key에 대응되는 indicator / strategy pipeline 존재 여부
3. `compute_candidate_score()`가 기대하는 signal column 계약과의 정합성
4. backtest와 front-test가 같은 signal column naming 계약을 사용할 수 있는지

검증 실패 시:

- 누락/불일치가 있으면 non-zero exit로 종료한다.
- 실패 메시지에는 어떤 weight / signal / pipeline이 누락되었는지 표시한다.

## Req 3. Signal Column Alias Contract

전략별 signal column 이름이 항상 `signal_{name}` 형태라고 가정하면 안 된다.

초기 signal alias map은 다음 계약을 기준으로 한다.

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

`validate_strategy_sync.py`는 이 alias map을 기준으로 각 전략 weight가 실제 생성 가능한 signal column과 연결되는지 검사해야 한다.

## Req 4. 결정 산출 parity 스크립트: `scripts/check_decision_parity.py`

스크립트는 다음 인자를 받는다.

```bash
python scripts/check_decision_parity.py --date 2026-05-04 --symbol AAPL
```

요구사항:

- `--date`, `--symbol` 인자를 받는다.
- 입력 날짜는 `plan_date`일 수 있으나, 실제 비교 기준은 `market_state["date"]`로 계산된 `data_date`여야 한다.
- parity 비교 범위는 1차적으로 아래만 포함한다.
  - `score`
  - `rs_val`
  - `buy_signal` 또는 front-test의 동등 개념인 `entry_signal`

1차 parity에서는 아래 운영 보호 로직은 비교 대상에서 제외하거나 별도 출력으로 분리한다.

- universe snapshot removed guard
- stale candidate filter
- review-only rebalance formatting
- journal row formatting

## Req 5. `check_decision_parity.py`의 산출값 기준

backtest 방식 산출:

- 동일 종목의 price history 로드
- backtest와 동일한 indicator / strategy / RS 파이프라인 적용
- 최종 `score`, `rs_val`, `buy_signal` 추출

front-test 방식 산출:

- front-test helper 또는 동등 경로로 동일 종목을 평가
- 최종 `score`, `rs_val`, `entry_signal` 추출
- 만약 front-test helper가 `entry_signal`을 직접 반환하지 않으면, 1차 구현에서는 다음 기준으로 재구성한다.

```python
entry_signal = (score >= score_threshold) and (rs_val > 0)
```

주의:

- 이 `entry_signal` 재구성은 front-test 전체 orchestration과 완전히 동일하다고 단정하지 않는다.
- MFU8-1에서는 단일 종목 산출값 parity를 먼저 검증한다.

## Req 6. Parity 판정 기준

기본 허용 오차:

```python
abs(diff) < 0.001
```

적용 대상:

- `score`
- `rs_val`

Boolean 비교:

```python
bool(bt_buy_signal) == bool(ft_entry_signal)
```

데이터 부족 처리:

- 양쪽 모두 계산 불가: `SKIP` 또는 `INCONCLUSIVE`
- 한쪽만 계산 가능: `FAIL`
- benchmark 부족: `INCONCLUSIVE`
- indicator history 부족: `INCONCLUSIVE`
- symbol price data 없음: `SKIP`
- 계산 중 예외 발생: `FAIL`, 단 원인 메시지 표시

## 3. 수용 기준 (Acceptance Criteria)

1. `python scripts/validate_strategy_sync.py` 실행 시 Exit Code 0으로 통과해야 한다.
2. `python scripts/check_decision_parity.py --date 2026-05-04 --symbol AAPL` 실행 시 backtest 산출값과 front-test 산출값을 같은 `data_date` 기준으로 출력해야 한다.
3. parity 허용 오차는 문서와 코드에서 모두 `abs(diff) < 0.001`로 일관되어야 한다.
4. 데이터 부족, benchmark 부족, indicator history 부족은 `FAIL`과 구분되어야 한다.
5. `python scripts/run_front_test.py` 실행 시 상수화 이후에도 기존 report 구조와 journal header는 유지되어야 한다.
6. `REVIEW_EXIT`는 journal row에 들어가지 않아야 한다.
7. 기존 markdown report section은 깨지지 않아야 한다.

## 4. 비기능 요구사항

- DB write 금지
- 기존 CLI behavior 보존
- look-ahead bias 금지
- parity 스크립트는 실패 시 무엇이 달랐는지 바로 읽을 수 있게 출력해야 한다.
- 외부 dependency 추가 금지
- full backtest run을 강제하지 말 것
- 가능한 read-only price/history 로딩만 사용한다.

## 5. 검증 명령

```bash
python -m py_compile scripts/validate_strategy_sync.py
python -m py_compile scripts/check_decision_parity.py

python scripts/validate_strategy_sync.py
python scripts/check_decision_parity.py --date 2026-05-04 --symbol AAPL
python scripts/check_decision_parity.py --date 2026-05-04 --symbol TSLA

python scripts/run_front_test.py
```

## 6. 후속 단계

MFU8-1 완료 후 다음을 검토한다.

- MFU8-2: Action / Review / Warning taxonomy 정리
- MFU8-3: SELL path parity 검증
- MFU8-4: 신규 전략 추가 체크리스트 자동화 강화
- MFU8-5: 신규 유니버스 추가 체크리스트 및 universe parity 검증
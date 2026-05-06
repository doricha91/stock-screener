## [PRD] MFU8: 요구사항 및 수용 기준

**1. 범위 (Scope)**

- In-Scope
  - `scripts/check_decision_parity.py` 생성
  - `scripts/validate_strategy_sync.py` 생성
  - front-test reason/action 문자열의 상수화 최소 정리
- Out-of-Scope
  - backtest/front-test 전체 아키텍처 통합
  - sell policy 정렬을 위한 전략 정책 변경
  - broker 주문 연동 추가

**2. 요구사항 (Requirements)**

**Req 1. Reason/Action 상수 체계 정리**

- 기존 `backtesting/reason_codes.py`가 이미 backtest의 reason SSOT 역할을 하고 있으므로, 새 `ReasonCode`를 별도 이중 정의하지 않는다.
- 필요한 경우 아래 중 하나를 선택한다.
  - 기존 `backtesting/reason_codes.py` 재사용
  - front-test 전용 최소 `ActionType`만 별도 정의
- `daily_plan_generator.py`의 `"BUY"`, `"SELL"`, `"REVIEW_EXIT"` 같은 하드코딩 문자열은 가능한 범위에서 상수화한다.
- 단, 기존 markdown report와 journal 포맷은 유지해야 한다.

**Req 2. 정적 동기화 검증 스크립트 (`scripts/validate_strategy_sync.py`)**

- 검증 기준은 `config.py` 단독이 아니라 `core.config_factory.make_config(...)`로 조립한 `merged_config`여야 한다.
- 아래 3가지를 검사한다.
  - active weight key 목록
  - 대응되는 indicator/strategy pipeline 존재 여부
  - `compute_candidate_score()`가 기대하는 signal column 계약과의 정합성
- 누락/불일치가 있으면 non-zero exit로 종료한다.

**Req 3. 결정 산출 parity 스크립트 (`scripts/check_decision_parity.py`)**

- `--date`, `--symbol` 인자를 받는다.
- 비교 기준일은 `plan_date`가 아니라 실제 계산 기준인 `data_date`를 사용해야 한다.
- parity 비교 범위는 1차적으로 아래만 포함한다.
  - `score`
  - `rs_val`
  - `buy_signal` 또는 front-test의 동등 개념인 `entry_signal`
- 1차 parity에서는 아래 운영 보호 로직은 비교 대상에서 제외하거나 별도 출력으로 분리한다.
  - universe snapshot removed guard
  - stale candidate filter
  - review-only rebalance formatting

**3. 수용 기준 (Acceptance Criteria)**

1. `python scripts/validate_strategy_sync.py` 실행 시 Exit Code 0으로 통과해야 한다.
2. `python scripts/check_decision_parity.py --date 2026-05-04 --symbol AAPL` 실행 시 backtest 산출값과 front-test 산출값을 같은 `data_date` 기준으로 출력해야 한다.
3. parity 허용 오차는 문서 전체에서 일관되게 정의한다.
   - 기본 기준: `abs(diff) < 0.001`
4. `python scripts/run_front_test.py` 실행 시 상수화 이후에도 기존 report 구조와 journal header는 유지되어야 한다.

**4. 비기능 요구사항**

- DB write 금지
- 기존 CLI behavior 보존
- look-ahead bias 금지
- parity 스크립트는 실패 시 무엇이 달랐는지 바로 읽을 수 있게 출력해야 한다.

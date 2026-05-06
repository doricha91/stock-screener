# MFU8: Backtest-Fronttest Decision Parity 검증 자동화

## [IDEA] MFU8: 매매 판단 정합성 검증 스크립트 및 Reason 코드 정리

**1. 배경 및 목적 (Why & What)**

현재 `daily_plan_generator.py`와 `core/backtest_engine.py`는 비슷한 점수/신호 체계를 사용하지만, 동일한 입력에 대해 실제로 같은 `score`, `rs_val`, `entry/buy signal`을 산출하는지 자동으로 검증하는 장치가 없습니다.

이 MFU의 목적은 두 엔진을 병합하는 것이 아닙니다. 대신 아래 두 가지를 달성하는 것입니다.

1. 동일한 `data_date`와 동일한 종목 데이터에 대해 backtest 산출값과 front-test 산출값이 일치하는지 점검하는 parity 체크 스크립트를 만든다.
2. front-test의 action/reason 문자열을 더 안정적으로 다루기 위해 상수 체계를 정리하되, 기존 backtest의 `ReasonCode` 체계와 충돌하지 않게 한다.

핵심 전제는 다음입니다.

- SSOT는 `config.py` 단독이 아니라 `core.config_factory.make_config(...)`로 조립된 `merged_config`이다.
- parity 대상은 "전체 front-test 결과"가 아니라 "동일 as-of 데이터에 대한 단일 종목 score/rs/signal 산출"이다.
- universe snapshot guard, stale filter, review-only action formatting 같은 운영 보호 로직은 parity 1차 범위에서 분리한다.

**2. Codex 행동 지침 (Actionable Directive)**

- 절대 금지:
  - `backtest_engine.py`의 핵심 루프를 리팩토링하지 말 것
  - DB 스키마를 건드리지 말 것
  - front-test 전체 orchestration을 갈아엎지 말 것
- 핵심 목표:
  1. `scripts/check_decision_parity.py`를 만들어, 동일 종목/동일 `data_date` 기준의 산출값 parity를 검증한다.
  2. `scripts/validate_strategy_sync.py`를 만들어, `merged_config` 기반 active weight와 indicator/strategy/signal 컬럼 계약이 어긋나지 않는지 검사한다.
  3. reason code 정리는 기존 `backtesting/reason_codes.py`와의 관계를 고려해 최소 범위로 진행한다. 별도 새 체계를 만들더라도 이중 SSOT를 만들지 않는다.

**3. 이번 MFU에서 해결하려는 문제**

- 새 전략 weight가 추가되었는데 한쪽 엔진에서만 반영되는 문제
- front-test와 backtest가 같은 종목을 서로 다른 score로 평가하는 문제
- reason 문자열이 하드코딩되어 유지보수 중 오타/드리프트가 발생하는 문제

**4. 이번 MFU에서 해결하지 않는 문제**

- front-test와 backtest의 전체 sell policy 통합
- `target_state`/`rebalance` 정책 자체 변경
- screener freshness guard 정책 변경
- live trading 로직 추가

**5. 성공 기준**

- parity 스크립트가 동일 종목/동일 일자 기준 `score`, `rs_val`, `entry/buy signal` 차이를 명확히 보여준다.
- 전략 동기화 검증 스크립트가 누락된 weight/indicator/strategy mapping을 fail로 잡아낸다.
- reason code 정리가 기존 리포트/저널 포맷을 깨지 않는다.

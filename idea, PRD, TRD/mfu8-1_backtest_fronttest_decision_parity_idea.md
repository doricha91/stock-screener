# MFU8-1: Backtest-Fronttest Score / RS / Signal Parity 검증 자동화

## [IDEA] MFU8-1: 매매 판단 산출값 정합성 검증 스크립트 및 Reason/Action 코드 정리

## 1. 배경 및 목적 (Why & What)

현재 `daily_plan_generator.py`와 `core/backtest_engine.py`는 비슷한 점수/신호 체계를 사용하지만, 동일한 입력에 대해 실제로 같은 `score`, `rs_val`, `entry/buy signal`을 산출하는지 자동으로 검증하는 장치가 없다.

최근 front-test 개선 과정에서 다음 문제가 확인되었다.

- 보유 종목이 신규 후보군에 없으면 `score = 0.0`으로 처리되는 문제가 있었다.
- `rebalance.symbol_diff_removed`가 front-test에서는 즉시 SELL로 표시되었지만, backtest에서는 직접 매도 실행 경로로 확인되지 않았다.
- 이후 `symbol_diff_removed` 기반 SELL은 `REVIEW_EXIT`로 낮춰졌지만, 여전히 backtest/front-test 판단 산출값이 같은지 검증하는 장치는 없다.

MFU8 전체의 최종 목표는 백테스트에 추가한 전략, 유니버스, 매매 판단이 프론트테스트에도 누락 없이 반영되는 구조를 만드는 것이다.

MFU8-1은 그중 첫 단계로, 전체 엔진 통합이 아니라 다음 두 가지를 달성한다.

1. 동일한 `data_date`와 동일한 종목 데이터에 대해 backtest 산출값과 front-test 산출값이 일치하는지 점검하는 parity 체크 스크립트를 만든다.
2. front-test의 action/reason 문자열을 더 안정적으로 다루기 위해 상수 체계를 정리하되, 기존 backtest의 `ReasonCode` 체계와 충돌하지 않게 한다.

## 2. 핵심 전제

- SSOT는 `config.py` 단독이 아니라 `core.config_factory.make_config(...)`와 `get_regime_config(...)`로 조립된 `merged_config`이다.
- parity 대상은 “전체 front-test 결과”가 아니라 “동일 as-of 데이터에 대한 단일 종목 score / rs_val / signal 산출”이다.
- universe snapshot guard, stale filter, review-only action formatting 같은 운영 보호 로직은 parity 1차 범위에서 분리한다.
- MFU8-1은 sell policy 전체를 동기화하지 않는다.
- MFU8-1은 backtest/front-test 전체 아키텍처를 병합하지 않는다.

## 3. Codex 행동 지침 (Actionable Directive)

### 절대 금지

- `core/backtest_engine.py`의 핵심 루프를 리팩토링하지 말 것
- DB 스키마를 건드리지 말 것
- front-test 전체 orchestration을 갈아엎지 말 것
- sell policy를 임의로 변경하지 말 것
- `target_state` / `rebalance` 정책 자체를 변경하지 말 것
- live trading 로직을 추가하지 말 것

### 핵심 목표

1. `scripts/check_decision_parity.py`를 만들어, 동일 종목 / 동일 `data_date` 기준의 산출값 parity를 검증한다.
2. `scripts/validate_strategy_sync.py`를 만들어, `merged_config` 기반 active weight와 indicator / strategy / signal column 계약이 어긋나지 않는지 검사한다.
3. reason/action code 정리는 기존 `backtesting/reason_codes.py`와의 관계를 고려해 최소 범위로 진행한다.
4. 별도 새 reason 체계를 만들더라도 이중 SSOT를 만들지 않는다.
5. 기존 markdown report와 journal table 포맷은 깨지 않는다.

## 4. 이번 MFU에서 해결하려는 문제

- 새 전략 weight가 추가되었는데 backtest 또는 front-test 한쪽에만 반영되는 문제
- front-test와 backtest가 같은 종목을 서로 다른 score로 평가하는 문제
- front-test와 backtest가 같은 종목을 서로 다른 `rs_val`로 평가하는 문제
- `buy_signal`과 `entry_signal`의 의미가 드리프트되는 문제
- reason/action 문자열이 하드코딩되어 유지보수 중 오타나 drift가 발생하는 문제

## 5. 이번 MFU에서 해결하지 않는 문제

- front-test와 backtest의 전체 sell policy 통합
- `target_state` / `rebalance` 정책 자체 변경
- screener freshness guard 정책 변경
- universe snapshot 정책 변경
- live trading 로직 추가
- broker 주문 연동
- PortfolioDB와 current_state snapshot의 완전 통합
- 수익률 계산 자동화
- full orchestration parity

## 6. 성공 기준

- parity 스크립트가 동일 종목 / 동일 일자 기준 `score`, `rs_val`, `entry/buy signal` 차이를 명확히 보여준다.
- 전략 동기화 검증 스크립트가 누락된 weight / indicator / strategy / signal column mapping을 fail로 잡아낸다.
- 데이터 부족, benchmark 부족, indicator history 부족 같은 케이스는 `FAIL`과 구분하여 `SKIP` 또는 `INCONCLUSIVE`로 표시할 수 있다.
- reason/action code 정리가 기존 리포트와 journal 포맷을 깨지 않는다.
- `python scripts/run_front_test.py`가 기존 report section과 journal header를 유지한 채 실행된다.

## 7. MFU8 전체에서의 위치

MFU8-1은 전체 MFU8의 첫 단계다.

전체 MFU8은 다음 흐름으로 확장된다.

1. MFU8-1: Score / RS / Entry Signal parity 검증 자동화
2. MFU8-2: Action / Review / Warning taxonomy 정리
3. MFU8-3: SELL path parity 검증
4. MFU8-4: 신규 전략 추가 체크리스트 및 자동 검증 강화
5. MFU8-5: 신규 유니버스 추가 체크리스트 및 universe parity 검증
6. MFU8-6: portfolio state / EOD update / journal 흐름 정합성 검증

## 8. 리스크와 한계

- 단일 종목 산출값 parity가 맞아도 전체 front-test 결과가 backtest와 완전히 같다는 뜻은 아니다.
- front-test에는 stale guard, universe removed guard, REVIEW_EXIT 같은 운영 보호 로직이 존재한다.
- 백테스트는 과거 시뮬레이션이고, front-test는 current_state snapshot 기반이라 완전 동일화가 어렵다.
- MFU8-1은 sell policy 정렬이 아니라 score / RS / signal 산출값 정합성을 먼저 확인하는 단계다.
# MFU-PAPER6-9C 작업 지시문: paper daily plan switching parity 수정

## 목적

`paper daily plan`의 SWITCH_IN / SWITCH_OUT 로직을 백테스트 정책과 맞춘다.

확정 정책:

```text
1. max_positions full gate는 도입하지 않는다.
2. target_long_slots gate도 도입하지 않는다.
3. regime별 target_cash_ratio는 기존처럼 buying power 계산에만 사용한다.
4. switch-in 후보는 백테스트처럼 buy_signal=True 후보만 허용한다.
5. same-day duplicate BUY는 금지한다.
```

이번 작업은 paper daily plan의 switch 후보군과 action 합성 버그를 수정하는 단계다.

## 배경

MFU-PAPER6-9B 조사 결과:

- 백테스트는 SELL → SWITCH → 일반 BUY 순서로 작동한다.
- 백테스트 switch 후보군은 `buy_signal=True`만 사용한다.
- `buy_signal = score >= score_threshold AND rs_val > 0`.
- 백테스트에는 max_positions가 꽉 찼을 때만 switch하는 gate는 없다.
- paper daily plan은 `score >= threshold`만 통과한 더 넓은 후보군을 switch에 사용했다.
- 그래서 `rs_lte_0 fail` 후보도 switch-in 가능했다.
- 2026-05-13에는 F가 SWITCH_IN과 STRATEGY_ENTRY로 중복 BUY됐다.

## 수정 대상

우선 확인/수정:

```text
core/daily_plan_generator.py
core/backtest_engine.py
core/target_portfolio_state.py
tests/*switch*
tests/*paper_daily_plan*
```

실제 경로가 다르면 검색해서 관련 함수 기준으로 수정한다.

## 구현 요구사항

### 1. switch 후보군을 buy_signal=True로 제한

paper daily plan의 switching candidate pool을 백테스트와 맞춘다.

기존 문제:

```text
score >= score_threshold만 통과한 후보가 switch-in 가능
```

수정 후:

```text
switch-in 후보 = buy_signal=True
buy_signal = score >= score_threshold AND rs_val > 0
```

주의:

```text
- Candidate Filter Diagnostics에서 rs_lte_0 fail인 종목은 switch-in 금지
- CF/BRK-B 같은 fail 후보가 다시 SWITCH_IN 되면 안 됨
- entry_signal이 별도라면 백테스트의 buy_signal 정의를 우선한다
```

### 2. max_positions / target_long_slots gate 추가 금지

다음 조건은 추가하지 않는다.

```text
current_positions >= max_positions
current_positions >= target_long_slots
```

switch는 백테스트처럼 슬롯이 꽉 차지 않아도 조건이 맞으면 가능하다.

### 3. target_cash_ratio 정책 유지

regime별 `target_cash_ratio`는 유지한다.

```text
사용 위치:
- buying power 계산
- 신규 BUY 수량 계산
- 현금 정책 표시

사용하지 않을 위치:
- switch 허용 여부 gate
```

### 4. same-day duplicate BUY 방지

같은 daily plan 안에서 동일 symbol BUY는 1회만 허용한다.

특히 아래 상황을 막는다.

```text
F BUY 693  SWITCH_IN
F BUY 734  STRATEGY_ENTRY
```

수정 방향:

```text
- SWITCH_IN으로 추가된 symbol은 이후 STRATEGY_ENTRY 후보에서 제외
- 또는 daily action 합성 마지막 단계에서 BUY symbol dedupe
- 단, 조용히 합산하지 말고 백테스트처럼 중복 후보를 제외하는 방향 권장
```

### 5. reason / diagnostics 일관성

수정 후 action과 diagnostics가 충돌하면 안 된다.

```text
Result fail / rs_lte_0 후보가 SWITCH_IN으로 표시되면 실패
```

## 절대 금지

```text
- production output 직접 수정 금지
- paper_execution_log.csv 수정 금지
- snapshot 파일 수정 금지
- outputs/front_test 수정 금지
- DB 수정 금지
- --commit 실행 금지
- max_positions full gate 추가 금지
- target_long_slots gate 추가 금지
- 대규모 리팩토링 금지
```

## 테스트 추가/수정

권장 테스트:

```text
tests/test_paper_switching_parity.py
```

필수 테스트:

```text
1. rs_val <= 0 후보는 score가 높아도 SWITCH_IN 불가
2. buy_signal=True 후보만 SWITCH_IN 가능
3. max_positions 미만이어도 switch 조건 자체는 평가 가능
4. target_cash_ratio는 buying power에는 반영되지만 switch gate에는 쓰이지 않음
5. 같은 symbol이 SWITCH_IN과 STRATEGY_ENTRY로 중복 BUY되지 않음
6. 2026-05-12 유사 fixture에서 CF/BRK-B가 rs_lte_0이면 switch-in 제외
7. 2026-05-13 유사 fixture에서 F 중복 BUY 방지
```

기존 테스트도 유지:

```bat
set PYTHONPATH=.

python -m pytest tests/test_paper_switching_parity.py -q
python -m pytest tests/test_paper_daily_plan_generation.py -q
python -m pytest tests/test_daily_plan_switch_symbol_mapping.py -q
python -m pytest tests/test_paper_eod_plan_path.py -q
python -m pytest tests/test_paper_account_state.py -q

python -m py_compile core/daily_plan_generator.py core/backtest_engine.py
```

## 수동 smoke

이번 MFU에서는 commit하지 않는다.

```bat
set PYTHONPATH=.

python scripts/run_paper_daily_plan.py --date 20260512
python scripts/run_paper_daily_plan.py --date 20260513
```

확인:

```text
- outputs/paper_test daily plan 생성
- rs_lte_0 fail 후보가 SWITCH_IN으로 나오지 않음
- 20260513에서 F BUY가 중복으로 나오지 않음
- outputs/front_test 변경 없음
- paper_execution_log / snapshots 변경 없음
```

## 성공 기준

```text
- paper switch 후보군이 buy_signal=True로 제한됨
- diagnostics fail 후보가 switch-in 되지 않음
- same-day duplicate BUY가 방지됨
- max_positions full gate는 추가되지 않음
- target_long_slots gate도 추가되지 않음
- target_cash_ratio는 buying power에만 기존처럼 적용됨
- 기존 paper EOD preview/commit 관련 테스트 영향 없음
```

## 결과 보고 형식

5천자 이내.

포함 항목:

```text
1. Summary
2. 변경 파일
3. switch 후보군 수정 내용
4. duplicate BUY 방지 방식
5. max_positions/target_long_slots gate 미도입 확인
6. target_cash_ratio 적용 범위 확인
7. 테스트 결과
8. 20260512/20260513 smoke 결과
9. outputs/front_test 변경 여부
10. paper_execution_log/snapshot 변경 여부
11. 남은 위험 / 다음 단계
```
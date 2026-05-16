# MFU-PAPER6-4A 작업 지시문: SWITCH_IN symbol mapping bug 조사/수정

## 목적

`run_paper_daily_plan.py --date 2026-05-12` smoke에서 생성된 paper daily action plan의 `SWITCH_IN` row에 symbol이 실제 ticker가 아니라 `0`, `2`처럼 숫자로 표시되는 문제를 조사하고 수정한다.

이번 MFU는 SWITCH_IN symbol mapping 문제만 다룬다.  
date normalize 문제는 후속 MFU-PAPER6-4B로 분리한다.

## 배경

MFU-PAPER6-3 smoke 결과:

- `python scripts/run_paper_daily_plan.py --date 2026-05-12` 실행 성공
- `outputs/paper_test/daily_action_plan_20260512.md` 생성 성공
- paper state / cash / holdings 반영 확인
- commit / 체결 반영 없음
- paper_execution_log.csv / snapshots 변경 없음
- 단, generated plan의 `SWITCH_IN` row에 symbol이 `0`, `2`로 표시되는 이상 동작 관찰

## 핵심 가설

가능성:

1. pandas DataFrame index가 symbol 대신 사용됨
2. candidate ranking 결과에서 symbol 컬럼을 잘못 참조함
3. `enumerate()` index가 symbol 자리에 들어감
4. switch-in row 생성 시 row.name 또는 index를 ticker처럼 사용함
5. paper state 주입 이후 candidate/current_symbols mapping이 어긋남
6. 기존 front daily plan에서도 있었지만 paper smoke에서 처음 발견된 문제일 수 있음

## 조사 대상

우선 아래 파일을 확인한다.

```text
core/daily_plan_generator.py
scripts/run_paper_daily_plan.py
scripts/run_front_test.py
core/paper_state_provider.py
```

필요하면 아래도 확인한다.

```text
screener 관련 ranking/candidate 생성 모듈
strategy signal 생성 모듈
daily action plan markdown renderer
```

## 조사 질문

1. `SWITCH_IN` row는 어디서 생성되는가?
2. 해당 row의 symbol 값은 어떤 변수에서 오는가?
3. BUY row와 SWITCH_IN row의 symbol 생성 경로가 다른가?
4. symbol 컬럼명이 `symbol`, `ticker`, `Symbol`, `Ticker` 중 무엇인가?
5. DataFrame index가 symbol처럼 사용되는 지점이 있는가?
6. paper mode에서만 발생하는가, front mode에서도 발생 가능한가?
7. `outputs/paper_test/daily_action_plan_20260512.md`의 원본 row 구조상 실제 symbol 데이터가 이미 깨졌는가, markdown 렌더링에서만 깨지는가?

## 수정 원칙

- `SWITCH_IN` symbol은 반드시 실제 ticker 문자열이어야 한다.
- 숫자 index를 ticker로 사용하면 안 된다.
- BUY / SWITCH_IN / SELL row 모두 동일한 symbol normalization 규칙을 사용한다.
- ticker가 없거나 비어 있으면 조용히 숫자로 대체하지 말고 명확히 error 또는 skip 처리한다.
- 기존 front-test 동작을 깨지 않는다.
- paper state provider 구조는 건드리지 않는다.

## 권장 수정 방향

가능하면 작은 helper를 둔다.

```python
def extract_candidate_symbol(row) -> str:
    ...
```

또는 기존 helper가 있다면 재사용한다.

우선순위:

```text
1. row["symbol"]
2. row["ticker"]
3. row["Symbol"]
4. row["Ticker"]
```

단, `row.name`, DataFrame index, enumerate index를 symbol fallback으로 쓰지 않는다.

유효성:

```text
- symbol은 str이어야 함
- strip 후 비어 있으면 invalid
- 숫자만 있는 값은 ticker로 인정하지 않음
```

단, 실제 숫자 ticker가 존재할 수 있는 시장 확장 가능성은 있지만, 현재 US stock paper mode에서는 숫자-only symbol을 허용하지 않는 것이 안전하다.

## 절대 금지

- paper_execution_log.csv 수정 금지
- paper_account_snapshot.csv 수정 금지
- paper_position_snapshot.csv 수정 금지
- outputs/front_test 수정 금지
- DB schema / DB files 수정 금지
- run_paper_eod_update.py commit 흐름 변경 금지
- date normalize 수정 금지
- benchmark / MDD / CAGR / Sharpe 추가 금지
- 대규모 리팩토링 금지

## 테스트 추가/수정

권장 테스트 파일:

```text
tests/test_daily_plan_switch_symbol_mapping.py
```

또는 기존:

```text
tests/test_paper_daily_plan_generation.py
```

에 추가해도 된다.

필수 테스트:

1. SWITCH_IN row가 실제 ticker를 사용하는지
   - candidate DataFrame index가 0, 2여도 symbol은 실제 ticker여야 함

2. row.name/index를 symbol로 쓰지 않는지
   - index가 숫자일 때도 output symbol이 숫자가 아니어야 함

3. symbol 컬럼 누락 시 명확한 실패
   - 잘못된 `0`, `2`로 대체하지 않음

4. BUY row 기존 동작 유지

5. paper daily plan smoke fixture
   - paper state 주입 상태에서도 SWITCH_IN symbol이 ticker로 생성되는지 확인

가능하면 실제 smoke 산출물과 유사한 candidate 구조를 fixture로 만든다.

## 수동 검증

기존 성공 형식인 dashed date를 사용한다.

```bat
set PYTHONPATH=.
python scripts/run_paper_daily_plan.py --date 2026-05-12
```

생성 파일 확인:

```bat
type outputs\paper_test\daily_action_plan_20260512.md
```

확인할 것:

```text
- SWITCH_IN row symbol이 0, 2가 아님
- 실제 ticker 문자열로 표시됨
- BUY / SELL / HOLD / SWITCH_OUT row가 깨지지 않음
```

오염 확인:

```bat
git status --short outputs\front_test outputs\paper_test
git diff -- outputs\front_test
```

허용되는 변경:

```text
outputs/paper_test/daily_action_plan_20260512.md
```

허용되지 않는 변경:

```text
outputs/front_test/*
outputs/paper_test/paper_execution_log.csv
outputs/paper_test/paper_account_snapshot.csv
outputs/paper_test/paper_position_snapshot.csv
```

## 검증 명령

```bat
set PYTHONPATH=.

python -m pytest tests/test_daily_plan_switch_symbol_mapping.py -q
python -m pytest tests/test_paper_daily_plan_generation.py -q
python -m pytest tests/test_paper_state_provider.py -q
python -m pytest tests/test_paper_account_state.py -q

python -m py_compile core/daily_plan_generator.py scripts/run_paper_daily_plan.py
```

테스트 파일명을 다르게 만들었다면 실제 파일명에 맞춰 실행한다.

## 성공 기준

- SWITCH_IN row symbol이 실제 ticker로 표시됨
- 숫자 index가 symbol로 출력되지 않음
- symbol 누락/invalid 케이스가 명확히 처리됨
- 기존 front-test 기본 동작 영향 없음
- paper state provider 영향 없음
- outputs/front_test 변경 없음
- paper_execution_log / snapshots 변경 없음
- date normalize는 이번 MFU에서 건드리지 않음

## 결과 보고 형식

5,000자 이내로 작성한다.

포함할 항목:

1. Summary
2. 원인 분석
3. 변경 파일
4. 수정 내용
5. 추가/수정 테스트
6. 수동 smoke 결과
7. SWITCH_IN row 검증 결과
8. 기존 front-test 영향 여부
9. 변경하지 않은 범위
10. 남은 위험 / 다음 단계

반드시 명시할 것:

- 원인이 DataFrame index 사용이었는지 여부
- SWITCH_IN symbol이 실제 ticker로 수정됐는지
- outputs/front_test 변경 여부
- paper_execution_log / snapshot 변경 여부
- date normalize는 아직 처리하지 않았는지
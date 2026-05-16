# MFU-PAPER6-2 작업 지시문: paper official daily plan 생성 연결

## 목적

공식 paper 계좌 상태를 기준으로 daily action plan을 생성할 수 있게 한다.

이번 작업은 B안으로 진행한다.

```text
scripts/run_front_test.py
= 기존 front sandbox daily plan 유지

scripts/run_paper_daily_plan.py
= paper_execution_log.csv + reducer 기반 공식 paper daily plan 생성
```

핵심은 `core/daily_plan_generator.py`의 state load / output path 하드코딩을 최소한으로 분리하고, paper 계좌 state를 주입할 수 있게 만드는 것이다.

## 선행 조사 요약

MFU-PAPER6-1 조사 결과:

- `run_front_test.py`는 orchestration wrapper에 가깝다.
- 실제 daily plan 생성 핵심은 `core/daily_plan_generator.py`에 있다.
- 현재 generator는 내부에서 `load_current_state()`를 직접 호출한다.
- output path도 `FRONT_TEST_DIR / daily_action_plan_YYYYMMDD.md`로 고정되어 있다.
- `PaperAccountState → CurrentPortfolioState` 호환 변환은 `paper_current_state_serializer.py`로 가능하다.
- paper mode buying power는 `PaperAccountState.cash`를 `absolute_cash`로 넘기면 기존 cash policy 로직을 재사용할 수 있다.

## 확정 정책

1. `front_state`
   - 관찰용 sandbox
   - 기존 `run_front_test.py`는 유지

2. `paper_state`
   - 공식 paper 계좌
   - source of truth는 `outputs/paper_test/paper_execution_log.csv + reducer`

3. 신규 script
   - `scripts/run_paper_daily_plan.py`

4. 출력 경로
   - `outputs/paper_test/daily_action_plan_YYYYMMDD.md`

5. 이번 단계 범위
   - paper 계좌 기반 daily plan 생성까지만
   - paper execution log append / commit은 하지 않음
   - 기존 `run_paper_eod_update.py`가 commit 담당

## 구현 범위

### 1. core/daily_plan_generator.py 최소 수정

기존 `generate_daily_plan()` 동작은 유지한다.

단, 내부 하드코딩을 최소 분리한다.

권장 방향:

```python
def generate_daily_plan(
    target_date=None,
    current_state=None,
    output_path=None,
    ...
):
    if current_state is None:
        current_state = load_current_state(...)
    if output_path is None:
        output_path = front_test_daily_action_plan_path(...)
```

주의:
- 기존 `run_front_test.py`에서 인자를 넘기지 않아도 기존과 동일하게 동작해야 한다.
- 기존 front output 경로가 바뀌면 안 된다.
- 대규모 리팩토링 금지.

### 2. paper state provider 추가

권장 신규 helper 위치:

```text
core/paper_state_provider.py
```

권장 함수:

```python
load_official_paper_state_for_daily_plan(date_str: str) -> CurrentPortfolioState-compatible object
```

역할:

```text
paper_execution_log.csv 읽기
→ build_paper_state_from_trades(...)
→ PaperAccountState 생성
→ paper_account_state_to_current_state_dict(...)
→ daily_plan_generator가 요구하는 구조로 변환
```

주의:
- source of truth는 `paper_current_state_YYYYMMDD.json`이 아니라 `paper_execution_log.csv + reducer`
- `absolute_cash = PaperAccountState.cash`
- `shares`, `avg_price`, `highest_prices`는 serializer 결과 사용
- `current_hedge_ratio=0.0`, `hedge_symbols=[]`는 기존 serializer 정책 사용

### 3. scripts/run_paper_daily_plan.py 추가

역할:

```text
1. --date 인자 받기
2. official paper state 로드
3. output path를 outputs/paper_test/daily_action_plan_YYYYMMDD.md로 지정
4. generate_daily_plan(current_state=paper_state, output_path=paper_output_path) 호출
5. 생성된 path 출력
```

주의:
- commit 없음
- paper_execution_log 수정 없음
- snapshot/report 수정 없음
- daily plan 파일만 생성

## 경로 helper

필요하면 `core/paths.py`에 helper 추가:

```python
paper_daily_action_plan_path(date_str: str) -> Path
```

반드시 `outputs/paper_test/` 아래를 사용한다.

## 절대 금지

- 기존 `run_front_test.py` 동작 변경 금지
- outputs/front_test 출력 경로 변경 금지
- paper_execution_log.csv 수정 금지
- paper_account_snapshot.csv 수정 금지
- paper_position_snapshot.csv 수정 금지
- DB schema / DB files 수정 금지
- run_paper_eod_update.py commit 흐름 변경 금지
- live/broker 관련 구현 금지
- benchmark / MDD / CAGR / Sharpe 구현 금지
- 대규모 리팩토링 금지

## 테스트 추가/수정

권장 테스트:

```text
tests/test_paper_state_provider.py
tests/test_paper_daily_plan_generation.py
```

필수 테스트:

1. 기존 front generate 동작 유지
   - current_state/output_path 미주입 시 기존 front path 사용

2. paper state provider
   - paper_execution_log rows로 PaperAccountState 재구성
   - absolute_cash가 PaperAccountState.cash와 일치
   - shares / avg_price / current_symbols 변환 확인

3. paper output path
   - `outputs/paper_test/daily_action_plan_YYYYMMDD.md` 사용 확인
   - `outputs/front_test` 사용 금지

4. paper daily plan smoke
   - tmp_path 또는 monkeypatch로 실제 outputs 오염 없이 생성
   - paper state의 보유 종목이 current_symbols로 반영되는지 확인

5. buying power 기준
   - paper cash가 absolute_cash로 전달되는지 확인

## 수동 검증 명령

PowerShell 기준:

```powershell
$env:PYTHONPATH="."
python -m pytest tests/test_paper_state_provider.py -q
python -m pytest tests/test_paper_daily_plan_generation.py -q
python -m pytest tests/test_paper_account_state.py -q
python -m pytest tests/test_paper_current_state_serializer.py -q
python -m py_compile core/daily_plan_generator.py core/paper_state_provider.py scripts/run_paper_daily_plan.py
```

기존 front smoke:

```powershell
python scripts/run_front_test.py
```

paper daily plan smoke:

```powershell
python scripts/run_paper_daily_plan.py --date 20260509
```

오염 확인:

```powershell
git status --short outputs\front_test outputs\paper_test
git diff -- outputs\front_test
```

## 성공 기준

- 기존 `run_front_test.py` 동작 유지
- `generate_daily_plan()`이 외부 current_state / output_path를 받을 수 있음
- `run_paper_daily_plan.py` 추가
- paper state는 `paper_execution_log.csv + reducer`에서 생성
- paper daily plan은 `outputs/paper_test/daily_action_plan_YYYYMMDD.md`에 생성
- paper mode buying power가 `PaperAccountState.cash` 기준
- outputs/front_test 오염 없음
- paper_execution_log / snapshot / DB 변경 없음
- run_paper_eod_update.py commit 흐름 변경 없음

## 결과 보고 형식

5,000자 이내로 작성한다.

포함할 항목:

1. Summary
2. 변경 파일
3. daily_plan_generator 변경 내용
4. paper_state_provider 동작
5. run_paper_daily_plan.py 역할
6. paper daily plan 출력 경로
7. buying power 기준 확인
8. 테스트 결과
9. 기존 front-test 영향 여부
10. 변경하지 않은 범위
11. 남은 위험 / 다음 단계

반드시 명시할 것:

- 기존 run_front_test.py 동작이 유지되는지
- paper_execution_log.csv를 수정했는지 여부
- outputs/front_test 변경 여부
- paper daily plan이 outputs/paper_test에 생성되는지
- commit/체결 반영은 하지 않았는지
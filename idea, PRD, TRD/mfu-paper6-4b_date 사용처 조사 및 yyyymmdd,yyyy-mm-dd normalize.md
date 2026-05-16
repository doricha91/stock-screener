# MFU-PAPER6-4B 작업 지시문: date 사용처 조사 및 YYYYMMDD / YYYY-MM-DD normalize

## 목적

프로젝트 내에서 date가 사용되는 주요 경로를 조사하고, `run_paper_daily_plan.py`가 `YYYYMMDD`와 `YYYY-MM-DD` 입력을 모두 안정적으로 받을 수 있게 수정한다.

핵심 원칙:

```text
입력:
- YYYYMMDD
- YYYY-MM-DD
둘 다 허용

DB 조회 / market_analyzer 호출:
- 반드시 YYYY-MM-DD 사용

파일명 / output path:
- 반드시 YYYYMMDD 사용

기존 run_front_test.py / run_paper_eod_update.py 동작:
- 깨지지 않아야 함
```

## 배경

MFU-PAPER6-3 smoke 결과:

```text
python scripts/run_paper_daily_plan.py --date 20260512
→ 실패

python scripts/run_paper_daily_plan.py --date 2026-05-12
→ 성공
```

DB에는 `daily_price`, `daily_indicators`, `market_index`가 2026-05-12까지 존재했으므로, 실패 원인은 데이터 부재가 아니라 compact date format이 `market_analyzer` 또는 SQL 비교 경로에 그대로 들어간 문제로 판단된다.

## 이번 작업 범위

이번 MFU는 아래 두 가지를 모두 포함한다.

```text
1. date 사용처 조사
2. run_paper_daily_plan.py 경로의 date normalize 수정
```

단, 대규모 리팩토링은 하지 않는다.

## 1단계: date 사용처 조사

아래 명령으로 date 관련 사용처를 조사한다.

```bat
findstr /S /N /I "args.date" scripts\*.py
findstr /S /N /I "get_market_state" *.py core\*.py scripts\*.py
findstr /S /N /I "_coerce_date target_date plan_date snapshot_date trade_date" *.py core\*.py scripts\*.py
findstr /S /N /I "daily_action_plan current_state paper_current_state" core\*.py scripts\*.py
```

조사 대상:

```text
scripts/run_paper_daily_plan.py
scripts/run_front_test.py
scripts/run_paper_eod_update.py
core/daily_plan_generator.py
core/paths.py
market_analyzer.py
current_state / paper_current_state 관련 loader
```

조사 결과에서 아래를 분류한다.

```text
1. CLI 입력 date를 받는 곳
2. DB 조회에 date를 쓰는 곳
3. market_analyzer.get_market_state()에 date를 넘기는 곳
4. 파일명 생성에 date를 쓰는 곳
5. 이미 normalize가 되어 있는 곳
6. normalize 없이 date를 그대로 넘기는 곳
```

## 2단계: 공통 date normalize helper 추가

가능하면 공통 helper를 추가한다.

권장 위치:

```text
core/date_utils.py
```

권장 함수:

```python
def normalize_date_input(date_str: str) -> tuple[str, str]:
    """
    Accepts:
        YYYYMMDD
        YYYY-MM-DD

    Returns:
        date_dash: YYYY-MM-DD
        date_compact: YYYYMMDD
    """
```

동작:

```text
입력 20260512
→ ("2026-05-12", "20260512")

입력 2026-05-12
→ ("2026-05-12", "20260512")
```

invalid 입력은 조용히 통과시키지 말고 `ValueError`로 실패시킨다.

예:

```text
2026/05/12
2026-5-12
202605
abc
```

## 3단계: run_paper_daily_plan.py 수정

`run_paper_daily_plan.py`에서 `--date` 입력을 받은 직후 normalize한다.

사용 규칙:

```text
date_dash:
- generate_daily_plan 내부 계산용
- market_analyzer.get_market_state()에 전달
- DB 조회용

date_compact:
- outputs/paper_test/daily_action_plan_YYYYMMDD.md 파일명 생성용
```

예상 흐름:

```python
date_dash, date_compact = normalize_date_input(args.date)

paper_state = load_official_paper_state_for_daily_plan(date_dash)

output_path = paper_daily_action_plan_path(date_compact)

generate_daily_plan(
    target_date=date_dash,
    current_state=paper_state,
    output_path=output_path,
)
```

실제 함수 인자명은 현재 코드에 맞춘다.

## 4단계: daily_plan_generator 경로 점검

`core/daily_plan_generator.py`가 `plan_date` 또는 `target_date`를 내부에서 다시 compact로 바꾸거나, 반대로 파일명에 dashed date를 쓰는지 확인한다.

수정 원칙:

```text
DB / market / 계산 날짜:
YYYY-MM-DD

파일명:
YYYYMMDD
```

기존 `run_front_test.py` 기본 호출이 깨지지 않게 한다.

## 절대 금지

```text
- run_front_test.py 기존 동작 변경 금지
- run_paper_eod_update.py 기존 동작 변경 금지
- paper_execution_log.csv 수정 금지
- paper_account_snapshot.csv 수정 금지
- paper_position_snapshot.csv 수정 금지
- outputs/front_test 오염 금지
- DB schema / DB files 수정 금지
- SWITCH_IN symbol mapping 재수정 금지
- live/broker 구현 금지
- benchmark / MDD / CAGR / Sharpe 추가 금지
- 대규모 리팩토링 금지
```

## 테스트 추가/수정

신규 테스트 파일 권장:

```text
tests/test_date_utils.py
```

필수 테스트:

```text
1. normalize_date_input("20260512")
   → date_dash="2026-05-12", date_compact="20260512"

2. normalize_date_input("2026-05-12")
   → date_dash="2026-05-12", date_compact="20260512"

3. invalid date 입력 시 ValueError

4. run_paper_daily_plan.py 또는 관련 helper가 compact 입력도 dashed로 내부 전달하는지 검증

5. output path는 compact filename을 쓰는지 검증
```

기존 테스트도 실행한다.

```bat
set PYTHONPATH=.

python -m pytest tests/test_date_utils.py -q
python -m pytest tests/test_paper_daily_plan_generation.py -q
python -m pytest tests/test_paper_state_provider.py -q
python -m pytest tests/test_daily_plan_switch_symbol_mapping.py -q
python -m pytest tests/test_paper_account_state.py -q
```

컴파일:

```bat
python -m py_compile core/date_utils.py core/daily_plan_generator.py core/paper_state_provider.py scripts/run_paper_daily_plan.py
```

## 수동 smoke

둘 다 실행한다.

```bat
set PYTHONPATH=.

python scripts/run_paper_daily_plan.py --date 20260512
python scripts/run_paper_daily_plan.py --date 2026-05-12
```

둘 다 아래 파일을 생성해야 한다.

```text
outputs/paper_test/daily_action_plan_20260512.md
```

확인:

```bat
type outputs\paper_test\daily_action_plan_20260512.md
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
DB files
```

## 성공 기준

```text
- date 사용처 조사 결과가 보고됨
- YYYYMMDD / YYYY-MM-DD 입력 모두 허용
- DB와 market_analyzer에는 YYYY-MM-DD만 전달
- 파일명에는 YYYYMMDD만 사용
- run_paper_daily_plan.py --date 20260512 성공
- run_paper_daily_plan.py --date 2026-05-12 성공
- 두 입력 모두 daily_action_plan_20260512.md 생성
- 기존 run_front_test.py 동작 영향 없음
- 기존 run_paper_eod_update.py 동작 영향 없음
- outputs/front_test 변경 없음
- paper_execution_log / snapshots 변경 없음
```

## 결과 보고 형식

5,000자 이내로 작성한다.

포함할 항목:

```text
1. Summary
2. 조사한 date 사용처
3. 확인된 문제 지점
4. 변경 파일
5. normalize helper 동작
6. run_paper_daily_plan.py 수정 내용
7. 테스트 결과
8. compact / dashed date smoke 결과
9. 기존 run_front_test.py 영향 여부
10. 기존 run_paper_eod_update.py 영향 여부
11. 변경하지 않은 파일/범위
12. 남은 위험 / 다음 단계
```

반드시 명시할 것:

```text
- 20260512 입력이 성공하는지
- 2026-05-12 입력이 성공하는지
- market_analyzer에는 YYYY-MM-DD가 전달되는지
- output 파일명은 YYYYMMDD인지
- outputs/front_test 변경 여부
- paper_execution_log / snapshot 변경 여부
```
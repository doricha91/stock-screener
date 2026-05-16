# MFU-PAPER6-9D 작업 지시문: paper account state as-of cutoff 구현

## 목적

`run_paper_daily_plan.py --date YYYYMMDD` 실행 시, 최신 paper 계좌 상태가 아니라 **해당 plan date 직전까지의 paper 계좌 상태**를 기준으로 daily plan을 생성하도록 수정한다.

핵심 원칙:

```text
daily plan 생성용 paper state:
trade_date < plan_date

EOD/report/snapshot용 paper state:
trade_date <= plan_date
```

예:

```text
plan_date = 2026-05-12
daily plan이 봐야 할 계좌 상태 = 2026-05-12 거래 전 상태
따라서 paper_execution_log는 trade_date < 2026-05-12까지만 반영
```

이번 MFU는 **account state cutoff만** 다룬다.  
market data / indicator / universe / regime as-of 기준은 후속 MFU에서 조사한다.

## 배경

MFU-PAPER6-9C 결과:

- paper switching 후보군 parity 수정 완료
- same-day duplicate BUY 방지 완료
- 단, `run_paper_daily_plan.py`는 historical as-of reducer가 아니라 최신 `paper_execution_log.csv` 전체 상태를 읽음
- 그래서 과거 날짜 plan을 다시 생성하면 그 날짜 당시 상태가 아니라 최신 paper state 기준으로 plan이 생성될 수 있음

## 수정 대상

우선 확인/수정:

```text
core/paper_state_provider.py
scripts/run_paper_daily_plan.py
core/paper_account_state.py
tests/*paper_state*
tests/*paper_daily_plan*
```

필요 시:

```text
core/date_utils.py
core/paths.py
```

## 구현 요구사항

### 1. paper state provider에 as-of cutoff 추가

`paper_execution_log.csv`를 reducer에 넣기 전에 date cutoff를 적용한다.

권장 함수명:

```python
load_official_paper_state_for_daily_plan(date_str: str)
```

또는 기존 함수에 명확히 반영한다.

정책:

```text
daily plan용:
trade_date < plan_date
```

주의:

```text
- plan_date가 2026-05-12면 2026-05-12 committed trade는 제외
- plan_date가 2026-05-13이면 2026-05-12 committed trade는 포함, 2026-05-13 committed trade는 제외
```

### 2. EOD/update 경로와 혼동 금지

`run_paper_eod_update.py`의 commit/snapshot 계산은 기존 의미를 유지한다.

```text
EOD after commit:
trade_date <= target_date
```

이번 MFU에서 EOD reducer 정책을 바꾸지 않는다.

### 3. date normalize 유지

`20260512`, `2026-05-12` 둘 다 정상 처리한다.

내부 비교는 `YYYY-MM-DD` 기준으로 통일한다.

### 4. 출력 path 정책 유지

파일명은 기존처럼 compact date를 사용한다.

```text
outputs/paper_test/daily_action_plan_20260512.md
```

## 절대 금지

```text
- market data / indicator as-of 정책 수정 금지
- universe snapshot 구현 금지
- regime/config snapshot 구현 금지
- paper_execution_log.csv 수정 금지
- snapshot 파일 수정 금지
- outputs/front_test 수정 금지
- DB 수정 금지
- --commit 실행 금지
- switch 후보군 정책 재수정 금지
- 대규모 리팩토링 금지
```

## 테스트 추가/수정

권장 테스트:

```text
tests/test_paper_state_asof_cutoff.py
```

필수 테스트:

```text
1. plan_date=2026-05-12일 때 2026-05-12 trade 제외
2. plan_date=2026-05-13일 때 2026-05-12 trade 포함
3. plan_date=2026-05-13일 때 2026-05-13 trade 제외
4. 20260513 / 2026-05-13 입력이 같은 cutoff 결과
5. run_paper_daily_plan.py가 cutoff된 paper_state를 사용
6. run_paper_eod_update.py 동작은 변경되지 않음
```

예시 fixture:

```text
2026-05-11 BUY CPAY
2026-05-12 SELL CPAY / BUY CF
2026-05-13 SELL CF / BUY F
```

기대:

```text
as_of_plan_date=2026-05-12 → CPAY 보유
as_of_plan_date=2026-05-13 → CF 보유
as_of_plan_date=2026-05-14 → F 보유
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
20260512 plan:
- 2026-05-12 commit 이후 상태를 보면 안 됨
- 2026-05-12 장 시작 전 상태 기준이어야 함

20260513 plan:
- 2026-05-12 commit 결과는 반영
- 2026-05-13 commit 결과는 반영하지 않아야 함
```

주의:

```text
market data / indicator 기준은 아직 별도 as-of 보장 대상이 아님
이번에는 account state cutoff만 확인
```

## 검증 명령

```bat
set PYTHONPATH=.

python -m pytest tests/test_paper_state_asof_cutoff.py -q
python -m pytest tests/test_paper_switching_parity.py -q
python -m pytest tests/test_paper_daily_plan_generation.py -q
python -m pytest tests/test_paper_state_provider.py -q
python -m pytest tests/test_paper_account_state.py -q

python -m py_compile core/paper_state_provider.py scripts/run_paper_daily_plan.py
```

## 성공 기준

```text
- daily plan용 paper state가 trade_date < plan_date 기준으로 계산됨
- 과거 날짜 plan 재생성 시 최신 paper state를 보지 않음
- 20260512 / 2026-05-12 입력이 동일하게 처리됨
- 20260513 / 2026-05-13 입력이 동일하게 처리됨
- run_paper_eod_update.py commit/snapshot 정책은 변경 없음
- paper_execution_log / snapshots 변경 없음
- outputs/front_test 변경 없음
```

## 결과 보고 형식

5천자 이내.

포함 항목:

```text
1. Summary
2. 변경 파일
3. as-of cutoff 정책
4. daily plan용 cutoff와 EOD용 cutoff 구분
5. 테스트 결과
6. 20260512 smoke 결과
7. 20260513 smoke 결과
8. paper_execution_log/snapshot 변경 여부
9. outputs/front_test 변경 여부
10. 남은 위험 / 다음 단계
```

반드시 명시:

```text
- daily plan은 trade_date < plan_date를 쓰는지
- EOD/report는 기존처럼 trade_date <= target_date 의미를 유지하는지
- market data/indicator as-of는 이번 범위에서 제외했는지
```
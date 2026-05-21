# MFU-PAPER11-2 작업 지시문: paper.py CLI skeleton + preflight/plan/eod wrapper

## 기준

브랜치: gemini_cli_update

## 목적

PAPER11-2의 목표는 paper 운영 명령을 하나의 CLI 진입점으로 묶는 `scripts/paper.py` skeleton을 구현하는 것이다.

이번 단계에서는 아래 기능만 연결한다.

```text
preflight
plan
eod --dry-run
eod --commit
```

이번 단계에서는 시장데이터 수집, reports regeneration, review workflow, shortcut command는 구현하지 않는다.

반드시 명시:

```text
이번 PAPER11-2는 paper.py CLI skeleton + preflight/plan/eod wrapper 구현이며, 시장데이터 수집, reports, review workflow는 포함하지 않는다.
```

## 배경

조사 결과:

- `run_paper_daily_plan.py`는 paper 상태를 `paper_execution_log.csv`에서 복원해 공식 daily plan을 생성하는 entrypoint다.
- 실제 원본 paper CSV를 갱신하는 핵심 writer는 `run_paper_eod_update.py --commit`이다.
- PAPER11-1에서 paper-specific preflight가 구현됐다.
- preflight는 `plan`, `eod`, `reports`, `review-template`, `review-append`, `all` stage를 지원한다.
- preflight 기본 실행은 read-only이며, `--write-report`가 있을 때만 report를 생성한다.

## 구현 파일

추가 권장 파일:

```text
scripts/paper.py
tests/test_paper_cli.py
docs/TRD/mfu_paper11_2_paper_cli_skeleton.md
```

필요 시 core helper 추가 가능:

```text
core/paper_cli_runner.py
```

단, 이번 단계에서는 대규모 구조 변경을 피한다.

## CLI 요구사항

### 1. 기본 help

아래 명령은 실제 작업을 실행하지 않고 help만 출력한다.

```text
python scripts/paper.py
python scripts/paper.py --help
```

지원 subcommand:

```text
preflight
plan
eod
```

### 2. preflight wrapper

명령:

```text
python scripts/paper.py preflight --date YYYYMMDD --stage plan
python scripts/paper.py preflight --date YYYYMMDD --stage eod
python scripts/paper.py preflight --stage reports
python scripts/paper.py preflight --stage review-template
python scripts/paper.py preflight --stage review-append
python scripts/paper.py preflight --date YYYYMMDD --stage all --strict
```

동작:

- PAPER11-1의 paper-specific preflight 로직을 호출한다.
- 가능하면 subprocess보다 `core.paper_preflight_check`의 함수 호출을 우선한다.
- 단, 기존 CLI 동작과 출력 일관성이 더 안전하면 `scripts/check_paper_preflight.py`를 subprocess로 호출해도 된다.
- `--write-report` 옵션을 그대로 전달할 수 있어야 한다.

### 3. plan wrapper

명령:

```text
python scripts/paper.py plan --date YYYYMMDD
```

동작:

1. 내부적으로 preflight stage=plan 실행
2. preflight 결과가 FAIL이면 plan 실행 중단
3. PASS 또는 PASS_WITH_WARNINGS이면 `run_paper_daily_plan.py --date YYYYMMDD` 실행

주의:

- `run_paper_daily_plan.py`의 기존 동작을 변경하지 않는다.
- daily plan 출력 경로는 기존 paper wrapper가 보장하는 `outputs/paper_test/daily_action_plan_YYYYMMDD.md`를 사용해야 한다.
- `core.daily_plan_generator.generate_daily_plan()`을 직접 호출하지 않는다.
  - 이유: 해당 함수의 기본 출력이 front path일 수 있으므로 paper wrapper를 우회하면 front_test 오염 위험이 있다.

### 4. eod wrapper

명령:

```text
python scripts/paper.py eod --date YYYYMMDD --dry-run
python scripts/paper.py eod --date YYYYMMDD --commit
```

동작:

1. 내부적으로 preflight stage=eod 실행
2. preflight 결과가 FAIL이면 eod 실행 중단
3. `--dry-run`이면 `run_paper_eod_update.py --date YYYYMMDD --allow-empty-journal` 실행
4. `--commit`이면 `run_paper_eod_update.py --date YYYYMMDD --commit` 실행

옵션 정책:

```text
--dry-run과 --commit 중 하나만 허용
둘 다 없으면 error
둘 다 있으면 error
```

commit 주의:

- `--commit`은 실제 paper 원장 CSV를 수정하는 위험한 writer다.
- 하지만 이번 wrapper는 명시적 `--commit`이 있을 때만 실행한다.
- 기본값으로 commit을 실행하면 안 된다.

## 자동 preflight 정책

`plan`, `eod`는 항상 자동으로 preflight를 먼저 실행한다.

정책:

```text
preflight result = FAIL -> 중단, exit code 1
preflight result = PASS_WITH_WARNINGS -> 계속 실행, warning 출력
preflight result = PASS -> 계속 실행
```

단, `eod --commit`의 strict 강제는 이번 단계에서 구현하지 않는다.  
향후 MFU에서 `--strict-commit` 또는 commit 전 dry-run evidence 정책을 추가할 수 있도록 TODO를 남긴다.

## 절대 금지

```text
시장데이터 수집 기능 추가 금지
prepare-data command 추가 금지
reports command 추가 금지
review-template/validate/append command 추가 금지
shortcut dry-run/commit/review command 추가 금지
run-all/daily 전체 자동 실행 command 추가 금지
run_paper_daily_plan.py 내부 수정 금지
run_paper_eod_update.py 내부 수정 금지
core/daily_plan_generator.generate_daily_plan 직접 호출 금지
기존 front-test용 core/preflight_check.py 수정 금지
paper_execution_log.csv 직접 수정 금지
paper_account_snapshot.csv 직접 수정 금지
paper_position_snapshot.csv 직접 수정 금지
outputs/front_test 수정 금지
DB 수정 금지
대규모 리팩토링 금지
```

## read/write 안전성

이번 CLI wrapper 자체는 직접 파일을 수정하지 않는다.

다만 감싼 기존 스크립트의 동작은 다음과 같다.

```text
paper.py plan
-> run_paper_daily_plan.py 실행
-> daily plan/config snapshot 생성 가능

paper.py eod --dry-run
-> run_paper_eod_update.py without --commit
-> read-only preview

paper.py eod --commit
-> run_paper_eod_update.py --commit
-> paper_execution_log/account_snapshot/position_snapshot/current_state 수정 가능
```

이 구분을 TRD와 help text에 명확히 남긴다.

## 테스트

테스트 파일:

```text
tests/test_paper_cli.py
```

필수 테스트:

```text
1. python scripts/paper.py --help가 subcommand를 표시
2. preflight subcommand가 paper preflight를 호출
3. plan subcommand가 preflight 먼저 호출
4. preflight FAIL이면 plan 실행 중단
5. plan PASS면 run_paper_daily_plan wrapper 호출
6. eod --dry-run이 preflight 먼저 호출
7. eod --dry-run이 run_paper_eod_update dry-run wrapper 호출
8. eod --commit이 명시적으로만 실행됨
9. eod에서 --dry-run과 --commit 둘 다 없으면 error
10. eod에서 --dry-run과 --commit 둘 다 있으면 error
11. reports/review/prepare-data command가 아직 존재하지 않음
12. core.daily_plan_generator.generate_daily_plan을 직접 호출하지 않음
```

테스트 방식:

- 가능하면 `monkeypatch` 또는 mock을 사용해 실제 writer 실행을 막는다.
- 테스트에서 `run_paper_eod_update.py --commit`이 실제 실행되면 안 된다.
- 원본 CSV를 수정하지 않는다.

## 검증 명령

```text
set PYTHONPATH=.

python -m pytest tests/test_paper_cli.py -q
python -m py_compile scripts/paper.py

python scripts/paper.py --help
python scripts/paper.py preflight --date 20260513 --stage plan
python scripts/paper.py preflight --date 20260513 --stage eod
```

주의:

아래 명령은 실제 파일을 생성/수정할 수 있으므로 결과 보고 시 실행 여부를 명확히 남긴다.

```text
python scripts/paper.py plan --date 20260513
python scripts/paper.py eod --date 20260513 --dry-run
```

아래 명령은 실제 paper 원장 CSV를 수정할 수 있으므로 이번 검증에서는 실행하지 않는다.

```text
python scripts/paper.py eod --date 20260513 --commit
```

## 성공 기준

```text
scripts/paper.py가 생성된다.
preflight/plan/eod subcommand가 동작한다.
plan/eod 실행 전에 paper preflight가 자동으로 실행된다.
preflight FAIL이면 후속 실행이 중단된다.
eod --commit은 명시적으로만 가능하다.
reports/review/prepare-data/shortcut command는 아직 없다.
기존 run_paper_daily_plan.py와 run_paper_eod_update.py는 수정하지 않는다.
기존 front-test용 preflight는 수정하지 않는다.
outputs/front_test는 수정하지 않는다.
테스트가 통과한다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 변경 파일
3. 추가된 CLI subcommand
4. preflight 자동 실행 방식
5. plan wrapper 동작
6. eod dry-run wrapper 동작
7. eod commit wrapper 동작
8. 명시적 commit 안전장치
9. 제외한 항목
10. 테스트 결과
11. 실제 실행한 명령
12. 원본 CSV 변경 여부
13. outputs/front_test 변경 여부
14. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER11-2는 paper.py CLI skeleton + preflight/plan/eod wrapper 구현이며, reports/review/market-data command는 포함하지 않는다.
```
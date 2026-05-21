# MFU-PAPER11-1 작업 지시문: paper-specific preflight check 구현

## 기준

브랜치: gemini_cli_update

## 목적

PAPER11-1의 목표는 paper 운영 자동화 전에 실행할 **paper 전용 preflight check**를 구현하는 것이다.

이번 단계는 실행 전 점검 전용이다.  
`run_paper_daily_plan.py`, `run_paper_eod_update.py --commit`, reports generation, review append를 직접 실행하지 않는다.

반드시 명시:

```text
이번 PAPER11-1은 paper 운영 전용 preflight check 구현이며, paper 원장 수정이나 --commit 실행은 포함하지 않는다.
```

## 배경

조사 결과:

- `run_paper_daily_plan.py`는 paper 상태를 `paper_execution_log.csv`에서 복원해 공식 daily plan을 생성하는 entrypoint다.
- 실제 원본 paper CSV를 갱신하는 핵심 writer는 `run_paper_eod_update.py --commit`이다.
- 기존 `core/preflight_check.py`는 front-test 전용 성격이 강하다.
- `scripts/preflight_check.py`와 루트 `preflight_check.py`는 존재하지 않는다.
- 따라서 paper 운영에는 별도 preflight가 필요하다.

## 구현 파일

권장 추가 파일:

```text
core/paper_preflight_check.py
scripts/check_paper_preflight.py
tests/test_paper_preflight_check.py
docs/TRD/mfu_paper11_1_paper_preflight_check.md
```

## CLI 요구사항

`scripts/check_paper_preflight.py`는 아래 옵션을 지원한다.

```text
--date YYYYMMDD 또는 YYYY-MM-DD
--stage plan | eod | reports | review-template | review-append | all
--strict 선택 옵션
```

예시:

```text
python scripts/check_paper_preflight.py --date 20260513 --stage plan
python scripts/check_paper_preflight.py --date 20260513 --stage eod
python scripts/check_paper_preflight.py --stage reports
python scripts/check_paper_preflight.py --stage review-append
python scripts/check_paper_preflight.py --date 20260513 --stage all --strict
```

## 핵심 원칙

### 1. read-only

preflight는 파일을 수정하지 않는다.

허용:
- 파일 존재 여부 확인
- 경로 안전성 확인
- 날짜 형식 확인
- 입력 파일 row count 확인
- report/review 산출물 존재 여부 확인
- warning/error report 출력

금지:
- `run_paper_eod_update.py --commit` 실행
- paper CSV 수정
- report 재생성
- review log append
- DB 수정
- outputs/front_test 수정

### 2. paper path 강제

모든 paper 관련 경로는 `outputs/paper_test` 하위여야 한다.

검사 대상:

```text
paper_execution_log.csv
paper_account_snapshot.csv
paper_position_snapshot.csv
daily_action_plan_YYYYMMDD.md
reports/*
reviews/*
```

`outputs/front_test` 경로가 감지되면 error 처리한다.

### 3. block / warning 구분

severity는 두 가지로 둔다.

```text
error
warning
```

정책:

```text
error_count > 0이면 FAIL
warning만 있으면 PASS_WITH_WARNINGS
error_count = 0 and warning_count = 0이면 PASS
```

`--strict` 모드에서는 일부 warning을 error로 승격할 수 있다.

## stage별 체크 항목

### 1. 공통 체크

모든 stage에서 확인:

```text
프로젝트 루트에서 실행 중인지
core/ 및 scripts/ import 가능 여부
outputs/paper_test 존재 여부
outputs/front_test를 쓰지 않는지
core.paths의 paper path helper 사용 가능 여부
날짜가 필요한 stage에서 --date 존재 여부
--date 형식이 YYYYMMDD 또는 YYYY-MM-DD인지
```

날짜가 미래면 warning 처리한다.

### 2. stage=plan

목적: `run_paper_daily_plan.py` 실행 전 점검

확인:

```text
market DB 경로 존재 여부
paper_execution_log.csv 존재 여부
paper_daily_action_plan_path(date)가 outputs/paper_test 하위인지
paper_config_snapshot_path(date)가 outputs/paper_test 하위인지
```

정책:

```text
paper_execution_log.csv 없음 = warning
```

이유: paper 초기 bootstrap 상태에서는 없을 수 있다.

### 3. stage=eod

목적: `run_paper_eod_update.py` dry-run 또는 commit 전 점검

확인:

```text
daily_action_plan_YYYYMMDD.md 존재 여부
paper_execution_log.csv 경로가 outputs/paper_test 하위인지
paper_account_snapshot.csv 경로가 outputs/paper_test 하위인지
paper_position_snapshot.csv 경로가 outputs/paper_test 하위인지
```

정책:

```text
daily_action_plan_YYYYMMDD.md 없음 = error
```

주의:
이번 MFU에서는 dry-run 선행 여부 강제는 구현하지 않는다.  
다만 향후 strict mode에서 dry-run evidence를 요구할 수 있도록 TODO를 남긴다.

### 4. stage=reports

목적: PAPER9 report regeneration 전 점검

확인:

```text
paper_execution_log.csv 존재 여부
paper_account_snapshot.csv 존재 여부
paper_position_snapshot.csv 존재 여부
reports directory 존재 여부
```

정책:

```text
paper_account_snapshot.csv 없음 = error
paper_position_snapshot.csv 없음 = error
paper_execution_log.csv 없음 = warning 또는 error
```

초기 상태에서는 execution log가 없을 수 있으므로, 우선 warning으로 둔다.

### 5. stage=review-template

목적: review template 생성 전 점검

확인:

```text
paper_symbol_review_worksheet.csv 존재 여부
paper_symbol_review_buckets.csv 존재 여부
reviews directory 존재 여부
```

없으면 error.

### 6. stage=review-append

목적: manual review log append 전 점검

확인:

```text
paper_manual_review_log_template.csv 존재 여부
paper_manual_review_log_validation_report.md 존재 여부
paper_manual_review_log_validation_issues.csv 존재 여부
validation report가 PASS인지 확인 가능 여부
```

정책:

```text
template 없음 = error
validation report 없음 = warning
validation FAIL = error
```

단, 이번 MFU에서는 validator를 직접 실행하지 않는다.  
존재하는 validation report를 읽어 상태만 확인한다.

## 산출물

preflight 실행 시 콘솔 출력은 필수다.

권장 산출물:

```text
outputs/paper_test/reports/paper_preflight_report.md
outputs/paper_test/reports/paper_preflight_issues.csv
```

단, read-only 원칙과 충돌하지 않도록 이번 MFU에서는 report 파일 생성 여부를 선택 가능하게 한다.

권장 CLI 옵션:

```text
--write-report
```

`--write-report`가 없으면 콘솔 출력만 한다.

## preflight issue 구조

내부 issue dict 권장 필드:

```text
severity
stage
check_name
message
path
suggestion
```

## report 구성

`paper_preflight_report.md`를 생성할 경우 포함:

```text
1. 생성 일시
2. stage
3. date
4. result: PASS / PASS_WITH_WARNINGS / FAIL
5. error count
6. warning count
7. checked paths
8. issues table
9. limitations
```

Limitations에 포함:

```text
- This preflight check is read-only.
- It does not run paper daily plan, EOD commit, report regeneration, or review append.
- It does not validate investment decisions.
- It only checks operational readiness for paper workflow.
```

## 절대 금지

```text
paper_execution_log.csv 수정 금지
paper_account_snapshot.csv 수정 금지
paper_position_snapshot.csv 수정 금지
paper_current_state_*.json 수정 금지
기존 report CSV 수정 금지
review log 수정 금지
outputs/front_test 수정 금지
DB 수정 금지
--commit 실행 금지
daily plan 생성 금지
EOD dry-run 실행 금지
report regeneration 실행 금지
review append 실행 금지
기존 core/preflight_check.py 수정 금지
대규모 리팩토링 금지
```

## 테스트

테스트 파일:

```text
tests/test_paper_preflight_check.py
```

필수 테스트:

```text
1. 정상 plan stage PASS 또는 PASS_WITH_WARNINGS
2. 잘못된 date 형식 error
3. date 필요한 stage에서 date 누락 error
4. paper path가 outputs/paper_test 밖이면 error
5. front_test path 감지 시 error
6. plan stage에서 execution log 없음은 warning
7. eod stage에서 daily action plan 없음은 error
8. reports stage에서 account snapshot 없음은 error
9. review-template stage에서 worksheet 없음은 error
10. review-append stage에서 template 없음은 error
11. validation FAIL이면 review-append error
12. warning만 있으면 PASS_WITH_WARNINGS
13. error가 있으면 FAIL
14. --write-report 없이 원본 파일 생성/수정 없음
```

## 검증 명령

```text
set PYTHONPATH=.

python -m pytest tests/test_paper_preflight_check.py -q
python -m py_compile core/paper_preflight_check.py
python -m py_compile scripts/check_paper_preflight.py

python scripts/check_paper_preflight.py --date 20260513 --stage plan
python scripts/check_paper_preflight.py --date 20260513 --stage eod
python scripts/check_paper_preflight.py --stage reports
python scripts/check_paper_preflight.py --stage review-template
python scripts/check_paper_preflight.py --stage review-append
```

`--commit`은 절대 실행하지 않는다.

## 성공 기준

```text
paper-specific preflight check가 구현된다.
기존 front-test용 core/preflight_check.py는 수정하지 않는다.
stage별 paper 운영 준비 상태를 점검한다.
error/warning이 구분된다.
front_test 오염 가능성을 감지한다.
기본 실행은 read-only다.
선택적으로 preflight report를 생성할 수 있다.
원본 paper CSV와 outputs/front_test는 수정하지 않는다.
테스트가 통과한다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 변경 파일
3. 추가된 CLI
4. 지원 stage
5. stage별 주요 체크
6. PASS / WARNING / FAIL 정책
7. --write-report 동작 여부
8. 기존 core/preflight_check.py 수정 여부
9. 제외한 항목
10. 테스트 결과
11. 원본 CSV 변경 여부
12. outputs/front_test 변경 여부
13. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER11-1은 paper-specific preflight check 구현이며, paper 원장 수정이나 --commit 실행은 포함하지 않는다.
```
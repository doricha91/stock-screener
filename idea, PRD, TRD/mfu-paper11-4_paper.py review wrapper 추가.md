# MFU-PAPER11-4 작업 지시문: paper.py review wrapper 추가

## 기준

브랜치: gemini_cli_update

## 목적

PAPER11-4의 목표는 `scripts/paper.py`에 review 계열 subcommand를 추가해, PAPER10에서 만든 manual review workflow를 하나의 CLI 진입점에서 실행할 수 있게 하는 것이다.

이번 단계에서 추가할 명령:

```text
review-template
review-validate
review-append
```

반드시 명시:

```text
이번 PAPER11-4는 paper.py review wrapper 구현이며, market-data, EOD commit, reports 재생성, Notion/UI 연동은 포함하지 않는다.
```

## 배경

현재 상태:

- PAPER11-1: paper-specific preflight 구현
- PAPER11-2: `paper.py`에 preflight / plan / eod wrapper 추가
- PAPER11-3: `paper.py reports` wrapper 추가
- PAPER10-1: manual review log template 생성
- PAPER10-2: manual review log validator 생성
- PAPER10-3: manual review log append workflow 생성

PAPER11-4에서는 기존 review script들을 `paper.py`에서 호출할 수 있게만 한다.

## 구현 파일

수정:

```text
scripts/paper.py
tests/test_paper_cli.py
docs/TRD/mfu_paper11_4_paper_review_wrapper.md
```

필요 시 추가 가능:

```text
core/paper_review_runner.py
```

단, 대규모 리팩토링은 금지한다.

## 추가할 CLI

### 1. review-template

명령:

```text
python scripts/paper.py review-template
```

동작:

1. 내부적으로 preflight `stage=review-template` 실행
2. preflight FAIL이면 중단
3. PASS 또는 PASS_WITH_WARNINGS이면 기존 script 실행

기존 script:

```text
scripts/generate_paper_manual_review_log_template.py
```

출력:

```text
outputs/paper_test/reviews/paper_manual_review_log_template.csv
outputs/paper_test/reviews/paper_manual_review_log_template.md
```

### 2. review-validate

명령:

```text
python scripts/paper.py review-validate
```

동작:

1. 기존 validator script 실행
2. validation result를 콘솔에 표시
3. error가 있으면 exit code 1
4. warning만 있으면 exit code 0

기존 script:

```text
scripts/validate_paper_manual_review_log.py
```

출력:

```text
outputs/paper_test/reviews/paper_manual_review_log_validation_report.md
outputs/paper_test/reviews/paper_manual_review_log_validation_issues.csv
```

주의:

- 이 명령은 read-only 검증 성격이다.
- 원본 template CSV를 수정하면 안 된다.

### 3. review-append

명령:

```text
python scripts/paper.py review-append
```

동작:

1. 내부적으로 preflight `stage=review-append` 실행
2. preflight FAIL이면 중단
3. PASS 또는 PASS_WITH_WARNINGS이면 기존 append script 실행

기존 script:

```text
scripts/append_paper_manual_review_log.py
```

출력/수정 가능 파일:

```text
outputs/paper_test/reviews/paper_manual_review_log.csv
outputs/paper_test/reviews/paper_manual_review_log_append_report.md
outputs/paper_test/reviews/paper_manual_review_log_append_issues.csv
```

정책:

```text
reviewed / deferred / not_applicable row만 append
pending row는 append 제외
기존 row update/overwrite 금지
```

## 자동화 범위

이번 단계에서는 아래처럼 각각의 명령을 분리한다.

```text
python scripts/paper.py review-template
python scripts/paper.py review-validate
python scripts/paper.py review-append
```

아래 통합 명령은 아직 만들지 않는다.

```text
python scripts/paper.py review
python scripts/paper.py review --append
```

이유:

- template 생성 후 사람이 수동으로 답변을 작성해야 한다.
- append는 누적 log를 수정하는 writer다.
- 따라서 append는 명시적으로만 실행해야 한다.

## preflight 정책

```text
review-template -> stage=review-template preflight 자동 실행
review-append -> stage=review-append preflight 자동 실행
review-validate -> 별도 preflight 없이 validator 직접 실행 가능
```

단, `review-validate` 전에 template 존재 여부 정도는 자체적으로 확인해도 된다.

## 절대 금지

```text
market-data / prepare-data command 추가 금지
shortcut review command 추가 금지
run-all / daily command 추가 금지
reports command 내부에 review append 포함 금지
EOD dry-run 실행 금지
EOD --commit 실행 금지
paper_execution_log.csv 수정 금지
paper_account_snapshot.csv 수정 금지
paper_position_snapshot.csv 수정 금지
outputs/front_test 수정 금지
DB 수정 금지
Notion/API/UI 연동 금지
기존 review script 대규모 리팩토링 금지
기존 row update/overwrite 구현 금지
```

## 테스트

수정/추가 테스트:

```text
tests/test_paper_cli.py
```

필수 테스트:

```text
1. paper.py --help에 review-template/review-validate/review-append 표시
2. review-template이 stage=review-template preflight를 먼저 호출
3. review-template preflight FAIL이면 generator 실행 중단
4. review-template PASS이면 기존 generator 호출
5. review-validate가 기존 validator 호출
6. review-validate error result면 exit code 1
7. review-append가 stage=review-append preflight를 먼저 호출
8. review-append preflight FAIL이면 append 실행 중단
9. review-append PASS이면 기존 append script 호출
10. review-append는 기존 row update/overwrite를 구현하지 않음
11. reports command가 review-append를 호출하지 않음
12. 통합 review command는 아직 존재하지 않음
```

테스트에서는 monkeypatch/mock을 사용해 실제 append가 실행되지 않도록 한다.

## 검증 명령

```text
set PYTHONPATH=.

python -m pytest tests/test_paper_cli.py -q
python -m py_compile scripts/paper.py

python scripts/paper.py --help
python scripts/paper.py review-template
python scripts/paper.py review-validate
```

주의:

아래 명령은 `paper_manual_review_log.csv`를 수정할 수 있으므로 실제 실행 여부를 결과 보고에 명확히 남긴다.

```text
python scripts/paper.py review-append
```

## 성공 기준

```text
paper.py에 review-template/review-validate/review-append가 추가된다.
review-template은 preflight 후 template generator를 호출한다.
review-validate는 validator를 호출한다.
review-append는 preflight 후 append workflow를 호출한다.
append는 명시적으로만 실행된다.
reports command는 review append를 실행하지 않는다.
원본 paper CSV와 outputs/front_test는 수정하지 않는다.
테스트가 통과한다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 변경 파일
3. 추가된 CLI subcommand
4. review-template wrapper 동작
5. review-validate wrapper 동작
6. review-append wrapper 동작
7. preflight 자동 실행 방식
8. append 안전장치
9. 제외한 항목
10. 테스트 결과
11. 실제 실행한 명령
12. 원본 CSV 변경 여부
13. outputs/front_test 변경 여부
14. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER11-4는 paper.py review wrapper 구현이며, market-data, EOD commit, reports 재생성, Notion/UI 연동은 포함하지 않는다.
```
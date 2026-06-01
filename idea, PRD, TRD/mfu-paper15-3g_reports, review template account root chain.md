BEGIN MFU-PAPER15-3G_REPORTS_REVIEW_TEMPLATE_ACCOUNT_ROOT

# MFU-PAPER15-3G 작업 지시문: Reports / Review Template Account Root Chain

## 목적

MFU-PAPER15-3G의 목표는 non-default 계좌에서 reports / review-template / review-validate / review 계열 산출물이 account-aware root 하위에서 일관되게 생성·조회되도록 연결하는 것이다.

이번 단계는 local report/review-template 체인 정렬에 한정한다.  
Notion actual sync/write, Notion row migration, broker/API, cloud runner, paper_default legacy migration은 포함하지 않는다.

반드시 명시:

```text
이번 PAPER15-3G는 non-default reports / review-template 체인을 account-aware root에 연결하는 작업이며, Notion actual sync/write, Notion row migration, broker/API, cloud runner, paper_default legacy migration은 포함하지 않는다.
```

## 배경

PAPER15-3F에서 non-default writer는 `outputs/paper_accounts/{account_id}` 하위로 쓸 수 있게 되었다.

다만 남은 리스크:

```text
paper.py review-append의 non-default 경로는 열렸지만,
그 upstream인 reports / review-template / review-validate / review 체인이 아직 account root에 일관되게 연결되지 않았다.
```

따라서 non-default 계좌에서 review-append를 안전하게 쓰려면, 먼저 review template과 관련 report가 해당 account root에서 생성·검증되어야 한다.

## 핵심 정책

```text
1. paper_default는 기존 outputs/paper_test legacy path 유지.
2. non-default는 outputs/paper_accounts/{account_id}/ 하위만 사용.
3. reports/reviews/template/validation 산출물이 account root 밖에 쓰이면 실패.
4. Notion actual sync/write는 하지 않는다.
5. 실제 운영 outputs/paper_accounts 생성은 테스트 외 금지.
```

## 구현 범위

### 1. account-aware 적용 대상

아래 명령에 `--account-id`를 추가하거나 기존 옵션을 account_paths에 연결한다.

```text
paper.py reports
paper.py review
paper.py review-template
paper.py review-validate
```

필요 시 아래 스크립트도 연결한다.

```text
scripts/append_paper_manual_review_log.py
```

정책:

```text
--account-id 생략 시 paper_default
paper_default는 legacy outputs/paper_test 사용
non-default는 build_paper_account_paths(account_id, create=True) 사용
```

### 2. report 산출물 account root 연결

아래 report/review 산출물이 account root 하위에 위치하도록 한다.

```text
reports/paper_daily_review_summary.md
reports/paper_performance_summary.md
reports/paper_equity_curve.csv
reports/paper_drawdown.csv
reports/paper_symbol_review_buckets.csv
reports/paper_symbol_review_worksheet.csv
reviews/paper_manual_review_log_template.csv
reviews/paper_manual_review_log_validation_report.md
reviews/paper_manual_review_log.csv
```

실제 파일명이 다르면 현재 코드 기준으로 조사 후 반영한다.

### 3. core 함수 optional account_paths 지원

필요한 함수에 `account_paths=None`을 추가한다.

대상 후보:

```text
core/paper_daily_review_summary.py
core/paper_performance_summary.py
core/paper_equity_curve.py
core/paper_drawdown.py
core/paper_symbol_review.py
core/paper_manual_review_log_template.py
core/paper_manual_review_log_validator.py
core/paper_manual_review_log_append.py
```

정책:

```text
account_paths is None:
  기존 core.paths 기반 동작 유지

account_paths provided:
  account_paths.reports_dir / account_paths.reviews_dir 하위만 사용
```

### 4. path safety check

non-default 계좌에서 write target이 account root 밖이면 실패한다.

필수 조건:

```text
non-default report target path는 account_paths.root 하위여야 한다.
non-default review/template target path는 account_paths.root 하위여야 한다.
non-default가 outputs/paper_test를 target으로 잡으면 FAIL.
paper_default legacy path는 기존처럼 허용.
```

필요 시 기존 helper를 재사용한다.

```text
assert_path_under_account_root(...)
```

### 5. review-append와의 연결성 확인

PAPER15-3F에서 review-append는 non-default root를 지원한다.  
이번 단계에서는 아래를 확인한다.

```text
review-template --account-id paper_growth
review-validate --account-id paper_growth
review-append --account-id paper_growth
```

이 세 흐름이 같은 account root의 reviews/ 파일을 기준으로 동작할 수 있어야 한다.

실제 운영 명령은 실행하지 않고 tmp_path 테스트로 검증한다.

## 테스트

테스트 추가/수정 후보:

```text
tests/test_paper_reports_account_paths.py
tests/test_paper_review_template_account_paths.py
tests/test_paper_review_validate_account_paths.py
tests/test_paper_writer_account_paths.py
```

필수 테스트:

```text
1. paper_default reports/review-template는 legacy path 유지
2. non-default reports는 account root/reports 하위에만 write
3. non-default review-template는 account root/reviews 하위에만 write
4. non-default review-validate는 account root/reviews 하위 파일을 읽고 report도 같은 root에 write
5. non-default가 outputs/paper_test를 target으로 잡으면 실패
6. review-template → review-validate → review-append가 같은 account root를 공유
7. 기존 paper_default 테스트가 깨지지 않음
8. 기존 read-only --account-id 테스트가 깨지지 않음
```

테스트는 반드시 tmp_path 기반으로 수행한다.  
실제 운영 `outputs/paper_accounts` 생성은 금지한다.

## 산출물

예상 수정/추가 파일:

```text
scripts/paper.py
scripts/append_paper_manual_review_log.py
core/paper_daily_review_summary.py
core/paper_manual_review_log_template.py
core/paper_manual_review_log_validator.py
core/paper_manual_review_log_append.py
tests/test_paper_reports_account_paths.py
tests/test_paper_review_template_account_paths.py
tests/test_paper_review_validate_account_paths.py
```

필요 시 문서 추가:

```text
docs/TRD/mfu_paper15_3g_reports_review_template_account_root.md
```

## 금지 사항

```text
paper_default legacy 데이터를 outputs/paper_accounts/paper_default로 migration 금지
Notion actual sync/write 실행 금지
Notion row migration script 작성 금지
broker/API 연동 금지
cloud runner 작업 금지
DB schema 변경 금지
실제 운영 outputs/paper_accounts 자동 생성 금지
실제 운영 writer/review 명령 실행 금지
git add . 금지
git add -A 금지
```

## 허용 사항

```text
reports/reviews/template/validation 경로 account_paths 지원
non-default local report/template 생성 허용
tmp_path 기반 테스트
path safety helper 재사용
TRD 문서 추가
pytest 실행
```

## 검증 명령

Windows CMD 기준:

```cmd
python -m pytest tests\test_paper_reports_account_paths.py
python -m pytest tests\test_paper_review_template_account_paths.py
python -m pytest tests\test_paper_review_validate_account_paths.py
python -m pytest tests\test_paper_writer_account_paths.py
python -m pytest tests\test_paper_account_paths.py tests\test_paper_account_profile.py
git diff -- scripts\paper.py scripts\append_paper_manual_review_log.py
git diff -- core\paper_daily_review_summary.py core\paper_manual_review_log_template.py core\paper_manual_review_log_validator.py core\paper_manual_review_log_append.py
git diff -- docs\TRD\mfu_paper15_3g_reports_review_template_account_root.md
git status --short
```

실제 운영 writer/review 명령과 Notion actual sync/write는 실행하지 않는다.

## 성공 기준

```text
non-default reports가 outputs/paper_accounts/{account_id}/reports 하위에 생성된다.
non-default review-template이 outputs/paper_accounts/{account_id}/reviews 하위에 생성된다.
non-default review-validate가 같은 account root의 reviews 파일을 사용한다.
review-template → review-validate → review-append 체인이 같은 account root를 공유한다.
paper_default는 기존 outputs/paper_test legacy path를 유지한다.
non-default가 outputs/paper_test에 쓰는 경로는 차단된다.
기존 paper_default daily ops 호환성은 유지된다.
Notion actual sync/write, migration, broker/API는 변경되지 않는다.
실제 운영 outputs/paper_accounts는 생성되지 않는다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 생성/수정한 파일
3. account-aware 적용 명령
4. paper_default legacy 정책
5. non-default reports root 정책
6. non-default reviews/template root 정책
7. review-template → review-validate → review-append 연결성
8. path safety check
9. 테스트 결과
10. Notion actual sync/write 실행 여부
11. 실제 운영 outputs/paper_accounts 생성 여부
12. 기존 paper_default 호환성
13. 다음 MFU 제안
```

반드시 명시:

```text
이번 PAPER15-3G는 non-default reports / review-template 체인을 account-aware root에 연결하는 작업이며, Notion actual sync/write, Notion row migration, broker/API, cloud runner, paper_default legacy migration은 포함하지 않는다.
```

END MFU-PAPER15-3G_REPORTS_REVIEW_TEMPLATE_ACCOUNT_ROOT
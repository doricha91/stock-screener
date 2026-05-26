# MFU-PAPER14-7B: 사후복기 Review 구조 조사 및 Notion 운영 루프 위치 정리

## 목적

이번 PAPER14-7B는 사후복기 Review 구조 조사 및 Notion 운영 루프 위치 정리 작업이며, Notion Review DB 생성, Review import/commit 구현, Python 코드 수정, Notion actual export는 수행하지 않았다.

이 문서는 paper 전체 운영 루프에서 `Manual Review / Retrospective`가 어떤 역할을 해야 하는지 조사하고, 기존 Python의 `paper_manual_review` 계열 CSV / Markdown / CLI / 테스트 구조를 기준으로 Notion이 들어갈 위치를 정리한다.

기본 원칙:

- Notion = 입력 UI / 검토 UI / staging layer
- Python = 검증 / 정규화 / commit 주체
- CSV / Markdown / SQLite = source of truth

## 기존 `paper_manual_review` 관련 코드 조사 결과

정확한 파일명이 `paper_manual_review.py`인 단일 모듈은 없다.  
대신 review 기능은 아래와 같이 이미 여러 단계로 분리되어 존재한다.

### 1. Review source 생성 계층

- `core/paper_symbol_review_buckets.py`
  - 심볼별 review bucket 분류 생성
- `core/paper_symbol_review_worksheet.py`
  - 질문 단위 worksheet 생성
- `core/paper_daily_review_summary.py`
  - 운영자용 `paper_daily_review_summary.md` 생성

해당 스크립트:

- `scripts/generate_paper_symbol_review_buckets.py`
- `scripts/generate_paper_symbol_review_worksheet.py`
- `scripts/generate_paper_daily_review_summary.py`

출력물:

- `outputs/paper_test/reports/paper_symbol_review_buckets.csv`
- `outputs/paper_test/reports/paper_symbol_review_buckets_summary.md`
- `outputs/paper_test/reports/paper_symbol_review_worksheet.csv`
- `outputs/paper_test/reports/paper_symbol_review_worksheet.md`
- `outputs/paper_test/reports/paper_daily_review_summary.md`

### 2. Manual Review template 생성 계층

- `core/paper_manual_review_log_template.py`
- `scripts/generate_paper_manual_review_log_template.py`

출력물:

- `outputs/paper_test/reviews/paper_manual_review_log_template.csv`
- `outputs/paper_test/reviews/paper_manual_review_log_template.md`

역할:

- worksheet 질문을 review log template row로 변환
- `manual_answer`, `review_status`, `follow_up_needed`, `review_tag`, `reviewer_note` 같은 수동 입력 칼럼을 비워 둔 채 생성

### 3. Manual Review validation 계층

- `core/paper_manual_review_log_validator.py`
- `scripts/validate_paper_manual_review_log.py`

출력물:

- `outputs/paper_test/reviews/paper_manual_review_log_validation_report.md`
- `outputs/paper_test/reviews/paper_manual_review_log_validation_issues.csv`

역할:

- template 또는 review log row 형식을 검증
- `review_status`, `follow_up_needed`, `review_tag`, duplicate key 등을 검사

### 4. Manual Review append / commit 계층

- `core/paper_manual_review_log_append.py`
- `scripts/append_paper_manual_review_log.py`

출력물:

- `outputs/paper_test/reviews/paper_manual_review_log.csv`
- `outputs/paper_test/reviews/paper_manual_review_log_append_report.md`
- `outputs/paper_test/reviews/paper_manual_review_log_append_issues.csv`

역할:

- template에서 append 가능한 row만 골라 review log 원장에 추가
- pending row는 append하지 않음
- duplicate key는 overwrite하지 않고 skip

### 5. CLI 연결

- `scripts/paper.py`
  - `review`
  - `review-template`
  - `review-validate`
  - `review-append`

현재 shortcut 의미:

- `paper.py review`
  - `reports -> review-template -> review-validate`
  - review material 생성과 validation까지만 수행
- `paper.py review-append`
  - 별도 명령으로 append 수행

### 6. 테스트

관련 테스트가 이미 존재한다.

- `tests/test_paper_cli.py`
- `tests/test_paper_daily_review_summary.py`
- `tests/test_paper_symbol_review_buckets.py`
- `tests/test_paper_symbol_review_worksheet.py`
- `tests/test_paper_manual_review_log_template.py`
- `tests/test_paper_manual_review_log_validator.py`
- `tests/test_paper_manual_review_log_append.py`
- `tests/test_paper_preflight_check.py`
- `tests/test_paper_status.py`
- `tests/test_paper_weekly_status.py`

결론:

- 기존 Review 코드는 실재하며, template / validate / append까지 포함한 CSV 기반 흐름이 이미 있다.

## 기존 Review CSV / MD source 후보

현재 기준으로 source of truth 후보는 명확하다.

### 1차 source of truth 후보

- `outputs/paper_test/reviews/paper_manual_review_log.csv`

이유:

- append 이후 최종 누적 review row가 저장되는 파일
- review_date + symbol + question_id를 기준으로 중복을 제어
- 수동 답변과 상태값이 최종적으로 남는 위치

### 2차 파생 / 작업용 source

- `outputs/paper_test/reviews/paper_manual_review_log_template.csv`
  - 아직 작성 전 또는 작성 중인 작업용 템플릿
- `outputs/paper_test/reviews/paper_manual_review_log_template.md`
  - template 안내 문서
- `outputs/paper_test/reviews/paper_manual_review_log_validation_report.md`
  - 검증 결과
- `outputs/paper_test/reviews/paper_manual_review_log_append_report.md`
  - append 결과

### 3차 참고용 source

- `outputs/paper_test/reports/paper_symbol_review_worksheet.csv`
- `outputs/paper_test/reports/paper_symbol_review_worksheet.md`
- `outputs/paper_test/reports/paper_symbol_review_buckets.csv`
- `outputs/paper_test/reports/paper_daily_review_summary.md`

결론:

- Review source of truth는 `paper_manual_review_log.csv`가 가장 적절하다.
- Notion은 이 CSV 원장을 대체하면 안 된다.

## Daily Review Summary와 Manual Review의 차이

### Daily Review Summary

- 시스템이 생성하는 결과 요약 report
- 하루 성과, review bucket, worksheet 포인터, warnings를 정리
- non-actionable summary

### Manual Review / Retrospective

- 사람이 작성하는 사후복기 원장
- 질문별 답변
- review status
- follow-up 필요 여부
- review tag
- reviewer note

정리:

- `Daily Review Summary = 시스템 생성 report`
- `Manual Review = 사람이 채우는 사후복기 원장`

즉 둘은 연결되지만 같은 계층이 아니다.

## Review source of truth 원칙

권장 원칙:

- source of truth:
  - `paper_manual_review_log.csv`
  - 관련 validation / append report markdown
- Notion:
  - review 입력 UI
  - review 검토 UI
  - staging layer

즉 Notion에서 review를 작성하더라도, 최종 commit은 Python이 검증 후 `paper_manual_review_log.csv`에 반영해야 한다.

## Notion Review staging layer 후보 흐름

가장 자연스러운 후보 흐름은 아래와 같다.

1. `Daily Review Summary` 확인
2. 사용자가 Notion Review 입력 DB에 사후복기 작성
3. Python이 Notion Review 입력값 read-only import
4. validation / preview
5. 사용자 승인
6. `paper_manual_review_log.csv` commit
7. Notion Review row status back-write

이 흐름이 적절한 이유:

- 기존 `template -> validate -> append` 구조와 잘 맞는다.
- Notion을 source of truth로 만들지 않는다.
- Python이 최종 검증과 dedupe를 담당한다.

## paper 전체 운영 루프에서 Notion 위치

권장 운영 루프:

1. Prepare
2. Daily Plan
3. Plan Export
4. Action
5. Actual Action Input
6. Validation Preview
7. Commit
8. State Refresh
9. Status Sync
10. Reports
11. Review / Retrospective
12. Weekly / Benchmark / Next Plan

단계별 구분:

### 1. Python 실행 단계

- `prepare`
- `plan`
- `preview`
- `commit`
- `state refresh`
- `status sync`
- `reports`
- `review validate`
- `review append`

### 2. Notion 입력 / 확인 단계

- Daily Plan 확인
- Manual Executions 입력
- Daily Review Summary 확인
- Manual Review / Retrospective 입력

### 3. source of truth 파일

- 계획:
  - `daily_action_plan_YYYYMMDD.md`
  - config snapshot JSON
- 실행:
  - `paper_execution_log.csv`
  - `paper_account_snapshot.csv`
  - `paper_position_snapshot.csv`
  - `paper_current_state_YYYYMMDD.json`
- review:
  - `paper_symbol_review_buckets.csv`
  - `paper_symbol_review_worksheet.csv`
  - `paper_manual_review_log.csv`

## 스마트폰 가능 단계 / 로컬 PC 필수 단계

### 스마트폰에서 가능한 단계

- Daily Plan 확인
- Manual Executions 입력
- Daily Review Summary 확인
- Manual Review / Retrospective 입력

이 단계들은 Notion 모바일 UI와 잘 맞는다.

### 반드시 로컬 PC에서 해야 하는 단계

- preview 실행
- commit 실행
- ledger / snapshot / current_state 갱신
- Manual Execution status back-write
- report 생성
- review validation
- review append
- Notion export / sync

이유:

- Python 실행
- CSV / Markdown source 관리
- validation / append / dedupe
- 상태 파일 갱신

## 구현 필요 여부와 후속 MFU 제안

현재 구조를 기준으로 보면, Review Notion 연동은 “완전히 새로 설계”할 문제가 아니라 기존 `paper_manual_review_log` 흐름을 Notion staging으로 연결하는 문제가 된다.

권장 후속 MFU:

1. Review 입력용 Notion schema contract 문서화
2. Review read-only importer preview
3. Review validation / append preview
4. Review commit to `paper_manual_review_log.csv`
5. Review status back-write
6. Review SOP 문서화

## 리스크와 반론

### 리스크 1. review는 질문 단위 row라 Notion 입력량이 많다

- 실제로 `paper_manual_review_log_template.csv`는 질문 단위 row가 많다.
- 모바일 UI에서는 row 수가 많으면 입력 피로도가 커질 수 있다.

### 리스크 2. template와 final log를 어떻게 분리할지 필요

- Notion에서 template row와 committed row를 같은 DB에 둘지, status/view로 분리할지 추가 설계가 필요하다.

### 반론 1. 그냥 Notion에 메모만 쓰면 되지 않나

- 그렇게 하면 Python review 원장과 분리되어 source of truth 원칙이 깨진다.
- 현재 시스템은 이미 CSV 원장 / validation / append 구조를 갖고 있으므로, Notion-only 메모로 후퇴할 이유가 약하다.

### 반론 2. review 자동화 전에 SOP부터 정리해야 하지 않나

- 일부는 맞다.
- 다만 현재는 review 원장 구조가 이미 존재하므로, 구조 조사와 Notion 위치 정리는 SOP보다 먼저 해도 의미가 있다.

## 최종 권고안

권고 A: 기존 `paper_manual_review` 구조를 활용해 Notion Review input/import/commit을 설계한다.

이유:

1. review 원장 구조가 이미 Python 쪽에 존재한다.
2. `template -> validate -> append` 흐름이 있어서 source of truth를 CSV로 유지하기 쉽다.
3. `Daily Review Summary`와 `Manual Review`를 명확히 분리할 수 있다.
4. Notion은 입력 UI / staging layer로만 쓰면 기존 원칙과 충돌하지 않는다.

## 반론과 검증

반론:

- 기존 review code가 너무 복잡해서 새로 만드는 것이 낫지 않나

검증:

- 실제로는 이미 테스트와 CLI가 갖춰져 있어 “없는 기능”이 아니다.
- 새로 만들면 오히려 source of truth / validation / append semantics를 중복 구현하게 된다.

따라서 현재는 새 원장을 invent하기보다 existing review log 구조를 재사용하는 것이 더 안전하다.

## 다음 MFU 제안

1. `PAPER14-7C`: Manual Review Notion schema contract + view policy
2. `PAPER14-7D`: Review read-only importer preview
3. `PAPER14-7E`: Review validation / append commit 설계 또는 구현
4. `PAPER14-7F`: Review status back-write
5. `PAPER14-7G`: Review 포함 운영 SOP 보강

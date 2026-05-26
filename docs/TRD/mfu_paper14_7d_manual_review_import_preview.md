# MFU-PAPER14-7D: Manual Review read-only importer preview

## 1. 목적

이번 PAPER14-7D는 Manual Review read-only importer preview 작업이며, Review append commit, Notion status back-write, Python review 원장 수정, Notion actual write는 수행하지 않았다.

본 MFU의 목표는 Notion `Manual Reviews` DB에 질문 단위 row로 입력된 사후복기 답변을 Python에서 read-only로 가져와, 기존 review 원장 구조에 맞는 validation preview를 생성하는 것이다.


## 2. question-level row 정책

`PAPER14-7C`에서 확정한 정책을 그대로 따른다.

- 질문 1개 = Notion row 1개
- 기존 CSV 기준 dedupe key = `review_date + symbol + question_id`
- Notion은 입력 UI 또는 staging layer
- 최종 review 원장은 `paper_manual_review_log.csv`


## 3. minimal input field 정책

사용자 입력 중심 필드는 아래에 한정한다.

- `Manual Answer`
- `Review Status`
- `Follow-up Needed`
- `Review Tag`
- `Reviewer Note`

나머지 필드는 template 또는 시스템 관리 필드로 본다.


## 4. source of truth 원칙

기본 원칙:

- Notion = 입력 UI / staging layer
- Python = 검증 / 정규화 / append commit 주체
- CSV / Markdown = Review source of truth

이번 7D에서는 아래 파일을 읽기만 한다.

- `outputs/paper_test/reviews/paper_manual_review_log.csv`
- `outputs/paper_test/reviews/paper_manual_review_log_template.csv`


## 5. Notion mapping

새 data source key:

- `manual_reviews`

환경변수 override:

- `NOTION_MANUAL_REVIEWS_DATA_SOURCE_ID`

예시 property mapping:

- `Name`
- `External Key`
- `Review Date`
- `Symbol`
- `Question ID`
- `Question`
- `Manual Answer`
- `Review Status`
- `Follow-up Needed`
- `Review Tag`
- `Reviewer Note`
- `Source Template Key`
- `Validation Status`
- `Validation Message`
- `Import Status`
- `Imported At`
- `Synced At`

import candidate 기본 조건:

- `Review Date = --date`
- `Import Status = READY`


## 6. validation 규칙

### 6.1 FAIL

- `Review Date` 없음
- `Symbol` 없음
- `Question ID` 없음
- `Question` 없음
- `Manual Answer` 없음
- `Review Status` 없음
- `Review Status = pending`
- 동일 batch 내 `review_date + symbol + question_id` 중복
- 기존 `paper_manual_review_log.csv`에 같은 review key 존재

### 6.2 WARNING

- `Follow-up Needed` 없음
- `Review Tag` 없음
- `Reviewer Note` 없음
- `Source Template Key` 없음
- template에 없는 `question_id`
- template와 `Question` 원문 불일치

### 6.3 기존 validator 재사용 범위

기존 `paper_manual_review_log_validator.py`의 아래 규칙을 preview에도 재사용한다.

- `review_status` 허용값 검사
- `follow_up_needed` 허용값 검사
- `review_tag` 허용값 검사
- duplicate key 검사
- `follow_up_needed=true`일 때 context 유무 검사

단, 이번 7D preview는 append 전 단계이므로 `Manual Answer 없음 = FAIL`, `pending = FAIL`을 별도로 더 엄격하게 적용한다.


## 7. preview report 구조

출력 파일:

- `outputs/paper_test/reports/manual_review_import_preview_YYYYMMDD.json`
- `outputs/paper_test/reports/manual_review_import_preview_YYYYMMDD.md`

포함 내용:

- `review_date`
- `candidate_count`
- `pass_count`
- `warning_count`
- `fail_count`
- `append_allowed`
- `normalized candidates`
- `validation issues`
- `duplicate_candidates`
- `source_data_source_id`

판정 규칙:

- FAIL 하나라도 있으면 `append_allowed=false`
- WARNING만 있으면 `append_allowed=true_with_warnings`
- 모두 PASS면 `append_allowed=true`


## 8. 제외 범위

이번 작업에서 하지 않는다.

- `paper_manual_review_log.csv` append
- review CSV/MD overwrite
- Notion `Validation Status / Import Status` back-write
- Notion actual write
- Review commit
- Manual Execution import/commit/status sync 재실행
- paper ledger CSV 수정


## 9. 후속 7E append commit 계획

후속 MFU에서 구현할 권장 흐름:

1. Notion `Manual Reviews` row read-only import
2. validation preview 생성
3. 사용자 승인
4. `paper_manual_review_log.csv` append
5. append report 생성
6. Notion review row status back-write

즉 7D는 append 직전의 preview 계층에 해당한다.


## 10. 테스트 결과

테스트 범위:

- question-level row normalization
- missing `Manual Answer` FAIL
- optional field WARNING
- batch duplicate FAIL
- existing review log duplicate FAIL
- preview JSON/Markdown 생성
- `--commit` not implemented failure


## 11. 남은 리스크

- 현재 template 비교는 로컬 `paper_manual_review_log_template.csv`가 존재할 때만 수행한다.
- `Question` mismatch는 warning으로만 처리하며 auto-fix는 하지 않는다.
- 모바일 입력 row 수가 많아질 수 있어, 장기적으로 template question count를 함께 관리할 필요가 있다.

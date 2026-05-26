# MFU-PAPER14-7E: Manual Review validation / append commit

## 1. 목적

이번 PAPER14-7E는 Manual Review preview 결과를 `paper_manual_review_log.csv`에 append commit하는 작업이며, Notion status back-write, Notion actual write, Manual Execution commit, paper trading ledger 수정은 수행하지 않는다.

본 MFU는 `PAPER14-7D`에서 생성된 preview JSON을 기준 artifact로 사용해, 검증된 review candidate만 기존 Python review 원장에 append하는 경로를 제공한다.


## 2. preview JSON 기준 append 원칙

기본 원칙:

- Notion을 다시 query하지 않는다.
- `--preview-json`으로 전달된 preview artifact만 append 기준으로 사용한다.
- preview와 실제 append 사이에 Notion row가 바뀌었다면 preview를 다시 생성해야 한다.

append 차단 조건:

- preview JSON 없음
- preview `review_date`와 `--date` 불일치
- `fail_count > 0`
- `append_allowed = false`
- `append_allowed = true_with_warnings`인데 `--allow-warnings` 없음


## 3. WARNING 처리 정책

- `append_allowed = true`
  - 바로 append 가능
- `append_allowed = true_with_warnings`
  - 기본은 append 금지
  - `--allow-warnings`가 있을 때만 append 허용
- `append_allowed = false`
  - append 금지

즉 warning preview는 사용자의 명시 승인 없이는 append하지 않는다.


## 4. review log mapping

Manual Review candidate는 기존 `paper_manual_review_log.csv` schema에 맞게 매핑한다.

직접 매핑:

- `review_date -> review_date`
- `symbol -> symbol`
- `question_id -> question_id`
- `question_text -> question_text`
- `manual_answer -> manual_answer`
- `review_status -> review_status`
- `follow_up_needed -> follow_up_needed`
- `review_tag -> review_tag`
- `reviewer_note -> reviewer_note`
- `created_at -> created_at`

template 보강 컬럼:

- `review_bucket`
- `review_priority`
- `sample_size_flag`
- `symbol_status`
- `question_category`
- `source_worksheet_path`

정책:

- 같은 `review_date + symbol + question_id`를 가진 template row가 있으면 그 row의 context 컬럼을 재사용한다.
- template row가 없으면 context 컬럼은 빈 값으로 두고 append row를 구성한다.
- `is_actionable`은 기존 정책대로 항상 `false`

중요:

- `paper_manual_review_log.csv` 컬럼은 확장하지 않는다.


## 5. 중복 방지 정책

기준 key:

- `review_date + symbol + question_id`

정책:

- preview candidate 자체에 duplicate canonical key가 있으면 commit 차단
- 기존 `paper_manual_review_log.csv`에 같은 review key가 있으면 commit 차단
- append pre-check row count와 실제 append row count가 다르면 commit 실패

즉 동일 review row를 중복 append하지 않는다.


## 6. backup / rollback 정책

append 전 backup:

- `outputs/dev_backups/paper_manual_review_log_before_manual_review_commit_YYYYMMDD_HHMMSS.csv`

정책:

- append 전 기존 review log를 백업한다.
- write 또는 sidecar report 생성 중 실패가 나면 backup으로 rollback한다.
- rollback 후에도 실패하면 상위 에러로 명확히 보고한다.


## 7. commit report 구조

출력 파일:

- `outputs/paper_test/reports/manual_review_import_commit_YYYYMMDD.json`
- `outputs/paper_test/reports/manual_review_import_commit_YYYYMMDD.md`

포함 내용:

- `review_date`
- `preview_json_path`
- `candidate_count`
- `appended_count`
- `skipped_count`
- `failed_count`
- `append_allowed`
- `allow_warnings`
- row별
  - `canonical_key`
  - `page_id`
  - `review_date`
  - `symbol`
  - `question_id`
  - `validation_warnings`
  - `append_status`


## 8. Notion back-write 제외

이번 7E에서는 아래를 하지 않는다.

- `Validation Status` back-write
- `Validation Message` back-write
- `Import Status` back-write
- `Imported At` back-write
- `Synced At` back-write

이 범위는 `PAPER14-7F`로 분리한다.


## 9. 후속 7F 계획

후속 `PAPER14-7F`에서 다룰 범위:

- append commit 결과를 Notion `Manual Reviews` row에 back-write
- `Validation Status`
- `Validation Message`
- `Import Status`
- `Imported At`
- `Synced At`

즉 7E는 Python review 원장 append까지만 책임지고, Notion status sync는 후속 단계로 남긴다.

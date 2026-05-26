# MFU-PAPER14-7F: Manual Review status back-write

## 목적

PAPER14-7E에서 `paper_manual_review_log.csv`에 append commit된 Manual Review 결과를
Notion `Manual Reviews` row에 상태값으로 되돌려 쓴다.

이번 단계는 append commit 이후 표시 상태 동기화다.

## 7E commit report 기반 sync 원칙

- sync 기준 artifact는 `manual_review_import_commit_YYYYMMDD.json`이다.
- Notion을 다시 query해서 append 여부를 판단하지 않는다.
- commit report에 기록된 `APPENDED` 또는 `COMMITTED` row만 sync 대상으로 본다.
- `page_id`, `canonical_key`, `review_date`, `symbol`, `question_id`가 없으면 `SKIPPED` 처리한다.
- 같은 report를 다시 sync해도 같은 값을 다시 쓰는 idempotent update여야 한다.

## back-write 대상 필드

아래 필드만 업데이트한다.

- `External Key`
- `Validation Status`
- `Validation Message`
- `Import Status`
- `Imported At`
- `Synced At`

권장 값:

- `External Key = canonical_key`
- `Validation Status = PASS 또는 WARNING`
- `Validation Message = validation warning 요약 또는 OK`
- `Import Status = COMMITTED`
- `Imported At = sync 실행 시각`
- `Synced At = sync 실행 시각`

## 수정하지 않는 사용자 입력 필드

아래 필드는 사용자가 입력한 review 내용이므로 수정하지 않는다.

- `Review Status`
- `Manual Answer`
- `Follow-up Needed`
- `Review Tag`
- `Reviewer Note`
- `Review Date`
- `Symbol`
- `Question ID`
- `Question`

## dry-run 정책

- `--dry-run`에서는 Notion write를 호출하지 않는다.
- dry-run에서도 commit report를 읽고 sync 대상/skip/실패 사유를 계산한다.
- dry-run 결과가 `SUCCESS` 또는 기대한 `PARTIAL_SUCCESS`인지 확인한 뒤 actual sync로 넘어간다.

## 실패 처리 정책

- 특정 page update 실패 시 해당 row는 `FAILED`로 기록한다.
- 일부 row만 실패하면 `overall_status = PARTIAL_SUCCESS`로 보고한다.
- 모든 대상 row가 실패하면 `overall_status = FAILED`가 될 수 있다.

## review 원장 rollback을 하지 않는 이유

7F는 review 원장 append 이후의 표시 상태 동기화 단계다.

- `paper_manual_review_log.csv`가 이미 source of truth다.
- Notion sync 실패는 표시 상태 불일치이지, append commit 실패가 아니다.
- 따라서 Notion sync 실패 시 review CSV rollback은 하지 않는다.

## 후속 SOP 반영 계획

운영 SOP에는 아래 순서를 반영하는 것이 적절하다.

1. Manual Review preview 생성
2. warning/fail 확인
3. append commit 실행
4. commit report 확인
5. review status back-write dry-run
6. review status back-write actual sync

## 제외 범위

이번 7F에서는 아래를 하지 않는다.

- Review append commit 재실행
- Notion review row 내용 수정
- Manual Execution import/commit/status sync 재실행
- paper trading ledger 수정
- Notion DB schema 변경

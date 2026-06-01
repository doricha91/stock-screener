## Purpose

로컬 `paper.py status`에 review append 진행도를 반영해 `REVIEW_READY`, `REVIEW_PARTIAL`, `REVIEW_DONE`를 구분한다.

## Scope / Non-scope

- Scope: `core/paper_status.py`의 로컬 workflow status semantics, review progress 계산, status JSON/text 보강, 테스트
- Non-scope: Notion DB 추가, Notion export/sync, broker/API, cloud runner, `paper_default` migration

## Existing workflow_status model

기존 상태:

- `NO_PLAN`
- `PLAN_READY`
- `COMMITTED`
- `REVIEW_READY`
- `UNKNOWN_OR_INCOMPLETE`

문제:

- review template이 PASS이고 일부 row만 append돼도 `REVIEW_READY`로만 보였다.

## New REVIEW_PARTIAL / REVIEW_DONE semantics

- `REVIEW_READY`
  - review template 존재
  - validation `PASS`
  - manual review log 없음
- `REVIEW_PARTIAL`
  - review template 존재
  - validation `PASS`
  - manual review log 1건 이상 존재
  - pending review row가 남아 있음
- `REVIEW_DONE`
  - review template 존재
  - validation `PASS`
  - manual review log 1건 이상 존재
  - pending review row가 0

## Review progress calculation

추가 필드:

- `review_answered_row_count`
- `review_pending_row_count`
- `review_done_row_count`
- `review_completion_ratio`
- `review_progress_status`

answered 판정:

- `review_status in {reviewed, done, complete, completed}`
- 또는 `manual_answer`가 비어 있지 않음

pending 판정:

- template row 중 answered가 아닌 row

## Status transition table

1. date 없음 → `UNKNOWN_OR_INCOMPLETE`
2. plan 없음 → `NO_PLAN`
3. same-date snapshot 없음 → `PLAN_READY`
4. reports + review template + validation `PASS`
   - pending 0 + review log 있음 → `REVIEW_DONE`
   - pending > 0 + review log 있음 → `REVIEW_PARTIAL`
   - review log 없음 → `REVIEW_READY`
5. current state + account snapshot + position snapshot → `COMMITTED`
6. 그 외 → `UNKNOWN_OR_INCOMPLETE`

validation이 `FAIL`이면 `REVIEW_PARTIAL`/`REVIEW_DONE`으로 전이하지 않는다.

## Backward compatibility

- `paper_default` legacy root 해석 유지
- non-default `account_paths` status 유지
- 기존 `COMMITTED` 판정 유지
- review log가 없는 기존 상태는 계속 `REVIEW_READY`

## Impact on paper_sandbox 4C result

기존 4C 상태:

- `review_template_row_count=4`
- `manual_review_log_row_count=1`
- `review_validation_result=PASS`
- 기존 `workflow_status=REVIEW_READY`

신규 판정:

- `review_answered_row_count=1`
- `review_pending_row_count=3`
- `review_completion_ratio=0.25`
- `review_progress_status=PARTIAL`
- `workflow_status=REVIEW_PARTIAL`
- `next_recommended_command=complete pending review rows then paper.py review-append`

## Future Notion Daily Ops Status DB dependency

이번 MFU는 로컬 status semantics만 정리한다. 향후 Notion Daily Ops 상태를 도입할 경우에도 로컬 source-of-truth는 이 progress 요약을 재사용하는 방향이 자연스럽다.

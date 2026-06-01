# PAPER16-3 Manual Notion View Consistency Check

## Purpose

PAPER16-1 / PAPER16-2에서 정의한 Daily Ops Status Dashboard 설계와 운영 정책을 기준으로, 사용자가 Notion에서 수동 정리한 `Daily Ops Status` view 구성이 문서와 일치하는지 점검하고 기록한다.

이번 작업은 Notion을 직접 수정하지 않는다. 이 문서는 사용자 제공 화면/수동 보고를 바탕으로 검증 결과, 남은 차이, 후속 조치를 정리한다.

## Source Material

기준 문서:

- `docs/TRD/mfu_paper16_daily_ops_status_dashboard_design.md`
- `docs/TRD/mfu_paper16_operator_command_map_and_rerun_policy.md`
- `docs/operations/paper_daily_ops.md`
- `docs/operations/paper_notion_ops.md`

사용자 확인 사항:

- 기존 `Daily Ops Status` DB 안에서 view를 추가/정리했다.
- 새 DB 또는 duplicate DB를 만들지 않은 것으로 사용자와 화면 기준 확인됐다.
- 5개 view가 모두 Table 보기로 구성됐다.
- view 이름은 `Today Ops`, `By Account`, `Needs Action`, `Recent Sync`, `Review Closeout`이다.
- `By Account` view에 `Workflow Status` 표시가 추가됐다.
- 현재 filter는 적용하지 않았다. row visibility 확보를 우선하기 위한 의도적 보류다.

운영 원칙:

- CSV / JSON / Markdown / SQLite가 source-of-truth다.
- Notion은 input / review / staging / presentation layer다.
- `External Key` 수동 수정은 금지한다.
- property 삭제는 금지한다.
- 기존 `Daily Ops Status` DB 안에서 view만 정리한다.
- Notion actual write/export는 실행하지 않는다.

## Manual Notion View Setup Summary

현재 수동 정리 결과는 PAPER16-1의 view 설계와 대체로 일치한다.

- 모든 view는 기존 `Daily Ops Status` DB 안에 있다.
- 모든 view는 Table format이다.
- duplicate DB 생성은 없는 것으로 기록한다.
- 필터는 아직 적용하지 않는다.
- group/visible property는 운영 visibility를 우선해 구성했다.
- `External Key`는 삭제하거나 수동 수정하지 않는다.

## View-by-View Consistency Check

| View | Expected Format | Actual Format | Key Visible Fields | Grouping | Filter Status | Result | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `Today Ops` | Table | Table | `Account ID`, `Status Date`, `Workflow Status`, `Review Progress Status`, `Review Completion Ratio`, `Sync Status`, `Next Recommended Command`, `Blocking Reason`, `Synced At` | `Account ID` 기준 그룹화가 적용된 것으로 보임 | not applied / deferred | pass with filter deferred | selected-date/today filter는 row visibility 문제로 보류 |
| `By Account` | Table | Table | `Account ID`, `Status Date`, `Workflow Status`, `Review Progress Status`, `Sync Status`, `Review Pending Row Count`, `Next Recommended Command`, `External Key` | `Account ID` 기준 그룹화 | not applied / deferred | pass with filter deferred | `Workflow Status` 표시 추가 완료 |
| `Needs Action` | Table | Table | `Workflow Status`, `Review Validation Result`, `Sync Status`, `Blocking Reason`, `Next Recommended Command` | `Workflow Status` 기준 그룹화 | not applied / deferred | partial pass / filter deferred | `REVIEW_PARTIAL`, `UNKNOWN_OR_INCOMPLETE` 등 조치 필요 상태 확인 가능. 필터 미적용으로 strict Needs Action view는 아직 아님 |
| `Recent Sync` | Table | Table | `External Key`, `Sync Status`, `Synced At`, `Last Status Checked At`, `Workflow Status`, `Review Progress Status` | `Sync Status` 기준 그룹화 | not applied / deferred | pass with filter deferred | recent-date filter는 row 축적 후 적용 |
| `Review Closeout` | Table | Table | `Review Completion Ratio`, `Review Template Exists`, `Review Validation Result`, `Manual Review Log Exists`, answered/pending counts, `Next Recommended Command` | `Review Progress Status` 기준 그룹화 | not applied / deferred | pass with filter deferred | pending/done filter는 row visibility 확인 후 적용 |

## Deferred Filters Policy

현재 Notion view에는 필터를 적용하지 않는다.

이유:

- 현재 샘플 row 수가 적다.
- filter 적용 시 필요한 row가 보이지 않는 문제가 있었다.
- 지금은 strict filtering보다 운영자가 row를 볼 수 있는 visibility 확보가 우선이다.

판정:

- 필터 미적용은 실패가 아니다.
- 의도적 보류 사항이다.
- Daily Ops Status row가 더 쌓이고 status 값이 안정화된 뒤 filter를 추가한다.

후속 filter hardening 후보:

- `Needs Action` filter hardening
- `Today Ops` selected-date filter
- `Recent Sync` recent-date filter
- `Review Closeout` pending/done filter

필터 추가 전 확인 기준:

- 기존 row가 사라져 보이지 않는지 확인한다.
- `paper_sandbox` row가 각 view에서 의도대로 남는지 확인한다.
- candidate/future status가 filter에서 누락되지 않는지 확인한다.
- filter 적용 전후 screenshot 또는 수동 체크 결과를 기록한다.

## Remaining Gaps

- Filters are intentionally not applied yet.
- Actual Notion UI verification is based on user-provided screenshots/manual report, not automated Notion API inspection.
- Candidate/future statuses such as `NOT_SYNCED`, `SYNC_FAILED`, `READY` may need future filter/view refinement.
- More rows are needed before filter behavior can be safely hardened.
- No automatic schema/view drift check exists yet.
- `Needs Action`은 filter가 없기 때문에 현재는 "조치 필요 상태를 볼 수 있는 view"이며, strict action-only view는 아니다.

## PAPER16 Closeout Readiness

PAPER16 dashboard foundation은 closeout 가능한 상태에 가깝다.

충족 사항:

- 5개 권장 view가 모두 존재한다.
- 모든 view가 기존 `Daily Ops Status` DB 안의 Table view다.
- 새 DB / duplicate DB를 만들지 않았다.
- `By Account`에 `Workflow Status`가 표시된다.
- source-of-truth 원칙이 유지된다.
- `External Key` 수동 수정 금지 원칙이 유지된다.
- filter deferred 상태가 실패가 아니라 의도적 보류로 기록됐다.

보류 사항:

- filter hardening은 row 축적 이후로 미룬다.
- 자동화된 Notion view drift check는 아직 없다.
- candidate/future status에 대한 view/filter 정책은 운영 데이터가 더 쌓인 뒤 재검토한다.

## PAPER16-4 Or Follow-up Candidates

후속 후보:

- PAPER16-4: Daily Ops Status filter hardening
- PAPER16-5: Manual Notion view drift checklist / screenshot audit
- PAPER16-6: Needs Action operating SOP refinement
- PAPER16-7: Schema/view drift check design

권장 순서:

1. row를 더 축적한다.
2. filter 적용 전후 visibility를 비교한다.
3. `Needs Action`부터 filter hardening을 적용한다.
4. `Today Ops`, `Recent Sync`, `Review Closeout` filter를 순차 적용한다.
5. 자동 schema/view drift check는 별도 설계로 분리한다.

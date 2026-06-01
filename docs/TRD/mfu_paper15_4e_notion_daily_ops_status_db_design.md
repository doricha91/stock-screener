## Purpose

다중계좌 paper 운영 상태를 계좌별·날짜별로 한눈에 보는 Notion `Daily Ops Status` DB를 설계한다.

## Scope / Non-scope

- Scope: DB 목적, 이름, External Key, property/type/source, status option, view, 운영 체크리스트
- Non-scope: Notion DB 실제 생성, Notion API write/sync/export, 코드 구현, mapping 수정, paper 원장 수정

## Current local workflow status model

로컬 source-of-truth는 `paper.py status`다.

- `NO_PLAN`
- `PLAN_READY`
- `COMMITTED`
- `REVIEW_READY`
- `REVIEW_PARTIAL`
- `REVIEW_DONE`
- `UNKNOWN_OR_INCOMPLETE`

review 진행도 보조 필드:

- `review_progress_status`
- `review_completion_ratio`
- `review_answered_row_count`
- `review_pending_row_count`

## Why a separate Daily Ops Status DB is needed

- 기존 Notion DB는 daily plan, snapshot, review, execution 같은 상세 데이터 중심이다.
- 운영자는 계좌별 하루 상태를 한 화면에서 보기가 어렵다.
- `Daily Ops Status`는 source-of-truth를 대체하지 않고, 로컬 artifact/status를 요약해서 보여주는 관제판 역할만 맡는다.

## DB name recommendation

권장:

- `Daily Ops Status`

대안 비교:

- `Paper Daily Ops Status`: paper 전용임은 분명하지만 이름이 길다.
- `Account Daily Ops Status`: 계좌 중심 의미는 강하지만 daily ops 문맥이 다소 약하다.

## External Key design

권장 형식:

- `daily_ops_status:{account_id}:{status_date}`

예:

- `daily_ops_status:paper_sandbox:2026-05-20`
- `daily_ops_status:paper_default:2026-05-20`

정책:

- 반드시 `account_id` 포함
- date는 `YYYY-MM-DD`
- legacy account-less key 없음
- `paper_default`도 신규 DB에서는 account-aware key만 사용

## Property table with type/source/description

| Property | Type | Source field | Description |
| --- | --- | --- | --- |
| Name | title | derived | `paper_sandbox 2026-05-20` 같은 표시용 제목 |
| External Key | rich_text | derived | `daily_ops_status:{account_id}:{status_date}` |
| Account ID | select | `status.account_id` | 계좌 scope |
| Status Date | date | `status.date` | 상태 기준 날짜 |
| Workflow Status | select | `status.workflow_status` | 로컬 workflow 상태 |
| Review Progress Status | select | `status.review_progress_status` | review 진행도 |
| Review Completion Ratio | number/percent | `status.review_completion_ratio` | review 완료 비율 |
| Next Recommended Command | rich_text | `status.next_recommended_command` | 다음 로컬 액션 |
| Blocking Reason | rich_text | derived | 실패/미완료 사유 요약 |
| Plan Exists | checkbox | `status.plan_exists` | 계획 존재 여부 |
| Current State Exists | checkbox | `status.current_state_exists` | current state 존재 여부 |
| Account Snapshot Exists | checkbox | `status.account_snapshot_exists` | snapshot 존재 여부 |
| Position Snapshot Exists | checkbox | `status.position_snapshot_exists` | position snapshot 존재 여부 |
| Execution Log Rows For Date | number | `status.execution_log_rows_for_date` | 당일 체결 row 수 |
| Reports Ready | checkbox | `status.reports_ready` | 핵심 report 준비 여부 |
| Daily Review Summary Exists | checkbox | `status.paper_daily_review_summary_exists` | summary markdown 존재 여부 |
| Performance Summary Exists | checkbox | `status.paper_performance_summary_exists` | performance summary 존재 여부 |
| Review Template Exists | checkbox | `status.review_template_exists` | review template 존재 여부 |
| Review Template Row Count | number | `status.review_template_row_count` | template row 수 |
| Review Validation Result | select | `status.review_validation_result` | `PASS`/`FAIL`/unknown |
| Manual Review Log Exists | checkbox | `status.manual_review_log_exists` | append log 존재 여부 |
| Manual Review Log Row Count | number | `status.manual_review_log_row_count` | append log row 수 |
| Review Answered Row Count | number | `status.review_answered_row_count` | answered row 수 |
| Review Pending Row Count | number | `status.review_pending_row_count` | pending row 수 |
| Last Status Checked At | date | export timestamp | 로컬 status 체크 시각 |
| Sync Status | select | exporter state | `DRY_RUN`/`SYNCED`/`FAILED`/`SKIPPED` |
| Synced At | date | exporter state | Notion export 처리 시각 |
| Schema Version | rich_text | derived | 예: `daily_ops_status.v1` |
| Source Root | rich_text | `status.account_root` | source-of-truth root 경로 |

## Workflow Status option list

- `NO_PLAN`
- `PLAN_READY`
- `COMMITTED`
- `REVIEW_READY`
- `REVIEW_PARTIAL`
- `REVIEW_DONE`
- `UNKNOWN_OR_INCOMPLETE`

## Review Progress option list

- `NOT_STARTED`
- `READY`
- `PARTIAL`
- `DONE`
- `UNKNOWN`
- `NOT_APPLICABLE`

초기 구현 메모:

- 현재 로컬 `paper.py status`는 `NOT_STARTED`, `PARTIAL`, `DONE`, `NOT_APPLICABLE`만 직접 산출한다.
- `READY`, `UNKNOWN`은 후속 exporter 정규화 계층에서 선택적으로 매핑 가능하다.

## Recommended Notion views

1. `Today by Account`
   - `Status Date = today`
   - `Account ID` group
   - `Workflow Status`, `Next Recommended Command`

2. `Needs Action`
   - `Workflow Status` in `NO_PLAN`, `PLAN_READY`, `COMMITTED`, `REVIEW_READY`, `REVIEW_PARTIAL`, `UNKNOWN_OR_INCOMPLETE`
   - `Next Recommended Command`, `Blocking Reason`

3. `Review Closeout`
   - `Workflow Status` in `REVIEW_READY`, `REVIEW_PARTIAL`, `REVIEW_DONE`
   - `Review Pending Row Count`, `Review Completion Ratio`

4. `By Account`
   - `Account ID` group
   - 날짜 내림차순

5. `Failed / Unknown`
   - `Workflow Status = UNKNOWN_OR_INCOMPLETE` or `Sync Status = FAILED`

## Relationship with existing Notion DBs

- `Daily Ops Status`는 관제판이다.
- `Daily Plans`, `Account Snapshots`, `Manual Executions`, `Manual Reviews` 등은 상세 데이터 DB다.
- 초기에는 relation/rollup 없이 `External Key`, `Account ID`, `Status Date` 기준의 느슨한 연결만 사용한다.
- relation/rollup은 운영 안정화 후 후속 MFU에서 검토한다.

## Manual Notion setup checklist

- 새 DB 이름을 `Daily Ops Status`로 생성
- `Account ID` select option에 최소 `paper_default` 추가
- `Workflow Status` select option을 문서 목록대로 생성
- `Review Progress Status` select option을 문서 목록대로 생성
- `Sync Status` select option 생성
- `Today by Account`, `Needs Action`, `Review Closeout`, `By Account`, `Failed / Unknown` view 생성
- `External Key`를 visible column으로 유지
- `Source Root`와 `Next Recommended Command`도 운영 view에서 보이게 유지

## Risks / open questions

- `Blocking Reason`을 로컬 status가 직접 줄지, exporter가 파생할지 아직 미정
- `Review Progress Status`의 `READY`, `UNKNOWN`을 실제 로컬 상태와 어떻게 대응할지 후속 정의 필요
- 날짜 기준을 snapshot date로 볼지 status check date로 볼지 exporter 정책을 고정해야 함
- 향후 relation/rollup을 넣을 때 DB 복잡도가 급격히 올라갈 수 있음

## Recommended next MFUs

- `PAPER15-4F`: Daily Ops Status mapping/schema 추가
- `PAPER15-4G`: local `paper.py status` -> Daily Ops Status dry-run exporter
- `PAPER15-4H`: Daily Ops Status actual export 제한 실행
- `PAPER15-4I`: legacy Notion row migration preview

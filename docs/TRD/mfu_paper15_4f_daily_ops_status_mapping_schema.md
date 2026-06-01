## Purpose

`Daily Ops Status` Notion DB를 Python mapping/schema 계층에서 인식하도록 추가한다.

## Scope / Non-scope

- Scope
  - `config/notion_property_mapping.example.json`의 `daily_ops_status` section
  - `config/notion_settings.example.json`의 data source placeholder
  - `core/notion_schema_validator.py`의 schema target / select option policy
  - 관련 단위 테스트
- Non-scope
  - Notion DB 실제 생성
  - Notion API write/sync/export
  - `Daily Ops Status` exporter 구현
  - `paper.py status` payload 구조 변경
  - paper 원장 수정

## Added mapping section

section name:

- `daily_ops_status`

mapping target property names:

- `name` -> `Name`
- `external_key` -> `External Key`
- `account_id` -> `Account ID`
- `status_date` -> `Status Date`
- `workflow_status` -> `Workflow Status`
- `review_progress_status` -> `Review Progress Status`
- `review_completion_ratio` -> `Review Completion Ratio`
- `next_recommended_command` -> `Next Recommended Command`
- `blocking_reason` -> `Blocking Reason`
- `plan_exists` -> `Plan Exists`
- `current_state_exists` -> `Current State Exists`
- `account_snapshot_exists` -> `Account Snapshot Exists`
- `position_snapshot_exists` -> `Position Snapshot Exists`
- `execution_log_rows_for_date` -> `Execution Log Rows For Date`
- `reports_ready` -> `Reports Ready`
- `daily_review_summary_exists` -> `Daily Review Summary Exists`
- `performance_summary_exists` -> `Performance Summary Exists`
- `review_template_exists` -> `Review Template Exists`
- `review_template_row_count` -> `Review Template Row Count`
- `review_validation_result` -> `Review Validation Result`
- `manual_review_log_exists` -> `Manual Review Log Exists`
- `manual_review_log_row_count` -> `Manual Review Log Row Count`
- `review_answered_row_count` -> `Review Answered Row Count`
- `review_pending_row_count` -> `Review Pending Row Count`
- `last_status_checked_at` -> `Last Status Checked At`
- `sync_status` -> `Sync Status`
- `synced_at` -> `Synced At`
- `schema_version` -> `Schema Version`
- `source_root` -> `Source Root`

## Property mapping table

| Mapping key | Notion property name | Property type | Required | Notes |
| --- | --- | --- | --- | --- |
| `name` | `Name` | `title` | required | 운영 row 표시 제목 |
| `external_key` | `External Key` | `rich_text` | required | `daily_ops_status:{account_id}:{status_date}` |
| `account_id` | `Account ID` | `select` | recommended | multi-account 식별용, 누락 시 validator `WARNING` |
| `status_date` | `Status Date` | `date` | required | 상태 기준 날짜 |
| `workflow_status` | `Workflow Status` | `select` | required | 로컬 workflow 상태 |
| `review_progress_status` | `Review Progress Status` | `select` | required | review 진행도 |
| `review_completion_ratio` | `Review Completion Ratio` | `number` | required | 0.0 ~ 1.0 비율 |
| `next_recommended_command` | `Next Recommended Command` | `rich_text` | required | 다음 로컬 액션 |
| `blocking_reason` | `Blocking Reason` | `rich_text` | optional | 막힘 사유 요약 |
| `plan_exists` | `Plan Exists` | `checkbox` | required | 존재 여부 |
| `current_state_exists` | `Current State Exists` | `checkbox` | required | 존재 여부 |
| `account_snapshot_exists` | `Account Snapshot Exists` | `checkbox` | required | 존재 여부 |
| `position_snapshot_exists` | `Position Snapshot Exists` | `checkbox` | required | 존재 여부 |
| `execution_log_rows_for_date` | `Execution Log Rows For Date` | `number` | required | 당일 execution row count |
| `reports_ready` | `Reports Ready` | `checkbox` | required | 핵심 reports ready 여부 |
| `daily_review_summary_exists` | `Daily Review Summary Exists` | `checkbox` | required | markdown 존재 여부 |
| `performance_summary_exists` | `Performance Summary Exists` | `checkbox` | required | markdown 존재 여부 |
| `review_template_exists` | `Review Template Exists` | `checkbox` | required | template 존재 여부 |
| `review_template_row_count` | `Review Template Row Count` | `number` | required | template row 수 |
| `review_validation_result` | `Review Validation Result` | `select` | optional | 초기 validator는 `PASS`, `FAIL` 권장 |
| `manual_review_log_exists` | `Manual Review Log Exists` | `checkbox` | required | append log 존재 여부 |
| `manual_review_log_row_count` | `Manual Review Log Row Count` | `number` | required | append log row 수 |
| `review_answered_row_count` | `Review Answered Row Count` | `number` | required | answered row 수 |
| `review_pending_row_count` | `Review Pending Row Count` | `number` | required | pending row 수 |
| `last_status_checked_at` | `Last Status Checked At` | `date` | required | status 계산 시각 |
| `sync_status` | `Sync Status` | `select` | optional | exporter 단계에서 사용 |
| `synced_at` | `Synced At` | `date` | optional | exporter 단계에서 사용 |
| `schema_version` | `Schema Version` | `rich_text` | required | 예: `daily_ops_status.v1` |
| `source_root` | `Source Root` | `rich_text` | required | 로컬 source-of-truth root |

## Select option policy

`Workflow Status` recommended options:

- `NO_PLAN`
- `PLAN_READY`
- `COMMITTED`
- `REVIEW_READY`
- `REVIEW_PARTIAL`
- `REVIEW_DONE`
- `UNKNOWN_OR_INCOMPLETE`

`Review Progress Status` recommended options:

- `NOT_STARTED`
- `READY`
- `PARTIAL`
- `DONE`
- `UNKNOWN`
- `NOT_APPLICABLE`

`Review Validation Result` recommended options:

- `PASS`
- `FAIL`

`Sync Status` recommended options:

- `DRY_RUN`
- `SYNCED`
- `FAILED`
- `SKIPPED`

validator policy:

- 필수 property 누락: `FAIL`
- 권장 property(`Account ID`) 누락: `WARNING`
- select option 일부 누락: `WARNING`
- DB ID 자체가 설정되지 않음: `WARNING` + `missing_data_source_id`, validation skip

## Schema validator behavior

`daily_ops_status`는 optional target이다.

- `config/notion_settings.json`에 `daily_ops_status` data source id가 없으면 전체 validator를 실패시키지 않는다.
- 대신 `WARNING` 결과와 `missing_data_source_id` issue를 반환한다.
- DB ID가 설정된 경우에는 아래를 검증한다.
  - property 존재 여부
  - property type
  - select option 권장 세트

validator entrypoint support:

- `scripts/dev/validate_notion_schema.py --daily-ops-status`
- `scripts/dev/validate_notion_schema.py --all`

## Why exporter is deferred

이번 단계는 mapping/schema recognition까지만 다룬다.

- 아직 `core/notion_exporters.py`에 `daily_ops_status` export target을 추가하지 않는다.
- 아직 `paper.py status` payload를 Notion property payload로 변환하지 않는다.
- actual export는 후속 MFU에서 `dry-run -> actual export` 순으로 연다.

## Manual Notion setup dependency

사용자가 실제 Notion에 아래를 수동 준비해야 한다.

- `Daily Ops Status` DB 생성
- `Account ID` select option에 최소 `paper_default`
- `Workflow Status` select option 전체 생성
- `Review Progress Status` select option 전체 생성
- `Sync Status` select option 전체 생성

이 단계 전까지는 validator warning+skip이 정상 동작이다.

## Next MFU recommendation

- `PAPER15-4G`: local `paper.py status` -> `Daily Ops Status` dry-run exporter
- `PAPER15-4H`: `Daily Ops Status` actual export 제한 실행

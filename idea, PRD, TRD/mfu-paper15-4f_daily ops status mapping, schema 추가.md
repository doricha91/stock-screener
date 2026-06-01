BEGIN MFU-PAPER15-4F_DAILY_OPS_STATUS_MAPPING_SCHEMA

# MFU-PAPER15-4F 작업 지시문: Daily Ops Status Mapping / Schema 추가

## 목적

MFU-PAPER15-4F의 목표는 PAPER15-4E에서 설계한 Notion `Daily Ops Status` DB를 Python 설정/mapping/schema 계층에서 인식할 수 있도록 추가하는 것이다.

이번 단계는 mapping/schema 인식 단계다.  
Notion DB 실제 생성, Notion API write/sync/export, Daily Ops Status exporter 구현, paper 원장 수정은 하지 않는다.

반드시 명시:

```text
이번 PAPER15-4F는 Notion Daily Ops Status DB의 mapping/schema 인식 작업이며, Notion DB 실제 생성, Notion API write/sync/export, exporter 구현, paper 원장 수정은 포함하지 않는다.
```

## 배경

PAPER15-4E에서 `Daily Ops Status` DB가 계좌별·날짜별 운영 관제판으로 설계됐다.

권장 External Key:

```text
daily_ops_status:{account_id}:{status_date}
```

로컬 workflow status 후보:

```text
NO_PLAN
PLAN_READY
COMMITTED
REVIEW_READY
REVIEW_PARTIAL
REVIEW_DONE
UNKNOWN_OR_INCOMPLETE
```

Review Progress Status 후보:

```text
NOT_STARTED
READY
PARTIAL
DONE
UNKNOWN
NOT_APPLICABLE
```

이번 단계에서는 이를 config/example/schema validator/test에 반영한다.

## 구현 범위

### 1. notion_property_mapping.example.json 수정

대상:

```text
config/notion_property_mapping.example.json
```

새 section 추가:

```json
"daily_ops_status": {
  "name": "Name",
  "external_key": "External Key",
  "account_id": "Account ID",
  "status_date": "Status Date",
  "workflow_status": "Workflow Status",
  "review_progress_status": "Review Progress Status",
  "review_completion_ratio": "Review Completion Ratio",
  "next_recommended_command": "Next Recommended Command",
  "blocking_reason": "Blocking Reason",
  "plan_exists": "Plan Exists",
  "current_state_exists": "Current State Exists",
  "account_snapshot_exists": "Account Snapshot Exists",
  "position_snapshot_exists": "Position Snapshot Exists",
  "execution_log_rows_for_date": "Execution Log Rows For Date",
  "reports_ready": "Reports Ready",
  "daily_review_summary_exists": "Daily Review Summary Exists",
  "performance_summary_exists": "Performance Summary Exists",
  "review_template_exists": "Review Template Exists",
  "review_template_row_count": "Review Template Row Count",
  "review_validation_result": "Review Validation Result",
  "manual_review_log_exists": "Manual Review Log Exists",
  "manual_review_log_row_count": "Manual Review Log Row Count",
  "review_answered_row_count": "Review Answered Row Count",
  "review_pending_row_count": "Review Pending Row Count",
  "last_status_checked_at": "Last Status Checked At",
  "sync_status": "Sync Status",
  "synced_at": "Synced At",
  "schema_version": "Schema Version",
  "source_root": "Source Root"
}
```

주의:

```text
기존 DB section 이름과 property 이름은 변경하지 않는다.
기존 mapping key를 삭제하지 않는다.
daily_ops_status만 추가한다.
```

### 2. notion_settings.example.json 확인/수정

대상 후보:

```text
config/notion_settings.example.json
```

Daily Ops Status DB ID placeholder가 필요한 구조라면 추가한다.

예:

```json
"daily_ops_status_database_id": ""
```

또는 기존 구조가 database map 형태라면 그 구조에 맞춘다.

주의:

```text
실제 Notion DB ID나 secret을 넣지 않는다.
사용자 로컬 notion_settings.json 생성/수정 금지.
```

### 3. schema validator 보강

대상 후보:

```text
core/notion_schema_validator.py
scripts/dev/validate_notion_schema.py
```

목표:

```text
daily_ops_status mapping section을 schema validator가 인식한다.
Daily Ops Status DB가 설정되지 않은 경우 전체 validator가 불필요하게 FAIL하지 않도록 한다.
설정된 경우 필수 property 누락을 report할 수 있게 한다.
```

권장 severity:

```text
- daily_ops_status DB ID가 설정되지 않은 경우: SKIPPED 또는 WARNING
- DB ID가 설정됐는데 필수 property가 없으면: FAIL 또는 명확한 issue
- Select option 누락은 초기에는 WARNING
```

필수 select option 후보:

```text
Workflow Status:
NO_PLAN
PLAN_READY
COMMITTED
REVIEW_READY
REVIEW_PARTIAL
REVIEW_DONE
UNKNOWN_OR_INCOMPLETE

Review Progress Status:
NOT_STARTED
READY
PARTIAL
DONE
UNKNOWN
NOT_APPLICABLE

Sync Status:
DRY_RUN
SYNCED
FAILED
SKIPPED
```

### 4. 테스트 추가/수정

테스트 파일 후보:

```text
tests/test_notion_mapping.py
tests/test_notion_schema_validator.py
tests/test_notion_daily_ops_status_mapping.py
```

필수 테스트:

```text
1. notion_property_mapping.example.json에 daily_ops_status section이 존재한다.
2. daily_ops_status.external_key == External Key
3. daily_ops_status.account_id == Account ID
4. daily_ops_status.workflow_status == Workflow Status
5. daily_ops_status.review_progress_status == Review Progress Status
6. 필수 property mapping key가 모두 존재한다.
7. 기존 mapping section은 깨지지 않는다.
8. schema validator가 daily_ops_status를 인식한다.
9. daily_ops_status DB ID가 없으면 validator가 SKIPPED/WARNING 처리한다.
10. Workflow Status / Review Progress Status / Sync Status option 후보가 문서 또는 validator policy에 반영된다.
```

### 5. 문서 추가

문서 추가:

```text
docs/TRD/mfu_paper15_4f_daily_ops_status_mapping_schema.md
```

문서 포함:

```text
1. Purpose
2. Scope / Non-scope
3. Added mapping section
4. Property mapping table
5. Select option policy
6. Schema validator behavior
7. Why exporter is deferred
8. Manual Notion setup dependency
9. Next MFU recommendation
```

## 금지 사항

```text
Notion DB 실제 생성 금지
Notion API write/sync/export 금지
Daily Ops Status exporter 구현 금지
core/notion_exporters.py의 실제 export 동작 변경 금지
core/paper_status.py 수정 금지
paper 원장 CSV 수정 금지
outputs 하위 파일 수정 금지
실제 notion_settings.json 생성/수정 금지
broker/API 실행 금지
cloud runner 작업 금지
git add . 금지
git add -A 금지
```

## 허용 사항

```text
config/notion_property_mapping.example.json 수정
config/notion_settings.example.json 예시 수정
schema validator가 daily_ops_status를 인식하도록 보강
mapping/schema 테스트 추가
문서 추가
read-only 파일 확인
pytest 실행
```

## 검증 명령

Windows CMD 기준:

```cmd
python -m pytest tests\test_notion_mapping.py
python -m pytest tests\test_notion_schema_validator.py
python -m pytest tests\test_notion_daily_ops_status_mapping.py
git diff -- config\notion_property_mapping.example.json config\notion_settings.example.json
git diff -- core\notion_schema_validator.py scripts\dev\validate_notion_schema.py
git diff -- docs\TRD\mfu_paper15_4f_daily_ops_status_mapping_schema.md
git status --short
```

테스트 파일명이 다르면 실제 추가/수정한 테스트 파일 기준으로 실행한다.

## 성공 기준

```text
notion_property_mapping.example.json에 daily_ops_status section이 추가된다.
Daily Ops Status 필수 property mapping이 모두 정의된다.
Workflow Status / Review Progress Status / Sync Status option 정책이 정리된다.
schema validator가 daily_ops_status를 인식한다.
Daily Ops Status DB ID가 아직 없어도 validator가 전체 실패하지 않는다.
기존 Notion DB mapping은 깨지지 않는다.
Daily Ops Status exporter는 구현하지 않는다.
Notion actual write/sync/export는 실행하지 않는다.
outputs와 paper 원장은 수정하지 않는다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 생성/수정한 파일
3. daily_ops_status mapping 추가 내용
4. notion_settings.example.json 변경 여부
5. 필수 property 목록
6. select option 정책
7. schema validator 변경 내용
8. 테스트 결과
9. 기존 Notion DB mapping 영향 여부
10. exporter 구현 여부
11. Notion actual write/sync/export 실행 여부
12. outputs 변경 여부
13. 남은 리스크
14. 다음 MFU 제안
```

반드시 명시:

```text
이번 PAPER15-4F는 Notion Daily Ops Status DB의 mapping/schema 인식 작업이며, Notion DB 실제 생성, Notion API write/sync/export, exporter 구현, paper 원장 수정은 포함하지 않는다.
```

END MFU-PAPER15-4F_DAILY_OPS_STATUS_MAPPING_SCHEMA
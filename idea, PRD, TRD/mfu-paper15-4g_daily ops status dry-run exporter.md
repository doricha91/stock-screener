BEGIN MFU-PAPER15-4G_DAILY_OPS_STATUS_DRY_RUN_EXPORTER

# MFU-PAPER15-4G 작업 지시문: Daily Ops Status Dry-run Exporter

## 목적

MFU-PAPER15-4G의 목표는 로컬 `paper.py status` 결과를 Notion `Daily Ops Status` DB payload로 변환하는 dry-run exporter를 구현하는 것이다.

이번 단계는 dry-run payload 생성과 검증에 한정한다.  
Notion actual write/sync/export, Notion row 생성/수정, paper 원장 수정은 하지 않는다.

반드시 명시:

```text
이번 PAPER15-4G는 local paper.py status 결과를 Notion Daily Ops Status DB payload로 변환하는 dry-run exporter 구현 작업이며, Notion actual write/sync/export, Notion row 생성/수정, paper 원장 수정은 포함하지 않는다.
```

## 배경

PAPER15-4D에서 로컬 `workflow_status`에 아래 상태가 추가됐다.

```text
REVIEW_PARTIAL
REVIEW_DONE
```

PAPER15-4E에서 Notion `Daily Ops Status` DB가 설계됐다.

PAPER15-4F에서 아래가 완료됐다.

```text
- config/notion_property_mapping.example.json에 daily_ops_status section 추가
- config/notion_settings.example.json에 data_sources.daily_ops_status placeholder 추가
- schema validator가 daily_ops_status를 인식
- daily_ops_status DB ID가 없으면 WARNING/SKIPPED 처리
```

이번 단계에서는 로컬 status를 Notion payload로 변환하되, 실제 Notion write는 하지 않는다.

## 구현 범위

### 1. Dry-run export CLI 추가

대상 후보:

```text
scripts/export_paper_to_notion.py
```

아래 옵션을 추가한다.

```cmd
python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --dry-run --json
python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --date 20260520 --dry-run --json
```

정책:

```text
--account-id 생략 시 paper_default
account_id는 validate_account_id 사용
--date 생략 시 run_paper_status의 target date resolve 정책 사용
--dry-run 필수
--dry-run 없이는 이번 단계에서 FAIL
```

### 2. Status payload builder 추가

파일 후보:

```text
core/notion_daily_ops_status_exporter.py
```

또는 기존 구조에 맞춰:

```text
core/notion_exporters.py
```

권장 함수:

```python
build_daily_ops_status_external_key(account_id: str, status_date: str) -> str
build_daily_ops_status_payload(status: dict, account_id: str, mapping: dict, *, dry_run: bool) -> dict
```

External Key:

```text
daily_ops_status:{account_id}:{status_date}
```

예:

```text
daily_ops_status:paper_sandbox:2026-05-20
```

### 3. Source status

`run_paper_status()` 결과를 source로 사용한다.

대상 파일:

```text
core/paper_status.py
scripts/paper.py
```

주의:

```text
core/paper_status.py의 status semantics는 이번 단계에서 변경하지 않는다.
필요하면 read-only 호출만 한다.
```

### 4. Notion property payload 매핑

`daily_ops_status` mapping을 사용해 아래 필드를 payload로 만든다.

필수 mapping:

```text
Name
External Key
Account ID
Status Date
Workflow Status
Review Progress Status
Review Completion Ratio
Next Recommended Command
Blocking Reason
Plan Exists
Current State Exists
Account Snapshot Exists
Position Snapshot Exists
Execution Log Rows For Date
Reports Ready
Daily Review Summary Exists
Performance Summary Exists
Review Template Exists
Review Template Row Count
Review Validation Result
Manual Review Log Exists
Manual Review Log Row Count
Review Answered Row Count
Review Pending Row Count
Last Status Checked At
Sync Status
Synced At
Schema Version
Source Root
```

정책:

```text
Name = {account_id} {status_date} Daily Ops Status
Sync Status = DRY_RUN
Synced At = dry-run 생성 시각 또는 null, 현재 코드 관례에 맞춤
Last Status Checked At = dry-run 생성 시각
Schema Version = daily_ops_status.v1
Source Root = status["paths"]["paper_root"]
Blocking Reason = 이번 단계에서는 간단 파생 또는 빈 문자열 허용
```

Blocking Reason 기본 파생 후보:

```text
NO_PLAN -> daily plan missing
PLAN_READY -> snapshot/current state missing
COMMITTED -> reports/review not ready
REVIEW_READY -> review append pending
REVIEW_PARTIAL -> pending review rows remain
UNKNOWN_OR_INCOMPLETE -> inspect status details
REVIEW_DONE -> empty
```

### 5. Dry-run summary 출력

`--json` 출력에는 아래를 포함한다.

```text
target = daily_ops_status
dry_run = true
account_id
status_date
external_key
workflow_status
review_progress_status
notion_properties
source_status
would_write = false
```

Notion client의 create/update/upsert는 호출하지 않는다.

### 6. 실제 Notion DB ID 처리

Notion DB가 이미 생성되어 있더라도 이번 단계에서는 write하지 않는다.

정책:

```text
daily_ops_status DB ID가 설정되어 있으면 dry-run summary에 data_source_configured=true 표시
DB ID가 없으면 data_source_configured=false 또는 warning 표시
어느 경우에도 actual write는 하지 않는다
```

선택적으로 read-only schema validation은 허용한다.

```cmd
python scripts\dev\validate_notion_schema.py --daily-ops-status
```

단, 이 명령은 Notion write가 아니라 schema read/validation이어야 한다.

## 테스트

테스트 파일 후보:

```text
tests/test_notion_daily_ops_status_exporter.py
tests/test_export_paper_to_notion_daily_ops_status_cli.py
```

필수 테스트:

```text
1. daily_ops_status external key가 account-aware로 생성된다.
2. paper_sandbox REVIEW_PARTIAL fixture가 Notion payload로 변환된다.
3. Workflow Status select 값이 REVIEW_PARTIAL로 들어간다.
4. Review Progress Status select 값이 PARTIAL로 들어간다.
5. Review Completion Ratio number가 들어간다.
6. Account ID select가 account_id로 들어간다.
7. Sync Status는 DRY_RUN으로 들어간다.
8. --dry-run 없이 --daily-ops-status 실행 시 FAIL.
9. Notion client create/update/upsert가 호출되지 않는다.
10. account_id 생략 시 paper_default로 동작한다.
11. invalid account_id는 실패한다.
12. 기존 exporter 대상은 깨지지 않는다.
```

## 산출물

예상 수정/추가 파일:

```text
core/notion_daily_ops_status_exporter.py
scripts/export_paper_to_notion.py
tests/test_notion_daily_ops_status_exporter.py
tests/test_export_paper_to_notion_daily_ops_status_cli.py
```

필요 시 수정:

```text
core/notion_exporters.py
tests/test_notion_mapping.py
```

문서 추가:

```text
docs/TRD/mfu_paper15_4g_daily_ops_status_dry_run_exporter.md
```

## 금지 사항

```text
Notion actual write/sync/export 금지
Notion page create/update/upsert 호출 금지
Daily Ops Status actual export 금지
paper 원장 CSV 수정 금지
outputs 하위 파일 수정 금지
core/paper_status.py semantics 변경 금지
Notion DB schema 변경 금지
broker/API 실행 금지
cloud runner 작업 금지
paper_default migration 금지
git add . 금지
git add -A 금지
```

## 허용 사항

```text
Daily Ops Status dry-run payload builder 구현
export_paper_to_notion.py에 --daily-ops-status dry-run CLI 추가
read-only paper status 호출
read-only schema validation
fake/mock Notion client 테스트
pytest 실행
TRD 문서 추가
```

## 검증 명령

Windows CMD 기준:

```cmd
python -m pytest tests\test_notion_daily_ops_status_exporter.py
python -m pytest tests\test_export_paper_to_notion_daily_ops_status_cli.py
python -m pytest tests\test_notion_mapping.py tests\test_notion_schema_validator.py
python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --dry-run --json
git diff -- core\notion_daily_ops_status_exporter.py scripts\export_paper_to_notion.py
git diff -- docs\TRD\mfu_paper15_4g_daily_ops_status_dry_run_exporter.md
git status --short
```

선택 read-only 검증:

```cmd
python scripts\dev\validate_notion_schema.py --daily-ops-status
```

실제 Notion write/export 명령은 실행하지 않는다.

## 성공 기준

```text
paper.py status 결과를 Daily Ops Status Notion payload로 변환할 수 있다.
External Key가 daily_ops_status:{account_id}:{status_date} 형식으로 생성된다.
paper_sandbox REVIEW_PARTIAL 상태가 dry-run payload에 반영된다.
Account ID, Workflow Status, Review Progress Status, Review Completion Ratio가 payload에 포함된다.
Sync Status는 DRY_RUN으로 설정된다.
--daily-ops-status는 이번 단계에서 --dry-run 필수다.
dry-run 실행 시 Notion create/update/upsert가 호출되지 않는다.
Notion actual write/sync/export는 실행되지 않는다.
outputs와 paper 원장은 수정되지 않는다.
기존 exporter 대상은 깨지지 않는다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 생성/수정한 파일
3. 추가한 CLI 옵션
4. Daily Ops Status external key 형식
5. status → Notion payload 매핑 내용
6. Blocking Reason 파생 정책
7. dry-run JSON 출력 예시 요약
8. paper_sandbox dry-run 결과
9. 테스트 결과
10. Notion actual write/sync/export 실행 여부
11. outputs 변경 여부
12. 기존 exporter 영향 여부
13. 남은 리스크
14. 다음 MFU 제안
```

반드시 명시:

```text
이번 PAPER15-4G는 local paper.py status 결과를 Notion Daily Ops Status DB payload로 변환하는 dry-run exporter 구현 작업이며, Notion actual write/sync/export, Notion row 생성/수정, paper 원장 수정은 포함하지 않는다.
```

END MFU-PAPER15-4G_DAILY_OPS_STATUS_DRY_RUN_EXPORTER
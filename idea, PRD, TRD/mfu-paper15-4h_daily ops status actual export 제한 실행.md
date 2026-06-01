BEGIN MFU-PAPER15-4H_DAILY_OPS_STATUS_ACTUAL_EXPORT_LIMITED

# MFU-PAPER15-4H 작업 지시문: Daily Ops Status Actual Export 제한 실행

## 목적

MFU-PAPER15-4H의 목표는 로컬 `paper.py status` 결과를 Notion `Daily Ops Status` DB에 제한적으로 actual export/upsert하는 것이다.

이번 단계는 `paper_sandbox` 1개 계좌, 1개 status date에 대한 제한 실행이다.  
Notion row bulk export, 기존 DB migration, paper 원장 수정, broker/API, cloud runner는 포함하지 않는다.

반드시 명시:

```text
이번 PAPER15-4H는 Daily Ops Status DB에 대한 제한적 actual export 실행 작업이며, bulk export, 기존 Notion row migration, paper 원장 수정, broker/API, cloud runner는 포함하지 않는다.
```

## 전제 조건

사용자가 이미 완료했다고 가정한다.

```text
1. Notion에 Daily Ops Status DB 생성 완료
2. 로컬 notion_settings.json 또는 환경 변수에 daily_ops_status DB ID 연결 완료
3. schema validator --daily-ops-status 통과
4. PAPER15-4G dry-run exporter 구현 완료
5. paper_sandbox dry-run payload 생성 성공
```

## 대상 계좌 / 날짜

고정 대상:

```text
account_id = paper_sandbox
status_date = run_paper_status가 resolve하는 날짜
현재 예상: 2026-05-20
```

External Key:

```text
daily_ops_status:paper_sandbox:2026-05-20
```

## 핵심 안전 정책

```text
1. actual export 대상은 Daily Ops Status DB만 허용한다.
2. account_id는 paper_sandbox만 허용한다.
3. paper_default actual export 금지.
4. bulk export 금지.
5. Notion 기존 상세 DB actual export 금지.
6. paper 원장, outputs 파일 수정 금지.
7. Notion upsert는 External Key 기준 1 row만 수행한다.
8. 실행 전 dry-run 결과와 actual payload가 일치해야 한다.
```

## 구현 범위

### 1. export_paper_to_notion.py actual branch 추가

대상:

```text
scripts/export_paper_to_notion.py
core/notion_daily_ops_status_exporter.py
```

현재 4G에서는 `--daily-ops-status`가 `--dry-run` 필수다.  
이번 단계에서는 아래 조건에서만 actual export를 허용한다.

```cmd
python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --confirm-actual --json
```

권장 정책:

```text
--daily-ops-status actual export에는 --confirm-actual 필수
--account-id paper_sandbox 외에는 FAIL
--all, bulk, multi-account 옵션 금지
Notion data source가 설정되어 있지 않으면 FAIL
schema validation을 통과하지 않으면 FAIL
```

`--confirm-actual` 옵션이 없으면 actual export를 차단한다.

### 2. actual upsert 구현

Daily Ops Status DB에 대해 External Key 기준 upsert를 수행한다.

정책:

```text
1. External Key로 기존 row lookup
2. 있으면 update
3. 없으면 create
4. Sync Status는 SYNCED
5. Synced At은 실제 export 시각
6. Schema Version은 daily_ops_status.v1
```

주의:

```text
Dry-run에서는 Sync Status=DRY_RUN 유지
Actual export에서는 Sync Status=SYNCED
```

### 3. actual export result 출력

JSON 출력에는 아래를 포함한다.

```text
target
account_id
status_date
external_key
dry_run=false
actual_export=true
action=create 또는 update
page_id
workflow_status
review_progress_status
sync_status=SYNCED
synced_at
data_source_configured=true
```

Notion API 실패 시:

```text
action=failed
sync_status=FAILED
error message 포함
```

### 4. Notion write 범위 제한

허용:

```text
Daily Ops Status DB page create/update 1건
```

금지:

```text
Daily Plans export
Account Snapshots export
Weekly Reports export
Benchmark Reports export
Daily Review Summaries export
Manual Execution status sync
Manual Review status sync
기존 Notion row migration
```

### 5. 사전/사후 검증 명령

사전:

```cmd
python scripts\dev\validate_notion_schema.py --daily-ops-status
python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --dry-run --json
```

actual:

```cmd
python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --confirm-actual --json
```

사후:

```cmd
python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --dry-run --json
git status --short
```

가능하면 Notion에서 직접 확인할 항목:

```text
Daily Ops Status DB에 paper_sandbox row 1건 생성/갱신
Account ID = paper_sandbox
Workflow Status = REVIEW_PARTIAL
Review Progress Status = PARTIAL
Review Completion Ratio = 0.25
External Key = daily_ops_status:paper_sandbox:2026-05-20
Sync Status = SYNCED
```

## 테스트

테스트 파일 후보:

```text
tests/test_notion_daily_ops_status_exporter.py
tests/test_export_paper_to_notion_daily_ops_status_cli.py
```

필수 테스트:

```text
1. --daily-ops-status actual export는 --confirm-actual 없으면 실패
2. --confirm-actual이 있어도 account_id가 paper_sandbox가 아니면 실패
3. data source 미설정이면 actual export 실패
4. dry-run은 Notion client를 호출하지 않음
5. actual export는 fake client에서 External Key lookup 후 create 가능
6. actual export는 fake client에서 기존 row update 가능
7. actual export payload의 Sync Status는 SYNCED
8. dry-run payload의 Sync Status는 DRY_RUN
9. 기존 exporter 대상은 영향 없음
```

## 산출물

예상 수정/추가 파일:

```text
core/notion_daily_ops_status_exporter.py
scripts/export_paper_to_notion.py
tests/test_notion_daily_ops_status_exporter.py
tests/test_export_paper_to_notion_daily_ops_status_cli.py
docs/TRD/mfu_paper15_4h_daily_ops_status_actual_export_limited.md
```

## 금지 사항

```text
paper_default actual export 금지
multi-account bulk export 금지
기존 Notion DB actual export 금지
Manual Execution/Review status sync 실행 금지
Notion row migration 금지
paper 원장 CSV 수정 금지
outputs 하위 파일 수정 금지
broker/API 실행 금지
cloud runner 작업 금지
paper_default migration 금지
git add . 금지
git add -A 금지
```

## 허용 사항

```text
Daily Ops Status DB paper_sandbox row 1건 actual create/update
Daily Ops Status schema validation
Daily Ops Status dry-run
fake/mock Notion client 테스트
TRD 문서 추가
pytest 실행
```

## 검증 명령

Windows CMD 기준:

```cmd
python -m pytest tests\test_notion_daily_ops_status_exporter.py
python -m pytest tests\test_export_paper_to_notion_daily_ops_status_cli.py
python -m pytest tests\test_notion_mapping.py tests\test_notion_schema_validator.py
python scripts\dev\validate_notion_schema.py --daily-ops-status
python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --dry-run --json
python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --confirm-actual --json
git diff -- core\notion_daily_ops_status_exporter.py scripts\export_paper_to_notion.py
git diff -- docs\TRD\mfu_paper15_4h_daily_ops_status_actual_export_limited.md
git status --short
```

## 성공 기준

```text
Daily Ops Status actual export가 paper_sandbox 1건에 한해 실행된다.
External Key 기준 create 또는 update가 수행된다.
Notion row에 Account ID, Status Date, Workflow Status, Review Progress Status가 반영된다.
paper_sandbox 상태가 REVIEW_PARTIAL / PARTIAL / 0.25로 반영된다.
Sync Status는 actual export에서 SYNCED로 기록된다.
--confirm-actual 없이는 actual export가 차단된다.
paper_default actual export는 차단된다.
기존 Notion DB export/sync는 실행되지 않는다.
paper 원장과 outputs는 수정되지 않는다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 생성/수정한 파일
3. 추가한 actual export guard
4. 실행한 사전 검증 명령
5. dry-run 결과 요약
6. actual export 실행 결과
7. action=create/update 여부
8. Notion page_id
9. export된 핵심 필드
10. paper_default 차단 여부
11. 기존 Notion DB 영향 여부
12. outputs 변경 여부
13. 테스트 결과
14. 남은 리스크
15. 다음 MFU 제안
```

반드시 명시:

```text
이번 PAPER15-4H는 Daily Ops Status DB에 대한 제한적 actual export 실행 작업이며, bulk export, 기존 Notion row migration, paper 원장 수정, broker/API, cloud runner는 포함하지 않는다.
```

END MFU-PAPER15-4H_DAILY_OPS_STATUS_ACTUAL_EXPORT_LIMITED

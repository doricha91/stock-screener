# MFU-PAPER14-6 작업 지시문: Daily Review Summary Notion read-only export

## 목적

Manual Executions commit 이후 하루 운영 결과를 요약한 Daily Review Summary를 Notion에 read-only export한다.

이번 작업은 Daily Review Summary 표시/검토 계층 추가다.

반드시 명시:

```text
이번 PAPER14-6은 Daily Review Summary Notion read-only export 작업이며, Manual Execution import/commit, Notion status back-write, broker/API 연동은 수행하지 않는다.
```

---

## 기준 커밋

기준 커밋:

```text
ffd2350f5933376f4bc2b9fec26901d76f0b797d
```

최근 로그에 아래 커밋들이 있어야 한다.

```text
b921af3 PAPER14-5D: commit Manual Executions preview to paper ledger
a6931fd PAPER14-5D: refresh current state after manual execution commit
7ebf999 PAPER14-5E: sync Manual Execution status back to Notion
```

작업 전 확인:

```cmd
cd /d D:\python\StockScreener
git rev-parse HEAD
git log --oneline -12
git status --short
```

기준 SHA 이후 상태가 아니면 중단하고 보고한다.

---

## 배경

현재 완료된 흐름:

```text
Daily Plan 생성
→ Daily Plan Notion export
→ Manual Executions에 실제 체결 입력
→ Python read-only import
→ validation preview
→ preview 기반 ledger commit
→ execution/account/position/current_state 갱신
→ Notion status back-write
```

이번 작업은 위 흐름의 결과를 하루 단위로 요약한다.

역할:

```text
Daily Plan = 오늘 할 일
Manual Executions = 실제 체결 입력
Daily Review Summary = 오늘 실제 운영 결과 요약
```

원칙:

```text
CSV/JSON/Markdown/SQLite = source of truth
Notion = presentation/review layer
```

---

## Notion 대상

새 data source key:

```text
daily_review_summaries
```

환경변수 override:

```env
NOTION_DAILY_REVIEW_SUMMARIES_DATA_SOURCE_ID=...
```

config fallback:

```json
{
  "data_sources": {
    "daily_review_summaries": ""
  }
}
```

---

## 구현 파일

수정/추가 후보:

```text
core/notion_exporters.py
core/notion_schema_validator.py
core/daily_review_summary_exporter.py
scripts/export_paper_to_notion.py
config/notion_property_mapping.example.json
config/notion_settings.example.json
tests/test_notion_exporters.py
tests/test_notion_schema_validator.py
tests/test_daily_review_summary_exporter.py
docs/TRD/mfu_paper14_6_daily_review_summary_notion_export.md
```

불필요한 파일 증가는 피한다. 기존 `notion_exporters.py` 안에서 작게 처리 가능하면 우선 기존 구조를 따른다.

---

## Source artifact 정책

Daily Review Summary는 Notion을 다시 읽지 않는다.

우선 source 후보:

```text
outputs/paper_test/reports/manual_execution_import_commit_YYYYMMDD.json
outputs/paper_test/reports/manual_execution_import_preview_YYYYMMDD.json
outputs/paper_test/paper_execution_log.csv
outputs/paper_test/paper_account_snapshot.csv
outputs/paper_test/paper_position_snapshot.csv
outputs/paper_test/paper_current_state_YYYYMMDD.json
```

우선순위:

```text
1. manual_execution_import_commit_YYYYMMDD.json
2. paper_execution_log.csv에서 source=notion_manual_execution, date=YYYY-MM-DD인 row
3. account/position/current_state snapshot으로 결과 상태 보강
```

commit report가 없으면 export를 실패시키지 말고 `availability_status=NO_COMMIT_REPORT` 또는 WARNING 성격으로 보고한다.

---

## Notion property mapping

`config/notion_property_mapping.example.json`에 추가한다.

```json
{
  "daily_review_summaries": {
    "name": "Name",
    "external_key": "External Key",
    "review_date": "Review Date",
    "review_status": "Review Status",
    "availability_status": "Availability Status",
    "committed_trade_count": "Committed Trade Count",
    "warning_count": "Warning Count",
    "fail_count": "Fail Count",
    "cash_start": "Cash Start",
    "cash_end": "Cash End",
    "cash_impact": "Cash Impact",
    "position_impact_summary": "Position Impact Summary",
    "commit_report_path": "Commit Report Path",
    "preview_report_path": "Preview Report Path",
    "latest_snapshot_date": "Latest Snapshot Date",
    "schema_version": "Schema Version",
    "synced_at": "Synced At",
    "sync_status": "Sync Status"
  }
}
```

권장 타입:

```text
Name = Title
External Key = Rich text
Review Date = Date
Review Status = Select
Availability Status = Select
Committed Trade Count = Number
Warning Count = Number
Fail Count = Number
Cash Start = Number, money display
Cash End = Number, money display
Cash Impact = Number, money display
Position Impact Summary = Rich text
Commit Report Path = Rich text
Preview Report Path = Rich text
Latest Snapshot Date = Date
Schema Version = Rich text
Synced At = Rich text
Sync Status = Select
```

---

## Select options

권장 후보:

```text
Review Status:
PASS
PASS_WITH_WARNINGS
FAIL
NO_ACTIVITY

Availability Status:
AVAILABLE
NO_COMMIT_REPORT
NO_MANUAL_EXECUTIONS
PARTIAL
UNKNOWN

Sync Status:
SYNCED
```

select option 누락은 WARNING, 속성 누락/타입 불일치는 FAIL로 처리한다.

---

## External Key 정책

```text
daily_review_summary:{review_date}
```

예:

```text
daily_review_summary:2026-05-25
```

동일 날짜 export 재실행 시 새 row를 만들지 않고 update되어야 한다.

---

## Page body 요구사항

Daily Review Summary page body는 간결하게 작성한다.

구성:

```text
## 오늘의 리뷰 요약

- Review Date
- Review Status
- Committed Trades
- Warnings
- Cash Start / End / Impact

## 체결 요약

- Symbol / Side / Quantity / Actual Price / Trade ID

## 포지션 변화

- Symbol별 수량 변화

## 경고 / 특이사항

- validation warnings
- commit sidecar의 warning 요약

## 원천 파일

- Commit Report Path
- Preview Report Path
- Snapshot / Current State 관련 path
```

Notion table block은 필수 아님.  
초기에는 bullet/plain text로 안정적으로 구현한다.

---

## CLI 요구사항

`scripts/export_paper_to_notion.py`에 옵션 추가:

```cmd
python scripts\export_paper_to_notion.py --daily-review-summary --date 2026-05-25 --dry-run --json
python scripts\export_paper_to_notion.py --daily-review-summary --date 2026-05-25 --json
```

`--all`에 포함할지는 이번 작업에서 보류해도 된다.  
포함한다면 결과 summary에서 target별 성공/실패가 분리되어야 한다.

---

## Schema validation

`validate_notion_schema.py`에 추가:

```cmd
python scripts\dev\validate_notion_schema.py --daily-review-summary
python scripts\dev\validate_notion_schema.py --all --json
```

---

## Export 정책

```text
--dry-run에서는 Notion write 금지
actual export는 사용자가 명시적으로 허용한 경우에만 실행
upsert 기준은 External Key
0개 발견 → created
1개 발견 → updated
2개 이상 발견 → error
```

Daily Review Summary는 read-only export다.  
Manual Executions, paper ledger, Notion Manual Executions row를 수정하지 않는다.

---

## 테스트 요구사항

추가/수정 테스트:

```text
tests/test_daily_review_summary_exporter.py
tests/test_notion_exporters.py
tests/test_notion_schema_validator.py
```

검증할 것:

```text
1. commit report에서 committed trade count를 계산한다.
2. warning count를 계산한다.
3. cash_start / cash_end / cash_impact를 반영한다.
4. position impact summary를 생성한다.
5. external key가 daily_review_summary:{date}로 생성된다.
6. dry-run은 Notion write를 하지 않는다.
7. upsert payload property type이 mapping과 일치한다.
8. commit report가 없을 때 availability_status가 적절히 설정된다.
9. Manual Execution commit/back-write는 호출하지 않는다.
```

---

## 검증 명령

Windows CMD 기준:

```cmd
cd /d D:\python\StockScreener
set PYTHONPATH=.

python -m py_compile core\daily_review_summary_exporter.py
python -m py_compile core\notion_exporters.py
python -m py_compile core\notion_schema_validator.py
python -m py_compile scripts\export_paper_to_notion.py

python -m pytest tests\test_daily_review_summary_exporter.py tests\test_notion_exporters.py tests\test_notion_schema_validator.py -q
python -m pytest tests\test_paper_manual_execution_commit.py tests\test_notion_manual_execution_importer.py tests\test_notion_manual_execution_status_sync.py -q
```

data source id가 설정되어 있으면:

```cmd
python scripts\dev\validate_notion_schema.py --daily-review-summary
python scripts\export_paper_to_notion.py --daily-review-summary --date 2026-05-25 --dry-run --json
```

actual export는 사용자 허용 시에만:

```cmd
python scripts\export_paper_to_notion.py --daily-review-summary --date 2026-05-25 --json
python scripts\export_paper_to_notion.py --daily-review-summary --date 2026-05-25 --json
```

기대:

```text
1차: created 또는 updated
2차: updated
```

---

## 금지 사항

```text
Manual Execution import/commit 재실행 금지
Notion Manual Executions status back-write 금지
paper_execution_log.csv 수정 금지
paper_account_snapshot.csv 수정 금지
paper_position_snapshot.csv 수정 금지
paper_current_state_YYYYMMDD.json 수정 금지
Daily Plan 원천 수정 금지
broker/API 연동 금지
Notion DB 자동 생성 금지
git add . 금지
git add -A 금지
```

---

## 문서화

추가 문서:

```text
docs/TRD/mfu_paper14_6_daily_review_summary_notion_export.md
```

포함 내용:

```text
목적
source artifact
Notion property mapping
External Key 정책
page body 구성
dry-run / actual export 정책
Manual Executions와의 관계
제외 범위
테스트 결과
남은 리스크
```

---

## 커밋 정책

코드와 문서만 커밋한다.

권장 stage:

```cmd
git add core\daily_review_summary_exporter.py
git add core\notion_exporters.py
git add core\notion_schema_validator.py
git add scripts\export_paper_to_notion.py
git add config\notion_property_mapping.example.json
git add config\notion_settings.example.json
git add tests\test_daily_review_summary_exporter.py
git add tests\test_notion_exporters.py
git add tests\test_notion_schema_validator.py
git add docs\TRD\mfu_paper14_6_daily_review_summary_notion_export.md
git diff --cached --name-only
```

커밋 메시지:

```cmd
git commit -m "PAPER14-6: export Daily Review Summary to Notion"
```

output / CSV / backup 파일은 커밋하지 않는다.

---

## 성공 기준

```text
Daily Review Summary source가 확인된다.
Daily Review Summary Notion payload가 생성된다.
schema validation이 추가된다.
--daily-review-summary --dry-run --json이 성공한다.
actual export를 수행한 경우 created/update와 updated가 확인된다.
Manual Execution commit/back-write는 수행하지 않는다.
paper ledger 파일은 수정하지 않는다.
테스트가 통과한다.
```

---

## 결과 보고 형식

5천자 이내.

```text
1. Summary
2. 기준 커밋 확인 결과
3. 변경 파일
4. 추가된 env/config key
5. source artifact 확인 결과
6. 추가된 mapping/schema
7. 추가된 CLI
8. Daily Review Summary 계산 내용
9. page body 구성
10. dry-run 결과
11. actual export 수행 여부
12. Notion UI 확인 결과
13. paper ledger 수정 여부
14. 테스트 결과
15. 커밋 hash와 message
16. 남은 리스크
17. 다음 MFU 제안
```

반드시 명시:

```text
이번 PAPER14-6은 Daily Review Summary Notion read-only export 작업이며, Manual Execution import/commit, Notion status back-write, broker/API 연동은 수행하지 않았다.
```
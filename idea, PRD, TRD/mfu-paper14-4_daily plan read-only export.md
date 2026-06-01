# MFU-PAPER14-4 작업 지시문: Daily Plan Notion read-only export

## 목적

MFU-PAPER14-4의 목표는 paper 운영 루프에서 생성되는 Daily Plan을 Notion `Daily Plans` data source로 read-only export하는 기능을 추가하는 것이다.

이번 작업은 Python → Notion 단방향 export만 다룬다.

반드시 명시:

```text
이번 PAPER14-4는 Daily Plan read-only Notion export 추가 작업이며, Daily Review Summary, Performance Summary, Manual Review 입력 연동은 포함하지 않는다.
```

---

## 배경

PAPER14-3에서는 아래 3개 Notion export가 완료됐다.

```text
Weekly Reports
Benchmark Reports
Account Snapshots
```

PAPER14-4에서는 다음 단계로 Daily Plan만 추가한다.

Notion은 source of truth가 아니다.

```text
source of truth = CSV / JSON / Markdown / SQLite
Notion = presentation / review layer
```

---

## 구현 전 조사

먼저 Daily Plan의 원천 산출물을 확인한다.

조사 대상:

```text
scripts/paper.py
outputs/paper_test/
outputs/paper_test/reports/
scripts/generate_paper_*
core/
tests/test_paper_cli.py
```

확인할 것:

```text
1. Daily Plan JSON 산출물이 있는지
2. Daily Plan Markdown 산출물이 있는지
3. plan_date 필드가 어디에 있는지
4. regime / confirmed trade / review item / warning count를 어디서 얻는지
5. 기존 CLI에서 prepare / preview / commit 중 어느 단계가 Daily Plan을 생성하는지
```

중요:

```text
Daily Plan 원천 파일을 확정할 수 없으면 구현하지 말고 보고한다.
추측으로 임의 파일 구조를 만들지 않는다.
```

---

## 구현 파일

수정 후보:

```text
core/notion_exporters.py
scripts/export_paper_to_notion.py
core/notion_schema_validator.py
config/notion_property_mapping.example.json
config/notion_settings.example.json
tests/test_notion_exporters.py
tests/test_notion_schema_validator.py
docs/TRD/mfu_paper14_4_daily_plan_notion_export.md
```

필요 시 추가 후보:

```text
core/notion_daily_plan_contract.py
```

단, 불필요한 파일 증가는 피한다.

---

## Notion 대상

새 대상 key:

```text
daily_plans
```

환경변수 override:

```text
NOTION_DAILY_PLANS_DATA_SOURCE_ID
```

설정 example에도 추가한다.

```json
{
  "data_sources": {
    "daily_plans": ""
  }
}
```

기존 data_sources 구조와 databases fallback 정책을 유지한다.

---

## Mapping 요구사항

`config/notion_property_mapping.example.json`의 기존 `daily_plans` mapping을 확인하고 필요한 경우 확장한다.

기본 후보:

```json
{
  "daily_plans": {
    "name": "Name",
    "external_key": "External Key",
    "plan_date": "Plan Date",
    "regime": "Regime",
    "confirmed_trade_count": "Confirmed Trade Count",
    "review_item_count": "Review Item Count",
    "warning_count": "Warning Count",
    "markdown_path": "Markdown Path",
    "json_path": "JSON Path",
    "schema_version": "Schema Version",
    "synced_at": "Synced At",
    "sync_status": "Sync Status"
  }
}
```

Notion 속성 타입 후보:

```text
Name = Title
External Key = Rich text
Plan Date = Date
Regime = Select
Confirmed Trade Count = Number
Review Item Count = Number
Warning Count = Number
Markdown Path = Rich text
JSON Path = Rich text
Schema Version = Rich text
Synced At = Rich text
Sync Status = Select
```

---

## Export 정책

External Key:

```text
daily_plan:{plan_date}
```

예:

```text
daily_plan:2026-05-24
```

정책:

```text
- 0개 발견 → created
- 1개 발견 → updated
- 2개 이상 발견 → error
- --dry-run 지원
- --json 지원
- page body는 간단한 summary만 작성
- page body 고도화는 제외
```

---

## CLI 요구사항

`scripts/export_paper_to_notion.py`에 아래 옵션을 추가한다.

```cmd
python scripts\export_paper_to_notion.py --daily-plan --dry-run --json
python scripts\export_paper_to_notion.py --daily-plan --json
```

`--all`이 이미 있다면 `daily-plan` 포함 여부는 다음 원칙을 따른다.

```text
- 구현 직후에는 --all에 포함하지 않아도 된다.
- 포함한다면 결과 summary에서 target별 성공/실패가 분리되어야 한다.
- 애매하면 --daily-plan 개별 실행만 지원하고 보고한다.
```

---

## Schema validation 요구사항

`validate_notion_schema.py`에 Daily Plans 검증을 추가한다.

CLI 후보:

```cmd
python scripts\dev\validate_notion_schema.py --daily-plan
python scripts\dev\validate_notion_schema.py --all --json
```

검증 기준:

```text
필수 속성 존재 여부
속성 타입 일치 여부
Regime / Sync Status는 Select 타입인지 확인
select option 누락은 WARNING
속성 누락/타입 불일치는 FAIL
```

---

## 문서화 요구사항

새 문서:

```text
docs/TRD/mfu_paper14_4_daily_plan_notion_export.md
```

포함 내용:

```text
1. 목적
2. Daily Plan source artifact
3. Notion data source key
4. property mapping
5. property type
6. select option 후보
7. External Key 정책
8. CLI 사용법
9. dry-run / actual export 정책
10. 제외 범위
11. 테스트 결과
12. 남은 리스크
```

---

## 제외 범위

이번 작업에서 하지 않는다.

```text
Daily Review Summary export
Performance Summary export
Manual Review 입력 연동
Notion DB 자동 생성
Notion schema migration
page body 고도화
paper 원장 CSV 수정
outputs/front_test 수정
DB/PNG/output 파일 수정/삭제
한글 경로 문서 수정/삭제
```

---

## 테스트

추가/수정 테스트:

```text
tests/test_notion_exporters.py
tests/test_notion_schema_validator.py
```

검증할 것:

```text
1. daily_plan External Key가 daily_plan:{plan_date}로 생성된다.
2. Notion property payload 타입이 schema contract와 일치한다.
3. --dry-run은 실제 write를 하지 않는다.
4. missing source artifact는 명확한 error로 처리한다.
5. schema validation에서 Daily Plans 속성 누락/타입 불일치를 FAIL로 잡는다.
6. 기존 weekly/benchmark/account export 테스트가 깨지지 않는다.
```

---

## 검증 명령

Windows CMD 기준:

```cmd
cd /d D:\python\StockScreener
set PYTHONPATH=.

python -m py_compile core\notion_exporters.py
python -m py_compile core\notion_schema_validator.py
python -m py_compile scripts\export_paper_to_notion.py
python -m py_compile scripts\dev\validate_notion_schema.py

python -m pytest tests\test_notion_exporters.py tests\test_notion_schema_validator.py tests\test_notion_settings.py tests\test_notion_mapping.py tests\test_notion_client.py -q

python scripts\export_paper_to_notion.py --daily-plan --dry-run --json
```

Daily Plans data source가 아직 없으면 schema validation actual call은 skip하고 보고한다.  
Daily Plans data source id가 있으면 아래도 실행한다.

```cmd
python scripts\dev\validate_notion_schema.py --daily-plan
```

actual export는 사용자가 명시적으로 허용한 경우에만 실행한다.

```cmd
python scripts\export_paper_to_notion.py --daily-plan --json
```

---

## 금지 사항

```text
git add .
git add -A
git reset --hard
git clean -fd
실제 Notion export/write 임의 실행
Daily Review / Performance / Manual Review 구현
Notion DB 자동 생성
원천 CSV/JSON/Markdown 임의 수정
paper 원장 CSV 수정
outputs/front_test 수정
```

---

## 커밋 정책

코드와 문서를 한 커밋으로 묶어도 된다.

권장 commit message:

```cmd
git commit -m "PAPER14-4: add Daily Plan Notion export"
```

단, Daily Plan source 조사만 하고 구현하지 못한 경우 커밋하지 말고 보고한다.

---

## 성공 기준

```text
Daily Plan source artifact가 확인된다.
Daily Plan Notion export payload가 생성된다.
--daily-plan --dry-run --json이 성공한다.
Daily Plans schema validation이 구현된다.
기존 PAPER14-3 export 기능이 깨지지 않는다.
Daily Review / Performance / Manual Review는 제외된다.
문서가 추가된다.
```

---

## 결과 보고 형식

5천자 이내.

```text
1. Summary
2. 변경 파일
3. Daily Plan source artifact 확인 결과
4. 추가된 mapping
5. 추가된 CLI
6. External Key 정책
7. schema validation 추가 결과
8. dry-run 결과
9. actual export 수행 여부
10. 테스트 결과
11. 실제 Notion write 수행 여부
12. paper 원장 CSV 변경 여부
13. outputs/front_test 변경 여부
14. 제외 범위 준수 여부
15. 커밋 hash와 message
16. 남은 리스크
17. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER14-4는 Daily Plan read-only Notion export 작업이며, Daily Review Summary, Performance Summary, Manual Review 입력 연동은 수행하지 않았다.
```
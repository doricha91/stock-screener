# MFU-PAPER14-5C 작업 지시문: Manual Executions read-only importer preview + validation engine

## 목적

Notion Manual Executions DB에 사용자가 입력한 실제 체결 정보를 Python에서 read-only로 가져와 검증하고, preview report를 생성한다.

이번 작업은 원장 반영 전 단계다.

반드시 명시:

이번 PAPER14-5C는 Notion Manual Executions read-only import + validation preview 작업이며, paper ledger commit, Daily Review Summary export, Notion status back-write는 수행하지 않는다.

---

## 기준 커밋

기준 커밋 / 베이스라인:

```text
ffd2350f5933376f4bc2b9fec26901d76f0b797d
```

추가로 최근 로그에 아래 5B 커밋이 있어야 한다.

```text
2b380c9 PAPER14-5B: document Manual Executions schema and views
```

작업 전 확인:

```cmd
cd /d D:\python\StockScreener
git rev-parse HEAD
git log --oneline -8
git status --short
```

기준 SHA 또는 그 이후 커밋이 아니면 작업을 중단하고 보고한다.

---

## 배경

PAPER14-5A/5B에서 원칙은 확정됐다.

```text
Notion = 입력 대기 / staging layer
Python = 검증 / 정규화 / 원장 반영 주체
CSV / SQLite = 최종 source of truth
```

Manual Executions DB는 사용자가 실제 체결 결과를 입력하는 곳이다.

5B에서 확정한 핵심 필드:

```text
Name
Execution Date
Symbol
Side
Quantity
Actual Price
Status
Plan Date
Commission
Currency
Broker
Note
Linked Daily Plan Key
External Key
Validation Status
Validation Message
Import Status
Imported At
Synced At
```

단, 이번 5C에서는 Notion의 Validation Status / Import Status를 업데이트하지 않는다. 읽기만 한다.

---

## 사용 환경 변수

`.env` 또는 환경변수에 아래 값을 사용한다.

```env
NOTION_MANUAL_EXECUTIONS_DATA_SOURCE_ID=...
```

config fallback도 지원한다면 key는 아래로 한다.

```json
{
  "data_sources": {
    "manual_executions": "..."
  }
}
```

---

## 구현 파일

수정/추가 후보:

```text
core/notion_client.py
core/notion_schema_validator.py
core/notion_manual_execution_importer.py
scripts/import_notion_executions.py
config/notion_property_mapping.example.json
config/notion_settings.example.json
tests/test_notion_client.py
tests/test_notion_schema_validator.py
tests/test_notion_manual_execution_importer.py
docs/TRD/mfu_paper14_5c_manual_execution_import_preview.md
```

필요 시 최소 수정:

```text
scripts/paper.py
tests/test_paper_cli.py
```

단, 초기 구현은 별도 스크립트 `scripts/import_notion_executions.py`를 우선한다.

---

## Notion schema / mapping 요구사항

`manual_executions` mapping을 example에 추가한다.

```json
{
  "manual_executions": {
    "name": "Name",
    "external_key": "External Key",
    "execution_date": "Execution Date",
    "plan_date": "Plan Date",
    "symbol": "Symbol",
    "side": "Side",
    "quantity": "Quantity",
    "actual_price": "Actual Price",
    "commission": "Commission",
    "currency": "Currency",
    "broker": "Broker",
    "status": "Status",
    "linked_daily_plan_key": "Linked Daily Plan Key",
    "note": "Note",
    "validation_status": "Validation Status",
    "validation_message": "Validation Message",
    "import_status": "Import Status",
    "imported_at": "Imported At",
    "synced_at": "Synced At"
  }
}
```

schema validator에 `manual_executions`를 추가한다.

필수 타입:

```text
Name = title
Execution Date = date
Symbol = rich_text
Side = select
Quantity = number
Actual Price = number
Status = select
```

선택/관리 타입:

```text
External Key = rich_text
Plan Date = date
Commission = number
Currency = select
Broker = select 또는 rich_text
Note = rich_text
Linked Daily Plan Key = rich_text
Validation Status = select
Validation Message = rich_text
Import Status = select
Imported At = rich_text
Synced At = rich_text
```

select option 누락은 WARNING, 속성 누락/타입 불일치는 FAIL로 처리한다.

---

## Import 대상 정책

기본 import 대상:

```text
Execution Date = --date
Status = READY
```

정책:

```text
Status가 DRAFT면 preview 대상에서 제외
Status가 READY인 row만 candidate
Status가 IMPORTED인 row는 제외
Status가 REJECTED인 row는 제외
```

CLI:

```cmd
python scripts\import_notion_executions.py --date 2026-05-25 --preview --json
python scripts\import_notion_executions.py --date 2026-05-25 --preview
```

이번 단계에서는 `--commit`을 구현하지 않는다.  
실수 방지를 위해 `--commit`이 들어오면 “not implemented in PAPER14-5C”로 실패시킨다.

---

## Normalization 정책

Notion row를 internal candidate로 변환한다.

필드 매핑:

```text
Execution Date -> execution_date
Plan Date -> plan_date
Symbol -> symbol, uppercase/trim
Side -> side, BUY/SELL
Quantity -> quantity, positive number
Actual Price -> actual_price
Commission -> commission, blank이면 0 + WARNING
Currency -> currency, blank이면 USD + WARNING
Broker -> broker, optional
Note -> note
Linked Daily Plan Key -> linked_daily_plan_key
```

SELL도 Notion 입력은 양수 quantity로 받는다.  
ledger 반영 시 음수 shares 변환은 후속 5D에서 처리한다.

---

## Validation 규칙

FAIL:

```text
Execution Date 없음
Symbol 없음
Side가 BUY/SELL 아님
Quantity <= 0
Actual Price <= 0
동일 batch 내 canonical key 중복
SELL 수량 > 현재 보유수량
BUY 후 예상 현금 < 0
```

WARNING:

```text
Plan Date 없음
Linked Daily Plan Key 없음
Commission 없음 → 0 정규화
Currency 없음 → USD 정규화
Broker 없음
Daily Plan에 없는 Symbol
계획 수량/가격과 실제 체결값 차이 큼
```

Daily Plan 비교가 아직 불명확하면 해당 검증은 WARNING 후보로 문서화하고 구현 범위에서 제외해도 된다. 단, 보고서에 명시한다.

---

## External Key / sequence 정책

canonical key 후보:

```text
manual_execution:{execution_date}:{symbol}:{side}:{sequence}
```

이번 5C에서는 원장 commit을 하지 않으므로, 이 key는 preview 내부 dedupe용으로 생성한다.

정렬 규칙:

```text
Execution Date
Symbol
Side
Notion page_id 또는 created_time
```

동일 날짜/종목/side가 여러 개면 01, 02 순서로 sequence를 부여한다.

후속 5D에서 ledger trade_id와 연결한다.

---

## Preview report 요구사항

출력 파일 후보:

```text
outputs/paper_test/reports/manual_execution_import_preview_YYYYMMDD.md
outputs/paper_test/reports/manual_execution_import_preview_YYYYMMDD.json
```

preview 내용:

```text
candidate row count
PASS / WARNING / FAIL count
normalized rows
validation messages
projected cash impact
projected position impact
commit_allowed: true/false
```

정책:

```text
FAIL이 하나라도 있으면 commit_allowed=false
WARNING만 있으면 commit_allowed=true_with_warnings
모두 PASS면 commit_allowed=true
```

이번 단계에서는 실제 commit을 하지 않는다.

---

## 기존 원장 연결

기존 파일을 읽어 검증에 사용한다.

```text
outputs/paper_test/paper_execution_log.csv
outputs/paper_test/paper_account_snapshot.csv
outputs/paper_test/paper_position_snapshot.csv
```

확인할 것:

```text
현재 보유수량
현재 현금
기존 imported candidate와의 중복 가능성
BUY 후 현금 부족 여부
SELL 후 보유수량 초과 여부
```

원장 파일을 수정하지 않는다.

---

## 금지 사항

```text
paper_execution_log.csv 수정 금지
paper_account_snapshot.csv 수정 금지
paper_position_snapshot.csv 수정 금지
Notion status back-write 금지
Daily Review Summary export 구현 금지
Performance Summary export 구현 금지
Manual Review 입력 연동 구현 금지
broker/API 연동 금지
실제 paper ledger commit 금지
git add . 금지
git add -A 금지
```

---

## 검증 명령

Windows CMD 기준:

```cmd
cd /d D:\python\StockScreener
set PYTHONPATH=.

python -m py_compile core\notion_client.py
python -m py_compile core\notion_schema_validator.py
python -m py_compile core\notion_manual_execution_importer.py
python -m py_compile scripts\import_notion_executions.py

python -m pytest tests\test_notion_client.py tests\test_notion_schema_validator.py tests\test_notion_manual_execution_importer.py -q
python -m pytest tests\test_notion_exporters.py tests\test_notion_settings.py tests\test_notion_mapping.py -q
```

Manual Executions data source id가 설정되어 있으면 read-only schema validation을 실행한다.

```cmd
python scripts\dev\validate_notion_schema.py --manual-executions
```

Notion에 테스트 row가 준비되어 있으면 preview를 실행한다.

```cmd
python scripts\import_notion_executions.py --date 2026-05-25 --preview --json
```

---

## 커밋 정책

권장 commit message:

```cmd
git commit -m "PAPER14-5C: add Manual Executions import preview"
```

커밋 전 확인:

```cmd
git diff --cached --name-only
```

보호 대상, output, DB, CSV 원장이 포함되면 커밋하지 않는다.

---

## 성공 기준

```text
Manual Executions schema validation이 추가된다.
NOTION_MANUAL_EXECUTIONS_DATA_SOURCE_ID를 사용할 수 있다.
Notion Manual Executions row를 read-only로 읽을 수 있다.
Status=READY, Execution Date=--date인 row를 candidate로 만든다.
candidate를 normalized execution input으로 변환한다.
validation 결과를 PASS/WARNING/FAIL로 분류한다.
preview markdown/json을 생성한다.
paper ledger는 수정하지 않는다.
Notion row도 수정하지 않는다.
```

---

## 결과 보고 형식

5천자 이내.

```text
1. Summary
2. 기준 커밋 확인 결과
3. 변경 파일
4. 추가된 env/config key
5. 추가된 CLI
6. schema validation 추가 내용
7. Notion read-only import 동작
8. normalization 정책
9. validation 규칙
10. preview report 생성 결과
11. 테스트 결과
12. 실제 Notion write 여부
13. paper ledger 수정 여부
14. 커밋 hash와 message
15. 남은 리스크
16. 다음 MFU 제안
```

반드시 명시:

이번 PAPER14-5C는 Manual Executions read-only import + validation preview 작업이며, paper ledger commit, Daily Review Summary export, Notion status back-write는 수행하지 않았다.
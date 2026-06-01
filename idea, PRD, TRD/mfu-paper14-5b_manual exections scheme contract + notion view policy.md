# MFU-PAPER14-5B 작업 지시문: Manual Executions schema contract + Notion view policy

## 목적

MFU-PAPER14-5B의 목표는 Notion `Manual Executions` DB의 schema contract와 view 정책을 확정하는 것이다.

이번 작업은 문서화 작업이다.  
Notion row read/import, validation engine, preview report, paper ledger commit은 구현하지 않는다.

반드시 명시:

이번 PAPER14-5B는 Manual Executions schema contract와 Notion view policy 문서화 작업이며, 실제 Notion import, paper ledger commit, Daily Review Summary export는 수행하지 않는다.

---

## 기준 커밋

기준 커밋 / 베이스라인:

```text
ffd2350f5933376f4bc2b9fec26901d76f0b797d
```

작업 전 확인:

```cmd
cd /d D:\python\StockScreener
git rev-parse HEAD
git log --oneline -5
git status --short
```

현재 HEAD가 기준 SHA 또는 그 이후인지 확인한다.  
다른 브랜치이거나 기준 이전 상태면 작업을 중단하고 보고한다.

---

## 배경

PAPER14-5A에서 아래 원칙이 정리됐다.

```text
Notion = 입력 대기 / staging layer
Python = 검증 / 정규화 / 원장 반영 주체
CSV / SQLite = 최종 source of truth
```

Manual Executions는 사용자가 실제 체결 정보를 Notion에 입력하는 DB다.  
하지만 Notion 메인 화면에 너무 많은 정보가 노출되면 운영성이 떨어진다.

따라서 이번 5B에서는 다음을 확정한다.

```text
1. Manual Executions DB 속성명 / 타입 / 필수 여부
2. 메인 입력 view에서 보여줄 최소 필드
3. 검증/관리용 view에서만 보여줄 기술 필드
4. 후속 importer가 읽을 안정적인 schema contract
```

---

## 구현 파일

추가 문서:

```text
docs/TRD/mfu_paper14_5b_manual_executions_schema_contract.md
```

수정 후보:

```text
docs/TRD/mfu_paper14_5a_manual_execution_input_design.md
```

원칙:

```text
- 기본은 새 5B 문서 추가
- 5A 문서는 필요한 경우에만 짧게 참조 링크 추가
- Python 코드 수정 금지
- config/notion_property_mapping.example.json 수정 금지
```

---

## 조사 대상

반드시 확인한다.

```text
docs/TRD/mfu_paper14_5a_manual_execution_input_design.md
core/paper_execution_log.py
core/paper_account_state.py
core/paper_trade_preview.py
core/paper_commit_guard.py
scripts/paper.py
tests/test_paper_cli.py
outputs/paper_test/paper_execution_log.csv
```

확인할 것:

```text
- paper_execution_log.csv 현재 컬럼
- commission / currency / broker 전용 컬럼 존재 여부
- BUY/SELL shares 표현 방식
- commit guard와 account state 검증 흐름
```

---

## Schema contract 요구사항

`Manual Executions` DB 속성을 아래 기준으로 정리한다.

### 필수 입력 필드

```text
Name
Execution Date
Symbol
Side
Quantity
Actual Price
Status
```

권장 타입:

```text
Name = Title
Execution Date = Date
Symbol = Rich text
Side = Select: BUY / SELL
Quantity = Number
Actual Price = Number
Status = Select: DRAFT / READY / IMPORTED / REJECTED
```

### 선택 입력 / 운영 편의 필드

```text
Plan Date
Commission
Currency
Broker
Note
Linked Daily Plan Key
```

권장 타입:

```text
Plan Date = Date
Commission = Number
Currency = Select: USD / KRW
Broker = Select 또는 Rich text
Note = Rich text
Linked Daily Plan Key = Rich text
```

### 검증 / import 관리 필드

```text
External Key
Validation Status
Validation Message
Import Status
Imported At
Synced At
```

권장 타입:

```text
External Key = Rich text
Validation Status = Select: NOT_CHECKED / PASS / WARNING / FAIL
Validation Message = Rich text
Import Status = Select: NOT_IMPORTED / PREVIEWED / COMMITTED / SKIPPED
Imported At = Rich text
Synced At = Rich text
```

---

## Notion view policy 요구사항

사용자 요구사항:

```text
Notion에서 입력은 하되, 너무 많은 정보가 메인화면에 노출되지 않아야 한다.
```

따라서 문서에 아래 view 정책을 반드시 포함한다.

### 1. 기본 view: `Input`

사용자가 실제로 입력하는 최소 화면이다.

표시 권장 필드:

```text
Name
Execution Date
Symbol
Side
Quantity
Actual Price
Commission
Note
Status
```

숨김 권장 필드:

```text
External Key
Plan Date
Currency
Broker
Linked Daily Plan Key
Validation Status
Validation Message
Import Status
Imported At
Synced At
```

필터 권장:

```text
Status != IMPORTED
```

### 2. 검증 view: `Validation`

Python validation 이후 확인하는 화면이다.

표시 권장 필드:

```text
Execution Date
Symbol
Side
Quantity
Actual Price
Status
Validation Status
Validation Message
Import Status
```

필터 후보:

```text
Validation Status is FAIL
또는
Validation Status is WARNING
```

### 3. 관리 view: `Technical`

후속 importer/debug용 화면이다.

표시 권장 필드:

```text
Name
External Key
Execution Date
Plan Date
Symbol
Side
Quantity
Actual Price
Commission
Currency
Broker
Linked Daily Plan Key
Status
Validation Status
Validation Message
Import Status
Imported At
Synced At
```

### 4. 완료 view: `Committed`

이미 commit된 입력을 확인하는 화면이다.

필터 후보:

```text
Import Status = COMMITTED
또는
Status = IMPORTED
```

---

## 정책 결정 문서화

아래 결정을 문서에 명시한다.

```text
- 메인 입력 view는 최소 필드만 표시한다.
- 기술/검증/import 필드는 숨기고 별도 view에서 확인한다.
- Notion view에서 필드를 숨기는 것은 Python 코드 수정이 아니다.
- 속성명/타입을 바꾸면 후속 Python importer, mapping, validator 수정이 필요하다.
- Commission / Currency / Broker는 우선 optional field로 유지한다.
- 현재 ledger schema에 dedicated column이 없으므로 commit 반영 방식은 후속 MFU에서 결정한다.
- Daily Plan에 없는 Symbol은 기본 WARNING 후보로 둔다.
```

---

## 제외 범위

이번 작업에서 하지 않는다.

```text
Notion Manual Executions DB 실제 생성
Notion schema validation 구현
Notion row read/import 구현
validation engine 구현
preview report 생성
paper_execution_log.csv commit 구현
Daily Review Summary export 구현
Performance Summary export 구현
실제 Notion write
paper 원장 CSV 수정
config/example 수정
Python 코드 수정
```

---

## 검증 명령

문서 작업이므로 코드 변경은 없어야 한다.  
그래도 상태 확인용으로 아래를 실행한다.

```cmd
cd /d D:\python\StockScreener
set PYTHONPATH=.

python -m pytest tests\test_paper_cli.py -q
python -m pytest tests\test_notion_exporters.py tests\test_notion_settings.py tests\test_notion_mapping.py tests\test_notion_client.py tests\test_notion_schema_validator.py -q
```

테스트가 기존 unrelated 이슈로 실패하면 수정하지 말고 보고한다.

---

## 커밋 정책

문서만 커밋한다.

```cmd
git add docs\TRD\mfu_paper14_5b_manual_executions_schema_contract.md
git diff --cached --name-only
git commit -m "PAPER14-5B: document Manual Executions schema and views"
```

필요 시에만:

```cmd
git add docs\TRD\mfu_paper14_5a_manual_execution_input_design.md
```

금지:

```text
git add .
git add -A
```

---

## 성공 기준

```text
Manual Executions schema contract가 정리된다.
필수 입력 필드와 선택/관리 필드가 구분된다.
Notion 기본 Input view에 노출할 최소 필드가 정의된다.
Validation / Technical / Committed view 정책이 정의된다.
후속 Python importer가 의존할 속성명/타입이 안정적으로 정리된다.
Python 코드와 config는 수정하지 않는다.
실제 Notion import/write/commit은 수행하지 않는다.
문서만 커밋된다.
```

---

## 결과 보고 형식

5천자 이내.

```text
1. Summary
2. 기준 커밋 확인 결과
3. 변경 파일
4. 조사한 파일
5. Manual Executions schema contract 요약
6. 필수 입력 필드
7. 선택/운영 편의 필드
8. 검증/import 관리 필드
9. Notion view policy
10. 메인 Input view에 표시할 필드
11. 숨길 필드
12. Python 코드 수정 여부
13. 테스트 결과
14. 커밋 hash와 message
15. 남은 리스크
16. 다음 MFU 제안
```

반드시 명시:

이번 PAPER14-5B는 Manual Executions schema contract와 Notion view policy 문서화 작업이며, 실제 Notion import, paper ledger commit, Daily Review Summary export는 수행하지 않았다.
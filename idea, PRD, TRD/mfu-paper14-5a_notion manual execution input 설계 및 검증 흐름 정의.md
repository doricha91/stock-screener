# MFU-PAPER14-5A 작업 지시문: Notion Manual Execution Input 설계 및 검증 흐름 정의

## 목적

실전 운영에서 Daily Plan과 실제 체결 결과가 달라지는 문제를 해결하기 위해, Notion을 수동 체결 입력 staging layer로 사용하는 설계를 정의한다.

이번 작업은 설계 문서화 작업이다.  
Notion 입력값을 실제 paper 원장에 반영하는 기능은 구현하지 않는다.

반드시 명시:

이번 PAPER14-5A는 Notion Manual Execution Input 설계 및 검증 흐름 정의 작업이며, 실제 Notion import, paper ledger commit, Daily Review Summary export는 포함하지 않는다.

---

## 배경

현재 PAPER14에서는 아래 Notion export가 구현되어 있다.

- Weekly Reports
- Benchmark Reports
- Account Snapshots
- Daily Plans

Daily Plan은 read-only 시스템 생성 계획으로 유지한다.  
Daily Plan page body는 exporter-managed이며, 수동 메모는 보존 대상이 아니다.

실전에서는 Daily Plan이 그대로 실행되지 않을 수 있다.

예:

- 실제 체결가가 계획가와 다름
- 체결 수량이 계획 수량과 다름
- 부분 체결 / 미체결 발생
- 수수료 / 세금 / 환전 차이 발생
- 실제 현금 잔고와 예상 잔고 차이 발생

따라서 PyCharm에서 CSV를 직접 수정하는 대신, Notion을 사람이 입력하기 쉬운 execution input 화면으로 사용할 수 있는지 설계한다.

---

## 핵심 원칙

아래 원칙을 반드시 유지한다.

```text
Notion = 입력 대기 / staging layer
Python = 검증 / 정규화 / 원장 반영 주체
CSV / SQLite = 최종 source of truth
```

Notion 입력값을 곧바로 원장에 반영하지 않는다.

반드시 아래 흐름을 따른다.

```text
Notion 입력
→ Python read-only import
→ validation
→ preview report
→ 사용자 확인
→ commit
→ paper execution ledger 반영
```

---

## 구현 파일

이번 작업은 코드 구현이 아니라 문서화가 목적이다.

추가 문서 후보:

```text
docs/TRD/mfu_paper14_5a_manual_execution_input_design.md
```

조사 대상:

```text
scripts/paper.py
tests/test_paper_cli.py
core/
outputs/paper_test/
outputs/paper_test/paper_execution_log.csv
outputs/paper_test/paper_account_snapshot.csv
outputs/paper_test/paper_position_snapshot.csv
docs/operations/paper_daily_ops.md
docs/TRD/mfu_paper14_4_daily_plan_notion_export.md
```

경로가 다르면 실제 존재 경로를 찾아 보고한다.

---

## 설계 문서 요구사항

문서에 아래 내용을 포함한다.

### 1. 문제 정의

정리할 것:

- Daily Plan은 계획일 뿐 실제 체결과 다를 수 있음
- CSV 직접 수정은 불편하고 실수 위험이 있음
- 실제 체결가 / 체결수량 / 수수료 / 잔고 입력이 필요함
- Notion을 입력 UI로 사용할 수 있지만 source of truth로 삼으면 안 됨

### 2. Notion DB 설계안

후보 DB 이름:

```text
Manual Executions
```

속성 후보:

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
Status
Linked Daily Plan Key
Note
Validation Status
Validation Message
Import Status
Imported At
Synced At
```

권장 타입:

```text
Name = Title
External Key = Rich text
Execution Date = Date
Plan Date = Date
Symbol = Rich text
Side = Select: BUY / SELL
Quantity = Number
Actual Price = Number
Commission = Number
Currency = Select: USD / KRW
Broker = Select or Rich text
Status = Select: DRAFT / READY / IMPORTED / REJECTED
Linked Daily Plan Key = Rich text
Note = Rich text
Validation Status = Select: NOT_CHECKED / PASS / WARNING / FAIL
Validation Message = Rich text
Import Status = Select: NOT_IMPORTED / PREVIEWED / COMMITTED / SKIPPED
Imported At = Rich text
Synced At = Rich text
```

단, 속성을 과도하게 늘리지 말고 “원장 반영에 필요한 최소 필드”와 “운영 편의 필드”를 구분한다.

### 3. External Key 정책

예상 후보:

```text
manual_execution:{execution_date}:{symbol}:{side}:{sequence}
```

또는 사용자가 직접 입력하지 않아도 되는 안정적 key 생성 방식을 제안한다.

검토할 것:

- 같은 종목을 하루에 여러 번 체결할 수 있는가
- 부분 체결을 별도 row로 볼 것인가
- 중복 import 방지를 어떻게 할 것인가

### 4. Validation 규칙

최소 규칙:

```text
Symbol이 없으면 FAIL
Side가 BUY/SELL이 아니면 FAIL
Quantity <= 0이면 FAIL
Actual Price <= 0이면 FAIL
Execution Date가 없으면 FAIL
External Key 중복이면 FAIL
SELL 수량이 보유수량보다 크면 FAIL
BUY 후 현금이 음수가 되면 FAIL
Daily Plan에 없는 Symbol이면 WARNING 또는 FAIL 후보
Commission이 비어 있으면 0으로 처리할지 WARNING 처리할지 정책 제안
Currency가 비어 있으면 기본값을 쓸지 FAIL 처리할지 정책 제안
```

### 5. Preview → Commit 흐름

제안 CLI 흐름:

```cmd
python scripts\paper.py execution-import preview --source notion --date YYYY-MM-DD
python scripts\paper.py execution-import commit --source notion --date YYYY-MM-DD
```

또는 별도 스크립트 후보:

```cmd
python scripts\import_notion_executions.py --date YYYY-MM-DD --preview
python scripts\import_notion_executions.py --date YYYY-MM-DD --commit
```

preview 산출물 후보:

```text
outputs/paper_test/reports/manual_execution_import_preview_YYYYMMDD.md
outputs/paper_test/reports/manual_execution_import_preview_YYYYMMDD.json
```

commit 정책:

```text
validation FAIL이 있으면 commit 금지
WARNING은 사용자가 허용한 경우에만 commit 가능
commit 후 Imported At / Import Status를 Notion에 update할지 여부는 후속 MFU에서 결정
```

### 6. 기존 원장 연결 조사

조사할 것:

```text
paper_execution_log.csv schema
paper_account_snapshot.csv schema
paper_position_snapshot.csv schema
scripts/paper.py commit 흐름
기존 paper execution 기록 방식
```

설계 문서에는 Notion 입력값이 어느 원장 필드로 매핑될지 초안을 작성한다.

### 7. Daily Review와의 관계

정책:

```text
Manual Executions = 사람이 입력한 실제 체결
Daily Review Summary = 그 결과를 요약해 보여주는 read-only report
```

Daily Review Summary는 이번 작업에서 구현하지 않는다.  
Manual Execution import/commit이 설계된 뒤 후속 단계로 둔다.

---

## 제외 범위

이번 작업에서 하지 않는다.

```text
Notion Manual Executions DB 실제 생성
Notion schema validation 구현
Notion에서 execution row 읽기 구현
paper ledger commit 구현
Daily Review Summary export 구현
Performance Summary export 구현
Manual Review 입력 연동 구현
증권사 API 연동
실제 Notion write
paper 원장 CSV 수정
outputs/front_test 수정
DB/PNG/output 파일 수정/삭제
한글 경로 문서 수정/삭제
```

---

## 검증 명령

문서 작업이므로 코드 변경은 없어야 한다.

```cmd
cd /d D:\python\StockScreener
set PYTHONPATH=.

python -m pytest tests\test_notion_exporters.py tests\test_notion_settings.py tests\test_notion_mapping.py tests\test_notion_client.py tests\test_notion_schema_validator.py -q
python -m pytest tests\test_paper_cli.py -q
```

코드 변경이 없으면 테스트는 선택적으로 실행해도 된다.  
실패 시 수정하지 말고 보고한다.

---

## 커밋 정책

문서만 커밋한다.

```cmd
git add docs\TRD\mfu_paper14_5a_manual_execution_input_design.md
git diff --cached --name-only
git commit -m "PAPER14-5A: design Notion manual execution input flow"
```

금지:

```text
git add .
git add -A
```

---

## 성공 기준

```text
Manual Executions DB 설계안이 정리된다.
Notion 입력값 검증 규칙이 정의된다.
preview → commit 흐름이 정의된다.
기존 paper 원장과의 연결 방식 초안이 정리된다.
Daily Review Summary와의 관계가 정의된다.
Notion은 staging layer, CSV/SQLite는 source of truth라는 원칙이 명시된다.
실제 구현은 하지 않는다.
```

---

## 결과 보고 형식

5천자 이내.

```text
1. Summary
2. 변경 파일
3. 조사한 파일
4. Manual Executions DB 설계안
5. 필수 입력 필드와 선택 입력 필드
6. validation 규칙
7. External Key 정책
8. preview → commit 흐름
9. 기존 paper ledger 연결 초안
10. Daily Review Summary와의 관계
11. 제외 범위 준수 여부
12. 테스트 실행 여부와 결과
13. 커밋 hash와 message
14. 남은 리스크
15. 다음 MFU 제안
```

반드시 명시:

이번 PAPER14-5A는 Notion Manual Execution Input 설계 및 검증 흐름 정의 작업이며, 실제 Notion import, paper ledger commit, Daily Review Summary export는 수행하지 않았다.
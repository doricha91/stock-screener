# MFU-PAPER14-3C 작업 지시문: Notion schema validation 구현

## 목적

MFU-PAPER14-3C의 목표는 실제 Notion export 전에 Weekly Reports / Benchmark Reports / Account Snapshots 3개 data source의 schema가 exporter 계약과 일치하는지 검증하는 것이다.

이번 단계는 read-only validation이다.

반드시 명시:

```text
이번 PAPER14-3C는 Notion data source schema read-only validation 구현이며, 실제 Notion export/write는 포함하지 않는다.
```

---

## 배경

PAPER14-3B에서 아래 문서가 추가됐다.

```text
docs/TRD/mfu_paper14_3b_notion_schema_contract.md
```

사용자는 Notion UI에서 아래 3개 DB를 수동 생성했다.

```text
Weekly Reports
Benchmark Reports
Account Snapshots
```

그리고 각 DB의 data source id를 `.env`에 등록했다.

```text
NOTION_WEEKLY_REPORTS_DATA_SOURCE_ID
NOTION_BENCHMARK_REPORTS_DATA_SOURCE_ID
NOTION_ACCOUNT_SNAPSHOTS_DATA_SOURCE_ID
```

이제 actual export 전에 Notion API로 schema를 읽어 필수 속성명과 타입이 맞는지 확인해야 한다.

---

## 구현 파일

추가 후보:

```text
core/notion_schema_validator.py
scripts/dev/validate_notion_schema.py
tests/test_notion_schema_validator.py
docs/TRD/mfu_paper14_3c_notion_schema_validation.md
```

수정 후보:

```text
core/notion_client.py
core/notion_settings.py
```

단, `core/notion_settings.py`는 꼭 필요한 경우만 수정한다.

---

## 검증 대상

아래 3개 data source를 검증한다.

```text
weekly_reports
benchmark_reports
account_snapshots
```

설정 값은 env override를 우선 사용한다.

```text
NOTION_WEEKLY_REPORTS_DATA_SOURCE_ID
NOTION_BENCHMARK_REPORTS_DATA_SOURCE_ID
NOTION_ACCOUNT_SNAPSHOTS_DATA_SOURCE_ID
```

---

## Schema 기준

기준 문서:

```text
docs/TRD/mfu_paper14_3b_notion_schema_contract.md
```

또한 실제 exporter payload 기준을 함께 확인한다.

```text
core/notion_exporters.py
config/notion_property_mapping.example.json
core/notion_client.py
```

타입 매핑:

```text
notion_title       -> title
notion_rich_text   -> rich_text
notion_date        -> date
notion_number      -> number
notion_select      -> select
```

주의:

```text
Synced At = rich_text
Official Run = select
Symbols = rich_text
External Key = rich_text
Name = title
```

---

## 구현 요구사항

### 1. NotionClient read-only schema method 추가

`core/notion_client.py`에 data source schema를 읽는 read-only method를 추가한다.

예상 함수명:

```python
retrieve_data_source(data_source_id: str) -> dict
```

또는:

```python
get_data_source_schema(data_source_id: str) -> dict
```

정책:

```text
- write API 호출 금지
- page create/update/delete 금지
- token value 로그 출력 금지
- 404/403/validation error는 명확한 메시지로 변환
```

### 2. schema validator 추가

`core/notion_schema_validator.py`를 추가한다.

기능:

```text
1. expected schema 정의
2. actual Notion data source schema 조회
3. 필수 속성 존재 여부 검증
4. 속성 타입 일치 여부 검증
5. 결과를 PASS / FAIL / WARNING으로 반환
```

검증 결과 예시:

```text
weekly_reports: PASS
benchmark_reports: FAIL
- Official Run expected select, got checkbox
account_snapshots: WARNING
- Valuation Status select exists, options not fully checked
```

### 3. CLI 추가

`scripts/dev/validate_notion_schema.py` 추가.

CLI 예시:

```bash
python scripts/dev/validate_notion_schema.py --weekly
python scripts/dev/validate_notion_schema.py --benchmark
python scripts/dev/validate_notion_schema.py --account-snapshot
python scripts/dev/validate_notion_schema.py --all
python scripts/dev/validate_notion_schema.py --json
```

정책:

```text
- 기본은 사람이 읽기 쉬운 text 출력
- --json은 machine-readable summary 출력
- 하나라도 FAIL이면 exit code 1
- PASS/WARNING만 있으면 exit code 0
```

---

## Select option 검증 정책

이번 단계에서는 select option은 “존재 여부와 타입”을 우선 검증한다.

옵션값까지 검증하는 경우 아래처럼 구분한다.

```text
필수 검증:
- select 속성이 존재하는지
- property type이 select인지

선택 검증:
- 현재 문서에 있는 option 후보가 Notion에 미리 존재하는지
```

옵션값이 없어도 Notion API가 자동 추가할 수 있으므로, option 누락은 기본적으로 FAIL이 아니라 WARNING으로 처리한다.

---

## 금지 사항

```text
실제 Notion export/write 금지
page create/update/delete 금지
python scripts/export_paper_to_notion.py --weekly 실행 금지
python scripts/export_paper_to_notion.py --benchmark 실행 금지
python scripts/export_paper_to_notion.py --account-snapshot 실행 금지
smoke test create/update 실행 금지
Notion DB 자동 생성 금지
paper 원장 CSV 수정 금지
outputs/front_test 수정 금지
한글 경로 문서 수정/삭제 금지
DB/PNG/output 파일 수정/삭제 금지
```

허용:

```text
Notion data source schema read
dry-run export
mock 기반 unit test
```

---

## 테스트

추가/수정 테스트:

```text
tests/test_notion_schema_validator.py
tests/test_notion_client.py
```

필수 테스트:

```text
1. expected schema가 weekly/benchmark/account에 대해 생성된다.
2. 모든 속성이 맞으면 PASS.
3. 필수 속성이 없으면 FAIL.
4. 타입이 다르면 FAIL.
5. select option 누락은 WARNING.
6. token value가 결과/예외에 노출되지 않는다.
7. --json 출력이 안정적인 구조를 가진다.
```

---

## 검증 명령

```bash
set PYTHONPATH=.

python -m py_compile core/notion_client.py
python -m py_compile core/notion_schema_validator.py
python -m py_compile scripts/dev/validate_notion_schema.py

python -m pytest tests/test_notion_client.py tests/test_notion_schema_validator.py -q
python -m pytest tests/test_notion_exporters.py tests/test_notion_settings.py tests/test_notion_mapping.py -q

python scripts/dev/validate_notion_schema.py --all
python scripts/dev/validate_notion_schema.py --all --json

python scripts/export_paper_to_notion.py --weekly --dry-run --json
python scripts/export_paper_to_notion.py --benchmark --dry-run --json
python scripts/export_paper_to_notion.py --account-snapshot --dry-run --json
```

주의:

```text
마지막 3개는 dry-run만 허용한다.
```

---

## 성공 기준

```text
Weekly Reports schema validation이 가능하다.
Benchmark Reports schema validation이 가능하다.
Account Snapshots schema validation이 가능하다.
필수 속성 누락을 FAIL로 잡는다.
속성 타입 불일치를 FAIL로 잡는다.
select option 누락은 WARNING으로 보고한다.
실제 Notion write/export는 수행하지 않는다.
테스트가 통과한다.
schema validation 결과가 text/json으로 출력된다.
```

---

## 결과 보고 형식

5천자 이내.

```text
1. Summary
2. 변경 파일
3. 추가된 CLI
4. NotionClient read-only method
5. Weekly schema validation 결과
6. Benchmark schema validation 결과
7. Account schema validation 결과
8. FAIL/WARNING 상세
9. select option 검증 정책
10. dry-run 결과
11. 테스트 결과
12. 실제 Notion export/write 미수행 확인
13. paper 원장 CSV 변경 여부
14. outputs/front_test 변경 여부
15. 한글 경로 문서와 DB/PNG/output 파일 미수정 확인
16. 남은 리스크
17. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER14-3C는 Notion schema read-only validation 구현이며, 실제 Notion export/write는 수행하지 않았다.
```
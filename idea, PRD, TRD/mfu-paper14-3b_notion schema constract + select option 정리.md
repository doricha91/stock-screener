# MFU-PAPER14-3B 작업 지시문: Notion schema contract + select option 정리

## 목적

MFU-PAPER14-3B의 목표는 PAPER14-3 actual export 전에 사람이 Notion에서 만들어야 할 DB schema contract를 확정하는 것이다.

대상은 아래 3개 DB로 제한한다.

```text
1. Weekly Reports
2. Benchmark Reports
3. Account Snapshots
```

이번 단계에서는 Notion에 실제 write하지 않는다.  
Notion DB 자동 생성, schema validation API 구현, actual export는 포함하지 않는다.

반드시 명시:

```text
이번 PAPER14-3B는 Weekly / Benchmark / Account Snapshot Notion DB의 속성명, 속성 타입, select option 후보를 정리하는 문서화 작업이며, 실제 Notion export/write는 포함하지 않는다.
```

---

## 배경

PAPER14 common layer와 exporter layer는 이미 별도 커밋으로 정리됐다.

```text
PAPER14: add Notion common client/settings/mapping layer
PAPER14: add read-only Notion export for paper reports
```

현재 exporter는 아래 3개를 dry-run으로 생성할 수 있다.

```text
weekly_reports
benchmark_reports
account_snapshots
```

하지만 actual export 전에 Notion UI에서 사람이 DB를 만들고, 속성명과 타입을 exporter payload와 맞춰야 한다.

특히 현재 코드 기준으로 주의할 점:

```text
- Synced At은 Date가 아니라 rich_text일 수 있음
- Official Run은 Checkbox가 아니라 select일 수 있음
- Symbols는 multi_select가 아니라 rich_text일 수 있음
- data source id를 사용해야 하며 database id와 혼동하면 안 됨
```

---

## 구현 파일

추가 후보:

```text
docs/TRD/mfu_paper14_3b_notion_schema_contract.md
```

수정 후보:

```text
docs/TRD/mfu_paper14_3_notion_readonly_export.md
config/notion_property_mapping.example.json
config/notion_settings.example.json
```

단, mapping/example 파일은 실제 불일치가 발견될 때만 수정한다.  
기본은 문서 추가 작업이다.

---

## 조사 대상 파일

아래 파일을 반드시 확인한다.

```text
core/notion_exporters.py
core/notion_client.py
config/notion_property_mapping.example.json
core/paper_weekly_status.py
core/paper_benchmark_comparison.py
outputs/paper_test/reports/paper_weekly_status_summary.json
outputs/paper_test/reports/paper_benchmark_comparison.json
outputs/paper_test/paper_account_snapshot.csv
```

없거나 경로가 다르면 실제 존재 경로를 찾아 보고한다.

---

## Schema contract 작성 요구사항

`docs/TRD/mfu_paper14_3b_notion_schema_contract.md`에 아래 내용을 정리한다.

### 1. Weekly Reports DB

정리할 것:

```text
- Notion 속성명
- Notion 속성 타입
- exporter 내부 source key
- 값 출처
- select option 후보
- 필수 여부
- 주의사항
```

반드시 포함할 속성 후보:

```text
Name
External Key
Period Start
Period End
Latest Snapshot Date
Coverage Status
Overall Status
Snapshot Count
End Equity
Equity Change %
Cash Ratio
Trade Count
Gap Count
High Gap Count
Markdown Path
JSON Path
Schema Version
Synced At
Sync Status
```

### 2. Benchmark Reports DB

반드시 포함할 속성 후보:

```text
Name
External Key
Latest Snapshot Date
Run Mode
Official Run
Availability Status
Paper Return
SPY Return
QQQ Return
CASH Return
Excess vs SPY
Excess vs QQQ
Excess vs CASH
Paper MDD
SPY MDD
QQQ MDD
Markdown Path
JSON Path
Schema Version
Synced At
Sync Status
```

### 3. Account Snapshots DB

반드시 포함할 속성 후보:

```text
Name
External Key
Snapshot Date
Initial Cash
Cash
Total Equity Market Value
Total Equity Cost Basis
Unrealized PnL
Cash Ratio Market Value
Cash Ratio Cost Basis
Position Count
Symbols
Valuation Status
Valuation Price Date
Synced At
Sync Status
```

---

## Select option 조사 요구사항

select option 후보는 추측하지 말고 아래 순서로 확인한다.

```text
1. exporter에서 notion_select(...)에 들어가는 값
2. weekly/benchmark/account snapshot 생성 코드의 가능한 상태값
3. 실제 sample JSON/CSV에 존재하는 값
4. 테스트 fixture에 존재하는 값
```

정확히 확정할 수 없는 값은 아래처럼 표시한다.

```text
확정: 코드에서 직접 생성되는 값
관찰: 현재 sample에서만 확인된 값
후보: 문맥상 가능하지만 코드상 전체 열거는 확인되지 않은 값
```

---

## 금지 사항

```text
실제 Notion export/write 금지
python scripts/export_paper_to_notion.py --weekly 실행 금지
python scripts/export_paper_to_notion.py --benchmark 실행 금지
python scripts/export_paper_to_notion.py --account-snapshot 실행 금지
smoke test 실환경 실행 금지
Notion DB 자동 생성 금지
schema validation API 구현 금지
paper 원장 CSV 수정 금지
outputs/front_test 수정 금지
한글 경로 문서 삭제/수정 금지
DB/PNG/output 파일 삭제/수정 금지
```

---

## 검증 명령

문서 작업이지만 코드 상태 확인을 위해 아래를 실행한다.

```bash
set PYTHONPATH=.

python -m py_compile core/notion_exporters.py
python -m py_compile core/notion_client.py
python -m py_compile core/paper_weekly_status.py
python -m py_compile core/paper_benchmark_comparison.py

python -m pytest tests/test_notion_exporters.py tests/test_notion_settings.py tests/test_notion_mapping.py tests/test_notion_client.py -q
python -m pytest tests/test_paper_weekly_status.py tests/test_paper_benchmark_comparison.py -q

python scripts/export_paper_to_notion.py --weekly --dry-run --json
python scripts/export_paper_to_notion.py --benchmark --dry-run --json
python scripts/export_paper_to_notion.py --account-snapshot --dry-run --json
```

주의:

```text
dry-run만 허용한다.
```

---

## 성공 기준

```text
Weekly Reports schema contract가 정리된다.
Benchmark Reports schema contract가 정리된다.
Account Snapshots schema contract가 정리된다.
각 속성의 Notion 타입이 exporter payload 기준으로 정리된다.
select option 후보가 확정/관찰/후보로 구분된다.
database id가 아니라 data source id를 사용해야 한다는 주의사항이 문서화된다.
실제 Notion write/export는 수행하지 않는다.
보호 대상 파일과 output 산출물은 건드리지 않는다.
테스트와 dry-run 결과가 보고된다.
```

---

## 결과 보고 형식

5천자 이내.

```text
1. Summary
2. 변경 파일
3. 조사한 파일
4. Weekly Reports schema 정리 결과
5. Benchmark Reports schema 정리 결과
6. Account Snapshots schema 정리 결과
7. select option 확정/관찰/후보 정리
8. mapping/example 파일 수정 여부
9. dry-run 결과
10. 테스트 결과
11. 실제 Notion export/write 미수행 확인
12. paper 원장 CSV 변경 여부
13. outputs/front_test 변경 여부
14. 한글 경로 문서와 DB/PNG/output 파일 미수정 확인
15. 남은 리스크
16. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER14-3B는 Notion schema contract 문서화 작업이며, 실제 Notion export/write는 수행하지 않았다.
```
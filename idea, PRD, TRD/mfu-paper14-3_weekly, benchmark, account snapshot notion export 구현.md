# MFU-PAPER14-3 작업 지시문: Weekly / Benchmark / Account Snapshot Notion export 구현

## 목적

PAPER14-3의 목표는 PAPER14-2에서 구현한 Notion 공통 client/settings/mapping/upsert 레이어를 사용해, 1차 read-only export를 구현하는 것이다.

대상은 아래 3개로 제한한다.

```text
1. Weekly Reports
2. Benchmark Reports
3. Account Snapshots
```

또한 PAPER14-2에서 실환경 smoke test가 update 경로만 확인됐으므로, 이번 단계에서 smoke DB를 사용해 create 경로도 명시적으로 검증한다.

반드시 명시:

```text
이번 PAPER14-3은 Weekly Reports / Benchmark Reports / Account Snapshots의 Notion read-only export 구현이며, Daily Plan export, Daily Review export, Performance Summary export, Manual Review 입력 연동은 포함하지 않는다.
```

---

## 배경

PAPER14-2에서 아래 공통 레이어가 구현됐다.

```text
core/notion_settings.py
core/notion_mapping.py
core/notion_client.py
scripts/dev/notion_smoke_test.py
```

검증된 것:

```text
NOTION_TOKEN 정상
Data Source 접근 정상
External Key 기반 update 정상
mapping loader 정상
settings loader 정상
```

다만 PAPER14-2 실제 실행에서는 기존 smoke row가 이미 존재해 두 번 모두 update 경로를 탔다.  
이번 PAPER14-3에서는 create 경로도 smoke DB에서 검증한다.

---

## 구현 파일

추가 후보:

```text
core/notion_exporters.py
scripts/export_paper_to_notion.py
tests/test_notion_exporters.py
docs/TRD/mfu_paper14_3_notion_readonly_export.md
```

수정 후보:

```text
scripts/dev/notion_smoke_test.py
config/notion_settings.example.json
config/notion_property_mapping.example.json
tests/test_notion_client.py
tests/test_notion_mapping.py
tests/test_notion_settings.py
```

필요 시:

```text
scripts/paper.py
tests/test_paper_cli.py
```

단, 이번 단계에서 `paper.py notion-export` 추가는 선택 사항이다.  
우선 standalone script 구현을 우선한다.

---

## Notion 대상 DB

사용자는 Notion UI에서 아래 DB를 미리 생성하고, integration connection을 부여한다.

```text
Weekly Reports DB
Benchmark Reports DB
Account Snapshots DB
Smoke Test DB
```

각 DB ID 또는 data source ID는 `config/notion_settings.json` 또는 환경변수 override로 제공한다.

---

## 설정 파일 요구사항

`config/notion_settings.example.json`에 아래 key가 있어야 한다.

```json
{
  "enabled": false,
  "token_env": "NOTION_TOKEN",
  "databases": {
    "smoke_test": "",
    "weekly_reports": "",
    "benchmark_reports": "",
    "account_snapshots": ""
  }
}
```

실제 `config/notion_settings.json`은 gitignore 대상이다.

---

## Mapping 요구사항

`config/notion_property_mapping.example.json`에 최소 아래 section을 둔다.

```json
{
  "weekly_reports": {},
  "benchmark_reports": {},
  "account_snapshots": {},
  "smoke_test": {}
}
```

### Weekly Reports mapping 후보

Source:

```text
outputs/paper_test/reports/paper_weekly_status_summary.json
outputs/paper_test/reports/paper_weekly_status_summary.md
```

External Key:

```text
weekly_report:{period.actual_start}:{period.actual_end}
```

주요 속성:

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
Synced At
Schema Version
Sync Status
```

### Benchmark Reports mapping 후보

Source:

```text
outputs/paper_test/reports/paper_benchmark_comparison.json
outputs/paper_test/reports/paper_benchmark_comparison.md
```

External Key:

```text
benchmark:{latest_snapshot_date}:{run_mode}
```

주요 속성:

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
Synced At
Schema Version
Sync Status
```

### Account Snapshots mapping 후보

Source:

```text
outputs/paper_test/paper_account_snapshot.csv
```

External Key:

```text
account_snapshot:{snapshot_date}
```

주요 속성:

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

## Export 동작 정책

### 1. Weekly Reports export

동작:

```text
1. paper_weekly_status_summary.json 읽기
2. paper_weekly_status_summary.md 존재 여부 확인
3. External Key 생성
4. mapping으로 Notion properties 생성
5. page body에는 1차로 짧은 summary만 넣음
6. 원본 markdown path/json path를 property로 남김
7. External Key 기준 upsert
```

주의:

```text
Markdown 전체 → Notion block 변환 일반화는 이번 단계 제외
```

### 2. Benchmark Reports export

동작:

```text
1. paper_benchmark_comparison.json 읽기
2. paper_benchmark_comparison.md 존재 여부 확인
3. External Key 생성
4. Paper/SPY/QQQ/CASH 주요 성과를 properties로 매핑
5. exploratory/unofficial 여부를 properties와 body에 명시
6. External Key 기준 upsert
```

### 3. Account Snapshots export

동작:

```text
1. paper_account_snapshot.csv 읽기
2. 기본은 최신 snapshot row 1개만 export
3. 옵션으로 --all-account-snapshots 또는 --date YYYYMMDD 확장 가능
4. External Key 기준 upsert
```

1차 권장:

```text
최신 snapshot row만 export
```

이유:

```text
Notion 대량 row 생성 위험을 줄이고 mapping/upsert를 먼저 검증하기 위함
```

---

## CLI 요구사항

standalone script 추가:

```text
python scripts/export_paper_to_notion.py --weekly
python scripts/export_paper_to_notion.py --benchmark
python scripts/export_paper_to_notion.py --account-snapshot
python scripts/export_paper_to_notion.py --all
```

선택 옵션:

```text
--dry-run
--json
```

정책:

```text
--dry-run은 Notion API write를 하지 않고 payload 요약만 출력
--json은 결과 summary를 stdout에 JSON으로 출력
```

이번 단계에서 `paper.py notion-export`는 선택 사항이다.  
추가한다면 아래 정도만 허용한다.

```text
python scripts/paper.py notion-export --weekly
python scripts/paper.py notion-export --benchmark
python scripts/paper.py notion-export --account-snapshot
```

---

## Create 경로 실환경 테스트 추가

PAPER14-2에서 update 경로만 실환경 확인됐으므로, 이번 단계에서 smoke script에 create-path 테스트 옵션을 추가한다.

### smoke script 옵션

```text
python scripts/dev/notion_smoke_test.py --unique-key
```

또는:

```text
python scripts/dev/notion_smoke_test.py --create-test
```

동작:

```text
1. 기존 고정 external key 대신 timestamp/random suffix가 붙은 external key 사용
2. Notion smoke DB에 새 row create
3. 결과가 CREATED인지 확인
4. 같은 key로 다시 실행하거나 내부적으로 update를 한 번 더 호출해 update 경로도 확인 가능
```

권장 출력:

```text
SMOKE CREATE TEST: CREATED
SMOKE UPDATE TEST: UPDATED
SMOKE TEST PASSED
```

주의:

```text
create-path 테스트는 smoke_test DB에서만 실행한다.
운영용 Weekly/Benchmark/Account DB에서 무작위 create 테스트를 하지 않는다.
```

---

## Page body 정책

이번 단계에서는 Notion page body를 간단히 유지한다.

허용:

```text
간단한 paragraph
원본 report path
generated_at
limitations 요약
```

제외:

```text
Markdown 전체를 block으로 변환
표를 Notion table로 변환
복잡한 nested blocks
```

---

## 보안 요구사항

반드시 유지:

```text
NOTION_TOKEN은 환경변수
실제 DB ID는 config/notion_settings.json 또는 env override
config/notion_settings.json은 gitignore
config/notion_property_mapping.json은 gitignore
토큰을 로그에 출력하지 않음
예외 메시지에 token value를 포함하지 않음
```

---

## 제외 범위

이번 단계에서 하지 않는다.

```text
Daily Plan export
Daily Review Summary export
Performance Summary export
Manual Review 입력 연동
Notion DB 자동 생성
Notion schema migration
Markdown 전체 block 변환
review import
review append 연동
paper 원장 CSV 수정
market_data.db 수정
reports 재생성
outputs/front_test 수정
```

---

## 테스트

mock 기반 unit test를 우선한다. 실제 Notion API는 smoke/manual 검증으로 분리한다.

추가/수정 테스트:

```text
tests/test_notion_exporters.py
tests/test_notion_client.py
tests/test_notion_mapping.py
tests/test_notion_settings.py
```

필수 테스트:

```text
1. weekly JSON에서 External Key 생성
2. benchmark JSON에서 External Key 생성
3. account snapshot row에서 External Key 생성
4. weekly Notion property payload 생성
5. benchmark Notion property payload 생성
6. account snapshot Notion property payload 생성
7. missing source file이면 명확한 에러
8. missing mapping이면 명확한 에러
9. dry-run에서는 create/update 호출하지 않음
10. upsert helper가 export path에서 호출됨
11. account snapshot 기본 export는 최신 row 1개만 선택
12. Notion token이 로그에 출력되지 않음
13. paper 원장 CSV를 수정하지 않음
14. outputs/front_test를 수정하지 않음
```

---

## 검증 명령

```text
set PYTHONPATH=.

python -m pytest tests/test_notion_exporters.py tests/test_notion_client.py tests/test_notion_settings.py tests/test_notion_mapping.py -q

python -m py_compile core/notion_exporters.py
python -m py_compile scripts/export_paper_to_notion.py
python -m py_compile scripts/dev/notion_smoke_test.py

python scripts/dev/notion_smoke_test.py --create-test

python scripts/export_paper_to_notion.py --weekly --dry-run
python scripts/export_paper_to_notion.py --benchmark --dry-run
python scripts/export_paper_to_notion.py --account-snapshot --dry-run

python scripts/export_paper_to_notion.py --weekly
python scripts/export_paper_to_notion.py --benchmark
python scripts/export_paper_to_notion.py --account-snapshot
```

주의:

```text
실제 export 명령은 Notion DB에 create/update를 수행한다.
paper 원장 CSV와 market_data.db는 수정하지 않는다.
```

---

## 성공 기준

```text
Weekly Reports export가 구현된다.
Benchmark Reports export가 구현된다.
Account Snapshot 최신 row export가 구현된다.
External Key 기반 upsert가 사용된다.
dry-run이 지원된다.
create 경로 smoke test가 추가되고 실환경에서 확인된다.
Notion DB에는 중복 row가 생기지 않는다.
token과 실제 DB ID는 커밋되지 않는다.
paper 원장 CSV와 outputs/front_test는 수정되지 않는다.
테스트가 통과한다.
```

---

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 변경 파일
3. 추가된 export 대상
4. 추가된 CLI
5. Weekly export 동작
6. Benchmark export 동작
7. Account Snapshot export 동작
8. External Key 정책
9. create 경로 smoke test 결과
10. dry-run 결과
11. 실제 Notion export 결과
12. 생성/업데이트된 Notion row 수
13. 제외한 항목
14. 테스트 결과
15. paper 원장 CSV 변경 여부
16. outputs/front_test 변경 여부
17. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER14-3은 Weekly Reports / Benchmark Reports / Account Snapshots의 Notion read-only export 구현이며, review 입력 연동과 paper 원장 수정은 포함하지 않는다.
```
# MFU-PAPER14-3D 작업 지시문: Notion actual export 검증

## 목적

MFU-PAPER14-3D의 목표는 Weekly Reports / Benchmark Reports / Account Snapshots 3개 Notion data source에 대해 실제 export를 수행하고, External Key 기반 upsert가 정상 동작하는지 검증하는 것이다.

이번 단계에서는 실제 Notion write가 발생한다.

검증 목표:

```text
1차 실행: CREATED 또는 기존 row가 있으면 UPDATED
2차 실행: UPDATED
```

반드시 명시:

```text
이번 PAPER14-3D는 Weekly / Benchmark / Account Snapshot의 실제 Notion export 검증이며, Daily Plan export, Daily Review export, Performance Summary export, Manual Review 입력 연동은 포함하지 않는다.
```

---

## 배경

PAPER14-3B에서 Notion schema contract 문서가 작성됐다.

```text
docs/TRD/mfu_paper14_3b_notion_schema_contract.md
```

PAPER14-3C에서 read-only schema validation이 구현됐다.

```text
core/notion_schema_validator.py
scripts/dev/validate_notion_schema.py
```

사용자는 Notion UI에서 3개 DB를 생성했고, schema validation 결과가 모두 PASS인 상태다.

대상 data source:

```text
weekly_reports
benchmark_reports
account_snapshots
```

---

## 전제 조건

먼저 아래를 확인한다.

```cmd
cd /d D:\python\StockScreener
set PYTHONPATH=.
git log --oneline -8
git status --short
```

최근 커밋에 아래 성격의 커밋이 있어야 한다.

```text
PAPER14: add Notion common client/settings/mapping layer
PAPER14: add read-only Notion export for paper reports
PAPER14-3B: document Notion schema contract
PAPER14-3C: add Notion schema validation
```

---

## 보호 대상

아래 파일은 수정/삭제/stage하지 않는다.

```text
.env
.env.*
config/notion_settings.json
config/notion_property_mapping.json
outputs/**
backtest_log.db
analysis_results/market_regime_timeline.png
idea, PRD, TRD/mfu-paper12-*
idea, PRD, TRD/mfu-paper13-*
idea, PRD, TRD/mfu-paper14-*
```

---

## 사전 검증

실제 export 전에 schema validation을 다시 실행한다.

```cmd
python scripts\dev\validate_notion_schema.py --all --json
```

조건:

```text
weekly_reports = PASS 또는 WARNING
benchmark_reports = PASS 또는 WARNING
account_snapshots = PASS 또는 WARNING
FAIL이 하나라도 있으면 actual export 금지
```

dry-run도 다시 확인한다.

```cmd
python scripts\export_paper_to_notion.py --weekly --dry-run --json
python scripts\export_paper_to_notion.py --benchmark --dry-run --json
python scripts\export_paper_to_notion.py --account-snapshot --dry-run --json
```

기대 External Key:

```text
weekly_report:2026-05-09:2026-05-20
benchmark:2026-05-20:exploratory
account_snapshot:2026-05-20
```

---

## Actual export 실행 정책

`--all`로 한 번에 실행하지 말고, 대상별로 독립 실행한다.

이유:

```text
- 실패 원인 분리
- Notion row 생성/수정 결과 추적
- Weekly / Benchmark / Account Snapshot 각각 CREATED → UPDATED 확인
```

---

## 1차 actual export

아래 순서로 실행한다.

```cmd
python scripts\export_paper_to_notion.py --weekly --json
python scripts\export_paper_to_notion.py --benchmark --json
python scripts\export_paper_to_notion.py --account-snapshot --json
```

각 결과에서 확인할 것:

```text
target
data_source_key
external_key
action
page_id
dry_run=false
```

기대 action:

```text
운영 DB에 기존 row가 없으면 CREATED
이미 같은 External Key row가 있으면 UPDATED
```

주의:

```text
첫 실행에서 UPDATED가 나와도 실패는 아니다.
단, 결과 보고에 “기존 row 존재로 추정”이라고 명시한다.
```

---

## 2차 actual export

동일 명령을 한 번 더 실행한다.

```cmd
python scripts\export_paper_to_notion.py --weekly --json
python scripts\export_paper_to_notion.py --benchmark --json
python scripts\export_paper_to_notion.py --account-snapshot --json
```

기대 action:

```text
weekly_reports: UPDATED
benchmark_reports: UPDATED
account_snapshots: UPDATED
```

2차 실행에서도 CREATED가 나오면 External Key upsert가 깨졌을 가능성이 있으므로 FAIL로 보고한다.

---

## Notion UI 확인

실행 후 Notion UI에서 각 DB를 확인한다.

확인할 것:

```text
Weekly Reports DB에 해당 External Key row 존재
Benchmark Reports DB에 해당 External Key row 존재
Account Snapshots DB에 해당 External Key row 존재
동일 External Key 중복 row 없음
주요 property 값 채워짐
page body에 짧은 summary 생성됨
```

중복 row가 있으면 삭제하지 말고 보고한다.

---

## 테스트

actual export 후에도 로컬 테스트를 실행한다.

```cmd
python -m pytest tests\test_notion_exporters.py tests\test_notion_settings.py tests\test_notion_mapping.py tests\test_notion_client.py tests\test_notion_schema_validator.py -q
```

필요 시 PAPER12/13 테스트도 확인한다.

```cmd
python -m pytest tests\test_paper_weekly_status.py tests\test_paper_benchmark_comparison.py tests\test_paper_cli.py -q
```

---

## 금지 사항

이번 단계에서 하지 않는다.

```text
Daily Plan export
Daily Review Summary export
Performance Summary export
Manual Review 입력 연동
Notion DB 자동 생성
Notion schema migration
Notion row 수동 삭제
paper 원장 CSV 수정
market_data.db 수정
outputs/front_test 수정
한글 경로 문서 수정/삭제
DB/PNG/output 파일 수정/삭제
git reset --hard
git clean -fd
```

---

## 성공 기준

```text
schema validation이 PASS 또는 WARNING 상태다.
dry-run 3종이 성공한다.
Weekly Reports actual export가 성공한다.
Benchmark Reports actual export가 성공한다.
Account Snapshots actual export가 성공한다.
2차 실행에서 3개 모두 UPDATED가 확인된다.
동일 External Key 중복 row가 없다.
paper 원장 CSV는 변경되지 않는다.
outputs/front_test는 변경되지 않는다.
실제 Notion write 결과가 결과 보고에 명확히 기록된다.
```

---

## 커밋 정책

이번 3D는 실제 export 검증 단계이므로, 코드 변경이 없다면 커밋하지 않는다.

단, 검증 결과 문서를 추가한다면 아래 파일만 커밋 후보로 둔다.

```text
docs/TRD/mfu_paper14_3d_actual_export_verification.md
```

문서 추가 시 추천 commit message:

```text
PAPER14-3D: document actual Notion export verification
```

코드 수정이 필요해진 경우에는 actual export를 중단하고, 수정 범위를 별도 보고한다.

---

## 결과 보고 형식

5천자 이내.

```text
1. Summary
2. 현재 브랜치
3. 사전 schema validation 결과
4. dry-run 결과
5. 1차 actual export 결과
   - weekly
   - benchmark
   - account snapshot
6. 2차 actual export 결과
   - weekly
   - benchmark
   - account snapshot
7. External Key 목록
8. CREATED / UPDATED 결과
9. Notion UI 확인 결과
10. 중복 row 여부
11. 테스트 결과
12. paper 원장 CSV 변경 여부
13. outputs/front_test 변경 여부
14. 한글 경로 문서와 DB/PNG/output 파일 미수정 확인
15. 코드 변경 여부
16. 커밋 여부
17. 남은 리스크
18. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER14-3D는 Weekly / Benchmark / Account Snapshot의 실제 Notion export 검증이며, Daily Plan export, Daily Review export, Performance Summary export, Manual Review 입력 연동은 포함하지 않는다.
p```
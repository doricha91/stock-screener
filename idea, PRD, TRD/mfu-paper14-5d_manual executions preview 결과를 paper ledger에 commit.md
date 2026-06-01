# MFU-PAPER14-5D 작업 지시문: Manual Executions preview 결과를 paper ledger에 commit

## 목적

MFU-PAPER14-5D의 목표는 PAPER14-5C에서 생성한 Manual Executions preview 결과를 사용자가 승인한 경우 `paper_execution_log.csv`에 commit하고, 기존 paper state 갱신 흐름과 연결하는 것이다.

이번 작업은 Notion 입력값을 직접 원장에 쓰는 것이 아니라, preview JSON을 기준으로 검증된 candidate만 commit한다.

반드시 명시:

이번 PAPER14-5D는 Manual Executions preview 결과를 paper execution ledger에 commit하는 작업이며, Notion status back-write, Daily Review Summary export, broker/API 연동은 수행하지 않는다.

---

## 기준 커밋

기준 커밋 / 베이스라인:

```text
ffd2350f5933376f4bc2b9fec26901d76f0b797d
```

최근 로그에 아래 커밋들이 있어야 한다.

```text
2b380c9 PAPER14-5B: document Manual Executions schema and views
e63a2f2 PAPER14-5C: add Manual Executions import preview
```

작업 전 확인:

```cmd
cd /d D:\python\StockScreener
git rev-parse HEAD
git log --oneline -8
git status --short
```

기준 SHA 이후 상태가 아니면 작업을 중단하고 보고한다.

---

## 배경

PAPER14-5C에서 아래가 구현됐다.

```text
Notion Manual Executions read-only query
normalization
validation
preview markdown/json 생성
```

실제 preview 예시:

```text
candidate_count = 1
fail_count = 0
warning_count = 1
commit_allowed = true_with_warnings
projected_cash_start = 60344.67
projected_cash_end = 60244.67
projected_position_impact = {"AAPL": 1}
```

이번 5D에서는 preview 결과를 기반으로 paper ledger에 commit한다.

핵심 원칙:

```text
Notion = 입력 대기 / staging layer
Preview JSON = commit 기준 artifact
CSV / SQLite = 최종 source of truth
```

---

## 구현 파일

수정/추가 후보:

```text
core/notion_manual_execution_importer.py
core/paper_manual_execution_commit.py
core/paper_execution_log.py
core/paper_account_state.py
scripts/import_notion_executions.py
tests/test_notion_manual_execution_importer.py
tests/test_paper_manual_execution_commit.py
docs/TRD/mfu_paper14_5d_manual_execution_commit.md
```

가능하면 기존 helper를 사용한다.  
`paper_execution_log.csv`를 ad-hoc으로 직접 조작하지 않는다.

---

## Commit CLI

기존 script에 commit 옵션을 구현한다.

```cmd
python scripts\import_notion_executions.py --date 2026-05-25 --preview --json
python scripts\import_notion_executions.py --date 2026-05-25 --commit --preview-json outputs\paper_test\reports\manual_execution_import_preview_20260525.json
```

WARNING이 있는 preview는 기본 commit 금지.

WARNING 포함 commit은 명시 옵션이 필요하다.

```cmd
python scripts\import_notion_executions.py --date 2026-05-25 --commit --preview-json outputs\paper_test\reports\manual_execution_import_preview_20260525.json --allow-warnings
```

정책:

```text
fail_count > 0이면 commit 금지
commit_allowed=false이면 commit 금지
commit_allowed=true_with_warnings이면 --allow-warnings 없이는 commit 금지
preview JSON이 없으면 commit 금지
preview date와 --date가 다르면 commit 금지
```

---

## Commit 대상

preview JSON의 candidates 중 아래 조건을 만족하는 row만 commit한다.

```text
validation_status = PASS 또는 WARNING
Status = READY 기준으로 preview된 row
fail severity 없음
```

Notion을 다시 읽어서 commit하지 않는다.  
commit은 preview JSON을 기준으로 한다.

Notion row가 수정됐다면 preview를 다시 생성해야 한다.

---

## Ledger mapping

Manual Execution candidate → `paper_execution_log.csv`

```text
execution_date -> date
symbol -> symbol
side -> side
quantity -> shares
actual_price -> price
note -> notes
source -> notion_manual_execution
reason -> manual_execution_import
```

shares 정책:

```text
BUY = positive shares
SELL = negative shares
```

trade_id는 기존 `paper_execution_log` 규칙과 충돌하지 않도록 기존 helper/규칙을 사용한다.  
중복 trade_id가 이미 있으면 commit 금지 또는 SKIPPED 처리한다.

---

## Commission / Currency / Broker 저장 정책

사용자 결정:

```text
commission / currency / broker는 paper_execution_log.csv schema를 확장하지 않는다.
notes에 억지로 넣지 않는다.
sidecar JSON/report에 보존한다.
```

sidecar artifact 후보:

```text
outputs/paper_test/reports/manual_execution_import_commit_YYYYMMDD.json
outputs/paper_test/reports/manual_execution_import_commit_YYYYMMDD.md
```

sidecar에 포함할 것:

```text
canonical_key
page_id
commission
currency
broker
validation warnings
preview_json_path
committed trade_id
```

---

## Paper current state 갱신

commit 후 기존 paper state 갱신 흐름을 사용한다.

확인 대상:

```text
scripts/run_paper_eod_update.py
core/paper_account_state.py
core/paper_execution_log.py
scripts/paper.py commit 관련 흐름
```

목표:

```text
paper_execution_log.csv append
paper_account_snapshot.csv 갱신
paper_position_snapshot.csv 갱신
```

기존 state refresh 경로가 명확하면 사용한다.  
불명확하면 ad-hoc 구현하지 말고 `paper_execution_log.csv commit까지만 구현`하고 state refresh 미완료로 보고한다.

---

## Backup / safety

commit 전 원장 백업을 만든다.

예:

```text
outputs/dev_backups/paper_execution_log_before_manual_execution_commit_YYYYMMDD_HHMMSS.csv
outputs/dev_backups/paper_account_snapshot_before_manual_execution_commit_YYYYMMDD_HHMMSS.csv
outputs/dev_backups/paper_position_snapshot_before_manual_execution_commit_YYYYMMDD_HHMMSS.csv
```

정책:

```text
CSV write는 가능하면 atomic write
commit 실패 시 부분 write 방지
중복 commit 방지
```

---

## Notion write 금지

이번 5D에서 하지 않는다.

```text
Validation Status back-write
Validation Message back-write
Import Status back-write
Imported At back-write
Synced At back-write
```

위 작업은 PAPER14-5E로 분리한다.

---

## 테스트 요구사항

추가/수정 테스트:

```text
tests/test_paper_manual_execution_commit.py
tests/test_notion_manual_execution_importer.py
```

검증할 것:

```text
1. FAIL preview는 commit 거부
2. WARNING preview는 --allow-warnings 없으면 commit 거부
3. WARNING preview는 --allow-warnings 있으면 commit 가능
4. BUY는 positive shares로 ledger row 생성
5. SELL은 negative shares로 ledger row 생성
6. 중복 trade_id는 commit 거부 또는 SKIPPED
7. commission/currency/broker는 sidecar에 보존
8. paper_execution_log schema는 확장하지 않음
9. Notion write/back-write는 호출하지 않음
10. 기존 5C preview 기능은 깨지지 않음
```

---

## 검증 명령

Windows CMD 기준:

```cmd
cd /d D:\python\StockScreener
set PYTHONPATH=.

python -m py_compile core\notion_manual_execution_importer.py
python -m py_compile core\paper_manual_execution_commit.py
python -m py_compile scripts\import_notion_executions.py

python -m pytest tests\test_notion_manual_execution_importer.py tests\test_paper_manual_execution_commit.py -q
python -m pytest tests\test_notion_client.py tests\test_notion_schema_validator.py tests\test_notion_exporters.py tests\test_notion_settings.py tests\test_notion_mapping.py -q
```

실제 preview 재생성:

```cmd
python scripts\import_notion_executions.py --date 2026-05-25 --preview --json
```

실제 commit 검증은 backup 생성 후 수행한다.

WARNING이 있는 경우:

```cmd
python scripts\import_notion_executions.py --date 2026-05-25 --commit --preview-json outputs\paper_test\reports\manual_execution_import_preview_20260525.json --allow-warnings
```

commit 후 상태 확인:

```cmd
python scripts\import_notion_executions.py --date 2026-05-25 --preview --json
```

중복 방지가 작동해 같은 preview를 다시 commit하지 않아야 한다.

---

## 허용되는 변경

이번 작업에서는 아래 파일 변경이 허용된다.

```text
outputs/paper_test/paper_execution_log.csv
outputs/paper_test/paper_account_snapshot.csv
outputs/paper_test/paper_position_snapshot.csv
outputs/paper_test/reports/manual_execution_import_commit_YYYYMMDD.json
outputs/paper_test/reports/manual_execution_import_commit_YYYYMMDD.md
outputs/dev_backups/*
```

단, 코드 커밋에는 원장 CSV / output 산출물 / backup 파일을 포함하지 않는다.

---

## 금지 사항

```text
Notion status back-write 금지
Daily Review Summary export 구현 금지
Performance Summary export 구현 금지
Manual Review 입력 연동 구현 금지
broker/API 연동 금지
paper_execution_log.csv schema 확장 금지
commission/currency/broker dedicated column 추가 금지
Notion DB schema 변경 금지
git add . 금지
git add -A 금지
```

---

## 문서화

추가 문서:

```text
docs/TRD/mfu_paper14_5d_manual_execution_commit.md
```

포함 내용:

```text
preview 기반 commit 원칙
WARNING 처리 정책
sidecar 보존 정책
ledger mapping
state refresh 정책
Notion back-write 제외
실패/중복 방지 정책
```

---

## 커밋 정책

코드와 문서만 커밋한다.

권장 stage 예:

```cmd
git add core\notion_manual_execution_importer.py
git add core\paper_manual_execution_commit.py
git add scripts\import_notion_executions.py
git add tests\test_notion_manual_execution_importer.py
git add tests\test_paper_manual_execution_commit.py
git add docs\TRD\mfu_paper14_5d_manual_execution_commit.md
git diff --cached --name-only
```

원장 CSV, output, backup 파일은 stage하지 않는다.

커밋 메시지:

```cmd
git commit -m "PAPER14-5D: commit Manual Executions preview to paper ledger"
```

---

## 성공 기준

```text
preview JSON 기반 commit이 가능하다.
FAIL preview는 commit되지 않는다.
WARNING preview는 --allow-warnings가 있어야 commit된다.
paper_execution_log.csv에 수동 체결 row가 반영된다.
paper current state 갱신 경로가 확인되거나, 미완료로 명확히 보고된다.
commission/currency/broker는 sidecar에 보존된다.
paper_execution_log.csv schema는 확장하지 않는다.
Notion status back-write는 수행하지 않는다.
중복 commit이 방지된다.
테스트가 통과한다.
```

---

## 결과 보고 형식

5천자 이내.

```text
1. Summary
2. 기준 커밋 확인 결과
3. 변경 파일
4. 추가된 commit CLI
5. preview JSON 기준 commit 정책
6. WARNING 처리 정책
7. ledger mapping
8. commission/currency/broker sidecar 보존 결과
9. paper_execution_log.csv 반영 결과
10. paper current state 갱신 결과
11. 중복 commit 방지 결과
12. Notion back-write 미수행 확인
13. 테스트 결과
14. 커밋 hash와 message
15. stage하지 않은 output/CSV/backup 파일
16. 남은 리스크
17. 다음 MFU 제안
```

반드시 명시:

이번 PAPER14-5D는 Manual Executions preview 결과를 paper execution ledger에 commit하는 작업이며, Notion status back-write, Daily Review Summary export, broker/API 연동은 수행하지 않았다.
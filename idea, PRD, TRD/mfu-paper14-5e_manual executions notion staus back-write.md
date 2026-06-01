# MFU-PAPER14-5E 작업 지시문: Manual Executions Notion status back-write

## 목적

PAPER14-5D에서 paper ledger에 commit된 Manual Execution 결과를 Notion Manual Executions DB에 상태값으로 되돌려 쓴다.

이번 작업은 Notion status back-write 단계다.

반드시 명시:

```text
이번 PAPER14-5E는 Manual Execution commit 결과를 Notion Manual Executions row에 상태값으로 back-write하는 작업이며, paper ledger commit, Daily Review Summary export, broker/API 연동은 수행하지 않는다.
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
```

작업 전 확인:

```cmd
cd /d D:\python\StockScreener
git rev-parse HEAD
git log --oneline -10
git status --short
```

기준 SHA 이후 상태가 아니면 중단하고 보고한다.

---

## 배경

PAPER14-5D에서는 preview JSON을 기준으로 Manual Execution을 `paper_execution_log.csv`에 commit했다.

5D / 5D-2 이후 commit 세트:

```text
paper_execution_log.csv
paper_account_snapshot.csv
paper_position_snapshot.csv
paper_current_state_YYYYMMDD.json
```

5D에서 Notion back-write는 제외했다.

따라서 현재 Notion Manual Executions row는 Python ledger에는 반영됐어도 Notion 화면에서는 여전히 `READY` 또는 이전 상태로 보일 수 있다.

이번 5E에서 그 불일치를 해소한다.

---

## 구현 파일

수정/추가 후보:

```text
core/notion_client.py
core/notion_manual_execution_status_sync.py
scripts/sync_notion_execution_status.py
tests/test_notion_client.py
tests/test_notion_manual_execution_status_sync.py
docs/TRD/mfu_paper14_5e_notion_execution_status_sync.md
```

가능하면 기존 `import_notion_executions.py`에 섞지 말고, 별도 스크립트로 시작한다.

---

## 입력 artifact

5D commit sidecar JSON을 status sync 기준 artifact로 사용한다.

예:

```text
outputs/paper_test/reports/manual_execution_import_commit_20260525.json
```

원칙:

```text
Notion을 다시 query해서 commit 여부를 판단하지 않는다.
5D commit sidecar에 기록된 committed row만 back-write한다.
page_id가 없는 row는 back-write하지 않고 WARNING으로 보고한다.
```

---

## CLI

새 스크립트 후보:

```cmd
python scripts\sync_notion_execution_status.py --date 2026-05-25 --commit-report outputs\paper_test\reports\manual_execution_import_commit_20260525.json --dry-run --json
python scripts\sync_notion_execution_status.py --date 2026-05-25 --commit-report outputs\paper_test\reports\manual_execution_import_commit_20260525.json --json
```

정책:

```text
--dry-run에서는 Notion write 금지
non-dry-run에서만 Notion page property update 수행
paper ledger 파일은 절대 수정하지 않음
```

---

## Back-write 대상 필드

Manual Executions row의 아래 속성만 업데이트한다.

```text
External Key
Validation Status
Validation Message
Import Status
Imported At
Synced At
Status
```

권장 값:

```text
External Key = candidate.canonical_key
Validation Status = PASS 또는 WARNING
Validation Message = validation warnings 요약
Import Status = COMMITTED
Imported At = commit 완료 시각 또는 sync 실행 시각
Synced At = sync 실행 시각
Status = IMPORTED
```

주의:

```text
Execution Date / Symbol / Side / Quantity / Actual Price / Commission / Currency / Broker / Note는 수정하지 않는다.
```

---

## Validation Message 정책

WARNING이 있으면 사람이 읽을 수 있게 요약한다.

예:

```text
missing_commission: Commission is blank; normalized to 0.
missing_currency: Currency is blank; normalized to USD.
```

WARNING이 없으면 빈 문자열 또는 `OK` 중 하나로 통일한다.  
권장: `OK`

---

## Sync 대상 정책

commit report에서 아래 조건을 만족하는 row만 sync한다.

```text
committed_trade_id 존재
page_id 존재
canonical_key 존재
```

제외:

```text
commit 실패 row
skipped row
page_id 없는 row
이미 COMMITTED인지 여부는 이번 단계에서 Notion query로 판단하지 않음
```

동일 report를 다시 sync해도 같은 값으로 update되므로 idempotent해야 한다.

---

## Notion 설정

환경변수:

```env
NOTION_MANUAL_EXECUTIONS_DATA_SOURCE_ID=...
```

다만 page update는 page_id 기준으로 수행하므로 data source id는 validation 또는 safety check 용도로만 사용해도 된다.

토큰:

```env
NOTION_TOKEN=...
```

토큰과 실제 data source id를 로그에 노출하지 않는다.

---

## 실패 처리

```text
Notion page update 실패 시 해당 row를 FAILED로 결과 보고
일부 row 실패 시 overall_status = PARTIAL_SUCCESS 또는 FAILED
실패해도 paper ledger rollback은 하지 않음
```

이유:

```text
5E는 ledger commit 이후 표시 상태 동기화 단계다.
Notion sync 실패는 ledger commit 실패가 아니다.
```

---

## 테스트 요구사항

추가/수정 테스트:

```text
tests/test_notion_manual_execution_status_sync.py
tests/test_notion_client.py
```

검증할 것:

```text
1. commit report에서 page_id / canonical_key / committed_trade_id를 읽는다.
2. dry-run에서는 Notion update를 호출하지 않는다.
3. non-dry-run에서는 page property update를 호출한다.
4. External Key / Validation Status / Validation Message / Import Status / Imported At / Synced At / Status payload가 맞다.
5. Execution Date / Symbol / Quantity / Actual Price 등 입력값은 수정하지 않는다.
6. page_id 없는 row는 skip 또는 warning 처리한다.
7. 일부 update 실패 시 partial result를 반환한다.
8. paper ledger 파일은 수정하지 않는다.
```

---

## 검증 명령

Windows CMD 기준:

```cmd
cd /d D:\python\StockScreener
set PYTHONPATH=.

python -m py_compile core\notion_manual_execution_status_sync.py
python -m py_compile scripts\sync_notion_execution_status.py

python -m pytest tests\test_notion_manual_execution_status_sync.py tests\test_notion_client.py -q
python -m pytest tests\test_paper_manual_execution_commit.py tests\test_notion_manual_execution_importer.py -q
```

dry-run:

```cmd
python scripts\sync_notion_execution_status.py --date 2026-05-25 --commit-report outputs\paper_test\reports\manual_execution_import_commit_20260525.json --dry-run --json
```

실제 Notion back-write는 사용자가 허용한 경우에만 실행한다.

```cmd
python scripts\sync_notion_execution_status.py --date 2026-05-25 --commit-report outputs\paper_test\reports\manual_execution_import_commit_20260525.json --json
```

---

## 금지 사항

```text
paper_execution_log.csv 수정 금지
paper_account_snapshot.csv 수정 금지
paper_position_snapshot.csv 수정 금지
paper_current_state_YYYYMMDD.json 수정 금지
Manual Execution commit 재실행 금지
Daily Review Summary export 구현 금지
Performance Summary export 구현 금지
broker/API 연동 금지
Notion DB schema 변경 금지
git add . 금지
git add -A 금지
```

---

## 문서화

추가 문서:

```text
docs/TRD/mfu_paper14_5e_notion_execution_status_sync.md
```

포함 내용:

```text
목적
5D commit report 기반 sync 원칙
back-write 대상 필드
수정하지 않는 필드
dry-run 정책
실패 처리 정책
ledger rollback을 하지 않는 이유
Notion sync 실패 시 운영 대응
```

필요하면 5D 문서에 짧은 참조만 추가한다.

---

## 커밋 정책

코드와 문서만 커밋한다.

권장 stage:

```cmd
git add core\notion_manual_execution_status_sync.py
git add scripts\sync_notion_execution_status.py
git add tests\test_notion_manual_execution_status_sync.py
git add tests\test_notion_client.py
git add docs\TRD\mfu_paper14_5e_notion_execution_status_sync.md
git diff --cached --name-only
```

커밋 메시지:

```cmd
git commit -m "PAPER14-5E: sync Manual Execution status back to Notion"
```

output / CSV / backup 파일은 커밋하지 않는다.

---

## 성공 기준

```text
5D commit report를 기준으로 Notion Manual Executions row 상태를 업데이트할 수 있다.
dry-run은 Notion write를 하지 않는다.
non-dry-run에서 Status=IMPORTED, Import Status=COMMITTED로 업데이트된다.
External Key, Validation Status, Validation Message, Imported At, Synced At이 업데이트된다.
입력 원본 필드는 수정하지 않는다.
paper ledger 파일은 수정하지 않는다.
일부 Notion update 실패 시 명확한 실패/partial 결과를 보고한다.
테스트가 통과한다.
```

---

## 결과 보고 형식

5천자 이내.

```text
1. Summary
2. 기준 커밋 확인 결과
3. 변경 파일
4. 추가된 CLI
5. commit report 기반 sync 정책
6. back-write 대상 필드
7. 수정하지 않는 필드
8. dry-run 결과
9. actual Notion back-write 수행 여부
10. Notion UI 확인 결과
11. paper ledger 수정 여부
12. 테스트 결과
13. 커밋 hash와 message
14. stage하지 않은 output 파일
15. 남은 리스크
16. 다음 MFU 제안
```

반드시 명시:

```text
이번 PAPER14-5E는 Manual Execution commit 결과를 Notion Manual Executions row에 status back-write하는 작업이며, paper ledger commit, Daily Review Summary export, broker/API 연동은 수행하지 않았다.
```
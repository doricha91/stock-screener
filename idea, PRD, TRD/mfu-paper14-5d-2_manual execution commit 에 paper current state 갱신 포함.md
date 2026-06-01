# MFU-PAPER14-5D-2 작업 지시문: Manual Execution commit에 paper_current_state 갱신 포함

## 목적

Manual Executions commit 이후 `paper_current_state_YYYYMMDD.json`도 함께 갱신되도록 수정한다.

이번 작업은 PAPER14-5D-1 권고안인 “권고 A: 5D commit 흐름에 포함”을 구현하는 작업이다.

반드시 명시:

```text
이번 PAPER14-5D-2는 Manual Execution commit 세트에 paper_current_state_YYYYMMDD.json 갱신을 포함하는 작업이며, Notion status back-write, Daily Review Summary export, broker/API 연동은 수행하지 않는다.
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
50232fd PAPER14-5D: assess paper current state refresh policy
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

PAPER14-5D에서는 Manual Executions preview 결과를 `paper_execution_log.csv`에 commit했고, 아래는 갱신됐다.

```text
paper_execution_log.csv
paper_account_snapshot.csv
paper_position_snapshot.csv
```

하지만 아래 파일은 갱신하지 않았다.

```text
paper_current_state_YYYYMMDD.json
```

5D-1 조사 결과, `paper_current_state_YYYYMMDD.json`은 execution log에서 파생되는 derived snapshot이지만, status / weekly completeness / commit guard에서 같은 날짜 commit 세트의 일부로 취급된다.

따라서 Manual Execution commit 후에도 기존 EOD commit semantics와 맞게 current_state를 함께 저장해야 한다.

---

## 구현 파일

수정 후보:

```text
core/paper_manual_execution_commit.py
core/paths.py
core/paper_current_state_storage.py
core/paper_account_state.py
scripts/import_notion_executions.py
tests/test_paper_manual_execution_commit.py
docs/TRD/mfu_paper14_5d_manual_execution_commit.md
```

필요 시 참조:

```text
scripts/run_paper_eod_update.py
core/paper_current_state_serializer.py
core/paper_state_provider.py
```

---

## 구현 요구사항

### 1. current_state 생성 경로 재사용

기존 공식 생성 흐름을 재사용한다.

조사 결과 기준 흐름:

```text
paper_execution_log.csv 읽기
→ build_paper_state_from_trades()
→ save_paper_current_state()
→ paper_current_state_YYYYMMDD.json 저장
```

새로운 임의 JSON schema를 만들지 않는다.  
기존 serializer/storage helper를 사용한다.

### 2. Manual Execution commit 세트 확장

Manual Execution commit 성공 후 아래 4종이 같은 commit 결과 세트로 맞아야 한다.

```text
paper_execution_log.csv
paper_account_snapshot.csv
paper_position_snapshot.csv
paper_current_state_YYYYMMDD.json
```

### 3. backup 범위 확장

commit 전 backup 대상에 current_state도 포함한다.

```text
paper_execution_log.csv
paper_account_snapshot.csv
paper_position_snapshot.csv
paper_current_state_YYYYMMDD.json
```

기존 current_state 파일이 없으면 “없음” 상태도 안전하게 처리한다.

### 4. 실패 처리

current_state 저장 실패 시 commit 결과를 실패로 처리하거나, 최소한 명확히 실패 보고한다.

가능하면 partial write를 피한다.

주의:

```text
current_state 실패를 조용히 무시하지 않는다.
```

### 5. Notion back-write 제외

이번 작업에서 아래는 하지 않는다.

```text
Validation Status back-write
Validation Message back-write
Import Status back-write
Imported At back-write
Synced At back-write
```

이 작업은 PAPER14-5E로 분리한다.

---

## 테스트 요구사항

추가/수정 테스트:

```text
tests/test_paper_manual_execution_commit.py
```

검증할 것:

```text
1. Manual Execution commit 성공 시 save_paper_current_state가 호출된다.
2. current_state output path가 commit date 기준으로 생성된다.
3. backup 대상에 current_state가 포함된다.
4. 기존 current_state가 없어도 commit 흐름이 안전하게 동작한다.
5. current_state 저장 실패 시 실패로 보고된다.
6. paper_execution_log.csv schema는 확장하지 않는다.
7. commission/currency/broker는 기존처럼 sidecar에만 보존된다.
8. Notion back-write는 호출하지 않는다.
9. 중복 commit 방지 동작은 유지된다.
```

---

## 검증 명령

Windows CMD 기준:

```cmd
cd /d D:\python\StockScreener
set PYTHONPATH=.

python -m py_compile core\paper_manual_execution_commit.py
python -m py_compile scripts\import_notion_executions.py

python -m pytest tests\test_paper_manual_execution_commit.py tests\test_notion_manual_execution_importer.py -q
python -m pytest tests\test_notion_client.py tests\test_notion_schema_validator.py tests\test_notion_exporters.py tests\test_notion_settings.py tests\test_notion_mapping.py -q
```

실환경 검증은 새 테스트 row 또는 별도 날짜로 수행한다.  
이미 commit된 2026-05-25 AAPL row를 중복 commit하지 않는다.

필요 시 preview만 실행한다.

```cmd
python scripts\import_notion_executions.py --date 2026-05-25 --preview --json
```

---

## 허용되는 output 변경

실환경 commit 검증을 수행하는 경우 아래 output 변경은 발생할 수 있다.

```text
outputs/paper_test/paper_execution_log.csv
outputs/paper_test/paper_account_snapshot.csv
outputs/paper_test/paper_position_snapshot.csv
outputs/paper_test/paper_current_state_YYYYMMDD.json
outputs/paper_test/reports/manual_execution_import_commit_YYYYMMDD.json
outputs/paper_test/reports/manual_execution_import_commit_YYYYMMDD.md
outputs/dev_backups/*
```

단, output / CSV / backup 파일은 git commit에 포함하지 않는다.

---

## 금지 사항

```text
Notion status back-write 금지
Daily Review Summary export 구현 금지
Performance Summary export 구현 금지
Manual Review 입력 연동 금지
broker/API 연동 금지
paper_execution_log.csv schema 확장 금지
commission/currency/broker dedicated column 추가 금지
Notion DB schema 변경 금지
이미 commit된 동일 preview 재commit 금지
git add . 금지
git add -A 금지
```

---

## 문서화

수정:

```text
docs/TRD/mfu_paper14_5d_manual_execution_commit.md
```

추가할 내용:

```text
- current_state도 Manual Execution commit 세트에 포함
- 5D-1 권고 반영
- backup 범위 4종으로 확장
- current_state는 source of truth가 아니라 execution log 파생 산출물
- Notion back-write는 여전히 5E로 분리
```

필요 시 5D-1 문서에는 짧은 참조만 추가한다.

---

## 커밋 정책

코드와 문서만 커밋한다.

권장 stage:

```cmd
git add core\paper_manual_execution_commit.py
git add scripts\import_notion_executions.py
git add tests\test_paper_manual_execution_commit.py
git add docs\TRD\mfu_paper14_5d_manual_execution_commit.md
git diff --cached --name-only
```

커밋 메시지:

```cmd
git commit -m "PAPER14-5D: refresh current state after manual execution commit"
```

---

## 성공 기준

```text
Manual Execution commit 후 paper_current_state_YYYYMMDD.json이 갱신된다.
current_state 갱신은 기존 helper/schema를 재사용한다.
backup 범위가 execution/account/position/current_state 4종으로 확장된다.
current_state 저장 실패가 명확히 실패로 처리된다.
paper_execution_log.csv schema는 확장하지 않는다.
Notion back-write는 수행하지 않는다.
테스트가 통과한다.
output/CSV/backup 파일은 커밋하지 않는다.
```

---

## 결과 보고 형식

5천자 이내.

```text
1. Summary
2. 기준 커밋 확인 결과
3. 변경 파일
4. current_state 갱신 구현 내용
5. 기존 helper 재사용 여부
6. backup 범위 변경
7. 실패 처리 정책
8. 실환경 commit 검증 여부
9. paper_current_state 생성 결과
10. Notion back-write 미수행 확인
11. 테스트 결과
12. 커밋 hash와 message
13. stage하지 않은 output/CSV/backup 파일
14. 남은 리스크
15. 다음 MFU 제안
```
BEGIN MFU-PAPER15-3E-4D_IMPORT_COMMIT_SYNC_CONTRACT_TEST

# MFU-PAPER15-3E-4D 작업 지시문: Importer → Commit/Append → Status Sync Contract Test

## 목적

MFU-PAPER15-3E-4D의 목표는 Manual Execution / Manual Review의 account-aware namespace가 아래 흐름에서 끊기지 않는지 contract test로 검증하는 것이다.

```text
Notion importer preview
→ commit/append sidecar report
→ status sync payload
```

이번 단계는 테스트 중심 작업이다.  
writer path 적용, non-default commit/append 허용, Notion actual sync/write, Notion row migration, paper 원장 migration은 하지 않는다.

반드시 명시:

```text
이번 PAPER15-3E-4D는 importer preview → commit/append report → status sync payload의 account namespace contract test이며, writer path 적용, non-default commit/append 허용, Notion actual sync/write, Notion row migration, paper 원장 migration은 포함하지 않는다.
```

## 배경

이전 단계에서 아래가 완료됐다.

```text
PAPER15-3E-4A:
Manual Execution / Review importer preview가 account-aware canonical_key 생성

PAPER15-3E-4B:
Manual Execution / Review status sync가 account_id, Account ID property, account-aware External Key 처리

PAPER15-3E-4C:
Manual Execution commit report / Manual Review append report가 account_id, canonical_key, legacy_canonical_key, legacy_key_compatible를 포함
```

이번 단계에서는 세 계층이 서로 같은 payload contract를 공유하는지 end-to-end에 가까운 단위 테스트로 검증한다.

## 구현 범위

### 1. 테스트 파일 추가

새 테스트 파일 후보:

```text
tests/test_paper15_3e_4d_execution_contract.py
tests/test_paper15_3e_4d_review_contract.py
```

또는 하나로 통합:

```text
tests/test_paper15_3e_4d_import_commit_sync_contract.py
```

## 2. Manual Execution contract test

검증 흐름:

```text
1. fake Notion Manual Execution READY row 생성
2. importer preview 생성
3. preview candidate의 account_id / canonical_key / legacy_canonical_key 확인
4. tmp_path 기반으로 commit report sidecar 생성
5. commit report row의 account_id / canonical_key / legacy_canonical_key / legacy_key_compatible 확인
6. status sync property builder 또는 fake sync handler에 report row 전달
7. status sync payload의 Account ID / External Key가 commit report와 일치하는지 확인
```

필수 검증:

```text
account_id = paper_default
canonical_key = manual_execution:paper_default:{execution_date}:{symbol}:{side}:{sequence}
legacy_canonical_key = manual_execution:{execution_date}:{symbol}:{side}:{sequence}
legacy_key_compatible = true
External Key = account-aware canonical_key
Account ID = paper_default
```

## 3. Manual Review contract test

검증 흐름:

```text
1. fake Notion Manual Review READY row 생성
2. importer preview 생성
3. preview candidate의 account_id / canonical_key / legacy_canonical_key 확인
4. tmp_path 기반으로 append report sidecar 생성
5. append report row의 account_id / canonical_key / legacy_canonical_key / legacy_key_compatible 확인
6. status sync property builder 또는 fake sync handler에 report row 전달
7. status sync payload의 Account ID / External Key가 append report와 일치하는지 확인
```

필수 검증:

```text
account_id = paper_default
canonical_key = manual_review:paper_default:{review_date}:{symbol}:{question_id}
legacy_canonical_key = manual_review:{review_date}:{symbol}:{question_id}
legacy_key_compatible = true
External Key = account-aware canonical_key
Account ID = paper_default
```

## 4. non-default 안전성 test

non-default 계좌는 아직 commit/append를 열지 않는다.

테스트 항목:

```text
1. non-default importer preview는 Account ID == account_id row만 읽는다.
2. non-default preview candidate는 account-aware canonical_key를 가진다.
3. non-default commit/append 시도는 현재 guard 정책에 따라 실패한다.
4. non-default legacy-only report를 status sync에 넘기면 FAILED 또는 명확한 차단 결과가 나온다.
```

## 5. legacy paper_default 호환 test

기존 legacy row와 report를 계속 지원하는지 확인한다.

테스트 항목:

```text
1. paper_default preview query는 Account ID blank row를 허용한다.
2. legacy canonical_key만 있는 paper_default report는 account-aware canonical_key로 정규화된다.
3. status sync payload는 최종적으로 account-aware External Key를 쓴다.
```

## 6. 금지 사항

```text
writer path 적용 금지
non-default commit/append 허용 금지
core/paths.py writer path 변경 금지
Notion actual sync/write 실행 금지
Notion row migration script 작성 금지
paper 원장 CSV 실제 수정 금지
DB write 금지
outputs 하위 실제 운영 파일 수정 금지
실제 운영 commit/append 명령 실행 금지
git add . 금지
git add -A 금지
```

## 7. 허용 사항

```text
contract test 추가
tmp_path 기반 sidecar/report 생성
fake/mock Notion client 사용
pure function/property builder 검증
필요 최소한의 test helper 추가
TRD 문서 추가
pytest 실행
```

가능하면 production code 변경은 피한다.  
단, 테스트를 위해 과도한 중복이 발생하는 경우에만 작은 helper 추출을 허용하되, 기존 동작을 바꾸지 않는다.

## 산출물

예상 추가/수정 파일:

```text
tests/test_paper15_3e_4d_import_commit_sync_contract.py
```

필요 시:

```text
docs/TRD/mfu_paper15_3e_4d_import_commit_sync_contract_test.md
```

production code 변경이 발생한 경우 반드시 결과 보고에 이유를 적는다.

## 검증 명령

Windows CMD 기준:

```cmd
python -m pytest tests\test_paper15_3e_4d_import_commit_sync_contract.py
python -m pytest tests\test_notion_manual_execution_importer.py tests\test_notion_manual_review_importer.py
python -m pytest tests\test_paper_manual_execution_commit.py tests\test_paper_manual_review_append_commit.py
python -m pytest tests\test_notion_manual_execution_status_sync.py tests\test_notion_manual_review_status_sync.py
git diff -- tests\test_paper15_3e_4d_import_commit_sync_contract.py
git diff -- docs\TRD\mfu_paper15_3e_4d_import_commit_sync_contract_test.md
git status --short
```

실제 Notion sync/write와 실제 운영 commit/append 명령은 실행하지 않는다.

## 성공 기준

```text
Manual Execution importer preview → commit report → status sync payload contract가 검증된다.
Manual Review importer preview → append report → status sync payload contract가 검증된다.
account_id가 세 계층에서 유지된다.
account-aware canonical_key가 External Key로 이어진다.
paper_default legacy key가 account-aware key로 정규화된다.
non-default legacy-only report는 안전하게 차단된다.
non-default commit/append는 아직 열리지 않는다.
Notion actual sync/write, writer path, migration은 변경되지 않는다.
paper 원장, DB, outputs 실제 운영 파일은 수정되지 않는다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 생성/수정한 파일
3. Execution contract test 내용
4. Review contract test 내용
5. paper_default legacy 호환 검증
6. non-default 차단 검증
7. status sync payload 검증
8. 테스트 결과
9. production code 변경 여부
10. writer path 적용 여부
11. non-default commit/append 허용 여부
12. Notion actual sync/write 실행 여부
13. outputs 변경 여부
14. 다음 MFU 제안
```

반드시 명시:

```text
이번 PAPER15-3E-4D는 importer preview → commit/append report → status sync payload의 account namespace contract test이며, writer path 적용, non-default commit/append 허용, Notion actual sync/write, Notion row migration, paper 원장 migration은 포함하지 않는다.
```

END MFU-PAPER15-3E-4D_IMPORT_COMMIT_SYNC_CONTRACT_TEST
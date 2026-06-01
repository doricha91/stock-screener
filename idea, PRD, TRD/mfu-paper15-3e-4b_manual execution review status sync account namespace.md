BEGIN MFU-PAPER15-3E-4B_STATUS_SYNC_ACCOUNT_NAMESPACE

# MFU-PAPER15-3E-4B 작업 지시문: Manual Execution / Review Status Sync Account Namespace

## 목적

MFU-PAPER15-3E-4B의 목표는 Manual Execution / Manual Review status sync가 account-aware canonical key와 Account ID property를 처리하도록 맞추는 것이다.

이번 단계는 status sync namespace 정합성 구현에 한정한다.  
Manual Execution commit, Manual Review append, writer path 적용, Notion row migration preview는 하지 않는다.

반드시 명시:

```text
이번 PAPER15-3E-4B는 Manual Execution / Review status sync의 account namespace 정합성 구현이며, commit/append 변경, writer path 적용, Notion row migration, paper 원장 수정은 포함하지 않는다.
```

## 배경

PAPER15-3E-4A에서 Manual Execution / Manual Review importer preview는 아래를 지원하게 됐다.

```text
--account-id
Account ID READY row filter
account-aware canonical_key
paper_default legacy_canonical_key
non-default commit/append 차단
```

하지만 status sync는 아직 account-less key 전제다.  
따라서 preview/commit report가 account-aware canonical key를 포함하는 경우, Notion row에 `External Key`와 `Account ID`를 올바르게 back-write할 수 있어야 한다.

## 구현 범위

### 1. 대상 파일

```text
core/notion_manual_execution_status_sync.py
core/notion_manual_review_status_sync.py
scripts/sync_notion_execution_status.py
scripts/sync_notion_review_status.py
core/notion_account_keys.py
tests/test_notion_manual_execution_status_sync.py
tests/test_notion_manual_review_status_sync.py
```

필요 시 추가:

```text
docs/TRD/mfu_paper15_3e_4b_status_sync_account_namespace.md
```

## 2. CLI에 --account-id 추가

아래 스크립트에 `--account-id`를 추가한다.

```text
scripts/sync_notion_execution_status.py
scripts/sync_notion_review_status.py
```

정책:

```text
--account-id 생략 시 paper_default
account_id는 validate_account_id 사용
commit report에 account_id가 있으면 CLI account_id와 일치해야 함
불일치 시 FAIL
legacy commit report에 account_id가 없으면 paper_default로 해석
```

## 3. status sync payload에 Account ID 추가

Manual Execution / Manual Review status back-write property에 아래를 추가한다.

```text
Account ID = account_id
External Key = account-aware canonical_key
```

Notion property type:

```text
Account ID: select
External Key: rich_text 기존 유지
```

수정 대상 property builder 후보:

```text
build_manual_execution_status_properties(...)
build_manual_review_status_properties(...)
```

주의:

```text
기존 Validation Status, Validation Message, Import Status, Imported At, Synced At 정책은 유지한다.
사용자 입력 필드인 Manual Answer, Review Status, Follow-up Needed 등은 수정하지 않는다.
```

## 4. account-aware canonical key 처리

Manual Execution:

```text
manual_execution:{account_id}:{execution_date}:{symbol}:{side}:{sequence}
```

Manual Review:

```text
manual_review:{account_id}:{review_date}:{symbol}:{question_id}
```

정책:

```text
- commit report row에 canonical_key가 있으면 우선 사용
- canonical_key가 legacy 형식이고 account_id=paper_default이면 legacy 호환으로 처리
- non-default account에서 legacy canonical_key만 있으면 차단 또는 FAILED 처리
- page_id가 있으면 기존처럼 page_id 기준 update
- page_id가 없으면 기존 정책대로 SKIPPED 처리
```

## 5. legacy paper_default 호환

기존 paper_default commit report를 깨지 않도록 한다.

정책:

```text
- account_id가 없는 commit report는 paper_default로 해석
- paper_default legacy canonical_key는 허용
- 단, 새 account-aware canonical_key가 있으면 그것을 External Key로 쓴다
- 이번 단계는 commit report에 포함된 page만 sync한다
- 기존 Notion row 전체 migration은 하지 않는다
```

## 6. sync result / dry-run 보강

sync result row와 summary에 아래를 포함한다.

```text
account_id
canonical_key
legacy_canonical_key, if available
legacy_key_compatible
updated_properties
```

dry-run에서는 Notion write를 호출하지 않고, 어떤 property가 업데이트될지만 보여준다.

## 7. 테스트

테스트 항목:

```text
1. execution status properties에 Account ID select 포함
2. review status properties에 Account ID select 포함
3. account-aware canonical_key가 External Key로 쓰임
4. paper_default legacy commit report 호환
5. non-default + legacy key only는 차단 또는 FAILED
6. CLI --account-id 생략 시 paper_default
7. CLI account_id와 report account_id 불일치 시 실패
8. dry-run은 Notion update_page를 호출하지 않음
9. 사용자 입력 필드는 수정하지 않음
10. 기존 account-less paper_default 테스트가 깨지지 않음
```

Notion API 실제 호출은 fake/mock client로만 검증한다.

## 산출물

예상 수정/추가 파일:

```text
core/notion_manual_execution_status_sync.py
core/notion_manual_review_status_sync.py
scripts/sync_notion_execution_status.py
scripts/sync_notion_review_status.py
tests/test_notion_manual_execution_status_sync.py
tests/test_notion_manual_review_status_sync.py
```

문서 추가:

```text
docs/TRD/mfu_paper15_3e_4b_status_sync_account_namespace.md
```

## 금지 사항

```text
Manual Execution commit 로직 변경 금지
Manual Review append 로직 변경 금지
writer path 적용 금지
Notion row migration script 작성 금지
Notion actual write/sync 실행 금지
paper 원장 CSV 수정 금지
DB write 금지
outputs 하위 파일 수정 금지
core/paths.py writer path 변경 금지
기존 Notion row bulk rewrite 금지
git add . 금지
git add -A 금지
```

## 허용 사항

```text
status sync property payload 보강
Account ID select property 추가
sync CLI --account-id 추가
dry-run summary 보강
fake/mock Notion client 테스트
TRD 문서 추가
pytest 실행
```

## 검증 명령

Windows CMD 기준:

```cmd
python -m pytest tests\test_notion_manual_execution_status_sync.py
python -m pytest tests\test_notion_manual_review_status_sync.py
python -m pytest tests\test_notion_manual_execution_importer.py tests\test_notion_manual_review_importer.py
python -m pytest tests\test_notion_account_keys.py tests\test_notion_mapping.py tests\test_notion_schema_validator.py
git diff -- core\notion_manual_execution_status_sync.py core\notion_manual_review_status_sync.py scripts\sync_notion_execution_status.py scripts\sync_notion_review_status.py
git diff -- docs\TRD\mfu_paper15_3e_4b_status_sync_account_namespace.md
git status --short
```

실제 Notion sync/write 명령은 실행하지 않는다.

## 성공 기준

```text
Execution status sync가 --account-id를 지원한다.
Review status sync가 --account-id를 지원한다.
Account ID property가 status back-write payload에 포함된다.
External Key가 account-aware canonical_key로 기록된다.
paper_default legacy commit report가 계속 호환된다.
non-default account에서 legacy-only key는 안전하게 차단된다.
dry-run은 Notion write 없이 결과를 보여준다.
commit/append, writer path, Notion migration은 변경되지 않는다.
paper 원장, DB, outputs는 수정되지 않는다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 생성/수정한 파일
3. 적용 대상 status sync
4. --account-id CLI 동작
5. Account ID property payload 처리
6. account-aware External Key 처리
7. legacy paper_default 호환 정책
8. non-default legacy key 차단 동작
9. dry-run summary 변경
10. 테스트 결과
11. commit/append 변경 여부
12. Notion actual sync 실행 여부
13. outputs 변경 여부
14. 다음 MFU 제안
```

반드시 명시:

```text
이번 PAPER15-3E-4B는 Manual Execution / Review status sync의 account namespace 정합성 구현이며, commit/append 변경, writer path 적용, Notion row migration, paper 원장 수정은 포함하지 않는다.
```

END MFU-PAPER15-3E-4B_STATUS_SYNC_ACCOUNT_NAMESPACE
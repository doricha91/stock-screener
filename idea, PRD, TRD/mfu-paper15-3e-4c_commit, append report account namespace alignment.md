BEGIN MFU-PAPER15-3E-4C_COMMIT_APPEND_REPORT_NAMESPACE_ALIGNMENT

# MFU-PAPER15-3E-4C 작업 지시문: Commit / Append Report Account Namespace Alignment

## 목적

MFU-PAPER15-3E-4C의 목표는 Manual Execution commit report와 Manual Review append commit report가 status sync가 기대하는 account-aware payload 형식과 정합되도록 맞추는 것이다.

이번 단계는 commit/append “report payload 정합성” 구현에 한정한다.  
writer path 적용, non-default commit/append 허용, Notion actual sync/write, Notion row migration, paper 원장 migration은 하지 않는다.

반드시 명시:

```text
이번 PAPER15-3E-4C는 Manual Execution commit report와 Manual Review append report의 account namespace 정합성 구현이며, writer path 적용, non-default commit/append 허용, Notion actual sync/write, Notion row migration, paper 원장 migration은 포함하지 않는다.
```

## 배경

PAPER15-3E-4A에서 importer preview는 account-aware canonical key를 생성한다.

```text
manual_execution:{account_id}:{execution_date}:{symbol}:{side}:{sequence}
manual_review:{account_id}:{review_date}:{symbol}:{question_id}
```

PAPER15-3E-4B에서 status sync는 아래 필드를 기대한다.

```text
account_id
canonical_key
legacy_canonical_key
legacy_key_compatible
updated_properties
```

이번 작업에서는 commit/append report가 위 형식을 안정적으로 제공하도록 맞춘다.

## 구현 범위

### 1. 대상 파일

```text
core/paper_manual_execution_commit.py
core/paper_manual_review_append_commit.py
scripts/import_notion_executions.py
scripts/import_notion_reviews.py
tests/test_paper_manual_execution_commit.py
tests/test_paper_manual_review_append_commit.py
tests/test_notion_manual_execution_status_sync.py
tests/test_notion_manual_review_status_sync.py
```

필요 시 추가:

```text
docs/TRD/mfu_paper15_3e_4c_commit_append_report_namespace_alignment.md
```

## 2. commit/append report payload 보강

Manual Execution commit report와 Manual Review append report의 row payload에 아래 필드를 포함한다.

```text
account_id
canonical_key
legacy_canonical_key
legacy_key_compatible
page_id
validation_status
commit_status 또는 append_status
```

정책:

```text
- preview payload에 account_id가 있으면 commit/append report에도 보존한다.
- preview payload에 account_id가 없으면 paper_default로 해석한다.
- account_id는 validate_account_id로 검증한다.
- canonical_key가 account-aware 형식이면 그대로 사용한다.
- paper_default legacy canonical_key만 있으면 account-aware canonical_key로 정규화한다.
- legacy_canonical_key는 paper_default 호환 목적일 때만 기록한다.
```

## 3. Manual Execution commit report 정합성

대상:

```text
core/paper_manual_execution_commit.py
```

정책:

```text
- commit JSON rows에 account_id 포함
- commit JSON rows에 account-aware canonical_key 포함
- legacy_canonical_key가 있으면 유지
- legacy_key_compatible boolean 포함
- status sync가 report만 보고 Account ID / External Key를 만들 수 있어야 함
```

주의:

```text
이번 단계에서 non-default execution commit을 허용하지 않는다.
non-default preview를 commit하려 하면 명확히 실패한다.
paper_default 기존 commit 호환성은 유지한다.
```

## 4. Manual Review append report 정합성

대상:

```text
core/paper_manual_review_append_commit.py
```

정책:

```text
- append commit JSON rows에 account_id 포함
- append commit JSON rows에 account-aware canonical_key 포함
- legacy_canonical_key가 있으면 유지
- legacy_key_compatible boolean 포함
- status sync가 report만 보고 Account ID / External Key를 만들 수 있어야 함
```

주의:

```text
이번 단계에서 non-default review append를 허용하지 않는다.
non-default preview를 append하려 하면 명확히 실패한다.
paper_default 기존 append 호환성은 유지한다.
```

## 5. legacy paper_default 호환

기존 legacy report를 깨지 않도록 한다.

정책:

```text
- account_id 없는 preview/report는 paper_default로 해석
- legacy key는 paper_default에서만 허용
- paper_default legacy key는 account-aware key로 정규화 가능
- non-default + legacy-only key는 실패
```

예:

```text
legacy:
manual_execution:2026-05-25:AAPL:BUY:01

normalized:
manual_execution:paper_default:2026-05-25:AAPL:BUY:01
```

## 6. status sync와의 contract 테스트

status sync가 commit/append report를 그대로 읽어도 동작하는지 contract 수준으로 검증한다.

테스트 방향:

```text
1. execution commit report row → execution status sync row parser/handler가 account_id 인식
2. review append report row → review status sync row parser/handler가 account_id 인식
3. account-aware canonical_key가 External Key로 쓰일 수 있음
4. paper_default legacy report도 정규화 가능
5. non-default legacy-only report는 실패
```

Notion actual sync는 실행하지 않는다. fake/mock client 또는 pure function 수준으로 검증한다.

## 7. CLI guard 유지

아래 기존 guard는 유지한다.

```text
import_notion_executions.py --commit --account-id paper_growth 차단
import_notion_reviews.py --commit --account-id paper_growth 차단
```

이번 단계에서 non-default commit/append를 열지 않는다.

## 금지 사항

```text
non-default commit/append 허용 금지
writer path 적용 금지
core/paths.py writer path 변경 금지
paper 원장 CSV 실제 수정 금지
실제 commit/append 명령 실행 금지
Notion actual sync/write 실행 금지
Notion row migration script 작성 금지
DB write 금지
outputs 하위 실제 운영 파일 수정 금지
git add . 금지
git add -A 금지
```

## 허용 사항

```text
commit/append report payload 생성 로직 수정
account_id/canonical_key 정규화 helper 추가
단위 테스트에서 tmp_path 기반 commit/append 검증
fake/mock status sync contract 테스트
TRD 문서 추가
pytest 실행
```

## 검증 명령

Windows CMD 기준:

```cmd
python -m pytest tests\test_paper_manual_execution_commit.py
python -m pytest tests\test_paper_manual_review_append_commit.py
python -m pytest tests\test_notion_manual_execution_status_sync.py
python -m pytest tests\test_notion_manual_review_status_sync.py
python -m pytest tests\test_notion_manual_execution_importer.py tests\test_notion_manual_review_importer.py
git diff -- core\paper_manual_execution_commit.py core\paper_manual_review_append_commit.py scripts\import_notion_executions.py scripts\import_notion_reviews.py
git diff -- docs\TRD\mfu_paper15_3e_4c_commit_append_report_namespace_alignment.md
git status --short
```

실제 Notion sync/write와 실제 운영 commit/append 명령은 실행하지 않는다.

## 성공 기준

```text
Manual Execution commit report row에 account_id가 포함된다.
Manual Execution commit report row에 account-aware canonical_key가 포함된다.
Manual Review append report row에 account_id가 포함된다.
Manual Review append report row에 account-aware canonical_key가 포함된다.
paper_default legacy preview/report는 계속 호환된다.
non-default legacy-only commit/append report는 실패한다.
status sync가 commit/append report payload를 그대로 사용할 수 있다.
non-default commit/append는 아직 열리지 않는다.
writer path, Notion actual sync/write, migration은 변경되지 않는다.
paper 원장, DB, outputs 실제 운영 파일은 수정되지 않는다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 생성/수정한 파일
3. Manual Execution commit report 변경
4. Manual Review append report 변경
5. account_id 처리 정책
6. account-aware canonical_key 정규화 정책
7. legacy paper_default 호환 정책
8. non-default legacy-only 차단 동작
9. status sync contract 검증
10. 테스트 결과
11. non-default commit/append 허용 여부
12. writer path 적용 여부
13. Notion actual sync/write 실행 여부
14. outputs 변경 여부
15. 다음 MFU 제안
```

반드시 명시:

```text
이번 PAPER15-3E-4C는 Manual Execution commit report와 Manual Review append report의 account namespace 정합성 구현이며, writer path 적용, non-default commit/append 허용, Notion actual sync/write, Notion row migration, paper 원장 migration은 포함하지 않는다.
```

END MFU-PAPER15-3E-4C_COMMIT_APPEND_REPORT_NAMESPACE_ALIGNMENT
BEGIN MFU-PAPER15-3F_WRITER_PATH_ACCOUNT_ROOT

# MFU-PAPER15-3F 작업 지시문: Writer Path Account-aware Root 적용

## 목적

MFU-PAPER15-3F의 목표는 paper writer / writer-like command가 account-aware root를 사용하도록 연결하는 것이다.

이번 단계는 local artifact writer 경로 적용에 한정한다.  
Notion actual sync/write, Notion row migration, broker/API, cloud runner는 포함하지 않는다.

반드시 명시:

```text
이번 PAPER15-3F는 local writer path를 account-aware root에 연결하는 작업이며, Notion actual sync/write, Notion row migration, broker/API, cloud runner, paper_default legacy migration은 포함하지 않는다.
```

## 배경

완료된 선행 작업:

```text
3A: account profile model / config skeleton
3B: account-aware path resolver
3C: read-only paper.py --account-id
3D: writer account guard
3E-4A: Manual Execution / Review importer account filter
3E-4B: status sync account namespace
3E-4C: commit/append report namespace alignment
3E-4D: importer → commit/append → status sync contract test
```

이제 non-default 계좌의 local writer를 `outputs/paper_accounts/{account_id}`로 연결할 수 있는 최소 기반이 마련됐다.

## 핵심 정책

```text
1. --account-id 생략 시 기존 paper_default legacy 운영을 유지한다.
2. paper_default writer는 이번 단계에서 기존 outputs/paper_test 경로를 유지한다.
3. non-default writer는 반드시 명시적 --account-id가 있어야 한다.
4. non-default writer는 outputs/paper_accounts/{account_id}/ 하위에만 쓴다.
5. non-default writer가 legacy outputs/paper_test에 쓰는 일은 없어야 한다.
6. non-default commit/append는 이번 단계에서 허용하되, account-aware root로만 허용한다.
7. Notion sync/write는 이번 단계에서 실행하지 않는다.
```

## 구현 범위

### 1. account-aware writer path 연결

아래 명령/스크립트가 `PaperAccountPaths`를 사용할 수 있게 한다.

```text
paper.py plan
paper.py eod
paper.py commit
paper.py review-append
scripts/import_notion_executions.py --commit
scripts/import_notion_reviews.py --commit
```

정책:

```text
account_id == paper_default:
  기존 legacy path 유지

account_id != paper_default:
  build_paper_account_paths(account_id, create=True)를 사용
  모든 output/write는 outputs/paper_accounts/{account_id}/ 하위로 제한
```

### 2. core writer 함수 account_paths 지원

필요한 writer 함수에 optional `account_paths=None`을 추가한다.

대상 후보:

```text
core/paper_manual_execution_commit.py
core/paper_manual_review_append_commit.py
core/paper_current_state_storage.py
core/paper_account_snapshot.py
core/paper_position_snapshot.py
core/daily_plan_generator.py
```

정책:

```text
account_paths is None:
  기존 core.paths 기반 동작 유지

account_paths provided:
  account_paths 하위 경로만 사용
```

기존 호출부가 깨지면 안 된다.

### 3. non-default writer guard 해제 조건

3D에서 non-default writer는 차단되어 있다. 이번 단계에서 아래 조건을 만족할 때만 허용한다.

```text
- --account-id가 명시됨
- account_id != paper_default
- account_id validation 통과
- PaperAccountPaths 생성 성공
- writer 대상 경로가 outputs/paper_accounts/{account_id}/ 하위임
```

위 조건을 만족하지 않으면 실패한다.

### 4. path safety check 추가

writer가 파일을 쓰기 전에 경로 안전성을 확인한다.

필수 조건:

```text
non-default writer target path는 반드시 account_paths.root 하위여야 한다.
non-default writer가 outputs/paper_test를 target으로 잡으면 FAIL.
paper_default legacy writer는 기존 outputs/paper_test 허용.
```

필요하면 helper 추가:

```text
assert_path_under_account_root(path, account_paths)
```

### 5. commit/append report 유지

3E-4C에서 맞춘 report contract를 유지한다.

필수 유지 필드:

```text
account_id
canonical_key
legacy_canonical_key
legacy_key_compatible
commit_status / append_status
page_id
```

non-default report에는 legacy-only key가 없어야 한다.

### 6. Notion 관련 범위

이번 단계에서 Notion actual sync/write는 하지 않는다.

허용:

```text
import_notion_executions.py --commit 이 local CSV/JSON에 쓰는 것
import_notion_reviews.py --commit 이 local review log에 쓰는 것
```

금지:

```text
sync_notion_execution_status.py actual sync 실행
sync_notion_review_status.py actual sync 실행
export_paper_to_notion.py actual write 실행
Notion row migration
```

## 테스트

테스트 추가/수정 후보:

```text
tests/test_paper_writer_account_paths.py
tests/test_paper_manual_execution_commit.py
tests/test_paper_manual_review_append_commit.py
tests/test_paper_cli_writer_account_guard.py
tests/test_paper15_3e_4d_import_commit_sync_contract.py
```

필수 테스트:

```text
1. paper_default writer는 기존 legacy path를 유지
2. non-default execution commit은 tmp_path account root 하위에만 write
3. non-default review append는 tmp_path account root 하위에만 write
4. non-default writer가 outputs/paper_test를 target으로 잡으면 실패
5. non-default commit report에 account_id와 account-aware canonical_key 포함
6. non-default append report에 account_id와 account-aware canonical_key 포함
7. paper_default legacy commit/append 호환 유지
8. --account-id 생략 시 기존 paper_default 동작 유지
9. invalid account_id 실패
10. 기존 read-only --account-id 테스트가 깨지지 않음
```

테스트는 반드시 tmp_path를 사용한다.  
실제 운영 `outputs/paper_accounts` 생성은 금지한다.

## 산출물

예상 수정/추가 파일:

```text
scripts/paper.py
scripts/import_notion_executions.py
scripts/import_notion_reviews.py
core/paper_account_guard.py
core/paper_manual_execution_commit.py
core/paper_manual_review_append_commit.py
core/paper_current_state_storage.py
core/paper_account_snapshot.py
core/paper_position_snapshot.py
tests/test_paper_writer_account_paths.py
```

필요 시 문서 추가:

```text
docs/TRD/mfu_paper15_3f_writer_path_account_root.md
```

## 금지 사항

```text
paper_default legacy 데이터를 outputs/paper_accounts/paper_default로 migration 금지
Notion actual sync/write 실행 금지
Notion row migration script 작성 금지
broker/API 연동 금지
cloud runner 작업 금지
DB schema 변경 금지
실제 운영 outputs/paper_accounts 자동 생성 금지
실제 운영 commit/append 명령 실행 금지
git add . 금지
git add -A 금지
```

## 허용 사항

```text
writer path account_paths 지원
non-default local writer 허용
tmp_path 기반 writer 테스트
path safety helper 추가
TRD 문서 추가
pytest 실행
```

## 검증 명령

Windows CMD 기준:

```cmd
python -m pytest tests\test_paper_writer_account_paths.py
python -m pytest tests\test_paper_manual_execution_commit.py tests\test_paper_manual_review_append_commit.py
python -m pytest tests\test_paper_cli_writer_account_guard.py
python -m pytest tests\test_paper15_3e_4d_import_commit_sync_contract.py
python -m pytest tests\test_paper_account_paths.py tests\test_paper_account_profile.py
git diff -- scripts\paper.py scripts\import_notion_executions.py scripts\import_notion_reviews.py
git diff -- core\paper_account_guard.py core\paper_manual_execution_commit.py core\paper_manual_review_append_commit.py
git diff -- docs\TRD\mfu_paper15_3f_writer_path_account_root.md
git status --short
```

실제 운영 writer 명령과 Notion actual sync/write는 실행하지 않는다.

## 성공 기준

```text
non-default writer가 outputs/paper_accounts/{account_id}/ 하위에만 쓴다.
paper_default writer는 기존 legacy path를 유지한다.
non-default Manual Execution commit이 account-aware root에서 동작한다.
non-default Manual Review append가 account-aware root에서 동작한다.
commit/append report contract가 유지된다.
non-default writer가 outputs/paper_test에 쓰는 경로는 차단된다.
기존 paper_default daily ops 호환성은 유지된다.
Notion actual sync/write, migration, broker/API는 변경되지 않는다.
실제 운영 outputs/paper_accounts는 생성되지 않는다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 생성/수정한 파일
3. writer path 적용 대상
4. paper_default legacy writer 정책
5. non-default writer root 정책
6. path safety check
7. Manual Execution commit 변경
8. Manual Review append 변경
9. report contract 유지 여부
10. 테스트 결과
11. Notion actual sync/write 실행 여부
12. 실제 운영 outputs/paper_accounts 생성 여부
13. 기존 paper_default 호환성
14. 다음 MFU 제안
```

반드시 명시:

```text
이번 PAPER15-3F는 local writer path를 account-aware root에 연결하는 작업이며, Notion actual sync/write, Notion row migration, broker/API, cloud runner, paper_default legacy migration은 포함하지 않는다.
```

END MFU-PAPER15-3F_WRITER_PATH_ACCOUNT_ROOT
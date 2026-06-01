BEGIN MFU-PAPER15-3D_WRITER_ACCOUNT_GUARD

# MFU-PAPER15-3D 작업 지시문: Writer Command Account Guard

## 목적

MFU-PAPER15-3D의 목표는 paper writer 또는 writer-like command가 다중계좌 구조에서 위험하게 실행되지 않도록 account guard를 추가하는 것이다.

이번 단계는 writer path 적용이 아니다.  
PAPER15-3F에서 writer path를 실제 account root에 연결하기 전, 먼저 writer command가 account context를 명확히 표시하고, non-default 계좌에 대한 위험한 write를 차단하는 안전장치를 만든다.

반드시 명시:

```text
이번 PAPER15-3D는 writer command account guard 구현이며, writer path 적용, DB schema 변경, paper 원장 migration, Notion external key 변경, Notion write/export 구조 변경은 포함하지 않는다.
```

## 배경

PAPER15-3C에서 아래 read-only 명령은 --account-id를 지원한다.

```text
paper.py status
paper.py weekly-status
paper.py benchmark
```

하지만 아래 writer/writer-like 명령은 아직 single-account path 전제다.

```text
paper.py plan
paper.py eod --commit
paper.py commit
paper.py review-append
import_notion_executions.py --commit
import_notion_reviews.py --commit
export_paper_to_notion.py actual write
sync_notion_execution_status.py actual sync
sync_notion_review_status.py actual sync
```

PAPER15-3F에서 writer path를 실제 account-aware root에 연결할 예정이므로, 이번 3D에서는 non-default writer 실행을 막고 paper_default legacy write만 명시적으로 허용하는 guard를 만든다.

## 구현 범위

### 1. writer account guard 모듈 추가

새 파일 후보:

```text
core/paper_account_guard.py
```

필수 함수 후보:

```text
resolve_writer_account_context(account_id: str | None = None) -> dict
guard_paper_writer_account(account_id: str | None = None, *, command_name: str, allow_non_default: bool = False) -> dict
format_writer_account_guard_message(context: dict) -> str
```

정책:

```text
- account_id 생략 시 paper_default
- account_id는 PAPER15-3A validation 사용
- paper_default는 허용
- non-default account는 기본 차단
- non-default를 허용하는 allow_non_default는 이번 단계에서 테스트 전용 또는 future hook으로만 둔다
- guard 결과에는 account_id, account_root, legacy_default_used, command_name, write_allowed, message를 포함한다
```

### 2. paper.py writer/writer-like 명령에 guard 연결

이번 단계에서 --account-id를 추가할 대상:

```text
paper.py plan
paper.py eod
paper.py commit
paper.py review-append
```

동작 정책:

```text
- --account-id 생략 시 paper_default로 해석
- paper_default writer는 기존 경로 동작을 유지하되 account guard message를 출력
- non-default account는 명확한 에러로 중단
- writer path는 아직 account root로 바꾸지 않는다
- 기존 core/paths.py writer path 반환값은 변경하지 않는다
```

주의:

```text
plan은 daily_action_plan 파일을 생성하므로 writer-like로 본다.
eod --dry-run은 원장 write는 아니지만 preview/report 생성 가능성이 있으므로 이번 단계에서는 eod 전체에 guard를 적용한다.
```

### 3. Notion commit/sync/export script guard는 설계만 문서화

이번 3D에서 아래 스크립트는 코드 변경하지 않는다.

```text
scripts/export_paper_to_notion.py
scripts/import_notion_executions.py
scripts/import_notion_reviews.py
scripts/sync_notion_execution_status.py
scripts/sync_notion_review_status.py
```

대신 문서에 후속 guard 적용 정책을 적는다.

권장 후속 정책:

```text
- Notion actual write/sync는 --account-id 명시를 강하게 요구
- non-default account는 3F/3E 이후에만 허용
- account_id 없는 Notion external key write는 장기적으로 금지
```

### 4. 테스트 추가

새 테스트 파일 후보:

```text
tests/test_paper_account_guard.py
tests/test_paper_cli_writer_account_guard.py
```

테스트 항목:

```text
1. guard에서 account_id 생략 시 paper_default
2. paper_default writer 허용
3. invalid account_id 실패
4. non-default writer 기본 차단
5. guard 결과에 account_id/account_root/legacy_default_used 포함
6. paper.py commit --account-id paper_growth 차단
7. paper.py plan --account-id paper_growth 차단
8. paper.py review-append --account-id paper_growth 차단
9. 기존 paper.py commit --date YYYYMMDD는 paper_default로 guard 통과
10. 기존 writer path 함수 반환값이 바뀌지 않음
```

테스트는 실제 writer command를 실행하지 않는다.  
가능하면 parser/handler 단위에서 guard만 검증한다.

## 산출물

예상 수정/추가 파일:

```text
core/paper_account_guard.py
scripts/paper.py
tests/test_paper_account_guard.py
tests/test_paper_cli_writer_account_guard.py
```

문서 추가:

```text
docs/TRD/mfu_paper15_3d_writer_account_guard.md
```

문서 포함 항목:

```text
1. Purpose
2. Scope / Non-scope
3. Writer command risk
4. Guard policy
5. paper_default behavior
6. non-default blocking policy
7. Notion writer/sync future policy
8. Relationship to PAPER15-3F
```

## 금지 사항

```text
writer path를 account root로 변경 금지
core/paths.py 기존 paper path 함수 반환값 변경 금지
paper 원장 CSV 수정 금지
paper_current_state 파일 수정 금지
DB write 금지
Notion API write 금지
Notion export 실행 금지
Notion status sync 실행 금지
Notion external key 변경 금지
migration script 작성 금지
프로젝트 실제 outputs/paper_accounts 자동 생성 금지
paper.py prepare/preview 실제 실행 금지
paper.py commit/eod/review-append 실제 writer 실행 금지
git add . 금지
git add -A 금지
```

## 허용 사항

```text
writer guard 코드 추가
paper.py writer-like parser에 --account-id 추가
paper.py handler 진입 전 guard 적용
단위 테스트 추가
문서 추가
pytest 실행
read-only status 명령 실행
```

## 검증 명령

Windows CMD 기준:

```cmd
python -m pytest tests\test_paper_account_profile.py tests\test_paper_account_paths.py tests\test_paper_cli_account_scope.py
python -m pytest tests\test_paper_account_guard.py tests\test_paper_cli_writer_account_guard.py
python scripts\paper.py status --account-id paper_default --json
git diff -- core\paper_account_guard.py scripts\paper.py tests\test_paper_account_guard.py tests\test_paper_cli_writer_account_guard.py
git diff -- docs\TRD\mfu_paper15_3d_writer_account_guard.md
git status --short
```

## 성공 기준

```text
writer account guard 모듈이 추가된다.
paper.py plan/eod/commit/review-append에 --account-id가 추가된다.
paper_default writer는 기존 경로 동작을 유지하며 guard를 통과한다.
non-default writer는 writer path 적용 전까지 차단된다.
guard 출력/결과에 account_id/account_root/legacy_default_used가 포함된다.
기존 read-only --account-id 동작은 깨지지 않는다.
기존 writer path는 account root로 변경되지 않는다.
paper 원장 CSV, DB, Notion, outputs 하위 실제 운영 파일은 수정되지 않는다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 생성/수정한 파일
3. guard 정책 요약
4. --account-id 추가 writer-like 명령
5. paper_default writer 동작
6. non-default writer 차단 동작
7. Notion writer/sync 미적용 여부
8. 테스트 결과
9. 기존 read-only CLI 영향 여부
10. 기존 writer path 변경 여부
11. 금지 사항 준수 여부
12. outputs/paper_test 변경 여부
13. outputs/paper_accounts 생성 여부
14. 다음 MFU 제안
```

반드시 명시:

```text
이번 PAPER15-3D는 writer command account guard 구현이며, writer path 적용, DB schema 변경, paper 원장 migration, Notion external key 변경, Notion write/export 구조 변경은 포함하지 않는다.
```

END MFU-PAPER15-3D_WRITER_ACCOUNT_GUARD
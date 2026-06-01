BEGIN MFU-PAPER15-4A_SAFETY_GATED_NON_DEFAULT_LOCAL_REHEARSAL

# MFU-PAPER15-4A 작업 지시문: Safety-gated Non-default Local Rehearsal

## 목적

MFU-PAPER15-4A의 목표는 실제 프로젝트 작업공간에서 non-default paper 계좌 root를 명시적으로 생성하고, 제한된 local daily ops 명령을 실행해 실제 운영 전 리허설을 수행하는 것이다.

이번 단계는 테스트 전용 tmp_path가 아니라 실제 로컬 sandbox root를 사용하는 리허설이다.  
단, Notion actual sync/write, broker/API, cloud runner, paper_default migration, 실제 투자 주문은 포함하지 않는다.

반드시 명시:

```text
이번 PAPER15-4A는 safety-gated non-default local rehearsal이며, Notion actual sync/write, broker/API, cloud runner, paper_default migration, 실제 투자 주문은 포함하지 않는다.
```

## 리허설 계좌

고정 account_id:

```text
paper_sandbox
```

허용 root:

```text
outputs/paper_accounts/paper_sandbox/
```

금지 root:

```text
outputs/paper_test/
outputs/paper_accounts/paper_default/
```

## 핵심 안전 정책

```text
1. account_id는 반드시 paper_sandbox만 사용한다.
2. paper_default 실행 금지.
3. 모든 생성/수정 파일은 outputs/paper_accounts/paper_sandbox/ 하위여야 한다.
4. outputs/paper_test 변경이 감지되면 FAIL.
5. Notion actual export/sync/write 금지.
6. broker/API 실행 금지.
7. 실제 commit/append는 이번 4A에서 하지 않는다.
8. eod는 dry-run만 허용한다.
9. 실패 시 paper_sandbox root만 정리 가능해야 한다.
```

## 작업 범위

### 1. 사전 안전 점검

실행 전 아래를 기록한다.

```cmd
git status --short
dir outputs\paper_test
dir outputs\paper_accounts
```

가능하면 실행 전 `outputs/paper_test` 변경 감지를 위해 파일 목록을 저장한다.

예시:

```cmd
dir /s /b outputs\paper_test > outputs\paper_test_before.txt
```

단, 이 before 파일은 가능하면 임시 위치에 두고, repo에 stage하지 않는다.

### 2. paper_sandbox root 생성

명시적으로 아래 root만 생성한다.

```cmd
mkdir outputs\paper_accounts\paper_sandbox
```

필요 하위 디렉터리는 명령 실행 과정에서 생성되어도 된다.

허용:

```text
outputs/paper_accounts/paper_sandbox/
outputs/paper_accounts/paper_sandbox/reports/
outputs/paper_accounts/paper_sandbox/reviews/
outputs/paper_accounts/paper_sandbox/config_snapshots/
outputs/paper_accounts/paper_sandbox/archive/
```

### 3. local rehearsal 명령 실행

아래 명령을 가능한 범위에서 순서대로 실행한다.

```cmd
python scripts\paper.py status --account-id paper_sandbox --json
python scripts\paper.py plan --account-id paper_sandbox
python scripts\paper.py eod --account-id paper_sandbox --dry-run
python scripts\paper.py reports --account-id paper_sandbox
python scripts\paper.py review-template --account-id paper_sandbox
python scripts\paper.py review-validate --account-id paper_sandbox
python scripts\paper.py status --account-id paper_sandbox --json
```

중요:

```text
commit 실행 금지.
review-append 실행 금지.
import_notion_executions.py --commit 실행 금지.
import_notion_reviews.py --commit 실행 금지.
sync_notion_execution_status.py 실행 금지.
sync_notion_review_status.py 실행 금지.
export_paper_to_notion.py actual 실행 금지.
```

만약 특정 명령이 데이터 부족으로 실패하면, 실패를 숨기지 말고 다음을 기록한다.

```text
- 실패 명령
- 실패 이유
- 생성된 파일 목록
- outputs/paper_test 변경 여부
- 다음 단계에서 필요한 fixture 또는 선행 데이터
```

### 4. 산출물 위치 검증

실행 후 아래를 확인한다.

```cmd
dir /s /b outputs\paper_accounts\paper_sandbox
dir /s /b outputs\paper_test > outputs\paper_test_after.txt
```

검증 기준:

```text
- paper_sandbox 산출물이 outputs/paper_accounts/paper_sandbox 하위에만 있어야 한다.
- outputs/paper_test는 변경되지 않아야 한다.
- outputs/paper_accounts/paper_default는 생성/수정되지 않아야 한다.
```

### 5. closeout 문서 작성

아래 문서를 작성한다.

```text
docs/TRD/mfu_paper15_4a_safety_gated_non_default_local_rehearsal.md
```

문서에 포함:

```text
1. Purpose
2. Scope / Non-scope
3. Rehearsal account_id
4. Commands executed
5. Command results
6. Generated files under paper_sandbox
7. outputs/paper_test contamination check
8. Failures / blockers
9. Readiness decision
10. Next MFU recommendation
```

## 금지 사항

```text
paper_default 실행 금지
outputs/paper_test 수정 금지
outputs/paper_accounts/paper_default 생성/수정 금지
commit 실행 금지
review-append 실행 금지
Notion actual sync/write/export 금지
broker/API 실행 금지
cloud runner 작업 금지
paper_default migration 금지
DB schema 변경 금지
git add . 금지
git add -A 금지
```

## 허용 사항

```text
outputs/paper_accounts/paper_sandbox 생성
paper_sandbox 기준 status/plan/eod dry-run/reports/review-template/review-validate 실행
paper_sandbox 하위 산출물 생성
closeout 문서 작성
read-only 검증 명령 실행
```

## 검증 명령

Windows CMD 기준:

```cmd
python scripts\paper.py status --account-id paper_sandbox --json
dir /s /b outputs\paper_accounts\paper_sandbox
git status --short
git diff -- docs\TRD\mfu_paper15_4a_safety_gated_non_default_local_rehearsal.md
```

필요 시 관련 테스트도 실행한다.

```cmd
python -m pytest tests\test_paper_writer_account_paths.py
python -m pytest tests\test_paper_reports_account_paths.py tests\test_paper_review_template_account_paths.py tests\test_paper_review_validate_account_paths.py
```

## 성공 기준

```text
outputs/paper_accounts/paper_sandbox가 명시적으로 생성된다.
paper_sandbox 기준 status/plan/eod dry-run/reports/review-template/review-validate 중 실행 가능한 명령 결과가 기록된다.
모든 생성 산출물이 outputs/paper_accounts/paper_sandbox 하위에만 존재한다.
outputs/paper_test 변경이 없다.
outputs/paper_accounts/paper_default 변경이 없다.
Notion actual sync/write/export가 실행되지 않는다.
commit/review-append가 실행되지 않는다.
실패한 명령이 있으면 원인과 다음 조치가 문서화된다.
non-default local rehearsal의 운영 가능/불가능 판단이 closeout 문서에 기록된다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 생성/수정한 파일
3. 실행한 명령
4. 성공한 명령
5. 실패한 명령과 원인
6. paper_sandbox 생성 산출물
7. outputs/paper_test 변경 여부
8. outputs/paper_accounts/paper_default 변경 여부
9. Notion actual sync/write/export 실행 여부
10. commit/review-append 실행 여부
11. 테스트 결과
12. 남은 리스크
13. 다음 MFU 제안
```

반드시 명시:

```text
이번 PAPER15-4A는 safety-gated non-default local rehearsal이며, Notion actual sync/write, broker/API, cloud runner, paper_default migration, 실제 투자 주문은 포함하지 않는다.
```

END MFU-PAPER15-4A_SAFETY_GATED_NON_DEFAULT_LOCAL_REHEARSAL
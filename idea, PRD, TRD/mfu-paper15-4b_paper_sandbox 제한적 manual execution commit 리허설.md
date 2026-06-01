BEGIN MFU-PAPER15-4B_PAPER_SANDBOX_MANUAL_EXECUTION_COMMIT_REHEARSAL

# MFU-PAPER15-4B 작업 지시문: paper_sandbox 제한적 Manual Execution Commit 리허설

## 목적

MFU-PAPER15-4B의 목표는 실제 workspace의 non-default 계좌 `paper_sandbox`에서 제한적 Manual Execution commit을 1건 수행하고, 그 결과로 account snapshot / position snapshot / execution log / current state / reports / review-template / review-validate 체인이 이어지는지 확인하는 것이다.

이번 단계는 `paper_sandbox` 전용 local paper 리허설이다.  
Notion actual sync/write, broker/API, cloud runner, paper_default migration, 실제 투자 주문은 포함하지 않는다.

반드시 명시:

```text
이번 PAPER15-4B는 paper_sandbox 전용 제한적 Manual Execution commit 리허설이며, Notion actual sync/write, broker/API, cloud runner, paper_default migration, 실제 투자 주문은 포함하지 않는다.
```

## 배경

PAPER15-4A에서 실제 workspace 기준 아래 명령은 성공했다.

```text
status
plan
eod --dry-run
최종 status
```

하지만 아래 명령은 commit-stage 산출물 부재로 실패했다.

```text
reports: paper_account_snapshot.csv 없음
review-template: reports/paper_symbol_review_worksheet.csv 없음
review-validate: reviews/paper_manual_review_log_template.csv 없음
```

따라서 이번 4B에서는 `paper_sandbox` 안에서만 제한적 Manual Execution commit을 허용해 최소 snapshot/report 체인을 생성한다.

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
5. outputs/paper_accounts/paper_default 변경이 감지되면 FAIL.
6. Notion actual sync/write/export 금지.
7. broker/API 실행 금지.
8. commit은 Manual Execution 1건만 허용한다.
9. review-append는 이번 단계에서 실행하지 않는다.
10. 실패 시 paper_sandbox root만 정리 가능해야 한다.
```

## 작업 범위

### 1. 사전 안전 점검

실행 전 아래를 기록한다.

```cmd
git status --short
dir /s /b outputs\paper_test > outputs_paper_test_before.txt
dir /s /b outputs\paper_accounts\paper_default > outputs_paper_default_before.txt
dir /s /b outputs\paper_accounts\paper_sandbox > outputs_paper_sandbox_before.txt
```

위 before 파일은 임시 검증용이다. 가능하면 repo에 stage하지 않는다.

### 2. 기존 paper_sandbox 상태 확인

```cmd
python scripts\paper.py status --account-id paper_sandbox --json
dir /s /b outputs\paper_accounts\paper_sandbox
```

필수 확인:

```text
daily_action_plan_20260520.md 존재 여부
config_snapshots/paper_config_snapshot_20260520.json 존재 여부
```

없으면 아래를 먼저 실행한다.

```cmd
python scripts\paper.py plan --date 20260520 --account-id paper_sandbox
python scripts\paper.py eod --date 20260520 --account-id paper_sandbox --dry-run
```

### 3. Manual Execution preview fixture 준비

Notion actual import는 실행하지 않는다.  
기존 테스트 또는 importer preview JSON schema를 참고해 `paper_sandbox` 전용 Manual Execution preview fixture를 준비한다.

권장 위치:

```text
outputs/paper_accounts/paper_sandbox/manual_execution_preview_20260520_sandbox.json
```

fixture 조건:

```text
account_id = paper_sandbox
execution_date 또는 trade_date = 2026-05-20
symbol은 daily_action_plan에 존재하는 종목을 우선 사용
side는 BUY 또는 SELL 중 plan과 일관된 값 사용
quantity는 최소 수량 사용
price는 plan 또는 fixture에서 명확히 기록
canonical_key는 account-aware 형식 사용
legacy_canonical_key는 non-default에서는 사용하지 않음
legacy_key_compatible=false
```

주의:

```text
실제 Notion API에서 row를 읽지 않는다.
실제 주문 API를 호출하지 않는다.
fixture 내용은 closeout 문서에 기록한다.
```

### 4. Manual Execution commit 1건 수행

기존 CLI가 preview file commit을 지원하면 CLI를 사용한다.

예시:

```cmd
python scripts\import_notion_executions.py --account-id paper_sandbox --commit --preview-file outputs\paper_accounts\paper_sandbox\manual_execution_preview_20260520_sandbox.json
```

만약 현재 CLI가 preview file 인자를 지원하지 않으면, 기존 core 함수 또는 테스트 helper를 사용해 동일한 commit 경로를 실행한다. 단, 반드시 `account_paths=paper_sandbox`를 전달해야 한다.

commit 후 확인할 산출물:

```text
paper_execution_log.csv
paper_account_snapshot.csv
paper_position_snapshot.csv
paper_current_state_20260520.json
commit sidecar report JSON
```

모든 파일은 아래 하위에 있어야 한다.

```text
outputs/paper_accounts/paper_sandbox/
```

### 5. reports / review-template / review-validate 재실행

commit 후 아래 명령을 실행한다.

```cmd
python scripts\paper.py reports --account-id paper_sandbox
python scripts\paper.py review-template --account-id paper_sandbox
python scripts\paper.py review-validate --account-id paper_sandbox
python scripts\paper.py status --account-id paper_sandbox --json
```

기대 결과:

```text
reports가 paper_account_snapshot.csv 부재로 실패하지 않아야 한다.
review-template이 paper_symbol_review_worksheet.csv 부재로 실패하지 않아야 한다.
review-validate가 manual_review_log_template.csv 부재로 실패하지 않아야 한다.
status가 sandbox root 기준 artifact 상태를 반영해야 한다.
```

### 6. 오염 검사

실행 후 아래를 기록한다.

```cmd
dir /s /b outputs\paper_test > outputs_paper_test_after.txt
dir /s /b outputs\paper_accounts\paper_default > outputs_paper_default_after.txt
dir /s /b outputs\paper_accounts\paper_sandbox > outputs_paper_sandbox_after.txt
```

검증 기준:

```text
outputs/paper_test before/after 차이 없음
outputs/paper_accounts/paper_default before/after 차이 없음
생성/수정 파일은 outputs/paper_accounts/paper_sandbox 하위에만 존재
```

### 7. closeout 문서 작성

아래 문서를 작성한다.

```text
docs/TRD/mfu_paper15_4b_paper_sandbox_manual_execution_commit_rehearsal.md
```

문서 포함 항목:

```text
1. Purpose
2. Scope / Non-scope
3. Rehearsal account_id
4. Pre-check result
5. Manual Execution fixture summary
6. Commit command or core path used
7. Generated sandbox artifacts
8. Reports result
9. Review-template result
10. Review-validate result
11. Final status result
12. outputs/paper_test contamination check
13. outputs/paper_accounts/paper_default contamination check
14. Failures / blockers
15. Readiness decision
16. Next MFU recommendation
```

## 금지 사항

```text
paper_default 실행 금지
outputs/paper_test 수정 금지
outputs/paper_accounts/paper_default 생성/수정 금지
Notion actual sync/write/export 금지
Notion row migration 금지
broker/API 실행 금지
cloud runner 작업 금지
paper_default migration 금지
실제 투자 주문 금지
review-append 실행 금지
git add . 금지
git add -A 금지
```

## 허용 사항

```text
outputs/paper_accounts/paper_sandbox 하위 파일 생성/수정
paper_sandbox 전용 Manual Execution commit 1건
paper_sandbox 기준 reports/review-template/review-validate/status 실행
fixture preview JSON 생성
closeout 문서 작성
read-only 검증 명령 실행
관련 pytest 실행
```

## 검증 명령

Windows CMD 기준:

```cmd
python scripts\paper.py status --account-id paper_sandbox --json
python scripts\paper.py reports --account-id paper_sandbox
python scripts\paper.py review-template --account-id paper_sandbox
python scripts\paper.py review-validate --account-id paper_sandbox
python scripts\paper.py status --account-id paper_sandbox --json
dir /s /b outputs\paper_accounts\paper_sandbox
git status --short
git diff -- docs\TRD\mfu_paper15_4b_paper_sandbox_manual_execution_commit_rehearsal.md
```

필요 시 관련 테스트도 실행한다.

```cmd
python -m pytest tests\test_paper_writer_account_paths.py
python -m pytest tests\test_paper_manual_execution_commit.py tests\test_paper_manual_review_append_commit.py
python -m pytest tests\test_paper_reports_account_paths.py tests\test_paper_review_template_account_paths.py tests\test_paper_review_validate_account_paths.py
```

## 성공 기준

```text
paper_sandbox에서 Manual Execution commit 1건이 수행된다.
commit 산출물은 outputs/paper_accounts/paper_sandbox 하위에만 생성된다.
paper_execution_log.csv가 sandbox root에 생성/갱신된다.
paper_account_snapshot.csv가 sandbox root에 생성/갱신된다.
paper_position_snapshot.csv가 sandbox root에 생성/갱신된다.
paper_current_state_20260520.json이 sandbox root에 생성/갱신된다.
reports가 sandbox root 기준으로 실행된다.
review-template이 sandbox root 기준으로 실행된다.
review-validate가 sandbox root 기준으로 실행된다.
최종 status가 sandbox root 기준 artifact 상태를 반영한다.
outputs/paper_test 변경이 없다.
outputs/paper_accounts/paper_default 변경이 없다.
Notion actual sync/write/export가 실행되지 않는다.
review-append는 실행되지 않는다.
실패한 명령이 있으면 원인과 다음 조치가 문서화된다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 생성/수정한 파일
3. 실행한 명령
4. Manual Execution fixture 요약
5. commit 성공 여부
6. 생성된 sandbox 산출물
7. reports 실행 결과
8. review-template 실행 결과
9. review-validate 실행 결과
10. 최종 status 결과
11. outputs/paper_test 변경 여부
12. outputs/paper_accounts/paper_default 변경 여부
13. Notion actual sync/write/export 실행 여부
14. review-append 실행 여부
15. 테스트 결과
16. 남은 리스크
17. 다음 MFU 제안
```

반드시 명시:

```text
이번 PAPER15-4B는 paper_sandbox 전용 제한적 Manual Execution commit 리허설이며, Notion actual sync/write, broker/API, cloud runner, paper_default migration, 실제 투자 주문은 포함하지 않는다.
```

END MFU-PAPER15-4B_PAPER_SANDBOX_MANUAL_EXECUTION_COMMIT_REHEARSAL
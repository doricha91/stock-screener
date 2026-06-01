BEGIN MFU-PAPER15-4C_PAPER_SANDBOX_REVIEW_APPEND_REHEARSAL

# MFU-PAPER15-4C 작업 지시문: paper_sandbox Review Append 리허설

## 목적

MFU-PAPER15-4C의 목표는 실제 workspace의 non-default 계좌 `paper_sandbox`에서 review-template / review-validate 이후 `review-append`까지 제한적으로 실행해, local daily ops review closeout 체인이 완주되는지 확인하는 것이다.

이번 단계는 `paper_sandbox` 전용 local review append 리허설이다.  
Notion actual sync/write, broker/API, cloud runner, paper_default migration, 실제 투자 주문은 포함하지 않는다.

반드시 명시:

```text
이번 PAPER15-4C는 paper_sandbox 전용 Review Append 리허설이며, Notion actual sync/write, broker/API, cloud runner, paper_default migration, 실제 투자 주문은 포함하지 않는다.
```

## 배경

PAPER15-4B에서 `paper_sandbox` 기준 아래 흐름은 성공했다.

```text
status
plan
eod --dry-run
Manual Execution commit 1건
reports
review-template
review-validate
최종 status = REVIEW_READY
```

아직 실행하지 않은 단계:

```text
review-append
review-append 이후 final status
```

따라서 이번 4C에서는 기존 `paper_sandbox` 산출물을 사용해 review-append를 제한적으로 실행한다.

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
8. 실제 투자 주문 금지.
9. 이번 단계에서는 review-append만 제한적으로 허용한다.
10. 추가 Manual Execution commit은 실행하지 않는다.
```

## 작업 범위

### 1. 사전 안전 점검

실행 전 아래를 기록한다.

```cmd
git status --short
dir /s /b outputs\paper_test > outputs_paper_test_before_4c.txt
dir /s /b outputs\paper_accounts\paper_default > outputs_paper_default_before_4c.txt
dir /s /b outputs\paper_accounts\paper_sandbox > outputs_paper_sandbox_before_4c.txt
```

before 파일은 임시 검증용이다. repo에 stage하지 않는다.

### 2. 기존 paper_sandbox 상태 확인

```cmd
python scripts\paper.py status --account-id paper_sandbox --json
dir /s /b outputs\paper_accounts\paper_sandbox
```

필수 확인:

```text
paper_execution_log.csv 존재
paper_account_snapshot.csv 존재
paper_position_snapshot.csv 존재
paper_current_state_20260520.json 존재
reports/ 하위 review worksheet 존재
reviews/paper_manual_review_log_template.csv 존재
review_validation_result=PASS 또는 이에 준하는 상태
```

부족한 파일이 있으면 임의로 생성하지 말고, 어떤 파일이 부족한지 closeout 문서에 기록한다.

### 3. review append 입력 준비

기존 review template을 사용한다.

후보 파일:

```text
outputs/paper_accounts/paper_sandbox/reviews/paper_manual_review_log_template.csv
```

필요하면 sandbox 전용 append 입력 파일을 만든다.

권장 후보:

```text
outputs/paper_accounts/paper_sandbox/reviews/paper_manual_review_log_append_input_20260520.csv
```

입력 파일 정책:

```text
- 기존 template schema를 유지한다.
- 최소 1개 row만 append 대상으로 채운다.
- account_id가 필요한 경우 paper_sandbox로 명시한다.
- symbol은 4B에서 commit한 AMT 또는 template에 존재하는 row를 사용한다.
- Review Status / Manual Answer / Follow-up Needed / Review Tag / Reviewer Note 등 필수 또는 권장 입력 필드는 현재 validator 기준에 맞게 채운다.
- 임의로 External Key 또는 Notion 관련 필드를 수정하지 않는다.
```

### 4. review-validate 재실행

append 입력 파일 또는 기존 template 기준으로 validation을 다시 실행한다.

예시:

```cmd
python scripts\paper.py review-validate --account-id paper_sandbox
```

현재 CLI가 입력 파일 옵션을 지원하면 실제 옵션을 확인해 사용한다.

```cmd
python scripts\paper.py review-validate --account-id paper_sandbox --input <sandbox_review_input_csv>
```

지원하지 않는 옵션은 새로 만들지 말고, 현재 코드가 지원하는 방식으로 수행한다.

### 5. review-append 실행

validation이 PASS인 경우에만 review-append를 실행한다.

예시:

```cmd
python scripts\paper.py review-append --account-id paper_sandbox
```

현재 CLI가 입력 파일 옵션이나 `--allow-warnings`를 요구하면 실제 코드 기준으로 사용한다.

중요:

```text
- paper_default로 review-append 실행 금지
- Notion import/sync 실행 금지
- review-append 대상은 paper_sandbox reviews/ 하위 파일이어야 한다.
```

### 6. 실행 후 확인

실행 후 아래를 확인한다.

```cmd
python scripts\paper.py status --account-id paper_sandbox --json
dir /s /b outputs\paper_accounts\paper_sandbox
dir /s /b outputs\paper_test > outputs_paper_test_after_4c.txt
dir /s /b outputs\paper_accounts\paper_default > outputs_paper_default_after_4c.txt
```

확인할 산출물:

```text
outputs/paper_accounts/paper_sandbox/reviews/paper_manual_review_log.csv
review append report 또는 sidecar JSON
최종 status의 manual_review_log_exists=true
가능하면 workflow_status가 REVIEW_DONE 또는 이에 준하는 완료 상태
```

정확한 status 이름은 현재 코드 기준으로 기록한다.

### 7. closeout 문서 작성

아래 문서를 작성한다.

```text
docs/TRD/mfu_paper15_4c_paper_sandbox_review_append_rehearsal.md
```

문서 포함 항목:

```text
1. Purpose
2. Scope / Non-scope
3. Rehearsal account_id
4. Pre-check result
5. Review append input summary
6. Review validation result
7. Review append command/result
8. Generated sandbox artifacts
9. Final status result
10. outputs/paper_test contamination check
11. outputs/paper_accounts/paper_default contamination check
12. Failures / blockers
13. Readiness decision
14. Next MFU recommendation
```

## 금지 사항

```text
paper_default 실행 금지
outputs/paper_test 수정 금지
outputs/paper_accounts/paper_default 생성/수정 금지
추가 Manual Execution commit 실행 금지
Notion actual sync/write/export 금지
Notion row migration 금지
broker/API 실행 금지
cloud runner 작업 금지
paper_default migration 금지
실제 투자 주문 금지
git add . 금지
git add -A 금지
```

## 허용 사항

```text
outputs/paper_accounts/paper_sandbox 하위 파일 생성/수정
paper_sandbox 전용 review append input fixture 생성
paper_sandbox 기준 review-validate 실행
paper_sandbox 기준 review-append 실행
paper_sandbox 기준 status 실행
closeout 문서 작성
read-only 검증 명령 실행
관련 pytest 실행
```

## 검증 명령

Windows CMD 기준:

```cmd
python scripts\paper.py status --account-id paper_sandbox --json
python scripts\paper.py review-validate --account-id paper_sandbox
python scripts\paper.py review-append --account-id paper_sandbox
python scripts\paper.py status --account-id paper_sandbox --json
dir /s /b outputs\paper_accounts\paper_sandbox
git status --short
git diff -- docs\TRD\mfu_paper15_4c_paper_sandbox_review_append_rehearsal.md
```

필요 시 관련 테스트도 실행한다.

```cmd
python -m pytest tests\test_paper_manual_review_append_commit.py
python -m pytest tests\test_paper_review_validate_account_paths.py
python -m pytest tests\test_paper_writer_account_paths.py
```

## 성공 기준

```text
paper_sandbox에서 review-validate가 PASS 또는 명확한 허용 상태가 된다.
paper_sandbox에서 review-append가 실행된다.
review append 산출물은 outputs/paper_accounts/paper_sandbox 하위에만 생성된다.
paper_manual_review_log.csv가 sandbox root의 reviews/ 하위에 생성/갱신된다.
append report 또는 sidecar가 sandbox root 하위에 생성된다.
최종 status가 sandbox root 기준 review append 결과를 반영한다.
outputs/paper_test 변경이 없다.
outputs/paper_accounts/paper_default 변경이 없다.
Notion actual sync/write/export가 실행되지 않는다.
추가 Manual Execution commit은 실행되지 않는다.
실패한 명령이 있으면 원인과 다음 조치가 문서화된다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 생성/수정한 파일
3. 실행한 명령
4. review append input 요약
5. review-validate 결과
6. review-append 성공 여부
7. 생성된 sandbox 산출물
8. 최종 status 결과
9. outputs/paper_test 변경 여부
10. outputs/paper_accounts/paper_default 변경 여부
11. Notion actual sync/write/export 실행 여부
12. 추가 Manual Execution commit 실행 여부
13. 테스트 결과
14. 남은 리스크
15. 다음 MFU 제안
```

반드시 명시:

```text
이번 PAPER15-4C는 paper_sandbox 전용 Review Append 리허설이며, Notion actual sync/write, broker/API, cloud runner, paper_default migration, 실제 투자 주문은 포함하지 않는다.
```

END MFU-PAPER15-4C_PAPER_SANDBOX_REVIEW_APPEND_REHEARSAL
BEGIN MFU-PAPER15-4D_LOCAL_REVIEW_WORKFLOW_STATUS_SEMANTICS

# MFU-PAPER15-4D 작업 지시문: Local Workflow Status Semantics - REVIEW_PARTIAL / REVIEW_DONE

## 목적

MFU-PAPER15-4D의 목표는 로컬 `paper.py status`의 `workflow_status`에 review append 이후 상태를 반영하는 것이다.

현재 status model은 review-template + validation PASS 이후 `REVIEW_READY`까지만 표현한다.  
이번 단계에서는 `REVIEW_PARTIAL`, `REVIEW_DONE`을 추가해 review append 진행도를 로컬 status에서 먼저 정확히 표현한다.

이번 단계는 로컬 status semantics 구현이다.  
Notion DB 추가, Notion export/sync, Notion schema 변경, broker/API, cloud runner, paper_default migration은 포함하지 않는다.

반드시 명시:

```text
이번 PAPER15-4D는 로컬 paper.py status의 REVIEW_PARTIAL / REVIEW_DONE 상태 도입 작업이며, Notion DB 추가, Notion export/sync, broker/API, cloud runner, paper_default migration은 포함하지 않는다.
```

## 배경

현재 `core/paper_status.py`에는 아래 workflow status만 있다.

```text
NO_PLAN
PLAN_READY
COMMITTED
REVIEW_READY
UNKNOWN_OR_INCOMPLETE
```

PAPER15-4C에서 `paper_sandbox` 기준 review-append는 성공했고 `paper_manual_review_log.csv`도 생성됐지만, 최종 `workflow_status`는 `REVIEW_READY`로 유지됐다.

4C 결과:

```text
manual_review_log_exists=true
manual_review_log_row_count=1
review_validation_result=PASS
rows_appended=1
rows_skipped_pending=3
workflow_status=REVIEW_READY
```

이는 실제 운영 의미상 `REVIEW_PARTIAL`에 가깝다.

## 구현 범위

### 1. workflow status 상수 추가

수정 대상:

```text
core/paper_status.py
```

추가 상수:

```python
WORKFLOW_REVIEW_PARTIAL = "REVIEW_PARTIAL"
WORKFLOW_REVIEW_DONE = "REVIEW_DONE"
```

기존 상수는 유지한다.

```text
NO_PLAN
PLAN_READY
COMMITTED
REVIEW_READY
UNKNOWN_OR_INCOMPLETE
```

### 2. review progress summary 추가

`run_paper_status()`에서 review template과 manual review log를 읽은 뒤, review 진행도를 계산한다.

필드 후보:

```text
review_template_row_count
manual_review_log_row_count
review_answered_row_count
review_pending_row_count
review_done_row_count
review_completion_ratio
review_progress_status
```

권장 helper:

```python
_summarize_review_progress(review_template_rows, review_log_rows) -> dict[str, Any]
```

정책:

```text
- template row가 없으면 review progress는 unknown 또는 not_applicable
- template row 중 review_status가 reviewed/done/complete 계열이거나 manual_answer가 채워진 row를 answered로 본다
- pending row는 template row 중 아직 answered가 아닌 row로 본다
- manual_review_log.csv에 append된 row가 1개 이상 있고 pending row가 남아 있으면 REVIEW_PARTIAL
- template row가 있고 pending row가 0이며 manual_review_log.csv에 append된 row가 1개 이상이면 REVIEW_DONE
- validation_result가 PASS가 아니면 REVIEW_PARTIAL/DONE으로 전이하지 않는다
```

필드명은 기존 CSV schema를 조사해 실제 컬럼에 맞춘다.

우선순위 후보 컬럼:

```text
review_status
manual_answer
symbol
question_id
review_date
source_template_key
canonical_key
```

### 3. workflow status 판정 변경

`_detect_workflow_status(status)`를 수정한다.

권장 판정 순서:

```text
1. date 없음 → UNKNOWN_OR_INCOMPLETE
2. plan 없음 → NO_PLAN
3. same-date snapshot 없음 → PLAN_READY
4. reports_ready + review_template_exists + validation PASS인 경우:
   4-1. review_done 조건 충족 → REVIEW_DONE
   4-2. review_partial 조건 충족 → REVIEW_PARTIAL
   4-3. 그 외 → REVIEW_READY
5. current_state/account_snapshot/position_snapshot 존재 → COMMITTED
6. 그 외 → UNKNOWN_OR_INCOMPLETE
```

주의:

```text
REVIEW_DONE은 모든 template row가 answered/append 완료인 경우에만 반환한다.
이번 PAPER15-4C 같은 rows_appended=1, pending=3 상태는 REVIEW_PARTIAL이어야 한다.
review log가 없으면 REVIEW_READY로 유지한다.
```

### 4. next_recommended_command 갱신

`_next_recommended_command()`도 상태에 맞게 조정한다.

권장:

```text
REVIEW_READY:
  paper.py review-append

REVIEW_PARTIAL:
  complete pending review rows then paper.py review-append

REVIEW_DONE:
  no immediate action

기존 NO_PLAN / PLAN_READY / COMMITTED / UNKNOWN 동작은 유지하되,
필요하면 문구만 현재 paper.py CLI에 맞게 정리한다.
```

### 5. status JSON / text 출력 보강

`paper.py status --json`에 review 진행 필드를 포함한다.

필수 후보:

```text
review_answered_row_count
review_pending_row_count
review_completion_ratio
review_progress_status
```

`format_paper_status(..., verbose=True)`에는 위 필드를 표시한다.

기본 출력에는 최소한 아래 중 하나를 표시한다.

```text
manual_review_log_row_count
review_pending_row_count
review_progress_status
```

### 6. 테스트 추가/수정

테스트 파일 후보:

```text
tests/test_paper_status_review_workflow.py
tests/test_paper_status.py
tests/test_paper15_4c_rehearsal_status_semantics.py
```

필수 테스트:

```text
1. review template exists + validation PASS + review log 없음 → REVIEW_READY
2. template 4개 중 1개 answered + review log 1개 → REVIEW_PARTIAL
3. template 4개 모두 answered + review log 4개 → REVIEW_DONE
4. validation FAIL이면 REVIEW_PARTIAL/DONE으로 전이하지 않음
5. manual_review_log.csv만 있고 template이 없으면 REVIEW_DONE으로 오판하지 않음
6. 기존 COMMITTED 상태 테스트가 깨지지 않음
7. paper_default legacy root 기준 status 테스트 유지
8. non-default account_paths 기준 status 테스트 유지
9. next_recommended_command가 REVIEW_READY/PARTIAL/DONE에 맞게 반환
```

가능하면 PAPER15-4C의 실제 상황을 fixture로 재현한다.

```text
template row count = 4
answered row count = 1
manual_review_log_row_count = 1
expected workflow_status = REVIEW_PARTIAL
```

## 산출물

예상 수정/추가 파일:

```text
core/paper_status.py
tests/test_paper_status_review_workflow.py
```

필요 시 수정:

```text
tests/test_paper_cli_account_scope.py
tests/test_paper15_3h_non_default_daily_ops_smoke.py
tests/test_paper15_3i_full_local_daily_ops_smoke.py
```

문서 추가:

```text
docs/TRD/mfu_paper15_4d_local_review_workflow_status_semantics.md
```

문서 포함:

```text
1. Purpose
2. Scope / Non-scope
3. Existing workflow_status model
4. New REVIEW_PARTIAL / REVIEW_DONE semantics
5. Review progress calculation
6. Status transition table
7. Backward compatibility
8. Impact on paper_sandbox 4C result
9. Future Notion Daily Ops Status DB dependency
```

## 금지 사항

```text
Notion DB 추가 금지
Notion export/sync 구현 금지
Notion actual sync/write 실행 금지
paper_sandbox 산출물 수정 금지
outputs/paper_test 수정 금지
outputs/paper_accounts/paper_default 수정 금지
broker/API 실행 금지
cloud runner 작업 금지
paper_default migration 금지
실제 운영 writer 명령 실행 금지
git add . 금지
git add -A 금지
```

## 허용 사항

```text
core/paper_status.py 수정
status semantics 테스트 추가
tmp_path 기반 fixture 테스트
문서 추가
pytest 실행
read-only status 명령 실행
```

## 검증 명령

Windows CMD 기준:

```cmd
python -m pytest tests\test_paper_status_review_workflow.py
python -m pytest tests\test_paper_writer_account_paths.py
python -m pytest tests\test_paper_reports_account_paths.py tests\test_paper_review_template_account_paths.py tests\test_paper_review_validate_account_paths.py
python scripts\paper.py status --account-id paper_sandbox --json
git diff -- core\paper_status.py tests\test_paper_status_review_workflow.py
git diff -- docs\TRD\mfu_paper15_4d_local_review_workflow_status_semantics.md
git status --short
```

실제 운영 writer 명령과 Notion actual sync/write는 실행하지 않는다.

## 성공 기준

```text
REVIEW_PARTIAL 상수가 추가된다.
REVIEW_DONE 상수가 추가된다.
review append 이후 진행도가 status JSON에 반영된다.
template 일부만 answered/appended된 경우 REVIEW_PARTIAL로 표시된다.
template 전체가 answered/appended된 경우 REVIEW_DONE으로 표시된다.
review log가 없는 기존 상태는 REVIEW_READY로 유지된다.
validation FAIL 상태는 REVIEW_DONE으로 오판하지 않는다.
paper_sandbox 4C와 같은 상태는 REVIEW_PARTIAL로 판정된다.
기존 paper_default status 호환성은 유지된다.
non-default account_paths status 호환성은 유지된다.
Notion 관련 코드는 변경하지 않는다.
outputs 하위 실제 운영 파일은 수정하지 않는다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 생성/수정한 파일
3. 추가한 workflow_status
4. REVIEW_READY / REVIEW_PARTIAL / REVIEW_DONE 판정 기준
5. review progress 계산 필드
6. next_recommended_command 변경
7. paper_sandbox 4C 상태 재판정 결과
8. 테스트 결과
9. 기존 paper_default 영향 여부
10. non-default status 영향 여부
11. Notion DB/export/sync 변경 여부
12. outputs 변경 여부
13. 남은 리스크
14. 다음 MFU 제안
```

반드시 명시:

```text
이번 PAPER15-4D는 로컬 paper.py status의 REVIEW_PARTIAL / REVIEW_DONE 상태 도입 작업이며, Notion DB 추가, Notion export/sync, broker/API, cloud runner, paper_default migration은 포함하지 않는다.
```

END MFU-PAPER15-4D_LOCAL_REVIEW_WORKFLOW_STATUS_SEMANTICS
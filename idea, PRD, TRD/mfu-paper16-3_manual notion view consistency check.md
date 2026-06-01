BEGIN MFU-PAPER16-3-MANUAL-NOTION-VIEW-CONSISTENCY-CHECK

# PAPER16-3 Manual Notion View Consistency Check

## 목적

PAPER16-1 / PAPER16-2에서 정의한 Daily Ops Status Dashboard 설계와 운영 정책을 기준으로, 사용자가 Notion에서 수동 정리한 Daily Ops Status view 구성이 문서와 일치하는지 점검하고 기록한다.

이번 작업은 Notion을 직접 수정하지 않는다.
Codex는 사용자의 수동 정리 결과를 바탕으로 repo 문서에 “검증 결과 / 남은 차이 / 후속 조치”를 정리한다.

## 배경

PAPER16-1에서는 Daily Ops Status Dashboard view 설계를 작성했다.

권장 view:

- Today Ops
- By Account
- Needs Action
- Recent Sync
- Review Closeout

PAPER16-2에서는 Operator Command Map, actual export/sync rerun policy, source-of-truth rollback 금지, 수동 Notion view 정리 절차를 작성했다.

현재 사용자가 Notion에서 수동으로 수행한 작업:

- 기존 Daily Ops Status DB 안에서 view를 추가/정리함
- 새 DB 생성 또는 duplicate DB 생성은 하지 않은 것으로 사용자와 화면 기준 확인됨
- 5개 view를 모두 표/Table 보기로 구성함
- view 이름:
  - Today Ops
  - By Account
  - Needs Action
  - Recent Sync
  - Review Closeout
- By Account view에 Workflow Status를 표시하도록 추가 수정함
- 필터는 현재 걸지 않음
  - 이유: 필터를 적용하면 row가 제대로 보이지 않는 문제가 있어, 현재는 visibility 확보를 우선함
  - 이 상태는 실패가 아니라 “필터 적용 보류”로 기록해야 함

중요 원칙:

- CSV/JSON/Markdown/SQLite가 source-of-truth
- Notion은 input/review/staging/presentation layer
- External Key 수동 수정 금지
- property 삭제 금지
- 기존 Daily Ops Status DB 안에서 view만 정리
- Notion actual write/export 실행 금지

## 대상 파일

생성 후보:

- docs/TRD/mfu_paper16_manual_notion_view_consistency_check.md

수정 후보:

- docs/operations/paper_notion_ops.md
- docs/operations/paper_daily_ops.md

수정은 최소 addendum만 허용한다.
필요 없으면 신규 TRD 문서만 생성한다.

참고 파일:

- docs/TRD/mfu_paper16_daily_ops_status_dashboard_design.md
- docs/TRD/mfu_paper16_operator_command_map_and_rerun_policy.md
- docs/operations/paper_daily_ops.md
- docs/operations/paper_notion_ops.md

## 작업 범위

### 1. PAPER16-3 검증 문서 작성

아래 파일을 생성한다.

```text
docs/TRD/mfu_paper16_manual_notion_view_consistency_check.md
```

문서에는 다음 섹션을 포함한다.

1. Purpose
2. Source Material
3. Manual Notion View Setup Summary
4. View-by-View Consistency Check
5. Deferred Filters Policy
6. Remaining Gaps
7. PAPER16 Closeout Readiness
8. PAPER16-4 또는 후속 작업 후보

### 2. View-by-view 검증 결과 기록

각 view별로 다음을 표로 정리한다.

| View | Expected Format | Actual Format | Key Visible Fields | Grouping | Filter Status | Result | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |

현재 사용자 확인 결과를 기준으로 다음을 반영한다.

#### Today Ops

- Actual Format: Table
- Account ID, Status Date, Workflow Status, Review Progress Status, Review Completion Ratio, Sync Status, Next Recommended Command, Blocking Reason, Synced At 등이 보임
- Account ID 기준 그룹화가 적용된 것으로 보임
- Filter: not applied / deferred
- Result: pass with filter deferred

#### By Account

- Actual Format: Table
- Account ID 기준 그룹화
- Workflow Status 표시 추가 완료
- Status Date, Review Progress Status, Sync Status, Pending Row Count, Next Recommended Command, External Key 등이 보임
- Filter: not applied / deferred
- Result: pass with filter deferred

#### Needs Action

- Actual Format: Table
- Workflow Status 기준 그룹화
- REVIEW_PARTIAL, UNKNOWN_OR_INCOMPLETE 등 조치 필요 상태 확인 가능
- Review Validation Result, Sync Status, Blocking Reason, Next Recommended Command 등이 보임
- Filter: not applied / deferred
- Result: partial pass / filter deferred

#### Recent Sync

- Actual Format: Table
- Sync Status 기준 그룹화
- External Key, Sync Status, Synced At, Last Status Checked At, Workflow Status, Review Progress Status 등이 보임
- Filter: not applied / deferred
- Result: pass with filter deferred

#### Review Closeout

- Actual Format: Table
- Review Progress Status 기준 그룹화
- Review Completion Ratio, Review Template Exists, Review Validation Result, Manual Review Log Exists, answered/pending counts, Next Recommended Command 등이 보임
- Filter: not applied / deferred
- Result: pass with filter deferred

### 3. 필터 보류 정책 명시

반드시 별도 섹션으로 “Deferred Filters Policy”를 작성한다.

내용:

- 현재 Notion view에는 필터를 적용하지 않음
- 이유: 현재 샘플 row 수가 적고, 필터 적용 시 필요한 row가 보이지 않는 문제가 있어 visibility를 우선함
- 이는 실패가 아니라 의도적 보류 사항
- Daily Ops Status row가 더 쌓이고 status 값이 안정화된 뒤 필터를 추가해야 함
- 후속 작업 후보:
  - Needs Action filter hardening
  - Today Ops selected-date filter
  - Recent Sync recent-date filter
  - Review Closeout pending/done filter
- 필터 추가 전에는 기존 row가 사라져 보이지 않는지 반드시 확인해야 함

권장 후속 필터 후보는 문서에 candidate로만 남긴다.
이번 작업에서는 Notion 필터를 실제로 적용하지 않는다.

### 4. 남은 gap 정리

다음은 gap으로 기록한다.

- Filters are intentionally not applied yet
- Actual Notion UI verification is based on user-provided screenshots/manual report, not automated Notion API inspection
- Candidate/future statuses such as NOT_SYNCED, SYNC_FAILED, READY may need future filter/view refinement
- More rows are needed before filter behavior can be safely hardened
- No automatic schema/view drift check exists yet

### 5. SOP 최소 addendum

필요하다면 docs/operations/paper_notion_ops.md 또는 docs/operations/paper_daily_ops.md에 최소 addendum을 추가한다.

반영할 내용:

- PAPER16-3 documents manual Notion view consistency
- Filters are intentionally deferred
- Manual views currently prioritize visibility over strict filtering
- Future filter hardening is required after more Daily Ops Status rows accumulate

SOP 수정이 과해질 것 같으면 신규 TRD 문서에만 기록한다.

## Non-scope

이번 작업에서는 절대 하지 않는다.

- Python 코드 수정
- Notion actual write/export 실행
- Notion DB/view 실제 수정
- Notion API 호출
- 필터를 실제 Notion에 적용
- 신규 status 구현
- 신규 CLI 구현
- wrapper CLI 구현
- Alert / Replay / Schema Drift / Universe / Strategy 작업
- outputs/paper 원장 수정
- paper_default actual export
- multi-account bulk export
- broker/API 연동
- cloud runner 작업

## 검증 명령

Windows CMD 기준으로 실행한다.

```cmd
git status --short
git diff -- docs\TRD\mfu_paper16_manual_notion_view_consistency_check.md docs\operations\paper_daily_ops.md docs\operations\paper_notion_ops.md
findstr /S /N /I "Today Ops By Account Needs Action Recent Sync Review Closeout deferred filter External Key source-of-truth Table" docs\TRD\mfu_paper16_manual_notion_view_consistency_check.md docs\operations\paper_daily_ops.md docs\operations\paper_notion_ops.md
git diff --check -- docs\TRD\mfu_paper16_manual_notion_view_consistency_check.md docs\operations\paper_daily_ops.md docs\operations\paper_notion_ops.md
```

신규 파일이 untracked이면 `git diff`에 본문이 안 나올 수 있으므로, 필요 시 아래로 본문을 확인한다.

```cmd
type docs\TRD\mfu_paper16_manual_notion_view_consistency_check.md
```

## 성공 기준

- PAPER16-3 검증 문서가 생성됨
- 5개 view가 모두 기존 Daily Ops Status DB 안의 Table view로 정리되었다고 기록됨
- Today Ops / By Account / Needs Action / Recent Sync / Review Closeout 각각의 검증 결과가 정리됨
- By Account에 Workflow Status 표시가 반영됐다고 기록됨
- 필터 미적용이 실패가 아니라 의도적 보류 사항으로 명시됨
- 후속 filter hardening 필요성이 명시됨
- 새 DB 생성/duplicate DB 금지 원칙이 유지됨
- External Key 수동 수정 금지 원칙이 유지됨
- Notion actual write/export 실행 없음
- 코드 변경 없음
- outputs/paper 원장 변경 없음
- SOP 변경은 최소 addendum 수준을 넘지 않음

## Git 주의사항

금지:

```cmd
git add .
git add -A
```

허용되는 stage 예시:

```cmd
git add docs\TRD\mfu_paper16_manual_notion_view_consistency_check.md
git add docs\operations\paper_daily_ops.md
git add docs\operations\paper_notion_ops.md
```

실제로 수정된 파일만 개별 stage한다.

기존 워크트리에 unrelated 변경이 남아 있을 수 있으므로, 커밋 전 반드시 `git status --short`를 확인한다.

이번 커밋에 포함하면 안 되는 예:

```text
outputs/backtest_log.db
backtest_log.db
analysis_results/*.png
idea, PRD, TRD/*
PAPER15 잔여 변경
```

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 생성/수정한 파일
3. view별 consistency check 요약
4. By Account Workflow Status 반영 여부
5. 필터 미적용 / deferred filter 정책 반영 여부
6. 남은 gap
7. SOP 업데이트 여부
8. 코드 변경 여부
9. Notion actual write/export 실행 여부
10. outputs/paper 원장 변경 여부
11. git diff --check 결과
12. 다음 단계: PAPER16 closeout 또는 filter hardening 후속 과제

END MFU-PAPER16-3-MANUAL-NOTION-VIEW-CONSISTENCY-CHECK

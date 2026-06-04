BEGIN MFU-PAPER17-3-COMMAND-GATE-SOP

# PAPER17-2 커밋 + PAPER17-3 Export / Sync Command Gate SOP 작성

## 목적

먼저 PAPER17-2 Actual Guard Gap / Duplicate Risk Design 문서를 커밋한다.

그 다음 PAPER17-3로 운영자가 Notion export/sync 명령을 실행할 때 참고할 수 있는 Command Gate SOP를 작성한다.

PAPER17-3의 핵심은 다음 명령군을 운영자 관점에서 분류하는 것이다.

- Allowed dry-run
- Allowed guarded actual
- Forbidden
- Future / needs hardening
- 확인 필요

이번 작업은 문서/SOP 작업이다. 코드 수정, Notion actual write/export/sync 실행, outputs/paper 원장 수정은 하지 않는다.

## 배경

PAPER17-2에서 확인된 핵심 정책:

- Daily Ops Status actual은 `paper_sandbox` + `--confirm-actual` + schema PASS 조건에서만 현재 허용 가능한 guarded actual path다.
- detail report exporter actual은 `--dry-run` 생략만으로 actual path가 열리므로 guard gap이다.
- `--all` bulk actual은 코드상 가능하더라도 정책상 금지다.
- Manual Execution/Review status sync actual은 `--dry-run` 생략 시 `update_page`가 가능하므로 confirm guard가 필요하다.
- account_id 생략 시 `paper_default`로 normalize되므로 actual 명령에서는 명시적 `--account-id`가 필요하다.
- Notion sync/export 실패만으로 local source-of-truth rollback은 금지다.
- External Key와 page_id는 rerun/idempotency 판단의 핵심 식별자다.

## 1단계: PAPER17-2 커밋

### 대상 파일

```cmd
docs\TRD\mfu_paper17_actual_guard_gap_and_duplicate_risk_design.md
```

### 확인 명령

```cmd
git status --short
type docs\TRD\mfu_paper17_actual_guard_gap_and_duplicate_risk_design.md
git diff --check -- docs\TRD\mfu_paper17_actual_guard_gap_and_duplicate_risk_design.md
```

### stage / commit

절대 사용 금지:

```cmd
git add .
git add -A
```

실행:

```cmd
git add docs\TRD\mfu_paper17_actual_guard_gap_and_duplicate_risk_design.md
git diff --cached --name-only
git diff --cached
git commit -m "docs: design PAPER17 actual guard gap and duplicate risk"
git log -1 --stat
git status --short
```

## 2단계: PAPER17-3 Command Gate SOP 작성

### 생성 파일

```cmd
docs\TRD\mfu_paper17_export_sync_command_gate_sop.md
```

필요 시 최소 addendum만 허용:

```cmd
docs\operations\paper_notion_ops.md
docs\operations\paper_daily_ops.md
```

SOP 파일은 기존 미커밋 변경이 섞여 있으면 수정하지 말고 신규 TRD만 생성한다.

## PAPER17-3 문서 필수 섹션

생성 문서에는 다음 섹션을 포함한다.

1. Purpose
2. Source-of-truth Principle
3. Command Gate Summary
4. Allowed Dry-run Commands
5. Allowed Guarded Actual Commands
6. Forbidden Commands
7. Future / Needs Hardening Commands
8. Required Preflight Checklist
9. Rerun Decision Checklist
10. Account Scope Rules
11. External Key / page_id Safety Rules
12. Operator Stop Rules
13. PAPER17-4 Recommendation

## Command Gate Summary

아래 형식의 표를 작성한다.

| Classification | Command / Pattern | Current Status | Required Before Run | Operator Decision |
| --- | --- | --- | --- | --- |

반드시 포함할 명령군:

### Allowed dry-run

- `python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --dry-run --json`
- detail report exporter dry-run
  - `--weekly --dry-run`
  - `--benchmark --dry-run`
  - `--account-snapshot --dry-run`
  - `--daily-plan --dry-run`
  - `--daily-review-summary --dry-run`
- `--all --dry-run`
- Manual Execution status sync dry-run
- Manual Review status sync dry-run

### Allowed guarded actual

현재는 아래만 허용으로 둔다.

- `python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --confirm-actual --json`

조건:

- dry-run 먼저 실행
- schema validation PASS
- account_id가 `paper_sandbox`
- Daily Ops Status 단일 target
- External Key 확인
- duplicate 의심 없음
- 사용자가 명시 승인

### Forbidden

반드시 금지로 분류한다.

- Daily Ops Status `paper_default` actual
- Daily Ops Status mixed target export
- `--all` actual
- multi-account bulk actual
- account_id 생략 actual
- schema/property mismatch 의심 상태의 actual
- duplicate 의심 상태의 actual
- stale page_id 의심 상태의 status sync actual
- Notion 실패만으로 local source-of-truth rollback
- External Key 수동 수정

### Future / needs hardening

아래는 현재 운영 금지 또는 확인 필요로 두고, future/hardening으로 분류한다.

- detail report exporter actual without `--confirm-actual`
- Manual Execution status sync actual without confirm guard
- Manual Review status sync actual without confirm guard
- non-default account actual beyond `paper_sandbox`
- paper_default actual migration/convergence
- duplicate audit command
- schema/view drift automatic check
- wrapper CLI / GitHub Actions / GUI / Notion button

## Required Preflight Checklist

actual 실행 전 체크리스트를 작성한다.

필수 항목:

- dry-run 결과 확인
- explicit `--account-id` 확인
- target이 하나인지 확인
- `paper_default`로 normalize되지 않았는지 확인
- schema/property preflight 가능 시 실행
- External Key 확인
- would-create / would-update 성격 확인
- duplicate 의심 여부 확인
- page_id 기반 sync라면 page_id가 report와 Notion row에 맞는지 확인
- source-of-truth 변경 여부와 Notion presentation update 여부 구분

## Rerun Decision Checklist

다음 기준을 포함한다.

- local commit/append 성공 후 Notion sync 실패 시 local rollback 금지
- 같은 report/account/date/External Key 또는 page_id 기준으로 sync/export만 재시도
- duplicate 의심 시 actual 중단
- stale page_id 의심 시 actual 중단
- schema/property mismatch 의심 시 actual 중단
- account_id 누락 또는 paper_default 오해 가능성 있으면 actual 중단
- paper_sandbox actual rerun도 별도 승인 없이는 실행하지 않음

## Operator Stop Rules

운영자가 즉시 멈춰야 하는 조건을 별도 섹션으로 정리한다.

예시:

- `--dry-run`을 실행하지 않았다.
- actual 명령에 `--account-id`가 없다.
- `account_id`가 예상과 다르다.
- target이 여러 개다.
- `--all` actual이다.
- External Key가 비어 있거나 예상과 다르다.
- duplicate row 가능성이 있다.
- page_id가 stale/wrong일 수 있다.
- schema/property mismatch가 의심된다.
- Notion 상태와 local source-of-truth가 충돌한다.

## Non-scope

이번 작업에서는 절대 하지 않는다.

- Python 코드 수정
- 신규 CLI 구현
- `--confirm-actual` 실제 구현
- duplicate audit command 구현
- Notion actual write/export/sync 실행
- Notion API write 호출
- Notion DB/view 수정
- outputs/paper 원장 수정
- paper_default actual export
- multi-account bulk export
- paper_sandbox actual rerun
- Alert / Replay / Schema Drift / Universe / Strategy 구현
- wrapper CLI / GitHub Actions / GUI / Notion button 구현

## 검증 명령

Windows CMD 기준으로 실행한다.

```cmd
git status --short
type docs\TRD\mfu_paper17_export_sync_command_gate_sop.md
findstr /N /I "Allowed dry-run Allowed guarded actual Forbidden Future confirm-actual dry-run paper_sandbox paper_default External Key page_id duplicate source-of-truth rerun stop" docs\TRD\mfu_paper17_export_sync_command_gate_sop.md
git diff --check -- docs\TRD\mfu_paper17_export_sync_command_gate_sop.md
```

SOP 파일을 수정했다면 추가로 실행한다.

```cmd
git diff --check -- docs\operations\paper_notion_ops.md docs\operations\paper_daily_ops.md
```

## 성공 기준

- PAPER17-2 문서가 커밋됨
- PAPER17-3 Command Gate SOP 문서가 생성됨
- 명령들이 allowed dry-run / allowed guarded actual / forbidden / future로 분류됨
- detail exporter actual과 status sync actual의 guard gap이 운영자 관점에서 명확히 표시됨
- `--all` actual과 multi-account bulk actual이 금지로 명시됨
- account_id 생략 actual 금지가 명확함
- paper_default actual 금지가 명확함
- External Key / page_id 안전 규칙이 포함됨
- rerun decision checklist가 포함됨
- operator stop rules가 포함됨
- 코드 변경 없음
- Notion actual write/export/sync 실행 없음
- outputs/paper 원장 변경 없음

## Git 주의사항

금지:

```cmd
git add .
git add -A
```

PAPER17-3 문서는 이번 작업에서 아직 커밋하지 않는다.  
사용자가 명시적으로 커밋을 지시하기 전까지는 생성과 검증까지만 수행한다.

단, 결과 보고에서 커밋 후보 파일을 명확히 제시한다.

커밋 후보:

```cmd
docs\TRD\mfu_paper17_export_sync_command_gate_sop.md
```

SOP addendum을 실제 수정했다면 해당 파일도 후보로 제시한다.

```cmd
docs\operations\paper_notion_ops.md
docs\operations\paper_daily_ops.md
```

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. PAPER17-2 커밋 생성 여부
3. PAPER17-2 커밋 SHA / 메시지
4. PAPER17-3 생성/수정 파일
5. Command Gate 분류 요약
6. Allowed dry-run 요약
7. Allowed guarded actual 요약
8. Forbidden command 요약
9. Future / needs hardening 요약
10. Required preflight checklist 요약
11. Rerun decision checklist 요약
12. Operator stop rules 요약
13. 코드 변경 여부
14. Notion actual write/export/sync 실행 여부
15. outputs/paper 원장 변경 여부
16. git diff --check 결과
17. PAPER17-4 추천 작업

END MFU-PAPER17-3-COMMAND-GATE-SOP
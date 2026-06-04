BEGIN MFU-PAPER17-2-ACTUAL-GUARD-GAP-AND-DUPLICATE-RISK-DESIGN

# PAPER17-1 커밋 + PAPER17-2 Actual Guard Gap / Duplicate Risk Design

## 목적

먼저 PAPER17-1 Export / Sync Policy Inventory 문서를 커밋한다.

그 다음 PAPER17-2로 현재 Notion export/sync 경로의 actual guard gap, dry-run 생략 위험, duplicate row 위험, External Key 기반 idempotency 검증 흐름, schema/property preflight 절차를 설계 문서로 정리한다.

이번 작업은 설계/문서 작업이다. 코드 수정, Notion actual write/export, outputs/paper 원장 수정은 하지 않는다.

## 배경

PAPER17-1 inventory에서 확인된 핵심 위험:

- Daily Ops Status actual은 `paper_sandbox` + `--confirm-actual` + schema PASS guard가 있음
- 기존 detail exporter actual은 `--dry-run` 생략 시 actual 가능하며 `--confirm-actual` guard가 없음
- Manual Execution/Review status sync actual도 `--dry-run` 생략 시 `update_page` 가능
- `--all` actual 경로는 코드상 multi-target actual export 가능하지만 정책상 금지
- `account_id` 생략 시 `paper_default`로 normalize되어 혼동 위험 있음
- duplicate row audit, schema/view drift 자동 점검, actual rerun harness는 아직 없음

## 1단계: PAPER17-1 커밋

### 대상 파일

```cmd
docs\TRD\mfu_paper17_export_sync_policy_inventory.md
```

### 확인

```cmd
git status --short
type docs\TRD\mfu_paper17_export_sync_policy_inventory.md
git diff --check -- docs\TRD\mfu_paper17_export_sync_policy_inventory.md
```

신규 untracked 파일이면 `git diff`에 본문이 나오지 않을 수 있으므로 `type`으로 본문을 확인한다.

### stage / commit

금지:

```cmd
git add .
git add -A
```

실행:

```cmd
git add docs\TRD\mfu_paper17_export_sync_policy_inventory.md
git diff --cached --name-only
git diff --cached
git commit -m "docs: inventory PAPER17 export sync policy"
git log -1 --stat
git status --short
```

## 2단계: PAPER17-2 문서 생성

### 생성 파일

```cmd
docs\TRD\mfu_paper17_actual_guard_gap_and_duplicate_risk_design.md
```

### 포함할 섹션

1. Purpose
2. Source-of-truth Principle
3. PAPER17-1 Findings Summary
4. Actual Guard Gap Matrix
5. Dry-run Omission Risk
6. Account Scope Risk
7. External Key / Idempotency Risk
8. Duplicate Row Audit Design
9. Schema / Property Preflight Design
10. Rerun Decision Policy
11. Proposed Hardening Options
12. Non-scope
13. PAPER17-3 Recommendation

## 3단계: PAPER17-2 문서 내용 요구사항

### Actual Guard Gap Matrix

아래 형식의 표를 작성한다.

| Area | Current Actual Trigger | Current Guard | Risk | Proposed Policy | Implementation Needed Later |
| --- | --- | --- | --- | --- | --- |

반드시 포함:

- Daily Ops Status actual
- detail report exporters actual
- `--all` bulk detail actual
- Manual Execution status sync actual
- Manual Review status sync actual
- schema validation read-only preflight

분류 기준:

- Safe enough now
- Policy forbidden
- Guard gap
- Needs confirm guard
- Needs duplicate audit
- Read-only preflight

### Dry-run Omission Risk

`--dry-run` 생략만으로 actual이 되는 경로를 정리한다.

반드시 기록:

- detail exporter actual path
- Manual Execution status sync actual
- Manual Review status sync actual
- `--all` bulk actual path

정책 제안:

- actual은 기본 금지
- dry-run 우선
- actual은 명시적 confirm guard 또는 문서화된 승인 명령 필요
- bulk actual은 duplicate audit 전까지 금지

### Account Scope Risk

반드시 포함:

- account_id 생략 시 `paper_default` normalize
- paper_default legacy fallback과 신규 multi-account 정책 혼동 위험
- Daily Ops Status actual은 paper_sandbox only 유지
- paper_default actual export 금지 유지
- paper_sandbox 외 non-default actual 확장은 후속 safety review 필요

### Duplicate Row Audit Design

구현하지 말고 설계만 작성한다.

설계할 항목:

- audit input: target DB, External Key, Account ID, status/report date
- audit output: zero/one/multiple match, page_id list, action recommendation
- duplicate 발견 시: actual rerun 중단
- same External Key 0건: create candidate
- 1건: update candidate
- 2건 이상: duplicate blocker
- bulk rerun 전 target별 duplicate audit 필요

### Schema / Property Preflight Design

반드시 포함:

- Daily Ops Status는 `validate_notion_schema.py --daily-ops-status`가 read-only preflight로 존재
- schema validation은 property mismatch 완화용이지 duplicate/page_id/account_id 위험까지 모두 막지는 못함
- detail exporter / status sync 경로의 schema/property preflight 범위는 확인 필요
- schema/property mismatch 의심 시 actual 금지

### Rerun Decision Policy

다음 기준을 문서화한다.

- source-of-truth commit/append 성공 후 Notion sync 실패 시 local rollback 금지
- 같은 report/account/date/External Key 또는 page_id 기준으로 sync/export만 재시도
- duplicate 의심 시 actual 중단
- stale page_id 의심 시 status sync actual 중단
- paper_sandbox actual rerun은 별도 사용자 승인 전까지 실행하지 않음

### Proposed Hardening Options

후속 구현 후보를 P0/P1/P2/P3로 분류한다.

예시:

- P0: accidental actual write 방지, bulk actual 금지 명확화
- P1: SOP command gate, dry-run-before-actual 절차
- P2: `--confirm-actual` guard 추가 설계, duplicate audit command 설계, schema preflight 확장
- P3: wrapper CLI, GitHub Actions, Notion button

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

## 검증 명령

Windows CMD 기준:

```cmd
git status --short
type docs\TRD\mfu_paper17_actual_guard_gap_and_duplicate_risk_design.md
findstr /N /I "guard gap dry-run confirm-actual External Key duplicate paper_default paper_sandbox bulk source-of-truth page_id preflight rerun" docs\TRD\mfu_paper17_actual_guard_gap_and_duplicate_risk_design.md
git diff --check -- docs\TRD\mfu_paper17_actual_guard_gap_and_duplicate_risk_design.md
```

신규 untracked 파일이면 `git diff`에 본문이 나오지 않을 수 있으므로 `type`으로 확인한다.

## 성공 기준

- PAPER17-1 inventory 문서가 커밋됨
- PAPER17-2 설계 문서가 생성됨
- actual guard gap matrix가 작성됨
- dry-run omission risk가 명확히 정리됨
- account scope risk가 정리됨
- duplicate row audit 설계가 포함됨
- schema/property preflight 한계가 명시됨
- rerun decision policy가 정리됨
- 후속 hardening option이 P0/P1/P2/P3로 분류됨
- 코드 변경 없음
- Notion actual write/export/sync 실행 없음
- outputs/paper 원장 변경 없음

## Git 주의사항

금지:

```cmd
git add .
git add -A
```

PAPER17-2는 아직 커밋하지 말고, 문서 생성과 검증 결과만 보고한다.  
단, 사용자가 명시적으로 커밋까지 지시하면 아래만 stage한다.

```cmd
git add docs\TRD\mfu_paper17_actual_guard_gap_and_duplicate_risk_design.md
```

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. PAPER17-1 커밋 생성 여부
3. PAPER17-1 커밋 SHA / 메시지
4. PAPER17-2 생성/수정 파일
5. actual guard gap 요약
6. dry-run omission risk 요약
7. account scope risk 요약
8. External Key / duplicate audit 설계 요약
9. schema/property preflight 설계 요약
10. rerun decision policy 요약
11. P0/P1/P2/P3 hardening 후보
12. 코드 변경 여부
13. Notion actual write/export/sync 실행 여부
14. outputs/paper 원장 변경 여부
15. git diff --check 결과
16. PAPER17-3 추천 작업

END MFU-PAPER17-2-ACTUAL-GUARD-GAP-AND-DUPLICATE-RISK-DESIGN
BEGIN MFU-PAPER17-1-EXPORT-SYNC-POLICY-INVENTORY

# PAPER17-1 Export / Sync Policy Inventory

## 목적

PAPER17의 첫 단계로 현재 repo에 존재하는 Notion export / sync 관련 명령, guard, dry-run/actual 정책, 허용/금지 대상, External Key 기반 update 정책, 중복 row 위험, 후속 hardening 필요 항목을 inventory 문서로 정리한다.

이번 작업은 실제 export/sync를 실행하지 않는다.  
정책과 현재 상태를 파악하는 문서 작업이다.

## 배경

PAPER16은 Daily Ops Status Dashboard를 closeout했다.

완료된 PAPER16 커밋:

- acb7f5540eabad0d6e97c8449a97dbe3d4c77d57
  - docs: define PAPER16 daily ops status dashboard
- 2f7410ff3aab6ab4da2d08acccdd349492d65a4e
  - docs: record PAPER16 manual Notion view check
- 599a06f728d908c5970ec0a1a273bacfdff21c09
  - docs: close out PAPER16 daily ops status dashboard

PAPER16에서 정리된 원칙:

- CSV / JSON / Markdown / SQLite가 source-of-truth
- Notion은 input / review / staging / presentation layer
- Notion sync/export 실패만으로 local source-of-truth rollback 금지
- External Key 수동 수정 금지
- Daily Ops Status view는 수동 정리 완료
- 필터 hardening은 후속 과제
- paper_default actual export 금지 유지
- multi-account bulk export 금지 유지

PAPER17은 Alert / Replay / Schema Drift / Universe / Strategy로 가기 전에 export/sync 정책을 더 단단하게 정리하는 단계다.

## 작업 범위

### 1. Export / Sync 관련 파일 조사

아래 파일을 우선 확인한다.

- scripts/export_paper_to_notion.py
- scripts/paper.py
- core/notion_mapping.py
- core/notion_settings.py
- core/notion_client.py
- docs/operations/paper_daily_ops.md
- docs/operations/paper_notion_ops.md
- docs/TRD/mfu_paper16_daily_ops_status_dashboard_design.md
- docs/TRD/mfu_paper16_operator_command_map_and_rerun_policy.md
- docs/TRD/mfu_paper16_manual_notion_view_consistency_check.md
- docs/TRD/mfu_paper16_daily_ops_status_dashboard_closeout.md
- docs/TRD/paper_ops_feature_roadmap_v1_1.md

필요하면 repo에서 `daily-ops-status`, `confirm-actual`, `dry-run`, `External Key`, `sync_status`, `Notion`, `export` 키워드로 검색한다.

### 2. Inventory 문서 생성

아래 파일을 새로 생성한다.

- docs/TRD/mfu_paper17_export_sync_policy_inventory.md

문서에는 다음 섹션을 포함한다.

1. Purpose
2. Source-of-truth Principle
3. Current Export / Sync Surfaces
4. Command Inventory
5. Dry-run / Actual Guard Inventory
6. Account Scope Inventory
7. External Key / Idempotency Inventory
8. Notion Target / Mapping Inventory
9. Failure / Rerun Policy Inventory
10. Forbidden Operations
11. Known Gaps / Risks
12. Follow-up Hardening Candidates
13. PAPER17-2 Recommendation

### 3. Command Inventory 작성

현재 확인된 export/sync 관련 명령을 표로 정리한다.

표 형식:

| Area | Command | Target | Dry-run Support | Actual Support | Account Scope | Source-of-truth Impact | Notion Impact | Current Policy | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

포함 후보:

- `python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --dry-run --json`
- `python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --confirm-actual --json`
- Manual Execution / Manual Review status sync 관련 명령이 repo에 존재하면 포함
- 기타 Notion export target이 존재하면 포함

중요: 실제 존재가 확인된 명령만 “current”로 표시한다.  
불확실한 명령은 추측하지 말고 “확인 필요” 또는 “candidate/future”로 분류한다.

### 4. 정책 분류

각 export/sync 항목을 아래 중 하나로 분류한다.

- Allowed dry-run
- Allowed guarded actual
- Forbidden
- Candidate / future
- 확인 필요

반드시 현재 정책을 반영한다.

- Daily Ops Status actual export는 현재 paper_sandbox limited target만 허용
- paper_default actual export는 금지
- multi-account bulk export는 금지
- actual export 전 dry-run 우선
- actual은 명시적 confirm flag 또는 문서화된 guarded command가 있을 때만 허용
- schema/property mismatch 의심 시 actual 금지
- Notion sync/export 실패만으로 source-of-truth rollback 금지

### 5. External Key / Idempotency Inventory

External Key 관련 정책을 정리한다.

포함할 내용:

- External Key가 create/update 매칭에 어떤 역할을 하는지
- 같은 account_id / status_date / External Key 기준 update를 우선해야 하는지
- External Key 수동 수정 금지
- duplicate row 발생 위험
- duplicate row audit이 아직 없는 점
- bulk rerun 금지 이유

모르는 부분은 추측하지 말고 “코드 확인 필요”로 남긴다.

### 6. Known Gaps / Risks 정리

최소 아래 항목을 포함한다.

- duplicate row audit 없음
- schema/view drift 자동 점검 없음
- paper_sandbox 외 actual export 확장 기준 미정
- paper_default legacy root 정책과 신규 Daily Ops Status actual export 정책 미수렴
- multi-account bulk export 금지 유지
- Notion API 자동 검증 없음
- 실패 후 rerun 절차는 문서화됐지만 자동 하네스는 없음
- candidate/future status와 실제 emitted status 간 차이 가능성

### 7. PAPER17-2 추천 범위 제안

PAPER17-2 후보를 문서 끝에 제안한다.

추천 방향:

- Daily Ops Status rerun / duplicate risk assessment
- External Key 기반 idempotent update 검증 흐름 설계
- duplicate row audit 설계
- schema/property mismatch preflight 확인 절차
- paper_sandbox actual rerun은 후속 단계에서 별도 승인 후만 검토

## Non-scope

이번 작업에서는 절대 하지 않는다.

- Python 코드 수정
- 신규 CLI 구현
- Notion actual write/export 실행
- Notion DB/view 수정
- Notion API 호출
- outputs/paper 원장 수정
- paper_default actual export 실행
- multi-account bulk export 실행
- Alert / Monitoring 구현
- Replay / Same-date Diff 구현
- Schema Drift 자동 점검 구현
- Universe / Strategy 확장
- wrapper CLI / GUI / GitHub Actions / Notion button 구현

## 검증 명령

Windows CMD 기준으로 실행한다.

```cmd
git status --short

findstr /S /N /I "daily-ops-status confirm-actual dry-run External Key sync_status notion export" scripts\*.py core\*.py docs\operations\*.md docs\TRD\*.md

type docs\TRD\mfu_paper17_export_sync_policy_inventory.md

findstr /N /I "source-of-truth dry-run confirm-actual paper_sandbox paper_default bulk export External Key duplicate schema drift forbidden" docs\TRD\mfu_paper17_export_sync_policy_inventory.md

git diff --check -- docs\TRD\mfu_paper17_export_sync_policy_inventory.md
```

신규 untracked 파일은 `git diff`에 본문이 나오지 않을 수 있으므로 `type`으로 본문을 확인한다.

## 성공 기준

- PAPER17-1 inventory 문서가 생성됨
- 현재 export/sync command inventory가 표로 정리됨
- dry-run / guarded actual / forbidden / candidate / 확인 필요가 구분됨
- Daily Ops Status paper_sandbox limited actual 정책이 명확함
- paper_default actual export 금지가 유지됨
- multi-account bulk export 금지가 유지됨
- External Key / idempotency / duplicate risk가 정리됨
- known gaps와 PAPER17-2 추천 범위가 정리됨
- 코드 변경 없음
- Notion actual write/export 실행 없음
- outputs/paper 원장 변경 없음

## Git 주의사항

금지:

```cmd
git add .
git add -A
```

허용되는 stage 예시:

```cmd
git add docs\TRD\mfu_paper17_export_sync_policy_inventory.md
```

실제로 수정된 파일만 개별 stage한다.

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 생성/수정한 파일
3. 조사한 주요 파일
4. Export / Sync command inventory 요약
5. dry-run / actual / forbidden 정책 요약
6. account scope 정책 요약
7. External Key / idempotency / duplicate risk 요약
8. known gaps
9. PAPER17-2 추천 범위
10. 코드 변경 여부
11. Notion actual write/export 실행 여부
12. outputs/paper 원장 변경 여부
13. git diff --check 결과

END MFU-PAPER17-1-EXPORT-SYNC-POLICY-INVENTORY
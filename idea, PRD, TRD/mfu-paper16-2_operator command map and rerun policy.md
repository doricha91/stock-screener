BEGIN MFU-PAPER16-2-OPERATOR-COMMAND-MAP-AND-RERUN-POLICY

# Daily Ops Status 상태별 Command Map + Actual Export Rerun Policy + 수동 Notion View 정리 절차

## 목적

PAPER16-1에서 작성한 Daily Ops Status Dashboard 설계를 기반으로, 운영자가 각 상태값에서 다음에 무엇을 해야 하는지 판단할 수 있도록 command map과 rerun policy를 SOP로 고정한다.

이번 작업의 핵심은 다음이다.

1. Workflow Status / Review Progress Status / Sync Status별 운영자 행동표 작성
2. 각 상태에서 허용/금지되는 로컬 명령 정리
3. Notion actual export 실패 또는 sync 실패 시 재실행 정책 정리
4. commit/append 이후 Notion sync 실패 시 원장을 rollback하지 않는 원칙 명시
5. 사용자가 Notion에서 수동으로 view를 정리할 때 따라야 할 절차 확정
6. PAPER16-3에서 화면 정합성 점검으로 이어질 체크리스트 작성

## 배경

PAPER16-1에서는 Daily Ops Status Dashboard 설계 문서가 추가되었고, 다음 view가 제안되었다.

- Today Ops
- By Account
- Needs Action
- Recent Sync
- Review Closeout

또한 PAPER16-1은 실제 Notion view/create/write/export를 수행하지 않는 설계 단계였고, source-of-truth는 CSV/JSON/Markdown/SQLite이며 Notion은 presentation/review layer라는 원칙을 유지했다.

PAPER16-2에서도 Codex는 Notion을 직접 수정하지 않는다. 사용자의 Notion 수동 조작은 PAPER16-2 결과 보고 검토 후 수행한다.

## 작업 범위

### 1. 기존 PAPER16-1 문서 검토

다음 문서를 우선 확인한다.

- docs/TRD/mfu_paper16_daily_ops_status_dashboard_design.md
- docs/operations/paper_daily_ops.md
- docs/operations/paper_notion_ops.md
- docs/TRD/paper_ops_feature_roadmap_v1_1.md
- docs/TRD/mfu_paper15_multi_account_foundation_closeout.md

PAPER16-1의 view 설계와 상태값 해석표를 기준으로 이어서 작성한다. 단, 실제 Notion 화면은 수정하지 않는다.

### 2. 상태별 Operator Command Map 작성

새 문서를 작성한다.

권장 파일명:

- docs/TRD/mfu_paper16_operator_command_map_and_rerun_policy.md

문서에는 최소 아래 표를 포함한다.

| Status Area | Status Value | Meaning | Allowed Action | Forbidden Action | Next Recommended Command | Notes |
| --- | --- | --- | --- | --- | --- | --- |

다음 상태 영역을 다룬다.

- workflow_status
- review_progress_status
- sync_status

기존 코드/문서에서 확인되는 status만 “current”로 분류한다. 확인되지 않거나 향후 후보인 값은 “candidate/future”로 분리한다.

### 3. 상태별 허용/금지 정책 정리

다음 기준을 문서화한다.

- FAIL / FAILED / blocking reason이 있는 상태에서는 commit/append/export 금지
- WARNING은 기본적으로 commit/append/export를 막고, 명시적 allow 옵션이 있을 때만 허용
- REVIEW_PARTIAL은 review가 완료되지 않은 상태이므로 closeout 처리 금지
- REVIEW_DONE은 review closeout 가능 상태
- SYNC_FAILED는 source-of-truth commit/append가 성공했다면 원장 rollback 금지
- SYNC_FAILED는 동일 source-of-truth 결과 기준으로 Notion sync/status update 재시도
- NOT_SYNCED 또는 pending sync 상태는 actual export/rerun 가능 여부를 SOP 기준으로 판단
- External Key는 수동 수정 금지

실제 명령어는 repo에 존재하는 CLI를 기준으로 작성한다. 명령어가 불확실하면 추측하지 말고 “확인 필요”로 표시한다.

### 4. Actual Export / Sync Rerun Policy 작성

Notion actual export 또는 status sync 실패 시 재실행 정책을 정리한다.

반드시 포함할 원칙:

- CSV/JSON/Markdown/SQLite가 source-of-truth
- Notion sync 실패는 presentation layer 실패이며, source-of-truth commit 성공을 rollback하지 않음
- 같은 account_id / run_date / external_key 기준으로 idempotent update를 우선 시도
- create/update 중복 위험이 있으면 duplicate row audit 전까지 bulk rerun 금지
- paper_sandbox limited actual create/update까지만 검증된 상태
- multi-account bulk export 금지
- paper_default actual export 금지
- actual write/export는 명시적 confirm flag 또는 documented command가 있을 때만 허용
- Notion DB property/schema mismatch가 의심되면 actual export 금지, schema/mapping 확인 우선

### 5. 수동 Notion View 정리 절차 확정

PAPER16-1의 view 설계를 바탕으로 사용자가 직접 Notion에서 수행할 수동 절차를 문서화한다.

포함할 내용:

- 새 DB를 만들지 말고 기존 Daily Ops Status DB 안에서 view를 추가/수정
- linked database를 쓰더라도 같은 DB를 바라보는지 확인
- database duplicate로 별도 DB를 만들지 말 것
- Today Ops / By Account / Needs Action / Recent Sync / Review Closeout view 이름 고정
- 각 view별 filter / sort / group / visible properties 설정
- External Key, Page ID 등 내부 필드는 숨길 수 있지만 삭제하거나 수동 수정하지 말 것
- 수동 정리 후 SOP와 view 이름/필드명이 일치하는지 확인

### 6. SOP 최소 업데이트

필요한 경우 아래 문서에 최소 addendum만 추가한다.

- docs/operations/paper_daily_ops.md
- docs/operations/paper_notion_ops.md

SOP에는 다음을 명시한다.

- PAPER16-2는 command map / rerun policy / manual view setup 절차를 고정하는 단계
- 실제 Notion view 정리는 Codex 작업 완료 후 사용자가 수동으로 수행
- Codex는 Notion actual write/export를 실행하지 않음
- PAPER16-3에서는 수동 정리된 Notion 화면과 SOP 정합성을 점검할 수 있음

## 대상 파일

생성/수정 후보:

- docs/TRD/mfu_paper16_operator_command_map_and_rerun_policy.md
- docs/operations/paper_daily_ops.md
- docs/operations/paper_notion_ops.md

참고 파일:

- docs/TRD/mfu_paper16_daily_ops_status_dashboard_design.md
- docs/TRD/paper_ops_feature_roadmap_v1_1.md
- docs/TRD/mfu_paper15_multi_account_foundation_closeout.md
- scripts/paper.py
- scripts/export_paper_to_notion.py
- core/notion_mapping.py
- core/notion_settings.py

참고 파일은 필요한 경우만 읽고, 불필요하게 수정하지 않는다.

## Non-scope

이번 작업에서는 절대 하지 않는다.

- Python 코드 수정
- 신규 status 구현
- 신규 CLI 구현
- wrapper CLI 구현
- GUI 구현
- GitHub Actions 구현
- Notion button 구현
- Notion actual write/export 실행
- Notion DB create/update 실행
- Notion view 실제 생성/수정
- multi-account bulk export
- paper_default actual export
- paper_default migration
- Alert / Monitoring Report 구현
- Replay / Same-date Diff 구현
- Schema Drift Check 구현
- Universe 확장
- Strategy 확장
- strategy_profile_id / risk_profile_id / universe_id 실제 config 구현
- outputs/paper 원장 수정
- broker/API 연동
- cloud runner 작업

## 검증 명령

Windows CMD 기준으로 실행한다.

```cmd
git status --short
git diff -- docs\TRD\mfu_paper16_operator_command_map_and_rerun_policy.md docs\operations\paper_daily_ops.md docs\operations\paper_notion_ops.md
findstr /S /N /I "command map rerun policy Daily Ops Status workflow_status review_progress_status sync_status SYNC_FAILED REVIEW_PARTIAL REVIEW_DONE External Key source-of-truth actual export Notion view" docs\TRD\mfu_paper16_operator_command_map_and_rerun_policy.md docs\operations\paper_daily_ops.md docs\operations\paper_notion_ops.md
git diff --check
```

문서 작업이므로 pytest는 필수 아님. 단, 프로젝트 정책상 문서 변경에도 smoke가 필요하면 가장 가벼운 문서/CLI smoke만 수행하고 보고한다.

## 성공 기준

- 상태별 Operator Command Map이 작성됨
- workflow_status / review_progress_status / sync_status별 Meaning / Allowed Action / Forbidden Action / Next Command가 정리됨
- current status와 candidate/future status가 구분됨
- actual export / sync 실패 시 rerun policy가 문서화됨
- source-of-truth 성공 후 Notion sync 실패 시 rollback하지 않는 원칙이 명확함
- External Key 수동 수정 금지가 명확함
- 사용자가 Notion view를 수동 정리할 수 있는 절차가 작성됨
- 새 DB 생성이 아니라 기존 Daily Ops Status DB의 view를 정리하는 방식임이 명확함
- 코드 변경 없음
- outputs/paper 원장 변경 없음
- Notion actual write/export 실행 없음
- SOP 업데이트는 최소 addendum 수준을 넘지 않음
- PAPER16-3에서 수동 Notion view 정합성 점검으로 이어질 수 있음

## Git 주의사항

금지:

```cmd
git add .
git add -A
```

허용되는 stage 예시:

```cmd
git add docs\TRD\mfu_paper16_operator_command_map_and_rerun_policy.md
git add docs\operations\paper_daily_ops.md
git add docs\operations\paper_notion_ops.md
```

실제로 수정된 파일만 개별 stage한다.

기존 워크트리에 unrelated 변경이 남아 있을 수 있으므로, 커밋 전 반드시 git status --short로 확인한다. outputs/backtest_log.db, backtest_log.db, analysis_results/*.png, idea/PRD/TRD 쪽 unrelated 파일은 이번 커밋에 포함하지 않는다.

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 생성/수정한 파일
3. 상태별 Operator Command Map 요약
4. current status와 candidate/future status 구분 결과
5. actual export / sync rerun policy 요약
6. source-of-truth 성공 후 Notion sync 실패 시 rollback 정책
7. 수동 Notion view 정리 절차 요약
8. SOP 업데이트 여부
9. 코드 변경 여부
10. Notion actual write/export 실행 여부
11. outputs/paper 원장 변경 여부
12. git diff 요약
13. git diff --check 결과
14. 남은 리스크 또는 PAPER16-3 추천 작업

END MFU-PAPER16-2-OPERATOR-COMMAND-MAP-AND-RERUN-POLICY
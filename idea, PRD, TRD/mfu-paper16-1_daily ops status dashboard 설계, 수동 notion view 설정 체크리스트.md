BEGIN MFU-PAPER16-1-DAILY-OPS-STATUS-DASHBOARD-DESIGN

# Daily Ops Status Dashboard 설계 + 수동 Notion View 설정 체크리스트

## 목적

PAPER16의 첫 단계로 Daily Ops Status Dashboard의 운영 목적, 권장 Notion view 구조, 표시 필드 우선순위, 상태값 해석 기준, 수동 설정 체크리스트를 문서화한다.

이번 작업은 실제 Notion 화면을 수정하지 않는다. Codex는 repo 안의 기존 mapping/schema/SOP/roadmap을 기준으로 “사용자가 나중에 Notion에서 손으로 정리할 view 설계안”을 작성한다.

최종 목표는 운영자가 Notion Daily Ops Status 화면에서 다음을 판단할 수 있게 만드는 것이다.

- 특정 날짜의 특정 계좌가 현재 어느 운영 단계에 있는가
- plan / execution / review / sync 중 어디까지 끝났는가
- REVIEW_PARTIAL, REVIEW_DONE, SYNCED, SYNC_FAILED 등 상태가 무엇을 의미하는가
- 다음에 로컬 PC에서 어떤 명령 또는 수동 확인을 해야 하는가
- paper_sandbox 기준 dashboard 수동 정리 전에 어떤 필드/필터/정렬/그룹을 설정해야 하는가

## 배경

PAPER15에서 다중계좌 foundation은 closeout 가능한 수준으로 정리됐다.

현재 원칙:

- CSV / JSON / Markdown / SQLite가 source-of-truth
- Notion은 input UI / review UI / staging / presentation layer
- Daily Ops Status limited actual create/update는 PAPER15 진행 중 paper_sandbox 대상으로 이미 검증됨
- PAPER15 closeout/consistency check에서는 추가 Notion actual write/export를 실행하지 않음
- PAPER16-1에서도 Notion actual write/export는 금지

PAPER16-1은 Alert/Monitoring, Replay, Schema Drift, Universe 확장, Strategy 확장으로 가기 전에 Daily Ops Status Dashboard의 사람이 보는 운영 기준을 먼저 고정하는 작업이다.

## 구현 범위

### 1. 기존 구조 파악

다음 항목을 repo 기준으로 확인한다.

- Daily Ops Status mapping/schema가 어디에 정의되어 있는지
- Daily Ops Status exporter가 어떤 필드를 사용하고 있는지
- paper_daily_ops.md와 paper_notion_ops.md에서 Daily Ops Status가 어떻게 설명되어 있는지
- paper_ops_feature_roadmap_v1_1.md에서 PAPER16 이후 흐름이 어떻게 배치되어 있는지

### 2. Dashboard 목적 문서화

새 문서를 작성한다.

권장 파일명:

- docs/TRD/mfu_paper16_daily_ops_status_dashboard_design.md

문서에는 최소 아래 내용을 포함한다.

- Dashboard의 목적
- Dashboard가 해결해야 하는 운영 질문
- source-of-truth 원칙
- Notion의 역할 한계
- paper_sandbox 기준 우선 적용 원칙
- paper_default / multi-account bulk export / actual write 금지 원칙

### 3. 권장 Notion view 설계

Daily Ops Status DB에 대해 권장 view를 설계한다.

최소 권장 view:

1. Today Ops
   - 오늘 날짜 또는 선택 날짜 기준 운영 상태 확인
   - 계좌별 workflow_status / review_progress_status / sync_status 중심

2. By Account
   - account_id별 최근 운영 상태 확인
   - 계좌별 최근 run date, workflow_status, sync_status 확인

3. Needs Action
   - REVIEW_PARTIAL, WARNING, FAIL, SYNC_FAILED, NOT_SYNCED 등 조치 필요한 항목 확인
   - 운영자가 다음 행동을 결정하기 위한 view

4. Recent Sync
   - 최근 Notion sync 결과 확인
   - external_key, sync_status, synced_at 또는 이에 준하는 필드 중심

실제 Notion view를 만들지 말고, 문서에 다음 수준으로만 작성한다.

- view 이름
- 목적
- 권장 필터
- 권장 정렬
- 권장 그룹
- 표시할 필드
- 숨겨도 되는 필드
- 운영자가 이 view에서 판단해야 할 것

### 4. 필드 우선순위 정리

Daily Ops Status에서 운영자가 반드시 봐야 하는 필드와 숨겨도 되는 필드를 분리한다.

예시 분류:

Primary fields:

- date 또는 run_date
- account_id
- workflow_status
- review_progress_status
- review_completion_ratio
- sync_status
- external_key
- last_updated 또는 synced_at

Secondary fields:

- page_id
- source file path
- raw report path
- internal mapping/debug fields

실제 필드명은 repo의 mapping/schema를 기준으로 확인하고 문서에 맞춰 작성한다. 모르는 필드는 추측하지 말고 “확인 필요”로 남긴다.

### 5. 상태값 해석표 작성

workflow_status / review_progress_status / sync_status에 대해 운영자 기준 해석표를 작성한다.

예시 형식:

| Field | Value | Meaning | Operator action |
| --- | --- | --- | --- |

다만 새로운 status를 코드에 추가하지 않는다. 기존에 확인된 status를 우선 사용한다. 필요하지만 아직 구현되지 않은 상태값은 “candidate / future”로 분리한다.

### 6. 수동 Notion view 설정 체크리스트 작성

사용자가 Codex 작업 이후 Notion에서 직접 view를 정리할 수 있도록 체크리스트를 작성한다.

체크리스트에는 아래를 포함한다.

- 만들 view 이름
- 각 view의 filter 조건
- sort 조건
- group 조건
- 표시할 property
- 숨길 property
- 주의사항
- 실제 화면 정리 후 SOP와 이름/필드가 일치하는지 확인하는 방법

### 7. SOP 최소 업데이트

필요한 경우 아래 문서에 최소 addendum만 추가한다.

- docs/operations/paper_daily_ops.md
- docs/operations/paper_notion_ops.md

SOP에는 “PAPER16-1은 설계 단계이며 실제 Notion view 생성/수정은 사용자가 수동으로 수행한다”는 점을 명시한다.

## 대상 파일

주요 생성/수정 후보:

- docs/TRD/mfu_paper16_daily_ops_status_dashboard_design.md
- docs/operations/paper_daily_ops.md
- docs/operations/paper_notion_ops.md

참고만 할 파일:

- docs/TRD/mfu_paper15_multi_account_foundation_closeout.md
- docs/TRD/paper_ops_feature_roadmap_v1_1.md
- core/notion_mapping.py
- core/notion_settings.py
- core/notion_client.py
- scripts/export_paper_to_notion.py
- scripts/paper.py

참고 파일은 필요한 경우만 읽고, 불필요한 수정은 하지 않는다.

## Non-scope

이번 작업에서는 절대 하지 않는다.

- Python 코드 수정
- Daily Ops Status exporter 수정
- 신규 CLI 구현
- wrapper CLI 구현
- GUI 구현
- GitHub Actions 구현
- Notion button 구현
- Notion actual write/export 실행
- Notion DB actual create/update
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
git diff -- docs\TRD\mfu_paper16_daily_ops_status_dashboard_design.md docs\operations\paper_daily_ops.md docs\operations\paper_notion_ops.md
findstr /S /N /I "Daily Ops Status Today Ops By Account Needs Action Recent Sync workflow_status review_progress_status sync_status actual write export source-of-truth" docs\TRD\mfu_paper16_daily_ops_status_dashboard_design.md docs\operations\paper_daily_ops.md docs\operations\paper_notion_ops.md
git diff --check
```

문서 작업이므로 pytest는 필수 아님. 단, 프로젝트 정책상 문서 변경에도 smoke가 필요하면 가장 가벼운 smoke만 수행하고 보고한다.

## 성공 기준

- Daily Ops Status Dashboard의 목적이 명확히 문서화됨
- 권장 Notion view가 최소 3개 이상 제안됨
- 각 view별 필터/정렬/그룹/표시 필드/숨김 필드가 정리됨
- workflow_status / review_progress_status / sync_status 해석표가 작성됨
- 수동 Notion view 설정 체크리스트가 작성됨
- source-of-truth 원칙이 유지됨
- Notion은 presentation/review layer임이 명확함
- 실제 Notion actual write/export를 실행하지 않음
- Python 코드 변경 없음
- outputs/paper 원장 변경 없음
- SOP 업데이트는 최소 addendum 수준을 넘지 않음
- 다음 단계인 사용자의 Notion view 수동 정리와 PAPER16-2 SOP refinement로 자연스럽게 이어짐

## Git 주의사항

금지:

```cmd
git add .
git add -A
```

허용되는 stage 예시:

```cmd
git add docs\TRD\mfu_paper16_daily_ops_status_dashboard_design.md
git add docs\operations\paper_daily_ops.md
git add docs\operations\paper_notion_ops.md
```

실제로 수정된 파일만 개별 stage한다.

기존 워크트리에 unrelated 변경이 남아 있을 수 있으므로, 커밋 전 반드시 git status --short로 확인한다. outputs/backtest_log.db, backtest_log.db, analysis_results/*.png, idea/PRD/TRD 쪽 unrelated 파일은 이번 커밋에 포함하지 않는다.

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 생성/수정한 파일
3. Daily Ops Status Dashboard 목적 요약
4. 제안한 Notion view 목록
5. 각 view의 핵심 필터/정렬/표시 필드 요약
6. 상태값 해석표 요약
7. 수동 Notion view 설정 체크리스트 요약
8. SOP 업데이트 여부
9. 코드 변경 여부
10. Notion actual write/export 실행 여부
11. outputs/paper 원장 변경 여부
12. git diff 요약
13. git diff --check 결과
14. 남은 리스크 또는 PAPER16-2 추천 작업

END MFU-PAPER16-1-DAILY-OPS-STATUS-DASHBOARD-DESIGN
BEGIN MFU-PAPER16-DOCS-CONSOLIDATE-COMMIT

# PAPER16 문서 작업 단일 커밋 정리

## 목적

PAPER16에서 진행한 문서 작업을 하나의 커밋으로 정리한다.

포함 대상은 PAPER16-1 / PAPER16-2 / PAPER16-2A 문서 작업이다.

- PAPER16-1: Daily Ops Status Dashboard 설계
- PAPER16-2: Operator Command Map / Rerun Policy
- PAPER16-2A: 커밋 전 wording fix

이번 작업은 커밋 정리 작업이다.
새로운 기능 구현, 문서 내용 확장, Notion actual write/export, outputs/paper 원장 수정은 하지 않는다.

## 배경

PAPER16은 Daily Ops Status를 운영자가 보는 presentation dashboard로 정리하는 단계다.

PAPER16에서 정리한 핵심 내용:

- Daily Ops Status Dashboard view 설계
- 수동 Notion view 설정 체크리스트
- Workflow Status / Review Progress Status / Sync Status별 operator command map
- actual export / sync rerun policy
- source-of-truth rollback 금지 원칙
- External Key 수동 수정 금지
- 기존 Daily Ops Status DB 안에서 view만 추가/수정하고 duplicate DB를 만들지 않는 원칙

CSV/JSON/Markdown/SQLite는 source-of-truth이고, Notion은 input/review/staging/presentation layer다.

## 포함할 파일

PAPER16 커밋 대상 후보는 아래 4개다.

```cmd
docs\TRD\mfu_paper16_daily_ops_status_dashboard_design.md
docs\TRD\mfu_paper16_operator_command_map_and_rerun_policy.md
docs\operations\paper_daily_ops.md
docs\operations\paper_notion_ops.md
```

단, `docs\operations\paper_daily_ops.md`, `docs\operations\paper_notion_ops.md`에 PAPER15 변경이 아직 커밋되지 않은 상태로 섞여 있다면 주의한다.

## 작업 범위

### 1. 워크트리 상태 확인

먼저 현재 상태를 확인한다.

```cmd
git status --short
```

다음 unrelated 파일은 이번 커밋에 포함하지 않는다.

```text
outputs/backtest_log.db
backtest_log.db
analysis_results/market_regime_timeline.png
idea, PRD, TRD/* 관련 임시 지시문 또는 기존 변경
tmp* 또는 접근 불가 임시 폴더
```

### 2. PAPER16 대상 diff 확인

아래 명령으로 PAPER16 관련 변경만 확인한다.

```cmd
git diff -- docs\TRD\mfu_paper16_daily_ops_status_dashboard_design.md docs\TRD\mfu_paper16_operator_command_map_and_rerun_policy.md docs\operations\paper_daily_ops.md docs\operations\paper_notion_ops.md
```

신규 untracked TRD 파일은 `git diff`에 본문이 안 나올 수 있으므로, 필요하면 아래로 본문을 확인한다.

```cmd
type docs\TRD\mfu_paper16_daily_ops_status_dashboard_design.md
type docs\TRD\mfu_paper16_operator_command_map_and_rerun_policy.md
```

### 3. PAPER15 변경 혼입 여부 확인

다음 파일에는 PAPER15 addendum과 PAPER16 addendum이 함께 들어 있을 수 있다.

```cmd
docs\operations\paper_daily_ops.md
docs\operations\paper_notion_ops.md
```

확인 기준:

- PAPER16만 커밋할 수 있으면 PAPER16 변경만 stage한다.
- PAPER15 변경이 같은 hunk에 섞여 있어서 안전하게 분리하기 어렵다면, 무리하게 커밋하지 말고 결과 보고에 “PAPER15 변경과 PAPER16 변경이 같은 SOP 파일에 혼재되어 있어 git add -p 또는 선행 PAPER15 커밋이 필요함”이라고 보고한다.
- `git add .`, `git add -A`는 절대 사용하지 않는다.

가능하면 아래 방식 중 하나를 선택한다.

A안: PAPER16 변경만 안전하게 stage 가능할 때

```cmd
git add docs\TRD\mfu_paper16_daily_ops_status_dashboard_design.md
git add docs\TRD\mfu_paper16_operator_command_map_and_rerun_policy.md
git add -p docs\operations\paper_daily_ops.md
git add -p docs\operations\paper_notion_ops.md
```

B안: SOP 파일의 PAPER15/PAPER16 변경이 이미 함께 정리되어 있고, 이전 PAPER15 문서 변경도 별도 커밋 예정이 아니라면 중단 후 보고한다. 이 경우 사용자가 “PAPER15+PAPER16 통합 docs 커밋”으로 바꿀지 결정해야 한다.

### 4. diff check

PAPER16 대상 파일에 대해 diff check를 수행한다.

```cmd
git diff --check -- docs\TRD\mfu_paper16_daily_ops_status_dashboard_design.md docs\TRD\mfu_paper16_operator_command_map_and_rerun_policy.md docs\operations\paper_daily_ops.md docs\operations\paper_notion_ops.md
```

대상 파일에서 trailing whitespace 문제가 나오면 해당 줄 끝 공백만 제거한다.
unrelated 파일의 diff check 실패는 이번 커밋 blocker로 보지 말고 결과 보고에 분리해서 적는다.

### 5. staged diff 확인

커밋 전 반드시 staged diff를 확인한다.

```cmd
git diff --cached --name-only
git diff --cached
```

staged 파일에 아래가 들어가면 안 된다.

```text
outputs/backtest_log.db
backtest_log.db
analysis_results/*
idea, PRD, TRD/*
```

PAPER16 커밋에는 원칙적으로 아래 파일만 들어가야 한다.

```text
docs/TRD/mfu_paper16_daily_ops_status_dashboard_design.md
docs/TRD/mfu_paper16_operator_command_map_and_rerun_policy.md
docs/operations/paper_daily_ops.md
docs/operations/paper_notion_ops.md
```

### 6. 커밋 생성

staged diff가 PAPER16 문서 작업만 포함한다면 커밋한다.

권장 커밋 메시지:

```cmd
git commit -m "docs: define PAPER16 daily ops status dashboard"
```

커밋 후 아래를 확인한다.

```cmd
git status --short
git log -1 --stat
```

## Non-scope

이번 작업에서는 절대 하지 않는다.

- Python 코드 수정
- 문서 내용 신규 확장
- Notion actual write/export 실행
- Notion DB/view 생성 또는 수정
- outputs/paper 원장 수정
- backtest DB 수정
- analysis_results 파일 stage
- paper_default migration
- multi-account bulk export
- Alert / Replay / Schema Drift / Universe / Strategy 작업
- GitHub Actions / GUI / wrapper CLI 구현

## Git 금지 사항

절대 사용 금지:

```cmd
git add .
git add -A
```

## 성공 기준

- PAPER16 관련 문서 작업이 하나의 커밋으로 정리됨
- 신규 PAPER16 TRD 2개가 커밋에 포함됨
- PAPER16 관련 SOP addendum이 커밋에 포함됨
- unrelated 파일이 staged/commit되지 않음
- outputs/backtest_log.db, backtest_log.db, analysis_results 파일이 커밋에 포함되지 않음
- Notion actual write/export 실행 없음
- outputs/paper 원장 변경 없음
- `git diff --check` 대상 파일 기준 통과
- 커밋 후 `git log -1 --stat`로 커밋 내용을 확인함

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 커밋 생성 여부
3. 커밋 SHA
4. 커밋 메시지
5. 커밋에 포함된 파일
6. 제외한 unrelated 파일
7. PAPER15 변경 혼입 여부 판단
8. git diff --check 결과
9. Notion actual write/export 실행 여부
10. outputs/paper 원장 변경 여부
11. 남은 워크트리 변경
12. 다음 단계: Notion view 수동 정리 또는 PAPER16-3 준비

END MFU-PAPER16-DOCS-CONSOLIDATE-COMMIT

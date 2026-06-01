BEGIN MFU-PAPER14-DAILY-OPS-REFACTOR

# 목적

`docs/operations/paper_daily_ops.md`를 PAPER14 Notion closeout 이후의 최신 운영 흐름 기준으로 리팩토링한다.

이번 작업은 기능 구현이 아니라 문서 정리 작업이다. 현재 `paper_daily_ops.md`에는 오래된 section과 최신 addendum이 병존할 가능성이 있으므로, 실제 paper trading daily ops에서 매일 참고할 수 있는 단일 canonical 운영 문서로 정리한다.

# 배경

현재 기준 베이스라인 SHA:

```text
ffd2350f5933376f4bc2b9fec26901d76f0b797d
```

최근 closeout 커밋:

```text
eed9132 PAPER14: document Notion closeout
```

참고 문서:

- `docs/TRD/mfu_paper14_notion_closeout.md`
- `docs/operations/paper_notion_ops.md`
- `docs/operations/paper_daily_ops.md`

PAPER14 Notion 원칙:

- Notion = 입력 UI / 검토 UI / staging layer
- CSV / JSON / Markdown / SQLite = source of truth
- Python = validation / preview / commit / append / export 주체

# 작업 파일

수정 대상:

- `docs/operations/paper_daily_ops.md`

참고만 할 파일:

- `docs/TRD/mfu_paper14_notion_closeout.md`
- `docs/operations/paper_notion_ops.md`

이번 MFU에서는 참고 파일을 수정하지 않는다.

# 작업 범위

`paper_daily_ops.md`를 최신 daily loop 기준으로 재구성한다.

반드시 포함할 섹션:

## 1. Purpose / Scope

- 이 문서가 실제 paper trading daily ops용 운영 문서임을 명시
- Notion closeout 이후 최신 daily loop 기준 문서임을 명시
- Notion은 source of truth가 아니라 입력/검토/staging layer임을 명시

## 2. Source-of-truth 원칙

아래 내용을 명확히 정리한다.

- Notion = 입력 UI / 검토 UI / staging layer
- CSV / JSON / Markdown / SQLite = source of truth
- Python = validation / preview / commit / append / export 주체
- source-of-truth commit 성공 후 Notion sync 실패 시 원장 rollback 금지
- 같은 commit report로 status sync만 재실행

## 3. 최신 Canonical Daily Loop

아래 흐름을 단일 canonical daily loop로 정리한다.

- Prepare / preflight
- Daily Plan 생성
- Daily Plan Notion export
- Notion에서 Daily Plan 확인
- 실제 action 수행
- Notion Manual Executions 입력
- Manual Executions preview
- execution commit
- account / position / current_state 갱신
- Manual Executions status sync
- Daily Review Summary export
- Notion에서 Daily Review Summary 확인
- Notion Manual Reviews 입력
- Manual Reviews preview
- review append
- Manual Reviews status sync
- Weekly / Benchmark / Account Snapshot export

## 4. 스마트폰 가능 단계 / 로컬 PC 필수 단계

스마트폰 가능:

- Daily Plan 확인
- Manual Executions 입력
- Daily Review Summary 확인
- Manual Reviews 입력
- Notion status 확인

로컬 PC 필수:

- preview 실행
- commit / append 실행
- ledger / review log / state 갱신
- status back-write
- Notion export / sync

## 5. Safety Policy

아래 정책을 명확히 정리한다.

- FAIL 있으면 commit / append 금지
- WARNING 있으면 기본 차단
- `--allow-warnings`를 명시했을 때만 commit / append 허용
- WARNING 허용 시 운영자가 사유를 기록해야 함
- preview 없이 commit / append 금지
- Notion 입력값은 원장 반영 전까지 staging data로만 취급

## 6. Status Policy

아래 용어를 운영 관점에서 짧게 설명한다.

- READY
- COMMITTED
- SYNCED
- PASS
- WARNING
- FAIL
- created
- updated
- dry-run
- `--allow-warnings`

각 status가 Manual Executions / Manual Reviews / Notion export 흐름에서 어떤 의미인지 정리한다.

## 7. Daily Checklist

운영자가 하루 단위로 따라 할 수 있는 checklist를 작성한다.

권장 구조:

- Before market / prepare
- Plan review
- Execution input
- Preview
- Commit
- Status sync
- Daily review
- Manual review
- End-of-day export/check

## 8. Failure / Retry Policy

아래 상황별 처리 방침을 정리한다.

- preview FAIL
- preview WARNING
- commit 성공 후 Notion sync 실패
- Notion API / network 실패
- Notion 입력 누락
- 중복 입력 의심
- source artifact 미생성
- status back-write 실패

## 9. Relationship with Other Docs

다른 문서와의 관계를 명확히 정리한다.

- `docs/TRD/mfu_paper14_notion_closeout.md`
  - PAPER14 전체 범위 / 결정 기록
- `docs/operations/paper_notion_ops.md`
  - Notion-specific operation detail
- `docs/operations/paper_daily_ops.md`
  - 매일 보는 canonical daily operation guide

## 10. Deprecated / Historical Notes

기존 문서에 오래된 절차가 있다면 삭제하거나, 삭제가 위험하면 `Historical / Deprecated` 섹션으로 이동한다.

최신 daily loop와 충돌하는 오래된 절차가 본문에 남아 있으면 안 된다.

# 금지 사항

- Python 코드 수정 금지
- CSV / JSON / SQLite / PNG / report / output 수정 금지
- Notion actual export/write/sync 실행 금지
- Manual Execution commit 실행 금지
- Manual Review append 실행 금지
- DB schema 변경 금지
- 새로운 기능 설계 추가 금지
- Performance Summary 구현 금지
- GitHub Actions / cloud runner / broker API 구현 금지
- `git add .` 금지
- `git add -A` 금지
- unrelated worktree 파일 수정/스테이지 금지

# 작업 절차

## 1. 현재 상태 확인

Windows CMD:

```cmd
git rev-parse --short HEAD
git status --short
```

확인 사항:

- HEAD가 `eed9132`인지 확인
- unrelated worktree 변경이 있어도 이번 작업에 포함하지 말 것

## 2. 참고 문서 확인

Windows CMD:

```cmd
type docs\TRD\mfu_paper14_notion_closeout.md
type docs\operations\paper_notion_ops.md
type docs\operations\paper_daily_ops.md
```

## 3. 문서 리팩토링

`docs/operations/paper_daily_ops.md`를 수정한다.

요구사항:

- 최신 daily loop 중심으로 재배열
- 중복 section 정리
- 오래된 section 제거 또는 Historical / Deprecated로 이동
- 운영자가 하루에 따라 할 수 있는 순서로 정리
- 명령어 예시는 Windows CMD 기준 유지
- 불확실한 명령어는 새로 만들지 말고 기존 문서에 있는 명령어만 정리
- 구현 파일명 / CLI 옵션을 추측하지 말 것

## 4. 변경 확인

Windows CMD:

```cmd
git diff -- docs\operations\paper_daily_ops.md
git diff --check -- docs\operations\paper_daily_ops.md
git status --short
```

## 5. Stage / Commit

반드시 필요한 파일만 stage한다.

Windows CMD:

```cmd
git add docs\operations\paper_daily_ops.md
git commit -m "PAPER14: refactor paper daily ops guide"
```

# 성공 기준

- `docs/operations/paper_daily_ops.md`가 최신 PAPER14 Notion daily loop 기준으로 정리됨
- 오래된 절차와 최신 절차의 충돌이 제거됨
- source-of-truth 원칙이 명확히 반영됨
- 스마트폰 가능 단계 / 로컬 PC 필수 단계가 분리됨
- FAIL / WARNING / `--allow-warnings` / sync retry 정책이 운영자가 바로 볼 수 있게 정리됨
- 코드 및 output 파일 변경 없음
- unrelated worktree 파일이 commit에 포함되지 않음
- `git diff --check` 통과
- commit 생성 완료

# 결과 보고 형식

작업 완료 후 아래 형식으로 보고한다.

1. Summary
   - 무엇을 리팩토링했는지
   - 기능/코드 변경이 있었는지

2. 기준 커밋 확인 결과
   - 시작 HEAD
   - 최종 HEAD
   - 새 commit hash / message

3. 변경 파일
   - 수정한 파일 목록

4. 문서 구조 변경 요약
   - 새 섹션 구조
   - 삭제/이동한 오래된 내용
   - canonical daily loop 정리 방식

5. 반영한 운영 정책
   - source-of-truth 원칙
   - status/safety 정책
   - WARNING/FAIL 정책
   - Notion sync 실패 retry 정책

6. 스마트폰/로컬 PC 역할 분리
   - 어떻게 정리했는지

7. 테스트 / 검증
   - 실행한 명령
   - 결과
   - pytest 미실행 시 이유

8. Stage하지 않은 파일
   - unrelated worktree 파일이 남아 있다면 목록화
   - 이번 commit에 포함하지 않았음을 명시

9. Risks and limitations
   - 여전히 남은 문서 중복
   - 다른 문서와의 불일치 가능성
   - 추후 정리 필요 항목

10. Suggested next step
   - 다음 MFU 제안

END MFU-PAPER14-DAILY-OPS-REFACTOR
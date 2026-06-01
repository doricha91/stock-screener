# MFU-PAPER14-DAILY-OPS-REFACTOR 작업 지시문: paper daily ops guide 리팩토링

## 목적

PAPER14 Notion closeout 이후 `docs/operations/paper_daily_ops.md`를 최신 daily ops 기준으로 리팩토링한다.

이번 작업은 기능 구현이 아니라 운영 문서 정리 작업이다.

반드시 명시:

```text
이번 MFU-PAPER14-DAILY-OPS-REFACTOR는 paper_daily_ops.md를 최신 PAPER14 Notion daily loop 기준으로 리팩토링하는 작업이며, Python 코드 수정, Notion actual write/export, Manual Execution commit, Manual Review append, paper trading ledger 수정은 수행하지 않는다.
```

---

## 기준 커밋

기준 커밋:

```text
ffd2350f5933376f4bc2b9fec26901d76f0b797d
```

최근 로그에 아래 커밋이 있어야 한다.

```text
eed9132 PAPER14: document Notion closeout
```

작업 전 확인:

```cmd
cd /d D:\python\StockScreener
git rev-parse HEAD
git log --oneline -15
git status --short
```

`eed9132` 이후 상태가 아니거나 closeout 문서가 없으면 중단하고 보고한다.

---

## 배경

PAPER14 Notion closeout에서 전체 Notion 연동 범위가 문서화됐다.

확정 원칙:

```text
Notion = 입력 UI / 검토 UI / staging layer
CSV / JSON / Markdown / SQLite = source of truth
Python = validation / preview / commit / append / export 주체
```

현재 남은 리스크:

```text
paper_daily_ops.md에 오래된 section과 최신 addendum이 병존
실제 운영자가 어떤 절차가 최신인지 헷갈릴 수 있음
WARNING / FAIL / Notion sync 실패 정책이 흩어져 있을 수 있음
스마트폰 가능 단계와 로컬 PC 필수 단계가 명확히 분리되어 있지 않을 수 있음
```

따라서 `paper_daily_ops.md`를 매일 보는 canonical daily operation guide로 정리한다.

---

## 수정 파일

수정 대상:

```text
docs/operations/paper_daily_ops.md
```

참고 파일:

```text
docs/TRD/mfu_paper14_notion_closeout.md
docs/operations/paper_notion_ops.md
```

참고 파일은 읽기만 하고 수정하지 않는다.

---

## 리팩토링 요구사항

`paper_daily_ops.md`에 아래 섹션을 포함한다.

```text
1. Purpose / Scope
2. Source-of-truth 원칙
3. Canonical Daily Loop
4. 스마트폰 가능 단계 / 로컬 PC 필수 단계
5. Safety Policy
6. Status Policy
7. Daily Checklist
8. Failure / Retry Policy
9. Relationship with Other Docs
10. Historical / Deprecated Notes
```

---

## Canonical Daily Loop

아래 흐름을 최신 daily loop로 정리한다.

```text
Prepare / preflight
→ Daily Plan 생성
→ Daily Plan Notion export
→ Notion에서 Daily Plan 확인
→ 실제 action 수행
→ Notion Manual Executions 입력
→ Manual Executions preview
→ execution commit
→ account / position / current_state 갱신
→ Manual Executions status sync
→ Daily Review Summary export
→ Notion에서 Daily Review Summary 확인
→ Notion Manual Reviews 입력
→ Manual Reviews preview
→ review append
→ Manual Reviews status sync
→ Weekly / Benchmark / Account Snapshot export
```

최신 loop와 충돌하는 오래된 절차는 본문에 남기지 않는다. 삭제가 위험하면 `Historical / Deprecated Notes`로 이동한다.

---

## 스마트폰 / 로컬 PC 역할 구분

스마트폰 가능:

```text
Daily Plan 확인
Manual Executions 입력
Daily Review Summary 확인
Manual Reviews 입력
Notion status 확인
```

로컬 PC 필수:

```text
preview 실행
commit / append 실행
ledger / review log / state 갱신
status back-write
Notion export / sync
```

---

## Safety / Status 정책

문서에 아래 정책을 명확히 반영한다.

```text
FAIL 있으면 commit / append 금지
WARNING 있으면 기본 차단
--allow-warnings를 명시했을 때만 commit / append 허용
WARNING 허용 시 운영자가 사유를 기록해야 함
preview 없이 commit / append 금지
Notion 입력값은 원장 반영 전까지 staging data로만 취급
source-of-truth commit 성공 후 Notion sync 실패 시 원장 rollback 금지
같은 commit report로 status sync만 재실행
```

아래 용어를 운영 관점에서 설명한다.

```text
READY
COMMITTED
SYNCED
PASS
WARNING
FAIL
created
updated
dry-run
--allow-warnings
```

---

## 다른 문서와의 관계

아래 관계를 명시한다.

```text
docs/TRD/mfu_paper14_notion_closeout.md
= PAPER14 전체 범위 / 결정 기록

docs/operations/paper_notion_ops.md
= Notion-specific operation detail

docs/operations/paper_daily_ops.md
= 매일 보는 canonical daily operation guide
```

---

## 금지 사항

```text
Python 코드 수정 금지
CSV / JSON / SQLite / PNG / report / output 수정 금지
Notion actual export/write/sync 실행 금지
Manual Execution commit 실행 금지
Manual Review append 실행 금지
DB schema 변경 금지
Performance Summary 구현 금지
GitHub Actions / cloud runner / broker API 구현 금지
closeout 문서 수정 금지
paper_notion_ops.md 수정 금지
git add . 금지
git add -A 금지
unrelated worktree 파일 수정/스테이지 금지
```

---

## 검증 명령

Windows CMD 기준:

```cmd
cd /d D:\python\StockScreener

git diff -- docs\operations\paper_daily_ops.md
git diff --check -- docs\operations\paper_daily_ops.md
git status --short
```

문서 작업만 수행하므로 pytest는 필수 아님.

다만 아래를 수동 확인한다.

```text
최신 daily loop가 canonical 형태로 정리됐는가
source-of-truth 원칙이 명확한가
WARNING / FAIL / --allow-warnings 정책이 명확한가
스마트폰 가능 단계와 로컬 PC 필수 단계가 분리됐는가
Notion sync 실패 시 rollback 금지 / status sync 재실행 정책이 포함됐는가
오래된 절차가 최신 본문과 충돌하지 않는가
```

---

## 커밋 정책

필요한 파일만 stage한다.

```cmd
git add docs\operations\paper_daily_ops.md
git diff --cached --name-only
git commit -m "PAPER14: refactor paper daily ops guide"
```

CSV/output/DB/PNG/unrelated 문서는 stage하지 않는다.

---

## 성공 기준

```text
paper_daily_ops.md가 최신 PAPER14 Notion daily loop 기준으로 정리된다.
오래된 절차와 최신 절차의 충돌이 제거된다.
source-of-truth 원칙이 명확히 반영된다.
스마트폰 가능 단계 / 로컬 PC 필수 단계가 분리된다.
FAIL / WARNING / --allow-warnings / sync retry 정책이 운영자가 바로 볼 수 있게 정리된다.
코드 및 output 파일 변경이 없다.
unrelated worktree 파일이 commit에 포함되지 않는다.
git diff --check가 통과한다.
commit이 생성된다.
```

---

## 결과 보고 형식

5천자 이내.

```text
1. Summary
2. 기준 커밋 확인 결과
3. 변경 파일
4. 문서 구조 변경 요약
5. canonical daily loop 정리 방식
6. 반영한 source-of-truth 원칙
7. 반영한 safety/status 정책
8. 스마트폰/로컬 PC 역할 분리
9. Deprecated/Historical 처리 내용
10. 테스트/검증 결과
11. 커밋 hash와 message
12. stage하지 않은 파일
13. 남은 리스크
14. 다음 MFU 제안
```

반드시 명시:

```text
이번 MFU-PAPER14-DAILY-OPS-REFACTOR는 paper_daily_ops.md를 최신 PAPER14 Notion daily loop 기준으로 리팩토링하는 작업이며, Python 코드 수정, Notion actual write/export, Manual Execution commit, Manual Review append, paper trading ledger 수정은 수행하지 않았다.
```


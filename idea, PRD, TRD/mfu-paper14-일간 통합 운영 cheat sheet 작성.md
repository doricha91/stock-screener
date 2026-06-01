# MFU-PAPER14-DAILY-NOTION-CHEAT-SHEET 작업 지시문: 일간 통합 운영 cheat sheet 작성

## 목적

PAPER14 Notion 운영 문서 정렬 이후, 운영자가 매일 실제로 따라 볼 수 있는 1페이지 수준의 통합 운영 cheat sheet를 작성한다.

이번 작업은 기능 구현이 아니라 문서 추가 작업이다.

반드시 명시:

```text
이번 MFU-PAPER14-DAILY-NOTION-CHEAT-SHEET는 paper_daily_ops.md와 paper_notion_ops.md를 기반으로 일간 통합 운영 cheat sheet를 추가하는 작업이며, Python 코드 수정, Notion mapping/schema 변경, Notion actual write/export, Manual Execution commit, Manual Review append, paper trading ledger 수정은 수행하지 않는다.
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
ea79d79 PAPER14: refactor paper daily ops guide
e4efc4b PAPER14: align Notion ops SOP with daily guide
```

작업 전 확인:

```cmd
cd /d D:\python\StockScreener
git rev-parse HEAD
git log --oneline -15
git status --short
```

`e4efc4b` 이후 상태가 아니거나 daily ops / notion ops 정렬 커밋이 없으면 중단하고 보고한다.

---

## 배경

현재 문서 역할은 다음과 같다.

```text
docs/TRD/mfu_paper14_notion_closeout.md
= PAPER14 전체 범위 / 결정 기록

docs/operations/paper_daily_ops.md
= 매일 보는 canonical daily operation guide

docs/operations/paper_notion_ops.md
= Notion DB별 세부 입력/확인/동기화 SOP
```

남은 문제:

```text
운영자가 매일 실제로 볼 최소 절차가 아직 1페이지로 압축되어 있지 않음
daily ops와 notion ops를 둘 다 봐야 하는 전제가 남아 있음
반복 운영 중 preview/commit/status sync 순서를 놓칠 위험이 있음
```

이번 MFU에서는 상세 SOP를 다시 늘리지 않고, 실제 운영자가 하루 단위로 체크할 최소 절차만 압축한다.

---

## 추가 파일

새로 추가할 파일:

```text
docs/operations/paper_daily_notion_cheat_sheet.md
```

참고 파일:

```text
docs/operations/paper_daily_ops.md
docs/operations/paper_notion_ops.md
docs/TRD/mfu_paper14_notion_closeout.md
```

참고 파일은 읽기만 하고 수정하지 않는다.

---

## 문서 작성 요구사항

cheat sheet는 짧고 실행 순서 중심이어야 한다.

포함할 섹션:

```text
1. Purpose
2. 절대 원칙
3. 오늘의 운영 순서
4. 스마트폰에서 할 일
5. 로컬 PC에서 할 일
6. commit / append 전 확인
7. WARNING / FAIL 처리
8. Notion sync 실패 시 처리
9. 오늘 마감 전 확인
10. 자세한 문서 링크
```

---

## 반드시 포함할 절대 원칙

```text
Notion = 입력 UI / 검토 UI / staging layer
CSV / JSON / Markdown / SQLite = source of truth
Python = validation / preview / commit / append / export 주체
preview 없이 commit / append 금지
FAIL 있으면 commit / append 금지
WARNING 있으면 기본 차단
--allow-warnings가 있을 때만 허용
source-of-truth commit 성공 후 Notion sync 실패 시 rollback 금지
같은 commit report로 status sync만 재실행
```

---

## 오늘의 운영 순서

아래 흐름을 체크리스트로 압축한다.

```text
[ ] Prepare / preflight
[ ] Daily Plan 생성
[ ] Daily Plan Notion export
[ ] Notion에서 Daily Plan 확인
[ ] 실제 action 수행
[ ] Notion Manual Executions 입력
[ ] Manual Executions preview
[ ] execution commit
[ ] account / position / current_state 갱신 확인
[ ] Manual Executions status sync
[ ] Daily Review Summary export
[ ] Notion에서 Daily Review Summary 확인
[ ] Notion Manual Reviews 입력
[ ] Manual Reviews preview
[ ] review append
[ ] Manual Reviews status sync
[ ] Weekly / Benchmark / Account Snapshot export
```

세부 명령어는 추측하지 않는다. 기존 문서에서 확인 가능한 명령어만 사용한다. 불확실하면 “세부 명령은 paper_notion_ops.md 참조”라고 적는다.

---

## 스마트폰 / 로컬 PC 구분

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

스마트폰에서 commit / append 가능한 것처럼 쓰지 않는다.

---

## WARNING / FAIL 처리

반드시 아래 정책을 짧게 적는다.

```text
PASS = 다음 단계 진행 가능
WARNING = 기본 차단, --allow-warnings 필요
FAIL = commit / append 금지
WARNING 허용 시 사유 기록
동일 preview 재사용 시 duplicate / stale 여부 확인
```

---

## Notion sync 실패 처리

아래를 명시한다.

```text
source-of-truth commit / append가 성공했다면 Notion sync 실패는 원장 실패가 아니다.
ledger / review log rollback 금지.
같은 commit report로 status sync만 재실행.
재실행 전 page_id / canonical_key / commit report 경로를 확인.
```

---

## 금지 사항

```text
Python 코드 수정 금지
Notion mapping/schema 변경 금지
core/notion_mapping.py 수정 금지
CSV / JSON / SQLite / PNG / report / output 수정 금지
Notion actual export/write/sync 실행 금지
Manual Execution commit 실행 금지
Manual Review append 실행 금지
DB schema 변경 금지
Performance Summary 구현 금지
paper_daily_ops.md 수정 금지
paper_notion_ops.md 수정 금지
closeout TRD 수정 금지
git add . 금지
git add -A 금지
unrelated worktree 파일 수정/스테이지 금지
```

---

## 검증 명령

Windows CMD 기준:

```cmd
cd /d D:\python\StockScreener

git diff -- docs\operations\paper_daily_notion_cheat_sheet.md
git diff --check -- docs\operations\paper_daily_notion_cheat_sheet.md
git status --short
```

문서 추가 작업이므로 pytest는 필수 아님.

수동 확인:

```text
1페이지 수준으로 압축됐는가
daily ops와 notion ops의 정책과 충돌하지 않는가
Notion을 source of truth로 오해하게 만들지 않는가
스마트폰/PC 역할이 명확한가
WARNING/FAIL 처리 기준이 명확한가
sync 실패 시 rollback 금지 원칙이 포함됐는가
실제 CLI나 mapping을 추측하지 않았는가
```

---

## 커밋 정책

필요한 파일만 stage한다.

```cmd
git add docs\operations\paper_daily_notion_cheat_sheet.md
git diff --cached --name-only
git commit -m "PAPER14: add daily Notion ops cheat sheet"
```

CSV/output/DB/PNG/unrelated 파일은 stage하지 않는다.

---

## 성공 기준

```text
paper_daily_notion_cheat_sheet.md가 추가된다.
문서가 daily ops + notion ops의 압축본 역할을 한다.
source-of-truth 원칙이 명확하다.
스마트폰 가능 단계와 로컬 PC 필수 단계가 분리된다.
WARNING / FAIL / --allow-warnings / sync retry 정책이 짧게 정리된다.
mapping/schema/code/output 변경이 없다.
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
4. cheat sheet 문서 구조
5. 반영한 daily loop
6. 반영한 source-of-truth 원칙
7. 반영한 WARNING/FAIL/sync retry 정책
8. 스마트폰/로컬 PC 역할 구분
9. mapping/schema/code/output 수정 여부
10. 테스트/검증 결과
11. 커밋 hash와 message
12. stage하지 않은 파일
13. 남은 리스크
14. 다음 MFU 제안
```

반드시 명시:

```text
이번 MFU-PAPER14-DAILY-NOTION-CHEAT-SHEET는 paper_daily_ops.md와 paper_notion_ops.md를 기반으로 일간 통합 운영 cheat sheet를 추가하는 작업이며, Python 코드 수정, Notion mapping/schema 변경, Notion actual write/export, Manual Execution commit, Manual Review append, paper trading ledger 수정은 수행하지 않았다.
```

END MFU-PAPER14-DAILY-NOTION-CHEAT-SHEET
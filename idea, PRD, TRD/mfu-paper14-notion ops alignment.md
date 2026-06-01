# MFU-PAPER14-NOTION-OPS-ALIGNMENT 작업 지시문: Notion SOP 정합성 업데이트

## 목적

`docs/operations/paper_notion_ops.md`를 최신 `docs/operations/paper_daily_ops.md` 기준에 맞춰 정합성 업데이트한다.

이번 작업은 기능 구현이 아니라 Notion-specific SOP 문서 정렬 작업이다.

반드시 명시:

```text
이번 MFU-PAPER14-NOTION-OPS-ALIGNMENT는 paper_notion_ops.md를 최신 paper_daily_ops.md의 canonical daily loop와 source-of-truth/safety/status 정책에 맞춰 업데이트하는 작업이며, Python 코드 수정, Notion actual write/export, Manual Execution commit, Manual Review append, paper trading ledger 수정은 수행하지 않는다.
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
```

작업 전 확인:

```cmd
cd /d D:\python\StockScreener
git rev-parse HEAD
git log --oneline -15
git status --short
```

`ea79d79` 이후 상태가 아니거나 `paper_daily_ops.md` 리팩토링 커밋이 없으면 중단하고 보고한다.

---

## 배경

현재 문서 역할은 다음과 같다.

```text
docs/TRD/mfu_paper14_notion_closeout.md
= PAPER14 전체 범위 / 결정 기록

docs/operations/paper_daily_ops.md
= 매일 보는 canonical daily operation guide

docs/operations/paper_notion_ops.md
= Notion-specific operation detail
```

`paper_daily_ops.md`는 최신 PAPER14 daily loop 기준으로 리팩토링됐다.

남은 리스크:

```text
paper_notion_ops.md와 paper_daily_ops.md 사이에 일부 개념 중복이 남아 있음
daily ops는 canonical guide지만 세부 명령 예시는 paper_notion_ops.md를 함께 봐야 함
두 문서의 safety/status/source-of-truth 표현이 달라질 경우 운영 혼선 가능
```

따라서 이번 MFU에서는 `paper_notion_ops.md`를 `paper_daily_ops.md`의 최신 구조와 정책에 맞춰 정렬한다.

---

## 수정 파일

수정 대상:

```text
docs/operations/paper_notion_ops.md
```

참고 파일:

```text
docs/operations/paper_daily_ops.md
docs/TRD/mfu_paper14_notion_closeout.md
```

참고 파일은 읽기만 하고 수정하지 않는다.

---

## 정합성 업데이트 요구사항

`paper_notion_ops.md`를 아래 기준으로 정리한다.

## 1. 문서 역할 명확화

본문 초반에 아래 관계를 명시한다.

```text
paper_daily_ops.md = canonical daily loop
paper_notion_ops.md = Notion DB별 세부 입력/확인/동기화 SOP
closeout TRD = PAPER14 범위와 결정 기록
```

`paper_notion_ops.md`가 daily loop의 상위 문서처럼 보이면 안 된다.

## 2. Source-of-truth 원칙 정렬

아래 원칙을 `paper_daily_ops.md`와 동일한 의미로 반영한다.

```text
Notion = 입력 UI / 검토 UI / staging layer
CSV / JSON / Markdown / SQLite = source of truth
Python = validation / preview / commit / append / export 주체
```

반드시 포함:

```text
Notion 입력값은 preview/commit/append 전까지 staging data다.
source-of-truth commit 성공 후 Notion sync 실패는 원장 실패가 아니다.
Notion sync 실패 시 원장 rollback 금지.
같은 commit report로 status sync만 재실행.
```

## 3. Canonical Daily Loop와 연결

`paper_notion_ops.md` 안의 Notion 관련 절차를 최신 daily loop 순서에 맞춘다.

정렬 기준:

```text
Daily Plan Notion export / 확인
Manual Executions 입력
Manual Executions preview / commit / status sync
Daily Review Summary export / 확인
Manual Reviews 입력
Manual Reviews preview / append / status sync
Weekly / Benchmark / Account Snapshot export
```

구버전 loop나 addendum이 남아 있으면 삭제하거나 `Historical / Deprecated`로 이동한다.

## 4. DB별 Notion SOP 정리

아래 DB별로 역할을 짧게 정리한다.

```text
Daily Plans
Manual Executions
Account Snapshots
Weekly Reports
Benchmark Reports
Daily Review Summaries
Manual Reviews
```

각 DB마다 가능하면 아래 항목을 맞춘다.

```text
목적
사용자가 Notion에서 하는 일
Python이 하는 일
source artifact
write 방향
status 필드
주의사항
```

단, 실제 구현/CLI/필드명을 추측하지 않는다. 기존 문서나 closeout 문서에서 확인 가능한 내용만 정리한다.

## 5. Safety / Status 정책 정렬

아래 정책이 `paper_daily_ops.md`와 충돌하지 않게 정리한다.

```text
preview 없이 commit / append 금지
FAIL 있으면 commit / append 금지
WARNING 있으면 기본 차단
--allow-warnings가 있을 때만 commit / append 허용
WARNING 허용 시 사유 기록 필요
Notion 입력값은 원장 반영 전까지 staging data
```

아래 용어 설명이 있으면 daily ops와 의미를 맞춘다.

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

## 6. 스마트폰 / 로컬 PC 역할 정렬

daily ops 기준과 일치시킨다.

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

## 7. 중복/충돌 정리

아래는 정리 대상이다.

```text
daily ops와 같은 내용을 장황하게 반복하는 section
최신 daily loop와 충돌하는 예전 절차
Notion을 source of truth처럼 오해하게 만드는 표현
commit/append를 스마트폰에서 할 수 있는 것처럼 보이는 표현
Notion sync 실패를 원장 실패처럼 표현하는 문장
```

삭제가 위험한 경우 `Historical / Deprecated`로 이동한다.

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
broker/API/GitHub Actions/cloud runner 구현 금지
paper_daily_ops.md 수정 금지
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

git diff -- docs\operations\paper_notion_ops.md
git diff --check -- docs\operations\paper_notion_ops.md
git status --short
```

문서 작업만 수행하므로 pytest는 필수 아님.

수동 확인:

```text
paper_notion_ops.md가 daily ops의 하위 세부 SOP로 정리됐는가
source-of-truth 원칙이 daily ops와 같은 의미인가
WARNING / FAIL / --allow-warnings 정책이 충돌하지 않는가
스마트폰 가능 단계와 로컬 PC 필수 단계가 daily ops와 일치하는가
Notion sync 실패 시 rollback 금지 / status sync 재실행 정책이 포함됐는가
구버전 절차가 최신 본문과 충돌하지 않는가
```

---

## 커밋 정책

필요한 파일만 stage한다.

```cmd
git add docs\operations\paper_notion_ops.md
git diff --cached --name-only
git commit -m "PAPER14: align Notion ops SOP with daily guide"
```

CSV/output/DB/PNG/unrelated 문서는 stage하지 않는다.

---

## 성공 기준

```text
paper_notion_ops.md가 paper_daily_ops.md의 canonical daily loop와 정합성을 가진다.
Notion SOP가 daily ops의 하위 세부 절차 문서로 정리된다.
source-of-truth 원칙이 명확히 반영된다.
safety/status/retry 정책이 daily ops와 충돌하지 않는다.
스마트폰 가능 단계 / 로컬 PC 필수 단계가 daily ops와 일치한다.
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
4. paper_daily_ops.md와의 정합성 업데이트 요약
5. Notion DB별 SOP 정리 내용
6. 반영한 source-of-truth 원칙
7. 반영한 safety/status/retry 정책
8. 스마트폰/로컬 PC 역할 정렬 내용
9. Deprecated/Historical 처리 내용
10. 테스트/검증 결과
11. 커밋 hash와 message
12. stage하지 않은 파일
13. 남은 리스크
14. 다음 MFU 제안
```

반드시 명시:

```text
이번 MFU-PAPER14-NOTION-OPS-ALIGNMENT는 paper_notion_ops.md를 최신 paper_daily_ops.md의 canonical daily loop와 source-of-truth/safety/status 정책에 맞춰 업데이트하는 작업이며, Python 코드 수정, Notion actual write/export, Manual Execution commit, Manual Review append, paper trading ledger 수정은 수행하지 않았다.
```
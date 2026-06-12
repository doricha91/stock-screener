# Paper Notion Operations Guide

## OPER9 Closeout Note

OPER9 closes the Python Daily Ops Orchestrator track. Notion remains an input UI, review UI, and status display UI; it is not the source of truth.

Use the Orchestrator for daily stage judgment:

```cmd
python scripts\paper_daily_ops.py status --account-id <ACCOUNT_ID> --data-date <DATA_DATE> --trade-date <TRADE_DATE> --json
```

Optional read-only Notion status:

```cmd
--include-notion-read
```

Do not automatically run Notion export/sync, local commit/append, broker/order, ledger mutation, or DB mutation from this document. n8n scheduling, notification, and approval flow design belongs to OPER10/AUTO follow-up work.

## 1. Role of This Document

이번 MFU-PAPER14-NOTION-OPS-ALIGNMENT는 `paper_notion_ops.md`를 최신 `paper_daily_ops.md`의 canonical daily loop와 source-of-truth/safety/status 정책에 맞춰 업데이트하는 작업이며, Python 코드 수정, Notion actual write/export, Manual Execution commit, Manual Review append, paper trading ledger 수정은 수행하지 않는다.

이 문서의 역할:

- `paper_daily_ops.md`에서 정의한 canonical daily loop를 전제로 한다
- Notion DB별 세부 입력 / 확인 / 동기화 SOP를 정리한다
- 운영자가 Notion에서 무엇을 하고, 로컬 PC에서 무엇을 해야 하는지 구분한다

문서 관계:

- `paper_daily_ops.md` = canonical daily loop
- `paper_notion_ops.md` = Notion DB별 세부 입력 / 확인 / 동기화 SOP
- `mfu_paper14_notion_closeout.md` = PAPER14 전체 범위와 결정 기록

즉, 이 문서는 daily loop의 상위 문서가 아니라 하위 세부 절차 문서다.

## 2. Source-of-Truth 원칙

운영 원칙:

- Notion = 입력 UI / 검토 UI / staging layer
- CSV / JSON / Markdown / SQLite = source of truth
- Python = validation / preview / commit / append / export 주체

실무 해석:

- Notion 입력값은 preview / commit / append 전까지 staging data다
- source-of-truth commit 성공 후 Notion sync 실패는 원장 실패가 아니다
- Notion sync 실패 시 원장 rollback은 하지 않는다
- 같은 commit report로 status sync만 재실행한다

## 3. Notion in the Canonical Daily Loop

이 문서가 다루는 Notion 관련 절차는 아래 순서를 따른다.

1. `Daily Plan` Notion export / 확인
2. `Manual Executions` 입력
3. `Manual Executions` preview / commit / status sync
4. `Daily Review Summary` export / 확인
5. `Manual Reviews` 입력
6. `Manual Reviews` preview / append / status sync
7. `Weekly / Benchmark / Account Snapshot` export

주요 원칙:

- Notion은 입력과 확인에 사용한다
- commit / append / export의 최종 실행 주체는 Python이다
- 스마트폰은 입력과 확인, 로컬 PC는 preview / commit / append / sync 용도다

## 4. Notion DB별 SOP

### 4.1 `Daily Plans`

목적:

- 당일 실행 계획을 Notion에서 확인하기 쉽게 보여준다

사용자가 Notion에서 하는 일:

- 당일 계획 확인
- page body에서 확정 거래 / 검토 항목 / 경고 확인

Python이 하는 일:

- local plan source를 바탕으로 read-only export
- External Key 기준 created / updated upsert

source artifact:

- `daily_action_plan_YYYYMMDD.md`
- `paper_config_snapshot_YYYYMMDD.json`

write 방향:

- Python -> Notion

status 필드:

- `Sync Status`

주의사항:

- Notion row는 계획 표시 계층이다
- source-of-truth는 local Markdown / JSON이다

### 4.2 `Manual Executions`

목적:

- 실제 체결을 스마트폰 포함 Notion UI에서 쉽게 입력한다

사용자가 Notion에서 하는 일:

- execution row 입력
- `READY` 상태 확인

Python이 하는 일:

- read-only import
- preview 생성
- preview 기준 execution commit
- commit report 기준 status sync

source artifact:

- Notion input row
- `manual_execution_import_preview_YYYYMMDD.json`
- `manual_execution_import_commit_YYYYMMDD.json`
- `paper_execution_log.csv`

write 방향:

- Notion -> Python -> CSV -> Notion status sync

status 필드:

- `Status`
- `Validation Status`
- `Import Status`

주의사항:

- Notion input row는 source-of-truth가 아니다
- preview 없이 commit 금지
- `WARNING`은 기본 차단
- `--allow-warnings`가 있을 때만 commit 허용

예시 명령:

```cmd
python scripts\import_notion_executions.py --date 2026-05-25 --preview --json
python scripts\import_notion_executions.py --date 2026-05-25 --commit --preview-json outputs\paper_test\reports\manual_execution_import_preview_20260525.json --allow-warnings
python scripts\sync_notion_execution_status.py --date 2026-05-25 --commit-report outputs\paper_test\reports\manual_execution_import_commit_20260525.json --json
```

### 4.3 `Daily Review Summaries`

목적:

- 하루 운영 결과를 요약해서 검토한다

사용자가 Notion에서 하는 일:

- trade count, warning count, cash impact, position impact 확인

Python이 하는 일:

- local source artifact를 사용해 read-only export
- External Key 기준 created / updated upsert

source artifact:

- execution commit report
- execution preview report
- `paper_execution_log.csv`
- `paper_account_snapshot.csv`
- `paper_position_snapshot.csv`
- optional `paper_current_state_YYYYMMDD.json`

write 방향:

- Python -> Notion

status 필드:

- `Review Status`
- `Availability Status`
- `Sync Status`

주의사항:

- result summary일 뿐 source-of-truth는 아니다
- commit report가 없으면 fallback summary만 가능할 수 있다

예시 명령:

```cmd
python scripts\export_paper_to_notion.py --daily-review-summary --date 2026-05-25 --dry-run --json
python scripts\export_paper_to_notion.py --daily-review-summary --date 2026-05-25 --json
```

### 4.4 `Manual Reviews`

목적:

- 질문 단위 retrospective 답변을 Notion에서 입력한다

사용자가 Notion에서 하는 일:

- question-level row에 `Manual Answer`, `Review Status`, `Follow-up Needed`, `Review Tag`, `Reviewer Note` 입력
- `READY` 상태 확인

Python이 하는 일:

- read-only import
- preview 생성
- preview 기준 review append
- commit report 기준 status sync

source artifact:

- Notion input row
- `manual_review_import_preview_YYYYMMDD.json`
- `manual_review_import_commit_YYYYMMDD.json`
- `paper_manual_review_log.csv`

write 방향:

- Notion -> Python -> CSV -> Notion status sync

status 필드:

- `Validation Status`
- `Import Status`

주의사항:

- review 원장은 `paper_manual_review_log.csv`
- Notion은 입력/staging layer
- preview 없이 append 금지
- `WARNING`은 기본 차단
- `--allow-warnings`가 있을 때만 append 허용

OPER9 post-15 note:

- Manual Review preview candidates require `Import Status = READY`.
- `Review Status = reviewed` plus a filled Manual Answer is not enough if `Import Status` remains `DRAFT`.
- The expected operator-ready combination is `Review Status = reviewed` and `Import Status = READY`.
- After append/sync, Python commit reports and local `paper_manual_review_log.csv` remain source of truth; Notion status is UI/status evidence.

예시 명령:

```cmd
python scripts\import_notion_reviews.py --date 2026-05-25 --preview --json
python scripts\import_notion_reviews.py --date 2026-05-25 --commit --preview-json outputs\paper_test\reports\manual_review_import_preview_20260525.json --allow-warnings
python scripts\sync_notion_review_status.py --date 2026-05-25 --commit-report outputs\paper_test\reports\manual_review_import_commit_20260525.json --json
```

### 4.5 `Account Snapshots`

목적:

- 최신 또는 특정 날짜의 계좌 상태를 표시한다

사용자가 Notion에서 하는 일:

- equity, cash, cash ratio, position count 확인

Python이 하는 일:

- snapshot CSV 기준 read-only export

source artifact:

- `paper_account_snapshot.csv`

write 방향:

- Python -> Notion

status 필드:

- `Sync Status`
- `Valuation Status`

주의사항:

- source-of-truth는 snapshot CSV다

### 4.6 `Weekly Reports`

목적:

- 주간 운영 completeness와 변화 요약

사용자가 Notion에서 하는 일:

- gap count, coverage, overall status 확인

Python이 하는 일:

- weekly report export

source artifact:

- weekly markdown / json report

write 방향:

- Python -> Notion

status 필드:

- `Overall Status`
- `Coverage Status`
- `Sync Status`

주의사항:

- 주간 운영 판단 보조용이며 source-of-truth는 local report다

### 4.7 `Benchmark Reports`

목적:

- paper 성과를 benchmark와 비교

사용자가 Notion에서 하는 일:

- paper return, excess return, MDD 비교 확인

Python이 하는 일:

- benchmark comparison export

source artifact:

- benchmark comparison markdown / json

write 방향:

- Python -> Notion

status 필드:

- `Availability Status`
- `Sync Status`

주의사항:

- 비교용 report 계층이며 source-of-truth는 local report다

## 5. Status and Safety Policy

### 운영 용어

`READY`
: Notion 입력 완료, Python preview 대기 상태

`COMMITTED`
: local source-of-truth artifact 반영 완료 상태

`SYNCED`
: export row가 최신 동기화 상태로 반영된 상태

`PASS`
: blocking issue 없음

`WARNING`
: 비차단 이슈 있음, 기본 차단 상태

`FAIL`
: blocking issue 있음, commit / append 금지

`created`
: export 시 새 Notion row 생성

`updated`
: export 시 기존 Notion row update

`dry-run`
: payload / decision path만 생성, write 없음

`--allow-warnings`
: 운영자가 WARNING을 명시 허용할 때만 사용하는 override

### 운영 정책

- preview 없이 commit / append 금지
- `FAIL` 있으면 commit / append 금지
- `WARNING` 있으면 기본 차단
- `--allow-warnings`가 있을 때만 commit / append 허용
- `WARNING` 허용 시 운영자가 사유 기록
- Notion 입력값은 source-of-truth 반영 전까지 staging data

## 6. Smartphone vs Local PC

### 스마트폰 가능

- `Daily Plan` 확인
- `Manual Executions` 입력
- `Daily Review Summary` 확인
- `Manual Reviews` 입력
- Notion status 확인

### 로컬 PC 필수

- preview 실행
- commit / append 실행
- ledger / review log / state 갱신
- status back-write
- Notion export / sync

## 7. Notion Sync Failure / Retry Policy

기본 원칙:

- source-of-truth commit 성공 후 Notion sync 실패는 원장 실패가 아니다
- 원장 rollback은 하지 않는다
- 같은 commit report로 status sync만 재실행한다

적용 대상:

- `Manual Executions` status sync
- `Manual Reviews` status sync

이유:

- status sync는 presentation / status layer
- source-of-truth commit 성공 여부와 분리해서 다뤄야 한다

## 8. Historical / Deprecated Notes

현재 canonical 본문과 충돌하는 구버전 해석은 운영 본문에서 제외한다.

예:

- Notion이 상위 운영 문서처럼 보이는 표현
- 스마트폰에서 commit / append도 할 수 있는 것처럼 보이는 표현
- Notion sync 실패를 원장 실패처럼 다루는 표현
- 초기 addendum 단계의 단순 export 중심 loop

이 문서는 최신 `paper_daily_ops.md`를 전제로 하는 하위 SOP다.

## 9. Out of Scope

이 문서는 다음을 다루지 않는다.

- Notion DB 자동 생성
- Notion schema migration
- Performance Summary 구현
- mobile remote execution
- GitHub Actions / cloud runner 운영
- broker/API 연동
## 10. PAPER15 Multi-account / Daily Ops Status Addendum

Current PAPER15 closeout policy:

- `Daily Ops Status` actual export was validated during PAPER15 only for limited `paper_sandbox` create/update
- closeout and consistency-check documentation work does not run additional Notion actual write/export
- schema validator pass is required before actual export
- `paper_default` actual export for the new Daily Ops Status flow is still forbidden
- multi-account bulk export is still forbidden
- `strategy_profile`, `universe_profile`, and `risk_profile` remain follow-up work

Operator guidance:

- use dry-run first
- use guarded actual export only where explicitly approved
- keep Notion as presentation layer, not source-of-truth

## 11. PAPER16-1 Daily Ops Status Dashboard Addendum

PAPER16-1 defines recommended manual Notion views for `Daily Ops Status`.

- Codex does not create or modify Notion views in this step
- Notion actual write/export is not executed in this step
- initial manual cleanup should focus on `paper_sandbox`
- `paper_default` actual export and multi-account bulk export remain forbidden
- `External Key`, `Account ID`, `Status Date`, `Workflow Status`, `Review Progress Status`, and `Sync Status` should stay visible in at least one troubleshooting view

## 12. PAPER16-2 Command Map / Rerun Policy Addendum

PAPER16-2 documents Daily Ops Status command selection, sync/export rerun policy, and manual view cleanup procedure.

- `External Key` must not be manually edited
- Notion sync/export failure is presentation-layer failure when local source-of-truth commit/append succeeded
- local source-of-truth rollback is forbidden for Notion sync/export failure alone
- retry actual export only with documented guarded commands and the same External Key
- do not create a duplicate Daily Ops Status DB when cleaning views
- manual views should be named `Today Ops`, `By Account`, `Needs Action`, `Recent Sync`, and `Review Closeout`
- PAPER16-3 may verify that the manually cleaned Notion views match the SOP

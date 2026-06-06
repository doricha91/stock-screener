# Paper Daily Operation Guide

## 1. Purpose / Scope

이번 MFU-PAPER14-DAILY-OPS-REFACTOR는 `paper_daily_ops.md`를 최신 PAPER14 Notion daily loop 기준으로 리팩토링하는 작업이며, Python 코드 수정, Notion actual write/export, Manual Execution commit, Manual Review append, paper trading ledger 수정은 수행하지 않는다.

이 문서는 운영자가 매일 참고하는 canonical daily operation guide다.

목적:

- 최신 PAPER14 일일 운영 순서를 한 문서로 정리
- source-of-truth 원칙을 운영 관점에서 명확히 고정
- 스마트폰 가능 단계와 로컬 PC 필수 단계를 구분
- `WARNING`, `FAIL`, `--allow-warnings`, sync retry 정책을 빠르게 확인 가능하게 정리

범위:

- daily paper trading operation
- Notion 입력 / 검토 / sync 운영 순서
- preview / commit / append / export 실행 원칙

비범위:

- Python 코드 설명
- DB schema 설명
- Notion DB별 상세 속성 계약

## 2. Source-of-Truth 원칙

운영 기본 원칙:

- Notion = 입력 UI / 검토 UI / staging layer
- CSV / JSON / Markdown / SQLite = source of truth
- Python = validation / preview / commit / append / export 주체

해석:

- Notion에 값이 입력되어 있어도 preview / commit / append 전까지는 source-of-truth가 아니다.
- source-of-truth commit이 끝난 뒤 Notion sync가 실패해도, 원장 성공 여부는 그대로 유지된다.
- Notion은 운영 편의와 검토 속도를 높이기 위한 계층이지, 원장 자체가 아니다.

## 3. Canonical Daily Loop

최신 PAPER14 기준 daily loop:

1. `Prepare / preflight`
2. `Daily Plan` 생성
3. `Daily Plan` Notion export
4. Notion에서 `Daily Plan` 확인
5. 실제 action 수행
6. Notion `Manual Executions` 입력
7. `Manual Executions` preview
8. preview 확인 후 execution commit
9. `paper_account_snapshot`, `paper_position_snapshot`, `paper_current_state` 갱신 확인
10. `Manual Executions` status sync
11. `Daily Review Summary` export
12. Notion에서 `Daily Review Summary` 확인
13. Notion `Manual Reviews` 입력
14. `Manual Reviews` preview
15. preview 확인 후 review append
16. `Manual Reviews` status sync
17. `Weekly / Benchmark / Account Snapshot` export

운영 해석:

- 계획 계층: `Daily Plan`
- 실제 체결 입력 계층: `Manual Executions`
- 결과 요약 계층: `Daily Review Summary`
- 사후복기 계층: `Manual Reviews`
- 기간 요약 계층: `Weekly / Benchmark / Account Snapshot`

## 4. 스마트폰 가능 단계 / 로컬 PC 필수 단계

### 스마트폰 가능 단계

- `Daily Plan` 확인
- `Manual Executions` 입력
- `Daily Review Summary` 확인
- `Manual Reviews` 입력
- Notion `READY / COMMITTED / SYNCED` 상태 확인

### 로컬 PC 필수 단계

- preview 실행
- commit / append 실행
- ledger / review log / state 갱신
- status back-write
- Notion export / sync

실무 원칙:

- 스마트폰은 입력 / 확인 / 검토용
- 로컬 PC는 source-of-truth 변경과 운영 검증용

## 5. Safety Policy

운영 안전 원칙:

- preview 없이 commit / append 금지
- `FAIL`이 있으면 commit / append 금지
- `WARNING`이 있으면 기본 차단
- `--allow-warnings`를 명시했을 때만 commit / append 허용
- `--allow-warnings` 사용 시 운영자가 사유를 review note 또는 operation note에 기록해야 함
- Notion 입력값은 source-of-truth 반영 전까지 staging data로만 취급
- source-of-truth commit 성공 후 Notion sync 실패 시 원장 rollback 금지
- 같은 commit report로 status sync만 재실행

추가 주의:

- 저수준 명령으로 same-date guard를 우회하지 않는다.
- 운영 표준은 `scripts/paper.py` shortcut 및 별도 importer/sync script를 사용한다.

## 6. Status Policy

### `READY`

- Notion 입력이 완료됨
- Python preview 대기 상태

### `COMMITTED`

- local source-of-truth artifact에 commit 또는 append 완료
- execution / review 원장 반영 기준 상태

### `SYNCED`

- read-only export row가 최신 값으로 동기화됨
- 주로 export 대상 DB의 표시 상태 의미

### `PASS`

- blocking issue 없음

### `WARNING`

- 비차단 이슈 있음
- 기본적으로 commit / append 차단

### `FAIL`

- blocking issue 있음
- commit / append 금지

### `created`

- Notion export 시 동일 External Key row가 없어 새 row 생성

### `updated`

- Notion export 시 동일 External Key row 1개를 찾아 update

### `dry-run`

- payload / decision path만 생성
- Notion write 없음
- CSV / ledger / review log write 없음

### `--allow-warnings`

- `WARNING` preview를 운영자가 명시적으로 허용할 때만 사용하는 override
- 평상시 기본 운영 경로는 아니다

## 7. Daily Checklist

### 시작 전

- 오늘 operation date를 명확히 정한다.
- data freshness / preflight가 통과하는지 확인한다.
- Daily Plan source artifact가 생성되었는지 확인한다.

### 장중 / 실행 후

- Notion `Daily Plan` 확인
- 실제 체결이 있으면 Notion `Manual Executions`에 입력
- local PC에서 execution preview 실행
- `FAIL` / `WARNING` 여부 확인
- 필요한 경우에만 `--allow-warnings`로 execution commit
- account / position / current state 반영 확인
- execution status sync 확인

### 장마감 후

- `Daily Review Summary` export
- Notion에서 `Daily Review Summary` 확인
- 거래 또는 경고/계획이탈이 있으면 `Manual Reviews` 입력
- local PC에서 review preview 실행
- `FAIL` / `WARNING` 여부 확인
- 필요한 경우에만 `--allow-warnings`로 review append
- review status sync 확인

### 보조 export

- 필요 시 `Weekly / Benchmark / Account Snapshot` export 실행

## 8. Failure / Retry Policy

### preview 단계 실패

- source artifact, mapping, validation issue를 먼저 수정
- preview 성공 전에는 commit / append 진행 금지

### commit / append 단계 실패

- source-of-truth가 반영되지 않았는지 먼저 확인
- 실패 원인이 중복인지, validation인지, file write인지 구분
- 원인 해결 전 재시도하지 않는다

### Notion sync 실패

- source-of-truth rollback 금지
- 같은 commit report로 sync만 재실행
- 이유:
  - Notion sync는 presentation / status layer
  - source-of-truth commit 성공과 분리해야 함

### `WARNING` 처리

- 기본은 중단
- 허용 시 운영자가 사유 기록
- 기록 위치:
  - review note
  - operation note
  - 작업 보고

## 9. Relationship with Other Docs

- [mfu_paper14_notion_closeout.md](/D:/python/StockScreener/docs/TRD/mfu_paper14_notion_closeout.md)
  - PAPER14 전체 범위 / 완료 / 보류 / 후속 결정 기록

- [paper_notion_ops.md](/D:/python/StockScreener/docs/operations/paper_notion_ops.md)
  - Notion-specific operation detail

- `paper_daily_ops.md`
  - 매일 보는 canonical daily operation guide

원칙:

- daily 운영 순서를 빠르게 확인할 때는 이 문서를 본다.
- Notion DB별 상세 절차나 명령 예시는 `paper_notion_ops.md`를 본다.
- 범위/설계/보류 판단은 closeout 문서를 본다.

## 10. Historical / Deprecated Notes

다음은 현재 canonical 본문에서 제외된 과거 표현 또는 구버전 관점이다.

- `prepare -> preview -> commit -> review -> status -> notion export`
  - 초기 PAPER14 addendum 단계의 단순 loop
  - 현재는 `Manual Executions`, `Daily Review Summary`, `Manual Reviews`가 포함된 loop가 canonical이다.

- 초기 addendum에서 `Daily Plan export`, `Daily Review Summary export`, `Manual Review input integration`이 out-of-scope로 적혀 있던 부분
  - 당시 시점 기준이며, 현재는 해당 범위 상당 부분이 구현 완료되었다.

- 기존 문서에 남아 있던 구버전 section과 최신 addendum의 병존
  - 이번 리팩토링으로 canonical 본문에서는 제거하고, historical note로만 남긴다.
## 11. PAPER15 Multi-account Policy Addendum

Current PAPER15 closeout policy:

- `init-account` is allowed only for non-default accounts
- `paper_default` init is forbidden
- `paper_default` keeps the legacy `outputs/paper_test` policy for now
- non-default local roots must stay under `outputs/paper_accounts/{account_id}`
- `paper_sandbox` rehearsal validated:
  - plan
  - eod dry-run
  - Manual Execution commit
  - reports
  - review-template
  - review-validate
  - review-append
  - local status `REVIEW_PARTIAL`
- Daily Ops Status limited actual create/update was validated during PAPER15 for `paper_sandbox`; closeout and consistency-check documentation work does not run additional Notion actual write/export
- strategy/universe/profile remains a follow-up item

Still forbidden:

- multi-account bulk export
- `paper_default` actual export for new multi-account Daily Ops Status flow
- cloud runner execution
- wrapper CLI automation

## 12. PAPER16-1 Daily Ops Status Dashboard Addendum

PAPER16-1 is a dashboard design step only.

- recommended Notion views are documented for manual setup
- Codex does not create or modify Notion views in this step
- Notion actual write/export is not executed in this step
- Daily Ops Status remains presentation layer only
- CSV / JSON / Markdown / SQLite remain source-of-truth

## 13. PAPER16-2 Command Map / Rerun Policy Addendum

PAPER16-2 fixes the operator command map and rerun policy for Daily Ops Status.

- use workflow_status / review_progress_status / sync_status to choose the next local command
- run dry-run before any allowed actual export
- do not rollback source-of-truth after Notion sync/export failure if local commit or append already succeeded
- rerun Notion sync/export against the same account_id, status date, report, and External Key
- actual Daily Ops Status export remains guarded and paper_sandbox-only until a later policy expands it
- manual Notion view cleanup is performed by the user after this documentation step
- PAPER16-3 can check the manually cleaned Notion views against the SOP

## 14. OPER9 Local Daily Ops Status Helper

OPER9 adds a local read-only status helper for the account-aware daily ops loop:

```cmd
python scripts\paper_daily_ops.py status --account-id <ACCOUNT_ID> --data-date <DATA_DATE> --trade-date <TRADE_DATE> --json
```

This helper only inspects local artifacts and recommends the next command as text. It does not call Notion, export or sync Notion rows, commit Manual Executions, append Manual Reviews, modify ledgers, or place broker orders.

## 15. OPER9-3 Daily Ops Orchestrator Contract Addendum

OPER9-3 keeps the existing `mfu_oper9_daily_ops_status.v1` schema version and adds backward-compatible fields for safer human and automation consumption.

Required compatibility fields remain:

- `next_command`
- `read_only=true`
- `write_executed=false`
- `notion_api_called=false`
- `commit_append_executed=false`

Added contract fields:

- `next_action`: structured command risk metadata for the top-level recommendation and each stage
- `summary`: terminal, attention, blocker, warning, unknown, and recommended operator action flags
- `stage_counts`: count of `DONE`, `READY`, `BLOCKED`, `WARNING`, `UNKNOWN`, and `NOT_STARTED` stages
- `operation_write_executed=false`: explicit marker that operational writes did not run
- `status_report_written` and `status_report_path`: diagnostic status report persistence markers

`next_action` classification:

- read-only checks are `READ_ONLY` + `SAFE`
- Notion export/sync commands are `NOTION_WRITE` + `REQUIRES_MANUAL_REVIEW`
- Manual Execution commit and Manual Review append commands are `LEDGER_WRITE` + `REQUIRES_MANUAL_REVIEW`
- broker/order command classes are `DANGEROUS`, but this helper must not recommend broker commands
- when workflow status is `REVIEW_DONE`, `next_command` and `next_action` are both `null`

Exit policy:

- default mode returns `0` when the CLI successfully generates status output
- input validation errors return `2`
- unexpected exceptions return `3`
- `--strict-exit` returns `1` for `WARNING` or `UNKNOWN`, and `2` for `BLOCKED`

Status report persistence:

```cmd
python scripts\paper_daily_ops.py status --account-id <ACCOUNT_ID> --data-date <DATA_DATE> --trade-date <TRADE_DATE> --json --write-status-report
```

By default no file is written. With `--write-status-report`, the helper writes the final status JSON to `--status-report-path` or to:

```text
<account_root>\reports\daily_ops_status_<TRADE_DATE>.json
```

This is diagnostic/status output only. It does not change Notion, ledgers, DB files, broker state, Manual Execution commits, or Manual Review append state.

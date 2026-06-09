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

## OPER9-6 Local Notion Reconciliation Addendum

Daily Ops status can optionally combine local artifact status with read-only Notion status by using:

```cmd
python scripts\paper_daily_ops.py status --account-id <ACCOUNT_ID> --data-date <DATA_DATE> --trade-date <TRADE_DATE> --json --include-notion-read
```

Rules:

- Local CSV, JSON, Markdown, and SQLite artifacts remain source-of-truth.
- Notion rows are UI/input/review signals only.
- Notion COMMITTED/SYNCED status without the matching local commit or append report is a reconciliation conflict.
- Local commit, append, ledger, and snapshot evidence must not be inferred from Notion alone.
- BLOCKED reconciliation suppresses risky next commands.
- `REVIEW_DONE` keeps top-level and stage-level `next_command` and `next_action` null; unsynced Notion status is reported as a reconciliation warning/conflict.

See [mfu_oper9_6_local_notion_reconciliation_matrix.md](/D:/python/StockScreener/docs/TRD/mfu_oper9_6_local_notion_reconciliation_matrix.md) for the stage matrix.

## OPER9 Closeout Addendum

OPER9 is closed as the Python Daily Ops Orchestrator track.

Final role split:

- Python Orchestrator: stage judgment, local artifact checks, optional read-only Notion status, reconciliation, blockers, `next_action`, and risk metadata.
- Local CSV/JSON/Markdown/SQLite: source of truth.
- Notion: input UI, review UI, and status display UI only.
- n8n: future OPER10/AUTO scheduling, notification, and approval layer.

Current status CLI:

```cmd
python scripts\paper_daily_ops.py status --account-id <ACCOUNT_ID> --data-date <DATA_DATE> --trade-date <TRADE_DATE> --json
```

Supported options:

- `--include-notion-read`
- `--strict-exit`
- `--write-status-report`
- `--status-report-path <PATH>`

Safety boundary:

- do not automatically run Notion export/sync commands
- do not automatically run `import_notion_executions.py --commit`
- do not automatically run `import_notion_reviews.py --commit`
- do not run broker/API/order commands
- do not automate ledger or DB mutation
- keep n8n implementation for OPER10/AUTO follow-up

See [mfu_oper9_daily_ops_orchestrator_closeout.md](/D:/python/StockScreener/docs/TRD/mfu_oper9_daily_ops_orchestrator_closeout.md).

## OPER9-7 Operator Summary Addendum

Daily Ops status JSON includes `operator_summary` for n8n and notification renderers.

Use it as the compact message source:

- `operator_summary.operator_message`
- `operator_summary.current_step`
- `operator_summary.current_step_status`
- `operator_summary.recommended_operator_action`
- `operator_summary.next_command`
- `operator_summary.command_type`
- `operator_summary.risk_level`
- `operator_summary.requires_manual_approval`
- `operator_summary.has_reconciliation_conflicts`

n8n should render or route this summary. It should not re-derive stage decisions from `stages`.

Automation boundary:

- `READ_ONLY` + `SAFE` commands may be considered for future read-only automation.
- `NOTION_WRITE` requires explicit approval.
- `LEDGER_WRITE` is not an n8n auto-execution target.
- `DANGEROUS` commands must not be auto-executed.
- broker/order, ledger/DB mutation, Notion write/sync, commit, and append remain excluded unless a later approval-based MFU explicitly changes the policy.

See [mfu_oper9_7_operator_summary_json_contract.md](/D:/python/StockScreener/docs/TRD/mfu_oper9_7_operator_summary_json_contract.md).

## OPER9-8 Step Advancement Addendum

Operator-facing `next_command` and `operator_summary.current_step` must advance with the local workflow.

Rules:

- Once Daily Plan artifacts exist and `workflow_status` is `PLAN_READY` or later, do not send the operator back to `DATA_FRESHNESS`.
- Stage-level `DATA_FRESHNESS` may remain diagnostic `READY` if no durable freshness report exists, but it must not become the top-level command after the plan is generated.
- n8n should trust `operator_summary.current_step` and `operator_summary.next_command`, not the first READY stage in `stages`.
- Downstream preview stages must not override earlier pending operational stages such as Daily Plan Notion export or Manual Execution template export.
- legacy `paper_test` warnings remain visible but should not rewind the workflow to a passed stage.

See [mfu_oper9_8_orchestrator_step_advancement_fix.md](/D:/python/StockScreener/docs/TRD/mfu_oper9_8_orchestrator_step_advancement_fix.md).

## OPER9-9 Stage Advancement Matrix Addendum

OPER9-9 audits the full operator-facing stage advancement matrix.

Rules:

- `next_command` and `operator_summary.current_step` must point to the actual next operational stage.
- Passed stages must not return as top-level commands only because diagnostic evidence is missing.
- Downstream preview, commit, append, or sync commands must not skip required upstream gates such as Daily Plan export or template export.
- If local/Notion reconciliation reports a conflict, `operator_summary.recommended_operator_action` should direct the operator to resolve the conflict instead of running risky commands.
- When `workflow_status=REVIEW_DONE`, `next_command` remains `null`, `operator_summary.current_step=FINAL_STATUS`, and `operator_summary.terminal=true`.

n8n usage:

- Render `operator_summary.current_step`, `operator_summary.operator_message`, `operator_summary.next_command`, `operator_summary.recommended_operator_action`, `operator_summary.risk_level`, and `operator_summary.requires_manual_approval`.
- Do not select a different next step by scanning raw `stages`.
- Treat `NOTION_WRITE`, `LEDGER_WRITE`, and `DANGEROUS` commands as approval-gated or excluded according to the current OPER9 safety boundary.

See [mfu_oper9_9_orchestrator_stage_advancement_matrix_audit.md](/D:/python/StockScreener/docs/TRD/mfu_oper9_9_orchestrator_stage_advancement_matrix_audit.md).

## OPER9-10 Notion Env Loading Addendum

`paper_daily_ops.py status --include-notion-read` uses the same root `.env` loading pattern as the existing Notion export/import/sync scripts.

Rules:

- `.env` may provide `NOTION_TOKEN`, `NOTION_DAILY_PLANS_DATA_SOURCE_ID`, `NOTION_MANUAL_EXECUTIONS_DATA_SOURCE_ID`, and `NOTION_MANUAL_REVIEWS_DATA_SOURCE_ID`.
- `config/notion_settings.json` remains supported.
- Environment override values take priority over settings file data source values.
- If `config/notion_settings.json` is missing or disabled, env-only Notion live read is allowed when the required env values exist.
- Missing configuration errors should identify the missing env variable or data source key without printing secret values.
- `--include-notion-read` remains read-only and opt-in.

Still forbidden:

- Notion create/update/delete from the orchestrator status command.
- automatic `export_paper_to_notion.py`, `sync_notion_*`, or `import_notion_* --commit` execution.
- broker/API/order execution.
- ledger or DB mutation.
- committing `.env`, Notion tokens, data source ids, or generated status output.

See [mfu_oper9_10_notion_env_loading_alignment.md](/D:/python/StockScreener/docs/TRD/mfu_oper9_10_notion_env_loading_alignment.md).

## OPER9-13 Manual Execution Reconciliation Addendum

Manual Execution operator state handling includes two additional rules:

- DRAFT Manual Execution rows with blank Actual Price and no READY rows are a Notion input wait state, not a command-ready state. `operator_summary.recommended_operator_action` may be `WAIT_FOR_INPUT`, and `next_command` should be `null`.
- After local execution preview, commit, or status sync has completed, READY rows are no longer required in Notion. COMMITTED, IMPORTED, or SYNCED rows are normal post-sync evidence and must not create a false `RESOLVE_CONFLICT` recommendation.

Notion live-read warnings for a missing `Account ID` select option should be surfaced as a structured operator warning without exposing token, data source id, page id, or row contents. This warning does not block a safe upstream next command by itself.

See [mfu_oper9_13_manual_execution_state_reconciliation_hardening.md](/D:/python/StockScreener/docs/TRD/mfu_oper9_13_manual_execution_state_reconciliation_hardening.md).

## OPER9-14 Manual Review Wait State Addendum

Manual Review operator state handling includes the same command-vs-input distinction:

- PENDING/DRAFT Manual Review rows with no READY/REVIEWED rows are a Notion review input wait state. `operator_summary.recommended_operator_action` may be `WAIT_FOR_INPUT`, and `next_command` should be `null`.
- The operator should fill Manual Answer and set Review Status to READY/REVIEWED in Notion before running `import_notion_reviews.py --preview`.
- READY/REVIEWED Manual Review rows should advance to the review preview command.
- A local review preview artifact with no review commit report should advance to the review append command, with manual approval required.
- `FINAL_STATUS` should not become the operator-facing step while Manual Review input is pending.

See [mfu_oper9_14_manual_review_wait_state_reconciliation_hardening.md](/D:/python/StockScreener/docs/TRD/mfu_oper9_14_manual_review_wait_state_reconciliation_hardening.md).

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

## 16. OPER9-4 Local Evidence Sidecar Addendum

OPER9-4 lets the Daily Ops Orchestrator consume local JSON evidence sidecars for Notion export/sync stages. The helper still does not call Notion or execute export/sync/commit/append commands.

Supported evidence files:

```text
<account_root>\reports\daily_plan_notion_export_<TRADE_DATE_YYYYMMDD>.json
<account_root>\reports\manual_execution_template_export_<TRADE_DATE_YYYYMMDD>.json
<account_root>\reports\manual_execution_status_sync_<TRADE_DATE_YYYYMMDD>.json
<account_root>\reports\manual_review_template_export_<TRADE_DATE_YYYYMMDD>.json
<account_root>\reports\manual_review_status_sync_<TRADE_DATE_YYYYMMDD>.json
```

The filename date uses compact `YYYYMMDD`, matching existing paper artifacts such as `manual_execution_import_preview_20260608.json`. The JSON payload still uses `trade_date=YYYY-MM-DD`.

Evidence schema:

- `schema_version=paper_notion_evidence.v1`
- `target_system=notion`
- `evidence_type` must match the stage
- `account_id` and `trade_date` must match the status request
- `data_date` must match when present
- `status` is one of `PASS`, `WARNING`, `FAILED`, `UNKNOWN`
- `failed_count > 0` blocks the stage

Stage interpretation:

- no sidecar: keep `UNKNOWN`
- `PASS` evidence: `DONE`
- `WARNING` evidence: `WARNING`
- `FAILED` evidence or `failed_count > 0`: `BLOCKED`
- account/date/type/schema mismatch: `BLOCKED`
- malformed JSON: `WARNING`, never `DONE`
- legacy `outputs\paper_test` evidence is not DONE evidence for non-default accounts

Stage JSON now includes:

- `evidence_path`
- `evidence_status`
- `evidence_checked`
- `evidence_errors`

These fields are diagnostic status fields. They do not mean that the orchestrator performed a Notion write.

## 17. OPER9-5 Optional Notion Live Read Addendum

OPER9-5 adds optional read-only Notion UI-state verification.

Default status remains local-only:

```cmd
python scripts\paper_daily_ops.py status --account-id <ACCOUNT_ID> --data-date <DATA_DATE> --trade-date <TRADE_DATE> --json
```

Notion read is opt-in:

```cmd
python scripts\paper_daily_ops.py status --account-id <ACCOUNT_ID> --data-date <DATA_DATE> --trade-date <TRADE_DATE> --json --include-notion-read
```

Optional timeout:

```cmd
--notion-timeout-seconds <N>
```

The helper only calls read-only Notion data source query APIs. It does not create, update, delete, export, sync, commit, append, place orders, or mutate ledgers.

Top-level JSON fields:

- `notion_live_read_enabled`
- `notion_live_read_called`
- `notion_live_read_status`
- `notion_live_read_errors`
- `notion_live_read_summary`

Stage JSON fields:

- `notion_checked`
- `notion_status`
- `notion_row_count`
- `notion_status_counts`
- `notion_errors`
- `notion_warnings`

Operational policy:

- Notion is UI-state verification only.
- Local CSV/JSON/Markdown/SQLite artifacts remain source of truth.
- Notion/local mismatch is not treated as DONE.
- Notion read failure is reported in JSON and does not imply an operational write failure.
- `REVIEW_DONE` still suppresses `next_command` and `next_action`.

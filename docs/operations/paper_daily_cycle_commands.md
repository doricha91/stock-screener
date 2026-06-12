# Paper Daily Cycle Command Runbook

This runbook is the daily operator manual for the paper trading cycle before n8n automation. It is based on the current CLI and code paths in this repository:

- `scripts\paper.py`
- `scripts\paper_daily_ops.py`
- `scripts\export_paper_to_notion.py`
- `scripts\import_notion_executions.py`
- `scripts\import_notion_reviews.py`
- `scripts\sync_notion_execution_status.py`
- `scripts\sync_notion_review_status.py`

Local CSV/JSON/Markdown/SQLite artifacts are the source of truth. Notion is an input, review, staging, and status UI. Broker/API/order execution is out of scope.

## 1. Quick Start

Set the three daily variables first.

```cmd
cd /d D:\python\StockScreener
conda activate HANTU311_64

set ACCOUNT_ID=paper_orch_smoke_202606
set DATA_DATE=2026-06-12
set TRADE_DATE=2026-06-15
```

Meaning:

- `ACCOUNT_ID`: paper account root to operate, for example `paper_orch_smoke_202606`, `paper_pilot_202606`, or `paper_sandbox`.
- `DATA_DATE`: latest completed US market data date used for decisions.
- `TRADE_DATE`: next paper trading / operating date.

Example:

- If operating on Saturday morning KST after the Friday US market close, `DATA_DATE` is the Friday US market date.
- `TRADE_DATE` is the next US trading day.

Always start with the Orchestrator:

```cmd
python scripts\paper_daily_ops.py status --account-id %ACCOUNT_ID% --data-date %DATA_DATE% --trade-date %TRADE_DATE% --json > outputs\orch_status.json

python -c "import json; p=json.load(open(r'outputs\orch_status.json',encoding='utf-8')); print(json.dumps(p.get('operator_summary'),ensure_ascii=False,indent=2))"
```

Read these fields before doing anything:

- `current_step`
- `recommended_operator_action`
- `next_command`
- `command_type`
- `risk_level`
- `requires_manual_approval`
- `warnings`
- `blockers`
- `terminal`

## 2. Full Operating Flow

| Step | Stage | Purpose | Command | Read/write | Automation | Approval | Normal result | If it fails |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | Orchestrator status | Decide the next stage | `python scripts\paper_daily_ops.py status ... --json` | read-only | Yes | No | `operator_summary` is readable | Inspect `blockers`, `warnings`, and `current_step` |
| 1 | Data prepare | Refresh market inputs | `python scripts\paper.py prepare-data --date %DATA_DATE% --universe` | DB / universe write | No | Yes | prepare summary has no errors | Check network/yfinance and DB state |
| 2 | Data freshness | Verify DB readiness | `python scripts\paper.py data-freshness --date %DATA_DATE%` | read-only | Yes | No | `result: PASS` | Do not plan on `FAIL`; inspect warnings |
| 3 | Daily Plan | Generate account plan | `python scripts\paper.py plan --data-date %DATA_DATE% --trade-date %TRADE_DATE% --account-id %ACCOUNT_ID%` | local artifact write | No | Yes | `.md`, `.json`, config snapshot created | Fix freshness/preflight/date issues |
| 4 | Daily Plan Notion export | Show plan in Notion | `python scripts\export_paper_to_notion.py --daily-plan ... --confirm-actual --json` | Notion write | No | Yes | failed count is zero | Check Notion schema/auth/export result |
| 5 | Manual Execution template export | Create execution input rows | `export_paper_to_notion.py --manual-execution-template ...` | Notion write | No | Yes | candidates exported or zero-candidate no-op | Check plan candidates and Notion result |
| 6 | Notion Manual Execution input | User enters fills | Notion UI | Notion manual edit | No | User action | rows have `Actual Price` and `Status=READY` | Check account/date filters |
| 7 | Manual Execution preview | Validate execution rows | `python scripts\import_notion_executions.py --preview ...` | read + preview files | Yes | No | `fail_count=0`, commit allowed | Fix Notion row values |
| 8 | Manual Execution commit | Commit execution preview | `import_notion_executions.py --commit --preview-json ...` | local ledger/state write | No | Yes | committed report created | Stop on failures; do not sync failed commit |
| 9 | Manual Execution status sync | Back-write execution status | `sync_notion_execution_status.py --commit-report ...` | Notion write | No | Yes | sync succeeds, failed count zero | Retry with same commit report after fixing Notion |
| 10 | Daily Review | Generate review artifacts | `python scripts\paper.py review --account-id %ACCOUNT_ID% --date %TRADE_DATE%` | local report/review write | No | Yes | template row count and validation PASS | Check preflight/report errors |
| 11 | Manual Review template export | Create review input rows | `export_paper_to_notion.py --manual-review-template ...` | Notion write | No | Yes | review rows exported | Check template date and Notion result |
| 12 | Notion Manual Review input | User answers review prompts | Notion UI | Notion manual edit | No | User action | `Manual Answer`, `Review Status`, `Import Status` ready | Check `Import Status=READY` |
| 13 | Manual Review preview | Validate review rows | `python scripts\import_notion_reviews.py --preview ...` | read + preview files | Yes | No | `candidate_count` expected, `fail_count=0` | Fix Notion row values |
| 14 | Manual Review append | Append review log | `import_notion_reviews.py --commit --preview-json ...` | local review log write | No | Yes | appended count expected | Stop on failures |
| 15 | Manual Review status sync | Back-write review status | `sync_notion_review_status.py --commit-report ...` | Notion write | No | Yes | sync succeeds, failed count zero | Retry with same commit report after fixing Notion |
| 16 | EOD dry-run | Preview end-of-day closure | `python scripts\paper.py eod --date %TRADE_DATE% --account-id %ACCOUNT_ID% --dry-run` | read-only | Yes | No | write intents are understood | Do not commit until dry-run is reviewed |
| 17 | EOD commit | Close local paper state | `python scripts\paper.py eod --date %TRADE_DATE% --account-id %ACCOUNT_ID% --commit` | local state/snapshot write | No | Yes | current state and snapshots written | Stop on guard/preflight failures |
| 18 | Final status | Confirm closure | `paper.py status`, `paper_daily_ops.py status` | read-only | Yes | No | `REVIEW_DONE`, terminal true | Resolve blockers/conflicts |

## 3. Canonical Command Sequence

### 3.1 Initial Orchestrator Check

```cmd
python scripts\paper_daily_ops.py status --account-id %ACCOUNT_ID% --data-date %DATA_DATE% --trade-date %TRADE_DATE% --json > outputs\orch_status.json

python -c "import json; p=json.load(open(r'outputs\orch_status.json',encoding='utf-8')); print(json.dumps(p.get('operator_summary'),ensure_ascii=False,indent=2))"
```

Normal:

- `terminal=false` at the start of a new cycle.
- `current_step` points to the next required stage.
- `next_command` may be present.
- `blockers=[]` before moving on.

Stop if:

- `recommended_operator_action=RESOLVE_CONFLICT`.
- `blockers` is non-empty.
- `command_type=UNKNOWN` and the command has not been reviewed.

### 3.2 Data Prepare

Canonical paper wrapper:

```cmd
python scripts\paper.py prepare-data --date %DATA_DATE% --universe
```

This is the current paper-specific wrapper. It prepares:

- market index data;
- ticker info;
- stock price data;
- `daily_indicators`;
- optional universe snapshot when `--universe` is passed.

This command can modify `outputs\market_data.db` and optional universe snapshot files. It depends on yfinance/network availability. US market data can lag shortly after market close.

Shortcut:

```cmd
python scripts\paper.py prepare --date %DATA_DATE% --universe
```

`prepare` runs `prepare-data` and then `data-freshness`. It stops on `PASS_WITH_WARNINGS` unless `--allow-warnings` is explicitly provided.

Standalone fallback commands exist but are lower priority for Daily Ops:

```cmd
python screener\data_collector.py && python data_processor.py
```

Use the paper wrapper first unless there is a specific diagnostic reason to run the standalone scripts.

### 3.3 Data Freshness

```cmd
python scripts\paper.py data-freshness --date %DATA_DATE%
```

Normal:

- `result: PASS`
- `error_count: 0`

Meaning:

- `PASS`: required market data checks passed.
- `PASS_WITH_WARNINGS`: no error checks, but warning checks exist. The plan command can still block because explicit-date plan uses strict freshness.
- `FAIL`: do not create a plan.

The freshness checker verifies at least:

- `daily_price`
- `market_index`, including `SPY`, with `QQQ` and `^VIX` checked as additional symbols
- `daily_indicators`
- `tickers`
- universe snapshot availability under the quarterly/as-of policy

Optional DB date diagnostic:

```cmd
python -c "import sqlite3; con=sqlite3.connect(r'outputs\market_data.db'); cur=con.cursor(); target='%DATA_DATE%'; tables=[r[0] for r in cur.execute('select name from sqlite_master where type=?',('table',))]; wanted=['daily_price','daily_indicators','market_index','market_status_log']; [print(t,'max_date=',cur.execute(f'select max(date) from {t}').fetchone()[0],'rows_target=',cur.execute(f'select count(*) from {t} where date=?',(target,)).fetchone()[0]) for t in wanted if t in tables and 'date' in [r[1] for r in cur.execute(f'pragma table_info({t})')]]; con.close()"
```

This diagnostic reads `outputs\market_data.db`; it does not write.

### 3.4 Daily Plan

```cmd
python scripts\paper.py plan --data-date %DATA_DATE% --trade-date %TRADE_DATE% --account-id %ACCOUNT_ID%
```

Before running:

- `data-freshness --date %DATA_DATE%` should be `PASS`.
- Confirm `DATA_DATE` is a completed US market date.
- Confirm `TRADE_DATE` is after `DATA_DATE` and is not a weekend.

Normal:

- account-scoped `daily_action_plan_YYYYMMDD.md` is created.
- account-scoped `daily_action_plan_YYYYMMDD.json` is created.
- account-scoped config snapshot is created.
- Plan candidates can be greater than zero or zero. Zero candidates can be a normal no-action day.

After running, check Orchestrator again:

```cmd
python scripts\paper_daily_ops.py status --account-id %ACCOUNT_ID% --data-date %DATA_DATE% --trade-date %TRADE_DATE% --json > outputs\orch_status.json
python -c "import json; p=json.load(open(r'outputs\orch_status.json',encoding='utf-8')); print(json.dumps(p.get('operator_summary'),ensure_ascii=False,indent=2))"
```

### 3.5 Daily Plan Notion Export

Prefer the Orchestrator `next_command`. General form:

```cmd
python scripts\export_paper_to_notion.py --daily-plan --account-id %ACCOUNT_ID% --date %TRADE_DATE% --confirm-actual --json
```

Before running:

- Daily Plan stage is `DONE`.
- Confirm this is a Notion write.
- Operator approval is required.

Normal:

- create/update result is reported.
- failed count is zero.
- account/date match the current operation.

## 4. Manual Execution Operation

### 4.1 Template Export

```cmd
python scripts\export_paper_to_notion.py --manual-execution-template --account-id %ACCOUNT_ID% --date %TRADE_DATE% --confirm-actual --json
```

This is a Notion write and requires approval.

Normal:

- `candidate_count` is reported.
- rows are created or updated in the Manual Executions DB.
- failed count is zero.

If `candidate_count=0`, this may be a no-action day. Re-check Orchestrator; it can mark the Manual Execution stages no-op `DONE`.

### 4.2 Notion Manual Execution Input

In the Manual Executions DB, verify or enter:

- `Account ID`: must equal `%ACCOUNT_ID%`.
- `Execution Date`: must equal `%TRADE_DATE%`.
- `Symbol`
- `Side`: `BUY` or `SELL`.
- `Quantity`
- `Plan Price`: reference value.
- `Actual Price`: price to use for paper execution.
- `Commission`: `0` is allowed if applicable.
- `Currency`: usually `USD`.
- `Broker`: usually `PAPER`.
- `Status`: set to `READY` for preview/commit candidates.
- `Import Status`: initially not imported; sync updates it after commit.
- `Validation Status` / `Validation Message`: checked after sync.

Operational condition:

- Actual Price is entered.
- `Status=READY`.
- Account and date filters match.

### 4.3 Execution Preview

```cmd
python scripts\import_notion_executions.py --date %TRADE_DATE% --account-id %ACCOUNT_ID% --preview --json
```

This reads Notion and writes preview artifacts. It does not commit local ledger state.

Normal:

- `candidate_count > 0` on a normal execution day.
- `fail_count=0`.
- `commit_allowed` is true or true-with-warnings after operator review.

If `candidate_count=0`, check:

- Is this a no-action day?
- Are Notion rows set to `Status=READY`?
- Is `Actual Price` entered?
- Does `Account ID` equal `%ACCOUNT_ID%`?
- Does `Execution Date` equal `%TRADE_DATE%`?

### 4.4 Execution Commit

Use the preview JSON path printed by the preview command or recommended by Orchestrator.

```cmd
python scripts\import_notion_executions.py --date %TRADE_DATE% --account-id %ACCOUNT_ID% --commit --preview-json "<EXECUTION_PREVIEW_JSON>" --json
```

This writes local source-of-truth artifacts and requires approval.

Before running:

- Review the preview JSON/summary.
- Confirm `fail_count=0`.
- Confirm projected cash/position impact.
- Use `--allow-warnings` only after explicitly accepting preview warnings.

Normal:

- commit report JSON/Markdown is created.
- committed row count matches expected candidate count.
- execution log/current state/snapshot updates are reported by the commit path.

### 4.5 Execution Status Sync

```cmd
python scripts\sync_notion_execution_status.py --date %TRADE_DATE% --account-id %ACCOUNT_ID% --commit-report "<EXECUTION_COMMIT_REPORT>" --json
```

This writes Notion status fields and requires approval.

Normal:

- sync succeeds.
- updated count matches committed rows.
- failed count is zero.

If sync fails after local commit, do not roll back local source-of-truth artifacts just because Notion status sync failed. Fix Notion/schema/auth and retry with the same commit report.

### 4.6 Execution Candidates Equal Zero

This is the no-action day path.

Conditions:

- Daily Plan exists.
- Actual BUY/SELL execution candidates are zero.

Expected Orchestrator behavior:

- `MANUAL_EXECUTION_TEMPLATE=DONE`
- `MANUAL_EXECUTION_PREVIEW=DONE`
- `MANUAL_EXECUTION_COMMIT=DONE`
- `MANUAL_EXECUTION_STATUS_SYNC=DONE`
- stages include `no_execution_candidates=true`

Operation:

- Manual Execution commit is not required.
- Continue to Daily Review.
- Final closure can still require EOD no-action roll-forward.

## 5. Daily Review Operation

### 5.1 Generate Daily Review

```cmd
python scripts\paper.py review --account-id %ACCOUNT_ID% --date %TRADE_DATE%
```

This writes local reports/review files and requires approval.

Main generated or refreshed artifacts:

- `reports\paper_daily_review_summary.md`
- `reports\paper_performance_summary.md`
- `reviews\paper_manual_review_log_template.csv`
- `reviews\paper_manual_review_log_validation_report.md`
- symbol review worksheets/reports under the account reports directory

Normal:

- `PAPER REPORTS` success.
- review template row count is reported.
- validation result is `PASS`.

Important date guard:

- The review template CSV must have `review_date == %TRADE_DATE%`.
- On no-action days, daily review/performance summary snapshot dates can be `%DATA_DATE%` or the latest prior snapshot date. That mismatch is a warning when `no_execution_candidates=true`, not a blocker.
- Review template date mismatch is always blocking.

## 6. Manual Review Operation

### 6.1 Template Export

```cmd
python scripts\export_paper_to_notion.py --manual-review-template --account-id %ACCOUNT_ID% --date %TRADE_DATE% --confirm-actual --json
```

This is a Notion write and requires approval.

Normal:

- candidate count is reported.
- rows are created or updated.
- failed count is zero.

### 6.2 Notion Manual Review Input

In the Manual Reviews DB, verify or enter:

- `Account ID`: must equal `%ACCOUNT_ID%`.
- `Review Date`: must equal `%TRADE_DATE%`.
- `Symbol`
- `Question ID`
- `Question`
- `Manual Answer`: required before append.
- `Review Status`: set to reviewed/REVIEWED after the answer is complete.
- `Import Status`: set to `READY` for preview/append candidates.
- `Follow Up Needed`: fill as applicable.
- `Review Tag`: fill as applicable, for example execution quality, position sizing, risk management.
- `Reviewer Note`: optional.
- `Validation Status` / `Validation Message`: checked after sync.

Important:

- `Manual Answer` alone is not enough.
- `Review Status=reviewed` alone is not enough.
- The importer queries `Import Status=READY`. If rows remain `DRAFT`, preview can return `candidate_count=0`.

### 6.3 Review Preview

```cmd
python scripts\import_notion_reviews.py --date %TRADE_DATE% --account-id %ACCOUNT_ID% --preview --json
```

This reads Notion and writes preview artifacts. It does not append to the review log.

Normal:

- `candidate_count` equals the number of READY Notion review rows for the account/date.
- `fail_count=0`.
- `append_allowed` is true or true-with-warnings after operator review.

If `candidate_count=0`, check:

- `Import Status=READY`
- `Review Status=reviewed` or `REVIEWED`
- `Manual Answer` is not blank
- `Account ID` equals `%ACCOUNT_ID%`
- `Review Date` equals `%TRADE_DATE%`
- Notion view filters are not hiding relevant rows

### 6.4 Review Append

```cmd
python scripts\import_notion_reviews.py --date %TRADE_DATE% --account-id %ACCOUNT_ID% --commit --preview-json "<REVIEW_PREVIEW_JSON>" --json
```

This appends local review log source-of-truth and requires approval.

Before running:

- Review preview JSON/summary.
- Confirm `fail_count=0`.
- Confirm duplicate warnings are acceptable before using `--allow-warnings`.

Normal:

- status is committed.
- appended count matches expected rows.
- failed count is zero.
- backup/report paths are printed.

### 6.5 Review Status Sync

```cmd
python scripts\sync_notion_review_status.py --date %TRADE_DATE% --account-id %ACCOUNT_ID% --commit-report "<REVIEW_COMMIT_REPORT>" --json
```

This writes Notion status fields and requires approval.

Normal:

- sync succeeds.
- updated count matches appended rows.
- failed count is zero.
- `Import Status` / validation fields reflect the committed review import.

If sync fails after append, do not roll back the local review log only because Notion status sync failed. Fix Notion/schema/auth and retry with the same commit report.

## 7. EOD Operation

### 7.1 EOD Dry-Run

```cmd
python scripts\paper.py eod --date %TRADE_DATE% --account-id %ACCOUNT_ID% --dry-run
```

This is read-only and can be automated.

Review these fields:

- `no_action_day`
- `execution_candidate_count`
- `ready_preview_count`
- `would_append_execution_log`
- `would_write_current_state`
- `would_write_account_snapshot`
- `would_write_position_snapshot`
- `source_snapshot_date`
- `target_snapshot_date`
- `write_performed`

Normal execution day:

- `ready_preview_count` can be greater than zero.
- `would_append_execution_log` can be true.

No-action day:

- `no_action_day=true`
- `ready_preview_count=0`
- `would_append_execution_log=false`
- current-state/account-snapshot/position-snapshot write intents should be true if account state can be reconstructed and market valuation succeeds.

### 7.2 EOD Commit

```cmd
python scripts\paper.py eod --date %TRADE_DATE% --account-id %ACCOUNT_ID% --commit
```

This writes local ledger/state/snapshot artifacts and requires approval.

Before running:

- EOD dry-run has been reviewed.
- Same-date replacement is not required.
- No blockers remain in Orchestrator.
- If no-action day, confirm `would_append_execution_log=false`.

Normal:

- preflight passes.
- `paper_current_state_YYYYMMDD.json` write is performed.
- account snapshot row write is performed.
- position snapshot rows write is performed when market valuation succeeds.
- no-action day can report `rows_appended=0`; that is normal.
- `replaced_same_date=false`.

Replacement guard:

- Same-date replacement must not be used casually.
- `--replace` belongs to the `paper.py commit` shortcut path and requires explicit approval.
- Prefer `eod --dry-run` followed by `eod --commit` for daily operations.

## 8. Final Status

### 8.1 Local Paper Status

```cmd
python scripts\paper.py status --account-id %ACCOUNT_ID% --date %TRADE_DATE% --json
```

Success criteria:

- `workflow_status=REVIEW_DONE`
- `same_date_snapshot_exists=true`
- `current_state_exists=true`
- `account_snapshot_exists=true`
- `position_snapshot_exists=true`
- `review_progress_status=DONE`
- `errors=[]`
- `next_recommended_command="no immediate action"`

### 8.2 Orchestrator Final Status

Local-only check:

```cmd
python scripts\paper_daily_ops.py status --account-id %ACCOUNT_ID% --data-date %DATA_DATE% --trade-date %TRADE_DATE% --json > outputs\orch_status.json
python -c "import json; p=json.load(open(r'outputs\orch_status.json',encoding='utf-8')); print(json.dumps(p.get('operator_summary'),ensure_ascii=False,indent=2))"
```

Optional Notion live-read check:

```cmd
python scripts\paper_daily_ops.py status --account-id %ACCOUNT_ID% --data-date %DATA_DATE% --trade-date %TRADE_DATE% --json --include-notion-read > outputs\orch_status.json
python -c "import json; p=json.load(open(r'outputs\orch_status.json',encoding='utf-8')); print(json.dumps(p.get('operator_summary'),ensure_ascii=False,indent=2))"
```

Success criteria:

- `workflow_status=REVIEW_DONE`
- `overall_status=PASS`
- `current_step=FINAL_STATUS`
- `current_step_status=DONE`
- `operator_message="Daily ops loop is complete."`
- `recommended_operator_action=NONE`
- `next_command=null`
- `warnings=[]`
- `blockers=[]`
- `terminal=true`
- `has_reconciliation_conflicts=false`
- `conflict_count=0`

Note:

- Local-only Orchestrator status can be terminal even when opt-in Notion live read later reports stale UI status.
- Treat Notion live-read conflicts as UI/status reconciliation issues unless local source-of-truth artifacts disagree.

## 9. Orchestrator `next_command` Rules

Run Orchestrator status after each stage. If `operator_summary.next_command` is present, prefer that command over a memorized command.

Use `command_type` and `risk_level` as the execution gate:

- `READ_ONLY`: safe to automate. Examples: status, data-freshness, preview, EOD dry-run.
- `NOTION_WRITE`: writes Notion create/update/sync state. Requires approval.
- `LEDGER_WRITE`: writes local ledger/review log/snapshot/source-of-truth artifacts. Requires preview review and approval.
- `UNKNOWN`: do not automate. Inspect the command meaning before manual execution.

Use `recommended_operator_action` as the operator branch:

- `RUN_NEXT_COMMAND`: run the command only after checking its command type.
- `WAIT_FOR_INPUT`: wait for manual Notion/user input.
- `RUN_COMMIT`: review preview output and get approval.
- `RUN_SYNC`: review commit report and get approval.
- `RESOLVE_CONFLICT`: do not run risky commands; resolve conflict first.
- `NONE`: complete or no immediate action.

## 10. Troubleshooting Branches

### Freshness FAIL

- Confirm `prepare-data` was run for `%DATA_DATE%`.
- Check `daily_price`, `daily_indicators`, and `market_index` max dates.
- Confirm `%DATA_DATE%` is an actual US trading day.
- Do not run plan until freshness is fixed.

### Freshness PASS_WITH_WARNINGS

- Review each warning line.
- The standalone freshness command can return with warnings, but explicit-date plan uses strict freshness and can block.
- Re-run `prepare-data` or adjust `%DATA_DATE%` only after confirming the cause.

### Plan Candidate Count Is Zero

- This can be normal.
- Confirm Orchestrator marks Manual Execution stages no-op `DONE`.
- Continue to Daily Review.
- Expect EOD no-action roll-forward before final closure.

### Manual Execution Preview `candidate_count=0`

- If no-action day, this can be normal.
- Otherwise check `Actual Price`, `Status=READY`, `Account ID`, and `Execution Date` in Notion.

### Manual Review Preview `candidate_count=0`

- Check `Manual Answer`.
- Check `Review Status=reviewed`.
- Check `Import Status=READY`.
- Check `Account ID`.
- Check `Review Date`.

### EOD Warning: No READY_FOR_PAPER_TRADE Previews To Append

- On no-action days, this can be normal.
- Confirm `no_action_day=true`.
- Confirm `would_append_execution_log=false`.
- Confirm current-state/account-snapshot/position-snapshot write intents are true before commit.

### Final Status WARNING or BLOCKED

- Run both `paper.py status` and Orchestrator status.
- Check whether `workflow_status` is still `PLAN_READY`.
- Check `same_date_snapshot_exists`.
- Check `review_progress_status`.
- Inspect Orchestrator `blockers`, `warnings`, and reconciliation conflicts.

## 11. Safety Boundary

Automation allowed:

- `python scripts\paper_daily_ops.py status ...`
- `python scripts\paper.py status ...`
- `python scripts\paper.py data-freshness ...`
- `python scripts\import_notion_executions.py --preview ...`
- `python scripts\import_notion_reviews.py --preview ...`
- `python scripts\paper.py eod ... --dry-run`

Approval required:

- `python scripts\paper.py prepare-data ...`
- `python scripts\paper.py prepare ...`
- `python scripts\paper.py plan ...`
- `python scripts\export_paper_to_notion.py ... --confirm-actual`
- `python scripts\import_notion_executions.py --commit ...`
- `python scripts\import_notion_reviews.py --commit ...`
- `python scripts\sync_notion_execution_status.py ...`
- `python scripts\sync_notion_review_status.py ...`
- `python scripts\paper.py eod ... --commit`
- `python scripts\paper.py commit ...`

Do not automate:

- broker/API/order commands;
- `import_notion_* --commit` without preview review;
- `paper.py eod --commit` without dry-run review;
- `paper.py commit` without explicit approval;
- `--replace` usage;
- manual edits/copies of generated source-of-truth outputs.

## 12. Daily Checklist

- [ ] `ACCOUNT_ID` confirmed.
- [ ] `DATA_DATE` confirmed as the latest completed US market data date.
- [ ] `TRADE_DATE` confirmed as the next operating/trading date.
- [ ] Initial Orchestrator status reviewed.
- [ ] `prepare-data` completed, if data refresh is needed and approved.
- [ ] `data-freshness` is `PASS`.
- [ ] Daily Plan generated.
- [ ] Daily Plan Notion export completed, if approved.
- [ ] Manual Execution requirement checked.
- [ ] Execution preview/commit/sync completed, or no-op path confirmed.
- [ ] Daily Review generated.
- [ ] Manual Review Template exported, if approved.
- [ ] Notion Manual Review rows completed.
- [ ] Review preview/append/sync completed.
- [ ] EOD dry-run reviewed.
- [ ] EOD commit approved and executed if closure is required.
- [ ] `paper.py status` shows `REVIEW_DONE`.
- [ ] Orchestrator shows `PASS` / `terminal=true`.
- [ ] Generated outputs and live account artifacts are not committed to git.

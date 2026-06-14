# MFU-OPER9-20D-A EOD Duplicate Append / Idempotency Investigation

## Summary

This is a read-only investigation of the 2026-06-15 EOD duplicate append / partial commit incident for `paper_orch_smoke_202606`.

Confirmed findings:

- Manual Execution commit had already appended 9 economic trades to `paper_execution_log.csv` with `source=notion_manual_execution`.
- EOD commit independently parsed the Daily Plan markdown journal and generated 9 `PaperTradePreview` rows with `source=paper_virtual_fill`.
- `append_paper_execution_log()` detects duplicates only by `trade_id`.
- `trade_id` includes `source` and `reason`, so the same economic trade from `notion_manual_execution/manual_execution_import` and `paper_virtual_fill/Act fields blank...` receives different IDs.
- EOD commit appends execution log rows before rebuilding account state.
- When the rebuilt account state failed with `cannot SELL more shares than held`, EOD returned failure after the execution log append had already happened.
- EOD does not currently have the backup/rollback wrapper that Manual Execution commit has.

Primary conclusion:

EOD currently behaves as a trade append plus state/snapshot writer. In the Daily Ops / Notion manual execution flow, EOD should instead treat an existing Manual Execution commit report for the date as source-of-truth execution evidence and only close state/snapshots, or it must prove there are no already committed economic duplicates before writing anything.

## Incident Timeline

Observed operational sequence:

1. Daily Plan for `2026-06-15` contained 9 execution candidates.
2. Manual Execution Notion flow committed those 9 rows.
3. `paper_execution_log.csv` contained 9 rows for `2026-06-15` with `source=notion_manual_execution`.
4. EOD commit parsed `daily_action_plan_20260615.md`.
5. The markdown journal rows had blank actual fill fields (`[ ]`) and recommendation values.
6. EOD converted those rows into 9 `paper_virtual_fill` previews.
7. EOD appended those 9 previews to `paper_execution_log.csv`.
8. Account state rebuild then failed with `cannot SELL more shares than held`.
9. Current state, account snapshot, and position snapshot were not written.
10. Manual recovery removed the 9 `paper_virtual_fill` rows and left only the 9 `notion_manual_execution` rows.

## Current Recovered State

Read-only check of `outputs\paper_accounts\paper_orch_smoke_202606\paper_execution_log.csv`:

- `rows_20260615=9`
- all rows are `source=notion_manual_execution`
- symbols/sides/shares:
  - `AMCR BUY 243`
  - `AMT SELL -51`
  - `AVB SELL -52`
  - `BF-B BUY 353`
  - `CCL BUY 339`
  - `LIN BUY 9`
  - `LYV BUY 2`
  - `PLD BUY 65`
  - `SW BUY 3`

`paper.py status --account-id paper_orch_smoke_202606 --date 2026-06-15 --json` reports:

- `workflow_status=REVIEW_DONE`
- `same_date_snapshot_exists=true`
- `current_state_exists=true`
- `account_snapshot_exists=true`
- `position_snapshot_exists=true`
- `execution_log_rows_for_date=9`
- `review_progress_status=DONE`
- `next_recommended_command=no immediate action`

`paper_daily_ops.py status --account-id paper_orch_smoke_202606 --data-date 2026-06-12 --trade-date 2026-06-15 --json` reports:

- `operator_summary.current_step=FINAL_STATUS`
- `operator_summary.terminal=true`
- `operator_summary.next_command=null`
- without live Notion read, `overall_status=UNKNOWN` because several Notion evidence sidecars are absent, but terminal closure is still true from local status.

## EOD Dry-run vs Commit Flow

Entry point:

- `scripts/paper.py::handle_eod()`
- resolves `account_paths`
- runs EOD preflight
- calls `scripts.run_paper_eod_update.run_paper_eod_dry_run(..., commit=bool(args.commit), account_paths=account_paths)`

Core EOD flow in `scripts/run_paper_eod_update.py::run_paper_eod_dry_run()`:

1. Resolve account-aware paths.
2. Parse `daily_action_plan_YYYYMMDD.md`.
3. Build `journal_rows`.
4. Convert journal rows to `PaperTradePreview` via `build_paper_trade_previews()`.
5. Call `append_paper_execution_log(paper_trade_previews, ..., commit=commit)`.
6. Reload the execution log with `build_paper_account_preview_from_log()`.
7. If account preview succeeds, save current state.
8. If valuation/snapshot build succeeds, save account snapshot and position snapshot.

Dry-run difference:

- In dry-run, `commit=False`, so `append_paper_execution_log()` computes `rows_to_append` but does not write them.
- Account preview is then built from the existing log, not from the hypothetical appended rows.
- Therefore dry-run can appear account-preview OK even though commit would append rows first and then fail when previewing the mutated log.

Commit difference:

- In commit mode, `append_paper_execution_log(..., commit=True)` writes rows before account preview.
- Account preview then reads the mutated log.
- If the appended rows make the ledger invalid, the failure happens after the log write.

## EOD Trade Source Analysis

EOD does not consume `manual_execution_import_commit_YYYYMMDD.json` as the execution source.

EOD trade generation source is:

- `daily_action_plan_YYYYMMDD.md`
- strict markdown journal parser or fallback preview parser
- `build_paper_trade_previews()`

The 2026-06-15 Daily Plan markdown rows had:

- `rec_shares` and `rec_price` populated
- `act_shares=[ ]`
- `act_price=[ ]`
- `reason=[ ]`
- `status=READY_FOR_PAPER_TRADE`

`core/paper_trade_preview.py::resolve_paper_actual_fill()` treats blank actual fields as paper fallback:

- uses `Rec_Shares/Rec_Price`
- sets `source=paper_virtual_fill`
- sets reason to `Act fields blank; used Rec_Shares/Rec_Price as paper fill`

That explains why EOD generated 9 `paper_virtual_fill` rows even though Manual Execution had already committed 9 `notion_manual_execution` rows.

## Duplicate Detection Analysis

Duplicate check is implemented in `core/paper_execution_log.py::append_paper_execution_log()`.

Current duplicate key:

- existing `trade_id` values from `paper_execution_log.csv`
- generated `trade_id` for each preview row
- duplicate if generated `trade_id` matches an existing or same-batch `trade_id`

`build_paper_trade_id()` hashes:

- `date`
- `symbol`
- `side`
- `shares`
- `price`
- `reason`
- `source`

Therefore duplicate detection is source/reason-sensitive.

For the same economic trade:

- Manual Execution commit row:
  - `source=notion_manual_execution`
  - `reason=manual_execution_import`
- EOD virtual fill row:
  - `source=paper_virtual_fill`
  - `reason=Act fields blank; used Rec_Shares/Rec_Price as paper fill`

Even when date, symbol, side, shares, and price match, the hash differs because `source` and `reason` differ. The EOD rows are not considered duplicates.

Current duplicate tests cover same-preview duplicate replay, not economic duplicates across different sources.

## Write Ordering / Partial Commit Analysis

EOD commit write order:

1. `append_paper_execution_log(..., commit=True)` writes execution log rows.
2. `build_paper_account_preview_from_log()` rebuilds account state from the now-mutated log.
3. If account preview succeeds, current state is written.
4. If snapshot build succeeds, account snapshot is written.
5. If position valuation succeeds, position snapshot is written.

Failure path:

- If account preview raises `ValueError`, EOD stores `account_preview_error`.
- Current state, account snapshot, and position snapshot writes are skipped.
- The already appended execution log rows remain.
- The function later prints `ERROR: paper account preview failed` and returns `1`.

No rollback was found in EOD commit.

Contrast with Manual Execution commit:

- `core/paper_manual_execution_commit.py::commit_manual_execution_preview()` pre-checks append with `commit=False`.
- creates backups for execution log/current state/account snapshot/position snapshot.
- appends with `commit=True`.
- rebuilds state and writes snapshots inside a `try`.
- on exception, `_restore_from_backups()` restores all targets.

EOD lacks the equivalent transactional wrapper.

## Manual Execution Commit vs EOD Responsibility Boundary

Current behavior:

- Manual Execution commit writes execution rows and state/snapshots.
- EOD also tries to append execution rows from the Daily Plan markdown and then write state/snapshots.

This creates overlapping responsibility.

For the Daily Ops / Notion manual execution flow, the better boundary is:

- Manual Execution commit is the source-of-truth trade append step.
- EOD should close or roll-forward state/snapshots from already committed ledger rows.
- EOD should not create a second set of trade rows from Daily Plan recommendations when a Manual Execution commit report exists for the same account/date.

No-action EOD roll-forward remains valid because no execution rows are appended.

## Root Cause Candidates

Confirmed root causes:

1. EOD parses Daily Plan markdown, not Manual Execution commit report.
2. EOD converts blank actual fields to `paper_virtual_fill`.
3. Duplicate detection uses `trade_id` only.
4. `trade_id` includes `source` and `reason`, so economic duplicates across source systems are invisible.
5. EOD writes `paper_execution_log.csv` before account preview/state validation.
6. EOD lacks rollback after post-append failure.

Contributing design issue:

- EOD still owns a legacy journal-to-ledger append responsibility while the current Daily Ops flow already has a dedicated Manual Execution commit responsibility.

## Recommended 20D-B Fix Plan

Priority 1: Pre-write validation / no partial commit.

- In EOD commit mode, compute prospective rows without writing.
- Rebuild prospective account state using existing rows plus prospective rows in memory.
- Run account preview, market valuation, account snapshot build, and position snapshot build before any file write.
- Only write execution log/current state/snapshots after all pre-write validation passes.

Priority 2: Manual Execution commit report boundary.

- If `reports/manual_execution_import_commit_YYYYMMDD.json` exists for the account/date, EOD must not append Daily Plan-derived virtual fills for that date.
- In that case, EOD should use the existing `paper_execution_log.csv` as source-of-truth and write/refresh current state and snapshots only.

Priority 3: Economic duplicate guard.

- Add an economic duplicate key such as:
  - `date`
  - `symbol`
  - `side`
  - absolute/effective `shares`
  - rounded `price`
- Use it in addition to `trade_id`.
- Treat `notion_manual_execution` vs `paper_virtual_fill` with the same economic key as duplicate or conflict.

Priority 4: EOD idempotency contract.

- Re-running EOD commit for the same date should not append rows already represented in the ledger.
- If same-date snapshots exist, preserve existing replacement guard behavior.
- Decide whether EOD commit should support explicit `--replace` for state/snapshot refresh without execution append.

Priority 5: Tests.

- Manual Execution commit report exists + EOD commit must not append virtual fills.
- EOD commit account preview failure must leave execution log unchanged.
- Same economic trade with different `source/reason` is detected as duplicate/conflict.
- Dry-run should preview the same prospective account state that commit would validate.
- EOD re-run idempotency test for a normal execution day.

## Safety Constraints

This investigation did not change:

- code
- tests
- operation outputs
- Notion state
- broker/API/order state
- ledger/DB files

## No-write Confirmation

Executed commands were read-only:

- git metadata/status/log/grep
- code file reads
- current CSV/JSON reads
- `paper.py status --json`
- `paper_daily_ops.py status --json`

Commands intentionally not executed:

- `scripts/export_paper_to_notion.py --confirm-actual`
- `scripts/import_notion_executions.py --commit`
- `scripts/import_notion_reviews.py --commit`
- `scripts/sync_notion_execution_status.py`
- `scripts/sync_notion_review_status.py`
- `scripts/paper.py eod --commit`
- `scripts/paper.py commit`
- broker/API/order commands
- ledger/DB mutation commands

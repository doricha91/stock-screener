# MFU-OPER9-20D-B EOD Accounting Close Role Hardening

## Summary

MFU-OPER9-20D-B changes the default EOD role from trade generation to accounting close.

Default `paper.py eod --commit` no longer appends Daily Plan-derived `paper_virtual_fill` rows to `paper_execution_log.csv`. It closes the account from the already committed execution log and writes or refreshes the target-date current state, account snapshot, and position snapshot.

The trade append owner is Manual Execution commit. EOD is the close step.

## Problem

The 2026-06-15 incident showed overlapping responsibilities:

- Manual Execution commit appended 9 `source=notion_manual_execution` rows.
- EOD parsed the Daily Plan markdown and generated 9 additional `source=paper_virtual_fill` rows.
- Duplicate detection used `trade_id`, which includes `source` and `reason`, so the economic duplicate rows were not detected.
- EOD appended execution rows before account preview.
- Account preview then failed with `cannot SELL more shares than held`, leaving a partial execution log append without current-state/snapshot writes.

## New EOD Role

Default EOD mode is `accounting_close`.

In this mode:

- EOD reads the Daily Plan only to understand whether the date has execution candidates.
- EOD reads `paper_execution_log.csv` as the source of truth for committed trades.
- EOD does not append execution log rows.
- EOD writes `paper_current_state_YYYYMMDD.json` only after account preview succeeds.
- EOD writes account and position snapshots only after state reconstruction and valuation/snapshot build succeed.

Dry-run and commit both report:

- `eod_mode=accounting_close`
- `execution_candidate_count`
- `execution_log_rows_for_date`
- `manual_execution_commit_report_exists`
- `no_action_day`
- `would_append_execution_log=false`
- state/snapshot write intent

## Manual Execution Boundary

Manual Execution commit is responsible for adding trades to `paper_execution_log.csv`.

If `reports/manual_execution_import_commit_YYYYMMDD.json` exists, EOD must not fall back to Daily Plan virtual fills.

If the commit report exists but no target-date execution log rows exist, EOD blocks with a mismatch error. It does not invent rows from the Daily Plan.

## Normal Execution Day Policy

For a normal execution day:

- Daily Plan has official execution candidates: `action in {"BUY", "SELL"}` and `quantity > 0`.
- Target-date rows in `paper_execution_log.csv` must already exist before EOD close.
- EOD reconstructs account state from the committed log rows.
- Execution log row count remains unchanged.
- No `paper_virtual_fill` rows are created by default EOD.

If candidates exist but no committed target-date rows and no Manual Execution commit report exist, EOD blocks:

`EOD accounting close blocked: execution candidates exist but no committed execution rows were found. Run Manual Execution commit first.`

## No-Action Day Policy

No-action day behavior remains valid.

When Daily Plan execution candidate count is zero and no target-date execution log rows exist:

- EOD appends no execution rows.
- EOD reconstructs state from the existing log.
- EOD roll-forwards current state, account snapshot, and position snapshot to the target date.
- Cash, holdings, and cost basis carry forward.
- Market valuation can update for the target date.

## Partial Commit Prevention

The previous partial commit path came from execution log append before account preview.

The hardened default path removes execution log append from EOD. Therefore:

- account preview failure leaves `paper_execution_log.csv` unchanged
- current state is not written on preview failure
- account snapshot is not written on preview failure
- position snapshot is not written on preview failure

## Implementation Notes

Primary changed entry point:

- `scripts/run_paper_eod_update.py::run_paper_eod_dry_run`

Supporting behavior:

- candidate count is read from `daily_action_plan_YYYYMMDD.json` through `core.paper_daily_plan_candidates.count_daily_plan_execution_candidates`
- markdown journal parsing remains for preview output only
- EOD commit help text now describes accounting close instead of execution append

## Test Coverage

Added `tests/test_paper_eod_accounting_close.py` covering:

- Manual Execution commit report exists, target-date `notion_manual_execution` rows exist, candidates > 0: EOD writes snapshots and does not append `paper_virtual_fill`.
- Candidates > 0, no target-date execution rows, no commit report: EOD blocks and writes no close artifacts.
- Manual Execution commit report exists, but target-date execution rows are missing: EOD blocks as inconsistent evidence.
- No-action day candidates=0: EOD roll-forward succeeds with execution log unchanged.
- Account preview failure: execution log unchanged and no state/snapshot writes.
- Dry-run and commit both report `would_append_execution_log=false`.

## Safety Boundary

This hardening does not introduce a legacy virtual fill opt-in path.

Future work may add a separate explicit command or flag for legacy journal-to-ledger behavior, but it should not be the default EOD path.

Live Notion write, live EOD commit, import commit, sync, broker/API/order, and live ledger mutation are outside this task.

## Remaining Limitations

- Existing execution log duplicate detection still uses `trade_id`; this task avoids EOD duplicate append by removing default EOD append responsibility.
- If future workflows need EOD-generated fills, they need an explicit, separately approved mode with pre-write validation and economic duplicate checks.
- Same-date snapshot replacement behavior remains governed by existing snapshot writer semantics; operators should still avoid unapproved same-date replacement.

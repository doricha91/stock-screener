# MFU-OPER9-15 Manual Review Post-Commit Status Sync Reconciliation Fix

## 1. Summary

OPER9-15 fixes the Daily Ops Orchestrator terminal policy after Manual Review append/commit.

When local review append is complete but Notion Manual Review rows are still `READY` / `REVIEWED`, the workflow is not terminal for operator-facing status. The next step is Manual Review status sync, not `FINAL_STATUS`.

## 2. Baseline

- Baseline commit: `016913ac2872508dbf396701cd8cb8bd3c46dfa9`
- Smoke account: `paper_orch_smoke_202606`
- data_date: `2026-06-05`
- trade_date: `2026-06-08`

## 3. Problem Analysis

The local workflow can reach `REVIEW_DONE` after the Manual Review append report exists. With `--include-notion-read`, that is not sufficient to close the operator loop if Notion review rows have not been synced to committed/synced/imported status.

The previous behavior produced a contradictory operator summary:

- `terminal=true`
- `current_step=FINAL_STATUS`
- `operator_message=Daily ops loop is complete.`
- `has_reconciliation_conflicts=true`

That is unsafe for n8n because n8n trusts `operator_summary`.

## 4. Policy Changes

### Sync Pending State

When all of the following are true, `MANUAL_REVIEW_STATUS_SYNC` remains the operator-facing next step:

- local `manual_review_import_commit_YYYYMMDD.json` exists
- Notion live-read is enabled and checked
- Notion Manual Review rows exist
- rows are still `READY` / `REVIEWED`
- committed/synced/imported status is not reflected

Expected operator summary:

- `current_step=MANUAL_REVIEW_STATUS_SYNC`
- `recommended_operator_action=RUN_SYNC`
- `next_command=python scripts\sync_notion_review_status.py ...`
- `terminal=false`
- `has_reconciliation_conflicts=false`

### Terminal State

`REVIEW_DONE` is terminal only when:

- Notion live-read is disabled/skipped and local-only closeout policy applies, or
- Notion review status sync is confirmed with `COMMITTED`, `SYNCED`, `IMPORTED`, or equivalent synced status.

If sync remains required, `FINAL_STATUS` must not become the operator-facing current step.

### Conflict Policy

`REVIEW_DONE` plus unsynced Notion review rows is not treated as a source-of-truth conflict. It is a required status sync step. The reconciliation result is READY/RUN_SYNC, not RESOLVE_CONFLICT.

## 5. Safety Boundaries

OPER9-15 does not execute writes.

Still forbidden:

- Notion create/update/delete from Orchestrator status
- automatic `sync_notion_review_status.py`
- automatic `import_notion_reviews.py --commit`
- broker/API/order execution
- ledger/DB mutation
- committing `.env`, secrets, generated output, or smoke artifacts

Local CSV/JSON/Markdown/SQLite artifacts remain the source of truth. Notion remains an input/review/status UI.

## 6. Test Coverage

Added or updated regression coverage for:

- review commit exists but Notion review status sync is pending
- sync pending state recommending `MANUAL_REVIEW_STATUS_SYNC`
- terminal true only when sync is done
- terminal true never paired with reconciliation conflicts
- OPER9-13 Manual Execution hardening tests
- OPER9-14 Manual Review wait-state tests

## 7. Remaining Limits

- The Orchestrator recommends the sync command but does not execute it.
- n8n approval and notification rendering remain OPER10/AUTO scope.

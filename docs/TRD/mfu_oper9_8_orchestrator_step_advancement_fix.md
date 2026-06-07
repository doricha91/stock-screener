# MFU-OPER9-8 Orchestrator Step Advancement Fix

## 1. Summary

MFU-OPER9-8 fixes stale top-level next step selection in the Daily Ops Orchestrator.

The observed bug was:

- `workflow_status=PLAN_READY`
- Daily Plan artifacts existed
- `DATA_FRESHNESS` still remained stage-level `READY`
- top-level `next_command` and `operator_summary.current_step` incorrectly pointed back to `DATA_FRESHNESS`

The fix keeps detailed stage diagnostics intact but prevents already-passed stages from becoming the operator-facing next command.

## 2. Root Cause

The top-level next command used the first stage in stage order with status `READY`, `WARNING`, or `UNKNOWN` and a `next_command`.

Because `DATA_FRESHNESS` is a read-only check and has no durable local evidence artifact in the orchestrator, it could remain `READY` even after `paper.py plan` had successfully generated the Daily Plan. Once the Daily Plan exists, operational flow has already advanced past data freshness.

## 3. Advancement Policy

Top-level `next_command` now filters stale command candidates:

- `DATA_FRESHNESS` is eligible only before the local Daily Plan is DONE and while workflow is `NO_PLAN` or unknown/incomplete.
- `DAILY_PLAN` is skipped once Daily Plan artifacts are DONE or workflow has advanced past `NO_PLAN`.
- downstream execution/review stages are not eligible before the local Daily Plan is DONE.
- stage-level diagnostics can still show historical or informational `READY` states.
- operator-facing `next_command` and `operator_summary.current_step` must point to the actual next operational stage.

For `PLAN_READY`, the expected next stage is a Daily Plan follow-up such as:

- `DAILY_PLAN_NOTION_EXPORT`
- then `MANUAL_EXECUTION_TEMPLATE`
- then later preview/commit/sync steps as evidence progresses

## 4. Operator Summary Policy

`operator_summary` continues to select the current step from the top-level `next_command` unless terminal or reconciliation conflict rules apply.

Conflict precedence remains:

1. `REVIEW_DONE` terminal uses `FINAL_STATUS`.
2. reconciliation conflict uses the conflict stage.
3. otherwise, the stage matching top-level `next_command` is current.

Non-conflict downstream reconciliation `READY` signals must not cause n8n to skip earlier pending operational stages.

## 5. n8n Safety

n8n should render `operator_summary`; it should not re-derive next steps from stage order.

Important automation constraints:

- `NOTION_WRITE` commands require explicit approval.
- `LEDGER_WRITE` commands are not n8n auto-execution targets.
- `DANGEROUS` commands must not be auto-executed.
- `paper.py plan` creates local Daily Plan artifacts and should not be treated as a read-only command.
- broker/order, ledger/DB mutation, Notion write/sync, commit, and append remain excluded unless a later approval-based MFU explicitly changes policy.

## 6. Smoke Result

For account `paper_orch_smoke_202606`, `data_date=2026-06-05`, `trade_date=2026-06-08`:

- `workflow_status=PLAN_READY`
- Daily Plan artifacts exist
- top-level `next_command` is not `data-freshness`
- `operator_summary.current_step=DAILY_PLAN_NOTION_EXPORT`
- `operator_summary.operator_message=The next daily ops step is ready.`

The account still reports a legacy `paper_test` warning. That warning is preserved but no longer sends the operator back to `DATA_FRESHNESS`.

## 7. Exclusions

This work did not run or implement:

- n8n workflow
- Telegram/Slack/Email integration
- Notion create/update/delete
- `export_paper_to_notion.py`
- `sync_notion_*`
- `import_notion_* --commit`
- broker/API/order execution
- ledger or DB mutation
- generated output commit

# MFU-OPER9-20C Execution Candidate Schema Alignment

## 1. Summary

MFU-OPER9-20C aligns Daily Ops Orchestrator execution candidate counting with the official Daily Plan JSON schema.

The official execution candidate source is `daily_action_plan_YYYYMMDD.json` `items[]`.

An item is an execution candidate when:

- `action in {"BUY", "SELL"}` after trim/uppercase normalization
- `quantity > 0`
- `symbol` is present

`action=EXECUTE`, `status=PENDING`, and `side=BUY/SELL` are not the official Daily Plan candidate schema and are not used as the primary count rule.

## 2. Problem

The 2026-06-15 smoke cycle had a valid execution day:

- `daily_action_plan_20260615.json` contained 9 items.
- `BUY=7`, `SELL=2`.
- All actionable rows used `action=BUY/SELL` and positive `quantity`.
- Manual Execution preview/commit artifacts existed with 9 rows.
- Notion Manual Execution rows existed in the operational history.

Before this fix, the Orchestrator counted candidates using a legacy-looking shape:

- `action=EXECUTE`
- `status=PENDING`
- `side in {"BUY", "SELL"}`

That made the Orchestrator mark the day as `no_execution_candidates=true`, causing Manual Execution stages to be skipped as no-op.

## 3. Shared Helper

New module:

- `core/paper_daily_plan_candidates.py`

Public API:

- `is_daily_plan_execution_candidate(item) -> bool`
- `extract_daily_plan_execution_candidates(plan) -> list[dict]`
- `count_daily_plan_execution_candidates(plan) -> int`

Rule identifier:

- `items.action_in_buy_sell_quantity_positive.v1`

Malformed items are not candidates. The helper requires a dict item, an official BUY/SELL `action`, a present `symbol`, and a positive numeric `quantity`.

## 4. Orchestrator Alignment

`core/paper_daily_ops_orchestrator.py` now uses the shared helper for:

- `execution_candidate_count`
- `no_execution_candidates`
- `candidate_count_rule`

Stage metadata includes:

- `execution_candidate_count`
- `no_execution_candidates`
- `plan_candidate_source`
- `candidate_count_rule`

The 2026-06-15 shape now returns:

- `execution_candidate_count=9`
- `no_execution_candidates=false`
- `candidate_count_rule=items.action_in_buy_sell_quantity_positive.v1`

## 5. Exporter Alignment

Manual Execution Notion export now uses the same helper through `core/notion_exporters.py`.

The exporter no longer has a separate candidate interpretation for `type`/`shares` or legacy `EXECUTE/PENDING/side` rows. Its candidate inclusion rule is the same official Daily Plan helper rule used by the Orchestrator.

This prevents Orchestrator and exporter from disagreeing about whether a Daily Plan is an execution day or a no-action day.

## 6. No-Candidates Priority Hardening

True no-action day handling remains supported, but the no-candidates shortcut is constrained.

No-candidates skip is not allowed to hide downstream evidence:

- `manual_execution_import_preview_YYYYMMDD.json`
- `manual_execution_import_commit_YYYYMMDD.json`
- Manual Execution Notion rows
- a local execution commit report that still requires Notion status sync

If a commit report exists, `MANUAL_EXECUTION_STATUS_SYNC` is evaluated normally. The Orchestrator must recommend sync when sync evidence is missing, instead of marking the stage DONE through `OPER9_17_EXEC_SYNC_SKIPPED_NO_CANDIDATES`.

If Manual Execution Notion rows exist, no-candidates skip is suppressed so preview/commit/sync stages cannot be silently skipped.

## 7. True No-Action Behavior

True no-action days are still valid.

A day may be treated as no-action only when:

- the Daily Plan has zero official execution candidates
- there is no contradicting preview artifact
- there is no contradicting commit artifact
- Manual Execution Notion rows do not indicate pending execution work

In that case, Manual Execution Template/Preview/Commit/Status Sync can still be marked no-op DONE and the loop can advance to Daily Review.

## 8. Test Coverage

Added or updated coverage:

- current schema positive:
  - `action=BUY/SELL`, `quantity>0` counts as execution candidates
- true no-action:
  - empty items, HOLD, zero quantity, malformed rows count as zero
- 2026-06-15 shape:
  - BUY 7 and SELL 2 count as 9
  - OPER9-17 no-candidates rules do not apply
- preview/commit/status-sync priority:
  - commit artifact prevents no-candidates status sync skip
  - Notion Manual Execution READY/NOT_IMPORTED rows prevent no-candidates skip
- exporter alignment:
  - Manual Execution Notion export uses the shared helper and matches Orchestrator candidate count

## 9. Read-Only Smoke

Read-only verification for `paper_orch_smoke_202606`, `data_date=2026-06-12`, `trade_date=2026-06-15` showed:

- Daily Plan item count: 9
- action counts: `BUY=7`, `SELL=2`
- official candidate count: 9
- `MANUAL_EXECUTION_TEMPLATE.execution_candidate_count=9`
- `MANUAL_EXECUTION_TEMPLATE.no_execution_candidates=false`
- `MANUAL_EXECUTION_STATUS_SYNC.status=READY`
- next command points to `sync_notion_execution_status.py`

The generated verification JSON is an output artifact and is not committed.

## 10. Safety Boundary

This task did not run live/write commands:

- Notion export/write/sync
- `import_notion_executions.py --commit`
- `import_notion_reviews.py --commit`
- `paper.py eod --commit`
- `paper.py commit`
- broker/API/order commands
- ledger/DB mutation commands

Only tests and read-only status/smoke inspection were run.

## 11. Remaining Limitations

- The helper intentionally follows the current official Daily Plan schema. If a future Daily Plan schema reintroduces a distinct execution action shape, that should be added explicitly with tests.
- Existing historical docs may still describe the pre-20C mismatch as an audit finding. Where updated, they now mark it as resolved by 20C.
- Notion live read may still return API/schema warnings independently of candidate counting; that is a separate operational issue.

## 12. Next Task

Recommended follow-up:

- Verify Manual Execution status sync completion for 2026-06-15 after explicit operator approval.
- Continue OPER10/AUTO read-only workflow design using the corrected `candidate_count_rule` metadata.

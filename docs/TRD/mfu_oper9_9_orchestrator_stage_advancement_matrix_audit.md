# MFU-OPER9-9 Orchestrator Stage Advancement Matrix Audit

## 1. Summary

OPER9-9 audits the Daily Ops Orchestrator stage advancement rules after the OPER9-8 stale `DATA_FRESHNESS` fix.

The goal is to make the operator-facing `next_command`, `operator_summary.current_step`, and `operator_summary.recommended_operator_action` point to the actual next operational step. Stage-level diagnostic status may still show missing evidence or warnings, but it must not rewind the top-level recommendation to a stage that the workflow already passed.

This audit uses fake local artifacts and fake Notion status reports only. It does not run Notion writes, syncs, imports with `--commit`, broker commands, ledger updates, or generated-output commits.

## 2. Advancement Principles

- The top-level `next_command` represents the next executable operational stage, not the first diagnostic issue in the stage list.
- Once a later durable local artifact or evidence sidecar proves progress, earlier stages are excluded from top-level command selection.
- Downstream preview, commit, append, or sync commands cannot become top-level recommendations before required upstream plan/export/template gates are complete.
- `operator_summary.current_step` follows the top-level `next_command` stage.
- Reconciliation conflicts and `REVIEW_DONE` terminal status remain explicit exceptions.
- n8n should render and route `operator_summary`; it should not derive a different operational decision from raw `stages`.

## 3. Required Matrix

| Case | Local / Notion condition | Expected operator-facing next stage |
| --- | --- | --- |
| A. Initial | `NO_PLAN`, no Daily Plan artifact | `DATA_FRESHNESS` or the configured initial local step |
| B. Plan ready | Daily Plan artifact exists | `DAILY_PLAN_NOTION_EXPORT`; do not return to `DATA_FRESHNESS` or `DAILY_PLAN` |
| B. Plan ready with downstream preview | Daily Plan artifact exists and preview artifact also exists, but export/template evidence is missing | `DAILY_PLAN_NOTION_EXPORT` or `MANUAL_EXECUTION_TEMPLATE`; do not skip to preview/commit |
| C. Daily Plan Notion export done | Daily Plan artifact plus Daily Plan export evidence | `MANUAL_EXECUTION_TEMPLATE` |
| C. Daily Plan Notion export missing | Daily Plan artifact without export evidence | `DAILY_PLAN_NOTION_EXPORT` |
| D. Manual Execution template done | Manual Execution template export evidence exists | Notion input wait or `MANUAL_EXECUTION_PREVIEW` when READY rows exist |
| D. Manual Execution template missing | Template evidence missing | `MANUAL_EXECUTION_TEMPLATE` even if a local preview artifact exists |
| E. Manual Execution preview ready | Notion READY rows exist, no local preview | `MANUAL_EXECUTION_PREVIEW` |
| E. Manual Execution preview done | Local execution preview exists, no commit report | `MANUAL_EXECUTION_COMMIT` |
| F. Manual Execution commit done | Local execution commit report exists | `MANUAL_EXECUTION_STATUS_SYNC` |
| F. Notion committed only | Notion COMMITTED but no local commit report | `RESOLVE_CONFLICT`; suppress risky commands |
| G. Execution sync missing | Local commit report exists, Notion sync/evidence missing | `MANUAL_EXECUTION_STATUS_SYNC` |
| G. Execution sync done | Execution sync evidence exists | `DAILY_REVIEW` |
| H. Daily Review missing | Execution commit/sync done, review artifacts missing | `DAILY_REVIEW` |
| H. Daily Review done | Review summary/template artifact exists | `MANUAL_REVIEW_TEMPLATE` |
| I. Manual Review template missing | Review template local artifact exists, Notion review rows/evidence missing | `MANUAL_REVIEW_TEMPLATE` |
| I. Manual Review template done | Manual Review template evidence exists | Notion review input wait or `MANUAL_REVIEW_PREVIEW` when READY rows exist |
| J. Manual Review preview ready | Notion review READY/reviewed rows exist, no local review preview | `MANUAL_REVIEW_PREVIEW` |
| J. Manual Review preview done | Local review preview exists, no review commit report | `MANUAL_REVIEW_APPEND` |
| J. Manual Review append done | Local review commit report exists | `MANUAL_REVIEW_STATUS_SYNC` |
| K. Review sync missing | Local review commit report exists, sync missing | `MANUAL_REVIEW_STATUS_SYNC` |
| K. Terminal | Review sync evidence exists and local `workflow_status=REVIEW_DONE` | `next_command=null`, `operator_summary.current_step=FINAL_STATUS`, `terminal=true` |

## 4. Stale Command Suppression

The orchestrator now treats these stages as stale for top-level command selection when downstream durable progress exists:

- `DATA_FRESHNESS` and `DAILY_PLAN`: stale after Daily Plan exists or workflow moved beyond `NO_PLAN`.
- `DAILY_PLAN_NOTION_EXPORT`: stale after Manual Execution template, execution commit, or Daily Review progress exists.
- `MANUAL_EXECUTION_TEMPLATE`: stale after execution commit/sync or Daily Review progress exists.
- `MANUAL_EXECUTION_PREVIEW`: stale after execution commit/sync or Daily Review progress exists.
- `MANUAL_EXECUTION_COMMIT`: stale after execution sync or Daily Review progress exists.
- `MANUAL_EXECUTION_STATUS_SYNC`: stale after Daily Review progress exists.
- `DAILY_REVIEW`: stale after Manual Review template/preview/append progress exists.
- `MANUAL_REVIEW_TEMPLATE`: stale after review preview/append/sync progress exists.
- `MANUAL_REVIEW_PREVIEW`: stale after review append/sync progress exists.
- `MANUAL_REVIEW_APPEND`: stale after review sync or terminal `REVIEW_DONE`.
- `MANUAL_REVIEW_STATUS_SYNC`: stale after terminal `REVIEW_DONE`.

Before any of these downstream stages can become top-level candidates, the Daily Plan must already be locally done. This prevents early preview/commit/sync commands from being recommended in a no-plan state.

## 5. Test Coverage

The matrix is covered in `tests/test_paper_daily_ops_orchestrator.py` with fake account roots, fake local artifacts, fake evidence sidecars, and fake Notion status reports.

Assertions cover:

- top-level `next_command`
- `operator_summary.current_step`
- `operator_summary.next_command`
- `operator_summary.recommended_operator_action`
- `risk_level` and `requires_manual_approval`
- stale previous command suppression
- downstream skip prevention
- `REVIEW_DONE` terminal command suppression

## 6. Safety Boundary

OPER9-9 does not implement n8n workflows and does not execute:

- Notion create/update/delete
- `export_paper_to_notion.py`
- `sync_notion_*`
- `import_notion_executions.py --commit`
- `import_notion_reviews.py --commit`
- broker/API/order calls
- ledger or DB mutation
- generated output commits

## 7. Remaining Limits

- The audit fixes deterministic advancement policy, but it does not prove live Notion API success.
- Notion schema drift detection remains a separate validation track.
- n8n must still be designed as a rendering/routing layer, not a second decision engine.
- Approval-based execution remains out of scope until a later OPER10/OPER11 MFU.

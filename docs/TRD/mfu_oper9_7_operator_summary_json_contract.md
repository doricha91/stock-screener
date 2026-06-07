# MFU-OPER9-7 Operator Summary JSON Contract

## 1. Purpose

MFU-OPER9-7 adds a compact `operator_summary` field to the Daily Ops Orchestrator status JSON.

The target consumer is n8n, Telegram, Slack, Email, or a Notion message renderer. These consumers should render or route the summary; they should not re-implement trading or operations judgment logic.

Python Daily Ops Orchestrator remains the decision engine. Local CSV/JSON/Markdown/SQLite remains source of truth. Notion remains UI/status display and is not source of truth.

## 2. Scope

In scope:

- add top-level `operator_summary`
- keep existing JSON fields unchanged
- expose the current step, action, command risk, counts, warnings, blockers, and reconciliation conflict summary
- keep commands as Windows CMD strings

Out of scope:

- n8n workflow creation
- Telegram/Slack/Email integration
- Notion create/update/delete
- Notion export/sync command execution
- `import_notion_* --commit`
- broker/API/order execution
- ledger or DB mutation
- generated output commit

## 3. JSON Shape

Top-level addition:

```json
{
  "operator_summary": {
    "title": "Paper Daily Ops",
    "account_id": "paper_orch_smoke_202606",
    "data_date": "2026-06-05",
    "trade_date": "2026-06-08",
    "workflow_status": "NO_PLAN",
    "overall_status": "UNKNOWN",
    "current_step": "DATA_FRESHNESS",
    "current_step_status": "READY",
    "operator_message": "Data freshness check is ready. Run the read-only freshness command first.",
    "recommended_operator_action": "RUN_NEXT_COMMAND",
    "next_command": "python scripts\\paper.py data-freshness --date 2026-06-05",
    "command_type": "READ_ONLY",
    "risk_level": "SAFE",
    "requires_manual_approval": false,
    "warnings": [],
    "blockers": [],
    "ready_count": 2,
    "blocked_count": 0,
    "warning_count": 0,
    "done_count": 0,
    "unknown_count": 0,
    "terminal": false,
    "notion_live_read_enabled": false,
    "notion_live_read_status": "SKIPPED",
    "has_reconciliation_conflicts": false,
    "conflict_count": 0
  }
}
```

Allowed `recommended_operator_action` values:

- `NONE`
- `RUN_NEXT_COMMAND`
- `CHECK_NOTION`
- `RUN_PREVIEW`
- `RUN_COMMIT`
- `RUN_SYNC`
- `RESOLVE_CONFLICT`
- `RESOLVE_BLOCKERS`

## 4. Current Step Selection

Selection order:

1. If terminal/`REVIEW_DONE`, use `FINAL_STATUS` and keep `next_command=null`.
2. If `reconciliation_summary.recommended_operator_action=RESOLVE_CONFLICT`, use the first reconciliation conflict stage.
3. If top-level `next_command` exists, use the first stage with the same command.
4. If no executable command exists, use the first `BLOCKED`, `WARNING`, `READY`, then `UNKNOWN` stage.
5. If no stage can be selected, use `current_step=null` and `current_step_status=UNKNOWN`.

Blocked stages do not hide an executable safe next command. The Orchestrator remains responsible for deciding whether a command is safe to recommend.

## 5. Message Policy

Messages are intentionally short and renderer-friendly.

Examples:

- `DATA_FRESHNESS READY`: `Data freshness check is ready. Run the read-only freshness command first.`
- `DAILY_PLAN READY`: `Daily Plan is ready to generate after data freshness passes.`
- status sync `READY`: `Local commit exists. Notion status sync is still needed.`
- reconciliation conflict: `Local and Notion states conflict. Resolve the conflict before running risky commands.`
- `REVIEW_DONE`: `Daily ops loop is complete.`

Detailed artifact paths stay in `stages`. `operator_summary` intentionally omits long path lists.

## 6. n8n Usage

n8n should consume `operator_summary` first:

- title/date/account display: `title`, `account_id`, `data_date`, `trade_date`
- headline state: `overall_status`, `workflow_status`, `current_step`, `current_step_status`
- message body: `operator_message`
- action/routing: `recommended_operator_action`, `terminal`, `has_reconciliation_conflicts`
- command display: `next_command`
- safety badges: `command_type`, `risk_level`, `requires_manual_approval`
- compact counts: `ready_count`, `blocked_count`, `warning_count`, `done_count`, `unknown_count`

n8n must not auto-execute commands with:

- `requires_manual_approval=true`
- `risk_level=DANGEROUS`
- `command_type=LEDGER_WRITE`
- Notion write/sync command types unless a later approval-based MFU explicitly allows them

## 7. Compatibility

This is an additive contract. Existing fields remain:

- `schema_version`
- `next_command`
- `next_action`
- `summary`
- `stage_counts`
- `reconciliation_summary`
- `stages[*].reconciliation_*`
- `stages[*].notion_*`
- `stages[*].evidence_*`

The schema version remains `mfu_oper9_daily_ops_status.v1`.

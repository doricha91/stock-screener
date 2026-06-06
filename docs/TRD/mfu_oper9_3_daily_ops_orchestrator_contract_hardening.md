# MFU-OPER9-3 Daily Ops Orchestrator Contract Hardening

## 1. Summary

MFU-OPER9-3 hardens the local-only Daily Ops Orchestrator contract introduced in OPER9-2.

The scope is JSON, CLI, exit-code, and status-report contract stability for human operators and later automation consumers. This work does not implement n8n workflows and does not execute Notion reads, Notion writes, Manual Execution commits, Manual Review appends, broker calls, ledger writes, or DB changes.

Current CLI remains:

```cmd
python scripts\paper_daily_ops.py status --account-id <ACCOUNT_ID> --data-date <DATA_DATE> --trade-date <TRADE_DATE> --json
```

New optional CLI flags:

```cmd
--strict-exit
--write-status-report
--status-report-path <PATH>
```

## 2. Schema Version Decision

`schema_version` remains `mfu_oper9_daily_ops_status.v1`.

Reason:

- Existing top-level fields are preserved.
- Added fields are additive and derived from existing local status data.
- Existing consumers that key on v1 can continue reading `next_command`, safety flags, and `stages`.
- A version bump is deferred until a future change removes fields, changes meanings, or adds an incompatible evidence/source contract.

## 3. JSON Contract Additions

Existing compatibility fields remain:

```json
{
  "next_command": "python ...",
  "read_only": true,
  "write_executed": false,
  "notion_api_called": false,
  "commit_append_executed": false
}
```

New top-level fields:

```json
{
  "operation_write_executed": false,
  "status_report_written": false,
  "status_report_path": null,
  "next_action": null,
  "summary": {
    "terminal": false,
    "needs_attention": true,
    "has_blockers": false,
    "has_warnings": false,
    "has_unknowns": true,
    "recommended_operator_action": "CHECK_NOTION"
  },
  "stage_counts": {
    "DONE": 0,
    "READY": 0,
    "BLOCKED": 0,
    "WARNING": 0,
    "UNKNOWN": 0,
    "NOT_STARTED": 0
  }
}
```

Each stage also includes a `next_action` object next to the existing `next_command` field.

## 4. next_action Contract

`next_command` remains the backward-compatible string field.

`next_action` is a structured interpretation of the same command:

```json
{
  "command": "python scripts\\import_notion_executions.py --date 2026-06-08 --account-id paper_ops --commit --preview-json \"...\" --json",
  "command_type": "LEDGER_WRITE",
  "risk_level": "REQUIRES_MANUAL_REVIEW",
  "requires_manual_approval": true,
  "writes_notion": false,
  "writes_ledger": true,
  "calls_broker": false,
  "reason": "Commit/append commands mutate local source-of-truth artifacts and require operator review."
}
```

Classification policy:

- `paper.py data-freshness` and `paper.py status` are `READ_ONLY` + `SAFE`.
- `export_paper_to_notion.py ... --confirm-actual` is `NOTION_WRITE` + `REQUIRES_MANUAL_REVIEW`.
- `sync_notion_*` commands are `NOTION_WRITE` + `REQUIRES_MANUAL_REVIEW`.
- `import_notion_executions.py --commit` and `import_notion_reviews.py --commit` are `LEDGER_WRITE` + `REQUIRES_MANUAL_REVIEW`.
- Preview import commands are `READ_ONLY` + `SAFE`.
- Broker/order command classes are `DANGEROUS`, but the orchestrator does not currently recommend broker commands.
- If local workflow status is `REVIEW_DONE`, top-level and stage-level `next_action` are `null`.

## 5. Exit Code Policy

Default behavior preserves OPER9-2 compatibility:

- `0`: CLI ran and generated JSON/status output, even if `overall_status` is `WARNING`, `UNKNOWN`, or local-stage `BLOCKED`.
- `2`: input validation error, such as missing account id or invalid date.
- `3`: unexpected exception.

Automation can opt into strict branching with `--strict-exit`:

- `0`: generated status is not `WARNING`, `UNKNOWN`, or `BLOCKED`.
- `1`: generated status is `WARNING` or `UNKNOWN`.
- `2`: generated status is `BLOCKED`, or input validation failed.
- `3`: unexpected exception.

This keeps existing operator scripts stable while giving external automation a deterministic exit-code contract.

## 6. Status Report Persistence

Default execution writes no files and prints to stdout only.

When `--write-status-report` is provided, the CLI persists the final status JSON. If `--status-report-path` is omitted, the default path is:

```text
<account_root>\reports\daily_ops_status_<TRADE_DATE>.json
```

This file is diagnostic/status output, not an operational write. The payload keeps:

```json
{
  "write_executed": false,
  "operation_write_executed": false,
  "status_report_written": true
}
```

`status_report_path` is set to the written file path only after the report is written.

## 7. Safety Boundary

Still forbidden in OPER9-3:

- Notion live read
- Notion actual write/export/sync execution
- Manual Execution commit execution
- Manual Review append execution
- broker/API integration
- ledger/DB mutation
- generated outputs other than explicitly requested status report persistence
- n8n workflow creation

## 8. Verification

Required verification:

```cmd
python scripts\paper_daily_ops.py status --help
python scripts\paper_daily_ops.py status --account-id paper_pilot_202606 --data-date 2026-06-05 --trade-date 2026-06-08 --json
python scripts\paper_daily_ops.py status --account-id paper_pilot_202606 --data-date 2026-06-05 --trade-date 2026-06-08 --json --write-status-report
pytest tests/test_paper_daily_ops_orchestrator.py -q
pytest tests/test_paper_daily_ops_orchestrator.py tests/test_paper_daily_plan_generation.py -q
git diff --check
git status --short
```

Status report smoke output must not be committed.

## 9. Remaining Limitations

- Notion export/sync stages remain `UNKNOWN` unless a future local sidecar evidence contract proves them.
- The contract classifies recommended command risk, but does not execute or verify downstream commands.
- `schema_version` will need a bump if OPER9-4 changes the evidence model incompatibly.

## 10. Next Work

Recommended next MFU:

```text
MFU-OPER9-4 Daily Ops Orchestrator Evidence Contract
```

Candidate scope:

- Notion export/sync local sidecar contract
- local proof for reducing `UNKNOWN` stage count
- explicit evidence freshness and source metadata

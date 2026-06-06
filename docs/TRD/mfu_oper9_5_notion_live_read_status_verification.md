# MFU-OPER9-5 Notion Live Read Status Verification

## 1. Summary

MFU-OPER9-5 adds optional read-only Notion live status verification to the Daily Ops Orchestrator.

Default status execution remains local-only. Notion API reads occur only when the operator passes:

```cmd
--include-notion-read
```

This work does not make Notion the source of truth. Local CSV/JSON/Markdown/SQLite artifacts remain the source-of-truth layer. Notion live read is a UI-state verification signal only.

## 2. Reused Notion Infrastructure

The implementation reuses existing project layers:

- `core/notion_settings.py`
  - `load_notion_settings`
  - `get_notion_token`
  - `get_notion_data_source_id`
- `core/notion_client.py`
  - `NotionClient.query_data_source`
  - `NotionAPIError`
- `core/notion_mapping.py`
  - `load_notion_property_mapping`
  - `get_mapping_section`
  - `resolve_notion_property_name`
- existing config keys:
  - `daily_plans`
  - `manual_executions`
  - `manual_reviews`

No duplicate Notion client was introduced.

## 3. CLI Contract

Existing command remains:

```cmd
python scripts\paper_daily_ops.py status --account-id <ACCOUNT_ID> --data-date <DATA_DATE> --trade-date <TRADE_DATE> --json
```

New opt-in flags:

```cmd
--include-notion-read
--notion-timeout-seconds <N>
```

Default behavior:

- `--include-notion-read` absent: no Notion API call
- `--include-notion-read` present: read-only Notion data source queries may be executed

## 4. JSON Contract

Top-level additions:

```json
{
  "notion_live_read_enabled": true,
  "notion_live_read_called": true,
  "notion_live_read_status": "PASS|WARNING|BLOCKED|UNKNOWN|SKIPPED",
  "notion_live_read_errors": [],
  "notion_live_read_summary": {}
}
```

Stage-level additions:

```json
{
  "notion_checked": true,
  "notion_status": "PASS|WARNING|BLOCKED|UNKNOWN|SKIPPED",
  "notion_row_count": 1,
  "notion_status_counts": {
    "READY": 1
  },
  "notion_errors": [],
  "notion_warnings": []
}
```

Existing OPER9-3/4 fields remain:

- `next_command`
- `next_action`
- `summary`
- `stage_counts`
- `evidence_path`
- `evidence_status`
- `evidence_checked`
- `evidence_errors`
- safety flags

## 5. Read Targets

The read-only verifier queries:

- Daily Plans
  - `DAILY_PLAN_NOTION_EXPORT`
- Manual Executions
  - `MANUAL_EXECUTION_TEMPLATE`
  - `MANUAL_EXECUTION_PREVIEW`
  - `MANUAL_EXECUTION_STATUS_SYNC`
- Manual Reviews
  - `MANUAL_REVIEW_TEMPLATE`
  - `MANUAL_REVIEW_PREVIEW`
  - `MANUAL_REVIEW_STATUS_SYNC`

Queries filter by mapped account/date properties. The verifier summarizes row counts, status distributions, mismatches, warnings, and errors.

## 6. Stage Decision Rules

When Notion read is skipped, local/evidence stage behavior is unchanged.

When Notion read is enabled:

- clear Notion `PASS` can improve Notion export/sync stages to `DONE`
- Notion `WARNING` marks the corresponding Notion export/sync stage as `WARNING`
- Notion mismatch or read-stage `BLOCKED` marks the stage as `BLOCKED`
- local dependency `BLOCKED` is not upgraded to `DONE` by Notion alone
- Manual Execution READY rows preserve the preview recommendation when local preview is missing
- local commit plus unsynced Notion rows keeps the sync command visible as `WARNING`
- `REVIEW_DONE` still suppresses top-level and stage-level `next_command` / `next_action`

## 7. Failure Handling

If settings, token, data source id, mapping, or API read fails under `--include-notion-read`, the CLI still emits JSON. The live-read status is reported as `BLOCKED` or `UNKNOWN` with errors.

This is not treated as an operational write failure.

## 8. Safety Boundary

Forbidden in OPER9-5:

- Notion create/update/delete
- `export_paper_to_notion.py` execution
- `sync_notion_execution_status.py` execution
- `sync_notion_review_status.py` execution
- `import_notion_executions.py --commit`
- `import_notion_reviews.py --commit`
- broker/API/order integration
- ledger/DB mutation
- n8n workflow creation
- generated outputs commit

## 9. Verification

Required verification:

```cmd
python scripts\paper_daily_ops.py status --help
python scripts\paper_daily_ops.py status --account-id paper_pilot_202606 --data-date 2026-06-05 --trade-date 2026-06-08 --json
python scripts\paper_daily_ops.py status --account-id paper_pilot_202606 --data-date 2026-06-05 --trade-date 2026-06-08 --json --include-notion-read
pytest tests\test_paper_daily_ops_orchestrator.py -q
pytest tests\test_paper_daily_ops_orchestrator.py tests\test_paper_daily_plan_generation.py -q
git diff --check
git status --short
```

Tests use fake/mocked Notion clients. Default tests must not call the real Notion API.

## 10. Manual Smoke

An optional real Notion read smoke can be run only when:

- `config/notion_settings.json` is configured
- the token env var is present
- the operator explicitly passes `--include-notion-read`

No write command is part of this smoke.

## 11. Remaining Limitations

- Reconciliation policy is still intentionally coarse.
- The live read summarizes UI rows but does not make Notion authoritative.
- More exact local/Notion status combinations should be formalized in a reconciliation matrix.

## 12. Next Work

Recommended next work:

- `MFU-OPER9-6 Local/Notion Reconciliation Matrix`
- or `MFU-OPER9 Closeout`

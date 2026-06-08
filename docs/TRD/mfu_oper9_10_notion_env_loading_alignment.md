# MFU-OPER9-10 Notion Env Loading Alignment

## 1. Summary

OPER9-10 aligns Daily Ops Orchestrator read-only Notion status with the existing Notion export/import/sync scripts.

Before this change, `scripts\export_paper_to_notion.py` loaded `.env` and could use `.env`-only Notion settings, while:

```cmd
python scripts\paper_daily_ops.py status --account-id <ACCOUNT_ID> --data-date <DATA_DATE> --trade-date <TRADE_DATE> --json --include-notion-read
```

could stop with `Notion settings are disabled or missing.` when `config/notion_settings.json` was missing or disabled.

OPER9-10 keeps Notion live read opt-in and read-only, but allows the same `.env`-centered configuration path used by the existing Notion operation scripts.

## 2. Configuration Resolution

`scripts\paper_daily_ops.py` now loads the repository root `.env` with `load_dotenv(ROOT / ".env")`.

`core.paper_daily_ops_notion_status.build_notion_live_read_status()` keeps the existing settings resolution order:

1. Explicit environment override values.
2. `settings.data_sources`.
3. Legacy `settings.databases` fallback.

When `config/notion_settings.json` is missing or `enabled=false`, live read is still allowed if the required env-only settings are present.

Required env-only values:

- token from `settings.token_env`, normally `NOTION_TOKEN`
- `NOTION_DAILY_PLANS_DATA_SOURCE_ID`
- `NOTION_MANUAL_EXECUTIONS_DATA_SOURCE_ID`
- `NOTION_MANUAL_REVIEWS_DATA_SOURCE_ID`

## 3. Error Reporting

The live read helper now reports missing configuration by value name instead of returning only a generic disabled-settings message.

Examples:

- `Missing Notion token in environment variable: NOTION_TOKEN.`
- `Missing required Notion env override: NOTION_MANUAL_REVIEWS_DATA_SOURCE_ID.`
- `Missing Notion data source id for key 'daily_plans'.`

Token values and data source ids must not be logged or committed.

## 4. Live Read Behavior

Daily Plan live read uses the same External Key lookup path as the Daily Plan export/upsert path:

```text
daily_plan:<account_id>:<trade_date>
```

This avoids treating Notion as source-of-truth while making the read-only verification match the previously exported row.

Individual Notion API query failures are preserved as stage warnings instead of discarding successful reads from other stages. Configuration failures, missing token, missing required data source env overrides, and mapping failures still produce a BLOCKED live read report.

## 5. Safety Boundary

This change does not execute or add:

- Notion create/update/delete
- `export_paper_to_notion.py`
- `sync_notion_*`
- `import_notion_executions.py --commit`
- `import_notion_reviews.py --commit`
- broker/API/order calls
- ledger or DB mutation
- n8n workflows

`--include-notion-read` remains an explicit opt-in read-only status check.

## 6. Test Coverage

`tests/test_paper_daily_ops_orchestrator.py` covers:

- disabled/missing settings with sufficient env overrides proceeds without BLOCKED
- missing token reports the token env name
- missing data source env reports the missing env override name
- CLI status path calls the root `.env` loader when `--include-notion-read` is used
- Daily Plan live read uses External Key lookup
- per-stage Notion API exceptions are JSON-safe warnings
- existing fake-client Notion read and OPER9 operator summary/stage advancement tests remain intact

## 7. Expected Smoke Outcome

After a Daily Plan has already been exported to Notion, the read-only status command should be able to read the existing row using `.env` settings:

```cmd
python scripts\paper_daily_ops.py status --account-id paper_orch_smoke_202606 --data-date 2026-06-05 --trade-date 2026-06-08 --json --include-notion-read
```

Expected high-level result:

- `notion_live_read_enabled=true`
- `notion_live_read_called=true`
- `notion_live_read_status=PASS`, `WARNING`, or another non-configuration BLOCKED status if Notion itself rejects the read
- `DAILY_PLAN_NOTION_EXPORT.notion_row_count > 0` when the row exists
- operator-facing next step advances past `DAILY_PLAN_NOTION_EXPORT` when reconciliation confirms the row

## 8. Remaining Limits

- This does not add schema drift auto-remediation.
- It does not make Notion a source of truth.
- It does not implement n8n.
- Approval-based execution remains a later OPER10/OPER11 concern.

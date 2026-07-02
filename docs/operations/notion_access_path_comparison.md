# Notion Access Path Comparison

This note compares the Notion access path used by Stage A writes with the Gate 1
manual execution read path.

## 1. Existing Notion Write Path

Stage A Step 4/5 writes use `scripts/export_paper_to_notion.py`.

Access flow:

```text
export_paper_to_notion.py
-> load_dotenv()
-> load_notion_settings(allow_missing=True)
-> load_notion_property_mapping()
-> NotionClient(get_notion_token(settings))
-> export_manual_execution_template_to_notion(...)
-> get_notion_data_source_id(
     settings,
     "manual_executions",
     env_override="NOTION_MANUAL_EXECUTIONS_DATA_SOURCE_ID"
   )
```

Key behavior:

- Missing `config/notion_settings.json` is allowed.
- When the settings file is missing, `load_notion_settings(allow_missing=True)`
  returns a default settings object with `token_env=NOTION_TOKEN`.
- Data source IDs can come from environment variables such as
  `NOTION_MANUAL_EXECUTIONS_DATA_SOURCE_ID`.
- Property names come from `load_notion_property_mapping()`, which can fall
  back to `config/notion_property_mapping.example.json`.

## 2. Gate Read Path

Gate 1 reads use `scripts/runbook_gate_checker.py`.

Before the fix, the access flow was:

```text
runbook_gate_checker.py
-> _load_dotenv_if_available()
-> load_notion_settings(allow_missing=False)
-> load_notion_property_mapping()
-> get_notion_data_source_id(
     settings,
     "manual_executions",
     env_override="NOTION_MANUAL_EXECUTIONS_DATA_SOURCE_ID"
   )
-> NotionClient(get_notion_token(settings))
-> query_data_source(...)
```

After the fix, Gate 1 uses `load_notion_settings(allow_missing=True)`, matching
the write path's env-compatible settings behavior.

## 3. Token Loading Difference

The write path loads `.env` at module startup and permits a missing settings
file. It can therefore resolve the token through `NOTION_TOKEN`.

The original Gate read path loaded `.env` opportunistically, but required
`config/notion_settings.json`. That meant it failed before the same environment
fallback path could be used.

## 4. Data Source ID Loading Difference

Both paths use the same data source key and environment override:

```text
data_source_key: manual_executions
env_override: NOTION_MANUAL_EXECUTIONS_DATA_SOURCE_ID
```

The write path could reach this override because missing settings were allowed.
The read path could not reach it while `allow_missing=False`.

## 5. Mapping Loading Difference

Both paths use the `manual_executions` mapping section. Gate 1 depends on these
logical fields:

```text
account_id
execution_date
linked_daily_plan_key
actual_price
status
import_status
symbol
side
quantity
external_key
```

The property mapping loader is shared and was not the cause of the Gate 1
BLOCKED result.

## 6. Account ID and Key Normalization

Both paths normalize account IDs through `normalize_notion_account_id()`.

The linked plan key expected by Gate 1 matches the write/export convention:

```text
daily_plan:{account_id}:{trade_date}
```

Manual execution external keys follow the same account/date convention:

```text
manual_execution:{account_id}:{trade_date}:...
```

## 7. Root Cause

Gate 1 failed because `runbook_gate_checker.py` used
`load_notion_settings(allow_missing=False)`.

In the current environment, `config/notion_settings.json` is absent, while the
working write path relies on `.env` values and `allow_missing=True`. The read
path therefore stopped with:

```text
Missing Notion settings file: config/notion_settings.json
```

before token and data source environment overrides could be used.

## 8. Fix Applied

Gate 1 now uses:

```python
load_notion_settings(allow_missing=True)
```

This aligns Gate read access with the existing write/export path without
changing Notion write behavior, schema, status fields, or automatic input
updates.

## 9. Longer-Term Option

If more read/write Notion paths are added, consider extracting a small shared
helper such as `core/notion_access.py`:

```text
load_notion_access_context(target)
get_client()
get_data_source_id(target)
get_mapping(target)
```

That is not required for the current minimal fix.

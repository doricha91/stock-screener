# PAPER17-5/6 Notion Settings Preflight and Duplicate Audit Read-only Smoke Rerun

## 1. Purpose

Document the Notion settings path required by the Daily Ops Status duplicate audit and record the second read-only smoke attempt for `paper_sandbox / 2026-05-20`.

This work is a read-only preflight/smoke step. It does not perform Notion actual write/export/sync.

## 2. Background

PAPER17-4A added the `daily_ops_status` duplicate audit dry-run implementation.

PAPER17-4B attempted the first read-only smoke and stopped with `settings_error` because `config/notion_settings.json` was missing. No Notion API read and no Notion write/export/sync occurred.

PAPER17-6 aligned the duplicate audit CLI with the project convention that Notion settings may come from `.env` / environment variables.

## 3. Required Settings

The audit CLI now loads Notion settings through `load_notion_settings(allow_missing=True)`.

Required local settings:

| Setting | Source | Current preflight result |
| --- | --- | --- |
| Notion settings file | `config/notion_settings.json` | optional for env-only duplicate audit |
| Token env var name | `token_env`, default `NOTION_TOKEN` | set for successful smoke |
| Daily Ops Status data source id | `data_sources.daily_ops_status` or override env | `NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID` set for successful smoke |
| Property mapping | `config/notion_property_mapping.example.json` / active mapping loader | `daily_ops_status.external_key = External Key` exists |

Secret values were not printed or recorded.

## 4. Supported Configuration Paths

Supported settings-file path:

```text
config/notion_settings.json
```

It should be created locally from:

```text
config/notion_settings.example.json
```

The example file includes:

```json
{
  "enabled": false,
  "token_env": "NOTION_TOKEN",
  "data_sources": {
    "daily_ops_status": ""
  }
}
```

The Daily Ops Status data source can also be supplied by environment override:

```text
NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID
```

The Notion token is read from the environment variable named by `token_env`; by default:

```text
NOTION_TOKEN
```

For env-only duplicate audit smoke, both variables are required:

```text
NOTION_TOKEN
NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID
```

## 5. Secret Safety Policy

- Do not commit `config/notion_settings.json`.
- Do not commit `.env` or `.env.*`.
- Do not print Notion tokens.
- Do not print full data source IDs in reports.
- Report only whether settings are present or missing.
- Stage only this TRD document for PAPER17-5.

## 6. Preflight Checklist

| Check | Result |
| --- | --- |
| `config/notion_settings.json` exists | not required for env-only path |
| `NOTION_TOKEN` is set | yes for successful smoke |
| `NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID` is set | yes for successful smoke |
| CLI help shows write/confirm option | no |
| CLI supports only `daily_ops_status` target | yes |
| Mapping has Daily Ops Status External Key property | yes |

The first sandboxed retry hit a Notion transport error. After a user-approved read-only network retry, the smoke reached Notion query/read and returned one matching row.

## 7. Read-only Smoke Command

```cmd
python scripts\dev\audit_notion_duplicates.py --target daily_ops_status --account-id paper_sandbox --date 2026-05-20 --json
```

## 8. Smoke Result

The PAPER17-6 smoke was rerun with env-based settings and reached Notion query/read. It returned one matching row.

```json
{
  "target": "daily_ops_status",
  "account_id": "paper_sandbox",
  "status_date": "2026-05-20",
  "external_key": "daily_ops_status:paper_sandbox:2026-05-20",
  "match_count": 1,
  "page_ids": ["****4292"],
  "classification": "update_candidate",
  "recommended_action": "safe_to_update_after_required_preflight",
  "write_executed": false
}
```

The page ID is masked in this document. The CLI also masks `data_source_id` in JSON output.

## 9. Interpretation

`update_candidate` means exactly one Daily Ops Status row exists for `daily_ops_status:paper_sandbox:2026-05-20`.

This is not actual export approval. Actual export remains gated until:

- schema/property preflight is clean,
- duplicate audit returns a non-blocking result,
- the Command Gate SOP preflight passes.

## 10. Remaining Limitations

- This rerun covered only `daily_ops_status / paper_sandbox / 2026-05-20`.
- This preflight does not replace schema validation.
- This preflight does not validate Notion view/filter drift.
- This preflight is not actual export approval.
- `write_executed=false` remained true for the smoke result.

## 11. PAPER17-7 Recommendation

PAPER17-7 should define a dedicated Notion settings preflight command or operator checklist that reports:

- settings file presence,
- token env var presence,
- Daily Ops Status data source configuration,
- active mapping availability,
- secret-safe masked status only.

Do not proceed to actual export until duplicate audit, schema preflight, External Key review, and all Command Gate checks pass.

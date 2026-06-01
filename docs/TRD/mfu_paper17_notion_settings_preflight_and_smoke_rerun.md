# PAPER17-5 Notion Settings Preflight and Duplicate Audit Read-only Smoke Rerun

## 1. Purpose

Document the Notion settings path required by the Daily Ops Status duplicate audit and record the second read-only smoke attempt for `paper_sandbox / 2026-05-20`.

This work is a read-only preflight/smoke step. It does not perform Notion actual write/export/sync.

## 2. Background

PAPER17-4A added the `daily_ops_status` duplicate audit dry-run implementation.

PAPER17-4B attempted the first read-only smoke and stopped with `settings_error` because `config/notion_settings.json` was missing. No Notion API read and no Notion write/export/sync occurred.

## 3. Required Settings

The audit CLI loads Notion settings through `load_notion_settings(allow_missing=False)`.

Required local settings:

| Setting | Source | Current preflight result |
| --- | --- | --- |
| Notion settings file | `config/notion_settings.json` | not present |
| Token env var name | `token_env`, default `NOTION_TOKEN` | `NOTION_TOKEN` not set |
| Daily Ops Status data source id | `data_sources.daily_ops_status` or override env | `NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID` not set |
| Property mapping | `config/notion_property_mapping.example.json` / active mapping loader | `daily_ops_status.external_key = External Key` exists |

Secret values were not printed or recorded.

## 4. Supported Configuration Paths

The supported settings path is:

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
| `config/notion_settings.json` exists | no |
| `NOTION_TOKEN` is set | no |
| `NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID` is set | no |
| CLI help shows write/confirm option | no |
| CLI supports only `daily_ops_status` target | yes |
| Mapping has Daily Ops Status External Key property | yes |

Because settings are missing, actual export remains forbidden and the read-only smoke cannot reach Notion query/read.

## 7. Read-only Smoke Command

```cmd
python scripts\dev\audit_notion_duplicates.py --target daily_ops_status --account-id paper_sandbox --date 2026-05-20 --json
```

## 8. Smoke Result

The smoke was rerun and stopped safely with `settings_error`.

```json
{
  "target": "daily_ops_status",
  "account_id": "paper_sandbox",
  "status_date": "2026-05-20",
  "external_key": "",
  "match_count": 0,
  "page_ids": [],
  "classification": "settings_error",
  "recommended_action": "stop_actual_settings_error",
  "write_executed": false
}
```

The omitted error text stated that `config/notion_settings.json` is missing.

## 9. Interpretation

`settings_error` means the duplicate audit did not reach Notion query/read. This is the correct safe failure mode when the local Notion settings are absent.

No actual export can be considered until:

- local Notion settings are configured,
- the token environment variable is present,
- Daily Ops Status data source ID is configured,
- schema/property preflight is clean,
- duplicate audit returns a non-blocking result,
- the Command Gate SOP preflight passes.

## 10. Remaining Limitations

- This rerun did not perform Notion API read because settings are missing.
- The duplicate status for `daily_ops_status:paper_sandbox:2026-05-20` is still unknown.
- This preflight does not replace schema validation.
- This preflight does not validate Notion view/filter drift.
- This preflight is not actual export approval.
- `write_executed=false` remained true for the smoke result.

## 11. PAPER17-6 Recommendation

PAPER17-6 should define a dedicated Notion settings preflight command or operator checklist that reports:

- settings file presence,
- token env var presence,
- Daily Ops Status data source configuration,
- active mapping availability,
- secret-safe masked status only.

After that, rerun the same read-only duplicate audit smoke once. Do not proceed to actual export until the duplicate audit and all Command Gate checks pass.

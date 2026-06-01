# PAPER17-4A Daily Ops Status Duplicate Audit Dry-run

## Purpose

PAPER17-4A adds a read-only duplicate audit interface for the Notion `daily_ops_status` target.

The audit checks the Notion row match state for a single `account_id` / `status_date` / `External Key` before any guarded actual export is considered. It is one preflight step only and does not approve actual export by itself.

## Scope

In scope:

- `daily_ops_status` only.
- External Key format: `daily_ops_status:{account_id}:{status_date}`.
- Read-only Notion query by External Key.
- Classification of zero, one, or multiple matching rows.
- JSON output with `write_executed=false`.
- Fake-client unit tests.

Out of scope:

- Notion write.
- Actual export/sync.
- Duplicate cleanup.
- Schema/view drift automation.
- Detail exporter duplicate audit.
- Manual Execution/Review status sync duplicate audit.

## CLI

Recommended command:

```cmd
python scripts\dev\audit_notion_duplicates.py --target daily_ops_status --account-id paper_sandbox --date 2026-05-20 --json
```

Optional arguments:

```cmd
--external-key daily_ops_status:paper_sandbox:2026-05-20
--expected-page-id <page_id>
--json
```

Policy:

- `--target` must be `daily_ops_status`.
- `--account-id` is required.
- `--date` or `--external-key` is required.
- If `--external-key` is provided, `--date` is also required so account/date/key consistency can be checked.
- No actual/write option is available.
- No `--confirm-actual` option is available.

## Settings Contract

The duplicate audit CLI supports both settings-file and environment-variable based configuration.

Supported paths:

- `config/notion_settings.json` with `data_sources.daily_ops_status`.
- `.env` / environment variables.

Required environment variables for env-only operation:

```text
NOTION_TOKEN
NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID
```

`config/notion_settings.json` is optional for this CLI when both environment variables are present.

Secret handling:

- Do not commit `.env`.
- Do not commit `config/notion_settings.json`.
- Do not print the Notion token.
- Do not print the full data source ID.
- JSON output masks `data_source_id`.

## Input Contract

Inputs:

- `target`: `daily_ops_status`
- `account_id`: audited account id
- `date`: `YYYY-MM-DD` or `YYYYMMDD`
- `external_key`: optional, but must match account/date when provided
- `expected_page_id`: optional, for update rerun consistency checks

External Key format:

```text
daily_ops_status:{account_id}:{status_date}
```

Example:

```text
daily_ops_status:paper_sandbox:2026-05-20
```

## Output Contract

Minimum JSON fields:

```json
{
  "target": "daily_ops_status",
  "account_id": "paper_sandbox",
  "status_date": "2026-05-20",
  "external_key": "daily_ops_status:paper_sandbox:2026-05-20",
  "match_count": 1,
  "page_ids": ["..."],
  "classification": "update_candidate",
  "recommended_action": "safe_to_update_after_required_preflight",
  "write_executed": false,
  "data_source_id": "****abcd"
}
```

Classification values:

- `create_candidate`
- `update_candidate`
- `duplicate_blocker`
- `manual_review_required`
- `settings_error`
- `query_error`

Recommended action values:

- `safe_to_create_after_required_preflight`
- `safe_to_update_after_required_preflight`
- `stop_actual_duplicate_detected`
- `stop_actual_manual_review_required`
- `stop_actual_settings_error`
- `stop_actual_query_error`

## Classification Rules

| Condition | Classification | Recommended Action |
| --- | --- | --- |
| `match_count = 0` | `create_candidate` | `safe_to_create_after_required_preflight` |
| `match_count = 1` | `update_candidate` | `safe_to_update_after_required_preflight` |
| `match_count >= 2` | `duplicate_blocker` | `stop_actual_duplicate_detected` |
| `expected_page_id` provided and actual single page differs | `manual_review_required` | `stop_actual_manual_review_required` |
| `external_key` / `account_id` / `date` mismatch | `manual_review_required` | `stop_actual_manual_review_required` |
| settings load/data source id error | `settings_error` | `stop_actual_settings_error` |
| Notion query error | `query_error` | `stop_actual_query_error` |

All results must include `write_executed=false`.

## Read-only Safety Policy

- The implementation calls `query_by_external_key` only.
- It must not call `create_page`.
- It must not call `update_page`.
- It must not call `upsert_page_by_external_key`.
- It must not run status sync actual.
- It must not run export actual.
- It must not modify Notion rows or properties.

## Example Outputs

Zero matches:

```json
{
  "classification": "create_candidate",
  "recommended_action": "safe_to_create_after_required_preflight",
  "match_count": 0,
  "page_ids": [],
  "write_executed": false
}
```

One match:

```json
{
  "classification": "update_candidate",
  "recommended_action": "safe_to_update_after_required_preflight",
  "match_count": 1,
  "page_ids": ["page-id"],
  "write_executed": false
}
```

Two or more matches:

```json
{
  "classification": "duplicate_blocker",
  "recommended_action": "stop_actual_duplicate_detected",
  "match_count": 2,
  "page_ids": ["page-1", "page-2"],
  "write_executed": false
}
```

## Test Coverage

Unit tests cover:

- External Key generation and date normalization.
- `0` matches -> `create_candidate`.
- `1` match -> `update_candidate`.
- `2+` matches -> `duplicate_blocker`.
- expected_page_id mismatch -> `manual_review_required`.
- account/date/external_key mismatch -> `manual_review_required`.
- `write_executed=false`.
- unsupported target CLI failure.
- env-only settings path using `NOTION_TOKEN` and `NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID`.
- secret raw values are not printed in CLI JSON output.

Tests use fake clients and do not call the Notion API.

## Remaining Limitations

- This audit is limited to `daily_ops_status`.
- Duplicate audit does not replace schema validation.
- Schema validation does not replace duplicate audit.
- Audit pass alone does not allow actual export.
- Full Command Gate SOP preflight is still required before any guarded actual export.
- Duplicate cleanup is not implemented.

## PAPER17-7 Recommendation

Next steps:

- Add a dedicated secret-safe settings preflight command or checklist.
- Consider masking page IDs in operator-facing output if needed.
- Keep actual export blocked unless duplicate audit, schema preflight, External Key review, and explicit operator approval all pass.

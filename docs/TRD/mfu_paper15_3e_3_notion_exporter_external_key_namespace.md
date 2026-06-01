## Purpose

PAPER15-3E-3 applies `Account ID` and account-aware `External Key` generation to the read-only Notion exporter layer only.

## Scope / Non-scope

In scope:
- `Daily Plans`
- `Account Snapshots`
- `Weekly Reports`
- `Benchmark Reports`
- `Daily Review Summaries`
- `scripts/export_paper_to_notion.py --account-id`
- `core/notion_exporters.py` payload and dry-run summary updates

Out of scope:
- Manual Execution / Manual Review importer changes
- status sync changes
- legacy row migration preview
- Notion schema migration
- actual Notion write execution

## Account-aware External Key

Read-only export targets now build keys in the following form:

- `daily_plan:{account_id}:{date}`
- `account_snapshot:{account_id}:{snapshot_date}`
- `weekly_report:{account_id}:{period_start}:{period_end}`
- `benchmark:{account_id}:{latest_snapshot_date}:{run_mode}`
- `daily_review_summary:{account_id}:{review_date}`

If `--account-id` is omitted, the exporter resolves to `paper_default`.

## Account ID Property

Read-only export payloads now include:

- `account_id -> Account ID`

The payload uses Notion `select` properties and writes the resolved `account_id` value.

## Legacy Fallback

`paper_default` supports legacy lookup fallback during upsert planning:

1. Look up the new account-aware key.
2. If not found, look up the legacy account-less key.
3. If the legacy page exists, update that page and mark `legacy_fallback_used=true`.

Non-default accounts do not use legacy fallback.

## Dry-run Summary

Dry-run summaries now include:

- `account_id`
- `external_key`
- `legacy_external_key`
- `legacy_fallback_used`
- `data_source_key`
- `target`
- `action`
- `dry_run`

## Why Importers / Status Sync Are Unchanged

This MFU is limited to read-only exporters. Importers and status sync paths still use the pre-existing account-less behavior and will be updated in later MFUs so that key namespaces, lookup filters, and backward-compatibility rules can be changed together.

## Next Step

Recommended follow-up:

- `PAPER15-NOTION-KEY` for importer/status-sync account-aware key namespace and lookup policy

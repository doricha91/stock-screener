# MFU-OPER9-4A Evidence Filename Date Format Alignment

## 1. Summary

MFU-OPER9-4A aligns Daily Ops Orchestrator Notion evidence sidecar filenames with existing paper artifact date naming.

Only the filename date format changes. Evidence JSON payload dates remain unchanged.

## 2. Change

Before:

```text
<account_root>\reports\daily_plan_notion_export_2026-06-08.json
```

After:

```text
<account_root>\reports\daily_plan_notion_export_20260608.json
```

The same compact `YYYYMMDD` filename rule applies to:

- `daily_plan_notion_export_20260608.json`
- `manual_execution_template_export_20260608.json`
- `manual_execution_status_sync_20260608.json`
- `manual_review_template_export_20260608.json`
- `manual_review_status_sync_20260608.json`

## 3. Payload Date Rule

The evidence payload still uses normalized dates:

```json
{
  "trade_date": "2026-06-08",
  "data_date": "2026-06-05"
}
```

Validation continues to compare payload `trade_date` against the orchestrator request date in `YYYY-MM-DD` format.

## 4. Compatibility

`paper_notion_evidence.v1` remains unchanged.

Hyphenated evidence filenames are not searched as fallback. If only the old filename exists, the orchestrator treats the stage as having no evidence and keeps the existing `UNKNOWN` behavior unless another guard applies.

## 5. Safety Boundary

This patch does not:

- call Notion
- write/export/sync Notion rows
- run Manual Execution commit
- run Manual Review append
- change broker/API/order logic
- mutate ledgers or DB files
- add evidence producer options
- create n8n workflow files

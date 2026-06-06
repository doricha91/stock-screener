# MFU-OPER9-4 Daily Ops Orchestrator Evidence Contract

## 1. Summary

MFU-OPER9-4 adds a local evidence sidecar contract for Daily Ops Orchestrator Notion export/sync stages.

The orchestrator still does not call Notion, write Notion rows, run Manual Execution commits, append Manual Reviews, call broker APIs, mutate ledgers, or change DB files. It only reads local JSON evidence files when they exist.

## 2. Target Stages

Evidence sidecars are supported for:

- `DAILY_PLAN_NOTION_EXPORT`
- `MANUAL_EXECUTION_TEMPLATE`
- `MANUAL_EXECUTION_STATUS_SYNC`
- `MANUAL_REVIEW_TEMPLATE`
- `MANUAL_REVIEW_STATUS_SYNC`

Preview and commit/append stages continue to use their existing local preview/commit report artifacts.

## 3. Evidence Schema

Schema version:

```text
paper_notion_evidence.v1
```

Common JSON shape:

```json
{
  "schema_version": "paper_notion_evidence.v1",
  "evidence_type": "DAILY_PLAN_NOTION_EXPORT",
  "account_id": "paper_pilot_202606",
  "trade_date": "2026-06-08",
  "data_date": "2026-06-05",
  "source_command": "python ...",
  "source_artifacts": [],
  "target_system": "notion",
  "operation": "export",
  "dry_run": false,
  "actual_executed": true,
  "notion_api_called": true,
  "write_executed": true,
  "status": "PASS",
  "page_count": 1,
  "created_count": 0,
  "updated_count": 1,
  "skipped_count": 0,
  "failed_count": 0,
  "warnings": [],
  "errors": [],
  "created_at": "2026-06-08T09:00:00+09:00",
  "producer": "export_paper_to_notion.py"
}
```

Required validation fields:

- `schema_version`
- `evidence_type`
- `account_id`
- `trade_date`
- `data_date` when not null
- `target_system=notion`
- `status`
- `failed_count`

## 4. Evidence Path Rules

The orchestrator automatically searches under account-root reports:

```text
<account_root>\reports\daily_plan_notion_export_<TRADE_DATE>.json
<account_root>\reports\manual_execution_template_export_<TRADE_DATE>.json
<account_root>\reports\manual_execution_status_sync_<TRADE_DATE>.json
<account_root>\reports\manual_review_template_export_<TRADE_DATE>.json
<account_root>\reports\manual_review_status_sync_<TRADE_DATE>.json
```

`<TRADE_DATE>` uses the normalized `YYYY-MM-DD` value.

For non-default accounts, matching `outputs\paper_test` evidence is never accepted as DONE evidence. If only legacy evidence exists, the stage is blocked because the evidence belongs to the wrong account root.

## 5. Stage Decision Rules

When the dependency for a target stage is not met, the existing BLOCKED behavior remains.

When the dependency is met:

- no evidence sidecar: keep existing `UNKNOWN`
- valid evidence with `status=PASS` and `failed_count=0`: `DONE`
- valid evidence with `status=WARNING`: `WARNING`
- valid evidence with `status=FAILED`: `BLOCKED`
- valid evidence with `failed_count > 0`: `BLOCKED`
- account/date/evidence_type/schema mismatch: `BLOCKED`
- malformed JSON: `WARNING`, never DONE
- unsupported/missing status: `BLOCKED`

`REVIEW_DONE` terminal behavior still suppresses `next_command` and `next_action` at top level and stage level.

## 6. JSON Contract Additions

Each stage now includes evidence metadata fields:

```json
{
  "evidence_path": "D:\\python\\StockScreener\\outputs\\paper_accounts\\paper_pilot_202606\\reports\\daily_plan_notion_export_2026-06-08.json",
  "evidence_status": "PASS",
  "evidence_checked": true,
  "evidence_errors": []
}
```

Existing OPER9-3 fields remain:

- `next_command`
- `next_action`
- `summary`
- `stage_counts`
- `status_report_written`
- `status_report_path`
- `operation_write_executed`
- safety flags

## 7. Safety Boundary

OPER9-4 does not implement evidence generation in Notion export/sync scripts. It defines and consumes the sidecar contract only.

Still forbidden:

- n8n workflow creation
- Notion live read
- Notion actual write/export/sync execution
- Manual Execution commit execution
- Manual Review append execution
- broker/API/order integration
- ledger/DB mutation
- generated outputs commit
- incompatible `schema_version` change

## 8. Verification

Required verification:

```cmd
python scripts\paper_daily_ops.py status --help
python scripts\paper_daily_ops.py status --account-id paper_pilot_202606 --data-date 2026-06-05 --trade-date 2026-06-08 --json
python scripts\paper_daily_ops.py status --account-id paper_pilot_202606 --data-date 2026-06-05 --trade-date 2026-06-08 --json --write-status-report
pytest tests\test_paper_daily_ops_orchestrator.py -q
pytest tests\test_paper_daily_ops_orchestrator.py tests\test_paper_daily_plan_generation.py -q
git diff --check
git status --short
```

Status report smoke output and any evidence sidecar test artifacts must not be committed.

## 9. Remaining Limitations

- Export/sync scripts do not yet have `--write-evidence`.
- Existing real operation evidence must be created by a future producer or manually for diagnostics.
- The orchestrator validates local sidecars but does not verify Notion state directly.

## 10. Next Work

Recommended next work:

- MFU-OPER9 Closeout: summarize completed orchestrator scope and defer n8n to OPER10/AUTO.
- MFU-OPER10 n8n Read-only Workflow Design: call orchestrator status, read status reports, and design alert/approval flow.

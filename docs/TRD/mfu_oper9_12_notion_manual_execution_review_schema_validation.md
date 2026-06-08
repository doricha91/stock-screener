# MFU-OPER9-12 Notion Manual Execution / Review Schema Validation

## 1. Summary

This document records a read-only validation of the Manual Execution and Manual Review Notion live-read warning observed after OPER9-10 and OPER9-11.

- Baseline commit: `5ba7fd8a491bab4438fe90b2ba3777d7dfed5ae8`
- Scope: schema validation, data source validation, property mapping validation, and minimal query filter validation
- Code changes: none
- Notion write/create/update/delete: none
- import `--commit`, ledger mutation, broker/API/order execution: none
- Secret handling: token, data source IDs, page IDs, and private row contents are not documented

## 2. Background

OPER9-10 aligned `paper_daily_ops.py status --include-notion-read` with the existing `.env`-based Notion configuration path. After that change:

- Daily Plan live read succeeds through the exported Notion row.
- `DAILY_PLAN_NOTION_EXPORT` reports `PASS`, `row_count=1`, and reconciliation `DONE`.
- `operator_summary.current_step` advances to `MANUAL_EXECUTION_TEMPLATE`.

OPER9-11 then found that downstream Manual Execution and Manual Review live-read queries still return HTTP 400 warnings. Those warnings are not simple "no row yet" states; they are Notion API validation failures.

## 3. Validation Scope

The audit covered:

- Manual Executions data source retrieval
- Manual Reviews data source retrieval
- Required logical property mapping and property types
- Minimal query filter tests:
  - no filter
  - date-only filter
  - account-only select filter
  - account-only rich_text filter
  - date + account select filter
  - date + account rich_text filter
- Comparison against importer/exporter/sync/live-read paths in:
  - `core/notion_mapping.py`
  - `core/paper_daily_ops_notion_status.py`
  - `core/notion_manual_execution_importer.py`
  - `core/notion_manual_review_importer.py`
  - `core/notion_exporters.py`
  - `scripts/import_notion_executions.py`
  - `scripts/import_notion_reviews.py`
  - `scripts/sync_notion_execution_status.py`
  - `scripts/sync_notion_review_status.py`

## 4. Validation Results

| Target | Check | Result | Risk | Evidence | Recommendation |
|---|---|---:|---|---|---|
| Manual Executions | Data source retrieve | PASS | LOW | Retrieve succeeded against the configured redacted data source; property count was 20. | Data source ID and endpoint are valid for read-only access. |
| Manual Executions | Required properties | PASS | LOW | `execution_date`, `account_id`, `status`, `import_status`, `actual_price`, and `external_key` all resolved. Types were date, select, select, select, number, and rich_text. | No mapping/config correction needed for these checked keys. |
| Manual Executions | No-filter query | PASS | LOW | Query succeeded; row count was 10. | Data source query endpoint works. |
| Manual Executions | `execution_date` filter | PASS | LOW | Date-only query succeeded; row count was 8. | Date property mapping and date filter construction are valid. |
| Manual Executions | `account_id` select filter | FAIL | MEDIUM | HTTP 400: the smoke account value is not present as an `Account ID` select option. Existing options include `paper_default` and another pilot account, but not the smoke account. | Add/preseed the smoke account select option or allow the approved template export to create/use it, then rerun live-read. |
| Manual Executions | `execution_date` + `account_id` select filter | FAIL | MEDIUM | Same HTTP 400 as account-only select filtering. | The combined live-read query fails because the account select value is invalid for the current Notion schema state. |
| Manual Executions | `account_id` rich_text filter | FAIL | LOW | HTTP 400: property type mismatch because `Account ID` is a select property, not text. | Expected failure; live-read should continue treating `account_id` as select. |
| Manual Reviews | Data source retrieve | PASS | LOW | Retrieve succeeded against the configured redacted data source; property count was 18. | Data source ID and endpoint are valid for read-only access. |
| Manual Reviews | Required properties | PASS | LOW | `review_date`, `account_id`, `review_status`, `import_status`, `external_key`, `reviewer_note`, `review_tag`, and `follow_up_needed` all resolved. Types were date, select, select, select, rich_text, rich_text, multi_select, and select. | No mapping/config correction needed for these checked keys. |
| Manual Reviews | No-filter query | PASS | LOW | Query succeeded; row count was 22. | Data source query endpoint works. |
| Manual Reviews | `review_date` filter | PASS | LOW | Date-only query succeeded; row count was 12. | Date property mapping and date filter construction are valid. |
| Manual Reviews | `account_id` select filter | FAIL | MEDIUM | HTTP 400: the smoke account value is not present as an `Account ID` select option. Existing options include `paper_default` and another pilot account, but not the smoke account. | Add/preseed the smoke account select option or allow the approved template export to create/use it, then rerun live-read. |
| Manual Reviews | `review_date` + `account_id` select filter | FAIL | MEDIUM | Same HTTP 400 as account-only select filtering. | The combined live-read query fails because the account select value is invalid for the current Notion schema state. |
| Manual Reviews | `account_id` rich_text filter | FAIL | LOW | HTTP 400: property type mismatch because `Account ID` is a select property, not text. | Expected failure; live-read should continue treating `account_id` as select. |

## 5. HTTP 400 Cause Assessment

| Candidate | Assessment | Rationale |
|---|---|---|
| Data source ID mismatch | Unlikely / ruled out | Data source retrieve, no-filter query, and date-only query all succeeded for both targets. |
| Property mapping mismatch | Unlikely for checked keys | Required logical keys resolved to the expected Notion property names and types. |
| Property type mismatch | Not the primary cause | The expected live-read path uses select filtering for `account_id`, matching the actual property type. The rich_text probe failed as expected. |
| Endpoint mismatch | Ruled out | Retrieve and query calls work before adding the account select filter. |
| Date filter construction issue | Ruled out | Date-only filters passed for both Manual Executions and Manual Reviews. |
| Account filter construction issue | Partially confirmed | The filter shape matches the select property, but the selected smoke account value is not an existing select option. |
| Example mapping drift | Not shown for checked keys | The checked logical keys align with the current data source schemas. |
| Notion API version / data source vs database concept mismatch | Unlikely | The same read path can retrieve and query both target data sources. |

The minimum failing condition is the `account_id` select filter for the smoke account. Notion rejects select filters that reference an option name that does not exist in the target data source.

## 6. Follow-up Fix Need

No code fix is required to explain the current HTTP 400 warning. The immediate mismatch is Notion schema state: the Manual Executions and Manual Reviews `Account ID` select options do not include the smoke account.

Recommended follow-up options:

1. Preseed the smoke account value in the `Account ID` select options for Manual Executions and Manual Reviews.
2. Continue the smoke through an explicitly approved `MANUAL_EXECUTION_TEMPLATE` export, then rerun read-only status to confirm whether the export path creates/uses the missing select option.
3. Consider a later Orchestrator live-read hardening task that handles a missing account select option as a structured warning instead of a raw HTTP 400 warning.
4. Consider an external-key or date-only fallback only if it can preserve the local source-of-truth and account isolation rules.

Mapping/config correction is not required for the checked fields. Env values are sufficiently valid for retrieving and querying the target data sources.

## 7. Smoke Resume Judgment

The smoke account can continue to `MANUAL_EXECUTION_TEMPLATE` with the normal manual-approval boundary for Notion writes. The warning means Manual Execution / Manual Review account-filtered live-read is not reliable for this smoke account until the `Account ID` select option exists in those data sources.

Current reliable live-read stage:

- Daily Plan / Daily Plan Notion export

Current warning-limited live-read stages:

- Manual Execution template / preview / status sync
- Manual Review template / preview / status sync

After the approved template export path runs for the smoke account, rerun:

```cmd
python scripts\paper_daily_ops.py status --account-id paper_orch_smoke_202606 --data-date 2026-06-05 --trade-date 2026-06-08 --json --include-notion-read
```

Expected confirmation would be that Manual Execution account-filtered live-read no longer returns HTTP 400 for the smoke account.

## 8. Security Notes

- Notion token values were not printed into this document.
- Data source IDs, database IDs, page IDs, and private row contents were not documented.
- Query evidence is summarized only as redacted schema/type metadata, row counts, and sanitized failure cause.
- Generated validation output remains outside the committed document set.

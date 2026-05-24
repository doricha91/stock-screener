# MFU-PAPER14-3D Actual Notion Export Verification

## Scope

이번 PAPER14-3-closeout은 Weekly / Benchmark / Account Snapshot Notion export 검증 결과와 Notion UI 표시 설정을 문서화하는 작업이며, page body 개선, 추가 export 구현, 실제 Notion write는 포함하지 않는다.

This document records the PAPER14-3D verification outcome for actual Notion export only.

Included targets:

- `weekly_reports`
- `benchmark_reports`
- `account_snapshots`

Excluded:

- Daily Plan export
- Daily Review Summary export
- Performance Summary export
- Manual Review input integration
- page body improvement
- additional exporter implementation

## Verification Date

- Verification thread date: `2026-05-24`

## Data Sources

- Weekly Reports: `3696806c-e0e1-80b1-b8fb-000bcf1d3458`
- Benchmark Reports: `3696806c-e0e1-807e-9faf-000b3a93d2db`
- Account Snapshots: `3696806c-e0e1-8010-a375-000bdfde16db`

## Pre-check Result

### Schema validation

- Result: `PASS`
- Command: `python scripts/dev/validate_notion_schema.py --all --json`

### Dry-run export

- Weekly dry-run: success
- Benchmark dry-run: success
- Account snapshot dry-run: success

Expected external keys matched the generated payload:

- `weekly_report:2026-05-09:2026-05-20`
- `benchmark:2026-05-20:exploratory`
- `account_snapshot:2026-05-20`

## First Actual Export

### Weekly Reports

- External Key: `weekly_report:2026-05-09:2026-05-20`
- Action: `created`
- Page ID: `36a6806c-e0e1-8127-bd8d-dc6a6e59120c`

### Benchmark Reports

- External Key: `benchmark:2026-05-20:exploratory`
- Action: `created`
- Page ID: `36a6806c-e0e1-8118-9723-f022bfe59429`

### Account Snapshots

- External Key: `account_snapshot:2026-05-20`
- Action: `created`
- Page ID: `36a6806c-e0e1-814c-ac90-d0684e085fd1`

## Second Actual Export

### Weekly Reports

- External Key: `weekly_report:2026-05-09:2026-05-20`
- Action: `updated`
- Page ID: `36a6806c-e0e1-8127-bd8d-dc6a6e59120c`

### Benchmark Reports

- External Key: `benchmark:2026-05-20:exploratory`
- Action: `updated`
- Page ID: `36a6806c-e0e1-8118-9723-f022bfe59429`

### Account Snapshots

- External Key: `account_snapshot:2026-05-20`
- Action: `updated`
- Page ID: `36a6806c-e0e1-814c-ac90-d0684e085fd1`

## External Key Summary

| Target | External Key | First run | Second run |
| --- | --- | --- | --- |
| Weekly Reports | `weekly_report:2026-05-09:2026-05-20` | `created` | `updated` |
| Benchmark Reports | `benchmark:2026-05-20:exploratory` | `created` | `updated` |
| Account Snapshots | `account_snapshot:2026-05-20` | `created` | `updated` |

## Why duplicate rows were considered absent

- The second execution returned `updated` for all three targets.
- The `page_id` remained the same between the first and second execution for each target.
- That is consistent with External Key based upsert rather than duplicate page creation.

## Notion UI confirmation

User-confirmed items:

- Each target DB showed the exported row.
- Major properties were visible in the Notion UI.
- Ratio / return / drawdown fields were sent as raw decimal values and displayed correctly after Notion percent formatting.
- Example confirmed in UI: `0.6044888 -> 60.44888%`

## Remaining Risks

- This verification did not improve page body rendering.
- Full markdown-to-block conversion is still out of scope.
- Future schema changes in Notion UI must continue to respect the exporter contract in PAPER14-3B / 3C.

## Conclusion

- Schema validation passed.
- Dry-run passed.
- First actual export created the rows.
- Second actual export updated the same rows.
- PAPER14-3 External Key upsert behavior was verified for the three supported data sources.

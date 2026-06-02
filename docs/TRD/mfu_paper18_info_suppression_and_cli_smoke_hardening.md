# MFU PAPER18-3 INFO Suppression and CLI Smoke Hardening

## 1. Purpose

PAPER18-3 hardens the PAPER18 Alert Report generator so the Markdown report stays focused on exceptions and risk conditions.

The goal is to preserve all INFO AlertItems in JSON while reducing Markdown INFO output to counts and suppression reasons. This prevents the Alert Report from becoming a duplicate Daily Ops Status Dashboard.

## 2. Scope

This MFU covers:

- INFO suppression metadata in AlertItem output.
- Markdown rendering changes for INFO items.
- `actual_intent` behavior for expected page id warnings.
- fixture-based CLI smoke coverage using a temporary output directory.
- documentation of the new behavior.

This MFU does not call Notion API, run Notion write/export/sync, execute Telegram/Slack/Email delivery, or modify paper ledger artifacts.

## 3. INFO Suppression Policy

JSON preserves INFO items in full.

Markdown suppresses INFO detail by default:

- no INFO title expansion,
- no INFO message expansion,
- no INFO recommended action expansion,
- count-only summary,
- suppression reason summary.

Suppression fields:

```json
{
  "suppressed_in_markdown": true,
  "suppression_reason": "actual_intent=false"
}
```

Current suppression reasons:

- `actual_intent=false`
- `non_actual_warning`
- `preflight_pass_info`

## 4. actual_intent Policy

`actual_intent=false`:

- expected page id missing warning remains `INFO`.
- the INFO item is preserved in JSON.
- Markdown suppresses the detailed INFO item.
- `suppression_reason=actual_intent=false`.

`actual_intent=true`:

- expected page id missing or preflight WARNING becomes `NEEDS_REVIEW`.
- the item is not suppressed in Markdown.
- operator confirmation remains required before any actual export approval.

## 5. Markdown Behavior

Expanded sections:

- `BLOCKING`
- `NEEDS_REVIEW`
- `SYNC_FAILED`

Suppressed summary section:

```text
## Info / Suppressed Summary
- INFO: n
- Suppressed INFO: n
- INFO details are preserved in JSON.
- Suppression reason `actual_intent=false`: n
```

The Markdown report must not list normal states or become a dashboard-style status board.

## 6. JSON Preservation Policy

JSON report keeps every AlertItem, including INFO items.

This allows downstream delivery adapters, future filtering, or local audit tools to inspect the full event set without forcing the operator-facing Markdown report to expand low-severity details.

## 7. CLI Smoke Test Hardening

The test suite now includes a fixture-based CLI smoke test:

- creates a temporary preflight JSON fixture,
- calls `generate_paper_alert_report.py` through its `main()` function,
- uses `tmp_path` as `--output-dir`,
- confirms JSON report creation,
- confirms Markdown report creation,
- confirms no `outputs/paper_accounts` output path is used,
- confirms `delivery_executed=false`,
- confirms `notion_api_called=false`,
- confirms `notion_write_export_sync_executed=false`.

The smoke test does not call Notion API.

## 8. Test Coverage

Additional coverage:

- `actual_intent=false` + expected page id missing -> `INFO` + `suppressed_in_markdown=true`.
- `actual_intent=true` + expected page id missing -> `NEEDS_REVIEW` + `suppressed_in_markdown=false`.
- JSON preserves suppressed INFO items.
- Markdown does not expand suppressed INFO title/message/action.
- Markdown reports suppressed INFO count.
- BLOCKING / NEEDS_REVIEW / SYNC_FAILED details remain visible in Markdown.
- fixture-based CLI smoke writes only to `tmp_path`.

## 9. Limitations

- INFO suppression is global for Markdown in the current renderer.
- There is no CLI option yet to expand INFO details in Markdown.
- Delivery adapters are still future work.
- Alert sources remain limited to Daily Ops Status and PAPER17 Daily Ops actual preflight payloads.
- Manual Execution/Review, freshness, schema/view drift, replay/diff, and data quality alerts are not connected yet.

## 10. PAPER18-4 Recommendation

Recommended next MFU:

- add an optional Markdown `--include-info-details` mode if operators need full local text reports,
- add Daily Ops Status payload fixture coverage beyond preflight-only smoke,
- define delivery adapter interface without sending external messages,
- evaluate adding Manual Execution/Review and freshness sources after the closeout report remains stable.

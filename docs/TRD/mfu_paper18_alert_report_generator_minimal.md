# MFU PAPER18-2 Alert Report Generator Minimal

## 1. Purpose

PAPER18-2 implements the first local Paper Ops Exception Report generator.

The alert report is not a duplicate of the Daily Ops Status Dashboard. The dashboard remains the operational progress board, while this report only surfaces exceptions, risks, stop conditions, and limited informational summaries that an operator should not miss.

This MFU is read-only report generation. It does not run Notion write/export/sync, Daily Ops Status actual export, Telegram/Slack/Email delivery, paper commit/append/status sync, or paper ledger mutation.

## 2. Scope

Initial scope is intentionally narrow:

- account: `paper_sandbox`
- phase: `closeout`
- input source: Daily Ops Status payload JSON
- input source: PAPER17 Daily Ops Status actual preflight payload JSON
- output: local JSON and Markdown report
- delivery: no external delivery adapter is executed

The generator can build a report from dictionary payloads in core code or from JSON files through the CLI.

## 3. CLI

Command shape:

```cmd
python scripts\dev\generate_paper_alert_report.py --account-id paper_sandbox --date 2026-05-20 --phase closeout --daily-ops-status-json <path> --preflight-json <path> --output-dir <path> --json
```

Supported options:

- `--account-id`: required paper account id.
- `--date`: required report date, `YYYY-MM-DD` or `YYYYMMDD`.
- `--phase`: currently only `closeout`.
- `--actual-intent`: escalates preflight warnings because an operator intends actual export.
- `--daily-ops-status-json`: optional Daily Ops Status payload file.
- `--preflight-json`: optional PAPER17 preflight payload file.
- `--output-dir`: optional output directory; tests and smoke runs should use this to avoid operational output contamination.
- `--json`: prints a machine-readable generation summary.

## 4. Input Contract

The generator accepts two optional JSON object inputs.

Daily Ops Status input should include fields such as:

- `account_id`
- `status_date`
- `workflow_status`
- `sync_status`
- `blocking_reason`

PAPER17 preflight input should include fields such as:

- `account_id`
- `status_date`
- `external_key`
- `overall_status`
- `schema_validation_result`
- `duplicate_audit.classification`
- `checks`
- `recommended_action`
- `write_executed`

Missing optional inputs do not trigger Notion reads. The generator only evaluates payloads already supplied by the operator or upstream local tools.

## 5. AlertItem Schema

Each item uses schema version `paper_alert_report.v1`.

```json
{
  "schema_version": "paper_alert_report.v1",
  "severity": "NEEDS_REVIEW",
  "category": "DAILY_OPS_PREFLIGHT",
  "account_id": "paper_sandbox",
  "status_date": "2026-05-20",
  "title": "Daily Ops actual preflight returned WARNING",
  "message": "Operator confirmation is required before any actual export.",
  "recommended_action": "Confirm expected_page_id and preflight evidence before requesting actual export approval.",
  "evidence": {},
  "source": "daily_ops_actual_preflight",
  "source_path": "<redacted_path>",
  "external_safe": true,
  "sendable": false,
  "redacted": true
}
```

Report envelope:

```json
{
  "schema_version": "paper_alert_report.v1",
  "account_id": "paper_sandbox",
  "report_date": "2026-05-20",
  "phase": "closeout",
  "actual_intent": false,
  "summary": {
    "blocking_count": 0,
    "needs_review_count": 0,
    "sync_failed_count": 0,
    "info_count": 1
  },
  "items": []
}
```

## 6. Severity Mapping

Current severities:

- `BLOCKING`
- `NEEDS_REVIEW`
- `SYNC_FAILED`
- `INFO`

Initial mapping:

| Condition | Severity | Notes |
| --- | --- | --- |
| preflight `overall_status=FAIL` | `BLOCKING` | Actual export must not run. |
| preflight `schema_validation_result=FAIL` | `BLOCKING` | Schema/property mismatch blocks actual. |
| duplicate audit `classification=duplicate_blocker` | `BLOCKING` | Multiple matching External Key rows block actual. |
| account mismatch between input and requested account | `BLOCKING` | Operator must stop and inspect the source payload. |
| preflight `overall_status=WARNING` and `actual_intent=true` | `NEEDS_REVIEW` | Operator confirmation required. |
| expected page id warning and `actual_intent=false` | `INFO` | Informational because no actual export is intended. |
| duplicate audit `classification=update_candidate` and `actual_intent=false` | `INFO` | One matching row exists; no action without actual intent. |
| Daily Ops Status sync failure | `SYNC_FAILED` | Do not rollback local source-of-truth. |

Normal completed states are not expanded into a full status board.

## 7. actual_intent Policy

`actual_intent=false`:

- expected page id warnings are not promoted to strong alerts.
- update candidates remain `INFO`.
- preflight PASS can be summarized as `INFO`.

`actual_intent=true`:

- preflight WARNING becomes `NEEDS_REVIEW`.
- missing expected page id requires operator confirmation.
- duplicate blocker, schema FAIL, account mismatch, and preflight FAIL remain `BLOCKING`.

Actual export remains outside PAPER18-2 and still requires separate explicit approval.

## 8. Output Path Policy

Default account-based output path:

```text
outputs/paper_accounts/{account_id}/alerts/paper_alert_report_{YYYYMMDD}.json
outputs/paper_accounts/{account_id}/alerts/paper_alert_report_{YYYYMMDD}.md
```

Tests and local smoke runs should pass `--output-dir` and use a temporary directory. This avoids changing operational `outputs/paper_accounts` during validation.

## 9. Markdown Report Format

Markdown output uses this structure:

```text
# Paper Ops Exception Report - {account_id} - {date}

## Summary
## Blocking
## Needs Review
## Sync Failed
## Info / Suppressed Summary
## Source Inputs
## Redaction Notes
```

The Markdown report prioritizes exception readability. INFO is summarized and does not become a dashboard replacement.

## 10. Redaction Policy

Always redact:

- Notion token
- Notion data source id
- full Notion page_id
- absolute local path
- secret/env values

Allowed values:

- account id
- status date
- severity
- category
- duplicate classification
- schema validation result
- recommended action

Page ids and data source ids are masked as `****last4`. Absolute paths are replaced with `<redacted_path>`.

## 11. Test Coverage

PAPER18-2 test coverage includes:

- preflight FAIL to `BLOCKING`
- duplicate blocker to `BLOCKING`
- `actual_intent=true` WARNING to `NEEDS_REVIEW`
- `actual_intent=false` expected page id warning to `INFO`
- update candidate to `INFO`
- summary count calculation
- report schema version
- Markdown rendering
- account output filename policy through a temporary output directory
- sensitive value redaction
- no delivery adapter execution

Tests do not call Notion API.

## 12. Limitations

- Only `closeout` phase is supported.
- Initial source coverage is limited to Daily Ops Status and PAPER17 actual preflight payloads.
- Manual Execution/Review status sync, data freshness, same-date diff, schema/view drift, and replay/diff are not connected yet.
- Telegram/Slack/Email delivery is not implemented.
- Actual export approval is not implemented and is not implied by this report.
- The default operational output path exists, but validation should use `--output-dir` to avoid output contamination.

## 13. PAPER18-3 Recommendation

Recommended next MFU:

- add fixture-based CLI smoke for JSON and Markdown generation,
- decide whether INFO items should be suppressed by default in operator-facing Markdown,
- add Daily Ops Status payload fixture coverage,
- prepare delivery adapter boundary without enabling external delivery,
- evaluate additional alert sources after closeout report behavior is stable.

# PAPER18-1 Alert / Monitoring Signal Inventory and Delivery-ready Report Schema

## 1. Purpose

PAPER18-1 defines the first Alert / Monitoring Report design for paper operations.

The report is a Paper Ops Exception Report. It highlights exceptions, risks, blocking conditions, and operator review items that should not be missed. It is not a duplicate of the Daily Ops Status Dashboard.

This is design-only work. It does not implement code, Notion write/export/sync, Telegram delivery, or outputs/paper ledger changes.

## 2. Non-overlap with Daily Ops Status Dashboard

Role split:

```text
Daily Ops Status Dashboard = operational progress board
Alert / Monitoring Report = exception / risk / stop-condition report
```

Daily Ops Status should show where each account/date is in the workflow.

Alert Report should show only items that require attention, review, or stopping action. Normal completed states should be hidden by default or summarized as INFO counts only.

## 3. User Decisions

Confirmed design decisions:

- Alert Report scope: exceptions and risks only.
- Execution timing: design supports mid-loop and closeout phases, but initial implementation should target daily loop closeout.
- Severity values: `BLOCKING`, `NEEDS_REVIEW`, `SYNC_FAILED`, `INFO`.
- Initial alert sources: Daily Ops Status and PAPER17 Daily Ops Status actual preflight.
- actual preflight WARNING escalation depends on `actual_intent`.
- Output format: JSON and Markdown.
- Output partitioning: account-based.
- Telegram or other external delivery is deferred.
- Sensitive information must be redacted.

## 4. Initial Scope

Initial scope:

- Generate a delivery-ready JSON/Markdown report schema.
- Use Daily Ops Status and PAPER17 actual preflight as initial sources.
- Define severity mapping and actual_intent escalation rules.
- Define account-scoped output paths.
- Define redaction policy for future delivery adapters.

Non-goal:

- Listing all normal states.
- Replacing Daily Ops Status views.
- Running actual export.
- Sending alerts externally.

## 5. Alert Sources

Initial sources:

| Source | Purpose | Initial use |
| --- | --- | --- |
| Daily Ops Status | Workflow and review state summary | Surface blocking workflow states, sync failures, missing artifacts |
| PAPER17 Daily Ops Status actual preflight | Actual-export readiness preflight | Surface FAIL/WARNING conditions before intended actual export |

Future sources only:

- Manual Execution preview / commit / status sync.
- Manual Review preview / append / status sync.
- data freshness.
- same-date commit guard.
- Daily Review Summary.
- schema/view drift.
- replay/diff.

## 6. Severity Policy

Severity values:

```text
BLOCKING
NEEDS_REVIEW
SYNC_FAILED
INFO
```

Initial classification:

| Severity | Examples | Operator meaning |
| --- | --- | --- |
| `BLOCKING` | preflight FAIL, schema validation FAIL, `duplicate_blocker`, account_id mismatch, source-of-truth artifact missing/corrupt | Stop actual/export/commit path until resolved |
| `NEEDS_REVIEW` | `actual_intent=true` with preflight WARNING, expected_page_id missing before intended actual, operator confirmation required | Human review needed before proceeding |
| `SYNC_FAILED` | local source-of-truth commit/append succeeded but Notion sync/export failed | Do not rollback local source-of-truth; retry presentation sync/export only |
| `INFO` | `update_candidate`, preflight PASS, `actual_intent=false` expected_page_id warning | Informational or suppressed-by-default condition |

## 7. AlertItem JSON Schema

Alert report envelope:

```json
{
  "schema_version": "paper_alert_report.v1",
  "account_id": "paper_sandbox",
  "report_date": "2026-05-20",
  "phase": "closeout",
  "actual_intent": false,
  "generated_at": "2026-06-02T00:00:00+09:00",
  "summary": {
    "blocking_count": 0,
    "needs_review_count": 1,
    "sync_failed_count": 0,
    "info_count": 2
  },
  "items": []
}
```

AlertItem schema:

```json
{
  "schema_version": "paper_alert_report.v1",
  "severity": "NEEDS_REVIEW",
  "category": "DAILY_OPS_PREFLIGHT",
  "account_id": "paper_sandbox",
  "status_date": "2026-05-20",
  "title": "Daily Ops actual preflight returned WARNING",
  "message": "expected_page_id was not provided.",
  "recommended_action": "Confirm page_id only if actual export is intended.",
  "evidence": {
    "overall_status": "WARNING",
    "duplicate_classification": "update_candidate",
    "schema_validation_result": "PASS"
  },
  "source": "daily_ops_actual_preflight",
  "source_path": "outputs/paper_accounts/paper_sandbox/alerts/...",
  "external_safe": true,
  "sendable": false,
  "redacted": true
}
```

Field notes:

- `severity`: one of `BLOCKING`, `NEEDS_REVIEW`, `SYNC_FAILED`, `INFO`.
- `category`: stable machine-readable category such as `DAILY_OPS_STATUS`, `DAILY_OPS_PREFLIGHT`, `NOTION_SYNC`.
- `evidence`: must be redacted before external delivery.
- `external_safe`: whether the item can be sent outside the local machine.
- `sendable`: whether a future delivery adapter should send it by default.
- `redacted`: true when sensitive values have been masked.

## 8. Markdown Report Structure

Markdown report structure:

```text
# Paper Ops Exception Report - {account_id} - {report_date}

## Summary
- BLOCKING: n
- NEEDS_REVIEW: n
- SYNC_FAILED: n
- INFO: n

## Blocking
...

## Needs Review
...

## Sync Failed
...

## Info / Suppressed Summary
...

## Source Inputs
...

## Redaction Notes
...
```

Normal completed items should not be expanded by default. INFO may be summarized unless the operator requests verbose output.

## 9. Account-based Output Path Policy

For non-default accounts, use the existing account-aware root convention:

```text
outputs/paper_accounts/{account_id}/alerts/paper_alert_report_{YYYYMMDD}.json
outputs/paper_accounts/{account_id}/alerts/paper_alert_report_{YYYYMMDD}.md
```

Example:

```text
outputs/paper_accounts/paper_sandbox/alerts/paper_alert_report_20260520.json
outputs/paper_accounts/paper_sandbox/alerts/paper_alert_report_20260520.md
```

`paper_default` continues to follow legacy path policy until a future migration/convergence MFU changes it. PAPER18-1 does not define paper_default actual alert writes.

## 10. actual_intent Policy

`actual_intent=false`:

- expected_page_id missing WARNING should not be escalated to a strong alert.
- It can be `INFO` or suppressed.
- preflight `update_candidate` is informational.

`actual_intent=true`:

- expected_page_id missing becomes `NEEDS_REVIEW`.
- preflight WARNING becomes `NEEDS_REVIEW`.
- duplicate blocker becomes `BLOCKING`.
- schema validation FAIL becomes `BLOCKING`.
- account mismatch becomes `BLOCKING`.

Actual export is not part of PAPER18-1 and remains forbidden until a separate explicit approval step.

## 11. Redaction / Secret Safety Policy

Always redact:

- Notion token.
- Notion data source id.
- full Notion page_id.
- absolute local paths.
- secret/env values.

Allowed to show:

- account_id.
- status_date.
- severity.
- category.
- duplicate classification.
- schema validation result.
- recommended_action.

Masking examples:

- data_source_id -> `****784b`
- page_id -> `****4292`
- absolute path -> repo-relative path or `<redacted_path>`

## 12. Delivery Adapter Boundary

PAPER18-1 does not implement Telegram, Slack, Email, or any external delivery.

Boundary:

```text
Alert Engine -> JSON/Markdown Report
Delivery Adapter -> future reader/sender for Telegram/Slack/Email
```

Delivery failure is not source-of-truth failure. It must not trigger local ledger rollback.

## 13. Timing / Phase Policy

Initial implementation phase:

```text
closeout
```

Future phases:

```text
checkpoint
pre-actual
```

Phase-aware rule:

- closeout can treat missing end-of-day artifacts as stronger alerts.
- checkpoint must avoid false positives for steps that are not expected to be complete yet.
- pre-actual focuses on actual export blockers: schema, duplicate, External Key, account scope, expected_page_id, and explicit approval readiness.

## 14. False Positive / False Negative Risks

False positive risks:

- checkpoint phase reporting expected incomplete work as missing.
- expected_page_id missing becoming noisy when `actual_intent=false`.
- INFO items expanded too aggressively and duplicating the dashboard.

False negative risks:

- sync failure hidden because local source-of-truth succeeded.
- duplicate row risk missed when duplicate audit is not run.
- schema/view drift not included in initial sources.
- stale page_id not detectable without expected_page_id.

Mitigation:

- keep initial implementation closeout-focused.
- require `actual_intent` as an explicit input.
- keep future source expansion incremental.
- do not send external notifications until redaction and delivery policies are tested.

## 15. Non-scope

PAPER18-1 does not include:

- Python code implementation.
- Alert report CLI implementation.
- Telegram / Slack / Email delivery.
- Notion actual write/export/sync.
- Daily Ops Status actual export.
- outputs/paper ledger changes.
- schema/view drift implementation.
- replay/diff implementation.
- duplicate cleanup.
- paper_default actual allow.
- multi-account bulk actual allow.

## 16. PAPER18-2 Recommendation

PAPER18-2 should implement the local Alert Report generator for `paper_sandbox` closeout only.

Recommended scope:

- read Daily Ops Status status/preflight JSON inputs or fixture payloads.
- produce account-scoped JSON and Markdown reports.
- implement severity mapping and actual_intent policy.
- keep Telegram/external delivery out of scope.
- use tmp_path tests for output paths.

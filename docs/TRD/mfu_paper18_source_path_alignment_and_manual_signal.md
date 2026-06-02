# MFU PAPER18-5 Source Path Alignment and Manual Signal

## 1. Purpose

PAPER18-5 extends the Alert Report generator with minimal source path alignment documentation and high-level Manual Execution / Manual Review alert signals.

This remains a read-only alert source expansion. It does not call Notion API, run Notion write/export/sync, run commit/append/status sync, send external delivery, or mutate paper ledger artifacts.

## 2. Scope

Implemented:

- Manual Execution high-level source input.
- Manual Review high-level source input.
- explicit JSON options for manual sources.
- narrow `--source-root` candidate resolution for manual sources.
- high-level status mapping only.
- duplicate alert avoidance for Daily Ops review pending vs Manual Review pending.

Not implemented:

- Manual Execution / Manual Review row-level analysis.
- producer-side source generation.
- Notion status sync.
- data freshness, schema/view drift, replay/diff sources.

## 3. Source Path Alignment Table

| Source | Current/Expected Filename | Producer Command | Alert Use | Status |
| --- | --- | --- | --- | --- |
| Daily Ops Status | `daily_ops_status_{YYYYMMDD}.json`, `daily_ops_status.json` | Daily Ops Status dry-run/actual/preflight tooling | workflow, review, sync exception source | current alert input; producer handoff still needs contract |
| PAPER17 actual preflight | `daily_ops_actual_preflight_{YYYYMMDD}.json`, `preflight_daily_ops_status_actual_{YYYYMMDD}.json`, `preflight.json` | `scripts/dev/preflight_daily_ops_status_actual.py` | actual readiness warning/fail source | current alert input |
| Manual Execution preview/commit/status | `manual_execution_{YYYYMMDD}.json`, `manual_execution_status_{YYYYMMDD}.json`, `manual_execution_import_commit_{YYYYMMDD}.json`, `manual_execution.json` | `import_notion_executions.py`, `sync_notion_execution_status.py` reports or future summary writer | high-level preview/commit/pending/sync signal | candidate / needs upstream contract |
| Manual Review preview/append/status | `manual_review_{YYYYMMDD}.json`, `manual_review_status_{YYYYMMDD}.json`, `manual_review_append_{YYYYMMDD}.json`, `manual_review.json` | `import_notion_reviews.py`, `append_paper_manual_review_log.py`, `sync_notion_review_status.py` reports or future summary writer | high-level validation/append/pending/sync signal | candidate / needs upstream contract |

Explicit JSON input remains the official fallback and takes precedence over `--source-root`.

## 4. Manual Execution High-level Signal Mapping

| Signal | Severity | Notes |
| --- | --- | --- |
| `execution_preview_result=FAIL` or `FAILED` | `BLOCKING` | Preview failure blocks commit/sync decisions. |
| `execution_preview_result=WARNING` | `NEEDS_REVIEW` | Operator review required. |
| `execution_commit_status=MISSING` or `NOT_COMMITTED` | `NEEDS_REVIEW` | Closeout should confirm whether commit is required. |
| `execution_sync_status=FAILED` or `SYNC_FAILED` | `SYNC_FAILED` | Do not rollback local source-of-truth. |
| `execution_pending_row_count > 0` | `NEEDS_REVIEW` | Pending execution rows remain. |
| account mismatch | `BLOCKING` | Source account differs from requested account. |

The generator does not inspect individual execution rows.

## 5. Manual Review High-level Signal Mapping

| Signal | Severity | Notes |
| --- | --- | --- |
| `review_validation_result=FAIL` or `FAILED` | `BLOCKING` | Review validation blocks closeout. |
| `review_append_status=MISSING` or `NOT_APPENDED` | `NEEDS_REVIEW` | Append/closeout is incomplete. |
| `review_sync_status=FAILED` or `SYNC_FAILED` | `SYNC_FAILED` | Do not rollback local source-of-truth. |
| `review_pending_row_count > 0` | `NEEDS_REVIEW` | Pending review rows remain. |
| `review_progress_status=PARTIAL`, `NOT_STARTED`, `READY`, or `UNKNOWN` | `NEEDS_REVIEW` | Review progress is incomplete. |
| account mismatch | `BLOCKING` | Source account differs from requested account. |

If Daily Ops Status already emits the review pending/incomplete alert, Manual Review pending/progress is suppressed to avoid duplicate alerts. Manual Review validation failure and sync failure are still emitted because they represent distinct risks.

## 6. Missing / Malformed Source Policy

Malformed manual source:

- `BLOCKING`
- source exists but cannot be parsed or is not a JSON object.

Missing manual source:

- treated as suppressed `INFO` unless the source is explicitly required by future producer contracts.
- not promoted to `BLOCKING` in PAPER18-5 because producer handoff is still candidate / needs upstream contract.

Existing Daily Ops Status and preflight missing/malformed policies remain unchanged.

## 7. CLI Changes

New explicit source options:

```cmd
--manual-execution-json <path>
--manual-review-json <path>
```

Existing options remain:

```cmd
--account-id
--date
--phase closeout
--actual-intent
--daily-ops-status-json
--preflight-json
--source-root
--output-dir
--json
```

Explicit JSON options take precedence over `--source-root` candidates.

## 8. Duplicate Alert Avoidance

Daily Ops Status can already represent review pending/incomplete through `review_progress_status` and `review_pending_row_count`.

To avoid duplicate operator noise:

- Daily Ops review pending/incomplete emits one `Daily Ops review is incomplete` alert.
- Manual Review pending/progress does not emit a duplicate `Manual Review is incomplete` alert when the Daily Ops review alert exists.
- Manual Review validation failure and sync failure are not suppressed.

## 9. Read-only Safety Policy

The generator:

- reads local JSON files only,
- writes JSON/Markdown report files only,
- does not call Notion API,
- does not run Notion write/export/sync,
- does not run Telegram/Slack/Email delivery,
- does not run commit/append/status sync,
- does not mutate paper ledger artifacts.

## 10. Test Coverage

Added coverage:

- Manual Execution preview FAIL -> `BLOCKING`
- Manual Execution sync failed -> `SYNC_FAILED`
- Manual Execution pending rows -> `NEEDS_REVIEW`
- Manual Review validation FAIL -> `BLOCKING`
- Manual Review sync failed -> `SYNC_FAILED`
- Manual Review pending rows -> `NEEDS_REVIEW`
- Daily Ops review pending suppresses duplicate Manual Review pending alert
- malformed manual source -> alert generated
- explicit Manual Execution JSON overrides `--source-root`
- INFO suppression remains intact
- tmp_path output avoids operational outputs contamination

## 11. Limitations

- Manual source filenames are candidate contracts, not fully stabilized producer outputs.
- Manual Execution / Review row-level details are not analyzed.
- Missing manual sources remain low severity until upstream producer contracts are fixed.
- data freshness, schema/view drift, same-date guard, and replay/diff are not connected yet.

## 12. PAPER18-6 Recommendation

Recommended next MFU:

- formalize producer handoff contracts for Daily Ops Status and manual source summaries,
- add data freshness and same-date guard sources,
- add Manual Execution/Review row-level checks only after high-level summary contracts stabilize,
- keep external delivery disabled until alert noise level is validated.

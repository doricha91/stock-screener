# MFU PAPER18-4 Real Ops Alert Source Connection

## 1. Purpose

PAPER18-4 connects the Alert Report generator to real local operation sources while keeping the report read-only.

The Alert Report remains a Paper Ops Exception Report. It is not a duplicate Daily Ops Status Dashboard, and it does not list all normal states.

## 2. Scope

Implemented source scope:

- Daily Ops Status JSON payload.
- PAPER17 Daily Ops Status actual preflight JSON payload.
- Explicit JSON input paths.
- Optional `--source-root` account/date source resolution.
- Missing and malformed source handling.
- JSON and Markdown report generation.

Out of scope:

- Notion API calls.
- Notion write/export/sync.
- Telegram/Slack/Email delivery.
- paper commit/append/status sync.
- paper ledger mutation.

## 3. Source Inputs

Existing explicit inputs remain supported:

```cmd
python scripts\dev\generate_paper_alert_report.py --account-id paper_sandbox --date 2026-05-20 --phase closeout --daily-ops-status-json <path> --preflight-json <path> --output-dir <path> --json
```

PAPER18-4 adds optional source-root resolution:

```cmd
python scripts\dev\generate_paper_alert_report.py --account-id paper_sandbox --date 2026-05-20 --phase closeout --source-root <path> --output-dir <path> --json
```

Resolver candidates:

Daily Ops Status:

- `{source_root}/daily_ops_status_{YYYYMMDD}.json`
- `{source_root}/daily_ops_status.json`

Daily Ops actual preflight:

- `{source_root}/daily_ops_actual_preflight_{YYYYMMDD}.json`
- `{source_root}/preflight_daily_ops_status_actual_{YYYYMMDD}.json`
- `{source_root}/preflight.json`

The resolver is intentionally narrow. It does not scan arbitrary output trees.

## 4. Daily Ops Status Mapping

Initial Daily Ops Status alert mapping:

| Signal | Alert severity | Notes |
| --- | --- | --- |
| `sync_status=FAILED` or `SYNC_FAILED` | `SYNC_FAILED` | Local source-of-truth rollback is still forbidden. |
| `workflow_status=UNKNOWN_OR_INCOMPLETE` or `NO_PLAN` | `BLOCKING` | Closeout state is incomplete or missing. |
| `review_progress_status=PARTIAL`, `NOT_STARTED`, `READY`, or `UNKNOWN` | `NEEDS_REVIEW` | Review closeout is not complete. |
| `review_pending_row_count > 0` | `NEEDS_REVIEW` | Pending review rows remain. |
| `review_validation_result=FAIL` or `FAILED` | `BLOCKING` | Review validation blocks closeout. |
| account mismatch | `BLOCKING` | Payload account does not match requested account. |

Normal completed states are not expanded into AlertItems.

## 5. Preflight Mapping

Existing PAPER17 preflight mapping is preserved:

- `overall_status=FAIL` -> `BLOCKING`
- `schema_validation_result=FAIL` -> `BLOCKING`
- `duplicate_audit.classification=duplicate_blocker` -> `BLOCKING`
- account mismatch -> `BLOCKING`
- `actual_intent=true` + `overall_status=WARNING` -> `NEEDS_REVIEW`
- `actual_intent=false` + expected page id warning -> suppressed `INFO`
- `duplicate_audit.classification=update_candidate` + `actual_intent=false` -> suppressed `INFO`

Preflight PASS or WARNING does not approve actual export.

## 6. Missing / Malformed Source Policy

Source handling policy:

| Source condition | Alert severity | Notes |
| --- | --- | --- |
| Daily Ops Status missing at `closeout` | `NEEDS_REVIEW` | Operator should provide the source or explain why it is unavailable. |
| Preflight missing and `actual_intent=false` | suppressed `INFO` | No actual export intent, so this is not a strong alert. |
| Preflight missing and `actual_intent=true` | `NEEDS_REVIEW` | Preflight is required before actual export approval. |
| Any malformed JSON source | `BLOCKING` | Existing but unreadable source blocks reliable operator decisions. |

Missing sources are converted into alert source events. The generator does not attempt Notion export/sync or other recovery actions.

## 7. CLI

New option:

```text
--source-root <path>
```

Existing options are unchanged:

- `--account-id`
- `--date`
- `--phase closeout`
- `--actual-intent`
- `--daily-ops-status-json`
- `--preflight-json`
- `--output-dir`
- `--json`

Explicit JSON paths take precedence over `--source-root` resolution.

## 8. Output Path Policy

Default account-based output path remains:

```text
outputs/paper_accounts/{account_id}/alerts/paper_alert_report_{YYYYMMDD}.json
outputs/paper_accounts/{account_id}/alerts/paper_alert_report_{YYYYMMDD}.md
```

Tests and smoke checks must use `tmp_path` or `--output-dir` and must not write to operational account paths.

## 9. Read-only Safety Policy

The generator only reads local JSON files and writes local report files.

It does not:

- call Notion API,
- run Notion write/export/sync,
- call create/update/upsert APIs,
- send Telegram/Slack/Email,
- run commit/append/status sync,
- mutate paper ledger artifacts.

## 10. Test Coverage

Added or maintained coverage:

- Daily Ops Status sync failure -> `SYNC_FAILED`
- Daily Ops Status review partial/incomplete -> `NEEDS_REVIEW`
- Daily Ops Status missing source at closeout -> `NEEDS_REVIEW`
- malformed source -> `BLOCKING`
- preflight missing + `actual_intent=false` -> suppressed `INFO`
- preflight missing + `actual_intent=true` -> `NEEDS_REVIEW`
- source-root resolver with `tmp_path` fixtures
- JSON/Markdown generation
- INFO suppression preservation
- no Notion API flags in CLI smoke
- no delivery execution

## 11. Limitations

- Source-root resolution is intentionally narrow and does not discover arbitrary historical outputs.
- Daily Ops Status source file production remains a separate upstream concern.
- Manual Execution/Review detail sources are not connected.
- data freshness, schema/view drift, replay/diff, and same-date diff sources are not connected.
- There is no external delivery adapter.

## 12. PAPER18-5 Recommendation

Recommended next MFU:

- add Daily Ops Status source generation or export-artifact handoff contract,
- add Manual Execution/Review high-level source signals,
- add data freshness and same-date guard alert sources,
- keep external delivery disabled until report content stabilizes.

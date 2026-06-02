# PAPER18-6 Freshness and Same-date Guard Alert Sources

## 1. Purpose

PAPER18-6 connects two additional read-only alert sources to the Paper Ops Exception Report:

- data freshness status
- same-date commit guard status

The goal is to surface stale data and same-date writer guard risk without turning the Alert Report into a Daily Ops Status Dashboard clone. Normal completed status is not expanded as alert details.

## 2. Scope

This MFU extends the existing Alert Report generator only. It preserves the current Daily Ops Status, PAPER17 preflight, Manual Execution, and Manual Review mappings.

Included:

- explicit JSON input support for freshness and same-date guard sources
- narrow `--source-root` candidate lookup for the new sources
- AlertItem mapping for fail, stale, blocked, malformed, and missing-source signals
- JSON preservation and Markdown INFO suppression behavior
- tmp_path-based tests with no real outputs pollution

Excluded:

- freshness producer implementation
- same-date guard producer implementation
- schema/view drift source
- replay/diff source
- Notion API calls or external delivery

## 3. Source Path Candidates

The source contract is intentionally narrow. Explicit JSON input remains the official fallback when producer paths are not stable.

| Source | Current/Expected Filename | Producer Command | Alert Use | Status |
| --- | --- | --- | --- | --- |
| Daily Ops Status | `daily_ops_status_{YYYYMMDD}.json`, `daily_ops_status.json` | Existing Daily Ops dry-run/export payload flow | workflow, review, sync risk | Current |
| PAPER17 preflight | `daily_ops_actual_preflight_{YYYYMMDD}.json`, `preflight_daily_ops_status_actual_{YYYYMMDD}.json`, `preflight.json` | `scripts/dev/preflight_daily_ops_status_actual.py` | actual readiness warning/fail | Current |
| Manual Execution | `manual_execution_{YYYYMMDD}.json`, `manual_execution_status_{YYYYMMDD}.json`, `manual_execution_import_commit_{YYYYMMDD}.json`, `manual_execution.json` | Manual Execution preview/commit/status sync reports | high-level execution risk | Candidate / partial |
| Manual Review | `manual_review_{YYYYMMDD}.json`, `manual_review_status_{YYYYMMDD}.json`, `manual_review_append_{YYYYMMDD}.json`, `manual_review.json` | Manual Review validate/append/status sync reports | high-level review risk | Candidate / partial |
| Data Freshness | `data_freshness_{YYYYMMDD}.json`, `freshness_{YYYYMMDD}.json`, `market_data_freshness_{YYYYMMDD}.json`, `data_freshness.json` | data freshness checker or future closeout artifact | stale/fail market data risk | Candidate |
| Same-date Guard | `same_date_guard_{YYYYMMDD}.json`, `same_date_commit_guard_{YYYYMMDD}.json`, `commit_guard_{YYYYMMDD}.json`, `same_date_guard.json` | same-date commit guard or future closeout artifact | duplicate writer/run guard risk | Candidate |

Explicit CLI inputs take precedence over `--source-root` candidate lookup.

## 4. Data Freshness Mapping

Supported fields are intentionally tolerant because producer contracts are not final:

- `freshness_status`
- `data_freshness_status`
- `market_data_status`
- `result`
- `stale_symbols_count`
- `stale_source_count`
- `max_stale_days`
- `stale_threshold_days`
- `max_allowed_stale_days`

Mapping:

| Signal | Severity | Notes |
| --- | --- | --- |
| `FAIL` / `FAILED` | `BLOCKING` | Data freshness failure blocks clean closeout decisions. |
| `STALE` | `NEEDS_REVIEW` by default, `BLOCKING` if `max_stale_days > stale_threshold_days` | Avoid over-escalating stale producer candidates unless threshold evidence is explicit. |
| `WARNING` / `PASS_WITH_WARNINGS` | `NEEDS_REVIEW` | Operator should inspect warning context. |
| `stale_symbols_count > 0` or `stale_source_count > 0` | `NEEDS_REVIEW` | Stale inputs require review but are not always blocking. |
| account/date mismatch | `BLOCKING` | Source does not match requested alert report context. |

Normal fresh/pass status is not expanded into Markdown detail.

## 5. Same-date Guard Mapping

Supported fields:

- `same_date_guard_status`
- `commit_guard_status`
- `guard_status`
- `blocked`
- `block_reason`
- `existing_commit_count`
- `same_date_commit_exists`

Mapping:

| Signal | Severity | Notes |
| --- | --- | --- |
| `BLOCKED` / `FAIL` / `FAILED` | `BLOCKING` | Writer/commit guard risk is source-of-truth safety related. |
| `blocked = true` | `BLOCKING` | Explicit block flag stops writer actions. |
| `same_date_commit_exists = true` | `NEEDS_REVIEW` by default, `BLOCKING` if `block_reason` is present | Existing commit needs operator confirmation before writer commands. |
| `WARNING` | `NEEDS_REVIEW` | Operator should inspect guard warning. |
| account/date mismatch | `BLOCKING` | Source does not match requested alert report context. |

## 6. Missing / Malformed Source Policy

Missing source policy remains conservative because the upstream producer contract is not yet stable:

- missing data freshness source at closeout -> suppressed `INFO`
- missing same-date guard source at closeout -> suppressed `INFO`
- malformed freshness JSON -> `BLOCKING`
- malformed same-date guard JSON -> `BLOCKING`

Missing source must not trigger Notion export/sync or writer commands to compensate.

## 7. CLI Changes

The Alert Report CLI now accepts:

```cmd
python scripts\dev\generate_paper_alert_report.py --account-id paper_sandbox --date 2026-05-20 --phase closeout --freshness-json <path> --same-date-guard-json <path> --output-dir <path> --json
```

Existing options are preserved:

- `--daily-ops-status-json`
- `--preflight-json`
- `--manual-execution-json`
- `--manual-review-json`
- `--source-root`
- `--output-dir`
- `--actual-intent`

Explicit JSON input overrides `--source-root` discovery.

## 8. Duplicate Alert Avoidance

PAPER18-6 does not add broad duplicate merging. It avoids Dashboard-style duplication by:

- not emitting alert items for normal fresh/pass states
- suppressing INFO detail in Markdown
- keeping data freshness and same-date guard categories distinct from Daily Ops review and sync categories

If future producers duplicate Daily Ops fields exactly, a dedicated dedupe key should be added later.

## 9. Read-only Safety Policy

This MFU is read-only:

- no Notion API calls
- no Notion write/export/sync
- no Telegram/Slack/Email delivery
- no commit/append/status sync execution
- no outputs/paper ledger modification
- tests use `tmp_path` and `--output-dir`

The report generator reads JSON source files and writes only the requested Alert Report JSON/Markdown outputs.

## 10. Test Coverage

Added/maintained coverage includes:

- data freshness `FAIL` -> `BLOCKING`
- data freshness `STALE` -> `NEEDS_REVIEW`
- stale count -> `NEEDS_REVIEW`
- malformed freshness source -> `BLOCKING`
- missing freshness source -> suppressed `INFO`
- same-date guard `BLOCKED` and `blocked=true` -> `BLOCKING`
- same-date commit exists -> `NEEDS_REVIEW`
- malformed same-date guard source -> `BLOCKING`
- missing same-date guard source -> suppressed `INFO`
- explicit freshness JSON overrides `--source-root`
- existing INFO suppression and CLI smoke behavior

## 11. Limitations

- Freshness and same-date guard producer contracts are still candidates.
- `--source-root` discovery remains intentionally narrow.
- Missing freshness/guard sources are suppressed `INFO`, not hard blockers.
- Schema/view drift and replay/diff are not connected yet.
- Manual Execution/Review row-level analysis is still out of scope.
- No external delivery adapter is implemented.

## 12. PAPER18 Closeout Recommendation

PAPER18 is closeout-ready for local Paper Ops Exception Report foundation after PAPER18-6 if the tests pass, because the initial source set now covers:

- Daily Ops Status
- PAPER17 actual preflight
- Manual Execution high-level signal
- Manual Review high-level signal
- data freshness
- same-date guard

Recommended next step:

- PAPER18 closeout documentation, then proceed to schema/view drift or replay/diff as PAPER19/PAPER20 candidates.

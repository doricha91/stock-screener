# PAPER18 Alert / Monitoring Report Closeout

## 1. Purpose

PAPER18 closes out the local Paper Ops Exception Report foundation. The purpose was not to duplicate the Daily Ops Status Dashboard, but to create a focused JSON/Markdown report that surfaces exceptions, risks, and stop conditions an operator should not miss.

## 2. PAPER18 Scope

PAPER18 covered:

- Alert / Monitoring Report design
- Alert Report generator implementation
- INFO suppression policy
- fixture-based CLI smoke hardening
- real ops source connection
- Manual Execution / Manual Review high-level signal connection
- data freshness / same-date guard alert source connection
- read-only JSON/Markdown output

PAPER18 did not implement external delivery, Notion write/export/sync, actual export approval, schema/view drift, or replay/diff.

## 3. Non-overlap with Daily Ops Status Dashboard

Daily Ops Status Dashboard = operational progress board.

Alert Report = exception / risk / stop-condition report.

The Alert Report does not list every normal status row. It prioritizes `BLOCKING`, `NEEDS_REVIEW`, and `SYNC_FAILED` items. `INFO` items are preserved in JSON but suppressed in Markdown as count/reason summaries to avoid turning the report into another status dashboard.

## 4. Completed Work

Completed PAPER18 commits:

```text
e3a548bcfa0748cd47581ca6613578454f78eafd
docs: design PAPER18 alert monitoring report

73a6347a9bcd860253cd330b016ac9f8be6fe622
feat: add PAPER18 alert report generator

a0405081bc58dbe5bc15752d56eb14f7e43accbb
feat: harden PAPER18 alert info suppression and CLI smoke

2794cc30a88aec49b93d0942aba1f79e45cfe017
feat: connect PAPER18 alert report to real ops sources

c1f2ba0d489eaee5d38209d839c74fa61de024dc
feat: add PAPER18 manual ops alert signals

22f8425dcccfabb3e3720742dd8c3fb8d4850736
feat: add PAPER18 freshness and same-date guard alerts
```

## 5. Delivered Artifacts

- `docs/TRD/mfu_paper18_alert_monitoring_signal_inventory_and_schema.md`
- `core/paper_alert_report.py`
- `scripts/dev/generate_paper_alert_report.py`
- `tests/test_paper_alert_report.py`
- `docs/TRD/mfu_paper18_alert_report_generator_minimal.md`
- `docs/TRD/mfu_paper18_info_suppression_and_cli_smoke_hardening.md`
- `docs/TRD/mfu_paper18_real_ops_alert_source_connection.md`
- `docs/TRD/mfu_paper18_source_path_alignment_and_manual_signal.md`
- `docs/TRD/mfu_paper18_freshness_and_same_date_guard_alert_sources.md`

## 6. Alert Source Coverage

Current Alert source set:

- Daily Ops Status
- PAPER17 Daily Ops Status actual preflight
- Manual Execution high-level signal
- Manual Review high-level signal
- Data freshness
- Same-date guard

Daily Ops Status signals:

- sync failure
- workflow incomplete / unknown
- review incomplete / pending
- review validation failure
- account mismatch

PAPER17 preflight signals:

- preflight `FAIL` / `WARNING`
- schema validation `FAIL`
- duplicate audit `duplicate_blocker`
- `actual_intent`-based expected page id warning handling
- account mismatch

Manual Execution signals:

- preview `FAIL` / `WARNING`
- commit missing / not committed
- sync failed
- pending rows
- account/date mismatch

Manual Review signals:

- validation `FAIL`
- append missing / not appended
- sync failed
- pending rows
- partial / unknown review progress
- account/date mismatch

Data freshness signals:

- `FAIL` / `FAILED`
- `STALE`
- stale symbol/source count
- stale threshold breach
- malformed source
- account/date mismatch

Same-date guard signals:

- `BLOCKED` / `FAIL` / `FAILED`
- `blocked = true`
- `same_date_commit_exists = true`
- `block_reason`
- malformed source
- account/date mismatch

## 7. Severity Policy

`BLOCKING`:

- preflight `FAIL`
- schema validation `FAIL`
- duplicate audit `duplicate_blocker`
- validation `FAIL`
- malformed JSON
- same-date guard blocked/fail
- account/date mismatch
- clear source-of-truth safety risk

`NEEDS_REVIEW`:

- `actual_intent=true` with preflight `WARNING`
- pending/incomplete/manual confirmation required
- stale count greater than zero
- same-date commit exists without explicit block reason
- warning-level manual execution/review/freshness signals

`SYNC_FAILED`:

- local source-of-truth may be valid, but Notion sync/export/status reflection failed
- no local rollback should be performed only because presentation sync failed

`INFO`:

- duplicate audit `update_candidate` without actual intent
- source missing where the producer contract is still candidate-level
- `actual_intent=false` expected page id warning
- normal informational preflight pass/update context

## 8. INFO Suppression Policy

JSON preserves all AlertItems, including `INFO`.

Markdown expands only `BLOCKING`, `NEEDS_REVIEW`, and `SYNC_FAILED` details by default. `INFO` is represented as counts and suppression reasons, with a note that details remain available in JSON.

This keeps the Alert Report exception-oriented and prevents duplicate status-board behavior.

## 9. Output / Delivery Boundary

Output format:

- JSON report
- Markdown report

Default output path:

```text
outputs/paper_accounts/{account_id}/alerts/paper_alert_report_{YYYYMMDD}.json
outputs/paper_accounts/{account_id}/alerts/paper_alert_report_{YYYYMMDD}.md
```

Tests and smoke paths use `tmp_path` or explicit `--output-dir`.

Delivery boundary:

- Telegram / Slack / Email delivery is not implemented.
- Delivery adapters remain future work.
- Delivery failure must not be treated as source-of-truth failure.

## 10. Read-only Safety Policy

PAPER18 only generates local alert reports.

Safety invariants:

- Notion API calls: none
- Notion write/export/sync: none
- Telegram/Slack/Email delivery: none
- `commit` / `append` / status sync commands: none
- outputs/paper ledger mutation: none
- broker/API/cloud runner activity: none

## 11. Validation Summary

Final validation:

```cmd
pytest tests\test_paper_alert_report.py
```

Result:

```text
41 passed
```

Pytest emitted a cache permission warning for `.pytest_cache`, but this is not a functional failure and does not affect Alert Report behavior.

## 12. Known Limitations

- Freshness and same-date guard producer contracts are still candidate-level.
- Manual Execution / Manual Review handling is high-level signal mapping, not row-level analysis.
- Schema/view drift source is not connected.
- Replay/diff source is not connected.
- Telegram/Slack/Email delivery adapter is not implemented.
- Actual export approval flow remains separate and must be implemented immediately before any actual write expansion.
- Missing source behavior is intentionally conservative and can be hardened after producer contracts stabilize.

## 13. Deferred Items

- schema/view drift alert source
- replay/same-date diff alert source
- external delivery adapter
- row-level Manual Execution / Manual Review diagnostics
- actual approval/operator runbook integration
- freshness producer contract formalization
- same-date guard producer contract formalization

## 14. Closeout Decision

PAPER18 is closeout-ready because the initial Paper Ops Exception Report now covers Daily Ops, preflight, Manual Execution/Review, freshness, and same-date guard sources while preserving read-only safety and JSON/Markdown output.

Actual export, Notion write/export/sync, external delivery, schema/view drift, and replay/diff remain outside PAPER18 and require separate MFUs.

## 15. Next MFU Recommendation

Recommended next MFU:

```text
PAPER19 Replay / Same-date Diff Minimal Harness
```

Goal:

- regenerate the same date's Daily Plan
- compare the regenerated plan against the existing plan
- detect action / symbol / quantity / price / warning differences
- surface config snapshot and universe snapshot difference candidates
- reduce reproducibility risk before universe or strategy expansion

Schema/View Drift remains an important follow-up candidate, but the next major direction after PAPER18 is Replay / Same-date Diff Minimal Harness.

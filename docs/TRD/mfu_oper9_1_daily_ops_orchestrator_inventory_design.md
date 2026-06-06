# MFU-OPER9-1 Daily Ops Orchestrator Inventory Design

## 1. Scope

This document is an inventory and design handoff for MFU-OPER9 Daily Ops Orchestrator MVP.

OPER9-1 does not implement an orchestrator. It documents the existing paper daily ops commands, local artifact contracts, stage status heuristics, duplicate risks, fallback risks, and a safe CLI direction for OPER9-2.

Excluded from this step:

- automatic Notion actual write
- automatic Manual Execution commit
- automatic Manual Review append
- paper ledger CSV/JSON/SQLite mutation
- broker/API integration
- Notion schema or view changes
- Daily Ops Status actual export implementation
- full orchestrator MVP implementation
- generated outputs commit

Latest closeout reference:

```text
fa1b0702b554d1399714f8f362c5824a9e467294 docs: close out OPER6 to OPER8 paper ops
```

## 2. Current Official Operating Command Flow

The current OPER6-8 official flow is manual and command-driven:

```cmd
python scripts\paper.py data-freshness --date <DATA_DATE>
python scripts\paper.py plan --data-date <DATA_DATE> --trade-date <TRADE_DATE> --account-id <ACCOUNT_ID>
python scripts\export_paper_to_notion.py --daily-plan --account-id <ACCOUNT_ID> --date <TRADE_DATE> --confirm-actual --json
python scripts\export_paper_to_notion.py --manual-execution-template --account-id <ACCOUNT_ID> --date <TRADE_DATE> --confirm-actual --json
python scripts\import_notion_executions.py --date <TRADE_DATE> --account-id <ACCOUNT_ID> --preview --json
python scripts\import_notion_executions.py --date <TRADE_DATE> --account-id <ACCOUNT_ID> --commit --preview-json "<preview_json>" --json
python scripts\sync_notion_execution_status.py --date <TRADE_DATE> --account-id <ACCOUNT_ID> --commit-report "<commit_json>" --json
python scripts\paper.py review --account-id <ACCOUNT_ID> --date <TRADE_DATE>
python scripts\export_paper_to_notion.py --manual-review-template --account-id <ACCOUNT_ID> --date <TRADE_DATE> --confirm-actual --json
python scripts\import_notion_reviews.py --date <TRADE_DATE> --account-id <ACCOUNT_ID> --preview --json
python scripts\import_notion_reviews.py --date <TRADE_DATE> --account-id <ACCOUNT_ID> --commit --preview-json "<preview_json>" --json
python scripts\sync_notion_review_status.py --date <TRADE_DATE> --account-id <ACCOUNT_ID> --commit-report "<commit_json>" --json
python scripts\paper.py status --account-id <ACCOUNT_ID> --date <TRADE_DATE> --json
```

Important existing semantics:

- `data_date` is the completed market-data date used for signal and data freshness checks.
- `trade_date`, `plan_date`, `execution_date`, `snapshot_date`, and `review_date` are the operational date.
- Official Daily Plan mode requires paired `--data-date` and `--trade-date`.
- `paper.py plan` blocks `trade_date <= data_date` and weekend `trade_date`.
- Notion actual writes require explicit `--confirm-actual`.
- Manual Execution commit and Manual Review append require a preview JSON.
- `paper.py status` is read-only and currently provides a coarse workflow status, not a full stage-by-stage checklist.

## 3. Command Inventory

| Command | Read/write profile | Existing outputs or side effects | Notes |
| --- | --- | --- | --- |
| `python scripts\paper.py data-freshness --date <DATA_DATE>` | read-only unless `--write-report` is used | optional `reports/paper_data_freshness_report.md`, `reports/paper_data_freshness_issues.csv` | Uses `core.paper_data_freshness.run_paper_data_freshness_check`. Strict mode turns stale required data into errors. |
| `python scripts\paper.py plan --data-date <DATA_DATE> --trade-date <TRADE_DATE> --account-id <ACCOUNT_ID>` | writes plan artifacts | `daily_action_plan_<TRADE_DATE>.md`, `daily_action_plan_<TRADE_DATE>.json`, `config_snapshots/paper_config_snapshot_<TRADE_DATE>.json` | Official explicit mode. Runs data freshness and preflight before writing plan artifacts. |
| `python scripts\export_paper_to_notion.py --daily-plan ... --confirm-actual --json` | Notion actual write | Notion Daily Plans row create/update | Local source is Daily Plan markdown plus JSON/config sidecar. |
| `python scripts\export_paper_to_notion.py --manual-execution-template ... --confirm-actual --json` | Notion actual write | Notion Manual Executions DRAFT row create/update | Source is Daily Plan JSON sidecar. Uses account-aware External Key. |
| `python scripts\import_notion_executions.py --preview --json` | Notion read plus local preview file write | `reports/manual_execution_import_preview_<TRADE_DATE>.json/.md` | Does not modify Notion or ledgers. Validates READY rows and duplicate trade ids. |
| `python scripts\import_notion_executions.py --commit --preview-json ... --json` | local ledger/state write | `paper_execution_log.csv`, snapshots, `reports/manual_execution_import_commit_<TRADE_DATE>.json/.md`, backups | Requires preview JSON. Blocks duplicate paper trades and FAIL rows. |
| `python scripts\sync_notion_execution_status.py --commit-report ... --json` | Notion actual write unless `--dry-run` | Notion Manual Executions status fields | Requires commit report. Checks CLI account against report account. |
| `python scripts\paper.py review --account-id ... --date <TRADE_DATE>` | local report/template write | reports and `reviews/paper_manual_review_log_template.csv/.md`, validation report | Wrapper for reports, review template, and review validation. |
| `python scripts\export_paper_to_notion.py --manual-review-template ... --confirm-actual --json` | Notion actual write | Notion Manual Reviews pending rows | Source is local review template CSV. |
| `python scripts\import_notion_reviews.py --preview --json` | Notion read plus local preview file write | `reports/manual_review_import_preview_<TRADE_DATE>.json/.md` | Does not modify Notion or review log. Validates answers and duplicates. |
| `python scripts\import_notion_reviews.py --commit --preview-json ... --json` | local review log write | `reviews/paper_manual_review_log.csv`, `reports/manual_review_import_commit_<TRADE_DATE>.json/.md`, backups | This is the Manual Review append path. Requires preview JSON. |
| `python scripts\sync_notion_review_status.py --commit-report ... --json` | Notion actual write unless `--dry-run` | Notion Manual Reviews status fields | Requires review commit report. Checks CLI account against report account. |
| `python scripts\paper.py status --account-id ... --date <TRADE_DATE> --json` | read-only | stdout JSON | Uses local artifacts to report workflow status and next recommended command. |

## 4. Artifact Path Inventory

For non-default accounts, the root is:

```text
outputs/paper_accounts/<ACCOUNT_ID>
```

For `paper_default`, legacy fallback may use:

```text
outputs/paper_test
```

Core resolver:

- `core.paper_account_paths.build_paper_account_paths()`
- `core.paper_account_paths.resolve_paper_account_root()`
- `core.paths.PAPER_TEST_DIR`

| Artifact | Account-aware path | Legacy/default path | Producer |
| --- | --- | --- | --- |
| Daily Plan markdown | `<root>/daily_action_plan_<YYYYMMDD>.md` | `outputs/paper_test/daily_action_plan_<YYYYMMDD>.md` | `paper.py plan` |
| Daily Plan JSON sidecar | `<root>/daily_action_plan_<YYYYMMDD>.json` | `outputs/paper_test/daily_action_plan_<YYYYMMDD>.json` | `paper.py plan` via Daily Plan generator |
| Daily Plan config snapshot | `<root>/config_snapshots/paper_config_snapshot_<YYYYMMDD>.json` | `outputs/paper_test/config_snapshots/paper_config_snapshot_<YYYYMMDD>.json` | `paper.py plan` |
| Data freshness report | `<root>/reports/paper_data_freshness_report.md` not currently account-routed by `paper.py data-freshness` | `outputs/paper_test/reports/paper_data_freshness_report.md` | `paper.py data-freshness --write-report` |
| Data freshness issues | same caveat as above | `outputs/paper_test/reports/paper_data_freshness_issues.csv` | `paper.py data-freshness --write-report` |
| Manual Execution preview JSON | `<root>/reports/manual_execution_import_preview_<YYYYMMDD>.json` | `outputs/paper_test/reports/manual_execution_import_preview_<YYYYMMDD>.json` | `import_notion_executions.py --preview` |
| Manual Execution preview markdown | `<root>/reports/manual_execution_import_preview_<YYYYMMDD>.md` | `outputs/paper_test/reports/manual_execution_import_preview_<YYYYMMDD>.md` | `import_notion_executions.py --preview` |
| Manual Execution commit JSON | `<root>/reports/manual_execution_import_commit_<YYYYMMDD>.json` | `outputs/paper_test/reports/manual_execution_import_commit_<YYYYMMDD>.json` | `import_notion_executions.py --commit` |
| Manual Execution commit markdown | `<root>/reports/manual_execution_import_commit_<YYYYMMDD>.md` | `outputs/paper_test/reports/manual_execution_import_commit_<YYYYMMDD>.md` | `import_notion_executions.py --commit` |
| Execution log | `<root>/paper_execution_log.csv` | `outputs/paper_test/paper_execution_log.csv` | execution commit |
| Current state | `<root>/paper_current_state_<YYYYMMDD>.json` | `outputs/paper_test/paper_current_state_<YYYYMMDD>.json` | execution commit |
| Account snapshot | `<root>/paper_account_snapshot.csv` | `outputs/paper_test/paper_account_snapshot.csv` | execution commit |
| Position snapshot | `<root>/paper_position_snapshot.csv` | `outputs/paper_test/paper_position_snapshot.csv` | execution commit |
| Daily Review Summary | `<root>/reports/paper_daily_review_summary.md` | `outputs/paper_test/reports/paper_daily_review_summary.md` | `paper.py review` |
| Performance summary | `<root>/reports/paper_performance_summary.md` | `outputs/paper_test/reports/paper_performance_summary.md` | report chain |
| Manual Review template CSV | `<root>/reviews/paper_manual_review_log_template.csv` | `outputs/paper_test/reviews/paper_manual_review_log_template.csv` | `paper.py review` or `paper.py review-template` |
| Manual Review template markdown | `<root>/reviews/paper_manual_review_log_template.md` | `outputs/paper_test/reviews/paper_manual_review_log_template.md` | `paper.py review` or `paper.py review-template` |
| Manual Review validation report | `<root>/reviews/paper_manual_review_log_validation_report.md` | `outputs/paper_test/reviews/paper_manual_review_log_validation_report.md` | `paper.py review` |
| Manual Review preview JSON | `<root>/reports/manual_review_import_preview_<YYYYMMDD>.json` | `outputs/paper_test/reports/manual_review_import_preview_<YYYYMMDD>.json` | `import_notion_reviews.py --preview` |
| Manual Review preview markdown | `<root>/reports/manual_review_import_preview_<YYYYMMDD>.md` | `outputs/paper_test/reports/manual_review_import_preview_<YYYYMMDD>.md` | `import_notion_reviews.py --preview` |
| Manual Review commit JSON | `<root>/reports/manual_review_import_commit_<YYYYMMDD>.json` | `outputs/paper_test/reports/manual_review_import_commit_<YYYYMMDD>.json` | `import_notion_reviews.py --commit` |
| Manual Review commit markdown | `<root>/reports/manual_review_import_commit_<YYYYMMDD>.md` | `outputs/paper_test/reports/manual_review_import_commit_<YYYYMMDD>.md` | `import_notion_reviews.py --commit` |
| Manual Review log | `<root>/reviews/paper_manual_review_log.csv` | `outputs/paper_test/reviews/paper_manual_review_log.csv` | review append |
| `paper.py status` references | plan, current state, account snapshot, position snapshot, execution log, daily review summary, performance summary, review template, validation report, review log | same | `core.paper_status.run_paper_status()` |

Open point:

- Data freshness report writing is rooted in `paper_reports_dir()` and is not clearly account-aware. OPER9 should treat data freshness as a live read-only check result, not as an account-scoped persisted artifact, until this is changed separately.

## 5. Stage Input/Output Artifact Table

| Stage | Required inputs | Expected outputs or evidence |
| --- | --- | --- |
| DATA_FRESHNESS | market DB, universe snapshot, `data_date` | live result from `run_paper_data_freshness_check(data_date, strict=True)`; optional legacy report if written |
| DAILY_PLAN | DATA_FRESHNESS PASS, account root/state, `data_date`, `trade_date` | Daily Plan md/json and config snapshot for `trade_date` |
| DAILY_PLAN_NOTION_EXPORT | Daily Plan md/json/config snapshot | no reliable local sidecar currently; evidence is command result or Notion row, external to local status |
| MANUAL_EXECUTION_TEMPLATE | Daily Plan JSON sidecar | no reliable local sidecar currently; evidence is command result or Notion rows, external to local status |
| MANUAL_EXECUTION_PREVIEW | Notion Manual Executions READY rows, snapshots/log for validation | manual execution preview JSON/markdown |
| MANUAL_EXECUTION_COMMIT | preview JSON with `commit_allowed=true` or allowed warnings | execution commit JSON/markdown, execution log rows, current state, account snapshot, position snapshot |
| MANUAL_EXECUTION_STATUS_SYNC | execution commit JSON | no reliable local sidecar currently; evidence is command result or Notion fields |
| DAILY_REVIEW | committed snapshots/log, report chain inputs | daily review summary, performance summary, symbol reports, review template, validation report |
| MANUAL_REVIEW_TEMPLATE | review template CSV | no reliable local sidecar currently; evidence is command result or Notion rows |
| MANUAL_REVIEW_PREVIEW | Notion Manual Reviews READY rows, template/log for validation | manual review preview JSON/markdown |
| MANUAL_REVIEW_APPEND | review preview JSON with `append_allowed=true` or allowed warnings | review commit JSON/markdown, review log rows |
| MANUAL_REVIEW_STATUS_SYNC | review commit JSON | no reliable local sidecar currently; evidence is command result or Notion fields |
| FINAL_STATUS | all local artifacts | `paper.py status --json` reports `workflow_status=REVIEW_DONE` |

## 6. Stage Status Draft

Status vocabulary:

- `DONE`: stage has sufficient local evidence, or the local final status proves it is complete.
- `READY`: prerequisites are present and the next command can be recommended without violating guards.
- `BLOCKED`: missing required input, guard failure, or previous stage not complete.
- `WARNING`: incomplete or externally unverifiable state, fallback risk, or duplicate risk.
- `UNKNOWN`: local artifacts cannot safely prove the status.

| Stage | DONE | READY | BLOCKED | WARNING | UNKNOWN |
| --- | --- | --- | --- | --- | --- |
| DATA_FRESHNESS | live strict check for `data_date` returns PASS | market DB exists and dates are valid but check not yet run in current invocation | missing/invalid `data_date`, unreadable DB, strict FAIL | live non-strict would pass with warnings, optional persisted report stale/missing | check unavailable due unexpected exception |
| DAILY_PLAN | md/json/config snapshot exist for `trade_date`, JSON account matches `account_id`, sidecar `data_date` and `trade_date` match | DATA_FRESHNESS DONE and no plan artifact exists | invalid date guard, missing account root/inception state, freshness FAIL | plan md exists but JSON/config missing, JSON date/account mismatch, legacy `--date` artifact only | artifact exists but JSON cannot be parsed |
| DAILY_PLAN_NOTION_EXPORT | local proof not currently reliable; can be inferred only if a trusted export result is captured later | DAILY_PLAN DONE | DAILY_PLAN not DONE | no local export sidecar; requires Notion actual write to verify | default until OPER9 has a local export log contract |
| MANUAL_EXECUTION_TEMPLATE | local proof not currently reliable; can be inferred only if trusted export result or Notion read is captured later | DAILY_PLAN DONE and DAILY_PLAN_NOTION_EXPORT is DONE or WARNING-with-operator-confirmation | missing Daily Plan JSON | no local export sidecar; Notion may have DRAFT rows but local status cannot prove it | default without Notion read/export log |
| MANUAL_EXECUTION_PREVIEW | preview JSON/markdown exist, dates/account match, `fail_count=0`, `commit_allowed` is `true` or `true_with_warnings` | MANUAL_EXECUTION_TEMPLATE not BLOCKED and no preview exists | missing template stage, preview JSON parse error, preview account/date mismatch, `fail_count>0` | `commit_allowed=true_with_warnings`, preview older than Daily Plan, candidate_count=0 | Notion read not run and no preview artifact |
| MANUAL_EXECUTION_COMMIT | commit JSON/markdown exist, report account/date match, snapshots for `trade_date` exist, execution rows for date exist | preview DONE and no commit JSON/snapshot rows exist | missing preview JSON, preview blocks commit, duplicate evidence already exists | commit JSON exists but snapshots/log rows missing, or ledger rows exist without commit sidecar | artifacts inconsistent and cannot decide |
| MANUAL_EXECUTION_STATUS_SYNC | local proof not currently reliable; can be inferred only from Notion sync command result if captured | MANUAL_EXECUTION_COMMIT DONE | missing commit report | no local sync sidecar; Notion status may be stale | default without Notion read/sync log |
| DAILY_REVIEW | daily review summary, performance summary, review template, validation report PASS exist for `trade_date` | MANUAL_EXECUTION_COMMIT DONE | missing committed snapshots/log | reports exist but template date mismatch, validation report missing or non-PASS | report artifacts exist but cannot prove target date |
| MANUAL_REVIEW_TEMPLATE | local proof not currently reliable; can be inferred only from trusted export result or Notion read | DAILY_REVIEW DONE | missing review template CSV | no local export sidecar; Notion may have pending rows but local status cannot prove it | default without Notion read/export log |
| MANUAL_REVIEW_PREVIEW | review preview JSON/markdown exist, dates/account match, `fail_count=0`, `append_allowed` is `true` or `true_with_warnings` | MANUAL_REVIEW_TEMPLATE not BLOCKED and no review preview exists | missing template, preview parse error, preview account/date mismatch, `fail_count>0` | `append_allowed=true_with_warnings`, duplicate candidates present, candidate_count=0 | Notion read not run and no preview artifact |
| MANUAL_REVIEW_APPEND | review commit JSON/markdown exist, report account/date match, review log contains matching completed keys | review preview DONE and no commit/log duplicate evidence exists | missing preview JSON, preview blocks append, duplicate review keys already exist | commit JSON exists but review log rows missing, review log rows exist without commit sidecar | artifacts inconsistent and cannot decide |
| MANUAL_REVIEW_STATUS_SYNC | local proof not currently reliable; can be inferred only from Notion sync command result if captured | MANUAL_REVIEW_APPEND DONE | missing review commit report | no local sync sidecar; Notion status may be stale | default without Notion read/sync log |
| FINAL_STATUS | `paper.py status --json` would report `workflow_status=REVIEW_DONE` | all local terminal artifacts exist but status not checked | earlier BLOCKED stage | status says REVIEW_PARTIAL or local artifacts indicate done but sync stages are unproven | status returns UNKNOWN_OR_INCOMPLETE |

## 7. Duplicate Commit/Append Risk Analysis

Existing defenses:

- Manual Execution preview assigns canonical keys and validates duplicate projected paper trade ids.
- Manual Execution commit pre-checks `append_paper_execution_log(..., commit=False)` and blocks duplicate paper trades before writing.
- Manual Execution commit writes `reports/manual_execution_import_commit_<YYYYMMDD>.json/.md`.
- Manual Review preview validates duplicate batch keys and duplicate existing review keys.
- Manual Review append selects committable candidates, checks duplicate canonical keys, and blocks duplicate existing review log rows.
- Manual Review append writes `reports/manual_review_import_commit_<YYYYMMDD>.json/.md`.

Remaining recommender risks:

- Recommending commit again after commit sidecar exists can waste operator time and may hit duplicate blockers.
- Recommending append again after review commit sidecar exists can hit duplicate blockers.
- Recommending commit/append from a stale preview can apply rows that no longer match current Notion/manual input intent.
- Local ledger/log rows may exist even if commit report is missing, for example after a prior partial operation or manual file movement.

OPER9-2 guard recommendation:

- Never recommend Manual Execution commit if any of these are true:
  - `manual_execution_import_commit_<TRADE_DATE>.json` exists for the account root.
  - `paper_execution_log.csv` already has rows for `date=<TRADE_DATE>` with `source=notion_manual_execution`.
  - current state or account/position snapshot exists for `snapshot_date=<TRADE_DATE>` and preview is older than those artifacts.
- Never recommend Manual Review append if any of these are true:
  - `manual_review_import_commit_<TRADE_DATE>.json` exists for the account root.
  - `paper_manual_review_log.csv` contains all template keys for `review_date=<TRADE_DATE>`.
  - preview JSON has duplicate candidates or `fail_count>0`.
- If duplicate evidence exists, return `DONE` when terminal artifacts are consistent, otherwise `WARNING` with `next_command=null`.

## 8. paper_test Fallback Risk Analysis

Current resolver behavior:

- Non-default accounts resolve to `outputs/paper_accounts/<ACCOUNT_ID>`.
- `paper_default` resolves to `outputs/paper_accounts/paper_default` if it exists.
- If `paper_default` account root does not exist and legacy fallback is allowed, it uses `outputs/paper_test`.
- Many older helper paths in `core.paths` still point directly to `outputs/paper_test`.

Risks:

- A missing `--account-id` defaults through `normalize_notion_account_id(None)` or account profile resolution and can route to `paper_default`.
- Legacy `paper_test` artifacts can make a stage look DONE for the wrong account.
- Data freshness reports are currently legacy-rooted when written, so they should not be treated as account-specific evidence.
- Some Notion query filters include legacy compatibility for `paper_default`, which is intentional but should not bleed into non-default account recommendations.

OPER9-2 guard recommendation:

- Require `--account-id` for `ops status`; do not default silently.
- Resolve account root and expose:
  - `account_root`
  - `legacy_default_used`
  - `fallback_warnings`
- For non-default accounts, mark any required artifact found only under `outputs/paper_test` as `WARNING`, not `DONE`.
- For `paper_default`, explicitly show when legacy fallback is used.
- Never recommend a write or commit command based on artifacts from a different account root.

## 9. Date and Account Guard Design

Required CLI inputs:

- `account_id`: required.
- `data_date`: required.
- `trade_date`: required.

Normalization:

- Accept `YYYYMMDD` or `YYYY-MM-DD`.
- Normalize JSON output to `YYYY-MM-DD`.
- Build file paths with compact `YYYYMMDD`.

Blocking guard rules:

- `trade_date <= data_date`: BLOCKED.
- weekend `trade_date`: BLOCKED, matching existing `paper.py plan`.
- missing `account_id`: BLOCKED.
- invalid account id per existing account profile validation: BLOCKED.
- Daily Plan JSON account mismatch: BLOCKED.
- Daily Plan JSON `data_date` or `trade_date` mismatch: BLOCKED.
- preview JSON account/date mismatch: BLOCKED.
- commit report account/date mismatch: BLOCKED.

Warnings:

- `legacy_default_used=true`.
- local stage evidence exists in `paper_test` while requested account is non-default.
- stage can only be verified through Notion state and no local evidence exists.
- preview has warnings and would need explicit `--allow-warnings`.

## 10. Output JSON Schema Draft

Top-level schema:

```json
{
  "schema_version": "mfu_oper9_daily_ops_status.v1",
  "account_id": "paper_pilot_202606",
  "account_root": "outputs/paper_accounts/paper_pilot_202606",
  "legacy_default_used": false,
  "data_date": "2026-06-05",
  "trade_date": "2026-06-08",
  "overall_status": "DONE",
  "workflow_status": "REVIEW_DONE",
  "next_command": null,
  "guards": {
    "account_id_required": true,
    "data_date_required": true,
    "trade_date_required": true,
    "trade_date_after_data_date": true,
    "paper_test_fallback_detected": false,
    "write_actions_enabled": false
  },
  "stages": [],
  "artifact_roots": {
    "account_root": "outputs/paper_accounts/paper_pilot_202606",
    "legacy_paper_test_root": "outputs/paper_test"
  },
  "notes": []
}
```

Stage object schema:

```json
{
  "stage_name": "MANUAL_EXECUTION_PREVIEW",
  "status": "DONE",
  "blockers": [],
  "warnings": [],
  "required_artifacts": [
    "outputs/paper_accounts/paper_pilot_202606/reports/manual_execution_import_preview_20260608.json"
  ],
  "existing_artifacts": [
    "outputs/paper_accounts/paper_pilot_202606/reports/manual_execution_import_preview_20260608.json",
    "outputs/paper_accounts/paper_pilot_202606/reports/manual_execution_import_preview_20260608.md"
  ],
  "missing_artifacts": [],
  "next_command": null,
  "note": "Preview exists and commit report already exists, so commit is not recommended."
}
```

Recommended extra fields for implementation:

- `status_reason`
- `source_of_truth`
- `parsed_summary`
- `mtime`
- `stale_against`
- `notion_verification_required`

## 11. Recommended CLI

Recommendation: option B with a small naming adjustment:

```cmd
python scripts\paper_daily_ops.py status --account-id <ACCOUNT_ID> --data-date <DATA_DATE> --trade-date <TRADE_DATE> --json
```

Reasons:

- `scripts\paper.py` is already a broad operational shortcut surface and includes mutating commands. Adding `ops` there increases accidental association with write-capable daily operations.
- A dedicated `paper_daily_ops.py status` file makes the read-only boundary easier to document, test, and enforce.
- The explicit `status` subcommand leaves room for future read-only subcommands such as `explain` or `artifacts` without implying execution.
- It can reuse `core.paper_account_paths`, `core.paper_status`, and small local artifact readers without touching existing command behavior.

Rejected for OPER9-2 MVP:

```cmd
python scripts\paper.py ops ...
```

This is convenient, but `paper.py` already includes writer shortcuts and legacy commands. It is less clear as a safety boundary.

Acceptable future alias after MVP hardening:

```cmd
python scripts\paper.py ops-status --account-id <ACCOUNT_ID> --data-date <DATA_DATE> --trade-date <TRADE_DATE> --json
```

Only add this after the standalone read-only CLI has tests.

## 12. Minimum Safe Implementation Scope for OPER9-2

Implement only:

- `scripts\paper_daily_ops.py status`
- a small `core.paper_daily_ops_status` module, if needed
- read-only local artifact existence and JSON/CSV summary parsing
- required account/date guards
- stage status JSON output
- next command recommendations as strings only
- `next_command=null` when the stage is done or unsafe to recommend
- tests for date guard, account root resolution, duplicate commit/append recommendation suppression, and REVIEW_DONE terminal behavior

Allowed local reads:

- Daily Plan md/json/config snapshot
- preview/commit sidecar JSON/markdown
- account/position snapshot CSV
- execution log CSV
- review template/log/validation files
- `core.paper_status.run_paper_status()`

Do not run Notion reads in the first MVP unless explicitly added behind a separate opt-in flag such as `--include-notion-read`.

## 13. Do Not Implement in OPER9-2 Yet

Do not implement:

- automatic Notion export
- automatic Notion sync
- automatic Manual Execution commit
- automatic Manual Review append
- Daily Ops Status actual export
- Notion schema/view mutation
- broker/API integration
- paper ledger mutation
- output artifact cleanup
- broad account migration from `paper_test`
- strategy behavior changes
- `paper.py plan` or existing importer behavior changes

## 14. 2026-06-08 Artifact Observation

Read-only file listing found account-aware artifacts for:

```text
account_id = paper_pilot_202606
data_date = 2026-06-05
trade_date = 2026-06-08
root = outputs/paper_accounts/paper_pilot_202606
```

Observed examples:

- `daily_action_plan_20260608.md`
- `daily_action_plan_20260608.json`
- `config_snapshots/paper_config_snapshot_20260608.json`
- `reports/manual_execution_import_preview_20260608.json`
- `reports/manual_execution_import_commit_20260608.json`
- `paper_current_state_20260608.json`
- `paper_execution_log.csv`
- `paper_account_snapshot.csv`
- `paper_position_snapshot.csv`
- `reports/paper_daily_review_summary.md`
- `reviews/paper_manual_review_log_template.csv`
- `reviews/paper_manual_review_log_validation_report.md`
- `reports/manual_review_import_preview_20260608.json`
- `reports/manual_review_import_commit_20260608.json`
- `reviews/paper_manual_review_log.csv`

Legacy `outputs/paper_test` also exists and contains older default-account artifacts. OPER9-2 should make this visible and avoid using it as evidence for non-default accounts.

## 15. Self-Review / Verification Report

Commands used for required verification:

```cmd
git log --oneline --decorate -n 30
git rev-parse HEAD
type docs\TRD\mfu_oper6_8_closeout.md
git diff --check
git status --short
```

Read-only artifact checks used:

```cmd
dir outputs\paper_accounts\paper_pilot_202606
dir outputs\paper_accounts\paper_pilot_202606\reports
dir outputs\paper_accounts\paper_pilot_202606\reviews
dir outputs\paper_accounts\paper_pilot_202606\config_snapshots
dir outputs\paper_test
```

No command in this investigation performed:

- Notion actual write
- Manual Execution commit
- Manual Review append
- Notion status sync
- ledger mutation
- DB schema or data migration
- broker/API order placement

Current design risk:

- Some Notion export/sync completion cannot be proven locally because there is no dedicated local export/sync sidecar for every Notion write stage. OPER9-2 should report those as `UNKNOWN` or `WARNING` unless a trusted local report contract is added later.

## 16. Open Questions

1. Should OPER9-2 treat Notion export/sync stages as `UNKNOWN` by default, or should it allow operator-supplied evidence paths?
2. Should `--include-notion-read` be deferred until OPER9-3, keeping OPER9-2 purely local?
3. Should a future MFU add local dry-run/export/sync sidecars so Notion stages can be verified without live reads?
4. Should `paper_default` continue to permit `outputs/paper_test` fallback in the long term, or should it be migrated to `outputs/paper_accounts/paper_default`?

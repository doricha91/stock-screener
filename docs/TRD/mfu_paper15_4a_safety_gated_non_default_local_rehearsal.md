# MFU-PAPER15-4A Safety-gated Non-default Local Rehearsal

## Purpose

Run a safety-gated local rehearsal for a non-default paper account inside the real project workspace without touching legacy `paper_default` roots or external systems.

## Scope / Non-scope

In scope:
- explicit creation of `outputs/paper_accounts/paper_sandbox`
- local `status`
- local `plan`
- local `eod --dry-run`
- local `reports`
- local `review-template`
- local `review-validate`
- contamination checks for `outputs/paper_test` and `outputs/paper_accounts/paper_default`

Out of scope:
- commit
- review-append
- Notion actual export/sync/write
- broker/API
- cloud runner
- `paper_default` legacy migration

## Rehearsal account_id

- `account_id = paper_sandbox`
- allowed root: `outputs/paper_accounts/paper_sandbox`
- forbidden roots:
  - `outputs/paper_test`
  - `outputs/paper_accounts/paper_default`

## Commands executed

1. `python scripts\paper.py status --account-id paper_sandbox --json`
2. `python scripts\paper.py plan --date 20260520 --account-id paper_sandbox`
3. `python scripts\paper.py eod --date 20260520 --account-id paper_sandbox --dry-run`
4. `python scripts\paper.py reports --account-id paper_sandbox`
5. `python scripts\paper.py review-template --account-id paper_sandbox`
6. `python scripts\paper.py review-validate --account-id paper_sandbox`
7. `python scripts\paper.py status --account-id paper_sandbox --json`

## Command results

Successful:
- initial `status`
  - account root was empty but correctly resolved to `outputs/paper_accounts/paper_sandbox`
- `plan`
  - completed successfully
  - wrote:
    - `daily_action_plan_20260520.md`
    - `config_snapshots/paper_config_snapshot_20260520.json`
- `eod --dry-run`
  - completed successfully
  - confirmed dry-run path separation
  - did not write ledger/snapshot artifacts
- final `status`
  - date resolved to `2026-05-20`
  - workflow moved to `PLAN_READY`

Failed:
- `reports`
  - failed at `equity_curve`
  - reason: `outputs/paper_accounts/paper_sandbox/paper_account_snapshot.csv` did not exist
- `review-template`
  - failed
  - reason: `reports/paper_symbol_review_worksheet.csv` did not exist
- `review-validate`
  - failed
  - reason: `reviews/paper_manual_review_log_template.csv` did not exist

## Generated files under paper_sandbox

Files:
- `outputs/paper_accounts/paper_sandbox/daily_action_plan_20260520.md`
- `outputs/paper_accounts/paper_sandbox/config_snapshots/paper_config_snapshot_20260520.json`

Directories created:
- `archive/`
- `config_snapshots/`
- `replay_diff/`
- `reports/`
- `reviews/`

No files were created under `reports/` or `reviews/` because the chain stopped before those artifacts could be produced.

## outputs/paper_test contamination check

Before/after file-list comparison showed no differences for `outputs/paper_test`.

Result:
- no added files detected
- no removed files detected
- no sandbox artifact leaked into `outputs/paper_test`

## Failures / blockers

Primary blocker:
- `reports` requires committed account snapshot data, but this rehearsal explicitly forbids `commit`

Downstream blockers:
- `review-template` depends on `paper_symbol_review_worksheet.csv`
- `review-validate` depends on `paper_manual_review_log_template.csv`

Interpretation:
- the non-default root routing is working
- the full review chain cannot advance on a pure `plan + eod dry-run` rehearsal without fixture or commit-stage data

## Readiness decision

`paper_sandbox` is ready for:
- account-aware root creation
- read-only status
- plan generation
- eod dry-run path rehearsal

`paper_sandbox` is not yet sufficient for:
- `reports`
- `review-template`
- `review-validate`

when the rehearsal forbids commit-stage artifact creation.

## Next MFU recommendation

Next MFU should introduce a safety-gated rehearsal fixture step or seeded non-default sandbox dataset so that:
- account snapshot
- position snapshot
- execution log

exist before `reports -> review-template -> review-validate` is exercised in the real workspace, while still avoiding real Notion sync/write and avoiding `paper_default` contamination.

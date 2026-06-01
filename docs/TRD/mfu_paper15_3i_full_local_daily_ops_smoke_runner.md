# MFU-PAPER15-3I Non-default Full Local Daily Ops Smoke Runner

## Purpose

Validate that a non-default paper account can complete the full local daily ops chain under a tmp-path account-aware root without touching legacy `paper_default` paths.

## Scope / Non-scope

In scope:
- tmp-path smoke validation for non-default local daily ops
- plan path generation
- eod dry-run path verification
- manual execution commit fixture
- reports
- review-template
- review-validate
- review-append
- final status re-check

Out of scope:
- real `outputs/paper_accounts/*` creation
- Notion actual sync/write
- Notion row migration
- broker/API
- cloud runner
- `paper_default` legacy migration

## Smoke Account Assumptions

- `account_id = paper_smoke`
- root is `tmp_path / outputs / paper_accounts / paper_smoke`
- all CSV/JSON/MD artifacts stay inside that account root
- no real operator command is executed against project `outputs/`

## Verified Full Local Daily Ops Chain

Verified chain:

1. `run_paper_daily_plan()` writes the daily plan and config snapshot under the non-default root
2. `run_paper_eod_dry_run(..., commit=False)` reads the same root and completes without writes outside it
3. manual execution commit fixture writes execution log, current state, snapshots, and sidecar under the same root
4. report generators write under `reports/`
5. review template generation writes under `reviews/`
6. review validation reads and writes under `reviews/`
7. review append writes the manual review log and append artifacts under `reviews/`
8. `run_paper_status()` re-reads the same root and reports a review-ready workflow

## Path Safety Results

- non-default write targets stayed under `account_paths.root`
- explicit attempts to target `outputs/paper_test` from a non-default account failed
- no tmp-path legacy `paper_test` directory was created during the smoke flow
- `paper_default` legacy root behavior remained unchanged in the control test

## Notion Dry-run / Contract Status

- no actual Notion API calls were made
- this MFU reused prior namespace contract coverage as the Notion-side safety basis
- the full smoke runner only validates the local artifact chain

## Remaining Limitations

- plan generation is smoke-tested with a monkeypatched local fixture writer rather than the full market-data-backed implementation
- eod is validated in dry-run mode only
- the smoke uses tmp-path fixtures, not a real operator run
- `paper_default` still intentionally uses the legacy root

## Readiness Decision

Non-default local daily ops is ready at full local smoke level for:
- account-root daily plan artifact generation
- eod dry-run path handling
- manual execution commit fixture writes
- report generation
- review template / validation / append
- final status re-check

It is not yet a full external closeout because Notion actual sync/write remains out of scope.

## Next MFU Recommendation

The next MFU should validate the operator-facing non-default daily ops playbook with a higher-level orchestration helper or dev smoke runner that wraps the verified local chain without touching real project outputs.

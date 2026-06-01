# MFU-PAPER15-3G Reports / Review Template Account Root

## Purpose

Align non-default paper reports, review-template, review-validate, and review-append upstream artifacts under the same account-aware root.

## Scope / Non-scope

In scope:
- `paper.py reports`
- `paper.py review`
- `paper.py review-template`
- `paper.py review-validate`
- local report/review template/validation outputs under `outputs/paper_accounts/{account_id}`

Out of scope:
- Notion actual sync/write
- Notion row migration
- broker/API
- cloud runner
- `paper_default` legacy migration

## Policy

- `paper_default` keeps legacy `outputs/paper_test`
- non-default accounts use `outputs/paper_accounts/{account_id}`
- non-default report/review outputs must stay under `account_paths.root`
- non-default writes to `outputs/paper_test` are rejected

## Implementation Summary

- `scripts/paper.py` now accepts `--account-id` for `reports`, `review`, `review-template`, `review-validate`
- report generator scripts accept optional `account_paths`
- review template / validation scripts accept optional `account_paths`
- core report helpers that previously hard-coded `PAPER_TEST_DIR` now support account-root safety via optional root checks
- daily review summary and report index now render account-specific report paths instead of fixed `outputs/paper_test/reports/...`

## Verification Focus

- non-default reports write only to `account_paths.reports_dir`
- non-default review template/validation write only to `account_paths.reviews_dir`
- `review-template -> review-validate -> review-append` can share the same non-default root
- `paper_default` legacy behavior remains unchanged

## Next Dependency

Next MFU should focus on account-aware report consumers or operational closeout around multi-account daily ops, not on path migration of `paper_default`.

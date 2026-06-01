# MFU-PAPER15-3F Writer Path Account-aware Root

## Purpose

Connect local paper writer and writer-like commands to account-aware roots for non-default accounts while preserving `paper_default` legacy writer behavior.

## Scope / Non-scope

Scope:
- `paper.py plan`, `paper.py eod`, `paper.py commit`, `paper.py review-append`
- `import_notion_executions.py --commit`
- `import_notion_reviews.py --commit`
- local CSV/JSON/MD sidecar writes under account-aware roots

Non-scope:
- Notion actual sync/write
- Notion row migration
- broker/API
- cloud runner
- `paper_default` legacy migration

## Writer Root Policy

- `paper_default` keeps legacy `outputs/paper_test`
- non-default accounts use `outputs/paper_accounts/{account_id}`
- non-default writer paths must stay under `account_paths.root`
- non-default writer targets must not point to `outputs/paper_test`

## Applied Areas

- execution commit local ledger / state / snapshot / sidecar report
- review append local review log / append report / issues csv
- daily plan markdown / config snapshot
- EOD local state / execution log / snapshots

## Safety

- path safety checks validate non-default writer targets stay under account root
- rollback/dev backups for non-default commit/append are stored under `account_root/archive/dev_backups`
- legacy `paper_default` path checks remain unchanged

## Compatibility

- existing `paper_default` daily ops remain compatible
- read-only `--account-id` behavior remains unchanged
- commit/append report contract from PAPER15-3E-4C is preserved

## Next MFU

- account-aware report/template generation for remaining paper review workflow
- optional `paper_default` root convergence strategy after operational validation

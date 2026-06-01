## Purpose

Add an official `init-account` bootstrap command for new non-default paper accounts.

## Scope / Non-scope

In scope:
- local non-default account bootstrap
- dry-run plan output
- guarded file creation under `outputs/paper_accounts/{account_id}`

Out of scope:
- Notion export or sync
- broker/API
- cloud runner
- `paper_default` migration

## Init Command Syntax

```cmd
python scripts\paper.py init-account --account-id paper_growth --initial-cash 100000 --currency USD --date 20260601 --dry-run --json
python scripts\paper.py init-account --account-id paper_growth --initial-cash 100000 --currency USD --date 20260601 --confirm-create
```

## Safety Policy

- non-default account only
- `paper_default` rejected
- default behavior is dry-run unless `--confirm-create` is provided
- overwrite is blocked
- `--allow-existing` is read/validate only

## Generated Directory Structure

- account root
- `reports/`
- `reviews/`
- `archive/`
- `config_snapshots/`
- `replay_diff/`

## Generated File Schema

- `paper_account_snapshot.csv`
  - seeded with one INIT row
- `paper_position_snapshot.csv`
  - header only
- `paper_execution_log.csv`
  - header only
- `paper_current_state_{YYYYMMDD}.json`
  - empty-position current state with init metadata

## paper_default Policy

- `init-account` cannot target `paper_default`
- no default-root migration is attempted

## Existing Account Policy

- existing initialized core files cause failure
- existing empty root is blocked by default
- `--allow-existing` only permits read/validate style inspection

## Multi-account Onboarding Support

Bootstrap removes the manual snapshot/current-state seed step and gives every new non-default account the same initial file contract.

## Future SOP Update Notes

- add operator steps for when to run `init-account`
- define when a newly bootstrapped account should move from `NO_PLAN` to first plan/commit workflow

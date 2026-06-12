# MFU-OPER9-19A EOD Preflight Account Scope Alignment

## Summary

OPER9-19A aligns `paper.py eod --account-id <account> --dry-run` preflight with the selected paper account root.

## Problem

`handle_eod()` ran EOD preflight before resolving `account_paths`. As a result, `core.paper_preflight_check.run_preflight(stage="eod")` received `account_paths=None` and used the legacy/default paper root.

For non-default accounts, this caused `eod::daily_action_plan_exists` to fail even when the target account had `daily_action_plan_YYYYMMDD.md` under its own account root.

## Change

`handle_eod()` now resolves account paths before preflight:

- dry-run: `build_paper_account_paths(args.account_id, create=False)`;
- commit path: `build_paper_account_paths(args.account_id, create=True)`;
- preflight is called through `_call_preflight(..., account_paths=account_paths)`;
- the EOD runner receives the same `account_paths`.

The `paper.py commit` shortcut continues to route through `handle_eod(commit=True)`, so it inherits the same account-aware preflight alignment. This was verified by unit test only; no commit command was executed.

## Scope Boundary

This MFU only fixes account scope for EOD preflight. It does not change no-action day roll-forward, terminal closure, ledger mutation policy, or EOD commit semantics.

No-action day EOD roll-forward and final terminal closure verification remain for OPER9-19B.

## Validation

Tests cover:

- non-default EOD dry-run preflight using `account_paths.daily_action_plan_path(date)`;
- preflight failure when the account root lacks the daily plan;
- commit-path handler setup preserving `create=True` before preflight without executing a real commit.

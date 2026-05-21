# MFU-PAPER11-8 Paper Operator Shortcuts

## Summary

- Added operator-facing shortcut commands to `scripts/paper.py`:
  - `prepare`
  - `preview`
  - `commit`
  - `review`
- Existing granular commands remain available:
  - `prepare-data`
  - `data-freshness`
  - `preflight`
  - `plan`
  - `eod`
  - `reports`
  - `review-template`
  - `review-validate`
  - `review-append`

## Shortcut Behavior

### `prepare`

```text
python scripts/paper.py prepare --date YYYYMMDD
python scripts/paper.py prepare --date YYYYMMDD --universe
python scripts/paper.py prepare --date YYYYMMDD --allow-warnings
```

Sequence:

1. `prepare-data`
2. `data-freshness`

Policy:

- `PASS` -> success
- `PASS_WITH_WARNINGS` -> fail by default
- `PASS_WITH_WARNINGS` + `--allow-warnings` -> success
- `FAIL` -> fail

Notes:

- `--universe` is forwarded only to `prepare-data`
- `prepare` does not run `plan`

### `preview`

```text
python scripts/paper.py preview --date YYYYMMDD
python scripts/paper.py preview --date YYYYMMDD --allow-warnings
```

Sequence:

1. `data-freshness`
2. `plan`
3. `eod --dry-run`

Policy:

- `PASS` -> continue
- `PASS_WITH_WARNINGS` -> fail by default
- `PASS_WITH_WARNINGS` + `--allow-warnings` -> continue
- `FAIL` -> fail

Notes:

- `preview` does not run `prepare-data`
- `preview` does not run EOD commit

### `commit`

```text
python scripts/paper.py commit --date YYYYMMDD
```

Sequence:

1. `eod --commit`

Notes:

- explicit commit-only shortcut
- no automatic chaining from `preview`
- no dry-run evidence enforcement in this MFU

### `review`

```text
python scripts/paper.py review
python scripts/paper.py review --allow-warnings
```

Sequence:

1. `reports`
2. `review-template`
3. `review-validate`

Notes:

- `review-append` is intentionally excluded
- reports warnings are blocking by default
- `--allow-warnings` relaxes only the reports-preflight gate

## Safety Notes

- No shortcut removes or replaces the granular commands.
- `preview` never escalates to commit.
- `review` never appends to the manual review log.
- `prepare` and `commit` remain explicit writer shortcuts.

## Out of Scope

- automatic EOD commit after preview
- automatic review append
- run-all / daily mega-command
- dry-run evidence enforcement before commit

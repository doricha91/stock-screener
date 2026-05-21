# MFU-PAPER11-9 Commit Safety Guard

## Summary

- Scope: add a same-date commit guard to the operator shortcut:
  - `python scripts/paper.py commit --date YYYYMMDD`
- Default behavior:
  - block commit when same-date paper snapshot artifacts already exist
- Explicit override:
  - `python scripts/paper.py commit --date YYYYMMDD --replace`

## Guard Scope

- Guard is applied to the operator shortcut `paper.py commit`.
- Guard is **not** applied to the lower-level diagnostic command `paper.py eod --date YYYYMMDD --commit`.
- Reason:
  - keep the shortcut safe by default
  - preserve the lower-level command for controlled diagnostics

## Same-Date Existence Criteria

The guard treats the commit as already existing if **any** of the following is true for the requested date:

1. `paper_account_snapshot.csv` contains `snapshot_date == YYYY-MM-DD`
2. `paper_position_snapshot.csv` contains `snapshot_date == YYYY-MM-DD`
3. `outputs/paper_test/paper_current_state_YYYYMMDD.json` exists

Evaluation order:

1. account snapshot CSV
2. position snapshot CSV
3. current-state JSON existence

## Behavior

### Default commit

```text
python scripts/paper.py commit --date 20260520
```

- if same-date snapshot exists:
  - block
  - print `--replace` guidance
  - do not call EOD commit
  - return exit code `1`

### Replace commit

```text
python scripts/paper.py commit --date 20260520 --replace
```

- if same-date snapshot exists:
  - allow execution to continue intentionally
  - delegate to existing EOD commit path
  - existing backup / replace policy remains in `run_paper_eod_update.py`

## CSV Parsing Policy

- Missing CSV file:
  - treated as no same-date snapshot
- CSV parse failure:
  - treated as guard error
  - commit is blocked
- Missing `snapshot_date` column:
  - treated as parse/format error
  - commit is blocked

## Out of Scope

- dry-run evidence enforcement
- preview success marker
- freshness evidence enforcement
- reports/review auto-run
- EOD commit internal replacement logic changes
- backup policy changes

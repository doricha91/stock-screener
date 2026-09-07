# ACCT-01D Account Isolation Evidence — Result

- Status: `PASS`
- D base (reviewed ACCT-01C local commit): `0da9b0f906f477613ee72e4fdcd0c6fa8d5d7c14`
- Branch: `acct-01d-account-isolation-evidence`
- Evidence time: 2026-09-07 (Asia/Seoul)
- Commit/push/merge: not performed for ACCT-01D.

## Result

ACCT-01D adds an isolated account-boundary regression test.  It creates canonical
`paper_alpha` and `paper_beta` roots plus a separate legacy root only beneath
pytest's temporary directory.  SHA-256 tree snapshots prove that a selected
writer/output changes only its intended canonical root; unrelated canonical and
legacy trees remain unchanged.

The test uses the existing initialized-account fixture, current-state writer,
state read provider, replay-diff output writer, and explicit legacy-read
resolver.  It does not use repository `outputs/` as a write target.

## D-2 targeted validation

| Check | Result |
| --- | --- |
| `tests/test_acct01d_isolation.py` | `7 passed` |
| ACCT-01B writer + ACCT-01C closure focused regression | `24 passed` |
| `python -m py_compile tests/test_acct01d_isolation.py` | PASS |
| `git diff --check` before D-3 bundle generation | PASS |

The initial D test attempt encountered a pytest shared-temp permission error;
the required rerun with an isolated `--basetemp` passed.  The initial focused
B/C collection lacked a market DB path in the isolated worktree; rerunning with
`STOCK_SCREENER_MARKET_DB` pointing read-only to the existing project DB passed.
No DB write occurred.

## D-3 ACCT-01 regression superset

The D-3 suite covered D isolation; A account path/guard/bootstrap/profile; B
writer closure; C read/report/export/replay closure; CLI account scope; status,
weekly status, benchmark, state-provider, report/review, replay, alert,
baseline, Notion-export and Daily Ops export paths.

- Result: `319 passed, 3 failed`.
- The three failures are the known `UNRELATED` prepare-data mock-signature
  nodes recorded in ACCT-01B/C evidence:
  - `tests/test_paper_cli.py::test_prepare_data_calls_existing_runner`
  - `tests/test_paper_cli.py::test_prepare_data_passes_skip_and_universe_flags`
  - `tests/test_paper_cli.py::test_prepare_data_does_not_call_eod_commit`
- Cause: legacy mocks omit the now-required `trade_date` and `account_id`
  keyword parameters.  No D-SCOPE or A/B/C-REGRESSION red node occurred.

Warnings were the upstream `pandas_ta` deprecation and isolated-worktree
`.pytest_cache` permission warning.  Full-repository pytest was not run by
design; this task requires the ACCT-01 regression superset rather than all tests.

## Boundary results

- A writer leaves B and legacy unchanged: PASS.
- B writer leaves A and legacy unchanged: PASS.
- Omitted configured-default and explicit A/B reads stay in canonical roots: PASS.
- Cross-account source and output paths fail closed: PASS.
- Replay output is created only in the selected canonical namespace: PASS.
- Explicit `paper_default` legacy read is allowed; non-default legacy read and
  legacy writer/output targets are rejected: PASS.
- Missing and partial roots fail without creation or repair: PASS.

## Scope and safety

- Production source changes: none.
- New persisted schema, migration, paper-default initialization/migration,
  legacy data copy, operational Paper state mutation, Notion write, DB write,
  broker action, commit, push, and merge: not performed.
- Final reviewer verdict is PASS. The three unrelated prepare-data mocks remain
  outside ACCT-01D scope.

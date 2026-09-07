# ACCT-01C Read, Report, Export, Replay Closure — Result Evidence

- Status: `PENDING_CHATGPT_REVIEW`
- Evidence time: `2026-09-07 +09:00`
- Reviewed ACCT-01B base: `797859586cbb7ba2e321f1f870f45d713c8c7176`
- Working branch: `acct-01c-read-report-export-replay-closure`
- Commit/push: not performed

## Result

ACCT-01C closes the read/report/export/replay account-path boundary without a migration or persisted-schema change. Omitted pure reads resolve the configured default canonical account root. Legacy reads require explicit opt-in and are allowed only for `paper_default`; no output-producing path may use that compatibility mode.

Weekly status, benchmark, report/review chains, Notion export CLI, replay/diff, baseline capture, alert report, drawdown, equity, audit, and preflight report output now require an initialized explicit canonical account context. They do not create an account root through generic `create=True`; output paths are constrained beneath the provided account root. State/replay paths reject cross-root artifacts, and snapshot account/date validation remains fail-closed.

## Changed source and tests

- Account read resolution and output guard: `core/paper_account_paths.py`, `core/paper_account_guard.py`.
- Read/status/output consumers: state/status/weekly/benchmark/alert/replay/Notion exporter modules and `scripts/paper.py`.
- Output scripts: replay/baseline, Notion export, report/review summaries, drawdown, equity, and audit.
- Contract and regression tests: ACCT-01C closure test; CLI/account-scope, report, benchmark, state-provider, replay, alert, baseline, export, and initialized-account fixture coverage.

The complete source/test diff from the reviewed base is recorded in the Changes Patch.

## Contract evidence

- Omitted pure read resolves configured canonical default; explicit non-default read resolves that account root.
- Silent `PAPER_TEST_DIR` and module-level legacy defaults were removed from normal C read/output selection.
- Explicit legacy-read is `paper_default`-only and read-only; legacy-read cannot be combined with output CLI commands.
- Output omission, absent/partial root, root mismatch, and source-artifact identity/date mismatch fail closed.
- Replay diff and baseline capture use `create=False` and initialized-account validation.
- No new persisted schema, migration, legacy data copy, operational state mutation, Notion API call, DB write, or broker action occurred.

## C-2 targeted validation (previous phase)

| Suite | Result |
| --- | --- |
| C contract + C-READ five + B writer | `29 passed` |
| Replay/alert/replay-wrapper/baseline | `68 passed` |
| Drawdown/equity/audit | `18 passed` |
| Notion export/Daily Ops export CLI | `81 passed` |
| Earlier C contract/diagnostic | `47 passed` |

## C-3 broad regression

| Broad group | Result |
| --- | --- |
| Account/read/status/weekly/benchmark/report/review and B writer contract | `254 passed` |
| Replay/alert/baseline, diagnostics, Notion export, and Daily Ops | `271 passed` |
| CLI writer/account contract and C-READ five | `74 passed`; C-READ five green |
| CLI account scope | `11 passed` |

The CLI group retains three known `UNRELATED` prepare-data mock-signature failures. They were already classified as unrelated in ACCT-01B Evidence and were not changed: `test_prepare_data_calls_existing_runner`, `test_prepare_data_passes_skip_and_universe_flags`, and `test_prepare_data_does_not_call_eod_commit`.

All focused/broad runs used the configured market DB read-only via `STOCK_SCREENER_MARKET_DB`; no project DB was modified. Warnings were the upstream `pandas_ta` deprecation and isolated-worktree `.pytest_cache` permission warning.

## Final checks

- Changed Python sources: `python -m py_compile` — PASS.
- `git diff --check` — PASS.
- Full repository pytest — intentionally not run; Phase 3 requires the ACCT-01 regression superset, not whole-repository execution.

## Remaining risks and boundaries

- The three prepare-data mock-signature failures remain outside ACCT-01C scope.
- ACCT-01D isolation smoke, `paper_default` migration/init, actual Notion export, Paper operational mutation, and DB writes were deliberately not run.
- Final acceptance remains ChatGPT review; ACCT-01 is not declared complete.

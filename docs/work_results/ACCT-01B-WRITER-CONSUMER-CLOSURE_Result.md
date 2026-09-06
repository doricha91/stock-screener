# ACCT-01B Writer Consumer Closure — Result Evidence

- Status: `PENDING_CHATGPT_REVIEW`
- Evidence time: `2026-09-06 20:15:48 +09:00`
- Base (reviewed ACCT-01A local commit): `383f42e9748cf98f070b179a0bee748cfdb7d471`
- Working branch: `acct-01b-writer-consumer-closure`
- Working tree: `C:\Users\inocha\AppData\Local\Temp\StockScreener_ACCT01B_20260906`
- B commit/push: not performed

## Result

The existing ACCT-01B implementation remains intact and the revision gaps are closed. B-scope writers require an explicit initialized `PaperAccountPaths` context (direct CLI callers require `--account-id`) or an already-frozen runbook context. Canonical writes resolve below `outputs/paper_accounts/<account_id>`; missing, empty, partially initialized, legacy, and cross-account targets fail closed without creating or repairing artifacts.

For a missing or incomplete non-default account, the error continues to identify the supported `init-account --confirm-create` path. For canonical `paper_default`, the error no longer recommends the unsupported `init-account --account-id paper_default`; it explicitly says that migration or separately approved initialization is required.

No new persisted schema or frozen-context format was introduced. Read/report/export/replay closure remains ACCT-01C scope, and migration/operational isolation remains ACCT-01D scope.

## Initialized-account decision

The guard reuses the artifacts produced by the existing account bootstrap. A root is initialized only when all of the following are regular files:

- `paper_account_snapshot.csv`
- `paper_position_snapshot.csv`
- `paper_execution_log.csv`
- at least one `paper_current_state_YYYYMMDD.json`

A directory alone is insufficient. An invalidly named current-state file is insufficient. Validation is read-only and does not create the root, missing files, or replacement artifacts. The normal non-default `init-account --confirm-create` result passes this guard.

## Changed writer surfaces

- State/artifact writers: account snapshot, current-state snapshot, position snapshot, execution log, manual execution commit, manual review append/log.
- Direct orchestration: daily plan, EOD update, execution-log reset, and `paper.py` commit/plan/eod/review-append handlers.
- Import/sync writers: Notion execution/review import and execution/review status sync.
- Runbook writer path: execution reconciliation preview consumes the initialized frozen account root.
- Revision tests: initialization/dead-end cases plus contract-aware legacy writer fixtures.

## Removed legacy fallbacks and generic creation

- Removed `account_paths is None -> PAPER_TEST_DIR` write selection from B writer surfaces.
- Direct writer omission no longer selects `paper_default`; direct writer CLIs reject missing `--account-id`.
- Removed generic `create=True` from execution/review import, execution/review status sync, B writer handlers, and runbook reconciliation writer paths.
- The remaining `create=True` calls in `paper.py` are read/report/review-template/validation compatibility paths and remain ACCT-01C scope.
- Existing artifact identity/date validation remains active before replacement or append.

## Validation evidence

### Initialization and B contract matrix

```text
python -m pytest tests/test_acct01b_writer_consumer_closure.py -q --basetemp <isolated-temp>
```

Result: `17 passed, 2 warnings`. This includes the existing ten B contract cases and the revision cases for missing non-default, missing `paper_default`, empty root, partial bootstrap, normal bootstrap acceptance, and validation-no-create behavior.

### Legacy compatibility sweeps

The same three broad groups that exposed the pre-revision failures were rerun.

| Group | Initial result | Classification | Final result |
| --- | --- | --- | --- |
| Low-level storage/snapshot writers | `14 failed, 39 passed` | `B-WRITER 14` | `53 passed` |
| EOD/daily-plan writers | `9 failed, 46 passed` | `B-WRITER 9` | `55 passed` |
| Paper CLI compatibility | `32 failed, 56 passed` | `B-WRITER 24`, `C-READ 5`, `UNRELATED 3` | `B-WRITER 24` fixed; rerun `8 failed, 80 passed` with only the unchanged C/Unrelated nodes remaining |

Totals from the original red nodes: `55 total = B-WRITER 47 + C-READ 5 + UNRELATED 3`. All 47 B-WRITER nodes are green. No failing node was hidden by removing it from a curated command.

The complete node-by-node classification is in Review Evidence.

### Existing ACCT-01B regression

The previous focused regression categories were rerun as a strict superset covering the B contract matrix, manual execution/review, PAPER15, execution/review import and sync, reconciliation/recovery, and Stage B/D/E runner paths.

Initial revision run: `36 failed, 286 passed`; all 36 failures were test fixtures that represented a directory or partial root as initialized. Those fixtures were changed to seed the existing bootstrap core-artifact contract.

Final result: `322 passed, 2 warnings in 30.79s`.

The prior A regression pair (`test_paper_manual_execution_commit.py` and `test_paper15_3e_4d_import_commit_sync_contract.py`) is included in that run; focused reruns also produced `24 passed` for execution/review commit and `4 passed` for PAPER15.

### Additional validation

- `python -m py_compile` on all 19 changed source modules plus the revision helper and contract module: PASS.
- `git diff --check <A-base> -- core scripts tests`: PASS (recorded after final patch generation).
- Static B-writer scan: no generic `create=True` in the five import/sync/reconciliation targets or B writer handler blocks.
- Direct CLI omission and canonical mapping cases remain covered by the B contract matrix.

One diagnostic EOD/plan run was mistakenly pointed at `outputs/backtest_log.db`; four accounting tests failed because that database has no `daily_price` table. It was not treated as a product result. The command was rerun read-only against the configured `outputs/market_data.db` and finished `55 passed`. No database content was modified.

Warnings were an upstream `pandas_ta` deprecation warning and inability to write `.pytest_cache` in the isolated worktree. Explicit writable `--basetemp` paths were used for test temporary data.

## Safety and scope confirmation

- No Notion API call or write was performed.
- No Paper Stage/Gate/wrapper or operational state mutation was performed.
- No project DB write, migration, or schema change was performed; `outputs/market_data.db` was read only by tests.
- No broker/order action was performed.
- No dependency, persisted schema, ROADMAP, ACCT-01C, or ACCT-01D change was made.
- The original dirty `gemini_cli_update` worktree was not modified, stashed, reset, cleaned, or committed.

## Remaining risks

- Five `C-READ` CLI expectations and three unrelated prepare-data mock-signature tests remain red and unchanged; they are listed in Review Evidence.
- Read/report/export/replay consumers may still use legacy compatibility until ACCT-01C.
- Canonical `paper_default` is intentionally not auto-initialized or migrated by this revision.
- Operational isolation was not smoke-tested because it is prohibited ACCT-01D scope.
- Ten `.test_tmp*` directories created by early pytest invocations remain untracked because pytest removed their object-level ACLs and explicit cleanup attempts were denied. They are outside `Changes.patch` and contain only isolated test data.
- Final acceptance belongs to ChatGPT review; ACCT-01 as a whole is not marked complete.

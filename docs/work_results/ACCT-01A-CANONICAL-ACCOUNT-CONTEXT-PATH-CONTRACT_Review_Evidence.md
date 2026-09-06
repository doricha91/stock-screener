# ACCT-01A Canonical Account Context / Path Contract Review Evidence

## Review target

- Base SHA: `6f1d420182a3741c39ea61de09e73421b81baf9a`
- Branch: `acct-01a-account-context-contract`
- Worktree: `C:\Users\inocha\AppData\Local\Temp\StockScreener_ACCT01A_20260905`
- Exact changes: `docs/work_results/ACCT-01A-CANONICAL-ACCOUNT-CONTEXT-PATH-CONTRACT_Changes.patch`
- Review scope: central resolver/guard contract, direct status expectation, tests, and ACCT-01B/C/D inventory

## Acceptance Criteria

| Criterion | Status | Evidence |
| --- | --- | --- |
| Canonical root is `outputs/paper_accounts/<account_id>` | PASS | Resolver implementation and `tests/test_paper_account_paths.py` |
| Omitted read account uses configured default profile | PASS | `resolve_paper_account_profile(None)` path and focused test |
| Normal `paper_default` read does not silently fall back to legacy | PASS | Resolver default is `allow_legacy_default=False`; explicit test |
| Legacy read requires explicit compatibility | PASS | Flag and explicit `account_root` edge tests |
| Legacy compatibility is read-only | PASS | Legacy plus `create=True` raises; writer guard denies legacy-marked context |
| Omitted direct writer account is rejected | PASS | `resolve_writer_account_context(None)` raises; guard test |
| Explicit canonical default and opted-in non-default writer contexts are handled | PASS | Writer guard tests |
| Path containment and non-default-to-legacy target rejection are tested | PASS | Writer guard containment tests |
| Existing init command remains normal creation owner | PASS | Existing bootstrap/init CLI tests: 34 passed across profile/bootstrap/init groups |
| Generic `create=True` callers are inventoried | PASS | Paired Result Evidence caller table |
| Persisted schema remains unchanged | PASS | Exact patch contains only resolver/guard behavior and tests |
| Exact patch contains all changed source/test files and no Evidence/DB/output | PASS | Five `diff --git` headers; reverse apply check and file-list check |
| Focused ACCT-01A test bundle succeeds | PASS | 64 passed |
| Every affected-suite test succeeds | FAIL | 670 passed, 14 failed; all 14 reproduced at Base SHA |
| Base comparison reproduces affected-suite failure set | PASS | Same 14 node IDs failed at Base SHA; 660 passed |
| Actual Paper operating isolation is established | NOT VERIFIED | Operational mutation/smoke prohibited; ACCT-01D |
| Actual legacy data migration readiness is established | NOT VERIFIED | Migration and operating-data inspection not performed |
| Notion/broker integration behavior is established | NOT VERIFIED | External writes and broker/order prohibited |
| Consumer-wide writer closure is established | NOT VERIFIED | ACCT-01B remains |
| Consumer-wide read/export/replay closure is established | NOT VERIFIED | ACCT-01C remains |
| No implementation file was additionally modified during evidence task | PASS | Before/after source/test blob hashes match |

## Observed implementation

1. `resolve_paper_account_root()` and `build_paper_account_paths()` default `allow_legacy_default` to false.
2. Configured default resolution continues to reuse `resolve_paper_account_profile(None)`.
3. Explicit legacy compatibility is limited to `paper_default`, requires the compatibility flag, and cannot be combined with `create=True`.
4. `resolve_writer_account_context()` requires an explicit account id and resolves with legacy compatibility disabled.
5. `guard_paper_writer_account()` refuses any diagnostic context marked `legacy_default_used`.
6. Generic canonical `create=True` remains temporarily for the callers inventoried in Result Evidence.

## Test evidence

### Focused tests

Command:

```powershell
$env:STOCK_SCREENER_MARKET_DB='D:\python\StockScreener\outputs\market_data.db'
pytest tests/test_paper_account_paths.py tests/test_paper_account_guard.py tests/test_paper_account_profile.py tests/test_paper_account_bootstrap.py tests/test_paper_cli_init_account.py tests/test_paper_status_account_scope.py -q --basetemp C:\Users\inocha\AppData\Local\Temp\acct01a_final_pytest
```

Result:

```text
64 passed, 1 dependency deprecation warning
```

The DB environment variable was used only to satisfy `scripts.paper` import. No DB writer or migration command was run.

### Affected tests

Task implementation command:

```powershell
$env:STOCK_SCREENER_MARKET_DB='D:\python\StockScreener\outputs\market_data.db'
$testFiles=@(rg -l 'paper_account_paths|paper_account_guard|resolve_writer_account_context|guard_paper_writer_account|build_paper_account_paths|resolve_paper_account_root' tests -g '*.py')
pytest $testFiles -q --basetemp C:\Users\inocha\AppData\Local\Temp\acct01a_all_direct_pytest
```

Result:

```text
40 test files
670 passed, 14 failed, 1 warning
```

Base SHA comparison command, run in a separate detached clean worktree:

```powershell
$env:STOCK_SCREENER_MARKET_DB='D:\python\StockScreener\outputs\market_data.db'
$testFiles=@(rg -l 'paper_account_paths|paper_account_guard|resolve_writer_account_context|guard_paper_writer_account|build_paper_account_paths|resolve_paper_account_root' tests -g '*.py')
pytest $testFiles -q --tb=line --basetemp C:\Users\inocha\AppData\Local\Temp\acct01a_baseline_direct_pytest
```

Base result:

```text
40 test files
660 passed, 14 failed, 1 warning
```

The implementation has ten additional tests in the same selected files. The failing node set is identical between the implementation and Base SHA.

### Failure-by-failure comparison

| # | Test node ID | Core failure in task run | ACCT-01A relation | Base reproduction |
| ---: | --- | --- | --- | --- |
| 1 | `tests/test_daily_plan_json_sidecar.py::test_run_paper_daily_plan_passes_official_sidecar_metadata` | `ValueError: Non-default account initial_cash is missing` | No changed resolver/guard assertion; fixture snapshot lacks `initial_cash` | PASS — same node/message family |
| 2 | `tests/test_mfu_safe1_end_to_end.py::test_normal_cap_daily_plan_preview_commit_end_to_end` | Snapshot CSV missing required columns | Not introduced by ACCT-01A; snapshot schema fixture failure | PASS — same node/missing-columns failure |
| 3 | `tests/test_mfu_safe1_end_to_end.py::test_over_cap_recovery_daily_plan_preview_commit_end_to_end` | Snapshot CSV missing required columns | Not introduced by ACCT-01A; snapshot schema fixture failure | PASS — same node/missing-columns failure |
| 4 | `tests/test_paper15_3e_4d_import_commit_sync_contract.py::test_execution_preview_commit_sync_contract_for_paper_default_legacy_row` | Snapshot path outside expected legacy account root | Subject-adjacent legacy writer gap, but not introduced by this diff | PASS — same node/path-mismatch failure |
| 5 | `tests/test_paper15_3e_4d_import_commit_sync_contract.py::test_non_default_execution_contract_keeps_account_namespace_and_syncs_from_account_root` | Snapshot CSV missing required columns | ACCT-01B consumer fixture/path chain; not introduced by this diff | PASS — same node/missing-columns failure |
| 6 | `tests/test_paper15_3h_non_default_daily_ops_smoke.py::test_non_default_daily_ops_smoke_chain` | Assertion: actual `COMMITTED`, expected `REVIEW_READY` | Daily Ops lifecycle semantics, not central A contract | PASS — same node/assertion |
| 7 | `tests/test_paper_cli_writer_account_guard.py::test_plan_explicit_dates_pass_data_and_trade_dates` | Mock rejected unexpected `enforce_asof_contract` keyword | Existing mock signature mismatch | PASS — same node/TypeError |
| 8 | `tests/test_paper_manual_execution_commit.py::test_warning_preview_commits_with_allow_warnings` | `FileNotFoundError` under `outputs/dev_backups_manual_commit` | Legacy writer backup fixture; ACCT-01B gap | PASS — same node/backup-path failure |
| 9 | `tests/test_paper_manual_execution_commit.py::test_sell_commits_negative_shares` | `FileNotFoundError` under `outputs/dev_backups_manual_commit` | Legacy writer backup fixture; ACCT-01B gap | PASS — same node/backup-path failure |
| 10 | `tests/test_paper_manual_execution_commit.py::test_commit_preserves_execution_log_schema` | `FileNotFoundError` under `outputs/dev_backups_manual_commit` | Legacy writer backup fixture; ACCT-01B gap | PASS — same node/backup-path failure |
| 11 | `tests/test_paper_manual_execution_commit.py::test_commit_succeeds_when_current_state_did_not_preexist` | `FileNotFoundError` under `outputs/dev_backups_manual_commit` | Legacy writer backup fixture; ACCT-01B gap | PASS — same node/backup-path failure |
| 12 | `tests/test_paper_manual_execution_commit.py::test_existing_current_state_is_backed_up` | `FileNotFoundError` under `outputs/dev_backups_manual_commit` | Legacy writer backup fixture; ACCT-01B gap | PASS — same node/backup-path failure |
| 13 | `tests/test_paper_manual_execution_commit.py::test_current_state_save_failure_rolls_back` | `FileNotFoundError` under `outputs/dev_backups_manual_commit` before injected failure | Legacy writer backup fixture; ACCT-01B gap | PASS — same node/backup-path failure |
| 14 | `tests/test_paper_manual_execution_commit.py::test_v2_outcome_filter_commits_only_trade_bearing_candidate` | `FileNotFoundError` under `outputs/dev_backups_manual_commit` | Legacy writer backup fixture; ACCT-01B gap | PASS — same node/backup-path failure |

### Other validation

- `python -m py_compile core/paper_account_paths.py core/paper_account_guard.py`: succeeded.
- `git diff --check`: no whitespace errors; LF-to-CRLF notices only.
- Exact patch contains five source/test diff headers and applies in reverse against the task worktree.
- Test-created temporary directories were removed. The task-worktree `outputs/backtest_log.db` blob stayed identical to HEAD: `4257291614663b6d167ec081f4691b393800c720`.

## Potential regression

- Direct callers omitting `account_id` from the writer guard now receive `ValueError`; ACCT-01B must adapt command-level handling and frozen-context paths.
- Callers relying on silent `paper_default` legacy fallback now resolve an uncreated canonical path unless they explicitly request legacy read compatibility.
- Existing no-context helpers still use or create `PAPER_TEST_DIR`.
- All 14 affected-suite failures pre-exist at Base SHA, but seven expose the unresolved legacy writer/backup coupling assigned to ACCT-01B.

## Compatibility impact

| Previous behavior | New central behavior | Temporary compatibility |
| --- | --- | --- |
| Omitted/default read could silently select `outputs/paper_test` | Configured default resolves to its canonical root | Explicit `allow_legacy_default=True` read |
| Omitted direct writer became `paper_default` | Omitted direct writer fails | Frozen runbook context remains conceptually valid |
| Legacy `paper_default` writer could be approved | Legacy-marked context is denied | None for write |
| Generic `create=True` could create selected root | Canonical creation remains temporarily; legacy creation fails | Inventoried for B/C removal |

## Remaining legacy dependencies

- `core/paths.py` singleton helpers and import-time `PAPER_TEST_DIR` creation.
- Snapshot/state/log/review/EOD no-context writer fallbacks.
- Status/weekly/report/performance/audit/generator no-context read fallbacks.
- Notion exporter legacy adapter.
- Replay, daily ops, alert, baseline, runbook compatibility paths.

## Items requiring ChatGPT/user review

1. Whether immediate `ValueError` for an omitted direct writer is the desired A-stage boundary.
2. Whether transitional canonical `create=True` is sufficiently constrained until B/C.
3. Whether the seven reproduced legacy backup failures should be explicit ACCT-01B acceptance inputs.
4. Whether the PAPER15 legacy-row path mismatch needs a separate B regression fixture.
5. Confirmation that migration and operational isolation evidence remain deferred to D.

## Verdict

`PENDING_CHATGPT_REVIEW`

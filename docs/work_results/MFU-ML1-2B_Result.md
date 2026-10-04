# MFU-ML1-2B Result Evidence

## Scope

- Task: `MFU-ML1-2B_RUNTIME_STRATEGY_UNIVERSE_BINDING`
- Phase: implementation, focused regression, and review bundle
- Base / HEAD: `f9ce53662e6cacab8df642895bfd2e83df40bf46`
- Branch: detached isolated worktree
- Worktree: `C:\Users\inocha\AppData\Local\Temp\StockScreener_MFU_ML1_2B_20261003`
- Operational mutation: **NO**
- Commit / push: **NO / NO**

## Implemented behavior

- Added a pure per-call runtime binding assembler in `core/paper_runtime_binding.py`.
- Runtime config now derives strategy values from frozen `effective_strategy_base`, applies only the frozen active-regime overlay, and reapplies/verifies frozen shared constraints.
- The official Stage A command pins its current runbook state path. The plan entrypoint loads that exact state, verifies account/data/trade context, and fails closed on frozen/current binding drift.
- Versioned direct account calls resolve a call-local current binding. Legacy profile paths retain their prior unbound behavior.
- `shared_snapshot` and explicit-symbol universe definitions now drive the actual screener ticker stream for bound accounts.
- Explicit symbols with fewer than the screener's required 200 as-of rows are recorded as `missing_market_data`; they are not silently discarded.
- Existing holdings, hedge symbols, and the benchmark are recorded in the managed-symbol stream independently of entry eligibility. Existing holding valuation/risk/exit paths remain unchanged.
- The screener accepts optional per-call runtime parameters and weights. No module-global config or strategy constants are mutated.
- Daily Plan JSON and config snapshot evidence record strategy/universe references, frozen digest, effective base, active regime and overlay, effective runtime strategy, shared policy, requested/materialized/excluded universe, and preserved holdings.
- Existing pinned runtime evidence, when present, is cross-checked before reuse. Older snapshots without this optional field remain readable and are not migrated.

## Changed source and tests

- `core/paper_runtime_binding.py`
  - `resolve_runtime_binding`
  - `build_runtime_config`
  - `validate_runtime_consumption`
  - `validate_pinned_runtime_evidence`
  - `record_runtime_universe`
- `core/daily_plan_generator.py`
  - `materialize_explicit_entry_universe`
  - bound runtime config/universe selection in `generate_daily_plan`
  - runtime evidence in JSON sidecar and config snapshot calls
- `core/paper_config_snapshot.py`
  - optional `runtime_binding` evidence serialization
- `screener/screener.py`
  - optional per-call `runtime_config` in preparation, scoring, thresholding, and `run_screener`
- `scripts/run_paper_daily_plan.py`
  - frozen runbook state load/context verification and binding injection
- `scripts/paper.py`
  - internal `--runbook-state-json` forwarding
- `scripts/runbook_command_registry.py`
  - Stage A Daily Plan state-path argument
- `scripts/runbook_stage_runner.py`
  - deterministic current state-path rendering
- `tests/test_ml1_2b_runtime_binding.py`
  - 17 focused runtime, universe, isolation, evidence, drift, and runbook wiring tests
- `docs/TRD/mfu_ml1_2b_runtime_strategy_universe_binding.md`
  - runtime flow, precedence, universe, evidence, and scope-boundary contract

## Validation executed

### Targeted ML1-2B

```text
$env:STOCK_SCREENER_MARKET_DB='D:\python\StockScreener\outputs\market_data.db'; python -m pytest -q -p no:cacheprovider tests/test_ml1_2b_runtime_binding.py
17 passed, 1 third-party deprecation warning
```

### Daily Plan / config / screener / Stage A regression

```text
$env:STOCK_SCREENER_MARKET_DB='D:\python\StockScreener\outputs\market_data.db'; python -m pytest -q -p no:cacheprovider tests/test_paper_daily_plan_generation.py tests/test_paper_daily_plan_universe_asof.py tests/test_paper_config_snapshot.py tests/test_screener_asof_cutoff.py tests/test_runbook_stage_runner.py
65 passed, 1 third-party deprecation warning
```

### ML1-2A frozen identity / runbook / recovery / NTG compatibility

```text
$env:STOCK_SCREENER_MARKET_DB='D:\python\StockScreener\outputs\market_data.db'; python -m pytest -q -p no:cacheprovider tests/test_ml1_2a_binding_fresh.py tests/test_runbook_state.py tests/test_runbook_recovery.py tests/test_runbook_day_rollover.py tests/test_operational_no_trade_gap.py tests/test_operational_gap_recovery.py
313 passed
```

### Additional affected Daily Plan regression

```text
$env:STOCK_SCREENER_MARKET_DB='D:\python\StockScreener\outputs\market_data.db'; python -m pytest -q -p no:cacheprovider tests/test_paper_daily_plan_screener_cutoff.py tests/test_paper_daily_plan_market_log_policy.py tests/test_paper_daily_plan_candidates.py tests/test_paper_cli_writer_account_guard.py tests/test_paper20_capture_daily_plan_baseline.py tests/test_daily_plan_switch_symbol_mapping.py tests/test_daily_plan_long_position_cap_integration.py tests/test_daily_plan_long_position_cap.py tests/test_daily_plan_json_sidecar.py
55 passed, 1 PRE-EXISTING failure, 1 third-party deprecation warning
```

The pre-existing failure is `test_run_paper_daily_plan_passes_official_sidecar_metadata`. At base SHA, `run_paper_daily_plan` already requires a fully initialized account root, while this unchanged test creates only `paper_account_snapshot.csv`. The failure occurs in the unchanged account guard before any ML1-2B code. `core/paper_account_guard.py` and this test have no task diff.

### Static validation

```text
python -m py_compile core\paper_runtime_binding.py core\daily_plan_generator.py core\paper_config_snapshot.py screener\screener.py scripts\run_paper_daily_plan.py scripts\paper.py scripts\runbook_command_registry.py scripts\runbook_stage_runner.py tests\test_ml1_2b_runtime_binding.py
PASS

git diff --check
PASS (line-ending notices only)

git apply --check --reverse docs/work_results/MFU-ML1-2B_Changes.patch
PASS
```

Changes patch SHA-256: `5DDA90B30F673BEF745F9BB7F9A02FC0337EF68E242CD04A5FD14AB629F7F1B8`

The first test attempt without `STOCK_SCREENER_MARKET_DB` produced four collection errors because the clean worktree does not contain the ignored market DB. Subsequent tests used the root DB through the documented read-only environment override. No DB write or market refresh was performed.

## Scope exclusions preserved

- Production paper account/profile activation: not performed
- Fresh account prepare/create/resume: not performed
- Bootstrap seed writer: unchanged
- Shared market refresh and Stage A refresh/consume architecture: unchanged
- Operational runbook lifecycle execution: not performed
- Parallel execution / multi-strategy account behavior: not added
- Position/trade strategy ownership: unchanged
- Dirty root alignment/deployment/scheduler changes: not performed
- Backtest/optimizer behavior: unchanged and not executed
- ML1-3/4/5: not started

## Remaining risk

- The repository still contains the pre-existing incomplete-bootstrap sidecar test fixture described above.
- Production activation remains a separately authorized phase. This change only wires frozen/versioned bindings into the runtime path when such a binding is present.
- No full repository pytest was run because the task requested impact-based validation and the focused/broad affected suites completed.

## Status

Final `git status --short`:

```text
 M core/daily_plan_generator.py
 M core/paper_config_snapshot.py
 M screener/screener.py
 M scripts/paper.py
 M scripts/run_paper_daily_plan.py
 M scripts/runbook_command_registry.py
 M scripts/runbook_stage_runner.py
?? core/paper_runtime_binding.py
?? docs/TRD/mfu_ml1_2b_runtime_strategy_universe_binding.md
?? docs/work_results/MFU-ML1-2B_Changes.patch
?? docs/work_results/MFU-ML1-2B_Changes_Stat.txt
?? docs/work_results/MFU-ML1-2B_Result.md
?? docs/work_results/MFU-ML1-2B_Review.md
?? docs/work_results/MFU-ML1-2B_Synthetic_Runtime.json
?? tests/test_ml1_2b_runtime_binding.py
```

```text
Strategy runtime injection: PASS
Regime runtime overlay: PASS
Universe runtime binding: PASS
Existing holdings preservation: PASS
Runtime/frozen cross-check: PASS
Account A isolation: PASS
Account B isolation: PASS
Operational mutation: NO
Commit: NO
Push: NO
ML1-3: NOT STARTED
REVIEW STATUS: PENDING_CHATGPT_REVIEW
```

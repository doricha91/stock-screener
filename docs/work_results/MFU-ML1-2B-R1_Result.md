# MFU-ML1-2B-R1 Result Evidence

## Scope

- Task: `MFU-ML1-2B-R1_RUNTIME_CONSUMER_CLOSURE`
- Phase: focused revision, regression validation, and review bundle
- Base / HEAD: `f9ce53662e6cacab8df642895bfd2e83df40bf46`
- Branch: detached isolated worktree
- Worktree: `C:\Users\inocha\AppData\Local\Temp\StockScreener_MFU_ML1_2B_20261003`
- Operational mutation: **NO**
- Commit / push: **NO / NO**
- ML1-3: **NOT STARTED**

## Implemented closure

- Bound screener calls now prepare volume indicators and score the complete ten-signal ensemble: `turtle`, `rsi`, `sma`, `bbands`, `macd`, `bbs`, `dema`, `obv`, `mfi`, and `vol_spike`.
- Runtime scoring weights are resolved per call. No module-global config or weight object is mutated.
- Legacy/unbound screener calls retain the original seven-weight defaults and immediate threshold behavior.
- Bound Daily Plan calls set `apply_entry_filter=False`, retain the complete signal row, recompute the ten-weight ensemble score, add positive-RS weight, and apply the final threshold in Daily Plan.
- The redundant function-local `compute_candidate_score` import was removed because activating signal-column recomputation exposed its Python local-name shadowing of the module import.
- Explicit-universe materialization records `missing_market_data` only for `None`, empty, or below-minimum data. Unexpected read, permission, DB, or internal exceptions now propagate and abort plan generation.
- The TRD now identifies Daily Plan as the bound path's final scoring/threshold authority and records the market-data exception boundary.

## R1 changed files and symbols

- `screener/screener.py`
  - `RUNTIME_STRATEGY_WEIGHTS`
  - `_prepare_data_for_ensemble`
  - `build_screener_results(..., apply_entry_filter=True)`
- `core/daily_plan_generator.py`
  - `materialize_explicit_entry_universe`
  - bound `generate_daily_plan` screener invocation and existing final score stage
  - removal of shadowing local import
- `tests/test_ml1_2b_runtime_binding.py`
  - complete runtime score, A/B isolation, legacy scoring, deferred threshold, final selection, and fail-closed exception regressions
- `docs/TRD/mfu_ml1_2b_runtime_strategy_universe_binding.md`
  - final score/threshold SSOT and exception behavior

## Validation executed

All pytest runs used the existing root market DB through read-only environment override:

```text
$env:STOCK_SCREENER_MARKET_DB='D:\python\StockScreener\outputs\market_data.db'
```

### R1 targeted

```text
python -m pytest -q -p no:cacheprovider tests/test_ml1_2b_runtime_binding.py
27 passed, 1 third-party deprecation warning
```

The first attempt omitted the documented DB environment override and stopped during collection with `FileNotFoundError`. It performed no test or operational mutation. The corrected command above passed.

### Daily Plan / config / screener / Stage A focused regression

```text
python -m pytest -q -p no:cacheprovider tests/test_paper_daily_plan_generation.py tests/test_paper_daily_plan_universe_asof.py tests/test_paper_config_snapshot.py tests/test_screener_asof_cutoff.py tests/test_runbook_stage_runner.py
65 passed, 1 third-party deprecation warning
```

### ML1-2A / runbook / recovery / NTG compatibility

```text
python -m pytest -q -p no:cacheprovider tests/test_ml1_2a_binding_fresh.py tests/test_runbook_state.py tests/test_runbook_recovery.py tests/test_runbook_day_rollover.py tests/test_operational_no_trade_gap.py tests/test_operational_gap_recovery.py
313 passed
```

### Additional affected Daily Plan regression

```text
python -m pytest -q -p no:cacheprovider tests/test_paper_daily_plan_screener_cutoff.py tests/test_paper_daily_plan_market_log_policy.py tests/test_paper_daily_plan_candidates.py tests/test_paper_cli_writer_account_guard.py tests/test_paper20_capture_daily_plan_baseline.py tests/test_daily_plan_switch_symbol_mapping.py tests/test_daily_plan_long_position_cap_integration.py tests/test_daily_plan_long_position_cap.py tests/test_daily_plan_json_sidecar.py
55 passed, 1 PRE-EXISTING failure, 1 third-party deprecation warning
```

The sole failure remains `test_run_paper_daily_plan_passes_official_sidecar_metadata`: its fixture creates only the account snapshot while the existing writer guard requires all bootstrap core artifacts. `core/paper_account_guard.py` and `tests/test_daily_plan_json_sidecar.py` have no diff from base `f9ce536...`; the prior ML1-2B evidence also records the same base reproduction. R1 does not change this guard or fixture.

### Static validation

```text
python -m py_compile screener\screener.py core\daily_plan_generator.py tests\test_ml1_2b_runtime_binding.py
PASS

git diff --check
PASS (line-ending notices only)

git apply --check --reverse docs/work_results/MFU-ML1-2B-R1_Delta.patch
PASS
```

Delta patch SHA-256: `51AC5302CA6B6D6C9AA48852DB67D22D3182960B3C01C01F202E67D6E8C9F558`

No full repository pytest was run because the task requires impact-based validation and no new unexpected failure remained after the focused suites.

## Preserved boundaries

- Binding schema/digest, account profile schema, and runbook identity: unchanged
- Fresh-account contract and bootstrap seed writer: unchanged
- Market refresh, execution, and ledger behavior: unchanged
- Multi-strategy ownership, parallel execution, deployment/local alignment: not started
- Existing holdings, explicit/shared universe, frozen/current drift, pinned evidence, and shared constraints: preserved by the 313-test compatibility suite and focused Daily Plan suites
- Production data and DB writes: not performed

## Remaining risk

- The pre-existing incomplete-bootstrap sidecar fixture remains failing and outside R1 scope.
- Production activation and operational runtime execution remain separately authorized work.

## Status

```text
Finding 1 — complete runtime scoring weights:
RESOLVED

Finding 1 — premature threshold:
RESOLVED

Finding 2 — unexpected market-data exception:
RESOLVED

A/B scoring isolation:
PASS

Legacy compatibility:
PASS

ML1-2A/runbook/recovery/NTG:
PASS

Operational mutation:
NO

Commit:
NO

Push:
NO

ML1-3:
NOT STARTED

REVIEW STATUS:
READY_FOR_INDEPENDENT_REVIEW
```

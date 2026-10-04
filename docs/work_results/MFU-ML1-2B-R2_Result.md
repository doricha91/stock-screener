# MFU-ML1-2B-R2 Result Evidence

## Scope

- Task: `MFU-ML1-2B-R2_PANIC_ENTRY_GATE_PRESERVATION`
- Phase: focused revision, regression validation, and review bundle
- Base / HEAD: `f9ce53662e6cacab8df642895bfd2e83df40bf46`
- Delta baseline: uncommitted `ML1-2B + ML1-2B-R1` state
- Branch: detached isolated worktree
- Worktree: `C:\Users\inocha\AppData\Local\Temp\StockScreener_MFU_ML1_2B_20261003`
- Operational mutation: **NO**
- Commit / push: **NO / NO**
- ML1-3: **NOT STARTED**

## Implemented closure

- Daily Plan's final buy predicate now reuses `core.decision_core.is_enterable_candidate()` for the shared regime/score gate and retains the existing positive-RS requirement.
- The existing two-argument helper API remains compatible through a default non-PANIC regime.
- Final formatted candidates pass the actual runtime regime into the predicate.
- Switching candidates use the same final regime-aware predicate and switching evaluation is skipped when that eligible set is empty.
- In `PANIC`, strategy-entry and `SWITCH_IN` BUY paths are blocked even for high-score, positive-RS candidates.
- Holding valuation, score evaluation, trailing-stop, SELL, risk, hedge, and position-management paths remain active.
- R1's deferred preliminary threshold and complete ten-weight-plus-RS final scoring remain unchanged.

## R2 changed files and symbols

- `core/daily_plan_generator.py`
  - `is_buy_signal_candidate`
  - `filter_switch_candidates_for_daily_plan`
  - final candidate formatting and switching call sites in `generate_daily_plan`
- `tests/test_ml1_2b_runtime_binding.py`
  - PANIC/BULL/BEAR final gate regression
  - PANIC/BULL switching eligibility regression
  - bound PANIC end-to-end BUY prohibition with holding SELL preservation
- `docs/TRD/mfu_ml1_2b_runtime_strategy_universe_binding.md`
  - regime hard gate ordering and PANIC management boundary

`screener/screener.py` required no R2 change.

## Validation executed

All pytest runs used the existing root market DB through a read-only environment override:

```text
$env:STOCK_SCREENER_MARKET_DB='D:\python\StockScreener\outputs\market_data.db'
```

### ML1-2B targeted

```text
python -m pytest -q -p no:cacheprovider tests/test_ml1_2b_runtime_binding.py
32 passed, 1 third-party deprecation warning
```

### Daily Plan / config / screener / Stage A / switching focused regression

```text
python -m pytest -q -p no:cacheprovider tests/test_paper_daily_plan_generation.py tests/test_paper_daily_plan_universe_asof.py tests/test_paper_config_snapshot.py tests/test_screener_asof_cutoff.py tests/test_runbook_stage_runner.py tests/test_paper_switching_parity.py
71 passed, 1 third-party deprecation warning
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

The sole failure remains `test_run_paper_daily_plan_passes_official_sidecar_metadata`: its incomplete fixture is rejected by the unchanged bootstrap writer guard before ML1-2B/R1/R2 logic runs. R2 does not change the guard or fixture.

### Static validation

```text
python -m py_compile core\daily_plan_generator.py tests\test_ml1_2b_runtime_binding.py
PASS

git diff --check
PASS (line-ending notices only)

git apply --check --reverse docs/work_results/MFU-ML1-2B-R2_Delta.patch
PASS
```

R2 delta SHA-256: `DEAF10DEB2048E46EB7A2AA765F3464D6C8A92DFE36740846FD5B1176D98820E`

No full repository pytest was run because the required impact-based suites found no new unexpected failure.

## Preserved boundaries

- Complete ten-strategy runtime scoring and volume indicators: unchanged
- Bound Daily Plan deferred threshold and final score + RS authority: unchanged
- Legacy/unbound seven-weight screener and PANIC behavior: unchanged
- Unexpected market-data exception propagation: unchanged
- A/B call isolation and no module-global mutation: unchanged
- Binding schema/digest, account profile, runbook identity, bootstrap, market refresh, execution, and ledger: unchanged
- Operational DB write, refresh, and runbook execution: not performed

## Status

```text
Finding — PANIC entry hard gate preservation:
RESOLVED

PANIC strategy entry:
PASS

PANIC switch-in prevention:
PASS

BULL/BEAR entry compatibility:
PASS

R1 deferred threshold:
PASS

10-weight runtime scoring:
PASS

Market-data fail-closed:
PASS

A/B isolation:
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

# MFU-ML1-2B-R1 Review Evidence

## Review basis

- Task: `MFU-ML1-2B-R1_RUNTIME_CONSUMER_CLOSURE`
- Base / HEAD: `f9ce53662e6cacab8df642895bfd2e83df40bf46`
- Delta basis: the reviewed, uncommitted ML1-2B implementation captured before R1 edits
- Review artifact: `docs/work_results/MFU-ML1-2B-R1_Delta.patch`
- Status: `READY_FOR_INDEPENDENT_REVIEW`

## Acceptance Criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | Every actual ensemble weight from the frozen runtime strategy reaches the consumer | PASS | Bound screener uses ten runtime weight keys, prepares volume indicators, emits ten signal columns, and the targeted actual-score test matches the sum from binding-derived BULL/BEAR configs. |
| 2 | Runtime evidence and actual scoring semantics agree | PASS | The actual-score regression builds configs with `build_runtime_config` and verifies the screener score from those exact per-call values. Existing runtime evidence validation tests pass. |
| 3 | A candidate is not lost by a premature threshold | PASS | A below-threshold screener candidate is retained with `apply_entry_filter=False`; bound Daily Plan adds RS, applies its final threshold, and selects `AAA`. |
| 4 | Final candidate scoring and threshold SSOT is clear | PASS | Bound `generate_daily_plan` explicitly defers screener filtering; Daily Plan's existing ten-weight + RS stage performs final thresholding. TRD documents this authority. |
| 5 | Only normal market-data insufficiency becomes `missing_market_data` | PASS | Parametrized tests cover `None`, empty, 199 rows, and the existing mixed 210/10-row materialization case. |
| 6 | Unexpected market-data failures fail closed | PASS | Direct materialization preserves the exact `RuntimeError`; bound plan propagation test preserves `PermissionError`, never invokes the screener, and writes no plan. |
| 7 | A/B runtime scoring remains isolated | PASS | Actual A(BULL) → B(BEAR) → A(BULL) scores are deterministic; A repeats exactly and differs from B. |
| 8 | Universe, holdings, frozen, and pinned contracts remain intact | PASS | ML1-2B focused suites pass and ML1-2A/runbook/recovery/NTG compatibility is 313 passed. |
| 9 | Legacy path has no regression | PASS | Unbound screener retains the seven original weights, excludes runtime volume signal columns from output, and keeps immediate filtering. Focused suites pass. |
| 10 | No operational mutation | PASS | Tests use synthetic temp artifacts and the root market DB only through a read-only path override; no refresh, DB write, account prepare, execution, commit, or push occurred. |

## Finding disposition

### Finding 1: incomplete runtime scoring weights

**RESOLVED.** Bound scoring now includes `obv`, `mfi`, and `vol_spike` together with the original seven strategies. Volume indicators are prepared only for runtime-bound calls, while unbound defaults remain unchanged.

### Finding 1: premature screener threshold

**RESOLVED.** Only the bound Daily Plan path disables preliminary screener filtering. The same returned signal row is recomputed with ten frozen runtime weights plus RS and filtered in the existing Daily Plan final stage.

### Finding 2: unexpected market-data exception masking

**RESOLVED.** Broad exception conversion was removed. Normal absence remains a deterministic exclusion; unexpected exceptions abort the operation and cannot appear as `missing_market_data` evidence.

## Failure classification

- `PRE-EXISTING`: `test_run_paper_daily_plan_passes_official_sidecar_metadata`
  - Cause: incomplete bootstrap fixture rejected by unchanged writer guard.
  - Base relationship: guard and test are byte-for-source unchanged from `f9ce536...`; prior ML1-2B evidence records the same base reproduction.
  - R1 action: none, per scope.
- `ENVIRONMENT` (resolved): first targeted invocation omitted `STOCK_SCREENER_MARKET_DB` and failed during collection. Re-run with the documented read-only override passed 27 tests.

## Reviewer focus

1. Confirm `apply_entry_filter=False` is supplied only when runtime binding evidence exists.
2. Confirm unbound `STRATEGY_WEIGHTS` and its immediate filtering remain unchanged.
3. Confirm R1 delta contains no binding schema, digest, bootstrap, execution, or operational write changes.
4. Confirm unexpected explicit-universe read failures propagate before evidence or plan output.

```text
REVIEW STATUS:
READY_FOR_INDEPENDENT_REVIEW
```

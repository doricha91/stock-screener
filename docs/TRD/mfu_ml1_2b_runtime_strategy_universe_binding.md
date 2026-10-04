# MFU-ML1-2B Runtime Strategy and Universe Binding

## Purpose

This MFU connects the versioned, frozen account binding from ML1-2A to Paper Daily Plan runtime consumption. It does not activate a production profile or change account bootstrap, recovery, execution, or scheduler behavior.

## Runtime flow

```text
Stage A frozen runbook state
  -> current binding drift check
  -> frozen effective_strategy_base
  -> frozen active-regime overlay
  -> frozen shared-policy constraints
  -> per-call runtime config
  -> bound entry-universe materialization
  -> screener / Daily Plan consumers
  -> config snapshot and Daily Plan runtime evidence
```

The Stage A command passes its exact runbook state path to the Daily Plan entrypoint. The entrypoint validates account, data date, and trade date before consuming the frozen binding. A versioned direct call without a runbook state uses a call-local resolved binding. Legacy account-profile paths continue without runtime binding injection.

## Strategy precedence and isolation

The only account strategy base is `semantics.effective_strategy_base`. Runtime values are assembled in this order:

1. Existing `make_config()` structural/default config
2. Frozen effective strategy base
3. Frozen regime policy and `REGIME_RULES`
4. Frozen shared policy
5. Existing active-regime overlay through `get_regime_config()`

The runtime assembler verifies effective strategy values, the complete regime policy, and shared constraints before consumers run. Pinned config snapshots are checked against the same values. Config dictionaries are copied and passed as call arguments; module globals are not patched.

The screener accepts an optional per-call runtime config. Bound calls prepare and expose the complete ensemble signal set (`turtle`, `rsi`, `sma`, `bbands`, `macd`, `bbs`, `dema`, `obv`, `mfi`, and `vol_spike`) and score it with the frozen runtime weights. Calls without runtime injection retain the prior seven-weight defaults and filtering behavior.

For a bound Daily Plan, the screener does not apply its preliminary entry threshold. It returns the complete scored signal rows, and Daily Plan is the authoritative final scoring and entry-gate location: it recomputes the ten-weight ensemble score, adds the configured positive-RS weight, and then applies the shared regime hard gate, `score_threshold`, and the existing positive-RS gate. This prevents a candidate that can pass the final frozen-strategy-plus-RS semantics from being discarded by an incomplete preliminary score while preserving the existing `PANIC` prohibition on new BUY entries. The same final eligibility predicate filters switching replacements, so `PANIC` cannot produce `SWITCH_IN` BUY actions. Valuation, risk, exit, trailing-stop, SELL, hedge, and holding-management paths remain active. Other screener callers keep the existing immediate threshold behavior.

## Universe contract

`shared_snapshot` uses the existing quarterly as-of snapshot and passes its normalized active symbols to the screener.

An explicit-symbol binding sorts and checks each requested symbol against the same start-date and 200-row minimum used by the screener. Symbols without sufficient as-of market data are excluded from entry screening with deterministic evidence:

```text
reason = missing_market_data
```

Only normal data insufficiency (`None`, an empty frame, or fewer than 200 rows) receives this exclusion. Database, permission, read, and other unexpected exceptions propagate and abort Daily Plan generation; they are not converted into `missing_market_data` evidence.

Entry eligibility and position management remain separate:

```text
entry stream = materialized bound entry universe
managed stream = entry stream + existing holdings + hedge symbols + benchmark
```

Holdings outside the entry universe therefore continue through existing valuation, risk, exit, and switching evaluation paths.

## Runtime evidence and fail-closed checks

The config snapshot and Daily Plan JSON sidecar record:

- account ID and frozen binding digest
- strategy and universe references
- effective strategy base
- active/applied regime and overlay
- effective runtime strategy
- shared policy
- entry-universe definition
- requested and materialized entry universes
- excluded symbols and reasons
- preserved holdings and managed symbols
- runtime/frozen validation result

If a pinned snapshot already contains this evidence, source fields and materialization fields must match the newly derived values. Older snapshots without the optional evidence field remain readable and are not migrated.

## Boundaries

This MFU does not perform production activation, account preparation, bootstrap writes, market refresh redesign, operational runbook execution, parallel account execution, position/trade strategy ownership, deployment, backtest changes, or optimizer changes.

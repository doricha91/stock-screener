# MFU-PAPER9-1 Closed Trade Journal Investigation

## Summary

- Scope: read-only investigation for `paper_execution_log.csv` and the current paper reducer/snapshot/report pipeline.
- Conclusion: the current pipeline can compute account-level and symbol-level realized PnL, but it does not preserve trade-lot history or per-close realized rows. A `closed trade journal` can be added in PAPER9-2, but only as a derived artifact with explicit limits, or with a small dedicated reducer that tracks close events while replaying the execution log.
- Key finding: realized PnL is based on average cost, not FIFO. This makes `realized_pnl` reproducible from the log, but makes a single `open_date` ambiguous after multiple BUYs merge into one average-cost position.

## Files Reviewed

- `outputs/paper_test/paper_execution_log.csv`
- `outputs/paper_test/paper_account_snapshot.csv`
- `outputs/paper_test/paper_position_snapshot.csv`
- `core/paper_account_state.py`
- `core/paper_execution_log.py`
- `core/paper_trade_preview.py`
- `core/paper_account_snapshot.py`
- `core/paper_position_snapshot.py`
- `core/paper_performance_summary.py`
- `scripts/run_paper_eod_update.py`
- `scripts/generate_paper_equity_curve.py`
- `scripts/generate_paper_performance_summary.py`
- `tests/test_paper_sell_e2e.py`
- `tests/test_paper_pipeline_adversarial.py`
- `tests/test_paper_execution_log.py`

## paper_execution_log.csv Columns

Actual header from `outputs/paper_test/paper_execution_log.csv`:

`trade_id,date,regime,symbol,side,shares,price,gross_amount,source,status,reason,notes,rec_shares,rec_price,created_at`

## BUY/SELL Row Structure

Observed sample rows:

- BUY: `2026-05-09, CPAY, BUY, 29, 343.99, 9975.71, journal_actual_fill`
- SELL: `2026-05-12, CPAY, SELL, -29, 338.34, -9811.86, paper_virtual_fill`

Observed and code-enforced conventions:

- BUY `shares` must be `> 0`
- SELL `shares` must be `< 0`
- BUY `gross_amount` is positive
- SELL `gross_amount` is negative
- `rec_shares` is stored as positive absolute quantity even for SELL rows

Source of sign enforcement:

- `core/paper_trade_preview.py`: SELL preview shares are negated before row creation
- `core/paper_account_state.py`: BUY negative or SELL positive shares raise `ValueError`
- `tests/test_paper_execution_log.py`: explicit BUY positive / SELL negative assertions

## Current Reducer Flow

1. `scripts/run_paper_eod_update.py` parses the markdown journal and builds `PaperTradePreview`.
2. `core/paper_execution_log.py` converts previews into execution-log rows and appends them if `--commit` is used.
3. `scripts/run_paper_eod_update.py::build_paper_account_preview_from_log()` reloads `paper_execution_log.csv`.
4. `core/paper_account_state.py::build_paper_state_from_trades()` replays every row in order through `apply_paper_trade()`.
5. The resulting reducer state feeds:
   - `core/paper_account_snapshot.py`
   - `core/paper_position_snapshot.py`
   - PAPER8 report scripts

The reducer is state-based, not event-journal based. It keeps:

- cash
- open positions by symbol
- `applied_trade_ids`
- cumulative `realized_pnl`
- cumulative `realized_pnl_by_symbol`

It does not keep:

- closed trade rows
- realized event rows
- lot history
- entry dates per lot
- per-sell realized return percentages

## realized_pnl Calculation Location

- Primary logic: `core/paper_account_state.py::apply_paper_trade()`
- Account snapshot persistence: `core/paper_account_snapshot.py::build_paper_account_snapshot_row()`
- Open-position snapshot reuse: `core/paper_position_snapshot.py::build_paper_position_snapshot_rows()`

## realized_pnl Calculation Method

Current formula on SELL:

- `realized_pnl_delta = (sell_price - existing.avg_price) * sell_quantity`

Interpretation:

- Method: average cost
- Not FIFO
- Not lot-specific matching

Evidence:

- BUY updates one merged `avg_price` per symbol
- SELL uses the current merged `existing.avg_price`
- Tests confirm partial sell -> remaining shares keep the same average cost
- Tests confirm partial sell + rebuy -> next full sell uses the newly recomputed merged average cost

Example from `tests/test_paper_pipeline_adversarial.py`:

- Buy 10 @ 100
- Sell 4 @ 120 => realized `+80`, remaining `6 @ 100`
- Buy 6 @ 90 => merged position `12 @ 95`
- Sell 12 @ 110 => realized `+180`

## Partial SELL Handling

Code behavior:

- reducer checks `existing.shares >= abs(shares)`
- realized PnL is computed only on sold quantity
- remaining position stays open
- remaining shares keep the same `avg_price`
- symbol remains in `positions`

Test coverage:

- `tests/test_paper_sell_e2e.py::test_partial_sell_end_to_end`

Observed production log:

- no partial SELL sample found in current `outputs/paper_test/paper_execution_log.csv`

## Full SELL Handling

Code behavior:

- realized PnL is computed on full remaining quantity
- cash increases by `sell_quantity * sell_price`
- if remaining shares become zero, symbol is removed from `positions`
- realized PnL only survives in cumulative account/symbol aggregates

Test coverage:

- `tests/test_paper_sell_e2e.py::test_full_sell_end_to_end_removes_position`

## trade_id Stability Assessment

`trade_id` is generated in `core/paper_execution_log.py::build_paper_trade_id()` from:

- `date`
- `symbol`
- `side`
- `shares`
- `price`
- `reason`
- `source`

Assessment:

- Stable enough for row-level deduplication/replay idempotency
- Not appropriate as a closed-trade linkage key between BUY and SELL
- Not a lot id
- Not an open-trade id
- Can change if `reason` or `source` changes for the same economic trade
- Multiple BUY lots for one symbol are intentionally merged later by the reducer, so `trade_id` does not solve close matching

## Can Current Structure Produce a Closed Trade Journal?

Yes, but only with constraints.

What is already possible from the current log:

- close date
- symbol
- shares closed
- exit price
- realized PnL using the same average-cost rule as the reducer
- close-side `trade_id`
- source
- reason

What is not natively preserved:

- exact entry lot(s)
- FIFO-style matching
- single authoritative `open_date` after multiple BUYs merge
- holding days with unambiguous semantics under average-cost rebuy paths
- per-close persistent journal rows in existing snapshots

Therefore:

- A PAPER9-2 script can derive a `realized trade journal` by replaying the execution log with an average-cost reducer that emits one row per SELL.
- A stricter `closed trade journal` with `open_date` and `holding_days` needs explicit policy. Under average cost, those fields are ambiguous once multiple BUY dates mix.

## Ambiguous or Risky Areas

- `open_date` is not stable after multiple BUY rows merge into one averaged position.
- `holding_days` depends on how `open_date` is defined.
- `realized_return_pct` also needs a policy:
  - `(exit - avg_cost) / avg_cost` is reproducible
  - but it is not a true lot-matched trade return
- `realized_pnl_by_symbol` exists, but only as cumulative aggregate. There is no per-sell realized ledger.
- `paper_position_snapshot.csv` stores open positions only (`position_status = OPEN`), so closed positions are intentionally absent.

## Recommended PAPER9-2 Implementation Shape

Preferred minimal path:

- add a dedicated read-only reducer/helper that replays `paper_execution_log.csv`
- emit one derived row per SELL using the same average-cost rules as `apply_paper_trade()`
- keep it independent from PAPER8 report scripts
- do not refactor the existing account reducer unless reuse becomes clearly necessary

Recommended additions:

- new helper module, e.g. `core/paper_closed_trade_journal.py`
- new generation script, e.g. `scripts/generate_paper_closed_trade_journal.py`

This keeps PAPER9-2 bounded and avoids touching the EOD writer path.

## Candidate Output Columns

Closed trade / realized trade journal minimum columns:

- `close_date`
- `symbol`
- `shares_closed`
- `entry_price_basis`
- `exit_price`
- `realized_pnl`
- `realized_return_pct`
- `close_trade_id`
- `source`
- `reason`

Recommended extra columns:

- `cost_basis_closed`
- `gross_exit_amount`
- `method` (`average_cost`)
- `journal_type` (`realized_trade`)
- `notes`

Only if policy is explicitly documented:

- `open_date`
- `holding_days`

Suggested rule if included:

- mark them as `blended_open_date` / `blended_holding_days` or leave blank when multiple BUY dates contributed

Symbol performance candidate columns:

- `symbol`
- `closed_trade_count`
- `winning_trade_count`
- `losing_trade_count`
- `shares_closed_total`
- `realized_pnl_total`
- `avg_realized_return_pct`
- `avg_win_pnl`
- `avg_loss_pnl`
- `max_win_pnl`
- `max_loss_pnl`
- `first_close_date`
- `last_close_date`

## Final Judgment

- FIFO: no
- Average cost: yes
- Partial SELL support: yes
- Full SELL support: yes
- Trade-level realized ledger exists today: no
- Closed trade journal derivation in PAPER9-2: yes, if defined as an average-cost SELL-event journal
- Need broad refactor before PAPER9-2: no
- Need small dedicated replay/emitter helper: yes

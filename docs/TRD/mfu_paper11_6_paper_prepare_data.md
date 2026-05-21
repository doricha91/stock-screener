# MFU-PAPER11-6 Paper Prepare-Data Wrapper

## Summary

- Scope: add an explicit `paper.py prepare-data` command for minimal paper plan readiness.
- Included:
  - ticker collection
  - market index refresh
  - ticker metadata refresh
  - daily price refresh
  - daily indicators refresh
  - optional universe snapshot refresh
- Excluded:
  - `run_screener(save=True)`
  - `screener_history` writes
  - `outputs/screener_results.csv`
  - `financials` updates
  - `market_status_log` writes
  - `setup_db.py`
  - paper plan / EOD / reports / review workflows

## Implementation Pre-Check Results

### 1. `data_collector.update_market_indices()`

- Call shape: no args
- Side effects:
  - writes `market_index` in `outputs/market_data.db`
  - downloads via `yfinance`
- Return behavior:
  - no structured return value
  - handles per-symbol issues internally with prints

### 2. `data_collector.update_tickers_info(tickers)`

- Call shape: requires ticker list
- Side effects:
  - writes `tickers` in `outputs/market_data.db`
  - uses `yf.Ticker(...).info`
- Return behavior:
  - no structured return value
  - per-symbol failures are printed and the loop continues

### 3. `data_collector.update_stock_data(tickers)`

- Call shape: requires ticker list
- Side effects:
  - writes `daily_price` in `outputs/market_data.db`
  - downloads via `yfinance`
- Return behavior:
  - no structured return value
  - per-symbol failures are printed and the loop continues

### 4. `data_processor.update_technical_indicators()`

- Call shape: no args
- Side effects:
  - writes `daily_indicators` in `outputs/market_data.db`
  - reads `tickers` and `daily_price`
- Return behavior:
  - no structured return value
  - per-symbol failures are printed and the loop continues

### 5. `update_universe.py` invocation path

- `scripts/update_universe.py` exposes `main()`, but it stamps snapshot date with `datetime.now()`.
- For `paper.py prepare-data --date YYYYMMDD --universe`, direct script `main()` is not ideal because requested date and snapshot date may diverge.
- Chosen approach:
  - reuse `core.universe_manager.fetch_live_basket_symbols`
  - reuse `compare_universe`
  - reuse `save_universe_snapshot`
  - reuse `screener.data_manager.get_ticker_list`
- Result:
  - no subprocess required
  - snapshot date can match the requested CLI date

### 6. Failure / exception behavior

- The reused data refresh functions mostly do not raise structured statuses.
- They print internal errors and continue where possible.
- The wrapper treats step completion without exception as step success.
- If a reused function raises an exception, the wrapper marks the step as failed and propagates the error to the caller.

### 7. Writer impact

- `update_market_indices` -> `market_index`
- `update_tickers_info` -> `tickers`
- `update_stock_data` -> `daily_price`
- `update_technical_indicators` -> `daily_indicators`
- optional universe refresh -> `outputs/universe/universe_snapshot_YYYYMMDD.json`

## CLI

```text
python scripts/paper.py prepare-data --date YYYYMMDD
python scripts/paper.py prepare-data --date YYYYMMDD --universe
python scripts/paper.py prepare-data --date YYYYMMDD --skip-prices
python scripts/paper.py prepare-data --date YYYYMMDD --skip-indicators
```

Also added standalone wrapper:

```text
python scripts/prepare_paper_data.py --date YYYYMMDD
```

## Execution Steps

1. Normalize requested date
2. Collect merged S&P 500 + Nasdaq 100 tickers
3. Unless `--skip-prices`:
   - `update_market_indices()`
   - `update_tickers_info(tickers)`
   - `update_stock_data(tickers)`
4. Unless `--skip-indicators`:
   - `update_technical_indicators()`
5. If `--universe`:
   - fetch live basket symbols
   - compare against local DB tickers
   - save `outputs/universe/universe_snapshot_YYYYMMDD.json`
6. Print readiness summary to console

## Safety Notes

- `prepare-data` is an explicit DB writer command.
- It is not auto-run by `paper.py plan`.
- It does not call:
  - `run_screener(save=True)`
  - `setup_db.py`
  - `market_analyzer.get_market_state(write_log=True)`
  - any paper ledger writer
- It does not touch:
  - `outputs/front_test/*`
  - `paper_execution_log.csv`
  - `paper_account_snapshot.csv`
  - `paper_position_snapshot.csv`

## Limitations

- The reused collector/processor functions are legacy-style and mostly print progress instead of returning structured per-step metrics.
- `prepare-data` does not verify freshness beyond successful function completion.
- `financials` update remains out of scope because no active repository writer was identified.

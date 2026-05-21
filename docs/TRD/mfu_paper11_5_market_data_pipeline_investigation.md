# MFU-PAPER11-5 Market Data Pipeline Investigation

## Summary

- This investigation is read-only. No code edits, DB writes, or data collection runs were performed.
- The current market-data pipeline is split across multiple scripts/modules:
  - `scripts/run_screener.py` orchestrates ticker fetch, market-index update, ticker metadata update, stock-price update, market-state evaluation, and screener save.
  - `data_processor.py` separately computes and writes `daily_indicators`.
  - `scripts/update_universe.py` separately writes universe snapshot JSON under `outputs/universe/`.
- `run_paper_daily_plan.py` does **not** depend on a prebuilt screener CSV/DB row. It rebuilds candidates in-process via `core.daily_plan_generator.generate_daily_plan()` -> `screener.screener.build_screener_results(...)`.
- The plan path depends on `outputs/market_data.db` being populated at least for:
  - `daily_price`
  - `market_index`
  - `daily_indicators`
  - `tickers`
  - optional but operationally important: universe snapshot JSON under `outputs/universe/`
- `financials` table exists in schema but no active writer script was found in the current repository.

## Files Checked

- `scripts/run_screener.py`
- `scripts/update_universe.py`
- `scripts/setup_db.py`
- `scripts/run_paper_daily_plan.py`
- `core/daily_plan_generator.py`
- `core/universe_manager.py`
- `core/paths.py`
- `screener/data_collector.py`
- `screener/data_manager.py`
- `screener/screener.py`
- `screener/database.py`
- `data_processor.py`
- `market_analyzer.py`
- `config.py`
- `check_db_ready.py`

## Current Pipeline Candidate

### Step 1. ticker/universe preparation

- Related script/module:
  - `screener.data_collector.get_sp500_tickers()`
  - `screener.data_collector.get_nasdaq100_tickers()`
  - `scripts/update_universe.py`
  - `core.universe_manager.py`
- Input:
  - Wikipedia constituent pages
  - local DB ticker list via `screener.data_manager.get_ticker_list()`
- Output:
  - in-memory ticker list for `run_screener.py`
  - `outputs/universe/universe_snapshot_YYYYMMDD.json` for `update_universe.py`
- Read/write:
  - live web read
  - `update_universe.py` is a file writer
  - `run_screener.py` itself does not persist a universe snapshot

### Step 2. price data update

- Related script/module:
  - `screener.data_collector.update_stock_data(tickers)`
  - called by `scripts/run_screener.py`
- Input:
  - ticker list
  - Yahoo Finance download
- Output DB/table:
  - `outputs/market_data.db`
  - table: `daily_price`
- Read/write:
  - DB writer

### Step 3. market index update

- Related script/module:
  - `screener.data_collector.update_market_indices()`
  - called by `scripts/run_screener.py`
- Input:
  - fixed symbols: `SPY`, `QQQ`, `^VIX`, `^TNX`, `DX-Y.NYB`
  - plus `config.HEDGE_TICKERS`
  - Yahoo Finance download
- Output DB/table:
  - `outputs/market_data.db`
  - table: `market_index`
- Read/write:
  - DB writer

### Step 4. indicator calculation

- Related script/module:
  - `data_processor.update_technical_indicators()`
- Input DB/table:
  - `daily_price`
  - `tickers`
- Output DB/table:
  - `daily_indicators`
- Read/write:
  - DB writer
- Notes:
  - this step is **not** called by `scripts/run_screener.py`
  - current pipeline is split: price update and indicator update are separate

### Step 5. screener input/output generation

- Related script/module:
  - `screener.screener.build_screener_results()`
  - `screener.screener.run_screener(save=True)`
  - `scripts/run_screener.py`
- Input:
  - ticker list from `tickers` table or provided list
  - OHLCV from `daily_price`
  - market regime from `market_analyzer.get_market_state()`
  - indicator functions from `screener/indicator.py` applied in-memory
- Output:
  - DB table `screener_history` via `save_results_to_db()`
  - file `outputs/screener_results.csv` via `save_results_to_csv()`
- Read/write:
  - DB writer
  - file writer

### Step 6. paper daily plan dependencies

- `scripts/run_paper_daily_plan.py` -> `core.daily_plan_generator.generate_daily_plan()`
- Direct/indirect dependencies:
  - `market_analyzer.get_market_state(target_date=plan_date, write_log=False)`
    - reads `daily_indicators`
    - reads `market_index`
    - reads `daily_price`
    - reads `tickers`
    - reads `market_status_log` for prior regime history
  - `load_market_index_series(...)`
    - reads `market_index`
  - `build_screener_results(market_state=m_state, end_date=plan_date)`
    - reads `daily_price`
    - reads `tickers`
    - computes indicators in-memory via `screener/indicator.py`
  - `load_universe_snapshot_as_of_quarter(plan_date)`
    - reads `outputs/universe/universe_snapshot_*.json`

## DB Writer Inventory

### `outputs/market_data.db`

- `scripts/run_screener.py`
  - DB writer through `data_collector.update_market_indices`
  - DB writer through `data_collector.update_tickers_info`
  - DB writer through `data_collector.update_stock_data`
  - DB writer through `run_screener(save=True)` -> `screener_history`
- `screener/data_collector.py`
  - DB writer: `tickers`, `market_index`, `daily_price`
- `data_processor.py`
  - DB writer: `daily_indicators`
- `market_analyzer.py`
  - conditional DB writer: `market_status_log` when `write_log=True`
- `scripts/setup_db.py`
  - dangerous writer: drops and recreates `market_status_log`
- `screener/database.py`
  - schema/table creator for `tickers`, `daily_price`, `market_index`, `financials`, `market_status_log`, `daily_indicators`, `screener_history`

### Table-level summary

- `tickers`
  - writer: `screener.data_collector.update_tickers_info`
- `daily_price`
  - writer: `screener.data_collector.update_stock_data`
- `market_index`
  - writer: `screener.data_collector.update_market_indices`
- `daily_indicators`
  - writer: `data_processor.update_technical_indicators`
- `market_status_log`
  - writer: `market_analyzer.get_market_state(..., write_log=True)`
  - dangerous reset: `scripts/setup_db.py`
- `financials`
  - schema exists, active writer not found
- `screener_history`
  - writer: `screener.screener.save_results_to_db`

## Read/Write Classification

- read-only
  - `scripts/run_paper_daily_plan.py`
  - `check_db_ready.py`
  - `screener/data_manager.py`
  - `core/daily_plan_generator.py` when called with `market_state_write_log=False`
- DB writer
  - `scripts/run_screener.py`
  - `screener/data_collector.py`
  - `data_processor.py`
  - `market_analyzer.py` default `write_log=True`
  - `screener/screener.py` with `save=True`
- file writer
  - `scripts/update_universe.py` -> `outputs/universe/*.json`
  - `screener/screener.py` -> `outputs/screener_results.csv`
- dangerous writer
  - `scripts/setup_db.py` because it drops/recreates `market_status_log`
- unknown / not found
  - no active `financials` updater found

## Screener Input Flow

- `run_screener.py` collects live ticker baskets from Wikipedia each run.
- It updates:
  - `market_index`
  - `tickers`
  - `daily_price`
- Then it calls `market_analyzer.get_market_state()`, which relies on `daily_indicators` and market series already being present.
- Then it calls `screener.screener.run_screener(...)`.
- `build_screener_results()` does not use `daily_indicators` table; it recomputes indicator features in-memory from `daily_price`.
- By contrast, `market_analyzer.get_market_state()` **does** use `daily_indicators` for breadth and trigger logic.

## Prepare-Data Candidate Entrypoint

- Conclusion: **D. 데이터 수집과 지표 계산을 먼저 분리/정리해야 함**
- Reason:
  - `scripts/run_screener.py` is the closest operational entrypoint, but it omits `data_processor.update_technical_indicators()`.
  - `run_paper_daily_plan.py` depends on `market_analyzer.get_market_state()`, which expects `daily_indicators` to exist and be current.
  - Therefore wrapping only `run_screener.py` as `paper.py prepare-data` would be incomplete and can leave plan generation using stale/missing regime inputs.

## Minimum Data Readiness Before Paper Plan

- Minimum recommended sequence before `paper.py plan`:
  1. DB schema ready (`screener/database.py create_tables` or prior setup already done)
  2. ticker / index / price refresh
  3. `daily_indicators` refresh
  4. optional but recommended: universe snapshot refresh
- If only one operational command is allowed today, there is no single safe SSOT entrypoint that covers all four steps.

## Risk Areas For Future `paper.py prepare-data`

- `scripts/run_screener.py`
  - mixes DB writes and screener result writes in one command
  - may give a false sense of completeness because `daily_indicators` is not refreshed there
- `market_analyzer.get_market_state()`
  - default `write_log=True` writes `market_status_log`
  - wrapper must use it carefully if “prepare-data” is intended to stay out of regime-log side effects
- `scripts/setup_db.py`
  - must not be included in an everyday prepare-data wrapper
  - it drops `market_status_log`
- `scripts/update_universe.py`
  - file write only, but it fetches live web data and creates a new as-of snapshot every run

## `outputs/front_test` Contamination Risk

- Low for the current data pipeline itself:
  - market data writers target `outputs/market_data.db`
  - screener CSV targets `outputs/screener_results.csv`
  - universe snapshots target `outputs/universe/`
- Main cross-path risk is not in data collection, but later orchestration:
  - `core.daily_plan_generator.generate_daily_plan()` defaults to `front_daily_action_plan_path()` when wrapper output is omitted
  - therefore future `prepare-data` is not the main front-test contamination vector; direct daily-plan misuse is

## Recommended Direction For `paper.py prepare-data`

- Recommended command shape:
  - `python scripts/paper.py prepare-data --date YYYYMMDD`
  - or explicit flags:
    - `python scripts/paper.py prepare-data --prices --indicators --universe`
- Recommended implementation policy:
  - do **not** wrap `scripts/run_screener.py` as the only step
  - separate at least:
    - price/index/ticker refresh
    - indicator refresh
    - optional universe snapshot refresh
  - keep screener result generation out of prepare-data unless its side effects are explicitly desired

## Additional Decisions Needed

- Should `prepare-data` include `screener_history` / `outputs/screener_results.csv` generation, or only readiness for plan?
- Should universe snapshot refresh be mandatory or optional?
- Should `market_status_log` writes be avoided during prepare-data?
- Should `financials` remain ignored, or is there an external missing writer not yet in repo?

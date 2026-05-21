# MFU-PAPER11-7 Market Data Freshness / Readiness Check

## Summary

- Scope: add a read-only freshness/readiness check for `market_data.db` before paper plan generation.
- Added commands:
  - `python scripts/paper.py data-freshness --date YYYYMMDD`
  - `python scripts/paper.py data-freshness --date YYYYMMDD --strict`
  - `python scripts/check_paper_data_freshness.py --date YYYYMMDD`
- This check does not run market-data collection, DB writes, paper planning, or EOD commit.

## Checks

- `market_data.db` existence and read-only connection
- required table existence:
  - `daily_price`
  - `market_index`
  - `daily_indicators`
  - `tickers`
- `daily_price`:
  - row count
  - max date
  - distinct symbol count
- `market_index`:
  - per-symbol existence and latest date for `SPY`, `QQQ`, `^VIX`
- `daily_indicators`:
  - row count
  - max date
  - distinct symbol count
  - stale-vs-`daily_price` detection
- `tickers`:
  - row count
  - optional `listing_board` distribution
- optional universe snapshot:
  - `outputs/universe/universe_snapshot_YYYYMMDD.json`

## Result Policy

- `FAIL`
  - one or more errors
- `PASS_WITH_WARNINGS`
  - no errors and at least one warning
- `PASS`
  - no errors and no warnings

## Strict Policy

- In `--strict`, these stale conditions escalate from warning to error:
  - `daily_price MAX(date) < target_date`
  - `SPY market_index MAX(date) < target_date`
  - `daily_indicators MAX(date) < daily_price MAX(date)`
- Universe snapshot missing remains warning even in strict mode.

## Report Output

- Default: console only
- Optional `--write-report`:
  - `outputs/paper_test/reports/paper_data_freshness_report.md`
  - `outputs/paper_test/reports/paper_data_freshness_issues.csv`

## Safety Notes

- The checker opens the DB in SQLite read-only mode.
- It does not call:
  - `data_collector.update_*`
  - `data_processor.update_technical_indicators`
  - `paper.py prepare-data`
  - `run_paper_daily_plan.py`
  - `run_paper_eod_update.py`

## Limitations

- This checker validates freshness heuristics, not business correctness of downloaded data.
- Weekend/holiday handling is intentionally conservative:
  - stale dates become warnings in default mode
  - strict mode escalates them to errors for operational discipline

# MFU-PAPER13-2 Benchmark Comparison

## Scope

이번 MFU는 existing exploratory paper snapshot을 기준으로 `SPY`, `QQQ`, `CASH` benchmark comparison을 생성한다.

포함:

- since-inception comparison
- starting capital source = `paper_account_snapshot.initial_cash`
- paper equity source = `total_equity_market_value` 우선, `total_equity_cost_basis` fallback
- benchmark price source = `market_index.adj_close` 우선, `close` fallback
- Markdown / JSON output

제외:

- clean reset / archive
- official run re-baselining
- Notion 연동
- HTML / CSV 생성
- period benchmark
- monthly DCA benchmark

## Data sources

- `outputs/paper_test/paper_account_snapshot.csv`
- `outputs/market_data.db`
  - table: `market_index`
  - symbols: `SPY`, `QQQ`

## Output files

- `outputs/paper_test/reports/paper_benchmark_comparison.md`
- `outputs/paper_test/reports/paper_benchmark_comparison.json`

## JSON notes

- `schema_version = paper_benchmark_comparison.v1`
- `run_mode = exploratory`
- `official_run = false`
- `limitations`에 unofficial benchmark 경고를 고정 포함한다.

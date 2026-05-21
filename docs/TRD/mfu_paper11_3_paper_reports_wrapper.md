# MFU-PAPER11-3 Paper Reports Wrapper

## Scope

- Extend `scripts/paper.py` with a `reports` subcommand
- Auto-run paper preflight for `stage=reports`
- Execute existing PAPER9 report generators in dependency order

## Added Components

- `scripts/paper.py` updates
- `tests/test_paper_cli.py` updates

## Report Order

1. `generate_paper_equity_curve.py`
2. `generate_paper_drawdown.py`
3. `generate_paper_performance_summary.py`
4. `generate_paper_realized_trade_journal.py`
5. `generate_paper_symbol_realized_performance.py`
6. `generate_paper_realized_ranking_report.py`
7. `generate_paper_symbol_unrealized_performance.py`
8. `generate_paper_symbol_side_by_side_performance.py`
9. `generate_paper_symbol_review_buckets.py`
10. `generate_paper_symbol_review_worksheet.py`
11. `generate_paper_daily_review_summary.py`

## Notes

- `reports --strict` blocks execution when preflight warnings exist
- Any failed report step aborts the chain immediately
- The wrapper does not call EOD commit or review append
- Outputs are limited to `outputs/paper_test/reports/*`

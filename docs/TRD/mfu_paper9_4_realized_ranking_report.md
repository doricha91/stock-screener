# MFU-PAPER9-4 Realized Ranking / Reporting

## Scope

- Generate realized ranking and reporting from `outputs/paper_test/reports/paper_symbol_realized_performance.csv`
- Treat symbol-level realized performance CSV as the source of truth
- Exclude replay, unrealized PnL, open positions, FIFO, lot ledger, `open_date`, and `holding_days`

## Added Components

- `core/paper_realized_ranking_report.py`
- `scripts/generate_paper_realized_ranking_report.py`
- `tests/test_paper_realized_ranking_report.py`

## Outputs

- `outputs/paper_test/reports/paper_realized_ranking_report.md`
- `outputs/paper_test/reports/paper_realized_ranking.csv`

## Ranking Types

- `top_realized_pnl`
- `worst_realized_pnl`
- `loss_contribution`
- `win_rate`
- `profit_factor`
- `trade_count`

## Notes

- Loss contribution uses `abs(symbol_total_realized_pnl) / total_abs_loss`.
- Blank or non-comparable profit factor values are excluded from the profit factor ranking.
- Symbols with `realized_trade_count <= 2` are flagged as small-sample rows.
- This report remains realized SELL-event only and does not combine open-position metrics.

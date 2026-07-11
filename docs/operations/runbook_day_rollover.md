# Runbook Day Rollover Preview

## Purpose

`scripts\runbook_day_rollover.py` calculates the next paper/test runbook dates from the latest completed controller state. It is a read-only preview. It does not create state, update `_env.cmd`, write Notion data, run a stage, call a broker, or place an order.

## Command

```bat
python scripts\runbook_day_rollover.py ^
  --workspace D:\n8n\workspace\stock_screener_ops ^
  --account-id paper_pilot_202606 ^
  --confirm-paper-test
```

Use the `HANTU311_64` Python environment. The confirmation flag is mandatory, and the account ID must contain `paper` or `test`.

## State Selection

The preview reads account-scoped JSON files under `runbook_states\`. Every state must pass the existing `runbook_state.v1` validation, and its filename must equal `{runbook_day_id}.json`.

A completed day must have all controller stages at `PASS`, Stage E as the current and last completed stage, step 18 completed, a pinned `final_status_report_json`, and no `last_error`. The latest completed day is selected by `trade_date`. Tied latest completed states, invalid state identity, or any incomplete active day cause `BLOCKED`.

## Date Rule

```text
next_data_date = latest completed trade_date
next_trade_date = first NYSE trading day after next_data_date
```

Weekends and full-day NYSE holidays are excluded. The bundled calendar is `config\market_holidays_us.json`, schema `us_market_holidays.v1`, with coverage from `2025-01-01` through `2027-12-31`. Dates outside that range are never assumed to be trading days and produce `BLOCKED`.

The preview checks for the calculated ID in `runbook_states` and the controller artifact/run directories. Existing data sets `already_exists=true` and `safe_to_prepare=false`; nothing is overwritten.

## Result And Exit Codes

- `PASS`: calculation completed; process exit code `0`.
- `BLOCKED`: input, state, active-day, identity, or calendar validation failed; process exit code `2`.

Always inspect `runner_result`, `already_exists`, `safe_to_prepare`, `blockers`, and `next_required_action` before proceeding. This preview does not execute a returned action or raw `operator_summary.next_command`.

Until 6-4C exists, the preview does not prepare the next local runbook environment. Calendar holidays and coverage must be reviewed and extended before the configured coverage end.

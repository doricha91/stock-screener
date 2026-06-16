# Daily Runner Refresh Design

This document captures the current file-based n8n paper ops runner contract and the proposed date resolution policy for the future `daily_refresh` command. It is a design document only. It does not introduce `daily_refresh`, Windows Task Scheduler integration, or n8n workflow changes.

## Current Runner Contract

Runner entrypoint:

```cmd
python scripts\n8n_paper_ops_runner.py <command_key>
```

Allowed `command_key` values are hard-coded:

```text
context
status
eod_dryrun
```

The runner never accepts a raw shell command. Internal subprocess calls use explicit Python argv with `shell=False`.

Default workspace:

```text
D:\n8n\workspace\stock_screener_ops
```

The workspace can be overridden with `--workspace`, mainly for tests and smoke runs.

### Shared Context Contract

Context file:

```text
<workspace>\context.json
```

Required JSON fields:

```json
{
  "account_id": "paper_orch_smoke_202606",
  "data_date": "2026-06-12",
  "trade_date": "2026-06-15"
}
```

`data_date` and `trade_date` accept `YYYY-MM-DD` or `YYYYMMDD` input and are normalized to `YYYY-MM-DD` when stored or loaded.

`account_id` is the paper account scope used by downstream paper ops commands.

`data_date` is the completed market data date used by daily ops status.

`trade_date` is the paper operation/trade date used by daily ops status and EOD dry-run.

### Command Contract: context

| Field | Contract |
| --- | --- |
| command | `python scripts\n8n_paper_ops_runner.py context --account-id <id> --data-date <date> --trade-date <date>` |
| purpose | Persist the active account/date context and generate Telegram-readable context text. |
| required inputs | `--account-id`, `--data-date`, `--trade-date` |
| optional inputs | `--workspace`, `--timeout-seconds` accepted by parser but timeout is not used by this command. |
| reads | No existing context required. |
| writes | `<workspace>\context.json`, `<workspace>\context_latest.txt` |
| stdout summary | Same content as `context_latest.txt`; starts with `Paper Ops Context`. |
| exit code | `0` on successful context write; `1` on validation/write failure. |
| runner_result | `PASS` on success, `FAIL` on exception. `WARNING` is not currently emitted by this command. |
| n8n command using output | `/context` reads `/workspace/stock_screener_ops/context_latest.txt`. |
| failure behavior | Writes `context_latest.txt` containing `Paper Ops Runner Error`, `command_key: context`, `runner_result: FAIL`, and the error message. `context.json` may be absent or unchanged if validation fails before write. |

### Command Contract: status

| Field | Contract |
| --- | --- |
| command | `python scripts\n8n_paper_ops_runner.py status` |
| purpose | Read context, run read-only daily ops status, and generate Telegram-readable status text. |
| required inputs | A valid `<workspace>\context.json` with `account_id`, `data_date`, and `trade_date`. |
| optional inputs | `--workspace`, `--timeout-seconds` |
| reads | `<workspace>\context.json`; downstream command may read local paper ops artifacts and optionally Notion in read-only mode. |
| internal argv | `python scripts\paper_daily_ops.py status --account-id <context.account_id> --data-date <context.data_date> --trade-date <context.trade_date> --json --include-notion-read` |
| writes | `<workspace>\status_latest.txt`, `<workspace>\status_latest.json` |
| stdout summary | Same content as `status_latest.txt`; starts with `Paper Daily Ops Status`. |
| exit code | Returns the downstream `paper_daily_ops.py status` process exit code; returns `1` if context loading, JSON parsing, timeout, or runner handling fails. |
| runner_result | `PASS` if downstream exit code is `0`; `FAIL` otherwise. `WARNING` is not currently emitted by this wrapper. |
| n8n command using output | `/status` reads `/workspace/stock_screener_ops/status_latest.txt`. |
| failure behavior | On runner exception, writes `status_latest.txt` error text and `status_latest.json` with `{"runner_result": "FAIL", "error": "..."}`. If the downstream command exits non-zero but emits parseable JSON, `status_latest.json` is still written and `status_latest.txt` includes `stderr`. |

### Command Contract: eod_dryrun

| Field | Contract |
| --- | --- |
| command | `python scripts\n8n_paper_ops_runner.py eod_dryrun` |
| purpose | Read context, run paper EOD in dry-run mode, and generate Telegram-readable EOD safety summary. |
| required inputs | A valid `<workspace>\context.json` with `account_id`, `data_date`, and `trade_date`. |
| optional inputs | `--workspace`, `--timeout-seconds` |
| reads | `<workspace>\context.json`; downstream command reads local paper state/artifacts for `context.trade_date`. |
| internal argv | `python scripts\paper.py eod --date <context.trade_date> --account-id <context.account_id> --dry-run` |
| writes | `<workspace>\eod_dryrun_latest.txt`, `<workspace>\eod_dryrun_latest.raw.txt` |
| stdout summary | Same content as `eod_dryrun_latest.txt`; starts with `Paper EOD Dry-Run`. |
| exit code | `0` only if the downstream process exits `0` and all required EOD PASS fields match; otherwise `1`. |
| runner_result | `PASS` only when the EOD dry-run output contains all required PASS fields. `FAIL` when a required field is missing/mismatched, downstream exits non-zero, or a runner exception occurs. `WARNING` is not currently emitted by this wrapper. |
| n8n command using output | `/eod_dryrun` reads `/workspace/stock_screener_ops/eod_dryrun_latest.txt`. |
| failure behavior | On required PASS field mismatch, still writes `.raw.txt` and a readable `.txt` with `pass_condition_failures`. On runner exception, writes both files with `Paper Ops Runner Error`. |

Required EOD PASS fields:

```text
eod_mode=accounting_close
would_append_execution_log=false
would_write_current_state=true
would_write_account_snapshot=true
would_write_position_snapshot=true
```

## Workspace File Mapping

| Runner output | Producer command | n8n / Telegram command | Container path |
| --- | --- | --- | --- |
| `context_latest.txt` | `context` | `/context` | `/workspace/stock_screener_ops/context_latest.txt` |
| `status_latest.txt` | `status` | `/status` | `/workspace/stock_screener_ops/status_latest.txt` |
| `status_latest.json` | `status` | Not sent directly; diagnostic/source payload. | `/workspace/stock_screener_ops/status_latest.json` |
| `eod_dryrun_latest.txt` | `eod_dryrun` | `/eod_dryrun` | `/workspace/stock_screener_ops/eod_dryrun_latest.txt` |
| `eod_dryrun_latest.raw.txt` | `eod_dryrun` | Not sent directly; raw diagnostic output. | `/workspace/stock_screener_ops/eod_dryrun_latest.raw.txt` |
| `context.json` | `context` today; future `daily_refresh` | Read by `status` and `eod_dryrun`. | `/workspace/stock_screener_ops/context.json` |

## Date Resolution Helper Contract

Implemented helper:

```text
resolve_daily_refresh_dates()
```

Location:

```text
scripts/n8n_paper_ops_runner.py
```

The helper is intentionally not exposed as a CLI command in this stage. It is read-only and does not write `context.json`, `*_latest.txt/json`, or any DB rows.

Inputs:

| Input | Purpose |
| --- | --- |
| `account_id` | Required explicit account id for this stage. Empty value returns a FAIL resolution. |
| `db_path` | SQLite market DB path. Opened read-only with SQLite URI `mode=ro`. |
| `as_of_date` | Optional injectable date/datetime/string for tests and scheduled runs. Defaults to local `date.today()`. |
| `stale_threshold_days` | Calendar-day threshold for stale market data warning. Default is `3`. |
| `market_index_symbol` | Required market index symbol. Default is `SPY`. |

Return dataclass:

```python
@dataclass(frozen=True)
class DailyRefreshDateResolution:
    account_id: str
    data_date: str | None
    trade_date: str | None
    source_data_max_date: str | None
    daily_price_max_date: str | None
    market_index_max_date: str | None
    daily_indicators_max_date: str | None
    runner_result: str
    stale: bool
    stale_days: int | None
    date_policy: str
    reason: str
    recommended_operator_action: str
```

Example output:

```json
{
  "account_id": "paper_orch_smoke_202606",
  "data_date": "2026-06-12",
  "trade_date": "2026-06-15",
  "source_data_max_date": "2026-06-12",
  "daily_price_max_date": "2026-06-12",
  "market_index_max_date": "2026-06-12",
  "daily_indicators_max_date": "2026-06-12",
  "stale": false,
  "stale_days": 1,
  "date_policy": "latest_complete_market_data_to_next_weekday",
  "runner_result": "PASS",
  "reason": "latest complete market data date found in DB",
  "recommended_operator_action": "none"
}
```

Implemented data_date policy:

1. Do not derive `data_date` from the wall-clock date alone.
2. Read market DB freshness in read-only mode.
3. Determine latest required data dates:
   - `daily_price`: `SELECT MAX(date) FROM daily_price`
   - `market_index` for `SPY`: `SELECT MAX(date) FROM market_index WHERE symbol = 'SPY'`
   - `daily_indicators`: `SELECT MAX(date) FROM daily_indicators`
4. Resolve `source_data_max_date` as `min(daily_price_max_date, market_index_max_date, daily_indicators_max_date)`.
5. Set `data_date = source_data_max_date`.

Implemented trade_date policy:

1. Set `trade_date` to the next weekday after `data_date`.
2. Friday `data_date` resolves to the following Monday.
3. Saturday/Sunday `data_date` resolves to the following Monday but returns `WARNING`, because market data dated on a weekend is unusual and should be verified.

Current limitations:

1. US market holiday handling is not implemented yet.
2. The helper uses a weekend-only next trade date policy.
3. The helper does not call Notion, `paper.py`, `paper_daily_ops.py`, or `core.paper_data_freshness.run_paper_data_freshness_check`.
4. A later `daily_refresh` implementation may add a market-calendar helper or reuse a project-level trading calendar once available.

Operational guardrails:

1. `trade_date` must be strictly after `data_date` and must not be a weekend. Existing explicit date validators in `scripts.paper` and `scripts.run_paper_daily_plan` enforce the same shape for downstream plan commands.
2. If required tables or columns are missing, the helper returns `FAIL` instead of raising an uncaught exception.
3. If required data is empty, the helper returns `FAIL`.
4. If SPY market index rows are absent, the helper returns `FAIL`.
5. If required source max dates are not aligned, the helper returns `WARNING` and uses the conservative complete date.
6. If `data_date` is older than `stale_threshold_days` relative to `as_of_date`, the helper returns `WARNING`.

`runner_result` meaning for date resolution:

| Result | Meaning |
| --- | --- |
| `PASS` | `account_id`, `data_date`, and `trade_date` are resolved with complete required market data and no stale warning. |
| `WARNING` | Dates are usable for read-only refresh, but source-date lag, stale data, weekend data date, or holiday-calendar limitations deserve operator review. |
| `FAIL` | Cannot safely resolve account/date context; `daily_refresh` must not refresh context/status/eod files as if current. |

## DB Tables And Columns

| Table | Columns used | Required |
| --- | --- | --- |
| `daily_price` | `date` | Yes |
| `market_index` | `date`, `symbol` | Yes, with `symbol='SPY'` |
| `daily_indicators` | `date` | Yes |

## Date Resolution Edge Cases

| Case | Expected data_date | Expected trade_date | runner_result | recommended_operator_action |
| --- | --- | --- | --- | --- |
| 1. Weekday after normal data refresh | Latest complete required DB date. | Next operating trade date after `data_date`. | `PASS` | None. |
| 2. Monday execution where latest data is prior Friday | Prior Friday if it is latest complete DB date. | Monday if it is an operating trade date; otherwise next resolvable operating date. | `PASS` if calendar confidence is high; `WARNING` if holiday handling is uncertain. | Verify market calendar if Monday is a US holiday. |
| 3. Weekend execution | Latest complete DB date, often Friday. | Next operating trade date after `data_date`, often Monday. | `PASS` if date gap is expected; `WARNING` if stale threshold is exceeded. | No action unless stale warning appears. |
| 4. US market holiday | Latest complete DB date before holiday. | Next non-holiday operating date if a market calendar is available. | `PASS` with calendar support; otherwise `WARNING` or `FAIL` depending on ambiguity. | Confirm holiday calendar or set context manually. |
| 5. DB latest price data not yet available | Previous complete required DB date, if within stale threshold. | Next operating trade date after that data date. | `WARNING` if still usable but delayed; `FAIL` if missing/too old. | Refresh market data, then rerun `daily_refresh`. |
| 6. data_date too old | Latest complete DB date. | Not refreshed as current if stale threshold breached. | `FAIL` or `WARNING` based on configured threshold. | Investigate data pipeline and refresh DB. |
| 7. trade_date cannot be resolved | Resolved latest complete DB date. | Empty/unset. | `FAIL` | Provide explicit trade date or add/repair market calendar support. |
| 8. account_id absent or context corrupted | Not resolved. | Not resolved. | `FAIL` | Recreate context with `context --account-id --data-date --trade-date` or pass account explicitly to future `daily_refresh`. |

## Proposed daily_refresh Contract

Future command:

```cmd
python scripts\n8n_paper_ops_runner.py daily_refresh
```

The command is not implemented in this stage.

Proposed sequence:

```text
1. Resolve account_id.
2. Resolve data_date / trade_date with read-only market DB checks.
3. Update context.json and context_latest.txt.
4. Run status refresh.
5. Run eod_dryrun refresh.
6. Write daily_refresh_latest.txt and daily_refresh_latest.json.
```

Proposed new output files:

```text
D:\n8n\workspace\stock_screener_ops\daily_refresh_latest.txt
D:\n8n\workspace\stock_screener_ops\daily_refresh_latest.json
```

Proposed `daily_refresh_latest.txt`:

```text
Daily Runner Refresh
runner_result: PASS/WARNING/FAIL
generated_at: ...
account_id: ...
data_date: ...
trade_date: ...
source_data_max_date: ...
source_data_ready_date: ...
stale: true/false
stale_days: ...
status_result: PASS/FAIL
eod_dryrun_result: PASS/FAIL
recommended_operator_action: ...
```

Proposed exit code:

| Condition | Exit code |
| --- | --- |
| All stages PASS | `0` |
| Refresh completed with WARNING but files are usable | `0` initially, with `runner_result: WARNING`; consider `1` only if Task Scheduler needs warning-as-failure semantics. |
| Date resolution fails, context cannot be loaded/written, or required stage fails | `1` |

The command must preserve existing `context`, `status`, and `eod_dryrun` behavior.

## Implemented Tests

Date resolution tests use temporary SQLite DB files and do not touch the operating market DB.

Covered cases:

| Case | Expected result |
| --- | --- |
| Required source max dates are all equal | `PASS`, `data_date` is that date, Friday resolves to Monday. |
| `daily_indicators` lags by one day | `WARNING`, `data_date` is the lagging complete date. |
| Required source data is empty | `FAIL`. |
| SPY `market_index` rows are missing | `FAIL`. |
| Friday `data_date` | next Monday `trade_date`. |
| Old complete `data_date` | `WARNING`, `stale=true`. |
| Missing `account_id` | `FAIL`. |
| Helper side effects | no `context.json`, `context_latest.txt`, `status_latest.txt`, or `eod_dryrun_latest.txt` files are written. |

## Next Implementation Step

Step 6-2B should implement `daily_refresh` orchestration on top of `resolve_daily_refresh_dates()`:

1. Resolve account/date.
2. If resolution is `FAIL`, write `daily_refresh_latest.txt/json` only and stop.
3. If resolution is `PASS` or accepted `WARNING`, write context.
4. Run existing `status` and `eod_dryrun` handlers.
5. Write `daily_refresh_latest.txt/json`.
6. Keep existing individual commands unchanged.

## Out of Scope For This Stage

- Implementing `daily_refresh`
- Adding Windows `.bat` or PowerShell wrappers
- Registering Task Scheduler
- Changing n8n workflow or adding `/refresh_status`
- Running Notion sync/write commands
- Executing broker actions or paper write/approval commands
- Modifying DB schema or data

# Next Runbook Day Environment Prep

## Purpose

`scripts\runbook_day_prep.py` reuses the 6-4B rollover preview and writes only the machine-local wrapper environment file. It does not run a stage or gate, create runbook state, write Notion data, connect to a broker, or execute an order.

## Command

```bat
python scripts\runbook_day_prep.py ^
  --workspace D:\n8n\workspace\stock_screener_ops ^
  --account-id paper_pilot_202606 ^
  --env-local ops\runbook_wrappers\_env.local.cmd ^
  --write-env-local ^
  --confirm-paper-test
```

The command writes only after rollover returns `PASS`, `safe_to_prepare=true`, and `already_exists=false`. It validates that account, dates, and `runbook_day_id` agree before and after writing.

## Files

- `_env.cmd`: tracked loader with repository/workspace paths, Conda activation, and validation.
- `_env.template.cmd`: tracked example only; it is never loaded automatically.
- `_env.local.cmd`: ignored machine-local account and runbook dates.

The local file, its `.tmp`, and its `.bak` are ignored by Git. Review the generated local file before proceeding.

## Write Policy

The new content is written to `_env.local.cmd.tmp` and read back for validation. If a previous local file exists, it is copied to `_env.local.cmd.bak`, then the validated temporary file atomically replaces the local file. A previous backup is overwritten, so only the most recent pre-update version is retained.

If the existing local values already match, the command returns `PASS` with `file_changed=false` and does not rewrite or back up the file. A blocked rollover or validation failure leaves the existing local file unchanged.

The process exit code is `0` for `PASS` and `2` for `BLOCKED`.

## Next Step

6-4C prepares configuration only. Do not treat a successful write as authorization to run a wrapper. Review `_env.local.cmd`; 6-4D remains responsible for the next operational verification.

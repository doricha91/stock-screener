# Next Runbook Day Environment Prep

## Purpose

scripts\runbook_day_prep.py reuses the 6-4B rollover preview and updates only the machine-local runbook-day file. It does not modify machine or account settings, run a stage or gate, create runbook state, access Notion, connect to a broker, or execute an order.

## Environment Files

- _machine.local.cmd: PC paths, Conda environment, pause, and Python encoding settings.
- _account.local.cmd: paper account identity and ACCOUNT_MODE=PAPER.
- _runbook_day.local.cmd: data date, trade date, and runbook-day ID.

The matching template files are tracked examples. _env.cmd never falls back to a template. All actual local files are ignored by Git and must be reviewed by the operator before use.

An old _env.local.cmd requires manual migration. The prep command reports BLOCKED and does not migrate it automatically.

## Command

    python scripts\runbook_day_prep.py ^
      --workspace D:\n8n\workspace\stock_screener_ops ^
      --account-id paper_pilot_202606 ^
      --account-local ops\runbook_wrappers\_account.local.cmd ^
      --runbook-day-local ops\runbook_wrappers\_runbook_day.local.cmd ^
      --write-env-local ^
      --confirm-paper-test

The account local file must exist, use ACCOUNT_MODE=PAPER, and match --account-id. The command writes only after rollover returns PASS, safe_to_prepare=true, and already_exists=false.

## Write Policy

Only _runbook_day.local.cmd is written. New content is written to _runbook_day.local.cmd.tmp and read back for validation. If a prior day file exists, it is copied to _runbook_day.local.cmd.bak, then the validated temporary file atomically replaces it.

Only the most recent backup is retained. Identical values return PASS with file_changed=false and do not rewrite the file. A blocked rollover or validation failure preserves the existing day file. PASS returns exit code 0; BLOCKED returns 2.

## Operational Boundary

6-4C-1 changes the environment structure only. Before operating, review all three local files. The full July 6 wrapper cycle is a separate 6-4D procedure; this prep result does not authorize wrapper execution.

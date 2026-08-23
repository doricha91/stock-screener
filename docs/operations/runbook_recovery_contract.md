# Runbook recovery contract

`scripts/runbook_recovery.py` provides a fail-closed exception for a progressed, contaminated paper/test runbook that cannot be completed, replayed, or retired. It never changes the source state. Authorization creates one immutable `runbook_recovery.v1` sidecar under `runbook_recoveries/<source_runbook_day_id>.json`.

## Safety boundary

- Recovery applies only to a paper/test account with exactly one progressed active runbook.
- The source state remains `ACTIVE_INCOMPLETE` in its original controller evidence. A valid sidecar gives it only the rollover classification `RECOVERY_EXCLUDED`.
- `RECOVERY_EXCLUDED` is not completed, legacy completed, or retired and is never a completed baseline.
- The canonical account execution ledger must have zero rows on every derived gap trading date.
- The restart dates must be canonical trading days and the trade date must be the first trading day after the data date.
- Missing historical runbooks, plans, executions, reviews, snapshots, benchmark points, and Notion pages are not backfilled.
- Status and preview are read-only. Authorize is create-only and requires all four explicit confirmations.
- A changed source hash, conflicting execution, malformed sidecar, invalid calendar identity, or target artifact without its exact state invalidates exclusion and restores the active blocker.

## Commands

Inspect the source without writing:

```bat
python scripts\runbook_recovery.py status ^
  --workspace D:\n8n\workspace\stock_screener_ops ^
  --account-id paper_pilot_202606 ^
  --runbook-day-id paper_pilot_202606_2026-08-13_2026-08-14
```

Preview the approved conditional pair without writing:

```bat
python scripts\runbook_recovery.py preview ^
  --workspace D:\n8n\workspace\stock_screener_ops ^
  --account-id paper_pilot_202606 ^
  --runbook-day-id paper_pilot_202606_2026-08-13_2026-08-14 ^
  --restart-data-date 2026-08-21 ^
  --restart-trade-date 2026-08-24 ^
  --reason "Stage A look-ahead contaminated; no real trades; missed interval accepted" ^
  --confirm-paper-test ^
  --confirm-contaminated-incomplete ^
  --confirm-no-real-trades ^
  --confirm-gap-without-backfill
```

After operator approval, run the same inputs with `authorize` instead of `preview`. Authorization must not be run merely because preview passes; the source SHA, latest completed identity, zero execution count, gap dates, and restart pair must be reviewed first.

## Rollover and initialization

An unconsumed valid sidecar makes the read-only rollover preview return only its pinned restart pair. Existing runbook-day prep consumes that result without accepting date overrides. Initialization permits that exact target and rejects a different target while the recovery is unconsumed.

After target creation, the target is an ordinary `ACTIVE_INCOMPLETE` runbook and the existing active guard applies. After the target reaches ordinary `STANDARD_COMPLETED`, rollover selects it as the latest completed baseline and returns to the unchanged sequential rule. Recovery never bypasses Stage A readiness/as-of validation or the Stage A–F completion contract.

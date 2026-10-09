# MFU-ML1-3B Prepare-First Fresh First Run

## Scope

`prepare-first-run` is the one-time onboarding transition between `init-account`
and the existing Stage A wrapper chain. The operator supplies only `account_id`
and `DATA_DATE`; the configured market calendar derives `TRADE_DATE`.

## Authority and identity

The account snapshot created by `init-account` records the canonical account ID.
After bootstrap, the account-local snapshot and current-state seed are the
authority for currency, initial cash, empty initial positions, and their content
hashes. The live account profile still owns currency declaration and exact
versioned strategy/universe references. A later profile `initial_cash` edit does
not rewrite or invalidate an otherwise intact materialized bootstrap.

The prepare identity is a semantic digest over:

- account ID, data date, derived trade date, and runbook day ID;
- exact strategy/universe references and binding digest;
- materialized currency, initial cash, and empty-position identity;
- the four bootstrap artifact hashes.

The binding digest contract itself remains unchanged.

## Durable transition

The command validates the canonical account root, bootstrap, lifecycle history,
binding, calendar coverage, account-local context, and all existing recovery and
operational-gap initialization guards before writing. It then writes, in order:

1. `_runbook_day.local.cmd` with the exact derived day context;
2. immutable account-local `lifecycle/prepare_first_run.json` evidence;
3. the existing `runbook_state.v2` A/READY, all-PENDING state.

The state is written last. Only the presence of an internally valid evidence,
matching operator context, matching bootstrap hashes, and matching pristine state
is classified as `PREPARED`. A partial set is `RECOVERY_REQUIRED` and is never
repaired or overwritten automatically.

An exact retry returns `REUSE` without changing bytes. A matching state that has
already progressed returns `RESUME_EXISTING_RUN`. Different dates, bindings,
identities, or corrupt evidence fail closed.

## Stage A boundary

Stage A blocks a versioned no-history account with a materialized account root
until valid prepare evidence and the pristine state exist. Existing progressed,
legacy, rollover, and recovery lifecycles keep their prior entry behavior. The
daily wrappers `00` through `04` are unchanged.

## ML1-3C interruption and concurrency hardening

C-1 verifies interruption at each write boundary: partial context/evidence
requires recovery; a fully saved valid state converges to byte-stable REUSE.

C-2 serializes prepare publication with an account-local OS lifetime lock
(Windows: exclusive-create `.prepare_first_run.lock` with delete-on-close;
POSIX: nonblocking flock on the account directory). It rechecks publication paths and state history after
acquisition. Contention fails closed using CONFLICT; a subsequent uncontended
retry validates the winning identity normally. The OS releases the lock on
normal return, handled exceptions, and process exit. Thus a post-state crash
still converges to REUSE. A pre-existing foreign/stale lock file blocks prepare
and fresh Stage A; no timeout-based stale-lock removal or automatic repair is provided.

Prepare checks lexical path ancestors before resolving or reading artifacts,
rejecting symlinks and Windows reparse points. State and prepare lifecycle
directories reject unattributable entries and temp residue. Retired or otherwise
disposed runs cannot be reused as pristine prepare state. Existing progressed
legacy states without prepare evidence retain the resume path.

This lock coordinates prepare-first-run callers only; it does not coordinate
external filesystem edits, other writers, or parallel daily account operations.
Hostile concurrent path replacement is not a descriptor-level security boundary.

## Deferred

Automatic interruption recovery/repair, exhaustive adversarial combinations,
non-empty initial positions, parallel accounts, scheduler changes, and real-account
activation remain outside this MFU. Actual symlink integration tests require OS
link-creation privilege; modeled path checks do not substitute for that coverage.

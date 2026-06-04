# PAPER20-1 Replay Wrapper Operational Smoke Scope

## Purpose

PAPER20-1 prepares the operational smoke scope for the PAPER19 Daily Plan replay wrapper.

This MFU is inventory and planning only. It does not run the replay wrapper, regenerate a Daily Plan, call Notion, export/sync, or mutate outputs/paper ledgers.

## Scope

Included:

- inspect existing `outputs/` artifacts for Daily Plan JSON sidecar candidates
- confirm replay wrapper and pure diff CLI availability through `--help`
- define baseline sidecar eligibility criteria
- propose the PAPER20-2 smoke account/date/path only when an eligible baseline exists
- define explicit `--output-dir` policy
- draft the PAPER20-2 smoke command

Excluded:

- replay wrapper execution
- Daily Plan generation
- generated smoke artifacts
- Notion API/write/export/sync
- actual export
- outputs/paper ledger mutation
- runbook finalization

## Current PAPER19 Replay Chain

PAPER19 closed out the minimum replay/same-date diff chain:

```text
Daily Plan JSON diff core/CLI
-> paper_daily_plan.v1 sidecar producer
-> sidecar replay diff smoke
-> minimal fingerprints
-> paper_config_hash.v1 helper and sidecar populate
-> replay wrapper minimal dry-run
```

Operational smoke will use:

```text
scripts/dev/replay_daily_plan_diff.py
scripts/dev/diff_daily_plan.py
```

CLI help checks passed for both commands during PAPER20-1 inventory.

## Baseline Sidecar Inventory

Inventory command results:

```text
outputs/**/daily_action_plan_*.json
-> no files found

outputs/**/paper_daily_plan_diff*
-> no files found

outputs/**/replay_diff*
-> outputs/paper_accounts/paper_sandbox/replay_diff/
-> outputs/paper_accounts/paper_sandbox/replay_diff/archive/
-> outputs/paper_accounts/paper_sandbox/replay_diff/archive/config_snapshots/

outputs/**/paper_config_snapshot*
-> outputs/paper_accounts/paper_sandbox/config_snapshots/paper_config_snapshot_20260520.json
-> outputs/paper_test/config_snapshots/paper_config_snapshot_20260520.json
```

Observed `paper_sandbox` artifacts:

| Artifact | Path | Status |
| --- | --- | --- |
| Daily Plan Markdown | `outputs/paper_accounts/paper_sandbox/daily_action_plan_20260520.md` | Exists |
| Daily Plan JSON sidecar | `outputs/paper_accounts/paper_sandbox/daily_action_plan_20260520.json` | Not found |
| Config snapshot | `outputs/paper_accounts/paper_sandbox/config_snapshots/paper_config_snapshot_20260520.json` | Exists |
| Current state snapshot | `outputs/paper_accounts/paper_sandbox/paper_current_state_20260520.json` | Exists |
| Replay diff directory | `outputs/paper_accounts/paper_sandbox/replay_diff/` | Exists |

No eligible `paper_daily_plan.v1` baseline sidecar was found in the current workspace.

Candidate metadata could not be verified because no `daily_action_plan_*.json` sidecar exists:

| Candidate | account_id | plan_date | schema_version | run_mode | official_run | items | fingerprints | config_hash | config_hash_policy | Eligibility |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| None found | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | Not eligible |

## Baseline Eligibility Criteria

PAPER20-2 smoke baseline must satisfy:

- `account_id = paper_sandbox`
- `schema_version = paper_daily_plan.v1`
- clear `plan_date`
- `items[]` exists
- generated artifact is not a unit-test fixture
- preferably official or committed Daily Plan sidecar
- `fingerprints` exists
- `config_hash` and `config_hash_policy` exist when available

If no eligible baseline sidecar exists, PAPER20-2 should not run the replay wrapper. The baseline sidecar must first be created or explicitly selected through a separate approved step.

## Proposed Smoke Date / Account

Current recommended account:

```text
account_id = paper_sandbox
```

Potential date based on existing artifacts:

```text
date = 2026-05-20
```

Reason:

- `daily_action_plan_20260520.md` exists for `paper_sandbox`
- `paper_config_snapshot_20260520.json` exists for `paper_sandbox`
- `paper_current_state_20260520.json` exists for `paper_sandbox`

Blocker:

```text
No eligible baseline sidecar exists yet:
outputs/paper_accounts/paper_sandbox/daily_action_plan_20260520.json
```

Therefore, PAPER20-2 smoke should use `paper_sandbox / 2026-05-20` only after the baseline sidecar is available.

## Explicit --output-dir Policy

PAPER20-2 must explicitly pass `--output-dir`.

Initial smoke must not omit `--output-dir` because the replay wrapper default can write under the account replay_diff directory.

Recommended explicit output directory:

```text
outputs/tmp_paper20_replay_smoke/
```

Alternative account-scoped smoke directory:

```text
outputs/paper_accounts/paper_sandbox/replay_diff_smoke/PAPER20_20260520/
```

Smoke generated artifacts must not be committed by default.

## Smoke Command Draft

Do not execute in PAPER20-1.

Draft command for PAPER20-2 after an eligible baseline sidecar exists:

```cmd
python scripts\dev\replay_daily_plan_diff.py --account-id paper_sandbox --date 2026-05-20 --baseline-plan outputs\paper_accounts\paper_sandbox\daily_action_plan_20260520.json --output-dir outputs\tmp_paper20_replay_smoke --json
```

If the baseline sidecar path differs, update only `--baseline-plan` and keep the explicit `--output-dir` policy.

## Safety Policy

PAPER20 operational smoke safety policy:

- replay wrapper is for dry-run verification
- baseline sidecar must not be overwritten
- official Daily Plan artifact must not be overwritten
- Notion API/write/export/sync is forbidden
- actual/export/sync/commit/append is forbidden
- outputs/paper ledger mutation is forbidden
- generated smoke artifacts are not committed by default
- `--output-dir` must be explicit for initial smoke

## Expected PASS / WARNING / FAIL Interpretation

`PASS`:

- baseline and regenerated sidecars match on compared Daily Plan fields
- no core row/fingerprint difference requires action

`WARNING`:

- price/warning/reason/note differs
- `config_hash` or other fingerprint differs
- duplicate row key is detected
- cause candidate exists but root cause is not confirmed

`FAIL`:

- baseline missing or malformed
- account/date mismatch
- symbol set differs
- action differs
- quantity differs

Any WARNING/FAIL must be documented before considering further operational use. No actual/export/sync step is authorized by a PASS result.

## Non-scope

This MFU does not perform:

- replay wrapper execution
- Daily Plan generation
- actual export
- Notion API calls
- Notion write/export/sync
- outputs/paper ledger mutation
- generated smoke artifact commit
- stable `plan_item_id`
- `universe_hash`
- `market_data_asof`
- `indicator_snapshot_hash`
- `state_snapshot_hash`
- final runbook writing

## PAPER20-2 Recommendation

Recommended PAPER20-2:

```text
PAPER20-2 Baseline Sidecar Availability Check + Operational Smoke
```

Required precondition:

```text
An eligible paper_sandbox paper_daily_plan.v1 baseline sidecar exists.
```

If the sidecar remains absent, PAPER20-2 should stop with a documented blocker rather than generating/replaying implicitly.

If the sidecar exists, PAPER20-2 should:

- run the draft command with explicit `--output-dir`
- confirm regenerated artifacts stay under the smoke output directory
- confirm baseline/official artifact overwrite did not occur
- summarize PASS/WARNING/FAIL
- keep generated artifacts uncommitted unless explicitly approved

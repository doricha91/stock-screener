# PAPER20-2 Baseline Sidecar Check and Conditional Operational Smoke

## Purpose

PAPER20-2 re-checks whether an eligible `paper_sandbox` Daily Plan JSON sidecar exists for an operational replay wrapper smoke.

The conditional rule is:

```text
eligible baseline sidecar exists -> run replay wrapper with explicit --output-dir
eligible baseline sidecar missing -> do not run replay wrapper, document blocker
```

This run followed Case A: no eligible baseline sidecar was found, so no replay wrapper smoke was executed.

## PAPER20-1 Baseline Blocker Recap

PAPER20-1 found:

- no `outputs/**/daily_action_plan_*.json` files
- `outputs/paper_accounts/paper_sandbox/daily_action_plan_20260520.md` exists
- `outputs/paper_accounts/paper_sandbox/daily_action_plan_20260520.json` does not exist
- `paper_config_snapshot_20260520.json` exists
- `paper_current_state_20260520.json` exists
- `outputs/paper_accounts/paper_sandbox/replay_diff/` exists

PAPER20-1 recommended `paper_sandbox / 2026-05-20` as the operational smoke candidate only after an eligible baseline sidecar becomes available.

## Baseline Sidecar Re-check

Re-check results:

```text
outputs/**/daily_action_plan_*.json
-> no files found

outputs/**/daily_action_plan_20260520.json
-> no files found

outputs/**/paper_config_snapshot_20260520.json
-> outputs/paper_accounts/paper_sandbox/config_snapshots/paper_config_snapshot_20260520.json
-> outputs/paper_test/config_snapshots/paper_config_snapshot_20260520.json

outputs/**/paper_current_state_20260520.json
-> outputs/paper_accounts/paper_sandbox/paper_current_state_20260520.json
-> outputs/paper_test/paper_current_state_20260520.json
```

Direct path check:

| Path | Exists |
| --- | --- |
| `outputs/paper_accounts/paper_sandbox/daily_action_plan_20260520.md` | yes |
| `outputs/paper_accounts/paper_sandbox/daily_action_plan_20260520.json` | no |

CLI availability checks:

- `python scripts\dev\replay_daily_plan_diff.py --help` passed
- `python scripts\dev\diff_daily_plan.py --help` passed

No baseline sidecar content was available for metadata inspection.

## Eligibility Decision

Eligibility result:

```text
eligible_baseline_sidecar = false
```

Reason:

```text
Expected baseline sidecar is missing:
outputs/paper_accounts/paper_sandbox/daily_action_plan_20260520.json
```

The following fields could not be verified because no sidecar file exists:

- `schema_version = paper_daily_plan.v1`
- `account_id = paper_sandbox`
- `plan_date = 2026-05-20`
- `items[]`
- `fingerprints`
- `config_hash`
- `config_hash_policy`

## Conditional Smoke Execution

Smoke execution result:

```text
smoke_executed = false
```

The replay wrapper was not executed because the eligible baseline sidecar is missing.

No Daily Plan generation was attempted.

No sidecar creation was attempted.

No generated smoke artifact was created.

## Output-dir Policy

PAPER20-2 preserves the PAPER20-1 policy:

```text
Initial operational smoke must explicitly pass --output-dir.
Do not omit --output-dir.
```

Preferred smoke output directory remains:

```text
outputs/tmp_paper20_replay_smoke/
```

Generated smoke artifacts must not be committed unless explicitly approved.

## Smoke Result

No smoke result exists for PAPER20-2 because the smoke was intentionally not executed.

Fields are therefore:

| Field | Value |
| --- | --- |
| wrapper exit code | n/a |
| run_id | n/a |
| regenerated Markdown path | n/a |
| regenerated JSON sidecar path | n/a |
| generated config snapshot path | n/a |
| diff JSON report path | n/a |
| diff Markdown report path | n/a |
| overall_status | n/a |
| write_executed | n/a, wrapper not executed |
| actual_executed | n/a, wrapper not executed |
| notion_api_called | n/a, wrapper not executed |
| notion_sync_executed | n/a, wrapper not executed |
| notion_write_export_sync_executed | n/a, wrapper not executed |
| commit_append_executed | n/a, wrapper not executed |

## PASS / WARNING / FAIL Interpretation

For the future PAPER20-3 or resumed PAPER20-2 smoke:

`PASS`:

- compared Daily Plan fields match
- operational replay smoke is usable for read-only validation
- PASS does not authorize actual/export/sync

`WARNING`:

- price, warning, reason, note, fingerprint, or `config_hash` differs
- a cause candidate exists, but root cause is not confirmed
- manual review is required before operational use

`FAIL`:

- baseline missing or malformed
- account/date mismatch
- symbol/action/quantity differs
- replay wrapper smoke fails

Current PAPER20-2 outcome is a blocker before smoke, not a PASS/WARNING/FAIL replay result.

## Safety Verification

Verified:

- replay wrapper was not executed
- Daily Plan generation was not executed
- baseline sidecar was not created
- official Daily Plan artifact was not regenerated
- Notion API was not called
- Notion write/export/sync was not executed
- actual export was not executed
- outputs/paper ledger was not modified
- generated smoke artifacts were not created or staged

## Generated Artifact Policy

No generated artifacts were created in PAPER20-2.

If future smoke creates artifacts under `outputs/tmp_paper20_replay_smoke/` or account smoke directories, they must remain uncommitted unless separately approved.

## Non-scope

This MFU did not perform:

- baseline sidecar generation
- Daily Plan generation
- official artifact regeneration
- replay wrapper execution
- actual export
- Notion API calls
- Notion write/export/sync
- outputs/paper ledger mutation
- generated artifact commit
- stable `plan_item_id`
- `universe_hash`
- `market_data_asof`
- `indicator_snapshot_hash`
- `state_snapshot_hash`
- final runbook writing

## PAPER20-3 Recommendation

Recommended next MFU:

```text
PAPER20-3 Baseline Sidecar Creation Approval / Controlled Baseline Capture
```

Goal:

- decide how to create or capture an eligible `paper_sandbox / 2026-05-20` baseline sidecar
- preserve existing Markdown and official artifacts
- avoid implicit replay wrapper execution until the sidecar exists
- keep generated artifacts uncommitted unless explicitly approved

Once the baseline sidecar exists, resume the operational smoke with:

```cmd
python scripts\dev\replay_daily_plan_diff.py --account-id paper_sandbox --date 2026-05-20 --baseline-plan outputs\paper_accounts\paper_sandbox\daily_action_plan_20260520.json --output-dir outputs\tmp_paper20_replay_smoke --json
```

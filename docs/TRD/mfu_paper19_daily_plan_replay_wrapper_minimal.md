# PAPER19-10 Daily Plan Replay Wrapper Minimal Dry-run

## Purpose

PAPER19-10 adds a minimal Daily Plan replay/same-date diff wrapper.

The wrapper accepts an existing baseline Daily Plan JSON sidecar, generates a replay-only regenerated Daily Plan artifact for the same account/date, and compares baseline vs regenerated sidecars through the existing PAPER19 replay diff core.

This is dry-run orchestration only. It does not execute actual export, Notion sync, paper ledger commit/append, or external delivery.

## Scope

Implemented scope:

- add `scripts/dev/replay_daily_plan_diff.py`
- validate `account_id`, date, and baseline sidecar metadata before generation
- create a replay run directory under `replay_diff/runs/{run_id}`
- generate regenerated Markdown and JSON sidecar in the run directory
- write regenerated config snapshot inside the run directory
- call `core.paper_replay_diff.compare_daily_plan_files`
- write JSON and Markdown replay diff reports in the run directory
- return safety markers in the wrapper summary

Out of scope:

- actual export
- Notion API/write/export/sync
- paper ledger commit/append
- Manual Execution/Review replay
- schema/view drift
- `plan_item_id`
- stable row id refactor

## CLI

Command:

```cmd
python scripts\dev\replay_daily_plan_diff.py --account-id paper_sandbox --date 2026-05-20 --baseline-plan <path> --output-dir <path> --json
```

Supported options:

```text
--account-id
--date
--baseline-plan
--output-dir
--run-id
--json
```

The CLI intentionally does not expose:

```text
--confirm-actual
--notion
--sync
--commit
```

## Wrapper Flow

Flow:

1. Normalize and validate the requested date.
2. Resolve the output root.
3. Load the baseline Daily Plan JSON sidecar.
4. Stop before generation if the baseline is missing, malformed, or has account/date mismatch.
5. Create `{output_dir}/runs/{run_id}/`.
6. Load the official paper state for the requested account/date.
7. Call `generate_daily_plan()` with replay-only output paths.
8. Write regenerated Markdown and JSON sidecar in the run directory.
9. Compare baseline sidecar and regenerated sidecar with `core.paper_replay_diff`.
10. Write diff JSON/Markdown reports in the run directory.
11. Emit a wrapper summary with dry-run safety markers.

## Baseline / Regenerated Handling

Baseline:

- must be an existing Daily Plan JSON sidecar
- must match `account_id`
- must match `plan_date`
- is never overwritten by the wrapper

Regenerated:

- is generated into the replay run directory
- uses `run_mode = replay`
- uses `official_run = false`
- writes `regenerated_daily_action_plan_{YYYYMMDD}.md`
- writes `regenerated_daily_action_plan_{YYYYMMDD}.json`
- writes `regenerated_paper_config_snapshot_{YYYYMMDD}.json`

`run_mode` / `official_run` may differ from baseline metadata. Diff judgment remains delegated to `core.paper_replay_diff`; the wrapper does not interpret this as root cause.

## Output Path Policy

Default output root:

```text
outputs/paper_accounts/{account_id}/replay_diff/
```

Per-run output structure:

```text
{output_dir}/runs/{run_id}/regenerated_daily_action_plan_{YYYYMMDD}.md
{output_dir}/runs/{run_id}/regenerated_daily_action_plan_{YYYYMMDD}.json
{output_dir}/runs/{run_id}/regenerated_paper_config_snapshot_{YYYYMMDD}.json
{output_dir}/runs/{run_id}/paper_daily_plan_diff_{YYYYMMDD}.json
{output_dir}/runs/{run_id}/paper_daily_plan_diff_{YYYYMMDD}.md
```

Tests use `tmp_path` and explicit `--output-dir` so they do not write to real account outputs.

## Dry-run Safety Policy

The wrapper summary includes:

```json
{
  "write_executed": false,
  "actual_executed": false,
  "notion_api_called": false,
  "notion_sync_executed": false,
  "notion_write_export_sync_executed": false,
  "commit_append_executed": false
}
```

Safety rules:

- baseline is never overwritten
- official Daily Plan artifact is never overwritten
- regenerated artifacts are confined to the replay run directory
- Notion API is not called
- Notion write/export/sync is not called
- paper ledger commit/append is not called

## Diff Integration

The wrapper does not implement diff judgment.

Diff judgment remains in:

```text
core.paper_replay_diff
```

Wrapper integration uses:

```text
compare_daily_plan_files()
write_daily_plan_diff_report()
```

Cause candidates remain non-causal. The report may say `config_hash changed; this is a possible cause candidate`, but must not say the plan changed because config changed.

## Test Coverage

Added tests cover:

- `--help`
- missing baseline stops before generation
- baseline account/date mismatch stops before generation
- replay run directory creation
- regenerated sidecar creation
- baseline overwrite prevention
- diff JSON/Markdown report creation
- same-plan wrapper flow returns PASS
- quantity diff returns FAIL / `QUANTITY_DIFF`
- config hash diff returns WARNING / `CONFIG_OR_UNIVERSE_DIFF`
- safety markers remain false
- no Notion/export/sync path is invoked
- `tmp_path` output isolation

## Limitations

- The wrapper currently calls the existing Daily Plan generator directly; heavy data dependencies are mocked in unit tests.
- Default output root can write under account replay diff if `--output-dir` is omitted.
- The wrapper does not yet accept an externally generated regenerated sidecar.
- `run_id` defaults to UTC timestamp, which is suitable for uniqueness but not deterministic unless explicitly provided.
- Stable row id and `plan_item_id` remain out of scope.

## PAPER19 Closeout Recommendation

PAPER19 can be prepared for closeout after this wrapper is accepted because the minimum chain now exists:

```text
Daily Plan sidecar -> config hash fingerprint -> replay wrapper -> replay diff JSON/Markdown report
```

Recommended next step:

```text
PAPER19 Closeout
```

Closeout should summarize:

- Daily Plan JSON sidecar contract
- replay diff core
- sidecar compatibility smoke
- config hash policy/helper
- replay wrapper dry-run safety
- remaining work: stable row id, universe/market fingerprints, heavier producer contracts

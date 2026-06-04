# PAPER20-4 Dev-only Daily Plan Controlled Baseline Capture CLI

## 1. Purpose

PAPER20-4 resolves the PAPER20-3 blocker by adding a development-only Daily Plan baseline capture CLI under `scripts/dev/`.

The CLI is intended to create a controlled Daily Plan Markdown artifact, `paper_daily_plan.v1` JSON sidecar, and config snapshot under an explicit `--output-dir` only.

This is not an official operations CLI and it does not perform replay wrapper smoke. PAPER20-5 is the intended first real controlled capture/smoke task.

## 2. PAPER20-3 Blocker Recap

PAPER20-3 stopped before capture because `scripts/run_paper_daily_plan.py` only accepted `--date`.

That meant there was no safe way to create `paper_sandbox / 2026-05-26` Daily Plan outputs in a controlled directory without risking writes to official artifact paths.

PAPER20-4 intentionally does not change the official CLI contract. It adds a dev-only helper instead.

## 3. Dev-only CLI Design

New CLI:

```cmd
python scripts\dev\capture_daily_plan_baseline.py --account-id paper_sandbox --date 2026-05-26 --output-dir outputs\tmp_paper20_baseline_capture --json
```

The CLI calls `core.daily_plan_generator.generate_daily_plan()` directly with explicit controlled output paths.

Default metadata:

```text
run_mode = baseline_capture
official_run = false
```

It loads the same official paper state provider used by the official Daily Plan path, but writes generated artifacts only under `--output-dir`.

## 4. CLI Contract

Required options:

```text
--account-id
--date
--output-dir
```

Optional options:

```text
--run-mode
--json
```

`--output-dir` is required. There is no default to `outputs/paper_accounts/...` or any official artifact directory.

The accepted date formats are:

```text
YYYY-MM-DD
YYYYMMDD
```

## 5. Output-dir Safety Policy

Expected controlled outputs:

```text
{output_dir}/daily_action_plan_YYYYMMDD.md
{output_dir}/daily_action_plan_YYYYMMDD.json
{output_dir}/config_snapshots/paper_config_snapshot_YYYYMMDD.json
```

The helper also uses an archive path under:

```text
{output_dir}/archive/config_snapshots/
```

The CLI must not write the official Daily Plan artifact path and must not overwrite baseline or official artifacts outside the explicit `--output-dir`.

## 6. Generated Artifact Policy

Generated baseline capture artifacts are smoke artifacts.

They are not committed by default:

```text
outputs/tmp*
outputs/tmp_paper20_baseline_capture/*
outputs/tmp_paper20_replay_smoke/*
outputs/paper_accounts/*
```

PAPER20-4 tests use `tmp_path` and fake generation to avoid creating real smoke artifacts.

## 7. Sidecar Eligibility Check

After generation, the CLI loads the generated JSON sidecar and checks:

```text
schema_version = paper_daily_plan.v1
account_id matches input
plan_date matches input
items is a list
fingerprints is an object
config_hash presence
config_hash_policy = paper_config_hash.v1
```

Missing `config_hash` or `config_hash_policy` is reported as a warning, not a hard failure.

Missing or malformed sidecar is a failure.

## 8. Safety Summary

JSON output includes safety markers:

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

These markers mean the dev helper did not execute actual/export/sync/commit/append paths. File writes are limited to the explicit controlled output directory.

## 9. Test Coverage

Added tests cover:

```text
--help exits successfully
--output-dir is required
tmp_path output-dir isolation
generate_daily_plan call arguments
run_mode = baseline_capture
official_run = false
safety marker output
successful sidecar eligibility
missing sidecar failure
malformed sidecar failure
config_hash missing warning
```

The tests monkeypatch `generate_daily_plan()` and do not call Notion, export, sync, commit, append, or actual operations.

## 10. Non-scope

PAPER20-4 does not do the following:

```text
actual 2026-05-26 controlled baseline capture
replay wrapper smoke
official run_paper_daily_plan.py behavior change
Notion API call
Notion write/export/sync
actual export
Manual Execution commit
Manual Review append
source-of-truth ledger commit/append
account/position/current_state ledger mutation
generated artifact commit
stable plan_item_id implementation
universe_hash implementation
market_data_asof implementation
indicator_snapshot_hash implementation
state_snapshot_hash implementation
official run_paper_daily_plan.py --output-dir support
```

## 11. PAPER20-5 Recommendation

PAPER20-5 should run the first real controlled capture and replay smoke:

```cmd
python scripts\dev\capture_daily_plan_baseline.py --account-id paper_sandbox --date 2026-05-26 --output-dir outputs\tmp_paper20_baseline_capture --json
python scripts\dev\replay_daily_plan_diff.py --account-id paper_sandbox --date 2026-05-26 --baseline-plan outputs\tmp_paper20_baseline_capture\daily_action_plan_20260526.json --output-dir outputs\tmp_paper20_replay_smoke --json
```

PAPER20-5 must still treat generated artifacts as non-committable smoke outputs and must document PASS / WARNING / FAIL results without running Notion/export/sync/actual/commit/append operations.

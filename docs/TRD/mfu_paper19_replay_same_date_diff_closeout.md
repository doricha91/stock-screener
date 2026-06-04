# PAPER19 Replay / Same-date Diff Closeout

## Purpose

PAPER19 built the minimum reproducibility check for paper Daily Plans.

The goal was not to improve performance or change strategy logic. The goal was to answer:

```text
When an official/committed Daily Plan and a regenerated Daily Plan for the same account/date are compared, what changed?
```

PAPER19 records differences and fingerprint cause candidates without claiming confirmed root cause.

## PAPER19 Scope

Included:

- Daily Plan JSON diff core and CLI
- `paper_daily_plan.v1` JSON sidecar producer
- sidecar compatibility smoke tests
- minimal sidecar fingerprints
- `paper_config_hash.v1` policy and helper
- sidecar `config_hash` / `config_hash_policy` population
- minimal dry-run replay wrapper

Excluded:

- actual export
- Notion API/write/export/sync
- paper ledger commit/append
- Manual Execution/Review replay
- Notion sync replay
- schema/view drift
- stable row id / `plan_item_id`
- richer universe/market/indicator/state hashes

## Completed Work

Completed PAPER19 commits:

```text
a98e6e54dd97b15801698c799a55a5cb9149b20d
docs: define PAPER19 replay same-date diff scope

a6a40ed5ea0c743b674034407f5c68061989def4
feat: add PAPER19 daily plan replay diff core

bef90e951201152d73694b1c120b5bb76a124a04
docs: design PAPER19 daily plan replay source alignment

247cb79908413911b8e92ab524ad94d158559a63
docs: define PAPER19 daily plan JSON artifact contract

27d122d0249a0ac37ed3d020c364eaa6051c3678
feat: add PAPER19 daily plan JSON sidecar

a252cdddae7dcffdd936dce5558b70e1c5b41202
test: connect PAPER19 daily plan sidecar to replay diff

24e323118c9cda189edff50a3ef464eb7f6bcdbf
feat: populate PAPER19 daily plan sidecar fingerprints

da9abb1ea2d2fb5b96c37d8f10359c8bf57cd59f
docs: define PAPER19 config hash policy

beb128ff93d3fb861f0bdc03ec46fb09da5de65a
feat: add PAPER19 config hash fingerprints

f4b02d2d5c461e9f196468f5ab5ed65f8c5428dd
feat: add PAPER19 daily plan replay wrapper
```

Functional completion:

- baseline/regenerated Daily Plan JSON diff core implemented
- `scripts/dev/diff_daily_plan.py` implemented
- `paper_daily_plan.v1` sidecar generated beside the existing Markdown Daily Plan
- existing Markdown Daily Plan output preserved
- `paper_config_snapshot_YYYYMMDD.json` meaning and path preserved
- sidecar compatibility with replay diff verified by smoke tests
- `generator_version`, `config_snapshot_path`, and `state_snapshot_path` populated
- `paper_config_hash.v1` helper implemented
- sidecar `config_hash` and `config_hash_policy` populated when config snapshot is readable
- `scripts/dev/replay_daily_plan_diff.py` minimal dry-run wrapper implemented

## Delivered Artifacts

Core and CLI:

```text
core/paper_replay_diff.py
scripts/dev/diff_daily_plan.py
scripts/dev/replay_daily_plan_diff.py
core/paper_config_hash.py
```

Daily Plan sidecar integration:

```text
core/daily_plan_generator.py
scripts/run_paper_daily_plan.py
```

Tests:

```text
tests/test_paper_replay_diff.py
tests/test_daily_plan_json_sidecar.py
tests/test_paper_config_hash.py
tests/test_paper19_sidecar_replay_diff_smoke.py
tests/test_paper19_replay_wrapper.py
```

Documentation:

```text
docs/TRD/mfu_paper19_replay_same_date_diff_scope_and_contract.md
docs/TRD/mfu_paper19_daily_plan_json_diff_core.md
docs/TRD/mfu_paper19_daily_plan_replay_source_alignment_and_wrapper_design.md
docs/TRD/mfu_paper19_daily_plan_json_artifact_contract_and_generation_structure_check.md
docs/TRD/mfu_paper19_daily_plan_json_sidecar_producer.md
docs/TRD/mfu_paper19_sidecar_diff_smoke_and_fingerprint_scope.md
docs/TRD/mfu_paper19_daily_plan_sidecar_minimal_fingerprints.md
docs/TRD/mfu_paper19_config_hash_policy_and_replay_diff_decision.md
docs/TRD/mfu_paper19_config_hash_helper_and_sidecar_populate.md
docs/TRD/mfu_paper19_daily_plan_replay_wrapper_minimal.md
```

## Replay / Same-date Diff Flow

Minimum flow:

```text
1. baseline sidecar input
2. account/date validation
3. replay-only runs/{run_id} directory creation
4. generate_daily_plan() called with run_mode=replay and official_run=false
5. regenerated Markdown / JSON sidecar / config snapshot generated in the replay run directory
6. compare_daily_plan_files() compares baseline and regenerated sidecars
7. JSON/Markdown diff report generated
8. safety markers remain false
```

The wrapper does not implement diff judgment. Diff policy remains in `core.paper_replay_diff`.

## JSON Sidecar Contract

The Daily Plan JSON sidecar schema is:

```text
paper_daily_plan.v1
```

The sidecar includes:

- `account_id`
- `plan_date`
- `run_mode`
- `official_run`
- `generated_at`
- normalized `items`
- `fingerprints`

Item normalization maps existing Daily Plan action item fields:

```text
type -> action
shares -> quantity
price -> price
symbol -> symbol
warning -> warning
reason -> reason
note -> note
```

The sidecar is generated from structured Daily Plan data, not by parsing Markdown. Existing `daily_action_plan_YYYYMMDD.md` remains the official human-readable artifact.

## Config Hash / Fingerprint Policy

Implemented fingerprint fields:

- `generator_version`
- `config_snapshot_path`
- `state_snapshot_path`
- `config_hash`
- `config_hash_policy`

`config_snapshot_path` remains trace metadata. It is not proof of config equality or difference.

`paper_config_hash.v1`:

- outputs `sha256:<hex>`
- excludes volatile/runtime/local metadata such as `generated_at`, `run_id`, and path-like fields
- excludes secret/token/env-like fields
- changes when semantic config fields change

Replay diff treats `config_hash` differences as WARNING cause candidates:

```text
config_hash changed; this is a possible cause candidate.
```

It does not claim that config change caused the plan difference.

## Replay Wrapper Dry-run Safety

The replay wrapper safety policy:

- baseline/official artifacts are not overwritten
- regenerated artifacts are written only under the replay run directory
- `write_executed=false`
- `actual_executed=false`
- `notion_api_called=false`
- `notion_sync_executed=false`
- `notion_write_export_sync_executed=false`
- `commit_append_executed=false`
- Notion API/write/export/sync is not executed
- outputs/paper ledger is not modified

The wrapper CLI intentionally has no `--confirm-actual`, `--notion`, `--sync`, or `--commit` option.

## Validation Summary

PAPER19-10 validation commands:

```cmd
python scripts\dev\replay_daily_plan_diff.py --help
python scripts\dev\diff_daily_plan.py --help
python scripts\run_paper_daily_plan.py --help

pytest tests\test_paper19_replay_wrapper.py
pytest tests\test_paper_replay_diff.py
pytest tests\test_daily_plan_json_sidecar.py
pytest tests\test_paper_config_hash.py
pytest tests\test_paper19_sidecar_replay_diff_smoke.py
```

PAPER19-10 validation result:

- replay wrapper tests: 6 passed
- replay diff tests: 15 passed
- Daily Plan sidecar tests: 6 passed
- config hash tests: 5 passed
- sidecar replay smoke tests: 6 passed

Pytest cache permission warnings were observed in this environment. They did not indicate functional test failure.

## Known Limitations

- If `--output-dir` is omitted, the wrapper may create artifacts under the account `replay_diff` directory.
- Real operational end-to-end smoke with an actual `paper_sandbox` baseline sidecar is still limited.
- Unit tests isolate heavy data dependencies with fake generator behavior.
- Stable row id / `plan_item_id` is not implemented.
- `universe_hash` is not implemented.
- `market_data_asof` is not implemented.
- `indicator_snapshot_hash` is not implemented.
- `state_snapshot_hash` is not implemented.
- Manual Execution/Review replay is not included.
- Notion sync replay is not included.

## Deferred Items

Deferred hardening candidates:

- stable `plan_item_id` / row identity
- richer fingerprints: `universe_hash`, `market_data_asof`, `indicator_snapshot_hash`, `state_snapshot_hash`
- operational smoke runbook for real `paper_sandbox` baseline sidecars
- explicit `--output-dir` usage policy
- schema/view drift check
- external delivery adapter

## Closeout Decision

PAPER19 is closeout-ready because the minimal Daily Plan replay/same-date diff chain now exists:

```text
Daily Plan JSON sidecar generation
-> config hash fingerprints
-> pure diff core
-> sidecar smoke validation
-> dry-run replay wrapper
-> JSON/Markdown diff report
```

Actual export, Notion sync, paper ledger writes, and external delivery remain outside PAPER19.

## Next MFU Recommendation

Recommended next MFU:

```text
PAPER20 Replay Wrapper Operational Smoke / Runbook
```

Suggested scope:

- run a manual smoke with a real `paper_sandbox` baseline sidecar
- require explicit `--output-dir`
- document PASS/WARNING/FAIL interpretation
- document how to archive or inspect replay run outputs
- keep actual/export/sync/ledger mutation out of scope

Follow-up candidates:

- stable `plan_item_id` / row identity hardening
- richer fingerprints: `universe_hash`, `market_data_asof`, `indicator_snapshot_hash`, `state_snapshot_hash`
- schema/view drift check
- external delivery adapter

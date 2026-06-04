# PAPER20-7 Producer Source Rename and Config Hash Normalization

## Purpose

PAPER20-7 resolves the high-confidence false `config_hash` WARNING observed in the PAPER20-5 controlled replay smoke.

The root cause was that the config snapshot field named `source` represented artifact producer provenance, not a semantic strategy, universe, or market-data input. Baseline capture and replay wrapper used different producer names, so the config hash changed even though Daily Plan items and semantic config were unchanged.

## PAPER20-6 False Warning Recap

PAPER20-6 classified the prior `config_hash` WARNING as a high-confidence false warning:

- Daily Plan action, symbol, quantity, price, and warning diffs were zero.
- Normalized config diff was `source` only.
- Baseline `source` was `capture_daily_plan_baseline`.
- Regenerated `source` was `replay_daily_plan_diff`.
- No semantic config difference was confirmed.

## source vs producer_source Decision

New config snapshot artifacts now use `producer_source` instead of `source`.

`producer_source` means the tool or command that produced the artifact, for example:

- `capture_daily_plan_baseline`
- `replay_daily_plan_diff`
- `run_paper_daily_plan`

This field is provenance metadata. It must not be confused with semantic fields such as `strategy_source`, `universe_source`, or `market_data_source`.

## Hash Normalization Change

`paper_config_hash.v1` now excludes both `source` and `producer_source` from the normalized hash input.

The following provenance/runtime/local metadata differences do not change `config_hash`:

- `generated_at`
- `run_id`
- path-like keys
- `source`
- `producer_source`

The hash policy still uses deterministic JSON canonicalization and `sha256:<hex>` output.

## Backward Compatibility

Existing PAPER20-5 artifacts may still contain `source`. The hash helper treats both legacy `source` and new `producer_source` as provenance metadata, so old and new artifacts can be compared without producer-name-only hash drift.

New artifacts should not emit `source`; they should emit `producer_source`.

## Semantic Source Field Policy

The hash helper does not exclude semantic source fields merely because their names contain `source`.

These fields remain hash inputs because they can affect Daily Plan decisions:

- `strategy_source`
- `strategy_profile_id`
- `universe_source`
- `universe_id`
- `market_data_source`
- `config_profile_id`
- `risk_profile_id`

Future policies may define richer semantic source fingerprints, but PAPER20-7 does not implement those.

## Test Coverage

Validation executed:

- `python scripts\dev\capture_daily_plan_baseline.py --help`
- `python scripts\dev\replay_daily_plan_diff.py --help`
- `pytest tests\test_paper_config_hash.py`
- `pytest tests\test_paper_config_snapshot.py`
- `pytest tests\test_paper20_capture_daily_plan_baseline.py`
- `pytest tests\test_paper19_replay_wrapper.py`

Covered cases:

- `source` only differs -> config hash is unchanged.
- `producer_source` only differs -> config hash is unchanged.
- `source` vs `producer_source` representation differs -> config hash is unchanged.
- `strategy_source` differs -> config hash changes.
- `universe_source` differs -> config hash changes.
- `market_data_source` differs -> config hash changes.
- generated/runtime/path/provenance metadata changes -> config hash is unchanged.
- New config snapshot payload uses `producer_source`.

## Controlled Replay Smoke Recheck

This smoke is not historical actual-operation verification. It is controlled operational smoke based on current code, current database, and current configuration.

Baseline capture command:

```cmd
python scripts\dev\capture_daily_plan_baseline.py --account-id paper_sandbox --date 2026-05-26 --output-dir outputs\tmp_paper20_baseline_capture --json
```

Baseline result:

- exit code: `0`
- sidecar: `outputs\tmp_paper20_baseline_capture\daily_action_plan_20260526.json`
- config snapshot: `outputs\tmp_paper20_baseline_capture\config_snapshots\paper_config_snapshot_20260526.json`
- `producer_source`: `capture_daily_plan_baseline`
- `schema_version`: `paper_daily_plan.v1`
- `items_count`: `0`
- `config_hash_policy`: `paper_config_hash.v1`

Replay smoke command:

```cmd
python scripts\dev\replay_daily_plan_diff.py --account-id paper_sandbox --date 2026-05-26 --baseline-plan outputs\tmp_paper20_baseline_capture\daily_action_plan_20260526.json --output-dir outputs\tmp_paper20_replay_smoke --json
```

Replay result:

- exit code: `0`
- run_id: `20260604_115029`
- regenerated sidecar: `outputs\tmp_paper20_replay_smoke\runs\20260604_115029\regenerated_daily_action_plan_20260526.json`
- regenerated config snapshot: `outputs\tmp_paper20_replay_smoke\runs\20260604_115029\regenerated_paper_config_snapshot_20260526.json`
- diff JSON: `outputs\tmp_paper20_replay_smoke\runs\20260604_115029\paper_daily_plan_diff_20260526.json`
- diff Markdown: `outputs\tmp_paper20_replay_smoke\runs\20260604_115029\paper_daily_plan_diff_20260526.md`
- overall_status: `PASS_WITH_METADATA_DIFF`
- diff_categories: `METADATA_DIFF`
- cause_candidates: `[]`

The prior config_hash false WARNING was resolved. The remaining status is metadata-only.

## Safety Verification

Confirmed safety markers in replay summary:

- `write_executed=false`
- `actual_executed=false`
- `notion_api_called=false`
- `notion_sync_executed=false`
- `notion_write_export_sync_executed=false`
- `commit_append_executed=false`

No Notion API/write/export/sync was executed. No actual export was executed. No Manual Execution/Review commit or append was executed. No source-of-truth ledger mutation was performed.

Generated smoke artifacts under `outputs\tmp_paper20_baseline_capture` and `outputs\tmp_paper20_replay_smoke` are not commit candidates.

## Known Limitations

- `PASS_WITH_METADATA_DIFF` still appears because metadata such as generation timestamps and paths differ.
- `items_count=0` reflects the controlled smoke input conditions and does not prove trading correctness.
- Market data freshness remains limited by the current database state.
- `strategy_source`, `universe_source`, and `market_data_source` are policy-preserved semantic inputs, but no richer source fingerprints are implemented here.
- `universe_hash`, `market_data_asof`, `indicator_snapshot_hash`, `state_snapshot_hash`, and stable `plan_item_id` remain deferred.

## PAPER20-8 Recommendation

Recommended next step:

PAPER20-8 Replay Smoke Runbook Closeout

Scope:

- Record the resolved config_hash false warning behavior.
- Define how operators should interpret `PASS_WITH_METADATA_DIFF`.
- Keep controlled smoke artifacts out of git.
- Defer richer semantic fingerprints and stable row identity to later MFUs.

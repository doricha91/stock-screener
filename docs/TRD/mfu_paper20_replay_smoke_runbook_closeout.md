# PAPER20 Replay Smoke Runbook Closeout

## Purpose

PAPER20 closes out the Replay Wrapper Operational Smoke / Runbook work. The goal was to verify the PAPER19 replay wrapper under controlled, operation-like conditions and give operators a concrete runbook for interpreting replay diff results.

This closeout is documentation-only. No Python code was changed in this MFU. No replay smoke or Daily Plan generation was executed in this MFU.

## PAPER20 Scope

PAPER20 was scoped to controlled replay smoke readiness and interpretation, not strategy validation or actual execution.

In scope:

- Baseline sidecar inventory and eligibility checks.
- Controlled baseline capture path design.
- Dev-only capture CLI for explicit output-dir capture.
- Controlled baseline capture and replay wrapper smoke.
- Replay result interpretation runbook.
- config_hash false WARNING analysis and normalization follow-up.

Out of scope:

- Historical actual-operation verification.
- Trading correctness validation.
- Notion API/write/export/sync.
- Actual export.
- Source-of-truth ledger commit/append.
- Generated artifact commit.

## Completed Work

Completed chain:

```text
baseline inventory
-> baseline sidecar blocker confirmed
-> controlled output-dir blocker confirmed
-> dev-only capture CLI implemented
-> controlled baseline capture executed
-> replay wrapper smoke executed
-> config_hash false WARNING analyzed
-> producer_source rename / hash normalization hardened
-> controlled smoke re-executed
-> PASS_WITH_METADATA_DIFF confirmed
-> runbook aligned
```

## Controlled Smoke Timeline

PAPER20-1 documented that no eligible historical `paper_daily_plan.v1` baseline sidecar existed for the target account/date.

PAPER20-2 rechecked the blocker and did not run replay smoke because the eligible baseline sidecar was still absent.

PAPER20-3 identified that the official Daily Plan CLI did not expose a controlled `--output-dir`, so controlled baseline capture could not safely proceed without official artifact overwrite risk.

PAPER20-4 added a dev-only capture CLI under `scripts/dev/` with required `--output-dir`.

PAPER20-5 used the dev-only capture CLI to create a controlled baseline for `paper_sandbox / 2026-05-26`, then ran the replay wrapper. The result was `WARNING` due to `config_hash` diff only.

PAPER20-6 analyzed the warning and classified it as high-confidence false warning: normalized config differed only by producer provenance `source`.

PAPER20-7 renamed new artifact provenance to `producer_source`, excluded both `source` and `producer_source` from `paper_config_hash.v1`, and re-ran controlled smoke. The final result was `PASS_WITH_METADATA_DIFF`.

## Dev-only Capture CLI

The dev-only capture CLI added in PAPER20-4 is:

```cmd
python scripts\dev\capture_daily_plan_baseline.py --account-id paper_sandbox --date 2026-05-26 --output-dir outputs\tmp_paper20_baseline_capture --json
```

Properties:

- `--output-dir` is required.
- Default `run_mode` is `baseline_capture`.
- `official_run=false`.
- It writes only under the explicit output directory.
- It is not the official operating CLI.
- Generated artifacts are not commit candidates.

## Replay Smoke Result

PAPER20-7 final controlled replay smoke result:

```text
overall_status = PASS_WITH_METADATA_DIFF
diff_categories = METADATA_DIFF
config_hash diff = none
cause_candidates = []
write_executed=false
actual_executed=false
notion_api_called=false
notion_sync_executed=false
notion_write_export_sync_executed=false
commit_append_executed=false
```

Diff reports from the final recheck:

```text
outputs\tmp_paper20_replay_smoke\runs\20260604_115029\paper_daily_plan_diff_20260526.json
outputs\tmp_paper20_replay_smoke\runs\20260604_115029\paper_daily_plan_diff_20260526.md
```

These are generated smoke artifacts and must not be staged or committed.

## config_hash False Warning Resolution

PAPER20-6 found:

```text
Daily Plan field diffs = none
normalized config diff = source only
source = producer/provenance metadata
```

PAPER20-7 resolved this by:

- Emitting `producer_source` in new config snapshots.
- Treating legacy `source` as backward-compatible provenance metadata.
- Excluding both `source` and `producer_source` from `paper_config_hash.v1`.
- Keeping `strategy_source`, `universe_source`, and `market_data_source` hash-significant because they may be semantic inputs.

## PASS_WITH_METADATA_DIFF Interpretation

`PASS_WITH_METADATA_DIFF` means the Daily Plan comparison core fields match, but metadata-like fields still differ.

Typical metadata differences:

- `generated_at`
- run id
- output path
- report path
- producer/provenance metadata

For PAPER20-7, config_hash false warning was resolved and `cause_candidates` was empty.

This status is acceptable as a read-only replay smoke success signal. It does not approve actual/export/sync/commit/append.

## Runbook Status

`docs\operations\paper_replay_diff_runbook.md` was checked and minimally updated.

It now covers:

- `PASS` interpretation.
- `PASS_WITH_METADATA_DIFF` interpretation.
- `WARNING` interpretation.
- `config_hash WARNING` triage.
- `FAIL` interpretation.
- generated artifact non-commit policy.
- Notion/API/write/export/sync prohibition.
- PASS does not mean actual/export/sync approval.
- `source` / `producer_source` as provenance metadata.
- `strategy_source` / `universe_source` / `market_data_source` as hash-significant semantic candidates.

## Safety Verification

PAPER20 safety policy remains:

```text
No Notion API/write/export/sync.
No actual export.
No Manual Execution commit.
No Manual Review append.
No source-of-truth ledger commit/append.
No outputs/paper ledger mutation.
Generated smoke artifacts are not committed.
```

The generated smoke directories remain non-stage targets:

```text
outputs/tmp_paper20_baseline_capture/*
outputs/tmp_paper20_replay_smoke/*
```

## Generated Artifact Policy

Generated baseline capture and replay smoke artifacts may exist locally after PAPER20 smoke work. They are operational evidence only and are not source artifacts.

Do not stage:

- `outputs/tmp*`
- `outputs/tmp_paper20_baseline_capture/*`
- `outputs/tmp_paper20_replay_smoke/*`
- `outputs/paper_accounts/*` generated smoke outputs

Closeout commits should include documentation only.

## Known Limitations

- The final smoke had `items_count=0`, so action-row reproducibility coverage is limited.
- The `2026-05-26` controlled plan used `data_date=2026-05-20`; it is not trading correctness validation.
- This is not historical actual-operation verification.
- `universe_hash` is not implemented.
- `market_data_asof` is not implemented.
- `indicator_snapshot_hash` is not implemented.
- `state_snapshot_hash` is not implemented.
- Stable `plan_item_id` is not implemented.
- Official `scripts/run_paper_daily_plan.py --output-dir` support remains a future decision.

## Closeout Decision

PAPER20 is closeout-ready.

Reason:

```text
The controlled replay smoke chain is operationally exercised, the config_hash false warning was analyzed and fixed, the final replay result is PASS_WITH_METADATA_DIFF, and the runbook now explains how operators should interpret PASS/WARNING/FAIL outcomes without treating replay success as actual/export/sync approval.
```

## Next MFU Recommendation

Recommended next MFU:

PAPER21 Stable Plan Row Identity / Non-empty Replay Smoke Expansion

Goals:

- Introduce or design stable `plan_item_id` / row identity for Daily Plan items.
- Exercise replay smoke with a non-empty item set when safe data conditions are available.
- Keep replay checks read-only and separate from actual/export/sync approval.

Alternative follow-ups:

- Universe / market / indicator / state fingerprint expansion.
- Official controlled `--output-dir` support for `scripts/run_paper_daily_plan.py`.
- Schema/view drift check.

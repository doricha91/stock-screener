# PAPER20-6 Replay Smoke config_hash WARNING Analysis

## 1. Purpose

This document analyzes the `config_hash` WARNING from the PAPER20-5 controlled replay smoke.

Core question:

```text
Was the config_hash difference a meaningful config difference, or a false warning caused by controlled output-dir, generation time, path, or run metadata?
```

This analysis does not change code, config hash policy, replay wrapper behavior, Daily Plan generation, Notion sync, or any source-of-truth ledger.

## 2. PAPER20-5 Warning Recap

PAPER20-5 completed the controlled smoke chain:

```text
controlled baseline capture: success
replay wrapper smoke: success
overall_status: WARNING
diff_categories: CONFIG_OR_UNIVERSE_DIFF
Daily Plan action diff: 0
Daily Plan quantity diff: 0
Daily Plan price diff: 0
Daily Plan warning diff: 0
cause candidate: config_hash changed
```

The smoke was not historical actual-operation verification. It used current code, current database, and current configuration.

## 3. Artifact Availability

PAPER20-5 artifacts were available.

Baseline artifacts:

```text
outputs\tmp_paper20_baseline_capture\daily_action_plan_20260526.json
outputs\tmp_paper20_baseline_capture\config_snapshots\paper_config_snapshot_20260526.json
```

Regenerated replay artifacts:

```text
outputs\tmp_paper20_replay_smoke\runs\20260604_065248\regenerated_daily_action_plan_20260526.json
outputs\tmp_paper20_replay_smoke\runs\20260604_065248\regenerated_paper_config_snapshot_20260526.json
outputs\tmp_paper20_replay_smoke\runs\20260604_065248\paper_daily_plan_diff_20260526.json
outputs\tmp_paper20_replay_smoke\runs\20260604_065248\paper_daily_plan_diff_20260526.md
```

No generated artifact was staged or committed.

## 4. Baseline vs Regenerated Sidecar Summary

Baseline sidecar summary:

```text
schema_version: paper_daily_plan.v1
account_id: paper_sandbox
plan_date: 2026-05-26
run_mode: baseline_capture
official_run: false
items_count: 0
config_hash: sha256:c609650e17b43733337c5dc3711a7c1feac4bbd00ecb46e2a0664668f6ecaf00
config_hash_policy: paper_config_hash.v1
```

Regenerated sidecar summary:

```text
schema_version: paper_daily_plan.v1
account_id: paper_sandbox
plan_date: 2026-05-26
run_mode: replay
official_run: false
items_count: 0
config_hash: sha256:30428f4192bc453db56a3d786332b26637a1eaacdc82663bf1e51cf9973db6ff
config_hash_policy: paper_config_hash.v1
```

Sidecar-level interpretation:

```text
account/date/schema matched
items_count matched
official_run matched
run_mode differed as expected between capture and replay
config_hash differed
```

## 5. Config Snapshot Raw Comparison

Raw config snapshot comparison found two differing paths:

```text
generated_at
source
```

Raw difference interpretation:

```text
generated_at differs because baseline and replay were generated at different times.
source differs because the baseline config snapshot source was capture_daily_plan_baseline and the replay source was replay_daily_plan_diff.
```

No action, quantity, price, risk, sizing, strategy, max position, account, or universe semantic config difference was identified in this diagnostic summary.

## 6. Normalized Config Hash Comparison

The existing `paper_config_hash.v1` normalization excludes volatile/path-like fields such as:

```text
generated_at
created_at
updated_at
run_id
*_path
*_dir
*_directory
secret/token/env-like keys
```

After applying `normalize_paper_config_for_hash()`, the remaining normalized diff was:

```text
source:
  baseline: capture_daily_plan_baseline
  regenerated: replay_daily_plan_diff
```

Normalized hash result:

```text
baseline: sha256:c609650e17b43733337c5dc3711a7c1feac4bbd00ecb46e2a0664668f6ecaf00
regenerated: sha256:30428f4192bc453db56a3d786332b26637a1eaacdc82663bf1e51cf9973db6ff
equal: false
```

The hashes differ because `source` is currently included in the normalized hash input.

## 7. Diff Classification

Classification:

```text
config_hash WARNING classification: false warning
confidence: high
```

Reason:

```text
Daily Plan compared fields matched.
Normalized config differed only by source metadata.
source identifies the producer path, not a trading/risk/strategy parameter.
generated_at was already excluded and did not remain in normalized diff.
```

This does not prove the replay chain is perfect. It means this specific config_hash WARNING is not evidence of a meaningful config change.

## 8. False Warning Assessment

This warning is best treated as a false warning caused by metadata included in `paper_config_hash.v1`.

Recommended interpretation:

```text
The replay wrapper smoke chain worked.
The Daily Plan compared fields matched.
The WARNING was caused by source metadata differences between controlled baseline capture and replay wrapper generation.
The config_hash difference remains a cause candidate, not a confirmed root cause.
```

Potential follow-up:

```text
Consider excluding source from paper_config_hash.v1 normalization or explicitly classifying it as runtime/provenance metadata.
```

That follow-up should be implemented in a separate MFU with tests.

## 9. Operational Interpretation

For operators:

```text
WARNING does not automatically mean the plan is unsafe.
First check action/quantity/symbol differences.
If action/quantity/symbol differences are zero, inspect fingerprint diffs.
If config_hash differs, compare normalized config diff.
If normalized config diff is only generated_at/path/source/run metadata, treat as false-warning candidate.
If semantic config differs, escalate to a separate review.
```

PAPER20-5 result:

```text
operational smoke chain: usable
trading correctness: not validated
actual/export/sync approval: not granted
follow-up required: config_hash normalization policy review
```

## 10. Safety Verification

Safety verification:

```text
code changed: no
generated artifact staged: no
Notion API called: no
Notion write/export/sync executed: no
actual export executed: no
Manual Execution commit executed: no
Manual Review append executed: no
source-of-truth ledger commit/append executed: no
outputs/paper ledger changed by this task: no
```

Diagnostic commands only read existing PAPER20-5 artifacts and printed summaries to the console.

## 11. Known Limitations

Known limitations:

```text
The diagnostic did not perform a domain-specific semantic review of every config key.
The classification depends on the current artifact pair from PAPER20-5.
The baseline and replay plans both had items_count = 0.
The plan used data_date = 2026-05-20 for plan_date = 2026-05-26.
No code fix was made in this MFU.
```

## 12. PAPER20-7 Recommendation

Recommended PAPER20-7:

```text
PAPER20-7 config_hash normalization policy hardening
```

Scope candidate:

```text
1. Decide whether config snapshot source is runtime/provenance metadata.
2. If yes, exclude source from paper_config_hash.v1 normalization.
3. Add regression tests showing source-only changes do not alter config_hash.
4. Re-run controlled capture/replay smoke and confirm WARNING disappears or changes classification.
5. Keep generated artifacts uncommitted.
```

Non-goals:

```text
Notion API/write/export/sync
actual export
ledger commit/append
trading strategy changes
```

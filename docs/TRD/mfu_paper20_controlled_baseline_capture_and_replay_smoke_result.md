# PAPER20-5 Controlled Baseline Capture and Replay Wrapper Smoke Result

## 1. Purpose

This document records the PAPER20-5 controlled baseline capture and replay wrapper smoke for:

```text
account_id = paper_sandbox
plan_date = 2026-05-26
```

This is not historical actual-operation verification.
This is controlled operational smoke based on current code, current database, and current configuration.

Korean interpretation:

```text
이번 smoke는 과거 2026-05-26 당시 실제 운영 결과의 재현성 검증이 아니다.
현재 코드/현재 DB/현재 config 기준으로 baseline capture와 replay wrapper가 정상 연결되는지 확인하는 controlled smoke다.
```

## 2. Historical Verification Boundary

The generated baseline is not an official historical baseline from 2026-05-26.

It was created during PAPER20-5 using the current repository code, the current local database, and the current configuration. Therefore, it only validates that the controlled capture and replay wrapper chain can run safely and produce comparable artifacts.

The result must not be interpreted as approval for actual export, Notion sync, Manual Execution commit, Manual Review append, or any source-of-truth ledger mutation.

## 3. Controlled Baseline Capture Result

Command:

```cmd
python scripts\dev\capture_daily_plan_baseline.py --account-id paper_sandbox --date 2026-05-26 --output-dir outputs\tmp_paper20_baseline_capture --json
```

The first run used a 120-second command timeout and stopped during screening. It did not complete the capture.

The same controlled command was rerun with a longer timeout and completed successfully.

Result:

```text
exit_code: 0
account_id: paper_sandbox
plan_date: 2026-05-26
run_mode: baseline_capture
official_run: false
markdown_path: outputs\tmp_paper20_baseline_capture\daily_action_plan_20260526.md
sidecar_json_path: outputs\tmp_paper20_baseline_capture\daily_action_plan_20260526.json
config_snapshot_path: outputs\tmp_paper20_baseline_capture\config_snapshots\paper_config_snapshot_20260526.json
```

Daily Plan generation notes:

```text
market_state: BULL
data_date: 2026-05-20
screened tickers: 529
found candidates: 3
candidate after freshness guard / filters: no immediate action items
```

The generated baseline sidecar had `items_count = 0`. This is still eligible because `items` exists as a list and the smoke validates the capture/diff chain, not trading correctness.

## 4. Baseline Sidecar Eligibility

Baseline sidecar:

```text
outputs\tmp_paper20_baseline_capture\daily_action_plan_20260526.json
```

Eligibility result:

```text
eligible: true
schema_version: paper_daily_plan.v1
account_id: paper_sandbox
plan_date: 2026-05-26
items_count: 0
fingerprints_present: true
config_hash_present: true
config_hash_policy: paper_config_hash.v1
warnings: none
errors: none
```

The baseline sidecar was generated under the explicit controlled output directory only.

## 5. Replay Wrapper Smoke Result

Command:

```cmd
python scripts\dev\replay_daily_plan_diff.py --account-id paper_sandbox --date 2026-05-26 --baseline-plan outputs\tmp_paper20_baseline_capture\daily_action_plan_20260526.json --output-dir outputs\tmp_paper20_replay_smoke --json
```

Result:

```text
exit_code: 0
run_id: 20260604_065248
run_dir: outputs\tmp_paper20_replay_smoke\runs\20260604_065248
overall_status: WARNING
diff_categories: CONFIG_OR_UNIVERSE_DIFF
```

Generated replay artifacts:

```text
regenerated_markdown_path: outputs\tmp_paper20_replay_smoke\runs\20260604_065248\regenerated_daily_action_plan_20260526.md
regenerated_sidecar_path: outputs\tmp_paper20_replay_smoke\runs\20260604_065248\regenerated_daily_action_plan_20260526.json
regenerated_config_snapshot_path: outputs\tmp_paper20_replay_smoke\runs\20260604_065248\regenerated_paper_config_snapshot_20260526.json
diff_json_path: outputs\tmp_paper20_replay_smoke\runs\20260604_065248\paper_daily_plan_diff_20260526.json
diff_markdown_path: outputs\tmp_paper20_replay_smoke\runs\20260604_065248\paper_daily_plan_diff_20260526.md
```

Diff summary:

```text
added_symbols: 0
removed_symbols: 0
action_diff_count: 0
quantity_diff_count: 0
price_diff_count: 0
warning_diff_count: 0
duplicate_row_key_count: 0
```

Cause candidate:

```text
config_hash changed; this is a possible cause candidate.
```

The diff report explicitly states that the config hash difference is a cause candidate, not a confirmed root cause.

## 6. PASS / WARNING / FAIL Interpretation

Interpretation policy:

```text
PASS:
- compared Daily Plan fields match
- controlled replay smoke chain works
- not approval for actual/export/sync

PASS_WITH_METADATA_DIFF:
- generated_at, run_id, path, or other metadata-only differences
- usually not an operational stop condition

WARNING:
- price, warning, reason, note, fingerprint, or config_hash difference
- possible cause candidate exists, but the cause is not confirmed
- manual review is required before relying on the result operationally

FAIL:
- baseline missing or malformed
- account/date mismatch
- symbol/action/quantity difference
- replay wrapper execution failure
```

PAPER20-5 result:

```text
overall_status = WARNING
reason = config_hash differs between baseline capture and regenerated replay output
```

This does not block the controlled smoke chain itself, but it does require follow-up before treating same-date replay as fully stable.

## 7. Safety Marker Verification

Baseline capture summary:

```text
write_executed: false
actual_executed: false
notion_api_called: false
notion_sync_executed: false
notion_write_export_sync_executed: false
commit_append_executed: false
```

Replay wrapper summary:

```text
write_executed: false
actual_executed: false
notion_api_called: false
notion_sync_executed: false
notion_write_export_sync_executed: false
commit_append_executed: false
```

Diff report safety markers:

```text
write_executed: false
notion_api_called: false
notion_write_export_sync_executed: false
```

No Notion API, Notion write/export/sync, actual export, Manual Execution commit, Manual Review append, or source-of-truth ledger commit/append command was executed.

## 8. Operating Loop Readiness Checklist

Daily Plan:

```text
controlled Daily Plan generation: available
Markdown generation: confirmed
JSON sidecar generation: confirmed
config snapshot generation: confirmed
current_state reference: available through existing paper state provider
```

Replay:

```text
replay wrapper execution: confirmed
regenerated Markdown generation: confirmed
regenerated JSON sidecar generation: confirmed
regenerated config snapshot generation: confirmed
diff JSON report generation: confirmed
diff Markdown report generation: confirmed
safety markers: confirmed
```

Notion:

```text
Notion export/sync: not executed
Manual Execution/Review sync: not executed
```

Ledger:

```text
commit/append: not executed
account/position/current_state ledger mutation: not executed
```

Market Data:

```text
market data update after 2026-05-20: not performed in this task
2026-05-26 plan correctness: not validated as trading correctness
controlled operational smoke chain: validated
```

## 9. Market Data Limitation

The Daily Plan generation used `data_date = 2026-05-20` for a `plan_date = 2026-05-26`.

No market data update after 2026-05-20 was performed in this task. Therefore, the 2026-05-26 output must be treated as controlled operational smoke, not as a trading-correct Daily Plan for 2026-05-26.

## 10. Generated Artifact Policy

Generated artifacts exist under:

```text
outputs\tmp_paper20_baseline_capture\
outputs\tmp_paper20_replay_smoke\
```

These artifacts are smoke outputs and must not be staged or committed by default.

Only this TRD result document is intended to be committed.

## 11. Known Limitations

Known limitations:

```text
baseline sidecar items_count was 0
overall_status was WARNING due to config_hash diff
data_date was 2026-05-20 while plan_date was 2026-05-26
first capture attempt timed out at 120 seconds before successful rerun
generated artifacts are temporary smoke artifacts
stable plan_item_id remains unimplemented
universe_hash remains unimplemented
market_data_asof remains unimplemented
indicator_snapshot_hash remains unimplemented
state_snapshot_hash remains unimplemented
```

The config hash difference is a signal to inspect the baseline capture and replay config snapshot generation path. It is not proof that config change caused a plan difference.

## 12. PAPER20-6 Recommendation

Recommended PAPER20-6:

```text
PAPER20-6 Replay Smoke Config Hash Difference Review / Runbook
```

Recommended goals:

```text
1. Compare baseline and regenerated config snapshots at a summary level.
2. Identify whether config_hash changed due to volatile fields not excluded by paper_config_hash.v1.
3. Decide whether the config hash policy needs a small normalization adjustment.
4. Preserve the rule that config_hash differences are cause candidates, not confirmed root causes.
5. Write an operator runbook for interpreting PASS / WARNING / FAIL replay smoke results.
```

Non-goals for PAPER20-6:

```text
Notion API/write/export/sync
actual export
ledger commit/append
generated smoke artifact commit
trading strategy change
```

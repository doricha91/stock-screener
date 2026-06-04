# Paper Replay Diff Runbook

## 1. Purpose

This runbook explains how to interpret Daily Plan replay/same-date diff results.

Replay diff is a read-only operational validation tool. It compares a baseline Daily Plan JSON sidecar with a regenerated Daily Plan JSON sidecar and reports differences.

It is not actual export approval.

## 2. When to Run Replay Diff

Run replay diff when an operator needs to check whether a same-date Daily Plan generation path is stable enough for review.

Typical cases:

```text
before relying on a regenerated Daily Plan
after controlled baseline capture
after changing replay wrapper plumbing
after config fingerprint policy changes
when investigating PAPER20/PAPER19 replay warnings
```

Use explicit output directories for smoke runs:

```text
outputs\tmp_paper20_baseline_capture\
outputs\tmp_paper20_replay_smoke\
```

Do not commit generated smoke artifacts by default.

## 3. Required Safety Rules

Replay diff safety rules:

```text
Do not call Notion API.
Do not run Notion write/export/sync.
Do not run actual export.
Do not run Manual Execution commit.
Do not run Manual Review append.
Do not mutate account/position/current_state ledgers.
Do not stage generated outputs/tmp* artifacts.
Do not treat PASS/WARNING as explicit approval for actual/export/sync.
```

Expected safety markers:

```text
write_executed=false
actual_executed=false
notion_api_called=false
notion_sync_executed=false
notion_write_export_sync_executed=false
commit_append_executed=false
```

## 4. PASS Interpretation

`PASS` means:

```text
compared Daily Plan fields match
no blocking diff category was found
read-only replay smoke is usable as a validation signal
```

`PASS` does not mean:

```text
actual/export/sync is approved
the plan is historically verified
trading correctness is guaranteed
market data freshness is guaranteed
```

## 5. PASS_WITH_METADATA_DIFF Interpretation

`PASS_WITH_METADATA_DIFF` means differences are limited to metadata-like fields.

Examples:

```text
generated_at
run_id
output path
report path
producer_source / provenance-only naming
other non-semantic artifact metadata
```

This is usually not an operational stop condition, but operators should confirm no action, symbol, quantity, price, warning, reason, or note difference exists.

PAPER20-7 example:

```text
overall_status: PASS_WITH_METADATA_DIFF
diff_categories: METADATA_DIFF
cause_candidates: []
config_hash diff: none
classification: read-only replay smoke success with metadata-only differences
```

## 6. WARNING Interpretation

`WARNING` means a non-blocking difference was detected.

Common WARNING causes:

```text
price diff
warning/reason/note diff
fingerprint diff
config_hash diff
duplicate row key
```

WARNING is a cause-candidate signal. It is not a confirmed root cause.

Before relying on a WARNING result:

```text
1. Check whether action/symbol/quantity changed.
2. If not, inspect price/warning/reason/note diffs.
3. If only fingerprints changed, inspect the fingerprint source.
4. Record the finding as a follow-up if semantic meaning is unclear.
```

## 7. config_hash WARNING Triage

For `config_hash` WARNING:

```text
1. Check Daily Plan field diffs first.
2. If action/symbol/quantity changed, treat as a serious replay stability issue.
3. If action/symbol/quantity did not change, compare normalized config diff.
4. Check whether the diff is generated_at, output_dir, run_id, path, source, producer_source, or other provenance metadata.
5. If only volatile/provenance metadata differs, treat as a false-warning candidate.
6. If semantic config differs, split a follow-up MFU for config/replay review.
7. Do not claim the config difference caused the plan difference unless separately proven.
```

PAPER20-5 example:

```text
overall_status: WARNING
Daily Plan field diffs: none
normalized config diff: source only
classification: false warning
follow-up: consider excluding source from paper_config_hash.v1 normalization
```

PAPER20-7 resolution:

```text
source was clarified as producer/provenance metadata.
new config snapshots use producer_source.
source and producer_source are excluded from paper_config_hash.v1.
strategy_source, universe_source, and market_data_source remain semantic hash-significant candidates.
controlled replay smoke result became PASS_WITH_METADATA_DIFF with no config_hash cause candidate.
```

## 8. FAIL Interpretation

`FAIL` means the replay diff found a blocking issue or could not safely compare inputs.

Common FAIL causes:

```text
baseline missing
baseline malformed
regenerated sidecar missing
regenerated sidecar malformed
account/date mismatch
symbol set difference
action difference
quantity difference
replay wrapper failure
```

When FAIL occurs:

```text
Do not run actual/export/sync.
Do not patch generated artifacts manually.
Do not mutate ledgers to make the diff pass.
Document the blocker and split a follow-up MFU.
```

## 9. What Not To Do

Do not:

```text
interpret replay PASS as actual approval
interpret PASS_WITH_METADATA_DIFF as actual/export/sync approval
interpret config_hash WARNING as confirmed root cause
ignore action/quantity/symbol FAIL
modify generated smoke artifacts and rerun diff as if official
stage outputs/tmp* artifacts
stage generated replay smoke artifacts
run Notion write/export/sync from replay triage
run Manual Execution/Review commit or append from replay triage
change strategy logic during replay triage
```

## 10. Follow-up Decision Rules

Use these decision rules:

```text
PASS:
  record result and continue only if other preflight checks also pass

PASS_WITH_METADATA_DIFF:
  record metadata-only nature and continue only if operator accepts it

WARNING with no action/symbol/quantity diff:
  inspect warning category and decide whether a follow-up MFU is needed

config_hash WARNING from provenance metadata:
  classify as false-warning candidate and consider hash policy hardening

config_hash WARNING from source/producer_source only:
  should not occur after PAPER20-7; verify artifact version and hash normalization

config_hash WARNING from semantic config:
  split config/replay review before operational use

FAIL:
  stop; document blocker; do not run actual/export/sync
```

Replay diff is one read-only validation signal. It does not replace Command Gate, duplicate audit, Notion schema validation, or explicit operator approval.

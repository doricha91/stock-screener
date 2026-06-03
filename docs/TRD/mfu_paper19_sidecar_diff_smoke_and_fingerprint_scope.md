# PAPER19-6 Daily Plan Sidecar Diff Smoke and Fingerprint Scope

## 1. Purpose

PAPER19-6 verifies that the `paper_daily_plan.v1` JSON sidecar produced by PAPER19-5 is compatible with the PAPER19-2 replay diff core and CLI.

It also defines the scope for future Daily Plan fingerprint population. This MFU does not populate fingerprints, regenerate Daily Plans, call Notion, or mutate outputs/paper ledgers.

## 2. Sidecar -> Diff Compatibility

The PAPER19-5 sidecar is compatible with the current replay diff input contract because it provides:

- `account_id`
- `plan_date`
- `items[]`
- normalized item fields: `symbol`, `action`, `quantity`, `price`, `warning`, `reason`, `note`
- `fingerprints`

The diff core already accepts `items[]` and compares:

- row identity by `symbol + action`
- `quantity` as FAIL-level diff
- `price` as WARNING-level diff
- `warning`, `reason`, and `note` as WARNING-level diff
- `fingerprints.config_hash` and `fingerprints.universe_hash` as config/universe cause-candidate diffs
- state/market/code/generator fingerprint fields as state/market fingerprint cause-candidate diffs

The sidecar is therefore a formal candidate input for `scripts/dev/diff_daily_plan.py`.

## 3. Smoke Test Coverage

Added sidecar-shaped smoke tests:

| Case | Expected Result |
| --- | --- |
| same sidecar plan | `PASS` / `NO_DIFF` |
| quantity changed | `FAIL` / `QUANTITY_DIFF` |
| warning changed | `WARNING` / `WARNING_DIFF` |
| fingerprint changed | `WARNING` plus cause candidates |
| optional fields missing | `PASS` when compared fields still match |
| CLI smoke | JSON and Markdown diff report written under `tmp_path` output dir |

The smoke uses fixture JSON files only. It does not run the real Daily Plan generator and does not write to real `outputs/paper_accounts`.

## 4. Fingerprint Scope

Candidate sidecar fingerprint fields:

| Field | Purpose |
| --- | --- |
| `config_hash` | Detect config changes that may correlate with plan changes. |
| `universe_hash` | Detect universe snapshot changes. |
| `state_snapshot_hash` | Detect account/position state snapshot changes. |
| `state_snapshot_path` | Point to the state snapshot used for generation. |
| `market_data_asof` | Record market data as-of date. |
| `indicator_snapshot_hash` | Detect indicator data snapshot changes if such artifact exists. |
| `code_commit_sha` | Record code version used for generation. |
| `generator_version` | Record generator/schema version. |

Policy:

- Fingerprints are cause candidates only.
- A fingerprint diff must not be described as the confirmed root cause of a plan diff.
- Full snapshots must not be embedded in the sidecar.
- Use hash/path/as-of/version identifiers instead.

## 5. Immediate Candidates

Candidates for PAPER19-7 or near-term implementation:

1. `config_hash` or `config_snapshot_path`
   - The Daily Plan flow already writes `paper_config_snapshot_YYYYMMDD.json`.
   - The fastest safe option is to include a config snapshot path first, then add a deterministic hash if needed.
2. `state_snapshot_path`
   - Paper account paths already expose current state snapshot path candidates.
   - Use path reference only; do not inline account state.
3. `generator_version`
   - Can start as `paper_daily_plan.v1` or a generator constant.
4. `code_commit_sha`
   - Useful if a safe local git SHA read helper exists.
   - Should remain optional if git metadata is unavailable.

## 6. Deferred Candidates

Deferred until producer contracts are clearer:

- `universe_hash`
  - Universe metadata is loaded in the generator, but stable hash/source id contract should be defined before committing it.
- `market_data_asof`
  - `data_date` is available from market state, but the exact field semantics should be aligned with freshness/market data policy.
- `indicator_snapshot_hash`
  - No stable indicator snapshot artifact contract was confirmed in PAPER19-6.
- `state_snapshot_hash`
  - Hashing full account state should be designed carefully to avoid exposing or over-coupling to state serialization details.

## 7. Non-scope

PAPER19-6 does not include:

- fingerprint population implementation
- `plan_item_id` implementation
- Daily Plan regeneration wrapper
- real Daily Plan generation execution
- Notion API calls
- Notion write/export/sync
- actual export
- outputs/paper ledger mutation
- schema/view drift
- Telegram/Slack/Email delivery

## 8. PAPER19-7 Recommendation

Recommended PAPER19-7:

```text
Daily Plan Sidecar Fingerprint Minimal Population
```

Suggested scope:

- populate `generator_version`
- include `config_snapshot_path` and/or `config_hash`
- include `state_snapshot_path` when available from account-aware paths
- optionally include `code_commit_sha` if safe and deterministic
- keep `universe_hash`, `market_data_asof`, and `indicator_snapshot_hash` deferred unless their producer contracts are clear
- add tests that prove fingerprint fields appear in the sidecar and are consumed by replay diff as cause candidates

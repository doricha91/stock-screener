# PAPER19-8 Config Hash Policy and Replay Diff Decision

## 1. Purpose

PAPER19-8 defines the first policy for `config_hash` in Daily Plan replay/same-date diff and decides how to interpret the existing `config_snapshot_path` fingerprint.

This is documentation only. It does not implement hashing, change the sidecar schema, run Daily Plan generation, run replay diff, call Notion, or mutate outputs/paper ledgers.

## 2. Current State

PAPER19-7 currently populates Daily Plan sidecar fingerprints with:

```json
{
  "generator_version": "paper_daily_plan.v1",
  "config_snapshot_path": ".../paper_config_snapshot_YYYYMMDD.json",
  "state_snapshot_path": ".../paper_current_state_YYYYMMDD.json"
}
```

Current replay diff behavior:

- compares known fingerprint fields listed in `core.paper_replay_diff.FINGERPRINT_FIELDS`
- currently includes `config_hash`, `universe_hash`, `state_snapshot_hash`, `state_snapshot_path`, `market_data_asof`, `indicator_snapshot_hash`, `code_commit_sha`, and `generator_version`
- does not currently compare `config_snapshot_path`
- emits WARNING-level cause candidates for fingerprint differences
- explicitly treats cause candidates as not confirmed root causes

Current config snapshot behavior:

- `core.paper_config_snapshot.build_paper_config_snapshot_payload()` writes `paper_config_snapshot_YYYYMMDD.json`
- the payload includes runtime fields such as `generated_at`, `source`, and `market_state_write_log`
- the payload includes semantic fields such as `market_status_summary`, `final_config`, and `universe`

## 3. config_snapshot_path Role

`config_snapshot_path` is trace metadata.

It identifies where the config snapshot artifact was expected or written. It is not a stable content fingerprint.

Rules:

- Same path does not guarantee same config content.
- Different path does not guarantee different config content.
- Path differences may reflect account root, replay run directory, archive behavior, or local environment.
- A path-only difference must not be treated as a FAIL.

Recommended replay diff interpretation:

```text
config_snapshot_path differs
-> weak WARNING or INFO-like cause candidate
-> never FAIL by itself
-> do not claim config caused a plan change
```

Allowed wording:

```text
config_snapshot_path differs. Config source may differ. This is a cause candidate, not a confirmed cause.
```

Forbidden wording:

```text
Plan changed because config_snapshot_path changed.
```

## 4. config_hash Purpose

`config_hash` is the stable fingerprint of meaningful Daily Plan configuration content.

Purpose:

- detect meaningful setting changes that may correlate with Daily Plan differences
- stay stable across runtime-only metadata changes
- support replay diff cause-candidate reporting without copying full config snapshots into the sidecar

Policy:

- Meaningful Daily Plan setting changes should change `config_hash`.
- Volatile metadata such as `generated_at`, run id, and local paths should not change `config_hash`.
- `config_hash` is still a cause candidate, not proof of root cause.

## 5. Stable Hashing Policy v1

Policy name:

```text
paper_config_hash.v1
```

Hash algorithm:

```text
sha256
```

Recommended sidecar shape:

```json
{
  "fingerprints": {
    "config_snapshot_path": "...",
    "config_hash": "sha256:...",
    "config_hash_policy": "paper_config_hash.v1"
  }
}
```

Implementation should be deterministic:

- build a semantic config projection
- canonicalize it
- hash the canonical bytes with SHA-256
- prefix with `sha256:`

## 6. Include / Exclude Field Policy

Include candidates:

| Field / Area | Status | Notes |
| --- | --- | --- |
| `account_id` | Candidate | Include only if account-specific policy affects plan generation. |
| `currency` | Candidate | Include when account currency affects sizing/cash calculations. |
| `benchmark_id` | Candidate | Include once benchmark id is official in account/profile config. |
| `universe_id` | Candidate | Include once universe id is official in the Daily Plan config boundary. |
| `strategy_profile_id` | Candidate | Include once strategy profile is official. |
| `risk_profile_id` | Candidate | Include once risk profile is official. |
| `max_positions` | Include candidate | Present in current `final_config` summary and plan-impacting. |
| `score_threshold` | Include candidate | Present in current config and plan-impacting. |
| `entry_period` / `exit_period` | Include candidate | Plan-impacting signal/exit configuration. |
| `rs_lookback` | Include candidate | Plan-impacting relative strength lookback. |
| `target_cash_ratio` | Include candidate | Cash allocation/sizing policy. |
| `risk_per_trade` | Include candidate | Sizing/risk policy when used. |
| `trailing_stop_multiplier` | Include candidate | Exit/risk policy. |
| `SWITCHING_PREMIUM` | Include candidate | Switching policy. |
| `ALLOW_PROFIT_SWITCH` | Include candidate | Switching policy. |
| `SWITCHING_MAX_COUNT` | Include candidate | Switching policy. |
| `strategy_weights` | Include candidate | Plan-impacting scoring weights. |
| `hedge_enabled` | Candidate | Include if present and plan-impacting. |
| `official_run` | Candidate | Include only if it changes generation behavior, not merely metadata. |

Exclude candidates:

| Field / Area | Reason |
| --- | --- |
| `generated_at` | Volatile timestamp. |
| `created_at` / `updated_at` | Volatile timestamp. |
| `run_id` | Runtime identifier. |
| `absolute_path` | Local machine dependent. |
| `local_path` | Local machine dependent. |
| `report_path` | Artifact location, not semantic config. |
| `log_path` | Artifact/log location. |
| `config_snapshot_path` | Trace metadata; do not include in `config_hash`. |
| archive paths | Runtime artifact management. |
| machine/user-specific path | Non-portable local environment. |

Fields not confirmed in the current config snapshot should remain candidates, not assumed implemented fields.

## 7. Canonicalization Policy

Canonicalization for `paper_config_hash.v1` should use:

- JSON object with sorted keys
- compact JSON separators
- UTF-8 bytes
- stable representation for booleans, strings, integers, floats, lists, and nulls
- repo-relative path normalization only if a path must be included
- no absolute local paths
- no volatile timestamps
- no generated archive filenames
- no field order dependence

Recommended implementation shape:

```text
projection = select_semantic_config_fields(config_snapshot)
canonical_json = json.dumps(projection, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
config_hash = "sha256:" + sha256(canonical_json.encode("utf-8")).hexdigest()
```

Numeric policy:

- preserve existing numeric values without stringifying where possible
- avoid locale-dependent formatting
- avoid rounding unless the producer contract explicitly requires it

## 8. Replay Diff Interpretation

Replay diff should interpret config-related fingerprints as follows:

| Condition | Interpretation | Severity |
| --- | --- | --- |
| `config_snapshot_path` differs only | Config source path may differ; weak cause candidate only. | WARNING or INFO-like candidate, never FAIL |
| `config_hash` differs | Config content fingerprint differs; stronger cause candidate. | WARNING |
| Path differs + hash same | Storage location likely changed while semantic config stayed stable. | INFO or suppressed note |
| Path same + hash differs | Same artifact path may have changed content. | WARNING |
| Path differs + hash differs | Config source and content both differ; config change possibility is higher. | WARNING |

Cause wording must remain non-causal:

```text
config_hash changed; this is a possible cause candidate.
```

Do not write:

```text
quantity changed because config_hash changed.
```

Decision:

- Do not treat `config_snapshot_path` as equivalent to `config_hash`.
- Do not make path-only differences FAIL.
- Add `config_hash` later using `paper_config_hash.v1` before relying on config content diff semantics.

## 9. Non-scope

PAPER19-8 does not include:

- Python code implementation
- config hash helper implementation
- sidecar schema modification
- Daily Plan generation execution
- replay diff execution
- Notion API calls
- Notion write/export/sync
- outputs/paper ledger mutation
- actual export
- `code_commit_sha` implementation

## 10. PAPER19-9 Recommendation

Recommended PAPER19-9:

```text
Config Hash Helper Minimal Implementation
```

Suggested scope:

- implement `paper_config_hash.v1` projection/canonicalization/hash helper
- add unit tests proving volatile fields do not change the hash
- add unit tests proving semantic config fields do change the hash
- populate `config_hash` and `config_hash_policy` in the Daily Plan sidecar
- keep `config_snapshot_path` as trace metadata
- update replay diff tests to confirm `config_hash` produces WARNING cause candidates

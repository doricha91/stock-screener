# PAPER19-9 Config Hash Helper and Daily Plan Sidecar Populate

## Purpose

PAPER19-9 implements the `paper_config_hash.v1` policy defined in PAPER19-8 and populates Daily Plan JSON sidecar fingerprints with `config_hash` and `config_hash_policy`.

This MFU strengthens replay/same-date diff cause-candidate tracking. It does not implement a replay wrapper, regenerate Daily Plans, call Notion, run export/sync, or mutate outputs/paper ledgers.

## Scope

Implemented scope:

- add a stable config hash helper
- normalize config snapshots before hashing
- exclude volatile/runtime/local/secret-like metadata from the hash input
- record `config_hash` and `config_hash_policy` in `paper_daily_plan.v1` sidecars when the config snapshot file is readable
- keep `config_snapshot_path` as trace metadata
- verify replay diff still treats `config_hash` changes as WARNING cause candidates

Out of scope:

- replay wrapper orchestration
- Daily Plan regeneration
- `plan_item_id`
- stable row id refactor
- `universe_hash`
- `market_data_asof`
- `indicator_snapshot_hash`
- `state_snapshot_hash`
- Notion write/export/sync

## Implemented Helper

New helper module:

```text
core/paper_config_hash.py
```

Implemented functions:

```text
normalize_paper_config_for_hash(config: dict) -> dict
compute_paper_config_hash(config: dict) -> str
compute_paper_config_hash_from_file(path: str | Path) -> str | None
```

Policy constant:

```text
PAPER_CONFIG_HASH_POLICY = paper_config_hash.v1
```

Hash output format:

```text
sha256:<hex>
```

## Normalization Policy

The helper uses a deterministic projection:

- recursively walks dict/list/set structures
- sorts JSON keys during hash serialization
- uses compact JSON separators
- encodes UTF-8
- converts `Path` and unknown scalar-like values to strings only after volatile key filtering
- removes volatile/runtime/local/secret-like keys before hashing

The implementation intentionally uses "full config minus documented volatile fields" rather than a narrow whitelist. This is safer for the current snapshot contract because new semantic fields added to the snapshot can affect the hash unless they are explicitly volatile.

## Excluded Volatile Fields

The hash input excludes exact volatile keys such as:

```text
generated_at
created_at
updated_at
run_id
report_id
archive_path
```

It also excludes local/runtime/secret-like key patterns:

```text
absolute_path
local_path
report_path
log_path
temporary_path
temp_path
machine
username
user_name
secret
token
password
api_key
env
```

Path-like keys ending with these suffixes are also excluded:

```text
_path
_dir
_directory
```

This means runtime metadata such as `config_snapshot_path`, `state_snapshot_path`, and local report paths remain trace metadata and do not directly affect `config_hash`.

## Sidecar Fingerprint Impact

Daily Plan sidecars now include the config hash when the config snapshot file exists and contains valid JSON:

```json
{
  "fingerprints": {
    "generator_version": "paper_daily_plan.v1",
    "config_snapshot_path": "...",
    "config_hash": "sha256:...",
    "config_hash_policy": "paper_config_hash.v1",
    "state_snapshot_path": "..."
  }
}
```

If the config snapshot file is missing or malformed:

- sidecar generation does not fail
- `config_snapshot_path` remains present as trace metadata
- `config_hash` is omitted
- `config_hash_policy` is omitted

This preserves Daily Plan generation safety while making missing/malformed snapshot hash data visible by absence.

## Replay Diff Cause Candidate Impact

PAPER19 replay diff already compares `fingerprints.config_hash`.

When baseline and regenerated sidecars have different `config_hash` values:

- overall status becomes `WARNING` unless a stronger plan diff exists
- `CONFIG_OR_UNIVERSE_DIFF` is included
- `cause_candidates` records that `config_hash` changed
- the report wording remains "possible cause candidate"

The report must not claim that the plan changed because config changed. The hash is evidence for investigation, not root-cause proof.

## Test Coverage

Added and updated tests cover:

- `sha256:<hex>` output format
- policy name `paper_config_hash.v1`
- different JSON key order produces the same hash
- `generated_at` changes do not change the hash
- `run_id` changes do not change the hash
- path-only changes do not change the hash
- secret/token/env-like fields are excluded
- semantic config field changes do change the hash
- Daily Plan sidecar records `config_hash`
- Daily Plan sidecar records `config_hash_policy`
- missing config snapshot does not break sidecar payload generation
- malformed config snapshot does not break sidecar payload generation
- replay diff records config hash differences as cause candidates without root-cause wording

## Limitations

- The helper does not compute `universe_hash`.
- The helper does not compute `state_snapshot_hash`.
- The helper does not compute `market_data_asof`.
- The helper does not compute `indicator_snapshot_hash`.
- The helper does not provide a schema-specific whitelist yet.
- If a future snapshot adds volatile fields with unknown names, those keys may need to be added to the exclusion policy.
- If a future snapshot adds path-like semantic values, the current broad path exclusion may need refinement.

## PAPER19-10 Recommendation

Recommended next MFU:

```text
PAPER19-10 Daily Plan Replay Wrapper Minimal Dry-run
```

Candidate scope:

- keep `diff_daily_plan.py` as pure comparison
- create a dry-run wrapper that accepts account/date and a baseline sidecar
- generate or receive a regenerated sidecar in a replay-only output directory
- invoke the existing replay diff core
- preserve `write_executed=false`
- avoid Notion, export/sync, actual execution, and outputs/paper ledger mutation

# PAPER19-7 Daily Plan Sidecar Minimal Fingerprints

## 1. Purpose

PAPER19-7 populates the minimal `fingerprints` object in the `paper_daily_plan.v1` JSON sidecar.

The goal is to give PAPER19 replay diff enough metadata to identify possible cause candidates without changing Daily Plan strategy logic, Markdown output, Notion flow, or paper ledger behavior.

## 2. Scope

Implemented scope:

- populate `generator_version`
- populate `config_snapshot_path` when a config snapshot output path is passed to `generate_daily_plan`
- populate `state_snapshot_path` when a state snapshot path is passed to `generate_daily_plan`
- pass account-aware `state_snapshot_path` from `scripts/run_paper_daily_plan.py`
- keep `code_commit_sha` omitted because no existing project utility/convention was confirmed

Not implemented:

- `plan_item_id`
- `universe_hash`
- `market_data_asof`
- `indicator_snapshot_hash`
- `state_snapshot_hash`
- `code_commit_sha`

## 3. Implemented Fingerprints

Current sidecar fingerprint object:

```json
{
  "generator_version": "paper_daily_plan.v1",
  "config_snapshot_path": "outputs/paper_accounts/paper_sandbox/config_snapshots/paper_config_snapshot_20260520.json",
  "state_snapshot_path": "outputs/paper_accounts/paper_sandbox/paper_current_state_20260520.json"
}
```

Field policy:

| Field | Status | Source |
| --- | --- | --- |
| `generator_version` | Implemented | Fixed to `paper_daily_plan.v1`. |
| `config_snapshot_path` | Implemented when available | Existing config snapshot output path. |
| `state_snapshot_path` | Implemented when available | Account-aware current state snapshot path passed by the official wrapper. |
| `code_commit_sha` | Deferred | No existing safe project utility/convention was confirmed. |

The implementation does not fabricate hashes or infer missing values.

## 4. Deferred Fingerprints

Deferred fields:

- `universe_hash`
- `market_data_asof`
- `indicator_snapshot_hash`
- `state_snapshot_hash`
- `code_commit_sha`

Reasons:

- `universe_hash` needs a stable universe snapshot identity/hash contract.
- `market_data_asof` needs alignment with freshness/market-data policy.
- `indicator_snapshot_hash` needs a stable indicator snapshot artifact.
- `state_snapshot_hash` needs a careful state serialization/hash policy.
- `code_commit_sha` should use a shared project utility or documented convention rather than ad-hoc shelling out in the generator.

## 5. Sidecar Schema Impact

The sidecar remains `paper_daily_plan.v1`.

No required item fields changed. The only schema impact is that `fingerprints` is no longer an empty object when known path/version metadata is available.

Example:

```json
{
  "schema_version": "paper_daily_plan.v1",
  "account_id": "paper_sandbox",
  "plan_date": "2026-05-20",
  "run_mode": "official",
  "official_run": true,
  "items": [],
  "fingerprints": {
    "generator_version": "paper_daily_plan.v1",
    "config_snapshot_path": "...",
    "state_snapshot_path": "..."
  }
}
```

## 6. Replay Diff Cause Candidate Impact

PAPER19 replay diff already compares supported fingerprint fields such as:

- `state_snapshot_path`
- `code_commit_sha`
- `generator_version`
- `config_hash`
- `universe_hash`

When a supported fingerprint differs, replay diff emits a WARNING and records a cause candidate. This remains a possible cause candidate only.

Required wording:

```text
state_snapshot_path changed; this is a possible cause candidate.
```

Forbidden wording:

```text
quantity changed because state_snapshot_path changed.
```

`config_snapshot_path` is currently recorded in sidecars for traceability, but replay diff does not yet classify it as a `config_hash` replacement.

## 7. Markdown / Notion Safety

PAPER19-7 preserves:

- existing `daily_action_plan_YYYYMMDD.md` path and Markdown rendering flow
- existing `paper_config_snapshot_YYYYMMDD.json` meaning
- existing Notion mapping/export/sync behavior
- existing paper ledger behavior

No Notion API call, Notion write/export/sync, actual export, or external delivery is executed.

## 8. Test Coverage

Updated tests cover:

- `generator_version` is recorded in the sidecar
- `config_snapshot_path` is recorded when config snapshot output is passed
- `state_snapshot_path` is passed by the official wrapper
- `state_snapshot_path` is recorded in generated sidecar payload
- `code_commit_sha` is omitted rather than faked
- replay diff still detects supported fingerprint changes as WARNING/cause candidates
- existing quantity/warning sidecar smoke behavior remains intact

## 9. Limitations

- `config_snapshot_path` is trace metadata, not a hash.
- Replay diff does not currently treat `config_snapshot_path` as equivalent to `config_hash`.
- `code_commit_sha` is omitted until a shared safe version utility exists.
- `state_snapshot_path` may point to an expected path even if the snapshot is produced later in the operating loop.
- Full snapshots are not copied into the sidecar.

## 10. PAPER19-8 Recommendation

Recommended PAPER19-8:

```text
Daily Plan Sidecar Fingerprint Diff Expansion
```

Suggested scope:

- decide whether replay diff should compare `config_snapshot_path`
- add a safe project-level code version helper if `code_commit_sha` is required
- decide whether state snapshot existence should be validated by preflight rather than sidecar generation
- keep `universe_hash`, `market_data_asof`, and `indicator_snapshot_hash` deferred until producer contracts are stable

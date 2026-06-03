# PAPER19-5 Daily Plan JSON Sidecar Producer

## 1. Purpose

PAPER19-5 adds a minimal `paper_daily_plan.v1` JSON sidecar for Daily Plan generation while preserving the existing Markdown artifact.

The sidecar is generated from the same structured data used by `core.daily_plan_generator.generate_daily_plan()` before Markdown rendering. It does not parse Markdown back into JSON.

## 2. Scope

Implemented scope:

- keep `daily_action_plan_YYYYMMDD.md` output unchanged
- write `daily_action_plan_YYYYMMDD.json` beside the Markdown output
- normalize current `action_items` into JSON `items`
- include `account_id`, `plan_date`, `run_mode`, and `official_run`
- preserve existing `paper_config_snapshot_YYYYMMDD.json` behavior

Out of scope:

- strategy logic changes
- Markdown format changes
- Markdown parser implementation
- PAPER19 diff core changes
- replay wrapper implementation
- Notion API/write/export/sync
- outputs/paper ledger mutation

## 3. Implemented JSON Schema

Schema version:

```text
paper_daily_plan.v1
```

Current JSON envelope:

```json
{
  "schema_version": "paper_daily_plan.v1",
  "account_id": "paper_sandbox",
  "plan_date": "2026-05-20",
  "run_mode": "exploratory",
  "official_run": false,
  "generated_at": "2026-05-20T00:00:00Z",
  "items": [],
  "fingerprints": {}
}
```

`fingerprints` is currently present as an empty object unless a later MFU wires config/universe/state/market fingerprints into the normalized Daily Plan object.

## 4. Markdown Compatibility

The Markdown rendering path remains unchanged:

- `format_markdown_report(...)` still receives the existing structured inputs
- Markdown output path remains `daily_action_plan_YYYYMMDD.md`
- Markdown content is written before config snapshot handling as before
- JSON sidecar is additive and does not replace Markdown

Tests verify that adding the JSON sidecar does not change the injected Markdown rendering output.

## 5. Field Normalization

Current `action_items` use existing generator field names. The sidecar normalizes only the fields required by PAPER19 diff:

| Existing field | JSON field |
| --- | --- |
| `type` | `action` |
| `shares` | `quantity` |
| `price` | `price` |
| `symbol` | `symbol` |
| `warning` | `warning` |
| `reason` | `reason` |
| `note` | `note` |

Missing fields are represented as `null` in the current minimal schema.

## 6. Output Path Policy

Default JSON sidecar path:

```text
daily_action_plan_YYYYMMDD.json
```

The path is derived from the Markdown output path by replacing `.md` with `.json`.

Examples:

```text
outputs/paper_accounts/{account_id}/daily_action_plan_20260520.md
outputs/paper_accounts/{account_id}/daily_action_plan_20260520.json
```

The config snapshot path remains separate:

```text
outputs/paper_accounts/{account_id}/config_snapshots/paper_config_snapshot_20260520.json
```

The JSON sidecar must not be confused with `paper_config_snapshot_YYYYMMDD.json`.

## 7. run_mode / official_run Handling

`generate_daily_plan()` now accepts optional metadata:

```text
account_id
run_mode
official_run
json_sidecar_path
write_json_sidecar
```

Default values:

```text
account_id = paper_default
run_mode = exploratory
official_run = false
write_json_sidecar = true
```

`scripts/run_paper_daily_plan.py` passes:

```text
account_id = account_paths.account_id or paper_default
run_mode = official
official_run = true
```

This makes the official wrapper explicit without changing existing Markdown output naming.

## 8. Test Coverage

Added tests in `tests/test_daily_plan_json_sidecar.py`:

- Markdown output is still generated
- JSON sidecar is generated beside Markdown
- schema version is `paper_daily_plan.v1`
- `account_id`, `plan_date`, `run_mode`, and `official_run` are present
- `type/shares/price` normalize to `action/quantity/price`
- `warning/reason/note` are included when available
- config snapshot output remains separate
- official wrapper passes account/run metadata
- tests use `tmp_path` and monkeypatched dependencies

## 9. Notion / Export Safety

PAPER19-5 does not touch:

- Notion mapping
- Notion client
- Notion exporters
- Notion schema validation
- export/sync commands
- actual export approval flow

No Notion API call, write/export/sync, or external delivery is executed by this MFU.

## 10. Limitations

- `fingerprints` is present but not populated yet.
- `plan_item_id` is not implemented yet.
- Review-only and warning-only rows are not yet represented as separate normalized row types unless they are present in `action_items`.
- The sidecar currently normalizes actionable `action_items`; future MFUs may need a richer Daily Plan object that includes review/warning sections explicitly.
- `run_mode` values are string metadata and are not yet backed by a central enum.

## 11. PAPER19-6 Recommendation

Recommended PAPER19-6:

```text
Daily Plan JSON Sidecar Integration with PAPER19 Diff Smoke
```

Suggested scope:

- feed generated sidecar fixture into `scripts/dev/diff_daily_plan.py`
- add fingerprint population candidates from config snapshot/universe metadata
- decide whether `plan_item_id` should be generated in the producer
- keep replay wrapper out of scope until sidecar semantics are stable

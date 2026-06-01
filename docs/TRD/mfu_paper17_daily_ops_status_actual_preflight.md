# PAPER17-7 Daily Ops Status Actual Preflight

## 1. Purpose

PAPER17-7 formalizes a read-only preflight for Daily Ops Status actual export readiness.

The preflight summarizes settings/env readiness, schema validation, duplicate audit, External Key consistency, account scope, and Command Gate readiness in one PASS / WARNING / FAIL result.

This command does not execute actual export and does not replace explicit user approval.

## 2. Scope

In scope:

- `daily_ops_status` only.
- `paper_sandbox` only for actual readiness.
- Settings/env check for Notion token and Daily Ops Status data source.
- Read-only Daily Ops Status schema validation.
- Read-only duplicate audit by External Key.
- External Key / account_id / status_date consistency check.
- Command Gate summary.

Out of scope:

- Notion actual write/export/sync.
- `paper_default` actual export.
- multi-account bulk actual export.
- detail exporter actual.
- Manual Execution/Review status sync actual.
- duplicate cleanup.

## 3. CLI

Recommended command:

```cmd
python scripts\dev\preflight_daily_ops_status_actual.py --account-id paper_sandbox --date 2026-05-20 --json
```

Supported options:

```text
--account-id
--date
--external-key
--expected-page-id
--json
```

No `--confirm-actual` option is available.

## 4. Input Contract

- `account_id`: required. Only `paper_sandbox` can pass current actual readiness.
- `date`: required. Accepts `YYYY-MM-DD` or `YYYYMMDD`.
- `external_key`: optional. If provided, it must match `daily_ops_status:{account_id}:{status_date}`.
- `expected_page_id`: optional. If omitted, the preflight can still run but returns a Command Gate warning.

## 5. Preflight Checks

| Check | Purpose |
| --- | --- |
| `settings_env_check` | Confirms `NOTION_TOKEN` and Daily Ops Status data source configuration are available. |
| `schema_validation_check` | Runs read-only schema validation for `daily_ops_status`. |
| `duplicate_audit_check` | Runs read-only duplicate audit by External Key. |
| `external_key_check` | Confirms External Key matches account/date. |
| `account_scope_check` | Blocks accounts other than `paper_sandbox`. |
| `command_gate_check` | Confirms operator-level guard conditions and expected page context. |

## 6. Output Contract

Minimum JSON shape:

```json
{
  "target": "daily_ops_status",
  "account_id": "paper_sandbox",
  "status_date": "2026-05-20",
  "external_key": "daily_ops_status:paper_sandbox:2026-05-20",
  "overall_status": "WARNING",
  "checks": [],
  "duplicate_audit": {},
  "schema_validation_result": "PASS",
  "allowed_actual_command": "python scripts\\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --confirm-actual --json",
  "recommended_action": "review_warnings_before_explicit_user_approval",
  "write_executed": false
}
```

## 7. PASS / WARNING / FAIL Policy

Final status rules:

- Any `FAIL` check -> `overall_status=FAIL`.
- Warnings and no failures -> `overall_status=WARNING`.
- All required checks pass and only allowed skipped checks exist -> `overall_status=PASS`.

Required FAIL conditions:

- Missing `NOTION_TOKEN`.
- Missing `NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID` or equivalent data source setting.
- schema validation FAIL.
- duplicate audit `duplicate_blocker`.
- duplicate audit `settings_error`.
- duplicate audit `query_error`.
- account_id other than `paper_sandbox`.
- missing/invalid account_id.
- External Key mismatch.
- invalid date format.

WARNING conditions:

- `expected_page_id` is not provided.
- Operator confirmation is still required.
- A future schema or duplicate check returns a non-blocking warning.

## 8. Read-only Safety Policy

Allowed:

- environment/settings presence check.
- Notion schema read/validation.
- Notion query/read for duplicate audit.

Forbidden:

- `create_page`.
- `update_page`.
- `upsert_page_by_external_key`.
- actual export.
- status sync actual.
- outputs/paper ledger changes.

The preflight result always includes `write_executed=false`.

## 9. Example Outputs

WARNING example from PAPER17-7 smoke:

```json
{
  "overall_status": "WARNING",
  "schema_validation_result": "PASS",
  "duplicate_audit": {
    "classification": "update_candidate",
    "match_count": 1,
    "write_executed": false
  },
  "recommended_action": "review_warnings_before_explicit_user_approval",
  "write_executed": false
}
```

Interpretation: prerequisites are mostly satisfied, exactly one matching row exists, but `expected_page_id` was not provided and explicit user approval is still required before any actual export.

## 10. Test Coverage

Tests cover:

- missing settings/env -> FAIL.
- account other than `paper_sandbox` -> FAIL.
- External Key mismatch -> FAIL.
- duplicate `create_candidate` -> WARNING without expected page id.
- duplicate `update_candidate` -> WARNING without expected page id.
- duplicate `duplicate_blocker` -> FAIL.
- schema validation FAIL -> FAIL.
- `write_executed=false`.
- fake client write methods are not called.
- error messages do not expose data source IDs.

## 11. Limitations

- The real smoke covered only `daily_ops_status / paper_sandbox / 2026-05-20`.
- `overall_status=WARNING` is expected when `expected_page_id` is omitted.
- PASS or WARNING does not execute actual export.
- PASS or WARNING does not replace explicit user approval.
- paper_default actual remains forbidden.
- multi-account bulk actual remains forbidden.
- schema/view drift automation is not implemented.

## 12. PAPER17-8 Recommendation

PAPER17-8 should decide whether to add an operator-facing actual export checklist or wrapper that consumes this preflight output.

The next implementation should not run actual export automatically. It should require explicit user approval and should continue to block paper_default, multi-account bulk, duplicate blockers, and stale page_id cases.

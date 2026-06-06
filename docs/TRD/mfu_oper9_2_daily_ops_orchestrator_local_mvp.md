# MFU-OPER9-2 Daily Ops Orchestrator Local MVP

## 1. Summary

MFU-OPER9-2 adds a read-only local Daily Ops Orchestrator status MVP.

The MVP does not run daily operations. It inspects local artifacts, applies account/date guards, reports stage blockers and warnings, and recommends the next operator command as text only.

Implemented CLI:

```cmd
python scripts\paper_daily_ops.py status --account-id <ACCOUNT_ID> --data-date <DATA_DATE> --trade-date <TRADE_DATE> --json
```

## 2. Scope

Implemented:

- local-only stage status JSON
- required `account_id`, `data_date`, and `trade_date`
- `trade_date > data_date` guard
- account-aware root inspection
- `paper_test` fallback detection
- duplicate commit/append recommendation suppression
- preview-before-commit/append recommendation policy
- REVIEW_DONE terminal next-command suppression
- JSON safety markers:
  - `read_only=true`
  - `write_executed=false`
  - `notion_api_called=false`
  - `commit_append_executed=false`

Not implemented:

- Notion live read
- Notion actual write/export/sync execution
- Manual Execution commit execution
- Manual Review append execution
- broker/API integration
- ledger mutation
- Daily Ops Status actual export
- market calendar resolver

## 3. Files

Code:

- `core/paper_daily_ops_orchestrator.py`
- `scripts/paper_daily_ops.py`

Tests:

- `tests/test_paper_daily_ops_orchestrator.py`

Docs:

- `docs/TRD/mfu_oper9_2_daily_ops_orchestrator_local_mvp.md`
- `docs/operations/paper_daily_ops.md`

## 4. CLI Contract

Required:

```cmd
--account-id <ACCOUNT_ID>
--data-date <YYYYMMDD|YYYY-MM-DD>
--trade-date <YYYYMMDD|YYYY-MM-DD>
```

Optional:

```cmd
--json
--account-root <PATH>
--legacy-root <PATH>
--execution-preview-json <PATH>
--execution-commit-report <PATH>
--review-preview-json <PATH>
--review-commit-report <PATH>
```

The path override options are for tests and diagnostics. They do not enable writes.

## 5. JSON Contract

Top-level fields include:

```json
{
  "schema_version": "mfu_oper9_daily_ops_status.v1",
  "account_id": "paper_pilot_202606",
  "data_date": "2026-06-05",
  "trade_date": "2026-06-08",
  "overall_status": "WARNING",
  "read_only": true,
  "write_executed": false,
  "notion_api_called": false,
  "commit_append_executed": false,
  "legacy_default_used": false,
  "stages": []
}
```

Each stage includes:

```json
{
  "stage_name": "MANUAL_EXECUTION_PREVIEW",
  "status": "DONE",
  "blockers": [],
  "warnings": [],
  "required_artifacts": [],
  "existing_artifacts": [],
  "missing_artifacts": [],
  "next_command": null,
  "note": ""
}
```

## 6. Stage Coverage

Supported stages:

- DATA_FRESHNESS
- DAILY_PLAN
- DAILY_PLAN_NOTION_EXPORT
- MANUAL_EXECUTION_TEMPLATE
- MANUAL_EXECUTION_PREVIEW
- MANUAL_EXECUTION_COMMIT
- MANUAL_EXECUTION_STATUS_SYNC
- DAILY_REVIEW
- MANUAL_REVIEW_TEMPLATE
- MANUAL_REVIEW_PREVIEW
- MANUAL_REVIEW_APPEND
- MANUAL_REVIEW_STATUS_SYNC
- FINAL_STATUS

Local artifact proof policy:

- Daily Plan can be DONE from local md/json/config snapshot.
- Execution preview can be DONE from local preview JSON.
- Execution commit can be DONE from local commit report JSON.
- Daily Review can be DONE from local reports/template/validation PASS.
- Review preview can be DONE from local preview JSON.
- Review append can be DONE from local commit report JSON.
- Final status can be DONE when local `paper.py status` reports `REVIEW_DONE`.

Notion export/sync stages remain `UNKNOWN` when only local artifacts are available because the MVP does not perform Notion live reads and no local export/sync sidecar contract exists yet.

## 7. Guard and Safety Behavior

Account and date guards:

- empty `account_id` raises a CLI validation error or returns BLOCKED JSON in `--json` mode
- missing or invalid dates raise validation errors
- `trade_date <= data_date` produces top-level BLOCKED status

Fallback policy:

- non-default accounts use only account-root artifacts
- `outputs/paper_test` artifacts are never DONE evidence for non-default accounts
- legacy `paper_test` artifacts can produce warnings or blockers depending on whether the missing account-root stage would otherwise be inferred from them
- `paper_default` legacy fallback is exposed through `legacy_default_used=true`

Duplicate policy:

- if Manual Execution commit report exists, commit is DONE and no commit command is recommended
- if execution ledger/snapshot evidence exists without commit report, commit recommendation is suppressed with WARNING
- if Manual Review commit report exists, append is DONE and no append command is recommended
- if review log rows exist without review commit report, append recommendation is suppressed with WARNING

Preview policy:

- commit is never recommended without execution preview JSON
- append is never recommended without review preview JSON
- preview FAIL rows block commit/append recommendation
- `true_with_warnings` preview states are WARNING, not silent PASS

Terminal policy:

- when local workflow status is `REVIEW_DONE`, top-level `next_command` is null
- commit/append commands are suppressed from all stages in REVIEW_DONE

## 8. Verification

Required verification commands:

```cmd
python scripts\paper_daily_ops.py status --help
python scripts\paper_daily_ops.py status --account-id paper_pilot_202606 --data-date 2026-06-05 --trade-date 2026-06-08 --json
pytest tests/test_paper_daily_ops_orchestrator.py -q
git diff --check
git status --short
```

Additional recommended regression:

```cmd
pytest tests/test_paper_daily_ops_orchestrator.py tests/test_paper_daily_plan_generation.py -q
```

## 9. Known Limitations

- Notion live read is intentionally excluded.
- Notion export/sync stages cannot be proven DONE from local state alone.
- Market calendar handling only matches the existing basic date comparison guard; no automatic market calendar resolver is added.
- Evidence path options are minimal and should be hardened in a later MFU if operators need external proof injection.
- The MVP does not persist its own status report to disk.

## 10. Follow-Up

Recommended next MFU:

```text
MFU-OPER9-3 Daily Ops Orchestrator Evidence and Notion-Safe Verification
```

Candidate scope:

- local export/sync result sidecar contract
- optional Notion live read behind explicit opt-in
- richer stale-artifact checks using mtime and source sidecar metadata
- account-root migration policy for `paper_default`

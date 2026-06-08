# MFU-OPER9-11 Operational Path Consistency Audit After Env Alignment

## 1. Summary

This audit checks whether the recent Daily Ops Orchestrator, Notion, and account-aware operating paths remain consistent after OPER9-10.

Baseline commit:

```text
945e166f6608fb9a6d09a1596eb24df752b3aa86
```

Scope:

- No code changes were made for this audit.
- No `.env` or config files were created or modified.
- No Notion write/export/sync, import `--commit`, broker/API/order, ledger, or DB mutation command was run.
- The only Notion command executed was the read-only `paper_daily_ops.py status --include-notion-read` smoke.

OPER9-10 is considered applied:

- `paper_daily_ops.py status --include-notion-read` loads the repository root `.env`.
- Env-only Notion settings are accepted when the required env values are present.
- Daily Plan live read uses the same External Key lookup convention as Daily Plan export/upsert.
- The smoke account Daily Plan row is read successfully.

## 2. OPER9-10 Confirmation

Read-only smoke command:

```cmd
python scripts\paper_daily_ops.py status --account-id paper_orch_smoke_202606 --data-date 2026-06-05 --trade-date 2026-06-08 --json --include-notion-read
```

Observed result:

- `notion_live_read_status=WARNING`
- `notion_live_read_errors=[]`
- `DAILY_PLAN_NOTION_EXPORT.notion_status=PASS`
- `DAILY_PLAN_NOTION_EXPORT.notion_row_count=1`
- `DAILY_PLAN_NOTION_EXPORT.reconciliation_status=DONE`
- `operator_summary.current_step=MANUAL_EXECUTION_TEMPLATE`

Interpretation:

- The earlier env-loading failure is resolved.
- The existing Daily Plan Notion row is read-only verified.
- The Orchestrator no longer repeats `DAILY_PLAN_NOTION_EXPORT`.
- Remaining warnings are downstream Manual Execution / Manual Review live-read query warnings.

## 3. Investigation Scope

Audited areas:

- settings loading path
- Notion data source and mapping usage
- account-aware local paths
- date format and date semantics
- artifact naming and locations
- CLI contract and generated `next_command`
- safety guards around preview, commit, append, sync, and source-of-truth

Representative files reviewed:

- `scripts/export_paper_to_notion.py`
- `scripts/import_notion_executions.py`
- `scripts/import_notion_reviews.py`
- `scripts/sync_notion_execution_status.py`
- `scripts/sync_notion_review_status.py`
- `scripts/paper_daily_ops.py`
- `core/notion_settings.py`
- `core/paper_daily_ops_notion_status.py`
- `core/paper_daily_ops_orchestrator.py`
- `core/paper_daily_ops_evidence.py`
- `core/paper_account_paths.py`

## 4. Results Table

| Area | Existing convention | Current implementation | Match? | Risk | Recommendation |
|---|---|---|---|---|---|
| `.env` loading | Notion scripts call `load_dotenv()` before settings/token resolution | Export/import/sync scripts call `load_dotenv()`; `paper_daily_ops.py` now loads root `.env` | Yes | LOW | Keep as-is |
| settings fallback | env override, then settings data_sources, then legacy databases | `get_notion_data_source_id()` preserves this order; env-only works when settings file is absent/disabled | Yes | LOW | Keep as-is |
| mapping source | `config/notion_property_mapping.json`, fallback to example mapping | Actual local config file is absent; example mapping fallback is used | Partial | MEDIUM | Run schema drift validation before deeper smoke |
| Daily Plan Notion read | Daily Plan export/upsert uses account-aware External Key | live read now queries the same Daily Plan External Key | Yes | LOW | Keep as-is |
| Manual Execution Notion read | importer queries Manual Executions by execution date/status/account | live read queries Manual Executions by execution date/account and status fields | Partial | MEDIUM | Validate Manual Executions data source id and properties |
| Manual Review Notion read | importer queries Manual Reviews by review date/import status/account | live read queries Manual Reviews by review date/account and status fields | Partial | MEDIUM | Validate Manual Reviews data source id and properties |
| account root | non-default accounts use `outputs/paper_accounts/<account_id>` | smoke account artifacts are under `outputs/paper_accounts/paper_orch_smoke_202606` | Yes | LOW | Keep as-is |
| legacy fallback | `paper_default` may use `outputs/paper_test`; non-default must not use it as DONE evidence | Orchestrator blocks legacy `paper_test` evidence for non-default accounts | Yes | LOW | Keep guard |
| file dates | artifact filenames use compact `YYYYMMDD` | Daily Plan/config snapshot/evidence sidecars use compact dates | Yes | LOW | Keep as-is |
| JSON dates | JSON payloads use `YYYY-MM-DD` | Daily Plan JSON uses `data_date`, `trade_date`, `plan_date` as ISO dates | Yes | LOW | Keep as-is |
| CLI command shape | Windows CMD strings, explicit account/date flags | generated commands match help output for export/import/sync/review/plan | Yes | LOW | Keep as-is |
| commit safety | preview required before commit/append | Orchestrator blocks commit/append until preview JSON exists | Yes | LOW | Keep as-is |
| duplicate commit safety | commit report suppresses re-commit | commit/report presence marks DONE and removes commit recommendation | Yes | LOW | Keep as-is |
| REVIEW_DONE terminal | no next command after terminal state | stage advancement tests enforce null `next_command` and `FINAL_STATUS` | Yes | LOW | Keep as-is |

## 5. Found Inconsistencies

### MEDIUM: Manual Execution live-read query returns HTTP 400

- Symptom: `MANUAL_EXECUTION_TEMPLATE`, `MANUAL_EXECUTION_PREVIEW`, and `MANUAL_EXECUTION_STATUS_SYNC` report Notion live-read warnings with HTTP 400.
- Related files:
  - `core/paper_daily_ops_notion_status.py`
  - `core/notion_mapping.py`
  - `config/notion_property_mapping.example.json`
  - `scripts/import_notion_executions.py`
  - `scripts/sync_notion_execution_status.py`
- Existing convention: Manual Execution importer/sync use the Manual Executions data source id and mapping keys such as `execution_date`, `account_id`, `status`, and `import_status`.
- Current implementation: live read uses the same logical keys but a broader date/account query for multiple stages.
- Operational impact: Daily Plan progression is not blocked, but live Notion confirmation for Manual Execution rows is not reliable until the query/schema issue is resolved.
- Severity: MEDIUM.
- Follow-up fix needed: yes, before relying on live read to validate Manual Execution template/preview/sync readiness.

### MEDIUM: Manual Review live-read query returns HTTP 400

- Symptom: `MANUAL_REVIEW_TEMPLATE`, `MANUAL_REVIEW_PREVIEW`, and `MANUAL_REVIEW_STATUS_SYNC` report Notion live-read warnings with HTTP 400.
- Related files:
  - `core/paper_daily_ops_notion_status.py`
  - `core/notion_mapping.py`
  - `config/notion_property_mapping.example.json`
  - `scripts/import_notion_reviews.py`
  - `scripts/sync_notion_review_status.py`
- Existing convention: Manual Review importer/sync use the Manual Reviews data source id and mapping keys such as `review_date`, `account_id`, `review_status`, and `import_status`.
- Current implementation: live read uses the same logical keys but all read attempts return HTTP 400 in the smoke account.
- Operational impact: this does not block the current smoke step, because Manual Review is downstream of Manual Execution. It will matter before review preview/status-sync stages are trusted.
- Severity: MEDIUM.
- Follow-up fix needed: yes, before closing the full Notion live-read verification path.

### LOW: root `.env` loading call style is not identical across scripts

- Symptom: most Notion scripts call `load_dotenv()` while `paper_daily_ops.py` calls `load_dotenv(ROOT / ".env")`.
- Related files:
  - `scripts/export_paper_to_notion.py`
  - `scripts/import_notion_executions.py`
  - `scripts/import_notion_reviews.py`
  - `scripts/sync_notion_execution_status.py`
  - `scripts/sync_notion_review_status.py`
  - `scripts/paper_daily_ops.py`
- Existing convention: import-time dotenv loading after inserting repository root into `sys.path`.
- Current implementation: same effect for normal root-based execution, with `paper_daily_ops.py` being more explicit.
- Operational impact: low. Explicit root loading is more deterministic for Orchestrator status.
- Severity: LOW.
- Follow-up fix needed: optional cleanup only.

### LOW: no checked-in local Notion settings or mapping override

- Symptom: `config/notion_settings.json` and `config/notion_property_mapping.json` are absent locally; example mapping is used and data source ids come from env.
- Related files:
  - `core/notion_settings.py`
  - `core/notion_mapping.py`
  - `config/notion_settings.example.json`
  - `config/notion_property_mapping.example.json`
- Existing convention: settings/mapping may be supplied by local config or env/example fallback.
- Current implementation: env-only settings plus example mapping.
- Operational impact: acceptable for current Daily Plan path, but increases schema drift risk for Manual Executions and Manual Reviews.
- Severity: LOW to MEDIUM depending on operator reliance on live read.
- Follow-up fix needed: recommended read-only schema validation; do not commit private ids or secrets.

No HIGH severity inconsistency was found in the inspected paths.

## 6. Notion Live Read Warning Analysis

Smoke output by stage:

- `DAILY_PLAN_NOTION_EXPORT`: `PASS`, row count `1`, no warnings.
- `MANUAL_EXECUTION_TEMPLATE`: `WARNING`, row count `0`, HTTP 400 warning.
- `MANUAL_EXECUTION_PREVIEW`: `WARNING`, row count `0`, HTTP 400 warning.
- `MANUAL_EXECUTION_STATUS_SYNC`: `WARNING`, row count `0`, HTTP 400 warning.
- `MANUAL_REVIEW_TEMPLATE`: `WARNING`, row count `0`, HTTP 400 warning.
- `MANUAL_REVIEW_PREVIEW`: `WARNING`, row count `0`, HTTP 400 warning.
- `MANUAL_REVIEW_STATUS_SYNC`: `WARNING`, row count `0`, HTTP 400 warning.

The exact data source ids are intentionally omitted.

Interpretation:

- The warning is not caused by missing `.env` settings.
- The warning is not a normal "no rows yet" `UNKNOWN`; it is an actual Notion API validation failure.
- Daily Plan verification succeeds and is sufficient to advance the smoke account to `MANUAL_EXECUTION_TEMPLATE`.
- The most likely causes are data source id mismatch, property mapping mismatch, or data source/database endpoint mismatch for Manual Executions and Manual Reviews.
- Select/status option mismatch is less likely for the query itself because the current failing live-read filters only by date/account for template/status stages, but it may affect later status interpretation.
- Date/account filter mismatch could be involved if the actual property type differs from the example mapping.

Operational impact:

- Current smoke can continue to the Manual Execution Template export step.
- Before relying on `--include-notion-read` to prove Manual Execution or Manual Review readiness, the Manual Executions and Manual Reviews schema/query mismatch should be investigated.
- It is acceptable to classify this as a schema drift / data source validation follow-up, not as an OPER9-10 env loading regression.

## 7. Consistency Confirmed

Confirmed consistent areas:

- `.env` loading alignment after OPER9-10.
- Daily Plan External Key read alignment with export/upsert.
- account-aware root under `outputs/paper_accounts/<account_id>`.
- non-default account guard against using `outputs/paper_test` artifacts as DONE evidence.
- file naming uses compact `YYYYMMDD`.
- JSON internal dates use `YYYY-MM-DD`.
- evidence sidecar filenames align with existing artifact naming.
- generated Orchestrator commands match CLI help for:
  - `paper.py data-freshness`
  - `paper.py plan`
  - `export_paper_to_notion.py --daily-plan`
  - `export_paper_to_notion.py --manual-execution-template`
  - `import_notion_executions.py --preview`
  - `import_notion_executions.py --commit`
  - `sync_notion_execution_status.py`
  - `paper.py review`
  - `export_paper_to_notion.py --manual-review-template`
  - `import_notion_reviews.py --preview`
  - `import_notion_reviews.py --commit`
  - `sync_notion_review_status.py`
- preview-before-commit/append guards remain in place.
- local commit/append reports remain source-of-truth evidence.
- `REVIEW_DONE` terminal null command policy is covered by tests.

## 8. Follow-up Candidates

### OPER9 closeout before-final fix candidates

- Run read-only schema validation for Manual Executions and Manual Reviews.
- Confirm whether the env data source ids for Manual Executions and Manual Reviews are true data source ids for the current Notion API version.
- Confirm actual Manual Executions and Manual Reviews property names/types against the example mapping.

### Smoke resume checks

- Continue the smoke from `MANUAL_EXECUTION_TEMPLATE`.
- After template export, run Orchestrator status with `--include-notion-read` again.
- Confirm whether Manual Execution rows become readable or the HTTP 400 persists.

### OPER10 / n8n prerequisites

- n8n can consume `operator_summary` for the current Daily Plan-to-template step.
- n8n should surface `notion_live_read_status=WARNING` as operator attention, not as an automatic blocker for the current next command.
- Before n8n relies on Manual Execution/Review live-read details, resolve or explicitly classify the Manual Execution/Review HTTP 400 warnings.

### Long-term improvements

- Add a read-only schema drift audit command to the Orchestrator status workflow or closeout checklist.
- Add stage-specific Notion warning summaries to `operator_summary` if operators need compact visibility.
- Consider External Key lookup for additional exported template stages where canonical keys are available and align with existing export paths.

## 9. Security Notes

- `.env` was not read into this document.
- Token values were not printed or documented.
- Data source ids were not documented.
- `config/notion_settings.json` was not created or modified.
- `config/notion_property_mapping.json` was not created or modified.

## 10. Conclusion

Smoke account resume:

- Allowed to resume from `MANUAL_EXECUTION_TEMPLATE`.
- The current next command is a Notion write command and still requires explicit manual approval under existing OPER9 policy.

OPER9 closeout:

- Closeout is possible if the remaining Manual Execution/Manual Review live-read warning is documented as a known limitation or follow-up.
- A stricter closeout would first run read-only schema validation and fix the Manual Execution/Manual Review query mismatch.

Before OPER10 / n8n:

- Required: document that n8n renders `operator_summary` and does not reinterpret raw `stages`.
- Recommended: resolve Manual Execution/Manual Review live-read HTTP 400 warnings before n8n depends on those stage-specific Notion checks for automation routing.
- Still forbidden without later approval MFU: Notion write automation, import `--commit`, append, ledger mutation, broker/API/order execution.

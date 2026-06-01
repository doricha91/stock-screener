# PAPER17-1 Export / Sync Policy Inventory

## Purpose

PAPER17-1은 현재 repo에 존재하는 Notion export / sync 관련 명령, guard, dry-run/actual 정책, account scope, External Key 기반 update 정책, duplicate row 위험, 후속 hardening 필요 항목을 inventory로 정리한다.

이번 작업은 문서 조사 전용이다. Notion actual write/export/sync를 실행하지 않고, Python 코드와 outputs/paper 원장을 수정하지 않는다.

## Source-of-truth Principle

운영 원칙:

- CSV / JSON / Markdown / SQLite가 source-of-truth다.
- Notion은 input / review / staging / presentation layer다.
- Notion export/sync 실패만으로 local source-of-truth를 rollback하지 않는다.
- actual export/sync 전에는 dry-run 또는 schema/mapping preflight를 우선한다.
- `External Key`는 Notion row create/update 매칭의 핵심 key이며 수동 수정 금지다.
- paper_default actual export와 multi-account bulk export는 현재 금지 정책을 유지한다.

## Current Export / Sync Surfaces

현재 확인된 Notion export / sync surface:

- `scripts/export_paper_to_notion.py`
- `scripts/sync_notion_execution_status.py`
- `scripts/sync_notion_review_status.py`
- `scripts/dev/validate_notion_schema.py`
- `core/notion_exporters.py`
- `core/notion_daily_ops_status_exporter.py`
- `core/notion_manual_execution_status_sync.py`
- `core/notion_manual_review_status_sync.py`
- `core/notion_client.py`
- `core/notion_settings.py`
- `core/notion_mapping.py`

Importer preview/commit 명령은 Notion row status back-write가 아니라 Notion staging row read 및 local source-of-truth write 경로이므로, 이번 inventory에서는 status sync와 연결되는 주변 surface로만 취급한다.

## Command Inventory

| Area | Command | Target | Dry-run Support | Actual Support | Account Scope | Source-of-truth Impact | Notion Impact | Current Policy | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Daily Ops Status export | `python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --dry-run --json` | `daily_ops_status` | Yes | No | `paper_sandbox` 검증됨, account_id 생략 시 `paper_default`로 normalize 가능 | Read-only status read | None | Allowed dry-run | DB ID가 없어도 payload inspection 가능 |
| Daily Ops Status actual | `python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --confirm-actual --json` | `daily_ops_status` | No | Yes | actual은 code guard상 `paper_sandbox` only | Read-only status read | External Key 기준 create/update 1 row | Allowed guarded actual | schema validation PASS 필요 |
| Daily Ops Status actual for paper_default | `python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_default --confirm-actual --json` | `daily_ops_status` | N/A | Blocked by guard | `paper_default` | None if blocked | None if blocked | Forbidden | `core/notion_daily_ops_status_exporter.py` actual allowed account is `paper_sandbox` |
| Daily Ops Status with mixed targets | `python scripts\export_paper_to_notion.py --daily-ops-status --weekly --dry-run` | mixed | N/A | N/A | N/A | N/A | N/A | Forbidden | CLI rejects `--daily-ops-status` combined with other export targets |
| Read-only report exporters dry-run | `python scripts\export_paper_to_notion.py --weekly --dry-run --json` and analogous `--benchmark`, `--account-snapshot`, `--daily-plan`, `--daily-review-summary` | existing detail DBs | Yes | No | `--account-id` supported, default `paper_default` | Reads local artifacts | None | Allowed dry-run | Existing exporter targets share `export_selected_paper_reports_to_notion` |
| Read-only report exporters actual | `python scripts\export_paper_to_notion.py --weekly --json` and analogous targets | existing detail DBs | No | Yes | `--account-id` supported | Reads local artifacts | External Key upsert/update | 확인 필요 / policy hardening needed | Existing actual path does not use `--confirm-actual`; SOP should decide future guard |
| Bulk detail export | `python scripts\export_paper_to_notion.py --all --dry-run --json` | multiple detail DBs | Yes | No when dry-run | `--account-id` supported | Reads local artifacts | None | Allowed dry-run | Useful for payload inspection only |
| Bulk detail actual | `python scripts\export_paper_to_notion.py --all --json` | multiple detail DBs | No | Yes in current code | `--account-id` supported | Reads local artifacts | multiple Notion create/update operations | Forbidden by current PAPER16 policy until hardening | Code supports it, policy should prohibit use for now |
| Manual Execution status sync dry-run | `python scripts\sync_notion_execution_status.py --date <YYYY-MM-DD> --commit-report <path> --account-id <account_id> --dry-run --json` | Manual Executions status fields | Yes | No | CLI account_id must match report account_id | Reads commit sidecar | None | Allowed dry-run | Builds payload without `update_page` |
| Manual Execution status sync actual | `python scripts\sync_notion_execution_status.py --date <YYYY-MM-DD> --commit-report <path> --account-id <account_id> --json` | Manual Executions status fields | No | Yes | CLI/report account_id match required | Reads commit sidecar | `update_page` by page_id | 확인 필요 / guarded SOP needed | Does not use External Key upsert; relies on page_id in report |
| Manual Review status sync dry-run | `python scripts\sync_notion_review_status.py --date <YYYY-MM-DD> --commit-report <path> --account-id <account_id> --dry-run --json` | Manual Reviews status fields | Yes | No | CLI account_id must match report account_id | Reads append sidecar | None | Allowed dry-run | Builds payload without `update_page` |
| Manual Review status sync actual | `python scripts\sync_notion_review_status.py --date <YYYY-MM-DD> --commit-report <path> --account-id <account_id> --json` | Manual Reviews status fields | No | Yes | CLI/report account_id match required | Reads append sidecar | `update_page` by page_id | 확인 필요 / guarded SOP needed | Does not use External Key upsert; relies on page_id in report |
| Notion schema validation | `python scripts\dev\validate_notion_schema.py --daily-ops-status` | schema read | N/A | Read-only API | target-specific | None | Reads Notion schema only | Allowed read-only preflight | Not a write/export command |

## Dry-run / Actual Guard Inventory

Current guard findings:

- `--daily-ops-status` requires either `--dry-run` or `--confirm-actual`.
- `--daily-ops-status` rejects simultaneous `--dry-run` and `--confirm-actual`.
- `--daily-ops-status` cannot be combined with other export targets.
- Daily Ops Status actual export is limited in code to `account_id=paper_sandbox`.
- Daily Ops Status actual export validates schema before writing.
- Daily Ops Status dry-run does not instantiate a Notion write client and returns `would_write=false`.
- Existing detail exporters use `--dry-run` to suppress Notion writes, but actual mode is available by omitting `--dry-run`.
- Existing detail exporter actual mode currently does not require `--confirm-actual`.
- Manual Execution/Review status sync use `--dry-run` to suppress `update_page`.
- Manual Execution/Review status sync actual mode is available by omitting `--dry-run`.

Policy classification:

| Classification | Current Meaning |
| --- | --- |
| Allowed dry-run | Daily Ops Status dry-run, detail exporter dry-run, Manual Execution/Review status sync dry-run |
| Allowed guarded actual | Daily Ops Status actual for `paper_sandbox` with `--confirm-actual` and schema PASS |
| Forbidden | paper_default Daily Ops Status actual, multi-account bulk export, Daily Ops Status mixed-target export |
| Candidate / future | actual expansion beyond `paper_sandbox`, bulk policy, automatic duplicate audit |
| 확인 필요 | guard policy for existing detail exporter actual and Manual Execution/Review status sync actual |

## Account Scope Inventory

Current account scope:

- `normalize_notion_account_id(None)` resolves omitted account to `paper_default`.
- Daily Ops Status dry-run can build payload for a resolved account, but actual is limited to `paper_sandbox`.
- Existing detail exporters accept `--account-id` and build account-aware External Keys and `Account ID` payloads.
- Existing detail exporters keep paper_default legacy fallback for some targets.
- Manual Execution/Review status sync require CLI account_id and commit report account_id to match.
- Legacy commit/report without account_id resolves to `paper_default`.

Policy:

- `paper_sandbox` is the only validated Daily Ops Status actual target.
- `paper_default` actual export for new multi-account Daily Ops Status flow is forbidden.
- multi-account bulk export remains forbidden.
- additional non-default actual targets require a later safety review and duplicate/idempotency hardening.

## External Key / Idempotency Inventory

External Key role:

- `core/notion_client.py` provides `query_by_external_key` and `upsert_page_by_external_key`.
- `upsert_page_by_external_key` queries by External Key, updates when exactly one row exists, creates when no row exists, and raises `NotionDuplicateExternalKeyError` when multiple rows exist.
- Daily Ops Status uses `daily_ops_status:{account_id}:{status_date}`.
- Daily Ops Status actual calls `upsert_page_by_external_key` and reports `action=create` or `action=update`.
- Existing detail exporters use account-aware External Keys for read-only report targets and support paper_default legacy fallback in selected paths.
- Manual Execution/Review status sync primarily updates by `page_id` from commit/append reports, while writing account-aware canonical key and `Account ID` fields to the Notion row.

Idempotency policy:

- Same account_id / status_date / External Key should update the same Daily Ops Status row.
- External Key must not be manually edited in Notion.
- Duplicate External Key rows block safe upsert and require audit before rerun.
- Bulk rerun is prohibited until duplicate row audit and bulk policy are defined.

Known duplicate risk:

- A wrong External Key, manually edited External Key, or schema/property mismatch can create or hide duplicate rows.
- Existing detail exporters have legacy fallback behavior for `paper_default`; this is useful for compatibility but should be audited before any bulk actual rerun.
- Status sync by page_id avoids External Key lookup duplicate risk, but depends on commit/append report page_id correctness.

## Notion Target / Mapping Inventory

Current mapping/data source targets:

- `weekly_reports`
- `benchmark_reports`
- `account_snapshots`
- `daily_plans`
- `daily_review_summaries`
- `manual_reviews`
- `manual_executions`
- `daily_ops_status`

Settings:

- data source IDs are loaded from `config/notion_settings.json` or environment overrides.
- Daily Ops Status environment override: `NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID`.
- Manual Execution/Review status sync check `NOTION_MANUAL_EXECUTIONS_DATA_SOURCE_ID` and `NOTION_MANUAL_REVIEWS_DATA_SOURCE_ID`.

Schema validation:

- `scripts/dev/validate_notion_schema.py --daily-ops-status` is a read-only schema validation path.
- `daily_ops_status` actual export requires validator status `PASS`.
- Missing configured data source is handled as a settings error for actual export.

## Failure / Rerun Policy Inventory

Current policy:

- Notion export/sync failure is presentation-layer failure unless local source-of-truth was also modified by the failed command.
- Local source-of-truth commit/append should not be rolled back solely because Notion sync/export failed.
- Dry-run should be rerun first after schema/mapping/client errors.
- For Daily Ops Status, rerun should use the same `account_id`, `status_date`, and External Key.
- If duplicate rows are suspected, stop actual reruns and inspect manually.
- If schema/property mismatch is suspected, run documented schema/mapping validation if available; otherwise inspect mapping and Notion properties manually.

Current failure outputs:

- Daily Ops Status actual failure returns `sync_status=FAILED` in CLI failure summary.
- Manual Execution/Review status sync returns `overall_status=FAILED` on error.
- Existing detail exporter duplicate External Key can raise `NotionDuplicateExternalKeyError`.

## Forbidden Operations

Currently forbidden:

- paper_default Daily Ops Status actual export
- multi-account bulk actual export
- Daily Ops Status actual export without `--confirm-actual`
- Daily Ops Status export combined with other targets
- Notion row migration
- manual External Key edits
- actual export when schema/property mismatch is suspected
- source-of-truth rollback solely due to Notion sync/export failure
- cloud-triggered export without explicit safety review

## Known Gaps / Risks

Known gaps:

- duplicate row audit is not implemented.
- schema/view drift automatic check is not implemented.
- paper_sandbox is the only validated Daily Ops Status actual target.
- paper_sandbox actual rerun policy is documented but not backed by a dedicated rerun harness.
- paper_default legacy root policy and new Daily Ops Status actual export policy are intentionally not converged.
- existing detail exporter actual paths do not require `--confirm-actual`.
- Manual Execution/Review status sync actual paths do not require a confirm flag.
- multi-account bulk export remains prohibited by policy, but some code paths can perform multi-target actual export if invoked without `--dry-run`.
- Notion API automated verification of view configuration does not exist.
- candidate/future status labels may differ from actual emitted status values.

Risks:

- operator command misuse due to split CLI surface.
- duplicate Notion rows if External Key or mapping is wrong.
- accidental actual export to legacy/detail DBs if dry-run is omitted.
- status sync actual update to wrong page if commit/append sidecar page_id is stale or wrong.
- paper_default actual export confusion because omitted account_id normalizes to `paper_default`.

## Follow-up Hardening Candidates

Candidate hardening work:

- Add a formal command matrix/SOP gate for every actual export/sync command.
- Add `--confirm-actual` or equivalent guard to existing detail exporter actual paths.
- Add guarded confirm policy to Manual Execution/Review status sync actual paths.
- Add duplicate row audit by target, External Key, Account ID, and date.
- Add Daily Ops Status rerun risk assessment for `paper_sandbox`.
- Add schema/property mismatch preflight checklist or lightweight command wrapper.
- Add dry-run-before-actual enforcement for eligible paths.
- Add clearer paper_default actual export blocking for new multi-account flows.
- Add operator-visible report for would-create vs would-update before actual export.

## PAPER17-2 Recommendation

Recommended PAPER17-2 scope:

- Design Daily Ops Status rerun / duplicate risk assessment.
- Define External Key based idempotent update verification flow.
- Specify duplicate row audit inputs and output format.
- Define schema/property mismatch preflight checks before any actual export.
- Keep paper_sandbox actual rerun as a separate explicitly approved step.

PAPER17-2 should remain design or dry-run/preflight focused unless the user explicitly approves a limited actual rerun.

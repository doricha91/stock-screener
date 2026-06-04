# MFU-DAILY-OPS-ORCH-1 Stage Inventory and Gate Policy

## 1. Purpose

이번 MFU-DAILY-OPS-ORCH-1은 Daily Ops Orchestrator의 stage inventory, gate policy, next action recommendation 설계를 위한 문서 작업이며, 코드 구현, 신규 CLI 구현, DB write, paper 원장 수정, Notion write/export/sync, 자동 실행기 구현은 포함하지 않는다.

This document defines the first Daily Ops Orchestrator design layer for the Paper operation loop. It inventories existing PAPER16-20 documents, commands, reports, artifacts, stage candidates, status meanings, gate policy, and safe next-action recommendation rules.

## 2. Scope / Non-scope

Scope:

- Existing document / SOP inventory for PAPER16-20 and roadmap v1.3.
- Existing CLI / report / artifact inventory.
- Proposed stage map for the daily Paper operation loop.
- Stage-level input artifacts, output artifacts, command candidates, status candidates, gates, next actions, and gaps.
- Orchestrator status vocabulary and write-gate interpretation.

Non-scope:

- Code modification.
- New CLI implementation.
- Test modification.
- DB write.
- Paper ledger CSV modification.
- `outputs/paper_test`, `outputs/front_test`, or `outputs/paper_accounts` generated artifact modification.
- Notion API write, export, or status sync execution.
- Manual Execution commit.
- Manual Review append.
- Migration script.
- Automation runner.
- Broker/API integration.
- External delivery implementation.

## 3. Background and roadmap v1.3 alignment

Roadmap v1.3 changes the immediate priority from Stable Plan Row Identity / Non-empty Replay Smoke Expansion to Daily Ops Orchestrator / 운영 루프 통합.

Completed base flow:

- PAPER16: Daily Ops Status Dashboard.
- PAPER17: Export / Sync Policy Hardening.
- PAPER18: Alert / Monitoring Report.
- PAPER19: Replay / Same-date Diff.
- PAPER20: Replay Wrapper Operational Smoke / Runbook.

The remaining operational issue is that the operator still has to remember and sequence prepare, preflight, daily plan generation, Notion export readiness, Manual Execution preview/commit/status sync, review preparation, alert triage, replay check, and closeout. The first Orchestrator stage should reduce that memory burden without executing writes.

## 4. Daily Ops Orchestrator definition

The initial Daily Ops Orchestrator is:

- stage status aggregator
- next action recommender
- ops checklist compiler
- command map 정합화 계층
- gate policy 해석 계층

The initial Daily Ops Orchestrator is not:

- 자동 실행기
- Notion actual write/export/sync 실행기
- source-of-truth commit/append 자동화 도구
- 외부 전송 도구
- Broker/API 연동 도구

It may recommend a safe command candidate, but it must not run the command for the operator.

## 5. Existing document / SOP inventory

| Document | Status | Orchestrator relevance |
|---|---|---|
| `idea, PRD, TRD/paper 운영 기능 개발 로드맵 v1.3.md` | Found | Sets Daily Ops Orchestrator as next priority and defines stage aggregator / next action recommender boundary. |
| `docs/operations/paper_daily_ops.md` | Found | Canonical daily loop, source-of-truth rules, preview before commit/append, WARNING/FAIL policy, sync retry policy. |
| `docs/operations/paper_notion_ops.md` | Found | Notion DB SOP, Notion as input/review/staging layer, manual execution/review preview/commit/status sync flow, paper_default actual export prohibition. |
| `docs/operations/paper_replay_diff_runbook.md` | Found | Replay diff interpretation, read-only boundary, PASS/WARNING/FAIL meaning, PASS_WITH_METADATA_DIFF non-approval rule. |
| `docs/TRD/mfu_paper16_daily_ops_status_dashboard_design.md` | Found | Daily Ops Status fields, Next Recommended Command, Blocking Reason, workflow/review/sync status concepts. |
| `docs/TRD/mfu_paper16_operator_command_map_and_rerun_policy.md` | Found | Command map, rerun policy, source-of-truth rollback prohibition, paper_sandbox-only actual Daily Ops Status export guard. |
| `docs/TRD/mfu_paper17_export_sync_policy_inventory.md` | Found | Export/sync command classes and policy inventory. |
| `docs/TRD/mfu_paper17_export_sync_command_gate_sop.md` | Found | dry-run / actual / confirm guard and duplicate/preflight gate concepts. |
| `docs/TRD/mfu_paper18_alert_monitoring_closeout.md` | Found | Alert severity mapping: BLOCKING, NEEDS_REVIEW, SYNC_FAILED, INFO suppression; read-only alert boundary. |
| `docs/TRD/mfu_paper19_replay_same_date_diff_closeout.md` | Found | Daily Plan sidecar, replay diff, replay wrapper dry-run safety markers. |
| `docs/TRD/mfu_paper20_replay_smoke_runbook_closeout.md` | Found | Controlled replay smoke result, PASS_WITH_METADATA_DIFF interpretation, generated artifact non-commit policy. |

Not found in the requested list: none. File names matched the requested set.

## 6. Existing CLI / report / artifact inventory

| Item | Status | Read/write class | Notes |
|---|---|---|---|
| `scripts/paper.py` | Found | Mixed | Shortcuts and wrappers. `prepare-data` may update `market_data.db`; `status` is read-only; `eod --dry-run` is read-only; `eod --commit` may modify ledger files. |
| `scripts/paper.py status --date <date> --account-id <id> --json` | Current | Read-only | Candidate source for stage status aggregation. |
| `scripts/paper.py plan --date <date> --account-id <id>` | Current | Write/report generation | Runs paper daily plan after preflight; official plan output can be source artifact. |
| `scripts/paper.py eod --date <date> --account-id <id> --dry-run` | Current | Read-only / dry-run | Manual Execution preview-like EOD wrapper candidate. |
| `scripts/paper.py eod --date <date> --account-id <id> --commit` | Current | Write | Ledger-changing stage; Orchestrator must only recommend after gates pass. |
| `scripts/paper.py reports --account-id <id>` | Current | Report generation | Builds review/report artifacts after preflight. |
| `scripts/paper.py review-template --account-id <id>` | Current | Report/template generation | Prepares manual review inputs. |
| `scripts/paper.py review-validate --account-id <id>` | Current | Read-only validation | Checks manual review readiness. |
| `scripts/paper.py review-append --account-id <id>` | Current | Write | Appends review log; gated write stage. |
| `scripts/run_paper_daily_plan.py --date <date>` | Current | Write/report generation | Official daily plan generator; help shows only `--date`, no account-id or dry-run option. |
| `scripts/export_paper_to_notion.py --daily-plan --dry-run --json` | Current | Dry-run | Daily Plan Notion export readiness candidate. |
| `scripts/export_paper_to_notion.py --daily-review-summary --date <date> --dry-run --json` | Current | Dry-run | Daily Review Summary export readiness candidate. |
| `scripts/export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --dry-run --json` | Current | Dry-run | Daily Ops Status payload candidate. |
| `scripts/export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --confirm-actual --json` | Current but guarded | Actual Notion write/export | Current policy limits actual Daily Ops Status export to `paper_sandbox`; Orchestrator must not execute. |
| `scripts/import_notion_executions.py --date <date> --account-id <id> --preview --json` | Current | Preview | Reads Notion and writes preview report; does not modify Notion or ledgers in preview mode. |
| `scripts/import_notion_executions.py --commit --preview-json <path> --allow-warnings` | Current but write | Commit | Commits validated execution rows to paper ledger; gated. |
| `scripts/import_notion_reviews.py --date <date> --account-id <id> --preview --json` | Current | Preview | Reads Notion and writes preview report; does not modify Notion or review source files in preview mode. |
| `scripts/import_notion_reviews.py --commit --preview-json <path> --allow-warnings` | Current but write | Append | Appends validated review rows; gated. |
| `scripts/sync_notion_execution_status.py --date <date> --commit-report <path> --dry-run --json` | Current | Dry-run | Status sync payload check. Without `--dry-run`, updates Notion status fields. |
| `scripts/sync_notion_review_status.py --date <date> --commit-report <path> --dry-run --json` | Current | Dry-run | Status sync payload check. Without `--dry-run`, updates Notion status fields. |
| `scripts/dev/diff_daily_plan.py` | Found | Read-only comparison plus output report | Compares two existing Daily Plan JSON files; may write diff report to output dir. |
| `scripts/dev/replay_daily_plan_diff.py` | Found | Dry-run replay plus output report | Generates replay-only sidecar and diff report; no actual/export/sync/commit options. |
| `scripts/dev/capture_daily_plan_baseline.py` | Found | Dev-only controlled output | Requires explicit `--output-dir`; not official output path by default. |
| `scripts/dev/generate_paper_alert_report.py` | Found | Local report generation | Produces Paper Ops Exception Alert Report from JSON inputs/source-root. |

Key artifact families:

- Daily Plan Markdown / JSON sidecar, including `paper_daily_plan.v1`.
- Paper config snapshot / `paper_config_hash.v1`.
- Manual Execution preview and commit reports.
- Manual Review preview and commit reports.
- Daily Review Summary Markdown / JSON / Notion payload.
- Daily Ops Status payload JSON.
- Alert Report JSON / Markdown.
- Replay diff JSON / Markdown and replay-only regenerated sidecar.
- Paper ledger/source CSV/JSON/SQLite artifacts, which remain source-of-truth and must not be mutated by Orchestrator stage aggregation.

## 7. Proposed stage map

Proposed stage order:

```text
prepare / preflight
daily plan generation
daily plan JSON sidecar check
Notion daily plan export readiness
Manual Execution input readiness
Manual Execution preview
Manual Execution commit eligibility
Manual Execution status sync readiness
Daily Review Summary readiness
Manual Review input readiness
Manual Review append eligibility
Manual Review status sync readiness
Alert Report check
Replay / same-date diff check
Daily Ops closeout
```

The order is operational rather than strictly chronological. For example, Alert Report and Replay / same-date diff can be closeout checks that summarize risks after core source artifacts exist.

## 8. Stage inventory table

| Stage | Purpose | Input artifacts | Output artifacts | Current command candidates | Read-only / dry-run / write | Status candidates | Gate policy | Next action recommendation candidate | Known gaps |
|---|---|---|---|---|---|---|---|---|---|
| prepare / preflight | Confirm market data and paper workflow readiness before plan/reports/write stages. | market data DB/files, account config, paper source files, preflight checks. | preflight report, freshness summary, status JSON. | `python scripts\paper.py status --date <date> --account-id <id> --json`; `python scripts\paper.py data-freshness`; `python scripts\paper.py preflight` | status/data-freshness read-only; prepare-data may write market_data.db. | PASS, WARNING, BLOCKING, NOT_STARTED, UNKNOWN | BLOCKING/FAIL stops write recommendations; WARNING blocks write recommendations until explicit operator allowance. | If status missing, run read-only status. If freshness/preflight unknown, run read-only checks first. | Need Orchestrator-readable normalized status contract across status/freshness/preflight outputs. |
| daily plan generation | Ensure official Daily Plan exists for account/date. | preflight PASS/allowed WARNING, config, universe, market data, account state. | Daily Plan Markdown and JSON sidecar. | `python scripts\paper.py plan --date <date> --account-id <id>`; `python scripts\run_paper_daily_plan.py --date <date>` | Write/report generation. | PASS, WARNING, BLOCKING, NOT_STARTED, UNKNOWN | Do not recommend generation when preflight is BLOCKING. Treat plan generation as source artifact creation, not dry-run. | If plan missing and preflight is safe, recommend existing daily plan generation procedure. | `run_paper_daily_plan.py` help shows no account-id/dry-run; account-aware official plan command contract needs confirmation. |
| daily plan JSON sidecar check | Verify Daily Plan has machine-readable JSON sidecar for replay/export/status. | Daily Plan Markdown/JSON sidecar. | sidecar presence/compatibility status. | Current exact standalone validator not confirmed; replay/diff tools consume sidecars. | Read-only if implemented as file inspection. | PASS, WARNING, BLOCKING, NOT_STARTED, UNKNOWN | Missing sidecar blocks replay and weakens Notion/export readiness; does not by itself authorize regeneration. | If sidecar missing, recommend checking plan generation output and PAPER19 sidecar producer path. | No confirmed dedicated sidecar-check CLI. |
| Notion daily plan export readiness | Check whether Daily Plan could be exported to Notion without performing actual write. | Daily Plan artifacts, Notion settings/mapping, account/date. | dry-run Notion payload summary. | `python scripts\export_paper_to_notion.py --daily-plan --account-id <id> --dry-run --json` | Dry-run. | PASS, WARNING, BLOCKING, NOT_STARTED, UNKNOWN | schema/view drift suspicion or missing mapping blocks actual export. Dry-run PASS is not actual export approval. | If dry-run missing, recommend daily-plan export dry-run only. | Actual export guard differs by target; Daily Plan actual approval policy should remain separate. |
| Manual Execution input readiness | Determine whether Notion Manual Executions rows are ready for preview. | Notion Manual Executions rows, account/date filters, current paper state. | input readiness / preview candidate status. | `python scripts\import_notion_executions.py --date <date> --account-id <id> --preview --json` | Preview command reads Notion and creates preview report; no ledger write. | PASS, WARNING, NEEDS_REVIEW, NOT_STARTED, UNKNOWN | Notion rows are staging only. Missing/incomplete input prevents commit recommendation. | If input not checked, recommend preview command. If rows incomplete, recommend Notion input review. | Needs normalized machine output path discovery for latest preview. |
| Manual Execution preview | Validate execution rows against current paper state before commit. | Notion rows, account state, preview command inputs. | `manual_execution_import_preview_<date>.json` and summary. | `python scripts\import_notion_executions.py --date <date> --account-id <id> --preview --json` | Preview. | PASS, WARNING, BLOCKING, NEEDS_REVIEW, NOT_STARTED, UNKNOWN | FAIL/BLOCKING stops commit. WARNING blocks commit unless explicitly allowed. | If preview missing, recommend preview. If WARNING, recommend cause review or explicit allowance documentation. | Preview status vocabulary should be mapped to Orchestrator values. |
| Manual Execution commit eligibility | Decide whether commit can be recommended; do not run commit. | Manual Execution preview JSON, current ledger state, same-date guard. | eligibility decision only; commit report only after human-run commit. | `python scripts\import_notion_executions.py --date <date> --account-id <id> --commit --preview-json <preview_json> [--allow-warnings] --json` | Write. | PASS, WARNING, BLOCKING, NEEDS_REVIEW, NOT_STARTED, UNKNOWN | Commit recommendation only when preview PASS or explicitly allowed WARNING. BLOCKING/FAIL forbids. | If eligible, show commit command candidate. If not, stop and cite blocking/warning reason. | Orchestrator must avoid building a one-click runner; same-date duplicate guard should be first-class. |
| Manual Execution status sync readiness | Check whether committed execution rows can be reflected back to Notion status fields. | Manual Execution commit report JSON, Notion settings/mapping, account/date. | dry-run status sync payload or sync readiness status. | `python scripts\sync_notion_execution_status.py --date <date> --account-id <id> --commit-report <commit_report> --dry-run --json` | Dry-run; without `--dry-run` is Notion write. | PASS, WARNING, SYNC_FAILED, NOT_STARTED, UNKNOWN | Notion sync failure is not rollback reason. Use same commit report for status sync retry. Schema/view drift suspicion blocks actual status sync. | If commit report exists and sync missing/failed, recommend dry-run or guarded status sync retry candidate. | Need latest commit report discovery. |
| Daily Review Summary readiness | Ensure reports and daily review summary are ready for operator review. | committed ledger/state, reports, review buckets/worksheet. | Daily Review Summary Markdown/JSON and optional Notion dry-run payload. | `python scripts\paper.py reports --account-id <id>`; `python scripts\export_paper_to_notion.py --daily-review-summary --date <date> --account-id <id> --dry-run --json` | Report generation / dry-run. | PASS, WARNING, BLOCKING, NOT_STARTED, UNKNOWN | Missing commit/report artifacts can block review readiness. Dry-run export is not actual export approval. | If summary missing, recommend reports generation, then daily-review-summary dry-run if Notion presentation is needed. | Report generation writes report artifacts; Orchestrator only recommends. |
| Manual Review input readiness | Determine whether Manual Reviews rows are filled enough for validation. | Notion Manual Reviews rows, review template/log, account/date. | preview candidate status. | `python scripts\import_notion_reviews.py --date <date> --account-id <id> --preview --json`; `python scripts\paper.py review-validate --account-id <id>` | Preview/read-only validation. | PASS, WARNING, NEEDS_REVIEW, NOT_STARTED, UNKNOWN | Notion reviews are staging only; incomplete rows prevent append recommendation. | If input not checked, recommend review preview/validate. | Need clear mapping between Notion review preview and local review-template validation. |
| Manual Review append eligibility | Decide whether review append can be recommended; do not run append. | Manual Review preview JSON, review validation result, existing review log. | eligibility decision only; append/commit report only after human-run append. | `python scripts\import_notion_reviews.py --date <date> --account-id <id> --commit --preview-json <preview_json> [--allow-warnings] --json`; `python scripts\paper.py review-append --account-id <id>` | Write. | PASS, WARNING, BLOCKING, NEEDS_REVIEW, NOT_STARTED, UNKNOWN | FAIL/BLOCKING forbids append. WARNING requires explicit allowance and reason. | If eligible, show append command candidate. If incomplete, recommend Notion review input or validation. | There are two append paths; Orchestrator must clarify which source/report controls each path. |
| Manual Review status sync readiness | Check whether appended review rows can be reflected back to Notion status fields. | Manual Review commit report JSON, Notion settings/mapping, account/date. | dry-run status sync payload or sync readiness status. | `python scripts\sync_notion_review_status.py --date <date> --account-id <id> --commit-report <commit_report> --dry-run --json` | Dry-run; without `--dry-run` is Notion write. | PASS, WARNING, SYNC_FAILED, NOT_STARTED, UNKNOWN | Sync failure does not rollback review append. Same commit report should be reused. Schema/view drift suspicion blocks actual status sync. | If commit report exists and sync missing/failed, recommend dry-run or guarded status sync retry candidate. | Need latest review commit report discovery. |
| Alert Report check | Summarize BLOCKING/NEEDS_REVIEW/SYNC_FAILED conditions from available source reports. | Daily Ops Status JSON, preflight JSON, execution/review high-level JSON, freshness JSON, same-date guard JSON, source-root. | Alert Report JSON / Markdown. | `python scripts\dev\generate_paper_alert_report.py --account-id <id> --date <date> --source-root <root> --json` | Local report generation. | PASS, WARNING, BLOCKING, NEEDS_REVIEW, SYNC_FAILED, NOT_STARTED, UNKNOWN | Alert BLOCKING stops commit/append/export/sync recommendations. SYNC_FAILED routes to sync retry, not rollback. | If alert missing, recommend generating alert report from source-root or explicit JSON inputs. | Replay/diff source may still be optional or incomplete; closeout phase is the only current phase. |
| Replay / same-date diff check | Optionally verify Daily Plan same-date reproducibility without approving writes. | baseline Daily Plan JSON sidecar, regenerated/replay sidecar, config snapshot. | replay diff JSON / Markdown, replay wrapper summary. | `python scripts\dev\diff_daily_plan.py ... --json`; `python scripts\dev\replay_daily_plan_diff.py --account-id <id> --date <date> --baseline-plan <json> --output-dir <dir> --json` | Read-only/dry-run style validation plus generated smoke artifacts. | PASS, WARNING, BLOCKING, NOT_STARTED, UNKNOWN | Replay PASS or PASS_WITH_METADATA_DIFF never approves actual/export/sync/commit/append. FAIL/BLOCKING stops operational confidence. | If report missing, mark optional closeout check or recommend replay diff with controlled output-dir. | Stable plan row identity and non-empty replay smoke remain deferred. |
| Daily Ops closeout | Decide whether the day can be considered operationally closed. | statuses from all stages, ledger/review artifacts, sync statuses, alert/replay reports. | closeout checklist/status summary. | Current exact Orchestrator CLI not implemented; `python scripts\paper.py status --date <date> --account-id <id> --json` is current input candidate. | Read-only design target. | PASS, WARNING, BLOCKING, NEEDS_REVIEW, SYNC_FAILED, UNKNOWN | Closeout PASS requires no open BLOCKING/NEEDS_REVIEW and known sync/review disposition. Sync failure may allow source-of-truth closeout with presentation retry item. | If incomplete, recommend the earliest unresolved safe stage action. | No integrated closeout compiler exists yet. |

## 9. Status value definitions

| Status | Orchestrator meaning | Write recommendation impact |
|---|---|---|
| PASS | The stage completed and its artifact/status can be used by downstream stage decisions. | May allow downstream recommendation if all prior gates also pass. |
| WARNING | The stage has a non-blocking but material issue, incomplete confidence, or operator judgment requirement. | Write recommendations are blocked by default. Explicit allowance and reason are required. |
| BLOCKING | The stage found a safety issue, missing required artifact, duplicate risk, schema risk, or hard failure that prevents write-like downstream action. | Forbid commit/append/export/sync recommendations. |
| NEEDS_REVIEW | Human review is required before the stage can be considered safe. | Do not recommend write actions until review resolves. |
| NOT_STARTED | Required artifact/report/status has not been produced or found. | Recommend the safest read-only/dry-run precursor, not write action. |
| SKIPPED | Stage was intentionally skipped by policy or not applicable to this date/account. | Downstream impact depends on documented skip reason. Unknown skip reason becomes NEEDS_REVIEW. |
| SYNC_FAILED | Local source-of-truth commit/append may have succeeded, but Notion/export/status reflection failed. | Do not rollback source-of-truth. Recommend same-report sync retry or investigation. |
| UNKNOWN | Orchestrator cannot safely classify the stage. | Treat as blocking for write recommendations until evidence is available. |

## 10. Gate policy

- FAIL/BLOCKING means commit/append is forbidden.
- WARNING is blocked by default and requires explicit operator allowance before any write recommendation.
- Notion sync failure is not a source-of-truth rollback reason.
- If Notion sync fails after source-of-truth success, retry only status sync/export reflection with the same commit report, account_id, date, and External Key context.
- Replay PASS is not approval for actual/export/sync/commit.
- PASS_WITH_METADATA_DIFF can be treated as read-only replay smoke success, but it is not write approval.
- Schema/view drift suspicion forbids actual write/export/sync until schema/view compatibility is confirmed.
- `paper_default` actual Daily Ops Status export remains forbidden by current policy.
- Multi-account bulk actual export remains forbidden by current policy.
- Daily Ops Status actual export remains guarded and currently limited to documented `paper_sandbox` approval flow.
- Dry-run output is evidence for review, not proof that actual write is safe.
- Notion remains input UI / review UI / staging / presentation layer; CSV / JSON / Markdown / SQLite remain source-of-truth.
- Generated smoke artifacts are not source-of-truth and should not be committed by default.

## 11. Next action recommendation policy

The Orchestrator recommends only safe next action candidates. It does not execute commands.

Policy:

- Prefer read-only or dry-run recommendations before write recommendations.
- Recommend write commands only as text candidates after all required gates pass.
- If a command has not been confirmed by `--help` or existing SOP, mark it as candidate/future or 확인 필요.
- Include account/date placeholders and required report paths instead of guessing real paths.
- Surface the reason for no recommendation when a stage is BLOCKING, WARNING, NEEDS_REVIEW, or UNKNOWN.

Examples:

- Daily Plan missing -> recommend `python scripts\paper.py plan --date <date> --account-id <id>` only after preflight is PASS or explicitly allowed; otherwise recommend preflight/status first.
- Manual Execution preview missing -> recommend `python scripts\import_notion_executions.py --date <date> --account-id <id> --preview --json`.
- Alert BLOCKING -> do not recommend commit/append/export/sync; recommend alert report inspection and blocker resolution.
- WARNING exists -> do not recommend write step; recommend cause review or explicit allowance documentation.
- Notion sync failed -> do not rollback source-of-truth; recommend status sync dry-run/retry using the same commit report.
- Replay report missing -> mark as optional closeout check unless the operator is investigating reproducibility; if recommended, require controlled `--output-dir`.

## 12. Safety boundaries

- Orchestrator must not call Notion API.
- Orchestrator must not run Notion actual write/export/sync.
- Orchestrator must not commit Manual Execution rows.
- Orchestrator must not append Manual Review rows.
- Orchestrator must not write paper ledger CSV files.
- Orchestrator must not mutate DB files.
- Orchestrator must not create generated replay smoke artifacts as part of status aggregation.
- Orchestrator must not interpret replay PASS as actual approval.
- Orchestrator must not enable broker/API/live order paths.
- Orchestrator must not treat Notion status as source-of-truth.

## 13. Known gaps / risks

- No integrated Orchestrator CLI exists yet.
- No normalized stage status schema exists across status, preflight, import previews, sync dry-runs, alert reports, and replay reports.
- Latest artifact discovery rules need design: daily plan sidecar, preview JSON, commit report JSON, alert report, replay diff report.
- `run_paper_daily_plan.py` help shows only `--date`; account-aware official plan generation path needs confirmation.
- Daily Plan JSON sidecar check has no confirmed standalone CLI.
- Manual Execution and Manual Review each have multiple command paths; Orchestrator must avoid mixing local paper.py review wrappers with Notion import commit paths incorrectly.
- Replay / same-date diff remains read-only and optional for closeout unless a reproducibility investigation is active.
- Stable Plan Row Identity and non-empty replay smoke remain deferred important work.
- Schema/View Drift Check is still a follow-up; until implemented, schema/view suspicion should remain a conservative blocker for actual Notion write/export/sync.
- Existing uncommitted local generated/DB artifacts can appear in `git status`; Orchestrator docs must not stage or normalize them.

## 14. Recommended next MFU

Recommended next MFU: Daily Ops Orchestrator status contract and read-only source adapter design.

Suggested scope:

- Define `paper_daily_ops_orchestrator.v1` JSON schema.
- Define stage IDs, status enum, severity enum, gate result, artifact references, command recommendation shape, and safety markers.
- Map existing sources into that schema without running writer commands.
- Define latest-artifact discovery policy for account/date.
- Keep implementation deferred or limited to read-only prototype only after design approval.

## 15. Self-review / verification checklist

- The document defines Daily Ops Orchestrator as stage status aggregator / next action recommender, not an automation runner.
- Existing PAPER16-20 outputs are connected to proposed stages.
- Required stage candidates are included.
- Each stage has input artifacts, output artifacts, current command candidates, read/write class, status candidates, gate policy, next action candidate, and known gaps.
- PASS, WARNING, BLOCKING, NEEDS_REVIEW, NOT_STARTED, SKIPPED, SYNC_FAILED, UNKNOWN are defined.
- FAIL/BLOCKING/WARNING gate policy is explicit.
- Replay PASS and PASS_WITH_METADATA_DIFF are not treated as write approval.
- Notion sync failure is not a source-of-truth rollback reason.
- `paper_default` actual export and multi-account bulk actual export remain forbidden.
- No code, DB, paper ledger, Notion write/export/sync, or generated output mutation is included in this MFU.

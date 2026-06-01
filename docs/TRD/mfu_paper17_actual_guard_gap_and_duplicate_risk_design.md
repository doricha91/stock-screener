# PAPER17-2 Actual Guard Gap / Duplicate Risk Design

## Purpose

PAPER17-2는 PAPER17-1 inventory에서 확인된 Notion export/sync actual guard gap, dry-run 생략 위험, duplicate row 위험, External Key 기반 idempotency 검증 흐름, schema/property preflight 절차를 설계 문서로 정리한다.

이번 작업은 설계 전용이다. Python 코드 수정, 신규 CLI 구현, Notion actual write/export/sync 실행, outputs/paper 원장 수정은 하지 않는다.

## Source-of-truth Principle

운영 원칙:

- CSV / JSON / Markdown / SQLite가 source-of-truth다.
- Notion은 input / review / staging / presentation layer다.
- Notion export/sync 실패만으로 local source-of-truth를 rollback하지 않는다.
- actual export/sync는 기본 금지로 보고, dry-run과 preflight를 먼저 통과해야 한다.
- actual write는 명시적인 confirm guard 또는 문서화된 승인 명령이 있을 때만 허용한다.
- `External Key`와 `page_id`는 rerun/idempotency 판단의 핵심 식별자다.

## PAPER17-1 Findings Summary

PAPER17-1에서 확인된 사항:

- Daily Ops Status actual은 `paper_sandbox` + `--confirm-actual` + schema PASS guard가 있다.
- 기존 detail report exporter actual은 `--dry-run` 생략만으로 actual path가 열린다.
- `--all`은 코드상 multi-target actual export가 가능하지만, 현재 정책상 금지다.
- Manual Execution status sync actual은 `--dry-run` 생략 시 `update_page`를 호출할 수 있다.
- Manual Review status sync actual도 `--dry-run` 생략 시 `update_page`를 호출할 수 있다.
- `account_id` 생략은 `paper_default`로 normalize되며, legacy policy와 신규 multi-account policy 혼동 위험이 있다.
- duplicate row audit, schema/view drift 자동 점검, actual rerun harness는 아직 없다.

## Actual Guard Gap Matrix

| Area | Current Actual Trigger | Current Guard | Risk | Proposed Policy | Implementation Needed Later |
| --- | --- | --- | --- | --- | --- |
| Daily Ops Status actual | `--daily-ops-status --account-id paper_sandbox --confirm-actual` | `--confirm-actual`, account_id=`paper_sandbox`, schema validation PASS, single target only | Safe enough now; rerun duplicate risk still needs audit | Keep as the only allowed guarded actual path | Add rerun/duplicate preflight before repeated actual |
| detail report exporters actual | `--weekly`, `--benchmark`, `--account-snapshot`, `--daily-plan`, or `--daily-review-summary` without `--dry-run` | Notion client is created when `--dry-run` is omitted; no `--confirm-actual` | Guard gap; accidental actual write if dry-run omitted | Treat as policy-forbidden until confirm guard/SOP gate exists | Add `--confirm-actual` or wrapper gate; document allowed target/account matrix |
| `--all` bulk detail actual | `--all` without `--dry-run` | Existing exporter can run multiple target actual writes | Policy forbidden; duplicate and blast-radius risk | Forbid until duplicate audit, bulk policy, and explicit approval exist | Add hard CLI block or guarded bulk confirmation later |
| Manual Execution status sync actual | `sync_notion_execution_status.py` without `--dry-run` | account_id/report account_id match; page_id based `update_page`; no confirm flag | Needs confirm guard; stale/wrong page_id risk | Dry-run first; actual only with documented approval | Add confirm guard, page_id preflight, report/account/date validation summary |
| Manual Review status sync actual | `sync_notion_review_status.py` without `--dry-run` | account_id/report account_id match; page_id based `update_page`; no confirm flag | Needs confirm guard; stale/wrong page_id risk | Dry-run first; actual only with documented approval | Add confirm guard, page_id preflight, report/account/date validation summary |
| schema validation read-only preflight | `validate_notion_schema.py --daily-ops-status` | Read-only schema API call | Read-only preflight; does not cover duplicate/page_id/account correctness | Required before Daily Ops Status actual; recommended before other actual paths where available | Extend target-specific preflight coverage and reporting |

Classification:

- Safe enough now: Daily Ops Status actual for `paper_sandbox` only.
- Policy forbidden: `paper_default` Daily Ops Status actual, multi-target actual, bulk actual.
- Guard gap: detail report exporter actual paths.
- Needs confirm guard: Manual Execution/Review status sync actual.
- Needs duplicate audit: any repeated actual export or bulk rerun.
- Read-only preflight: schema validation paths.

## Dry-run Omission Risk

Risk pattern:

- Some commands use `--dry-run` as the only barrier between preview and actual.
- If the operator omits `--dry-run`, the command can instantiate `NotionClient` and write to Notion.
- This is acceptable only for deliberately approved guarded paths. It is risky for broad or legacy exporter paths.

High-risk paths:

- detail report exporter actual path: `export_paper_to_notion.py --weekly` and analogous targets without `--dry-run`
- `--all` bulk actual path: `export_paper_to_notion.py --all` without `--dry-run`
- Manual Execution status sync actual: `sync_notion_execution_status.py` without `--dry-run`
- Manual Review status sync actual: `sync_notion_review_status.py` without `--dry-run`

Policy proposal:

- actual is forbidden by default.
- dry-run must run first.
- actual requires explicit confirm guard or a documented approved command.
- bulk actual is forbidden until duplicate audit and bulk policy are implemented.
- commands whose actual path is opened only by omitting `--dry-run` should be hardened.

## Account Scope Risk

Current behavior:

- omitted `account_id` normalizes to `paper_default`.
- `paper_default` has legacy compatibility semantics in several paths.
- Daily Ops Status actual is explicitly limited to `paper_sandbox`.
- existing detail exporters support account-aware External Keys and paper_default legacy fallback in selected paths.
- Manual Execution/Review status sync checks CLI account_id against the sidecar report account_id.

Risks:

- an operator may omit `--account-id` and accidentally target `paper_default`.
- paper_default legacy fallback can be confused with new multi-account actual export policy.
- paper_default actual export remains forbidden for new Daily Ops Status flow.
- non-default actual expansion beyond `paper_sandbox` has not had safety review.

Policy proposal:

- keep Daily Ops Status actual limited to `paper_sandbox`.
- keep paper_default actual export forbidden for new multi-account Daily Ops Status flow.
- require explicit `--account-id` for any future actual export/sync path.
- require a safety review before enabling actual for any non-default account other than `paper_sandbox`.
- keep paper_default legacy compatibility for read/dry-run only unless a separate migration/convergence plan exists.

## External Key / Idempotency Risk

External Key policy:

- `External Key` is the canonical matching key for create/update style export.
- Daily Ops Status key format is `daily_ops_status:{account_id}:{status_date}`.
- same account_id / status_date / External Key should update exactly one existing page.
- `External Key` must not be manually edited in Notion.

Idempotency risks:

- zero match means create candidate, but only if the target/account/date are intentionally new.
- one match means update candidate.
- multiple matches means duplicate blocker.
- wrong mapping, wrong property type, or manually edited External Key can hide or create duplicates.
- detail exporters with paper_default legacy fallback require extra care before bulk rerun.
- status sync by `page_id` avoids External Key lookup but introduces stale/wrong page_id risk.

Policy proposal:

- actual export should show would-create vs would-update before write.
- repeated actual export should run duplicate preflight first.
- multiple matches should block actual rerun.
- stale or missing `page_id` should block status sync actual.

## Duplicate Row Audit Design

This is a design only; no audit command is implemented in PAPER17-2.

Audit input:

- target DB / data source key
- External Key property name
- External Key value
- Account ID
- status/report date
- optional expected page_id

Audit output:

- target
- account_id
- date
- external_key
- match_count
- page_id list
- classification: `create_candidate`, `update_candidate`, `duplicate_blocker`, `manual_review_required`
- recommended action

Decision rules:

- same External Key 0건: create candidate
- same External Key 1건: update candidate
- same External Key 2건 이상: duplicate blocker
- expected page_id mismatch: manual review required
- duplicate 발견 시 actual rerun 중단
- bulk rerun 전 target별 duplicate audit 필요

Minimum audit targets:

- `daily_ops_status`
- existing detail report targets before any bulk actual rerun
- Manual Execution/Review status sync sidecar page_id consistency before actual sync

## Schema / Property Preflight Design

Existing preflight:

- `scripts/dev/validate_notion_schema.py --daily-ops-status` exists as a read-only preflight.
- Daily Ops Status actual export requires schema validation status `PASS`.

Preflight limitation:

- schema validation reduces property mismatch risk.
- schema validation does not prove External Key uniqueness.
- schema validation does not prove page_id correctness.
- schema validation does not prove account_id/date/operator target correctness.
- schema validation does not inspect Notion view/filter configuration.

Policy proposal:

- schema/property mismatch suspicion blocks actual export.
- run documented schema/mapping validator when available.
- if no validator exists for a path, inspect mapping and Notion properties manually before dry-run rerun.
- extend detail exporter and status sync preflight coverage before broader actual enablement.

## Rerun Decision Policy

Rerun rules:

- If local source-of-truth commit/append succeeded and Notion sync failed, do not rollback local source-of-truth.
- Rerun only the Notion export/sync path using the same report/account/date/External Key or page_id.
- If duplicate is suspected, stop actual rerun.
- If stale page_id is suspected, stop status sync actual.
- If schema/property mismatch is suspected, stop actual and run preflight.
- If account_id is omitted or resolves unexpectedly to `paper_default`, stop actual.
- `paper_sandbox` actual rerun is not executed until separately approved by the user.
- multi-account bulk actual rerun remains forbidden.

Daily Ops Status rerun decision:

- dry-run first.
- confirm status_date, account_id, External Key, would_create/would_update.
- run schema validation.
- run duplicate audit when implemented.
- actual rerun only after explicit approval.

Manual Execution/Review status sync rerun decision:

- use same commit/append report.
- confirm report account_id matches CLI account_id.
- confirm page_id exists and is expected.
- dry-run first.
- actual only after explicit approval or future confirm guard.

## Proposed Hardening Options

### P0 Immediate Safety

- document and enforce "no actual without dry-run first" in operator SOP.
- keep bulk actual forbidden.
- keep paper_default actual export forbidden for new multi-account flows.
- mark detail exporter actual and status sync actual as guard-gap paths.

### P1 Operator Policy

- create command gate table for allowed dry-run, allowed actual, forbidden, and future paths.
- require explicit account_id in all actual SOP examples.
- require schema/preflight before actual.
- define rerun checklist for Daily Ops Status and status sync.

### P2 Implementation Design

- add `--confirm-actual` or equivalent guard to detail exporter actual paths.
- add confirm guard to Manual Execution/Review status sync actual paths.
- design duplicate audit command by target / External Key / Account ID / date.
- add would-create vs would-update dry-run summary before actual.
- extend schema/property preflight coverage for detail exporters and status sync.

### P3 Convenience / Automation

- wrapper CLI for approved operator flows.
- GitHub Actions only after dry-run/actual policy is hardened.
- GUI / Notion button only after command guard and audit policies are implemented.
- automated schema/view drift check after manual view policy stabilizes.

## Non-scope

PAPER17-2 does not include:

- Python code changes
- new CLI implementation
- actual `--confirm-actual` implementation
- duplicate audit command implementation
- Notion actual write/export/sync
- Notion API write calls
- Notion DB/view modification
- outputs/paper ledger modification
- paper_default actual export
- multi-account bulk export
- paper_sandbox actual rerun
- Alert / Replay / Schema Drift / Universe / Strategy implementation

## PAPER17-3 Recommendation

Recommended PAPER17-3:

- create an operator-facing command gate document/SOP for export/sync actual paths.
- convert PAPER17-2 policy into a concise allowed/forbidden command matrix.
- decide whether detail exporter actual paths should be blocked in code or first documented as forbidden.
- design the minimum duplicate audit dry-run interface.
- keep implementation separate from actual Notion execution.

PAPER17-3 should remain no-actual unless the user explicitly approves a narrow dry-run/preflight implementation.

# PAPER17-3 Export / Sync Command Gate SOP

## Purpose

PAPER17-3는 운영자가 Notion export/sync 명령을 실행할 때 어떤 명령이 dry-run으로 허용되고, 어떤 actual 명령이 현재 guarded actual로 허용되며, 어떤 명령이 금지 또는 future hardening 대상인지 판단할 수 있도록 Command Gate SOP를 정리한다.

이번 작업은 문서/SOP 작업이다. Python 코드 수정, 신규 CLI 구현, Notion actual write/export/sync 실행, outputs/paper 원장 수정은 하지 않는다.

## Source-of-truth Principle

운영 원칙:

- CSV / JSON / Markdown / SQLite가 source-of-truth다.
- Notion은 input / review / staging / presentation layer다.
- Notion export/sync 실패만으로 local source-of-truth를 rollback하지 않는다.
- actual 실행 전에는 dry-run과 preflight를 먼저 수행한다.
- actual은 명시적 confirm guard 또는 문서화된 승인 명령이 있을 때만 허용한다.
- `External Key`와 `page_id`는 rerun/idempotency 판단의 핵심 식별자다.

## Command Gate Summary

| Classification | Command / Pattern | Current Status | Required Before Run | Operator Decision |
| --- | --- | --- | --- | --- |
| Allowed dry-run | `python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --dry-run --json` | current allowed | explicit account_id, read-only status available | inspect payload only |
| Allowed dry-run | detail report exporter dry-run: `--weekly --dry-run`, `--benchmark --dry-run`, `--account-snapshot --dry-run`, `--daily-plan --dry-run`, `--daily-review-summary --dry-run` | current allowed | target/date/source artifact exists | inspect payload; do not assume Notion update |
| Allowed dry-run | `python scripts\export_paper_to_notion.py --all --dry-run --json` | current allowed as read-only payload inspection | explicit account_id preferred | inspect multi-target payload only |
| Allowed dry-run | `python scripts\sync_notion_execution_status.py --date <YYYY-MM-DD> --commit-report <path> --account-id <account_id> --dry-run --json` | current allowed | commit report exists, account_id matches report | inspect status sync payload |
| Allowed dry-run | `python scripts\sync_notion_review_status.py --date <YYYY-MM-DD> --commit-report <path> --account-id <account_id> --dry-run --json` | current allowed | append report exists, account_id matches report | inspect status sync payload |
| Allowed guarded actual | `python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --confirm-actual --json` | current guarded actual | dry-run first, schema PASS, External Key checked, duplicate suspicion absent, explicit user approval | allowed only for `paper_sandbox` Daily Ops Status single target |
| Forbidden | Daily Ops Status `paper_default` actual | blocked by current guard/policy | N/A | do not run |
| Forbidden | Daily Ops Status mixed target export | rejected by current CLI/policy | N/A | do not run |
| Forbidden | `python scripts\export_paper_to_notion.py --all --json` | code path may exist, policy forbidden | N/A | do not run |
| Forbidden | multi-account bulk actual | policy forbidden | N/A | do not run |
| Forbidden | actual command with omitted `--account-id` | policy forbidden for actual | N/A | stop; add explicit account_id or do not run |
| Forbidden | actual while schema/property mismatch is suspected | policy forbidden | N/A | stop; run preflight/manual schema check |
| Forbidden | actual while duplicate row is suspected | policy forbidden | N/A | stop; audit duplicate risk |
| Forbidden | status sync actual with stale/wrong `page_id` suspicion | policy forbidden | N/A | stop; inspect report/page_id |
| Forbidden | local source-of-truth rollback due only to Notion failure | policy forbidden | N/A | do not rollback local ledger/review state |
| Forbidden | manual `External Key` edit | policy forbidden | N/A | do not edit |
| Future / needs hardening | detail report exporter actual without `--confirm-actual` | guard gap | future confirm guard/SOP gate | do not run for now |
| Future / needs hardening | Manual Execution status sync actual without confirm guard | needs confirm guard | future confirm guard/page_id preflight | dry-run only for now unless separately approved |
| Future / needs hardening | Manual Review status sync actual without confirm guard | needs confirm guard | future confirm guard/page_id preflight | dry-run only for now unless separately approved |
| Future / needs hardening | non-default actual beyond `paper_sandbox` | not approved | future safety review | do not run |
| Future / needs hardening | paper_default actual migration/convergence | not approved | future migration/convergence design | do not run |
| Future / needs hardening | duplicate audit command | not implemented | future design/implementation | use manual audit only |
| Future / needs hardening | schema/view drift automatic check | not implemented | future design/implementation | use manual/schema validator where available |
| Future / needs hardening | wrapper CLI / GitHub Actions / GUI / Notion button | not implemented | command guard and audit policy first | defer |

## Allowed Dry-run Commands

Allowed dry-run commands:

- `python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --dry-run --json`
- `python scripts\export_paper_to_notion.py --weekly --account-id <account_id> --dry-run --json`
- `python scripts\export_paper_to_notion.py --benchmark --account-id <account_id> --dry-run --json`
- `python scripts\export_paper_to_notion.py --account-snapshot --account-id <account_id> --dry-run --json`
- `python scripts\export_paper_to_notion.py --daily-plan --account-id <account_id> --dry-run --json`
- `python scripts\export_paper_to_notion.py --daily-review-summary --account-id <account_id> --date <YYYY-MM-DD> --dry-run --json`
- `python scripts\export_paper_to_notion.py --all --account-id <account_id> --dry-run --json`
- `python scripts\sync_notion_execution_status.py --date <YYYY-MM-DD> --commit-report <path> --account-id <account_id> --dry-run --json`
- `python scripts\sync_notion_review_status.py --date <YYYY-MM-DD> --commit-report <path> --account-id <account_id> --dry-run --json`

Dry-run interpretation:

- dry-run is inspection only.
- dry-run does not prove actual is allowed.
- dry-run output must be checked for account_id, target, External Key, action, page_id, and source paths.
- dry-run should be rerun after any schema/mapping/source artifact correction.

## Allowed Guarded Actual Commands

Currently allowed guarded actual:

```cmd
python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --confirm-actual --json
```

Conditions:

- dry-run ran first.
- schema validation PASS was confirmed.
- `account_id` is exactly `paper_sandbox`.
- target is exactly `daily_ops_status`.
- no other export target is combined.
- External Key is expected.
- would-create / would-update meaning is understood.
- duplicate row is not suspected.
- user explicitly approves the actual run.

No other actual export/sync command is considered generally allowed by this SOP.

## Forbidden Commands

Forbidden:

- Daily Ops Status `paper_default` actual.
- Daily Ops Status mixed target export.
- `--all` actual.
- multi-account bulk actual.
- actual command with omitted `--account-id`.
- actual command where `account_id` normalizes unexpectedly to `paper_default`.
- actual command when schema/property mismatch is suspected.
- actual command when duplicate row is suspected.
- status sync actual when stale/wrong `page_id` is suspected.
- Notion failure driven local source-of-truth rollback.
- manual `External Key` edit.
- cloud-triggered export without explicit safety review.

## Future / Needs Hardening Commands

Future / needs hardening:

- detail report exporter actual without `--confirm-actual`.
- Manual Execution status sync actual without confirm guard.
- Manual Review status sync actual without confirm guard.
- non-default account actual beyond `paper_sandbox`.
- paper_default actual migration/convergence.
- duplicate audit command.
- schema/view drift automatic check.
- wrapper CLI.
- GitHub Actions.
- GUI.
- Notion button.

These are not approved operator actual paths until a later MFU implements or documents the relevant guard.

## Required Preflight Checklist

Before any actual export/sync:

- dry-run result reviewed.
- explicit `--account-id` present.
- target is a single intended target.
- command does not resolve to `paper_default` unless the future SOP explicitly allows that path.
- schema/property preflight ran if available.
- External Key is non-empty and expected.
- would-create / would-update meaning is understood.
- duplicate row is not suspected.
- if page_id based sync, page_id matches the report and expected Notion row.
- local source-of-truth change and Notion presentation update are treated separately.
- user explicitly approves actual.

## Rerun Decision Checklist

Rerun rules:

- If local commit/append succeeded and Notion sync failed, do not rollback local source-of-truth.
- Rerun only the Notion export/sync path.
- Use the same report/account/date/External Key or page_id.
- If duplicate is suspected, stop actual.
- If stale page_id is suspected, stop actual.
- If schema/property mismatch is suspected, stop actual.
- If account_id is missing, stop actual.
- If paper_default confusion is possible, stop actual.
- paper_sandbox actual rerun also requires separate approval.
- bulk rerun remains forbidden.

## Account Scope Rules

Account rules:

- actual commands must include explicit `--account-id`.
- omitted account_id resolves to `paper_default` and is not acceptable for current actual paths.
- Daily Ops Status actual is currently limited to `paper_sandbox`.
- paper_default actual export is forbidden for new multi-account flows.
- non-default actual beyond `paper_sandbox` needs later safety review.
- report account_id must match CLI account_id for status sync dry-run/actual consideration.

## External Key / page_id Safety Rules

External Key rules:

- `External Key` must not be manually edited.
- expected Daily Ops Status External Key format is `daily_ops_status:{account_id}:{status_date}`.
- zero matching rows means create candidate.
- one matching row means update candidate.
- multiple matching rows means duplicate blocker.
- unknown or blank External Key blocks actual.

page_id rules:

- Manual Execution/Review status sync uses page_id from commit/append report.
- stale or unexpected page_id blocks actual.
- page_id mismatch should be treated as manual review required.
- page_id based sync does not replace External Key/account/date reasoning.

## Operator Stop Rules

Stop immediately if:

- `--dry-run` was not executed first.
- actual command lacks `--account-id`.
- account_id is not the expected account.
- command target is multiple targets.
- command is `--all` actual.
- command targets `paper_default` actual.
- External Key is empty or unexpected.
- duplicate row is possible.
- page_id may be stale or wrong.
- schema/property mismatch is suspected.
- Notion state conflicts with local source-of-truth.
- operator cannot explain whether the action will create or update.

## PAPER17-4 Recommendation

Recommended PAPER17-4:

- design or implement the minimum duplicate audit dry-run interface.
- include target, account_id, date, External Key, match count, page_id list, and recommendation.
- start with `daily_ops_status` only.
- keep actual rerun out of scope unless separately approved.
- use this SOP as the command gate baseline for future code hardening.

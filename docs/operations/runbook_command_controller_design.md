# Runbook Command Controller Design

This document designs a safe controller for running selected Paper Daily Cycle runbook commands from n8n/Telegram. It is a design document only. It does not implement Python controller code, n8n workflow changes, Telegram commands, Windows wrappers, Task Scheduler, Notion writes, or broker/order execution.

## Purpose

The current n8n/Telegram MVP can read latest status files. The next automation layer should let the operator choose, run, inspect, and approve runbook commands without ever executing arbitrary Telegram text.

Target shape:

```text
Telegram = mobile control panel
n8n = message/button router
Windows runner wrapper = local Python execution entrypoint
Runbook Command Controller = allowlisted command_key executor
stock-screener scripts = actual paper ops commands
```

The controller is not a trading bot. It is a guarded operator tool for the documented Paper Daily Cycle. It must preserve the project rule that local files, CSV/JSON/Markdown artifacts, SQLite DBs, and existing scripts remain the source of truth.

## Role Separation

### daily_refresh

`daily_refresh` is a status/preview freshness command, not the full daily ops executor.

Implemented role:

```text
resolve dates
-> update context
-> paper_daily_ops.py status --json --include-notion-read
-> paper.py eod --dry-run
-> latest status files
```

It should remain safe for scheduled refresh. It does not run plan generation, Notion export/import, commit, sync, approval, or live broker activity.

### Runbook Command Controller

The controller is the future executor for `paper_daily_cycle_commands.md` steps. It maps an explicit `command_key` to a predefined argv template and executes it with `shell=False`.

It is responsible for:

- command registry lookup
- context substitution
- approval gate enforcement
- preview/commit dependency checks
- command run result files
- post-run refresh policy

It must not execute `operator_summary.next_command` as a raw string. The orchestrator can suggest the next step, but the controller must translate that suggestion to a known `command_key` before execution.

### Approval Controller

The approval controller manages write-risk commands. It creates approval files with frozen argv/context, records approval decisions, expires stale requests, and only executes approved frozen argv.

It is responsible for:

- `/request <command_key>`
- `/approve <approval_id>`
- `/reject <approval_id>`
- approval status/history files
- expiration checks

### n8n/Telegram

n8n and Telegram are UI/transport only.

They are responsible for:

- chat allowlist
- command text/button routing
- showing latest output files
- collecting approval decisions
- invoking the Windows runner wrapper with allowlisted runner commands

They must not:

- run stock-screener Python scripts directly from Telegram input
- concatenate user text into a shell command
- bypass controller approval checks

## Non-Negotiable Safety Rules

- Telegram input is never a shell command.
- `operator_summary.next_command` is never executed directly.
- Every executable action is `command_key -> registry -> argv_template -> subprocess(..., shell=False)`.
- Unknown commands are `BLOCKED`.
- Write commands require a request/approve flow.
- Approval freezes `account_id`, `data_date`, `trade_date`, `command_key`, `argv`, and relevant preview/report paths.
- `approve` executes only stored approval argv, not a newly assembled command.
- No broker/API/order placement is in scope.

## Command Registry Schema

The controller should keep a registry in code or JSON/YAML loaded by code. The first implementation should prefer Python constants for type safety and testability.

Required fields:

| Field | Purpose |
| --- | --- |
| `command_key` | Stable operator-facing key, e.g. `status`, `execution_preview`. |
| `step_id` | Paper Daily Cycle step number or symbolic id. |
| `display_name` | Human-readable name for Telegram/UI. |
| `argv_template` | List-style argv template. No raw shell string. |
| `command_type` | Gate class such as `READ_ONLY`, `NOTION_WRITE`, `LEDGER_WRITE`. |
| `approval_required` | Boolean derived from type but stored explicitly for clarity. |
| `allowed_auto_run` | Whether `/run <command_key>` may execute without approval. |
| `required_context_fields` | Usually `account_id`, `data_date`, `trade_date`; some commands need preview/report paths. |
| `expected_outputs` | Files or JSON fields expected after success. |
| `success_criteria` | Text or machine-readable checks for PASS. |
| `failure_policy` | What to do on error and which next action to recommend. |
| `post_run_refresh` | Whether to run `status`, `daily_refresh`, or no refresh after completion. |

Example registry entry:

```python
{
    "command_key": "execution_preview",
    "step_id": 7,
    "display_name": "Execution Preview",
    "argv_template": [
        "scripts\\import_notion_executions.py",
        "--date", "{trade_date}",
        "--account-id", "{account_id}",
        "--preview",
        "--json",
    ],
    "command_type": "READ_ONLY_PREVIEW",
    "approval_required": False,
    "allowed_auto_run": True,
    "required_context_fields": ["account_id", "trade_date"],
    "expected_outputs": ["preview_json_path", "fail_count", "commit_allowed"],
    "success_criteria": "fail_count=0 and commit_allowed=true-or-reviewable",
    "failure_policy": "Do not request commit approval; fix Notion input rows first.",
    "post_run_refresh": "status",
}
```

Context substitution must validate every placeholder. Missing context fields should fail before subprocess execution.

## Command Types And Approval Gate

| command_type | Meaning | Auto run | Approval |
| --- | --- | --- | --- |
| `READ_ONLY` | Inspects local or remote read-only state. | Yes | No |
| `READ_ONLY_PREVIEW` | Reads input and writes preview artifacts only. | Yes | No |
| `LOCAL_ARTIFACT_WRITE` | Writes local plans/reports/templates but not ledger/source-of-truth commit. | No | Yes |
| `NOTION_WRITE` | Creates/updates/syncs Notion rows/status. | No | Yes |
| `LEDGER_WRITE` | Appends local source-of-truth ledger/review log. | No | Yes, after preview |
| `STATE_SNAPSHOT_WRITE` | Writes current state/account/position snapshots. | No | Yes, after dry-run |
| `UNKNOWN` | Not classified. | No | Not executable |
| `BLOCKED` | Explicitly forbidden or unsafe in current context. | No | Not executable |

Gate rules:

- `READ_ONLY` and `READ_ONLY_PREVIEW` may run through `/run <command_key>`.
- `LOCAL_ARTIFACT_WRITE` and `NOTION_WRITE` require `/request` then `/approve`.
- `LEDGER_WRITE` and `STATE_SNAPSHOT_WRITE` require a successful preview/dry-run artifact and `/approve`.
- `UNKNOWN` and `BLOCKED` cannot be run or requested.
- If `recommended_operator_action=RESOLVE_CONFLICT`, all write requests are blocked until status is clean.

## Runbook Step To command_key Mapping

This table maps Paper Daily Cycle steps 0-18 to controller command keys. It is an initial registry design, not an implementation.

| Step | command_key | argv template | Type | Auto run | Approval | Success criteria | Failure policy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | `status` | `scripts\\paper_daily_ops.py status --account-id {account_id} --data-date {data_date} --trade-date {trade_date} --json --include-notion-read` | `READ_ONLY` | Yes | No | `operator_summary` exists, blockers reviewed | Stop on blockers/conflicts |
| 1 | `data_prepare` | `scripts\\paper.py prepare-data --date {data_date} --universe` | `LOCAL_ARTIFACT_WRITE` | No | Yes | prepare errors absent | Fix market data/network/DB |
| 2 | `data_freshness` | `scripts\\paper.py data-freshness --date {data_date}` | `READ_ONLY` | Yes | No | `result=PASS` | Do not run plan |
| 3 | `daily_plan` | `scripts\\paper.py plan --data-date {data_date} --trade-date {trade_date} --account-id {account_id}` | `LOCAL_ARTIFACT_WRITE` | No | Yes | account plan md/json/config snapshot written | Fix freshness/preflight/date |
| 4 | `export_daily_plan_notion` | `scripts\\export_paper_to_notion.py --daily-plan --account-id {account_id} --date {trade_date} --confirm-actual --json` | `NOTION_WRITE` | No | Yes | failed count 0 | Fix Notion schema/auth/data |
| 5 | `export_execution_template` | `scripts\\export_paper_to_notion.py --manual-execution-template --account-id {account_id} --date {trade_date} --confirm-actual --json` | `NOTION_WRITE` | No | Yes | candidate rows create/update or no-op | Check plan candidates/Notion output |
| 6 | `wait_execution_input` | Not executable; Notion UI input | `BLOCKED` | No | N/A | `Status=READY`, actual fill fields complete | Wait for operator input |
| 7 | `execution_preview` | `scripts\\import_notion_executions.py --date {trade_date} --account-id {account_id} --preview --json` | `READ_ONLY_PREVIEW` | Yes | No | `fail_count=0`, commit allowed/reviewable | Fix Notion execution rows |
| 8 | `execution_commit` | `scripts\\import_notion_executions.py --date {trade_date} --account-id {account_id} --commit --preview-json {execution_preview_json} --json` | `LEDGER_WRITE` | No | Yes | commit report written, committed count expected | Stop; do not sync |
| 9 | `sync_execution_status` | `scripts\\sync_notion_execution_status.py --date {trade_date} --account-id {account_id} --commit-report {execution_commit_report} --json` | `NOTION_WRITE` | No | Yes | failed count 0 | Retry same report after Notion fix |
| 10 | `daily_review` | `scripts\\paper.py review --account-id {account_id} --date {trade_date}` | `LOCAL_ARTIFACT_WRITE` | No | Yes | reports/review template validation PASS | Fix report/preflight/template dates |
| 11 | `export_review_template` | `scripts\\export_paper_to_notion.py --manual-review-template --account-id {account_id} --date {trade_date} --confirm-actual --json` | `NOTION_WRITE` | No | Yes | review rows create/update, failed count 0 | Fix Notion schema/auth |
| 12 | `wait_review_input` | Not executable; Notion UI input | `BLOCKED` | No | N/A | `Import Status=READY`, answer reviewed | Wait for operator input |
| 13 | `review_preview` | `scripts\\import_notion_reviews.py --date {trade_date} --account-id {account_id} --preview --json` | `READ_ONLY_PREVIEW` | Yes | No | `fail_count=0`, append allowed/reviewable | Fix Notion review rows |
| 14 | `review_append` | `scripts\\import_notion_reviews.py --date {trade_date} --account-id {account_id} --commit --preview-json {review_preview_json} --json` | `LEDGER_WRITE` | No | Yes | appended count expected, failed count 0 | Stop; do not sync |
| 15 | `sync_review_status` | `scripts\\sync_notion_review_status.py --date {trade_date} --account-id {account_id} --commit-report {review_commit_report} --json` | `NOTION_WRITE` | No | Yes | failed count 0 | Retry same report after Notion fix |
| 16 | `eod_dryrun` | `scripts\\paper.py eod --date {trade_date} --account-id {account_id} --dry-run` | `READ_ONLY_PREVIEW` | Yes | No | write intent safe, required dry-run fields match | Review before commit |
| 17 | `eod_commit` | `scripts\\paper.py eod --date {trade_date} --account-id {account_id} --commit` | `STATE_SNAPSHOT_WRITE` | No | Yes | state/snapshot writes performed as expected | Stop and inspect preflight/guard |
| 18 | `final_status` | `scripts\\paper_daily_ops.py status --account-id {account_id} --data-date {data_date} --trade-date {trade_date} --json --include-notion-read` | `READ_ONLY` | Yes | No | `overall_status=PASS`, terminal true | Resolve blockers/conflicts |

Additional controller keys:

| command_key | Purpose | Type | Notes |
| --- | --- | --- | --- |
| `daily_refresh` | Refresh context/status/eod dry-run latest files. | `READ_ONLY_PREVIEW` | Already implemented runner command; not the full controller. |
| `next` | Show recommended next registry command. | `READ_ONLY` | Derived from status + registry mapping. |
| `last` | Show last command run summary. | `READ_ONLY` | Reads `command_runs/latest.txt`. |

## n8n/Telegram Command Design

Initial read commands:

| Telegram command | n8n behavior | Runner/controller behavior |
| --- | --- | --- |
| `/status` | Read latest status file or call runner read command depending phase. | Show current Paper Daily Ops status. |
| `/refresh` | Trigger Windows wrapper for `daily_refresh` or read latest refresh result depending deployment phase. | Refresh context/status/eod dry-run files. |
| `/next` | Run/read controller next recommendation. | Map orchestrator status to registry command_key. |
| `/last` | Read command run latest txt. | Show last controller command result. |
| `/help` | Static supported command list. | No Python needed. |

Execution commands:

| Telegram command | Policy |
| --- | --- |
| `/run <command_key>` | Only `READ_ONLY` and `READ_ONLY_PREVIEW` command keys execute immediately. |
| `/request <command_key>` | Creates approval request for eligible write commands. |
| `/approve <approval_id>` | Executes stored approved argv if not expired and chat_id is allowed. |
| `/reject <approval_id>` | Marks approval rejected; no command execution. |

n8n should parse only the command name and opaque IDs/keys. It should pass the key to the Windows runner wrapper as an argument to the controller, not assemble the underlying stock-screener argv itself.

Example flow:

```text
Telegram /run execution_preview
-> n8n validates chat_id
-> Windows runner wrapper calls controller run execution_preview
-> controller builds argv from registry/context
-> subprocess(shell=False)
-> command_runs/latest.txt/json
-> n8n sends latest.txt
```

## Approval File Design

Approval requests freeze the command at request time. The approve step must not rebuild argv from current context.

Workspace layout:

```text
D:\n8n\workspace\stock_screener_ops\approvals\pending
D:\n8n\workspace\stock_screener_ops\approvals\approved
D:\n8n\workspace\stock_screener_ops\approvals\rejected
D:\n8n\workspace\stock_screener_ops\approvals\expired
D:\n8n\workspace\stock_screener_ops\command_runs
```

Approval JSON schema:

```json
{
  "approval_id": "20260620T073000Z_execution_commit_ab12cd34",
  "schema_version": "runbook_approval.v1",
  "status": "PENDING",
  "command_key": "execution_commit",
  "command_type": "LEDGER_WRITE",
  "requested_at": "2026-06-20T07:30:00+09:00",
  "expires_at": "2026-06-20T08:00:00+09:00",
  "requested_by_chat_id": "8025114939",
  "account_id": "paper_orch_smoke_202606",
  "data_date": "2026-06-12",
  "trade_date": "2026-06-15",
  "argv": [
    "python",
    "scripts\\import_notion_executions.py",
    "--date",
    "2026-06-15",
    "--account-id",
    "paper_orch_smoke_202606",
    "--commit",
    "--preview-json",
    "..."
  ],
  "preview_artifacts": {
    "execution_preview_json": "..."
  },
  "risk_summary": {
    "requires_manual_approval": true,
    "reason": "LEDGER_WRITE after preview"
  }
}
```

Approval transitions:

```text
PENDING -> APPROVED -> EXECUTED / FAILED
PENDING -> REJECTED
PENDING -> EXPIRED
```

Every transition should leave an immutable JSON copy and append a short audit line to a local approval history log.

## Command Run Result File Design

Every controller run should write Telegram-readable txt and machine-readable json.

Paths:

```text
command_runs\latest.txt
command_runs\latest.json
command_runs\YYYYMMDD_HHMMSS_<command_key>.txt
command_runs\YYYYMMDD_HHMMSS_<command_key>.json
command_runs\YYYYMMDD_HHMMSS_<command_key>.log
```

Result JSON fields:

```json
{
  "schema_version": "runbook_command_run.v1",
  "run_id": "20260620_073000_execution_preview",
  "command_key": "execution_preview",
  "command_type": "READ_ONLY_PREVIEW",
  "runner_result": "PASS",
  "process_exit_code": 0,
  "started_at": "...",
  "finished_at": "...",
  "account_id": "...",
  "data_date": "...",
  "trade_date": "...",
  "argv": ["python", "scripts\\import_notion_executions.py", "..."],
  "stdout_path": "...",
  "stderr_path": "...",
  "expected_outputs": {},
  "success_criteria": {},
  "recommended_operator_action": "REQUEST execution_commit after reviewing preview"
}
```

TXT summary format:

```text
Runbook Command
runner_result: PASS
command_key: execution_preview
command_type: READ_ONLY_PREVIEW
account_id: ...
data_date: ...
trade_date: ...
process_exit_code: 0
summary: ...
recommended_operator_action: ...
```

The controller should retain raw stdout/stderr in `.log` and include only the compact operator summary in `.txt`.

## Full Development Sequence

### 6-3A. Runbook Command Controller design

Goal: write this design.
Out of scope: implementation, n8n changes, Telegram changes.

### 6-3B. command registry read-only implementation

Goal: implement registry definitions, schema validation, and list/get operations.
Out of scope: executing commands.

### 6-3C. `/next` candidate generation

Goal: map `paper_daily_ops.py status` and `operator_summary.next_command` to a registry `command_key`.
Out of scope: executing write commands.

### 6-3D. READ_ONLY / PREVIEW command execution

Goal: implement `/run <command_key>` equivalent for `READ_ONLY` and `READ_ONLY_PREVIEW`.
Out of scope: approval/write execution.

### 6-3E. command run result file structure

Goal: persist `command_runs/latest.*`, timestamped json/txt/log, and Telegram-safe summaries.
Out of scope: approval controller.

### 6-3F. approval request / approve / reject file structure

Goal: implement approval JSON lifecycle, freeze argv, expiration, and audit history.
Out of scope: connecting high-risk write commands before previews are validated.

### 6-3G. approval-required write command connection

Goal: connect `LOCAL_ARTIFACT_WRITE`, `NOTION_WRITE`, `LEDGER_WRITE`, and `STATE_SNAPSHOT_WRITE` through request/approve.
Out of scope: broker/API/live order execution.

### 6-4A. Windows runner wrapper cleanup

Goal: provide a stable local wrapper for controller commands and log paths.
Out of scope: Task Scheduler registration.

### 6-4B. n8n Telegram `/next`, `/run` connection

Goal: add n8n routes for safe read/preview execution and latest result reads.
Out of scope: approval buttons for write commands.

### 6-4C. n8n Telegram `/request`, `/approve` connection

Goal: add approval request and decision UX around stored approval files.
Out of scope: expanding command types beyond the runbook registry.

### 6-5. daily_refresh scheduled push

Goal: schedule/push daily refresh status after market data is expected to be ready.
Out of scope: full runbook execution scheduling.

### 6-6. warning/error alert

Goal: alert on stale data, failed refresh, failed command runs, expired approvals, and unresolved blockers.
Out of scope: auto-remediation.

## Open Questions And Risks

- US market holiday calendar is still not implemented in `daily_refresh`.
- Some commit commands require preview JSON/report path discovery; registry entries need artifact resolution rules.
- Notion write commands need careful schema/auth failure handling and retry rules.
- Approval expiration duration should be chosen conservatively.
- `operator_summary.next_command` parsing must be treated as advisory only.
- Any future command that is not clearly classified must default to `UNKNOWN` or `BLOCKED`.

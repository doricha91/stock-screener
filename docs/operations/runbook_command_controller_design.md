# Runbook Command Controller Design

This document designs a safe controller for running selected Paper Daily Cycle runbook commands. The revised near-term target is an ngrok-free scheduled push model, with interactive Telegram control deferred to a later phase. It is a design document only. It does not implement Python controller code, n8n workflow changes, Telegram commands, Windows wrappers, Task Scheduler, Notion writes, or broker/order execution.

## Purpose

The current n8n/Telegram MVP can read latest status files when inbound webhook routing is available. For the next 3-6 month forward test, the safer first automation layer is local scheduled refresh plus outbound Telegram push. Interactive command execution and approval from Telegram should remain a later phase.

Phase 1 target shape:

```text
Windows Task Scheduler = scheduled trigger
Windows runner wrapper = local execution entrypoint
daily_refresh = safe status/preview refresh
Runbook Command Controller = optional local CLI for read-only/preview command execution
Telegram sendMessage = scheduled result push channel
Operator = manual Notion import/sync/commit/write approval executor
```

The controller is not a trading bot. It is a guarded operator tool for the documented Paper Daily Cycle. It must preserve the project rule that local files, CSV/JSON/Markdown artifacts, SQLite DBs, and existing scripts remain the source of truth.

## Deployment Phases

### Phase 1: Local Scheduled Push

- ngrok is not required.
- Windows Task Scheduler runs `daily_refresh` and, later, local controller read/preview commands.
- Telegram is a `sendMessage` push destination.
- No inbound Telegram commands are received.
- Notion import/sync/commit/write approval stays manual.

Phase 1 is the default target for the 3-6 month forward test because it has no public inbound endpoint requirement and keeps write-risk operations under direct operator control.

### Phase 2: Interactive Local Control

- Telegram commands can run controller actions.
- Webhook-based Telegram Trigger requires ngrok, Cloudflare Tunnel, VPS, or another public HTTPS endpoint when n8n runs on the local PC.
- Polling-based Telegram bot control can avoid ngrok, but it requires a separate local polling loop and operational supervision.
- Approval Controller connection begins in or after this phase.

Phase 2 target shape:

```text
Telegram = mobile control panel
n8n = message/button router
Windows runner wrapper = local Python execution entrypoint
Runbook Command Controller = allowlisted command_key executor
stock-screener scripts = actual paper ops commands
```

### Phase 3: Server/VPS Operation

- n8n/controller runs on a server or VPS.
- ngrok is not required.
- A public HTTPS domain, reverse proxy, and correct `WEBHOOK_URL` are required for webhook mode.
- Server security, backup, monitoring, and maintenance become part of the operating model.

## Ngrok Requirement Matrix

| Use case | Needs ngrok? | Reason |
| --- | --- | --- |
| `daily_refresh` local CLI | No | Local execution. |
| Windows Task Scheduler | No | No external inbound request. |
| Telegram `sendMessage` push | No | Outbound HTTPS request from local PC. |
| Task Scheduler -> localhost n8n webhook | No | Localhost call only. |
| Telegram Trigger receiving `/status` | Yes, if local webhook | Telegram must reach local n8n over public HTTPS. |
| Telegram `/run`, `/approve` real-time handling | Yes, if webhook-based | Public HTTPS endpoint is required. |
| Telegram polling bot | No | Local process calls `getUpdates` outbound. |
| VPS/cloud n8n | No ngrok | Server provides public HTTPS directly. |

ngrok is not required for Phase 1. ngrok or an equivalent public HTTPS tunnel is required only when local n8n must receive Telegram webhook events.

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

`daily_refresh` remains the safest scheduled automation boundary. It may be run once per operating day after expected market data availability. Its output is suitable for Telegram push. It must not execute Notion write, ledger commit, state commit, sync, or broker/order actions.

Phase 1 push outputs:

```text
context_latest.txt
status_latest.txt
eod_dryrun_latest.txt
daily_refresh_latest.txt
daily_refresh_latest.json
```

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

Phase 1 controller scope is intentionally narrow:

- registry list/get
- `command_key` classification
- next candidate display
- last/latest result lookup
- optional local CLI execution for `READ_ONLY` and `READ_ONLY_PREVIEW` only

Phase 1 does not include:

- Telegram `/run` connection
- Telegram `/request` connection
- Telegram `/approve` connection
- Notion write execution
- ledger commit execution
- `eod_commit` execution

### Approval Controller

The approval controller manages write-risk commands. It creates approval files with frozen argv/context, records approval decisions, expires stale requests, and only executes approved frozen argv.

It is responsible for:

- `/request <command_key>`
- `/approve <approval_id>`
- `/reject <approval_id>`
- approval status/history files
- expiration checks

Approval Controller is designed now but not activated in Phase 1. In Phase 1, write-risk commands remain manual operator actions. Approval files are required only when Phase 2 interactive control begins.

Phase 1 manual-only items:

- Notion import
- Notion sync
- execution commit
- review append
- eod commit
- git commit / push
- any write approval
- any broker/API/order action

### n8n/Telegram

n8n and Telegram are UI/transport only. In Phase 1, Telegram is a scheduled push destination, not an inbound command source.

They are responsible for:

- chat allowlist when inbound control exists
- command text/button routing in Phase 2
- showing latest output files
- collecting approval decisions in Phase 2
- invoking the Windows runner wrapper with allowlisted runner commands in Phase 2

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

## Phase 1 Scheduled Telegram Push

Phase 1 should use scheduled outbound push, not Telegram Trigger inbound commands.

Flow:

```text
Windows Task Scheduler
-> run_daily_refresh wrapper
-> python scripts\n8n_paper_ops_runner.py daily_refresh
-> daily_refresh_latest.txt/json
-> Telegram sendMessage
```

Push implementation options:

| Option | Shape | Advantages | Tradeoffs |
| --- | --- | --- | --- |
| A | Python wrapper calls Telegram `sendMessage` directly. | No n8n required, no ngrok required, simplest moving parts. | Telegram formatting/token handling moves into Python-side configuration. |
| B | Task Scheduler calls a localhost n8n webhook after refresh. | Can reuse existing n8n Telegram credential/workflow style. | n8n must be running; still no Telegram Trigger inbound command path. |

Initial recommendation:

- Use Option A for the minimum Phase 1 setup.
- Use Option B only if reusing existing n8n Telegram credential management is more important than minimizing components.
- Do not use Telegram Trigger/webhook in Phase 1.

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

## Phase 2 n8n/Telegram Command Design

Phase 1:

- No inbound Telegram commands.
- Scheduled push only.
- Optional local CLI only.

The following commands are retained as a Phase 2 interactive control design. They are not part of the Phase 1 scheduled push scope.

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

This design is reserved for Phase 2 or later. Approval Controller is not active in Phase 1. During Phase 1, write-risk commands stay manual operator actions and no approval file is required for scheduled push.

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

### 6-3A-R1. Revise controller design for ngrok-free scheduled push

Goal: revise this design so Phase 1 does not require ngrok and prioritizes scheduled Telegram push.
Out of scope: implementation, n8n changes, Telegram changes.

### 6-3B. command registry read-only implementation

Goal: implement registry definitions, schema validation, and list/get operations.
Out of scope: executing commands.

### 6-3C. controller local CLI list/get/next/last

Goal: expose local CLI commands for registry list/get, next candidate, and latest result lookup.
Out of scope: executing write commands.

### 6-3D. READ_ONLY / READ_ONLY_PREVIEW local CLI execution

Goal: execute allowlisted read-only and preview commands from local CLI with `shell=False`.
Out of scope: approval/write execution.

### 6-3E. command run result file structure

Goal: persist `command_runs/latest.*`, timestamped json/txt/log, and Telegram-safe summaries.
Out of scope: approval controller.

### 6-4A. Windows daily_refresh wrapper

Goal: provide a stable wrapper that runs `daily_refresh`, writes logs, and returns a clear exit status.
Out of scope: Task Scheduler registration and Telegram push.

### 6-4B. scheduled Telegram push implementation

Goal: send `daily_refresh_latest.txt` or a compact summary to Telegram via outbound `sendMessage`.
Out of scope: inbound Telegram commands.

### 6-4C. Task Scheduler documentation

Goal: document scheduling time, working directory, environment variables, logs, and failure handling.
Out of scope: registering the task automatically.

### 6-5. 3-6 month forward-test operating procedure

Goal: define daily operating routine, manual review/write steps, metrics, and weekly review cadence.
Out of scope: interactive Telegram control.

### 6-6. warning/error scheduled alert

Goal: push alerts for stale data, failed refresh, failed command runs, and missed operating days.
Out of scope: auto-remediation.

### 6-7. optional approval file lifecycle implementation

Goal: implement approval request/reject/expire storage without connecting write command execution.
Out of scope: Telegram approval UI and write command execution.

### 6-8. optional interactive Telegram control decision

Goal: choose whether interactive control should use webhook or polling after Phase 1 proves useful.
Out of scope: implementing both paths at once.

### 6-8A. webhook path: ngrok/Cloudflare Tunnel/VPS

Goal: implement interactive n8n/Telegram routing with a public HTTPS endpoint.
Out of scope: polling loop implementation.

### 6-8B. polling path: Telegram getUpdates

Goal: implement a local outbound polling loop that avoids public inbound webhook requirements.
Out of scope: public webhook setup.

### 6-9. approval-required write command connection

Goal: connect `LOCAL_ARTIFACT_WRITE`, `NOTION_WRITE`, `LEDGER_WRITE`, and `STATE_SNAPSHOT_WRITE` through request/approve after previews are reliable.
Out of scope: broker/API/live order execution.

## Forward Test Boundary

During the 3-6 month forward test:

- `daily_refresh` runs automatically once per operating day.
- Telegram push reports `PASS`/`WARNING`/`FAIL`, `data_date`, `trade_date`, stale flag, and `recommended_operator_action`.
- The operator manually reviews outputs.
- The operator manually performs Notion imports, syncs, commits, and any write approvals.
- No automatic write command is executed from Telegram.
- No live order or broker action is allowed.

Tracking metrics:

- `daily_refresh` success rate
- stale data frequency
- failed run frequency
- manual intervention count
- Notion sync/commit error count
- missed operating days
- time spent per daily cycle
- whether push-only was sufficient

## Open Questions And Risks

- US market holiday calendar is still not implemented in `daily_refresh`.
- Some commit commands require preview JSON/report path discovery; registry entries need artifact resolution rules.
- Notion write commands need careful schema/auth failure handling and retry rules.
- Approval expiration duration should be chosen conservatively.
- `operator_summary.next_command` parsing must be treated as advisory only.
- Any future command that is not clearly classified must default to `UNKNOWN` or `BLOCKED`.
- Phase 1 Telegram token handling must avoid committing tokens and should use environment variables or private local configuration.
- Option B for Phase 1 depends on local n8n availability even though it does not require ngrok.

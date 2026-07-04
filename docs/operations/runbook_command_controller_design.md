# Runbook Command Controller Design

This document designs a safe controller for running Paper Daily Cycle runbook commands. The revised Phase 1 target is ngrok-free scheduled runbook automation: local Windows scheduling executes guarded runbook stages and pushes stage results to Telegram with outbound `sendMessage`. Interactive Telegram control remains a later phase. This is a design document only. It does not implement Python controller code, n8n workflow changes, Telegram commands, Windows wrappers, Task Scheduler registration, Notion writes, or broker/order execution.

## Purpose

The current n8n/Telegram MVP can read latest status files when inbound webhook routing is available. For the next 3-6 month forward test, the intended first automation layer is local scheduled runbook execution plus outbound Telegram push. Telegram inbound commands are not required because the local Windows host initiates every scheduled run.

Phase 1 target shape:

```text
Windows Task Scheduler = scheduled trigger
Windows runner wrapper = local controller entrypoint
Runbook Command Controller = guarded Stage A/B/C executor for Step 0-18
daily_refresh = status/eod_dryrun freshness helper, not the stage executor
Notion = manual input surface for Step 6 and Step 12 gates
Telegram sendMessage = scheduled stage result push channel
Operator = manual input provider and exception resolver
```

The controller is not a trading bot. It is a guarded operator tool for the documented Paper Daily Cycle. It must preserve the project rule that local files, CSV/JSON/Markdown artifacts, SQLite DBs, and existing scripts remain the source of truth.

## Deployment Phases

### Phase 1: Ngrok-free Scheduled Runbook Automation

- ngrok is not required.
- Telegram inbound commands are not used.
- The controller runs on local Windows without ngrok, Cloudflare Tunnel, or VPS.
- Stage A starts at a user-configured scheduled time.
- Step 6 and Step 12 are the only manual input gates.
- Step 0-5, Step 7-11, and Step 13-18 run automatically when their guard conditions are satisfied.
- Each step and stage writes txt/json/log results.
- Telegram receives stage result, wait, blocked, and failure messages through outbound `sendMessage`.
- Broker/API/live order execution is out of scope.

Phase 1 is the default target for the 3-6 month forward test because it has no public inbound endpoint requirement while still automating the documented runbook around explicit manual Notion gates.

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

## Phase 1 Stage Model

Stage A starts at a user-configured scheduled time. Example: 21:00 KST is only an example, not a hardcoded policy.

Configuration candidates:

```text
RUNBOOK_STAGE_A_TIME_LOCAL=HH:MM
RUNBOOK_POLL_INTERVAL_MINUTES=60
RUNBOOK_TIMEZONE=Asia/Seoul
```

### Stage A: Pre-market / Daily Plan Stage

Trigger: user-configured scheduled time.

Steps:

- Step 0 Orchestrator status
- Step 1 Data prepare
- Step 2 Data freshness
- Step 3 Daily Plan
- Step 4 Daily Plan Notion export
- Step 5 Manual Execution template export

### Manual Gate 1: Step 6 Notion Execution Input

The controller polls for readiness. It must not run Stage B until every readiness condition is met.

Readiness conditions:

- Actual Price is filled.
- `Status=READY`.
- Account ID matches the frozen runbook context.
- Execution Date matches `trade_date`.

### Stage B: Execution Import / Review Template Stage

Trigger: Gate 1 readiness is met, either during a scheduled check or periodic polling.

Steps:

- Step 7 Execution preview
- Step 8 Execution commit
- Step 9 Execution status sync
- Step 10 Daily Review
- Step 11 Manual Review template export

### Manual Gate 2: Step 12 Notion Review Input

The controller polls for readiness. It must not run Stage C until every readiness condition is met.

Readiness conditions:

- Manual Answer is filled.
- Review Status is `reviewed` or `REVIEWED`.
- Import Status is `READY`.
- Account ID matches the frozen runbook context.
- Review Date matches `trade_date`.

### Stage C: Review Import / EOD Close Stage

Trigger: Gate 2 readiness is met, either during a scheduled check or periodic polling.

Steps:

- Step 13 Review preview
- Step 14 Review append
- Step 15 Review status sync
- Step 16 EOD dry-run
- Step 17 EOD commit
- Step 18 Final status

### Gate Polling And State

Gate polling:

- Default example: once per hour.
- The actual value must be configurable.
- If gate conditions are not met, the controller must not execute the next stage and should push `WAIT` to Telegram.
- If gate conditions are met, the controller should run the next stage once.
- Stage state must prevent duplicate execution after sleep, reboot, retry, or repeated polling.

State files:

```text
D:\n8n\workspace\stock_screener_ops\runbook_states\{runbook_day_id}.json
D:\n8n\workspace\stock_screener_ops\runbook_state.json
D:\n8n\workspace\stock_screener_ops\stage_runs\latest.txt
D:\n8n\workspace\stock_screener_ops\stage_runs\latest.json
D:\n8n\workspace\stock_screener_ops\stage_runs\YYYYMMDD_HHMMSS_<stage>.txt
D:\n8n\workspace\stock_screener_ops\stage_runs\YYYYMMDD_HHMMSS_<stage>.json
D:\n8n\workspace\stock_screener_ops\stage_runs\YYYYMMDD_HHMMSS_<stage>.log
```

`runbook_state.json` is a new controller-owned state contract introduced for Phase 1 scheduled runbook automation. It is not an existing schema used by earlier runner scripts. It must coexist with the existing n8n runner context files and must not replace them. It shares the `account_id`, `data_date`, and `trade_date` concepts, but controller state, stage status, artifacts, and duplicate-run records are owned by `runbook_state.json`.

Multi-account state layout:

- New stage runner code must use `runbook_states\{runbook_day_id}.json`, derived from `account_id`, `data_date`, and `trade_date`.
- The legacy/default `runbook_state.json` single-state path remains for compatibility and local schema utilities.
- Stage runner implementation must not rely on the legacy single-state path when `account_id`, `data_date`, and `trade_date` are known.

## Role Separation

### daily_refresh

`daily_refresh` is a status/eod_dryrun freshness helper, not the Phase 1 runbook stage executor.

Implemented role:

```text
resolve dates
-> update context
-> paper_daily_ops.py status --json --include-notion-read
-> paper.py eod --dry-run
-> latest status files
```

It should remain safe for status freshness checks. It does not run plan generation, Notion export/import, commit, sync, approval, or live broker activity.

`daily_refresh` can still be used by the controller as a freshness helper or fallback diagnostic. It is not the center of Phase 1. The center of Phase 1 is the Runbook Command Controller, which controls Stage A/B/C execution and gate polling.

`daily_refresh` helper outputs:

```text
context_latest.txt
status_latest.txt
eod_dryrun_latest.txt
daily_refresh_latest.txt
daily_refresh_latest.json
```

### Runbook Command Controller

The controller is the Phase 1 executor for `paper_daily_cycle_commands.md` steps. It maps an explicit `command_key` to a predefined argv template and executes it with `shell=False`.

It is responsible for:

- command registry lookup
- context substitution
- stage guard enforcement and Phase 2 approval gate enforcement
- preview/commit dependency checks
- command run result files
- post-run refresh policy
- Stage A/B/C state transitions
- Gate 1/2 polling and readiness checks
- duplicate-run prevention

It must not execute `operator_summary.next_command` as a raw string. The orchestrator can suggest the next step, but the controller must translate that suggestion to a known `command_key` before execution.

Phase 1 controller scope:

- registry list/get
- `command_key` classification
- next candidate display for operator visibility
- last/latest result lookup
- Stage A Step 0-5 execution
- Gate 1 readiness polling
- Stage B Step 7-11 execution
- Gate 2 readiness polling
- Stage C Step 13-18 execution
- Telegram scheduled push summaries

Phase 1 does not include:

- Telegram `/run` connection
- Telegram `/request` connection
- Telegram `/approve` connection
- inbound Telegram control
- broker/API/live order execution

### Approval Controller

The approval controller manages write-risk commands. It creates approval files with frozen argv/context, records approval decisions, expires stale requests, and only executes approved frozen argv.

It is responsible for:

- `/request <command_key>`
- `/approve <approval_id>`
- `/reject <approval_id>`
- approval status/history files
- expiration checks

Approval Controller is designed now but not activated in Phase 1. In Phase 1, controller-owned stage execution uses fixed stage policy, frozen context, idempotency keys, preview artifacts, commit reports, and fail-stop guards instead of interactive approval files. Approval files are required only when Phase 2 interactive control begins.

Phase 1 manual-only items:

- Step 6 Notion Execution input
- Step 12 Notion Review input
- exception resolution after `FAILED` or `BLOCKED`
- git commit / push
- any interactive Telegram approval
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
- Interactive write commands require a request/approve flow in Phase 2.
- Approval freezes `account_id`, `data_date`, `trade_date`, `command_key`, `argv`, and relevant preview/report paths.
- `approve` executes only stored approval argv, not a newly assembled command.
- No broker/API/order placement is in scope.

## Major Risks And Required Guards

Major risks:

- Duplicate execution creates duplicate Notion rows.
- Re-running commit commands duplicates local ledger/state effects.
- Context/date changes between preview and commit.
- Stage B or C runs before Step 6 or Step 12 input is ready.
- Steps continue after an earlier step failed.
- Stale data is used to create a plan.
- Notion sync failure leaves local source-of-truth and Notion status inconsistent.
- EOD commit is re-run or same-date replacement occurs unexpectedly.
- PC sleep, reboot, or update causes a scheduled run to be missed.

Required guards:

- Execute only allowlisted `command_key` values.
- Use `shell=False` execution only.
- Use stage-level idempotency keys.
- Freeze `account_id`, `data_date`, and `trade_date` for the runbook day.
- Freeze preview artifact paths for commit steps.
- Freeze commit report paths for sync steps.
- Stop the current stage immediately when a step fails.
- Keep Stage B/C `BLOCKED` until Gate 1/2 readiness is proven.
- Require EOD dry-run `PASS` before EOD commit.
- Prevent same-date commit re-execution unless an explicit manual recovery path is designed later.
- Do not automatically use replacement, force, or allow-warnings flags.

## Phase 1 Scheduled Telegram Push

Phase 1 should use scheduled outbound push, not Telegram Trigger inbound commands. Push messages report stage progress and required manual action; they do not accept commands.

Flow:

```text
Windows Task Scheduler
-> runbook controller wrapper
-> controller starts Stage A or polls Gate 1/2 based on runbook_state.json
-> stage_runs/latest.txt/json
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

Telegram Phase 1 role:

- scheduled run result push
- `WAIT` / `BLOCKED` / `FAILED` / `PASS` alerts
- next required manual action guidance

Telegram summary fields:

```text
stage
runner_result
account_id
data_date
trade_date
current_step
last_completed_step
blocked_reason
next_required_manual_action
next_poll_time
```

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

| command_type | Meaning | Interactive run | Interactive approval |
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

These gate rules apply to Phase 2 interactive Telegram control and ad hoc local command execution. Phase 1 scheduled runbook automation uses stage policy instead: the controller may execute eligible write-risk steps automatically only inside Stage A/B/C, with frozen context, idempotency keys, fixed artifact paths, and fail-stop guards.

## Phase 1 Step Automation Policy

| Step | Phase 1 policy |
| --- | --- |
| 0-5 | Run automatically in Stage A when schedule and guard conditions are satisfied. |
| 6 | Manual Gate 1; never auto-execute. |
| 7-11 | Run automatically after Gate 1 readiness is confirmed. |
| 12 | Manual Gate 2; never auto-execute. |
| 13-18 | Run automatically after Gate 2 readiness is confirmed. |

Each stage must stop immediately on failure and push `FAILED` or `BLOCKED` to Telegram. A waiting gate should push `WAIT`, not run the next stage.

## Runbook Step To command_key Mapping

This table maps Paper Daily Cycle steps 0-18 to controller command keys. It is an initial registry design, not an implementation.

| Step | command_key | argv template | Type | Interactive run | Interactive approval | Success criteria | Failure policy |
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
- Scheduled Stage A/B/C runbook automation.
- Scheduled push for stage results, waits, blocks, and failures.
- Optional local CLI inspection for registry/state/latest results.

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

This design is reserved for Phase 2 or later. Approval Controller is not active in Phase 1. During Phase 1, stage-owned write-risk commands are controlled by stage policy, frozen context, idempotency, artifact pinning, and fail-stop behavior; interactive approval files are not required.

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

### 6-3A-R2. Revise design for scheduled runbook automation

Goal: revise this design so Phase 1 is ngrok-free scheduled runbook automation with Step 6 and Step 12 as manual gates.
Out of scope: implementation, n8n changes, Telegram changes.

### 6-3B. command registry implementation for all Step 0-18 command_keys

Goal: implement registry definitions, schema validation, list/get operations, command typing, and Stage A/B/C eligibility for every runbook step.
Out of scope: executing commands.

### 6-3C-1. frozen runbook context and runbook_state schema

Goal: define the runbook day context and state schema before any stage execution.
Out of scope: executing stages.

Notes:

- Freeze `account_id`, `data_date`, and `trade_date` per runbook day.
- Context must not change inside the same `runbook_state` even if the wall-clock date changes during polling.
- `runbook_state.json` must include `stage`, `last_completed_step`, `current_status`, and `frozen_context`.
- If an existing state has a different requested context, return `BLOCKED` and do not overwrite it automatically.
- Reset/recovery for a different context is a separate follow-up design step.

### 6-3C-2. idempotency key and duplicate-run prevention

Goal: define idempotency keys, strict duplicate-run blocks, and recovery boundaries.
Out of scope: executing duplicate-sensitive commands.

Notes:

- Step 8, Step 14, and Step 17 duplicate prevention is the highest priority.
- `runbook_state.json` is a new controller-owned state contract, not an existing runner schema.
- `idempotency_records` are stored in `runbook_state.json`.
- If sleep, reboot, retry, or repeated polling tries to re-run the same idempotency key, return `BLOCKED`.
- Do not automatically use replacement, force, or allow-warnings flags before a manual recovery path is designed.
- Reset/recovery is a later design step.

### 6-3C-3. multi-account layout, transitions, and idempotency lifecycle

Goal: connect controller-owned state to future stage execution without executing any runbook commands.
Out of scope: Stage A/B/C execution, gate polling, subprocess execution, Notion read/write, and Telegram push.

Notes:

- State path helpers must support `runbook_states\{runbook_day_id}.json` for multi-account operation.
- `get_state_path(workspace)` remains a legacy/default single-state path and must not be removed.
- Stage transition helpers should be the only way future stage runners set `RUNNING`, `WAIT`, `PASS`, `BLOCKED`, or `FAILED`.
- Step completion should update `last_completed_step` and merge artifact updates without changing frozen context.
- Artifact refs must be normalized before they become idempotency key material: workspace-relative when possible, `/` separators, no leading `./`, and workspace-outside absolute paths rejected.
- Duplicate-sensitive commands should reserve an idempotency record before execution, transition through `RESERVED -> RUNNING -> PASS/FAILED`, and block repeated keys.
- `RESERVED`, `RUNNING`, `PASS`, `FAILED`, and `UNKNOWN_AFTER_CRASH` duplicate keys must not auto-run again.
- Recovery/reset is a later design step.
- This step still does not execute Step 8, Step 14, Step 17, or any other command.

### 6-3C-4. step result file schema and stage summary contract

Goal: define command result and stage summary schemas before Stage A execution.
Out of scope: Stage A/B/C execution, gate polling, subprocess execution, Notion read/write, and Telegram push.

Notes:

- Command result files must be stored under `command_runs/{runbook_day_id}/`.
- Stage summary files must be stored under `stage_runs/{runbook_day_id}/`.
- Command result JSON wraps each step result with `runbook_day_id`, `frozen_context`, `stage_id`, `step_id`, `command_key`, `runner_result`, process metadata, artifact refs, a Telegram-friendly summary, and raw payload.
- Stage summary JSON aggregates command results and decides `runner_result` by priority: `FAILED > BLOCKED > WAIT > WARNING > PASS`.
- `SKIPPED` is counted but does not make a stage fail.
- TXT summaries must be human-readable and suitable as the base for scheduled Telegram push.
- Log file paths are part of the contract, but log files may remain optional until subprocess execution is implemented.
- This step does not execute registry commands.

### 6-3D. Stage A Step 0-5 execution

Goal: execute Step 0-5 with fail-stop behavior, stage result files, and Telegram-ready summaries.
Out of scope: Gate 1 polling and Stage B.

6-3D must use the transition helpers and per-`runbook_day_id` state path introduced in 6-3C-3.
6-3D must write command results and stage summaries through the 6-3C-4 result helpers.

Implementation notes:

- Stage A runner uses `runbook_states/{runbook_day_id}.json`; it must not use a shared single-state file for active execution.
- Stage A runner starts with `start_stage(state, "A")`, records successful steps through `complete_step()`, and finishes with `complete_stage()` only when every Step 0-5 command passes.
- Stage A command execution is restricted to registry entries where `stage_id="A"`, `step_id` is 0-5, `phase1_auto_execute=true`, `manual_gate=false`, and `argv_template` is present.
- Registry argv templates are rendered with frozen `account_id`, `data_date`, and `trade_date`, then executed with `shell=False`.
- If the first argv item is a project Python script under `scripts\*.py`, the runner invokes it through the current Python interpreter.
- Stage A is fail-stop: the first `FAILED` or `BLOCKED` command stops later steps, records the stage state, and writes a stage summary.
- Each command writes JSON/TXT result files under `command_runs/{runbook_day_id}/`; command logs record argv, cwd, exit code, stdout, stderr, and duration.
- Stage summary JSON/TXT and `latest_A` files are written under `stage_runs/{runbook_day_id}/`.
- Dry-run mode is allowed for smoke tests; it writes normal result files but does not execute subprocesses.
- Gate 1 polling, Stage B/C execution, Telegram push, Windows scheduling, and n8n changes remain out of scope.

### 6-3D-1. Stage A full real smoke for paper accounts

Goal: allow full Stage A Step 0-5 real smoke for paper/test accounts.
Out of scope: Gate 1 polling, Stage B/C execution, Telegram push, Windows scheduling, n8n changes, and broker/live order execution.

Policy:

- Dry-run Stage A may run without extra confirmation.
- Non-dry-run Stage A requires `--confirm-paper-test`.
- When `--confirm-paper-test` is used, `account_id` must contain `paper` or `test` case-insensitively.
- Missing confirmation returns `BLOCKED` with reason `paper_test_confirmation_required`.
- Non-paper account IDs return `BLOCKED` with reason `paper_account_required`.
- The paper/test account guard is intentionally simple for smoke testing and should become configurable before any live-account transition.
- Non-dry-run Stage A can execute Step 4/5 Notion writes and must only be used against paper/test Notion data.

Paper full smoke command:

```cmd
python scripts\runbook_stage_runner.py stage-a ^
  --workspace D:\n8n\workspace\stock_screener_ops ^
  --account-id paper_smoke ^
  --data-date YYYY-MM-DD ^
  --trade-date YYYY-MM-DD ^
  --confirm-paper-test
```

After the run, inspect `stage_runs/{runbook_day_id}/latest_A.json`, the command result files, command logs, and Notion export results.

### 6-3D-2. State last_error clear and stdout JSON payload extraction

Goal: clear stale active errors after a successful rerun and preserve mixed stdout JSON payloads for later gate/stage logic.
Out of scope: Gate 1 polling, Stage B/C execution, Telegram push, n8n changes, Task Scheduler, Notion write behavior changes, and domain success criteria.

Policy:

- `complete_stage(state, stage_id)` clears `last_error` when the stage completes with `PASS`.
- Historical failure events remain in `history`; only the active current error is cleared.
- Stage A command result `raw_payload` should preserve JSON details even when stdout contains human-readable text before the final JSON object or array.
- Stdout JSON extraction first accepts whole-stdout JSON, then falls back to the last parseable JSON object or array at the end of stdout.
- Arrays are wrapped as `{"json": [...]}`.
- Malformed or absent JSON still produces `{}`.
- Stderr is never parsed as JSON payload.

### 6-3E. Gate 1 readiness check

Before 6-3E, Stage A full real smoke should be run only for paper/test accounts with `--confirm-paper-test`.
Before Gate 1 readiness check, Stage A `PASS` state must not carry stale `last_error` from earlier failed attempts.

Goal: poll Notion execution input readiness for Actual Price, `Status=READY`, Account ID, and Execution Date.
Out of scope: Stage B execution.

Implementation notes:

- Gate 1 reads the per-`runbook_day_id` state through `runbook_states/{runbook_day_id}.json`.
- Gate 1 is `BLOCKED` if frozen context mismatches, Stage A is not `PASS`, or Stage A has an active `last_error`.
- A previous `GATE1` WAIT state may be polled again; it should not permanently block readiness checks.
- Gate 1 queries Notion Manual Executions read-only using Account ID, Execution Date, and `linked_daily_plan_key=daily_plan:{account_id}:{trade_date}`.
- Gate 1 uses the same env-compatible Notion access path as Stage A exports: load `.env`, call `load_notion_settings(allow_missing=True)`, use `NOTION_MANUAL_EXECUTIONS_DATA_SOURCE_ID` as the data source override, and load the `manual_executions` property mapping. See `docs/operations/notion_access_path_comparison.md`.
- Each row is ready only when `Status=READY`, `Import Status=NOT_IMPORTED`, `Actual Price` is filled, account/date/linked plan match, and `failed_count=0`.
- Any unready row returns `WAIT`, records missing reasons per row, and updates state through `wait_gate(state, "GATE1", ...)`.
- All rows ready returns `PASS` and marks `GATE1` complete through the state transition helper.
- Notion query or settings failures return `BLOCKED`.
- Gate outputs are written under `gate_runs/{runbook_day_id}/` as timestamped JSON/TXT plus `latest_GATE1.json` and `latest_GATE1.txt`.
- This step does not execute Stage B, import executions, update Notion, change Status, fill Actual Price, send Telegram, or modify n8n.

### 6-3F-0. Execution Reconciliation Architecture Review

Goal: review system-wide Daily Plan vs Actual Execution flow before Stage B implementation.
Out of scope: production code changes, Stage B execution, Notion write/read changes, ledger/account state changes, Telegram, n8n, and scheduling.

Notes:

- Execution Reconciliation belongs in Stage B Preview, not Gate 1.
- Gate 1 remains responsible for input readiness only.
- Stage B Preview should compare the frozen Daily Plan sidecar with Notion Manual Execution rows and produce a pinned reconciliation artifact before any ledger/account state commit.
- Stage B Commit should consume only the approved pinned artifact and rely on idempotency plus existing ledger duplicate checks.
- Review details: `docs/operations/execution_reconciliation_architecture_review.md`.

### 6-3F-1. Stage B execution preview and artifact pinning

Goal: create a read-only Execution Reconciliation Preview artifact before any commit.
Out of scope: Step 8 commit, ledger/account state writes, Notion status sync, Telegram, n8n, and later Stage B steps.

Notes:

- `core/execution_reconciliation.py` owns pure plan-vs-actual comparison logic and performs no file, Notion, ledger, or account state I/O.
- `scripts/runbook_execution_reconciliation_preview.py` reads the frozen Daily Plan sidecar and Notion Manual Execution rows, then writes preview artifacts.
- Preview artifacts are written under both the paper account reconciliation directory and `reconciliation_runs/{runbook_day_id}/`.
- Matching uses `manual_execution:{account_id}:{trade_date}:{symbol}:{side}:{sequence}`.
- Row results use `MATCHED`, `DEVIATED`, `MISSING`, and `EXTRA`; severity uses `INFO`, `WARNING`, `NEEDS_REVIEW`, and `BLOCKED`.
- Overall runner result is aggregated by priority: `BLOCKED > NEEDS_REVIEW > WARNING > PASS`.
- This step does not run Stage B commit, update Notion, append the ledger, write snapshots, send Telegram, or modify n8n.
- Step 8 must later consume a pinned reconciliation/preview artifact; it must not reconstruct judgment from Telegram text.

### 6-3F-2. Stage B commit / sync / review template execution

Goal: run Step 8-11 using pinned artifacts and fail-stop behavior.
Out of scope: Gate 2 polling and Stage C.

Notes:

- Step 8 must use only the `preview_json` pinned by Step 7 and a pinned `execution_reconciliation_preview_json`.
- The reconciliation preview must have `schema_version=execution_reconciliation_preview.v1`, matching account/date context, `runner_result=PASS`, zero warning/needs_review/blocked/missing/extra counts, and matching planned/actual/matched counts.
- Phase 1 does not auto-commit `WARNING`, `NEEDS_REVIEW`, or `BLOCKED` reconciliation previews.
- Step 8 must not re-query Notion or recalculate plan-vs-actual judgment; it only validates the pinned reconciliation artifact before commit.
- Step 9 must use only the `commit_report` produced by Step 8.
- If Step 8 succeeds and Step 9 fails, do not attempt automatic local source-of-truth rollback.
- Telegram summary must say whether retry should use the same `commit_report`.

### 6-3G. Gate 2 readiness check

Goal: poll Notion review input readiness for Manual Answer, Review Status, Import Status, Account ID, and Review Date.
Out of scope: Stage C execution.

### 6-3H-1. Stage C review preview and artifact pinning

Goal: run Step 13 and freeze the review preview artifact before append.
Out of scope: Step 14 append and later Stage C steps.

Notes:

- Pin the `review_preview_json` path from Step 13 `review_preview`.
- Do not advance to Step 14 when `fail_count` is not 0.
- Manual Answer, Review Status, and Import Status mismatch should be treated as Gate 2 readiness problems.

### 6-3H-2. Stage C append / sync / eod dry-run / eod commit / final status

Goal: run Step 14-18 using pinned artifacts, EOD dry-run gating, and fail-stop behavior.
Out of scope: inbound Telegram control.

Notes:

- Step 14 must use only the `review_preview_json` pinned by Step 13.
- Step 15 must use only the `review_commit_report` produced by Step 14.
- Step 17 `eod_commit` must not run without Step 16 `eod_dryrun` PASS.
- Step 17 same-date commit re-execution must return `BLOCKED`.
- If Step 18 `final_status` returns `WARNING`, the operator action must be explicit.

### 6-4A. Windows wrapper for runbook controller

Goal: provide a stable wrapper for stage start, polling, logs, environment variables, and exit codes.
Out of scope: registering the task automatically.

### 6-4B. configurable schedule and polling documentation

Goal: document `RUNBOOK_STAGE_A_TIME_LOCAL`, `RUNBOOK_POLL_INTERVAL_MINUTES`, timezone, missed-run behavior, and recovery checks.
Out of scope: implementing Task Scheduler registration.

### 6-4C. Telegram scheduled push

Goal: push stage `PASS`, `WAIT`, `BLOCKED`, and `FAILED` summaries using outbound `sendMessage`.
Out of scope: inbound Telegram commands.

### 6-5. failure/block/wait alert handling

Goal: standardize alert text, retry recommendations, blocked reasons, next manual action, and next poll time.
Out of scope: auto-remediation.

### 6-6. forward-test operating procedure

Goal: define 3-6 month operating cadence, monitoring metrics, manual exception handling, and review checkpoints.
Out of scope: interactive Telegram control.

### 6-7. optional inbound Telegram control decision

Goal: decide whether Phase 2 should use webhook or polling after scheduled automation is proven.
Out of scope: implementing inbound control.

Phase 2 options:

- Webhook path: ngrok, Cloudflare Tunnel, or VPS.
- Polling path: Telegram `getUpdates`.
- Interactive commands: `/status`, `/run`, `/request`, `/approve`, `/reject`.

## Forward Test Boundary

During the 3-6 month forward test:

- Stage A starts automatically once per operating day at the user-configured scheduled time.
- Gate 1 and Gate 2 polling runs at the configured interval.
- Stage B runs once after Step 6 Notion execution input is ready.
- Stage C runs once after Step 12 Notion review input is ready.
- Telegram push reports `PASS` / `WARNING` / `WAIT` / `BLOCKED` / `FAILED`, `stage`, `account_id`, `data_date`, `trade_date`, `current_step`, `last_completed_step`, `blocked_reason`, `next_required_manual_action`, and `next_poll_time`.
- The operator manually provides Step 6 and Step 12 Notion inputs.
- The operator manually resolves blocked or failed states.
- No automatic write command is executed from Telegram inbound commands.
- No live order or broker action is allowed.

Tracking metrics:

- Stage A/B/C success rate
- stale data frequency
- failed step frequency
- blocked/wait frequency
- manual intervention count
- Notion sync/commit error count
- duplicate-prevention block count
- missed operating days
- time spent per daily cycle
- whether scheduled automation without inbound Telegram control was sufficient

## Open Questions And Risks

- US market holiday calendar is still not implemented in `daily_refresh`.
- Some commit commands require preview JSON/report path discovery; registry entries need artifact resolution rules.
- Notion write commands need careful schema/auth failure handling and retry rules.
- Approval expiration duration should be chosen conservatively.
- `operator_summary.next_command` parsing must be treated as advisory only.
- Any future command that is not clearly classified must default to `UNKNOWN` or `BLOCKED`.
- Phase 1 Telegram token handling must avoid committing tokens and should use environment variables or private local configuration.
- Option B for Phase 1 depends on local n8n availability even though it does not require ngrok.

# Execution Reconciliation Architecture Review

## 1. Scope

This is a design review for `Execution Reconciliation`: comparing the generated
Daily Plan with the actual Manual Execution rows entered in Notion before Stage B
commits anything to paper ledger/account state.

Out of scope:

- implementing reconciliation logic
- changing Stage B execution code
- changing Notion read/write behavior
- changing ledger, portfolio, or account state writes
- adding Telegram, n8n, Task Scheduler, broker, or live-order behavior

Core question:

```text
When actual executions entered in Notion differ from the Daily Plan, which layer
should decide PASS / WAIT / WARNING / NEEDS_REVIEW / BLOCKED?
```

## 2. Current System Flow

Current Phase 1 runbook flow:

```text
Stage A
-> Step 3 daily_plan creates local Daily Plan markdown/json artifacts
-> Step 4 export_daily_plan_notion upserts the Daily Plan row
-> Step 5 export_execution_template upserts Manual Execution DRAFT rows

Gate 1
-> reads Manual Execution rows from Notion
-> requires Actual Price, Status=READY, Import Status=NOT_IMPORTED
-> returns WAIT / PASS / BLOCKED

Stage B planned
-> Step 7 execution_preview reads READY Manual Execution rows
-> Step 8 execution_commit writes ledger/state from pinned preview JSON
-> Step 9 sync_execution_status updates Notion from commit report
-> Step 10 daily_review builds local review artifacts
-> Step 11 export_review_template writes review template rows
```

## 3. Files Reviewed

Daily Plan generation:

- `scripts/paper.py`
- `scripts/run_paper_daily_plan.py`
- `core/daily_plan_generator.py`
- `core/paper_daily_plan_candidates.py`
- `tests/test_daily_plan_json_sidecar.py`

Notion export:

- `scripts/export_paper_to_notion.py`
- `core/notion_exporters.py`
- `core/notion_account_keys.py`
- `config/notion_property_mapping.example.json`

Gate 1:

- `scripts/runbook_gate_checker.py`
- `tests/test_runbook_gate_checker.py`

Stage B preview/commit/sync:

- `scripts/runbook_command_registry.py`
- `scripts/import_notion_executions.py`
- `core/notion_manual_execution_importer.py`
- `core/paper_manual_execution_commit.py`
- `scripts/sync_notion_execution_status.py`
- `core/notion_manual_execution_status_sync.py`

Ledger / portfolio / account state:

- `core/paper_execution_log.py`
- `core/paper_trade_preview.py`
- `core/paper_account_state.py`
- `core/paper_account_snapshot.py`
- `core/paper_position_snapshot.py`
- `core/paper_current_state_storage.py`

Reporting:

- `core/daily_review_summary_exporter.py`
- `scripts/export_paper_to_notion.py`
- `scripts/runbook_result.py`

## 4. Daily Plan Schema

Daily Plan JSON sidecars are written by `core/daily_plan_generator.py` with:

```text
schema_version = paper_daily_plan.v1
account_id
data_date
trade_date
plan_date
run_mode
official_run
generated_at
items[]
fingerprints
```

The execution candidate contract is in `core/paper_daily_plan_candidates.py`:

```text
items[] row is an execution candidate when:
- row is an object
- action in {BUY, SELL}
- symbol is present
- quantity is positive
```

Observed execution item fields:

```text
symbol
action
quantity
price
warning
reason
note
```

`core/daily_plan_generator.py` uses `type`/`shares` internally, but
`normalize_daily_plan_item()` normalizes the sidecar into `action`/`quantity`.
The sidecar is the correct source for reconciliation because it is the stable
artifact handed to Notion export.

## 5. Manual Execution Schema

`core/notion_exporters.py` converts Daily Plan execution candidates into Notion
Manual Execution rows.

Template fields:

```text
external_key
account_id
execution_date
plan_date
symbol
side
quantity
actual_price = null
commission = 0
currency = USD
broker = PAPER
status = DRAFT
import_status = initial_import_status
linked_daily_plan_key = daily_plan:{account_id}:{execution_date}
plan_price
note
```

External key policy:

```text
manual_execution:{account_id}:{execution_date}:{symbol}:{side}:{sequence}
```

The sequence is assigned per `(symbol, side)` among Daily Plan execution
candidates. This is currently the strongest row-level bridge between plan row
and manual execution row.

## 6. Import / Ledger / Portfolio Flow

Stage B Step 7 preview is handled by `scripts/import_notion_executions.py` and
`core/notion_manual_execution_importer.py`.

Current preview behavior:

- queries Notion `manual_executions` for `execution_date`, `Status=READY`, and
  `account_id`
- normalizes page rows into `ManualExecutionCandidate`
- assigns canonical keys using account/date/symbol/side/sequence
- validates basic shape, actual price, cash sufficiency, sell quantity vs current holding
- checks duplicate prospective trade IDs against `paper_execution_log.csv`
- writes `manual_execution_import_preview_YYYYMMDD.json/md`
- returns `commit_allowed` as `true`, `true_with_warnings`, or `false`

Stage B Step 8 commit is handled by `core/paper_manual_execution_commit.py`.

Current commit behavior:

- requires a preview JSON path
- blocks mismatched preview date/account
- blocks `fail_count > 0` or `commit_allowed=false`
- blocks warnings unless `--allow-warnings` is supplied
- converts candidates into `PaperTradePreview`
- pre-checks `append_paper_execution_log(commit=False)`
- blocks duplicate paper trade warnings
- appends to execution log, rebuilds current state, writes account and position snapshots
- writes `manual_execution_import_commit_YYYYMMDD.json/md`
- rolls back backed-up files if commit fails

Stage B Step 9 sync uses `core/notion_manual_execution_status_sync.py` with the
commit report, not a fresh command reconstruction.

## 7. Existing Safety Controls

Already present:

- Stage A writes Notion rows through deterministic external keys and upsert.
- Gate 1 only checks input completion; it does not import or write ledger state.
- Stage B preview and commit are separate commands.
- Commit requires a preview JSON.
- Commit blocks preview date/account mismatch.
- Commit blocks preview FAIL rows.
- Commit blocks duplicate paper trade IDs.
- Commit backs up execution log/account snapshot/position snapshot/current state
  and rolls back on failure.
- Runbook state has per-runbook-day state and idempotency records for strict
  once commands.
- Registry marks `execution_commit` as strict once and preview-artifact dependent.

## 8. Gaps and Risks

Main gap:

```text
No explicit Daily Plan vs Actual Execution reconciliation artifact exists yet.
```

Current Stage B preview validates whether Notion rows can be committed to the
paper account. It does not explicitly decide whether the actual rows still match
the Daily Plan intent.

Risks:

- quantity differs from plan and is silently treated as the real execution
- price deviates materially from plan but only affects cash projection
- plan candidate is missing because the operator skipped a row
- extra READY execution exists that was not generated from the plan
- `Status=READY` expresses input completion but not plan agreement
- external key sequence drift can occur if duplicated symbol/side rows are
  reordered or manually added
- commit can correctly protect ledger consistency while still committing a
  semantically unintended execution
- Stage C can report committed trades, but it is late for preventing bad import

## 9. Reconciliation Responsibility Boundary

Recommended boundary:

Gate 1:

- owns input readiness only
- verifies required fields are present and row belongs to frozen context
- returns `WAIT` until operator has filled Manual Execution rows
- must not perform plan-vs-actual semantic judgment beyond row identity/context

Stage B Preview:

- owns Execution Reconciliation
- reads the frozen Daily Plan sidecar and Notion Manual Execution rows
- produces a reconciliation preview artifact
- does not write ledger, account state, or Notion status
- blocks Stage B Commit when reconciliation severity is `BLOCKED`

Stage B Commit:

- owns source-of-truth mutation
- consumes only a pinned preview/reconciliation artifact
- must not re-query and reinterpret Notion rows independently
- uses idempotency and existing duplicate trade controls

Stage C Report:

- reports plan-vs-actual deltas and operator reasons
- should not discover first-time blockers that should have stopped Stage B

Telegram:

- summarizes reconciliation status and next action
- owns no business judgment

## 10. Recommended Reconciliation Status Model

Recommended `reconciliation_status` values:

```text
MATCHED
PRICE_DEVIATION
QUANTITY_DEVIATION
MISSING_EXECUTION
SKIPPED_WITH_REASON
SKIPPED_WITHOUT_REASON
EXTRA_EXECUTION
FIELD_MISMATCH
DUPLICATE_EXECUTION
IMPORT_STATUS_CONFLICT
```

Recommended row-level fields:

```text
plan_external_key
manual_execution_external_key
linked_daily_plan_key
account_id
trade_date
symbol
side
planned_quantity
actual_quantity
planned_price
actual_price
quantity_delta
price_delta_pct
status
import_status
operator_reason
reconciliation_status
severity
message
```

## 11. Recommended Severity Model

Recommended severities:

```text
INFO
WARNING
NEEDS_REVIEW
BLOCKED
```

Recommended runner results:

```text
PASS
WARNING
NEEDS_REVIEW
BLOCKED
FAILED
```

Mapping:

| Condition | Severity | Runner result | Default action |
| --- | --- | --- | --- |
| all rows match | INFO | PASS | allow Stage B commit |
| price deviation within policy | WARNING | WARNING | allow preview, include summary |
| quantity differs with explicit reason | NEEDS_REVIEW | NEEDS_REVIEW | require operator review before commit |
| quantity differs without reason | BLOCKED | BLOCKED | do not commit |
| missing planned execution without skip reason | BLOCKED | BLOCKED | do not commit |
| skipped planned execution with reason | NEEDS_REVIEW | NEEDS_REVIEW | review before commit |
| extra execution not linked to plan | BLOCKED | BLOCKED | do not commit in Phase 1 |
| import_status not `NOT_IMPORTED` before commit | BLOCKED | BLOCKED | do not commit |
| duplicate external/canonical key | BLOCKED | BLOCKED | do not commit |

## 12. Recommended Stage Placement

Place Execution Reconciliation in Stage B Preview, before ledger commit:

```text
Step 7 execution_preview
-> read Daily Plan JSON sidecar
-> read Notion Manual Executions
-> run plan-vs-actual reconciliation
-> write execution_reconciliation_preview_YYYYMMDD.json/md
-> write existing manual_execution_import_preview_YYYYMMDD.json/md only if reconciliation allows it

Step 8 execution_commit
-> consume pinned reconciliation/preview artifact only
-> reserve idempotency key
-> commit
-> mark idempotency PASS/FAILED
```

This avoids expanding Gate 1 beyond readiness while preventing commit of
semantically unsafe actual execution rows.

## 13. Impact on Gate 1 / Stage B / Gate 2 / Stage C / Telegram

Gate 1:

- remains a readiness gate
- should not decide quantity/price deviations
- may include row counts but should not approve import semantics

Stage B Preview:

- becomes the primary reconciliation decision layer
- should return `PASS`, `WARNING`, `NEEDS_REVIEW`, or `BLOCKED`
- should pin Daily Plan sidecar path and Manual Execution page IDs/external keys

Stage B Commit:

- should accept only a pinned preview artifact whose reconciliation outcome is
  commit-eligible
- should not allow `--allow-warnings` automatically from scheduled automation
  until a recovery/approval policy is defined

Gate 2:

- should consume Stage B commit/report outputs
- should not reinterpret execution rows

Stage C:

- should surface plan-vs-actual deltas in daily review summaries
- should distinguish "execution accepted with review reason" from "unexpected
  mismatch"

Telegram:

- should report:
  - reconciliation runner result
  - matched / warning / needs_review / blocked counts
  - missing/extra execution counts
  - next required operator action
- should not contain threshold or matching logic

## 14. Open Questions

1. Quantity deviation policy:
   Should partial fills with a reason be `NEEDS_REVIEW` or `WARNING`?

2. Price deviation threshold:
   Phase 1 should probably record price deltas and use a simple percent threshold
   only for warnings. ATR-based thresholds can wait.

3. Skip reason source:
   The current Manual Execution mapping has `note`, but no explicit
   `skip_reason` or `override_reason`. Should `note` be sufficient for Phase 1?

4. Skipped status:
   Should Notion support `Status=SKIPPED` for a plan row, or should skipped rows
   remain `READY` with zero quantity forbidden? Recommended: add a clear status
   later, but do not change schema in this review step.

5. Extra execution override:
   Phase 1 should block extras by default. A future manual override should use an
   explicit reason field and a separate approval path.

6. Sequence stability:
   Since canonical keys use sequence per `(symbol, side)`, duplicated same-symbol
   same-side plan rows require careful matching. Reconciliation should preserve
   plan order and external key identity.

## 15. Proposed Next Implementation Steps

### 6-3F-1 Stage B Execution Reconciliation Preview

- Read frozen Daily Plan sidecar for `account_id` and `trade_date`.
- Read Notion Manual Execution rows for the same account/date/linked plan.
- Match by `manual_execution:{account_id}:{trade_date}:{symbol}:{side}:{sequence}`.
- Produce `execution_reconciliation_preview_YYYYMMDD.json/md`.
- Also write runbook workspace copies under
  `reconciliation_runs/{runbook_day_id}/` with `latest_execution_reconciliation_preview.json/md`.
- Use the Phase 1 simplified status model:
  `MATCHED`, `DEVIATED`, `MISSING`, and `EXTRA`.
- Use row severities `INFO`, `WARNING`, `NEEDS_REVIEW`, and `BLOCKED`.
- Aggregate runner result by `BLOCKED > NEEDS_REVIEW > WARNING > PASS`.
- Do not write ledger, account state, or Notion status.
- Return `PASS`, `WARNING`, `NEEDS_REVIEW`, or `BLOCKED`.

### 6-3F-2 Stage B Commit Safety

- Commit only from a pinned reconciliation/preview artifact.
- Require a pinned `execution_reconciliation_preview_json` whose
  `runner_result` is `PASS`.
- Block `WARNING`, `NEEDS_REVIEW`, and `BLOCKED` reconciliation previews in
  Phase 1; no automatic warning approval exists.
- Validate schema, account/date context, warning/needs_review/blocked/missing/
  extra counts, and planned/actual/matched counts before ledger/account writes.
- Do not re-query Notion or recalculate reconciliation during commit.
- Use runbook idempotency records for Step 8.
- Keep existing ledger duplicate checks.
- Do not auto-use `--allow-warnings` in scheduled automation until policy exists.

### 6-3G Telegram Notification Framework

- Summarize stage/gate/reconciliation artifacts.
- Include counts and next required operator action.
- Keep all judgment in controller artifacts, not Telegram workflow text.

### 6-3F-3 Stage B Runner Integration

- Run Step 7 import preview, Step 7R reconciliation preview, Step 8 commit, and
  Step 9 Notion status sync in a fail-stop Stage B sequence.
- Pin every successful artifact into `runbook_state.json`.
- Step 8 consumes only pinned `execution_preview_json` and
  `execution_reconciliation_preview_json`.
- Step 9 consumes only pinned `execution_commit_report_json`.
- Reports produced under repo `outputs/` are copied into
  `workspace/artifacts/{runbook_day_id}/stage_b/` before pinning, so later
  Stage B commands consume controller-owned workspace copies.
- A stale Stage B `RUNNING` state may be recovered only when there is no Step 8
  PASS idempotency record and no pinned commit report. Already committed dates
  remain blocked from automatic rerun.
- Dry-run renders all commands and simulates pinning without ledger/account state
  writes or Notion updates.

### 6-3F-4 Stage B Completion Verification

- Read the pinned `execution_commit_report_json` and
  `execution_status_sync_report`.
- Verify commit status, committed row count, snapshot write flags, sync success,
  updated count, failed count, and committed trade id set consistency.
- Write `stage_b_verification.v1` JSON/MD artifacts under
  `verification_runs/{runbook_day_id}/`.
- Pin `stage_b_verification_json` and `stage_b_verification_md` into
  controller-owned runbook state when the matching state exists.
- Treat this as automatic completion verification, not Gate 2. Gate 2 remains
  the future Manual Review input readiness check.

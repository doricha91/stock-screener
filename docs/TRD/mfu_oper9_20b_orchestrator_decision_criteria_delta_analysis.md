# MFU-OPER9-20B Orchestrator Decision Criteria Delta Analysis

## 1. Summary

This document compares the current Daily Ops Orchestrator decision criteria documented in OPER9-20A with the criteria added or changed during OPER9. It is a delta analysis only. No code or test behavior is changed here.

The main conclusion is that OPER9-17 solved a real no-action day loop, but its implementation introduced a higher-priority `no_execution_candidates` path that can override the normal Manual Execution path. The helper added in OPER9-17 counts only a legacy-looking shape:

- `items[].action == "EXECUTE"`
- `items[].status == "PENDING"`
- `items[].side in {"BUY", "SELL"}`

The current Daily Plan sidecar schema and the Manual Execution exporter/importer use a different actionable shape:

- `items[].action in {"BUY", "SELL"}` or `items[].type in {"BUY", "SELL"}`
- `symbol` present
- `quantity` or `shares` positive

For the 2026-06-15 smoke case, this mismatch made a plan with 9 actionable BUY/SELL rows look like a zero-candidate no-action day. As a result, Manual Execution Template, Preview, Commit, and Status Sync were all marked DONE through OPER9-17 skip rules.

## 2. Scope and Method

Scope:

- Compare existing Orchestrator behavior with OPER9-added criteria.
- Identify criteria collisions and priority problems.
- Prepare a concrete fix plan for OPER9-20C.
- Document risks and invariants.

Read-only sources inspected:

- `docs/TRD/mfu_oper9_20a_orchestrator_decision_criteria_audit.md`
- `docs/TRD/mfu_oper9_daily_ops_orchestrator_closeout.md`
- `docs/TRD/mfu_oper9_post15_closeout_addendum.md`
- `docs/TRD/mfu_oper9_13_manual_execution_state_reconciliation_hardening.md`
- `docs/TRD/mfu_oper9_14_manual_review_wait_state_reconciliation_hardening.md`
- `docs/TRD/mfu_oper9_15_manual_review_post_commit_status_sync_reconciliation_fix.md`
- `docs/TRD/mfu_oper9_16_date_scoped_review_artifact_guard.md`
- `docs/TRD/mfu_oper9_17_no_execution_candidates_advancement_guard.md`
- `docs/TRD/mfu_oper9_18_no_action_day_daily_review_completion_guard.md`
- `docs/TRD/mfu_oper9_19a_eod_preflight_account_scope_alignment.md`
- `docs/TRD/mfu_oper9_19b_no_action_day_eod_roll_forward_final_closure.md`
- `core/paper_daily_ops_orchestrator.py`
- `core/paper_daily_ops_reconciliation.py`
- `core/paper_daily_ops_operator_summary.py`
- `core/paper_daily_ops_notion_status.py`
- `core/paper_daily_ops_evidence.py`
- `core/paper_status.py`
- `core/notion_exporters.py`
- `core/notion_manual_execution_importer.py`
- `scripts/run_paper_eod_update.py`
- `tests/test_paper_daily_ops_orchestrator.py`
- `tests/test_paper_daily_ops_orchestrator_guard.py`
- `tests/test_paper_cli.py`
- `tests/test_paper_cli_account_scope.py`
- `tests/test_paper_status.py`

Read-only commands included `git log`, `git show`, `git grep`, file reads, and JSON artifact inspection. No Notion write, sync, import commit, EOD commit, broker/API/order, ledger mutation, or DB mutation command was executed.

## 3. Baseline Identification

There is no single clean "pre-OPER9 Orchestrator" code baseline because the Orchestrator was introduced during OPER9.

Confirmed baseline layers:

| Baseline | Commit | Confidence | Use in this analysis |
| --- | --- | --- | --- |
| Pre-OPER9 no-code baseline | before `370f9f8` | High | Orchestrator code did not exist yet; not useful for function-level delta. |
| OPER9 design baseline | `370f9f8` | High | Stage inventory design only. |
| First comparable code baseline | `b644764` | High | OPER9-2 local MVP. Manual Execution stages existed without no-candidate guard or reconciliation. |
| OPER9-17 immediate prior baseline | `5474ae1` | High | Best baseline for analyzing no-execution-candidates delta. |
| Current audit baseline | `8917d83` | High | OPER9-20A current criteria inventory. |

Key baseline behavior before OPER9-17, confirmed from `5474ae1:core/paper_daily_ops_orchestrator.py`:

- `MANUAL_EXECUTION_TEMPLATE` did not count Daily Plan candidates.
- If Daily Plan was DONE, the template stage used local Notion evidence if present; otherwise it returned `UNKNOWN` with `export_paper_to_notion.py --manual-execution-template ...`.
- `MANUAL_EXECUTION_PREVIEW` used local preview JSON if present; otherwise recommended `import_notion_executions.py --preview`.
- `MANUAL_EXECUTION_COMMIT` used local commit report, ledger/snapshot evidence, and preview validity.
- `MANUAL_EXECUTION_STATUS_SYNC` required local commit report before recommending `sync_notion_execution_status.py`.
- `DAILY_REVIEW` required execution commit evidence or same-date snapshots before review generation.

This baseline was conservative but could loop on no-action days because zero candidates produce no Notion rows and no execution commit.

## 4. OPER9 Policy Delta Inventory

| MFU | Problem addressed | Added/changed criteria | Intended benefit | Current risk |
| --- | --- | --- | --- | --- |
| OPER9-13 | Manual Execution DRAFT and post-sync states were misrepresented. | Added WAIT_FOR_INPUT for DRAFT rows; accepted `COMMITTED/IMPORTED/SYNCED` as post-sync states; converted Account ID select HTTP 400 into structured warning. | Prevent false conflicts and tell operator to enter Actual Price. | Mostly valid. Can be bypassed when OPER9-17 sets no-candidates first. |
| OPER9-14 | Manual Review PENDING/DRAFT rows could be hidden behind status commands. | Added Manual Review input wait and READY/REVIEWED preview priority. | Keep human review input operator-facing. | Valid. No direct 2026-06-15 collision found. |
| OPER9-15 | Review append done but Notion status sync pending could still show terminal. | Added sync-needed terminal guard and `OPER9_15_REVIEW_SYNC_REVIEW_DONE_NOTION_UNSYNCED`. | Do not close terminal before review status sync. | Valid. Suggest similar priority thinking for Manual Execution sync after commit. |
| OPER9-16 | Fixed-name review artifacts could be stale. | Added internal date checks for review template and summaries. | Prevent stale review completion. | Valid, but no-action day needed later relaxation for snapshot dates. |
| OPER9-17 | Zero execution candidates caused repeated Manual Execution export recommendation. | Added `_daily_plan_execution_candidate_count`, `no_execution_candidates`, and skip-DONE rules for Manual Execution Template/Preview/Commit/Sync. | Allow true no-action days to advance to Daily Review. | Candidate schema mismatch; skip rules override normal evidence and sync paths. |
| OPER9-18 | No-action Daily Review remained READY when summary snapshot date was prior day. | If `no_execution_candidates=true`, summary snapshot mismatch becomes warning; review template date and validation PASS remain required. | Complete review on no-action days without same-date execution snapshot. | Inherits false no-action decisions from OPER9-17. |
| OPER9-19A | EOD preflight used fallback root before account paths were resolved. | Build account paths before EOD preflight. | Account-scoped EOD dry-run/commit preflight. | Valid. No direct 20B collision. |
| OPER9-19B | No-action day lacked same-date state closure. | No-action EOD roll-forward writes current state/account snapshot/position snapshot without execution rows. | Let status and Orchestrator reach terminal closure after no-action review. | Depends on accurate no-action candidate classification. |

## 5. Stage Delta Matrix

| Stage | Pre-OPER9 or existing comparable criteria | OPER9 added/modified criteria | Current priority | Risk | 2026-06-15 impact | Decision | Next task |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `DATA_FRESHNESS` | READY read-only freshness command unless global blockers. | Stale command suppression prevents rewind after plan exists. | Suppressed if Daily Plan/workflow advanced. | Low. | None. | Keep. | None. |
| `DAILY_PLAN` | Required markdown/json/config snapshot with account/date checks. | Legacy paper_test guard and date/account validation hardened. | Local source-of-truth. | Low. | Correctly DONE. | Keep. | None. |
| `DAILY_PLAN_NOTION_EXPORT` | Evidence missing meant export needed/unknown. | Notion live read reconciliation can mark DONE/READY/WARNING. | Reconciliation can override local status. | Medium on Notion API/schema warnings. | Existing status varied depending live read. | Keep. | Improve Notion diagnostics separately. |
| `MANUAL_EXECUTION_TEMPLATE` | Local plan DONE -> evidence/Notion row or export command. | OPER9-17 candidate count can mark DONE no-op before normal evidence/rows. | `candidate_count==0` wins before evidence and reconciliation. | High. | 9 BUY/SELL candidates counted as 0; template DONE skip. | Modify. | 20C schema alignment and priority guard. |
| `MANUAL_EXECUTION_PREVIEW` | Preview JSON DONE/WARNING, else READY preview command. | OPER9-13 post-sync no READY rows accepted; OPER9-17 no-candidates skip. | No-candidates skip wins before preview JSON. | High. | Existing preview with 9 candidates hidden by skip. | Modify. | Do not skip if preview artifact exists or candidates >0. |
| `MANUAL_EXECUTION_COMMIT` | Commit report DONE; ledger/snapshot without report WARNING; preview needed before commit. | OPER9-17 no-candidates skip. | No-candidates skip wins before commit report. | High. | Existing commit report with 9 committed rows hidden by skip. | Modify. | Commit report should override skip. |
| `MANUAL_EXECUTION_STATUS_SYNC` | Commit report required; then sync evidence or sync command. | OPER9-17 no-candidates skip. | No-candidates skip wins before commit report/sync need. | High. | Sync report absent but stage DONE skip. | Modify. | Commit report should force sync evaluation. |
| `DAILY_REVIEW` | Required execution commit or same-date snapshot before review. Fixed artifacts initially accepted by existence. | OPER9-16 date guard; OPER9-18 no-action snapshot mismatch relaxation. | `no_execution_candidates` relaxes summary snapshot blocker. | Medium/High if false no-action. | False no-action made summary mismatch warning rather than blocker; template date still blocked. | Modify dependency. | Fix no-candidates source first. |
| `MANUAL_REVIEW_TEMPLATE` | Current review template CSV required. | OPER9-16 template date guard; Notion reconciliation. | Template date guard wins. | Low. | Protected by stale template date blocker. | Keep. | None. |
| `MANUAL_REVIEW_PREVIEW` | Preview JSON or Notion ready rows. | OPER9-14 wait state and ready/reviewed priority. | Manual input wait before generic statuses. | Low. | None. | Keep. | None. |
| `MANUAL_REVIEW_APPEND` | Commit report/log/preview based. | Existing reconciliation hardened. | Local commit report source-of-truth. | Low. | None. | Keep. | None. |
| `MANUAL_REVIEW_STATUS_SYNC` | Review commit report required. | OPER9-15 sync-required before terminal. | Sync needed blocks terminal. | Low. | None. | Keep. | Consider analogous Execution sync priority. |
| `FINAL_STATUS` | `paper.py status` diagnostic. | Terminal true only when REVIEW_DONE and no required sync. | Terminal suppresses commands. | Low/Medium. | Not terminal yet. | Keep. | Add Execution sync required condition if needed. |

## 6. Manual Execution Decision Delta

### Existing comparable flow before OPER9-17

Manual Execution was driven by source-of-truth local artifacts plus Notion state:

1. Template stage required Daily Plan DONE.
2. If template export evidence or Notion rows existed, it could be DONE.
3. If Notion READY rows existed, preview became the next actionable step.
4. If preview JSON existed, commit became the next actionable step.
5. If commit report existed, status sync became the next actionable step unless sync evidence/Notion synced rows existed.
6. Local commit report remained the proof of local execution completion. Notion-only committed rows did not prove local commit.

This flow is conservative and source-of-truth aligned. Its weakness was true no-action days, where no Manual Execution rows and no commit report are expected.

### OPER9-17 delta

OPER9-17 inserted candidate count into `MANUAL_EXECUTION_TEMPLATE`, then propagated the resulting flag into:

- `MANUAL_EXECUTION_TEMPLATE`
- `MANUAL_EXECUTION_PREVIEW`
- `MANUAL_EXECUTION_COMMIT`
- `MANUAL_EXECUTION_STATUS_SYNC`
- `DAILY_REVIEW` gating
- OPER9-18 no-action Daily Review snapshot relaxation

The inserted check is earlier than preview, commit, status sync, and Notion reconciliation. When the flag is true, downstream stage builders return DONE before inspecting their normal required artifacts.

### Collision

The no-candidates path is valid only if the candidate count is accurate. Because it is currently inaccurate for the official Daily Plan sidecar schema, it overwrites:

- Notion row evidence;
- local preview evidence;
- local commit report evidence;
- status sync recommendation;
- normal execution-day Daily Review gating.

## 7. No-Execution-Candidates Guard Delta

OPER9-17 intended policy:

- If Daily Plan has zero Manual Execution export candidates, skip the Manual Execution loop as no-op DONE.
- If export evidence shows `candidate_count=0` and `failed_count=0`, accept it as durable no-op evidence.
- Do not repeat Manual Execution template export.
- Advance to Daily Review.

Implementation details:

- `_daily_plan_execution_candidate_count()` was added in `core/paper_daily_ops_orchestrator.py`.
- The helper reads `daily_action_plan_YYYYMMDD.json`.
- It returns zero only when all items fail this condition: `action=EXECUTE`, `status=PENDING`, `side=BUY/SELL`.
- Reconciliation rules `OPER9_17_EXEC_TEMPLATE_NO_CANDIDATES`, `OPER9_17_EXEC_PREVIEW_SKIPPED_NO_CANDIDATES`, `OPER9_17_EXEC_COMMIT_SKIPPED_NO_CANDIDATES`, and `OPER9_17_EXEC_SYNC_SKIPPED_NO_CANDIDATES` return DONE and suppress `next_command`.

Mismatch:

- The OPER9-17 document required the candidate criteria to match `export_paper_to_notion.py` as closely as possible.
- The exporter actually uses `item["action"] or item["type"] in {BUY, SELL}` and positive `quantity`/`shares`.
- Tests added in OPER9-17 used legacy-shaped fixtures (`action=EXECUTE`, `status=PENDING`, `side=BUY/SELL`) and did not cover current sidecar shape (`action=BUY/SELL`, `quantity>0`).

Priority problem:

- The no-candidates guard is currently a high-priority shortcut.
- It does not check for existing local preview/commit artifacts before skipping preview/commit/sync.
- It does not let a commit report force `MANUAL_EXECUTION_STATUS_SYNC`.

## 8. Reconciliation Priority Delta

Before OPER9-17, reconciliation decided Manual Execution conflicts using local stage status, Notion row counts, READY rows, post-sync statuses, and local commit reports.

OPER9-13 improved this by distinguishing post-sync state:

- no READY rows after commit/sync is expected;
- `COMMITTED`, `IMPORTED`, and `SYNCED` are accepted post-sync statuses;
- DRAFT rows with missing prices become `WAIT_FOR_INPUT`.

OPER9-17 sits above that reconciliation logic:

- `_manual_execution_template()`, `_manual_execution_preview()`, `_manual_execution_commit()`, and `_manual_execution_status_sync()` in reconciliation immediately return DONE if `stage.get("no_execution_candidates")`.
- This means Notion statuses and local commit state do not get their normal reconciliation priority once the flag is true.

Required 20C adjustment:

- No-candidates skip should be allowed only when no execution candidates exist by the same criteria as export/import.
- If local preview exists, preview stage should evaluate the preview.
- If local commit report exists, commit stage should be DONE because of the report, not because of no-candidates.
- If local commit report exists and sync evidence is absent, status sync should not be skipped by no-candidates.

## 9. Operator Summary Priority Delta

OPER9-7 to OPER9-15 improved `operator_summary` from a raw first-command selector to an operator workflow summary:

- terminal first;
- reconciliation conflict next;
- top-level `next_command`;
- manual input wait;
- then first `BLOCKED`, `WARNING`, `READY`, `UNKNOWN`.

That priority is generally correct. The 2026-06-15 issue is not primarily an `operator_summary` ordering bug. It is upstream stage status corruption:

- Manual Execution stages are marked DONE through no-candidates skip.
- Therefore no Execution sync command is available for `operator_summary` to choose.
- `DAILY_REVIEW` becomes the next visible command.

Still, 20C should consider whether `MANUAL_EXECUTION_STATUS_SYNC` with an existing commit report should be protected as a required sync stage in the same style as OPER9-15 protected `MANUAL_REVIEW_STATUS_SYNC`.

## 10. Invariant Check

### Manual Execution invariants

| Invariant | Current result | Evidence | Required action |
| --- | --- | --- | --- |
| Daily Plan with BUY/SELL positive quantity item must not set `no_execution_candidates=true`. | FAIL | 2026-06-15 had 9 BUY/SELL positive quantity items but count was 0. | Fix candidate count schema. |
| Notion Manual Execution rows READY/NOT_IMPORTED with Actual Price should be preview/commit candidates. | At risk | Importer criteria support this, but Orchestrator can skip before using it. | Guard skip with Notion/local artifact evidence. |
| Existing commit report should outrank no-candidates skip for status sync. | FAIL/At risk | 2026-06-15 commit report exists, status sync stage skipped DONE. | Prioritize commit report and sync need. |
| Existing local commit should suppress duplicate commit but may still require Notion status sync. | Partially FAIL | Commit repeat suppressed, but sync can be skipped by false no-candidates. | Add sync priority hardening. |
| Notion-only completion must not prove local commit. | PASS outside false skip path | OPER9-6 reconciliation blocks Notion committed without local report. | Preserve. |
| Local source-of-truth remains authoritative. | Partially FAIL | Source artifacts can be hidden by false no-candidates branch. | Preserve and re-prioritize local artifacts. |

### No-action invariants

| Invariant | Current result | Evidence | Required action |
| --- | --- | --- | --- |
| Only true zero-candidate Daily Plans should no-op Manual Execution. | FAIL | Candidate count schema mismatch. | Fix count helper and tests. |
| No-action day can still require Daily Review, Manual Review, and EOD closure. | PASS | OPER9-18/19B policies. | Keep. |
| No-action EOD must not append execution log rows. | PASS | OPER9-19B tests and policy. | Keep. |
| No-action terminal requires REVIEW_DONE/final PASS conditions. | PASS if classification correct | OPER9-19B/19C. | Keep. |

### Review invariants

| Invariant | Current result | Evidence | Required action |
| --- | --- | --- | --- |
| Manual Review preview follows Import Status READY and Manual Answer/Review Status conditions. | PASS | OPER9-14 and importer behavior. | Keep. |
| Review commit followed by unsynced Notion status must not terminal-close. | PASS | OPER9-15. | Keep. |
| Fixed-name review artifacts require internal date checks. | PASS | OPER9-16/18. | Keep. |
| No-action review summary snapshot mismatch can be warning only for true no-action days. | At risk | False no-candidates contaminates no-action review guard. | Fix upstream no-candidates. |

## 11. 2026-06-15 Case Study

Account:

- `paper_orch_smoke_202606`

Dates:

- data_date: `2026-06-12`
- trade_date: `2026-06-15`

Daily Plan:

- file: `outputs\paper_accounts\paper_orch_smoke_202606\daily_action_plan_20260615.json`
- `items=9`
- `BUY=7`
- `SELL=2`
- `action=BUY/SELL`
- positive `quantity` rows: 9
- `status`: absent/null for all 9
- `side`: absent/null for all 9

Local Manual Execution artifacts:

- `reports/manual_execution_import_preview_20260615.json` exists
- preview `candidate_count=9`
- `reports/manual_execution_import_commit_20260615.json` exists
- commit report contains 9 committed rows
- `reports/manual_execution_template_export_20260615.json` was not found during this audit
- `reports/manual_execution_status_sync_20260615.json` was not found during this audit

Previously saved Orchestrator status evidence:

- `MANUAL_EXECUTION_TEMPLATE.status=DONE`
- `no_execution_candidates=true`
- `execution_candidate_count=0`
- `reconciliation_rule_id=OPER9_17_EXEC_TEMPLATE_NO_CANDIDATES`
- Notion row count in `outputs\orch_status.json`: 9
- Notion status counts in `outputs\orch_status.json`: `IMPORTED=9`, `COMMITTED=9`
- `MANUAL_EXECUTION_STATUS_SYNC.status=DONE`
- `reconciliation_rule_id=OPER9_17_EXEC_SYNC_SKIPPED_NO_CANDIDATES`

Fresh 20A audit status with live read returned Notion API/schema warning and row count 0, but still reproduced the same local candidate-count bug:

- `MANUAL_EXECUTION_TEMPLATE.status=DONE`
- `no_execution_candidates=true`
- `execution_candidate_count=0`
- `current_step=DAILY_REVIEW`

Conclusion:

- This is not an execution importer/exporter failure.
- Export/import and local commit evidence agree that the day had executable BUY/SELL candidates.
- The structural bug is in Orchestrator candidate counting and the priority of the no-candidates shortcut.

## 12. Risks and Regressions

| Risk | Severity | Description |
| --- | --- | --- |
| False no-action classification | High | Real execution days can be treated as no-action when plan items use current `action=BUY/SELL` schema. |
| Status sync skipped after real commit | High | Existing commit report may not lead to Manual Execution status sync recommendation. |
| Daily Review gating relaxed incorrectly | Medium/High | False no-action propagates to OPER9-18 and can downgrade summary snapshot mismatch. |
| Test coverage gap | High | OPER9-17 tests cover legacy-shaped no-candidate fixtures, not current Daily Plan sidecar schema. |
| Reconciliation bypass | Medium/High | Notion/local evidence rules added in OPER9-13 can be bypassed by OPER9-17 early return. |
| Operator summary misleading next step | Medium | The summary shows the next visible command from corrupted stage state, not from a direct summary bug. |

## 13. Recommended Fix Plan for OPER9-20C

Priority 1: Execution candidate count schema alignment.

- Count current sidecar shape:
  - `items[]`
  - `action` or `type` in `BUY/SELL`
  - `symbol` present
  - `quantity` or `shares` > 0
- Preserve legacy compatibility only if needed:
  - `action=EXECUTE`, `status=PENDING`, `side=BUY/SELL`
- Prefer extracting a shared helper or mirroring `core/notion_exporters.py:_manual_execution_template_candidates_from_sidecar()` criteria.

Priority 2: Strengthen no-candidates guard conditions.

- Do not apply no-candidates skip if candidate count is `None`.
- Do not apply no-candidates skip if local preview or commit artifact exists for the target date.
- Do not let no-candidates skip hide an existing commit report.
- If commit report exists and status sync evidence is missing, `MANUAL_EXECUTION_STATUS_SYNC` should evaluate normally.
- Treat `manual_execution_template_export_YYYYMMDD.json` with `candidate_count=0`, `failed_count=0`, and matching account/date as no-op proof only when no local preview/commit evidence contradicts it.

Priority 3: Regression tests.

- Current schema positive case: `items=[{"action":"BUY","symbol":"AAPL","quantity":10}]` must not set `no_execution_candidates=true`.
- Current schema zero case: no BUY/SELL positive quantity rows should skip Manual Execution.
- Legacy schema positive case: `action=EXECUTE/status=PENDING/side=BUY` if backward compatibility is retained.
- Export evidence zero case.
- Commit exists plus no-candidates false-positive case: status sync must not be skipped.
- 2026-06-15 shape fixture with BUY 7 / SELL 2.

Priority 4: Operator summary review.

- After fixing stage state, verify that `MANUAL_EXECUTION_STATUS_SYNC` appears before `DAILY_REVIEW` when a real execution commit exists but status sync is missing.
- Consider an Execution sync-required terminal/stage guard analogous to OPER9-15 Manual Review sync protection.

## 14. No-write Safety Confirmation

This task did not run:

- `scripts/export_paper_to_notion.py --confirm-actual`
- `scripts/import_notion_executions.py --commit`
- `scripts/import_notion_reviews.py --commit`
- `scripts/sync_notion_execution_status.py`
- `scripts/sync_notion_review_status.py`
- `scripts/paper.py eod --commit`
- `scripts/paper.py commit`
- broker/API/order commands
- ledger/DB mutation commands

Read-only artifact inspection included existing JSON files under `outputs\paper_accounts\paper_orch_smoke_202606` and existing status snapshots. These operational outputs were not modified and are not included in this commit.

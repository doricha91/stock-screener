# RECOVERY-LIFECYCLE-AUDIT-1 Review Evidence

## Work instruction identity

- Absolute path: `D:\python\StockScreener\docs_chatGPT_work\Recovery lifecycle audit_반복 recovery lifecycle 감사 및 수정.md`
- Title: `Codex 작업지시문 — RECOVERY-LIFECYCLE-AUDIT-1 반복 Recovery lifecycle 감사 및 수정`
- Top-level sections: 20
- Instruction length: 745 lines
- Branch: `gemini_cli_update`
- Start HEAD: `e17978f332a8853588f287cf5aa2a5ef9bd57c74`
- Unexpected conflicting target changes: none

Root `AGENTS.md` and the complete instruction were read as UTF-8 before implementation.

## Start dirty state

Pre-existing tracked changes recorded before this audit:

```text
 M core/runbook_recovery.py
 M docs/operations/paper_daily_cycle_commands.md
 M docs/operations/runbook_recovery_contract.md
 M "idea, PRD, TRD/paper 운영 기능 개발 로드맵 v1.3.md"
 M ops/runbook_wrappers/02_gate1_execution_input.cmd
 M outputs/backtest_log.db
 M scripts/runbook_gate_checker.py
 M tests/test_runbook_gate_checker.py
 M tests/test_runbook_recovery.py
 M tests/test_runbook_stage_wrappers.py
```

The worktree also contained the RECOVERY-RESTART-1 and RECOVERY-LIFECYCLE-1 result bundles, many unrelated untracked documents/temp directories, and inaccessible pytest temp directories. All were preserved. `core/runbook_day_rollover.py` was clean at task start.

## Audited call graph

```text
scripts/runbook_recovery.py
  -> preview_recovery / authorize_recovery / recovery_status
  -> validate_recovery_evidence
  -> target_status == PRESENT => consumed

scripts/runbook_day_rollover.py
  -> preview_rollover
  -> classify_state
  -> validate_recovery_evidence
  -> current authorization selection

scripts/runbook_state.py::init_state_file_for_context
  -> assert_initialization_allowed
  -> classify_state + current authorization selection
  -> preview_rollover for normal post-consumption context
```

The instruction referenced `core/runbook_state.py`, which does not exist in this repository. The actual equivalent implementation is `scripts/runbook_state.py`; it was inspected and not modified.

## Audited lifecycle state model

| State | Before audit | Expected | Result |
| --- | --- | --- | --- |
| A. No Recovery history | Normal rollover | Normal rollover | Preserved |
| B. One consumed Recovery | Falls through to normal | Historical, normal rollover | Preserved |
| C. Multiple consumed Recoveries | BLOCKED as multiple | Historical, normal rollover | Fixed |
| D. One unconsumed Recovery | Exact recovery pair | Exact recovery pair | Preserved |
| E. Consumed many + unconsumed one | BLOCKED as multiple | Select unconsumed one | Fixed |
| F. Unconsumed valid two or more | BLOCKED | Fail-closed BLOCKED | Preserved with corrected candidate set |
| G. Invalid evidence | Reclassified active | Fail-closed active blocker | Preserved |
| H. Target absent | `consumed=false` | Exact target preparable | Preserved |
| I. Target exists | `consumed=true`; target active guard | No authorization reuse | Preserved |
| J. Target completed | Normal rollover for one history | Normal rollover | Preserved and generalized |
| K. Second Recovery | Authorize succeeds; rollover blocked by history | Select Recovery #2 | Fixed |
| L. Second target completed | BLOCKED by two histories | Normal rollover | Fixed |

## Problems found

1. `preview_rollover()` counted every valid `RECOVERY_EXCLUDED` history before checking consumed state.
2. `assert_initialization_allowed()` duplicated the same total-count rule and could block exact second targets or the next normal state after multiple historical Recoveries.
3. Rollover and initialization lacked a shared definition of current Recovery authorization.

## Problems fixed

- Added `_current_recovery_authorizations()` in `core/runbook_recovery.py`.
- The helper revalidates each classified Recovery through `validate_recovery_evidence()`, fails closed if validity changed, and selects only `consumed=false` records.
- `preview_rollover()` now applies 0/1/2+ policy to current unconsumed candidates only.
- `assert_initialization_allowed()` uses the same helper for exact recovery target and post-consumption normal context decisions.
- Multiple blockers list only conflicting current unconsumed sources, not historical consumed sources.

## Problems not changed and reasons

- Recovery authorize does not add a new schema field or separate current-authorization registry. Existing immutable sidecars plus target existence already provide validity and consumed SSOT; a registry would duplicate state and require broader design/schema work.
- A deliberately abnormal fixture can create two unconsumed sidecars by bypassing normal centralized initialization. This remains an explicit fail-closed state in both rollover and initialization, as required. Normal lifecycle cannot create the second source through `init_state_file_for_context()` while the first target is absent.
- No operational contract file was changed. Its existing exact-pair and target active/completed semantics remain correct and do not define historical Recovery count as an error.
- No actual operating workspace inspection was needed to reproduce the supplied dates; all reproduction used pytest temporary fixtures as required.

## Scoped changes

```text
core/runbook_recovery.py
  _current_recovery_authorizations
  assert_initialization_allowed current/historical selection hunks

core/runbook_day_rollover.py
  preview_rollover current/historical selection hunk

tests/test_runbook_recovery.py
  dynamic completion helper target identity
  _mark_active_incident
  test_repeated_recovery_lifecycle_selects_only_current_authorization
  test_multiple_unconsumed_recoveries_remain_fail_closed

docs/work_results/RECOVERY-LIFECYCLE-AUDIT-1_Result.md
docs/work_results/RECOVERY-LIFECYCLE-AUDIT-1_Review_Evidence.md
```

The larger diff in `core/runbook_recovery.py` and `tests/test_runbook_recovery.py` also contains preserved RECOVERY-RESTART-1 and RECOVERY-LIFECYCLE-1 hunks that predated this audit.

## Repeated-Recovery integration test

`test_repeated_recovery_lifecycle_selects_only_current_authorization` runs one continuous lifecycle:

1. Seed an ordinary completed Runbook and Recovery #1 source `2026-08-13 → 2026-08-14`.
2. Authorize Recovery #1 to `2026-08-21 → 2026-08-24`.
3. Create and complete target #1; assert normal rollover to `2026-08-24 → 2026-08-25`.
4. Create/progress that next source and authorize Recovery #2 to `2026-08-27 → 2026-08-28`.
5. Assert Recovery #1 valid+consumed and Recovery #2 valid+unconsumed simultaneously.
6. Assert rollover PASS, `rollover_mode=RECOVERY`, Recovery #2 source only, exact operational pair/ID, and `safe_to_prepare=true`.
7. Create target #2; assert Recovery #2 becomes consumed and ordinary active guard blocks reuse.
8. Complete target #2; assert normal rollover to `2026-08-28 → 2026-08-31` despite two consumed histories.
9. Initialize that exact normal context, exercising the corrected central initialization guard.

The test uses only pytest temporary workspace/account paths and isolated completion-classifier patching. It does not touch actual operating evidence.

## Acceptance matrix

| # | Requirement | Evidence |
| --- | --- | --- |
| 1 | Historical consumed not current | Integration test validates first consumed and selects second only |
| 2 | Multiple consumed allow normal rollover | Final integration rollover PASSes with two consumed sidecars |
| 3 | Consumed many + unconsumed one selects one | Current integration rollover selects `MISSED_SOURCE_ID` |
| 4 | 8/13 historical + 8/24 current fixture | Exact dates used in integration test |
| 5 | Exact 8/27 → 8/28 restart | Data date, trade date, target ID asserted |
| 6 | Two current unconsumed fail closed | `test_multiple_unconsumed_recoveries_remain_fail_closed` |
| 7 | Invalid evidence not ignored | Existing mutation tests and full Recovery suite PASS |
| 8 | Target creation prevents reuse | Integration test asserts target active guard; existing exact-target tests PASS |
| 9 | Completed target returns normal | Both target completion stages asserted in integration test |
| 10 | Continuous second-Recovery lifecycle | Single integration test covers steps 1–13 |
| 11 | RECOVERY-RESTART-1 preserved | Full Recovery suite including equality tests PASS |
| 12 | RECOVERY-LIFECYCLE-1 preserved | Valid/invalid previous-recovery tests PASS in full suite |
| 13 | Rollover suite | 88 passed |
| 14 | No schema change | Schema constants and payload/state/ledger shapes unchanged |
| 15 | No actual operating write | No command targeted `D:\n8n\workspace\stock_screener_ops` |
| 16 | Dirty changes preserved | No destructive git command; unrelated status retained |

## Commands actually run

```text
python -m pytest tests/test_runbook_recovery.py -q -k "repeated_recovery_lifecycle or multiple_unconsumed_recoveries"
2 passed, 35 deselected in 6.98s

python -m pytest tests/test_runbook_recovery.py -q
37 passed in 30.31s

python -m pytest tests/test_runbook_day_rollover.py -q
88 passed in 20.56s

python -m py_compile core/runbook_recovery.py core/runbook_day_rollover.py
PASS

git diff --check
PASS

git status --short
PASS (recorded; existing dirty/untracked files remain)
```

## Entire repository suite

Not run. The required new lifecycle tests and complete Recovery/rollover suites directly cover the changed selection boundary, totaling 125 passing tests. The repository also contains numerous unrelated dirty/untracked workstreams and inaccessible temporary directories that are outside this task.

## Operating environment and protected state

- No command was run against `D:\n8n\workspace\stock_screener_ops`.
- No actual Recovery preview, authorize, prepare, state, sidecar, or execution ledger write was performed.
- No Notion, DB, broker, or external write was performed.
- The pre-existing protected `outputs/backtest_log.db` modification was not touched.
- No package installation or upgrade occurred.
- No reset, checkout, clean, stash, commit, or push occurred.

## Schema and policy review

- Recovery sidecar schema remains `runbook_recovery.v1`.
- Runbook state and execution ledger schemas are unchanged.
- RECOVERY-RESTART-1 equality, multi-day and earlier-date BLOCK policies are unchanged.
- RECOVERY-LIFECYCLE-1 `_base_classification()` and evidence-aware classification remain intact.
- Stage A, Notion, execution pipeline, strategy and general completion/retirement policies are unchanged.

## AGENTS.md compliance

- Inspected and summarized current behavior before editing.
- Kept the fix scoped to Recovery selection and direct regression tests.
- Preserved existing dirty changes and protected files.
- Used no destructive command or external/operational write.
- Ran the specified focused, full, compile, diff and status validations.
- Generated both required work-result documents.

## Remaining risks

- Selection performs a second validator pass after classification. This intentionally catches changed evidence fail-closed but adds validation I/O proportional to Recovery history.
- The selection helper is private and accepts rollover `StateRecord` objects through `Any` to avoid a circular type dependency. Runtime behavior is covered, but a future larger refactor could introduce a shared typed record protocol.
- Abnormal manual state creation can still produce two unconsumed authorizations; both consumers block safely, but remediation remains an operator/audit procedure because immutable sidecars are not deleted automatically.

## Structural blockers

None.

## Review commands

```text
git diff -- core/runbook_day_rollover.py core/runbook_recovery.py tests/test_runbook_recovery.py docs/work_results/RECOVERY-LIFECYCLE-AUDIT-1_Result.md docs/work_results/RECOVERY-LIFECYCLE-AUDIT-1_Review_Evidence.md
rg -n "_current_recovery_authorizations|test_repeated_recovery_lifecycle|test_multiple_unconsumed_recoveries" core/runbook_recovery.py core/runbook_day_rollover.py tests/test_runbook_recovery.py
```

## Final bundle validation

- UTF-8 re-read: PASS for Result and Review Evidence.
- Bundle trailing-whitespace scan: PASS.
- Final `git diff --check`: PASS.
- Final branch: `gemini_cli_update`.
- Final HEAD: `e17978f332a8853588f287cf5aa2a5ef9bd57c74` (unchanged).
- Task-scoped status: three code/test files modified and two required bundle files untracked; inspected CLI/state files remain unmodified.

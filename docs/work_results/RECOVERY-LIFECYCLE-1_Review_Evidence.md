# RECOVERY-LIFECYCLE-1 Review Evidence

## Work instruction identity

- Absolute path: `D:\python\StockScreener\docs_chatGPT_work\Recovery-lifecycle_기존 recover excluded 재분류 버그 수정.md`
- Title: `Codex 작업지시문 — RECOVERY-LIFECYCLE-1 기존 RECOVERY_EXCLUDED 재분류 버그 수정`
- Top-level sections: 9
- Branch: `gemini_cli_update`
- Start HEAD: `e17978f332a8853588f287cf5aa2a5ef9bd57c74`
- Unexpected conflicting target changes: none

Root `AGENTS.md` and the complete work instruction were read as UTF-8 before implementation.

## Start worktree evidence

The target files already contained the pre-existing RECOVERY-RESTART-1 changes:

```text
 M core/runbook_recovery.py
 M tests/test_runbook_recovery.py
```

OPS-UX-1 files, documentation, `outputs/backtest_log.db`, numerous untracked documents, and temporary directories were also already dirty. All were preserved. No reset, checkout, clean, stash, commit, or push was run.

## Scoped task files

```text
core/runbook_recovery.py
tests/test_runbook_recovery.py
docs/work_results/RECOVERY-LIFECYCLE-1_Result.md
docs/work_results/RECOVERY-LIFECYCLE-1_Review_Evidence.md
```

The task added only the lifecycle-specific hunks to the two already-dirty code/test files. `core/runbook_day_rollover.py` and `tests/test_runbook_day_rollover.py` were inspected and regression-tested without modification.

## Acceptance matrix

| Requirement | Evidence |
| --- | --- |
| Past valid `RECOVERY_EXCLUDED` is omitted from a new Recovery active count | `test_previous_valid_recovery_is_excluded_from_new_recovery_active_count` asserts the active list contains only the current target |
| Current real `ACTIVE_INCOMPLETE` is counted as the sole active source | Same test asserts the current target is the selected source and Preview PASSes |
| Preview is not blocked by `active_runbook_day_count_must_equal_one` | Same test asserts PASS and absence of that blocker |
| Existing validator, not a disposition string alone, controls exclusion | `_raw_classification()` calls `validate_recovery_evidence()` after base classification |
| Invalid recovery evidence returns to active fail-closed | `test_previous_invalid_recovery_returns_to_new_recovery_active_count` tampers calendar SHA and asserts both old and current IDs are active |
| Recovery internal and rollover classifications agree | Both new tests compare `_raw_classification()` with `classify_state()` for valid and invalid sidecars |
| Evidence source validation avoids recursive disposition acceptance | `validate_recovery_evidence()` uses `_base_classification()` for the original source-state check |
| Existing multi-day Recovery is preserved | Full 35-test Recovery suite passed |
| RECOVERY-RESTART-1 equality policy is preserved | Existing missed-operating-day equality tests passed in the full Recovery suite |
| General rollover behavior is preserved | Full 88-test rollover suite passed |
| Schemas and external lifecycle are unchanged | No schema constants, state/sidecar/ledger schema, or rollover code changed |

## Commands actually run

```text
python -m pytest tests/test_runbook_recovery.py -q -k "previous_valid_recovery_is_excluded or previous_invalid_recovery_returns"
2 passed, 33 deselected in 3.91s

python -m pytest tests/test_runbook_recovery.py -q
35 passed in 24.81s

python -m pytest tests/test_runbook_day_rollover.py -q
88 passed in 20.13s

python -m py_compile core/runbook_recovery.py core/runbook_day_rollover.py
PASS

git diff --check
PASS

git status --short
PASS (recorded; existing dirty/untracked files remain)
```

## Implementation review

- `_base_classification()` preserves the original completed/legacy/retired/active decision and deliberately ignores Recovery disposition.
- `_raw_classification()` only attempts recovery evidence validation after the base result is `ACTIVE_INCOMPLETE`; valid evidence returns `RECOVERY_EXCLUDED`, while missing or invalid evidence preserves `ACTIVE_INCOMPLETE`.
- `_load_recovery_context()` uses the evidence-aware result for active and completed sets and propagates the caller's calendar.
- Preview source checks and Recovery status use the same evidence-aware classification.
- `validate_recovery_evidence()` uses only base classification when proving that the source was an incomplete Runbook, preventing self-validation recursion.
- Rollover's existing `classify_state()` remains unchanged and uses the same `validate_recovery_evidence()` SSOT.

## External and protected state evidence

- No DB/schema or protected `.db` file was changed by this task.
- No source Runbook state, artifact, recovery evidence, or execution ledger was edited outside pytest temporary fixtures.
- No actual Recovery authorize/rollover or live/paper broker action was executed.
- No Notion command or external write was executed.
- No dependency was installed or upgraded.
- Pre-existing OPS-UX-1 and RECOVERY-RESTART-1 changes were retained.

## Tests not run

The repository-wide pytest suite was not run. The mandatory Recovery and rollover suites directly cover the modified classification boundary and downstream consumer, totaling 123 passing tests. Pre-existing unrelated dirty workstreams and inaccessible temporary directories remain outside this task.

## Review command

Because `core/runbook_recovery.py` and `tests/test_runbook_recovery.py` already contained RECOVERY-RESTART-1 changes at task start, review the lifecycle-specific symbols and tests directly:

```text
git diff -- core/runbook_recovery.py tests/test_runbook_recovery.py docs/work_results/RECOVERY-LIFECYCLE-1_Result.md docs/work_results/RECOVERY-LIFECYCLE-1_Review_Evidence.md
rg -n "_base_classification|previous_valid_recovery|previous_invalid_recovery" core/runbook_recovery.py tests/test_runbook_recovery.py
```

## Final bundle validation

- UTF-8 re-read: PASS for both Result and Review Evidence files.
- Bundle trailing-whitespace scan: PASS.
- Final `git diff --check`: PASS.
- Final branch: `gemini_cli_update`.
- Final HEAD: `e17978f332a8853588f287cf5aa2a5ef9bd57c74` (unchanged).
- Task status: the two pre-existing dirty target files remain modified and the two task bundle files are untracked; no unrelated tracked file was added to this task scope.

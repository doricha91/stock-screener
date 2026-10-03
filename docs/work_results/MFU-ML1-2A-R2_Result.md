# MFU-ML1-2A-R2 Result Evidence

Review status: PENDING_CHATGPT_REVIEW

## Baseline and scope

- Task: MFU-ML1-2A-R2_DANGLING_LIFECYCLE_SYMLINK_FAIL_CLOSED
- Worktree: C:/Users/inocha/AppData/Local/Temp/StockScreener_MFU_ML1_2_20260927
- Branch: detached HEAD
- Base / HEAD: 808d14cb889a90ebbbe90b307acb640b4dc8198c
- Starting state: the uncommitted ML1-2A + R1 source/test/TRD patch was present and
  `git apply --reverse --check docs/work_results/MFU-ML1-2A-R1_Changes.patch` passed.
- R2 scope: close only the dangling lifecycle-root symlink fail-open finding.

## Finding closure

### MINOR dangling lifecycle-root symlink fail-open: RESOLVED

`core.paper_account_fresh._history_blockers()` now classifies a lifecycle root in
this order:

    is_symlink -> unreadable_history blocker
    absent     -> no history
    non-dir    -> unreadable_history blocker
    directory  -> existing recursive evidence scan

This makes both live and dangling symlinks blockers. A genuinely absent path still
has the existing no-history behavior. Existing non-JSON, temporary-extension,
malformed and unattributable evidence checks are unchanged.

The validator remains read-only. It creates, deletes, repairs and renames no
operational artifact.

## Changed files and symbols

R2 delta only:

- `core/paper_account_fresh.py`
  - `_history_blockers`: checks `root.is_symlink()` before `root.exists()`.
- `tests/test_ml1_2a_binding_fresh.py`
  - `test_lifecycle_root_symlink_fails_closed`: deterministic dangling/live root
    cases, including `is_symlink() == True` with `exists() == False`.

No TRD change was necessary: R1 already specifies that unreadable or unexplained
lifecycle evidence fails closed. R2 corrects the implementation of that contract.

## Validation

Executed:

1. Targeted suite:

       python -m pytest tests/test_ml1_2a_binding_fresh.py -q
         -p no:cacheprovider
         --basetemp=C:/Users/inocha/AppData/Local/Temp/ml1_2a_r2_targeted_20261003_01
         --tb=short

   Result: 84 passed in 8.34s.

2. Static validation:

       python -m py_compile core/paper_account_fresh.py
       git diff --check

   Result: PASS.

3. Patch validation:

       git apply --reverse --check docs/work_results/MFU-ML1-2A-R2_Changes.patch
       git apply --reverse --check docs/work_results/MFU-ML1-2A-R2_Delta.patch

   Result: PASS for both patches.

The targeted file is the only test/consumer location importing
`validate_prepare_first_request`; no separate focused suite directly consumes this
validator. The R1 focused evidence remains 313 passed, and it was not repeated for
this isolated predicate-order fix.

The full repository suite, backtest and optimizer were not run because this change
does not alter strategy calculations or runtime consumption.

## Symlink environment evidence

An isolated actual dangling-symlink capability probe was attempted under the system
temporary directory. Windows rejected `Path.symlink_to()` with `WinError 1314`
(required privilege not held), before a link was created. The regression therefore
uses deterministic method modeling rather than skipping:

    dangling: is_symlink() == True, exists() == False
    live:     is_symlink() == True, exists() == True

Both cases produce `unreadable_history:operational_no_trade_gaps` and make the
request ineligible.

## Scope containment

- Policy ownership / semantic digest: unchanged
- V2 profile schema: unchanged
- Frozen serializer / Recovery / NTG structure: unchanged
- Runtime strategy injection: not performed
- Active regime application: not performed
- Runtime account universe selection: not performed
- Fresh actual prepare/create/resume: not performed
- Bootstrap writer: unchanged
- Operational account/profile/market/Notion mutation: not performed
- Commit/push/PR: not performed
- ML1-2B: not started

## Remaining risks

No current-scope correctness risk remains. Actual symlink creation could not be
exercised in this Windows environment, but the exact `pathlib` predicate states that
caused the finding are covered deterministically without a skip.

## Review bundle

- `docs/work_results/MFU-ML1-2A-R2_Result.md`
- `docs/work_results/MFU-ML1-2A-R2_Review.md`
- `docs/work_results/MFU-ML1-2A-R2_Changes.patch`
- `docs/work_results/MFU-ML1-2A-R2_Changes_Stat.txt`
- `docs/work_results/MFU-ML1-2A-R2_Delta.patch`

`MFU-ML1-2A-R2_Changes.patch` is the complete base-relative ML1-2A + R1 + R2
source/test/TRD diff. `MFU-ML1-2A-R2_Delta.patch` contains only the R1-to-R2
two-file delta.

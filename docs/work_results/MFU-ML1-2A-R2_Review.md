# MFU-ML1-2A-R2 Review Evidence

Status: PENDING_CHATGPT_REVIEW

Base / HEAD: 808d14cb889a90ebbbe90b307acb640b4dc8198c

## Finding disposition

| Finding | Result | Evidence |
| --- | --- | --- |
| MINOR dangling lifecycle-root symlink fail-open | RESOLVED | Symlink check precedes existence check; deterministic dangling/live regression passes |

## Before / after decision order

Before:

    exists? no -> ignored as missing
    directory or symlink? -> blocker

After:

    symlink? yes -> blocker
    exists? no -> genuinely absent
    directory? no -> blocker
    otherwise -> recursive evidence scan

The previous order allowed a dangling symlink to return `exists() == False` before
its symlink identity was inspected. The new order treats live and dangling links
identically and retains the existing blocker name.

## Acceptance Criteria

| AC | Result | Evidence |
| --- | --- | --- |
| 1 Dangling lifecycle root cannot pass fresh | PASS | `dangling` parameter case returns ineligible |
| 2 Live lifecycle root symlink remains blocked | PASS | `live` parameter case returns ineligible |
| 3 Truly missing root retains no-history behavior | PASS | Empty-workspace fresh eligibility remains covered by the 84-test targeted suite |
| 4 Existing artifact fail-closed behavior retained | PASS | non-JSON/tmp/malformed/unattributable cases pass in the same targeted suite |
| 5 Validator remains read-only | PASS | Predicate-order change only; no writer call added |
| 6 R1 ownership/digest/v2 behavior unchanged | PASS | R2 delta contains only fresh predicate order and its regression test |
| 7 Targeted and necessary focused validation pass | PASS | 84 targeted passed; no other direct consumer exists; prior 313 focused evidence retained |
| 8 Runtime/operational scope unchanged | PASS | R2 delta is limited to two files and performs no operational write |
| 9 Minimal source/test closure | PASS | 4 insertions/1 deletion in source; 21 test insertions |

## Test assessment

The regression directly distinguishes the previously conflated states:

    is_symlink=True, exists=False  # dangling
    is_symlink=True, exists=True   # live

The old implementation fails the dangling case because it exits at `exists() ==
False`. The revised implementation blocks before checking existence. Windows did
not grant actual symlink creation privilege (`WinError 1314`), so the deterministic
model was used as required instead of skipping the test.

## Static and patch checks

- `python -m py_compile core/paper_account_fresh.py`: PASS
- `git diff --check`: PASS
- Complete patch reverse check: PASS
- R1-to-R2 delta reverse check: PASS

## Review recommendation

READY_FOR_INDEPENDENT_REVIEW

This is not approval to commit, push, create a PR or begin ML1-2B.

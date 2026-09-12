# MFU-SV2-2 Result

Status: COMPLETE, pending ChatGPT review.

- `core/notion_manual_execution_importer.py` now derives the preview stateful stream from actual trade-bearing candidates and orders sequence-bearing v3 input by `execution_sequence` ascending. Cash, holdings, SELL validation, BUY cash validation, and long-position validation consume that stream.
- `scripts/runbook_stage_runner.py` treats both v2 and v3 as outcome contracts, so importer aggregate fields do not preempt reconciliation.
- Canonical-key assignment and trade-ID generation were not changed.

Validation:

- `tests/test_notion_manual_execution_importer.py -q`: 17 passed.
- `tests/test_runbook_stage_runner_stage_b.py -q`: 31 passed.
- `tests/test_execution_outcome_flow.py tests/test_paper_manual_execution_commit.py -q`: 47 passed, 2 pre-existing account-fixture failures.
- Changed Python files compile and `git diff --check` pass.

Operating data, root/SV1 worktrees, commits, pushes, and PRs: not modified.

# MFU-SV2 Actual Execution Order Contract — Result

- Status: COMPLETE (pending review)
- Worktree: `C:\Users\inocha\AppData\Local\Temp\StockScreener_MFU_SV2_20260912`
- Baseline: `0b3ac87816439cff546641986847c48ad5ad526b` plus approved MFU-SV1 source/test diff and resumed SV2 partial diff.

## Contract

- v1 remains legacy and unchanged.
- v2 remains outcome-only and sequence-free.
- New runbooks default to v3. An untouched, unfinalized v2 state may explicitly activate to v3; started, finalized, artifact-bearing, or idempotency-bearing v2 state is immutable.
- v3 carries `execution_sequence` from Notion input through candidate preview and reconciliation. EXECUTED/PARTIAL requires a positive integer; NOT_EXECUTED requires blank; gaps are permitted; duplicates fail closed.
- The v3 commit plan derives the effective trade-bearing stream by ascending sequence. Writer filtering, long-position validation and ledger append consume that same filtered order. Preview/reconciliation sequence drift fails before a writer call.
- Canonical keys and trade IDs do not use execution sequence.

## Validation

- `python -m pytest tests/test_execution_outcome_flow.py tests/test_runbook_state.py tests/test_paper_manual_execution_commit.py tests/test_runbook_stage_runner_stage_b.py tests/test_notion_manual_execution_importer.py -q`
  - 132 passed.
  - 2 pre-existing failures: uninitialized account fixture in `test_runbook_preview_reads_persisted_finalize_state`; missing explicit account paths in `test_all_not_executed_commit_is_complete_zero_write`. Both match MFU-SV1-2 reproduction.
- `python -m py_compile` for all changed Python modules: passed.
- `git diff --check`: passed.

No operating data, root worktree, SV1 worktree, Git metadata, commit, push, or PR was modified.

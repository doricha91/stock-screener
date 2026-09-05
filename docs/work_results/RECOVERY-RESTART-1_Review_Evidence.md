# RECOVERY-RESTART-1 Review Evidence

## Work instruction identity

- Absolute path: `D:\python\StockScreener\docs_chatGPT_work\Recovery-restart_1 운영일 누락 recovery 재시작 규칙 보완.md`
- Title: `Codex 작업지시문 — RECOVERY-RESTART-1 운영일 누락 Recovery 재시작 규칙 보완`
- Top-level sections: 10
- Branch: `gemini_cli_update`
- Start HEAD: `e17978f332a8853588f287cf5aa2a5ef9bd57c74`
- Unexpected conflicting target changes: none

Root `AGENTS.md` and the complete work instruction were read before implementation.

## Start worktree evidence

Pre-existing tracked changes:

```text
 M docs/operations/paper_daily_cycle_commands.md
 M "idea, PRD, TRD/paper 운영 기능 개발 로드맵 v1.3.md"
 M ops/runbook_wrappers/02_gate1_execution_input.cmd
 M outputs/backtest_log.db
 M scripts/runbook_gate_checker.py
 M tests/test_runbook_gate_checker.py
 M tests/test_runbook_stage_wrappers.py
```

Numerous pre-existing untracked temp/document files were also present. `core/runbook_recovery.py`, `core/runbook_day_rollover.py`, `tests/test_runbook_recovery.py`, and `tests/test_runbook_day_rollover.py` were clean. No staged changes existed.

## Scoped diff

```text
core/runbook_recovery.py
tests/test_runbook_recovery.py
docs/operations/runbook_recovery_contract.md
docs/work_results/RECOVERY-RESTART-1_Result.md
docs/work_results/RECOVERY-RESTART-1_Review_Evidence.md
```

`core/runbook_day_rollover.py` and its tests were read and fully regression-tested but did not require modification.

## Acceptance matrix

| Requirement | Evidence |
| --- | --- |
| `2026-08-24 → 2026-08-25` source can restart `2026-08-25 → 2026-08-26` | `test_missed_operating_day_equality_preview_authorize_and_exact_rollover` |
| Preview and Authorize PASS | Same test asserts both results and valid sidecar |
| Rollover returns exact target | Same test asserts recovery mode, dates, and runbook ID |
| Equality is guarded, not a simple comparison relaxation | `_restart_policy_violations()` checks calendar pair and commit evidence; `_execution_gap()` checks ledger |
| Source trade execution blocks | `test_missed_operating_day_equality_blocks_source_trade_execution` |
| Source execution commit evidence blocks | `test_missed_operating_day_equality_blocks_execution_commit_evidence` |
| Earlier restart data date blocks | `test_restart_data_date_before_source_trade_date_remains_blocked` |
| Equality requires exact next trading day | `test_missed_operating_day_equality_requires_exact_next_trading_day` |
| Sidecar revalidates restart relation | `test_recovery_evidence_revalidates_restart_date_relation` |
| Existing multi-day Recovery preserved | Existing Recovery suite passed in full |
| Hash/ledger mutation remains fail-closed | Existing source mutation and post-authorization execution contradiction tests passed |
| Exact authorized target only | Existing initialization/prep exact-pair tests passed |
| Normal rollover preserved | Full 88-test rollover suite passed |
| Source state/artifact unchanged | Equality lifecycle test compares source bytes before/after authorization and rollover preview |
| Schema/lifecycle unchanged | No schema constants or rollover lifecycle files changed |

## Commands actually run

```text
python -m pytest tests/test_runbook_recovery.py -q -k "missed_operating_day or restart_data_date_before_source_trade_date or revalidates_restart_date_relation"
6 passed, 27 deselected in 21.06s

python -m pytest tests/test_runbook_recovery.py -q
33 passed in 124.50s

python -m pytest tests/test_runbook_day_rollover.py -q
88 passed in 133.23s

python -m py_compile core/runbook_recovery.py core/runbook_day_rollover.py
PASS

git diff --check
PASS
```

An initial full Recovery invocation reached the 120-second command timeout without a test failure payload. It was rerun with a sufficient timeout and completed with 33 passing tests. A first focused run exposed only a duplicate-key bug in the new test helper (`3 passed, 2 failed`); the helper was corrected and all focused/full tests then passed.

## Policy implementation review

- `_restart_policy_violations()` is the shared SSOT for trading-day validation, exact next-trading-day pairing, chronological relation, and equality-only execution-commit prohibition.
- Preview maps shared violations to its established reason taxonomy.
- Evidence validation maps the same violations to immutable-sidecar validation reasons.
- `_execution_gap()` remains the ledger SSOT. For equality its canonical gap is exactly `[source_trade_date]`.
- `_has_execution_commit_evidence()` treats a commit report state reference or PASS `execution_commit` idempotency record as evidence.
- Validation independently confirms that the source still classifies as `ACTIVE_INCOMPLETE` without using the Recovery disposition itself.
- Existing sidecar schema version, disposition, source/latest/calendar SHA256 fields, target status, confirmation set, and create-only authorization are unchanged.

## External and protected state evidence

- No DB or schema write was performed.
- No actual execution ledger was changed.
- No Notion or broker command was executed.
- No operational Recovery preview/authorize/rollover was executed.
- No package installation occurred.
- No commit, push, branch change, reset, checkout, clean, or stash occurred.
- The pre-existing `outputs/backtest_log.db` modification was not touched.

## Tests not run

The repository-wide pytest suite was not run. The mandatory Recovery and rollover suites, totaling 121 passing tests, directly cover the modified contract and its downstream consumer. Pre-existing inaccessible temp directories and unrelated dirty workstreams remain outside this task.

## Review command

```text
git diff -- core/runbook_recovery.py tests/test_runbook_recovery.py docs/operations/runbook_recovery_contract.md docs/work_results/RECOVERY-RESTART-1_Result.md docs/work_results/RECOVERY-RESTART-1_Review_Evidence.md
```

# ACCT-01D Account Isolation Evidence — Review Evidence

- Review state: `PASS`
- D base: `0da9b0f906f477613ee72e4fdcd0c6fa8d5d7c14`
- D implementation: `tests/test_acct01d_isolation.py`
- Production source changes: none.

## Acceptance criteria

| Criterion | Assessment | Evidence |
| --- | --- | --- |
| A write does not mutate B or legacy | PASS | Parametrized D isolation writer test plus SHA-256 snapshots. |
| B write does not mutate A or legacy | PASS | Same parametrized test in the reverse direction. |
| A/B read isolation | PASS | Explicit A/B reads, omitted configured-default read, and cross-root rejection. |
| Output namespace isolation | PASS | Replay JSON/Markdown are beneath A only; B target is rejected. |
| Legacy read-only boundary | PASS | Explicit `paper_default` legacy read works; non-default legacy read fails. |
| Cross-account mismatch fails closed | PASS | B log under A context and B output directory under A context both fail. |
| Missing/partial root has no creation/repair | PASS | Writer and replay output cases preserve pre-call tree snapshot. |
| A/B/C contract regression has no regression | PASS | D-3 ACCT-01 superset: 319 passing nodes. |
| Operational state/DB/Notion unchanged | PASS | Test writes were tmp-path only; project market DB was read-only; no external calls were made. |
| Migration not performed | PASS | No paper-default init/migration or legacy data movement. |
| No unresolved D-SCOPE or A/B/C-REGRESSION failure | PASS | Only the three pre-recorded unrelated CLI mock failures remain. |

## Validation

- D-2: D isolation `7 passed`; B/C focused regression `24 passed`.
- D-3: ACCT-01 regression superset `319 passed, 3 failed`.
- The three failures are `UNRELATED`, not new, and do not require reviewed-base
  reproduction: their mock signatures reject the pre-existing `trade_date`
  keyword in `scripts.paper.handle_prepare_data`.
- An initial isolated-worktree market-DB collection issue was resolved by a
  read-only `STOCK_SCREENER_MARKET_DB` setting.  An initial shared pytest-temp
  permission issue was resolved by an isolated `--basetemp`.
- Changed test compilation and `git diff --check`: PASS.
- Full-repository pytest: not run by design.

## Reviewer focus

- Confirm the D test's temporary A/B/legacy roots and SHA-256 tree comparison
  are sufficient evidence of non-contamination.
- Confirm the known prepare-data mock-signature nodes remain out of ACCT-01D
  scope.
- Final reviewer verdict: ACCT-01D PASS; ACCT-01A/B/C/D closeout is approved.

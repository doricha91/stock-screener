# MFU-ML1-2A Result Evidence

Review status: PENDING_CHATGPT_REVIEW

## Baseline and scope

- Worktree: C:/Users/inocha/AppData/Local/Temp/StockScreener_MFU_ML1_2_20260927
- Branch: detached HEAD (gemini_cli_update lineage)
- Base and resulting HEAD: 808d14cb889a90ebbbe90b307acb640b4dc8198c
- Initial git status --short: EMPTY / CLEAN.
- AGENTS.md and docs_chatGPT_work/00_DEVELOPMENT_WORKFLOW.md applied.
- Task: MFU-ML1-2A_VERSIONED_PROFILE_BINDING_FROZEN_IDENTITY_FRESH_ELIGIBILITY
- Original root D:/python/StockScreener: read-only; no edits/sync.

## Implemented

Versioned exact strategy/universe references and registry resolution; detached
resolved semantic evidence plus deterministic SHA-256 digest; version-aware
frozen runbook state; integrity/drift validation before state writes/stage entry;
immutable existing frozen evidence; pure/read-only fresh eligibility and
prepare-first request validation. New helpers isolate business validation from
scripts; existing bootstrap writer is unchanged.

### Changed files

- core/paper_account_profile.py: v2 explicit reference fields and strict schema checks; v1 fallback retained.
- core/paths.py: canonical binding-registry path.
- core/paper_account_binding.py: registry, resolver, policy evidence, digest, integrity/drift validation.
- core/paper_account_fresh.py: read-only eligibility and request validation.
- scripts/runbook_state.py: separate binding-aware context, v2 state, serialization and write/entry guards; direct CLI import support.
- tests/test_ml1_2a_binding_fresh.py: 68 synthetic targeted cases.
- tests/test_runbook_state.py: expected supported-schema diagnostic updated.
- docs/TRD/mfu_ml1_2a_binding_frozen_fresh.md: contract and ownership documentation.

Patch includes all eight files including previously untracked source/test/doc;
evidence, caches and temporary artifacts are excluded. 1011 additions / 12 deletions.

### Schema before / after

Before: paper_account_profiles.v1, string refs, no explicit versions; runbook_state.v1
with three-field FrozenRunbookContext.
After: opt-in paper_account_profiles.v2 requires strategy_profile/strategy_version
and universe_profile/universe_version. Registry paper_binding_profiles.v1 contains
exact ID/version/content rows; resolved paper_account_binding.v1 contains semantics
and digest. New runs against the v2 registry use runbook_state.v2 and the derived
BindingFrozenRunbookContext. Legacy v1 context remains three fields even through
__dict__ and dataclasses.asdict. Execution contract v3 and runbook ID unchanged.
No production account/profile registry was created or modified.

### Synthetic binding example

Account: synthetic_a; strategy synthetic_strategy/v1 with entry_period=12 and
rsi_weight=1; universe synthetic_universe/v1 with canonical symbols AAA, BBB.
Digest: sha256:d0ae0d53237aeeecd86ff2dbd529b5ae925b327a79f25bd94695dc7ef28206fc
Full resolved evidence: MFU-ML1-2A_Synthetic_Binding.json (synthetic refs only).
Account ID, initial_cash, display metadata and other registry entries are excluded.

## Validation commands and results

All tests use temporary synthetic artifacts; no operational DB/workspace/Notion
fixtures. Base command directory is the worktree above. Python environment was
HANTU311_64. Each --basetemp below is under C:/Users/inocha/AppData/Local/Temp/.

1. python -m pytest tests/test_ml1_2a_binding_fresh.py -q
   - 51 SETUP ERRORS: existing pytest-of-inocha directory access denied (WinError 5).
   - ENVIRONMENT, not contract assertions; retried once with explicit isolated basetemp and escalation.
2. python -m pytest tests/test_ml1_2a_binding_fresh.py -q --basetemp=C:/Users/inocha/AppData/Local/Temp/ml1_2a_targeted_20260929_01 --tb=short
   - 51 passed in 3.88s; pytest cache permission warning. Later runs disable cacheprovider.
3. python -m pytest tests/test_ml1_2a_binding_fresh.py -q -p no:cacheprovider --basetemp=C:/Users/inocha/AppData/Local/Temp/ml1_2a_targeted_20260929_02 --tb=short
   - 61 passed in 5.98s, including frozen rewrite protection and binding-aware recovery.
4. python -m pytest tests/test_paper_account_profile.py tests/test_runbook_state.py tests/test_runbook_recovery.py tests/test_operational_no_trade_gap.py tests/test_operational_gap_recovery.py tests/test_runbook_day_rollover.py tests/test_runbook_retirement.py -q -p no:cacheprovider --basetemp=C:/Users/inocha/AppData/Local/Temp/ml1_2a_focused_20260929_01 --tb=short
   - 263 passed, 7 failed in 63.68s.
   - CURRENT-SCOPE: one expected-schema diagnostic assertion; five direct CLI import failures; one closure/adapter regression from a new optional field leaking into legacy context.__dict__.
   - Fixed direct CLI root import, adjusted schema diagnostic test, and retained the exact legacy context type while adding a separate derived binding-aware type.
5. python -m pytest tests/test_ml1_2a_binding_fresh.py tests/test_runbook_state.py tests/test_operational_gap_recovery.py::test_adapter_rejects_closed_tampered_live_and_calendar_invalid_sources -q -p no:cacheprovider --basetemp=C:/Users/inocha/AppData/Local/Temp/ml1_2a_closure_20260929_01 --tb=short
   - 100 passed in 8.52s. All seven preceding failures resolved; no unrelated fixes or base reproduction.
6. python -m pytest tests/test_ml1_2a_binding_fresh.py tests/test_runbook_stage_b_recovery.py tests/test_failed_no_trade_closure.py -q -p no:cacheprovider --basetemp=C:/Users/inocha/AppData/Local/Temp/ml1_2a_final_20260929_01 --tb=short
   - 111 passed in 13.93s: final 68 targeted cases + 43 direct context-consumer recovery/closure regressions.
   - Expanded only because legacy __dict__ consumers were implicated and fresh metric/mode checks were added.
7. python -m py_compile core/paper_account_profile.py core/paths.py core/paper_account_binding.py core/paper_account_fresh.py scripts/runbook_state.py
   - PASS.
8. git diff --check
   - PASS. Git only emitted normal LF/CRLF conversion notices.
9. git apply --reverse --check docs/work_results/MFU-ML1-2A_Changes.patch
   - PASS; patch matches actual tracked and untracked worktree files.

No remaining test failures. Full pytest/backtest/optimizer were not run: no runtime
strategy/position/return calculation changed; focused scope covers changed contracts.
No external commands, network fixtures, DB migrations or operational account writes.

## Round-trip / legacy / recovery evidence

Targeted tests prove state save/load/save/reload byte equality, unchanged runbook ID,
legacy field omission including __dict__/asdict, missing/tampered binding rejection,
drift rejection with destination bytes unchanged, refusal to overwrite an existing
frozen binding even after canonical profile change, historical readability, and
binding-aware recovery authorization validation/rollover with source state untouched.

## Remaining risks and deferred ownership

- ML1-2B: actual make_config/screener/Daily Plan injection, account universe consumption,
  runtime/frozen consumed-value comparison and broader A/B non-contamination.
- ML1-3: bootstrap account_id seed repair, actual prepare/create/resume and ready-marker-last.
  The unchanged real bootstrap writer produces blank seed account_id and is intentionally rejected.
- ML1-4: shared refresh vs account consume-only, actual market readiness.
- ML1-5: sequential multi-account lifecycle/isolation validation.
- Code baseline: no generic provider added. SHA recorded here as audit evidence only;
  runtime code-SHA compatibility remains unresolved, separate from semantic digest.
- Registry v2 is opt-in and strict for all its entries. No live activation/registration occurred.
- Historical state reading validates frozen integrity independently of today's profile;
  current binding validation applies at new-contract write/entry boundaries.
- Corrupt/unattributable lifecycle evidence fails closed; no manual cleanup/migration performed.

## Final status

ML1-2A implemented: YES (candidate for independent review)
Runtime strategy injection: NO
Runtime account universe selection: NO
Fresh account actual prepare/write: NO
Bootstrap seed writer modification: NO
Source modification: YES
Operational mutation: NO
Test execution: YES - synthetic targeted/focused only
Commit / push / PR: NO
Notion write / market refresh: NO
Operational runbook/stage execution / paper account creation: NO
Review bundle: CREATED
Review status: PENDING_CHATGPT_REVIEW

Runtime consumer integration remains pending ML1-2B; no next phase started.

## Final Git evidence

```text
 M core/paper_account_profile.py
 M core/paths.py
 M scripts/runbook_state.py
 M tests/test_runbook_state.py
?? core/paper_account_binding.py
?? core/paper_account_fresh.py
?? docs/TRD/mfu_ml1_2a_binding_frozen_fresh.md
?? docs/work_results/MFU-ML1-2A_Changes.patch
?? docs/work_results/MFU-ML1-2A_Changes_Stat.txt
?? docs/work_results/MFU-ML1-2A_Result.md
?? docs/work_results/MFU-ML1-2A_Review.md
?? docs/work_results/MFU-ML1-2A_Synthetic_Binding.json
?? tests/test_ml1_2a_binding_fresh.py
```

Tracked diff stat (new files are included in Changes.patch/Changes_Stat):

```text
 core/paper_account_profile.py | 27 ++++++++++++++
 core/paths.py                 |  4 ++
 scripts/runbook_state.py      | 86 +++++++++++++++++++++++++++++++++++++------
 tests/test_runbook_state.py   |  2 +-
 4 files changed, 107 insertions(+), 12 deletions(-)
```

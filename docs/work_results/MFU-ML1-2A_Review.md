# MFU-ML1-2A Review Evidence

Status: PENDING_CHATGPT_REVIEW
Base / HEAD: 808d14cb889a90ebbbe90b307acb640b4dc8198c
Worktree: C:/Users/inocha/AppData/Local/Temp/StockScreener_MFU_ML1_2_20260927 (detached)

| AC | Implementation and direct evidence | Candidate result |
| --- | --- | --- |
| 1 Exact ID/version | paper_account_binding resolver + test_exact_resolve_and_evidence | PASS |
| 2 No new-contract fallback | strict v2 refs/registry; invalid_reference_no_fallback, missing_registry_unknown_account, unknown_new_account_state_cannot_fall_back | PASS |
| 3 Full resolved evidence/digest | semantics + digest; Synthetic_Binding.json; validate_binding | PASS |
| 4 Metadata/non-account non-impact | test_digest_metadata_order_and_account_nonimpact; integral number and symbol normalization | PASS |
| 5 Frozen round-trip | test_state_round_trip_unchanged_identity; load validates v2 binding | PASS |
| 6 Legacy no migration/rewrite | test_legacy_omission_and_no_migration, legacy_context_dict_and_asdict_have_no_new_field; existing context loaded first | PASS |
| 7 Drift/tamper fail-closed | semantic_change_changes_digest, drift_blocks_save_and_stage_start_without_write, frozen_missing_tamper_and_schema_downgrade_blocked, existing_frozen_state_cannot_be_replaced_after_profile_change | PASS |
| 8 Fresh classifications | matrix below; validate_prepare_first_request is read-only | PASS |
| 9 Runbook ID | test_state_round_trip_unchanged_identity + existing test_runbook_state | PASS |
| 10 NTG/recovery | focused run 263 passes + all 7 failures resolved by 100-pass closure; binding-aware recovery test; 43 additional recovery/closure tests pass | PASS |
| 11 Runtime unchanged | no diff in config_factory, screener, daily_plan_generator, universe_manager | PASS |
| 12 Bootstrap/prepare write unchanged | no diff in paper_account_bootstrap, wrappers; unmodified bootstrap blank seed explicitly rejected | PASS |
| 13 Targeted/static | final targeted 68 + focused consumers 43 = 111 pass; compile/diff check; reverse patch check | PASS |
| 14 Operational/root unchanged | all edits confined to approved isolated worktree; synthetic test paths; no operational CLI/write | PASS |

## Fresh eligibility matrix

| Input | Expected and observed | Tests |
| --- | --- | --- |
| Complete synthetic seed + valid refs + no history | Eligible, VALIDATED_NOT_PREPARED; tree bytes unchanged | fresh_eligible_no_mutation |
| Ledger rows / position rows | Blocked | execution_or_position_history_blocked |
| Completed / NO_ACTION / READY state | Non-fresh | run_and_recovery_history_never_fresh |
| Failed state / recovery sidecar / hashed gap evidence | Non-fresh | run_and_recovery_history_never_fresh |
| Missing bootstrap / unexplained artifact | Blocked | partial_and_context_conflicts_blocked |
| Blank or wrong account ID / currency / cash / date / NaN / nonzero position | Blocked | invalid_bootstrap_blocked |
| Cash ratios / realized map / PnL percentage inconsistent | Blocked | bootstrap_initial_metrics_must_agree |
| Existing production bootstrap behavior (synthetic tmp only) | Blank seed account_id rejected, writer untouched | unmodified_bootstrap_blank_seed_is_rejected |
| Wrong authoritative workspace/root/date / tampered expected binding | Blocked | partial_and_context_conflicts_blocked |
| Current-state trade history | Blocked | partial_and_context_conflicts_blocked |
| Other account valid recovery evidence | No effect on eligibility | fresh_other_account_history_nonimpact |
| Live account | Blocked from fresh paper path | live_account_not_fresh_paper_eligible |

## Safety and version boundaries

Strategy whitelist rejects safety/hedge/capital/routing overrides and unsupported keys.
No registered production profile was invented. shared_policy is a detached SSOT
snapshot without account strategy injection; this is contract evidence only.

Legacy FrozenRunbookContext remains exactly three fields. A separate derived type
contains binding only in runbook_state.v2. All context/ref/hash mechanisms stay in
the existing state/recovery system. No new persistent ordered keys or run identity.

New-state creation, state write and stage/lifecycle entry re-resolve current binding.
Existing frozen state cannot be overwritten with a different binding. Reading old
states never performs migration or current-profile reinterpretation.

Code baseline audit is in this bundle. No runtime Git provider or code-SHA recovery
policy was invented. This remains a deferred review item rather than implicit
permission to continue a run under arbitrary changed code.

## Failure handling

Initial pytest setup permission errors were ENVIRONMENT and rerun in a new explicit
isolated basetemp with escalation. Cacheprovider was disabled after a cache permission
warning. Seven focused failures were CURRENT-SCOPE; all were fixed and revalidated.
No remaining failures; no unrelated production changes or redundant full-suite runs.
Exact commands/results: MFU-ML1-2A_Result.md.

## Review bundle

- MFU-ML1-2A_Result.md
- MFU-ML1-2A_Review.md
- MFU-ML1-2A_Changes.patch (complete source/test/TRD diff, evidence excluded)
- MFU-ML1-2A_Changes_Stat.txt
- MFU-ML1-2A_Synthetic_Binding.json

Independent ChatGPT review required before commit/push or ML1-2B.

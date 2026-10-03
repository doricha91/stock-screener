# MFU-ML1-2A-R1 Result Evidence

Review status: PENDING_CHATGPT_REVIEW

## Baseline and scope

- Task: MFU-ML1-2A-R1_POLICY_OWNERSHIP_SEMANTIC_DIGEST_FAIL_CLOSED_REVISION
- Worktree: C:/Users/inocha/AppData/Local/Temp/StockScreener_MFU_ML1_2_20260927
- Branch: detached HEAD
- Base / HEAD: 808d14cb889a90ebbbe90b307acb640b4dc8198c
- Starting state: the uncommitted reviewed ML1-2A patch matched the original Changes patch by reverse apply check.
- Scope: close only the three independent-review findings. No runtime binding injection, active-regime selection, bootstrap writer, operational profile or account activation was performed.

## Finding closure

### MAJOR false semantic drift: RESOLVED

Binding evidence now separates strategy source reference/content, canonical
effective_strategy_base, regime_policy, non-overridable shared_policy, and
universe source reference/content.

The semantic digest hashes effective_strategy_base, regime_policy, shared_policy,
universe content and account type/currency. Exact strategy/universe references are
frozen provenance and compared separately by assert_binding_matches.

False-drift evidence:

    default entry_period=12 + profile entry_period=12 -> effective=12
    default entry_period=20 + profile entry_period=12 -> effective=12
    semantic digest in both cases:
    sha256:5a89f716b58ebe41b1790cdc1d98f45e2281ee6066da707471bc9d65e079fcc6

The targeted test also proves that changing an unoverridden default changes the
digest, and changing only a profile reference with identical semantics preserves
the digest but fails the separate identity comparison.

### MINOR v2 unknown fields: RESOLVED

paper_account_profiles.v2 entries have an explicit top-level field allowlist.
Unknown, misspelled and attempted safety-policy fields fail closed. The v1 loader
retains its prior permissive behavior.

### MINOR unexplained lifecycle artifact: RESOLVED

Canonical history/lifecycle directories now reject non-JSON files, unexpected
extensions, malformed JSON and JSON without attributable account identity.
Only valid JSON evidence proving another account is ignored for the current account.
The validator remains read-only.

## Ownership map

    strategy:
      entry/exit/indicator periods, score threshold, strategy weights,
      trailing/switching parameters, rebalance frequency

    regime_policy:
      regime classifier switches/thresholds, MIN_MODE_MAINTAIN_DAYS,
      REGIME_RULES with only target_cash_ratio, SWITCHING_PREMIUM,
      trailing_stop_multiplier and weights overlays

    shared_policy:
      risk_per_trade, position caps, hedge policy, benchmark symbol

The three base ownership sets are disjoint and checked at import. Strategy profile
parameters can use only strategy-owned keys. Runtime precedence is frozen as:

    strategy defaults
    -> strategy profile override
    -> effective_strategy_base
    -> active regime overlay (ML1-2B runtime responsibility)

## Changed files and symbols

R1 source/test/TRD revisions:

- core/paper_account_binding.py: ownership sets and validators; _resolved_policy;
  _semantic_payload; effective semantic digest; separate reference identity drift.
- core/paper_account_profile.py: VERSIONED_ACCOUNT_FIELDS and v2 unknown-field rejection.
- core/paper_account_fresh.py: lifecycle artifact classification and account attribution.
- tests/test_ml1_2a_binding_fresh.py: ownership/digest/identity/v2/fresh regressions.
- docs/TRD/mfu_ml1_2a_binding_frozen_fresh.md: revised ownership, precedence,
  digest and fail-closed contract.

The complete base-relative patch also contains the previously reviewed ML1-2A
serializer/path/state changes. No new change was made to those accepted symbols.

## Validation

Executed:

1. Initial targeted revision run:
   python -m pytest tests/test_ml1_2a_binding_fresh.py -q -p no:cacheprovider
   --basetemp=C:/Users/inocha/AppData/Local/Temp/ml1_2a_r1_targeted_20260930_01
   --tb=short
   - 47 passed, 34 failed.
   - CURRENT-SCOPE single cause: MIN_MODE_MAINTAIN_DAYS was not classified.
   - It is consumed as regime transition-duration policy and was assigned to
     regime_policy; no unrelated change was made.

2. Targeted closure runs:
   - 81 passed after ownership classification.
   - 82 passed after adding the unsupported-overlay regression.
   - Final canonical-order run: 82 passed in 20.16s.

3. Focused compatibility regression:
   python -m pytest tests/test_paper_account_profile.py tests/test_runbook_state.py
   tests/test_runbook_recovery.py tests/test_operational_no_trade_gap.py
   tests/test_operational_gap_recovery.py tests/test_runbook_day_rollover.py
   tests/test_runbook_retirement.py tests/test_failed_no_trade_closure.py
   tests/test_runbook_stage_b_recovery.py -q -p no:cacheprovider
   --basetemp=C:/Users/inocha/AppData/Local/Temp/ml1_2a_r1_focused_20260930_01
   --tb=short
   - 313 passed in 228.08s.

4. python -m py_compile core/paper_account_profile.py core/paths.py
   core/paper_account_binding.py core/paper_account_fresh.py scripts/runbook_state.py
   - PASS.

5. git apply --reverse --check docs/work_results/MFU-ML1-2A-R1_Changes.patch
   - PASS after final patch generation.

6. git diff --check
   - PASS after final evidence generation.

No full repository pytest, backtest or optimizer was run. This revision changes
binding evidence/validation rather than trading calculations or runtime strategy
consumption; targeted and direct lifecycle consumers form the relevant scope.

## Scope containment

- core/config_factory.py: no diff
- screener/screener.py: no diff
- core/daily_plan_generator.py: no diff
- core/universe_manager.py: no diff
- core/paper_account_bootstrap.py: no diff
- ops/runbook_wrappers/: no diff
- Runtime strategy injection: NOT PERFORMED
- Runtime account universe selection: NOT PERFORMED
- Active regime selection/application: NOT PERFORMED
- Fresh actual prepare/create/resume: NOT PERFORMED
- Operational account/profile/market/Notion mutation: NOT PERFORMED

## Remaining risks and deferred items

- ML1-2B must consume effective_strategy_base, select the active regime overlay,
  and verify the actual consumed runtime values.
- Shared-snapshot as-of universe membership and lineage remain the later Stage A
  runtime freeze responsibility.
- Code baseline compatibility remains separate from the semantic binding digest.
- Existing bootstrap blank account_id writer behavior remains ML1-3 scope.

## Review bundle

- MFU-ML1-2A-R1_Result.md
- MFU-ML1-2A-R1_Review.md
- MFU-ML1-2A-R1_Changes.patch
- MFU-ML1-2A-R1_Changes_Stat.txt
- MFU-ML1-2A-R1_Synthetic_Binding.json

The original ML1-2A review bundle was retained unchanged as historical evidence.


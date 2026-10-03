# MFU-ML1-2A: versioned binding, frozen state, and fresh eligibility

## Scope and activation

This contract resolves and freezes configuration evidence. It does not inject
strategy parameters into make_config/screener/Daily Plan or change runtime universe
selection. Runtime consumption and pre-plan consumed-value verification belong to
ML1-2B. No operational account or production profile is registered by this change.

## Account and registry schema

Existing paper_account_profiles.v1 loading/default fallback remains the legacy
path. paper_account_profiles.v2 requires strategy_profile + strategy_version and
universe_profile + universe_version on every entry. Versions are explicit strings;
there is no latest lookup. V2 account entries reject unknown top-level fields,
including misspelled or attempted safety override fields, while v1 retains its
existing permissive compatibility. Unknown schema, missing references, unknown
account, unknown registry version and unsupported parameters fail closed.

The canonical registry is config/paper_binding_profiles.json, resolved through
core.paths.paper_binding_registry_path. It is not created automatically. Schema:

```json
{
  "schema_version": "paper_binding_profiles.v1",
  "strategy": [{"id": "synthetic_strategy", "version": "v1",
                "content": {"parameters": {"entry_period": 12}}}],
  "universe": [{"id": "synthetic_universe", "version": "v1",
                "content": {"kind": "symbols", "symbols": ["AAA", "BBB"]}}]
}
```

This is a synthetic illustration, not a production configuration. An alternate
universe definition is {"kind":"shared_snapshot"}; its actual as-of membership
remains the later runtime integration's responsibility. Unknown universe fields
are rejected. Symbol sets are sorted and duplicate/invalid symbols rejected.

The strategy allowlist is deliberately limited to existing indicator periods,
weights, score/switching/trailing parameters and rebalance frequency. Risk,
capital, hedge and unrelated safety overrides, unknown keys, nonfinite numbers,
negative weights and noninteger periods are rejected. No defaults are invented:
make_config supplies current strategy defaults and validated profile parameters
override them to form effective_strategy_base.

## Resolved evidence and digest

core.paper_account_binding.resolve_account_binding returns paper_account_binding.v1
with provenance, semantics and digest. Semantics contain account type/currency,
exact refs, resolved strategy/universe source content, effective_strategy_base,
regime_policy and shared_policy. Strategy-owned keys occur only in the effective
strategy base. Regime classifier/overlay definitions occur only in regime_policy.
Shared policy contains only non-overridable risk, position-cap, hedge and benchmark
policy. MIN_MODE_MAINTAIN_DAYS is regime-owned because it controls regime transition
duration and is not a strategy profile override.

The frozen precedence contract is strategy defaults followed by strategy profile
overrides. At runtime, the active REGIME_RULES overlay follows that effective base;
actual regime selection and runtime injection remain ML1-2B responsibilities.

sha256_payload is reused. The digest input is effective_strategy_base, regime_policy,
shared_policy, universe content and account type/currency. Source references remain
frozen identity evidence and are compared separately, so changing an exact ID/version
is rejected even if its semantics happen to match. A strategy-overridden default may
change without false drift; an unoverridden default or effective policy change alters
the digest. Equivalent integral numeric values and universe ordering are normalized.
Account ID is checked separately through frozen runbook identity. Other accounts,
display names, Notion profile, timestamps, paths, bootstrap cash, registry order,
descriptive regime text and logging switches are excluded. Existing config objects
are never mutated.

## Frozen state and compatibility

Legacy runbook_state.v1 keeps the original three-field FrozenRunbookContext,
including its __dict__/asdict form. No new field is synthesized on load or save.

A new run created against a v2 account registry uses runbook_state.v2 and
BindingFrozenRunbookContext (the existing context extended with binding).
The ID remains account_id + DATA_DATE + TRADE_DATE; execution contract v3 is unchanged.
Deserializer verifies binding presence/shape/digest; validate_state also verifies
integrity. save_state, start_stage and lifecycle entry compare new-state binding
with the current canonical resolver. save_state rejects replacing existing frozen
identity/binding or changing an existing file between v1 and v2.

Historical reads validate internal evidence, without looking up today's registry.
Already-existing legacy contexts are loaded before resolving a prospective new
state, so profile registration cannot silently migrate progressed/completed runs.
Recovery still uses its existing source context and file hashes. A synthetic
binding-aware recovery/rollover test confirms the full frozen evidence round-trip.
No recovery schema or identity migration is introduced.

There is no shared code-version provider; code baseline audit is recorded in the
review bundle only. Runtime code-SHA compatibility remains an unresolved design
item, separate from the binding digest. No Git subprocess/provider was added.

## Read-only first-run validation

core.paper_account_fresh.validate_prepare_first_request checks canonical profile,
binding, PAPER/TEST mode, account paths, authoritative workspace, calendar/date pair,
bootstrap completeness and content, identity/currency/cash consistency, empty
execution/position/current-state evidence, and absence of lifecycle/recovery/gap
history. It reuses existing snapshot identity, bootstrap manifest, state loading,
calendar and lifecycle directory contracts. Non-JSON, unexpected-extension,
unparseable or account-unattributable lifecycle evidence fails closed. Only valid
JSON evidence that proves a different account is excluded from the current account.

DATA_DATE equals the seed effective date; TRADE_DATE must be the calendar's next
trading day. Missing bootstrap files, unexpected account files/directories,
completed/NO_ACTION/failed/READY runs, recovery evidence, nonempty ledgers,
identity or cash mismatch, and invalid headers/values are non-fresh. Any run
history makes a new fresh request ineligible; duplicate prepared-request reuse
is a separate ML1-3 responsibility.

A successful result says VALIDATED_NOT_PREPARED, never ready. It performs no writes,
repairs, market refresh, ready-marker creation or account initialization. Bootstrap's
known blank account_id seed is rejected, not repaired. The writer fix and actual
multi-file prepare/resume belong to ML1-3. Market readiness is a separate later gate.

## Tests

See tests/test_ml1_2a_binding_fresh.py for synthetic-only ownership, effective
strategy, semantic/identity drift, v2 unknown-field, frozen state, recovery and
fresh lifecycle coverage. Existing profile/state/recovery/NTG/rollover/retirement
and Stage B recovery/failed closure tests form the focused regression scope. Review
artifacts record exact commands and failures/resolutions.

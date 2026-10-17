"""Per-call Paper Daily Plan runtime derived from a frozen account binding."""
from __future__ import annotations

import copy
from typing import Any

from core.config_factory import get_regime_config, make_config
from core.paper_account_binding import (
    BindingError,
    assert_binding_matches,
    resolve_account_binding,
    validate_binding,
)
from core.paper_account_profile import (
    VERSIONED_ACCOUNT_PROFILE_SCHEMA,
    load_paper_account_profiles,
)


def resolve_runtime_binding(
    account_id: str,
    *,
    frozen_binding: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Resolve current binding and, when supplied, prove it matches frozen evidence."""
    profiles = load_paper_account_profiles(allow_missing=True)
    if profiles.schema_version != VERSIONED_ACCOUNT_PROFILE_SCHEMA:
        if frozen_binding is not None:
            raise BindingError("frozen binding requires versioned account profiles")
        return None
    current = resolve_account_binding(account_id, profiles=profiles)
    if frozen_binding is not None:
        assert_binding_matches(frozen_binding, current)
        return copy.deepcopy(frozen_binding)
    validate_binding(current)
    return copy.deepcopy(current)


def build_runtime_config(
    binding: dict[str, Any],
    *,
    active_regime: str,
    start_date: str,
    end_date: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Assemble account-local config without mutating module-global configuration."""
    validate_binding(binding)
    semantics = binding["semantics"]
    strategy_base = copy.deepcopy(semantics["effective_strategy_base"])
    regime_policy = copy.deepcopy(semantics["regime_policy"])
    shared_policy = copy.deepcopy(semantics["shared_policy"])

    base_config = make_config({}, start_date, end_date)
    base_config.update(strategy_base)
    base_config.update(regime_policy)
    base_config.update(shared_policy)
    base_config["REGIME_RULES"] = copy.deepcopy(regime_policy["REGIME_RULES"])

    rules = regime_policy["REGIME_RULES"]
    applied_regime = active_regime if active_regime in rules else "UNSTABLE"
    applied_overlay = copy.deepcopy(rules.get(applied_regime, {}))
    runtime_config = get_regime_config(active_regime, base_config)

    effective_runtime_strategy = copy.deepcopy(strategy_base)
    for key, value in applied_overlay.items():
        if key == "description":
            continue
        if key == "weights":
            for name, weight in value.items():
                effective_runtime_strategy[f"{name}_weight"] = weight
        else:
            effective_runtime_strategy[key] = value

    evidence = {
        "schema_version": "paper_runtime_binding.v1",
        "binding_digest": binding["digest"],
        "strategy_reference": copy.deepcopy(semantics["strategy"]["reference"]),
        "universe_reference": copy.deepcopy(semantics["universe"]["reference"]),
        "effective_strategy_base": strategy_base,
        "regime_policy": regime_policy,
        "active_regime": active_regime,
        "applied_regime": applied_regime,
        "applied_regime_overlay": applied_overlay,
        "effective_runtime_strategy": effective_runtime_strategy,
        "shared_policy": shared_policy,
        "entry_universe_definition": copy.deepcopy(semantics["universe"]["content"]),
        "requested_entry_universe": [],
        "materialized_entry_universe": [],
        "excluded_symbols": [],
        "managed_symbols": [],
        "existing_holdings_preserved": [],
        "runtime_frozen_validation": "PASS",
    }
    quarterly = semantics.get("quarterly_universe")
    if quarterly is not None:
        evidence.update({
            "universe_profile": quarterly["universe_profile"],
            "universe_version": quarterly["universe_version"],
            "quarterly_artifact": {
                "schema_version": quarterly["schema_version"],
                "version": quarterly["artifact_version"],
                "artifact_hash": quarterly["artifact_hash"],
            },
            "selected_universe_slice": {
                "name": quarterly["slice_name"],
                "symbol_hash": quarterly["slice_hash"],
            },
        })
    validate_runtime_consumption(runtime_config, evidence)
    return runtime_config, evidence


def validate_runtime_consumption(
    runtime_config: dict[str, Any],
    runtime_evidence: dict[str, Any],
) -> None:
    """Fail closed if a consumer config differs from its frozen derived values."""
    for key, expected in runtime_evidence["effective_runtime_strategy"].items():
        if runtime_config.get(key) != expected:
            raise BindingError(f"runtime strategy mismatch: {key}")
    for key, expected in runtime_evidence["shared_policy"].items():
        if runtime_config.get(key) != expected:
            raise BindingError(f"runtime shared policy mismatch: {key}")
    for key, expected in runtime_evidence["regime_policy"].items():
        if runtime_config.get(key) != expected:
            raise BindingError(f"runtime regime policy mismatch: {key}")


def validate_pinned_runtime_evidence(
    pinned: Any,
    current: dict[str, Any],
    *,
    include_materialization: bool,
) -> None:
    """Validate optional prior runtime evidence without migrating older snapshots."""
    if pinned is None:
        return
    if not isinstance(pinned, dict):
        raise BindingError("malformed pinned runtime binding evidence")
    fields = [
        "account_id", "binding_digest", "strategy_reference", "universe_reference",
        "effective_strategy_base", "regime_policy", "shared_policy", "active_regime",
        "applied_regime", "applied_regime_overlay", "effective_runtime_strategy",
        "entry_universe_definition", "runtime_frozen_validation",
    ]
    if include_materialization:
        fields.extend([
            "requested_entry_universe", "materialized_entry_universe", "excluded_symbols",
            "managed_symbols", "existing_holdings_preserved",
        ])
    for field in (
        "universe_profile", "universe_version", "quarterly_artifact", "selected_universe_slice",
    ):
        if field in pinned or field in current:
            fields.append(field)
    for field in fields:
        if pinned.get(field) != current.get(field):
            raise BindingError(f"pinned runtime binding mismatch: {field}")


def record_runtime_universe(
    runtime_evidence: dict[str, Any],
    *,
    requested: list[str],
    materialized: list[str],
    excluded: list[dict[str, str]],
    existing_holdings: list[str],
    managed_symbols: list[str],
) -> dict[str, Any]:
    """Return deterministic runtime evidence after entry-universe materialization."""
    result = copy.deepcopy(runtime_evidence)
    result["requested_entry_universe"] = sorted(set(requested))
    result["materialized_entry_universe"] = sorted(set(materialized))
    result["excluded_symbols"] = sorted(
        ({"symbol": row["symbol"], "reason": row["reason"]} for row in excluded),
        key=lambda row: (row["symbol"], row["reason"]),
    )
    result["existing_holdings_preserved"] = sorted(set(existing_holdings))
    result["managed_symbols"] = sorted(set(managed_symbols))
    return result

"""Exact version binding contracts. This module does not activate runtime profiles."""
from __future__ import annotations

import copy
import json
import math
import re
from pathlib import Path
from typing import Any

from core.config_factory import make_config
from core.paper_account_profile import (
    PaperAccountProfileConfig, VERSIONED_ACCOUNT_PROFILE_SCHEMA,
    load_paper_account_profiles, resolve_paper_account_profile,
)
from core.paths import paper_binding_registry_path
from core.stage_a_asof_contract import sha256_payload

REGISTRY_SCHEMA = "paper_binding_profiles.v1"
BINDING_SCHEMA = "paper_account_binding.v1"
# These sets define binding ownership.  A key may appear in only one base-policy
# set; REGIME_RULES is the sole, explicit strategy overlay contract.
STRATEGY_PARAMETERS = frozenset({
    "entry_period", "exit_period", "score_threshold", "atr_period", "rsi_period",
    "sma_short_period", "sma_long_period", "bbands_period", "macd_fast_period",
    "macd_slow_period", "dema_short_period", "mfi_period", "rs_lookback",
    "turtle_weight", "rs_weight", "rsi_weight", "sma_weight", "bbands_weight",
    "macd_weight", "bbs_weight", "dema_weight", "obv_weight", "mfi_weight",
    "vol_spike_weight", "trailing_stop_multiplier", "SWITCHING_PREMIUM",
    "ALLOW_PROFIT_SWITCH", "SWITCHING_MAX_COUNT", "REBALANCE_FREQUENCY",
})
REGIME_POLICY_KEYS = frozenset({
    "use_market_regime", "REGIME_SMA_PERIOD", "REGIME_SMA_SHORT_PERIOD",
    "REGIME_ADX_PERIOD", "REGIME_ADX_THRESHOLD", "USE_CIRCUIT_BREAKER",
    "USE_MA_CROSS", "USE_MARKET_BREADTH", "USE_DRAWDOWN_TRIGGER",
    "USE_VIX_BREAKOUT", "CB_DROP_THRESHOLD", "CB_COOLDOWN_DAYS",
    "MA_CROSS_FAST", "MA_CROSS_SLOW", "BREADTH_THRESHOLD",
    "BREADTH_OVERSOLD_THRESHOLD", "DD_LOOKBACK", "DD_THRESHOLD",
    "VIX_MA_PERIOD", "VIX_MULTIPLIER", "MIN_MODE_MAINTAIN_DAYS", "REGIME_RULES",
})
SHARED_POLICY_KEYS = frozenset({
    "risk_per_trade", "max_positions", "max_long_positions", "USE_HEDGE_MODE",
    "HEDGE_TICKERS", "HEDGE_ASSET", "HEDGE_RATIO_BEAR", "HEDGE_RATIO_PANIC",
    "HEDGE_LIQUIDATION_PRIORITY", "MARKET_BENCHMARK_SYMBOL",
})
REGIME_OVERLAY_KEYS = frozenset({
    "target_cash_ratio", "SWITCHING_PREMIUM", "trailing_stop_multiplier", "weights",
})
STRATEGY_WEIGHT_NAMES = frozenset(
    key.removesuffix("_weight") for key in STRATEGY_PARAMETERS if key.endswith("_weight")
)
if (STRATEGY_PARAMETERS & SHARED_POLICY_KEYS
        or REGIME_POLICY_KEYS & SHARED_POLICY_KEYS
        or STRATEGY_PARAMETERS & REGIME_POLICY_KEYS):
    raise RuntimeError("binding policy ownership sets must be disjoint")


class BindingError(ValueError):
    pass


def _canonical(value: Any) -> Any:
    """Validate JSON values and normalize equivalent integral numbers."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise BindingError("nonfinite binding value")
        return int(value) if value.is_integer() else value
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    if isinstance(value, dict) and all(isinstance(k, str) for k in value):
        return {k: _canonical(value[k]) for k in sorted(value)}
    raise BindingError("binding must contain JSON values only")


def _reference(profile_id: Any, version: Any) -> dict[str, str]:
    if any(not isinstance(v, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", v)
           for v in (profile_id, version)):
        raise BindingError("malformed profile ID/version")
    return {"id": profile_id, "version": version}


def _content(kind: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BindingError(f"{kind} content must be an object")
    if kind == "strategy":
        if set(value) != {"parameters"} or not isinstance(value["parameters"], dict):
            raise BindingError("strategy requires parameters object")
        return {"parameters": _strategy_parameters(value["parameters"])}
    if value == {"kind": "shared_snapshot"}:
        return dict(value)
    if set(value) != {"kind", "symbols"} or value["kind"] != "symbols":
        raise BindingError("unsupported universe definition")
    symbols = value["symbols"]
    if not isinstance(symbols, list) or not symbols or any(
        not isinstance(s, str) or not re.fullmatch(r"[A-Z0-9][A-Z0-9.^-]*", s) for s in symbols
    ) or len(symbols) != len(set(symbols)):
        raise BindingError("invalid universe symbols")
    return {"kind": "symbols", "symbols": sorted(symbols)}


def load_binding_registry(path: Path | None = None) -> dict[str, Any]:
    with (Path(path) if path is not None else paper_binding_registry_path()).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    _registry_index(payload)
    return payload


def _registry_index(registry: Any) -> dict[tuple[str, str, str], dict[str, Any]]:
    if not isinstance(registry, dict) or registry.get("schema_version") != REGISTRY_SCHEMA:
        raise BindingError("unsupported binding registry schema")
    if set(registry) != {"schema_version", "strategy", "universe"}:
        raise BindingError("malformed binding registry")
    index = {}
    for kind in ("strategy", "universe"):
        rows = registry[kind]
        if not isinstance(rows, list):
            raise BindingError(f"{kind} registry must be a list")
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"id", "version", "content"}:
                raise BindingError("malformed registry entry")
            ref = _reference(row["id"], row["version"])
            key = (kind, ref["id"], ref["version"])
            if key in index:
                raise BindingError("duplicate profile ID/version")
            index[key] = _content(kind, row["content"])
    return index


def _strategy_parameters(value: Any, *, complete: bool = False) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) - STRATEGY_PARAMETERS:
        raise BindingError("unsupported or safety-policy override parameter")
    if complete and set(value) != STRATEGY_PARAMETERS:
        raise BindingError("effective strategy base is incomplete")
    for key, val in value.items():
        if key == "ALLOW_PROFIT_SWITCH":
            if not isinstance(val, bool):
                raise BindingError(f"boolean required: {key}")
            continue
        if key == "REBALANCE_FREQUENCY":
            if not isinstance(val, str) or not val or val.strip() != val:
                raise BindingError(f"nonempty string required: {key}")
            continue
        if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
            raise BindingError(f"invalid strategy parameter: {key}")
        if key.endswith("period") or key == "rs_lookback":
            if val <= 0 or int(val) != val:
                raise BindingError(f"positive integer required: {key}")
        elif key == "SWITCHING_MAX_COUNT":
            if val < 0 or int(val) != val:
                raise BindingError(f"nonnegative integer required: {key}")
        elif val < 0:
            raise BindingError(f"negative strategy parameter: {key}")
    return _canonical(value)


def _regime_policy(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != REGIME_POLICY_KEYS:
        raise BindingError("regime policy is incomplete or contains unknown keys")
    for key, val in value.items():
        if key == "REGIME_RULES":
            if not isinstance(val, dict) or not val:
                raise BindingError("REGIME_RULES must be a nonempty object")
            for regime, overlay in val.items():
                if not isinstance(regime, str) or not regime or not isinstance(overlay, dict):
                    raise BindingError("malformed regime overlay")
                if set(overlay) - REGIME_OVERLAY_KEYS:
                    raise BindingError("unsupported regime overlay key")
                for overlay_key, overlay_value in overlay.items():
                    if overlay_key == "weights":
                        if not isinstance(overlay_value, dict) or set(overlay_value) - STRATEGY_WEIGHT_NAMES:
                            raise BindingError("unsupported regime weight")
                        values = overlay_value.values()
                    else:
                        values = (overlay_value,)
                    if any(isinstance(item, bool) or not isinstance(item, (int, float))
                           or not math.isfinite(item) or item < 0 for item in values):
                        raise BindingError("invalid regime overlay value")
        elif key.startswith("USE_") or key == "use_market_regime":
            if not isinstance(val, bool):
                raise BindingError(f"boolean required: {key}")
        elif isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
            raise BindingError(f"invalid regime policy value: {key}")
        elif (key.endswith("_PERIOD") or key in {
            "CB_COOLDOWN_DAYS", "MA_CROSS_FAST", "MA_CROSS_SLOW", "DD_LOOKBACK",
            "MIN_MODE_MAINTAIN_DAYS",
        }) and (val <= 0 or int(val) != val):
            raise BindingError(f"positive integer required: {key}")
    return _canonical(value)


def _shared_policy(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != SHARED_POLICY_KEYS:
        raise BindingError("shared policy is incomplete or contains unknown keys")
    for key in ("risk_per_trade", "HEDGE_RATIO_BEAR", "HEDGE_RATIO_PANIC"):
        val = value[key]
        if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val) or val < 0:
            raise BindingError(f"invalid shared policy value: {key}")
    for key in ("max_positions", "max_long_positions"):
        val = value[key]
        if isinstance(val, bool) or not isinstance(val, int) or val <= 0:
            raise BindingError(f"positive integer required: {key}")
    if not isinstance(value["USE_HEDGE_MODE"], bool):
        raise BindingError("boolean required: USE_HEDGE_MODE")
    tickers = value["HEDGE_TICKERS"]
    if not isinstance(tickers, (list, tuple)) or not tickers or any(
        not isinstance(item, str) or not item.strip() for item in tickers
    ):
        raise BindingError("HEDGE_TICKERS must contain symbols")
    for key in ("HEDGE_ASSET", "HEDGE_LIQUIDATION_PRIORITY", "MARKET_BENCHMARK_SYMBOL"):
        if not isinstance(value[key], str) or not value[key].strip():
            raise BindingError(f"nonempty string required: {key}")
    return _canonical(value)


def _resolved_policy(strategy_parameters: dict[str, Any]) -> dict[str, dict[str, Any]]:
    base = copy.deepcopy(make_config({}, "", ""))
    for key in ("start_date", "end_date", "initial_capital", "enable_decision_logging"):
        base.pop(key, None)
    for overlay in base.get("REGIME_RULES", {}).values():
        if isinstance(overlay, dict):
            overlay.pop("description", None)
    owned = STRATEGY_PARAMETERS | REGIME_POLICY_KEYS | SHARED_POLICY_KEYS
    unknown = set(base) - owned
    if unknown:
        raise BindingError(f"unclassified binding policy keys: {sorted(unknown)}")
    defaults = {key: base[key] for key in sorted(STRATEGY_PARAMETERS) if key in base}
    effective = {**defaults, **_strategy_parameters(strategy_parameters)}
    return {
        "effective_strategy_base": _strategy_parameters(effective, complete=True),
        "regime_policy": _regime_policy({key: base[key] for key in sorted(REGIME_POLICY_KEYS) if key in base}),
        "shared_policy": _shared_policy({key: base[key] for key in sorted(SHARED_POLICY_KEYS) if key in base}),
    }


def shared_binding_policy() -> dict[str, Any]:
    """Return only non-overridable common policy; strategy/regime have separate SSOTs."""
    return _resolved_policy({})["shared_policy"]


def _semantic_payload(semantics: dict[str, Any]) -> dict[str, Any]:
    return _canonical({
        "account_type": semantics["account_type"],
        "currency": semantics["currency"],
        "effective_strategy_base": semantics["effective_strategy_base"],
        "regime_policy": semantics["regime_policy"],
        "shared_policy": semantics["shared_policy"],
        "universe": semantics["universe"]["content"],
    })


def resolve_account_binding(
    account_id: str, *, profiles: PaperAccountProfileConfig | None = None,
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profiles = profiles if profiles is not None else load_paper_account_profiles(allow_missing=False)
    if profiles.schema_version != VERSIONED_ACCOUNT_PROFILE_SCHEMA:
        raise BindingError("versioned account registry required")
    profile = resolve_paper_account_profile(account_id, config=profiles)
    index = _registry_index(registry if registry is not None else load_binding_registry())
    resolved: dict[str, dict[str, Any]] = {}
    for kind in ("strategy", "universe"):
        ref = _reference(getattr(profile, f"{kind}_profile"), getattr(profile, f"{kind}_version"))
        try:
            content = index[(kind, ref["id"], ref["version"])]
        except KeyError as exc:
            raise BindingError(f"unknown {kind} profile/version: {ref}") from exc
        resolved[kind] = {"reference": ref, "content": content}
    policy = _resolved_policy(resolved["strategy"]["content"]["parameters"])
    semantics = _canonical({
        "account_type": profile.account_type,
        "currency": profile.currency,
        **policy,
        **resolved,
    })
    payload = {"schema_version": BINDING_SCHEMA, "semantics": semantics}
    return {**payload, "digest": sha256_payload(_semantic_payload(semantics))}


def validate_binding(binding: Any) -> None:
    if not isinstance(binding, dict) or set(binding) != {"schema_version", "semantics", "digest"}:
        raise BindingError("binding evidence required")
    if binding["schema_version"] != BINDING_SCHEMA:
        raise BindingError("unsupported binding schema")
    semantics = binding["semantics"]
    if not isinstance(semantics, dict) or set(semantics) != {
        "account_type", "currency", "strategy", "universe", "effective_strategy_base",
        "regime_policy", "shared_policy",
    }:
        raise BindingError("malformed binding semantics")
    for key in ("account_type", "currency"):
        if not isinstance(semantics[key], str) or not semantics[key]:
            raise BindingError(f"binding {key} required")
    for kind in ("strategy", "universe"):
        entry = semantics[kind]
        if not isinstance(entry, dict) or set(entry) != {"reference", "content"}:
            raise BindingError("malformed resolved profile")
        ref = entry["reference"]
        if not isinstance(ref, dict) or set(ref) != {"id", "version"}:
            raise BindingError("malformed resolved reference")
        _reference(ref["id"], ref["version"])
        if _content(kind, entry["content"]) != entry["content"]:
            raise BindingError("noncanonical profile content")
    effective = _strategy_parameters(semantics["effective_strategy_base"], complete=True)
    if effective != semantics["effective_strategy_base"]:
        raise BindingError("noncanonical effective strategy")
    for key, value in semantics["strategy"]["content"]["parameters"].items():
        if effective.get(key) != value:
            raise BindingError("strategy override missing from effective strategy")
    if _regime_policy(semantics["regime_policy"]) != semantics["regime_policy"]:
        raise BindingError("noncanonical regime policy")
    if _shared_policy(semantics["shared_policy"]) != semantics["shared_policy"]:
        raise BindingError("noncanonical shared policy")
    if binding["digest"] != sha256_payload(_semantic_payload(semantics)):
        raise BindingError("binding evidence tamper")


def assert_binding_matches(frozen: Any, current: Any) -> None:
    validate_binding(frozen)
    validate_binding(current)
    for kind in ("strategy", "universe"):
        if frozen["semantics"][kind]["reference"] != current["semantics"][kind]["reference"]:
            raise BindingError(f"{kind} binding identity drift")
    if frozen["digest"] != current["digest"]:
        raise BindingError("binding drift")

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from core.stage_a_asof_contract import (
    StageAAsOfContext,
    sha256_payload,
    validate_config_snapshot,
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _extract_strategy_weights(final_config: dict[str, Any]) -> dict[str, Any]:
    return {
        "turtle": final_config.get("turtle_weight"),
        "rs": final_config.get("rs_weight"),
        "rsi": final_config.get("rsi_weight"),
        "sma": final_config.get("sma_weight"),
        "bbands": final_config.get("bbands_weight"),
        "macd": final_config.get("macd_weight"),
        "bbs": final_config.get("bbs_weight"),
        "dema": final_config.get("dema_weight"),
        "obv": final_config.get("obv_weight"),
        "mfi": final_config.get("mfi_weight"),
        "vol_spike": final_config.get("vol_spike_weight"),
    }


def build_paper_config_snapshot_payload(
    plan_date: str,
    market_state: dict[str, Any],
    final_config: dict[str, Any],
    source: str,
    market_state_write_log: bool,
    universe_metadata: dict[str, Any] | None = None,
    data_date: str | None = None,
    trade_date: str | None = None,
    asof_context: StageAAsOfContext | None = None,
) -> dict[str, Any]:
    weights = _extract_strategy_weights(final_config)
    market_status_summary = {
        "regime": market_state.get("regime"),
        "trade_halted": market_state.get("trade_halted"),
        "target_cash_ratio": final_config.get("target_cash_ratio"),
        "trailing_stop_multiplier": final_config.get("trailing_stop_multiplier"),
        "SWITCHING_PREMIUM": final_config.get("SWITCHING_PREMIUM"),
    }
    final_config_summary = {
        "max_positions": final_config.get("max_positions"),
        "score_threshold": final_config.get("score_threshold"),
        "entry_period": final_config.get("entry_period"),
        "exit_period": final_config.get("exit_period"),
        "rs_lookback": final_config.get("rs_lookback"),
        "trailing_stop_multiplier": final_config.get("trailing_stop_multiplier"),
        "risk_per_trade": final_config.get("risk_per_trade"),
        "target_cash_ratio": final_config.get("target_cash_ratio"),
        "SWITCHING_PREMIUM": final_config.get("SWITCHING_PREMIUM"),
        "ALLOW_PROFIT_SWITCH": final_config.get("ALLOW_PROFIT_SWITCH"),
        "SWITCHING_MAX_COUNT": final_config.get("SWITCHING_MAX_COUNT"),
        "strategy_weights": weights,
    }
    observed_at = asof_context.observed_at if asof_context is not None else datetime.now().astimezone().isoformat(timespec="seconds")
    effective_at = asof_context.trade_date if asof_context is not None else (trade_date or plan_date)
    return {
        "schema_version": 1,
        "plan_date": plan_date,
        "data_date": data_date or plan_date,
        "trade_date": trade_date or plan_date,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "observed_at": observed_at,
        "effective_at": effective_at,
        "producer_source": source,
        "source_revision": sha256_payload(_json_safe(final_config)),
        "capture_mode": "current_day_immutable_config" if asof_context is not None else "legacy_config_snapshot",
        "market_state_write_log": bool(market_state_write_log),
        "market_state": _json_safe(market_state),
        "market_status_summary": _json_safe(market_status_summary),
        "final_config": _json_safe(final_config_summary),
        "full_config": _json_safe(final_config),
        "universe": _json_safe(universe_metadata or {}),
        "notes": [
            "Final config after regime overlay.",
            "Market state computed without market_status_log write.",
            "Universe selection uses quarterly as-of policy for paper daily plan.",
            "Official Stage A reuse is validated by the AS-OF contract when enabled.",
        ],
    }


def save_paper_config_snapshot(
    plan_date: str,
    market_state: dict[str, Any],
    final_config: dict[str, Any],
    output_path: Path,
    archive_dir: Path,
    source: str = "run_paper_daily_plan",
    market_state_write_log: bool = False,
    universe_metadata: dict[str, Any] | None = None,
    data_date: str | None = None,
    trade_date: str | None = None,
    asof_context: StageAAsOfContext | None = None,
    immutable: bool = False,
) -> Path:
    output_path = Path(output_path)
    archive_dir = Path(archive_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    if output_path.exists() and immutable:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        if asof_context is None:
            raise ValueError("asof_context is required for immutable config snapshots")
        validate_config_snapshot(payload, context=asof_context, artifact_path=output_path)
        return output_path

    if output_path.exists():
        archive_name = (
            f"{output_path.stem}_archived_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{output_path.suffix}"
        )
        shutil.copy2(output_path, archive_dir / archive_name)

    payload = build_paper_config_snapshot_payload(
        plan_date=plan_date,
        market_state=market_state,
        final_config=final_config,
        source=source,
        market_state_write_log=market_state_write_log,
        universe_metadata=universe_metadata,
        data_date=data_date,
        trade_date=trade_date,
        asof_context=asof_context,
    )
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path

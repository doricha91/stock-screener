from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo


REQUIRED_STAGE_A_SOURCES = ("market", "indicator", "rs", "universe", "account", "config")
DATA_DATE_SOURCES = frozenset({"market", "indicator", "rs", "account"})


class StageAAsOfContractError(ValueError):
    def __init__(self, reason: str, detail: str, *, source: str | None = None) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail
        self.source = source

    def as_payload(self) -> dict[str, Any]:
        return {
            "blocked": True,
            "reason": self.reason,
            "detail": self.detail,
            "source": self.source,
        }


def _date_value(value: object, field: str) -> date:
    text = str(value or "").strip()
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError as exc:
        raise StageAAsOfContractError(
            "asof_provenance_invalid",
            f"{field} must be YYYY-MM-DD: {text!r}",
        ) from exc


def _datetime_value(value: object, field: str) -> datetime:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise StageAAsOfContractError(
            "asof_provenance_invalid",
            f"{field} must be an ISO-8601 datetime: {text!r}",
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("Asia/Seoul"))
    return parsed


@dataclass(frozen=True)
class StageAAsOfContext:
    account_id: str
    data_date: str
    trade_date: str
    observed_at: str

    @classmethod
    def build(
        cls,
        *,
        account_id: str,
        data_date: str,
        trade_date: str,
        observed_at: str | None = None,
        timezone: str = "Asia/Seoul",
    ) -> "StageAAsOfContext":
        normalized_data = _date_value(data_date, "data_date").isoformat()
        normalized_trade = _date_value(trade_date, "trade_date").isoformat()
        if normalized_trade <= normalized_data:
            raise StageAAsOfContractError(
                "asof_context_mismatch",
                f"trade_date must be after data_date: {normalized_data} -> {normalized_trade}",
            )
        now = datetime.now(ZoneInfo(timezone)).replace(microsecond=0)
        normalized_observed = (_datetime_value(observed_at, "observed_at") if observed_at else now).isoformat()
        return cls(
            account_id=str(account_id),
            data_date=normalized_data,
            trade_date=normalized_trade,
            observed_at=normalized_observed,
        )

    @property
    def historical(self) -> bool:
        return _datetime_value(self.observed_at, "observed_at").date() > _date_value(
            self.trade_date,
            "trade_date",
        )


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def sha256_payload(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _required(payload: Mapping[str, Any], field: str, *, source: str) -> Any:
    value = payload.get(field)
    if value is None or value == "" or value == []:
        raise StageAAsOfContractError(
            "asof_provenance_missing",
            f"{source} provenance is missing required field: {field}",
            source=source,
        )
    return value


def validate_universe_snapshot(
    payload: Mapping[str, Any],
    *,
    context: StageAAsOfContext,
    artifact_path: str | Path | None = None,
) -> dict[str, Any]:
    source = "universe"
    active_symbols = _required(payload, "active_symbols", source=source)
    if not isinstance(active_symbols, list):
        raise StageAAsOfContractError(
            "asof_provenance_invalid",
            "universe active_symbols must be a list",
            source=source,
        )
    effective = str(_required(payload, "effective_as_of", source=source))
    observed_at = str(_required(payload, "observed_at", source=source))
    source_name = str(_required(payload, "source", source=source))
    revision = str(payload.get("source_revision") or payload.get("artifact_hash") or "")
    if not revision:
        _required(payload, "source_revision", source=source)
    capture_mode = str(_required(payload, "capture_mode", source=source))
    if _date_value(effective, "effective_as_of") > _date_value(context.data_date, "data_date"):
        raise StageAAsOfContractError(
            "asof_future_source",
            f"universe effective_as_of {effective} is after data_date {context.data_date}",
            source=source,
        )
    if _datetime_value(observed_at, "observed_at").date() > _date_value(context.trade_date, "trade_date"):
        raise StageAAsOfContractError(
            "asof_future_source",
            f"universe observed_at {observed_at} is after trade_date {context.trade_date}",
            source=source,
        )
    return {
        "source": source_name,
        "effective_as_of": effective,
        "selected_max_date": effective,
        "observed_at": observed_at,
        "revision": revision,
        "artifact_hash": sha256_file(artifact_path) if artifact_path else payload.get("artifact_hash"),
        "capture_mode": capture_mode,
        "validator_result": "PASS",
    }


def validate_config_snapshot(
    payload: Mapping[str, Any],
    *,
    context: StageAAsOfContext,
    artifact_path: str | Path | None = None,
) -> dict[str, Any]:
    source = "config"
    for field, expected in (
        ("data_date", context.data_date),
        ("trade_date", context.trade_date),
    ):
        actual = str(_required(payload, field, source=source))
        if actual != expected:
            raise StageAAsOfContractError(
                "asof_context_mismatch",
                f"config {field} mismatch: {actual} != {expected}",
                source=source,
            )
    observed_at = str(_required(payload, "observed_at", source=source))
    effective_at = str(_required(payload, "effective_at", source=source))
    revision = str(_required(payload, "source_revision", source=source))
    _required(payload, "full_config", source=source)
    if _datetime_value(observed_at, "observed_at").date() > _date_value(context.trade_date, "trade_date"):
        raise StageAAsOfContractError(
            "asof_future_source",
            f"config observed_at {observed_at} is after trade_date {context.trade_date}",
            source=source,
        )
    if _date_value(effective_at, "effective_at") > _date_value(context.trade_date, "trade_date"):
        raise StageAAsOfContractError(
            "asof_future_source",
            f"config effective_at {effective_at} is after trade_date {context.trade_date}",
            source=source,
        )
    return {
        "source": str(payload.get("producer_source") or "paper_config_snapshot"),
        "effective_as_of": effective_at,
        "selected_max_date": context.data_date,
        "observed_at": observed_at,
        "revision": revision,
        "artifact_hash": sha256_file(artifact_path) if artifact_path else payload.get("artifact_hash"),
        "capture_mode": str(payload.get("capture_mode") or "immutable_config_snapshot"),
        "validator_result": "PASS",
    }


def validate_stage_a_lineage(
    lineage: Mapping[str, Any] | None,
    *,
    context: StageAAsOfContext,
) -> dict[str, dict[str, Any]]:
    if not isinstance(lineage, Mapping):
        raise StageAAsOfContractError(
            "asof_provenance_missing",
            "Daily Plan as_of_lineage is missing",
        )
    validated: dict[str, dict[str, Any]] = {}
    for source in REQUIRED_STAGE_A_SOURCES:
        raw = lineage.get(source)
        if not isinstance(raw, Mapping):
            raise StageAAsOfContractError(
                "asof_provenance_missing",
                f"Daily Plan lineage is missing source: {source}",
                source=source,
            )
        if raw.get("validator_result") != "PASS":
            raise StageAAsOfContractError(
                "asof_provenance_invalid",
                f"{source} validator_result is not PASS",
                source=source,
            )
        _required(raw, "source", source=source)
        _required(raw, "observed_at", source=source)
        if not (raw.get("artifact_hash") or raw.get("revision")):
            raise StageAAsOfContractError(
                "asof_provenance_missing",
                f"{source} lineage requires artifact_hash or revision",
                source=source,
            )
        if source in DATA_DATE_SOURCES:
            selected = str(_required(raw, "selected_max_date", source=source))
            if _date_value(selected, "selected_max_date") > _date_value(context.data_date, "data_date"):
                raise StageAAsOfContractError(
                    "asof_future_source",
                    f"{source} selected_max_date {selected} is after data_date {context.data_date}",
                    source=source,
                )
        elif source == "universe":
            effective = str(_required(raw, "effective_as_of", source=source))
            if _date_value(effective, "effective_as_of") > _date_value(context.data_date, "data_date"):
                raise StageAAsOfContractError(
                    "asof_future_source",
                    f"universe effective_as_of {effective} is after data_date {context.data_date}",
                    source=source,
                )
            observed = str(_required(raw, "observed_at", source=source))
            if _datetime_value(observed, "observed_at").date() > _date_value(context.trade_date, "trade_date"):
                raise StageAAsOfContractError(
                    "asof_future_source",
                    f"universe observed_at {observed} is after trade_date {context.trade_date}",
                    source=source,
                )
        else:
            effective = str(_required(raw, "effective_as_of", source=source))
            if _date_value(effective, "effective_as_of") > _date_value(context.trade_date, "trade_date"):
                raise StageAAsOfContractError(
                    "asof_future_source",
                    f"config effective_as_of {effective} is after trade_date {context.trade_date}",
                    source=source,
                )
            observed = str(_required(raw, "observed_at", source=source))
            if _datetime_value(observed, "observed_at").date() > _date_value(context.trade_date, "trade_date"):
                raise StageAAsOfContractError(
                    "asof_future_source",
                    f"config observed_at {observed} is after trade_date {context.trade_date}",
                    source=source,
                )
        validated[source] = dict(raw)
    return validated

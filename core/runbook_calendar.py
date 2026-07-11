from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from core.paths import market_holidays_us_path


DEFAULT_CALENDAR_PATH = market_holidays_us_path()
CALENDAR_SCHEMA_VERSION = "us_market_holidays.v1"


class CalendarCoverageError(ValueError):
    pass


@dataclass(frozen=True)
class MarketCalendar:
    market: str
    timezone: str
    coverage_start: date
    coverage_end: date
    holidays: frozenset[date]

    def is_trading_day(self, value: date) -> bool:
        self.require_coverage(value)
        return value.weekday() < 5 and value not in self.holidays

    def require_coverage(self, value: date) -> None:
        if not self.coverage_start <= value <= self.coverage_end:
            raise CalendarCoverageError(
                f"calendar_coverage_exceeded:{value.isoformat()}:"
                f"{self.coverage_start.isoformat()}..{self.coverage_end.isoformat()}"
            )

    def next_trading_day(self, after: date) -> date:
        candidate = after + timedelta(days=1)
        while True:
            if self.is_trading_day(candidate):
                return candidate
            candidate += timedelta(days=1)


def _parse_date(value: Any, field_name: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"invalid_calendar_{field_name}") from exc


def load_market_calendar(path: str | Path = DEFAULT_CALENDAR_PATH) -> MarketCalendar:
    calendar_path = Path(path)
    payload = json.loads(calendar_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("calendar_root_must_be_object")
    if payload.get("schema_version") != CALENDAR_SCHEMA_VERSION:
        raise ValueError("unsupported_calendar_schema_version")
    for field_name in ("market", "timezone", "coverage_start", "coverage_end", "holidays"):
        if field_name not in payload:
            raise ValueError(f"calendar_{field_name}_required")
    if not isinstance(payload["holidays"], list):
        raise ValueError("calendar_holidays_must_be_list")

    coverage_start = _parse_date(payload["coverage_start"], "coverage_start")
    coverage_end = _parse_date(payload["coverage_end"], "coverage_end")
    if coverage_start > coverage_end:
        raise ValueError("calendar_coverage_is_reversed")
    holidays = frozenset(_parse_date(value, "holiday") for value in payload["holidays"])
    if any(value < coverage_start or value > coverage_end for value in holidays):
        raise ValueError("calendar_holiday_outside_coverage")

    return MarketCalendar(
        market=str(payload["market"]),
        timezone=str(payload["timezone"]),
        coverage_start=coverage_start,
        coverage_end=coverage_end,
        holidays=holidays,
    )

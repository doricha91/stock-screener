from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


MARKET_TIMEZONE_BY_REGION = {
    "US": "US/Eastern",
    "KR": "Asia/Seoul",
    "JP": "Asia/Tokyo",
    "UTC": "UTC",
}

MARKET_CLOSE_TIME_BY_REGION = {
    "US": time(16, 0),
}

DAILY_BAR_BUFFER_MINUTES_BY_REGION = {
    "US": 240,
}


def get_market_now(region: str = "US") -> datetime:
    normalized_region = region.upper()
    timezone_name = MARKET_TIMEZONE_BY_REGION.get(normalized_region, "UTC")
    return datetime.now(ZoneInfo(timezone_name))


def get_market_today(region: str = "US") -> date:
    return get_market_now(region).date()


def parse_date_yyyy_mm_dd(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def should_skip_download_start_date(
    start_date: str,
    region: str = "US",
    market_today: date | None = None,
    now: datetime | None = None,
) -> tuple[bool, str]:
    """
    Return whether a yfinance download should be skipped because start_date is
    not before the current market date for the target region.

    This prevents requesting today's not-yet-finalized daily bar.
    """
    start_dt = parse_date_yyyy_mm_dd(start_date)
    effective_market_today = market_today or get_market_today(region)

    if start_dt > effective_market_today:
        return True, (
            f"start_date={start_date} is after market_today={effective_market_today} "
            f"for region={region}."
        )

    if start_dt < effective_market_today:
        return False, ""

    if is_after_daily_bar_release_time(region=region, now=now):
        return False, ""

    release_note = "same-day daily bar is not considered finalized yet"
    if region.upper() in MARKET_CLOSE_TIME_BY_REGION:
        close_time = MARKET_CLOSE_TIME_BY_REGION[region.upper()]
        buffer_minutes = DAILY_BAR_BUFFER_MINUTES_BY_REGION.get(region.upper(), 240)
        release_dt = datetime.combine(
            effective_market_today,
            close_time,
            tzinfo=(now.tzinfo if now and now.tzinfo is not None else ZoneInfo(MARKET_TIMEZONE_BY_REGION.get(region.upper(), "UTC"))),
        ) + timedelta(minutes=buffer_minutes)
        release_note = f"{release_note} (release threshold: {release_dt.strftime('%Y-%m-%d %H:%M %Z')})"

    return True, (
        f"start_date={start_date} equals market_today={effective_market_today} for region={region}, "
        f"and {release_note}."
    )

def is_after_daily_bar_release_time(
    region: str = "US",
    now: datetime | None = None,
    buffer_minutes: int | None = None,
) -> bool:
    """
    Return True if the current time in the target market is after the
    daily bar release threshold.

    For US:
    - market close = 16:00 US/Eastern
    - default buffer = 240 minutes
    - release threshold = 20:00 US/Eastern
    """
    normalized_region = region.upper()

    if normalized_region not in MARKET_CLOSE_TIME_BY_REGION:
        return False

    market_now = now or get_market_now(normalized_region)

    if market_now.tzinfo is None:
        timezone_name = MARKET_TIMEZONE_BY_REGION.get(normalized_region, "UTC")
        market_now = market_now.replace(tzinfo=ZoneInfo(timezone_name))

    close_time = MARKET_CLOSE_TIME_BY_REGION[normalized_region]
    buffer_min = (
        buffer_minutes
        if buffer_minutes is not None
        else DAILY_BAR_BUFFER_MINUTES_BY_REGION.get(normalized_region, 240)
    )

    close_dt = datetime.combine(market_now.date(), close_time, tzinfo=market_now.tzinfo)
    release_dt = close_dt + timedelta(minutes=buffer_min)

    return market_now >= release_dt

from datetime import date, datetime
from zoneinfo import ZoneInfo

from core.market_time import (
    get_market_today,
    is_after_daily_bar_release_time,
    should_skip_download_start_date,
)


def test_get_market_today_returns_date():
    assert isinstance(get_market_today("US"), date)
    assert isinstance(get_market_today("KR"), date)


def test_get_market_today_unknown_region_fallback():
    assert isinstance(get_market_today("UNKNOWN"), date)


def test_skip_when_start_date_after_market_today():
    should_skip, reason = should_skip_download_start_date(
        "2026-05-09",
        region="US",
        market_today=date(2026, 5, 8),
    )

    assert should_skip is True
    assert "after market_today" in reason


def test_do_not_skip_when_start_date_before_market_today():
    should_skip, reason = should_skip_download_start_date(
        "2026-05-07",
        region="US",
        market_today=date(2026, 5, 8),
    )

    assert should_skip is False
    assert reason == ""


def test_skip_same_day_before_release_time():
    now = datetime(2026, 5, 8, 18, 0, tzinfo=ZoneInfo("US/Eastern"))
    should_skip, reason = should_skip_download_start_date(
        "2026-05-08",
        region="US",
        market_today=date(2026, 5, 8),
        now=now,
    )

    assert should_skip is True
    assert "same-day daily bar is not considered finalized yet" in reason


def test_allow_same_day_after_release_time():
    now = datetime(2026, 5, 8, 21, 0, tzinfo=ZoneInfo("US/Eastern"))
    should_skip, reason = should_skip_download_start_date(
        "2026-05-08",
        region="US",
        market_today=date(2026, 5, 8),
        now=now,
    )

    assert should_skip is False
    assert reason == ""


def test_is_after_daily_bar_release_time_boundary():
    now = datetime(2026, 5, 8, 20, 0, tzinfo=ZoneInfo("US/Eastern"))
    assert is_after_daily_bar_release_time("US", now=now) is True


def test_unknown_region_release_check_is_conservative():
    now = datetime(2026, 5, 8, 21, 0)
    assert is_after_daily_bar_release_time("UNKNOWN", now=now) is False

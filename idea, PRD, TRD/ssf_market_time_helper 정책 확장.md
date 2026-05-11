# Codex Task: Small Safe Fix 1 - Allow US same-day download after market close buffer

## Objective

Update `core/market_time.py` so that US same-day daily-bar downloads are allowed **after US market close + safety buffer**.

Current behavior:

```text
start_date >= market_today
→ always skip
```

New intended behavior:

```text
start_date > market_today
→ skip

start_date < market_today
→ allow

start_date == market_today
→ skip before daily bar release time
→ allow after daily bar release time
```

This is a small safe fix.  
Do not modify `screener/data_collector.py` in this step unless absolutely necessary.

---

## Policy

For US market daily bars:

```text
market close time: 16:00 US/Eastern
safety buffer: 4 hours
daily bar release threshold: 20:00 US/Eastern
```

Reason:

- US market closes at 16:00 ET.
- yfinance/Yahoo daily bars may not be immediately available.
- 20:00 ET is a conservative default.
- This avoids requesting same-day bars too early while allowing Korea morning runs after US close.

This is not a full market calendar implementation.

---

## Files to change

Expected:

```text
core/market_time.py
tests/test_market_time.py
```

Do not change:

```text
screener/data_collector.py
screener/data_processor.py
core/preflight_check.py
DB schema
outputs/
paper-test files
backtest files
```

---

# Required changes

## 1. Extend `core/market_time.py`

Keep existing functions and backward compatibility as much as possible.

Current known functions:

```python
get_market_today(region)
parse_date_yyyy_mm_dd(value)
should_skip_download_start_date(start_date, region="US", market_today=None)
```

Add or update helper functions.

Recommended additions:

```python
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
```

Add constants:

```python
MARKET_CLOSE_TIME_BY_REGION = {
    "US": time(16, 0),
}

DAILY_BAR_BUFFER_MINUTES_BY_REGION = {
    "US": 240,  # 4 hours after close
}
```

Add function:

```python
def get_market_now(region: str = "US") -> datetime:
    normalized_region = region.upper()
    timezone_name = MARKET_TIMEZONE_BY_REGION.get(normalized_region, "UTC")
    return datetime.now(ZoneInfo(timezone_name))
```

Add function:

```python
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

    # If a naive datetime is provided in tests, interpret it in the region timezone.
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
```

Update `should_skip_download_start_date()` to support `now`.

Recommended signature:

```python
def should_skip_download_start_date(
    start_date: str,
    region: str = "US",
    market_today: date | None = None,
    now: datetime | None = None,
) -> tuple[bool, str]:
    ...
```

Expected logic:

```python
start_dt = parse_date_yyyy_mm_dd(start_date)
effective_market_today = market_today or get_market_today(region)

if start_dt > effective_market_today:
    return True, "..."

if start_dt < effective_market_today:
    return False, ""

# start_dt == effective_market_today
if is_after_daily_bar_release_time(region=region, now=now):
    return False, ""

return True, "..."
```

The reason string should clearly say whether the skip happened because:

```text
start_date is after market_today
```

or:

```text
same-day daily bar is not considered finalized yet
```

---

# Tests

Update:

```text
tests/test_market_time.py
```

Existing tests that expected `start_date == market_today` to always skip must be updated.

Required tests:

## 1. `start_date > market_today` still skips

```python
should_skip, _ = should_skip_download_start_date(
    "2026-05-09",
    region="US",
    market_today=date(2026, 5, 8),
)
assert should_skip is True
```

## 2. `start_date < market_today` does not skip

```python
should_skip, reason = should_skip_download_start_date(
    "2026-05-07",
    region="US",
    market_today=date(2026, 5, 8),
)
assert should_skip is False
assert reason == ""
```

## 3. `start_date == market_today` before release time skips

Use US/Eastern-aware datetime:

```python
from datetime import datetime
from zoneinfo import ZoneInfo

now = datetime(2026, 5, 8, 18, 0, tzinfo=ZoneInfo("US/Eastern"))
```

Expected:

```python
should_skip is True
```

## 4. `start_date == market_today` after release time does not skip

```python
now = datetime(2026, 5, 8, 21, 0, tzinfo=ZoneInfo("US/Eastern"))
```

Expected:

```python
should_skip is False
```

## 5. `is_after_daily_bar_release_time()` boundary

At exactly 20:00 ET, expected True.

```python
now = datetime(2026, 5, 8, 20, 0, tzinfo=ZoneInfo("US/Eastern"))
assert is_after_daily_bar_release_time("US", now=now) is True
```

## 6. unknown region remains conservative

Unknown region should not allow same-day release.

```python
assert is_after_daily_bar_release_time("UNKNOWN", now=datetime(2026, 5, 8, 21, 0)) is False
```

---

# Validation commands

Run:

```powershell
$env:PYTHONPATH="."; python -m pytest tests/test_market_time.py -q
$env:PYTHONPATH="."; python -m py_compile core/market_time.py
```

Do not run full collector yet in this step.

---

# Non-goals

Do not implement:

```text
market holiday calendar
early close calendar
KR collector
JP collector
crypto collector
data_collector.py rewrite
preflight change
DB schema change
generated artifact change
```

---

# Acceptance Criteria

1. `start_date > market_today` still skips.
2. `start_date < market_today` still allows.
3. `start_date == market_today` skips before US release threshold.
4. `start_date == market_today` allows after US release threshold.
5. US release threshold is 20:00 US/Eastern by default.
6. `US/Eastern` remains centralized in `core/market_time.py`.
7. `tests/test_market_time.py` passes.
8. No collector, DB, paper, backtest, or generated artifact changes are made.

---

# Report format

After implementation, report:

```text
1. Summary
2. Changed files
3. Behavior changes
4. Tests run
5. Tests not run and why
6. Risks and limitations
7. Suggested next step
```

Explicitly mention:

```text
- whether same-day US download is allowed after 20:00 ET
- whether same-day US download is still skipped before 20:00 ET
- whether data_collector.py was untouched in this step
```
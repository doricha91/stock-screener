# Codex Task: Small Safe Fix 2 - Apply same-day-after-close market_time guard to data_collector.py

## Objective

Apply the updated `core.market_time.should_skip_download_start_date()` behavior to `screener/data_collector.py`.

This is a minimal-diff change.

Current intended behavior after Small Safe Fix 1:

```text
US start_date > market_today
→ skip

US start_date < market_today
→ allow

US start_date == market_today before 20:00 ET
→ skip

US start_date == market_today at/after 20:00 ET
→ allow
```

---

## Current context

`data_collector.py` already uses:

```python
should_skip_download_start_date(start_date, region="US")
```

in:

```text
update_market_indices()
update_stock_data()
```

This step is mainly to verify that the updated helper behavior is actually used by the collector.

---

# Files expected to change

Prefer no production code change if `data_collector.py` already calls the helper.

Expected changes:

```text
tests/test_data_collector_market_time_guard.py
```

Possible only if needed:

```text
screener/data_collector.py
```

Do not change:

```text
DB schema
outputs/
paper-test files
backtest files
optimizer files
market regime files
```

---

# Required behavior

Verify that `data_collector.py` no longer blindly skips all `start_date == market_today`.

Instead, it should rely on the updated helper.

Do not reintroduce:

```python
datetime.today()
```

date comparison in `data_collector.py`.

Do not hardcode:

```python
ZoneInfo("US/Eastern")
```

inside `data_collector.py`.

---

# Test recommendation

Add a focused test with monkeypatch.

New file:

```text
tests/test_data_collector_market_time_guard.py
```

## Test idea

Monkeypatch `screener.data_collector.should_skip_download_start_date`.

Goal:

- prove `update_market_indices()` or the smallest callable path uses the helper
- avoid real yfinance
- avoid real DB if possible

If direct integration is too hard because of DB setup, keep the test narrow and only verify the imported helper is present and used in the expected function source.

Acceptable fallback test:

```python
import inspect
import screener.data_collector as dc

def test_data_collector_uses_market_time_helper():
    source = inspect.getsource(dc.update_market_indices)
    assert "should_skip_download_start_date" in source
    assert "datetime.today().strftime" not in source
```

And similarly for `update_stock_data`.

Better test if feasible:

- monkeypatch DB cursor result so `last_date = "2026-05-07"`
- monkeypatch helper to return `(True, "test skip")`
- monkeypatch `yf.download` to raise if called
- call the target function or extracted small path
- assert `yf.download` was not called

However, do not do large refactoring just to test this.

---

# Validation commands

Run:

```powershell
$env:PYTHONPATH="."; python -m pytest tests/test_market_time.py -q
$env:PYTHONPATH="."; python -m pytest tests/test_data_collector_market_time_guard.py -q
$env:PYTHONPATH="."; python -m py_compile core/market_time.py screener/data_collector.py
```

Optionally run collector manually after Korea morning / US post-close context:

```powershell
$env:PYTHONPATH="."; python screener/data_collector.py
```

Expected when current US time is after 20:00 ET and `start_date == market_today`:

```text
It should attempt yfinance download instead of skipping solely because start_date == market_today.
```

If yfinance has no data yet, it may still return empty data. That should be handled by existing empty-data logic.

---

# Non-goals

Do not implement:

```text
market holiday calendar
early close calendar
KR collector
full collector refactor
DB schema change
output DB change
paper current state
position sizing change
```

---

# Acceptance Criteria

1. `data_collector.py` continues using `should_skip_download_start_date(start_date, region="US")`.
2. `data_collector.py` does not hardcode `US/Eastern`.
3. `data_collector.py` does not reintroduce `datetime.today()` date guard logic.
4. Tests confirm both `update_market_indices()` and `update_stock_data()` use the helper.
5. Existing `tests/test_market_time.py` still passes.
6. No DB/output/generated artifacts are modified.

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
- whether data_collector.py required code changes
- whether same-day after 20:00 ET is now allowed by helper
- whether update_market_indices/update_stock_data still use the helper
- whether any DB/output files changed
```
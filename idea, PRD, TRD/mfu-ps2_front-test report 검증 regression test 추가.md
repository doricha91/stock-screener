# Codex Task: MFU-PS2 Front-test Report Rec_Shares Regression Test

## Objective

Implement MFU-PS2: add a regression test that verifies front-test normal new BUY `Rec_Shares` is calculated using the shared `calculate_entry_shares()` helper introduced in MFU-PS1.

This task is a **test-focused regression guard**.

Do not change strategy logic unless the test reveals a clear bug.

---

## Background

MFU-PS1 completed:

- Added `core/position_sizing.py`
- Added `calculate_entry_shares()`
- Updated backtest normal new BUY sizing to use the helper
- Updated front-test normal new BUY `Rec_Shares` sizing to use the helper
- Switching / hedge / sell logic were intentionally left unchanged

MFU-PS2 should verify that the actual front-test report/action generation path uses the same sizing result.

Target invariant:

```text
front-test normal BUY Rec_Shares
=
calculate_entry_shares(
    total_equity,
    available_buying_power,
    price,
    max_positions,
)
```

---

# Scope

## Include

1. Add a regression test for front-test normal new BUY `Rec_Shares`.
2. Verify the result against `calculate_entry_shares()`.
3. Use a small deterministic fixture or monkeypatch approach.
4. Keep the test focused on normal new BUY only.

## Exclude

Do not modify:

- switching sizing
- hedge sizing
- sell sizing
- paper-test write behavior
- paper execution log
- paper current state
- data collector
- DB schema
- generated artifacts
- optimizer behavior
- market regime logic
- config loading priority

---

# Recommended Test Strategy

Prefer testing the smallest callable front-test unit that produces normal BUY action/journal rows.

If `core/daily_plan_generator.py` has a helper for building action items or journal rows, test that helper directly.

If no clean helper exists, use a minimal integration-style test around the smallest stable function in `daily_plan_generator.py`, with monkeypatched inputs.

Avoid full live DB, yfinance, or real market data dependencies.

---

# Required Test

Create a new test file:

```text
tests/test_mfu_ps2_fronttest_rec_shares.py
```

The test should verify a normal new BUY candidate.

## Example scenario

Use deterministic values:

```text
total_equity = 100000
available_buying_power = 30000
price = 200
max_positions = 10
```

Expected result:

```text
target_position_value = 100000 / 10 = 10000
allocation = min(10000, 30000) = 10000
expected_rec_shares = int(10000 / 200) = 50
```

The front-test normal BUY `Rec_Shares` should be:

```text
50
```

It must not be:

```text
int(30000 / 200) = 150
```

---

# Test Implementation Guidance

## Option A: Helper-level regression if a front-test BUY row builder exists

If there is a function that builds normal BUY action or journal row, call it directly.

Example concept:

```python
from core.position_sizing import calculate_entry_shares

def test_fronttest_normal_buy_rec_shares_uses_position_sizing_helper():
    total_equity = 100000
    available_buying_power = 30000
    price = 200
    max_positions = 10

    expected = calculate_entry_shares(
        total_equity=total_equity,
        available_buying_power=available_buying_power,
        price=price,
        max_positions=max_positions,
    )

    # Call the smallest available daily_plan_generator helper that creates
    # a normal BUY action/journal row.
    row = build_or_extract_normal_buy_row(...)

    assert int(row["Rec_Shares"]) == expected
    assert int(row["Rec_Shares"]) == 50
    assert int(row["Rec_Shares"]) != int(available_buying_power / price)
```

Use actual function names from the current codebase.

---

## Option B: Monkeypatch `calculate_entry_shares()` to prove it is used

If direct numeric setup is hard, monkeypatch the imported helper inside `core.daily_plan_generator`.

Example concept:

```python
def fake_calculate_entry_shares(*args, **kwargs):
    return 123

monkeypatch.setattr(
    core.daily_plan_generator,
    "calculate_entry_shares",
    fake_calculate_entry_shares,
)
```

Then run the smallest front-test BUY generation path and assert:

```text
Rec_Shares == 123
```

This proves the front-test path uses the shared helper.

Use this only if Option A is difficult.

---

## Option C: Minimal report rendering check

If the only practical path is generating a small markdown/report fragment, verify that the generated normal BUY journal row contains the expected `Rec_Shares`.

Expected assertion:

```python
assert "| ... | BUY | 50 | 200" in markdown
```

Do not rely on full live data or DB.

---

# Important Rules

1. The test must focus on normal new BUY only.
2. Do not test SWITCH_IN in this MFU.
3. Do not test SELL sizing in this MFU.
4. Do not use real yfinance calls.
5. Do not require live market DB.
6. Do not write output files.
7. Do not modify generated reports.
8. Do not change `run_paper_eod_update.py`.
9. Do not change `screener/data_collector.py`.
10. Do not modify DB schema.

---

# If Production Code Needs a Tiny Refactor

A tiny extraction is allowed only if needed to make the test possible.

Allowed:

```text
Extract a small helper in core/daily_plan_generator.py that computes normal BUY Rec_Shares using calculate_entry_shares().
```

Example:

```python
def calculate_fronttest_entry_rec_shares(
    total_equity: float,
    available_buying_power: float,
    price: float,
    max_positions: int,
) -> int:
    return calculate_entry_shares(
        total_equity=total_equity,
        available_buying_power=available_buying_power,
        price=price,
        max_positions=max_positions,
    )
```

But prefer testing existing code without refactor if possible.

Not allowed:

- changing sizing policy
- changing report format
- changing journal columns
- changing action taxonomy

---

# Acceptance Criteria

1. New regression test file is added.
2. The test verifies that normal BUY `Rec_Shares` uses `calculate_entry_shares()`.
3. The test proves that `available_buying_power` is not fully spent on one symbol when `total_equity / max_positions` is smaller.
4. Expected `Rec_Shares` in the sample case is `50`, not `150`.
5. SWITCH_IN / hedge / sell behavior remains untouched.
6. No output files, DB files, or generated reports are modified.
7. Existing MFU-PS1 unit test still passes.

---

# Validation Commands

Run:

```powershell
$env:PYTHONPATH="."; python -m pytest tests/test_position_sizing.py -q
$env:PYTHONPATH="."; python -m pytest tests/test_mfu_ps2_fronttest_rec_shares.py -q
$env:PYTHONPATH="."; python -m py_compile core/position_sizing.py core/daily_plan_generator.py
```

If useful, also run:

```powershell
$env:PYTHONPATH="."; python scripts/check_decision_parity.py --date 2026-05-04 --symbol AAPL
$env:PYTHONPATH="."; python scripts/validate_strategy_sync.py
```

Do not run full test suite unless useful.

If full tests are run and fail due to existing collection/import issues, clearly separate existing failures from MFU-PS2 failures.

---

# Safety Rules

Follow `AGENTS.md`.

Do not:

- edit DB schema
- edit output databases
- edit generated reports/artifacts
- modify `.env`
- modify API keys or credentials
- change paper-test write behavior
- change data collector behavior
- change optimizer behavior
- change market regime logic
- change hedge mode logic
- change switching logic
- change sell logic

---

# Expected Final Diff

Expected files:

```text
tests/test_mfu_ps2_fronttest_rec_shares.py
```

Possible file only if tiny extraction is needed:

```text
core/daily_plan_generator.py
```

Unexpected files should be reported.

---

# Report Format

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

- whether production code was changed
- whether `core/daily_plan_generator.py` was modified
- whether the test checks numeric equality against `calculate_entry_shares()`
- whether the test proves `50`, not `150`, in the sample scenario
- whether switching/hedge/sell logic was untouched
- whether generated artifacts or DB files were untouched
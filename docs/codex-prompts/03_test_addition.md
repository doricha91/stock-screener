# Codex Prompt: Test Addition

Add tests for the behavior below.

## Behavior to Test

[Describe the behavior]
MDD 계산이 고정된 equity curve에서 예상값과 일치해야 한다.


## Why This Test Is Needed

[Explain the bug, calculation rule, or regression risk]
MDD는 백테스트 성과 평가의 핵심 지표이며, 계산식 변경 시 전체 전략 평가가 왜곡될 수 있다.


## Preferred Test Type

Choose the most appropriate type:

- Smoke test
- Core calculation unit test
- Representative regression test

Core calculation unit test


## Target Area

[Describe the related module, function, script, or workflow]
backtesting metrics calculation


## Relevant Files

- [file path 1]
- [file path 2]
backtesting/metrics.py
tests/test_metrics.py

## Rules

- Follow `AGENTS.md`.
- Inspect relevant files before editing.
- Prefer small deterministic test data.
- Do not require real market DB access.
- Do not call yfinance or external APIs.
- Do not require `.env`, API keys, tokens, or broker credentials.
- Do not modify output databases.
- Do not change DB schema.
- Do not change strategy behavior.
- Do not introduce look-ahead bias.
- Do not change production code unless necessary for testability.
- If production code must change, explain why before changing it.
- Keep the diff small and focused.
- If there are pre-existing uncommitted changes, report them before editing and avoid overwriting them.

## Test Data

Use one of the following:

1. Inline DataFrame
2. Small fixture
3. Temporary test database
4. Mocked dependency

Avoid using real production data unless explicitly requested.

## Validation

Run the relevant test command if possible.

Examples:

```bash
python -m pytest tests/
python -m pytest tests/test_backtest_engine.py
python -m pytest tests/test_optimizer.py
```

If full validation is too heavy, run the smallest focused test that covers the new behavior.

If validation cannot be run, clearly state:

1. Which validation was not run
2. Why it was not run
3. How the user can run it manually

## Output Format

1. Summary
2. Added or modified test files
3. What each test verifies
4. Production code changes, if any
5. Tests run
6. Tests not run and why
7. Remaining coverage gaps
8. Suggested next step
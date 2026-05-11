# Codex Prompt: Small Safe Fix

Apply only the smallest safe fix for the issue below.

## Goal

[Describe the one-sentence goal]


## Problem

[Describe the problem]


## Allowed Files

- [file path 1]
- [file path 2]
core/backtest_engine.py


## Forbidden Changes

- DB schema changes
- Output DB modifications
- `.env` / API key / token changes
- Broker credential changes
- Broad refactoring
- Unrelated formatting changes
- Strategy performance optimization
- Changes outside the requested scope
- Live trading or broker order behavior changes
- Large file/folder moves or renames
- New external dependencies unless explicitly approved

## Acceptance Criteria

1. [Criterion 1]
2. [Criterion 2]
3. [Criterion 3]

## Validation

Run the most relevant lightweight validation if possible.

Preferred examples:

```bash
python -m pytest
python -m pytest tests/
python -m pytest tests/test_backtest_engine.py
python run_portfolio_backtest.py
python run_optimizer.py
```

If full validation is too heavy, run a smaller focused validation.

If validation cannot be run, clearly state:

1. Which validation was not run
2. Why it was not run
3. How the user can run it manually

## Rules

- Follow `AGENTS.md`.
- Inspect relevant files before editing.
- Keep the diff small.
- Modify only the allowed files.
- Preserve existing CLI behavior unless explicitly requested.
- Preserve existing config loading behavior unless the task explicitly targets config.
- Do not change DB schema.
- Do not modify output databases.
- Do not introduce look-ahead bias.
- Do not silently change strategy behavior.
- Do not change benchmark logic unless explicitly requested.
- Do not change market regime thresholds unless explicitly requested.
- Do not change hedge mode parameters unless explicitly requested.
- If performance metrics change, explain whether the change is expected.
- If there are pre-existing uncommitted changes, report them before editing and avoid overwriting them.

## Output Format

1. Summary
2. Changed files
3. Behavior changes
4. Tests run
5. Tests not run and why
6. Risks and limitations
7. Suggested next step
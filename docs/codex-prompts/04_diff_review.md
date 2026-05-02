# Codex Prompt: Diff Review

Review the current git diff.

Do not modify files.

## Review Target

Review all current uncommitted changes.

If the user provides a specific file, commit range, or PR diff, review only that target.

## Review Focus

Check for:

1. Bugs
2. Unintended behavior changes
3. Look-ahead bias
4. DB schema or data safety risks
5. Strategy logic changes
6. Backtest metric calculation changes
7. Optimizer behavior changes
8. Market regime side effects
9. Hedge mode side effects
10. Config loading priority issues
11. Path handling issues
12. Test coverage gaps
13. Overly broad refactoring
14. Unrelated formatting or file changes
15. Secret, token, API key, or credential exposure
16. Output database or generated artifact modification

## Project Rules

- Follow `AGENTS.md`.
- Do not edit files.
- Do not commit changes.
- Do not run destructive commands.
- Do not modify DB schema.
- Do not modify output databases.
- Do not change `.env`, API keys, tokens, or broker credentials.
- If a change affects performance metrics, identify the exact logic responsible.
- If a change affects strategy behavior, classify it as one of:
  - bug fix
  - intended behavior change
  - experimental strategy change
  - unclear
- If a risk is uncertain, mark it as uncertain instead of guessing.

## Commands

If useful, inspect the diff with read-only commands such as:

```bash
git status
git diff --stat
git diff
```

Do not run tests unless explicitly requested.

## Output Format

1. Summary
2. Critical issues
3. Moderate issues
4. Minor issues
5. Good changes
6. Missing tests
7. Risk assessment
8. Recommended next action
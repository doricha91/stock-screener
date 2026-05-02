# Codex Prompt: Bug Investigation

Investigate the following bug without modifying files.

## Bug

[Describe the bug here]
hedge mode를 켰는데 실제 hedge ETF 매수가 발생하지 않는다.


## Expected Behavior

[Describe what should happen] 
market regime이 위험 상태이고 hedge mode 조건이 충족되면 hedge ETF 매수가 발생해야 한다.


## Observed Behavior

[Describe what actually happened]
백테스트는 정상 종료되지만 trade log에 hedge ETF 매수 기록이 없다.


## Logs / Error Messages

```text
[Paste logs here]
```

## Relevant Context

[Add related files, commands, config values, or recent changes if known]
최근 market regime logic에서 target_cash_ratio를 동적으로 조정하도록 변경했다.
hedge mode entry logic도 cash ratio 조건을 사용하는 것으로 보인다

## Investigation Scope

Please identify:

1. Most likely root cause
2. Related files and functions
3. Data or config assumptions involved
4. Whether DB, strategy logic, optimizer logic, market regime logic, or hedge mode is involved
5. Minimal safe fix candidate
6. Tests or verification commands that should be run

## Rules

- Follow `AGENTS.md`.
- Do not modify files.
- Do not change DB schema.
- Do not modify output databases.
- Do not change strategy behavior unless the bug is directly caused by incorrect strategy behavior.
- Do not guess. Mark uncertainty clearly.
- If the issue may affect backtest results, explain how.
- If the issue may affect database integrity, explain the risk.
- If the issue may affect live trading or broker order behavior, stop and report the risk before suggesting changes.

## Output Format

1. Summary
2. Root cause candidates
3. Evidence from code
4. Minimal fix proposal
5. Risk level
6. Recommended validation
7. Questions or uncertainties
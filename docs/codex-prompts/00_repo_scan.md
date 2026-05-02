# Codex Prompt: Repository Scan

Do not modify any files.

Inspect this repository and summarize the current architecture.

Focus on:

1. Project structure
2. Main entrypoints
3. Backtest execution flow
4. Optimizer execution flow
5. Configuration loading flow
6. Database read/write points
7. Test structure
8. High-risk files or directories
9. Areas that should not be changed casually

Project rules:

- Follow `AGENTS.md`.
- Do not edit files.
- Do not change DB schema.
- Do not modify `.env`, API keys, tokens, broker credentials, or output databases.
- Do not optimize trading performance.
- Do not run destructive commands.
- If something is unclear, say it is unclear instead of guessing.

Output format:

1. Summary
2. Key files and roles
3. Execution flow
4. Configuration flow
5. Database touchpoints
6. Test structure
7. Risks and cautions
8. Suggested next investigation step
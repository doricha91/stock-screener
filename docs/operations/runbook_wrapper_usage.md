# Runbook Windows Wrapper Usage

## Purpose

The Windows wrappers in `ops\runbook_wrappers\` reduce manual typing for the paper/test runbook command controller. They are thin `.cmd` launchers only: each wrapper loads shared environment values, changes to the repository root, calls the existing Python CLI, prints the process exit code, and returns that exit code.

These wrappers do not execute raw `operator_summary.next_command`, do not bypass the command registry allowlist, and do not add risk options such as `--force`, `--replace`, or `--allow-warnings`. A wrapper never approves a `WARNING` automatically.

They are not live trading, broker, API order, or order placement automation. They only call the local paper/test runbook controller and verifier commands.

## Location

- Shared settings: `ops\runbook_wrappers\_env.cmd`
- Stage wrappers: `ops\runbook_wrappers\01_*.cmd` through `ops\runbook_wrappers\09_*.cmd`

## Configure Dates And Account

Edit `ops\runbook_wrappers\_env.cmd` before running a new runbook day:

```bat
set REPO_ROOT=D:\python\StockScreener
set WORKSPACE=D:\n8n\workspace\stock_screener_ops
set ACCOUNT_ID=paper_pilot_202606
set DATA_DATE=2026-07-01
set TRADE_DATE=2026-07-02
set PAUSE_ON_EXIT=0
```

Until date rollover automation is added, `DATA_DATE` and `TRADE_DATE` are managed manually in `_env.cmd`.

`_env.cmd` uses `C:\Users\inocha\anaconda3\condabin\conda.bat` to activate `HANTU311_64`. It stops with a non-zero exit code if activation fails, the active environment name is different, or `%CONDA_PREFIX%\python.exe` does not exist. The wrappers use only that environment's `python.exe`; they do not fall back to another Python on `PATH`.

The wrappers can be started by double-clicking them in Windows Explorer. Running them from CMD or Anaconda Prompt is recommended so the JSON result remains visible. Set `PAUSE_ON_EXIT=1` to pause before a double-clicked window closes; the default `0` closes automatically.

## Execution Order

Run wrappers from `ops\runbook_wrappers\` in numeric order:

| Order | Wrapper | Calls |
| :--- | :--- | :--- |
| 01 | `01_stage_a_plan_prep.cmd` | `%PYTHON_EXE% scripts\runbook_stage_runner.py stage-a` |
| 02 | `02_gate1_execution_input.cmd` | `%PYTHON_EXE% scripts\runbook_gate_checker.py gate1` |
| 03 | `03_stage_b_execution_commit_sync.cmd` | `%PYTHON_EXE% scripts\runbook_stage_runner.py stage-b` |
| 04 | `04_stage_b_verify.cmd` | `%PYTHON_EXE% scripts\runbook_stage_b_verifier.py --json` |
| 05 | `05_stage_c_review_prep.cmd` | `%PYTHON_EXE% scripts\runbook_stage_runner.py stage-c` |
| 06 | `06_gate2_review_input.cmd` | `%PYTHON_EXE% scripts\runbook_stage_runner.py gate2` |
| 07 | `07_stage_d_preview.cmd` | `%PYTHON_EXE% scripts\runbook_stage_runner.py stage-d-preview` |
| 08 | `08_stage_d_append_sync.cmd` | `%PYTHON_EXE% scripts\runbook_stage_runner.py stage-d-append` |
| 09 | `09_stage_e_eod_close.cmd` | `%PYTHON_EXE% scripts\runbook_stage_runner.py stage-e` |

`02_gate1_execution_input.cmd` uses `scripts\runbook_gate_checker.py` because Gate 1 is exposed by the existing gate checker CLI. `04_stage_b_verify.cmd` omits `--confirm-paper-test` because the verifier CLI does not accept that argument.

## Result Meanings

Always inspect the command JSON output. Check `runner_result`, `warnings`, `blockers`, and `next_required_action`; a process exit code of `0` can still require operator attention for `WAIT` or `WARNING`.

- `PASS`: The stage or gate completed and the next numbered wrapper may be considered.
- `WAIT`: The controller is waiting for required operator input or external state. Do not skip ahead.
- `WARNING`: The command ran, but operator review is required. In particular, `stage-d-preview` may return `WARNING` with exit code `0`. Do not proceed based on the exit code alone, and as a rule do not run `08_stage_d_append_sync.cmd` until the warnings have been reviewed.
- `BLOCKED`: A required precondition failed or a blocking inconsistency was detected. Stop and inspect the JSON reason.
- `FAILED`: The command failed. Stop and inspect the output and generated artifacts.

`WAIT` and `WARNING` must be reviewed directly in the JSON output. The wrappers do not approve warnings and must not be modified to add `--allow-warnings` automatically.

If Stage E has already returned `PASS` for the same `ACCOUNT_ID`, `DATA_DATE`, and `TRADE_DATE`, do not rerun Stage E for that runbook day unless a separate recovery procedure explicitly authorizes it.

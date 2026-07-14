# Runbook Windows Wrapper Usage

## Purpose

The Windows wrappers in `ops\runbook_wrappers\` reduce manual typing for the paper/test runbook command controller. They are thin `.cmd` launchers only: each wrapper loads shared environment values, changes to the repository root, calls the existing Python CLI, prints the process exit code, and returns that exit code.

These wrappers do not execute raw `operator_summary.next_command`, do not bypass the command registry allowlist, and do not add risk options such as `--force`, `--replace`, or `--allow-warnings`. A wrapper never approves a `WARNING` automatically.

They are not live trading, broker, API order, or order placement automation. They only call the local paper/test runbook controller and verifier commands.

## Location

- Shared loader: `ops\runbook_wrappers\_env.cmd`
- Machine example/local: `_machine.template.cmd` / `_machine.local.cmd`
- Account example/local: `_account.template.cmd` / `_account.local.cmd`
- Runbook-day example/local: `_runbook_day.template.cmd` / `_runbook_day.local.cmd`
- Environment preparation wrapper: `ops\runbook_wrappers\00_prepare_next_runbook_day.cmd`
- Stage wrappers: `ops\runbook_wrappers\01_*.cmd` through `ops\runbook_wrappers\09_*.cmd`

## Configure Dates And Account

Create and review the machine and account local files before preparing a new runbook day. The account local contains:

```bat
set ACCOUNT_ID=paper_pilot_202606
set ACCOUNT_MODE=PAPER
```

`00_prepare_next_runbook_day.cmd` calls the existing 6-4C prep command and updates only the runbook-day local:

```bat
set DATA_DATE=2026-07-02
set TRADE_DATE=2026-07-06
set RUNBOOK_DAY_ID=paper_pilot_202606_2026-07-02_2026-07-06
```

All local files are ignored by Git. Templates are examples only and are never loaded as fallbacks. Wrapper 00 loads only the machine and account locals because it prepares the runbook-day local. Wrappers 01 through 09 continue to call only `_env.cmd`, which requires all three local files.

`_env.cmd` loads machine, account, and runbook-day locals in that order. It requires `ACCOUNT_MODE=PAPER`, validates the runbook ID, checks repository/workspace/Conda paths, activates `CONDA_ENV_NAME`, verifies the active environment, and sets `PYTHON_EXE` from `%CONDA_PREFIX%\python.exe`. It does not fall back to another Python on `PATH`.

The wrappers can be started by double-clicking them in Windows Explorer. Running them from CMD or Anaconda Prompt is recommended so the JSON result remains visible. Set `PAUSE_ON_EXIT=1` to pause before a double-clicked window closes; the default `0` closes automatically.

## Execution Order

Run wrappers from `ops\runbook_wrappers\` in numeric order. Wrapper 00 is environment preparation, not a Stage:

| Order | Wrapper | Calls |
| :--- | :--- | :--- |
| 00 | `00_prepare_next_runbook_day.cmd` | `%PYTHON_EXE% scripts\runbook_day_prep.py` to safely prepare `_runbook_day.local.cmd` from the latest completed runbook day |
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

## Starting A New Runbook Day

Run `00_prepare_next_runbook_day.cmd` once when starting a new runbook day. A `PASS` prints the generated `ACCOUNT_ID`, `DATA_DATE`, `TRADE_DATE`, and `RUNBOOK_DAY_ID`; review all four values before separately running `01_stage_a_plan_prep.cmd`. Wrapper 00 never runs wrapper 01 automatically.

If the current runbook day is incomplete or rollover is unsafe, wrapper 00 returns `BLOCKED`. Do not run wrapper 01 after a `BLOCKED` or `FAILED` result. An unchanged safe environment may return `PASS` with `file_changed=false`; this is idempotent and is not an error.

## Result Meanings

Always inspect the command JSON output. Check `runner_result`, `warnings`, `blockers`, and `next_required_action`; a process exit code of `0` can still require operator attention for `WAIT` or `WARNING`.

- `PASS`: The stage or gate completed and the next numbered wrapper may be considered.
- `WAIT`: The controller is waiting for required operator input or external state. Do not skip ahead.
- `WARNING`: The command ran, but operator review is required. In particular, `stage-d-preview` may return `WARNING` with exit code `0`. Do not proceed based on the exit code alone, and as a rule do not run `08_stage_d_append_sync.cmd` until the warnings have been reviewed.
- `BLOCKED`: A required precondition failed or a blocking inconsistency was detected. Stop and inspect the JSON reason.
- `FAILED`: The command failed. Stop and inspect the output and generated artifacts.

`WAIT` and `WARNING` must be reviewed directly in the JSON output. The wrappers do not approve warnings and must not be modified to add `--allow-warnings` automatically.

If Stage E has already returned `PASS` for the same `ACCOUNT_ID`, `DATA_DATE`, and `TRADE_DATE`, do not rerun Stage E for that runbook day unless a separate recovery procedure explicitly authorizes it.

Review all three local files before operational use. The full July 6 wrapper cycle belongs to the separate 6-4D procedure.

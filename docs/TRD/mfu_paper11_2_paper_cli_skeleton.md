# MFU-PAPER11-2 Paper CLI Skeleton

## Scope

- Add `scripts/paper.py` as a unified paper CLI entrypoint
- Support only `preflight`, `plan`, and `eod`
- Auto-run paper-specific preflight before `plan` and `eod`

## Added Components

- `scripts/paper.py`
- `tests/test_paper_cli.py`

## CLI

- `python scripts/paper.py`
- `python scripts/paper.py preflight --date YYYYMMDD --stage plan`
- `python scripts/paper.py plan --date YYYYMMDD`
- `python scripts/paper.py eod --date YYYYMMDD --dry-run`
- `python scripts/paper.py eod --date YYYYMMDD --commit`

## Notes

- `plan` wraps `scripts/run_paper_daily_plan.py` logic through its existing wrapper function
- `eod` wraps `scripts/run_paper_eod_update.py` logic through its existing wrapper function
- `plan` and `eod` stop on preflight `FAIL`
- `eod --commit` is explicit only
- No reports, review, market-data, or run-all commands are included in this MFU

# MFU-PAPER11-1 Paper Preflight Check

## Scope

- Add a paper-specific preflight checker for operational readiness
- Keep the workflow read-only by default
- Support stage-based checks for plan, EOD, reports, and review workflow

## Added Components

- `core/paper_preflight_check.py`
- `scripts/check_paper_preflight.py`
- `tests/test_paper_preflight_check.py`

## CLI

- `python scripts/check_paper_preflight.py --date YYYYMMDD --stage plan`
- `python scripts/check_paper_preflight.py --date YYYYMMDD --stage eod`
- `python scripts/check_paper_preflight.py --stage reports`
- `python scripts/check_paper_preflight.py --stage review-template`
- `python scripts/check_paper_preflight.py --stage review-append`
- `python scripts/check_paper_preflight.py --date YYYYMMDD --stage all --strict`

## Notes

- Default execution is read-only and prints readiness status to the console
- `--write-report` optionally writes markdown and issues CSV under `outputs/paper_test/reports/`
- Warnings and errors are separated
- Strict mode escalates warnings to errors
- Existing `core/preflight_check.py` is unchanged

# MFU-PAPER11-4 Paper Review Wrapper

## Scope

- Extend `scripts/paper.py` with explicit review workflow subcommands
- Support `review-template`, `review-validate`, and `review-append`
- Keep append explicit and separate from reports

## Added Components

- `scripts/paper.py` updates
- `tests/test_paper_cli.py` updates

## CLI

- `python scripts/paper.py review-template`
- `python scripts/paper.py review-validate`
- `python scripts/paper.py review-append`

## Notes

- `review-template` runs `stage=review-template` preflight first
- `review-validate` calls the validator directly and returns exit code 1 only when validation errors exist
- `review-append` runs `stage=review-append` preflight first
- There is still no integrated `review` meta-command
- This wrapper does not add row overwrite/update behavior

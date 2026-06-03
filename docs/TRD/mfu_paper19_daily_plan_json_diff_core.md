# PAPER19-2 Daily Plan JSON Diff Core

## 1. Purpose

PAPER19-2 implements the first minimal Replay / Same-date Diff harness: compare two provided Daily Plan JSON files and generate JSON/Markdown diff reports.

This is pure comparison. It does not regenerate a Daily Plan, execute replay, call Notion, export to Notion, or mutate source-of-truth artifacts.

## 2. Scope

Included:

- baseline Daily Plan JSON input
- regenerated Daily Plan JSON input
- single `account_id`
- single `plan_date`
- row-level comparison by `symbol + action`
- JSON diff output
- Markdown diff output
- fingerprint cause candidate reporting

Excluded:

- automatic plan regeneration
- `paper.py plan` execution
- execution/review replay
- Notion replay or export
- actual export
- schema/view drift
- Telegram/Slack/Email delivery

## 3. CLI

Command:

```cmd
python scripts\dev\diff_daily_plan.py --account-id paper_sandbox --date 2026-05-20 --baseline-plan <path> --regenerated-plan <path> --output-dir <path> --json
```

Supported options:

- `--account-id`
- `--date`
- `--baseline-plan`
- `--regenerated-plan`
- `--output-dir`
- `--json`

The CLI does not auto-discover source paths in PAPER19-2. Explicit file inputs are required.

## 4. Input Contract

The input JSON should expose or normalize to:

- `account_id`
- `plan_date` or `date`
- `items`, `action_items`, `actions`, or `rows`
- optional `metadata`
- optional `fingerprints`

Compared row fields:

- `symbol`
- `action`
- `quantity`
- `price`
- `warning`
- `reason`
- `note`

Optional row fields are compared when present:

- `cash_impact`
- `allocation`
- `target_weight`
- `stop_price`

Missing or malformed input returns `FAIL`.

## 5. Row Identity Policy

Default row key:

```text
symbol + action
```

Rules:

- baseline-only key -> `SYMBOL_SET_DIFF`
- regenerated-only key -> `SYMBOL_SET_DIFF`
- matching key -> compare fields
- one row per symbol on both sides with different action -> `ACTION_DIFF`
- duplicate `symbol + action` key -> `DUPLICATE_ROW_KEY`

Duplicate row keys are not auto-matched by list order.

## 6. Diff Categories

Implemented categories:

- `NO_DIFF`
- `METADATA_DIFF`
- `WARNING_DIFF`
- `PRICE_DIFF`
- `QUANTITY_DIFF`
- `ACTION_DIFF`
- `SYMBOL_SET_DIFF`
- `DUPLICATE_ROW_KEY`
- `CONFIG_OR_UNIVERSE_DIFF`
- `STATE_OR_MARKET_FINGERPRINT_DIFF`
- `MALFORMED_INPUT`
- `ACCOUNT_DATE_MISMATCH`
- `MISSING_INPUT`

## 7. PASS / WARNING / FAIL Policy

`PASS`:

- no core field differences
- `NO_DIFF`

`PASS_WITH_METADATA_DIFF`:

- only metadata differs
- no operator-facing plan row changed

`WARNING`:

- price difference
- warning/reason/note difference
- fingerprint-only difference
- duplicate row key

`FAIL`:

- missing input
- malformed input
- account/date mismatch
- symbol set difference
- action difference
- quantity difference

If multiple differences exist, the most severe status becomes `overall_status`.

## 8. Fingerprint / Cause Candidate Policy

Compared fingerprint fields:

- `config_hash`
- `universe_hash`
- `state_snapshot_hash`
- `state_snapshot_path`
- `market_data_asof`
- `indicator_snapshot_hash`
- `code_commit_sha`
- `generator_version`

Policy:

- full snapshots are not copied into the report
- fingerprint differences are cause candidates only
- the report does not claim root cause
- wording uses "possible cause candidate", not "because"

## 9. JSON / Markdown Output

JSON envelope:

```json
{
  "schema_version": "paper_daily_plan_replay_diff.v1",
  "account_id": "paper_sandbox",
  "plan_date": "2026-05-20",
  "overall_status": "WARNING",
  "diff_categories": ["PRICE_DIFF"],
  "summary": {},
  "diffs": [],
  "fingerprint_diffs": [],
  "cause_candidates": [],
  "write_executed": false
}
```

Markdown sections:

- Summary
- Failures
- Warnings
- Metadata / Fingerprint Differences
- Cause Candidates
- Input Files
- Safety Notes

Default output path:

```text
outputs/paper_accounts/{account_id}/replay_diff/paper_daily_plan_diff_{YYYYMMDD}.json
outputs/paper_accounts/{account_id}/replay_diff/paper_daily_plan_diff_{YYYYMMDD}.md
```

Tests and smoke use `tmp_path` / `--output-dir`.

## 10. Test Coverage

Covered by `tests/test_paper_replay_diff.py`:

- same plan -> `PASS` / `NO_DIFF`
- metadata-only diff -> `PASS_WITH_METADATA_DIFF`
- symbol set diff -> `FAIL`
- action diff -> `FAIL`
- quantity diff -> `FAIL`
- price diff -> `WARNING`
- warning/reason diff -> `WARNING`
- config hash diff -> cause candidate
- universe hash diff -> cause candidate
- account/date mismatch -> `FAIL`
- missing input -> `FAIL`
- malformed input -> `FAIL`
- duplicate row key -> `WARNING`
- JSON/Markdown output generation
- CLI fixture smoke with `tmp_path`

## 11. Limitations

- Inputs must already be JSON.
- The CLI does not regenerate Daily Plans.
- The CLI does not auto-discover account/date source paths.
- Price comparison is exact.
- Duplicate row keys are reported but not resolved.
- Row identity is not stable if `symbol + action` is insufficient.
- Existing Markdown/text regeneration diff utility remains separate.

## 12. PAPER19-3 Recommendation

Recommended PAPER19-3:

```text
Daily Plan Replay Diff Source Alignment / Optional Regeneration Wrapper Design
```

Possible scope:

- define how official/committed baseline JSON is produced or exported from existing Markdown plan artifacts
- decide whether regenerated JSON should be produced by a guarded wrapper
- keep automatic regeneration separate from pure diff
- preserve `tmp_path` tests and no real outputs mutation
- consider stable row id policy if duplicate `symbol + action` appears in real plans

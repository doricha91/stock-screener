# PAPER19-1 Replay / Same-date Diff Scope and Contract

## 1. Purpose

PAPER19 defines a minimal reproducibility check for paper operations. The core question is:

```text
For the same account/date, does a regenerated Daily Plan match the existing official or committed Daily Plan?
If not, what changed, and which fingerprints are available as cause candidates?
```

This is an operational reproducibility guard, not a strategy performance improvement feature.

PAPER19-1 is design only. It does not regenerate plans, execute replay, call Notion, write exports, or modify outputs/paper ledgers.

## 2. Scope

Initial PAPER19 scope is limited to Daily Plan diff.

Included:

- baseline Daily Plan JSON
- regenerated Daily Plan JSON
- single `account_id`
- single `date`
- JSON diff report contract
- Markdown diff report contract
- fingerprint / cause candidate policy

Excluded:

- execution replay
- review replay
- Notion sync replay
- actual export replay
- complete portfolio state restoration
- multi-date batch replay
- automatic plan regeneration
- strategy/universe expansion

Existing note:

- `scripts/check_paper_plan_regeneration_diff.py` already exists as a related Markdown/text regeneration diff utility.
- PAPER19-1 does not run or modify it.
- PAPER19-2 should start with a safer two-JSON comparison contract before deciding whether to integrate or replace the older text-oriented harness.

## 3. Baseline / Regenerated Plan Definition

`baseline_plan`:

- the official or committed Daily Plan artifact for the target `account_id` and `plan_date`
- intended to represent the source-of-truth plan the operator already used or accepted

`regenerated_plan`:

- a Daily Plan artifact generated again for the same `account_id` and `plan_date`
- provided as a separate input artifact, not generated automatically in PAPER19-1

Policy:

- PAPER19-1 only defines comparison contracts.
- PAPER19-2 should compare two explicit JSON files first.
- Automatic regeneration can be added only after file comparison semantics are stable.

## 4. Input Contract

Required logical inputs:

```json
{
  "account_id": "paper_sandbox",
  "plan_date": "2026-05-20",
  "baseline_plan_json": "path/to/baseline.json",
  "regenerated_plan_json": "path/to/regenerated.json"
}
```

Plan JSON should expose or normalize to:

- `account_id`
- `plan_date`
- `items` or equivalent action rows
- optional `metadata`
- optional `fingerprints`

Each action row should be normalized around:

- `symbol`
- `action`
- `quantity`
- `price`
- `warning`
- `reason`
- `note`

Optional fields:

- `cash_impact`
- `allocation`
- `target_weight`
- `stop_price`

Input validation:

- account mismatch -> `FAIL`
- date mismatch -> `FAIL`
- malformed JSON -> `FAIL`
- missing baseline or regenerated input -> `FAIL`

## 5. Diff Fields

Initial exact comparison fields:

| Field | Required | Initial Comparison | Notes |
| --- | --- | --- | --- |
| `symbol` | Yes | exact | participates in symbol set and row identity |
| `action` | Yes | exact | action changes are fail-level |
| `quantity` | Yes | exact | quantity changes are fail-level |
| `price` | Yes | exact | warning-level initially; tolerance is future work |
| `warning` | No | exact / normalized text | warning changes are warning-level |
| `reason` | No | exact / normalized text | warning-level because operator explanation changed |
| `note` | No | exact / normalized text | warning-level |
| `cash_impact` | Candidate | exact initially | candidate field when present |
| `allocation` | Candidate | exact initially | candidate field when present |
| `target_weight` | Candidate | exact initially | candidate field when present |
| `stop_price` | Candidate | exact initially | candidate field when present |

Initial row matching should use `symbol + action` when possible. If the same symbol appears multiple times, PAPER19-2 should either require stable row ids or report `manual_review_required`.

## 6. Diff Categories

Initial categories:

- `NO_DIFF`
- `METADATA_DIFF`
- `WARNING_DIFF`
- `PRICE_DIFF`
- `QUANTITY_DIFF`
- `ACTION_DIFF`
- `SYMBOL_SET_DIFF`
- `CONFIG_OR_UNIVERSE_DIFF`
- `STATE_OR_MARKET_FINGERPRINT_DIFF`

Category intent:

- `NO_DIFF`: no meaningful difference.
- `METADATA_DIFF`: only metadata differs.
- `WARNING_DIFF`: `warning`, `reason`, or `note` differs.
- `PRICE_DIFF`: price differs under exact comparison.
- `QUANTITY_DIFF`: quantity differs.
- `ACTION_DIFF`: action differs for the same symbol/row.
- `SYMBOL_SET_DIFF`: symbols were added or removed.
- `CONFIG_OR_UNIVERSE_DIFF`: plan rows may or may not differ, but config/universe fingerprints differ.
- `STATE_OR_MARKET_FINGERPRINT_DIFF`: state or market as-of fingerprints differ.

## 7. PASS / WARNING / FAIL Policy

`PASS`:

- no core field differences
- `NO_DIFF`
- metadata-only differences may be `PASS_WITH_METADATA_DIFF` if no operator-facing plan row changed

`WARNING`:

- `WARNING_DIFF`
- `PRICE_DIFF`
- fingerprint-only differences with no action/quantity/symbol set change
- metadata differences that should be visible but do not change execution intent

`FAIL`:

- `SYMBOL_SET_DIFF`
- `ACTION_DIFF`
- `QUANTITY_DIFF`
- account/date mismatch
- malformed or missing required input

Initial price policy:

- exact comparison only
- tolerance is future work
- if tolerance is later introduced, the report must record tolerance value and comparison mode

## 8. Fingerprint / Cause Candidate Policy

The report records cause candidates, not confirmed root causes.

Candidate fingerprints:

- `config_hash`
- `universe_hash`
- `state_snapshot_hash`
- `state_snapshot_path`
- `market_data_asof`
- `indicator_snapshot_hash`
- `code_commit_sha`
- `generator_version`

Rules:

- do not copy full snapshots into the report
- record hash, path, as-of, and commit SHA only
- do not expose secrets or absolute paths when avoidable
- do not assert causality from fingerprint differences

Allowed wording:

```text
Quantity differs, and config fingerprint also differs. Config change is a cause candidate.
```

Forbidden wording:

```text
Quantity differs because config changed.
```

## 9. Output Path Policy

Default account-aware paths:

```text
outputs/paper_accounts/{account_id}/replay_diff/paper_daily_plan_diff_{YYYYMMDD}.json
outputs/paper_accounts/{account_id}/replay_diff/paper_daily_plan_diff_{YYYYMMDD}.md
```

Test and smoke policy:

- use `tmp_path`
- support `--output-dir` in future CLI
- do not write to real `outputs/paper_accounts` during tests
- do not overwrite baseline Daily Plan artifacts

Legacy note:

- existing `core.paper_account_paths.PaperAccountPaths.regenerated_daily_action_plan_path()` already points to an account `replay_diff` directory.
- PAPER19-2 should align with account-aware path helpers instead of hardcoding paths.

## 10. JSON / Markdown Report Shape

JSON envelope candidate:

```json
{
  "schema_version": "paper_daily_plan_diff.v1",
  "account_id": "paper_sandbox",
  "plan_date": "2026-05-20",
  "overall_status": "WARNING",
  "diff_categories": ["PRICE_DIFF", "CONFIG_OR_UNIVERSE_DIFF"],
  "summary": {
    "added_symbols": 0,
    "removed_symbols": 0,
    "action_diff_count": 0,
    "quantity_diff_count": 0,
    "price_diff_count": 1,
    "warning_diff_count": 0
  },
  "items": [],
  "fingerprints": {
    "baseline": {},
    "regenerated": {},
    "cause_candidates": []
  },
  "write_executed": false
}
```

Item candidate:

```json
{
  "category": "PRICE_DIFF",
  "symbol": "AAPL",
  "baseline": {"price": 100.0},
  "regenerated": {"price": 101.0},
  "severity": "WARNING",
  "cause_candidates": ["market_data_asof differs"],
  "message": "Price differs under exact comparison."
}
```

Markdown structure:

```text
# Paper Daily Plan Same-date Diff - {account_id} - {YYYY-MM-DD}

## Summary
- Overall Status
- Diff Categories
- Added / Removed Symbols
- Action / Quantity / Price / Warning Diff Counts

## Fail-level Differences

## Warning-level Differences

## Metadata / Fingerprint Differences

## Cause Candidates

## Source Inputs

## Safety Notes
```

## 11. Test Strategy

PAPER19-2 tests should use fixture JSON pairs and `tmp_path`.

Required test candidates:

- same plan -> `PASS` / `NO_DIFF`
- symbol added/removed -> `FAIL` / `SYMBOL_SET_DIFF`
- action changed -> `FAIL` / `ACTION_DIFF`
- quantity changed -> `FAIL` / `QUANTITY_DIFF`
- price changed -> `WARNING` / `PRICE_DIFF`
- warning/reason/note changed -> `WARNING` / `WARNING_DIFF`
- metadata-only changed -> `PASS_WITH_METADATA_DIFF` or `WARNING`, depending on final policy
- `config_hash` changed -> cause candidate recorded
- `universe_hash` changed -> cause candidate recorded
- state/market fingerprint changed -> cause candidate recorded
- malformed JSON -> `FAIL`
- account/date mismatch -> `FAIL`
- JSON report generated
- Markdown report generated
- no real outputs pollution

## 12. Non-scope

PAPER19-1 does not include:

- Python code implementation
- CLI implementation
- Daily Plan regeneration execution
- replay execution
- Notion API calls
- Notion write/export/sync
- actual export
- outputs/paper ledger modification
- real operating plan modification
- execution/review replay
- schema/view drift implementation
- Telegram/Slack/Email delivery

## 13. PAPER19-2 Recommendation

Recommended PAPER19-2:

```text
Daily Plan JSON Diff Core + CLI Dry-run
```

Suggested scope:

- implement a pure comparison function for two Daily Plan JSON payloads
- add CLI that accepts explicit `--baseline-plan-json` and `--regenerated-plan-json`
- write JSON/Markdown diff to `--output-dir` or account `replay_diff`
- use `tmp_path` fixture tests
- do not regenerate a plan automatically
- do not call Notion
- do not mutate official/committed Daily Plan artifacts

After JSON diff semantics are stable, a later MFU can decide whether and how to wrap automatic same-date regeneration.

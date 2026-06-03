# PAPER19-4 Daily Plan JSON Artifact Contract and Generation Structure Check

## 1. Purpose

PAPER19-4 checks whether Daily Plan replay/diff should continue relying on Markdown artifacts only or introduce a structured JSON artifact alongside Markdown.

This is a design and inspection document only. It does not implement a JSON producer, run Daily Plan generation, call Notion, or modify outputs/paper ledgers.

## 2. Current Daily Plan Generation Structure

Current generation entry points and flow:

| Area | Current Finding | Notes |
| --- | --- | --- |
| Official CLI | `scripts/run_paper_daily_plan.py` | Described as "Generate official paper daily plan". |
| Core generator | `core/daily_plan_generator.py::generate_daily_plan` | Builds candidate, rebalance, warning, and action data, then renders Markdown. |
| Non-default account path | `core/paper_account_paths.py::PaperAccountPaths.daily_action_plan_path` | Writes `daily_action_plan_YYYYMMDD.md` under the account root. |
| Default path fallback | `core.paths.paper_daily_action_plan_path` / legacy paper path | Used when account paths are absent or `paper_default` legacy path is selected. |
| Config snapshot JSON | `paper_config_snapshot_YYYYMMDD.json` | Separate config/fingerprint-like artifact, not a Daily Plan action JSON artifact. |
| Existing regeneration check | `scripts/check_paper_plan_regeneration_diff.py` | Regenerates Markdown and compares text/sections; it is not a JSON structured diff producer. |

Observed current behavior:

- `scripts/run_paper_daily_plan.py` loads the official paper state, resolves the Markdown output path, resolves the config snapshot path, and calls `generate_daily_plan`.
- `generate_daily_plan` creates internal `action_items`, `rebalance_review_items`, `warning_items`, `journal_rows`, diagnostics, and stale/freshness related lists before rendering.
- `format_markdown_report(...)` receives structured Python lists/dicts and returns Markdown text.
- The generator writes Markdown to `daily_action_plan_YYYYMMDD.md`.
- The generator can write a config snapshot JSON via `save_paper_config_snapshot`, but no persisted Daily Plan JSON action artifact was found.
- Daily Ops / Notion SOP references Daily Plan source artifacts as Markdown Daily Plan plus config snapshot JSON.

Items that need follow-up inspection before implementation:

- exact `official_run` and `run_mode` propagation into a future Daily Plan JSON schema
- whether every Markdown-visible action/review/warning field is available before formatting
- whether current action item keys are stable enough for replay identity or need a normalized row object

## 3. Markdown-only Diff Assessment

Markdown-only diff advantages:

- Uses the existing official artifact directly.
- Requires no new JSON producer.
- Has the smallest short-term implementation cost.
- Existing text regeneration check already operates in this direction.

Markdown-only diff limitations:

- Sensitive to table formatting, wording, ordering, encoding, and whitespace changes.
- Weak extraction stability for `symbol`, `action`, `quantity`, `price`, `warning`, `reason`, and `note`.
- Hard to distinguish semantic plan changes from presentation changes.
- Harder to feed into PAPER18 alerts, future replay wrapper, and automated cause-candidate analysis.
- Encourages parsing rendered Markdown back into structure, which is brittle and can diverge from generator intent.

Assessment:

Markdown diff is acceptable as a short-term fallback or diagnostic, but it is not robust enough as the long-term replay/same-date diff contract. PAPER19 should prefer a structured JSON artifact once the producer boundary is explicit.

## 4. JSON Artifact Contract

Candidate Daily Plan JSON schema:

```json
{
  "schema_version": "paper_daily_plan.v1",
  "account_id": "paper_sandbox",
  "plan_date": "2026-05-20",
  "run_mode": "exploratory",
  "official_run": false,
  "generated_at": "2026-05-20T00:00:00Z",
  "items": [
    {
      "plan_item_id": "candidate-or-future-stable-id",
      "symbol": "AAPL",
      "action": "BUY",
      "quantity": 10,
      "price": 200.0,
      "warning": null,
      "reason": "STRATEGY_ENTRY",
      "note": null
    }
  ],
  "fingerprints": {
    "config_hash": "optional",
    "universe_hash": "optional",
    "state_snapshot_hash": "optional",
    "state_snapshot_path": "optional",
    "market_data_asof": "optional",
    "indicator_snapshot_hash": "optional",
    "code_commit_sha": "optional",
    "generator_version": "optional"
  },
  "source_refs": {
    "markdown_path": "optional",
    "config_snapshot_path": "optional"
  }
}
```

Contract rules:

- `schema_version`, `account_id`, `plan_date`, `generated_at`, and `items` should be required.
- `run_mode` and `official_run` should become required once the paper ops run-mode contract is finalized.
- Missing optional numeric fields should be omitted or `null`, not guessed from Markdown.
- The JSON artifact should contain normalized semantic plan rows, not Markdown fragments.
- Full market/config/state snapshots should not be copied into the Daily Plan JSON; use hashes, paths, as-of dates, and version identifiers.

## 5. Markdown + JSON Shared Source Principle

The generator should not produce Markdown first and then parse that Markdown into JSON.

Required principle:

```text
Build one normalized Daily Plan object.
Render Markdown from that object.
Serialize JSON from that same object.
```

Why:

- prevents Markdown/JSON semantic drift
- keeps replay diff aligned with the actual plan generation intent
- avoids fragile table parsing
- gives PAPER19 diff and PAPER18 alerts a stable structured input

If a temporary Markdown-to-JSON converter is ever added, it should be labeled as migration/backfill tooling, not the official Daily Plan JSON producer.

## 6. Baseline / Regenerated JSON Policy

Definitions:

```text
baseline JSON = official or committed Daily Plan artifact used by the operator
regenerated JSON = replay/diff dry-run artifact generated separately for the same account/date
```

Policy:

- Baseline JSON must represent the accepted/official plan, not an arbitrary preview.
- Regenerated JSON must never overwrite baseline JSON.
- Regenerated JSON should be written under replay-specific paths.
- Diff reports should compare two JSON files and should not trigger plan generation by themselves.
- JSON producer implementation should come before a regeneration wrapper that depends on it.

## 7. Proposed Output Paths

Existing account-aware paths include:

```text
outputs/paper_accounts/{account_id}/daily_action_plan_{YYYYMMDD}.md
outputs/paper_accounts/{account_id}/config_snapshots/paper_config_snapshot_{YYYYMMDD}.json
outputs/paper_accounts/{account_id}/replay_diff/
```

Candidate baseline JSON paths:

```text
outputs/paper_accounts/{account_id}/plans/daily_plan_{YYYYMMDD}.json
outputs/paper_accounts/{account_id}/daily_plan_{YYYYMMDD}.json
outputs/paper_accounts/{account_id}/replay_diff/baseline_daily_plan_{YYYYMMDD}.json
```

Candidate regenerated JSON paths:

```text
outputs/paper_accounts/{account_id}/replay_diff/regenerated_daily_plan_{YYYYMMDD}.json
outputs/paper_accounts/{account_id}/replay_diff/runs/{run_id}/regenerated_daily_plan.json
```

Recommendation:

- Use an account-root `plans/` directory for official/committed baseline JSON if a new directory is acceptable.
- Use `replay_diff/runs/{run_id}/` for repeated regenerated artifacts.
- Keep legacy Markdown path unchanged until the JSON sidecar is proven stable.

## 8. Required Fields

Minimum required fields for PAPER19 diff compatibility:

| Field | Required | Purpose |
| --- | --- | --- |
| `schema_version` | Yes | Versioned artifact contract. |
| `account_id` | Yes | Account scoping and mismatch detection. |
| `plan_date` | Yes | Same-date diff contract. |
| `generated_at` | Yes | Metadata and audit. |
| `items` | Yes | Plan rows to compare. |
| `items[].symbol` | Yes | Row identity and symbol set diff. |
| `items[].action` | Yes | Row identity and action diff. |
| `items[].quantity` | Yes for actionable rows | Quantity diff. |
| `items[].price` | Yes when available | Price diff. |
| `items[].warning` | Recommended | Warning diff. |
| `items[].reason` | Recommended | Warning/reason diff and operator context. |
| `items[].note` | Recommended | Operator context. |

`plan_item_id` is recommended as a future stable row identity but should not be fabricated if the producer cannot guarantee determinism.

## 9. Optional Fields / Fingerprints

Optional comparison and cause-candidate fields:

| Field | Purpose |
| --- | --- |
| `cash_impact` | Optional financial impact comparison. |
| `allocation` | Optional allocation diff. |
| `target_weight` | Optional target allocation diff. |
| `stop_price` | Optional risk/exit parameter diff. |
| `fingerprints.config_hash` | Config change candidate. |
| `fingerprints.universe_hash` | Universe change candidate. |
| `fingerprints.state_snapshot_hash` | State snapshot change candidate. |
| `fingerprints.state_snapshot_path` | Trace pointer; do not inline snapshot. |
| `fingerprints.market_data_asof` | Market data as-of comparison. |
| `fingerprints.indicator_snapshot_hash` | Indicator data candidate. |
| `fingerprints.code_commit_sha` | Code version candidate. |
| `fingerprints.generator_version` | Generator contract version. |

Cause policy:

- Record fingerprint differences as possible cause candidates only.
- Do not state that a fingerprint difference caused a plan row difference.
- Do not copy full snapshots into the diff or plan JSON.

## 10. Implementation Options and Estimated Work

| Option | Description | Estimated Work | Assessment |
| --- | --- | --- | --- |
| A. JSON sidecar from existing structured data | Normalize current `action_items` and related warning/review structures before Markdown rendering, then serialize JSON beside Markdown. | 1-2 MFUs | Preferred if current internal data contains all required fields. |
| B. Introduce normalized Daily Plan object | Add a small object/builder that owns items, metadata, warnings, diagnostics, and fingerprints; render Markdown and JSON from it. | 2-3 MFUs | More work, but best long-term contract. |
| C. Markdown-to-JSON parser | Parse current `daily_action_plan_YYYYMMDD.md` into structured rows. | 1 MFU | Not recommended for official producer; acceptable only as temporary migration/backfill aid. |
| D. Keep Markdown-only diff | Continue using text/section diff for replay. | 0-1 MFU | Short-term fallback only; weak semantic guarantees. |

Current inspection suggests Option A may be feasible because `generate_daily_plan` already has internal structured `action_items`, warning lists, review lists, diagnostics, and config snapshot metadata before rendering. However, Option B may still be needed if the future contract requires stable row ids and consistent metadata across Markdown, JSON, alerts, and replay.

## 11. Risks

- Current `action_items` use keys such as `type`, `shares`, and `price`, while PAPER19 diff expects normalized `action`, `quantity`, and `price`.
- Review-only and warning-only items may not map cleanly to actionable Daily Plan rows without an explicit row type.
- `symbol + action` remains a minimal row key and may be insufficient when multiple rows share the same symbol/action.
- `official_run` and `run_mode` are not yet confirmed as stable fields in the Daily Plan generator boundary.
- Adding JSON output directly in the generator without a normalized object may create Markdown/JSON drift.
- Producer paths must not overwrite baseline artifacts during replay regeneration.

## 12. Non-scope

PAPER19-4 does not include:

- Python code modification
- JSON producer implementation
- Daily Plan generation execution
- `paper.py plan` execution
- replay wrapper implementation
- Notion API calls
- Notion write/export/sync
- actual export
- outputs/paper ledger modification
- real operating artifact modification

## 13. PAPER19-5 Recommendation

Recommended PAPER19-5:

```text
Daily Plan Normalized Object / JSON Sidecar Producer Design or Minimal Implementation
```

Suggested scope:

- define a normalized Daily Plan object built before Markdown rendering
- map current `action_items` fields to the PAPER19 JSON contract
- decide how review-only and warning-only rows appear in JSON
- add `schema_version`, `account_id`, `plan_date`, `generated_at`, and optional fingerprints
- write JSON sidecar without changing existing Markdown output
- keep plan generation execution and actual operations out of tests by using fixtures/fakes where possible

Do not start the regeneration wrapper until baseline JSON production is stable.

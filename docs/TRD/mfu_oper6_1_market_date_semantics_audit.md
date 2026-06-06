# MFU OPER6-1: Market Date Semantics Audit and KST Operating Window

## 1. Purpose

This document audits how paper operation date arguments are currently used and proposes a safer EOD date model that separates `data_date` from `trade_date`.

이번 MFU-OPER6-1은 Market Date Semantics Audit 및 KST 운영 시간대 설계 작업이며, 코드 수정, DB write, paper 원장 수정, Notion write/export/sync, Manual Execution commit, Manual Review append, broker/API 연동은 포함하지 않는다.

## 2. Scope / Non-scope

Scope:

- Inspect current date semantics in paper operation CLIs, Daily Plan generation, source artifacts, snapshots, reviews, and Notion external keys.
- Document the risk created by a single overloaded `--date`.
- Propose a future `data_date` / `trade_date` model and KST operating window policy.

Non-scope:

- Code changes.
- DB writes or market data refresh.
- Paper execution ledger or review log changes.
- Notion write/export/sync or Notion view changes.
- Manual Execution commit, Manual Review append, or broker/API integration.

## 3. Problem statement

The current paper workflow often uses one `--date` value for several different concepts:

- Korean local operation date.
- Last completed US market data date.
- Paper trade execution date.
- Daily Plan date.
- Manual Execution date.
- Snapshot date.
- Review date.
- Notion external key date.

This worked for the `paper_pilot_202606 / 2026-06-05` account-aware pilot as an end-to-end operational proof, but it is not a clean EOD market-date model. In an EOD strategy, the intended semantics should be:

- Use data through June 4 to trade on June 5.
- Use data through June 5 to trade on June 8.

The recommended model is:

- `operation_datetime_kst`: actual command execution time in Korea.
- `data_date`: last completed US market session used for signal calculation.
- `trade_date`: actual US trading day to record paper trades.
- `plan_date = trade_date`.
- `execution_date = trade_date`.
- `snapshot_date = trade_date`.
- `review_date = trade_date`.

## 4. Current --date behavior by CLI

| CLI | Current `--date` meaning | Notes |
| --- | --- | --- |
| `paper.py plan --date` | Target / plan date | Runs preflight for a `daily_action_plan_YYYYMMDD` path and calls `run_paper_daily_plan(date)`. This date is also passed as `target_date` into market analysis. |
| `paper.py preview --date` | Target date for data freshness, plan, and EOD dry-run | Shortcut runs data freshness, plan, then EOD dry-run with the same date. It currently does not support separate data/trade dates. |
| `paper.py commit --date` | EOD commit/snapshot date | Same-date guard checks existing account snapshot, position snapshot, and `paper_current_state_YYYYMMDD` for this date. |
| `paper.py eod --date` | EOD wrapper target date | Dry-run is read-only preview; commit can write ledger/state/snapshot artifacts for this date. |
| `paper.py status --date` | Status target date | Checks `daily_action_plan_YYYYMMDD.md`, `paper_current_state_YYYYMMDD.json`, same-date snapshots, execution rows, and review state. |
| `paper.py init-account --date` | Account bootstrap / initial snapshot date | Seeds the new account at this date. It currently doubles as account inception date. |
| `paper.py data-freshness --date` | Market data target date | Checks whether `daily_price`, `market_index`, indicators, and optional universe snapshot are fresh enough for that date. |
| `paper.py review` | No date argument | Runs reports, review-template, and review-validate using current account artifacts. Review rows carry their own `review_date`. |
| `import_notion_executions.py --date` | Execution date | Queries Notion `Manual Executions` where `Execution Date = date` and `Status = READY`; preview/commit sidecars use `manual_execution_import_*_YYYYMMDD`. |
| `import_notion_reviews.py --date` | Review date | Queries Notion `Manual Reviews` where `Review Date = date` and `Import Status = READY`; preview/commit sidecars use `manual_review_import_*_YYYYMMDD`. |
| `sync_notion_execution_status.py --date` | Execution date | Syncs Notion status for a commit report matching the execution date. |
| `sync_notion_review_status.py --date` | Review date | Syncs Notion status for a commit report matching the review date. |
| `export_paper_to_notion.py --date --daily-plan` | Daily Plan date | Selects account-specific `daily_action_plan_YYYYMMDD.md` plus matching config snapshot. |
| `export_paper_to_notion.py --date --daily-review-summary` | Review date | Builds/exports Daily Review Summary for this review date. |
| `export_paper_to_notion.py --date --manual-review-template` | Review date | Selects local review template rows for this date and creates/updates Manual Reviews rows. |
| `export_paper_to_notion.py --date --daily-ops-status` | Status date | Uses the date as Daily Ops Status date. |

Related inspected files:

- `scripts/paper.py`
- `scripts/run_paper_daily_plan.py`
- `scripts/import_notion_executions.py`
- `scripts/import_notion_reviews.py`
- `scripts/sync_notion_execution_status.py`
- `scripts/sync_notion_review_status.py`
- `scripts/export_paper_to_notion.py`

`core/paper_daily_plan.py` was listed in the prompt but is not present in this repository. The actual Daily Plan implementation is `core/daily_plan_generator.py`.

## 5. Daily Plan data_date behavior

Current behavior:

- `scripts/run_paper_daily_plan.py::run_paper_daily_plan(date_str)` normalizes `date_str` into `normalized_db_date`.
- It loads paper state using `load_official_paper_state_for_daily_plan(normalized_db_date)`.
- `core/paper_state_provider.py` filters execution log rows with `trade_date < plan_date`.
- It calls `generate_daily_plan(date_str=normalized_db_date, ...)`.
- `core/daily_plan_generator.py` sets `plan_date = date_str`.
- It calls `market_analyzer.get_market_state(target_date=plan_date, ...)`.
- It then sets `data_date = m_state["date"]`.

Implications:

- `plan_date` and `data_date` can differ if `market_analyzer` resolves a different available market date.
- `data_date` is printed in logs as `plan_date=..., data_date=...`.
- `data_date` is used for benchmark close, price history, holding sell diagnostics, and several score/indicator calculations.
- The Daily Plan JSON sidecar records `plan_date` but, based on the current payload builder, does not clearly expose top-level `data_date`.
- The config snapshot records `plan_date`, `market_state`, and `market_status_summary`; `data_date` may be inferable from `market_state.date` if present, but this is not a clean source contract.

Risk:

- Operators may think `--date` means the market data date, while artifact names, Notion keys, and source-of-truth state use it as plan/trade date.
- If `target_date` points to an in-progress US session, generator behavior depends on market analyzer and DB freshness behavior rather than an explicit EOD policy.

## 6. Execution / Snapshot / Review date behavior

Execution:

- `import_notion_executions.py --date` means `execution_date`.
- The importer reads Notion rows with `Execution Date = execution_date` and `Status = READY`.
- Commit writes paper execution log rows whose `date` is the execution date.
- Commit writes `manual_execution_import_commit_YYYYMMDD.json/md`.

Snapshot:

- Manual Execution commit uses `execution_date` as `snapshot_date`.
- It writes or updates:
  - `paper_account_snapshot.csv`
  - `paper_position_snapshot.csv`
  - `paper_current_state_YYYYMMDD.json`
- Market valuation is also attempted for `execution_date`.

Review:

- `import_notion_reviews.py --date` means `review_date`.
- The importer reads Notion rows with `Review Date = review_date` and `Import Status = READY`.
- Review append writes `manual_review_import_commit_YYYYMMDD.json/md` and appends review rows with the review date.

Status:

- `paper.py status --date` resolves a target date and checks plan, current state, snapshots, execution rows, reports, and review progress for that date.

Current coupling:

- In normal operation, `execution_date`, `snapshot_date`, and `review_date` are expected to equal the same paper operating date.
- That paper operating date should become `trade_date` in the future model.

## 7. Notion external key date behavior

External key builders in `core/notion_account_keys.py` use account-aware date keys:

| Notion object | Current key format | Date meaning |
| --- | --- | --- |
| Daily Plan | `daily_plan:{account_id}:{plan_date}` | Plan date, currently the CLI date |
| Manual Execution | `manual_execution:{account_id}:{execution_date}:{SYMBOL}:{SIDE}:{sequence}` | Execution date |
| Manual Review | `manual_review:{account_id}:{review_date}:{SYMBOL}:{question_id}` | Review date |
| Daily Review Summary | `daily_review_summary:{account_id}:{review_date}` | Review date |
| Account Snapshot | `account_snapshot:{account_id}:{snapshot_date}` | Snapshot date |

Daily Ops Status uses a status date in its own exporter path. Operationally this should align with `trade_date` once the new model is implemented.

Recommendation:

- Keep Notion external key dates tied to `trade_date` / operating date.
- Do not use `data_date` in Daily Plan external keys unless a future schema explicitly adds a separate data-date field.
- Add visible `Data Date` only if the Notion schema is intentionally expanded in a later MFU.

## 8. Guard / duplicate risk

Current guards:

- `paper.py commit --date` checks same-date snapshots and `paper_current_state_YYYYMMDD`.
- Plan preflight blocks non-default account plans before account inception date.
- Data freshness checks whether market DB data is available through a target date.

Current gaps:

- Same-date guard uses the single target date, which is currently also the plan/trade/snapshot date.
- There is no explicit `trade_date > data_date` guard.
- There is no explicit weekend/holiday guard for `trade_date`.
- There is no explicit "US regular session is in progress" guard.
- Data freshness can warn when latest data is older than target date, but this is still based on a single target date rather than explicit `data_date`.
- Daily Plan sidecar/config snapshot do not provide a clean top-level contract for both `data_date` and `trade_date`.

Duplicate risk:

- If a user treats `--date` as `data_date`, they may create plan/execution/snapshot artifacts under the wrong trading day.
- If a user reruns operations with a corrected date later, same-date guards may not catch cross-date semantic duplication.

## 9. Recommended date model

Recommended definitions:

| Field | Meaning |
| --- | --- |
| `operation_datetime_kst` | Real command execution time in Asia/Seoul |
| `data_date` | Last completed US market session used for signal calculation |
| `trade_date` | US trading day on which the paper trade is intended to execute and be recorded |
| `plan_date` | Alias of `trade_date` |
| `execution_date` | Alias of `trade_date` |
| `snapshot_date` | Alias of `trade_date` |
| `review_date` | Alias of `trade_date` |
| Notion external key date | Alias of `trade_date` for operating records |

Example:

```text
operation_datetime_kst = 2026-06-06 18:00 KST
data_date = 2026-06-05
trade_date = 2026-06-08
plan_date = 2026-06-08
execution_date = 2026-06-08
snapshot_date = 2026-06-08
review_date = 2026-06-08
```

Core policy:

- Daily Plan signal calculation uses `data_date`.
- Daily Plan artifact paths, execution import, snapshots, reviews, and Notion external keys use `trade_date`.
- Plan JSON/config snapshot should record both `data_date` and `trade_date`.
- Status should report both where available.

## 10. KST operating window recommendation

| KST window | Recommendation | Rationale |
| --- | --- | --- |
| `05:00~07:00` | Caution window | US market has just closed during daylight saving time. Provider data may be delayed. Do not proceed unless freshness is PASS. |
| `07:00~18:00` | Data-stable but low-operator-availability window | Data may be more stable, but the user has low manual operation availability. |
| `18:00~22:00` | Recommended core window | Best manual window for preparing next US trading day using prior completed US data. |
| `22:00~22:30` | Pre-open buffer | Use only for final checks and manual input buffer. Avoid new complex planning. |
| `22:30~05:00` | Block or strong-warning window during US daylight saving time | US regular session is in progress. EOD plan generation should be forbidden or strongly warned. |

Standard time note:

- During US standard time, regular US market hours are roughly one hour later in KST.
- Window policy should be resolver-based rather than hard-coded only to daylight saving time.

Recommended broad operating window:

- `05:00~22:30 KST` can be considered possible with guards.

Recommended core operating window:

- `18:00~22:00 KST`.

## 11. CLI design candidates

Preferred initial explicit CLI:

```cmd
python scripts\paper.py plan --data-date 2026-06-05 --trade-date 2026-06-08 --account-id paper_pilot_202606
```

Follow-up automatic resolver CLI:

```cmd
python scripts\paper.py plan --resolve-market-date --account-id paper_pilot_202606
```

Initial recommendation:

- Implement explicit `--data-date` / `--trade-date` first.
- Keep `--resolve-market-date` as a later feature after the resolver and calendar policy are tested.
- Continue supporting legacy `--date` temporarily as an alias for `trade_date`, but warn that it is ambiguous.

Propagation design:

- `paper.py plan`: accepts `--data-date` and `--trade-date`; writes plan artifacts for `trade_date`; uses `data_date` for signal calculation.
- `export_paper_to_notion.py --daily-plan`: selects Daily Plan artifact by `trade_date`.
- `import_notion_executions.py --date`: remains `execution_date = trade_date`.
- `import_notion_reviews.py --date`: remains `review_date = trade_date`.
- `paper.py status --date`: remains status/trade date, but should display source `data_date` if a plan sidecar exists.

## 12. Market Date Resolver design candidate

Candidate module:

```text
core/market_date_resolver.py
```

Candidate return payload:

```json
{
  "operation_datetime": "2026-06-06T18:00:00+09:00",
  "operation_timezone": "Asia/Seoul",
  "market_timezone": "America/New_York",
  "data_date": "2026-06-05",
  "trade_date": "2026-06-08",
  "resolution_status": "PASS",
  "warnings": [],
  "errors": []
}
```

Required guard candidates:

- `data_date` must exist in `market_data.db`.
- `data_date` freshness `FAIL` blocks planning.
- `data_date` freshness `WARNING` blocks by default unless explicitly allowed.
- `trade_date <= data_date` blocks.
- Weekend `trade_date` blocks.
- US holiday `trade_date` blocks or warns depending on calendar confidence.
- Same `account_id + trade_date` plan/commit triggers same-date guard.
- If current KST time overlaps US regular session, EOD plan generation blocks or warns strongly.

US holiday handling options:

1. Use actual trading dates from the `market_index` table.
   - Pros: uses local market data reality.
   - Cons: missing/stale market data can be confused with holiday.

2. Add a dedicated market calendar helper.
   - Pros: clearer date semantics and holiday handling.
   - Cons: adds dependency/design work and needs tests.

3. Initial version blocks weekends and treats holidays as WARNING.
   - Pros: smallest implementation.
   - Cons: less safe around real US holidays and exchange closures.

Recommended path:

- Start with explicit `--data-date` / `--trade-date`, weekend block, freshness guards, and market-index calendar warning.
- Add a dedicated calendar helper after behavior is proven.

## 13. Existing 2026-06-05 pilot interpretation

The `paper_pilot_202606 / 2026-06-05` pilot should be preserved as-is.

Interpretation:

- It successfully validated the account-aware operating loop.
- It reached `REVIEW_DONE`.
- It proved the Daily Plan, Notion export, Manual Execution, review, append, sync, and status pipeline can close out for a non-default account.
- It was performed before explicit `data_date` / `trade_date` separation.
- It has market-date semantic limitations and should not be treated as a clean official EOD trading-day performance sample.

Policy:

- Do not edit existing artifacts or logs.
- Do not rewrite generated outputs.
- Use the pilot as account-aware workflow validation, not as final market-date policy validation.

## 14. Risks and open questions

Risks:

- Legacy `--date` remains ambiguous until code changes are made.
- Plan artifacts currently encode only one date in filenames.
- Daily Plan sidecar does not cleanly expose both `data_date` and `trade_date`.
- Market analyzer may resolve `data_date` implicitly, which is hard for operators to audit.
- Market data freshness currently checks a target date but does not know whether that date is intended as data date or trade date.
- Full US holiday treatment needs a calendar policy.

Open questions:

- Should legacy `--date` be deprecated immediately or retained with warnings?
- Should Notion Daily Plans add a `Data Date` property later?
- Should Daily Ops Status include both `Data Date` and `Trade Date`?
- Should `data_date` be derived from `market_index` only, or from a combined price/index/indicator freshness model?
- Should the resolver account for early close days?

## 15. Recommended next MFU

Recommended next MFU: implement explicit Market Date semantics.

Suggested scope:

1. Add `core/market_date_resolver.py` as a read-only helper.
2. Add explicit `--data-date` / `--trade-date` to `paper.py plan`.
3. Keep legacy `--date` with a warning or compatibility path.
4. Write `data_date` and `trade_date` into Daily Plan JSON sidecar and config snapshot.
5. Add guards:
   - `data_date` exists and freshness passes.
   - `trade_date > data_date`.
   - `trade_date` is not a weekend.
   - same `account_id + trade_date` plan/commit is guarded.
6. Add tests using temporary artifacts, not real `outputs/`.

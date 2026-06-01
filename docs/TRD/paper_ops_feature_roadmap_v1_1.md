## Purpose

Version 1.1 roadmap for paper operations after the PAPER15 multi-account foundation closeout.

## Roadmap Policy

- v1.0 priority order is preserved
- foundation completion is marked explicitly
- convenience layers remain lower priority than operational safety
- strategy/universe/profile work is not a PAPER15 blocker
- CSV/JSON/Markdown/SQLite remain source-of-truth; Notion remains input, review, staging, and presentation layer

## 0. Multi-account Foundation

Status: completed as foundation

Completed scope:

- account-aware path resolver
- non-default account root/config foundation
- non-default writer routing
- `paper_sandbox` rehearsal
- review workflow local semantics
- Daily Ops Status design, mapping/schema, dry-run exporter, limited actual export
- `init-account` bootstrap

Deferred sub-items:

- prepare/preview account-aware audit
- duplicate Notion row audit
- `paper_default` root convergence

## 1. Daily Ops Status Dashboard

Priority: P2 roadmap implementation, P1 operator documentation

Goals:

- stabilize Daily Ops Status operating view
- define update/runbook policy
- clarify `REVIEW_READY / REVIEW_PARTIAL / REVIEW_DONE` operator actions

## 1.5 Export / Sync Policy

Priority: P1/P2

Goals:

- document allowed vs forbidden actual write commands
- clarify dry-run vs confirm-actual semantics
- keep single-row guarded actual exports before any bulk policy

Command map policy:

- allowed:
  - guarded `Daily Ops Status` actual export for approved sandbox/non-default accounts
  - read-only dry-run exports
- forbidden:
  - multi-account bulk export
  - `paper_default` actual export for new multi-account flows
  - cloud-triggered export without explicit safety review

## 1.6 CLI Operational Simplification Candidate

Priority: P3

Current CLI problems:

- `paper.py` and `export_paper_to_notion.py` are split
- dry-run vs confirm-actual is easy to misuse
- account count growth raises command error risk

Policy:

- no wrapper CLI in PAPER15 closeout
- first stabilize 2 to 3 account operating patterns
- revisit wrapper CLI only after Daily Ops Status, Alert, Replay, and Schema Drift work matures

## 2. Alert / Monitoring Report

Priority: P2

Goals:

- surface blocking state early
- summarize status drift and missing artifact conditions
- prepare operator-facing monitoring before automation

## 2.5 Replay / Same-date Diff Minimum Harness

Priority: P2

Goals:

- compare regenerated outputs for same-date runs
- reduce accidental drift before automation layers

## 3. Notion UI Improvement

Priority: P3

Goals:

- clearer views
- operator-friendly grouped dashboards
- reduced navigation cost

## 3.5 Notion Schema Drift Check

Priority: P2

Goals:

- regular read-only validation
- clearer FAIL/WARNING handling
- operational response when schema and code diverge

## 4. Universe Change Preview -> Universe Expansion

Priority: P2

Before full universe expansion, formalize:

- `universe_id`
- `benchmark_id`
- account boundary for universe selection

Universe expansion should not happen before the account/profile boundary is defined.

Timing criteria:

- PAPER15 does not implement strategy, universe, or risk profiles as official per-account config
- define the account/profile boundary before Universe Change Preview
- formalize `universe_id` and `benchmark_id` during Universe expansion

## 5. Strategy Expansion

Priority: P2

Before strategy expansion, formalize:

- `strategy_profile_id`
- `risk_profile_id`
- per-account official run policy

Candidate per-account variables:

- `account_id`
- `display_name`
- `initial_cash`
- `currency`
- `benchmark_id`
- `universe_id`
- `strategy_profile_id`
- `risk_profile_id`
- `max_positions`
- `hedge_enabled`
- `official_run`

Candidate strategy profile variables:

- `entry_period`
- `exit_period`
- `rs_lookback`
- `atr_period`
- `score_threshold`
- indicator weights
- `trailing_stop_multiplier`
- regime-specific overrides

Candidate run-level variables:

- run date
- dry-run / actual
- `run_mode`
- `official_run`

Timing criteria:

- formalize `strategy_profile_id` and `risk_profile_id` before strategy expansion
- profile implementation is a prerequisite for Universe/Strategy expansion, but not a PAPER15 closeout blocker

## Priority Classification

### P0 Immediate Safety

- data corruption
- wrong write target
- account cross-contamination
- source-of-truth damage

### P1 Closeout / SOP

- PAPER15 closeout
- Daily Ops Status operator usage
- `init-account` usage
- current allowed/forbidden command set

### P2 Follow-up Roadmap

- account/profile boundary, explicitly not a PAPER15 completed feature
- `strategy_profile_id`, `universe_id`, `risk_profile_id`
- prepare/preview account-aware audit
- duplicate row audit
- `paper_default` root convergence
- alert/reporting
- replay harness
- schema drift check

### P3 Convenience

- wrapper CLI
- GUI
- GitHub Actions
- Notion button execution

## Recommended PAPER16+ Sequence

1. Daily Ops Status dashboard and SOP refinement
2. export/sync policy and command map hardening
3. alert / monitoring report
4. replay / same-date diff harness
5. schema drift operationalization
6. account/profile boundary formalization
7. universe expansion
8. strategy expansion

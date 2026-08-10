# StockScreener Current Roadmap

Status: Canonical

Last Updated: 2026-08-10

Branch: `gemini_cli_update`

Verified HEAD: `b140614ba90365c6fac520c326af1c7a1466f90a`

Evidence Baseline: `SYSTEM-AUDIT-20260810`

## A. Document Authority

`docs/ROADMAP_CURRENT.md` is the single canonical roadmap for the current development status, operating scope, and priority order of StockScreener.

When an older roadmap's “current status” or “next work” conflicts with this document, use this document for current status and priority. Runtime behavior and technical contracts must still be verified against the current implementation and accepted contract; this roadmap does not replace detailed PRD/TRD documents.

Authority hierarchy:

```text
Current code / tests / accepted operating contract
-> ROADMAP_CURRENT.md current status and priority
-> latest approved initiative-specific PRD/TRD
-> historical roadmaps and design history
```

Historical roadmaps, PRDs, and TRDs remain design evidence. Do not resolve a detailed technical conflict from roadmap prose alone; inspect the current implementation and accepted initiative contract.

## B. Current System Status

StockScreener is a mature, safety-oriented paper-trading operations system. Daily and weekly operation is supported within the verified paper-account scope.

- The accepted lifecycle covers Stage A -> Gate 1 -> Stage B -> verification -> Stage C -> Gate 2 -> Stage D -> Stage E -> Stage F -> completion -> rollover.
- Idempotency, recovery, no-action operation, completion manifests, legacy completion classification, zero-progress retirement, and next-day preparation exist.
- There are no evidence-backed P0 blockers.
- The current phase is **operate safely while hardening reliability before expansion**.

This does not mean that every historical roadmap is complete. The system is not live-ready, fully automated, fully expanded across all accounts/profiles, or complete across every research architecture.

## C. Current Operating Scope

### Currently allowed

- Operate verified paper accounts with the current Windows wrappers and runbook.
- Generate a date-aware Daily Plan.
- Use Manual Execution as the official paper execution path.
- Perform Manual Review through the current local and Notion staging/input/review flow.
- Complete the frozen A-F lifecycle, completion verification, and rollover.
- Produce daily paper-operation evidence, weekly reports, reviews, and the current benchmark comparison.
- Use Python as the validation and business-judgment engine. Local CSV/JSON/Markdown/SQLite artifacts remain source of truth; Notion remains staging/input/review/presentation.

### Not currently expanding or enabling

- Broad rollout to unverified accounts.
- Large additions of strategy, risk, or universe profiles.
- Approval-triggered Telegram write execution.
- Trading or business judgment embedded in n8n.
- Live broker or real-order integration.

The remaining P1 work limits expansion; it does not make the verified paper-operation scope unavailable.

## D. Completed Foundations

- Market-data, as-of universe, technical screening, and ensemble foundation.
- Market regime, safety triggers, cash, hedge, sizing, and long-position-cap policy.
- Paper ledger, account state, valuation, snapshots, and reports.
- Date-aware Daily Plan with sidecar and replay foundations.
- Manual Execution, reconciliation, commit, and status sync.
- Manual Review preparation, append, and status sync.
- Reporting and the current initial-capital benchmark comparison.
- Read-only Daily Ops Orchestrator and operator summary.
- Frozen A-F runbook with gates and Stage B verification.
- Idempotency, safe recovery, no-action lifecycle, and strict completion evidence.
- Legacy completion classification, zero-progress retirement, and rollover/day preparation.
- Windows operator wrappers.

## E. OPERATE NOW — P1

P0: **none**.

### 1. ACCT-01 — Multi-account vertical-slice closure

| Field | Value |
|---|---|
| Status | MOSTLY_COMPLETE |
| Necessity | MUST |
| Urgency | P1 |
| Why now | Residual default-root or profile fallback can mix account data when operation expands beyond proven accounts. |
| Done when | Every plan, report, replay, alert, export, and write boundary resolves and validates one account root with no silent `paper_test` fallback. |
| Expansion blocked until? | **YES** — broad multi-account and profile expansion |

### 2. REPLAY-01 — Stable action identity and non-empty replay

| Field | Value |
|---|---|
| Status | MOSTLY_COMPLETE |
| Necessity | MUST |
| Urgency | P1 |
| Why now | Replay must remain deterministic when the same symbol/date contains multiple actions or row order changes. |
| Done when | A stable action identity policy and non-empty replay corpus prove deterministic, order-independent matching, including duplicate symbol/action cases. |
| Expansion blocked until? | **YES** — automation or expansion that depends on replay trust |

### 3. NOTION-02 — Schema and view drift guard

| Field | Value |
|---|---|
| Status | PARTIAL |
| Necessity | MUST |
| Urgency | P1 |
| Why now | External Notion property, option, schema, and view changes can block or misroute an otherwise valid operation. |
| Done when | A periodic read-only preflight validates required schema/options/mapping and has a documented FAIL/WARNING response plus a view-drift checklist. |
| Expansion blocked until? | Not for the verified current flow; **YES** for broader Notion-dependent expansion |

### Recently completed

- `DOC-01` — **COMPLETE**: this canonical `ROADMAP_CURRENT.md` establishes the current roadmap authority and removes documentation supersession from the pending P1 list.

## F. NEXT PHASE

| Order | Initiative | Outcome / dependency |
|---:|---|---|
| 1 | `OPS-04` + `OBS-01` | Artifact retention, run index, operating SLOs, and observability. Preserve failed/blocked recovery evidence. |
| 2 | `TEST-01` | Side-effect-classified safe CI. Automate only proven isolated suites first. |
| 3 | `AUTO-03` / `AUTO-01` | Read-only scheduling plus deployment/run evidence. Write stages remain approval-gated. |
| 4 | `BENCH-02` | Define and implement the monthly-contribution SPY benchmark after cash-flow/dividend/fee/fraction policies are approved. |
| 5 | `CFG-01` / `STRAT-04` / `BT-01` | Incremental consistency cleanup only; no broad refactor. |
| 6 | `EXP-01` | Formal account/universe/strategy/risk profiles after the current P1 reliability gaps close. |

## G. LATER / RESEARCH

- `BT-02`: concrete no-lookahead loader, hybrid simulator, rolling walk-forward optimization, and plateau evaluator.
- `FUND-01`: point-in-time fundamental and quality-data collection/filtering.
- `UX-01`: Notion operator view and input UX improvements after drift validation is reproducible.
- `AUTO-02`: approval-based Telegram execution after read-only operations and an approval threat model are accepted.

These are research or later capabilities, not current production requirements. WFO, fundamentals, and approval execution are not COMPLETE.

## H. DEFER / DROP / ARCHIVE

| Item | Current decision |
|---|---|
| CSV-only market database | Historical and superseded by SQLite. |
| n8n-embedded business/trading judgment | DROP / superseded. Python remains the judgment engine. |
| `paper_virtual_fill` as the official operator path | Historical compatibility only. Manual Execution remains the official path. |
| Single hard-coded `paper_test` architecture | Superseded by account-aware path and identity handling. |
| Old v5.x performance-tuning examples | Research history, not active backlog commitments. |
| Live broker integration | DEFER / DROP_CANDIDATE for the current paper objective. Do not reopen without a separately approved safety program. |

## I. Development Sequence

```text
ACCT-01
-> REPLAY-01
-> NOTION-02
-> retention / observability
-> safe CI
-> read-only scheduling / deployment proof
-> monthly-contribution benchmark
-> account / universe / strategy / risk expansion
-> optional WFO / fundamentals research
```

`DOC-01` is complete and is not part of the pending sequence.

## J. Canonical References

Current operating and audit references:

- Operator/runbook: `docs/operations/paper_daily_cycle_commands.md`
- SYSTEM AUDIT summary: `docs_chatGPT_work/codex_results/SYSTEM-AUDIT-20260810/SYSTEM_AUDIT_SUMMARY.md`
- Initiative matrix: `docs_chatGPT_work/codex_results/SYSTEM-AUDIT-20260810/03_initiative_matrix.md`
- Gap priority: `docs_chatGPT_work/codex_results/SYSTEM-AUDIT-20260810/06_gap_priority.md`
- Current system map: `docs_chatGPT_work/codex_results/SYSTEM-AUDIT-20260810/05_current_system_map.md`
- Document/code conflicts: `docs_chatGPT_work/codex_results/SYSTEM-AUDIT-20260810/04_document_code_conflicts.md`

Historical references include System Architecture v5.x, Paper roadmap v1.x, OPER/MFU series, and the `docs_n8n/` roadmap/task series. They are historical/design lineage, not the current roadmap authority.

## K. Maintenance Rules

1. `docs/ROADMAP_CURRENT.md` is the only current roadmap SSOT.
2. A new idea does not enter the official backlog merely because it was proposed.
3. Add or prioritize only initiatives whose development has been approved.
4. Maintain detailed requirements and implementation design in the latest initiative-specific PRD/TRD.
5. Mark implementation complete only after checking code, tests, and relevant operating evidence.
6. Do not create a new roadmap file whenever a small task finishes.
7. Do not use proliferating names such as `ROADMAP_CURRENT_v2.md`, `ROADMAP_FINAL.md`, or `ROADMAP_YYYYMMDD.md` as the normal process.
8. Update this same `ROADMAP_CURRENT.md` when current status or priority changes.
9. On update, change at least `Last Updated`, `Verified HEAD` or the relevant baseline, and the affected initiative status/priority.
10. Preserve earlier states of this document through Git history.
11. Create a dated `SYSTEM-AUDIT-YYYYMMDD/` only for a major phase transition or repository-wide reassessment.
12. Reflect a new SYSTEM AUDIT result back into this same roadmap.
13. Do not rewrite historical roadmaps, PRDs, or TRDs to erase earlier decisions.
14. Keep only a short status for superseded or dropped initiatives here; use source documents and Git history for details.

Document roles:

```text
ROADMAP_CURRENT.md       = current status, scope, and priority
SYSTEM-AUDIT-YYYYMMDD/   = point-in-time repository-wide assessment
initiative PRD/TRD       = detailed requirement and implementation contract
Git history              = prior ROADMAP_CURRENT states
```

# PAPER19-3 Daily Plan Replay Source Alignment and Wrapper Design

## 1. Purpose

PAPER19-3 defines how the PAPER19-2 Daily Plan JSON diff core should connect to the real paper operations loop without mixing pure comparison with plan regeneration.

Goals:

- define where official/committed baseline Daily Plan JSON should come from
- define how regenerated Daily Plan JSON may be produced later
- keep diff comparison and regeneration wrapper responsibilities separate
- preserve read-only/dry-run safety

This is documentation only. No Python code, Daily Plan regeneration, `paper.py plan`, Notion API, or outputs/paper ledger mutation is performed.

## 2. Current PAPER19-2 State

PAPER19-2 completed:

- `core/paper_replay_diff.py`
- `scripts/dev/diff_daily_plan.py`
- `tests/test_paper_replay_diff.py`
- `docs/TRD/mfu_paper19_daily_plan_json_diff_core.md`

Current CLI:

```cmd
python scripts\dev\diff_daily_plan.py --account-id paper_sandbox --date 2026-05-20 --baseline-plan <path> --regenerated-plan <path> --output-dir <path> --json
```

Current behavior:

- compares two existing JSON files
- generates JSON/Markdown diff reports
- uses `symbol + action` as the initial row key
- reports duplicate row key as `DUPLICATE_ROW_KEY`
- records fingerprint differences as cause candidates
- does not regenerate a Daily Plan
- does not call Notion or mutate source-of-truth artifacts

## 3. Baseline Daily Plan Source Alignment

Definition:

```text
baseline_plan = official or committed Daily Plan JSON artifact
```

Current repo state:

- operational Daily Plan artifact is currently Markdown-centered, typically `daily_action_plan_YYYYMMDD.md`
- non-default account roots use `outputs/paper_accounts/{account_id}/daily_action_plan_{YYYYMMDD}.md`
- account-aware replay paths already exist under `outputs/paper_accounts/{account_id}/replay_diff/`
- PAPER19-2 expects JSON, so a formal baseline JSON artifact contract is still needed

Baseline requirements:

- must represent the plan actually accepted or used by the operator
- must not be a temporary preview unless explicitly marked as preview-only
- must include `account_id`, `plan_date`, normalized action rows, metadata, and fingerprints when available
- must be immutable for the purpose of replay diff comparison
- must not be overwritten by regenerated artifacts

Candidate baseline locations:

```text
outputs/paper_accounts/{account_id}/plans/daily_plan_{YYYYMMDD}.json
outputs/paper_accounts/{account_id}/replay_diff/baseline_daily_plan_{YYYYMMDD}.json
```

Recommendation:

- prefer a dedicated official/committed JSON producer in a later MFU
- if derived from Markdown, record `source_markdown_path` and `derivation_method`
- avoid treating ad-hoc converted JSON as official unless the workflow explicitly marks it as such

## 4. Regenerated Daily Plan Source Alignment

Definition:

```text
regenerated_plan = separate JSON artifact generated for the same account/date/config conditions in dry-run replay context
```

PAPER19-3 does not generate it.

Future regenerated artifact requirements:

- must be written under replay-specific paths
- must never overwrite baseline Daily Plan artifacts
- must carry generation metadata and fingerprints
- must not commit execution rows, append review rows, export to Notion, or update local ledgers
- must be safe to delete/recreate as replay output

Candidate regenerated locations:

```text
outputs/paper_accounts/{account_id}/replay_diff/regenerated_daily_plan_{YYYYMMDD}.json
outputs/paper_accounts/{account_id}/replay_diff/runs/{run_id}/regenerated_daily_plan.json
```

Run-scoped paths are preferred once repeated replay runs become common.

## 5. Pure Diff vs Regeneration Wrapper Boundary

Boundary:

```text
diff_daily_plan.py
= pure comparison tool for two existing JSON files

future replay wrapper
= dry-run orchestrator that creates a regenerated JSON artifact and hands both JSON files to the diff core
```

Rules:

- `core.paper_replay_diff` must not import or call Daily Plan generation code
- `scripts/dev/diff_daily_plan.py` must remain a pure file comparison CLI
- regeneration, if added, belongs in a separate wrapper
- wrapper must call the diff core only after regenerated JSON is produced
- wrapper must not include `--confirm-actual`
- wrapper must not call Notion/export/sync
- wrapper must not mutate source-of-truth ledgers

## 6. Proposed Wrapper Flow

Future candidate CLI:

```cmd
python scripts\dev\replay_daily_plan_diff.py --account-id paper_sandbox --date 2026-05-20 --baseline-plan <path> --output-dir <path> --json
```

Proposed flow:

1. Validate `account_id` and date.
2. Resolve or accept explicit baseline Daily Plan JSON path.
3. Confirm baseline is official/committed, not preview-only.
4. Resolve replay output directory under account `replay_diff`.
5. Run a dry-run-only Daily Plan generation path that writes regenerated JSON to replay output.
6. Pass baseline JSON and regenerated JSON to `core.paper_replay_diff`.
7. Write JSON/Markdown diff report.
8. Return summary with `write_executed=false`.

Required wrapper invariants:

- dry-run only by default and by design
- no `--confirm-actual`
- no Notion/export/sync
- no paper execution/review commit
- no overwrite of baseline artifact
- no update to official/current state ledgers

## 7. Output / Handoff Path Policy

PAPER19-2 diff report path remains:

```text
outputs/paper_accounts/{account_id}/replay_diff/paper_daily_plan_diff_{YYYYMMDD}.json
outputs/paper_accounts/{account_id}/replay_diff/paper_daily_plan_diff_{YYYYMMDD}.md
```

Future run-scoped wrapper artifacts:

```text
outputs/paper_accounts/{account_id}/replay_diff/runs/{YYYYMMDD_HHMMSS}/regenerated_daily_plan.json
outputs/paper_accounts/{account_id}/replay_diff/runs/{YYYYMMDD_HHMMSS}/paper_daily_plan_diff.json
outputs/paper_accounts/{account_id}/replay_diff/runs/{YYYYMMDD_HHMMSS}/paper_daily_plan_diff.md
```

Handoff contract:

- wrapper produces regenerated JSON
- wrapper calls diff core
- diff core emits report
- alert system may later consume report status, but should not run replay itself

## 8. Safety Policy

PAPER19 replay alignment keeps source-of-truth safety first:

- no automatic actual export
- no Notion API call
- no Notion write/export/sync
- no `paper.py plan` execution in PAPER19-3
- no source-of-truth ledger mutation
- no execution/review replay
- no overwrite of official/committed baseline artifacts
- no reliance on Notion as source-of-truth

If wrapper generation is implemented later, it must generate replay artifacts only.

## 9. Row Identity / Stable ID Consideration

PAPER19-2 row key:

```text
symbol + action
```

This is a minimal starting point, not a final identity contract.

Policy:

- if the same `symbol + action` appears multiple times, report `DUPLICATE_ROW_KEY`
- do not match rows by list order
- do not silently merge duplicate keys
- do not infer intent from row position

Stable id candidates:

- `plan_item_id`
- row-level `external_key`
- `symbol + action + reason_code`
- deterministic rank emitted by the plan producer
- stable hash of normalized plan row fields

Recommendation:

- future Daily Plan JSON producer should emit a stable `plan_item_id`
- PAPER19-4 should decide whether `symbol + action` is sufficient for real plan artifacts

## 10. Test Strategy

Future wrapper tests should use `tmp_path` and fake generation functions.

Test candidates:

- baseline path missing -> wrapper stops before generation
- baseline marked preview-only -> wrapper stops or returns `NEEDS_REVIEW`
- regenerated artifact is written under replay path
- regenerated artifact does not overwrite baseline
- wrapper passes regenerated JSON to diff core
- JSON/Markdown diff report is generated
- `write_executed=false` remains true
- Notion/API/export/sync is not called
- source-of-truth ledger files are not modified
- duplicate row key remains warning, not auto-matched

## 11. Non-scope

PAPER19-3 does not include:

- Python code implementation
- wrapper CLI implementation
- Daily Plan regeneration execution
- `paper.py plan` execution
- Notion API calls
- Notion write/export/sync
- actual export
- outputs/paper ledger modification
- real Daily Plan artifact modification
- execution/review replay
- schema/view drift
- Telegram/Slack/Email delivery

## 12. PAPER19-4 Recommendation

Recommended PAPER19-4:

```text
Daily Plan Baseline JSON Producer / Export Contract
```

Suggested scope:

- define official/committed baseline JSON schema
- decide whether baseline JSON is produced alongside Markdown plan generation
- add read-only conversion only if Markdown remains the canonical artifact
- include fingerprints and stable row id candidates
- do not implement regeneration wrapper until baseline JSON contract is stable

Alternative PAPER19-4:

```text
Replay Wrapper Dry-run Prototype with Fake Generator
```

This should only proceed if baseline JSON production is already clear enough.

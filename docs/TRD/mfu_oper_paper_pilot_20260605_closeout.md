# MFU OPER Closeout: paper_pilot_202606 / 2026-06-05

## 1. Purpose

This document closes out the `paper_pilot_202606` operating pilot for `2026-06-05` and summarizes the OPER1 through OPER5 account-aware fixes proven during the pilot.

이번 MFU-OPER-CLOSEOUT은 paper_pilot_202606 운영 파일럿 및 OPER1~OPER5 결과를 문서화하는 작업이며, 코드 수정, DB write, paper 원장 수정, Notion write/export/sync, Manual Execution commit, Manual Review append, broker/API 연동은 포함하지 않는다.

## 2. Scope / Non-scope

Scope:

- Document the completed `paper_pilot_202606 / 2026-06-05` operating loop.
- Record OPER1 through OPER5 problems, fixes, commits, and verification outcomes.
- Record remaining risks and recommended next work.

Non-scope:

- Code changes.
- DB writes or DB schema changes.
- Paper execution ledger or manual review log modification.
- Notion write/export/sync.
- Manual Execution commit.
- Manual Review append.
- Broker/API integration.

## 3. Pilot account and date

| Field | Value |
| --- | --- |
| Account ID | `paper_pilot_202606` |
| Pilot date | `2026-06-05` |
| Initial cash | `100000.00` USD |
| Initial positions | none |
| Initial execution log | empty |
| Final positions | `MAA|SW` |
| Final cash | `80160.55` |

## 4. Final status

Read-only status verification after OPER5:

| Field | Value |
| --- | --- |
| `workflow_status` | `REVIEW_DONE` |
| `review_progress_status` | `DONE` |
| `review_completion_ratio` | `1.0` |
| `manual_review_log_row_count` | `8` |
| `review_answered_row_count` | `8` |
| `review_pending_row_count` | `0` |
| `review_done_row_count` | `8` |
| `next_recommended_command` | `no immediate action` |

## 5. End-to-end operating flow

1. Created `paper_pilot_202606`.
2. Generated account-aware Daily Plan.
3. Exported Daily Plan to Notion.
4. Entered 2 Manual Executions in Notion.
5. Ran Manual Execution preview.
6. Committed Manual Executions.
7. Synced Manual Execution status to Notion.
8. Ran `paper.py review`.
9. Exported Manual Review Template to Notion Manual Reviews.
10. Answered 8 Manual Review rows.
11. Ran Manual Review preview.
12. Appended Manual Reviews.
13. Synced Manual Review status to Notion.
14. Verified `paper.py status` as `REVIEW_DONE`.

## 6. Trading result summary

| Trade | Quantity | Price | Cash impact |
| --- | ---: | ---: | ---: |
| `BUY MAA` | 73 | `135.37` | `-9882.01` |
| `BUY SW` | 232 | `42.92` | `-9957.44` |

Summary:

- `initial_cash = 100000.00`
- `cash_impact = -19839.45`
- `ending_cash = 80160.55`
- `positions = MAA|SW`

## 7. OPER1 summary

OPER1: Account-aware Daily Plan state loading.

Problem:

- `paper.py plan --account-id paper_pilot_202606` wrote output under the account root but loaded input state from default `outputs/paper_test`.
- This mixed default holdings such as `AAPL`, `BRK-B`, `F`, and `GEN` into the new pilot account plan.

Fix:

- Non-default Daily Plan state loading now uses account-specific execution log, current state, and snapshots.
- Plans before account inception date are blocked instead of falling back to default state.
- Status recommendation commands include `--account-id` for non-default accounts.

Commit:

- `6e46b8c03b7e884a17bbaff42ba43356b200f2ba`

## 8. OPER2 summary

OPER2: Account-aware Daily Plan Notion export.

Problem:

- Daily Plan Notion export showed `account_id=paper_pilot_202606` but selected source artifacts from default `outputs/paper_test` for `2026-05-20`.

Fix:

- `--daily-plan --account-id <non-default>` selects artifacts under the account-specific root.
- `--date YYYY-MM-DD` is supported for Daily Plan export.
- Non-default exports do not fall back to `outputs/paper_test`.

Commit:

- `b982a25c5e27bca6152e62d8ef0f731802992d43`

## 9. OPER3 summary

OPER3: Account-aware Manual Execution preview.

Problem:

- Manual Execution preview queried Notion rows for `paper_pilot_202606`, but cash, holdings, duplicate trade IDs, and report output path still used default `outputs/paper_test`.

Fix:

- Preview state now uses account-specific cash, holdings, and execution log.
- Duplicate trade ID checks are scoped to the account-specific execution log.
- Preview JSON/MD reports are written under the account-specific reports directory.

Confirmed result:

- `projected_cash_start = 100000.0`
- `projected_cash_end = 80160.55`
- `json_path = outputs\paper_accounts\paper_pilot_202606\reports\manual_execution_import_preview_20260605.json`

Commit:

- `50805fdfb7062118fc3ab88032620e52568d1c08`

## 10. OPER4 summary

OPER4: Account-aware Manual Review Template Notion export.

Problem:

- `paper.py review` generated local review template CSV/MD, but there was no account-aware export path to create Manual Reviews DB rows automatically.
- The operator had to manually copy 8 review questions into Notion.

Fix:

- Added `--manual-review-template`.
- Local template CSV is exported to Notion Manual Reviews as 1 question = 1 row.
- External Key format: `manual_review:{account_id}:{review_date}:{symbol}:{question_id}`.
- Initial Notion state uses `Review Status=pending` and `Import Status=DRAFT`.
- The operator changes rows to `READY` after answering.

Commit:

- `be3f4ea77c39678a18ed650c80f04b259df7e9e7`

## 11. OPER5 summary

OPER5: Review progress status from Manual Review Log.

Problem:

- Manual Review append and status sync succeeded, but `paper.py status` still returned `REVIEW_PARTIAL`.
- The status calculation counted answered rows from `paper_manual_review_log_template.csv`, which remains pending/blank after append.

Fix:

- Template rows define the total question set.
- `paper_manual_review_log.csv` defines completed answers.
- Progress is calculated by matching `review_date + SYMBOL + question_id`.
- Duplicate log keys count once.

Confirmed result:

- `workflow_status = REVIEW_DONE`
- `manual_review_log_row_count = 8`
- `review_answered_row_count = 8`
- `review_pending_row_count = 0`
- `review_completion_ratio = 1.0`
- `next_recommended_command = no immediate action`

Commit:

- `1718466bec8a6d54a2ffb672d87d848264136a53`

## 12. Account-aware issues found and fixed

The pilot found repeated account-aware routing gaps:

- Daily Plan input state loaded default state while writing account-specific output.
- Daily Plan Notion export selected default artifacts for a non-default account.
- Manual Execution preview used default cash/holdings/report paths.
- Manual Review Template lacked account-aware Notion export.
- Review status progress used template rows rather than appended account-specific review log rows.

The common pattern was that `account_id` often reached presentation or output fields before it reached source artifact selection and validation paths.

## 13. Current confirmed working flow

The following flow is confirmed for `paper_pilot_202606 / 2026-06-05`:

1. Account-specific Daily Plan generation.
2. Account-specific Daily Plan Notion export.
3. Account-specific Manual Execution preview.
4. Manual Execution commit and Notion status sync.
5. Account-specific local review template generation.
6. Account-specific Manual Review Template Notion export.
7. Manual Review preview.
8. Manual Review append and Notion status sync.
9. Final status detection as `REVIEW_DONE`.

## 14. Remaining risks / limitations

1. Daily Ops Status actual export is still restricted to `paper_sandbox`; `paper_pilot_202606` actual export is blocked by guard.
2. Manual Review questions are too numerous and broad. Current per-symbol 4-question generation can make the Manual Reviews DB heavy in long-running operations.
3. Account-aware gaps were found across several CLIs, so remaining export/report/replay/alert layers need an account-aware audit.
4. Full `pytest tests -q` may still fail because of existing `conftest` import issues unrelated to this pilot.
5. `outputs/paper_accounts/*` generated artifacts are not Git stage targets.

## 15. Recommended next work

1. Daily Ops Status actual export guard expansion.
   - Safely allow actual export for pilot accounts such as `paper_pilot_202606`.
   - Confirm duplicate audit, expected page handling, and explicit confirm guard.

2. Manual Review question and trigger policy improvement.
   - Do not generate every symbol times 4 questions by default.
   - Generate about 1 question per newly entered symbol.
   - Generate detailed questions only for loss, warning, execution drift, or rule violation cases.
   - Add a daily maximum question count.

3. Account-aware vertical slice audit.
   - Check weekly, benchmark, account snapshot, daily review summary, alert, replay, and daily ops status paths.

4. Daily Ops Orchestrator read-only status aggregator.
   - Detect current stage.
   - Recommend the next command.
   - Display blocking/warning status.
   - Do not automatically run source-of-truth writes or Notion actual writes.

## 16. Generated artifacts and Git policy

Generated artifacts under `outputs/paper_accounts/*`, `outputs/paper_test/*`, and `outputs/front_test/*` are not commit targets.

For this closeout, only this document should be staged:

```cmd
git add docs\TRD\mfu_oper_paper_pilot_20260605_closeout.md
```

Do not use:

```cmd
git add .
git add -A
```

## 17. Verification commands

Read-only commands used or recommended for this closeout:

```cmd
python scripts\paper.py status --account-id paper_pilot_202606 --date 2026-06-05 --json
git log --oneline -n 20
git diff -- docs/TRD/mfu_oper_paper_pilot_20260605_closeout.md
git diff --check
git status --short
```

Observed status command result:

- `workflow_status = REVIEW_DONE`
- `review_progress_status = DONE`
- `review_completion_ratio = 1.0`
- `next_recommended_command = no immediate action`

## 18. Closeout conclusion

The `paper_pilot_202606 / 2026-06-05` pilot completed the full paper operations loop from account creation through Daily Plan, Notion export, Manual Execution, review generation, Manual Review export, review append, status sync, and final local status confirmation.

The pilot proved that the account-aware fixes from OPER1 through OPER5 are necessary for safe non-default paper account operation. The current confirmed closeout state is `REVIEW_DONE`, with 8 of 8 review rows completed and no immediate local action remaining.

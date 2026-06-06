# MFU-OPER6~8 Closeout

## 1. Executive Summary

이번 MFU-OPER6-8 Closeout은 OPER6~8 계열 작업의 완료 범위, 현재 운영 루프 상태, 남은 한계, OPER9 인수인계 내용을 문서화하는 작업이며, 코드 변경, DB schema 변경, paper 원장 변경, Notion actual write/export/sync, Manual Execution commit, Manual Review append, broker/API 연동은 포함하지 않는다.

OPER6~8은 paper daily ops 루프를 data_date/trade_date 분리 모델로 전환하고, Daily Plan -> Manual Executions -> Commit -> Review -> Manual Review -> Status 흐름을 paper_pilot_202606 계좌 기준으로 끝까지 검증한 작업이다.

이 closeout은 OPER6~8에서 완료된 날짜 정합성, account-aware 운영 artifact 선택, Manual Execution DRAFT row 생성, Manual Review 날짜/질문/검증 개선을 하나의 운영 인수인계 문서로 정리한다.

## 2. Date Model

OPER6 이후 공식 paper daily ops 날짜 모델은 아래와 같다.

| Field | Meaning |
| --- | --- |
| data_date | 신호 계산에 사용한 마지막 완료 미국장 날짜 |
| trade_date | 실제 paper 매매/원장/리뷰 기준일 |
| plan_date | trade_date |
| execution_date | trade_date |
| snapshot_date | trade_date |
| review_date | trade_date |

Example:

```text
data_date = 2026-06-05
trade_date = 2026-06-08
```

Interpretation:

```text
2026-06-05까지의 완료된 미국장 데이터로
2026-06-08에 실행/기록할 paper operation을 준비한다.
```

## 3. OPER6 Summary

### OPER6-1: Market Date Semantics Audit and KST Operating Window

Commit:

```text
cf07fa324e20cb499e5d3892ff0b9b41009fb399
```

Scope:

- Audited how `--date` was used across Daily Plan, Manual Execution, Manual Review, snapshot, Notion external keys, and status.
- Defined the need to separate `data_date` and `trade_date`.
- Documented KST operating windows, including the recommended KST 18:00~22:00 core window.
- Clarified that the 2026-06-05 pilot verified account-aware operations but should not be interpreted as a fully market-date-correct official trading day.

### OPER6-2: Explicit data_date / trade_date Daily Plan

Commit:

```text
933dc02f32da2f1333fe7bcb7071897b94767700
```

Scope:

- Added explicit Daily Plan mode:

```cmd
python scripts\paper.py plan --data-date <DATA_DATE> --trade-date <TRADE_DATE> --account-id <ACCOUNT_ID>
```

- Uses `data_date` for signal/market/screening calculations.
- Uses `trade_date` for artifact filename, `plan_date`, sidecar date, and operational records.
- Adds top-level Daily Plan sidecar fields:

```json
{
  "data_date": "2026-06-05",
  "trade_date": "2026-06-08",
  "plan_date": "2026-06-08"
}
```

- Added guards for invalid explicit date combinations such as missing paired dates, `trade_date <= data_date`, weekend trade dates, and non-default account inception date violations.
- Legacy `--date` mode remains available for backward compatibility, but explicit mode is the recommended official EOD operation mode.

### OPER6-2A: Universe Freshness Quarterly As-of Alignment

Commit:

```text
035199ecc763f9d1c47d6f63eab56fa1829a09f1
```

Scope:

- Aligned `paper.py data-freshness` `universe_snapshot` checks with Daily Plan's quarterly/as-of universe loading policy.
- Same-quarter as-of universe snapshots no longer create unnecessary warnings.
- Prior-quarter fallback or missing/unreadable snapshots still produce warnings.
- This removed an unnecessary blocker for explicit plan generation when Daily Plan could validly use a same-quarter universe snapshot.

## 4. OPER7 Summary

### OPER7: Daily Plan -> Manual Execution DRAFT Row Export

Commit:

```text
253b4cccf4be3c0aa424c6fc84eef77a1cdc9b21
```

Scope:

- Added Manual Execution Template export from Daily Plan JSON sidecar.
- Creates or updates Notion Manual Executions DRAFT rows from confirmed Daily Plan `items`.
- This is not automatic execution. It is a Manual Execution input draft generator.

Core policies:

- Account ID is not hardcoded.
- Daily Plan JSON `account_id` is the source of truth.
- CLI `--account-id` is used for file discovery and validation only.
- CLI account mismatch with JSON account_id fails.
- `Actual Price` is left blank.
- `plan_price` is written to `Note`, not treated as actual execution price.
- `Status = DRAFT`.
- `Import Status = DRAFT`.
- User must enter Actual Price and change Status to READY before import preview can include the row.
- External Key based upsert prevents duplicate rows.

Command shape:

```cmd
python scripts\export_paper_to_notion.py --manual-execution-template --account-id <ACCOUNT_ID> --date <TRADE_DATE> --dry-run --json
python scripts\export_paper_to_notion.py --manual-execution-template --account-id <ACCOUNT_ID> --date <TRADE_DATE> --confirm-actual --json
```

## 5. OPER8 Summary

### OPER8A: Review Date / Trade Date Awareness

Commit:

```text
c401c45dee47b0713fcfd6c62562e93c89a3d9d4
```

Scope:

- Added explicit date support for `paper.py review`.
- Aligned `review_date` with `trade_date`.
- Reduced stale review/template/log misclassification risk in `paper.py status`.
- Ensured `manual-review-template` export can find rows for the target trade date.

Command shape:

```cmd
python scripts\paper.py review --account-id <ACCOUNT_ID> --date <TRADE_DATE>
```

### OPER8B: Manual Review Question Simplification

Commit:

```text
a0ebc2e582888e5428a8000fc6fc644da5d77cc1
```

Scope:

- Reduced Manual Review template question count from 38 to 12 for the 2026-06-08 loop.
- Changed the default policy to one execution review question per symbol plus three account-level questions.
- Kept `review_date = trade_date`.
- Preserved account-specific reviews directory routing.
- Did not execute Notion actual export or Manual Review append as part of the implementation task.

Question policy:

- Symbol-level: `execution_review_1`
- Account-level: `account_review_1`, `account_review_2`, `account_review_3`

### OPER8C-1: Reviewer Note Optional and Review Tag Mapping

Commit:

```text
b947ae844b89205da62e143e586bfa8f23041682
```

Scope:

- Removed generic `missing_reviewer_note` WARNING from Manual Review preview.
- Kept warnings for rows that need context:
  - `review_status = deferred` and both reviewer_note/review_tag are blank.
  - `follow_up_needed = true` and both reviewer_note/review_tag are blank.
- Added default Review Tag mapping using the existing allowed tag list:
  - `execution_review_1` -> `execution_quality`
  - `account_review_1` -> `position_sizing`
  - `account_review_2` -> `execution_quality`
  - `account_review_3` -> `risk_management`
- Did not add new Review Tag values.
- Did not change question IDs.

Verified 2026-06-08 Manual Review preview:

```text
candidate_count = 12
pass_count = 12
warning_count = 0
fail_count = 0
append_allowed = true
```

## 6. 2026-06-08 paper_pilot_202606 Operating Loop Result

Account:

```text
account_id = paper_pilot_202606
data_date = 2026-06-05
trade_date = 2026-06-08
```

Completed checkpoints:

- Daily Plan generated with `data_date=2026-06-05`, `trade_date=2026-06-08`.
- Daily Plan Notion export completed.
- Manual Execution Template export completed.
- Manual Execution commit completed.
- Manual Execution status sync completed.
- `paper.py review --account-id paper_pilot_202606 --date 2026-06-08` completed.
- Manual Review Template export completed.
- Manual Review preview PASS.
- Manual Review append completed.
- Manual Review status sync completed.
- `paper.py status` final REVIEW_DONE confirmed.

This closeout did not re-run commit, append, or sync. The operating loop result is documented from prior completed reports/status and user-provided operational context.

## 7. Current Official Operating Command Flow

Until OPER9, the official flow remains manual and command-driven.

```cmd
python scripts\paper.py data-freshness --date <DATA_DATE>
python scripts\paper.py plan --data-date <DATA_DATE> --trade-date <TRADE_DATE> --account-id <ACCOUNT_ID>
python scripts\export_paper_to_notion.py --daily-plan --account-id <ACCOUNT_ID> --date <TRADE_DATE> --confirm-actual --json
python scripts\export_paper_to_notion.py --manual-execution-template --account-id <ACCOUNT_ID> --date <TRADE_DATE> --confirm-actual --json
python scripts\import_notion_executions.py --date <TRADE_DATE> --account-id <ACCOUNT_ID> --preview --json
python scripts\import_notion_executions.py --date <TRADE_DATE> --account-id <ACCOUNT_ID> --commit --preview-json "<preview_json>" --json
python scripts\sync_notion_execution_status.py --date <TRADE_DATE> --account-id <ACCOUNT_ID> --commit-report "<commit_json>" --json
python scripts\paper.py review --account-id <ACCOUNT_ID> --date <TRADE_DATE>
python scripts\export_paper_to_notion.py --manual-review-template --account-id <ACCOUNT_ID> --date <TRADE_DATE> --confirm-actual --json
python scripts\import_notion_reviews.py --date <TRADE_DATE> --account-id <ACCOUNT_ID> --preview --json
python scripts\import_notion_reviews.py --date <TRADE_DATE> --account-id <ACCOUNT_ID> --commit --preview-json "<preview_json>" --json
python scripts\sync_notion_review_status.py --date <TRADE_DATE> --account-id <ACCOUNT_ID> --commit-report "<commit_json>" --json
python scripts\paper.py status --account-id <ACCOUNT_ID> --date <TRADE_DATE> --json
```

Important operating rule:

- Actual Notion writes require explicit `--confirm-actual`.
- Manual Execution commit and Manual Review append require preview report review.
- The operator must avoid staging generated outputs.

## 8. Known Risks and Remaining Limitations

- 명령어가 너무 많아 운영자가 순서를 실수하기 쉽다.
- `data_date`/`trade_date` 계산이 아직 완전 자동화되지 않았다.
- US market calendar, 휴장일, KST 운영 창 자동 resolver는 추가 보강 필요.
- Daily Ops Status actual export는 `paper_pilot_202606`에 아직 완전히 열려 있지 않을 수 있다.
- BUY/HOLD/SELL 상태별 Manual Review 질문 분리는 아직 미구현.
- 조건부 질문 `PRICE_GAP`, partial fill, validation issue 등은 아직 후속 작업이다.
- Notion UI view가 아직 입력 친화적으로 완전히 정리되지 않았다.
- 전체 `pytest tests -q`에는 기존 collection/test debt가 남아 있을 수 있다.
- The flow is still human-driven and lacks a single stage-level status/checklist runner.

## 9. OPER9 Handoff

Recommended next work:

```text
MFU-OPER9 Daily Ops Orchestrator MVP
```

OPER9 goal:

```text
여러 명령어로 분산된 daily ops loop를 하나의 orchestrator preview/status runner로 묶는다.
처음부터 actual write/commit을 자동화하지 않는다.
단계별 상태 확인, 다음 추천 명령, 필요한 파일 경로, date/account guard를 제공한다.
```

OPER9 should handle first:

- `account_id`
- `data_date`
- `trade_date`
- Stage status lookup
- Required artifact existence checks
- Preview/commit/sync path recommendation
- Duplicate execution prevention
- `paper_test` fallback prevention
- `outputs/*` artifact stage prohibition reminders
- Blocking/warning/pass display per stage

Suggested OPER9 stance:

- Read-only status aggregator first.
- Next action recommender second.
- No automatic actual Notion write.
- No automatic Manual Execution commit.
- No automatic Manual Review append.
- No broker/API integration.

## 10. Verification

Closeout document verification commands:

```cmd
git log --oneline --decorate --all -n 80
git rev-parse cf07fa3 933dc02 035199e 253b4cc c401c45 a0ebc2e b947ae8
type docs\TRD\mfu_oper6_8_closeout.md
git diff --check
git status --short
```

No code, DB, paper ledger, Notion actual write/export/sync, Manual Execution commit, Manual Review append, or broker/API operation is part of this closeout.

## 11. Closeout Conclusion

OPER6~8 moved the paper operations loop from a single ambiguous `--date` model toward an explicit EOD operating model based on `data_date` and `trade_date`. The 2026-06-08 `paper_pilot_202606` loop demonstrated that Daily Plan generation, Notion export, Manual Execution draft creation, execution commit, review generation, Manual Review import, and final status can close as REVIEW_DONE.

The remaining operational risk is not the lack of individual commands, but the number of commands and checks an operator must remember. OPER9 should convert this into a read-only orchestrator that shows stage state, blockers, next command candidates, and source artifact paths without automating writes or commits.

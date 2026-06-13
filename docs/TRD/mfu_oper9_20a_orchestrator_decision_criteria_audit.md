# MFU-OPER9-20A Orchestrator Decision Criteria Audit

## 1. Summary

이 문서는 현재 코드 기준으로 Paper Daily Ops Orchestrator가 각 stage를 `DONE`, `READY`, `BLOCKED`, `WARNING`, `UNKNOWN`, `SKIPPED` 계열로 판정하는 기준을 감사한 결과다. 이번 작업은 코드 수정이 아니라 판정 기준 인벤토리다.

주요 발견 사항은 다음과 같다.

- 전체 stage 순서는 `core/paper_daily_ops_orchestrator.py`의 `STAGE_NAMES`와 `build_daily_ops_status()`에 고정되어 있다.
- Local artifact 판정 후 Notion live read 결과가 attach되고, `core/paper_daily_ops_reconciliation.py`가 stage status와 `next_command`를 다시 조정한다.
- `operator_summary.current_step`은 terminal, reconciliation conflict, `next_command`, manual input wait, `BLOCKED/WARNING/READY/UNKNOWN` 순서로 선택된다.
- 2026-06-15 사례에서 `daily_action_plan_20260615.json`에는 `items[]` 9개가 있고 `action=BUY/SELL`, `quantity>0` 구조지만, Orchestrator candidate count 함수는 `action=EXECUTE`, `status=PENDING`, `side=BUY/SELL`만 실행 후보로 센다.
- 따라서 실제 BUY/SELL 9개, Notion Manual Execution row 9개, execution commit 9개가 있었는데도 Orchestrator는 `no_execution_candidates=true`로 Manual Execution 구간을 no-op 처리했다.

## 2. Audit Scope

조사한 주요 파일:

| 영역 | 파일 |
| --- | --- |
| Orchestrator core | `core/paper_daily_ops_orchestrator.py` |
| Reconciliation | `core/paper_daily_ops_reconciliation.py` |
| Operator summary | `core/paper_daily_ops_operator_summary.py` |
| Notion live read | `core/paper_daily_ops_notion_status.py` |
| Local status | `core/paper_status.py` |
| Notion evidence | `core/paper_daily_ops_evidence.py` |
| Notion export/import | `scripts/export_paper_to_notion.py`, `scripts/import_notion_executions.py`, `scripts/import_notion_reviews.py`, `scripts/sync_notion_execution_status.py`, `scripts/sync_notion_review_status.py`, `core/notion_exporters.py`, `core/notion_manual_execution_importer.py`, `core/notion_manual_review_importer.py` |
| EOD | `scripts/run_paper_eod_update.py` |
| Tests | `tests/test_paper_daily_ops_orchestrator.py`, `tests/test_paper_daily_ops_orchestrator_guard.py`, `tests/test_paper_cli.py`, `tests/test_paper_cli_account_scope.py`, `tests/test_paper_status.py` |
| Docs | `docs/TRD/mfu_oper9_*.md`, `docs/operations/paper_daily_ops.md`, `docs/operations/paper_daily_cycle_commands.md` |

실행한 명령은 read-only 조회, `git grep`, CLI status 조회, JSON 파일 읽기뿐이다. Notion write, import commit, sync, EOD commit, broker/API/order, ledger/DB mutation 명령은 실행하지 않았다.

## 3. Stage Decision Matrix

| stage_name | 목적 | Local evidence 기준 | Notion live read 기준 | DONE 조건 | READY 조건 | BLOCKED/WARNING/UNKNOWN 조건 | next_command | command_type / approval | 관련 코드 | 관련 테스트 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `DATA_FRESHNESS` | `data_date` market data freshness 확인 | 자동 실행하지 않음 | 없음 | 직접 DONE 판정 없음 | global blocker가 없으면 `READY` | account/date blocker가 있으면 `BLOCKED` | `python scripts\paper.py data-freshness --date <DATA_DATE>` | `READ_ONLY`, 승인 불필요 | `core/paper_daily_ops_orchestrator.py:361` | `tests/test_paper_daily_ops_orchestrator.py:355` |
| `DAILY_PLAN` | local Daily Plan 생성 여부 확인 | `daily_action_plan_YYYYMMDD.md`, `.json`, `config_snapshots/paper_config_snapshot_YYYYMMDD.json` | 없음 | 세 파일 존재, JSON parse 가능, account/data/trade date match | artifact 미존재 | legacy fallback mismatch, JSON date/account mismatch는 `BLOCKED`; parse 실패는 `UNKNOWN` | `python scripts\paper.py plan --data-date ... --trade-date ... --account-id ...` | `UNKNOWN`, 수동 검토 필요 | `core/paper_daily_ops_orchestrator.py:372` | `tests/test_paper_daily_ops_orchestrator.py:708`, `:719` |
| `DAILY_PLAN_NOTION_EXPORT` | Daily Plan Notion export 확인 | `reports/daily_plan_notion_export_YYYYMMDD.json` evidence | Daily Plans DB external key / account / plan date / sync status | local evidence PASS 또는 local plan + Notion row | local plan only | Notion without local plan은 `WARNING`; no local plan은 `BLOCKED`; evidence missing은 `UNKNOWN` | `python scripts\export_paper_to_notion.py --daily-plan ... --confirm-actual --json` | `NOTION_WRITE`, 승인 필요 | `core/paper_daily_ops_orchestrator.py:406`, `core/paper_daily_ops_reconciliation.py:107` | `tests/test_paper_daily_ops_orchestrator.py:614`, `:1129`, `:1149` |
| `MANUAL_EXECUTION_TEMPLATE` | Manual Execution Notion row export 확인 | `reports/manual_execution_template_export_YYYYMMDD.json`; Daily Plan candidate count | Manual Executions DB account/date rows, `Status`, `Import Status` | evidence PASS, Notion row present, 또는 no candidates guard | local plan exists but no evidence/row | no local plan `BLOCKED`; Notion without local plan `WARNING`; evidence missing `UNKNOWN` | `python scripts\export_paper_to_notion.py --manual-execution-template ... --confirm-actual --json` | `NOTION_WRITE`, 승인 필요 | `core/paper_daily_ops_orchestrator.py:433`, `core/paper_daily_ops_reconciliation.py:125` | `tests/test_paper_daily_ops_orchestrator.py:733`, `tests/test_paper_daily_ops_orchestrator_guard.py:335` |
| `MANUAL_EXECUTION_PREVIEW` | Notion Manual Execution preview 확인 | `manual_execution_import_preview_YYYYMMDD.json` | READY rows, Actual Price missing count | valid local preview, 또는 no candidates guard | READY rows exist and local preview missing | local preview with no READY rows can be `WARNING`; missing/no READY can be `UNKNOWN`; stale/mismatch preview `BLOCKED` | `python scripts\import_notion_executions.py --date ... --account-id ... --preview --json` | `READ_ONLY`, 승인 불필요 | `core/paper_daily_ops_orchestrator.py:486`, `core/paper_daily_ops_reconciliation.py:145` | `tests/test_paper_daily_ops_orchestrator.py:638`, `:782`, `:814`, `:1168` |
| `MANUAL_EXECUTION_COMMIT` | Manual Execution local commit 확인 | `manual_execution_import_commit_YYYYMMDD.json`; ledger/snapshot evidence | COMMITTED/SYNCED/IMPORTED rows | commit report exists, 또는 no candidates guard | preview DONE/WARNING and commit missing | ledger/snapshot without report `WARNING`; Notion committed without local report `BLOCKED`; preview missing `BLOCKED` | `python scripts\import_notion_executions.py --commit --preview-json ... --json` | `LEDGER_WRITE`, 승인 필요 | `core/paper_daily_ops_orchestrator.py:509`, `core/paper_daily_ops_reconciliation.py:184` | `tests/test_paper_daily_ops_orchestrator.py:750`, `:1198`, `:1418` |
| `MANUAL_EXECUTION_STATUS_SYNC` | Execution Notion status sync 확인 | `reports/manual_execution_status_sync_YYYYMMDD.json`; commit report | Import Status / Status all synced | evidence PASS, Notion rows all COMMITTED/SYNCED/IMPORTED, 또는 no candidates guard | commit report exists and sync missing | commit report missing `BLOCKED`; partial/unsynced Notion may be `READY` or `WARNING` depending workflow | `python scripts\sync_notion_execution_status.py --commit-report ... --json` | `NOTION_WRITE`, 승인 필요 | `core/paper_daily_ops_orchestrator.py:560`, `core/paper_daily_ops_reconciliation.py:205` | `tests/test_paper_daily_ops_orchestrator.py:1069`, `:1099` |
| `DAILY_REVIEW` | daily review/review template 생성 확인 | fixed filenames: `reports/paper_daily_review_summary.md`, `reports/paper_performance_summary.md`, `reviews/paper_manual_review_log_template.csv`, `reviews/paper_manual_review_log_validation_report.md` | 없음 | required files exist, template `review_date==trade_date`, validation PASS, summary date current or no-action allowance | required missing or stale fixed artifacts | template date mismatch and validation fail are blockers; no-action day summary snapshot mismatch is warning; normal day summary mismatch blocks | `python scripts\paper.py review --account-id ... --date ...` | `UNKNOWN`, 수동 검토 필요 | `core/paper_daily_ops_orchestrator.py:606` | `tests/test_paper_daily_ops_orchestrator_guard.py:151`, `:245`, `:275`, `:294`, `:314` |
| `MANUAL_REVIEW_TEMPLATE` | Manual Review Notion row export 확인 | `reviews/paper_manual_review_log_template.csv`; `reports/manual_review_template_export_YYYYMMDD.json` | Manual Reviews DB account/date rows, Review Status, Import Status | evidence PASS or Notion rows present | current review template exists but Notion export missing | template missing/date mismatch `BLOCKED`; evidence missing `UNKNOWN` | `python scripts\export_paper_to_notion.py --manual-review-template ... --confirm-actual --json` | `NOTION_WRITE`, 승인 필요 | `core/paper_daily_ops_orchestrator.py:679`, `core/paper_daily_ops_reconciliation.py:232` | `tests/test_paper_daily_ops_orchestrator.py:853`, `:1218` |
| `MANUAL_REVIEW_PREVIEW` | Notion Manual Review preview 확인 | `manual_review_import_preview_YYYYMMDD.json` | READY/REVIEWED/ANSWERED rows | valid local preview | Notion ready/reviewed rows and local preview missing | local preview with no ready rows can be `WARNING`; no rows `UNKNOWN`; mismatch preview `BLOCKED` | `python scripts\import_notion_reviews.py --preview --json` | `READ_ONLY`, 승인 불필요 | `core/paper_daily_ops_orchestrator.py:727`, `core/paper_daily_ops_reconciliation.py:242` | `tests/test_paper_daily_ops_orchestrator.py:914`, `:957`, `:1240` |
| `MANUAL_REVIEW_APPEND` | Manual Review local append 확인 | `manual_review_import_commit_YYYYMMDD.json`; `reviews/paper_manual_review_log.csv` rows | committed/synced Notion rows | commit report exists | preview DONE/WARNING and commit missing | review log rows without report `WARNING`; Notion committed without local report `BLOCKED`; preview missing `BLOCKED` | `python scripts\import_notion_reviews.py --commit --preview-json ... --json` | `LEDGER_WRITE`, 승인 필요 | `core/paper_daily_ops_orchestrator.py:751`, `core/paper_daily_ops_reconciliation.py:260` | `tests/test_paper_daily_ops_orchestrator.py:872`, `:983`, `:1432` |
| `MANUAL_REVIEW_STATUS_SYNC` | Review Notion status sync 확인 | `reports/manual_review_status_sync_YYYYMMDD.json`; review commit report | Import Status / Review Status all synced | evidence PASS or Notion rows all COMMITTED/SYNCED/IMPORTED | commit report exists and sync missing | commit report missing `BLOCKED`; `REVIEW_DONE` but unsynced is `READY` by OPER9-15 | `python scripts\sync_notion_review_status.py --commit-report ... --json` | `NOTION_WRITE`, 승인 필요 | `core/paper_daily_ops_orchestrator.py:782`, `core/paper_daily_ops_reconciliation.py:279` | `tests/test_paper_daily_ops_orchestrator.py:1262`, `:1294`, `:1327` |
| `FINAL_STATUS` | 최종 paper status 확인 | `paper.py status` workflow status | Notion unsynced 여부 reconciliation | `workflow_status=REVIEW_DONE` and no required sync | 직접 READY 없음 | non-REVIEW_DONE is `WARNING` with status command; unknown is `UNKNOWN`; review done but unsynced Notion can be `WARNING` | `python scripts\paper.py status --account-id ... --date ... --json` | `READ_ONLY`, 승인 불필요 | `core/paper_daily_ops_orchestrator.py:811`, `core/paper_daily_ops_reconciliation.py:294` | `tests/test_paper_daily_ops_orchestrator.py:1004`, `:1027`, `:1327` |

## 4. Evidence Matrix

| Evidence / artifact | 파일명 날짜 | 내부 날짜 검증 | fixed filename stale 위험 | 적용 stage | 비고 |
| --- | --- | --- | --- | --- | --- |
| Daily Plan markdown | `daily_action_plan_YYYYMMDD.md` | 파일명 date | 낮음 | `DAILY_PLAN` | account root 기준 |
| Daily Plan JSON | `daily_action_plan_YYYYMMDD.json` | `account_id`, `data_date`, `trade_date`/`plan_date` | 낮음 | `DAILY_PLAN`, execution candidate count | candidate count의 schema mismatch 확인됨 |
| Config snapshot | `config_snapshots/paper_config_snapshot_YYYYMMDD.json` | 파일 존재 위주 | 낮음 | `DAILY_PLAN` | required artifact |
| Daily Plan Notion evidence | `reports/daily_plan_notion_export_YYYYMMDD.json` | schema, evidence_type, account, trade_date, data_date, target_system, status | 낮음 | `DAILY_PLAN_NOTION_EXPORT` | `core/paper_daily_ops_evidence.py` |
| Manual Execution template evidence | `reports/manual_execution_template_export_YYYYMMDD.json` | 동일 | 낮음 | `MANUAL_EXECUTION_TEMPLATE` | `candidate_count=0`이면 no candidates skip 가능 |
| Execution preview | `manual_execution_import_preview_YYYYMMDD.json` | preview payload date/account validate | 낮음 | `MANUAL_EXECUTION_PREVIEW`, `MANUAL_EXECUTION_COMMIT` | `commit_allowed=true_with_warnings`이면 WARNING |
| Execution commit report | `manual_execution_import_commit_YYYYMMDD.json` | 존재 위주 | 낮음 | `MANUAL_EXECUTION_COMMIT`, `MANUAL_EXECUTION_STATUS_SYNC` | source-of-truth commit evidence |
| Execution status sync evidence | `reports/manual_execution_status_sync_YYYYMMDD.json` | Notion evidence schema/date/account | 낮음 | `MANUAL_EXECUTION_STATUS_SYNC` | sync proof |
| Review summary | `reports/paper_daily_review_summary.md` | `Latest snapshot date` label | 높음 | `DAILY_REVIEW` | normal day mismatch blocks; no-action day mismatch warning |
| Performance summary | `reports/paper_performance_summary.md` | `Latest Snapshot Date`/similar labels | 높음 | `DAILY_REVIEW` | mismatch warning |
| Review template CSV | `reviews/paper_manual_review_log_template.csv` | 모든 `review_date == trade_date`; UTF-8 BOM safe CSV reader | 높음 | `DAILY_REVIEW`, `MANUAL_REVIEW_TEMPLATE` | mismatch는 no-action day에도 blocker |
| Review validation report | `reviews/paper_manual_review_log_validation_report.md` | `Validation result: PASS` text | 높음 | `DAILY_REVIEW` | PASS 강제 |
| Manual Review template evidence | `reports/manual_review_template_export_YYYYMMDD.json` | Notion evidence schema/date/account | 낮음 | `MANUAL_REVIEW_TEMPLATE` | export proof |
| Review preview | `manual_review_import_preview_YYYYMMDD.json` | preview payload date/account validate | 낮음 | `MANUAL_REVIEW_PREVIEW`, `MANUAL_REVIEW_APPEND` | duplicates/warnings 반영 |
| Review commit report | `manual_review_import_commit_YYYYMMDD.json` | 존재 위주 | 낮음 | `MANUAL_REVIEW_APPEND`, `MANUAL_REVIEW_STATUS_SYNC` | append proof |
| Review status sync evidence | `reports/manual_review_status_sync_YYYYMMDD.json` | Notion evidence schema/date/account | 낮음 | `MANUAL_REVIEW_STATUS_SYNC` | sync proof |
| Current state | `paper_current_state_YYYYMMDD.json` | 파일명 date | 낮음 | `FINAL_STATUS`, paper status | no-action EOD roll-forward 대상 |
| Account snapshot | `paper_account_snapshot.csv` | row `snapshot_date == trade_date` | 중간 | paper status/EOD | same-date row 필요 |
| Position snapshot | `paper_position_snapshot.csv` | rows `snapshot_date == trade_date` | 중간 | paper status/EOD | same-date rows 필요 |

## 5. Notion Status Matrix

| Notion stage | 조회 필터 | 읽는 상태 속성 | PASS 기준 | WARNING/BLOCKED 기준 | 관련 코드 |
| --- | --- | --- | --- | --- | --- |
| Daily Plan | external key `account_id + trade_date` | `sync_status` | row 존재, account/date mismatch 없음 | row 0이면 UNKNOWN; mismatch는 BLOCKED | `core/paper_daily_ops_notion_status.py:267` |
| Manual Execution Template | `Execution Date == trade_date`, `Account ID == account_id` | `Status`, `Import Status` | row 존재 | row 0 UNKNOWN; account/date mismatch BLOCKED | `core/paper_daily_ops_notion_status.py:292` |
| Manual Execution Preview | template 조회 결과 재사용 | `Status`, `Import Status`, Actual Price | `READY` row > 0 and missing price 0 | READY row with missing Actual Price WARNING | `core/paper_daily_ops_notion_status.py:320` |
| Manual Execution Status Sync | `Execution Date == trade_date`, `Account ID == account_id` | `Import Status`, fallback `Status` | 모든 row가 `COMMITTED`/`SYNCED`/`IMPORTED` | 일부만 synced면 WARNING; row 0 UNKNOWN | `core/paper_daily_ops_notion_status.py:339`, `:515` |
| Manual Review Template | `Review Date == trade_date`, `Account ID == account_id` | `Review Status`, `Import Status` | row 존재 | row 0 UNKNOWN; mismatch BLOCKED | `core/paper_daily_ops_notion_status.py:367` |
| Manual Review Preview | template 조회 결과 재사용 | `Review Status`, `Import Status` | `READY` 또는 `REVIEWED` row > 0 | row 0 UNKNOWN | `core/paper_daily_ops_notion_status.py:395` |
| Manual Review Status Sync | `Review Date == trade_date`, `Account ID == account_id` | `Import Status`, fallback `Review Status` | 모든 row가 `COMMITTED`/`SYNCED`/`IMPORTED` | 일부 또는 전부 unsynced WARNING | `core/paper_daily_ops_notion_status.py:411`, `:515` |

Manual Execution importer의 실제 preview 대상은 `Execution Date == date`, `Status == READY`, `Account ID == account_id`인 row다. 이후 `Side in {BUY, SELL}`, `Quantity > 0`, `Actual Price > 0`를 validation한다. Import Status는 candidate fetch filter가 아니라 candidate metadata로 읽힌다.

Manual Review importer는 별도 확인이 필요하지만 운영 문서와 기존 회귀상 `Import Status=READY`, review date/account, manual answer/review status 조건이 preview 후보의 핵심 조건이다.

## 6. Reconciliation Rule Inventory

| rule_id | 적용 stage | 입력 조건 | 출력 status | conflict | OPER9 계열 | 관련 테스트 |
| --- | --- | --- | --- | --- | --- | --- |
| `OPER9_6_<STAGE>_NOTION_BLOCKED` | all reconciled stages | Notion status BLOCKED 또는 notion_errors | BLOCKED | true | OPER9-6 | `test_notion_mismatch_blocks_stage` |
| `OPER9_6_DAILY_PLAN_LOCAL_AND_NOTION_PRESENT` | Daily Plan export | local plan DONE + Notion row 있음 | DONE | false | OPER9-6 | `test_include_notion_read_improves_daily_plan_export_stage` |
| `OPER9_6_DAILY_PLAN_LOCAL_ONLY` | Daily Plan export | local plan DONE + Notion row 없음 | READY | false | OPER9-6 | `test_local_plan_without_notion_plan_reconciles_export_ready` |
| `OPER9_6_DAILY_PLAN_NOTION_WITHOUT_LOCAL` | Daily Plan export | Notion row 있음 + local plan 없음 | WARNING | true | OPER9-6 | `test_notion_plan_without_local_plan_is_reconciliation_warning` |
| `OPER9_6_DAILY_PLAN_MISSING_BOTH` | Daily Plan export | local/Notion 모두 없음 | BLOCKED | false | OPER9-6 | stage matrix tests |
| `OPER9_17_EXEC_TEMPLATE_NO_CANDIDATES` | Manual Execution template | `no_execution_candidates=true` | DONE | false | OPER9-17 | `test_no_execution_candidates_skips_manual_execution_loop` |
| `OPER9_6_EXEC_TEMPLATE_NOTION_WITHOUT_LOCAL_PLAN` | Manual Execution template | Notion rows exist but Daily Plan not DONE | WARNING | true | OPER9-6 | reconciliation tests |
| `OPER9_6_EXEC_TEMPLATE_LOCAL_PLAN_MISSING` | Manual Execution template | Daily Plan not DONE | BLOCKED | false | OPER9-6 | stage matrix tests |
| `OPER9_6_EXEC_TEMPLATE_NOTION_ROWS_PRESENT` | Manual Execution template | local plan DONE + Notion rows/status present | DONE | false | OPER9-6 | `test_notion_ready_manual_execution_preserves_preview_recommendation` |
| `OPER9_6_EXEC_TEMPLATE_LOCAL_PLAN_ONLY` | Manual Execution template | local plan DONE + no rows | READY | false | OPER9-6 | stage matrix tests |
| `OPER9_17_EXEC_PREVIEW_SKIPPED_NO_CANDIDATES` | Execution preview | `no_execution_candidates=true` | DONE | false | OPER9-17 | guard test |
| `OPER9_13_EXEC_PREVIEW_POST_COMMIT_NO_READY_ROWS` | Execution preview | local preview exists, no READY, but commit/sync/post-sync evidence exists | local status | warning conflict only if local WARNING | OPER9-13 | `test_manual_execution_post_sync_ready_absence_is_not_conflict` |
| `OPER9_6_EXEC_PREVIEW_LOCAL_WITHOUT_READY_NOTION` | Execution preview | local preview exists, no READY, no downstream evidence | WARNING | true | OPER9-6 | reconciliation tests |
| `OPER9_6_EXEC_PREVIEW_LOCAL_VALID` | Execution preview | local preview valid | local status | warning if local WARNING | OPER9-6 | stage tests |
| `OPER9_6_EXEC_PREVIEW_READY_MISSING_PRICE` | Execution preview | READY row with missing Actual Price | WARNING | true | OPER9-6 | `test_notion_execution_ready_missing_actual_price_is_warning` |
| `OPER9_6_EXEC_PREVIEW_READY_ROWS` | Execution preview | READY rows, local preview missing | READY | false | OPER9-6 | `test_notion_ready_manual_execution_preserves_preview_recommendation` |
| `OPER9_6_EXEC_PREVIEW_NO_READY_ROWS` | Execution preview | no local preview and no READY rows | UNKNOWN | false | OPER9-6 | stage tests |
| `OPER9_17_EXEC_COMMIT_SKIPPED_NO_CANDIDATES` | Execution commit | `no_execution_candidates=true` | DONE | false | OPER9-17 | guard test |
| `OPER9_6_EXEC_COMMIT_LOCAL_REPORT_PRESENT` | Execution commit | local commit report exists | DONE | false | OPER9-6 | `test_existing_execution_commit_suppresses_commit_recommendation` |
| `OPER9_6_EXEC_COMMIT_LEDGER_WITHOUT_REPORT` | Execution commit | ledger/snapshot evidence without report | WARNING | true | OPER9-6 | reconciliation tests |
| `OPER9_6_EXEC_COMMIT_NOTION_COMMITTED_WITHOUT_LOCAL` | Execution commit | Notion committed/synced but no local report | BLOCKED | true | OPER9-6 | `test_notion_committed_without_local_commit_blocks_commit_recommendation` |
| `OPER9_6_EXEC_COMMIT_PREVIEW_VALID` | Execution commit | local preview valid, no commit | READY | false | OPER9-6 | stage matrix tests |
| `OPER9_6_EXEC_COMMIT_PREVIEW_MISSING` | Execution commit | preview missing | BLOCKED | false | OPER9-6 | stage tests |
| `OPER9_17_EXEC_SYNC_SKIPPED_NO_CANDIDATES` | Execution status sync | `no_execution_candidates=true` | DONE | false | OPER9-17 | guard test |
| `OPER9_6_EXEC_SYNC_NOTION_SYNCED_WITHOUT_LOCAL_COMMIT` | Execution status sync | Notion synced but local commit missing | BLOCKED | true | OPER9-6 | reconciliation tests |
| `OPER9_6_EXEC_SYNC_LOCAL_COMMIT_MISSING` | Execution status sync | local commit missing | BLOCKED | false | OPER9-6 | stage tests |
| `OPER9_6_EXEC_SYNC_NOTION_SYNCED` | Execution status sync | local commit exists + Notion synced | DONE | false | OPER9-6 | status sync tests |
| `OPER9_6_EXEC_SYNC_REVIEW_DONE_NOTION_UNSYNCED` | Execution status sync | local REVIEW_DONE but execution Notion unsynced | WARNING | true | OPER9-6 | sync regression tests |
| `OPER9_6_EXEC_SYNC_LOCAL_COMMIT_UNSYNCED` | Execution status sync | local commit exists, Notion not synced | READY | false | OPER9-6 | `test_local_commit_with_unsynced_notion_status_keeps_sync_recommendation` |
| `OPER9_6_REVIEW_TEMPLATE_LOCAL_TEMPLATE_MISSING` | Manual Review template | local review not ready | BLOCKED | false | OPER9-6 | stage tests |
| `OPER9_6_REVIEW_TEMPLATE_NOTION_ROWS_PRESENT` | Manual Review template | rows present | DONE | false | OPER9-6 | stage tests |
| `OPER9_6_REVIEW_TEMPLATE_LOCAL_ONLY` | Manual Review template | local template exists, no rows | READY | false | OPER9-6 | `test_review_template_local_without_notion_rows_is_ready` |
| `OPER9_6_REVIEW_PREVIEW_LOCAL_WITHOUT_READY_NOTION` | Review preview | local preview exists, no ready rows | WARNING | true | OPER9-6 | review tests |
| `OPER9_6_REVIEW_PREVIEW_LOCAL_VALID` | Review preview | local preview valid | local status | warning if local WARNING | OPER9-6 | stage tests |
| `OPER9_6_REVIEW_PREVIEW_READY_ROWS` | Review preview | Notion ready/reviewed rows, preview missing | READY | false | OPER9-6 | `test_notion_review_ready_without_local_preview_is_ready` |
| `OPER9_6_REVIEW_PREVIEW_NO_READY_ROWS` | Review preview | no local preview and no ready rows | UNKNOWN | false | OPER9-6 | wait-state tests |
| `OPER9_6_REVIEW_APPEND_LOCAL_REPORT_PRESENT` | Review append | local commit report exists | DONE | false | OPER9-6 | append tests |
| `OPER9_6_REVIEW_APPEND_LOG_WITHOUT_REPORT` | Review append | review log rows without report | WARNING | true | OPER9-6 | append tests |
| `OPER9_6_REVIEW_APPEND_NOTION_COMMITTED_WITHOUT_LOCAL` | Review append | Notion committed/synced without local report | BLOCKED | true | OPER9-6 | reconciliation tests |
| `OPER9_6_REVIEW_APPEND_PREVIEW_VALID` | Review append | local preview valid | READY | false | OPER9-6 | stage tests |
| `OPER9_6_REVIEW_APPEND_PREVIEW_MISSING` | Review append | preview missing | BLOCKED | false | OPER9-6 | stage tests |
| `OPER9_6_REVIEW_SYNC_LOCAL_COMMIT_MISSING` | Review status sync | review commit report missing | BLOCKED | false | OPER9-6 | stage tests |
| `OPER9_6_REVIEW_SYNC_NOTION_SYNCED` | Review status sync | local commit + Notion synced | DONE | false | OPER9-6 | `test_review_done_with_synced_notion_remains_terminal_without_conflicts` |
| `OPER9_15_REVIEW_SYNC_REVIEW_DONE_NOTION_UNSYNCED` | Review status sync | local REVIEW_DONE but review Notion unsynced | READY | false | OPER9-15 | `test_review_done_with_unsynced_notion_recommends_review_status_sync` |
| `OPER9_6_REVIEW_SYNC_LOCAL_COMMIT_UNSYNCED` | Review status sync | local commit exists, Notion unsynced | READY | false | OPER9-6 | `test_review_commit_with_unsynced_notion_status_reconciles_sync_ready` |
| `OPER9_6_FINAL_REVIEW_DONE_NOTION_UNSYNCED` | Final status | REVIEW_DONE but Final stage sees unsynced Notion | WARNING | true | OPER9-6 | final tests |
| `OPER9_6_FINAL_REVIEW_DONE` | Final status | `workflow_status=REVIEW_DONE` | DONE | false | OPER9-6 | terminal tests |
| `OPER9_6_<STAGE>_NOTION_PASS/WARNING/LOCAL_ONLY` | fallback | generic Notion reconciliation | local/WARNING/local | warning conflict for Notion warning | OPER9-6 | generic tests |

## 7. Operator Summary Decision Rules

`build_daily_ops_status()`의 큰 순서는 다음과 같다.

1. account/data/trade date를 normalize하고 trade date가 data date 이후인지 검사한다.
2. account root와 legacy root를 resolve한다.
3. stage list를 local 기준으로 생성한다.
4. `include_notion_read`가 true이면 Notion live read 결과를 stage에 attach한다.
5. `apply_reconciliation()`로 local/Notion 상태를 조정한다.
6. `workflow_status == REVIEW_DONE`이고 required status sync가 없으면 terminal로 보고 모든 `next_command`를 제거한다.
7. `overall_status`, first `next_command`, `next_action`, stage counts, summary, operator summary를 만든다.

`operator_summary.current_step` 선택 우선순위:

1. terminal이면 `FINAL_STATUS`.
2. reconciliation recommended action이 `RESOLVE_CONFLICT`이면 첫 conflict stage.
3. top-level `next_command`가 있으면 그 command를 가진 stage.
4. Manual Execution 또는 Manual Review manual input wait stage.
5. 첫 `BLOCKED`, 그 다음 첫 `WARNING`, 첫 `READY`, 첫 `UNKNOWN`.

`recommended_operator_action` 선택 기준:

| 조건 | action |
| --- | --- |
| terminal | `NONE` |
| reconciliation conflict | `RESOLVE_CONFLICT` |
| manual input wait | `WAIT_FOR_INPUT` |
| next command `READ_ONLY` | `RUN_NEXT_COMMAND` |
| next command `LEDGER_WRITE` | `RUN_COMMIT` |
| next command `NOTION_WRITE` or `STATUS_SYNC` | sync command이면 `RUN_SYNC`, 그 외 `RUN_NEXT_COMMAND` |
| next command `UNKNOWN` and not dangerous | `RUN_NEXT_COMMAND` |
| summary fallback | `NONE`, `CHECK_NOTION`, `RESOLVE_BLOCKERS` 등 |

`next_action` command classification:

| 명령 패턴 | command_type | risk_level | approval |
| --- | --- | --- | --- |
| broker/order/live-order 포함 | `UNKNOWN` | `DANGEROUS` | 필요 |
| `import_notion_executions.py --commit`, `import_notion_reviews.py --commit` | `LEDGER_WRITE` | `REQUIRES_MANUAL_REVIEW` | 필요 |
| `--confirm-actual` 또는 `sync_notion_` | `NOTION_WRITE` | `REQUIRES_MANUAL_REVIEW` | 필요 |
| `import_notion_* --preview` | `READ_ONLY` | `SAFE` | 불필요 |
| `paper.py data-freshness`, `paper.py status` | `READ_ONLY` | `SAFE` | 불필요 |
| 그 외 | `UNKNOWN` | `REQUIRES_MANUAL_REVIEW` | 필요 |

`FINAL_STATUS` terminal 판단은 `paper.py status`의 `workflow_status=REVIEW_DONE`이면서 required status sync stage가 `READY` with `next_command` 상태가 아닐 때만 true다.

## 8. Execution Candidate Count Audit

### 8.1 Orchestrator candidate count 기준

함수: `core/paper_daily_ops_orchestrator.py:_daily_plan_execution_candidate_count()` (`:1242`)

현재 로직:

- `daily_action_plan_YYYYMMDD.json`을 읽는다.
- JSON root에 `items`가 없으면 `None`.
- `items`가 list가 아니면 `None`.
- 각 item에 대해 아래 조건을 모두 만족할 때만 count 증가:
  - `action == "EXECUTE"`
  - `status == "PENDING"`
  - `side in {"BUY", "SELL"}`

즉, 현재 Orchestrator는 `items[].action=BUY/SELL` 자체를 실행 후보로 세지 않는다.

### 8.2 현재 Daily Plan schema

2026-06-15 산출물:

- 파일: `outputs\paper_accounts\paper_orch_smoke_202606\daily_action_plan_20260615.json`
- top-level keys: `account_id`, `data_date`, `fingerprints`, `generated_at`, `items`, `official_run`, `plan_date`, `run_mode`, `schema_version`, `trade_date`
- `items` count: 9
- action counts: `BUY=7`, `SELL=2`
- status counts: `None=9`
- side counts: `None=9`
- type counts: `None=9`
- sample symbols: `AMT`, `BF-B`, `AVB`, `PLD`, `AMCR`, `CCL`, `LIN`, `LYV`, `SW`

Sample item shape:

```json
{
  "action": "SELL",
  "symbol": "AMT",
  "quantity": 51,
  "price": 187.17999267578125,
  "reason": "SWITCH_OUT (to BF-B, Score Gap: 6.0)",
  "warning": null,
  "note": null
}
```

### 8.3 Export 기준

`core/notion_exporters.py:_manual_execution_template_candidates_from_sidecar()` (`:817`)는 Daily Plan sidecar의 `items[]`를 읽고 다음 조건으로 Manual Execution candidate를 만든다.

- `side = item["action"] or item["type"]`
- `side in {"BUY", "SELL"}`
- `symbol` 존재
- `quantity` 또는 `shares`가 positive number

따라서 2026-06-15 plan의 `action=BUY/SELL`, `quantity>0` 9개는 export 기준으로 Manual Execution candidate 9개다.

### 8.4 Import 기준

`core/notion_manual_execution_importer.py:fetch_manual_execution_pages()` (`:241`)는 Notion Manual Executions DB에서 다음 row를 preview/commit 대상으로 읽는다.

- `Execution Date == date`
- `Status == READY`
- `Account ID == account_id` 또는 default account fallback

`normalize_manual_execution_pages()`와 `_validate_candidate_shape()`는 다음을 validation한다.

- `Side in {"BUY", "SELL"}`
- `Quantity > 0`
- `Actual Price > 0`
- execution date, symbol 필수

즉 import 기준도 `BUY/SELL`, positive quantity/actual price 구조다.

### 8.5 2026-06-15 사례 결론

확인된 사실:

- Daily Plan JSON에는 BUY/SELL execution item 9개가 있다.
- Notion Manual Execution row 9개가 READY/NOT_IMPORTED 상태로 존재했던 운영 이력이 있다.
- 실제 `import_notion_executions.py --commit` 결과 committed rows 9개가 있었다.
- Orchestrator는 `MANUAL_EXECUTION_TEMPLATE.no_execution_candidates=true`, `execution_candidate_count=0`, `OPER9_17_EXEC_TEMPLATE_NO_CANDIDATES`로 판정했다.

확인된 코드 원인:

- Orchestrator candidate count 기준이 현재 Daily Plan schema 및 Notion export/import 기준과 불일치한다.
- Orchestrator는 `action=EXECUTE`, `status=PENDING`, `side=BUY/SELL` 구조를 기대하지만, 현재 official Daily Plan sidecar는 `action=BUY/SELL`, `quantity>0` 구조다.
- 이 때문에 실제 execution candidates가 9개인데도 count가 0으로 계산되었다.

위 결론은 코드와 산출물 기준으로 확인되었다. 수정은 후속 MFU-OPER9-20C 범위다.

## 9. OPER9 Policy Inventory

| 범위 | 정책 요약 | 코드/Rule 연결 | 테스트 연결 |
| --- | --- | --- | --- |
| OPER9-1/2 | Daily Ops Orchestrator local MVP와 stage inventory | `STAGE_NAMES`, local stage builders | stage matrix tests |
| OPER9-3 | status JSON contract hardening | read-only/write flags, guards | CLI JSON tests |
| OPER9-4/4A | Notion evidence sidecar contract와 compact filename date | `core/paper_daily_ops_evidence.py` | evidence path/schema tests |
| OPER9-5 | Notion live read status verification | `core/paper_daily_ops_notion_status.py` | live read mock tests |
| OPER9-6 | Local/Notion reconciliation matrix | `core/paper_daily_ops_reconciliation.py` | reconciliation rule tests |
| OPER9-7 | operator summary JSON contract | `core/paper_daily_ops_operator_summary.py` | operator summary tests |
| OPER9-8/9 | stage advancement 및 stale next command suppression | `_first_next_command()`, `_is_stale_next_command_stage()` | stage advancement matrix tests |
| OPER9-10 | Notion env loading alignment | CLI dotenv load | env-only tests |
| OPER9-11/12 | operational path and Notion schema validation docs | docs/schema validation | docs/tests |
| OPER9-13 | Manual Execution post-commit no READY rows handling | `OPER9_13_EXEC_PREVIEW_POST_COMMIT_NO_READY_ROWS` | `test_manual_execution_post_sync_ready_absence_is_not_conflict` |
| OPER9-14 | Manual Review wait-state hardening | manual review pending wait helpers | `test_manual_review_pending_rows_wait_for_notion_input` |
| OPER9-15 | Review status sync required before terminal | `OPER9_15_REVIEW_SYNC_REVIEW_DONE_NOTION_UNSYNCED`, `_has_required_status_sync()` | `test_review_done_with_unsynced_notion_recommends_review_status_sync` |
| OPER9-16 | Date-scoped review artifact guard | fixed review artifact date checks | `test_stale_review_artifacts_should_not_mark_daily_review_done` |
| OPER9-17 | No-execution-candidates advancement guard | `_daily_plan_execution_candidate_count()`, `OPER9_17_*` | `test_no_execution_candidates_skips_manual_execution_loop` |
| OPER9-18 | No-action day daily review completion guard | `no_action_day_review_guard`, snapshot mismatch allowance | no-action review guard tests |
| OPER9-19A | EOD preflight account scope alignment | `scripts/paper.py handle_eod` | `test_eod_dry_run_preflight_uses_non_default_account_paths` |
| OPER9-19B | No-action EOD roll-forward verification | `scripts/run_paper_eod_update.py`, status/orchestrator closure | no-action EOD/status tests |

기존 기준 대비 변화 분석은 이 문서에서 수행하지 않는다. 다음 작업에서 pre-OPER9 baseline과 OPER9-added criteria를 비교한다.

## 10. Risks / Known Inconsistencies

| Risk | Severity | 확인 상태 | 설명 |
| --- | --- | --- | --- |
| Execution candidate count schema mismatch | High | 확인됨 | 실제 BUY/SELL 후보가 있어도 Orchestrator가 0개로 오판할 수 있다. |
| Notion rows READY/NOT_IMPORTED인데 no candidates skip | High | 2026-06-15 사례로 확인됨 | Manual Execution Template/Preview/Commit/Status Sync가 DONE으로 skip되어 status sync가 누락될 수 있다. |
| Execution commit artifact가 있는데 no candidates sync skip | Medium/High | 확인됨 | 2026-06-15 stage는 no candidates guard가 먼저 적용되어 downstream local/Notion evidence보다 우선했다. |
| Daily Review no-action guard 오염 | Medium | 확인됨 | 잘못된 no candidates가 `no_action_day_review_guard=true`로 전파되어 snapshot mismatch를 warning으로 낮출 수 있다. Template date mismatch는 여전히 blocker다. |
| fixed review filenames stale risk | Medium | guard 존재 | OPER9-16/18로 template date/validation은 강제하지만 summary/performance는 조건부 warning이다. |
| Notion live read API/schema warning | Medium | 관측됨 | Account ID select option 누락 등은 live read status WARNING을 만들 수 있다. |

## 11. Recommended Next Task

1. MFU-OPER9-20B: pre-OPER9 baseline과 OPER9-added decision criteria 비교.
2. MFU-OPER9-20C: Execution candidate count schema alignment 수정.
   - Orchestrator candidate count를 `core/notion_exporters.py`의 Manual Execution export 기준과 맞춘다.
   - 최소 후보 조건은 `items[]`, `action/type in {BUY, SELL}`, `symbol` 존재, `quantity/shares > 0`가 되어야 한다.
   - 기존 `action=EXECUTE/status=PENDING/side=BUY/SELL` legacy 형태를 지원할지 정책 결정이 필요하다.
3. Manual Execution status sync priority hardening 검토.
   - commit artifact 또는 Notion committed rows가 있으면 no-candidates skip보다 downstream sync evidence를 우선할지 결정한다.

## 12. No-write Safety Confirmation

실행하지 않은 명령:

- `scripts/export_paper_to_notion.py --confirm-actual`
- `scripts/import_notion_executions.py --commit`
- `scripts/import_notion_reviews.py --commit`
- `scripts/sync_notion_execution_status.py`
- `scripts/sync_notion_review_status.py`
- `scripts/paper.py eod --commit`
- `scripts/paper.py commit`
- broker/API/order 관련 명령
- ledger/DB mutation 명령

이번 감사 중 생성된 `outputs\orch_status_audit_20260615.json`은 read-only status 조회 결과물이며 git commit 대상이 아니다.

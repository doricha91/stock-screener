# MFU-PAPER11-0 Paper Daily Pipeline Investigation

## Summary

- `scripts/run_paper_daily_plan.py` is the paper-plan entrypoint. It does not trade, update snapshots, or write reports. It loads paper state from `paper_execution_log.csv` rows strictly before the target date, then calls `generate_daily_plan(...)` with a paper output path.
- `scripts/run_paper_eod_update.py` is the only core paper execution-chain writer in this flow. In dry-run it previews journal parsing, log append candidates, account preview, and snapshot preview. With `--commit` it writes the paper execution log, current state JSON, account snapshot CSV, and position snapshot CSV.
- Current `preflight_check` exists only at `core/preflight_check.py` and is called by `scripts/run_front_test.py`, not by `run_paper_daily_plan.py`.
- Current paper flow is loosely chained by file conventions, not by one orchestrator script: `plan -> eod -> report generators -> review generators -> manual review workflow`.
- Path separation between `outputs/paper_test` and `outputs/front_test` is mostly guaranteed by `core/paths.py` and explicit paper wrappers, but `core/daily_plan_generator.generate_daily_plan()` defaults to `front_daily_action_plan_path()` if no output path is given. That is the main contamination risk if a future orchestrator calls the wrong entrypoint or omits `output_path`.

## 조사한 파일

- `scripts/run_paper_daily_plan.py`
- `scripts/run_paper_eod_update.py`
- `scripts/preflight_check.py` -> not found
- `preflight_check.py` -> not found
- `core/preflight_check.py`
- `core/daily_plan_generator.py`
- `core/paper_state_provider.py`
- `core/paths.py`
- Additional downstream scripts:
  - `scripts/generate_paper_realized_trade_journal.py`
  - `scripts/generate_paper_symbol_realized_performance.py`
  - `scripts/generate_paper_realized_ranking_report.py`
  - `scripts/generate_paper_symbol_unrealized_performance.py`
  - `scripts/generate_paper_symbol_side_by_side_performance.py`
  - `scripts/generate_paper_symbol_review_buckets.py`
  - `scripts/generate_paper_symbol_review_worksheet.py`
  - `scripts/generate_paper_daily_review_summary.py`
  - `scripts/generate_paper_manual_review_log_template.py`
  - `scripts/validate_paper_manual_review_log.py`
  - `scripts/append_paper_manual_review_log.py`

## run_paper_daily_plan.py 역할

- Input:
  - target date
  - historical paper execution log via `load_official_paper_state_for_daily_plan()`
- Internal calls:
  - `_normalize_date_for_db()`
  - `load_official_paper_state_for_daily_plan()`
  - `paper_daily_action_plan_path()`
  - `generate_daily_plan(...)`
- Output:
  - `outputs/paper_test/daily_action_plan_YYYYMMDD.md`
  - `outputs/paper_test/config_snapshots/paper_config_snapshot_YYYYMMDD.json`
- Read/write:
  - reads paper execution log
  - writes paper action plan markdown and paper config snapshot
- Operational meaning:
  - official paper current-state reconstruction + daily plan generation
  - not an EOD committer
  - not a report orchestrator

## 선행 실행 필요 항목

- Mandatory before `run_paper_daily_plan.py`
  - market DB must exist and be fresh enough for `generate_daily_plan()`
  - universe snapshot / screener data used by `generate_daily_plan()` must already exist
  - `outputs/paper_test/paper_execution_log.csv` should exist if there is paper history to reconstruct
- Soft dependency
  - previous successful `run_paper_eod_update.py --commit` on earlier days, otherwise plan state falls back to empty/no-position paper state
- Not required by code
  - `paper_account_snapshot.csv`
  - `paper_position_snapshot.csv`
  - review/report outputs

## 후속 실행 필요 항목

- Immediately after plan generation:
  - `scripts/run_paper_eod_update.py --date <same_date> --allow-empty-journal`
  - then, after manual fill review, `scripts/run_paper_eod_update.py --date <same_date> --commit`
- After EOD commit:
  - reports regeneration chain
  - review chain

## preflight_check.py 조사 결과

- File existence:
  - `scripts/preflight_check.py` -> not found
  - `preflight_check.py` -> not found
  - `core/preflight_check.py` -> found
- Actual checks in `core/preflight_check.py`:
  - data freshness from market DB
  - front-test current state integrity via `load_current_state()`
  - regime calculation through `market_analyzer.get_market_state()`
- Current callers:
  - `scripts/run_front_test.py`
- Direct link to `run_paper_daily_plan.py`:
  - none
- Reusable for paper automation:
  - partially
  - market DB freshness and regime calculation are reusable
  - state integrity is currently front-test specific, not paper specific
- Missing paper-specific checks:
  - existence/parseability of `paper_execution_log.csv`
  - plan-date ordering vs existing paper trades
  - expected paper action plan path existence before EOD
  - snapshot/archive path writeability inside `outputs/paper_test`
  - review/template/log path integrity for downstream review workflow

## 현재 paper daily pipeline 후보

Step 1. 선행 데이터/상태 준비
- 관련 파일:
  - market DB
  - universe snapshot inputs
  - `outputs/paper_test/paper_execution_log.csv`
- 관련 스크립트:
  - no single paper preflight script currently
- read/write 여부:
  - mixed, but outside paper loop this is mostly prerequisite data preparation

Step 2. run_paper_daily_plan.py
- 입력:
  - target date
  - `paper_execution_log.csv`
  - market/universe/screener inputs through `generate_daily_plan()`
- 출력:
  - `outputs/paper_test/daily_action_plan_YYYYMMDD.md`
  - `outputs/paper_test/config_snapshots/...`
- 내부 호출 함수:
  - `load_official_paper_state_for_daily_plan`
  - `generate_daily_plan`
- read/write 여부:
  - paper output writer

Step 3. run_paper_eod_update.py dry-run
- 입력:
  - paper daily action plan markdown
  - existing `paper_execution_log.csv`
  - market DB for valuation preview
- 출력:
  - console preview only
- read/write 여부:
  - read-only

Step 4. run_paper_eod_update.py --commit
- 입력:
  - same as dry-run
- 출력:
  - `paper_execution_log.csv`
  - `paper_current_state_YYYYMMDD.json`
  - `paper_account_snapshot.csv`
  - `paper_position_snapshot.csv`
- 수정 파일:
  - all four above
- read/write 여부:
  - dangerous writer

Step 5. reports regeneration
- 관련 스크립트:
  - `generate_paper_realized_trade_journal.py`
  - `generate_paper_symbol_realized_performance.py`
  - `generate_paper_realized_ranking_report.py`
  - `generate_paper_symbol_unrealized_performance.py`
  - `generate_paper_symbol_side_by_side_performance.py`
  - `generate_paper_symbol_review_buckets.py`
  - `generate_paper_symbol_review_worksheet.py`
  - `generate_paper_daily_review_summary.py`
- 입력:
  - paper execution log / account snapshot / position snapshot / prior report CSVs
- 출력:
  - `outputs/paper_test/reports/*`
- read/write 여부:
  - review/report output writer

Step 6. review workflow
- template:
  - `generate_paper_manual_review_log_template.py`
- validator:
  - `validate_paper_manual_review_log.py`
- append:
  - `append_paper_manual_review_log.py`
- 수정 파일:
  - `outputs/paper_test/reviews/paper_manual_review_log.csv`
- read/write 여부:
  - review output writer

## read/write 위험 구분

- read-only
  - `scripts/run_paper_eod_update.py --allow-empty-journal` without `--commit`
  - `scripts/validate_paper_manual_review_log.py`
- paper output writer
  - `scripts/run_paper_daily_plan.py`
  - `scripts/run_paper_eod_update.py --commit`
- review output writer
  - all `scripts/generate_paper_*` under `reports/`
  - `scripts/generate_paper_manual_review_log_template.py`
  - `scripts/append_paper_manual_review_log.py`
- dangerous writer
  - `scripts/run_paper_eod_update.py --commit`
    - modifies `outputs/paper_test/paper_execution_log.csv`
    - modifies `outputs/paper_test/paper_account_snapshot.csv`
    - modifies `outputs/paper_test/paper_position_snapshot.csv`
    - writes `outputs/paper_test/paper_current_state_*.json`
- unknown
  - none in requested paper chain

## 원본/주요 파일 수정 스크립트

- `outputs/paper_test/paper_execution_log.csv`
  - `scripts/run_paper_eod_update.py --commit`
- `outputs/paper_test/paper_account_snapshot.csv`
  - `scripts/run_paper_eod_update.py --commit`
- `outputs/paper_test/paper_position_snapshot.csv`
  - `scripts/run_paper_eod_update.py --commit`
- `outputs/paper_test/reviews/paper_manual_review_log.csv`
  - `scripts/append_paper_manual_review_log.py`
- `outputs/front_test/*`
  - not touched by paper wrappers in the investigated flow
  - but `core/daily_plan_generator.generate_daily_plan()` defaults to `front_daily_action_plan_path()` when `output_path=None`

## outputs/front_test 오염 가능성

- Current paper wrappers are safe:
  - `run_paper_daily_plan.py` explicitly passes `paper_daily_action_plan_path(...)`
  - `run_paper_eod_update.py` uses `paper_*` paths only
  - report/review scripts all use `paper_reports_dir()` or `paper_reviews_dir()`
- Main contamination risk:
  - future orchestrator directly calls `generate_daily_plan()` without passing paper output path
  - future orchestrator accidentally reuses `run_front_test.py` preflight/state path assumptions
- So path separation is code-defined, but not impossible to bypass.

## 운영 자동화 전 권장 방향

- Judgment:
  - `C. 기존 preflight_check.py와 별도로 paper 운영용 preflight가 필요함`
- Reason:
  - current preflight is front-test oriented
  - paper plan/EOD/report/review chain has its own state files and failure modes
  - orchestrator needs explicit paper-specific checks before plan and before EOD commit

## 추가 결정 필요 사항

- Whether orchestrator should stop on missing prior `paper_execution_log.csv` or allow empty bootstrap state
- Whether dry-run EOD is mandatory before every commit EOD
- Exact report regeneration set after EOD commit:
  - minimal subset vs full PAPER9/PAPER10 chain
- Whether manual review steps belong in daily orchestrator or remain manual/optional
- Whether a new paper preflight should also verify review artifacts under `outputs/paper_test/reviews/`
- Whether `run_paper_daily_plan.py` should eventually enforce a paper-specific preflight internally or be kept thin

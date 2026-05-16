# MFU-PAPER6 Paper Loop Final TRD

## 핵심 모듈

- `core/paper_account_state.py`
  - `paper_execution_log.csv` reducer
- `core/paper_state_provider.py`
  - daily plan용 paper state provider
  - `trade_date < plan_date` cutoff
- `scripts/run_paper_daily_plan.py`
  - official paper daily plan entrypoint
- `core/daily_plan_generator.py`
  - market_state, screener, rebalance, switching, markdown 생성
- `scripts/run_paper_eod_update.py`
  - dry-run / commit / snapshot orchestration
- `core/paper_trade_preview.py`
  - `Rec_* -> Act_*` fallback
  - `paper_virtual_fill` source/reason
- `core/paper_config_snapshot.py`
  - final config snapshot 저장
- `core/universe_manager.py`
  - latest universe loader
  - quarterly universe as-of loader

## 데이터 흐름

### Daily Plan

1. `run_paper_daily_plan.py`
2. `load_official_paper_state_for_daily_plan(plan_date)`
3. `generate_daily_plan(...)`
4. `market_analyzer.get_market_state(target_date=plan_date, write_log=False)`
5. `build_screener_results(..., end_date=plan_date)`
6. `load_universe_snapshot_as_of_quarter(plan_date)`
7. action synthesis
8. `daily_action_plan_YYYYMMDD.md`
9. `paper_config_snapshot_YYYYMMDD.json`

### EOD

1. `run_paper_eod_update.py`
2. paper daily plan parse
3. paper trade preview 생성
4. dry-run 또는 commit
5. commit 시 execution log append
6. reducer 재실행
7. current state / account snapshot / position snapshot 저장

## as-of cutoff 정책

- paper daily plan account state
  - `trade_date < plan_date`
- EOD reducer / report
  - commit 이후 상태 유지
- screener/indicator
  - `price/indicator/score/buy_signal`은 `date <= plan_date`
- market_state
  - `target_date=plan_date`
  - `write_log=False`
- universe
  - 같은 분기 내 `plan_date` 이하 최신 snapshot
  - 없으면 이전 분기 최신 snapshot + warning

## switching 정책

- backtest parity 기준
  - `SELL -> SWITCH -> 일반 BUY`
- switch-in 후보
  - `buy_signal=True`
  - `score >= score_threshold`
  - `rs_val > 0`
- gate
  - `max_positions` full gate 없음
  - `target_long_slots` gate 없음
- duplicate BUY
  - same-day 동일 symbol 1회만 허용

## config snapshot

- 경로
  - `outputs/paper_test/config_snapshots/`
- 파일
  - `paper_config_snapshot_YYYYMMDD.json`
- archive
  - `outputs/paper_test/archive/config_snapshots/`
- 포함
  - `market_state_write_log=false`
  - `market_state`
  - `market_status_summary`
  - regime overlay 이후 `final_config`
  - `universe` metadata

## 테스트 범위

- state cutoff
  - `tests/test_paper_state_asof_cutoff.py`
- screener cutoff
  - `tests/test_screener_asof_cutoff.py`
  - `tests/test_paper_daily_plan_screener_cutoff.py`
- market log policy
  - `tests/test_paper_daily_plan_market_log_policy.py`
- switching parity
  - `tests/test_paper_switching_parity.py`
  - `tests/test_daily_plan_switch_symbol_mapping.py`
- EOD parser / virtual fill
  - `tests/test_paper_eod_plan_path.py`
  - `tests/test_paper_eod_rec_to_actual_fallback.py`
  - `tests/test_paper_eod_virtual_fill_source.py`
- config / universe snapshot
  - `tests/test_paper_config_snapshot.py`
  - `tests/test_universe_snapshot_asof.py`
  - `tests/test_paper_daily_plan_universe_asof.py`

## PAPER7로 넘길 기술 부채

- config snapshot replay 강제 적용 없음
- plan input snapshot 통합 없음
- full `run_paper_daily_plan.py` timeout 개선 필요
- 동일 날짜 regeneration diff harness 부재

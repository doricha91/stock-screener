# MFU-PAPER6 Paper Loop Final PRD

## 사용자 관점 기능

### 1. Daily Plan 생성

- 사용자 명령: `python scripts/run_paper_daily_plan.py --date YYYYMMDD`
- 입력 state
  - 공식 paper 계좌 상태
  - 기준: `paper_execution_log.csv`, `trade_date < plan_date`
- 출력
  - `outputs/paper_test/daily_action_plan_YYYYMMDD.md`
  - `outputs/paper_test/config_snapshots/paper_config_snapshot_YYYYMMDD.json`

### 2. EOD dry-run

- 사용자 명령: `python scripts/run_paper_eod_update.py --date YYYYMMDD --allow-empty-journal`
- 기본 input
  - `outputs/paper_test/daily_action_plan_YYYYMMDD.md`
- 동작
  - `Rec_*`를 paper virtual fill로 preview
  - file write 없이 rows/duplicates preview 제공

### 3. EOD commit

- 사용자 명령: `python scripts/run_paper_eod_update.py --date YYYYMMDD --allow-empty-journal --commit`
- 결과
  - `paper_execution_log.csv` append
  - `paper_current_state_YYYYMMDD.json` 저장
  - `paper_account_snapshot.csv` 저장
  - `paper_position_snapshot.csv` 저장

### 4. Duplicate 방지

- 같은 날짜 같은 trade preview 재실행 시 `trade_id` 기준 중복 append 방지
- same-day duplicate BUY 금지
  - `SWITCH_IN`
  - `STRATEGY_ENTRY`
  - 동일 symbol 2회 생성 금지

### 5. Config Snapshot

- daily plan 생성 시 사용한 final config 저장
- 저장 내용
  - market_state
  - market_status_summary
  - regime overlay 이후 final config
  - universe metadata
- 같은 날짜는 archive 후 replace

### 6. Universe As-Of

- latest snapshot 고정 사용 금지
- `plan_date`가 속한 분기 내 `plan_date` 이하 최신 snapshot 사용
- 없으면 이전 분기 이하 최신 snapshot 사용 + warning

## 재현성 정책

- paper daily plan account state
  - `trade_date < plan_date`
- EOD/report state
  - commit 이후 상태 반영
- screener/indicator
  - `date <= plan_date`
- market_state
  - `write_log=False`
- universe
  - quarterly as-of

## 제외 범위

- config snapshot replay 강제 적용
- universe snapshot 생성 로직 변경
- plan input snapshot 통합
- full replay mode
- benchmark/MDD/CAGR/Sharpe

## 운영 기대값

- official paper 계좌로 plan → dry-run → commit → snapshot 루프를 반복 가능
- 과거 날짜 재생성 시 최신 state/미래 price 혼입을 줄인 상태에서 검토 가능

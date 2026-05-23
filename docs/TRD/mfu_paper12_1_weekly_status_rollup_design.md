# MFU-PAPER12-1 Weekly/Status Rollup Design

## Summary

이번 PAPER12-1은 weekly/status rollup 조사 및 설계이며, 코드 구현과 writer 명령 실행은 포함하지 않는다.

현재 paper 운영 루프에서 주간 rollup의 기준축은 `paper_account_snapshot.csv`의 `snapshot_date`로 잡는 것이 가장 안전하다.  
이유는 다음과 같다.

- `paper.py status`도 snapshot 존재 여부를 기준으로 운영 상태를 판정한다.
- `paper_account_snapshot.csv`는 계좌 단위 핵심 지표를 날짜별로 1행씩 보관한다.
- `paper_position_snapshot.csv`는 같은 날짜의 종목 상태를 보강한다.
- `paper_execution_log.csv`는 거래가 없는 날 row가 0일 수 있으므로 주간 운영 완료 기준의 주축으로 쓰기 어렵다.
- report/review markdown 다수는 latest overwrite 구조라 날짜별 이력 원천으로는 제한적이다.

권장 설계는 아래와 같다.

- 주간 기준일: `snapshot_date`
- 기본 범위: 최근 `5` 영업일이 아니라 최근 `5` snapshot row 또는 `--start/--end` 명시 범위
- 운영 완료 판정: plan/snapshot/report/review artifact의 날짜별 존재 여부를 조합
- 계좌/포지션 변화는 snapshot 기반
- 거래 요약은 execution log 보조 집계
- review 상태는 template/log/validation의 최신 상태와 날짜 매핑을 혼합 사용

## 조사한 입력 파일

### Core paper state

- `outputs/paper_test/paper_account_snapshot.csv`
- `outputs/paper_test/paper_position_snapshot.csv`
- `outputs/paper_test/paper_execution_log.csv`
- `outputs/paper_test/daily_action_plan_YYYYMMDD.md`
- `outputs/paper_test/paper_current_state_YYYYMMDD.json`

### Reports

- `outputs/paper_test/reports/paper_daily_review_summary.md`
- `outputs/paper_test/reports/paper_performance_summary.md`
- `outputs/paper_test/reports/paper_equity_curve.csv`
- `outputs/paper_test/reports/paper_drawdown.csv`
- `outputs/paper_test/reports/paper_symbol_review_buckets.csv`
- `outputs/paper_test/reports/paper_symbol_review_worksheet.csv`

### Reviews

- `outputs/paper_test/reviews/paper_manual_review_log_template.csv`
- `outputs/paper_test/reviews/paper_manual_review_log_validation_report.md`
- `outputs/paper_test/reviews/paper_manual_review_log.csv`

## 현재 확인한 날짜 구조

### `paper_account_snapshot.csv`

핵심 컬럼:

- `snapshot_date`
- `cash`
- `position_count`
- `symbols`
- `positions_market_value`
- `total_equity_market_value`
- `cash_ratio_market_value`
- `unrealized_pnl`
- `realized_pnl`
- `total_pnl`
- `valuation_price_date`

현재 row:

- `2026-05-09`
- `2026-05-12`
- `2026-05-13`
- `2026-05-20`

판단:

- 주간 rollup의 primary key로 적합
- 시작/종료 equity, cash ratio, unrealized PnL 변화 계산에 직접 사용 가능

### `paper_position_snapshot.csv`

핵심 컬럼:

- `snapshot_date`
- `symbol`
- `shares`
- `avg_price`
- `cost_value`
- `close_price`
- `market_value`
- `unrealized_pnl`
- `position_status`

특징:

- 날짜당 종목 수만큼 multi-row
- 현재 샘플은 `2026-05-09`, `2026-05-12`, `2026-05-13`, `2026-05-20`

판단:

- 시작/종료 보유 종목 집합 비교에 적합
- `added_symbols`, `removed_symbols`, `held_symbols` 계산 가능
- 종목별 `market_value`, `unrealized_pnl` 변화 계산 가능

### `paper_execution_log.csv`

핵심 컬럼:

- `date`
- `symbol`
- `side`
- `shares`
- `price`
- `source`
- `status`
- `reason`

현재 trade date:

- `2026-05-09`: 3 rows
- `2026-05-12`: 4 rows
- `2026-05-13`: 3 rows

특징:

- 거래 없는 날짜는 row 0이 가능
- 주간 운영 미완료와 no-trade day를 구분해야 함

판단:

- `trade_count`, `buy_count`, `sell_count`, `no_trade_days` 계산에는 유용
- 운영 완료의 primary evidence로 쓰면 위험

### `daily_action_plan_YYYYMMDD.md`

현재 존재:

- `20260512`
- `20260513`
- `20260520`

판단:

- plan 생성 여부 증거로 사용 가능
- 다만 plan만 있고 commit snapshot이 없을 수 있으므로 `PLAN_READY` 근거 정도로 사용

### `paper_current_state_YYYYMMDD.json`

현재 존재:

- `20260509`
- `20260512`
- `20260513`
- `20260520`

판단:

- same-date commit 실행 여부의 강한 증거
- account/position snapshot과 함께 `COMMITTED` 판정에 포함 가능

## `paper.py status`와의 연결

`core/paper_status.py`의 현재 workflow status는 다음과 같다.

- `NO_PLAN`
- `PLAN_READY`
- `COMMITTED`
- `REVIEW_READY`
- `UNKNOWN_OR_INCOMPLETE`

권장 연결 방식:

- weekly rollup은 날짜별로 same logic을 재사용하거나 동등한 판정 함수를 사용
- 날짜별 `workflow_status` column을 rollup row에 그대로 포함
- 주간 summary header에는 `workflow_status_summary`를 별도 제공

권장 예:

- `all_dates_review_ready`
- `contains_unknown_or_incomplete`
- `latest_date_status = REVIEW_READY`

## weekly rollup 입력 데이터 정리

## 1. Account Snapshot 기반

계산 가능:

- `start_equity_market_value`
- `end_equity_market_value`
- `equity_change`
- `equity_change_pct`
- `start_cash`
- `end_cash`
- `cash_change`
- `start_cash_ratio`
- `end_cash_ratio`
- `cash_ratio_change`
- `start_unrealized_pnl`
- `end_unrealized_pnl`
- `unrealized_pnl_change`
- `position_count_start`
- `position_count_end`

보조 가능:

- `realized_pnl` start/end 비교
- `total_pnl` start/end 비교

주의:

- snapshot gap이 큰 주간에서는 “주중 매일 변화”가 아니라 “주간 시작/종료 변화”라는 점을 명시해야 함

## 2. Position Snapshot 기반

계산 가능:

- `start_symbols`
- `end_symbols`
- `added_symbols`
- `removed_symbols`
- `held_symbols`
- `top_positions_by_market_value`
- `top_unrealized_gain`
- `top_unrealized_loss`

추가 권장:

- `market_value_delta_by_symbol`
- `unrealized_pnl_delta_by_symbol`

주의:

- 가격이 없는 종목이 있으면 `positions_with_missing_valuation` 또는 stale valuation 경고가 필요

## 3. Execution Log 기반

계산 가능:

- `trade_count`
- `buy_count`
- `sell_count`
- `trade_dates`
- `no_trade_days`

보조 계산 가능:

- `realized_pnl_this_week`는 `paper_realized_trade_journal.csv`를 쓰면 더 정확함

권장:

- execution log 직접 realized 계산보다 PAPER9 산출물 재사용

## 4. Reports / Review 기반

### `paper_daily_review_summary.md`

현재 latest overwrite 구조다.

사용 가능:

- 최신 `workflow_status` 보조 설명
- latest high priority review symbols

제한:

- 날짜별 history source로 부적합

### `paper_performance_summary.md`

latest overwrite 구조다.

사용 가능:

- 최신 snapshot summary 보조 설명

제한:

- 주간 row-by-row source로 부적합

### `paper_symbol_review_buckets.csv`

latest symbol review state만 담고 있다.

사용 가능:

- latest review bucket counts
- latest high priority review items
- repeated review symbols 판단의 latest end-state anchor

제한:

- 주중 날짜별 bucket 변화는 복원 불가

### `paper_symbol_review_worksheet.csv`

latest worksheet row export다.

사용 가능:

- latest question count
- latest review 대상 symbol 목록

제한:

- 날짜별 review queue 변화 이력은 없음

### `paper_manual_review_log_template.csv`

특징:

- `review_date`
- `symbol`
- `question_id`
- `review_status`
- `follow_up_needed`

사용 가능:

- latest template row count
- pending review volume

제한:

- template은 아직 사람이 처리하지 않은 작업 목록일 수 있음
- weekly 완료 여부의 primary source는 아님

### `paper_manual_review_log_validation_report.md`

사용 가능:

- validation `PASS/FAIL`
- latest template integrity 상태

제한:

- 최신 validation만 알 수 있음
- 날짜별 validation history는 별도 누적되지 않음

### `paper_manual_review_log.csv`

사용 가능:

- `manual_review_rows`
- `reviewed_rows`
- `deferred_rows`
- `not_applicable_rows`
- `follow_up_needed` row count
- reviewed symbols

제한:

- 현재 row key는 `review_date + symbol + question_id`
- 주간 범위를 볼 때 `review_date` 기준 집계는 가능하지만 template 생성일과 review 처리일이 다를 수 있음

## 기준 날짜 권장안

## 1. 주간 기준일

권장: `snapshot_date`

이유:

- commit 완료 여부를 가장 안정적으로 반영
- account/position snapshot이 주간 성과와 포지션 변화를 연결하는 중심 데이터
- `paper.py status`와의 정합성이 높음

보조 날짜:

- `execution_log.date`
- `template.review_date`
- `daily_action_plan` filename date

## 2. 범위 지정

권장 우선순위:

1. `--start YYYYMMDD --end YYYYMMDD`
2. `--days 5`
3. `--week-start YYYYMMDD`

기본값 권장:

- `--days 5`

이유:

- 실제 거래일/운영일 밀도를 반영하기 쉬움
- 단순 최근 7일은 휴장일이 끼면 정보 밀도가 떨어질 수 있음

다만 구현 시 실제 의미는 “최근 5 calendar days”보다 “최근 5 snapshot rows” 또는 “해당 범위 내 snapshot_date들” 중 하나를 명확히 선택해야 한다.

권장:

- 기본 구현은 `--start/--end`와 `--days N snapshot rows` 조합

## Operation Coverage 설계

날짜별 coverage row에 아래를 포함하는 것을 권장한다.

- `date`
- `daily_action_plan_exists`
- `current_state_exists`
- `account_snapshot_exists`
- `position_snapshot_exists`
- `execution_log_rows`
- `reports_exists`
- `review_template_exists`
- `review_validation_status`
- `workflow_status`
- `missing_steps`
- `next_recommended_command`

### missing_steps 정의 초안

예:

- plan file 없음 -> `missing_plan`
- current_state/account/position snapshot 중 일부 없음 -> `missing_commit_snapshot`
- reports 없거나 stale -> `missing_reports`
- review template 없음 -> `missing_review_template`
- validation FAIL -> `review_validation_failed`

## operation gap 판단 기준 초안

### High severity

- `snapshot_without_plan`
- `account_snapshot_exists` but `position_snapshot_missing`
- `current_state_exists` but account/position snapshot missing
- `review_validation_failed`
- `workflow_status = UNKNOWN_OR_INCOMPLETE`

### Medium severity

- latest committed date 이후 reports 없음
- latest committed date 이후 review template 없음
- high priority review symbols가 있으나 manual review log에 대응 row 없음

### Low severity

- execution log row 0 on committed day
- universe/review auxiliary file 없음

주의:

- `execution_log_rows = 0`는 거래 없는 날이면 정상일 수 있으므로 gap으로 자동 판정하면 안 됨
- committed snapshot이 있고 position/account row가 정상이면 no-trade day는 정상 후보로 본다

## review 데이터 반영 가능성

권장 판단:

- 포함 가능하다
- 다만 latest overwrite 구조와 manual entry 지연을 감안해 “review completeness”는 soft metric으로 다뤄야 한다

권장 지표:

- `review_bucket_counts`
- `high_priority_review_items`
- `manual_review_rows`
- `pending_review_rows`
- `reviewed_rows`
- `validation_status`

정책:

- template만 있고 manual log row가 없으면 “미작성 상태”로 해석 가능
- pending row는 미완료 업무량으로 본다
- reviewed/deferred/not_applicable row는 weekly reviewed volume에 포함 가능

## reports overwrite 구조 대응

현재 다수 report markdown/csv는 latest overwrite 구조다.

따라서 weekly rollup에서 아래 원칙을 권장한다.

- account/position/execution log는 row-history source
- report markdown은 latest summary 보조 source
- 날짜별 history를 report file mtime으로 판단하지 않는다
- 날짜별 운영 완료 판정은 snapshot/plan/review artifact existence 중심으로 한다

## 추천 CLI

권장 후보:

```bash
python scripts/paper.py weekly-status
python scripts/paper.py weekly-status --days 5
python scripts/paper.py weekly-status --start 20260512 --end 20260520
python scripts/paper.py weekly-status --json
```

권장 이유:

- 기존 `status`와 naming 일관성 유지
- daily status의 상위 rollup이라는 의미가 명확함

## 추천 산출물

권장:

- `outputs/paper_test/reports/paper_weekly_status_summary.md`
- `outputs/paper_test/reports/paper_weekly_status_summary.csv`
- `outputs/paper_test/reports/paper_weekly_status_summary.json`

권장 역할:

- `.md`: operator-facing narrative summary
- `.csv`: 날짜별 operation coverage table
- `.json`: machine-readable integration payload

## 구현 범위 권장안

### PAPER12-2 최소 구현

- 날짜 범위 입력
- snapshot 중심 coverage row 생성
- account summary
- position added/removed symbols
- trade summary
- latest review/validation summary
- operation gap summary
- markdown + csv 출력

### 후속 단계로 미루는 것

- 날짜별 report freshness semantic check
- symbol-level weekly PnL delta table full expansion
- reviewed answer quality scoring
- backlog linkage
- weekly trend charts

## 구현 시 주의점

- `review` 관련 파일은 생성일과 처리일이 다를 수 있다
- no-trade day를 오류로 보면 안 된다
- latest overwrite report를 historical source로 오해하면 안 된다
- weekly rollup은 `status` 판정과 일관돼야 한다
- 기준 날짜를 `trade date`로 두면 snapshot 없는 운영일 처리에서 모호성이 커진다

## 최종 권장 결론

- 기준 날짜: `snapshot_date`
- 범위 기본값: 최근 5 snapshot rows 또는 명시적 `--start/--end`
- report 구조: `markdown + csv + json`
- CLI 이름: `paper.py weekly-status`
- operation gap severity: high/medium/low 3단계
- no-trade day: committed snapshot이 있으면 정상 가능
- review 정보 비어 있음: warning 또는 incomplete로 처리하되 hard fail은 지양

# MFU-PAPER12-1 Weekly / Status Rollup Design

## 1. 목적

이번 PAPER12-1은 weekly/status rollup 조사 및 설계이며, 코드 구현, DB write, paper 원장 수정은 포함하지 않는다.

이 문서는 paper 운영 결과를 주간 단위로 요약하기 위해 필요한 입력 데이터, 날짜 기준, 누락 판단 기준, 리포트 구조, 구현 범위를 정리한다.

핵심 질문은 아래와 같다.

- 이번 주에 어떤 날짜가 정상 운영됐는가?
- 누락된 단계는 무엇인가?
- equity, cash ratio, unrealized PnL, position count는 어떻게 변했는가?
- 거래/보유/리뷰 대상은 어떻게 변했는가?
- 다음 주에 확인할 warning이나 action item은 무엇인가?

## 2. 범위와 제외

이번 설계 범위:

- weekly/status rollup 입력 파일 조사
- 날짜 기준과 주간 범위 기준 제안
- 주간 summary report 구조 제안
- operation gap 판단 기준 제안
- review 데이터 반영 가능성 정리
- 추천 CLI와 산출물 형식 제안

이번 단계에서 제외:

- `paper.py` 수정
- report writer 구현
- DB write
- paper 원장 CSV 수정
- `prepare / preview / commit / review` 실행

## 3. 조사한 입력 파일

### 3.1 Canonical 시계열 입력

| 파일 | 날짜 기준 | 확인된 구조 | 주간 rollup에서의 역할 | 한계 |
|---|---|---|---|---|
| `outputs/paper_test/paper_account_snapshot.csv` | `snapshot_date` | account-level 일자별 snapshot | account summary의 기준 anchor | snapshot이 없는 날짜는 account 변화를 계산할 수 없음 |
| `outputs/paper_test/paper_position_snapshot.csv` | `snapshot_date` | symbol-level 일자별 snapshot | position summary의 기준 anchor | 일자별 포지션 변화는 snapshot 존재 날짜에 한정 |
| `outputs/paper_test/paper_execution_log.csv` | `date` | trade-level append log | trade summary 계산 | no-trade day가 존재할 수 있으므로 coverage 기준으로 단독 사용 불가 |

### 3.2 운영 상태 / 존재 여부 입력

| 파일 | 날짜 기준 | 주간 rollup에서의 역할 | 한계 |
|---|---|---|---|
| `outputs/paper_test/daily_action_plan_*.md` | 파일명 날짜 | plan 생성 여부 확인 | plan 내용만으로 commit 완료 여부는 판단 불가 |
| `outputs/paper_test/paper_current_state_*.json` | 파일명 날짜 | commit 이후 current state 존재 여부 확인 | account/position snapshot과 함께 봐야 의미가 완성됨 |

### 3.3 Auxiliary report 입력

| 파일 | 날짜 기준 | 주간 rollup에서의 역할 | 한계 |
|---|---|---|---|
| `outputs/paper_test/reports/paper_daily_review_summary.md` | latest snapshot date만 본문 포함 | 최신 review summary 참고 | overwrite 구조라 주간 이력의 canonical source로 쓰기 부적합 |
| `outputs/paper_test/reports/paper_performance_summary.md` | latest snapshot date만 본문 포함 | 최신 성과 보조 정보 | overwrite 구조 |
| `outputs/paper_test/reports/paper_equity_curve.csv` | `snapshot_date` | equity / cash / position count 시계열 보조 입력 | account snapshot과 중복 정보가 많아 secondary source로 쓰는 편이 안전 |
| `outputs/paper_test/reports/paper_drawdown.csv` | `snapshot_date` | 주간 drawdown / MDD 보조 정보 | primary coverage source는 아님 |
| `outputs/paper_test/reports/paper_symbol_review_buckets.csv` | latest snapshot 기준 | review bucket 요약 | overwrite 구조 |
| `outputs/paper_test/reports/paper_symbol_review_worksheet.csv` | latest snapshot 기준 | review 질문 worksheet | overwrite 구조 |

### 3.4 Review 입력

| 파일 | 날짜 기준 | 주간 rollup에서의 역할 | 한계 |
|---|---|---|---|
| `outputs/paper_test/reviews/paper_manual_review_log_template.csv` | `review_date` | pending review row 확인 | overwrite-style template일 가능성이 있어 과거 주간 이력과 완전 일치 보장 어려움 |
| `outputs/paper_test/reviews/paper_manual_review_log_validation_report.md` | generated at | validation 상태 확인 | markdown 파싱 필요 |
| `outputs/paper_test/reviews/paper_manual_review_log.csv` | `review_date` | 실제 reviewed row 집계 | manual review가 없는 날짜는 빈 상태가 정상일 수 있음 |

## 4. 입력 파일별 확인 결과

### 4.1 Account snapshot에서 계산 가능한 지표

`paper_account_snapshot.csv`에는 아래 필드가 있어 주간 account summary의 primary source로 적합하다.

- `total_equity_market_value`
- `cash`
- `cash_ratio_market_value`
- `unrealized_pnl`
- `position_count`
- `market_valuation_status`
- `valuation_price_date`
- `max_price_staleness_days`

따라서 아래 주간 지표를 계산할 수 있다.

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

### 4.2 Position snapshot에서 계산 가능한 지표

`paper_position_snapshot.csv`에는 아래 필드가 있어 symbol-level 변화 추적이 가능하다.

- `snapshot_date`
- `symbol`
- `shares`
- `market_value`
- `unrealized_pnl`
- `position_status`
- `price_staleness_days`

따라서 아래 주간 지표를 계산할 수 있다.

- `start_symbols`
- `end_symbols`
- `added_symbols`
- `removed_symbols`
- `held_symbols`
- `top_positions_by_market_value`
- `top_unrealized_gain`
- `top_unrealized_loss`
- `positions_with_missing_valuation`

### 4.3 Execution log에서 계산 가능한 지표

`paper_execution_log.csv`에는 아래 필드가 있다.

- `trade_id`
- `date`
- `symbol`
- `side`
- `shares`
- `price`
- `status`
- `reason`
- `created_at`

따라서 아래 주간 지표를 계산할 수 있다.

- `trade_count`
- `buy_count`
- `sell_count`
- `rows_appended_count`
- trade date별 row count
- `no_trade_days`

다만 현재 구조만으로는 아래 항목은 직접 보장되지 않는다.

- `duplicates_skipped_count`
- 정확한 `realized_pnl_this_week`

이 값들은 commit sidecar가 있으면 보강 가능하지만, execution log 단독으로는 제한적이다.

## 5. 주간 기준 날짜 설계

### 5.1 권장 기준 날짜

권장 primary 기준 날짜는 `snapshot_date`다.

이유:

1. `paper_account_snapshot.csv`와 `paper_position_snapshot.csv`가 모두 `snapshot_date`를 공통 anchor로 가진다.
2. 주간 상태 요약의 핵심 질문인 equity, cash ratio, unrealized PnL, position count 변화는 snapshot 기반으로 가장 안정적으로 계산된다.
3. `trade date`는 no-trade day를 설명하지 못한다.
4. `daily_action_plan_YYYYMMDD.md`와 `paper_current_state_YYYYMMDD.json`는 존재 여부 확인에는 좋지만, 주간 변화 계산의 canonical anchor로는 부족하다.

### 5.2 보조 날짜 기준

보조 날짜 기준은 아래처럼 사용한다.

- `daily_action_plan_YYYYMMDD.md`
  - plan 존재 여부 확인
- `paper_current_state_YYYYMMDD.json`
  - commit 이후 current state 존재 여부 확인
- `paper_execution_log.csv.date`
  - trade 존재 여부와 trade count 계산
- `review_date`
  - manual review pending / reviewed row 집계

### 5.3 결론

주간 rollup의 day row는 `snapshot_date`를 기준으로 만들고, 나머지 입력은 해당 날짜에 대해 join 또는 existence check하는 방식이 가장 안전하다.

## 6. 주간 범위 설계

### 6.1 권장 기본값

권장 기본값은 `최근 5영업일`이 아니라 `최근 5개 snapshot_date`다.

이유:

- 실제 운영 파일은 영업일 기준으로 빠질 수 있고, calendar 7일 기준은 주말/공휴일 때문에 노이즈가 커진다.
- snapshot이 생성된 날짜 기준으로 묶는 것이 현재 파일 구조와 가장 잘 맞는다.

### 6.2 권장 CLI 범위 옵션

권장 옵션:

- `python scripts/paper.py weekly-status`
- `python scripts/paper.py weekly-status --days 5`
- `python scripts/paper.py weekly-status --start YYYYMMDD --end YYYYMMDD`

권장 해석:

- `--days 5`
  - 최신 5개 `snapshot_date`
- `--start / --end`
  - 포함 범위의 snapshot_date 필터

`--week-start YYYYMMDD` 단독보다는 `--start / --end`가 더 일반적이고 운영자가 예외 주간 범위를 지정하기 쉽다.

## 7. daily_action_plan 파일로 운영 완료 여부를 추정할 수 있는가

부분적으로만 가능하다.

가능한 것:

- 해당 날짜에 plan 생성이 있었는지

불가능하거나 부족한 것:

- commit 완료 여부
- snapshot 생성 여부
- review 준비 완료 여부

따라서 `daily_action_plan_exists`는 coverage row의 한 칸으로 넣을 수는 있지만, 단독으로 `정상 운영`을 선언하는 기준으로 쓰면 안 된다.

## 8. paper.py status와 weekly rollup 연결 방식

현재 `paper.py status`는 single-date workflow status를 아래처럼 요약한다.

- `NO_PLAN`
- `PLAN_READY`
- `COMMITTED`
- `REVIEW_READY`
- `UNKNOWN_OR_INCOMPLETE`

weekly rollup은 각 포함 날짜별로 이 workflow status를 재사용하거나 동일 로직을 내장해 아래 필드를 채우는 구조가 적절하다.

- `workflow_status`
- `missing_steps`
- `next_recommended_command`

권장안:

- weekly rollup은 내부적으로 `paper_status`의 판단 로직을 reuse한다.
- 주간 summary header에는 날짜별 status를 압축한 `workflow_status_summary`를 추가한다.

예:

- `REVIEW_READY: 2`
- `COMMITTED: 1`
- `PLAN_READY: 1`
- `UNKNOWN_OR_INCOMPLETE: 1`

## 9. Review 데이터 반영 가능성

### 9.1 포함 가능 항목

review 관련으로 아래 항목은 포함 가능하다.

- `review_bucket_counts`
- `high_priority_review_items`
- `repeated_review_symbols`
- `manual_review_rows`
- `pending_review_rows`
- `reviewed_rows`
- `validation_status`

### 9.2 주의점

현재 review 데이터는 두 층으로 분리된다.

- `paper_manual_review_log_template.csv`
  - pending template row
- `paper_manual_review_log.csv`
  - 실제 append된 reviewed row

따라서 weekly rollup은 아래처럼 보는 것이 적절하다.

- pending review row
  - template 기준
- reviewed row
  - committed manual review log 기준

### 9.3 review가 비어 있을 때 처리 방식

권장안:

- reviewed row가 0이어도 자동 FAIL로 보지 않는다.
- trade가 없고 status가 `NO_ACTIVITY` 또는 review 미필요에 가까운 날짜는 `manual_review_rows = 0`이 정상일 수 있다.
- 단, trade가 있었거나 `REVIEW_READY`까지 갔는데 template/review log가 모두 비어 있으면 warning 또는 gap 후보로 본다.

## 10. overwrite-style report를 weekly rollup에서 다루는 방법

아래 파일은 overwrite 구조다.

- `paper_daily_review_summary.md`
- `paper_performance_summary.md`
- `paper_symbol_review_buckets.csv`
- `paper_symbol_review_worksheet.csv`

권장 처리:

- 이 파일들은 `latest snapshot`에 대한 auxiliary source로만 사용한다.
- 주간 historical coverage의 canonical source로 사용하지 않는다.
- 주간 요약에서 필요할 경우 “latest-only 참고값” 또는 “current reference”로만 포함한다.

즉, 주간 rollup의 핵심 이력 계산은 snapshot / execution log / review log 위주로 구성해야 한다.

## 11. Operation gap 정의 초안

### 11.1 Gap의 기본 의미

operation gap은 “해당 날짜가 정상적인 daily loop를 모두 밟지 못했거나, source / report / review가 불완전해서 후속 확인이 필요한 상태”를 뜻한다.

### 11.2 권장 severity 기준

#### HIGH

- snapshot 일부만 있고 (`account`만 있거나 `position`만 있는 등) commit 완료 상태가 깨진 경우
- `workflow_status = UNKNOWN_OR_INCOMPLETE`
- review validation 실패
- current state, account snapshot, position snapshot이 서로 모순되거나 핵심 source가 누락된 경우

#### MEDIUM

- snapshot은 있는데 plan이 없는 경우
- `COMMITTED` 상태인데 review template 또는 validation report가 없는 경우
- expected auxiliary report가 stale 또는 missing인 경우
- manual review가 필요해 보이는 날짜인데 pending/reviewed 흔적이 없는 경우

#### LOW

- no-trade day이지만 snapshot과 상태 파일은 완전한 경우
- review row가 아직 없지만 trade/상태상 필수 review로 단정하기 어려운 경우
- latest-only auxiliary report 부재

### 11.3 no-trade day 판단 기준

권장안:

- `execution_log_rows = 0`이라도 아래가 모두 있으면 정상 no-trade day로 본다.
  - `daily_action_plan_exists`
  - `current_state_exists`
  - `account_snapshot_exists`
  - `position_snapshot_exists`
- 이 경우 severity는 `LOW` 또는 `NONE`에 가깝게 처리한다.

## 12. 주간 summary report 포함 항목 설계

### 12.1 Header

- `week_start`
- `week_end`
- `generated_at`
- `latest_snapshot_date`
- `workflow_status_summary`

### 12.2 Operation Coverage

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

### 12.3 Account Summary

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

### 12.4 Position Summary

- `start_symbols`
- `end_symbols`
- `added_symbols`
- `removed_symbols`
- `held_symbols`
- `top_positions_by_market_value`
- `top_unrealized_gain`
- `top_unrealized_loss`
- `positions_with_missing_valuation`

### 12.5 Trade Summary

- `trade_count`
- `buy_count`
- `sell_count`
- `rows_appended_count`
- `duplicates_skipped_count` if available
- `realized_pnl_this_week` if available
- `no_trade_days`

### 12.6 Review / Warning Summary

- `review_bucket_counts`
- `high_priority_review_items`
- `repeated_review_symbols`
- `manual_review_rows`
- `pending_review_rows`
- `reviewed_rows`
- `validation_status`

### 12.7 Data / Operation Issues

- `missing_daily_action_plan_dates`
- `missing_commit_snapshot_dates`
- `snapshot_without_plan_dates`
- `report_stale_or_missing`
- `review_template_missing`
- `validation_failed`
- `unknown_or_incomplete_dates`

### 12.8 Recommended Next Actions

- `next_week_prepare_needed`
- `symbols_to_review`
- `data_quality_items`
- `operation_gap_items`
- `manual_review_append_needed`

## 13. 추천 CLI와 산출물

### 13.1 추천 CLI

- `python scripts/paper.py weekly-status`
- `python scripts/paper.py weekly-status --days 5`
- `python scripts/paper.py weekly-status --start YYYYMMDD --end YYYYMMDD`

### 13.2 추천 산출물

Primary:

- `outputs/paper_test/reports/paper_weekly_status_summary.md`
- `outputs/paper_test/reports/paper_weekly_status_summary.json`

Secondary:

- `outputs/paper_test/reports/paper_weekly_status_summary.csv`

권장안:

- `md + json`을 1차 산출물로 둔다.
- 이유:
  - human-readable summary는 markdown이 적합
  - nested fields와 list-type 항목은 json이 적합
  - csv는 flatten 과정에서 정보 손실이 생길 수 있으므로 optional로 둔다

## 14. 구현 시 주의점

1. `snapshot_date`를 primary anchor로 고정해야 한다.
2. overwrite-style report를 historical source로 오인하지 않아야 한다.
3. no-trade day를 자동 gap으로 보지 않아야 한다.
4. review template와 reviewed log의 역할을 분리해 집계해야 한다.
5. `paper.py status`와 weekly coverage 판단이 충돌하지 않도록 같은 규칙을 reuse해야 한다.
6. `duplicates_skipped_count`, `realized_pnl_this_week`는 현 구조상 optional field로 취급하는 편이 안전하다.

## 15. 권장 구현 범위와 제외 범위

### 15.1 PAPER12-2 구현 범위 권장안

- read-only weekly aggregator 추가
- `paper.py weekly-status` command 추가
- `md + json` writer 추가
- `paper_status` 로직 재사용
- no-trade day / missing-step / review gap rule 반영

### 15.2 이번 단계 제외 범위

- writer 구현
- side-effect 있는 명령 실행
- 과거 overwrite report를 복원하는 작업
- manual review workflow 자체 변경

## 16. 결론

권장 설계는 아래와 같다.

- 기준 날짜: `snapshot_date`
- 기본 범위: 최신 5개 `snapshot_date`
- 주요 source: `account snapshot`, `position snapshot`, `execution log`
- 보조 source: `daily_action_plan`, `current_state`, `status`, `review template/log`
- 산출물: `markdown + json` 우선
- gap 판단: `HIGH / MEDIUM / LOW`
- no-trade day: snapshot과 상태가 완전하면 정상으로 허용

이 설계는 현재 paper daily loop와 `paper.py status` 체계를 크게 흔들지 않으면서, 주간 운영 점검에 필요한 coverage / 변화 / 누락 / 다음 액션을 한 번에 보여주는 방향이다.

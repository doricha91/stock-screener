# MFU-PAPER12-1 작업 지시문: weekly/status rollup 조사 및 설계

## 목적

PAPER12-1의 목표는 paper 운영 결과를 주간 단위로 요약하기 위한 입력 데이터, 누락 판단 기준, 리포트 구조, 구현 범위를 조사하고 설계하는 것이다.

이번 단계는 조사/설계 전용이다.  
코드 수정, DB write, paper 원장 수정, report 생성 구현은 하지 않는다.

반드시 명시:

```text
이번 PAPER12-1은 weekly/status rollup 조사 및 설계이며, 코드 구현, DB write, paper 원장 수정은 포함하지 않는다.
```

## 배경

PAPER11에서 일일 paper 운영 루프가 1차 완성됐다.

운영용 shortcut:

```text
paper.py prepare --date YYYYMMDD
paper.py preview --date YYYYMMDD
paper.py commit --date YYYYMMDD
paper.py review
paper.py status [--date YYYYMMDD]
```

PAPER12에서는 일별 운영 결과를 주간 단위로 모아 아래 질문에 답할 수 있어야 한다.

```text
이번 주에 어떤 날짜가 정상 운영됐는가?
누락된 단계는 무엇인가?
계좌 equity, cash ratio, unrealized PnL은 어떻게 변했는가?
거래/보유/리뷰 대상은 어떻게 변했는가?
다음 주에 확인할 warning이나 action item은 무엇인가?
```

## 조사 대상 파일

아래 파일들의 구조와 날짜 기준을 확인한다.

```text
outputs/paper_test/paper_account_snapshot.csv
outputs/paper_test/paper_position_snapshot.csv
outputs/paper_test/paper_execution_log.csv
outputs/paper_test/daily_action_plan_*.md
outputs/paper_test/paper_current_state_*.json
outputs/paper_test/reports/paper_daily_review_summary.md
outputs/paper_test/reports/paper_performance_summary.md
outputs/paper_test/reports/paper_equity_curve.csv
outputs/paper_test/reports/paper_drawdown.csv
outputs/paper_test/reports/paper_symbol_review_buckets.csv
outputs/paper_test/reports/paper_symbol_review_worksheet.csv
outputs/paper_test/reviews/paper_manual_review_log_template.csv
outputs/paper_test/reviews/paper_manual_review_log_validation_report.md
outputs/paper_test/reviews/paper_manual_review_log.csv
```

## 핵심 조사 질문

아래 질문에 답한다.

1. weekly rollup의 기준 날짜는 무엇으로 잡을 것인가?
   - snapshot_date
   - trade date
   - daily_action_plan 파일 날짜
   - calendar week

2. 주간 범위는 어떻게 지정할 것인가?
   - 최근 5영업일
   - 최근 7일
   - --week-start YYYYMMDD
   - --start / --end

3. account snapshot에서 계산 가능한 지표는 무엇인가?
   - equity 변화
   - cash 변화
   - cash ratio 변화
   - unrealized PnL 변화
   - position count 변화

4. position snapshot에서 계산 가능한 지표는 무엇인가?
   - 보유 종목 변화
   - 신규 등장/사라진 종목
   - 종목별 평가액 변화
   - 종목별 미실현손익 변화

5. execution log에서 계산 가능한 지표는 무엇인가?
   - trade count
   - buy/sell count
   - realized trade 여부
   - 주간 신규 거래 없음도 정상으로 볼 수 있는지

6. daily_action_plan 파일로 운영 완료 여부를 추정할 수 있는가?

7. paper.py status의 workflow_status와 weekly rollup을 어떻게 연결할 것인가?

8. review template / manual review log를 weekly rollup에 포함할 수 있는가?
   - 아직 수동 입력이 없을 수 있음
   - pending row는 어떻게 볼 것인가

9. reports가 덮어쓰기 구조인 점을 weekly rollup에서 어떻게 다룰 것인가?

10. operation gap을 어떻게 정의할 것인가?

## 주간 리포트에 포함할 내용

PAPER12-1 설계 문서에는 weekly summary report에 포함할 항목을 아래 기준으로 정리한다.

### 1. Header

```text
week_start
week_end
generated_at
latest_snapshot_date
workflow_status_summary
```

### 2. Operation Coverage

```text
date
daily_action_plan_exists
current_state_exists
account_snapshot_exists
position_snapshot_exists
execution_log_rows
reports_exists
review_template_exists
review_validation_status
workflow_status
missing_steps
next_recommended_command
```

### 3. Account Summary

```text
start_equity_market_value
end_equity_market_value
equity_change
equity_change_pct
start_cash
end_cash
cash_change
start_cash_ratio
end_cash_ratio
cash_ratio_change
start_unrealized_pnl
end_unrealized_pnl
unrealized_pnl_change
position_count_start
position_count_end
```

### 4. Position Summary

```text
start_symbols
end_symbols
added_symbols
removed_symbols
held_symbols
top_positions_by_market_value
top_unrealized_gain
top_unrealized_loss
positions_with_missing_valuation
```

### 5. Trade Summary

```text
trade_count
buy_count
sell_count
rows_appended_count
duplicates_skipped_count, if available
realized_pnl_this_week, if available
no_trade_days
```

### 6. Review / Warning Summary

```text
review_bucket_counts
high_priority_review_items
repeated_review_symbols
manual_review_rows
pending_review_rows
reviewed_rows
validation_status
```

### 7. Data / Operation Issues

```text
missing_daily_action_plan_dates
missing_commit_snapshot_dates
snapshot_without_plan_dates
report_stale_or_missing
review_template_missing
validation_failed
unknown_or_incomplete_dates
```

### 8. Recommended Next Actions

```text
next_week_prepare_needed
symbols_to_review
data_quality_items
operation_gap_items
manual_review_append_needed
```

## 설계 판단 항목

아래 항목은 설계 문서에서 권장안을 제시한다.

```text
1. 주간 범위 기본값
2. 리포트 파일명
3. CSV/MD/JSON 중 어떤 산출물을 만들지
4. paper.py command 이름
5. operation gap severity 기준
6. no-trade day를 정상으로 볼 기준
7. review 정보가 비어 있을 때 처리 방식
```

권장 후보:

```text
python scripts/paper.py weekly-status
python scripts/paper.py weekly-status --days 5
python scripts/paper.py weekly-status --start YYYYMMDD --end YYYYMMDD
```

출력 후보:

```text
outputs/paper_test/reports/paper_weekly_status_summary.md
outputs/paper_test/reports/paper_weekly_status_summary.csv
outputs/paper_test/reports/paper_weekly_status_summary.json
```

## 산출물

조사/설계 문서 작성:

```text
docs/TRD/mfu_paper12_1_weekly_status_rollup_design.md
```

필요하면 보조 문서:

```text
docs/operations/paper_weekly_review_concept.md
```

## 금지 사항

```text
코드 수정 금지
DB write 금지
paper 원장 CSV 수정 금지
reports 생성 구현 금지
paper.py 수정 금지
prepare/preview/commit/review 실행 금지
review-append 실행 금지
outputs/front_test 수정 금지
```

## 허용 사항

```text
파일 읽기
CSV 구조 확인
날짜 컬럼 확인
row count 확인
기존 status/report 산출물 구조 조사
문서 작성
```

## 검증

문서 작업이므로 테스트는 필수 아님.

허용:

```text
python scripts/paper.py status --date 20260520
Get-Content / head / type으로 문서와 CSV header 확인
```

writer 명령은 실행하지 않는다.

## 성공 기준

```text
weekly/status rollup 입력 파일이 정리된다.
각 입력 파일의 날짜 기준과 사용 가능 지표가 정리된다.
weekly summary report에 포함할 항목이 정의된다.
operation gap 판단 기준 초안이 작성된다.
paper.py weekly-status 명령 후보가 설계된다.
구현 범위와 제외 범위가 명확히 정리된다.
코드와 원장 파일은 수정하지 않는다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 조사한 파일
3. weekly rollup 입력 데이터
4. 날짜 기준
5. 주간 요약 리포트 포함 항목
6. operation gap 판단 기준
7. review 데이터 반영 가능성
8. 추천 CLI
9. 추천 산출물
10. 구현 시 주의점
11. 코드 변경 여부
12. paper 원장 CSV 변경 여부
13. outputs/front_test 변경 여부
14. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER12-1은 weekly/status rollup 조사 및 설계이며, 코드 구현과 writer 명령 실행은 포함하지 않는다.
```
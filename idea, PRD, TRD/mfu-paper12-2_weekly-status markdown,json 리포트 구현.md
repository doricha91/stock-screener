# MFU-PAPER12-2 작업 지시문: weekly-status Markdown/JSON 리포트 구현

## 목적

PAPER12-2의 목표는 paper 운영 결과를 주간 단위로 요약하는 `weekly-status` 리포트를 구현하는 것이다.

이번 단계에서는 산출물을 Markdown과 JSON으로만 생성한다.

```text
outputs/paper_test/reports/paper_weekly_status_summary.md
outputs/paper_test/reports/paper_weekly_status_summary.json
```

반드시 명시:

```text
이번 PAPER12-2는 weekly-status Markdown/JSON 리포트 구현이며, Notion 연동, HTML 대시보드, CSV 산출물, DB write, paper 원장 수정은 포함하지 않는다.
```

## 배경

PAPER12-1 조사 결과:

- 주간 rollup의 기준축은 `paper_account_snapshot.csv`의 `snapshot_date`가 가장 안전하다.
- `paper_execution_log.csv`는 거래 없는 날 0 row가 정상일 수 있으므로 운영 완료 기준으로 부적합하다.
- reports 계열 파일은 latest overwrite 구조라 historical source가 아니라 보조 source로만 사용한다.
- no-trade day는 account/position snapshot이 정상이면 정상 후보로 본다.

## 구현 파일

권장 추가:

```text
core/paper_weekly_status.py
scripts/generate_paper_weekly_status.py
tests/test_paper_weekly_status.py
```

수정:

```text
scripts/paper.py
tests/test_paper_cli.py
docs/TRD/mfu_paper12_2_weekly_status_report.md
```

## CLI 요구사항

추가 명령:

```text
python scripts/paper.py weekly-status
python scripts/paper.py weekly-status --days 5
python scripts/paper.py weekly-status --start YYYYMMDD --end YYYYMMDD
python scripts/paper.py weekly-status --json
```

standalone script도 추가한다.

```text
python scripts/generate_paper_weekly_status.py
python scripts/generate_paper_weekly_status.py --days 5
python scripts/generate_paper_weekly_status.py --start YYYYMMDD --end YYYYMMDD
```

## 기간 정책

기본값:

```text
최근 5개 snapshot_date 기준
```

옵션:

```text
--days N
```

은 최근 N개 snapshot row를 기준으로 한다.

```text
--start YYYYMMDD --end YYYYMMDD
```

가 있으면 해당 날짜 범위의 `snapshot_date`를 기준으로 필터링한다.

주의:

```text
calendar day가 아니라 snapshot_date 기준이다.
execution log date를 기준축으로 삼지 않는다.
```

## 입력 파일

주 입력:

```text
outputs/paper_test/paper_account_snapshot.csv
outputs/paper_test/paper_position_snapshot.csv
```

보조 입력:

```text
outputs/paper_test/paper_execution_log.csv
outputs/paper_test/daily_action_plan_*.md
outputs/paper_test/paper_current_state_*.json
outputs/paper_test/reports/paper_symbol_review_buckets.csv
outputs/paper_test/reports/paper_symbol_review_worksheet.csv
outputs/paper_test/reviews/paper_manual_review_log.csv
outputs/paper_test/reviews/paper_manual_review_log_validation_report.md
```

보조 입력은 없을 수 있으므로, 없으면 warning 또는 empty로 처리한다.

## 리포트 포함 항목

### 1. Header

Markdown과 JSON에 포함:

```text
period_start
period_end
generated_at
snapshot_count
latest_snapshot_date
overall_status
```

### 2. Operation Coverage

날짜별 운영 상태 표를 만든다.

포함 필드:

```text
date
daily_action_plan_exists
current_state_exists
account_snapshot_exists
position_snapshot_exists
execution_log_rows
workflow_status
missing_steps
operation_gap_severity
next_recommended_command
```

판정 기준:

```text
account_snapshot + position_snapshot + current_state 있음 -> COMMITTED 후보
reports/review까지 있으면 REVIEW_READY 후보
plan 없음 -> NO_PLAN
일부만 있으면 UNKNOWN_OR_INCOMPLETE
```

### 3. Account Summary

주간 시작/종료 기준으로 계산한다.

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

주의:

```text
market value 컬럼이 없으면 cost basis 컬럼으로 fallback하되, JSON에 valuation_basis를 명시한다.
```

### 4. Position Summary

position snapshot 기준.

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

초기 구현에서 종목별 평가액/손익 컬럼명이 불명확하면 가능한 범위만 구현하고, unavailable 필드로 명시한다.

### 5. Trade Summary

execution log 기준.

```text
trade_count
buy_count
sell_count
no_trade_days
trade_dates
```

정책:

```text
trade_count = 0은 자동 error가 아니다.
snapshot이 정상인 no-trade day는 정상으로 본다.
```

### 6. Review / Warning Summary

가능한 경우만 집계한다.

```text
review_bucket_counts
high_priority_symbols
manual_review_rows
pending_review_rows
reviewed_rows
validation_status
```

없으면:

```text
review_data_available: false
```

로 기록한다.

### 7. Operation Gaps

gap list를 만든다.

severity:

```text
HIGH
MEDIUM
LOW
```

기준:

```text
HIGH:
- account_snapshot은 있는데 position_snapshot 없음
- current_state는 있는데 snapshot 일부 없음
- workflow_status = UNKNOWN_OR_INCOMPLETE
- review_validation_failed

MEDIUM:
- committed 이후 reports 없음
- committed 이후 review template 없음
- high priority review item 있는데 manual review 흔적 없음

LOW:
- execution_log_rows = 0
- optional review/manual log 없음
```

### 8. Recommended Next Actions

리포트 마지막에 다음 행동을 정리한다.

```text
operation_gap_items
symbols_to_review
manual_review_append_needed
next_recommended_command
```

## JSON 구조

권장 top-level schema:

```json
{
  "generated_at": "...",
  "period": {
    "start": "YYYY-MM-DD",
    "end": "YYYY-MM-DD",
    "snapshot_count": 0
  },
  "overall_status": "PASS|PASS_WITH_WARNINGS|FAIL",
  "operation_coverage": [],
  "account_summary": {},
  "position_summary": {},
  "trade_summary": {},
  "review_summary": {},
  "operation_gaps": [],
  "recommended_next_actions": []
}
```

## Markdown 구성

`paper_weekly_status_summary.md` 목차:

```text
# Paper Weekly Status Summary

## 1. Period
## 2. Overall Status
## 3. Operation Coverage
## 4. Account Summary
## 5. Position Summary
## 6. Trade Summary
## 7. Review / Warning Summary
## 8. Operation Gaps
## 9. Recommended Next Actions
## 10. Limitations
```

Limitations에 명시:

```text
- This report is generated from paper snapshots and local artifacts.
- Latest overwrite reports are used only as auxiliary sources.
- No-trade days are not treated as errors when snapshots are complete.
- This report does not validate investment correctness.
```

## paper.py 연결

`scripts/paper.py`에 추가:

```text
weekly-status
```

동작:

```text
1. weekly status generator 실행
2. Markdown/JSON 생성
3. 콘솔에 핵심 요약 출력
```

`--json` 옵션은 파일 생성 JSON을 stdout에도 출력한다.

## 절대 금지

```text
Notion 연동 금지
HTML 대시보드 구현 금지
CSV 산출물 생성 금지
DB write 금지
paper_execution_log.csv 수정 금지
paper_account_snapshot.csv 수정 금지
paper_position_snapshot.csv 수정 금지
prepare/preview/commit/review 실행 금지
reports 재생성 금지
review-append 실행 금지
outputs/front_test 수정 금지
```

## 테스트

테스트 파일:

```text
tests/test_paper_weekly_status.py
tests/test_paper_cli.py
```

필수 테스트:

```text
1. account snapshot 기준으로 최근 5개 snapshot 선택
2. --days N이 N개 snapshot을 선택
3. --start/--end가 날짜 범위를 올바르게 필터링
4. no-trade day를 error로 보지 않음
5. account snapshot 있는데 position snapshot 없으면 HIGH gap
6. plan 없으면 coverage에 missing step 표시
7. equity_change / equity_change_pct 계산
8. cash_ratio_change 계산
9. added_symbols / removed_symbols 계산
10. Markdown 파일 생성
11. JSON 파일 생성
12. paper.py weekly-status가 generator를 호출
13. writer 명령을 호출하지 않음
14. outputs/front_test를 수정하지 않음
```

테스트는 임시 디렉터리와 임시 CSV를 사용한다. 실제 paper 원장 파일은 수정하지 않는다.

## 검증 명령

```text
set PYTHONPATH=.

python -m pytest tests/test_paper_weekly_status.py tests/test_paper_cli.py -q
python -m py_compile core/paper_weekly_status.py
python -m py_compile scripts/generate_paper_weekly_status.py
python -m py_compile scripts/paper.py

python scripts/paper.py --help
python scripts/paper.py weekly-status
python scripts/paper.py weekly-status --days 5
```

주의:

```text
weekly-status는 reports 폴더에 Markdown/JSON 파일을 생성한다.
paper 원장 CSV는 수정하지 않는다.
```

## 성공 기준

```text
weekly-status 명령이 추가된다.
snapshot_date 기준 주간 rollup이 생성된다.
Markdown과 JSON 산출물이 생성된다.
operation coverage, account summary, position summary, trade summary, operation gaps가 포함된다.
no-trade day를 정상 가능 상태로 처리한다.
latest overwrite reports를 historical source로 사용하지 않는다.
paper 원장 CSV와 outputs/front_test를 수정하지 않는다.
테스트가 통과한다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 변경 파일
3. 추가된 CLI
4. 기간 선택 정책
5. 입력 파일
6. 생성 산출물
7. Markdown 구성
8. JSON 구조
9. 포함된 주간 요약 항목
10. operation gap 정책
11. 테스트 결과
12. 실제 weekly-status 실행 결과
13. paper 원장 CSV 변경 여부
14. outputs/front_test 변경 여부
15. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER12-2는 weekly-status Markdown/JSON 리포트 구현이며, Notion/HTML/CSV 연동과 paper 원장 수정은 포함하지 않는다.
```
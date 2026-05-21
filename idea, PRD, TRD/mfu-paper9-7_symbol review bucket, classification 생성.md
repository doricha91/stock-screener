# MFU-PAPER9-7 작업 지시문: symbol review bucket/classification 생성

## 기준

브랜치: gemini_cli_update  
기준 SHA: c6ed2bce27a8f08afc64c882d8c7abe05849c303

## 목적

PAPER9-7의 목표는 `paper_symbol_side_by_side_performance.csv`를 기반으로 종목별 **review bucket**을 생성하는 것이다.

이번 단계는 매수/매도 제안이 아니다.  
목적은 종목별 성과를 빠르게 복기·점검할 수 있도록 분류하는 것이다.

반드시 명시:

```text
is_actionable = false
```

## 입력

```text
outputs/paper_test/reports/paper_symbol_side_by_side_performance.csv
```

## 산출물

```text
outputs/paper_test/reports/paper_symbol_review_buckets.csv
outputs/paper_test/reports/paper_symbol_review_buckets_summary.md
```

## 구현 파일

권장 추가 파일:

```text
core/paper_symbol_review_buckets.py
scripts/generate_paper_symbol_review_buckets.py
tests/test_paper_symbol_review_buckets.py
docs/TRD/mfu_paper9_7_symbol_review_buckets.md
```

## 핵심 원칙

### 1. 손익 재계산 금지

이번 단계에서는 realized/unrealized PnL을 새로 계산하지 않는다.

- 입력 CSV의 realized_pnl 사용
- 입력 CSV의 unrealized_pnl 사용
- 입력 CSV의 total_pnl 사용

`paper_execution_log.csv` replay 금지.  
`paper_position_snapshot.csv` 재집계 금지.

### 2. bucket은 단순하게 유지한다

사용할 bucket:

```text
review_loss
track_realized_gain
monitor_open_gain
monitor_open_loss
neutral
```

`insufficient_data`는 bucket으로 만들지 않는다.  
대신 별도 컬럼 `sample_size_flag`로 남긴다.

### 3. neutral 기준

neutral 기준은 **0.5%**로 한다.

권장 기준:

```text
neutral_threshold_pct = 0.5
```

적용 기준:
- open position이 있으면 `open_unrealized_return_pct` 기준
- realized-only 종목이면 `avg_realized_return_pct` 또는 realized return 관련 컬럼 기준
- 둘 다 판단이 애매하면 total PnL의 절대값이 아니라 수익률 기준 우선

주의:
입력 CSV에 수익률 컬럼이 없거나 비어 있으면 PnL 부호 기준으로 fallback하되, summary에 warning을 남긴다.

## bucket 판정 규칙

우선순위는 open position을 먼저 본다.

```text
if open_market_value > 0 and open_unrealized_return_pct > 0.5:
    review_bucket = monitor_open_gain

elif open_market_value > 0 and open_unrealized_return_pct < -0.5:
    review_bucket = monitor_open_loss

elif open_market_value > 0:
    review_bucket = neutral

elif realized_pnl > 0 and avg_realized_return_pct > 0.5:
    review_bucket = track_realized_gain

elif realized_pnl < 0 and avg_realized_return_pct < -0.5:
    review_bucket = review_loss

else:
    review_bucket = neutral
```

주의:
- `both` 종목은 open position 기준을 먼저 적용한다.
- realized 손익이 있어도 현재 open position이 크면 open monitoring을 우선한다.
- 이 규칙은 매매 판단이 아니라 리뷰 분류다.

## sample_size_flag

bucket에는 넣지 않지만 표본 정보는 남긴다.

값 후보:

```text
no_realized_trades
low_sample
enough_sample
```

기준:

```text
realized_trade_count == 0 -> no_realized_trades
realized_trade_count < 3 -> low_sample
realized_trade_count >= 3 -> enough_sample
```

## review_priority

값:

```text
high
medium
low
```

권장 규칙:

```text
review_loss -> high
monitor_open_loss -> high
monitor_open_gain -> medium
track_realized_gain -> medium
neutral -> low
```

단, `sample_size_flag = low_sample`이면 summary에 “표본 부족으로 해석 주의”를 남긴다.

## CSV 컬럼

최소 컬럼:

```text
symbol
symbol_status
review_bucket
review_priority
is_actionable
sample_size_flag
review_reason
realized_pnl
unrealized_pnl
total_pnl
realized_trade_count
win_rate
avg_realized_return_pct
open_shares
open_market_value
open_unrealized_return_pct
position_weight_market
neutral_threshold_pct
```

`is_actionable`은 모든 row에서 `false`.

## review_reason 예시

```text
review_loss: realized loss exceeds neutral threshold; review entry/exit quality
track_realized_gain: realized gain exceeds neutral threshold; review repeatable signal pattern
monitor_open_gain: open position has unrealized gain above neutral threshold
monitor_open_loss: open position has unrealized loss below neutral threshold
neutral: performance is within neutral threshold or lacks strong signal
```

## Summary markdown 포함 내용

```text
1. 생성 일시
2. 입력 파일 경로
3. 출력 CSV 경로
4. neutral_threshold_pct = 0.5
5. bucket별 symbol count
6. priority별 symbol count
7. high priority symbols
8. low_sample symbols
9. is_actionable = false 명시
10. limitations
```

Limitations에 반드시 포함:

```text
- This is a non-actionable review classification report.
- It does not recommend buy/sell/hold actions.
- Realized PnL is average-cost SELL-event based.
- Unrealized PnL is current open-position snapshot based.
- total_pnl is a reference metric only.
- FIFO/LIFO/lot ledger accounting is not implemented.
- open_date and holding_days are excluded.
```

## 절대 금지

```text
- paper_execution_log.csv 수정 금지
- paper_account_snapshot.csv 수정 금지
- paper_position_snapshot.csv 수정 금지
- 기존 report CSV 수정 금지
- outputs/front_test 수정 금지
- DB 수정 금지
- --commit 실행 금지
- realized/unrealized PnL 재계산 금지
- paper_execution_log replay 금지
- 매수/매도/보유 추천 문구 생성 금지
- actionable commentary 생성 금지
- FIFO / lot ledger 구현 금지
- open_date / holding_days 계산 금지
- 대규모 리팩토링 금지
```

## 테스트

테스트 파일:

```text
tests/test_paper_symbol_review_buckets.py
```

필수 테스트:

```text
1. monitor_open_gain 분류
2. monitor_open_loss 분류
3. review_loss 분류
4. track_realized_gain 분류
5. neutral 분류
6. neutral threshold 0.5% 적용
7. open position 우선순위 적용
8. sample_size_flag 계산
9. review_priority 계산
10. is_actionable이 항상 false
11. summary에 non-actionable 문구 포함
12. 필수 컬럼 누락 감지
13. 숫자 변환 불가 값 감지
```

## 검증 명령

```bat
set PYTHONPATH=.

python -m pytest tests/test_paper_symbol_review_buckets.py -q
python -m py_compile core/paper_symbol_review_buckets.py
python -m py_compile scripts/generate_paper_symbol_review_buckets.py
python scripts/generate_paper_symbol_review_buckets.py
```

## 성공 기준

- review bucket CSV가 생성된다.
- summary markdown이 생성된다.
- bucket은 5개로 제한된다.
- neutral 기준 0.5%가 적용된다.
- sample_size_flag는 bucket과 분리된다.
- 모든 row의 is_actionable은 false다.
- 기존 CSV와 outputs/front_test는 수정하지 않는다.
- 테스트가 통과한다.

## 결과 보고 형식

5천자 이내.

포함:
1. Summary
2. 변경 파일
3. 산출물 경로
4. bucket별 count
5. priority별 count
6. high priority symbols
7. neutral threshold 적용 방식
8. sample_size_flag 결과
9. 제외한 항목
10. 테스트 결과
11. 원본 CSV 변경 여부
12. outputs/front_test 변경 여부
13. 다음 단계 제안

반드시 명시:

```text
이번 PAPER9-7은 비행동성 review classification이며, 매수/매도/보유 제안은 포함하지 않는다.
```
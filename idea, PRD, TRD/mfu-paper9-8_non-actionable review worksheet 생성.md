# MFU-PAPER9-8 작업 지시문: non-actionable review worksheet 생성

## 기준

브랜치: gemini_cli_update  
기준 SHA: c6ed2bce27a8f08afc64c882d8c7abe05849c303

## 목적

PAPER9-8의 목표는 `paper_symbol_review_buckets.csv`를 기반으로 **비행동성 review worksheet**를 생성하는 것이다.

이번 단계는 매매 제안이 아니다.  
목적은 종목별 성과를 복기할 때 확인해야 할 질문과 체크리스트를 자동 생성하는 것이다.

반드시 유지:

```text
is_actionable = false
```

## 입력

```text
outputs/paper_test/reports/paper_symbol_review_buckets.csv
```

참고 가능:

```text
outputs/paper_test/reports/paper_symbol_side_by_side_performance.csv
outputs/paper_test/reports/paper_symbol_review_buckets_summary.md
```

## 산출물

```text
outputs/paper_test/reports/paper_symbol_review_worksheet.md
outputs/paper_test/reports/paper_symbol_review_worksheet.csv
```

Markdown은 필수, CSV는 권장이다.

## 구현 파일

권장 추가 파일:

```text
core/paper_symbol_review_worksheet.py
scripts/generate_paper_symbol_review_worksheet.py
tests/test_paper_symbol_review_worksheet.py
docs/TRD/mfu_paper9_8_symbol_review_worksheet.md
```

## 핵심 원칙

### 1. 손익 재계산 금지

이번 단계에서는 realized/unrealized/total PnL을 새로 계산하지 않는다.

입력 CSV의 값을 그대로 사용한다.

금지:
- paper_execution_log.csv replay
- paper_position_snapshot.csv 재집계
- realized/unrealized PnL 재계산
- total PnL 재계산

### 2. review-only 유지

이번 산출물은 복기용 worksheet다.

허용:
- review questions
- checklist
- bucket별 점검 항목
- priority별 정렬
- sample size warning

금지:
- 매수 추천
- 매도 추천
- 보유 추천
- 비중 조절 제안
- 자동 action plan 생성
- actionable commentary

### 3. bucket별 질문 템플릿 사용

입력 bucket:

```text
review_loss
track_realized_gain
monitor_open_gain
monitor_open_loss
neutral
```

각 bucket에 맞는 질문 템플릿을 적용한다.

## Markdown 구성

`paper_symbol_review_worksheet.md`에 아래 섹션을 포함한다.

### 1. Header

포함:

```text
생성 일시
입력 파일 경로
출력 파일 경로
is_actionable = false
neutral_threshold_pct
```

### 2. Summary

포함:

```text
전체 symbol count
bucket별 count
priority별 count
high priority symbols
low_sample symbols
```

### 3. Review Queue

priority 순서로 정렬한다.

정렬 기준:

```text
review_priority: high → medium → low
bucket 순서: review_loss → monitor_open_loss → monitor_open_gain → track_realized_gain → neutral
total_pnl 오름차순 또는 절대값 큰 순서
```

각 symbol에 표시:

```text
symbol
review_bucket
review_priority
sample_size_flag
symbol_status
realized_pnl
unrealized_pnl
total_pnl
realized_trade_count
open_market_value
is_actionable
```

### 4. Symbol Worksheets

각 symbol별 worksheet를 생성한다.

형식 예시:

```markdown
## CF

- Bucket: review_loss
- Priority: high
- Sample Size: low_sample
- Actionable: false
- Realized PnL: ...
- Unrealized PnL: ...
- Total PnL: ...

### Review Checklist

- [ ] 진입 신호가 전략 조건과 일치했는가?
- [ ] 청산 rule은 정상 작동했는가?
- [ ] 포지션 크기가 과하지 않았는가?
- [ ] market regime 변화가 있었는가?
- [ ] 표본 부족으로 과잉해석하고 있지 않은가?

### Notes

- 
```

## bucket별 질문 템플릿

### review_loss

```text
- 진입 신호가 원래 전략 조건과 일치했는가?
- 손실 발생 전 market regime 변화가 있었는가?
- 청산 rule 또는 stop rule은 정상 작동했는가?
- 포지션 크기가 과하지 않았는가?
- 같은 조건이 반복되면 피해야 하는가, 아니면 표본 부족인가?
```

### track_realized_gain

```text
- 수익 거래의 진입 조건은 재현 가능한가?
- exit rule이 너무 빠르거나 늦지 않았는가?
- 수익이 특정 시장 국면에 의존했는가?
- 같은 조건을 전략 규칙으로 강화할 근거가 있는가?
- 표본 수가 충분한가?
```

### monitor_open_gain

```text
- 현재 평가이익이 exit rule 또는 trailing stop과 어떤 관계인가?
- 이익이 특정 종목에 과도하게 집중되어 있지 않은가?
- 다음 EOD update에서 신호 변화가 있었는가?
- 보유 근거가 아직 유효한가?
- 평가이익을 확정 수익으로 오해하고 있지 않은가?
```

### monitor_open_loss

```text
- 현재 평가손실이 stop 기준에 가까운가?
- 손실이 market regime 변화와 관련 있는가?
- 포지션 크기가 과하지 않은가?
- 신규 매수 제한 또는 리스크 관리 조건에 걸리는가?
- 손실을 과소평가하고 있지 않은가?
```

### neutral

```text
- 손익이 중립 범위에 있는 이유가 무엇인가?
- 아직 판단할 만큼 이벤트가 충분한가?
- 다음 snapshot에서 gain/loss bucket으로 이동할 가능성이 있는가?
- 리뷰 우선순위를 낮게 둬도 되는가?
```

## CSV 컬럼

`paper_symbol_review_worksheet.csv` 권장 컬럼:

```text
symbol
review_bucket
review_priority
sample_size_flag
symbol_status
is_actionable
question_id
question_text
question_category
requires_manual_answer
```

`is_actionable`은 모든 row에서 `false`.

## Summary limitations

Markdown에 반드시 포함:

```text
- This worksheet is non-actionable.
- It does not recommend buy/sell/hold actions.
- It is designed for manual review and post-trade analysis.
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
- 손익 재계산 금지
- paper_execution_log replay 금지
- 매수/매도/보유 추천 문구 생성 금지
- action plan 생성 금지
- FIFO / lot ledger 구현 금지
- open_date / holding_days 계산 금지
- 대규모 리팩토링 금지
```

## 테스트

테스트 파일:

```text
tests/test_paper_symbol_review_worksheet.py
```

필수 테스트:

```text
1. review_loss 질문 생성
2. track_realized_gain 질문 생성
3. monitor_open_gain 질문 생성
4. monitor_open_loss 질문 생성
5. neutral 질문 생성
6. priority 순 정렬
7. is_actionable이 항상 false
8. sample_size_flag 표시
9. markdown에 checklist 포함
10. markdown에 non-actionable 문구 포함
11. CSV question row 생성
12. 필수 컬럼 누락 감지
13. 빈 입력 처리
```

## 검증 명령

```bat
set PYTHONPATH=.

python -m pytest tests/test_paper_symbol_review_worksheet.py -q
python -m py_compile core/paper_symbol_review_worksheet.py
python -m py_compile scripts/generate_paper_symbol_review_worksheet.py
python scripts/generate_paper_symbol_review_worksheet.py
```

## 성공 기준

- review worksheet markdown이 생성된다.
- review worksheet CSV가 생성된다.
- bucket별 질문 템플릿이 적용된다.
- 모든 row/section이 non-actionable임을 명시한다.
- 기존 CSV와 outputs/front_test는 수정하지 않는다.
- 테스트가 통과한다.

## 결과 보고 형식

5천자 이내.

포함:
1. Summary
2. 변경 파일
3. 산출물 경로
4. 생성된 worksheet symbol 수
5. bucket별 worksheet 수
6. high priority worksheet 목록
7. non-actionable 유지 여부
8. 제외한 항목
9. 테스트 결과
10. 원본 CSV 변경 여부
11. outputs/front_test 변경 여부
12. 다음 단계 제안

반드시 명시:

```text
이번 PAPER9-8은 비행동성 review worksheet 생성이며, 매수/매도/보유 제안은 포함하지 않는다.
```
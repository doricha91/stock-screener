# MFU-PAPER9-9 작업 지시문: paper daily review summary / report index 생성

## 기준

브랜치: gemini_cli_update  
기준 SHA: c6ed2bce27a8f08afc64c882d8c7abe05849c303

## 목적

PAPER9-9의 목표는 PAPER9 성과 분석 체계의 1차 완성을 위해, 여러 중간 리포트를 하나의 운영용 입구로 묶는 **daily review summary**를 생성하는 것이다.

이번 단계는 새 성과 계산이 아니다.  
이미 생성된 report CSV/markdown을 읽어, 운영자가 매일 또는 주간으로 확인할 핵심 요약 문서를 만든다.

## 입력

필수 입력:

```text
outputs/paper_test/reports/paper_performance_summary.md
outputs/paper_test/reports/paper_symbol_side_by_side_performance.csv
outputs/paper_test/reports/paper_symbol_review_buckets.csv
outputs/paper_test/reports/paper_symbol_review_worksheet.md
```

참고 가능:

```text
outputs/paper_test/reports/paper_realized_trade_journal_summary.md
outputs/paper_test/reports/paper_symbol_realized_performance.csv
outputs/paper_test/reports/paper_symbol_unrealized_performance.csv
outputs/paper_test/reports/paper_realized_ranking_report.md
outputs/paper_test/reports/paper_symbol_review_buckets_summary.md
```

## 산출물

```text
outputs/paper_test/reports/paper_daily_review_summary.md
outputs/paper_test/reports/paper_report_index.md
```

`paper_daily_review_summary.md`는 운영자가 보는 최종 요약 리포트다.  
`paper_report_index.md`는 중간 산출물 목록과 용도를 정리하는 색인이다.

## 구현 파일

권장 추가 파일:

```text
core/paper_daily_review_summary.py
scripts/generate_paper_daily_review_summary.py
tests/test_paper_daily_review_summary.py
docs/TRD/mfu_paper9_9_daily_review_summary.md
```

## 핵심 원칙

### 1. 재계산 금지

이번 단계에서는 성과를 새로 계산하지 않는다.

금지:
- paper_execution_log.csv replay
- paper_position_snapshot.csv 재집계
- realized/unrealized/total PnL 재계산
- bucket 재분류
- worksheet 질문 재생성 로직 중복 구현

허용:
- 기존 report CSV/markdown에서 값 읽기
- 핵심 값 요약
- report path/index 생성
- warning/limitation 통합 표시

### 2. 운영용 최종 입구 만들기

운영자가 매번 모든 리포트를 열지 않아도 되도록 아래를 한 문서에 모은다.

```text
계좌 요약
realized / unrealized / total PnL
top/worst symbols
review bucket 요약
high priority review symbols
worksheet 위치
중간 리포트 목록
주요 limitations
```

### 3. non-actionable 유지

이번 리포트도 매매 제안이 아니다.

반드시 명시:

```text
This report is non-actionable.
It does not recommend buy/sell/hold actions.
```

## daily review summary 구성

`paper_daily_review_summary.md`에 아래 섹션을 포함한다.

### 1. Header

```text
생성 일시
report 기준 경로
is_actionable = false
```

### 2. Account Summary

가능하면 `paper_performance_summary.md` 또는 관련 CSV에서 아래 값을 가져온다.

```text
latest snapshot date
primary equity
cash
cash ratio
position ratio
realized PnL
unrealized PnL
total PnL
```

값 파싱이 어렵거나 불안정하면 “source report link/path”만 표시하고 warning을 남긴다.

### 3. Symbol Side-by-Side Summary

`paper_symbol_side_by_side_performance.csv`에서 요약한다.

```text
symbol count
realized_only count
unrealized_only count
realized_and_unrealized count
total realized PnL
total unrealized PnL
total PnL reference
top total PnL symbols
worst total PnL symbols
```

주의:
`total_pnl`은 참고값이며 lot-matched accounting 결과가 아님을 명시한다.

### 4. Review Bucket Summary

`paper_symbol_review_buckets.csv`에서 요약한다.

```text
bucket별 count
priority별 count
high priority symbols
sample_size_flag 요약
```

### 5. Review Worksheet Pointers

`paper_symbol_review_worksheet.md`의 위치를 표시한다.

가능하면 high priority symbol 목록과 함께 다음 문구를 표시한다.

```text
Review worksheet contains manual review questions only.
No buy/sell/hold recommendation is included.
```

### 6. Report Index

핵심 리포트와 역할을 표로 정리한다.

예:

```text
paper_performance_summary.md = 계좌 단위 성과 요약
paper_symbol_side_by_side_performance.csv = 종목별 realized/unrealized 통합표
paper_symbol_review_buckets.csv = 비행동성 리뷰 분류
paper_symbol_review_worksheet.md = 수동 복기 질문지
```

### 7. Limitations

반드시 포함:

```text
- This is a paper-test review summary, not real investment performance.
- This report is non-actionable.
- It does not recommend buy/sell/hold actions.
- realized PnL is average-cost SELL-event based.
- unrealized PnL is current open-position snapshot based.
- total_pnl is a reference metric only.
- FIFO/LIFO/lot ledger accounting is not implemented.
- open_date and holding_days are excluded.
- Metrics are preliminary when trade count or snapshot history is small.
```

## paper_report_index.md 구성

아래 카테고리로 정리한다.

```text
1. Final / operator-facing reports
2. Core account reports
3. Trade-level reports
4. Symbol-level reports
5. Review / worksheet reports
6. Debug / intermediate reports
```

각 row에 포함:

```text
report_path
category
purpose
operator_should_read_daily: true/false
notes
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
- bucket 재분류 금지
- actionable commentary 생성 금지
- 매수/매도/보유 추천 금지
- FIFO / lot ledger 구현 금지
- open_date / holding_days 계산 금지
- 대규모 리팩토링 금지
```

## 테스트

테스트 파일:

```text
tests/test_paper_daily_review_summary.py
```

필수 테스트:

```text
1. daily review summary markdown 생성
2. report index markdown 생성
3. side-by-side summary 값 표시
4. review bucket count 표시
5. high priority symbols 표시
6. worksheet path 표시
7. non-actionable 문구 포함
8. limitations 포함
9. report index category 생성
10. 필수 입력 누락 시 warning 또는 명확한 error
11. 원본 report CSV를 수정하지 않음
```

## 검증 명령

```bat
set PYTHONPATH=.

python -m pytest tests/test_paper_daily_review_summary.py -q
python -m py_compile core/paper_daily_review_summary.py
python -m py_compile scripts/generate_paper_daily_review_summary.py
python scripts/generate_paper_daily_review_summary.py
```

## 성공 기준

- `paper_daily_review_summary.md`가 생성된다.
- `paper_report_index.md`가 생성된다.
- 운영자가 볼 최종 입구 리포트가 생긴다.
- 주요 중간 리포트의 용도가 정리된다.
- 성과 재계산 없이 기존 산출물만 요약한다.
- non-actionable 경계를 유지한다.
- 기존 CSV와 outputs/front_test는 수정하지 않는다.
- 테스트가 통과한다.

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 변경 파일
3. 산출물 경로
4. daily summary에 포함된 핵심 섹션
5. report index 구성
6. high priority symbols 표시 여부
7. non-actionable 유지 여부
8. 제외한 항목
9. 테스트 결과
10. 원본 CSV 변경 여부
11. outputs/front_test 변경 여부
12. PAPER9 1차 완성 여부 판단
13. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER9-9는 PAPER9 성과 분석 체계의 운영용 최종 입구 리포트이며, 매수/매도/보유 제안은 포함하지 않는다.
```
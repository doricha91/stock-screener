# MFU-PAPER9-4 작업 지시문: realized 성과 ranking/reporting 강화

## 기준

브랜치: gemini_cli_update  
기준 SHA: c6ed2bce27a8f08afc64c882d8c7abe05849c303

## 목적

PAPER9-4의 목표는 PAPER9-3에서 생성한 `paper_symbol_realized_performance.csv`를 기반으로, 사람이 빠르게 해석할 수 있는 **realized 성과 ranking/report**를 생성하는 것이다.

이번 단계는 새로운 손익 계산이 아니라 **기존 종목별 realized 성과를 정렬·요약·리포팅하는 단계**다.

## 입력

```text
outputs/paper_test/reports/paper_symbol_realized_performance.csv
```

참고 가능:

```text
outputs/paper_test/reports/paper_realized_trade_journal.csv
outputs/paper_test/reports/paper_symbol_realized_performance_summary.md
```

## 산출물

권장 생성 파일:

```text
outputs/paper_test/reports/paper_realized_ranking_report.md
outputs/paper_test/reports/paper_realized_ranking.csv
```

CSV는 선택이지만 권장한다.  
Markdown은 필수다.

## 구현 범위

추가 권장 파일:

```text
core/paper_realized_ranking_report.py
scripts/generate_paper_realized_ranking_report.py
tests/test_paper_realized_ranking_report.py
```

## 핵심 원칙

### 1. source of truth

이번 단계의 source of truth는 `paper_symbol_realized_performance.csv`다.

이번 MFU에서는 `paper_execution_log.csv`를 다시 replay하지 않는다.  
realized PnL 계산을 재구현하지 않는다.

### 2. realized 성과만 다룬다

포함:
- total_realized_pnl 기준 ranking
- loss contribution ranking
- win_rate 기준 ranking
- profit_factor 기준 ranking
- trade_count 기준 ranking
- best/worst symbol table
- small sample warning

제외:
- unrealized PnL
- open position
- total PnL
- benchmark
- Sharpe / CAGR / MDD
- FIFO / lot ledger
- open_date / holding_days

## Markdown report 구성

`paper_realized_ranking_report.md`에 아래 섹션을 포함한다.

### 1. Summary

포함:
- 생성 일시
- 입력 파일 경로
- symbol count
- total realized trade count
- total realized PnL
- overall win/loss/flat count
- overall win rate
- cost_basis_method
- entry_basis_type
- lot_linking_status

### 2. Top / Worst Realized PnL Symbols

기준:
- `total_realized_pnl` 내림차순: top
- `total_realized_pnl` 오름차순: worst

표 컬럼:

```text
rank
symbol
total_realized_pnl
realized_trade_count
win_rate
avg_realized_return_pct
profit_factor
```

### 3. Loss Contribution Ranking

손실 종목만 대상으로 한다.

계산:
```text
loss_contribution_pct = abs(symbol_total_realized_pnl) / total_abs_loss * 100
```

주의:
- 손실 종목이 없으면 "No realized loss symbols"로 표시한다.
- total_abs_loss가 0이면 계산하지 않는다.

### 4. Win Rate Ranking

기준:
- `win_rate` 내림차순
- 동률이면 `realized_trade_count` 내림차순
- 그 다음 `total_realized_pnl` 내림차순

주의:
- realized_trade_count가 너무 작으면 해석 주의 warning을 남긴다.

### 5. Profit Factor Ranking

기준:
- `profit_factor` 내림차순

주의:
- profit_factor가 N/A, blank, inf인 경우 별도 처리한다.
- 거래 수가 적은 symbol의 profit_factor는 과대해석하지 않도록 warning을 남긴다.

### 6. Limitations

반드시 포함:

```text
- This report summarizes realized SELL-event performance only.
- Open positions and unrealized PnL are not included.
- FIFO/LIFO/lot ledger accounting is not implemented.
- open_date and holding_days are intentionally excluded.
- Metrics are preliminary when realized trade count is small.
```

## Ranking CSV

`paper_realized_ranking.csv` 권장 컬럼:

```text
ranking_type
rank
symbol
metric_value
total_realized_pnl
realized_trade_count
win_count
loss_count
flat_count
win_rate
avg_realized_return_pct
profit_factor
note
```

ranking_type 후보:

```text
top_realized_pnl
worst_realized_pnl
loss_contribution
win_rate
profit_factor
trade_count
```

## 테스트

테스트 파일:

```text
tests/test_paper_realized_ranking_report.py
```

필수 테스트:

1. top realized PnL ranking 정렬
2. worst realized PnL ranking 정렬
3. loss contribution 계산
4. 손실 종목이 없을 때 처리
5. win_rate ranking 정렬
6. profit_factor N/A 처리
7. realized_trade_count ranking 정렬
8. markdown에 limitations 포함
9. markdown에 realized-only 문구 포함
10. ranking CSV 생성
11. 빈 입력 CSV 처리
12. 필수 컬럼 누락 감지

## 검증 명령

```bat
set PYTHONPATH=.

python -m pytest tests/test_paper_realized_ranking_report.py -q
python -m py_compile core/paper_realized_ranking_report.py
python -m py_compile scripts/generate_paper_realized_ranking_report.py
python scripts/generate_paper_realized_ranking_report.py
```

생성 확인:

```text
outputs/paper_test/reports/paper_realized_ranking_report.md
outputs/paper_test/reports/paper_realized_ranking.csv
```

## 절대 금지

```text
- paper_execution_log.csv 수정 금지
- paper_account_snapshot.csv 수정 금지
- paper_position_snapshot.csv 수정 금지
- paper_realized_trade_journal.csv 수정 금지
- paper_symbol_realized_performance.csv 수정 금지
- outputs/front_test 수정 금지
- DB 수정 금지
- --commit 실행 금지
- realized PnL 계산 재구현 금지
- unrealized PnL 통합 금지
- open position 통합 금지
- FIFO / lot ledger 구현 금지
- open_date / holding_days 계산 금지
- 대규모 리팩토링 금지
```

## 성공 기준

- realized ranking markdown report가 생성된다.
- ranking CSV가 생성된다.
- source of truth는 `paper_symbol_realized_performance.csv`다.
- 종목별 top/worst/loss contribution/win rate/profit factor ranking이 생성된다.
- realized-only 한계가 명확히 표시된다.
- 원본 paper CSV와 기존 report CSV는 수정하지 않는다.
- outputs/front_test는 수정하지 않는다.
- 테스트가 통과한다.

## 결과 보고 형식

5천자 이내.

포함:

1. Summary
2. 변경 파일
3. 생성된 산출물 경로
4. ranking 종류
5. top/worst symbols
6. loss contribution 결과
7. small sample warning 여부
8. 제외한 항목
9. 테스트 결과
10. 원본 CSV 변경 여부
11. outputs/front_test 변경 여부
12. 다음 단계 제안

반드시 명시:

```text
이번 PAPER9-4는 realized SELL-event 기준 ranking/reporting이며, open position/unrealized PnL은 포함하지 않는다.
```
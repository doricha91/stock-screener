# MFU-PAPER13-2 작업 지시문: initial cash 기준 benchmark comparison 구현

## 목적

PAPER13-2의 목표는 paper 성과를 SPY / QQQ / CASH benchmark와 비교하는 최소 benchmark comparison 기능을 구현하는 것이다.

이번 단계는 기존 exploratory paper 데이터를 기준으로 benchmark 기능을 먼저 검증한다.

반드시 명시:

```text
이번 PAPER13-2는 benchmark comparison 구현이며, clean reset/archive, Notion 연동, HTML/CSV 생성, period benchmark, 월적립식 benchmark는 포함하지 않는다.
```

## 배경

PAPER13-1 조사 결과:

```text
comparison mode: since_inception
starting capital source: paper_account_snapshot.csv의 initial_cash
comparison dates: paper_account_snapshot.csv의 snapshot_date
benchmark symbols: SPY, QQQ, CASH
benchmark price source: outputs/market_data.db의 market_index
price column priority: adj_close -> close
paper equity column: total_equity_market_value
fallback: total_equity_cost_basis
```

현재 데이터는 공식 clean reset 이후 데이터가 아니므로, 출력에는 반드시 exploratory / unofficial benchmark임을 명시한다.

## 구현 파일

권장 추가:

```text
core/paper_benchmark_comparison.py
scripts/generate_paper_benchmark_comparison.py
tests/test_paper_benchmark_comparison.py
```

수정:

```text
scripts/paper.py
tests/test_paper_cli.py
docs/TRD/mfu_paper13_2_benchmark_comparison.md
```

## CLI 요구사항

추가 명령:

```text
python scripts/paper.py benchmark
python scripts/paper.py benchmark --json
```

standalone script:

```text
python scripts/generate_paper_benchmark_comparison.py
python scripts/generate_paper_benchmark_comparison.py --json
```

이번 단계에서는 아래 옵션을 만들지 않는다.

```text
--symbols
--start
--end
--period
--dca
```

## 산출물

생성:

```text
outputs/paper_test/reports/paper_benchmark_comparison.md
outputs/paper_test/reports/paper_benchmark_comparison.json
```

`--json` 옵션은 JSON payload를 stdout에도 출력한다.

## 입력 데이터

### 1. Paper account snapshot

```text
outputs/paper_test/paper_account_snapshot.csv
```

필수 컬럼 후보:

```text
snapshot_date
initial_cash
total_equity_market_value
total_equity_cost_basis
market_valuation_status
valuation_price_date
```

정책:

```text
initial_cash는 첫 유효 snapshot row의 initial_cash 사용
paper equity는 total_equity_market_value 우선
없으면 total_equity_cost_basis fallback
fallback 사용 시 valuation_basis에 명시
snapshot_date 기준으로 정렬
snapshot 2개 미만이면 INSUFFICIENT_DATA
```

### 2. Benchmark price source

```text
outputs/market_data.db
table: market_index
symbols: SPY, QQQ
columns: symbol, date, adj_close, close
```

정책:

```text
adj_close 우선
adj_close 없으면 close
snapshot_date와 같은 날짜 가격 사용
같은 날짜 가격이 없으면 이전 거래일 가격 사용
사용한 price_date, staleness_days, used_fallback_price를 JSON에 기록
시작 또는 종료 anchor price를 찾지 못하면 해당 benchmark unavailable
```

### 3. CASH benchmark

```text
start_equity = initial_cash
end_equity = initial_cash
return = 0
max_drawdown = 0
```

이자, 환율, 예수금 수익은 제외한다.

## 계산 정책

### Paper series

각 snapshot_date별로:

```text
date
paper_equity
paper_return_from_initial_cash
valuation_basis
valuation_status
valuation_price_date
```

### Benchmark series

SPY/QQQ별로:

```text
date
symbol
price
price_date
staleness_days
used_fallback_price
benchmark_equity
benchmark_return
```

계산:

```text
benchmark_equity = initial_cash * current_price / start_price
benchmark_return = benchmark_equity / initial_cash - 1
excess_return = paper_return - benchmark_return
```

### Max drawdown

paper와 benchmark 각각 equity series 기준으로 계산한다.

```text
drawdown = equity / rolling_peak - 1
max_drawdown = min(drawdown)
```

## 1차 지표

summary에 포함:

```text
paper_start_equity
paper_end_equity
paper_return
paper_max_drawdown

benchmark_start_equity
benchmark_end_equity
benchmark_return
benchmark_max_drawdown

excess_return
latest_gap
availability_status
```

benchmark별 summary를 만든다.

초기 제외:

```text
CAGR
Sharpe
Sortino
Calmar
volatility
period benchmark
monthly DCA benchmark
```

## JSON 구조

권장 top-level:

```json
{
  "schema_version": "paper_benchmark_comparison.v1",
  "generated_at": "...",
  "run_mode": "exploratory",
  "official_run": false,
  "comparison_mode": "since_inception",
  "starting_capital_source": "paper_account_snapshot.initial_cash",
  "initial_cash": 100000.0,
  "official_start_date": null,
  "start_date_source": "earliest_available_snapshot",
  "latest_snapshot_date": "YYYY-MM-DD",
  "benchmarks": ["SPY", "QQQ", "CASH"],
  "paper_series": [],
  "benchmark_series": {},
  "summary": {},
  "source_files": {},
  "limitations": []
}
```

`limitations`에 반드시 포함:

```text
This benchmark is computed from existing exploratory paper snapshots.
It should not be interpreted as official since-inception performance until clean reset/archive is completed.
```

## Markdown 구성

```text
# Paper Benchmark Comparison

## 1. Status
## 2. Data Sources
## 3. Paper Summary
## 4. Benchmark Summary
## 5. Paper vs Benchmark Table
## 6. Latest Gap
## 7. Limitations
```

Markdown에는 exploratory / unofficial임을 상단에 명확히 표시한다.

## paper.py 연결

`scripts/paper.py`에 subcommand 추가:

```text
benchmark
```

동작:

```text
1. benchmark comparison generator 실행
2. Markdown/JSON 생성
3. 콘솔에 핵심 요약 출력
```

## 절대 금지

```text
clean reset/archive 실행 금지
paper 원장 CSV 수정 금지
DB write 금지
Notion 연동 금지
HTML/CSV 생성 금지
period benchmark 구현 금지
monthly DCA benchmark 구현 금지
prepare/preview/commit/review 실행 금지
outputs/front_test 수정 금지
```

## 테스트

추가/수정:

```text
tests/test_paper_benchmark_comparison.py
tests/test_paper_cli.py
```

필수 테스트:

```text
1. initial_cash를 account snapshot에서 읽음
2. snapshot_date 기준 paper series 생성
3. total_equity_market_value 우선 사용
4. market value 없으면 cost basis fallback
5. SPY/QQQ adj_close 우선 사용
6. adj_close 없으면 close fallback
7. snapshot_date 가격 없으면 이전 거래일 가격 사용
8. staleness_days와 used_fallback_price 기록
9. CASH benchmark return/drawdown은 0
10. paper_return / benchmark_return / excess_return 계산
11. max_drawdown 계산
12. snapshot 2개 미만이면 INSUFFICIENT_DATA
13. Markdown 파일 생성
14. JSON 파일 생성
15. JSON에 run_mode=exploratory, official_run=false 포함
16. paper.py benchmark가 generator 호출
17. paper 원장 CSV와 market_data.db를 수정하지 않음
18. outputs/front_test를 수정하지 않음
```

테스트는 임시 CSV/SQLite DB를 사용한다.

## 검증 명령

```text
set PYTHONPATH=.

python -m pytest tests/test_paper_benchmark_comparison.py tests/test_paper_cli.py -q
python -m py_compile core/paper_benchmark_comparison.py
python -m py_compile scripts/generate_paper_benchmark_comparison.py
python -m py_compile scripts/paper.py

python scripts/paper.py --help
python scripts/paper.py benchmark
python scripts/paper.py benchmark --json
```

주의:

```text
benchmark는 reports 폴더에 Markdown/JSON을 생성한다.
paper 원장 CSV와 market_data.db는 수정하지 않는다.
```

## 성공 기준

```text
paper.py benchmark 명령이 추가된다.
SPY/QQQ/CASH benchmark comparison이 생성된다.
initial_cash 기준 since-inception 비교가 계산된다.
snapshot_date 기준으로 paper와 benchmark가 정렬된다.
Markdown/JSON 산출물이 생성된다.
exploratory / unofficial 상태가 명확히 표시된다.
clean reset/archive는 실행하지 않는다.
paper 원장 CSV와 outputs/front_test는 수정하지 않는다.
테스트가 통과한다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 변경 파일
3. 추가된 CLI
4. 입력 데이터
5. benchmark 계산 방식
6. CASH benchmark 처리
7. 결측 가격 처리
8. 생성 산출물
9. JSON 구조
10. Markdown 구성
11. exploratory/unofficial 표시
12. 제외한 항목
13. 테스트 결과
14. 실제 benchmark 실행 결과
15. paper 원장 CSV 변경 여부
16. outputs/front_test 변경 여부
17. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER13-2는 benchmark comparison 구현이며, clean reset/archive와 Notion 연동은 포함하지 않는다.
```
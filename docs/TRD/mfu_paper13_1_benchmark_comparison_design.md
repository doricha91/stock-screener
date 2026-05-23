# MFU-PAPER13-1 Benchmark Comparison Design

## 1. Scope

이번 MFU는 paper 성과를 `SPY`, `QQQ`, `CASH` benchmark와 비교하기 위한 입력 데이터, 기준일, 시작자산, reset 정책, 출력 schema를 조사하고 설계한다.

이번 단계는 조사/설계 전용이다.

- 코드 구현 없음
- DB write 없음
- paper 원장 CSV 수정 없음
- reset 실행 없음

## 2. Confirmed Phase-1 Policy

- benchmark symbols:
  - `SPY`
  - `QQQ`
  - `CASH`
- comparison mode:
  - `since_inception`
- starting capital:
  - `initial_cash`
- comparison date basis:
  - `paper_account_snapshot.csv.snapshot_date`
- outputs:
  - Markdown
  - JSON

## 3. Source Investigation

### 3.1 initial_cash source

조사 결과:

- `paper_account_snapshot.csv`에 `initial_cash` 컬럼이 명시적으로 존재한다.
- 실제 snapshot row에서 `initial_cash=100000.00`이 유지되고 있다.
- `paper_current_state_YYYYMMDD.json`에는 `cash`와 position 상태는 있지만 `initial_cash`는 없다.
- `paper_execution_log.csv`는 trade row 중심이라 initial capital의 공식 source로 적합하지 않다.

권장안:

- 1순위 공식 source:
  - `outputs/paper_test/paper_account_snapshot.csv.initial_cash`
- 이유:
  - snapshot 기준 성과 시계열과 직접 결합된다.
  - 재생성 가능한 current state JSON보다 더 안정적인 persisted ledger 성격을 가진다.
  - benchmark since-inception 계산에 필요한 시작자산이 명시적으로 저장된다.

fallback:

- 향후 `initial_cash` 컬럼이 누락된 legacy data만 있을 경우에 한해, earliest snapshot의 total equity 계열 값을 임시 fallback으로 고려할 수 있다.
- 다만 1차 구현에서는 fallback보다는 `initial_cash` 컬럼 존재를 강하게 요구하는 편이 안전하다.

### 3.2 official_start_date

후보:

- 첫 `paper_account_snapshot.csv.snapshot_date`
- 첫 `paper_execution_log.csv.date`
- clean reset 이후 첫 snapshot date
- 수동 설정 official start date

권장안:

- 공식 benchmark 시작일은 `clean reset 이후 첫 paper_account_snapshot.csv.snapshot_date`

이유:

- benchmark 기준축은 snapshot date다.
- execution log는 no-trade day에 row가 0이어도 정상일 수 있어 시작 기준으로 부적합하다.
- official run 이전 실험 데이터가 남아 있으면 since-inception benchmark 의미가 약해진다.

현재 관찰된 earliest snapshot:

- `2026-05-09`

단, 이 날짜를 곧바로 official start로 고정하기보다, clean reset 정책 확정 후 official run 첫 snapshot을 기준으로 삼는 것이 바람직하다.

### 3.3 clean reset policy candidates

#### A. archive/reset_YYYYMMDD/로 이동 후 새 official run 시작

장점:

- since-inception benchmark 의미가 가장 명확하다.
- 이전 실험 데이터와 공식 성과를 분리할 수 있다.
- 운영자 해석이 가장 단순하다.

단점:

- archive/reset 절차가 추가로 필요하다.
- 비교용 과거 report/review artifact 처리 기준을 정해야 한다.

#### B. 기존 데이터를 유지하되 official_start_date 이후만 benchmark에 사용

장점:

- 기존 파일 이동 없이 바로 적용 가능하다.
- 구현 부담이 낮다.

단점:

- 원장에는 이전 데이터가 남아 있어서 운영자 혼동 가능성이 있다.
- "official since-inception" 해석이 문서 의존적이다.

#### C. benchmark config에 ignore_before 날짜를 둔다

장점:

- 가장 유연하다.
- future period benchmark로 확장하기 쉽다.

단점:

- 설정 실수 가능성이 있다.
- 실제 원장과 리포트 해석의 기준이 분리된다.

권장안:

- 운영 명확성 우선이면 `A`
- 즉시 구현 우선이면 `B` 또는 `C`
- PAPER13-2 1차 구현은 reset 실행 없이도 가능하지만, benchmark 해석 신뢰도를 높이려면 중장기적으로 `A`가 가장 바람직하다.

### 3.4 SPY / QQQ price source

조사 결과:

- `outputs/market_data.db`에 `market_index` 테이블이 존재한다.
- schema:
  - `symbol`
  - `date`
  - `close`
  - `adj_close`
  - `moving_avg_200`
- `SPY`, `QQQ`, `^VIX` 모두 `market_index`에 존재한다.
- `SPY` / `QQQ`의 `MAX(date)`는 `2026-05-20`으로 snapshot date와 정렬 가능하다.
- `daily_price`에도 `SPY`, `QQQ`가 있으나 최신일이 `2025-12-31`로 `market_index`보다 뒤처져 있다.

권장안:

- 1순위 source:
  - `market_index`
- 1순위 price column:
  - `adj_close`
- fallback:
  - `close`

이유:

- benchmark는 total-return에 가까운 비교가 유리하므로 adjusted close 우선이 자연스럽다.
- 현재 repo 데이터 freshness 기준으로 `market_index`가 더 신뢰 가능하다.
- 기존 `market_analyzer.py`도 market regime 조회 시 `market_index`를 사용한다.

### 3.5 CASH benchmark definition

정의:

- `CASH equity = initial_cash`
- `return = 0`
- `drawdown = 0`

제외:

- 이자
- 환율 효과
- MMF/예수금 수익

### 3.6 paper equity basis

조사 결과:

`paper_account_snapshot.csv`에는 아래 컬럼들이 존재한다.

- `total_equity_cost_basis`
- `positions_market_value`
- `total_equity_market_value`
- `cash_ratio_market_value`
- `unrealized_pnl`
- `market_valuation_status`
- `valuation_price_date`

권장안:

- 1순위:
  - `total_equity_market_value`
- fallback:
  - `total_equity_cost_basis`

보조 metadata:

- `market_valuation_status`
- `valuation_price_date`
- JSON에 `valuation_basis`를 명시

## 4. Missing Benchmark Price Policy

snapshot date에 benchmark 가격이 없을 경우 후보:

- A. 이전 거래일 가격 사용
- B. unavailable 처리
- C. 전체 리포트 FAIL

권장안:

- 기본은 `이전 거래일 가격 fallback`
- 단, 아래 metadata를 JSON에 반드시 남긴다.
  - `price_date`
  - `staleness_days`
  - `used_fallback_price=true/false`

추가 정책:

- 시작일과 종료일 benchmark price를 모두 확보할 수 없으면 summary 계산을 `unavailable` 처리할 수 있다.
- 일부 중간 날짜 series만 누락되면 benchmark series에서 fallback 또는 hole 표기를 선택할 수 있다.

## 5. Phase-1 Benchmark Metrics

PAPER13-2 1차 구현 권장 최소 지표:

- `paper_start_equity`
- `paper_end_equity`
- `paper_return`
- `benchmark_start_equity`
- `benchmark_end_equity`
- `benchmark_return`
- `excess_return`
- `paper_max_drawdown`
- `benchmark_max_drawdown`
- `latest_gap`

초기 제외:

- `CAGR`
- `Sharpe`
- `Sortino`
- `Calmar`
- `volatility`
- monthly DCA benchmark
- period benchmark

이유:

- 초기 snapshot row 수가 적으면 통계 지표의 해석력이 약하다.

## 6. Recommended Output Design

### 6.1 Output files

- `outputs/paper_test/reports/paper_benchmark_comparison.md`
- `outputs/paper_test/reports/paper_benchmark_comparison.json`

### 6.2 JSON schema draft

```json
{
  "schema_version": "paper_benchmark_comparison.v1",
  "generated_at": "YYYY-MM-DDTHH:MM:SS",
  "comparison_mode": "since_inception",
  "starting_capital_source": "initial_cash",
  "initial_cash": 100000.0,
  "official_start_date": "YYYY-MM-DD",
  "latest_snapshot_date": "YYYY-MM-DD",
  "paper_basis": {
    "equity_column": "total_equity_market_value",
    "valuation_basis": "market_value",
    "currency": "USD"
  },
  "benchmarks": [
    {
      "symbol": "SPY",
      "price_source": "market_index.adj_close",
      "start_price_date": "YYYY-MM-DD",
      "end_price_date": "YYYY-MM-DD"
    }
  ],
  "paper_series": [],
  "benchmark_series": [],
  "summary": {},
  "source_files": {},
  "limitations": []
}
```

### 6.3 Markdown sections

- Header
- Comparison Basis
- Paper Summary
- Benchmark Summary
- Excess Return Summary
- Drawdown Summary
- Series Coverage / Fallback Notes
- Limitations

## 7. Recommended CLI for PAPER13-2

1차 구현 권장:

- `python scripts/paper.py benchmark`
- `python scripts/paper.py benchmark --json`

추후 확장 후보:

- `python scripts/paper.py benchmark --symbols SPY QQQ`
- `python scripts/paper.py benchmark --start YYYYMMDD --end YYYYMMDD`

## 8. Source Files To Track In JSON

권장 metadata:

- `paper_account_snapshot.csv`
- `paper_position_snapshot.csv`
- `paper_execution_log.csv`
- `market_data.db`
- `market_index` table metadata
- selected benchmark symbols / latest price dates

## 9. Implementation Boundary For PAPER13-2

포함 권장:

- since-inception only
- SPY / QQQ / CASH only
- initial cash only
- Markdown / JSON only
- latest summary + series output

제외 유지:

- period benchmark
- DCA benchmark
- Notion export
- HTML/CSV output
- reset execution
- archive move execution

## 10. Key Risks And Notes

- 기존 exploratory paper data가 남아 있으면 since-inception benchmark 해석이 왜곡될 수 있다.
- `market_index`와 `paper_account_snapshot` 날짜 정렬이 맞지 않을 수 있으므로 fallback price metadata가 중요하다.
- `paper_current_state_*.json`는 initial cash source로 부적합하다.
- 1차 benchmark는 "정확한 투자 평가"가 아니라 paper 운영 성과를 대조군과 비교하는 lightweight summary로 정의하는 편이 안전하다.

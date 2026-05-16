# MFU-PAPER5-1 Market Valuation Policy PRD

## 1. 목적

`paper_account_snapshot.csv`가 현재 `cost_basis` 기준 계좌 상태만 저장하고 있으므로,
후속 MFU에서 `market value`, `unrealized PnL`, `performance report`를 구현하기 전에
paper 계좌의 **공식 평가 가격 기준**을 먼저 확정한다.

이번 MFU의 목표는 정책 문서화이며, 계산 구현은 포함하지 않는다.

## 2. Valuation 목적

paper market valuation의 목적은 다음과 같다.

- paper 계좌의 일별 장마감 기준 평가금액을 일관되게 계산한다.
- `unrealized PnL`과 `total market equity` 계산의 기준 가격을 고정한다.
- 후속 `paper_performance_report`와 benchmark 비교가 동일한 평가 기준을 사용하도록 한다.

이번 단계에서는 아래 항목만 정의한다.

- 공식 가격 source
- valuation date rule
- missing price rule
- holiday/weekend rule

## 3. Price Source

공식 평가 가격 source는 **기존 DB의 `daily_price` close**로 한다.

선택 이유:

- 재현성이 높다.
- 테스트 안정성이 높다.
- 장중 데이터 흔들림과 외부 API 응답 변화에 덜 민감하다.
- front-test / backtest / data freshness 체계와의 정합성이 좋다.

이번 정책에서는 아래를 사용하지 않는다.

- yfinance 실시간 호출
- 외부 quote API 실시간 호출
- 브로커 실시간 호가

## 4. Valuation Date Rule

평가 기준일은 `snapshot_date`로 한다.

기본 원칙:

- `snapshot_date`의 해당 종목 종가(close)를 사용한다.
- EOD pipeline은 거래일 기준 실행을 원칙으로 한다.

즉, 가장 우선하는 가격은:

- symbol
- snapshot_date
- close

조합이다.

## 5. Missing Price Rule

이번 정책에서 공식 선택은 **B안**이다.

- A안: 누락 시 error
- B안: 가장 최근 available close 사용
- C안: avg_price fallback

선택 정책:

- `snapshot_date`에 가격이 없으면 **snapshot_date 이전 가장 최근 거래일의 close**를 사용한다.
- 이때 후속 산출물에는 `valuation_price_date`를 함께 남겨 실제 사용 가격일을 명시한다.

`avg_price` fallback은 이번 정책에서 채택하지 않는다.

이유:

- cost basis와 market valuation을 혼동시킨다.
- unrealized PnL이 0 또는 왜곡된 값으로 고정될 위험이 있다.
- 데이터 누락을 숨겨버릴 수 있다.

## 6. Holiday / Weekend Rule

기본 원칙:

- pipeline은 거래일 EOD 기준 실행을 원칙으로 한다.

보완 규칙:

- `snapshot_date`가 주말/휴장일이거나 해당 날짜 price row가 없으면,
  **직전 거래일 close**를 사용한다.

즉, 휴장일 처리도 사실상 “가장 최근 available close 사용” 정책에 포함된다.

## 7. 저장 컬럼 후보

후속 MFU에서 `paper_account_snapshot.csv` 또는 별도 valuation snapshot에 아래 컬럼을 추가할 수 있다.

- `positions_market_value`
- `total_equity_market_value`
- `unrealized_pnl`
- `unrealized_pnl_pct`
- `valuation_price_date`
- `valuation_method`

이 중 `valuation_price_date`는 이번 정책상 필수에 가깝다.

이유:

- `snapshot_date`와 실제 사용 가격일이 다를 수 있기 때문이다.

## 8. Excluded Scope

이번 단계에서 제외한다.

- 실제 `market value` 계산 구현
- `unrealized PnL` 계산 구현
- `paper_performance_report` 생성
- benchmark 비교
- MDD / CAGR / Sharpe
- DB schema 변경
- 실시간 quote source 도입

## 9. 후속 MFU 목록

권장 후속 순서:

1. MFU-PAPER5-2: DB close 기반 market valuation helper 추가
2. MFU-PAPER5-3: `paper_account_snapshot.csv`에 market value / unrealized PnL 컬럼 추가
3. MFU-PAPER5-4: `paper_performance_report` 초안 추가
4. MFU-PAPER5-5: benchmark 비교 및 drawdown/return metric 추가


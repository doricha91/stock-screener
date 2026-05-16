# MFU-PAPER5-1 Market Valuation Policy TRD

## 1. 목적

PAPER5 계열에서 market valuation을 구현할 때,
`paper_execution_log.csv` / `paper_current_state_YYYYMMDD.json` / `paper_account_snapshot.csv`
체계 위에 어떤 가격 조회 규칙을 얹을지 기술적으로 고정한다.

이번 문서는 구현 코드를 추가하지 않고, 후속 helper와 snapshot 확장 방향만 정의한다.

## 2. 기술 기준

공식 평가 가격 source:

- `daily_price` 계열 DB의 close

비공식 / 비허용 source:

- yfinance 실시간 호출
- intraday API
- broker quote
- avg_price fallback

즉, 후속 구현은 **로컬 DB + close 기준**만 사용해야 한다.

## 3. 평가 알고리즘 정책

종목별 평가 가격 결정 순서:

1. `snapshot_date`의 close 조회 시도
2. 없으면 `snapshot_date` 이전 최신 거래일 close 조회
3. 그래도 없으면 error 처리

이 정책은 다음 의도를 갖는다.

- 휴장일/주말에 안전하게 동작
- 재현 가능한 valuation 유지
- 데이터가 실제로 없을 때는 침묵하지 않고 실패

즉, 정책 조합은 다음과 같다.

- missing price rule: recent available close 사용
- no available close at all: error

## 4. 후속 helper 권장 구조

후속 구현에서 권장되는 helper 역할은 다음과 같다.

### 4-1. 가격 조회 helper

예상 역할:

- 입력:
  - `symbol`
  - `snapshot_date`
- 출력:
  - `valuation_close`
  - `valuation_price_date`

정책:

- 반환 close는 `snapshot_date` 또는 직전 거래일 close
- 실제 사용 날짜를 함께 반환

### 4-2. market valuation row builder

예상 역할:

- `PaperAccountState`
- 종목별 valuation price map
- `snapshot_date`

를 받아 다음을 계산:

- `positions_market_value`
- `total_equity_market_value`
- `unrealized_pnl`
- `unrealized_pnl_pct`

단, 이 MFU에서는 아직 구현하지 않는다.

## 5. snapshot 저장 확장 방향

후속 MFU에서 `paper_account_snapshot.csv`를 확장할 때 권장되는 추가 컬럼:

- `positions_market_value`
- `total_equity_market_value`
- `unrealized_pnl`
- `unrealized_pnl_pct`
- `valuation_price_date`
- `valuation_method`

권장 `valuation_method` 값:

- `cost_basis`
- `db_close`
- 필요 시 이후 `db_prev_close_fallback`

다만 첫 구현에서는 method를 지나치게 세분화하지 말고,
`valuation_price_date`를 함께 남기는 쪽이 더 중요하다.

## 6. 휴장일 / 주말 처리 기술 규칙

후속 구현은 거래일 캘린더를 직접 구현하지 않아도 된다.

대신:

- `snapshot_date <= price_date`
  같은 미래 참조는 금지
- `snapshot_date` 이전 또는 동일 날짜에서 가장 최근 available close만 허용

즉, look-ahead bias 없이 backward lookup만 허용한다.

## 7. 에러 처리 규칙

후속 market valuation helper는 아래에서 실패해야 한다.

- symbol에 대한 price history가 전혀 없음
- `snapshot_date` 이전 포함해서 usable close를 찾을 수 없음
- DB read 자체가 실패

이 경우:

- valuation snapshot 저장 중단
- 명확한 error 출력
- 기존 `paper_current_state`나 `paper_execution_log`는 수정하지 않음

## 8. 제외 범위

이번 TRD 범위 밖:

- 실시간 가격 source
- 장중 업데이트
- benchmark return 계산
- drawdown / Sharpe / CAGR
- 수수료 / 세금 / 슬리피지 반영
- DB schema 변경

## 9. 후속 MFU 제안

1. MFU-PAPER5-2
   - DB close valuation helper 구현
2. MFU-PAPER5-3
   - `paper_account_snapshot.csv` market valuation 확장
3. MFU-PAPER5-4
   - unrealized PnL 및 total market equity 저장
4. MFU-PAPER5-5
   - performance report / benchmark / drawdown metric


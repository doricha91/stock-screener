# MFU-PAPER5-2 작업 지시문: DB close 기반 valuation helper 구현

## 기준 정보

- 저장소: stock-screener
- 기준 최신 커밋 full SHA:
  301fa445a3b5b0e262763f75cabb489a58f064e1
- 선행 완료:
  - MFU-PAPER4-5: paper_account_snapshot.csv cost_basis 저장 완료
  - MFU-PAPER5-1: market valuation 가격 기준 정책 문서화 완료

## 이번 작업 목적

paper 계좌의 보유 종목을 DB `daily_price.close` 기준으로 평가하기 위한 valuation helper를 구현한다.

이번 단계는 helper와 테스트가 목적이다.  
`paper_account_snapshot.csv`에 market value 컬럼을 실제 연결하는 작업은 다음 MFU에서 처리한다.

## 확정 정책

1. 공식 가격 source:
   - 기존 DB `daily_price`의 `close`

2. 가격 조회 기준:
   - `snapshot_date` 당일 close가 있으면 사용
   - 없으면 snapshot_date 이전의 가장 최근 available close 사용
   - 그래도 없으면 error

3. 오래된 가격 처리:
   - 우선 제한 없이 직전 available close 사용
   - 대신 `price_staleness_days`를 계산해 기록
   - 너무 오래된 가격은 warning 후보로 남김

4. 가격 완전 누락:
   - 한 종목이라도 가격을 찾지 못하면 전체 valuation 실패
   - avg_price fallback 금지

5. valuation 날짜 기록:
   - 전체 `valuation_price_date`
   - 종목별 `valuation_price_dates`
   - 종목별 `price_staleness_days`

## 이번 단계에서 할 일

### 1. 신규 helper 파일 추가

권장 파일:

```text
core/paper_market_valuation.py
```

권장 dataclass:

```python
@dataclass
class PaperPositionValuation:
    symbol: str
    shares: int
    avg_price: float
    close_price: float
    market_value: float
    cost_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float | None
    valuation_price_date: str
    price_staleness_days: int
```

```python
@dataclass
class PaperAccountValuation:
    snapshot_date: str
    cash: float
    positions_cost_value: float
    positions_market_value: float
    total_equity_cost_basis: float
    total_equity_market_value: float
    cash_ratio_market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float | None
    valuation_method: str
    valuation_price_date: str
    valuation_price_dates: dict[str, str]
    price_staleness_days: dict[str, int]
    positions: list[PaperPositionValuation]
```

권장 함수:

```python
get_latest_close_on_or_before(
    conn,
    symbol: str,
    snapshot_date: str,
) -> tuple[float, str]
```

```python
value_paper_account_state(
    state: PaperAccountState,
    snapshot_date: str,
    db_path: Path,
) -> PaperAccountValuation
```

## 계산 정의

```text
cost_value = shares * avg_price
market_value = shares * close_price
positions_cost_value = sum(cost_value)
positions_market_value = sum(market_value)
total_equity_cost_basis = cash + positions_cost_value
total_equity_market_value = cash + positions_market_value
cash_ratio_market_value = cash / total_equity_market_value
unrealized_pnl = positions_market_value - positions_cost_value
unrealized_pnl_pct = unrealized_pnl / positions_cost_value
valuation_method = "db_daily_price_close"
```

예외:
- positions_cost_value가 0이면 unrealized_pnl_pct는 None
- total_equity_market_value가 0이면 error 또는 None 처리. 권장: error

## 주의할 DB 조회

`daily_price` schema를 먼저 확인하고 실제 컬럼명을 검증한다.

예상 컬럼 후보:
- symbol 또는 ticker
- date
- close

컬럼명이 다르면 기존 프로젝트의 DB 접근 패턴을 따라라.  
DB schema를 변경하지 마라.

## 절대 금지

- DB schema 변경 금지
- DB 파일 수정 금지
- outputs/front_test 수정 금지
- paper_account_snapshot.csv 구조 변경 금지
- run_paper_eod_update.py에 저장 연결 금지
- yfinance 실시간 호출 금지
- avg_price fallback 금지
- performance report 생성 금지
- MDD / CAGR / Sharpe 구현 금지

## 테스트 추가

권장 파일:

```text
tests/test_paper_market_valuation.py
```

필수 테스트:

1. snapshot_date 당일 close 사용
   - 해당 날짜 close가 있으면 그 가격 사용

2. 당일 close 없을 때 직전 close 사용
   - valuation_price_date가 직전 거래일로 기록되는지 확인

3. price_staleness_days 계산
   - snapshot_date와 실제 valuation_price_date 차이 계산

4. 가격 완전 누락 시 error
   - avg_price fallback이 발생하지 않아야 함

5. account-level 계산 검증
   - positions_market_value
   - total_equity_market_value
   - cash_ratio_market_value
   - unrealized_pnl
   - unrealized_pnl_pct

6. empty positions 처리
   - positions 없음
   - positions_market_value = 0
   - total_equity_market_value = cash
   - unrealized_pnl = 0

## 검증 명령

PowerShell 기준:

```powershell
$env:PYTHONPATH="."
python -m pytest tests/test_paper_market_valuation.py -q
python -m pytest tests/test_paper_account_state.py -q
python -m pytest tests/test_paper_account_snapshot.py -q
python -m py_compile core/paper_market_valuation.py
```

기존 관련 테스트도 가능하면 실행:

```powershell
python -m pytest tests/test_paper_current_state_serializer.py -q
python -m pytest tests/test_paper_current_state_storage.py -q
```

## 성공 기준

- DB daily_price close 기반 valuation helper가 구현됨
- snapshot_date close 우선, 없으면 직전 available close 사용
- 가격 완전 누락 시 error
- avg_price fallback 없음
- valuation_price_date, valuation_price_dates, price_staleness_days 기록 가능
- account-level market value와 unrealized PnL 계산 테스트 통과
- DB / outputs/front_test / paper_account_snapshot.csv 변경 없음
- run_paper_eod_update.py 저장 흐름 변경 없음

## 결과 보고 형식

5,000자 이내로 작성한다.

포함할 항목:

1. Summary
2. 변경 파일
3. 구현한 helper / dataclass
4. 가격 조회 정책 적용 결과
5. 계산 정의
6. 테스트 결과
7. 변경하지 않은 파일/범위
8. 남은 한계 / 다음 단계

반드시 명시할 것:

- DB schema를 변경했는지 여부
- paper_account_snapshot.csv를 변경했는지 여부
- outputs/front_test 변경 여부
- avg_price fallback을 사용하지 않았는지 여부
- 다음 단계가 paper_account_snapshot.csv에 market value 컬럼 연결인지 여부
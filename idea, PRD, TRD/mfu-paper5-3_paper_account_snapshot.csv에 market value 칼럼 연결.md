# MFU-PAPER5-3 작업 지시문: paper_account_snapshot.csv에 market value 컬럼 연결

## 기준 정보

- 저장소: stock-screener
- 기준 최신 커밋 full SHA:
  301fa445a3b5b0e262763f75cabb489a58f064e1
- 선행 완료:
  - MFU-PAPER4-5: cost_basis 기준 paper_account_snapshot.csv 저장 완료
  - MFU-PAPER5-1: market valuation 가격 정책 문서화 완료
  - MFU-PAPER5-2: DB daily_price.close 기반 valuation helper 구현 완료

## 이번 작업 목적

`core/paper_market_valuation.py`의 helper를 사용해 `paper_account_snapshot.csv`에 market value / unrealized PnL 관련 컬럼을 추가한다.

단, market valuation 실패가 전체 paper EOD commit을 막으면 안 된다.  
paper_execution_log, paper_current_state, cost_basis snapshot 저장은 계속 유지하고, market valuation만 실패 상태로 기록한다.

## 확정 정책

1. 기존 cost_basis 컬럼은 유지한다.
2. market value 컬럼을 추가한다.
3. 가격 평가는 DB `daily_price.close` 기준 helper를 사용한다.
4. avg_price fallback은 계속 금지한다.
5. 가격 완전 누락 등 valuation 실패 시 전체 EOD 실패가 아니라 snapshot의 market valuation 영역만 failed로 기록한다.
6. outputs/front_test는 절대 수정하지 않는다.

## 추가할 snapshot 컬럼

기존 컬럼 뒤에 아래 컬럼을 추가한다.

```text
positions_market_value
total_equity_market_value
cash_ratio_market_value
unrealized_pnl
unrealized_pnl_pct
market_valuation_status
market_valuation_error
valuation_method
valuation_price_date
valuation_price_dates
price_staleness_days
max_price_staleness_days
```

## 컬럼 정의

```text
positions_market_value
- sum(shares * close_price)

total_equity_market_value
- cash + positions_market_value

cash_ratio_market_value
- cash / total_equity_market_value

unrealized_pnl
- positions_market_value - positions_cost_value

unrealized_pnl_pct
- unrealized_pnl / positions_cost_value
- positions_cost_value가 0이면 빈 값 또는 None

market_valuation_status
- "success" 또는 "failed"

market_valuation_error
- success면 빈 값
- failed면 error message 저장

valuation_method
- success면 "db_daily_price_close"
- failed면 빈 값 또는 "db_daily_price_close_failed"

valuation_price_date
- 계좌 전체 보수 기준일
- MFU-PAPER5-2 helper의 account-level valuation_price_date 사용

valuation_price_dates
- 종목별 가격 기준일 dict를 JSON string으로 저장

price_staleness_days
- 종목별 staleness dict를 JSON string으로 저장

max_price_staleness_days
- 종목별 staleness 중 최대값
```

## 구현 권장 위치

### 1. core/paper_account_snapshot.py 수정

`build_paper_account_snapshot_row()`가 optional valuation 결과를 받을 수 있게 확장한다.

예시 방향:

```python
build_paper_account_snapshot_row(
    state,
    snapshot_date,
    initial_cash=100000.0,
    source_execution_log=None,
    source_current_state=None,
    market_valuation=None,
    market_valuation_error=None,
)
```

동작:
- market_valuation이 있으면 market value 컬럼 채움
- market_valuation_error가 있으면 market_valuation_status="failed"로 저장
- 둘 다 없으면 dry-run 또는 valuation 미수행 상태를 명확히 처리

### 2. scripts/run_paper_eod_update.py 수정

기존 흐름은 유지한다.

권장 흐름:

```text
1. paper_execution_log append / duplicate 처리
2. 최신 paper_execution_log.csv로 PaperAccountState 재계산
3. paper_current_state 저장
4. paper market valuation 시도
5. 성공하면 market value 포함 snapshot row 생성
6. 실패하면 cost_basis + failed status snapshot row 생성
7. --commit이면 paper_account_snapshot.csv 저장
8. dry-run이면 preview만 출력
```

중요:
- valuation 실패가 `--commit` 전체 실패로 이어지지 않게 한다.
- 단, cost_basis snapshot 생성 자체가 실패하면 기존처럼 error 처리 가능하다.

## 절대 금지

- DB schema 변경 금지
- DB 파일 수정 금지
- outputs/front_test 수정 금지
- paper_execution_log 기존 row 수정 금지
- avg_price fallback 금지
- yfinance 실시간 호출 금지
- performance report 생성 금지
- benchmark 비교 금지
- MDD / CAGR / Sharpe 구현 금지

## 테스트 추가/수정

기존 파일 수정 권장:

```text
tests/test_paper_account_snapshot.py
```

필수 테스트:

1. valuation success row 생성
   - positions_market_value
   - total_equity_market_value
   - cash_ratio_market_value
   - unrealized_pnl
   - unrealized_pnl_pct
   - market_valuation_status="success"

2. valuation failure row 생성
   - cost_basis 컬럼은 정상 유지
   - market_valuation_status="failed"
   - market_valuation_error 저장
   - market value 숫자 컬럼은 빈 값 또는 None

3. JSON string 컬럼 테스트
   - valuation_price_dates
   - price_staleness_days

4. max_price_staleness_days 계산 테스트

5. 같은 날짜 replace 유지 테스트
   - 기존 snapshot row 중복 없이 replace
   - archive backup 생성

6. dry-run smoke
   - snapshot preview만 출력
   - 파일 변경 없음

7. commit smoke
   - snapshot 저장
   - market valuation 성공/실패 상태가 CSV에 반영됨

## 검증 명령

PowerShell 기준:

```powershell
$env:PYTHONPATH="."
python -m pytest tests/test_paper_market_valuation.py -q
python -m pytest tests/test_paper_account_snapshot.py -q
python -m pytest tests/test_paper_account_state.py -q
python -m pytest tests/test_paper_current_state_storage.py -q
python -m py_compile core/paper_account_snapshot.py core/paper_market_valuation.py scripts/run_paper_eod_update.py
```

smoke:

```powershell
$env:PYTHONPATH="."
python scripts/run_paper_eod_update.py --date 20260509 --allow-empty-journal
python scripts/run_paper_eod_update.py --date 20260509 --allow-empty-journal --commit
```

검증:

```powershell
git status --short outputs\paper_test outputs\front_test
git diff -- outputs\front_test
dir outputs\paper_test
dir outputs\paper_test\archive
```

## 성공 기준

- paper_account_snapshot.csv에 market value 컬럼 추가
- valuation 성공 시 market value / unrealized PnL 값 저장
- valuation 실패 시 cost_basis snapshot은 유지되고 market_valuation_status="failed" 기록
- avg_price fallback 없음
- 같은 날짜 row replace / archive backup 기존 정책 유지
- dry-run에서 파일 변경 없음
- --commit에서 snapshot 저장
- outputs/front_test 변경 없음
- DB 변경 없음
- performance report 미생성

## 결과 보고 형식

5,000자 이내로 작성한다.

포함할 항목:

1. Summary
2. 변경 파일
3. 추가된 snapshot 컬럼
4. valuation success 처리
5. valuation failure 처리
6. dry-run 결과
7. commit 결과
8. 테스트 결과
9. outputs/front_test 변경 여부
10. 남은 한계 / 다음 단계

반드시 명시할 것:

- avg_price fallback 사용 여부
- DB schema 변경 여부
- paper_account_snapshot.csv row 중복 여부
- archive backup 파일명
- market valuation 실패 시 전체 EOD가 중단되는지 여부
- performance report는 아직 만들지 않았는지 여부
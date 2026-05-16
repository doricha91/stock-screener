# MFU-PAPER5-8 작업 지시문: paper_position_snapshot.csv 종목별 수익률 저장

## 기준 정보

- 저장소: stock-screener
- 기준 최신 커밋 full SHA:
  301fa445a3b5b0e262763f75cabb489a58f064e1
- 선행 완료:
  - MFU-PAPER5-3: account snapshot에 market value / unrealized PnL 연결
  - MFU-PAPER5-4: realized PnL 구현
  - MFU-PAPER5-6: adversarial paper pipeline regression 검증
  - MFU-PAPER5-7: read-only paper performance summary report 생성

## 이번 작업 목적

계좌 단위 `paper_account_snapshot.csv`와 별도로, 종목별 상태/수익률을 저장하는 `paper_position_snapshot.csv`를 추가한다.

목표는 현재 보유 종목별로 다음을 추적하는 것이다.

- 보유 수량
- 평균단가
- 원가
- 시장가 평가액
- 미실현손익
- 종목별 실현손익
- 종목별 총손익
- 평가 가격 기준일
- 가격 stale 여부

이번 단계는 종목별 snapshot 저장이 목적이며, benchmark / MDD / CAGR / Sharpe는 구현하지 않는다.

## 생성 파일

출력 경로:

```text
outputs/paper_test/paper_position_snapshot.csv
```

archive 경로:

```text
outputs/paper_test/archive/
```

같은 snapshot_date row들이 이미 있으면 기존 `paper_position_snapshot.csv`를 archive 백업한 뒤 해당 날짜 row 전체를 replace한다.

## CSV 컬럼

아래 컬럼을 사용한다.

```text
snapshot_date
symbol
shares
avg_price
cost_value
close_price
market_value
unrealized_pnl
unrealized_pnl_pct
realized_pnl
total_pnl
total_pnl_pct_on_current_cost
valuation_method
valuation_price_date
price_staleness_days
position_status
created_at
```

## 컬럼 정의

```text
snapshot_date
- 대상 EOD 날짜

symbol
- 종목 코드

shares
- 현재 보유 수량

avg_price
- 현재 평균단가

cost_value
- shares * avg_price

close_price
- DB daily_price.close 기반 평가가

market_value
- shares * close_price

unrealized_pnl
- market_value - cost_value

unrealized_pnl_pct
- unrealized_pnl / cost_value
- cost_value가 0이면 빈 값

realized_pnl
- PaperAccountState.realized_pnl_by_symbol[symbol]
- 없으면 0

total_pnl
- realized_pnl + unrealized_pnl

total_pnl_pct_on_current_cost
- total_pnl / cost_value
- 단, 이것은 “현재 보유 원가 기준”이지 누적 투입원금 기준 수익률이 아님

valuation_method
- db_daily_price_close

valuation_price_date
- 해당 symbol 평가에 사용한 close 날짜

price_staleness_days
- snapshot_date와 valuation_price_date 차이

position_status
- 현재 보유 중이면 OPEN
- 이번 단계에서는 보유 중인 종목만 저장하므로 기본 OPEN
```

## 구현 권장 구조

### 1. 신규 파일 추가

```text
core/paper_position_snapshot.py
```

권장 함수:

```python
build_paper_position_snapshot_rows(
    state: PaperAccountState,
    market_valuation: PaperAccountValuation,
    snapshot_date: str,
) -> list[dict]
```

```python
save_paper_position_snapshot(
    rows: list[dict],
    snapshot_path: Path,
    archive_dir: Path,
) -> dict
```

동작:
- 현재 보유 중인 positions만 row 생성
- 같은 snapshot_date가 이미 있으면 해당 날짜 row 전체 replace
- 다른 날짜 row는 유지
- 저장 전 paper path safety 검증
- snapshot_date, symbol 기준 정렬

### 2. scripts/run_paper_eod_update.py 연결

기존 흐름 뒤에 연결한다.

```text
paper_execution_log.csv
→ PaperAccountState reducer
→ paper_current_state 저장
→ account market valuation
→ paper_account_snapshot.csv 저장
→ paper_position_snapshot.csv 저장
```

중요:
- dry-run에서는 position snapshot preview만 출력하고 파일 저장 금지
- --commit에서만 저장
- market valuation success일 때만 position snapshot 저장
- market valuation failed이면 position snapshot 저장은 skip하고 warning 출력
- cost_basis account snapshot 저장은 기존처럼 유지

## 절대 금지

- outputs/front_test 수정 금지
- DB schema / DB files 수정 금지
- paper_execution_log 기존 row 수정 금지
- paper_account_snapshot.csv 기존 의미 변경 금지
- yfinance 호출 금지
- broker API 호출 금지
- benchmark / MDD / CAGR / Sharpe 구현 금지
- realized_pnl_log.csv 생성 금지
- 누적 투입원금 기준 종목 수익률 구현 금지

## 테스트 추가

신규 테스트 파일 권장:

```text
tests/test_paper_position_snapshot.py
```

필수 테스트:

1. position snapshot row 생성
   - shares, avg_price, cost_value, close_price, market_value 검증

2. unrealized/realized/total PnL 계산
   - realized_pnl_by_symbol 반영
   - total_pnl = realized_pnl + unrealized_pnl

3. total_pnl_pct_on_current_cost 계산
   - total_pnl / cost_value

4. 같은 날짜 replace
   - 기존 같은 snapshot_date row 중복 없이 replace
   - archive backup 생성

5. 다른 날짜 row 유지

6. valuation failed 시 저장 skip 또는 명확한 처리
   - account snapshot은 깨지면 안 됨

7. dry-run smoke
   - 파일 변경 없음

8. commit smoke
   - `paper_position_snapshot.csv` 저장
   - outputs/front_test 변경 없음

## 검증 명령

```powershell
$env:PYTHONPATH="."
python -m pytest tests/test_paper_position_snapshot.py -q
python -m pytest tests/test_paper_account_snapshot.py -q
python -m pytest tests/test_paper_market_valuation.py -q
python -m pytest tests/test_paper_account_state.py -q
python -m py_compile core/paper_position_snapshot.py scripts/run_paper_eod_update.py
```

smoke:

```powershell
python scripts/run_paper_eod_update.py --date 20260509 --allow-empty-journal
python scripts/run_paper_eod_update.py --date 20260509 --allow-empty-journal --commit
```

오염 확인:

```powershell
git status --short outputs\paper_test outputs\front_test
git diff -- outputs\front_test
```

## 성공 기준

- `paper_position_snapshot.csv` 생성
- 종목별 cost / market value / unrealized PnL 저장
- 종목별 realized PnL 반영
- 종목별 total PnL 저장
- 같은 날짜 row replace / archive backup 정상
- dry-run에서 파일 변경 없음
- --commit에서만 저장
- market valuation failed 시 position snapshot 저장 실패가 전체 EOD를 중단하지 않음
- outputs/front_test 변경 없음
- DB 변경 없음
- benchmark / MDD / CAGR / Sharpe 미구현

## 결과 보고 형식

5,000자 이내로 작성한다.

포함할 항목:

1. Summary
2. 추가/변경 파일
3. position snapshot CSV 컬럼
4. 계산 정의
5. dry-run 결과
6. commit 결과
7. replace / archive 결과
8. 테스트 결과
9. 변경하지 않은 범위
10. 남은 한계 / 다음 단계

반드시 명시할 것:

- `paper_position_snapshot.csv` 생성 여부
- 실제 outputs/front_test 변경 여부
- DB 변경 여부
- market valuation failed 시 처리
- 누적 투입원금 기준 종목 수익률은 아직 구현하지 않았는지 여부
- benchmark / MDD / CAGR / Sharpe를 아직 구현하지 않았는지 여부
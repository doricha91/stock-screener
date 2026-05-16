# MFU-PAPER5-4 작업 지시문: realized PnL 구현

## 기준 정보

- 저장소: stock-screener
- 기준 최신 커밋 full SHA:
  301fa445a3b5b0e262763f75cabb489a58f064e1
- 선행 완료:
  - MFU-PAPER4-5: cost_basis 기준 paper_account_snapshot.csv 저장
  - MFU-PAPER5-2: DB daily_price.close 기반 valuation helper 구현
  - MFU-PAPER5-3: paper_account_snapshot.csv에 market value / unrealized PnL 연결

## 이번 작업 목적

paper 계좌에서 SELL 발생 시 realized PnL을 계산하고, `PaperAccountState`와 `paper_account_snapshot.csv`에 누적 realized PnL을 반영한다.

이번 단계는 performance report가 아니라, 성과 리포트의 기반이 되는 “실현손익 누적 상태” 구현이다.

## 확정 정책

1. 원가 계산 방식:
   - 평균단가 방식 사용
   - realized_pnl = (sell_price - avg_price) * sold_shares

2. 일부 매도 후 avg_price:
   - 남은 포지션의 avg_price는 유지

3. 전량 매도:
   - position 제거
   - realized PnL은 누적 유지

4. 저장 위치:
   - PaperAccountState에 누적 realized_pnl 추가
   - PaperAccountState에 realized_pnl_by_symbol 추가
   - paper_account_snapshot.csv에도 누적 realized_pnl 저장

5. 비용:
   - 수수료 / 슬리피지 / 세금은 계속 0
   - 이번 단계에서 비용 모델 추가 금지

## 구현 범위

### 1. core/paper_account_state.py 수정

`PaperAccountState`에 필드 추가:

```python
realized_pnl: float = 0.0
realized_pnl_by_symbol: dict[str, float] = field(default_factory=dict)
```

SELL 처리 로직 수정:

```text
sold_shares = abs(trade shares)
realized_pnl_delta = (sell_price - position.avg_price) * sold_shares
state.realized_pnl += realized_pnl_delta
state.realized_pnl_by_symbol[symbol] += realized_pnl_delta
cash += sell_price * sold_shares
position.shares -= sold_shares
```

주의:
- 보유 수량 초과 SELL은 기존처럼 error
- duplicate trade_id는 기존처럼 skip
- duplicate skip 시 realized_pnl이 다시 누적되면 안 됨
- BUY 로직은 realized_pnl을 변경하지 않음

### 2. core/paper_account_snapshot.py 수정

`paper_account_snapshot.csv`에 아래 컬럼 추가:

```text
realized_pnl
realized_pnl_by_symbol
total_pnl
total_pnl_pct
```

정의:

```text
realized_pnl
- PaperAccountState.realized_pnl 누적값

realized_pnl_by_symbol
- JSON string
- 예: {"CPAY": 120.5, "GEN": -30.0}

total_pnl
- realized_pnl + unrealized_pnl
- market valuation이 success일 때만 계산
- valuation failed면 빈 값

total_pnl_pct
- total_pnl / initial_cash
- market valuation이 success일 때만 계산
```

주의:
- unrealized_pnl은 MFU-PAPER5-3의 market valuation 결과를 사용
- market valuation failed일 때 realized_pnl은 저장하되, total_pnl / total_pnl_pct는 빈 값으로 둔다

### 3. scripts/run_paper_eod_update.py 확인

기존 흐름 유지:

```text
paper_execution_log.csv
→ PaperAccountState reducer
→ paper_current_state 저장
→ market valuation 시도
→ paper_account_snapshot.csv 저장
```

주의:
- realized_pnl은 reducer에서 계산되어야 함
- 별도 realized_pnl_log.csv는 이번 단계에서 만들지 않음
- performance report도 만들지 않음

## 절대 금지

- DB schema 변경 금지
- DB 파일 수정 금지
- outputs/front_test 수정 금지
- paper_execution_log 기존 row 수정 금지
- avg_price fallback 금지
- yfinance 실시간 호출 금지
- 수수료 / 슬리피지 / 세금 모델 추가 금지
- realized_pnl_log.csv 생성 금지
- performance report 생성 금지
- benchmark 비교 금지
- MDD / CAGR / Sharpe 구현 금지

## 테스트 추가/수정

### tests/test_paper_account_state.py

필수 테스트:

1. SELL realized PnL 계산
   - 10주 avg_price 100
   - 4주 120 매도
   - realized_pnl = 80
   - 남은 shares = 6
   - avg_price = 100 유지

2. 전량 매도
   - position 제거
   - realized_pnl 누적 유지

3. 손실 매도
   - avg_price 100
   - sell_price 80
   - realized_pnl 음수 확인

4. duplicate trade skip
   - 같은 SELL trade_id 재적용 시 realized_pnl 중복 누적 없음

5. realized_pnl_by_symbol 누적
   - 종목별 realized_pnl 정상 누적

### tests/test_paper_account_snapshot.py

필수 테스트:

1. snapshot row에 realized_pnl 저장
2. realized_pnl_by_symbol JSON string 저장
3. valuation success 시 total_pnl = realized_pnl + unrealized_pnl
4. valuation success 시 total_pnl_pct = total_pnl / initial_cash
5. valuation failed 시 realized_pnl은 저장하되 total_pnl / total_pnl_pct는 빈 값

## 검증 명령

PowerShell 기준:

```powershell
$env:PYTHONPATH="."
python -m pytest tests/test_paper_account_state.py -q
python -m pytest tests/test_paper_account_snapshot.py -q
python -m pytest tests/test_paper_market_valuation.py -q
python -m pytest tests/test_paper_current_state_storage.py -q
python -m pytest tests/test_paper_current_state_serializer.py -q
python -m py_compile core/paper_account_state.py core/paper_account_snapshot.py scripts/run_paper_eod_update.py
```

smoke:

```powershell
$env:PYTHONPATH="."
python scripts/run_paper_eod_update.py --date 20260509 --allow-empty-journal
python scripts/run_paper_eod_update.py --date 20260509 --allow-empty-journal --commit
```

## 성공 기준

- SELL 발생 시 realized_pnl 계산
- 일부 매도 후 avg_price 유지
- 전량 매도 시 position 제거
- duplicate SELL 재실행 시 realized_pnl 중복 누적 없음
- PaperAccountState에 realized_pnl / realized_pnl_by_symbol 저장
- paper_account_snapshot.csv에 realized_pnl 관련 컬럼 추가
- valuation success 시 total_pnl / total_pnl_pct 계산
- valuation failed 시 cost_basis + realized_pnl은 저장되고 total_pnl은 비움
- outputs/front_test 변경 없음
- DB 변경 없음
- performance report 미생성

## 결과 보고 형식

5,000자 이내로 작성한다.

포함할 항목:

1. Summary
2. 변경 파일
3. realized PnL 계산 정책
4. PaperAccountState 변경
5. snapshot CSV 변경
6. 테스트 결과
7. dry-run / commit smoke 결과
8. outputs/front_test 변경 여부
9. 남은 한계 / 다음 단계

반드시 명시할 것:

- 평균단가 방식 사용 여부
- 일부 매도 후 avg_price 유지 여부
- duplicate SELL 중복 누적 방지 여부
- 수수료 / 슬리피지 / 세금 미반영 여부
- realized_pnl_log.csv를 만들지 않았는지 여부
- performance report를 아직 만들지 않았는지 여부
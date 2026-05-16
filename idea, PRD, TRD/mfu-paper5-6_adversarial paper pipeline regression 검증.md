# MFU-PAPER5-6 작업 지시문: adversarial paper pipeline regression 검증

## 기준 정보

- 저장소: stock-screener
- 기준 최신 커밋 full SHA:
  301fa445a3b5b0e262763f75cabb489a58f064e1
- 선행 완료:
  - MFU-PAPER5-3: snapshot에 market value / unrealized PnL 연결
  - MFU-PAPER5-4: realized PnL 구현
  - MFU-PAPER5-5: SELL partial/full/loss/duplicate e2e 회귀 테스트 추가

## 이번 작업 목적

성과 리포트 구현 전에, 일부러 복잡한 paper 거래 시나리오를 만들어 현재 pipeline의 취약점을 찾는다.

이번 작업은 기능 추가가 아니라 regression/adversarial 검증이다.  
가능하면 production code 수정 없이 테스트를 추가한다.

## 검증 대상 흐름

```text
paper_execution_log rows
→ PaperAccountState reducer
→ current_state serializer
→ market valuation
→ paper_account_snapshot row
→ multi-day state consistency
```

## 절대 금지

- 실제 outputs/paper_test 수정 금지
- outputs/front_test 수정 금지
- 운영 DB / DB schema 수정 금지
- paper_execution_log 기존 committed row 수정 금지
- performance report 생성 금지
- benchmark / MDD / CAGR / Sharpe 구현 금지
- realized_pnl_log.csv 생성 금지
- 수수료 / 슬리피지 / 세금 모델 추가 금지

## 테스트 파일

신규 테스트 파일 권장:

```text
tests/test_paper_pipeline_adversarial.py
```

모든 파일/DB는 `tmp_path` 또는 workspace-local tmp fixture를 사용한다.  
실제 운영 output은 절대 사용하지 않는다.

## 필수 시나리오 1: multi-day BUY → partial SELL → BUY 재진입 → full SELL

거래 예시:

```text
2026-05-01 BUY  CPAY 10 @ 100
2026-05-02 SELL CPAY 4  @ 120
2026-05-03 BUY  CPAY 6  @ 90
2026-05-04 SELL CPAY 12 @ 110
```

검증:
- partial SELL 후 realized_pnl = 80
- partial SELL 후 shares = 6, avg_price = 100 유지
- 재진입 BUY 후 평균단가 재계산 확인
- full SELL 후 CPAY position 제거
- realized_pnl 누적값 검증
- cash 값 역산 검증
- current_symbols / shares / avg_price 정합성 검증

## 필수 시나리오 2: duplicate BUY/SELL 혼합

동일 trade_id를 가진 BUY/SELL을 중복으로 넣는다.

검증:
- duplicate BUY가 shares/cash/avg_price를 중복 변경하지 않음
- duplicate SELL이 cash/realized_pnl/shares를 중복 변경하지 않음
- applied_trade_ids 기준 skip 확인

## 필수 시나리오 3: valuation failure 격리

테스트용 SQLite daily_price DB에서 일부 보유 종목 가격을 의도적으로 누락한다.

검증:
- market valuation은 failed 처리
- market_valuation_error 저장
- cost_basis snapshot은 생성 가능
- realized_pnl은 저장됨
- total_pnl / total_pnl_pct는 빈 값
- avg_price fallback 없음

## 필수 시나리오 4: stale price 사용

snapshot_date 당일 가격은 없고, 과거 close만 있는 케이스를 만든다.

검증:
- 직전 available close 사용
- valuation_price_date 기록
- price_staleness_days 기록
- max_price_staleness_days 계산

## 필수 시나리오 5: snapshot invariant 검증

각 snapshot row에서 아래 invariant를 검증한다.

```text
positions_cost_value = sum(shares * avg_price)
total_equity_cost_basis = cash + positions_cost_value
cash_ratio_cost_basis = cash / total_equity_cost_basis
total_pnl = realized_pnl + unrealized_pnl  # valuation success일 때만
total_pnl_pct = total_pnl / initial_cash   # valuation success일 때만
```

current_state와 snapshot 간에도 검증한다.

```text
current_state.shares == reducer positions shares
current_state.avg_price == reducer positions avg_price
current_state.absolute_cash == reducer cash
```

## 테스트용 DB

테스트 안에서 임시 SQLite DB를 만든다.

```text
daily_price
- symbol
- date
- close
```

필요한 symbol/date/close만 삽입한다.  
운영 DB를 읽거나 수정하지 않는다.

## 실패 처리 원칙

문제가 발견되면 바로 production code를 크게 고치지 말고 먼저 분류한다.

분류:
1. 테스트 기대값 오류
2. reducer 계산 오류
3. snapshot row 계산 오류
4. valuation failure 처리 오류
5. duplicate 처리 오류
6. serializer 정합성 오류

작은 명백한 버그는 최소 수정 가능하되, 구조 변경이 필요하면 수정하지 말고 원인과 수정안을 결과 보고에 남긴다.

## 검증 명령

PowerShell 기준:

```powershell
$env:PYTHONPATH="."
python -m pytest tests/test_paper_pipeline_adversarial.py -q
python -m pytest tests/test_paper_sell_e2e.py -q
python -m pytest tests/test_paper_account_state.py -q
python -m pytest tests/test_paper_account_snapshot.py -q
python -m pytest tests/test_paper_market_valuation.py -q
python -m pytest tests/test_paper_current_state_storage.py -q
python -m pytest tests/test_paper_current_state_serializer.py -q
```

컴파일:

```powershell
python -m py_compile core/paper_account_state.py core/paper_account_snapshot.py core/paper_market_valuation.py scripts/run_paper_eod_update.py
```

오염 확인:

```powershell
git status --short outputs\paper_test outputs\front_test
git diff -- outputs\front_test
```

## 성공 기준

- multi-day BUY/SELL/재진입/full SELL 정합성 확인
- duplicate BUY/SELL 중복 반영 없음
- valuation failure 시 cost_basis snapshot 유지
- stale price 날짜/일수 기록 정상
- current_state와 snapshot의 cash/shares/avg_price 정합성 확인
- total_pnl 계산 invariant 통과
- 실제 outputs/paper_test 변경 없음
- outputs/front_test 변경 없음
- 운영 DB 변경 없음
- performance report 미생성

## 결과 보고 형식

5,000자 이내로 작성한다.

포함할 항목:

1. Summary
2. 추가/변경 파일
3. 검증한 adversarial 시나리오
4. multi-day BUY/SELL 결과
5. duplicate 검증 결과
6. valuation failure 검증 결과
7. stale price 검증 결과
8. snapshot invariant 검증 결과
9. 테스트 결과
10. 변경하지 않은 범위
11. 발견된 문제 / 남은 한계 / 다음 단계

반드시 명시할 것:

- 실제 outputs/paper_test를 수정했는지 여부
- outputs/front_test 변경 여부
- 운영 DB 변경 여부
- production code 수정 여부
- performance report를 만들지 않았는지 여부
# MFU-PAPER5-5 작업 지시문: SELL realized PnL end-to-end 검증

## 기준 정보

- 저장소: stock-screener
- 기준 최신 커밋 full SHA:
  301fa445a3b5b0e262763f75cabb489a58f064e1
- 선행 완료:
  - MFU-PAPER5-3: paper_account_snapshot.csv에 market value / unrealized PnL 연결
  - MFU-PAPER5-4: SELL realized PnL reducer 및 snapshot 연결 완료

## 이번 작업 목적

실제 운영 output을 오염시키지 않고, 테스트 전용 임시 환경에서 SELL end-to-end 흐름을 검증한다.

검증 대상 흐름:

```text
paper execution log
→ PaperAccountState reducer
→ SELL realized PnL 계산
→ paper_current_state 호환 상태 생성
→ paper_account_snapshot row 생성
→ duplicate SELL 재적용 방지
```

이번 단계는 기능 추가가 아니라 smoke/regression 검증 중심이다.

## 확정 정책

1. 실제 `outputs/paper_test`는 오염시키지 않는다.
2. `tmp_path` 기반 테스트 fixture를 사용한다.
3. 일부 매도, 전량 매도, 손실 매도, duplicate SELL을 모두 검증한다.
4. 가능하면 `run_paper_eod_update.py` 흐름까지 포함한다.
5. 새 기능 추가는 최소화한다.
6. performance report는 아직 만들지 않는다.

## 절대 금지

- 실제 `outputs/paper_test/paper_execution_log.csv` 수정 금지
- 실제 `outputs/paper_test/paper_account_snapshot.csv` 수정 금지
- outputs/front_test 수정 금지
- DB schema / DB files 수정 금지
- 기존 committed paper_execution_log row 수정 금지
- realized_pnl_log.csv 생성 금지
- performance report 생성 금지
- benchmark / MDD / CAGR / Sharpe 구현 금지
- 수수료 / 슬리피지 / 세금 모델 추가 금지

## 테스트 추가 권장

신규 테스트 파일 권장:

```text
tests/test_paper_sell_e2e.py
```

또는 기존 테스트 구조상 더 적절하면 `tests/test_paper_account_snapshot.py`에 추가해도 된다.  
다만 SELL end-to-end 의미가 명확하도록 별도 파일을 권장한다.

## 필수 시나리오

### 1. 일부 매도

초기 거래:

```text
BUY CPAY 10 @ 100
SELL CPAY 4 @ 120
```

기대값:

```text
realized_pnl = 80
realized_pnl_by_symbol = {"CPAY": 80}
remaining shares = 6
avg_price = 100 유지
cash 증가 = 4 * 120
position 유지
```

### 2. 전량 매도

초기 거래:

```text
BUY CPAY 10 @ 100
SELL CPAY 10 @ 110
```

기대값:

```text
realized_pnl = 100
CPAY position 제거
cash 증가 = 10 * 110
current_symbols에 CPAY 없음
```

### 3. 손실 매도

초기 거래:

```text
BUY GEN 10 @ 100
SELL GEN 5 @ 80
```

기대값:

```text
realized_pnl = -100
realized_pnl_by_symbol = {"GEN": -100}
remaining shares = 5
avg_price = 100 유지
```

### 4. duplicate SELL 방지

동일한 SELL trade_id를 다시 적용한다.

기대값:

```text
realized_pnl 중복 누적 없음
cash 중복 증가 없음
shares 중복 감소 없음
duplicates_skipped 증가 또는 applied_trade_ids 기준 skip
```

## end-to-end 검증 범위

가능하면 아래까지 검증한다.

```text
1. 테스트용 paper_execution_log.csv 생성
2. reducer로 PaperAccountState 생성
3. realized_pnl / realized_pnl_by_symbol 확인
4. paper_current_state serializer 결과 확인
5. paper_account_snapshot row 생성 확인
6. market valuation success 조건에서 total_pnl 계산 확인
7. duplicate SELL 재적용 시 상태 불변 확인
```

단, 실제 `outputs/paper_test`를 사용하지 않는다.  
필요한 파일은 모두 `tmp_path` 아래에 만든다.

## market valuation 처리

테스트용 SQLite DB 또는 mock DB를 사용한다.

권장:
- `tmp_path`에 테스트용 SQLite DB 생성
- `daily_price` 테이블 생성
- 필요한 symbol/date/close만 삽입
- 실제 운영 DB는 사용하지 않는다

예시:

```text
daily_price:
symbol | date       | close
CPAY   | 2026-05-10 | 120
GEN    | 2026-05-10 | 80
```

## 확인할 snapshot 값

snapshot row에서 아래를 확인한다.

```text
realized_pnl
realized_pnl_by_symbol
positions_market_value
total_equity_market_value
unrealized_pnl
total_pnl
total_pnl_pct
market_valuation_status
```

valuation success인 경우:

```text
total_pnl = realized_pnl + unrealized_pnl
total_pnl_pct = total_pnl / initial_cash
```

valuation failed 케이스는 이번 테스트의 필수는 아니지만, 기존 테스트가 깨지면 안 된다.

## 검증 명령

PowerShell 기준:

```powershell
$env:PYTHONPATH="."
python -m pytest tests/test_paper_sell_e2e.py -q
python -m pytest tests/test_paper_account_state.py -q
python -m pytest tests/test_paper_account_snapshot.py -q
python -m pytest tests/test_paper_market_valuation.py -q
python -m pytest tests/test_paper_current_state_storage.py -q
python -m pytest tests/test_paper_current_state_serializer.py -q
```

컴파일 확인:

```powershell
python -m py_compile core/paper_account_state.py core/paper_account_snapshot.py core/paper_market_valuation.py scripts/run_paper_eod_update.py
```

상태 확인:

```powershell
git status --short outputs\paper_test outputs\front_test
git diff -- outputs\front_test
```

## 성공 기준

아래 조건을 모두 만족하면 완료 처리한다.

- 일부 매도 realized PnL 계산 정상
- 일부 매도 후 avg_price 유지
- 전량 매도 후 position 제거
- 손실 매도 realized PnL 음수 계산 정상
- realized_pnl_by_symbol 정상 누적
- duplicate SELL 재적용 시 cash / shares / realized_pnl 불변
- snapshot row에 realized_pnl / total_pnl 반영
- 실제 outputs/paper_test 오염 없음
- outputs/front_test 변경 없음
- DB schema / 운영 DB 변경 없음
- performance report 미생성

## 결과 보고 형식

5,000자 이내로 작성한다.

포함할 항목:

1. Summary
2. 추가/변경 파일
3. 검증한 SELL 시나리오
4. 일부 매도 결과
5. 전량 매도 결과
6. 손실 매도 결과
7. duplicate SELL 검증 결과
8. snapshot / total_pnl 검증 결과
9. 테스트 결과
10. 변경하지 않은 범위
11. 남은 한계 / 다음 단계

반드시 명시할 것:

- 실제 outputs/paper_test를 수정했는지 여부
- outputs/front_test 변경 여부
- duplicate SELL 중복 누적 방지 여부
- realized_pnl_log.csv를 만들지 않았는지 여부
- performance report를 아직 만들지 않았는지 여부
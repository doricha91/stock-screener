# MFU-PAPER8-1 작업 지시문: paper performance input audit

## 목적

PAPER8 성과 리포팅을 시작하기 전에, `paper_account_snapshot.csv`와 `paper_position_snapshot.csv`가 equity curve / drawdown / performance summary 계산에 사용할 수 있는 상태인지 점검한다.

이번 MFU는 **감사/audit 전용**이다.  
성과 지표 계산, equity curve 생성, drawdown 계산은 아직 하지 않는다.

## 기준 브랜치

```text
gemini_cli_update
```

## 배경

PAPER8의 기본 방향:

```text
- primary equity: total_equity_market_value
- secondary equity: total_equity_cost_basis
- benchmark / Sharpe / CAGR은 아직 제외
- 먼저 snapshot 입력 데이터 품질을 점검
```

## 조사 대상 파일

```text
outputs/paper_test/paper_account_snapshot.csv
outputs/paper_test/paper_position_snapshot.csv
outputs/paper_test/paper_execution_log.csv
```

필요 시 참고:

```text
core/paper_account_state.py
core/paper_state_provider.py
scripts/run_paper_eod_update.py
```

## 점검 항목

### 1. account snapshot 컬럼 확인

`paper_account_snapshot.csv`에 아래 컬럼이 있는지 확인한다.

```text
snapshot_date
cash
positions_cost_value
total_equity_cost_basis
positions_market_value
total_equity_market_value
realized_pnl
unrealized_pnl
total_pnl
market_valuation_status
```

없거나 이름이 다르면 실제 컬럼명을 보고한다.

### 2. 날짜 품질 확인

확인할 것:

```text
- snapshot_date 형식
- 날짜 정렬 가능 여부
- 중복 snapshot_date 존재 여부
- 결측 날짜 존재 여부
- 최신 snapshot_date
- row 수
```

주의:

```text
결측 날짜는 반드시 오류는 아니다.
거래일/commit이 있는 날만 snapshot이 있을 수 있다.
```

### 3. 숫자 컬럼 품질 확인

확인할 것:

```text
- cash 숫자 변환 가능 여부
- total_equity_market_value 숫자 변환 가능 여부
- total_equity_cost_basis 숫자 변환 가능 여부
- realized_pnl / unrealized_pnl / total_pnl 숫자 변환 가능 여부
- NaN / blank / inf 존재 여부
- 음수 cash 존재 여부
- total_equity 값이 0 이하인 row 존재 여부
```

### 4. market valuation 상태 확인

`market_valuation_status` 분포를 확인한다.

예:

```text
success
missing_price
partial
failed
```

확인할 것:

```text
- success 외 상태가 있는지
- success가 아닌 row는 performance primary equity 계산에서 어떻게 처리해야 할지
- positions_market_value가 비어 있는데 success로 표시되는 경우가 있는지
```

### 5. cost basis vs market value 관계 확인

각 row에서 아래 관계를 검증한다.

```text
total_equity_cost_basis ≈ cash + positions_cost_value
total_equity_market_value ≈ cash + positions_market_value
total_pnl ≈ realized_pnl + unrealized_pnl
```

허용 오차는 소수점 반올림을 고려해 작게 둔다.

예:

```text
tolerance = 0.05
```

### 6. position snapshot 품질 확인

`paper_position_snapshot.csv`에서 확인할 것:

```text
snapshot_date
symbol
shares
avg_price
cost_basis
market_price
market_value
unrealized_pnl
unrealized_return_pct
position_status 또는 OPEN 상태 관련 컬럼
```

없거나 이름이 다르면 실제 컬럼명을 보고한다.

점검:

```text
- snapshot_date별 open position 수
- shares > 0인지
- symbol blank 여부
- 같은 snapshot_date + symbol 중복 여부
- market_value ≈ shares * market_price
- cost_basis ≈ shares * avg_price
```

### 7. account snapshot과 position snapshot 교차 확인

같은 snapshot_date 기준으로 비교한다.

```text
account.positions_cost_value
≈ sum(position.cost_basis)

account.positions_market_value
≈ sum(position.market_value)
```

허용 오차:

```text
tolerance = 0.05
```

### 8. execution log와 최신 snapshot 비교

최신 `paper_execution_log.csv`를 reducer로 계산한 최신 보유 상태와 최신 `paper_position_snapshot.csv`가 대략 일치하는지 확인한다.

확인할 것:

```text
- 최신 OPEN symbols
- shares
- avg_price
- cash
```

이번 단계에서는 불일치 원인을 깊게 수정하지 말고, 발견 사항만 보고한다.

## 구현 범위

권장 새 스크립트:

```text
scripts/audit_paper_performance_inputs.py
```

권장 산출물:

```text
outputs/paper_test/reports/paper_performance_input_audit.md
```

필요하면 CSV도 생성 가능:

```text
outputs/paper_test/reports/paper_performance_input_audit_issues.csv
```

## 절대 금지

```text
- paper_execution_log.csv 수정 금지
- paper_account_snapshot.csv 수정 금지
- paper_position_snapshot.csv 수정 금지
- outputs/front_test 수정 금지
- DB 수정 금지
- --commit 실행 금지
- equity curve 생성 금지
- drawdown / MDD 계산 금지
- benchmark / Sharpe / CAGR 구현 금지
- 대규모 리팩토링 금지
```

## 테스트

권장 테스트:

```text
tests/test_paper_performance_input_audit.py
```

필수 테스트:

```text
1. 필수 컬럼 누락 감지
2. 날짜 중복 감지
3. 숫자 변환 불가 값 감지
4. total_equity = cash + positions value 검증
5. account snapshot과 position snapshot 합계 불일치 감지
6. 정상 fixture에서는 issue 없음
```

## 검증 명령

```bat
set PYTHONPATH=.

python -m pytest tests/test_paper_performance_input_audit.py -q
python -m py_compile scripts/audit_paper_performance_inputs.py
```

가능하면 실제 audit 실행:

```bat
python scripts/audit_paper_performance_inputs.py
```

## 성공 기준

```text
- snapshot 입력 데이터 품질을 자동 점검할 수 있음
- audit markdown report 생성
- 필수 컬럼/날짜/숫자/valuation/합계 검증 결과가 포함됨
- account snapshot과 position snapshot 교차 검증 포함
- paper_execution_log / snapshots는 수정하지 않음
- outputs/front_test 변경 없음
```

## 결과 보고 형식

5천자 이내.

포함 항목:

```text
1. Summary
2. 변경 파일
3. 생성된 audit report 경로
4. account snapshot audit 결과
5. position snapshot audit 결과
6. account-position 교차 검증 결과
7. execution log 최신 상태 비교 결과
8. 발견된 issue 목록
9. 테스트 결과
10. 코드/데이터/output 변경 여부
11. 다음 단계 제안
```

반드시 명시:

```text
- snapshot 원본 CSV를 수정했는지 여부
- outputs/front_test를 수정했는지 여부
- PAPER8-2 equity curve 생성으로 넘어가도 되는지
```
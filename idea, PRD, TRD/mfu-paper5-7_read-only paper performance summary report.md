# MFU-PAPER5-7 작업 지시문: read-only paper performance summary report

## 기준 정보

- 저장소: stock-screener
- 기준 최신 커밋 full SHA:
  301fa445a3b5b0e262763f75cabb489a58f064e1
- 선행 완료:
  - MFU-PAPER5-3: paper_account_snapshot.csv에 market value / unrealized PnL 연결
  - MFU-PAPER5-4: realized PnL 구현
  - MFU-PAPER5-5: SELL realized PnL e2e 회귀 검증
  - MFU-PAPER5-6: adversarial paper pipeline regression 검증

## 이번 작업 목적

`outputs/paper_test/paper_account_snapshot.csv`를 read-only로 읽어 현재 paper 계좌의 요약 리포트를 생성한다.

이번 단계는 performance report의 “초안”이다.  
MDD, CAGR, Sharpe, benchmark 비교 같은 고급 지표는 아직 구현하지 않는다.

## 핵심 원칙

1. `paper_account_snapshot.csv`는 읽기만 한다.
2. 기존 snapshot CSV를 수정하지 않는다.
3. DB를 읽거나 수정하지 않는다.
4. 기존 paper_execution_log.csv를 수정하지 않는다.
5. outputs/front_test는 절대 수정하지 않는다.
6. report는 별도 파일로 생성한다.
7. 계산은 snapshot에 이미 저장된 컬럼만 사용한다.

## 생성 파일

권장 출력 경로:

```text
outputs/paper_test/paper_performance_summary.md
```

또는 날짜별 파일이 필요하면:

```text
outputs/paper_test/paper_performance_summary_YYYYMMDD.md
```

이번 단계에서는 우선 단일 파일 overwrite 방식을 권장한다.

## 구현 권장 파일

신규 파일:

```text
core/paper_performance_summary.py
```

신규 스크립트:

```text
scripts/generate_paper_performance_summary.py
```

권장 함수:

```python
load_paper_account_snapshots(snapshot_path: Path) -> list[dict]
```

```python
build_paper_performance_summary(rows: list[dict]) -> dict
```

```python
render_paper_performance_summary_markdown(summary: dict) -> str
```

```python
write_paper_performance_summary(markdown: str, output_path: Path) -> None
```

## 리포트에 포함할 항목

최신 snapshot 기준:

```text
snapshot_date
valuation_status
cash
position_count
symbols
positions_cost_value
positions_market_value
total_equity_cost_basis
total_equity_market_value
realized_pnl
unrealized_pnl
total_pnl
total_pnl_pct
cash_ratio_cost_basis
cash_ratio_market_value
valuation_price_date
max_price_staleness_days
```

전체 snapshot 기준:

```text
first_snapshot_date
latest_snapshot_date
snapshot_count
latest_total_pnl
latest_total_pnl_pct
latest_realized_pnl
latest_unrealized_pnl
latest_total_equity_market_value
```

## markdown 구성 예시

```markdown
# Paper Performance Summary

## Latest Snapshot

- Snapshot Date:
- Valuation Status:
- Cash:
- Position Count:
- Symbols:

## Equity / PnL

- Total Equity Cost Basis:
- Total Equity Market Value:
- Realized PnL:
- Unrealized PnL:
- Total PnL:
- Total PnL %:

## Valuation Quality

- Valuation Method:
- Valuation Price Date:
- Max Price Staleness Days:
- Market Valuation Error:

## Snapshot Coverage

- First Snapshot Date:
- Latest Snapshot Date:
- Snapshot Count:

## Notes

- This report is generated from paper_account_snapshot.csv only.
- Benchmark, MDD, CAGR, Sharpe are not included yet.
```

## 처리 정책

### valuation success인 경우

다음 값을 표시한다.

```text
total_equity_market_value
realized_pnl
unrealized_pnl
total_pnl
total_pnl_pct
cash_ratio_market_value
```

### valuation failed인 경우

- valuation status를 failed로 표시
- market_valuation_error를 표시
- total_pnl / total_pnl_pct가 비어 있으면 “N/A”로 표시
- report 생성 자체는 실패시키지 않는다

### 빈 snapshot 파일

- row가 없으면 명확한 error 발생
- 빈 report를 만들지 않는다

### 숫자 포맷

권장:

```text
금액: 소수점 2자리
비율: percent 형식 또는 소수점 4~6자리
빈 값: N/A
```

## 절대 금지

- paper_account_snapshot.csv 수정 금지
- paper_execution_log.csv 수정 금지
- paper_current_state_YYYYMMDD.json 수정 금지
- outputs/front_test 수정 금지
- DB schema / DB files 수정 금지
- benchmark 비교 구현 금지
- MDD / CAGR / Sharpe 구현 금지
- yfinance 호출 금지
- broker API 호출 금지
- realized_pnl_log.csv 생성 금지

## 테스트 추가

신규 테스트 파일 권장:

```text
tests/test_paper_performance_summary.py
```

필수 테스트:

1. latest snapshot summary 생성
   - 최신 날짜 row를 제대로 선택하는지 확인

2. valuation success report
   - total_equity_market_value
   - realized_pnl
   - unrealized_pnl
   - total_pnl
   - total_pnl_pct 표시 확인

3. valuation failed report
   - report 생성은 성공
   - failed status와 error 표시
   - total_pnl 비어 있으면 N/A 처리

4. empty snapshot error
   - row가 없으면 error

5. read-only 보장
   - 입력 snapshot 파일 내용이 변경되지 않는지 확인

## 검증 명령

PowerShell 기준:

```powershell
$env:PYTHONPATH="."
python -m pytest tests/test_paper_performance_summary.py -q
python -m pytest tests/test_paper_account_snapshot.py -q
python -m pytest tests/test_paper_market_valuation.py -q
python -m py_compile core/paper_performance_summary.py scripts/generate_paper_performance_summary.py
```

수동 실행:

```powershell
$env:PYTHONPATH="."
python scripts/generate_paper_performance_summary.py
```

오염 확인:

```powershell
git status --short outputs\paper_test outputs\front_test
git diff -- outputs\front_test
```

## 성공 기준

- paper_account_snapshot.csv를 read-only로 읽음
- paper_performance_summary.md 생성
- latest snapshot 기준 요약 표시
- valuation success / failed 모두 report 생성 가능
- 빈 snapshot은 명확히 error
- 기존 snapshot/log/current_state 파일 수정 없음
- outputs/front_test 변경 없음
- DB 변경 없음
- benchmark / MDD / CAGR / Sharpe 미구현

## 결과 보고 형식

5,000자 이내로 작성한다.

포함할 항목:

1. Summary
2. 추가/변경 파일
3. report 생성 위치
4. 포함한 요약 항목
5. valuation success 처리
6. valuation failed 처리
7. 테스트 결과
8. read-only 보장 여부
9. 변경하지 않은 범위
10. 남은 한계 / 다음 단계

반드시 명시할 것:

- paper_account_snapshot.csv를 수정했는지 여부
- outputs/front_test 변경 여부
- DB 변경 여부
- benchmark / MDD / CAGR / Sharpe를 아직 구현하지 않았는지 여부
- 다음 단계로 어떤 성과지표를 추가할지 제안
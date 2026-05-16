# MFU-PAPER4-5 작업 지시문: paper_account_snapshot.csv 저장

## 기준 정보

- 저장소: stock-screener
- 기준 최신 커밋 full SHA:
  301fa445a3b5b0e262763f75cabb489a58f064e1
- 선행 완료:
  - MFU-PAPER4-4C: paper_current_state_YYYYMMDD.json 저장 연결
  - MFU-PAPER4-4D: dry-run/commit 재실행, duplicate skip, archive backup, loader round-trip smoke 검증 완료

## 이번 작업의 목적

`paper_execution_log.csv`를 source of truth로 사용해 `PaperAccountState`를 reducer로 재계산하고, 그 결과를 계좌 단위 cost-basis snapshot으로 `outputs/paper_test/paper_account_snapshot.csv`에 저장한다.

이번 단계는 성과 리포트가 아니라 “paper 계좌의 일별 비용기준 상태 기록”을 만드는 단계다.

## 확정된 정책

1. snapshot 목적:
   - 계좌 단위 cost-basis snapshot

2. 저장 시점:
   - `run_paper_eod_update.py --commit` 이후에만 CSV 저장
   - dry-run에서는 snapshot preview만 출력하고 파일 저장 금지

3. 평가 기준:
   - market value 제외
   - cost basis만 사용

4. 중복 날짜 처리:
   - 같은 snapshot_date row가 이미 있으면 기존 `paper_account_snapshot.csv`를 archive로 백업
   - 이후 해당 날짜 row만 replace
   - 다른 날짜 row는 유지

5. source of truth:
   - `outputs/paper_test/paper_execution_log.csv`
   - reducer: `build_paper_state_from_trades()` 또는 기존 PaperAccountState reducer 계열 사용

6. 이번 단계 제외:
   - unrealized PnL
   - total market equity
   - market value revaluation
   - paper_performance_report
   - benchmark 비교
   - MDD / CAGR / Sharpe 등 성과지표

## 절대 금지

- outputs/front_test/ 수정 금지
- scripts/run_eod_update.py 수정 금지
- DB schema / DB files 수정 금지
- 기존 committed paper_execution_log row 수정 금지
- 이미 commit된 trade의 Reason / trade_id 변경 금지
- market price revaluation 구현 금지
- unrealized PnL 계산 금지
- performance report 생성 금지
- position sizing, strategy, data_collector 로직 수정 금지

## 구현 권장 구조

### 1. 신규 helper 추가 권장

가능하면 아래 파일을 새로 만든다.

```text
core/paper_account_snapshot.py
```

권장 함수:

```python
build_paper_account_snapshot_row(
    state: PaperAccountState,
    snapshot_date: str,
    initial_cash: float = 100000.0,
    source_execution_log: str | None = None,
    source_current_state: str | None = None,
) -> dict
```

```python
save_paper_account_snapshot(
    snapshot_row: dict,
    snapshot_path: Path,
    archive_dir: Path,
) -> dict
```

역할:
- snapshot row 생성
- 기존 CSV가 있으면 읽기
- 같은 snapshot_date row가 있으면 기존 CSV를 archive로 백업
- 같은 날짜 row replace
- 다른 날짜 row 유지
- snapshot_date 기준 정렬 후 저장
- 저장 경로가 반드시 outputs/paper_test/ 아래인지 `assert_paper_path()`로 검증

### 2. CSV 저장 경로

기존 path helper가 있으면 사용한다.

```text
outputs/paper_test/paper_account_snapshot.csv
```

archive 위치:

```text
outputs/paper_test/archive/
```

백업 파일명 예시:

```text
paper_account_snapshot_20260509_YYYYMMDD_HHMMSS_backup.csv
```

## CSV 컬럼 정의

이번 단계의 최소 컬럼은 아래로 고정한다.

```text
snapshot_date
currency
initial_cash
cash
positions_cost_value
total_equity_cost_basis
cash_ratio_cost_basis
position_count
symbols
applied_trade_count
valuation_method
source_execution_log
source_current_state
created_at
```

### 컬럼 정의

```text
snapshot_date
- 대상 EOD 날짜
- 예: 2026-05-09

currency
- 현재는 USD

initial_cash
- 현재 paper policy 기준 100000.0

cash
- PaperAccountState.cash

positions_cost_value
- sum(shares * avg_price)

total_equity_cost_basis
- cash + positions_cost_value

cash_ratio_cost_basis
- cash / total_equity_cost_basis
- total_equity_cost_basis가 0이면 저장 중단 또는 명시적 error

position_count
- 보유 종목 수

symbols
- 보유 symbol 목록
- CSV 안정성을 위해 CPAY|GEN|VRSN 형태 권장
- 정렬된 symbol 기준

applied_trade_count
- len(state.applied_trade_ids)

valuation_method
- "cost_basis" 고정

source_execution_log
- outputs/paper_test/paper_execution_log.csv

source_current_state
- outputs/paper_test/paper_current_state_YYYYMMDD.json

created_at
- snapshot 생성 시각
```

## run_paper_eod_update.py 연결

기존 흐름을 유지하면서 `--commit` 이후에만 snapshot 저장을 연결한다.

권장 흐름:

```text
1. daily action plan parse
2. paper trade preview 생성
3. --commit이면 paper_execution_log append 또는 duplicate skip
4. 최신 paper_execution_log.csv를 읽어 PaperAccountState 재계산
5. paper_current_state_YYYYMMDD.json 저장
6. paper_account_snapshot row 생성
7. --commit이면 paper_account_snapshot.csv 저장
8. dry-run이면 snapshot preview만 출력
```

주의:
- `paper_execution_log.csv`에 새 row가 append되지 않아도, `--commit`이면 snapshot 저장은 수행할 수 있다.
- 같은 날짜 snapshot이 이미 있으면 archive 백업 후 replace한다.
- dry-run에서는 절대 CSV를 생성하거나 수정하지 않는다.

## 테스트 추가

새 테스트 파일 권장:

```text
tests/test_paper_account_snapshot.py
```

필수 테스트:

1. snapshot row 계산 테스트
   - cash
   - positions_cost_value
   - total_equity_cost_basis
   - cash_ratio_cost_basis
   - position_count
   - symbols
   - applied_trade_count

2. empty position 테스트
   - positions 없음
   - positions_cost_value = 0
   - total_equity_cost_basis = cash
   - cash_ratio_cost_basis = 1.0

3. 같은 날짜 replace 테스트
   - 기존 CSV에 같은 snapshot_date가 있을 때
   - archive 백업 생성
   - row 중복 없이 replace

4. 다른 날짜 유지 테스트
   - 기존 다른 날짜 row는 보존

5. paper path safety 테스트
   - outputs/paper_test 밖 저장 시 error

6. dry-run smoke
   - `run_paper_eod_update.py` dry-run에서 snapshot 파일 변경 없음

7. commit smoke
   - `--commit`에서 snapshot 저장
   - 재실행 시 같은 날짜 row replace
   - archive backup 생성

## 검증 명령

PowerShell 기준:

```powershell
$env:PYTHONPATH="."
python -m pytest tests/test_paper_account_state.py -q
python -m pytest tests/test_paper_current_state_serializer.py -q
python -m pytest tests/test_paper_current_state_storage.py -q
python -m pytest tests/test_paper_account_snapshot.py -q
python -m py_compile scripts/run_paper_eod_update.py core/paper_account_snapshot.py
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

아래 조건을 모두 만족하면 완료 처리한다.

- dry-run에서 `paper_account_snapshot.csv` 생성/수정 없음
- dry-run에서 snapshot preview는 출력됨
- `--commit`에서 `paper_account_snapshot.csv` 저장됨
- 같은 날짜 재실행 시 row 중복 없이 replace됨
- replace 전 기존 snapshot CSV가 archive로 백업됨
- `positions_cost_value`, `total_equity_cost_basis`, `cash_ratio_cost_basis` 계산이 cost basis 기준으로 정확함
- market value / unrealized PnL / performance report 관련 컬럼 또는 계산이 없음
- outputs/front_test 변경 없음
- DB / strategy / sizing / collector 변경 없음
- 관련 pytest 통과

## 결과 보고 형식

결과 보고는 5,000자 이내로 작성한다.

포함할 항목:

1. Summary
2. 변경 파일
3. snapshot CSV 컬럼
4. dry-run 결과
5. commit 결과
6. 같은 날짜 replace / archive backup 결과
7. 계산 검증 결과
8. 테스트 결과
9. outputs/front_test 변경 여부
10. 남은 한계 / 다음 단계

반드시 명시할 것:

- `paper_account_snapshot.csv` 생성 여부
- 같은 날짜 row 중복 여부
- archive backup 파일명
- snapshot 기준이 cost_basis임
- market value, unrealized PnL, performance report는 아직 제외했음
# Codex Task: MFU-PAPER4-3B Clean Paper Log Preview 검증

## 목표

초기화된 `outputs/paper_test/paper_execution_log.csv`에서 정식 paper trade를 새로 append한 뒤, `run_paper_eod_update.py`가 paper account preview를 정상 계산하는지 확인한다.

현재 상태:

- 기존 테스트성 paper log는 archive로 백업됨
- 현재 `paper_execution_log.csv`는 header-only 상태
- 초기 paper cash는 $100,000
- `run_paper_eod_update.py`는 paper_execution_log.csv를 읽어 account preview를 출력할 수 있음

이번 작업은 **검증 중심**이다.

## 변경 범위

가능하면 production code는 수정하지 않는다.

예상 변경:

```text
없음
```

필요 시 테스트 추가:

```text
tests/test_paper_clean_log_preview_flow.py
```

수정 금지:

```text
scripts/run_eod_update.py
core/paper_account_state.py
core/paper_execution_log.py
DB files
outputs/front_test/*
paper_current_state_*.json
paper_account_snapshot.csv
paper_performance_report_*.md
```

## 작업 내용

### 1. 현재 paper log 상태 확인

아래 파일이 header-only인지 확인한다.

```text
outputs/paper_test/paper_execution_log.csv
```

기대:

```text
trade_id,date,regime,symbol,side,shares,price,gross_amount,source,status,reason,notes,rec_shares,rec_price,created_at
```

데이터 row가 없어야 한다.

### 2. 정식 paper trade 후보 확인

`outputs/front_test/daily_action_plan_YYYYMMDD.md`에서 READY_FOR_PAPER_TRADE row가 있는지 확인한다.

기준 날짜는 현재 테스트에 적합한 날짜를 사용한다.  
기존 검증 날짜가 있으면 우선 사용한다.

예:

```powershell
$env:PYTHONPATH="."; python scripts/run_paper_eod_update.py --date 20260507 --allow-empty-journal
```

이 단계는 dry-run이어야 한다.

확인할 것:

- paper execution preview가 출력되는지
- rows_to_append 또는 ready_previews가 있는지
- account preview가 empty log 기준으로 안전하게 출력되는지
- write가 발생하지 않는지

### 3. commit 실행

READY_FOR_PAPER_TRADE row가 있고, 초기 cash $100,000 기준으로 가능한 거래라면 commit을 실행한다.

```powershell
$env:PYTHONPATH="."; python scripts/run_paper_eod_update.py --date YYYYMMDD --allow-empty-journal --commit
```

확인할 것:

- `paper_execution_log.csv`에 row가 append됨
- duplicate trade_id 방지 유지
- append 후 account preview가 정상 계산됨
- cash가 감소 또는 증가함
- positions가 정상 표시됨
- `paper_current_state_*.json`은 생성되지 않음

### 4. 같은 commit 재실행

같은 명령을 한 번 더 실행한다.

기대:

```text
rows_appended: 0
duplicates_skipped: 1 이상
account preview는 동일
```

중복 거래가 다시 반영되면 안 된다.

## 실패 시 처리

### 현금 부족 거래가 나오면

예:

```text
insufficient cash for BUY
```

이 경우 production code를 고치지 말고 원인을 보고한다.

보고할 것:

```text
- Symbol
- Shares
- Price
- Required cash
- Initial cash
- 해당 row가 MFU-PS1 이후 정상 sizing인지
- journal Act_Shares가 수동으로 과대 입력된 것인지
```

### READY_FOR_PAPER_TRADE가 없으면

commit하지 않는다.

보고할 것:

```text
- 대상 daily_action_plan 날짜
- ready_previews 수
- pending_actual_fill 수
- 왜 commit을 하지 않았는지
```

## 하지 말 것

이번 작업에서 금지:

```text
paper_current_state_*.json 생성
paper_account_snapshot.csv 생성
paper_performance_report 생성
outputs/front_test 수정
DB schema 수정
paper reducer 로직 수정
position sizing 수정
data collector 수정
```

## 검증 명령

```powershell
$env:PYTHONPATH="."; python -m pytest tests/test_paper_account_state.py -q
$env:PYTHONPATH="."; python -m pytest tests/test_paper_account_preview.py -q
$env:PYTHONPATH="."; python -m py_compile scripts/run_paper_eod_update.py
$env:PYTHONPATH="."; python scripts/run_paper_eod_update.py --date YYYYMMDD --allow-empty-journal
```

READY_FOR_PAPER_TRADE가 있고 거래 가능하면:

```powershell
$env:PYTHONPATH="."; python scripts/run_paper_eod_update.py --date YYYYMMDD --allow-empty-journal --commit
$env:PYTHONPATH="."; python scripts/run_paper_eod_update.py --date YYYYMMDD --allow-empty-journal --commit
```

## 완료 기준

1. header-only paper log에서 시작했음을 확인한다.
2. dry-run이 정상 동작한다.
3. 가능한 거래가 있을 경우 `--commit`으로 paper log append가 정상 수행된다.
4. append 후 account preview가 정상 계산된다.
5. 같은 commit 재실행 시 duplicate로 skip된다.
6. `paper_current_state_*.json`은 생성되지 않는다.
7. `outputs/front_test/`는 변경되지 않는다.
8. 실패 시 원인을 명확히 보고한다.

## 보고 형식

```text
1. Summary
2. Paper log initial state
3. Dry-run result
4. Commit result
5. Duplicate re-run result
6. Account preview result
7. Files changed under outputs/paper_test
8. Files intentionally not changed
9. Risks and limitations
10. Suggested next step
```
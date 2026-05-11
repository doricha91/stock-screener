# MFU-PAPER3: PaperTradePreview를 paper_execution_log.csv에 append

## 목적

`run_paper_eod_update.py`에서 생성한 `PaperTradePreview`를 `outputs/paper_test/paper_execution_log.csv`에 append할 수 있게 한다.

이번 단계에서는 **paper execution log 저장만 추가**한다.

아직 paper current state, paper account snapshot, paper performance는 구현하지 않는다.

---

## 현재 상태

MFU-PAPER2까지 완료된 내용:

- `outputs/paper_test/` 경로 분리 완료
- `run_paper_eod_update.py`가 front-test action plan journal을 read-only로 파싱
- `READY_FOR_PAPER_TRADE` row를 `PaperTradePreview`로 변환
- preview summary/table 출력
- 현재까지는 어떤 paper/live 파일도 write하지 않음

---

# 핵심 원칙

1. 기본 실행은 dry-run이다.
2. 실제 append는 `--commit` 옵션이 있을 때만 수행한다.
3. write 대상은 오직 `outputs/paper_test/paper_execution_log.csv`다.
4. live/front-test 파일은 절대 수정하지 않는다.
5. `scripts/run_eod_update.py`는 수정하지 않는다.
6. paper current state는 이번 단계에서 만들지 않는다.
7. paper account cash/holding 계산도 이번 단계에서 하지 않는다.

---

# 작업 범위

## 1. paper execution log helper 추가

신규 파일:

```text
core/paper_execution_log.py
```

추가할 함수:

```python
def paper_trade_preview_to_row(preview: PaperTradePreview) -> dict:
    ...

def build_paper_trade_id(row: dict) -> str:
    ...

def append_paper_execution_log(
    previews: list[PaperTradePreview],
    log_path: Path,
    commit: bool = False,
) -> tuple[list[dict], list[str]]:
    ...
```

---

## 2. CSV row 구조

`paper_execution_log.csv` 컬럼은 최소 아래처럼 한다.

```text
trade_id
date
regime
symbol
side
shares
price
gross_amount
source
status
reason
notes
rec_shares
rec_price
created_at
```

필드 규칙:

- `trade_id`: 중복 append 방지용 deterministic id
- `shares`: BUY는 양수, SELL은 음수
- `gross_amount = shares * price`
- `source = journal_actual_fill`
- `status = READY_FOR_PAPER_TRADE`
- `created_at`: append 시점 timestamp

---

## 3. trade_id 규칙

동일 실행을 여러 번 해도 같은 거래가 중복 저장되지 않도록 한다.

권장 방식:

```python
trade_id_source = "|".join([
    date,
    symbol,
    side,
    str(shares),
    f"{price:.6f}",
    reason,
    source,
])
```

이를 SHA256 또는 안정적인 hash로 변환한다.

주의:

- 같은 날짜, 같은 종목, 같은 side라도 수량/가격이 다르면 다른 trade_id가 되어야 한다.
- 완전히 같은 row를 재실행하면 중복 append하지 않는다.

---

## 4. append 동작

`append_paper_execution_log()` 동작:

1. preview list를 row list로 변환
2. 기존 `paper_execution_log.csv`가 있으면 읽기
3. 기존 `trade_id`와 비교
4. 신규 row만 append 대상
5. `commit=False`면 실제 파일 write 없이 append 예정 row만 반환
6. `commit=True`면 `outputs/paper_test/paper_execution_log.csv`에 append
7. write 전 `assert_paper_path()`로 paper root 검증
8. 변환/중복/skip 정보는 warnings에 기록

반환:

```python
rows_to_append, warnings
```

예시 warning:

```text
Skipping duplicate paper trade: CRL BUY 10000 @ 191.47
No READY_FOR_PAPER_TRADE previews to append
```

---

## 5. run_paper_eod_update.py에 --commit 추가

파일:

```text
scripts/run_paper_eod_update.py
```

옵션 추가:

```powershell
--commit
```

동작:

### 기본 dry-run

```powershell
python scripts/run_paper_eod_update.py --date 20260507 --allow-empty-journal
```

- preview 생성
- append 예정 row 출력
- 실제 csv write 없음

출력 예시:

```text
Paper execution log:
  mode: DRY-RUN
  log_path: outputs/paper_test/paper_execution_log.csv
  ready_previews: 1
  rows_to_append: 1
  duplicates_skipped: 0
  write_performed: False
```

### commit 실행

```powershell
python scripts/run_paper_eod_update.py --date 20260507 --allow-empty-journal --commit
```

- `paper_execution_log.csv`에 신규 row append
- 중복 trade_id는 append하지 않음

출력 예시:

```text
Paper execution log:
  mode: COMMIT
  log_path: outputs/paper_test/paper_execution_log.csv
  ready_previews: 1
  rows_appended: 1
  duplicates_skipped: 0
  write_performed: True
```

---

## 6. 절대 하지 말 것

이번 작업에서 금지:

- `paper_current_state_*.json` 생성/수정
- `paper_account_snapshot.csv` 생성/수정
- `paper_performance_report_*.md` 생성/수정
- `outputs/front_test/` 아래 파일 수정
- `outputs/front_test/execution_log.csv` 수정
- `scripts/run_eod_update.py` 수정
- `update_portfolio_state_after_close()` 호출
- `append_to_execution_log()` 호출
- `PerformanceTracker.update_performance()` 호출
- paper cash/holding/account 계산
- position sizing 동기화 작업 포함

---

# 테스트

신규 테스트 파일:

```text
tests/test_paper_execution_log.py
```

필수 테스트:

## 1. PaperTradePreview를 CSV row로 변환

- BUY preview 입력
- 기대:
  - side == BUY
  - shares 양수
  - gross_amount 양수
  - trade_id 존재

## 2. SELL preview 변환

- SELL preview 입력
- 기대:
  - shares 음수
  - gross_amount 음수

## 3. dry-run은 파일을 만들지 않음

```python
append_paper_execution_log(previews, log_path, commit=False)
```

기대:

- rows_to_append 반환
- log_path 파일 생성 안 됨

## 4. commit=True면 csv 생성

```python
append_paper_execution_log(previews, log_path, commit=True)
```

기대:

- csv 생성
- row 1개 저장

## 5. 같은 preview 재실행 시 중복 append 방지

1차 commit 후 같은 preview로 2차 commit.

기대:

- csv row 수 그대로
- duplicate warning 발생

## 6. paper path 밖이면 차단

`log_path`를 `outputs/front_test/execution_log.csv` 같은 경로로 주면 실패해야 한다.

---

# 검증 명령

```powershell
$env:PYTHONPATH="."; python -m pytest tests/test_paper_paths.py -q
$env:PYTHONPATH="."; python -m pytest tests/test_paper_journal_preview.py -q
$env:PYTHONPATH="."; python -m pytest tests/test_paper_trade_preview.py -q
$env:PYTHONPATH="."; python -m pytest tests/test_paper_execution_log.py -q
$env:PYTHONPATH="."; python -m py_compile core/paper_execution_log.py scripts/run_paper_eod_update.py
$env:PYTHONPATH="."; python scripts/run_paper_eod_update.py --date 20260507 --allow-empty-journal
```

실제 write 검증은 조심해서 실행한다.

```powershell
$env:PYTHONPATH="."; python scripts/run_paper_eod_update.py --date 20260507 --allow-empty-journal --commit
```

`--commit` 실행 후 확인:

```text
outputs/paper_test/paper_execution_log.csv 생성 또는 append
outputs/front_test/ 아래 파일 변경 없음
```

전체 테스트는 기존 import 문제가 있을 수 있으므로 실행한다면 결과를 분리해서 보고한다.

```powershell
$env:PYTHONPATH="."; python -m pytest tests -q
```

---

# Acceptance Criteria

완료 조건:

1. `core/paper_execution_log.py` 추가
2. `paper_trade_preview_to_row()` 추가
3. `append_paper_execution_log()` 추가
4. `run_paper_eod_update.py`에 `--commit` 옵션 추가
5. 기본 실행은 dry-run이며 파일을 쓰지 않음
6. `--commit` 실행 시 `outputs/paper_test/paper_execution_log.csv`에만 append
7. 중복 `trade_id`는 재실행해도 중복 저장되지 않음
8. paper path 밖 write는 차단됨
9. live/front-test 파일은 수정되지 않음
10. `scripts/run_eod_update.py`는 수정되지 않음
11. 신규 테스트가 통과함

---

# 보고 형식

작업 완료 후 아래 형식으로 보고한다.

```text
1. Summary
2. Changed files
3. Behavior changes
4. Tests run
5. Tests not run and why
6. Risks and limitations
7. Suggested next step
```

특히 다음을 명확히 보고한다.

- 기본 실행이 dry-run인지
- `--commit`에서만 write하는지
- write 대상이 `outputs/paper_test/paper_execution_log.csv`뿐인지
- duplicate 방지가 동작하는지
- live/front-test 경로가 오염되지 않았는지
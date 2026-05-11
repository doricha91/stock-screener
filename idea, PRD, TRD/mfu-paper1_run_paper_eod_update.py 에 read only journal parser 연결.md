# MFU-PAPER1: run_paper_eod_update.py에 read-only journal parser 연결

## 목적

`scripts/run_paper_eod_update.py`가 기존 front-test action plan을 읽고, journal/action 후보를 read-only로 파싱하여 paper trade preview를 출력하도록 한다.

이번 작업은 **read-only 단계**다.

paper state 생성, paper execution log 저장, paper account snapshot 저장은 아직 하지 않는다.

---

## 기준 상태

MFU-PAPER0에서 완료된 내용:

- `outputs/paper_test/` 전용 경로 추가
- `core/paths.py`에 paper path helper 추가
- `core/paper_safety.py`에 `assert_paper_path()` 추가
- `scripts/run_paper_eod_update.py` dry-run 골격 추가
- 기존 `scripts/run_eod_update.py`는 수정하지 않음
- 현재 paper script는 실제 write를 하지 않음

이번 MFU-PAPER1에서도 기존 live/front-test write 경로는 건드리지 않는다.

---

# 작업 범위

## 1. run_paper_eod_update.py에 journal parser read-only 연결

파일:

- `scripts/run_paper_eod_update.py`

기존 dry-run 구조를 유지하되, 입력 report가 존재하면 journal/action 정보를 read-only로 파싱한다.

기본 입력 report:

```text
outputs/front_test/daily_action_plan_YYYYMMDD.md
```

지원 날짜 형식:

```text
--date 20260507
--date 2026-05-07
```

---

## 2. 기존 execution_logger의 parser를 재사용하되 write 함수는 호출하지 않기

가능하면 기존 함수를 재사용한다.

대상 함수:

```python
from core.execution_logger import parse_journal_from_markdown, map_journal_to_trades
```

주의:

- `append_to_execution_log()`는 절대 호출하지 않는다.
- `update_portfolio_state_after_close()`는 절대 호출하지 않는다.
- `PerformanceTracker.update_performance()`는 절대 호출하지 않는다.
- `paper_execution_log.csv`도 이번 단계에서는 쓰지 않는다.
- `paper_current_state_YYYYMMDD.json`도 이번 단계에서는 쓰지 않는다.

---

## 3. read-only parsing 동작 정의

`run_paper_eod_update.py`는 다음 순서로 동작한다.

1. `--date` 인자 파싱
2. `outputs/front_test/daily_action_plan_YYYYMMDD.md` 경로 계산
3. paper output 경로 계산
4. 모든 paper output 경로가 `outputs/paper_test/` 아래인지 `assert_paper_path()`로 검증
5. input report 존재 여부 확인
6. journal parser read-only 실행
7. parsed journal rows 요약 출력
8. paper trade preview 출력
9. 실제 write 없이 종료

---

## 4. parsing 실패 처리

현재 `parse_journal_from_markdown()`은 `Act_Shares`, `Act_Price`, `Reason`이 비어 있으면 `ValueError`를 발생시킬 수 있다.

paper-test 초기에는 아직 실제 체결값이 없을 수 있으므로, 이번 단계에서는 다음 옵션을 추가한다.

```powershell
--allow-empty-journal
```

동작:

### 기본값

기본값은 엄격 모드다.

```powershell
python scripts/run_paper_eod_update.py --date 20260507
```

- journal 필수값이 비어 있으면 parser error를 출력하고 종료한다.
- 단, 어떤 파일도 쓰지 않는다.

### allow-empty-journal 모드

```powershell
python scripts/run_paper_eod_update.py --date 20260507 --allow-empty-journal
```

- 기존 parser가 실패하면 fallback parser를 사용한다.
- fallback parser는 journal table을 read-only로 읽되, 빈 Act 필드를 허용한다.
- 이 경우 actual trade가 아니라 “pending paper trade candidate”로 표시한다.

---

## 5. fallback parser 추가

파일:

- `scripts/run_paper_eod_update.py`

또는 helper 파일:

- `core/paper_journal_parser.py`

작게 시작하려면 `scripts/run_paper_eod_update.py` 내부 private helper로 구현한다.

권장 함수:

```python
def parse_journal_preview_from_markdown(report_path: Path) -> list[dict]:
    ...
```

역할:

- `daily_action_plan_YYYYMMDD.md`에서 journal table을 찾는다.
- 행을 dict로 변환한다.
- 빈 `Act_Shares`, `Act_Price`, `Reason`을 허용한다.
- `WARNING_*`, `REVIEW_*`는 paper trade candidate로 취급하지 않는다.
- `Type`이 `BUY` 또는 `SELL`인 행만 candidate로 본다.

반환 dict 예시:

```python
{
    "date": "2026-05-07",
    "regime": "BULL",
    "symbol": "AAPL",
    "type": "BUY",
    "rec_shares": "10",
    "rec_price": "185.20",
    "act_shares": "",
    "act_price": "",
    "reason": "",
    "notes": "",
    "status": "PENDING_ACTUAL_FILL"
}
```

만약 Act 필드가 모두 채워져 있으면:

```python
"status": "READY_FOR_PAPER_TRADE"
```

---

## 6. paper trade preview 출력

`run_paper_eod_update.py` 실행 시 다음 정보를 출력한다.

예시:

```text
PAPER EOD UPDATE - READ ONLY PREVIEW

Input report:
  outputs/front_test/daily_action_plan_20260507.md

Paper outputs:
  outputs/paper_test/paper_current_state_20260507.json
  outputs/paper_test/paper_execution_log.csv
  outputs/paper_test/paper_account_snapshot.csv

Journal preview:
  total_rows: 2
  ready_for_paper_trade: 1
  pending_actual_fill: 1
  skipped_review_or_warning: 0

Trade candidates:
| Symbol | Type | Rec_Shares | Rec_Price | Act_Shares | Act_Price | Status |
| AAPL   | BUY  | 10         | 185.20    | 10         | 185.30    | READY_FOR_PAPER_TRADE |
| TSLA   | SELL | 3          | 240.00    |            |           | PENDING_ACTUAL_FILL |

Status:
  path separation OK
  read-only parser OK
  no paper files were written
  no live/front-test files were written
  paper account calculation is not implemented in MFU-PAPER1
```

---

## 7. map_journal_to_trades는 조건부 preview로만 사용

기존 엄격 parser가 성공하고 모든 Act 필드가 채워진 경우에만:

```python
map_journal_to_trades(journal_entries)
```

를 호출해서 trade preview를 출력할 수 있다.

주의:

- 이 결과를 저장하지 않는다.
- state update에 사용하지 않는다.
- console preview만 출력한다.

예시 출력:

```text
Mapped trade preview:
  BUY AAPL shares=10 price=185.3
  SELL TSLA shares=-3 price=240.1
```

---

## 8. 절대 하지 말 것

이번 작업에서 하지 말 것:

1. `outputs/paper_test/paper_current_state_YYYYMMDD.json` 생성
2. `outputs/paper_test/paper_execution_log.csv` 생성 또는 수정
3. `outputs/paper_test/paper_account_snapshot.csv` 생성 또는 수정
4. `outputs/front_test/current_state_YYYYMMDD.json` 수정
5. `outputs/front_test/execution_log.csv` 수정
6. `scripts/run_eod_update.py` 수정
7. `core/portfolio_state_manager.py` 수정
8. `update_portfolio_state_after_close()` 호출
9. `append_to_execution_log()` 호출
10. `PerformanceTracker.update_performance()` 호출
11. 실제 paper account 계산 구현
12. position sizing 동기화 작업 포함

---

# 테스트 추가

## 신규 테스트 파일

```text
tests/test_paper_journal_preview.py
```

## 테스트 케이스

### 1. journal preview parser가 BUY/SELL 행을 읽는다

임시 markdown 파일을 만들고 journal table을 넣는다.

기대:

- BUY/SELL 행이 candidate로 반환됨
- symbol, type, rec_shares, rec_price가 읽힘

### 2. 빈 Act 필드를 허용한다

입력:

```text
Act_Shares = ""
Act_Price = ""
Reason = ""
```

기대:

```text
status == "PENDING_ACTUAL_FILL"
```

### 3. Act 필드가 채워져 있으면 ready 상태

입력:

```text
Act_Shares = "10"
Act_Price = "185.30"
Reason = "PAPER_FILLED"
```

기대:

```text
status == "READY_FOR_PAPER_TRADE"
```

### 4. REVIEW/WARNING은 candidate에서 제외

입력 type 또는 reason에 다음 포함:

```text
REVIEW_EXIT
WARNING_HIGHEST_PRICE_STALE
```

기대:

- trade candidate에서 제외

### 5. run_paper_eod_update.py dry-run 실행

가능하면 subprocess로 실행한다.

```powershell
python scripts/run_paper_eod_update.py --date 20260507 --allow-empty-journal
```

단, 실제 action plan 파일 의존이 있으면 테스트 복잡도가 커질 수 있으므로, 우선 parser 단위 테스트를 우선한다.

---

# 검증 명령

가능한 범위에서 실행한다.

```powershell
$env:PYTHONPATH="."; python -m pytest tests/test_paper_paths.py -q
$env:PYTHONPATH="."; python -m pytest tests/test_paper_journal_preview.py -q
$env:PYTHONPATH="."; python -m py_compile scripts/run_paper_eod_update.py
$env:PYTHONPATH="."; python scripts/run_paper_eod_update.py --date 20260507 --allow-empty-journal
```

전체 테스트는 기존 import 문제가 있을 수 있으므로, 실행한다면 결과를 구분해서 보고한다.

```powershell
$env:PYTHONPATH="."; python -m pytest tests -q
```

실패 시 보고 형식:

```text
- 실패한 명령:
- 실패 원인:
- 이번 MFU-PAPER1 변경과 직접 관련 있는지:
- 기존 실패로 보이면 existing failure suspected:
```

---

# Acceptance Criteria

완료 조건:

1. `run_paper_eod_update.py`가 기존 dry-run 기능을 유지한다.
2. `run_paper_eod_update.py`가 action plan journal을 read-only로 파싱한다.
3. `--allow-empty-journal` 옵션이 동작한다.
4. 빈 Act 필드가 있는 journal row는 `PENDING_ACTUAL_FILL`로 표시된다.
5. Act 필드가 채워진 row는 `READY_FOR_PAPER_TRADE`로 표시된다.
6. BUY/SELL 외 REVIEW/WARNING row는 trade candidate에서 제외된다.
7. paper output 경로는 계속 `outputs/paper_test/` 아래로만 계산된다.
8. live/front-test 파일에는 어떤 write도 발생하지 않는다.
9. paper 파일에도 이번 단계에서는 어떤 write도 발생하지 않는다.
10. 신규 parser 테스트가 통과한다.
11. 기존 `scripts/run_eod_update.py`는 수정되지 않는다.

---

# 구현 후 보고 형식

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

- `run_eod_update.py`를 수정했는지 여부
- paper/live 경로 분리가 유지되는지 여부
- 이번 script가 실제 write를 하는지 여부
- journal parser가 기존 strict parser를 썼는지, fallback preview parser를 썼는지
- 다음 단계에서 어떤 write 기능을 붙여야 하는지
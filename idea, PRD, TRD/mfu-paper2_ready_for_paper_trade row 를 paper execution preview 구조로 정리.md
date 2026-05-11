# MFU-PAPER2: PaperTradePreview 구조 정리

## 목적

`run_paper_eod_update.py`에서 read-only로 파싱한 journal row 중 `READY_FOR_PAPER_TRADE`만 표준화된 paper execution preview 구조로 변환한다.

이번 단계는 **preview 구조화까지만** 한다.  
아직 어떤 파일도 쓰지 않는다.

---

## 현재 상태

MFU-PAPER1까지 완료된 내용:

- `run_paper_eod_update.py`가 `daily_action_plan_YYYYMMDD.md`를 read-only로 파싱
- `READY_FOR_PAPER_TRADE`, `PENDING_ACTUAL_FILL` 상태 분류
- BUY/SELL만 candidate 처리
- REVIEW_*, WARNING_* 제외
- paper/live 경로 분리 유지
- 실제 write 없음

---

# 작업 범위

## 1. `core/paper_trade_preview.py` 추가

신규 파일:

```text
core/paper_trade_preview.py
```

아래 dataclass 추가:

```python
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PaperTradePreview:
    date: str
    regime: str
    symbol: str
    side: str
    shares: int
    price: float
    gross_amount: float
    source: str
    status: str
    reason: str
    notes: str = ""
    rec_shares: Optional[int] = None
    rec_price: Optional[float] = None
```

규칙:

- `side`: BUY 또는 SELL
- BUY `shares`: 양수
- SELL `shares`: 음수
- `gross_amount = shares * price`
- `source = "journal_actual_fill"`
- `status = "READY_FOR_PAPER_TRADE"`

---

## 2. 변환 함수 추가

파일:

```text
core/paper_trade_preview.py
```

함수:

```python
def build_paper_trade_previews(
    journal_rows: list[dict],
) -> tuple[list[PaperTradePreview], list[str]]:
    ...
```

동작:

- `status == "READY_FOR_PAPER_TRADE"`인 row만 변환
- `PENDING_ACTUAL_FILL`은 제외하고 warning에 기록
- BUY/SELL이 아닌 row 제외
- `reason`이 `REVIEW` 또는 `WARNING`으로 시작하면 제외
- `Act_Shares`, `Act_Price`, `Reason`이 비어 있으면 제외
- 숫자 변환 실패 시 전체 실패시키지 말고 warning에 기록

숫자 정리는 기존 helper 재사용 가능:

```python
from core.execution_logger import clean_numeric
```

---

## 3. `run_paper_eod_update.py`에 연결

파일:

```text
scripts/run_paper_eod_update.py
```

journal preview rows를 얻은 뒤:

```python
from core.paper_trade_preview import build_paper_trade_previews

previews, preview_warnings = build_paper_trade_previews(journal_rows)
```

출력 예시:

```text
Paper execution preview:
  total_journal_rows: 2
  ready_previews: 1
  skipped_or_pending: 1

| Date | Symbol | Side | Shares | Price | Gross | Source | Reason |
| 2026-05-07 | AAPL | BUY | 10 | 185.30 | 1853.00 | journal_actual_fill | PAPER_FILLED |

Preview warnings:
  - Skipping TSLA: status=PENDING_ACTUAL_FILL

Status:
  paper execution preview OK
  no paper files were written
  no live/front-test files were written
```

---

## 4. 절대 하지 말 것

이번 작업에서 금지:

- `paper_execution_log.csv` 생성/수정
- `paper_current_state_*.json` 생성/수정
- `paper_account_snapshot.csv` 생성/수정
- `paper_performance_report_*.md` 생성/수정
- `outputs/front_test/` 아래 파일 수정
- `scripts/run_eod_update.py` 수정
- `update_portfolio_state_after_close()` 호출
- `append_to_execution_log()` 호출
- paper account cash/holding 계산
- position sizing 동기화 작업 포함

---

# 테스트

신규 테스트 파일:

```text
tests/test_paper_trade_preview.py
```

필수 테스트:

1. READY BUY row 변환  
   - BUY, Act_Shares=10, Act_Price=185.30  
   - `shares == 10`
   - `price == 185.30`
   - `gross_amount == 1853.0`

2. READY SELL row 변환  
   - SELL, Act_Shares=3, Act_Price=240.10  
   - `shares == -3`
   - `gross_amount == -720.30`

3. PENDING row 제외  
   - `status == "PENDING_ACTUAL_FILL"`
   - preview 생성 안 함
   - warning 기록

4. REVIEW/WARNING row 제외  
   - reason이 `REVIEW_EXIT` 또는 `WARNING_*`
   - preview 생성 안 함

5. 잘못된 숫자 warning 처리  
   - Act_Shares=`abc`
   - preview 생성 안 함
   - warning 기록

---

# 검증 명령

```powershell
$env:PYTHONPATH="."; python -m pytest tests/test_paper_paths.py -q
$env:PYTHONPATH="."; python -m pytest tests/test_paper_journal_preview.py -q
$env:PYTHONPATH="."; python -m pytest tests/test_paper_trade_preview.py -q
$env:PYTHONPATH="."; python -m py_compile core/paper_trade_preview.py scripts/run_paper_eod_update.py
$env:PYTHONPATH="."; python scripts/run_paper_eod_update.py --date 20260507 --allow-empty-journal
```

전체 테스트는 기존 import 문제가 있을 수 있으므로 실행하더라도 결과를 분리해서 보고한다.

```powershell
$env:PYTHONPATH="."; python -m pytest tests -q
```

---

# Acceptance Criteria

완료 조건:

1. `core/paper_trade_preview.py` 추가
2. `PaperTradePreview` dataclass 추가
3. `build_paper_trade_previews()` 추가
4. READY BUY/SELL row가 preview로 변환됨
5. SELL은 음수 shares로 변환됨
6. PENDING/REVIEW/WARNING row는 제외됨
7. 변환 실패는 warning 처리됨
8. `run_paper_eod_update.py`가 preview summary를 출력함
9. 이번 단계에서도 어떤 파일도 write하지 않음
10. `scripts/run_eod_update.py`는 수정하지 않음

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
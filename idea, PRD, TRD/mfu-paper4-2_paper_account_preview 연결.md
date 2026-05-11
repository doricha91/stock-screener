# Codex Task: MFU-PAPER4-2 Paper Account Preview 연결

## 목표

`scripts/run_paper_eod_update.py`에서 `outputs/paper_test/paper_execution_log.csv`를 읽고, MFU-PAPER4-1에서 만든 reducer를 사용해 paper account preview를 출력한다.

이번 단계는 **read + preview only**다.  
아직 paper current state 저장은 하지 않는다.

현재 전제:

- MFU-PAPER3: `paper_execution_log.csv` append 완료
- MFU-PAPER4-1: `core/paper_account_state.py` reducer 완료
- 초기 paper account:
  - initial_cash = 100000.0
  - currency = USD
  - initial_positions = {}

## 변경 파일

예상 수정:

```text
scripts/run_paper_eod_update.py
```

필요 시 추가:

```text
tests/test_paper_account_preview.py
```

가능하면 수정하지 말 것:

```text
core/paper_account_state.py
core/paper_execution_log.py
scripts/run_eod_update.py
outputs/
DB files
```

## 구현 지시

### 1. paper_execution_log.csv 읽기

`run_paper_eod_update.py`에서 기존 preview / append 흐름 이후, 아래 파일을 읽는다.

```text
outputs/paper_test/paper_execution_log.csv
```

기존 path helper가 있으면 반드시 사용한다.

```python
from core.paths import paper_execution_log_path
```

파일이 없으면 에러로 죽이지 말고 preview에 다음처럼 표시한다.

```text
Paper account preview:
  paper_execution_log.csv not found
  no trades applied
```

### 2. reducer 연결

MFU-PAPER4-1 reducer를 사용한다.

```python
from core.paper_account_state import build_paper_state_from_trades
```

동작:

```python
trade_rows = read paper_execution_log.csv rows
state = build_paper_state_from_trades(
    trade_rows,
    initial_cash=100000.0,
    currency="USD",
)
```

### 3. preview 출력

출력 예시:

```text
Paper account preview:
  initial_cash: 100000.00 USD
  cash: 98146.70 USD
  positions: 1
  applied_trades: 1

Positions:
| Symbol | Shares | Avg Price | Highest Price |
| AAPL | 10 | 185.33 | 185.33 |
```

포지션이 없으면:

```text
Positions:
  none
```

### 4. reducer error 처리

`build_paper_state_from_trades()`에서 `ValueError`가 나면 전체 traceback보다 명확한 메시지를 출력하고 종료한다.

예:

```text
Paper account preview failed:
  insufficient cash for BUY CRL
```

이 단계에서는 잘못된 paper log를 조용히 무시하지 말 것.

### 5. CLI 옵션

기존 `--commit` 의미는 유지한다.

- `--commit` 없음:
  - journal preview
  - paper execution append dry-run
  - account preview 출력
  - write 없음

- `--commit` 있음:
  - paper_execution_log.csv append 수행
  - append 후 최신 paper_execution_log.csv를 다시 읽어 account preview 출력
  - 여전히 paper_current_state 저장은 하지 않음

중요:

```text
--commit은 paper_execution_log.csv append에만 영향을 준다.
paper_current_state 저장은 이번 단계에서 하지 않는다.
```

## 하지 말 것

이번 작업에서 금지:

```text
paper_current_state_*.json 생성/수정
paper_account_snapshot.csv 생성/수정
paper_performance_report_*.md 생성/수정
outputs/front_test/ 수정
scripts/run_eod_update.py 수정
DB schema 수정
performance 계산
market price 평가
unrealized PnL 계산
수수료/슬리피지/세금 반영
```

## 테스트

가능하면 신규 테스트 추가:

```text
tests/test_paper_account_preview.py
```

필수 테스트 범위:

1. paper_execution_log row 1개 BUY를 읽어 preview state 계산
   - initial cash 100000
   - BUY 10 @ 100
   - cash 99000
   - position shares 10

2. BUY 2개로 avg_price 확인
   - BUY 10 @ 100
   - BUY 10 @ 200
   - avg_price 150

3. SELL 반영 확인
   - BUY 후 SELL
   - cash 증가
   - shares 감소

4. 빈 log 또는 파일 없음 처리
   - 에러로 죽지 않음
   - no trades applied 메시지 또는 empty state

5. invalid log는 error 처리
   - cash 부족 BUY
   - 보유 수량 초과 SELL

테스트가 CLI까지 복잡하면 reducer 기반 preview helper를 작게 분리해 테스트해도 된다.

허용되는 작은 helper:

```python
def load_paper_execution_rows(log_path: Path) -> list[dict]:
    ...

def build_paper_account_preview_from_log(log_path: Path) -> PaperAccountState:
    ...
```

단, helper 추가 시에도 파일 write는 하지 않는다.

## 검증 명령

```powershell
$env:PYTHONPATH="."; python -m pytest tests/test_paper_account_state.py -q
$env:PYTHONPATH="."; python -m pytest tests/test_paper_account_preview.py -q
$env:PYTHONPATH="."; python -m py_compile scripts/run_paper_eod_update.py core/paper_account_state.py
$env:PYTHONPATH="."; python scripts/run_paper_eod_update.py --date 20260507 --allow-empty-journal
```

필요 시 commit 경로도 확인한다.

```powershell
$env:PYTHONPATH="."; python scripts/run_paper_eod_update.py --date 20260507 --allow-empty-journal --commit
```

단, `--commit`은 `paper_execution_log.csv` append만 수행해야 한다.

## 완료 기준

1. `run_paper_eod_update.py`가 `paper_execution_log.csv`를 읽는다.
2. reducer로 paper account state를 메모리에서 계산한다.
3. cash / positions / applied_trades preview가 출력된다.
4. 파일이 없거나 빈 경우 안전하게 처리한다.
5. invalid trade row는 명확히 error 처리한다.
6. `--commit`은 여전히 paper_execution_log append에만 영향을 준다.
7. `paper_current_state_*.json`은 아직 생성하지 않는다.
8. live/front-test 파일은 수정하지 않는다.
9. 관련 테스트가 통과한다.

## 보고 형식

```text
1. Summary
2. Changed files
3. Behavior changes
4. Tests run
5. Tests not run and why
6. Risks and limitations
7. Suggested next step
```

보고 시 반드시 명시:

```text
- paper_current_state 파일을 생성했는지 여부
- paper_execution_log.csv만 읽었는지 여부
- --commit 동작 범위
- live/front-test 파일 오염 여부
- invalid trade 처리 방식
```
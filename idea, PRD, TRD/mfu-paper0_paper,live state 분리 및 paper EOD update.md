# MFU-PAPER0: paper/live state 분리 및 paper EOD update 전용 스크립트 골격 추가

## 목적

프론트테스트용 live/front-test state와 페이퍼테스트용 paper state가 절대 섞이지 않도록 저장 경로를 분리한다.

이번 작업은 **small safe fix**다.  
paper account 계산 로직을 완성하는 작업이 아니다.

## 결정 사항

다음 결정은 확정이다.

1. paper 결과는 `outputs/paper_test/`로 완전 분리한다.
2. paper EOD update는 기존 `scripts/run_eod_update.py`를 수정하지 않고, 별도 스크립트 `scripts/run_paper_eod_update.py`로 작성한다.

---

## 현재 전제

현재 live/front-test 관련 경로는 대략 다음 구조다.

- `outputs/front_test/`
- `current_state_YYYYMMDD.json`
- `execution_log.csv`
- `daily_action_plan_YYYYMMDD.md`

이번 작업에서는 기존 live/front-test 경로와 기존 `run_eod_update.py` 동작을 깨면 안 된다.

---

# 작업 범위

## 1. paper 전용 경로 추가

파일:

- `core/paths.py`

기존 `FRONT_TEST_DIR`, `current_state_snapshot_path()`는 절대 변경하지 않는다.

아래 paper 전용 경로를 추가한다.

```python
PAPER_TEST_DIR = OUTPUTS / "paper_test"
PAPER_TEST_DIR.mkdir(parents=True, exist_ok=True)

def paper_current_state_snapshot_path(date_str: str) -> Path:
    clean_date = date_str.replace("-", "")
    return PAPER_TEST_DIR / f"paper_current_state_{clean_date}.json"

def paper_execution_log_path() -> Path:
    return PAPER_TEST_DIR / "paper_execution_log.csv"

def paper_account_snapshot_path() -> Path:
    return PAPER_TEST_DIR / "paper_account_snapshot.csv"

def paper_performance_report_path(date_str: str) -> Path:
    clean_date = date_str.replace("-", "")
    return PAPER_TEST_DIR / f"paper_performance_report_{clean_date}.md"
```

필요하면 `paper_daily_action_plan_path()`는 추가하지 않는다.  
paper EOD는 기존 `outputs/front_test/daily_action_plan_YYYYMMDD.md`를 읽고, 결과만 `outputs/paper_test/`에 쓰는 구조로 시작한다.

---

## 2. paper/live 경로 충돌 방지 helper 추가

파일은 아래 둘 중 하나로 선택한다.

우선순위 1:

- `core/paper_safety.py`

우선순위 2:

- 작게 유지하려면 `scripts/run_paper_eod_update.py` 내부 helper로 시작

권장 함수:

```python
from pathlib import Path

def assert_paper_path(path: Path, paper_root: Path) -> None:
    resolved_path = path.resolve()
    resolved_root = paper_root.resolve()
    if resolved_root not in resolved_path.parents and resolved_path != resolved_root:
        raise ValueError(f"Unsafe paper path outside PAPER_TEST_DIR: {path}")
```

목적:

- paper script가 `outputs/front_test/current_state_*.json`
- `outputs/front_test/execution_log.csv`
- live/front-test 파일

을 실수로 쓰지 못하게 막는다.

---

## 3. paper EOD update 전용 스크립트 골격 추가

신규 파일:

- `scripts/run_paper_eod_update.py`

이번 small safe fix에서는 **실제 paper account 계산 로직을 완성하지 않는다.**

이 스크립트는 다음까지만 수행한다.

1. `--date YYYYMMDD` 또는 `--date YYYY-MM-DD` 인자 받기
2. 해당 날짜의 live/front-test action plan 경로 찾기  
   - `outputs/front_test/daily_action_plan_YYYYMMDD.md`
3. paper output 경로 계산
   - `outputs/paper_test/paper_current_state_YYYYMMDD.json`
   - `outputs/paper_test/paper_execution_log.csv`
   - `outputs/paper_test/paper_account_snapshot.csv`
4. paper output 경로가 모두 `outputs/paper_test/` 아래인지 검증
5. 현재는 dry-run summary만 출력
6. 실제 write는 하지 않음
7. 마지막에 명확히 메시지 출력

예상 실행:

```powershell
$env:PYTHONPATH="."; python scripts/run_paper_eod_update.py --date 20260507
```

예상 출력 예시:

```text
PAPER EOD UPDATE - SAFE DRY RUN
Input report:
  outputs/front_test/daily_action_plan_20260507.md

Paper outputs:
  outputs/paper_test/paper_current_state_20260507.json
  outputs/paper_test/paper_execution_log.csv
  outputs/paper_test/paper_account_snapshot.csv

Status:
  path separation OK
  no live/front-test files will be written
  paper account calculation is not implemented in MFU-PAPER0
```

주의:

- 기존 `scripts/run_eod_update.py`는 수정하지 않는다.
- 이번 단계에서 `current_state_*.json`을 읽거나 쓰지 않아도 된다.
- 이번 단계에서 paper state를 실제 생성하지 않아도 된다.
- 이번 단계에서 daily action plan journal을 파싱하지 않아도 된다.
- 이번 단계에서 `execution_log.csv`를 수정하지 않는다.

---

## 4. 테스트 추가

신규 테스트 파일:

- `tests/test_paper_paths.py`

테스트 내용:

### 4-1. paper path가 front_test path와 다름

```python
current_state_snapshot_path("2026-05-07") != paper_current_state_snapshot_path("2026-05-07")
```

### 4-2. paper state는 outputs/paper_test 아래에 있음

```python
assert "paper_test" in str(paper_current_state_snapshot_path("2026-05-07"))
```

### 4-3. live/front-test state는 기존 경로 유지

```python
assert "front_test" in str(current_state_snapshot_path("2026-05-07"))
assert "paper_test" not in str(current_state_snapshot_path("2026-05-07"))
```

### 4-4. paper execution log 경로 확인

```python
assert paper_execution_log_path().name == "paper_execution_log.csv"
assert "paper_test" in str(paper_execution_log_path())
```

### 4-5. paper EOD script import/smoke test

가능하면 subprocess로 다음 명령을 테스트한다.

```powershell
python scripts/run_paper_eod_update.py --date 20260507
```

단, action plan 파일이 없어서 실패할 수 있다면 다음 중 하나로 처리한다.

- `--dry-run` 기본값으로 파일 존재 여부만 WARNING 처리
- 또는 테스트에서는 `tmp_path`/monkeypatch로 경로를 대체
- 복잡하면 script smoke test는 생략하고 path test만 추가

small safe fix이므로 테스트가 과도하게 복잡해지면 안 된다.

---

## 5. Non-goals

이번 작업에서 하지 말 것:

1. paper account 계산 로직 구현
2. paper_current_state 실제 생성
3. paper_execution_log 실제 누적
4. `scripts/run_eod_update.py` 수정
5. live/front-test `current_state_YYYYMMDD.json` 수정
6. live/front-test `execution_log.csv` 수정
7. daily action plan journal 파싱 로직 수정
8. 기존 front-test 실행 흐름 변경
9. 백테스트 로직 변경
10. position sizing 동기화 작업 포함

---

## 6. Acceptance Criteria

완료 조건:

1. `outputs/paper_test/` 디렉토리 경로가 `core/paths.py`에 정의된다.
2. paper state/log/snapshot/report 경로 함수가 추가된다.
3. 기존 `FRONT_TEST_DIR`와 `current_state_snapshot_path()` 동작은 변경되지 않는다.
4. `paper_current_state_snapshot_path()`는 `outputs/paper_test/paper_current_state_YYYYMMDD.json`을 반환한다.
5. `paper_execution_log_path()`는 `outputs/paper_test/paper_execution_log.csv`를 반환한다.
6. `scripts/run_paper_eod_update.py`가 추가된다.
7. `run_paper_eod_update.py`는 현재 단계에서 safe dry-run만 수행한다.
8. `run_paper_eod_update.py`는 live/front-test 파일을 쓰지 않는다.
9. paper/live 경로 충돌 방지 테스트가 통과한다.
10. 기존 front-test 관련 테스트나 import가 깨지지 않는다.

---

## 7. 검증 명령

가능한 범위에서 실행한다.

```powershell
$env:PYTHONPATH="."; python -m pytest tests/test_paper_paths.py -q
$env:PYTHONPATH="."; python -m py_compile core/paths.py scripts/run_paper_eod_update.py
$env:PYTHONPATH="."; python scripts/run_paper_eod_update.py --date 20260507
```

전체 테스트는 현재 기존 import 문제가 있을 수 있으므로, 실행한다면 결과를 구분해서 보고한다.

```powershell
$env:PYTHONPATH="."; python -m pytest tests -q
```

실패 시 보고 형식:

```text
- 실패한 명령:
- 실패 원인:
- 이번 MFU-PAPER0 변경과 직접 관련 있는지:
- 기존 실패로 보이면 existing failure suspected:
```

---

## 8. 구현 후 보고 형식

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

- 기존 live/front-test 경로를 수정했는지 여부
- `run_eod_update.py`를 수정했는지 여부
- paper script가 실제 write를 수행하는지 여부
- `outputs/paper_test/` 외부에 write 가능성이 있는지 여부
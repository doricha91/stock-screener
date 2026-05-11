# Codex Task: MFU-PAPER4-3A paper_execution_log 백업 및 초기화

## 목표

기존 `outputs/paper_test/paper_execution_log.csv`에는 테스트성 거래가 들어 있어, 초기 paper cash `$100,000` 기준 account preview가 실패하고 있다.

따라서 정식 paper-test 시작 전:

1. 현재 `paper_execution_log.csv`를 백업한다.
2. 새 `paper_execution_log.csv`는 header만 있는 빈 로그로 초기화한다.
3. 이후부터 정식 paper-test 거래만 append되게 한다.

## 변경 범위

수정 예상 파일:

```text
scripts/reset_paper_execution_log.py
```

필요 시 테스트:

```text
tests/test_reset_paper_execution_log.py
```

실제 대상 파일:

```text
outputs/paper_test/paper_execution_log.csv
outputs/paper_test/archive/
```

## 구현 지시

### 1. 신규 스크립트 추가

새 파일:

```text
scripts/reset_paper_execution_log.py
```

기능:

- `outputs/paper_test/paper_execution_log.csv` 존재 여부 확인
- 존재하면 `outputs/paper_test/archive/` 아래로 백업
- 백업 파일명은 timestamp 포함

예:

```text
outputs/paper_test/archive/paper_execution_log_20260509_105000_backup.csv
```

- 이후 기존 `paper_execution_log.csv`를 header만 있는 빈 CSV로 다시 생성

### 2. CSV header 유지

header는 기존 PAPER3 CSV 구조를 그대로 사용한다.

```text
trade_id,date,regime,symbol,side,shares,price,gross_amount,source,status,reason,notes,rec_shares,rec_price,created_at
```

가능하면 `core.paper_execution_log`에 이미 header 상수가 있으면 재사용한다.  
없으면 이번 스크립트 안에 동일 header를 명시하되, 추후 상수화 필요성을 보고한다.

### 3. 안전장치

기본 실행은 dry-run으로 한다.

```powershell
python scripts/reset_paper_execution_log.py
```

dry-run 출력 예:

```text
DRY-RUN: paper_execution_log reset preview
current log: outputs/paper_test/paper_execution_log.csv
backup target: outputs/paper_test/archive/paper_execution_log_YYYYMMDD_HHMMSS_backup.csv
new log: header-only paper_execution_log.csv
write_performed: False
```

실제 실행은 `--commit` 옵션이 있을 때만 한다.

```powershell
python scripts/reset_paper_execution_log.py --commit
```

### 4. path safety

반드시 `assert_paper_path()`를 사용해서 아래 경로 밖에 write하지 못하게 한다.

```text
outputs/paper_test/
```

금지:

```text
outputs/front_test/
outputs/*.db
DB files
live/front-test state
```

### 5. 파일이 없을 때

`paper_execution_log.csv`가 없으면:

- 백업은 생략
- header-only 새 파일 생성은 `--commit`에서만 수행
- dry-run에서는 생성 예정이라고만 출력

## 하지 말 것

이번 작업에서 금지:

```text
paper_current_state_*.json 생성/수정
paper_account_snapshot.csv 생성/수정
paper_performance_report 생성/수정
outputs/front_test/ 수정
scripts/run_eod_update.py 수정
scripts/run_paper_eod_update.py 수정
DB schema 수정
paper account reducer 수정
position sizing 수정
```

## 테스트

가능하면 신규 테스트 추가:

```text
tests/test_reset_paper_execution_log.py
```

테스트 항목:

1. dry-run은 파일을 변경하지 않음
2. `--commit` 시 기존 log가 archive로 백업됨
3. `--commit` 후 새 `paper_execution_log.csv`는 header만 있음
4. 기존 파일이 없어도 `--commit` 시 header-only log 생성 가능
5. paper path 밖 write는 차단됨

테스트가 복잡하면 최소한 script `py_compile`과 dry-run/commit 수동 검증을 수행한다.

## 검증 명령

```powershell
$env:PYTHONPATH="."; python -m py_compile scripts/reset_paper_execution_log.py
$env:PYTHONPATH="."; python scripts/reset_paper_execution_log.py
$env:PYTHONPATH="."; python scripts/reset_paper_execution_log.py --commit
```

테스트를 추가했다면:

```powershell
$env:PYTHONPATH="."; python -m pytest tests/test_reset_paper_execution_log.py -q
```

commit 후 확인:

```text
outputs/paper_test/archive/ 아래 백업 파일 생성
outputs/paper_test/paper_execution_log.csv 는 header-only 상태
outputs/front_test/ 파일 변경 없음
DB/output database 변경 없음
```

## 완료 기준

1. 기존 `paper_execution_log.csv`가 archive에 백업된다.
2. 새 `paper_execution_log.csv`가 header-only로 초기화된다.
3. 기본 실행은 dry-run이다.
4. 실제 변경은 `--commit`에서만 발생한다.
5. write 대상은 `outputs/paper_test/` 아래로 제한된다.
6. live/front-test 파일은 변경되지 않는다.
7. paper current state/snapshot/performance는 생성하지 않는다.

## 보고 형식

작업 후 아래 형식으로 보고한다.

```text
1. Summary
2. Changed files
3. Backup/reset behavior
4. Tests run
5. Files changed under outputs/paper_test
6. Files intentionally not changed
7. Risks and limitations
8. Suggested next step
```

특히 다음을 명확히 보고한다.

```text
- 백업 파일 경로
- 새 paper_execution_log.csv가 header-only인지
- dry-run 기본값이 유지되는지
- --commit에서만 write되는지
- outputs/front_test/ 오염 여부
```
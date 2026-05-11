# Codex Task: run_paper_eod_update.py 출력 모드 표시 수정

## 목표

`scripts/run_paper_eod_update.py` 실행 시 첫 제목이 항상 `SAFE DRY RUN`으로 표시되어 혼동이 있습니다.

현재 문제:

```text
--commit 실행인데도:
PAPER EOD UPDATE - SAFE DRY RUN
```

목표:

```text
--commit 없음:
PAPER EOD UPDATE - SAFE DRY RUN

--commit 있음:
PAPER EOD UPDATE - COMMIT MODE
```

이번 작업은 **출력 문구 수정만** 합니다.

## 변경 파일

예상 수정:

```text
scripts/run_paper_eod_update.py
```

필요 시 테스트:

```text
tests/test_run_paper_eod_update_mode_label.py
```

## 구현 지시

`run_paper_eod_update.py`에서 최초 출력 header를 `args.commit` 값에 따라 분기합니다.

예시:

```python
mode_label = "COMMIT MODE" if args.commit else "SAFE DRY RUN"
print(f"PAPER EOD UPDATE - {mode_label}")
```

또는 기존 출력 함수 구조에 맞게 동일한 의미로 반영합니다.

## 유지할 것

기존 동작은 바꾸지 않습니다.

유지해야 할 것:

```text
--commit 없음: 파일 write 없음
--commit 있음: paper_execution_log.csv append만 수행
duplicate trade_id skip 유지
paper account preview 유지
paper_current_state 저장 안 함
live/front-test 파일 write 안 함
```

## 하지 말 것

이번 작업에서 금지:

```text
paper_execution_log append 로직 변경
duplicate trade_id 로직 변경
paper account reducer 변경
paper_current_state_*.json 생성
paper_account_snapshot.csv 생성
paper_performance_report 생성
outputs/front_test 수정
DB schema 수정
position sizing 수정
Reason / journal parser 로직 변경
```

## 테스트 / 검증

최소 검증:

```powershell
$env:PYTHONPATH="."; python -m py_compile scripts/run_paper_eod_update.py
$env:PYTHONPATH="."; python scripts/run_paper_eod_update.py --date 20260509 --allow-empty-journal
$env:PYTHONPATH="."; python scripts/run_paper_eod_update.py --date 20260509 --allow-empty-journal --commit
```

기대 출력:

```text
PAPER EOD UPDATE - SAFE DRY RUN
```

```text
PAPER EOD UPDATE - COMMIT MODE
```

주의:

- `--commit` 실행 시 이미 같은 trade가 있으면 `duplicates_skipped`로 처리될 수 있습니다. 이는 정상입니다.
- 이번 작업의 핵심은 첫 header 문구가 mode에 맞는지 확인하는 것입니다.

## 완료 기준

1. dry-run 실행 시 `PAPER EOD UPDATE - SAFE DRY RUN` 출력
2. commit 실행 시 `PAPER EOD UPDATE - COMMIT MODE` 출력
3. paper_execution_log append/duplicate 동작은 기존과 동일
4. paper_current_state는 여전히 생성하지 않음
5. live/front-test 파일은 수정하지 않음

## 보고 형식

```text
1. Summary
2. Changed files
3. Behavior changes
4. Tests run
5. Files intentionally not changed
6. Risks and limitations
7. Suggested next step
```
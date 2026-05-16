# MFU-PAPER6-6A 작업 지시문: run_paper_eod_update.py 기본 input plan을 paper daily plan으로 전환

## 목적

`run_paper_eod_update.py`가 기본적으로 `outputs/front_test/daily_action_plan_YYYYMMDD.md`가 아니라, 공식 paper daily plan인 `outputs/paper_test/daily_action_plan_YYYYMMDD.md`를 읽도록 수정한다.

이번 작업은 paper-test 공식 루프를 완성하기 위한 path 전환 작업이다.

```text
paper_state
→ run_paper_daily_plan.py
→ outputs/paper_test/daily_action_plan_YYYYMMDD.md
→ run_paper_eod_update.py dry-run / commit
```

## 배경

MFU-PAPER6-5 결과:

- `run_paper_daily_plan.py`는 `outputs/paper_test/daily_action_plan_20260512.md`를 정상 생성함
- `SWITCH_IN` symbol은 `CF`, `BRK-B`로 정상 표시됨
- 하지만 `run_paper_eod_update.py`는 실제로 paper plan이 아니라 `outputs/front_test/daily_action_plan_20260512.md`를 읽음
- 원인은 `build_paper_eod_paths(date_str)` 내부에서 `FRONT_TEST_DIR / daily_action_plan_YYYYMMDD.md`를 하드코딩했기 때문
- `--commit`은 실행하지 않았고, paper log/snapshot 변경은 없었음

## 확정 정책

1. `run_paper_eod_update.py`의 기본 input plan:
   - `outputs/paper_test/daily_action_plan_YYYYMMDD.md`

2. front plan 자동 fallback:
   - 금지

3. paper daily plan이 없을 때:
   - 명확한 error 발생
   - 조용히 front plan을 읽으면 안 됨

4. `--plan-path`:
   - 필수 운영 옵션이 아님
   - 테스트/디버깅용 선택 override로 추가 가능
   - 기본값은 항상 paper daily plan

5. 이번 단계:
   - dry-run 검증까지
   - `--commit` 실행 금지

## 구현 범위

### 1. run_paper_eod_update.py 수정

현재 경로 생성 로직을 확인한다.

예상 문제 지점:

```python
input_report = FRONT_TEST_DIR / f"daily_action_plan_{clean_date}.md"
```

이를 paper path로 변경한다.

권장:

```python
input_report = paper_daily_action_plan_path(clean_date)
```

또는 기존 구조에 맞춰:

```python
input_report = PAPER_TEST_DIR / f"daily_action_plan_{clean_date}.md"
```

단, 가능하면 `core/paths.py`의 helper를 사용한다.

### 2. --plan-path 선택 옵션 추가

가능하면 argparse에 선택 옵션을 추가한다.

```text
--plan-path
```

동작:

```text
--plan-path가 있으면 해당 파일 사용
없으면 outputs/paper_test/daily_action_plan_YYYYMMDD.md 사용
```

주의:

```text
--plan-path가 없을 때 front_test로 fallback 금지
```

### 3. missing paper plan 처리

paper daily plan 파일이 없으면 명확히 실패한다.

예상 메시지:

```text
Paper daily action plan not found:
outputs/paper_test/daily_action_plan_YYYYMMDD.md

Run:
python scripts/run_paper_daily_plan.py --date YYYYMMDD
```

## 절대 금지

- `--commit` 실행 금지
- front plan 자동 fallback 금지
- `outputs/front_test` 수정 금지
- `paper_execution_log.csv` 수정 금지
- `paper_account_snapshot.csv` 수정 금지
- `paper_position_snapshot.csv` 수정 금지
- DB schema / DB files 수정 금지
- SWITCH_IN symbol mapping 재수정 금지
- date normalize 재수정 금지
- benchmark / MDD / CAGR / Sharpe 추가 금지
- 대규모 리팩토링 금지

## 테스트 추가/수정

권장 테스트 파일:

```text
tests/test_paper_eod_plan_path.py
```

필수 테스트:

1. 기본 input path가 paper daily plan인지 확인
   - `outputs/paper_test/daily_action_plan_YYYYMMDD.md`

2. front daily plan으로 fallback하지 않는지 확인

3. paper plan이 없으면 명확한 error

4. `--plan-path`가 있으면 override path 사용

5. 기존 date 형식 유지
   - `20260512`
   - `2026-05-12`
   - 둘 다 clean filename은 `20260512`

## 수동 dry-run 검증

기준일:

```text
2026-05-12
파일명: 20260512
```

먼저 paper daily plan 재생성:

```bat
set PYTHONPATH=.
python scripts/run_paper_daily_plan.py --date 20260512
```

확인:

```bat
type outputs\paper_test\daily_action_plan_20260512.md
```

dry-run 실행:

```bat
python scripts/run_paper_eod_update.py --date 20260512 --allow-empty-journal
```

확인할 것:

```text
Input report가 outputs/paper_test/daily_action_plan_20260512.md인지
outputs/front_test를 읽지 않는지
SWITCH_OUT / SWITCH_IN row를 읽는지
CF / BRK-B ticker가 유지되는지
write_performed: False인지
```

`--plan-path`를 추가했다면 override도 확인:

```bat
python scripts/run_paper_eod_update.py --date 20260512 --plan-path outputs\paper_test\daily_action_plan_20260512.md --allow-empty-journal
```

## 파일 변경 확인

```bat
git status --short outputs\front_test outputs\paper_test
git diff -- outputs\front_test
```

hash 확인:

```bat
python -c "from pathlib import Path; import hashlib; files=['outputs/paper_test/paper_execution_log.csv','outputs/paper_test/paper_account_snapshot.csv','outputs/paper_test/paper_position_snapshot.csv']; [print(f, hashlib.sha256(Path(f).read_bytes()).hexdigest() if Path(f).exists() else 'MISSING') for f in files]"
```

허용되는 변경:

```text
outputs/paper_test/daily_action_plan_20260512.md
```

허용되지 않는 변경:

```text
outputs/front_test/*
outputs/paper_test/paper_execution_log.csv
outputs/paper_test/paper_account_snapshot.csv
outputs/paper_test/paper_position_snapshot.csv
outputs/paper_test/paper_current_state_*.json
```

## 검증 명령

```bat
set PYTHONPATH=.

python -m pytest tests/test_paper_eod_plan_path.py -q
python -m pytest tests/test_paper_daily_plan_generation.py -q
python -m pytest tests/test_daily_plan_switch_symbol_mapping.py -q
python -m pytest tests/test_paper_account_state.py -q

python -m py_compile scripts/run_paper_eod_update.py core/paths.py
```

## 성공 기준

- `run_paper_eod_update.py` 기본 input report가 paper daily plan으로 변경됨
- front daily plan 자동 fallback 없음
- paper plan이 없으면 명확히 실패
- dry-run에서 paper daily plan을 실제로 읽음
- `SWITCH_IN` / `SWITCH_OUT` row가 dry-run parser에 전달됨
- `--commit` 미실행
- `paper_execution_log.csv` 변경 없음
- account / position snapshot 변경 없음
- `outputs/front_test` 변경 없음

## 결과 보고 형식

5,000자 이내로 작성한다.

포함할 항목:

1. Summary
2. 변경 파일
3. 기존 path 문제
4. 수정된 기본 input plan 경로
5. `--plan-path` 추가 여부
6. missing paper plan 처리
7. dry-run 실행 결과
8. 실제로 읽은 input report 경로
9. SWITCH row 해석 결과
10. paper log/snapshot 변경 여부
11. outputs/front_test 변경 여부
12. 남은 위험 / 다음 단계

반드시 명시할 것:

```text
- 기본 input이 outputs/paper_test로 바뀌었는지
- front_test fallback이 제거됐는지
- --commit을 실행하지 않았는지
- paper_execution_log.csv 변경 여부
- paper_account_snapshot.csv 변경 여부
- paper_position_snapshot.csv 변경 여부
```
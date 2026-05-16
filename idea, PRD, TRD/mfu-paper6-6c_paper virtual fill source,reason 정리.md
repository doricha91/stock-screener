# MFU-PAPER6-6C 작업 지시문: paper virtual fill source/reason 정리

## 목적

`run_paper_eod_update.py`의 paper dry-run preview에서 `Act_Shares` / `Act_Price`가 비어 있어 `Rec_Shares` / `Rec_Price`로 fallback된 거래를 명확히 표시한다.

이번 작업은 거래 계산 로직 변경이 아니라, **paper virtual fill의 출처와 사유를 명확히 남기는 작업**이다.

## 배경

MFU-PAPER6-6B 결과:

- `Act_Shares` / `Act_Price`가 `[ ]`일 때 `Rec_Shares` / `Rec_Price` fallback 성공
- preview 생성 성공:
  - CPAY SELL 29 @ 338.34
  - CF BUY 75 @ 130.39
  - VRSN SELL 34 @ 285.80
  - BRK-B BUY 20 @ 484.96
- `ready_previews = 4`
- `rows_to_append = 4`
- `--commit`은 실행하지 않음
- paper log / snapshot 변경 없음

남은 문제:

- preview row의 source가 아직 `journal_actual_fill`처럼 보임
- reason도 `[ ]` 상태로 남음
- 실제 의미는 “수동 체결값”이 아니라 “Rec 값을 paper 가상 체결값으로 사용”한 것임

## 확정 정책

1. Act 값이 실제 숫자면 기존처럼 actual fill로 본다.
2. Act 값이 비어 있거나 `[ ]`라서 Rec 값으로 fallback한 경우:
   - source를 `paper_virtual_fill` 또는 이에 준하는 명확한 값으로 표시한다.
   - reason에는 Rec 값을 사용했다는 사실을 남긴다.
3. paper_execution_log에 commit되기 전 dry-run preview에서 먼저 명확히 보이게 한다.
4. 이번 MFU에서는 `--commit`을 실행하지 않는다.
5. fallback 계산 정책 자체는 MFU-PAPER6-6B의 동작을 유지한다.

## 권장 source/reason 표현

권장:

```text
source = paper_virtual_fill
reason = Act fields blank; used Rec_Shares/Rec_Price as paper fill
```

또는 기존 schema 제약이 있다면:

```text
source = rec_to_actual_fallback
reason = Paper virtual fill from Rec_Shares/Rec_Price
```

중요한 점:

```text
source = journal_actual_fill
reason = [ ]
```

처럼 실제 수동 체결값처럼 오해되는 표현은 피한다.

## 구현 범위

### 1. core/paper_trade_preview.py 수정

대상 함수:

```text
resolve_paper_actual_fill(row)
can_resolve_paper_actual_fill(row)
preview row 생성 함수
```

수정 방향:

- Act 값이 숫자로 존재하면:
  - source는 기존 actual fill 의미 유지
  - reason은 기존 reason 유지 가능

- Act 값이 blank이고 Rec 값으로 fallback하면:
  - source를 `paper_virtual_fill`로 설정
  - reason에 fallback 사실을 기록

필요하면 helper 결과를 확장한다.

예:

```python
@dataclass
class ResolvedPaperFill:
    shares: float
    price: float
    source: str
    reason: str
```

단, 대규모 리팩토링은 금지한다. 기존 구조가 dict 기반이면 dict로 최소 수정한다.

### 2. scripts/run_paper_eod_update.py 수정

dry-run summary / preview 출력에서 source와 reason이 명확히 보이도록 한다.

확인할 것:

```text
CPAY SELL source=paper_virtual_fill
CF BUY source=paper_virtual_fill
VRSN SELL source=paper_virtual_fill
BRK-B BUY source=paper_virtual_fill
```

reason에는 최소한 아래 의미가 들어가야 한다.

```text
Act fields blank; used Rec_Shares/Rec_Price
```

### 3. commit row 생성 경로 확인

이번에는 commit하지 않지만, 나중에 commit 시 `paper_execution_log.csv`에 들어갈 row에도 같은 source/reason이 반영되는지 코드상 확인한다.

단, 실제 `--commit` 실행은 금지한다.

## 절대 금지

- `--commit` 실행 금지
- fallback 수량/가격 계산 정책 변경 금지
- paper_execution_log.csv 수정 금지
- paper_account_snapshot.csv 수정 금지
- paper_position_snapshot.csv 수정 금지
- paper_current_state_*.json 수정 금지
- outputs/front_test 수정 금지
- DB schema / DB files 수정 금지
- SWITCH_IN symbol mapping 재수정 금지
- date normalize 재수정 금지
- benchmark / MDD / CAGR / Sharpe 추가 금지
- 대규모 리팩토링 금지

## 테스트 추가/수정

권장 테스트 파일:

```text
tests/test_paper_eod_virtual_fill_source.py
```

필수 테스트:

1. Act placeholder fallback 시 source 확인

```text
Act_Shares=[ ]
Act_Price=[ ]
Rec_Shares=10
Rec_Price=100

기대:
shares=10
price=100
source=paper_virtual_fill
reason contains "Rec_Shares"
```

2. Act 값이 실제 숫자면 actual 우선

```text
Act_Shares=8
Act_Price=101
Rec_Shares=10
Rec_Price=100

기대:
shares=8
price=101
source가 paper_virtual_fill이 아님
```

3. dry-run preview row에 source/reason 반영

```text
CPAY / CF / VRSN / BRK-B preview row의 source/reason 확인
```

4. 기존 fallback 테스트 유지

```text
tests/test_paper_eod_rec_to_actual_fallback.py 통과
```

## 수동 dry-run 검증

```bat
set PYTHONPATH=.

python scripts/run_paper_daily_plan.py --date 20260512
python scripts/run_paper_eod_update.py --date 20260512 --allow-empty-journal
```

확인할 것:

```text
Input report:
outputs/paper_test/daily_action_plan_20260512.md

preview:
CPAY SELL
CF BUY
VRSN SELL
BRK-B BUY

source:
paper_virtual_fill 또는 명확한 fallback source

reason:
Act fields blank; used Rec_Shares/Rec_Price
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

python -m pytest tests/test_paper_eod_virtual_fill_source.py -q
python -m pytest tests/test_paper_eod_rec_to_actual_fallback.py -q
python -m pytest tests/test_paper_eod_plan_path.py -q
python -m pytest tests/test_paper_daily_plan_generation.py -q
python -m pytest tests/test_daily_plan_switch_symbol_mapping.py -q
python -m pytest tests/test_paper_account_state.py -q

python -m py_compile core/paper_trade_preview.py scripts/run_paper_eod_update.py
```

## 성공 기준

- Rec → Act fallback preview는 기존처럼 생성됨
- CPAY / CF / VRSN / BRK-B preview 유지
- fallback row source가 `journal_actual_fill`처럼 오해되지 않음
- fallback row reason에 Rec 값을 사용했다는 사실이 표시됨
- Act 값이 실제 숫자일 때는 Act 값이 우선됨
- `--commit` 미실행
- paper_execution_log.csv 변경 없음
- account / position snapshot 변경 없음
- outputs/front_test 변경 없음

## 결과 보고 형식

5,000자 이내로 작성한다.

포함할 항목:

1. Summary
2. 변경 파일
3. 기존 문제
4. source/reason 정책
5. parser/preview 수정 내용
6. 테스트 결과
7. dry-run 결과
8. preview row의 source/reason 예시
9. paper log/snapshot 변경 여부
10. outputs/front_test 변경 여부
11. 남은 위험 / 다음 단계

반드시 명시할 것:

```text
- fallback row source가 무엇으로 표시되는지
- fallback row reason이 무엇으로 표시되는지
- Act 값이 실제 숫자일 때 Act 우선 정책이 유지되는지
- --commit을 실행하지 않았는지
- paper_execution_log.csv 변경 여부
- paper_account_snapshot.csv 변경 여부
- paper_position_snapshot.csv 변경 여부
```
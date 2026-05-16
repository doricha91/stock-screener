# MFU-PAPER6-6B 작업 지시문: paper EOD parser에서 Rec 값을 Act 값으로 fallback 처리

## 목적

`run_paper_eod_update.py`가 paper daily plan을 dry-run으로 읽을 때, `Act_Shares` / `Act_Price`가 비어 있거나 `[ ]` placeholder인 경우 `Rec_Shares` / `Rec_Price`를 paper actual fill 값으로 간주해 trade preview를 생성하도록 수정한다.

paper-test는 실제 브로커 체결이 없는 가상 체결이므로, 공식 정책은 아래와 같다.

```text
paper mode:
Act_Shares가 비어 있거나 [ ]이면 Rec_Shares 사용
Act_Price가 비어 있거나 [ ]이면 Rec_Price 사용
```

이번 단계는 dry-run preview 정상화가 목적이다.  
`--commit`은 실행하지 않는다.

## 배경

MFU-PAPER6-6A 결과:

- `run_paper_eod_update.py` 기본 input plan이 `outputs/paper_test/daily_action_plan_YYYYMMDD.md`로 변경됨
- front_test fallback 제거됨
- paper daily plan row가 parser에 전달됨
- 전달된 row 예:
  - CPAY SELL
  - CF BUY
  - VRSN SELL
  - BRK-B BUY
- 하지만 `Act_Shares`, `Act_Price`가 `[ ]`라서 numeric parse 실패
- 결과:
  - `Journal preview.total_rows = 4`
  - `ready_for_paper_trade = 4`
  - `ready_previews = 0`
- paper_execution_log / snapshots 변경 없음

## 확정 정책

1. paper-test에서는 추천값을 가상 체결값으로 사용한다.
2. `Act_Shares`가 비었거나 `[ ]`이면 `Rec_Shares`를 사용한다.
3. `Act_Price`가 비었거나 `[ ]`이면 `Rec_Price`를 사용한다.
4. `Act_*` 값이 실제 숫자로 채워져 있으면 그 값을 우선 사용한다.
5. `Rec_*`도 비어 있거나 숫자 변환 불가하면 해당 row는 skip하고 명확한 warning을 남긴다.
6. 이번 MFU에서는 commit하지 않는다.

## 구현 범위

### 1. run_paper_eod_update.py parser 수정

fallback preview parser 또는 journal preview parser에서 `Act_Shares`, `Act_Price` 숫자 변환 전 아래 로직을 적용한다.

권장 helper:

```python
def is_blank_actual_value(value) -> bool:
    ...
```

blank로 볼 값:

```text
None
""
" "
"[ ]"
"[]"
"[  ]"
"N/A"
"nan"
```

권장 helper:

```python
def resolve_paper_actual_fill(row) -> tuple[float, float]:
    """
    Returns:
        act_shares, act_price

    Policy:
        Act_Shares numeric이면 Act_Shares 사용
        아니면 Rec_Shares 사용

        Act_Price numeric이면 Act_Price 사용
        아니면 Rec_Price 사용
    """
```

주의:

```text
- 숫자 변환 시 comma, $, 공백 제거 가능
- shares는 최종적으로 int 또는 float 중 기존 execution_log schema에 맞춤
- price는 float
- Rec 값도 invalid면 skip + warning
```

### 2. row status 분류 정리

현재 `ready_for_paper_trade = 4`인데 `ready_previews = 0`으로 보이는 혼란을 줄인다.

권장:

```text
ready_for_paper_trade
= paper mode fallback까지 적용했을 때 실제 preview 생성 가능한 row

skipped_or_pending
= Rec/Act 모두 부족하거나 invalid인 row
```

다만 summary 출력 구조를 크게 바꾸지 말고, 이번 MFU에서는 최소 수정한다.

### 3. SWITCH row 확인

paper daily plan의 switch row가 아래처럼 preview로 변환되는지 확인한다.

```text
SWITCH_OUT CPAY -> SELL CPAY
SWITCH_IN CF -> BUY CF
SWITCH_OUT VRSN -> SELL VRSN
SWITCH_IN BRK-B -> BUY BRK-B
```

## 절대 금지

- `--commit` 실행 금지
- paper_execution_log.csv 수정 금지
- paper_account_snapshot.csv 수정 금지
- paper_position_snapshot.csv 수정 금지
- outputs/front_test 수정 금지
- DB schema / DB files 수정 금지
- run_paper_daily_plan.py 대규모 수정 금지
- SWITCH_IN symbol mapping 재수정 금지
- date normalize 재수정 금지
- benchmark / MDD / CAGR / Sharpe 추가 금지

## 테스트 추가/수정

권장 테스트 파일:

```text
tests/test_paper_eod_rec_to_actual_fallback.py
```

필수 테스트:

1. Act 값이 `[ ]`이면 Rec 값 사용

```text
Rec_Shares=10
Rec_Price=100.5
Act_Shares=[ ]
Act_Price=[ ]

기대:
act_shares=10
act_price=100.5
```

2. Act 값이 숫자로 있으면 Act 값 우선

```text
Rec_Shares=10
Rec_Price=100
Act_Shares=8
Act_Price=101

기대:
act_shares=8
act_price=101
```

3. Rec 값도 invalid이면 skip

```text
Rec_Shares=[ ]
Rec_Price=[ ]
Act_Shares=[ ]
Act_Price=[ ]

기대:
preview 생성 안 함
warning 발생
```

4. SWITCH_IN / SWITCH_OUT row preview 생성

```text
CPAY SELL
CF BUY
VRSN SELL
BRK-B BUY
```

5. 숫자 ticker 재발 방지

```text
symbol이 0, 2가 아니어야 함
```

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

dry-run 실행:

```bat
python scripts/run_paper_eod_update.py --date 20260512 --allow-empty-journal
```

확인할 것:

```text
Input report가 outputs/paper_test/daily_action_plan_20260512.md인지
CPAY SELL, CF BUY, VRSN SELL, BRK-B BUY가 preview에 잡히는지
Act_Shares / Act_Price가 Rec_Shares / Rec_Price fallback으로 채워지는지
ready_previews가 0이 아닌지
rows_to_append가 preview 기준으로 계산되는지
write_performed: False인지
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

python -m pytest tests/test_paper_eod_rec_to_actual_fallback.py -q
python -m pytest tests/test_paper_eod_plan_path.py -q
python -m pytest tests/test_paper_daily_plan_generation.py -q
python -m pytest tests/test_daily_plan_switch_symbol_mapping.py -q
python -m pytest tests/test_paper_account_state.py -q

python -m py_compile scripts/run_paper_eod_update.py
```

## 성공 기준

- paper plan을 기본 input으로 읽음
- `[ ]` Act placeholder가 있어도 Rec 값 fallback으로 preview 생성
- CPAY SELL / CF BUY / VRSN SELL / BRK-B BUY가 preview에 반영
- 숫자 ticker 0, 2 재발 없음
- ready_previews가 0이 아님
- dry-run에서 `write_performed: False`
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
4. Rec → Act fallback 정책
5. parser 수정 내용
6. 테스트 결과
7. dry-run 결과
8. preview 생성 row
9. rows_to_append / duplicates_skipped / ready_previews
10. paper log/snapshot 변경 여부
11. outputs/front_test 변경 여부
12. 남은 위험 / 다음 단계

반드시 명시할 것:

```text
- Act placeholder [ ]가 Rec 값으로 fallback되는지
- Act 값이 실제 숫자일 때 Act 값이 우선되는지
- CPAY / CF / VRSN / BRK-B preview가 생성됐는지
- --commit을 실행하지 않았는지
- paper_execution_log.csv 변경 여부
- paper_account_snapshot.csv 변경 여부
- paper_position_snapshot.csv 변경 여부
```
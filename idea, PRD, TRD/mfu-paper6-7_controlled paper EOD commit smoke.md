# MFU-PAPER6-7 작업 지시문: controlled paper EOD commit smoke

## 목적

`run_paper_daily_plan.py`로 생성한 official paper daily plan을 `run_paper_eod_update.py --commit`으로 실제 paper 계좌에 반영하는 controlled commit smoke를 수행한다.

이번 단계는 paper loop의 첫 실제 commit 검증이다.

검증할 전체 흐름:

```text
paper_execution_log.csv + reducer
→ run_paper_daily_plan.py
→ outputs/paper_test/daily_action_plan_YYYYMMDD.md
→ run_paper_eod_update.py --commit
→ paper_execution_log.csv append
→ paper_current_state 저장
→ paper_account_snapshot.csv 저장
→ paper_position_snapshot.csv 저장
```

## 기준일

이번 controlled smoke 기준일:

```text
2026-05-12
파일명 기준: 20260512
```

기준 paper daily plan:

```text
outputs/paper_test/daily_action_plan_20260512.md
```

## 선행 조건

아래가 이미 완료된 상태여야 한다.

```text
1. run_paper_daily_plan.py가 outputs/paper_test/daily_action_plan_20260512.md 생성 가능
2. run_paper_eod_update.py 기본 input이 outputs/paper_test daily plan
3. Rec → Act fallback dry-run preview 생성 가능
4. fallback source = paper_virtual_fill
5. dry-run에서 ready_previews = 4, rows_to_append = 4 확인
```

예상 preview:

```text
CPAY  SELL 29 @ 338.34
CF    BUY  75 @ 130.39
VRSN  SELL 34 @ 285.80
BRK-B BUY  20 @ 484.96
```

## 핵심 정책

1. 이번 MFU에서는 `--commit`을 1회 실행한다.
2. 실행 전 반드시 dry-run으로 예상 append row를 확인한다.
3. dry-run 결과가 예상과 다르면 commit하지 않는다.
4. commit 후 paper 파일 변경은 허용한다.
5. outputs/front_test 변경은 절대 허용하지 않는다.
6. DB schema / DB files는 변경하지 않는다.
7. live/broker 관련 코드는 건드리지 않는다.

## 절대 금지

```text
- outputs/front_test 수정 금지
- DB schema / DB files 수정 금지
- live/broker 구현 금지
- benchmark / MDD / CAGR / Sharpe 구현 금지
- run_front_test.py 동작 변경 금지
- 대규모 리팩토링 금지
```

## 1단계: 실행 전 상태 기록

```bat
set PYTHONPATH=.

git status --short outputs\front_test outputs\paper_test
```

실행 전 hash 저장:

```bat
python -c "from pathlib import Path; import hashlib; files=['outputs/paper_test/paper_execution_log.csv','outputs/paper_test/paper_account_snapshot.csv','outputs/paper_test/paper_position_snapshot.csv']; [print(f, hashlib.sha256(Path(f).read_bytes()).hexdigest() if Path(f).exists() else 'MISSING') for f in files]"
```

archive 폴더 확인:

```bat
dir outputs\paper_test
dir outputs\paper_test\archive
```

## 2단계: 관련 테스트 실행

```bat
python -m pytest tests/test_paper_eod_virtual_fill_source.py -q
python -m pytest tests/test_paper_eod_rec_to_actual_fallback.py -q
python -m pytest tests/test_paper_eod_plan_path.py -q
python -m pytest tests/test_paper_daily_plan_generation.py -q
python -m pytest tests/test_daily_plan_switch_symbol_mapping.py -q
python -m pytest tests/test_paper_account_state.py -q

python -m py_compile core/paper_trade_preview.py scripts/run_paper_eod_update.py scripts/run_paper_daily_plan.py
```

## 3단계: paper daily plan 재생성

최신 코드 기준으로 plan을 다시 만든다.

```bat
python scripts/run_paper_daily_plan.py --date 20260512
```

확인:

```bat
type outputs\paper_test\daily_action_plan_20260512.md
```

확인할 것:

```text
- Input/output path가 outputs/paper_test인지
- SWITCH_IN ticker가 CF, BRK-B인지
- 숫자 ticker 0, 2가 없는지
- CPAY / GEN / VRSN 등 paper 보유 종목 기준 진단이 포함되는지
```

## 4단계: commit 전 dry-run

```bat
python scripts/run_paper_eod_update.py --date 20260512 --allow-empty-journal
```

commit 전 반드시 아래를 확인한다.

```text
input report = outputs/paper_test/daily_action_plan_20260512.md
ready_previews = 4
rows_to_append = 4
duplicates_skipped = 0
write_performed = False
source = paper_virtual_fill
reason = Act fields blank; used Rec_Shares/Rec_Price as paper fill
```

예상 preview:

```text
CPAY SELL
CF BUY
VRSN SELL
BRK-B BUY
```

아래 중 하나라도 다르면 commit하지 말고 원인만 보고한다.

```text
- input report가 outputs/front_test임
- ready_previews = 0
- rows_to_append = 0
- ticker가 0 또는 2로 표시됨
- source/reason이 누락됨
- dry-run인데 파일이 변경됨
```

## 5단계: controlled commit 실행

dry-run이 정상일 때만 실행한다.

```bat
python scripts/run_paper_eod_update.py --date 20260512 --allow-empty-journal --commit
```

확인할 것:

```text
write_performed = True
rows_appended = 4 또는 이에 준하는 append 결과
duplicates_skipped = 0
paper_execution_log.csv updated
paper_current_state_20260512.json 생성 또는 갱신
paper_account_snapshot.csv 저장
paper_position_snapshot.csv 저장
archive backup 생성 여부
```

## 6단계: commit 후 검증

paper execution log 확인:

```bat
type outputs\paper_test\paper_execution_log.csv
```

또는 마지막 일부만 확인:

```bat
python -c "from pathlib import Path; p=Path('outputs/paper_test/paper_execution_log.csv'); lines=p.read_text(encoding='utf-8').splitlines(); print('\n'.join(lines[-10:]))"
```

확인할 것:

```text
- CPAY SELL row 존재
- CF BUY row 존재
- VRSN SELL row 존재
- BRK-B BUY row 존재
- source 또는 reason에 paper_virtual_fill / Rec fallback 의미가 남는지
- trade_id 중복이 없는지
```

current state 확인:

```bat
dir outputs\paper_test
type outputs\paper_test\paper_current_state_20260512.json
```

확인할 것:

```text
- CPAY / VRSN position이 감소 또는 제거됐는지
- CF / BRK-B position이 추가됐는지
- cash가 SELL/BUY 후 반영됐는지
```

account snapshot 확인:

```bat
type outputs\paper_test\paper_account_snapshot.csv
```

position snapshot 확인:

```bat
type outputs\paper_test\paper_position_snapshot.csv
```

확인할 것:

```text
- snapshot_date = 20260512 또는 2026-05-12 기준 row 존재
- market valuation status 확인
- realized_pnl / unrealized_pnl / total_pnl 계산이 깨지지 않는지
- position snapshot에 최신 OPEN positions 반영
```

## 7단계: 오염 확인

```bat
git status --short outputs\front_test outputs\paper_test
git diff -- outputs\front_test
```

허용되는 변경:

```text
outputs/paper_test/daily_action_plan_20260512.md
outputs/paper_test/paper_execution_log.csv
outputs/paper_test/paper_current_state_20260512.json
outputs/paper_test/paper_account_snapshot.csv
outputs/paper_test/paper_position_snapshot.csv
outputs/paper_test/archive/*
```

허용되지 않는 변경:

```text
outputs/front_test/*
DB files
source code의 추가 수정
```

## 8단계: commit 후 duplicate dry-run 확인

같은 날짜를 다시 dry-run으로 실행한다.

```bat
python scripts/run_paper_eod_update.py --date 20260512 --allow-empty-journal
```

확인할 것:

```text
rows_to_append = 0
duplicates_skipped >= 4
write_performed = False
cash/shares/realized_pnl이 추가로 변하지 않음
```

주의:

```text
이번 단계에서는 duplicate 확인을 위해 dry-run만 한다.
두 번째 --commit은 실행하지 않는다.
```

## 실패 시 분류

실패하면 즉시 추가 수정을 하지 말고 원인을 분류한다.

```text
1. plan read 문제
2. preview 생성 문제
3. commit append 문제
4. duplicate trade_id 문제
5. current_state 저장 문제
6. account snapshot 저장 문제
7. position snapshot 저장 문제
8. market valuation 문제
9. source/reason 보존 문제
```

명백한 소형 버그가 아니면 후속 MFU로 분리한다.

## 성공 기준

아래 조건을 만족하면 완료 처리한다.

```text
- commit 전 dry-run 정상
- --commit 1회 실행
- paper_execution_log.csv에 expected rows append
- CPAY / CF / VRSN / BRK-B trade 반영
- source/reason에 paper virtual fill 의미 보존
- paper_current_state_20260512.json 저장
- paper_account_snapshot.csv 저장
- paper_position_snapshot.csv 저장
- outputs/front_test 변경 없음
- DB 변경 없음
- commit 후 duplicate dry-run에서 중복 append 방지 확인
```

## 결과 보고 형식

5,000자 이내로 작성한다.

포함할 항목:

1. Summary
2. 사용 기준일
3. commit 전 dry-run 결과
4. 실제 commit 명령
5. rows_appended / duplicates_skipped
6. paper_execution_log append 결과
7. source/reason 보존 여부
8. paper_current_state 결과
9. account snapshot 결과
10. position snapshot 결과
11. commit 후 duplicate dry-run 결과
12. outputs/front_test 변경 여부
13. DB 변경 여부
14. 발견된 문제 / 남은 위험 / 다음 단계

반드시 명시할 것:

```text
- --commit을 실제로 1회 실행했는지
- 어떤 row가 append됐는지
- paper_virtual_fill source/reason이 보존됐는지
- 두 번째 commit은 실행하지 않았는지
- duplicate dry-run 결과
- paper_execution_log.csv 변경 여부
- paper_account_snapshot.csv 변경 여부
- paper_position_snapshot.csv 변경 여부
- outputs/front_test 변경 여부
```
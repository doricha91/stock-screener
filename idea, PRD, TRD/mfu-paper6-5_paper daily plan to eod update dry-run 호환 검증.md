# MFU-PAPER6-5 작업 지시문: paper daily plan → EOD update dry-run 호환 검증

## 목적

`outputs/paper_test/daily_action_plan_20260512.md`를 `run_paper_eod_update.py`가 안전하게 읽고, paper trade preview를 생성할 수 있는지 dry-run으로 검증한다.

이번 단계는 검증 전용이다.

```text
절대 --commit 하지 않는다.
paper_execution_log.csv를 수정하지 않는다.
snapshot 파일들을 수정하지 않는다.
```

## 배경

선행 완료:

- MFU-PAPER6-2: `run_paper_daily_plan.py` 추가
- MFU-PAPER6-3: paper daily plan 실제 생성 smoke 성공
- MFU-PAPER6-4A: SWITCH_IN symbol mapping bug 수정
- MFU-PAPER6-4B: `run_paper_daily_plan.py` date normalize 완료

현재 생성된 기준 파일:

```text
outputs/paper_test/daily_action_plan_20260512.md
```

이 파일은 `run_paper_daily_plan.py --date 20260512` 또는 `--date 2026-05-12`로 생성 가능해야 한다.

## 이번 MFU의 핵심 질문

1. `run_paper_eod_update.py`가 현재 어떤 daily action plan 파일을 읽는가?
2. `outputs/paper_test/daily_action_plan_20260512.md`를 읽을 수 있는가?
3. 여전히 `outputs/front_test` 쪽 plan을 읽고 있지는 않은가?
4. paper daily plan의 BUY / SELL / SWITCH_IN / SWITCH_OUT row를 parser가 이해하는가?
5. dry-run에서 trade preview가 합리적으로 생성되는가?
6. dry-run 중 paper_execution_log / snapshot 파일이 변경되지 않는가?

## 기준일

이번 smoke 기준일:

```text
2026-05-12
```

파일명 기준:

```text
20260512
```

사용 파일:

```text
outputs/paper_test/daily_action_plan_20260512.md
```

## 절대 금지

- `--commit` 실행 금지
- `paper_execution_log.csv` 수정 금지
- `paper_account_snapshot.csv` 수정 금지
- `paper_position_snapshot.csv` 수정 금지
- `paper_current_state_*.json` 수정 금지
- `outputs/front_test` 수정 금지
- DB schema / DB files 수정 금지
- live/broker 관련 구현 금지
- benchmark / MDD / CAGR / Sharpe 구현 금지
- 대규모 리팩토링 금지

## 1단계: 현재 상태 확인

```bat
set PYTHONPATH=.

git status --short outputs\front_test outputs\paper_test

python -m pytest tests/test_paper_daily_plan_generation.py -q
python -m pytest tests/test_paper_state_provider.py -q
python -m pytest tests/test_daily_plan_switch_symbol_mapping.py -q
```

## 2단계: paper daily plan 재생성

기존 plan이 있더라도 최신 코드 기준으로 다시 생성한다.

```bat
python scripts/run_paper_daily_plan.py --date 20260512
```

확인:

```bat
dir outputs\paper_test
type outputs\paper_test\daily_action_plan_20260512.md
```

확인할 것:

```text
- 파일이 outputs/paper_test 아래 생성되는가
- SWITCH_IN symbol이 0, 2가 아니라 실제 ticker인가
- 예: CF, BRK-B
- CPAY / GEN / VRSN 등 paper 보유 종목 기준 진단이 들어가는가
```

## 3단계: run_paper_eod_update.py가 plan path를 어떻게 찾는지 조사

아래 파일에서 daily action plan 경로 결정 로직을 확인한다.

```text
scripts/run_paper_eod_update.py
core/paths.py
```

확인할 것:

```text
1. 기본적으로 outputs/front_test plan을 읽는가?
2. outputs/paper_test plan을 읽는가?
3. --plan-path 옵션이 이미 있는가?
4. date 기준으로 plan path를 자동 생성하는가?
5. paper daily plan path helper가 있는가?
```

가능하면 코드 수정 없이 먼저 현재 동작을 파악한다.

## 4단계: EOD dry-run 실행

우선 기존 명령으로 dry-run한다.

```bat
python scripts/run_paper_eod_update.py --date 20260512 --allow-empty-journal
```

만약 `--date 20260512`가 실패하고 dashed format이 필요하면 아래도 시도한다.

```bat
python scripts/run_paper_eod_update.py --date 2026-05-12 --allow-empty-journal
```

만약 `--plan-path` 옵션이 이미 있다면 반드시 paper plan을 명시해서 실행한다.

```bat
python scripts/run_paper_eod_update.py --date 20260512 --plan-path outputs\paper_test\daily_action_plan_20260512.md --allow-empty-journal
```

`--plan-path` 옵션이 없다면, 이번 MFU에서는 임의로 대규모 구현하지 말고 “필요함”으로 보고한다.

## 5단계: dry-run 결과 확인

확인할 것:

```text
- dry-run 모드로 실행됐는가
- write_performed: False인가
- rows_to_append 값은 무엇인가
- duplicates_skipped 값은 무엇인가
- READY / BUY / SELL / SWITCH_IN / SWITCH_OUT row가 어떻게 해석됐는가
- paper daily plan을 읽었는가, front daily plan을 읽었는가
- CF / BRK-B 같은 SWITCH_IN ticker가 유지되는가
- 0 / 2 같은 숫자 ticker가 다시 등장하지 않는가
```

## 6단계: 파일 변경 여부 확인

실행 전후로 아래 파일 hash를 비교한다.

```bat
python -c "from pathlib import Path; import hashlib; files=['outputs/paper_test/paper_execution_log.csv','outputs/paper_test/paper_account_snapshot.csv','outputs/paper_test/paper_position_snapshot.csv']; [print(f, hashlib.sha256(Path(f).read_bytes()).hexdigest() if Path(f).exists() else 'MISSING') for f in files]"
```

오염 확인:

```bat
git status --short outputs\front_test outputs\paper_test
git diff -- outputs\front_test
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

## 실패 시 분류

실패하면 바로 크게 수정하지 말고 원인을 분류한다.

```text
1. plan path 문제
   - run_paper_eod_update.py가 front_test plan만 읽음
   - paper plan path 지정 수단 없음

2. date format 문제
   - run_paper_eod_update.py가 YYYYMMDD / YYYY-MM-DD 중 하나만 허용

3. parser 문제
   - paper daily plan row format을 못 읽음

4. SWITCH row 문제
   - SWITCH_OUT을 SELL로 해석하지 못함
   - SWITCH_IN을 BUY로 해석하지 못함

5. duplicate 문제
   - 이미 committed trade를 다시 append하려 함

6. dry-run safety 문제
   - dry-run인데 파일이 변경됨
```

작고 명확한 버그는 최소 수정 가능하다.  
단, `--plan-path` 추가나 path 구조 변경이 필요하면 MFU-PAPER6-6으로 분리한다.

## 성공 기준

아래 조건을 모두 만족하면 MFU-PAPER6-5 완료 처리한다.

```text
- paper daily plan이 outputs/paper_test에 존재
- run_paper_eod_update.py dry-run 실행 성공
- paper daily plan을 읽었는지 확인됨
- trade preview / rows_to_append / duplicates_skipped 확인됨
- SWITCH_IN / SWITCH_OUT row 해석 결과 확인됨
- dry-run에서 paper_execution_log 변경 없음
- account / position snapshot 변경 없음
- outputs/front_test 변경 없음
- --commit 실행하지 않음
```

## 결과 보고 형식

5,000자 이내로 작성한다.

포함할 항목:

1. Summary
2. 사용한 기준일
3. 생성/사용한 paper daily plan 경로
4. run_paper_eod_update.py의 plan path 탐색 방식
5. 실행한 dry-run 명령
6. dry-run 결과
7. BUY / SELL / SWITCH_IN / SWITCH_OUT 해석 결과
8. rows_to_append / duplicates_skipped
9. paper_execution_log / snapshot 변경 여부
10. outputs/front_test 변경 여부
11. 실패 또는 경고가 있다면 원인 분류
12. 다음 MFU 제안

반드시 명시할 것:

```text
- --commit을 실행하지 않았는지
- paper daily plan을 읽었는지, front daily plan을 읽었는지
- --plan-path 옵션이 필요한지
- paper_execution_log.csv 변경 여부
- paper_account_snapshot.csv 변경 여부
- paper_position_snapshot.csv 변경 여부
- outputs/front_test 변경 여부
```
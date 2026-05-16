# MFU-PAPER7-2 작업 지시문: same-date daily plan regeneration diff 최소 harness

## 목적

같은 날짜의 paper daily plan을 다시 생성했을 때, 기존 plan과 새 plan의 차이를 감지하는 최소 diff harness를 만든다.

이번 MFU의 목적은 완전 replay가 아니다.

목표:

```text
기존 daily_action_plan_YYYYMMDD.md
vs
새로 생성한 daily_action_plan_YYYYMMDD.md

차이가 있는지 자동으로 확인하고,
차이 요약 리포트를 생성한다.
```

## 기준 브랜치

```text
gemini_cli_update
```

## 배경

PAPER7-1에서 replay 수준을 아래처럼 정의했다.

```text
Level 1: 주요 입력 snapshot 저장
Level 2: regeneration diff 비교
Level 3: snapshot 기반 replay 강제 적용
```

현재 상태는 Level 1 일부 완료이며, Level 2가 미구현이다.

이번 MFU는 Level 2의 최소 구현이다.

## 핵심 원칙

```text
1. 기존 plan 파일을 직접 덮어쓰지 않는다.
2. 새로 생성한 plan은 임시/비교용 경로에 저장한다.
3. diff 결과만 리포트로 남긴다.
4. --commit은 절대 실행하지 않는다.
5. replay 강제 적용은 하지 않는다.
```

## 구현 범위

### 1. 새 스크립트 추가

권장 파일:

```text
scripts/check_paper_plan_regeneration_diff.py
```

기본 사용 예:

```bat
python scripts/check_paper_plan_regeneration_diff.py --date 20260512
```

동작:

```text
1. 기존 plan 경로 확인
   outputs/paper_test/daily_action_plan_YYYYMMDD.md

2. 새 plan을 비교용 경로에 생성
   outputs/paper_test/replay_diff/regenerated_daily_action_plan_YYYYMMDD.md

3. 기존 plan과 새 plan 비교

4. diff report 생성
   outputs/paper_test/replay_diff/daily_plan_diff_YYYYMMDD.md
```

### 2. 기존 plan 보호

기존 파일은 절대 덮어쓰지 않는다.

금지:

```text
outputs/paper_test/daily_action_plan_YYYYMMDD.md 직접 replace
```

허용:

```text
outputs/paper_test/replay_diff/*
```

### 3. diff 방식

처음에는 단순 text diff로 충분하다.

권장:

```text
- 파일 존재 여부
- 동일 여부
- unified diff 일부
- 변경된 섹션명
- action table 변경 여부
- config snapshot 경로/존재 여부
```

가능하면 아래 섹션 단위도 요약한다.

```text
시장 국면 및 정책
자산 현황
Trailing Stop
확정 매매 지시
리밸런싱 검토
후보 필터 진단
Journal table
```

### 4. timeout 대응

기존 `run_paper_daily_plan.py` full run은 timeout 위험이 있다.

따라서 이번 MFU에서는 두 단계 중 가능한 최소안을 선택한다.

A안: full regeneration 가능하면 사용

```text
기존 daily plan 생성 함수를 output override 가능하게 호출
```

B안: full run이 어렵다면 helper-level diff부터 구현

```text
- paper account state as-of 결과
- config snapshot
- universe metadata
- market_state summary
```

단, 어떤 방식을 선택했는지 결과 보고에 명확히 쓴다.

## 권장 구현 방식

가능하면 `run_paper_daily_plan.py`에 무리한 변경을 하지 말고, 내부 generator 함수에 output path override를 추가하거나 wrapper에서 임시 경로로 저장하게 한다.

예:

```python
generate_daily_plan(
    target_date=plan_date,
    output_path=regenerated_path,
    ...
)
```

기존 호출부가 깨지면 안 된다.

## 절대 금지

```text
- --commit 실행 금지
- paper_execution_log.csv 수정 금지
- paper_account_snapshot.csv 수정 금지
- paper_position_snapshot.csv 수정 금지
- 기존 daily_action_plan_YYYYMMDD.md 덮어쓰기 금지
- outputs/front_test 수정 금지
- DB 수정 금지
- config snapshot replay 강제 적용 금지
- universe replay 강제 적용 금지
- 대규모 리팩토링 금지
```

## 테스트 추가/수정

권장 테스트:

```text
tests/test_paper_plan_regeneration_diff.py
```

필수 테스트:

```text
1. 기존 plan과 새 plan이 같으면 status=SAME
2. 다르면 status=DIFF
3. 기존 plan 파일은 변경되지 않음
4. regenerated plan은 replay_diff 폴더에 생성됨
5. diff report가 생성됨
6. 기존 plan이 없으면 명확한 error 또는 status=MISSING_BASE
7. outputs/front_test를 건드리지 않음
```

## 검증 명령

```bat
set PYTHONPATH=.

python -m pytest tests/test_paper_plan_regeneration_diff.py -q
python -m pytest tests/test_paper_daily_plan_generation.py -q
python -m pytest tests/test_paper_config_snapshot.py -q
python -m pytest tests/test_universe_snapshot_asof.py -q
python -m pytest tests/test_paper_state_asof_cutoff.py -q

python -m py_compile scripts/check_paper_plan_regeneration_diff.py
```

## 수동 확인

가능하면 아래 중 하나를 실행한다.

```bat
python scripts/check_paper_plan_regeneration_diff.py --date 20260512
```

또는 timeout 위험이 크면:

```bat
python scripts/check_paper_plan_regeneration_diff.py --date 20260512 --mode helper
```

확인:

```text
- 기존 daily_action_plan_20260512.md 보존
- replay_diff 폴더 생성
- regenerated plan 또는 helper snapshot 생성
- daily_plan_diff_20260512.md 생성
- diff status가 SAME / DIFF / MISSING_BASE 중 하나로 표시
```

## 성공 기준

```text
- same-date regeneration diff harness 추가
- 기존 plan 파일을 덮어쓰지 않음
- diff report 생성
- SAME / DIFF / MISSING_BASE 상태 구분
- paper_execution_log / snapshots 변경 없음
- outputs/front_test 변경 없음
- DB 변경 없음
- replay 강제 적용은 하지 않음
```

## 결과 보고 형식

5천자 이내.

포함 항목:

```text
1. Summary
2. 변경 파일
3. diff harness 동작 방식
4. full regeneration 사용 여부
5. timeout 대응 방식
6. 생성되는 파일 경로
7. 테스트 결과
8. 수동 확인 결과
9. 기존 plan 보존 여부
10. paper_execution_log/snapshot 변경 여부
11. outputs/front_test 변경 여부
12. 남은 위험 / 다음 단계
```

반드시 명시:

```text
- 기존 daily_action_plan 파일을 덮어쓰지 않았는지
- replay_diff 폴더에 비교 산출물이 생성되는지
- config/universe snapshot을 replay에 강제 적용하지 않았는지
- PAPER8로 넘어갈 수 있는지
```
# MFU-PAPER6-9I 작업 지시문: quarterly universe snapshot as-of 선택

## 목적

`run_paper_daily_plan.py --date YYYYMMDD` 실행 시 항상 최신 universe snapshot을 쓰지 않고, `plan_date` 기준으로 허용된 universe snapshot을 선택하도록 수정한다.

확정 정책:

```text
1. plan_date가 속한 분기 안에서 plan_date 이하 최신 universe snapshot 사용
2. 해당 분기에 snapshot이 없으면 이전 분기 이하 최신 snapshot 사용 + warning
3. plan_date 이후 snapshot은 절대 사용 금지
4. 사용한 universe snapshot 정보는 config snapshot에 함께 저장
```

이번 MFU는 universe as-of 선택만 다룬다.

## 배경

이전 조사에서 `load_latest_universe_snapshot()`이 항상 최신 `outputs/universe/universe_snapshot_*.json`을 읽는 것으로 확인됐다. 따라서 과거 날짜 plan을 재생성할 때 현재 최신 universe가 섞일 수 있다.

현재 완료된 범위:

```text
- paper account state as-of cutoff 완료
- screener/indicator plan_date cutoff 완료
- market_status_log write 방지 완료
- final config snapshot 저장 완료
```

남은 입력 변동성 중 하나가 universe snapshot이다.

## 수정 대상

우선 확인/수정:

```text
core/universe_manager.py
core/daily_plan_generator.py
core/paper_config_snapshot.py
scripts/run_paper_daily_plan.py
tests/*universe*
tests/*paper_daily_plan*
tests/*paper_config_snapshot*
```

필요 시:

```text
core/paths.py
```

## 구현 요구사항

### 1. quarterly universe as-of loader 추가

권장 함수명:

```python
load_universe_snapshot_as_of_quarter(plan_date: str)
```

동작:

```text
plan_date가 속한 분기의 시작일/종료일 계산
해당 분기 내에서 snapshot_date <= plan_date인 최신 snapshot 선택
없으면 plan_date 이전의 가장 최신 snapshot 선택
단, plan_date 이후 snapshot은 절대 선택 금지
```

예:

```text
plan_date = 2026-05-12
분기 = 2026Q2
허용: 2026-04-01 ~ 2026-05-12 snapshot
없으면 2026Q1 또는 그 이전 최신 snapshot + warning
```

반환값은 snapshot payload뿐 아니라 metadata를 포함한다.

권장 metadata:

```text
universe_policy
universe_snapshot_path
universe_snapshot_date
universe_snapshot_quarter
universe_fallback_used
universe_warning
```

### 2. 기존 latest loader 영향 최소화

`load_latest_universe_snapshot()` 자체를 무조건 바꾸지 않는다.

paper daily plan 경로에서만 as-of loader를 사용한다.

기존 다른 경로가 최신 universe를 필요로 하면 그대로 유지한다.

### 3. config snapshot에 universe 정보 저장

MFU-PAPER6-9H에서 만든 config snapshot에 아래 필드를 추가한다.

```text
universe
  - policy
  - snapshot_path
  - snapshot_date
  - snapshot_quarter
  - fallback_used
  - warning
```

주의:

```text
config snapshot 저장 시 같은 날짜 archive 후 replace 정책 유지
```

### 4. daily plan diagnostics와 일관성 확인

Freshness Guard나 `universe_removed` 판단이 새 universe 기준으로 작동하는지 확인한다.

단, universe snapshot 생성 로직 자체는 이번 범위에서 바꾸지 않는다.

## 절대 금지

```text
- universe snapshot 생성 로직 변경 금지
- config snapshot replay 강제 적용 금지
- plan input snapshot 통합 금지
- paper_execution_log.csv 수정 금지
- paper_account_snapshot.csv 수정 금지
- paper_position_snapshot.csv 수정 금지
- outputs/front_test 수정 금지
- DB 수정 금지
- --commit 실행 금지
- 대규모 리팩토링 금지
```

## 테스트 추가/수정

권장 테스트:

```text
tests/test_universe_snapshot_asof.py
tests/test_paper_daily_plan_universe_asof.py
```

필수 테스트:

```text
1. 같은 분기 내 plan_date 이하 최신 snapshot 선택
2. plan_date 이후 snapshot은 선택하지 않음
3. 같은 분기 snapshot이 없으면 이전 분기 최신 snapshot 사용
4. fallback 사용 시 warning/metadata 기록
5. paper daily plan 경로에서 as-of universe loader 사용
6. config snapshot에 universe metadata 저장
7. 기존 load_latest_universe_snapshot 동작은 깨지지 않음
```

fixture 예:

```text
snapshots:
- universe_snapshot_20260401.json
- universe_snapshot_20260520.json

plan_date=2026-05-12
기대:
- 20260520 사용 금지
- 20260401 사용
```

fallback 예:

```text
snapshots:
- universe_snapshot_20260331.json
- universe_snapshot_20260520.json

plan_date=2026-05-12
기대:
- 20260520 사용 금지
- 20260331 사용
- fallback_used=True
```

## 검증 명령

```bat
set PYTHONPATH=.

python -m pytest tests/test_universe_snapshot_asof.py -q
python -m pytest tests/test_paper_daily_plan_universe_asof.py -q
python -m pytest tests/test_paper_config_snapshot.py -q
python -m pytest tests/test_paper_daily_plan_generation.py -q
python -m pytest tests/test_paper_daily_plan_screener_cutoff.py -q
python -m pytest tests/test_paper_state_asof_cutoff.py -q

python -m py_compile core/universe_manager.py core/daily_plan_generator.py core/paper_config_snapshot.py scripts/run_paper_daily_plan.py
```

## 수동 확인

가능하면 helper 수준으로 확인한다.

```bat
python -c "from core.universe_manager import load_universe_snapshot_as_of_quarter; r=load_universe_snapshot_as_of_quarter('2026-05-12'); print(r.metadata)"
```

full `run_paper_daily_plan.py`은 timeout 가능성이 있으므로 필수 완료 기준으로 삼지 않는다.

## 성공 기준

```text
- paper daily plan 경로에서 plan_date 기준 universe snapshot 선택
- plan_date 이후 snapshot 사용 금지
- 같은 분기 내 plan_date 이하 최신 snapshot 선택
- 없으면 이전 분기 최신 snapshot + warning
- config snapshot에 universe metadata 저장
- 기존 latest universe loader 영향 없음
- paper_execution_log / snapshots 변경 없음
- outputs/front_test 변경 없음
```

## 결과 보고 형식

5천자 이내.

포함 항목:

```text
1. Summary
2. 변경 파일
3. universe as-of 선택 정책
4. fallback 정책
5. config snapshot 저장 필드
6. 테스트 결과
7. 수동 확인 결과
8. paper_execution_log/snapshot 변경 여부
9. outputs/front_test 변경 여부
10. 남은 위험 / 다음 단계
```

반드시 명시:

```text
- plan_date 이후 universe snapshot을 차단했는지
- 같은 분기 내 plan_date 이하 최신 snapshot을 쓰는지
- fallback 시 이전 분기 snapshot과 warning을 쓰는지
- config snapshot에 universe metadata가 저장되는지
```
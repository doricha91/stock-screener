# MFU-PAPER6-9F 작업 지시문: screener/indicator plan_date cutoff 적용

## 목적

`run_paper_daily_plan.py --date YYYYMMDD`로 paper daily plan을 만들 때, screener 후보 생성과 indicator 계산이 `plan_date` 이후 데이터를 사용하지 않도록 수정한다.

핵심 정책:

```text
paper daily plan 후보 생성:
price / indicator / score / buy_signal은 plan_date 이하 데이터만 사용한다.
```

즉:

```text
plan_date = 2026-05-12
→ screener는 2026-05-12 이후 price row를 읽으면 안 됨
→ indicator도 2026-05-12 이하 history로만 계산
→ candidate latest row도 date <= 2026-05-12 중 최신 row 사용
```

이번 MFU는 screener/indicator cutoff만 다룬다.  
universe snapshot as-of, config snapshot, market_status_log write policy는 후속 MFU로 분리한다.

## 배경

MFU-PAPER6-9E 조사 결과:

- account state as-of는 9D에서 해결됨
- regime은 `target_date <= plan_date` 기준이라 비교적 안전함
- 하지만 screener 후보 생성은 `build_screener_results()`에서 `get_price_data(symbol, start_date=...)`를 호출하고 `end_date`를 넘기지 않음
- 그래서 DB에 plan_date 이후 데이터가 있으면 미래 row가 섞일 수 있음
- indicator / score / buy_signal도 마지막 row 기준이라 미래 데이터 혼입 위험이 큼

## 기준 브랜치

반드시 아래 브랜치 기준으로 작업한다.

```text
gemini_cli_update
```

## 수정 대상

우선 확인/수정:

```text
scripts/run_paper_daily_plan.py
core/daily_plan_generator.py
screener/screener.py
screener/data_manager.py
screener/indicator.py
screener/strategy.py
tests/*daily_plan*
tests/*screener*
tests/*paper*
```

## 구현 요구사항

### 1. build_screener_results에 as-of end_date 전달

`screener/screener.py`의 후보 생성 함수가 `as_of_date` 또는 `end_date`를 받을 수 있게 한다.

권장:

```python
build_screener_results(..., end_date: str | None = None)
```

동작:

```text
end_date가 있으면 종목별 price history는 date <= end_date만 사용
end_date가 없으면 기존 동작 유지
```

기존 호출부가 깨지면 안 된다.

### 2. data_manager.get_price_data end_date 지원 확인/추가

`get_price_data(symbol, start_date=...)`가 `end_date`를 지원하는지 확인한다.

없으면 최소 수정으로 추가한다.

정책:

```text
WHERE date >= start_date
AND date <= end_date
```

또는 pandas filtering으로 처리한다.

### 3. indicator 계산은 cutoff된 history로만 수행

indicator는 cutoff된 price history에 대해 계산해야 한다.

금지:

```text
전체 최신 history로 indicator 계산 후 마지막에 plan_date row만 고르기
```

권장:

```text
price history를 먼저 date <= plan_date로 자름
그 후 indicator / strategy / score 계산
마지막 row = plan_date 이하 최신 row
```

### 4. run_paper_daily_plan.py / daily_plan_generator 연결

`run_paper_daily_plan.py --date`의 normalized `plan_date`가 screener 후보 생성까지 전달되게 한다.

예:

```text
run_paper_daily_plan.py
→ generate_daily_plan(target_date=plan_date)
→ build_screener_results(end_date=plan_date)
```

### 5. stale/freshness guard 확인

candidate latest row는 `date <= plan_date` 중 최신이어야 한다.

확인:

```text
Latest Date가 plan_date보다 미래면 실패
stale_days 계산은 plan_date 기준이어야 함
```

## 절대 금지

```text
- paper_execution_log.csv 수정 금지
- snapshot 파일 수정 금지
- outputs/front_test 수정 금지
- outputs/paper_test 수정 금지
- DB 수정 금지
- --commit 실행 금지
- universe snapshot as-of 구현 금지
- config snapshot 구현 금지
- market_status_log write policy 수정 금지
- 대규모 리팩토링 금지
```

## 테스트 추가/수정

권장 테스트:

```text
tests/test_screener_asof_cutoff.py
tests/test_paper_daily_plan_screener_cutoff.py
```

필수 테스트:

```text
1. get_price_data(end_date=2026-05-12)는 2026-05-13 row를 포함하지 않음
2. build_screener_results(end_date=2026-05-12)는 latest row가 2026-05-12 이하
3. indicator/score/buy_signal이 plan_date 이하 데이터로만 계산됨
4. end_date=None이면 기존 동작 유지
5. run_paper_daily_plan 경로에서 plan_date가 screener end_date로 전달됨
6. stale_days가 plan_date 기준으로 계산됨
```

테스트 fixture 예:

```text
AAPL 2026-05-12 close=100
AAPL 2026-05-13 close=200
plan_date=2026-05-12

기대:
candidate close/latest row는 100 / 2026-05-12
2026-05-13 데이터는 사용 금지
```

## 수동 smoke

이번 MFU에서는 commit하지 않는다.

```bat
set PYTHONPATH=.

python scripts/run_paper_daily_plan.py --date 20260512
python scripts/run_paper_daily_plan.py --date 20260513
```

확인:

```text
- 생성된 plan의 Candidate Latest Date가 target date보다 미래가 아님
- price / score / buy_signal이 plan_date 이후 데이터를 쓰지 않음
- outputs/front_test 변경 없음
- paper_execution_log / snapshot 변경 없음
```

full smoke가 오래 걸리면, 실제 전체 실행 대신 테스트 fixture와 함수 단위 검증을 우선한다. timeout은 실패 원인으로 보고한다.

## 검증 명령

```bat
set PYTHONPATH=.

python -m pytest tests/test_screener_asof_cutoff.py -q
python -m pytest tests/test_paper_daily_plan_screener_cutoff.py -q
python -m pytest tests/test_paper_switching_parity.py -q
python -m pytest tests/test_paper_state_asof_cutoff.py -q
python -m pytest tests/test_paper_daily_plan_generation.py -q

python -m py_compile scripts/run_paper_daily_plan.py core/daily_plan_generator.py screener/screener.py screener/data_manager.py
```

## 성공 기준

```text
- screener price history가 plan_date 이하로 cutoff됨
- indicator / score / buy_signal이 plan_date 이후 데이터를 사용하지 않음
- candidate latest date가 plan_date보다 미래가 아님
- 기존 end_date 없는 screener 호출은 유지됨
- paper account as-of cutoff와 충돌 없음
- paper_execution_log / snapshots 변경 없음
- outputs/front_test 변경 없음
```

## 결과 보고 형식

5천자 이내.

포함 항목:

```text
1. Summary
2. 변경 파일
3. screener cutoff 적용 방식
4. data_manager end_date 처리
5. indicator/score/buy_signal cutoff 확인
6. stale/freshness 기준 확인
7. 테스트 결과
8. smoke 결과 또는 timeout 여부
9. paper_execution_log/snapshot 변경 여부
10. outputs/front_test 변경 여부
11. 남은 위험 / 다음 단계
```

반드시 명시:

```text
- plan_date 이후 price row가 차단되는지
- indicator가 cutoff된 history로 계산되는지
- candidate latest date가 plan_date 이하인지
- universe/config snapshot은 이번 범위에서 제외했는지
```
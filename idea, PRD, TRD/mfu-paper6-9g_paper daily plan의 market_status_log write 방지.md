# MFU-PAPER6-9G 작업 지시문: paper daily plan의 market_status_log write 방지

## 목적

`run_paper_daily_plan.py --date YYYYMMDD` 실행 시 market regime은 기존처럼 계산하되, `market_status_log`에는 기록하지 않도록 수정한다.

이번 MFU는 **DB 로그 오염 방지**만 다룬다.

핵심 정책:

```text
paper daily plan 생성:
- market_analyzer.get_market_state(target_date=plan_date, write_log=False)
- market_state 결과는 daily plan 생성에 그대로 사용
- market_status_log DB write는 하지 않음
```

## 배경

MFU-PAPER6-9E 조사 결과:

- regime / trade_halted / target_cash_ratio / SWITCHING_PREMIUM 등은 `get_market_state(target_date=plan_date)` 기준으로 비교적 안전함
- 하지만 `get_market_state()` 기본값이 `write_log=True`이면, 과거 날짜 plan 재생성 중에도 `market_status_log`가 갱신될 수 있음
- replay / 검증 / 과거 plan 재생성에서는 DB write가 발생하면 안 됨

## 이번 범위

포함:

```text
1. run_paper_daily_plan.py 또는 daily_plan_generator 경로에서 get_market_state 호출 시 write_log=False 적용
2. market_state 반환값은 기존처럼 plan 생성에 사용
3. market_status_log row count가 증가하지 않는지 검증
```

제외:

```text
- config snapshot 저장
- universe snapshot as-of 선택
- plan input snapshot 저장
- replay mode 정식 구현
- screener cutoff 재수정
- paper account cutoff 재수정
```

## 수정 대상

우선 확인/수정:

```text
scripts/run_paper_daily_plan.py
core/daily_plan_generator.py
market_analyzer.py
tests/*daily_plan*
tests/*market*
```

## 구현 요구사항

### 1. get_market_state 호출부 수정

paper daily plan 생성 경로에서 아래 형태가 되도록 한다.

```python
market_analyzer.get_market_state(
    target_date=plan_date,
    write_log=False,
)
```

주의:

```text
- 모든 get_market_state 호출을 무조건 write_log=False로 바꾸지 않는다.
- paper daily plan 생성 경로만 우선 적용한다.
- 백테스트/기존 market logging 정책은 이번 MFU에서 바꾸지 않는다.
```

### 2. market_state 사용은 유지

`write_log=False`여도 반환값은 기존과 동일하게 사용해야 한다.

확인 항목:

```text
regime
trade_halted
target_cash_ratio
trailing_stop_multiplier
SWITCHING_PREMIUM
triggers
plan
```

### 3. DB write 방지 검증

테스트 또는 수동 검증에서 plan 생성 전후 `market_status_log` row count가 증가하지 않아야 한다.

가능한 확인 방식:

```text
1. market_status_log count before 저장
2. paper daily plan market state 계산 경로 실행
3. market_status_log count after 확인
4. before == after
```

full run이 timeout되면 unit test / monkeypatch 기반 검증을 우선한다.

## 절대 금지

```text
- DB schema 수정 금지
- market_status_log 수동 삭제/수정 금지
- paper_execution_log.csv 수정 금지
- snapshot 파일 수정 금지
- outputs/front_test 수정 금지
- outputs/paper_test 수정 금지
- --commit 실행 금지
- universe/config snapshot 구현 금지
- 대규모 리팩토링 금지
```

## 테스트 추가/수정

권장 테스트:

```text
tests/test_paper_daily_plan_market_log_policy.py
```

필수 테스트:

```text
1. paper daily plan 경로에서 get_market_state가 write_log=False로 호출됨
2. write_log=False여도 market_state 결과가 plan 생성에 전달됨
3. market_status_log row count가 증가하지 않음
4. 기존 daily plan generation 테스트가 통과함
```

monkeypatch 예시 검증:

```text
fake_get_market_state(target_date, write_log)
→ write_log is False 확인
→ regime/plan/triggers 반환
```

## 검증 명령

```bat
set PYTHONPATH=.

python -m pytest tests/test_paper_daily_plan_market_log_policy.py -q
python -m pytest tests/test_paper_daily_plan_generation.py -q
python -m pytest tests/test_paper_state_asof_cutoff.py -q
python -m pytest tests/test_paper_switching_parity.py -q
python -m pytest tests/test_paper_daily_plan_screener_cutoff.py -q

python -m py_compile scripts/run_paper_daily_plan.py core/daily_plan_generator.py market_analyzer.py
```

## 수동 확인

가능하면 아래처럼 DB count를 비교한다.

```bat
python -c "import sqlite3; c=sqlite3.connect('outputs/market_data.db'); cur=c.cursor(); cur.execute('SELECT COUNT(*) FROM market_status_log'); print(cur.fetchone()[0]); c.close()"
```

이후 paper daily plan 관련 market state 계산을 실행한 뒤 다시 count를 확인한다.

주의:

```text
full run_paper_daily_plan.py는 timeout 가능성이 있으므로 필수 완료 기준으로 삼지 않는다.
```

## 성공 기준

```text
- paper daily plan 경로에서 write_log=False 적용
- market_state 반환값은 기존처럼 사용
- market_status_log가 증가하지 않음
- paper account cutoff / screener cutoff / switch parity 테스트 영향 없음
- paper_execution_log / snapshots 변경 없음
- outputs/front_test 변경 없음
```

## 결과 보고 형식

5천자 이내.

포함 항목:

```text
1. Summary
2. 변경 파일
3. get_market_state 호출 변경 내용
4. market_state 사용 유지 여부
5. market_status_log write 방지 검증 결과
6. 테스트 결과
7. paper_execution_log/snapshot 변경 여부
8. outputs/front_test 변경 여부
9. 남은 위험 / 다음 단계
```

반드시 명시:

```text
- write_log=False가 paper daily plan 경로에 적용됐는지
- market_status_log row count가 증가하지 않았는지
- config snapshot / universe as-of는 이번 범위에서 제외했는지
```
# MFU-PAPER6-9H 작업 지시문: final config snapshot 저장

## 목적

`run_paper_daily_plan.py --date YYYYMMDD` 실행 시, 해당 daily plan 생성에 실제 사용된 **최종 config snapshot**을 저장한다.

이번 MFU는 config/market_state 기록만 다룬다.

포함:

```text
- regime 적용 후 최종 config 저장
- market_state 저장
- market_status_summary 저장
- 같은 날짜 snapshot이 있으면 archive 후 replace
```

제외:

```text
- universe snapshot as-of 선택
- replay mode 정식 구현
- config snapshot을 replay에 강제 적용
- paper_execution_log / snapshot 수정
- --commit 실행
```

## 배경

MFU-PAPER6-9G에서 paper daily plan 경로는 `market_analyzer.get_market_state(..., write_log=False)`를 사용하게 됐다. 즉, market state는 계산하지만 `market_status_log`에는 기록하지 않는다.

이제 DB에 쓰지 않는 대신, daily plan 생성 시 사용한 market_state와 최종 config를 별도 JSON snapshot으로 남긴다.

## 저장 위치

새 폴더를 만든다.

```text
outputs/paper_test/config_snapshots/
```

파일명:

```text
paper_config_snapshot_YYYYMMDD.json
```

예:

```text
outputs/paper_test/config_snapshots/paper_config_snapshot_20260512.json
```

## archive 후 replace 정책

같은 날짜 snapshot이 이미 있으면 덮어쓰기 전에 archive한다.

권장 archive 위치:

```text
outputs/paper_test/archive/config_snapshots/
```

권장 archive 파일명:

```text
paper_config_snapshot_YYYYMMDD_archived_YYYYMMDD_HHMMSS.json
```

정책:

```text
기존 파일 있음 → archive 복사 → 새 snapshot으로 replace
기존 파일 없음 → 새로 저장
```

## 저장해야 할 내용

snapshot에는 기본값이 아니라 **daily plan에서 실제 사용된 최종값**을 저장한다.

필수 필드:

```text
schema_version
plan_date
generated_at
source
market_state_write_log
market_state
market_status_summary
final_config
notes
```

`market_state_write_log`는 반드시 `false`.

`market_state`에는 `get_market_state(target_date=plan_date, write_log=False)`의 주요 반환값을 저장한다.

최소 포함:

```text
date
regime
trade_halted
triggers
plan
```

`market_status_summary` 예:

```text
regime
trade_halted
target_cash_ratio
trailing_stop_multiplier
SWITCHING_PREMIUM
```

`final_config`에는 regime 적용 후 실제 사용값을 저장한다.

필수 변수:

```text
max_positions
score_threshold
entry_period
exit_period
rs_lookback
trailing_stop_multiplier
risk_per_trade
target_cash_ratio
SWITCHING_PREMIUM
ALLOW_PROFIT_SWITCH
SWITCHING_MAX_COUNT
strategy weights
```

주의:

```text
- portfolio_config.py 기본값만 저장하면 안 됨
- config.py regime rule 적용 후 최종값을 저장해야 함
- BULL이면 BULL 적용 후 target_cash_ratio, trailing_stop_multiplier, SWITCHING_PREMIUM 저장
```

## 구현 대상

우선 확인/수정:

```text
scripts/run_paper_daily_plan.py
core/daily_plan_generator.py
core/paths.py
```

필요 시 새 파일:

```text
core/paper_config_snapshot.py
```

권장 helper:

```python
save_paper_config_snapshot(
    plan_date: str,
    market_state: dict,
    final_config: dict,
    output_dir: Path,
) -> Path
```

또는 기존 구조에 맞춰 최소 구현한다.

## 절대 금지

```text
- universe as-of 구현 금지
- config snapshot을 replay에 강제 적용 금지
- market_status_log write 금지
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
tests/test_paper_config_snapshot.py
```

필수 테스트:

```text
1. config snapshot 파일이 outputs/paper_test/config_snapshots/에 저장됨
2. 같은 날짜 snapshot이 있으면 archive 후 replace됨
3. snapshot에 market_state가 포함됨
4. market_state_write_log=false가 저장됨
5. final_config에 regime 적용 후 값이 저장됨
6. BULL 예시에서 target_cash_ratio / trailing_stop_multiplier / SWITCHING_PREMIUM이 최종값인지 확인
7. 저장 과정에서 market_status_log가 증가하지 않음
```

기존 회귀 테스트:

```bat
set PYTHONPATH=.

python -m pytest tests/test_paper_config_snapshot.py -q
python -m pytest tests/test_paper_daily_plan_market_log_policy.py -q
python -m pytest tests/test_paper_daily_plan_generation.py -q
python -m pytest tests/test_paper_state_asof_cutoff.py -q
python -m pytest tests/test_paper_daily_plan_screener_cutoff.py -q

python -m py_compile scripts/run_paper_daily_plan.py core/daily_plan_generator.py core/paths.py
```

## 수동 확인

가능하면 아래를 실행한다.

```bat
set PYTHONPATH=.
python scripts/run_paper_daily_plan.py --date 20260512
```

full run이 timeout되면 helper/unit test 검증을 우선한다.

확인:

```text
outputs/paper_test/config_snapshots/paper_config_snapshot_20260512.json 생성
market_state_write_log=false
market_state.regime 존재
final_config.target_cash_ratio 존재
final_config.trailing_stop_multiplier 존재
final_config.SWITCHING_PREMIUM 존재
```

같은 날짜를 다시 생성했을 때:

```text
기존 snapshot archive 생성
새 snapshot replace
```

## 성공 기준

```text
- final config snapshot 저장
- market_state 저장
- market_status_summary 저장
- regime 적용 후 최종 config 저장
- 같은 날짜 snapshot archive 후 replace
- market_status_log 증가 없음
- paper_execution_log / snapshots 변경 없음
- outputs/front_test 변경 없음
- universe as-of는 이번 범위에서 제외
```

## 결과 보고 형식

5천자 이내.

포함 항목:

```text
1. Summary
2. 변경 파일
3. snapshot 저장 위치
4. 저장 필드
5. regime 적용 후 최종 config 저장 여부
6. market_state / market_status_summary 저장 여부
7. archive 후 replace 동작
8. market_status_log 변경 여부
9. 테스트 결과
10. paper_execution_log/snapshot 변경 여부
11. outputs/front_test 변경 여부
12. 남은 위험 / 다음 단계
```

반드시 명시:

```text
- 기본 config가 아니라 최종 config를 저장했는지
- market_state_write_log=false인지
- 같은 날짜 snapshot archive 후 replace가 되는지
- universe as-of는 이번 범위에서 제외했는지
```
# MFU-PAPER6-8 작업 지시문: multi-day paper 운영 연속성 검증

## 목적

MFU-PAPER6-7에서 2026-05-12 controlled commit smoke가 성공했으므로, 이번에는 **다른 신규 trading date**에서 아래 paper loop가 연속으로 정상 동작하는지 검증한다.

```text
paper_execution_log.csv + reducer
→ run_paper_daily_plan.py
→ outputs/paper_test/daily_action_plan_YYYYMMDD.md
→ run_paper_eod_update.py dry-run
→ run_paper_eod_update.py --commit
→ paper_current_state / account snapshot / position snapshot 갱신
→ duplicate dry-run 확인
```

이번 작업은 multi-day continuity smoke다.

## 기준

- 직전 완료일: 2026-05-12
- 신규 검증일: DB에 존재하는 2026-05-12 이후 첫 trading date
- 예: 2026-05-13 데이터가 있으면 2026-05-13 사용
- DB에 2026-05-13 데이터가 없으면, `daily_indicators` / `daily_price` / `market_index`가 모두 존재하는 다음 최신 거래일을 사용

## 사전 확인

```bat
set PYTHONPATH=.

python -c "import sqlite3; conn=sqlite3.connect('outputs/market_data.db'); cur=conn.cursor(); \
print('daily_indicators'); cur.execute('SELECT date, COUNT(*) FROM daily_indicators GROUP BY date ORDER BY date DESC LIMIT 10'); print(cur.fetchall()); \
print('daily_price'); cur.execute('SELECT date, COUNT(*) FROM daily_price GROUP BY date ORDER BY date DESC LIMIT 10'); print(cur.fetchall()); \
print('market_index'); cur.execute('SELECT date, COUNT(*) FROM market_index GROUP BY date ORDER BY date DESC LIMIT 10'); print(cur.fetchall()); conn.close()"
```

보고서에는 실제 사용한 신규 기준일을 반드시 적는다.

## 절대 금지

- 같은 날짜 `20260512`로 두 번째 `--commit` 실행 금지
- outputs/front_test 수정 금지
- DB schema / DB files 수정 금지
- live/broker 구현 금지
- benchmark / MDD / CAGR / Sharpe 추가 금지
- 대규모 리팩토링 금지

## 1단계: 관련 테스트

```bat
python -m pytest tests/test_paper_eod_virtual_fill_source.py -q
python -m pytest tests/test_paper_eod_rec_to_actual_fallback.py -q
python -m pytest tests/test_paper_eod_plan_path.py -q
python -m pytest tests/test_paper_daily_plan_generation.py -q
python -m pytest tests/test_daily_plan_switch_symbol_mapping.py -q
python -m pytest tests/test_paper_account_state.py -q

python -m py_compile core/paper_trade_preview.py scripts/run_paper_daily_plan.py scripts/run_paper_eod_update.py
```

## 2단계: 신규 날짜 paper daily plan 생성

예시가 2026-05-13인 경우:

```bat
python scripts/run_paper_daily_plan.py --date 20260513
```

확인:

```bat
type outputs\paper_test\daily_action_plan_20260513.md
```

확인할 것:

```text
- outputs/paper_test에 생성됐는지
- current_symbols가 2026-05-12 commit 후 상태 기준인지
  예: BRK-B, CF, GEN
- CPAY, VRSN이 이전 보유 종목처럼 남아 있지 않은지
- BUY/SELL/SWITCH row의 ticker가 실제 ticker인지
```

## 3단계: commit 전 dry-run

```bat
python scripts/run_paper_eod_update.py --date 20260513 --allow-empty-journal
```

확인:

```text
- input report = outputs/paper_test/daily_action_plan_20260513.md
- write_performed = False
- preview row가 있으면 source/reason 확인
- preview row가 없더라도 정상적으로 no-op 처리되는지 확인
- paper_execution_log / snapshot 변경 없음
```

dry-run 결과가 이상하면 commit하지 않는다.

## 4단계: 신규 날짜 commit

dry-run이 정상일 때만 실행한다.

```bat
python scripts/run_paper_eod_update.py --date 20260513 --allow-empty-journal --commit
```

확인:

```text
- write_performed = True 또는 no-op이면 명확한 no-op 결과
- rows_appended / duplicates_skipped
- paper_current_state_20260513.json 생성 또는 갱신
- paper_account_snapshot.csv에 신규 날짜 row 추가
- paper_position_snapshot.csv에 신규 날짜 row 추가
- source/reason 보존
```

## 5단계: duplicate dry-run

같은 날짜로 dry-run만 재실행한다.

```bat
python scripts/run_paper_eod_update.py --date 20260513 --allow-empty-journal
```

확인:

```text
- 이미 append된 row는 duplicates_skipped 처리
- rows_to_append = 0 또는 신규 미체결 row만 남음
- write_performed = False
- 두 번째 --commit은 절대 실행하지 않음
```

## 6단계: 오염 확인

```bat
git status --short outputs\front_test outputs\paper_test
git diff -- outputs\front_test
```

허용 변경:

```text
outputs/paper_test/daily_action_plan_YYYYMMDD.md
outputs/paper_test/paper_execution_log.csv
outputs/paper_test/paper_current_state_YYYYMMDD.json
outputs/paper_test/paper_account_snapshot.csv
outputs/paper_test/paper_position_snapshot.csv
outputs/paper_test/archive/*
```

허용 금지:

```text
outputs/front_test/*
DB files
```

## 성공 기준

- 신규 trading date로 paper daily plan 생성
- plan이 직전 commit 후 paper_state를 기준으로 생성됨
- dry-run 정상
- 신규 날짜 commit 1회 실행
- current_state / account snapshot / position snapshot 갱신
- duplicate dry-run에서 중복 append 방지
- outputs/front_test 변경 없음
- DB 변경 없음

## 결과 보고 형식

5,000자 이내.

포함 항목:

1. Summary
2. 사용한 신규 기준일
3. DB 최신 날짜 확인 결과
4. paper daily plan 생성 결과
5. commit 전 dry-run 결과
6. 실제 commit 결과
7. rows_appended / duplicates_skipped
8. current_state 변화
9. account snapshot 결과
10. position snapshot 결과
11. duplicate dry-run 결과
12. outputs/front_test 변경 여부
13. DB 변경 여부
14. 발견 문제 / 다음 단계

반드시 명시:

```text
- 20260512에 두 번째 commit을 하지 않았는지
- 신규 날짜에 --commit을 1회만 실행했는지
- paper_state가 직전 commit 결과를 반영했는지
- paper_execution_log / snapshots 변경 여부
```
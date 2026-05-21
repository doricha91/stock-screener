# MFU-PAPER11-7 작업 지시문: market data freshness / readiness check

## 목적

PAPER11-7의 목표는 `paper.py prepare-data` 실행 후, `run_paper_daily_plan.py`를 실행해도 되는지 판단할 수 있는 **market data freshness / readiness check**를 구현하는 것이다.

이번 단계는 데이터 최신성 검증 전용이다.  
시장데이터 수집, DB write, paper plan 생성, EOD commit은 실행하지 않는다.

반드시 명시:

```text
이번 PAPER11-7은 market data freshness / readiness check 구현이며, 데이터 수집 실행, DB write, paper plan 생성, EOD commit은 포함하지 않는다.
```

## 배경

PAPER11-6에서 `paper.py prepare-data`가 추가됐다.

현재 prepare-data는 다음을 수행한다.

```text
S&P500/Nasdaq100 ticker 수집
market_index 갱신
tickers 갱신
daily_price 갱신
daily_indicators 갱신
optional universe snapshot 갱신
```

하지만 재사용한 collector/processor 함수들이 structured status를 반환하지 않아, 실제로 DB가 목표 날짜 기준으로 충분히 최신인지 판단하는 기능이 약하다.

따라서 PAPER11-7에서는 DB를 읽어서 freshness를 검증한다.

## 구현 파일

권장 추가:

```text
core/paper_data_freshness.py
scripts/check_paper_data_freshness.py
tests/test_paper_data_freshness.py
docs/TRD/mfu_paper11_7_data_freshness.md
```

수정:

```text
scripts/paper.py
tests/test_paper_cli.py
```

## CLI 요구사항

추가 명령:

```text
python scripts/paper.py data-freshness --date YYYYMMDD
python scripts/paper.py data-freshness --date YYYYMMDD --strict
python scripts/check_paper_data_freshness.py --date YYYYMMDD
```

동작:

```text
market_data.db를 read-only로 조회
필수 테이블 존재 여부 확인
목표 날짜 기준 최신성 확인
결과를 PASS / PASS_WITH_WARNINGS / FAIL로 출력
```

## 검사 대상

기본 DB 경로:

```text
core.paths.market_db_path()
```

검사 테이블:

```text
daily_price
market_index
daily_indicators
tickers
```

선택 검사:

```text
market_status_log
outputs/universe/universe_snapshot_YYYYMMDD.json
```

## freshness 체크 항목

### 1. DB 존재 여부

```text
market_data.db 없음 = error
DB 연결 실패 = error
```

### 2. 필수 테이블 존재 여부

아래 테이블이 없으면 error.

```text
daily_price
market_index
daily_indicators
tickers
```

### 3. daily_price 최신성

확인:

```text
MAX(date) FROM daily_price
target_date 이하 최신 날짜
symbol count
row count
```

정책:

```text
daily_price에 데이터 없음 = error
MAX(date) < target_date = warning
strict 모드에서는 error
```

단, 주말/휴장일 가능성이 있으므로 기본 모드에서는 warning으로 둔다.

### 4. market_index 최신성

필수 symbol 후보:

```text
SPY
QQQ
^VIX
```

확인:

```text
각 symbol별 MAX(date)
각 symbol별 row count
```

정책:

```text
SPY 없음 = error
QQQ 없음 = warning
^VIX 없음 = warning
SPY MAX(date) < target_date = warning
strict 모드에서는 error
```

### 5. daily_indicators 최신성

확인:

```text
MAX(date) FROM daily_indicators
symbol count
row count
```

정책:

```text
daily_indicators 없음 = error
MAX(date) < daily_price MAX(date) = warning
strict 모드에서는 error
```

이유:

```text
market_analyzer.get_market_state()는 daily_indicators에 의존하므로,
daily_price보다 daily_indicators가 오래되면 regime 판단이 stale할 수 있다.
```

### 6. tickers 상태

확인:

```text
tickers row count
listing_board 분포, 컬럼이 있으면
```

정책:

```text
tickers row count = 0 -> error
tickers row count가 너무 작으면 warning
```

기본 최소값은 보수적으로 둔다.

```text
min_ticker_count = 50
```

### 7. universe snapshot

기본은 optional check다.

확인:

```text
outputs/universe/universe_snapshot_YYYYMMDD.json 존재 여부
```

정책:

```text
없음 = warning
strict 모드에서도 warning 유지
```

이유:

```text
universe는 매일 갱신하지 않을 수 있다.
```

## 결과 모델

내부 result 구조:

```text
result: PASS / PASS_WITH_WARNINGS / FAIL
error_count
warning_count
target_date
market_db_path
checks[]
```

check item 필드:

```text
severity
check_name
status
message
table
symbol
latest_date
row_count
suggestion
```

## report 산출물

기본은 콘솔 출력.

선택 옵션:

```text
--write-report
```

생성 파일:

```text
outputs/paper_test/reports/paper_data_freshness_report.md
outputs/paper_test/reports/paper_data_freshness_issues.csv
```

## paper.py 연결

`scripts/paper.py`에 subcommand 추가:

```text
data-freshness
```

주의:

```text
prepare-data 안에서 자동 실행하지 않는다.
plan 안에서 자동 실행하지 않는다.
```

단, 향후 shortcut 단계에서 아래 흐름으로 묶을 수 있도록 함수는 분리한다.

```text
prepare-data
→ data-freshness
→ plan
```

## 절대 금지

```text
시장데이터 수집 실행 금지
data_collector.update_* 호출 금지
data_processor.update_technical_indicators 호출 금지
DB write 금지
paper.py prepare-data 실행 금지
paper plan 생성 금지
EOD dry-run 실행 금지
EOD commit 실행 금지
reports 생성 금지
review append 금지
outputs/front_test 수정 금지
setup_db.py 호출 금지
```

## 테스트

테스트 파일:

```text
tests/test_paper_data_freshness.py
tests/test_paper_cli.py
```

필수 테스트:

```text
1. DB 없음이면 FAIL
2. 필수 테이블 없음이면 FAIL
3. daily_price 데이터 없음이면 FAIL
4. SPY market_index 없음이면 FAIL
5. daily_indicators가 daily_price보다 오래되면 warning
6. strict 모드에서는 stale warning이 error로 승격
7. tickers row count 0이면 FAIL
8. universe snapshot 없음은 warning
9. warning만 있으면 PASS_WITH_WARNINGS
10. error 있으면 FAIL
11. --write-report 없으면 report 파일 생성 안 함
12. paper.py data-freshness가 core checker를 호출
13. data-freshness가 DB write 함수를 호출하지 않음
```

테스트는 임시 sqlite DB를 사용한다.  
실제 `outputs/market_data.db`는 수정하지 않는다.

## 검증 명령

```text
set PYTHONPATH=.

python -m pytest tests/test_paper_data_freshness.py tests/test_paper_cli.py -q
python -m py_compile core/paper_data_freshness.py
python -m py_compile scripts/check_paper_data_freshness.py
python -m py_compile scripts/paper.py

python scripts/paper.py --help
python scripts/paper.py data-freshness --date YYYYMMDD
```

주의:

```text
data-freshness는 read-only이므로 실제 실행 가능하다.
단, --write-report를 붙이면 outputs/paper_test/reports/* 파일을 생성할 수 있다.
```

## 성공 기준

```text
market_data.db freshness/readiness를 read-only로 검증한다.
daily_price, market_index, daily_indicators, tickers 상태를 확인한다.
daily_indicators stale 위험을 감지한다.
PASS / PASS_WITH_WARNINGS / FAIL이 구분된다.
strict 모드가 동작한다.
paper.py data-freshness 명령이 추가된다.
DB write와 paper 원장 수정이 없다.
outputs/front_test를 수정하지 않는다.
테스트가 통과한다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 변경 파일
3. 추가된 CLI
4. freshness 체크 항목
5. PASS/WARNING/FAIL 정책
6. strict 옵션 동작
7. report 생성 옵션
8. 제외한 항목
9. 테스트 결과
10. 실제 data-freshness 실행 결과
11. DB write 여부
12. paper 원장 CSV 변경 여부
13. outputs/front_test 변경 여부
14. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER11-7은 market data freshness / readiness check 구현이며, 데이터 수집 실행이나 DB write는 포함하지 않는다.
```
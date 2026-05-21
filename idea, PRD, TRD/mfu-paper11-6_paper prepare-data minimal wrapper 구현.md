# MFU-PAPER11-6 작업 지시문: paper prepare-data minimal wrapper 구현

## 목적

PAPER11-6의 목표는 `paper.py prepare-data` 명령을 추가해, paper daily plan 생성 전에 필요한 최소 market data 입력을 준비하는 것이다.

이번 단계는 `generate_daily_plan()`이 의존하는 `market_data.db`와 선택적 universe snapshot 준비에 집중한다.

반드시 명시:

```text
이번 PAPER11-6은 paper prepare-data minimal wrapper 구현이며, EOD commit, reports, review append, screener_history 저장은 포함하지 않는다.
```

## 배경

조사 결과:

```text
run_paper_daily_plan.py는 screener_results.csv를 읽지 않는다.
screener_history도 직접 사용하지 않는다.
market_data.db와 universe_snapshot_*.json을 기반으로 daily plan 후보를 재생성한다.
```

`generate_daily_plan()` 의존 데이터:

```text
outputs/market_data.db
- market_index
- daily_price
- daily_indicators
- tickers
- market_status_log 조회

outputs/universe/universe_snapshot_*.json
```

현재 문제:

```text
run_screener.py는 price/index/ticker update와 screener 저장을 수행하지만,
daily_indicators 갱신은 data_processor.update_technical_indicators()와 분리되어 있다.
```

따라서 `run_screener.py` 단일 래핑은 피한다.

## 구현 파일

수정:

```text
scripts/paper.py
tests/test_paper_cli.py
docs/TRD/mfu_paper11_6_paper_prepare_data.md
```

권장 추가:

```text
core/paper_prepare_data.py
scripts/prepare_paper_data.py
tests/test_paper_prepare_data.py
```

대규모 리팩토링은 금지한다.

## 구현 전 확인

구현 전에 반드시 아래를 확인한다.

```text
1. data_collector.update_market_indices() 호출 방식
2. data_collector.update_tickers_info(tickers) 호출 방식
3. data_collector.update_stock_data(tickers) 호출 방식
4. data_processor.update_technical_indicators() 인자와 부작용
5. update_universe.py를 함수 호출할 수 있는지, subprocess가 필요한지
6. 각 함수의 실패 시 exception / return behavior
7. 각 함수가 수정하는 DB/table/file
```

확인 결과를 TRD에 기록한다.

## CLI 요구사항

추가 명령:

```text
python scripts/paper.py prepare-data --date YYYYMMDD
python scripts/paper.py prepare-data --date YYYYMMDD --universe
python scripts/paper.py prepare-data --date YYYYMMDD --skip-prices
python scripts/paper.py prepare-data --date YYYYMMDD --skip-indicators
```

기본 동작:

```text
prices/index/tickers refresh 실행
daily_indicators refresh 실행
universe snapshot은 기본 실행하지 않음
```

`--universe`가 있을 때만 universe snapshot 갱신을 시도한다.

## prepare-data 최소 단계

### 1. ticker 수집

기존 함수 재사용:

```text
screener.data_collector.get_sp500_tickers()
screener.data_collector.get_nasdaq100_tickers()
```

정책:

```text
중복 제거
정렬
ticker count 출력
```

### 2. market index / tickers / daily price 갱신

기존 함수 재사용 후보:

```text
data_collector.update_market_indices()
data_collector.update_tickers_info(tickers)
data_collector.update_stock_data(tickers)
```

수정 대상:

```text
outputs/market_data.db
- market_index
- tickers
- daily_price
```

### 3. daily_indicators 갱신

기존 함수 재사용 후보:

```text
data_processor.update_technical_indicators()
```

수정 대상:

```text
outputs/market_data.db
- daily_indicators
```

주의:

```text
run_screener.py만 실행해서는 이 단계가 보장되지 않으므로 prepare-data에서 명시적으로 실행한다.
```

### 4. universe snapshot optional 갱신

`--universe` 옵션이 있을 때만 실행한다.

수정 대상:

```text
outputs/universe/universe_snapshot_YYYYMMDD.json
```

기본 실행에서 universe를 갱신하지 않는 이유:

```text
universe는 매일 바뀌지 않음
불필요한 파일 변화를 줄이기 위함
```

### 5. readiness summary 출력

콘솔에 아래를 요약한다.

```text
ticker count
market DB path
prices/index/tickers update status
daily_indicators update status
universe update status
errors/warnings
```

선택 산출물:

```text
outputs/paper_test/reports/paper_prepare_data_summary.md
```

단, 기본 구현은 콘솔 출력만 해도 된다.

## 포함하지 않을 것

```text
screener_history 저장
outputs/screener_results.csv 생성
screener.screener.run_screener(save=True) 실행
financials 갱신
scripts/setup_db.py 실행
market_status_log drop/recreate
paper plan 생성
EOD dry-run 실행
EOD --commit 실행
reports 생성
review append
```

## market_status_log 정책

prepare-data에서는 `market_analyzer.get_market_state(write_log=True)`를 호출하지 않는다.

이유:

```text
market_status_log에 부작용이 생길 수 있음
prepare-data 목적은 DB 입력 준비이지 regime log 기록이 아님
```

필요하면 향후 별도 MFU에서 다룬다.

## paper.py 연결

`scripts/paper.py`에 `prepare-data` subcommand를 추가한다.

주의:

```text
preflight 안에 prepare-data를 넣지 않는다.
plan 안에서 prepare-data를 자동 실행하지 않는다.
prepare-data는 사용자가 명시적으로 실행하는 DB writer command다.
```

권장 흐름:

```text
python scripts/paper.py prepare-data --date YYYYMMDD
python scripts/paper.py plan --date YYYYMMDD
```

## 안전 원칙

```text
prepare-data는 DB writer다.
명시적으로 실행할 때만 동작한다.
outputs/front_test는 수정하지 않는다.
paper_execution_log.csv는 수정하지 않는다.
paper_account_snapshot.csv는 수정하지 않는다.
paper_position_snapshot.csv는 수정하지 않는다.
```

## 테스트

테스트 파일:

```text
tests/test_paper_prepare_data.py
tests/test_paper_cli.py
```

필수 테스트:

```text
1. paper.py --help에 prepare-data 표시
2. prepare-data가 ticker 수집 함수를 호출
3. prepare-data가 update_market_indices 호출
4. prepare-data가 update_tickers_info 호출
5. prepare-data가 update_stock_data 호출
6. prepare-data가 update_technical_indicators 호출
7. --skip-prices면 price/index/ticker update 생략
8. --skip-indicators면 indicators update 생략
9. --universe 없으면 universe update 생략
10. --universe 있으면 universe update 호출
11. run_screener(save=True)를 호출하지 않음
12. setup_db.py를 호출하지 않음
13. EOD commit을 호출하지 않음
14. outputs/front_test를 수정하지 않음
```

테스트에서는 mock/monkeypatch를 사용해 실제 DB write와 API 호출을 막는다.

## 검증 명령

```text
set PYTHONPATH=.

python -m pytest tests/test_paper_prepare_data.py tests/test_paper_cli.py -q
python -m py_compile core/paper_prepare_data.py
python -m py_compile scripts/prepare_paper_data.py
python -m py_compile scripts/paper.py

python scripts/paper.py --help
```

주의:

아래 명령은 실제 DB write/API 호출 가능성이 있으므로 결과 보고 시 실행 여부를 명확히 남긴다.

```text
python scripts/paper.py prepare-data --date YYYYMMDD
```

## 성공 기준

```text
paper.py prepare-data 명령이 추가된다.
price/index/tickers update와 daily_indicators update가 분리 실행된다.
universe snapshot은 optional이다.
run_screener.py 단일 래핑이 아니다.
screener_history와 screener_results.csv는 생성하지 않는다.
setup_db.py는 호출하지 않는다.
paper 원장 CSV와 outputs/front_test는 수정하지 않는다.
테스트가 통과한다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 변경 파일
3. 추가된 CLI
4. 구현 전 확인 결과
5. prepare-data 실행 단계
6. skip 옵션 동작
7. universe 옵션 동작
8. 제외한 항목
9. 테스트 결과
10. 실제 prepare-data 실행 여부
11. DB write 여부
12. paper 원장 CSV 변경 여부
13. outputs/front_test 변경 여부
14. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER11-6은 paper prepare-data minimal wrapper 구현이며, EOD commit, reports, review append, screener_history 저장은 포함하지 않는다.
```
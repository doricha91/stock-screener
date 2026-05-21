# MFU-PAPER11-5 작업 지시문: market data / screener input pipeline 조사

## 목적

PAPER11-5의 목표는 `paper.py prepare-data` wrapper를 만들기 전에, 현재 프로젝트의 **시장데이터 수집 및 screener 입력 생성 체인**을 조사하는 것이다.

이번 작업은 조사 전용이다.  
코드 수정, DB 수정, 데이터 수집 실행, paper 원장 수정은 하지 않는다.

반드시 명시:

```text
이번 PAPER11-5는 market data / screener input pipeline 조사이며, 데이터 수집 실행이나 DB write는 포함하지 않는다.
```

## 배경

현재 paper 운영 체인은 아래까지 연결됐다.

```text
paper.py preflight
paper.py plan
paper.py eod --dry-run / --commit
paper.py reports
paper.py review-template / review-validate / review-append
```

하지만 `run_paper_daily_plan.py`는 market DB와 universe/screener 입력이 준비돼 있어야 정상적으로 plan을 생성한다.

따라서 shortcut command를 만들기 전에, 시장데이터 수집/처리 체인을 먼저 조사해야 한다.

## 핵심 질문

아래 질문에 답하라.

1. 현재 시장데이터 수집을 담당하는 script/module은 무엇인가?
2. `outputs/market_data.db`를 쓰는 writer script는 무엇인가?
3. `daily_price`, `daily_indicators`, `market_index`, `financials`, `tickers`는 각각 어디서 생성/갱신되는가?
4. 기술적 지표 계산은 어느 script/module에서 수행되는가?
5. universe 또는 screener 입력 데이터는 어디서 만들어지는가?
6. `run_paper_daily_plan.py`가 실제로 의존하는 DB table 또는 입력 파일은 무엇인가?
7. `market_analyzer.get_market_state()`가 의존하는 데이터는 무엇인가?
8. 데이터 수집과 지표 계산은 한 번에 실행되는가, 별도 단계인가?
9. 현재 안정적으로 감쌀 수 있는 prepare-data entrypoint가 있는가?
10. 어떤 스크립트가 read-only이고, 어떤 스크립트가 DB writer인가?
11. paper 운영 전에 반드시 실행해야 하는 최소 데이터 준비 단계는 무엇인가?
12. `paper.py prepare-data`로 묶으면 위험한 단계는 무엇인가?

## 조사 대상

우선 아래 파일/폴더를 확인한다.

```text
scripts/
core/
screener/
backtesting/
config.py
portfolio_config.py
market_analyzer.py
core/paths.py
```

아래 키워드로 검색한다.

```text
yfinance
download
fetch
update
daily_price
daily_indicators
market_index
financials
tickers
market_data.db
DataManager
data_manager
calculate_indicators
indicator
screener
universe
get_market_state
SPY
QQQ
VIX
```

## 조사 범위

허용:

```text
파일 읽기
함수 호출 관계 추적
argparse 옵션 확인
DB path 참조 위치 확인
read/write 여부 분류
조사 리포트 작성
```

금지:

```text
코드 수정
DB 수정
데이터 수집 실행
yfinance/API 호출 실행
paper.py 수정
paper_execution_log.csv 수정
paper_account_snapshot.csv 수정
paper_position_snapshot.csv 수정
outputs/front_test 수정
--commit 실행
대규모 리팩토링
```

## 반드시 정리할 것

### 1. 현재 데이터 파이프라인 후보

아래 형식으로 정리한다.

```text
Step 1. ticker/universe 준비
- 관련 script/module:
- 입력:
- 출력:
- read/write 여부:

Step 2. price data update
- 관련 script/module:
- 입력:
- 출력 DB/table:
- read/write 여부:

Step 3. market index update
- 관련 script/module:
- 입력:
- 출력 DB/table:
- read/write 여부:

Step 4. indicator calculation
- 관련 script/module:
- 입력 DB/table:
- 출력 DB/table:
- read/write 여부:

Step 5. screener input/output 생성
- 관련 script/module:
- 입력:
- 출력:
- read/write 여부:

Step 6. paper daily plan 의존성
- run_paper_daily_plan.py가 직접/간접 의존하는 데이터:
```

### 2. DB writer 목록

아래 파일 또는 테이블을 수정하는 script/module을 명확히 표시한다.

```text
outputs/market_data.db
daily_price
daily_indicators
market_index
financials
tickers
```

분류:

```text
read-only
DB writer
file writer
dangerous writer
unknown
```

### 3. prepare-data 후보 entrypoint

아래 중 하나로 판단한다.

```text
A. 기존 단일 script를 paper.py prepare-data에서 감싸면 충분함
B. 여러 script를 순서대로 호출해야 함
C. 현재 entrypoint가 불명확해서 별도 정리가 필요함
D. 데이터 수집과 지표 계산을 먼저 분리/정리해야 함
```

### 4. paper.py prepare-data 설계 제안

조사 후 아래를 제안한다.

```text
추천 명령 예:
python scripts/paper.py prepare-data --date YYYYMMDD

또는:
python scripts/paper.py prepare-data --date YYYYMMDD --prices --indicators --market-index
```

단, 이번 작업에서는 구현하지 않는다.

## 산출물

조사 리포트만 작성한다.

권장 경로:

```text
docs/TRD/mfu_paper11_5_market_data_pipeline_investigation.md
```

## 검증 명령

코드 수정이 없으므로 필수 테스트는 없다.

문법 확인이 필요한 경우에만 아래를 실행한다.

```text
python -m py_compile <조사한 주요 script>
```

데이터 수집 script는 실행하지 않는다.  
DB write 가능성이 있는 명령은 실행하지 않는다.

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 조사한 파일
3. 현재 market data pipeline 후보
4. screener input 생성 흐름
5. run_paper_daily_plan.py 의존 데이터
6. DB writer / read-only 구분
7. prepare-data 후보 entrypoint
8. 위험 구간
9. outputs/front_test 오염 가능성
10. paper.py prepare-data 권장 방향
11. 추가 결정 필요 사항
```

반드시 명시:

```text
이번 작업은 market data / screener input pipeline 조사이며, 코드 수정과 DB write는 하지 않는다.
```
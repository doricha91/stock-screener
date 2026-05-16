# MFU-PAPER6-9E 작업 지시문: daily plan 입력 데이터 as-of 기준 조사

## 목적

`run_paper_daily_plan.py --date YYYYMMDD`가 특정 날짜 plan을 만들 때, 계좌 상태 외의 입력값들이 어떤 기준일로 읽히는지 조사한다.

이번 MFU는 조사 전용이다. production code 수정은 하지 않는다.

핵심 질문:

```text
특정 날짜 plan을 나중에 다시 생성해도 같은 결과가 나오려면,
market data / indicator / universe / regime / config가 plan_date 기준으로 고정되어 있는가?
```

## 배경

MFU-PAPER6-9D 결과:

- daily plan용 paper account state는 `trade_date < plan_date`로 cutoff됨
- EOD/report 의미는 기존처럼 유지됨
- 하지만 market data / indicator / universe / regime / config snapshot은 아직 as-of 보장 대상이 아님
- run_paper_daily_plan.py full smoke는 screening timeout으로 완료되지 않았고, provider level cutoff만 확인됨

이번 작업은 계좌 상태 외 입력값의 기준일을 확인한다.

## 기준 브랜치

반드시 아래 브랜치 기준으로 조사한다.

```text
gemini_cli_update
```

## 조사 대상

우선 조사:

```text
scripts/run_paper_daily_plan.py
core/daily_plan_generator.py
core/paper_state_provider.py
market_analyzer.py
screener/data_manager.py
screener/indicator.py
screener/strategy.py
core/config_factory.py
core/portfolio_config.py
config.py
core/paths.py
```

필요 시:

```text
core/target_portfolio_state.py
DB 접근 함수
tests/*daily_plan*
tests/*paper*
```

## 조사 범위

### 1. plan_date 의미 확인

`run_paper_daily_plan.py --date 20260512`에서 `date`가 어떤 의미로 쓰이는지 확인한다.

확인할 것:

```text
- plan_date인지
- market data 기준일인지
- indicator latest date인지
- regime 판단 기준일인지
- output filename 기준일인지
```

특히 daily plan 문구의 “전일 종가 기준”과 실제 `Latest Date`가 일치하는지 확인한다.

### 2. market price 기준일

daily plan이 가격 데이터를 어디서 읽는지 확인한다.

확인할 것:

```text
- daily_price에서 plan_date row를 읽는가?
- plan_date 이전 최신 row를 읽는가?
- 전체 최신 데이터를 읽은 뒤 plan_date로 필터링하는가?
- 종목별 latest date가 다를 수 있는가?
- stale/freshness guard가 어떤 기준으로 동작하는가?
```

### 3. indicator 기준일

daily_indicators 또는 계산된 indicator가 어떤 기준일로 들어오는지 확인한다.

확인할 것:

```text
- plan_date의 indicator를 쓰는가?
- plan_date 이전 최신 indicator를 쓰는가?
- 미래 날짜 indicator가 섞일 가능성이 있는가?
- score / rs_val / buy_signal 계산 시 plan_date 이후 데이터가 들어갈 수 있는가?
```

### 4. universe 기준일

후보 universe가 어떤 기준으로 정해지는지 확인한다.

확인할 것:

```text
- tickers 테이블 최신 상태를 그대로 쓰는가?
- plan_date 기준 universe snapshot이 있는가?
- universe_removed 판단은 어떤 날짜 기준인가?
- 과거 날짜 plan 재생성 시 현재 universe 변경이 영향을 주는가?
```

예: `DAY: universe_removed` 같은 항목이 어떤 로직에서 나오는지 확인한다.

### 5. regime 기준일

market regime이 어떻게 계산되는지 확인한다.

확인할 것:

```text
- market_analyzer.get_market_state(target_date=plan_date)를 쓰는가?
- market_status_log를 읽는가, 매번 재계산하는가?
- target_date 이후 market data가 섞일 가능성이 있는가?
- trade_halted / target_cash_ratio / SWITCHING_PREMIUM이 plan_date 기준으로 확정되는가?
```

### 6. config 기준

config가 현재 코드 기준인지, 당시 snapshot인지 확인한다.

확인할 것:

```text
- make_config()가 현재 소스 코드의 값을 쓰는가?
- portfolio_config.py 변경 시 과거 plan 결과가 달라지는가?
- param_grid.py 값이 paper daily plan에 영향을 주는가?
- regime별 overwrite 후 최종값이 어디에 기록되는가?
```

### 7. full smoke timeout 원인 조사

9D에서 `run_paper_daily_plan.py` full smoke가 timeout된 이유를 조사한다.

확인할 것:

```text
- screening 전체 universe가 너무 큰가?
- DB query가 느린가?
- indicator 계산이 매번 full scan인가?
- 특정 함수에서 병목이 있는가?
- smoke용 fast mode나 target_tickers 제한이 가능한가?
```

단, 이번 MFU에서는 성능 최적화 구현은 하지 않는다.

## 절대 금지

```text
- production code 수정 금지
- DB 수정 금지
- paper_execution_log.csv 수정 금지
- snapshot 파일 수정 금지
- outputs/front_test 수정 금지
- outputs/paper_test 수정 금지
- --commit 실행 금지
- 성능 최적화 구현 금지
- universe snapshot 구현 금지
- config snapshot 구현 금지
```

## 산출물

결과 보고는 5천자 이내로 작성한다.

포함 항목:

```text
1. Summary
2. 조사 기준 브랜치
3. plan_date의 실제 의미
4. market price 기준일
5. indicator 기준일
6. universe 기준일
7. regime 기준일
8. config 기준
9. 미래 데이터 / 최신 상태 섞임 위험
10. run_paper_daily_plan.py timeout 원인 후보
11. 완전 재현성을 위해 필요한 후속 작업
12. 다음 MFU 제안
```

## 성공 기준

```text
- 계좌 상태 외 daily plan 입력값의 기준일이 정리됨
- plan_date 이후 데이터가 섞일 위험이 있는지 판단됨
- universe/config 최신값 의존 여부가 확인됨
- regime 계산 기준이 확인됨
- full smoke timeout 원인 후보가 정리됨
- 구현 전에 어떤 as-of 정책을 정해야 하는지 질문이 도출됨
```
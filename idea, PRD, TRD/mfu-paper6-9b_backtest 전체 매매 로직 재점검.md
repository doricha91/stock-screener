# MFU-PAPER6-9B 작업 지시문: Backtest 전체 매매 로직 재점검

## 목적

switch 후보군과 max_positions gate 정책을 확정하기 전에, `gemini_cli_update` 브랜치 기준으로 백테스트에서 실제로 어떤 매매 로직이 작동하는지 전면 재점검한다.

이번 MFU는 조사 전용이다. production code 수정은 하지 않는다.

## 배경

MFU-PAPER6-9A 조사 결과:

- backtest와 paper daily plan은 일부 같은 switch 함수를 쓰지만 완전 parity는 아님
- paper daily plan은 fail 후보도 switch-in 가능
- 2026-05-13에 F가 SWITCH_IN과 STRATEGY_ENTRY로 중복 BUY됨
- 사용자 의도는 “max_positions가 찼을 때만 교체매매”
- 현재 코드는 backtest/paper 모두 max_positions full일 때만 switch를 강제하지 않는 것으로 조사됨

따라서 정책을 고치기 전에, 백테스트의 모든 매매 로직을 먼저 기준점으로 정리한다.

## 기준 브랜치

반드시 아래 브랜치 기준으로 조사한다.

```text
gemini_cli_update
```

`main` 브랜치 기준으로 판단하지 않는다.

## 조사 대상 파일

우선 조사:

```text
core/backtest_engine.py
core/portfolio_config.py
core/config_factory.py
core/param_grid.py
config.py
screener/strategy.py
screener/portfolio.py
market_analyzer.py
```

필요 시 추가:

```text
core/daily_plan_generator.py
core/target_portfolio_state.py
tests/*backtest*
tests/*switch*
scripts/run_portfolio_backtest.py
scripts/run_optimizer.py
```

## 조사 범위

백테스트의 모든 매매 관련 로직을 아래 순서로 정리한다.

### 1. 일별 처리 순서

하루 루프에서 실제 순서를 확인한다.

```text
1. market regime 계산
2. trade_halted / target_cash_ratio 계산
3. 보유 종목 가격 업데이트
4. sell_signal / trailing stop 매도
5. switching 매도/매수
6. 일반 신규 BUY
7. cash / position / equity 업데이트
8. trade_history 기록
```

실제 코드 순서가 다르면 실제 순서대로 보고한다.

### 2. 매도 로직

확인할 것:

```text
- sell_signal 조건
- trailing stop 조건
- signal exit와 trailing stop 우선순위
- trade_halted=True일 때 매도는 계속 실행되는지
- 매도 수량은 전량인지 일부인지
- 매도 가격 기준은 close인지 다른 값인지
- 매도 reason이 trade_history에 어떻게 남는지
```

### 3. 일반 신규 매수 로직

확인할 것:

```text
- 신규 BUY 후보 조건
- buy_signal 정의
- score_threshold 조건
- rs_val > 0 조건
- entry signal 사용 여부
- already_owned 제외 여부
- 후보 정렬 기준
- max_positions 제한
- target_cash_ratio / required_cash 적용 여부
- shares_to_buy 산식
- risk_per_trade 사용 여부
- trade_halted=True일 때 신규 BUY 차단 여부
```

### 4. switching 로직

확인할 것:

```text
- switch 함수 이름과 위치
- switch가 실제 백테스트 루프에서 호출되는지
- 호출된다면 sell 이후인지 buy 이전인지
- switch 후보군 조건
- buy_signal=True만 쓰는지
- rs_val > 0 필수인지
- score gap 조건
- SWITCHING_PREMIUM 사용 여부
- ALLOW_PROFIT_SWITCH 의미
- SWITCHING_MAX_COUNT 적용 방식
- switch-out 대상 선정 기준
- switch-in 대상 선정 기준
- max_positions full일 때만 switch하는지
- target_long_slots 기준이 있는지
- 같은 날 같은 symbol 중복 buy 방지 여부
- candidates.drop 또는 position update 방식
```

### 5. 포지션/현금/슬롯 정책

확인할 것:

```text
- max_positions 실제 사용 위치
- target_cash_ratio가 long slot 계산에 쓰이는지
- target_long_slots 개념이 백테스트에 있는지
- current_positions >= max_positions일 때 신규 매수/교체가 어떻게 되는지
- cash 부족 시 어떤 순서로 skip되는지
```

### 6. trade_halted / market regime 영향

확인할 것:

```text
- trade_halted=True일 때 sell은 허용되는지
- trade_halted=True일 때 switch는 허용되는지
- trade_halted=True일 때 일반 BUY는 차단되는지
- BULL/BEAR/UNSTABLE regime별 설정값이 어떻게 적용되는지
```

### 7. 핵심 변수값 정리

아래 변수의 source와 실제값을 정리한다.

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
trade_halted
```

각 항목은 아래 형식으로 쓴다.

```text
변수명:
- 실제 값:
- 출처:
- 사용 위치:
- 백테스트 매매에 미치는 영향:
```

## paper-test와 비교는 최소만

이번 MFU의 주 목적은 백테스트 기준점 정리다.  
다만 마지막에 간단히 아래만 비교한다.

```text
1. paper-test가 백테스트와 명확히 다른 지점
2. paper-test를 고치려면 반드시 맞춰야 할 지점
3. 정책 결정이 필요한 지점
```

## 절대 금지

```text
- production code 수정 금지
- paper_execution_log.csv 수정 금지
- snapshot 파일 수정 금지
- outputs/front_test 수정 금지
- outputs/paper_test 수정 금지
- DB 수정 금지
- --commit 실행 금지
- 대규모 리팩토링 금지
```

## 산출물

결과 보고는 5천자 이내로 작성한다.

포함 항목:

```text
1. Summary
2. 조사 기준 브랜치
3. 백테스트 일별 매매 순서
4. 매도 로직
5. 일반 신규 BUY 로직
6. switching 로직
7. max_positions / cash / slot 정책
8. trade_halted / regime 영향
9. 핵심 변수값과 출처
10. paper-test와의 주요 불일치
11. 정책 결정이 필요한 질문
12. 다음 MFU 제안
```

## 성공 기준

```text
- 백테스트 전체 매매 로직이 순서대로 정리됨
- 일반 BUY / SELL / SWITCH 로직이 분리되어 설명됨
- max_positions가 실제 어디에 쓰이는지 확인됨
- switching이 max_positions full일 때만 작동하는지 확인됨
- switch 후보군 조건이 명확해짐
- paper-test 수정 전 정책 결정 질문이 도출됨
```
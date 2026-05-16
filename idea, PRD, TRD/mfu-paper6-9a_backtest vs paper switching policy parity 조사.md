# MFU-PAPER6-9A 작업 지시문: Backtest vs Paper switching policy parity 조사

## 목적

`paper_test`에서 발생한 SWITCH_OUT / SWITCH_IN 교체매매가 백테스트의 교체매매 정책과 일치하는지 조사한다.

특히 사용자 의도는 아래와 같다.

```text
교체매매 = max_positions가 이미 찼을 때만,
기존 보유종목 중 상대적으로 약한 종목을 팔고,
더 나은 신규 후보로 교체하는 것
```

이번 MFU는 조사/분석 단계다.  
production code 수정은 하지 않는다.

## 기준 브랜치

반드시 아래 브랜치 기준으로 조사한다.

```text
gemini_cli_update
```

`main` 브랜치 기준으로 판단하지 않는다.

## 조사 배경

최근 paper-test에서 다음 교체매매가 발생했다.

2026-05-12:

```text
CPAY SELL → CF BUY
VRSN SELL → BRK-B BUY
```

2026-05-13:

```text
CF SELL
F BUY
F BUY
```

확인하고 싶은 의문:

```text
1. CPAY/VRSN switch_out이 백테스트 정책과 같은가?
2. CF/BRK-B가 후보 필터에서 fail인데 switch-in 된 것이 의도인가?
3. F가 같은 날짜에 두 번 BUY 된 것이 의도인가?
4. paper-test에서 쓰는 max_positions 등 변수값이 백테스트와 같은가?
```

## 조사 대상

우선 아래 파일을 조사한다. 실제 경로가 다르면 검색해서 추적한다.

```text
core/backtest_engine.py
core/daily_plan_generator.py
core/paper_state_provider.py
scripts/run_paper_daily_plan.py
scripts/run_paper_eod_update.py
core/portfolio_config.py
core/config_factory.py
core/param_grid.py
config.py
```

필요 시 추가 조사:

```text
screener/strategy.py
screener/portfolio.py
market_analyzer.py
tests/*switch*
tests/*paper*
```

## 1단계: 백테스트 교체매매 정책 조사

`gemini_cli_update` 브랜치에서 백테스트에 실제 switch 로직이 있는지 확인한다.

확인할 것:

```text
1. max_positions 도달 시 교체매매가 발생하는가?
2. 보유 수량이 max_positions 미만이면 switch가 금지되는가?
3. switch 조건에 score gap이 있는가?
4. switch-in 후보는 buy_signal=True여야 하는가?
5. switch-in 후보는 rs_val > 0이어야 하는가?
6. 후보 필터 fail 종목도 switch-in 가능하게 되어 있는가?
7. 동일 symbol이 같은 날 여러 번 switch-in 될 수 있는가?
8. switch-out 대상은 어떻게 고르는가?
   - lowest score?
   - lowest RS?
   - target portfolio 제외?
   - 기타?
```

## 2단계: paper-test 교체매매 정책 조사

paper daily plan 생성 경로에서 switch 로직이 어떻게 작동하는지 확인한다.

확인할 것:

```text
1. paper_state의 current_symbols 기준은 무엇인가?
2. paper-test에서 max_positions를 어디서 가져오는가?
3. 현재 paper-test에서 실제 사용된 max_positions 값은 무엇인가?
4. score_threshold, rs_lookback, trailing_stop_multiplier 등 핵심 변수값은 무엇인가?
5. paper-test의 switch 후보는 어떤 candidate pool에서 오는가?
6. Candidate Filter Diagnostics에서 fail인 종목도 switch-in 가능한가?
7. 2026-05-12 CF / BRK-B가 왜 switch-in 됐는가?
8. 2026-05-13 F가 왜 두 번 BUY 됐는가?
```

## 3단계: paper-test 변수값 조사

현재 paper-test가 실제로 사용하는 변수값을 정리한다.

필수 확인 변수:

```text
max_positions
score_threshold
entry_period
exit_period
rs_lookback
trailing_stop_multiplier
risk_per_trade
target_cash_ratio
cash buffer / reserve buffer
strategy weights
market regime
trade_halted
target_cash_ratio
```

각 변수마다 아래 형식으로 정리한다.

```text
변수명:
- 실제 값:
- 출처 파일/함수:
- 백테스트와 동일 여부:
- paper-test에서 사용되는 위치:
```

## 4단계: 2026-05-12 사례 분석

`daily_action_plan_20260512.md` 기준으로 아래를 분석한다.

```text
보유 종목:
- CPAY
- GEN
- VRSN

switch:
- CPAY → CF
- VRSN → BRK-B

확인:
1. 당시 보유 종목 수가 max_positions와 같았는가?
2. CPAY/VRSN이 switch-out 대상으로 선택된 이유는 무엇인가?
3. CF/BRK-B가 switch-in 후보가 된 이유는 무엇인가?
4. CF/BRK-B가 rs_lte_0 fail인데도 switch-in 된 것이 코드상 의도인가?
5. 백테스트에서도 같은 상황이면 동일하게 switch되는가?
```

## 5단계: 2026-05-13 사례 분석

`daily_action_plan_20260513.md` 및 commit 결과 기준으로 아래를 분석한다.

```text
이전 보유:
- BRK-B
- CF
- GEN

결과:
- CF SELL
- F BUY 693
- F BUY 734

확인:
1. F가 두 번 BUY 된 이유는 무엇인가?
2. 서로 다른 switch-out source에서 같은 F가 선택된 것인가?
3. 동일 symbol 중복 switch-in을 허용하는 정책인가?
4. 백테스트에서도 같은 날 같은 symbol을 중복 매수할 수 있는가?
5. 의도하지 않은 중복이면 어디서 막아야 하는가?
```

## 절대 금지

```text
- production code 수정 금지
- paper_execution_log.csv 수정 금지
- snapshot 파일 수정 금지
- outputs/front_test 수정 금지
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
3. 백테스트 switch 정책
4. paper-test switch 정책
5. 현재 paper-test 변수값
6. 백테스트와 paper-test 변수값 비교
7. 2026-05-12 CPAY/VRSN switch 분석
8. 2026-05-13 F 중복 BUY 분석
9. 정책 일치/불일치 판단
10. 버그 후보
11. 수정이 필요하다면 다음 MFU 제안
```

## 성공 기준

```text
- gemini_cli_update 브랜치 기준으로 조사됨
- 백테스트에 switch 로직이 있는지 명확히 확인됨
- paper-test switch 로직의 조건이 명확히 정리됨
- paper-test가 사용하는 max_positions 등 변수값이 확인됨
- CF/BRK-B fail 후보 switch-in 여부가 설명됨
- F 중복 BUY 원인이 설명됨
- 백테스트와 paper-test의 일치/불일치가 판단됨
``` 
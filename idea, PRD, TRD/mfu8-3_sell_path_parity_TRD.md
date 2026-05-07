# [TRD] MFU8-3: SELL Path Parity 검증 기술 설계서 v1.0

## 1. 기술 목표

MFU8-3의 기술 목표는 backtest와 front-test의 보유 종목 SELL 판단 경로를 비교하고, front-test의 확정 SELL이 백테스트의 실제 sell execution과 대응되는지 검증하는 것이다.

검증 대상은 다음 4개다.

```text
1. explicit sell_signal
2. trailing stop
3. SWITCH_OUT
4. symbol_diff_removed / REVIEW_EXIT
```

MFU8-3은 trading policy를 바꾸지 않는다.  
MFU8-3은 우선 read-only 조사와 diagnostics 중심으로 진행한다.

## 2. 현재 조사 결과 요약

조사 결과 기준 front-test confirmed SELL 경로는 backtest와 완전 일치하지 않는다.

```text
explicit sell_signal:
- backtest: implemented
- front-test: not implemented
- risk: high

trailing stop:
- formula parity: high
- input parity: incomplete
- risk: medium-high

SWITCH_OUT:
- same function used
- candidate/input set parity incomplete
- risk: medium

symbol_diff_removed:
- backtest direct sell path not found
- front-test review-only
- risk: lowered
```

## 3. Backtest SELL path

확인 대상 파일:

```text
core/backtest_engine.py
```

실제 SELL execution은 `pf.sell(...)` 호출로 확인한다.

## 3.1 REGIME_FILTER_EXCLUSIVE

```text
location:
- core/backtest_engine.py around regime filter liquidation

trigger:
- current regime not in TARGET_REGIMES
- REGIME_FILTER_MODE == 'EXCLUSIVE'

reason:
- REGIME_FILTER_EXCLUSIVE

state update:
- pf.sell(...)

dependency:
- current holdings
- current prices
- regime config

target/rebalance dependency:
- no
```

## 3.2 explicit technical sell_signal

```text
trigger:
- row['sell_signal'] == True

generation:
- df['sell_signal'] = df['close'] < df['exit_low']

required columns:
- close
- exit_low

reason:
- ReasonCode.EXIT_SIGNAL

state update:
- pf.sell(...)

target/rebalance dependency:
- no
```

## 3.3 TRAILING_STOP

```text
trigger:
- pf.check_trailing_stop(...) == True

required inputs:
- close
- atr
- trailing_stop_multiplier
- PortfolioDB highest_price

reason:
- ReasonCode.EXIT_TRAILING_STOP

state update:
- pf.sell(...)

target/rebalance dependency:
- no

config dependency:
- trailing_stop_multiplier from merged/regime config
```

## 3.4 SWITCH_OUT

```text
trigger:
- evaluate_switching_opportunity(...) result contains switch pair

required inputs:
- candidate DataFrame
- current_pos_scores
- SWITCHING_PREMIUM
- ALLOW_PROFIT_SWITCH
- SWITCHING_MAX_COUNT

reason:
- ReasonCode.SWITCH_OUT

state update:
- pf.sell(...)

target/rebalance dependency:
- no direct dependency
```

## 3.5 symbol_diff_removed

```text
direct sell path:
- not found

usage:
- evaluate_rebalance_need(...) may compute it
- not directly connected to pf.sell(...)
```

## 4. Front-test SELL / REVIEW / WARNING path

확인 대상 파일:

```text
core/daily_plan_generator.py
```

## 4.1 SWITCH_OUT confirmed SELL

```text
trigger:
- switch_pairs result exists

reason:
- SWITCH_OUT

classification:
- ACTION

report section:
- ## 4. 확정 매매 지시

action_items:
- yes

journal_rows:
- yes

backtest equivalent:
- yes, partial
```

## 4.2 TRAILING_STOP confirmed SELL

```text
trigger:
- check_trailing_stop_manual(...) == True

reason:
- TRAILING_STOP

classification:
- ACTION

report section:
- ## 4. 확정 매매 지시

action_items:
- yes

journal_rows:
- yes

backtest equivalent:
- yes, partial
```

## 4.3 REVIEW_EXIT review-only

```text
trigger:
- symbol in rebalance.symbol_diff_removed
- symbol not in processed_symbols

reason:
- REVIEW_EXIT

classification:
- REVIEW

report section:
- ## 4-0. 리밸런싱 검토 필요

action_items:
- no

journal_rows:
- no

backtest direct sell equivalent:
- no
```

## 4.4 WARNING items

```text
classification:
- WARNING

report section:
- ## 4-0-1. 경고 및 주의 항목

action_items:
- no

journal_rows:
- no
```

## 5. SELL Path Matrix

| SELL Path | Backtest Trigger | Front-test Trigger | Same? | Front-test Classification | Journal? | Risk | Next Action |
|---|---|---|---|---|---|---|---|
| explicit sell_signal | `row['sell_signal'] == True` | 없음 | NOT_IMPLEMENTED | 없음 | No | 높음 | holding diagnostics에 먼저 노출 |
| trailing stop | `pf.check_trailing_stop(close, atr, highest, mult)` | `check_trailing_stop_manual(close, atr/fallback, highest_snapshot, mult)` | PARTIAL_MATCH | ACTION | Yes | 중간~높음 | ATR/highest input parity 개선 |
| SWITCH_OUT | `evaluate_switching_opportunity(...)` | 같은 함수 사용 | PARTIAL_MATCH | ACTION | Yes | 중간 | candidate set / holding score input 진단 유지 |
| symbol_diff_removed | direct sell path 확인 안 됨 | REVIEW_EXIT | MISMATCH but intentionally downgraded | REVIEW | No | 낮아짐 | 현재 상태 유지 |
| regime filter exit | REGIME_FILTER_EXCLUSIVE direct sell | 없음 | NOT_IMPLEMENTED | 없음 | No | 중간 | 정책 여부 별도 결정 |
| hedge-related exit | reason code는 있으나 실행 경로 불명확 | 없음 | INCONCLUSIVE | 없음 | No | 중간 | 별도 조사 |

## 6. Trailing Stop Parity 설계

## 6.1 공통 formula

backtest와 front-test의 trailing stop formula는 사실상 유사하다.

```text
stop_price = highest_price - ATR * multiplier
triggered = current_price < stop_price
```

## 6.2 Backtest input

```text
current price:
- row['close']

ATR:
- day_data['atr']

highest price:
- PortfolioDB.positions.highest_price
- pf.update_market_status(...)로 일별 갱신

multiplier:
- trailing_stop_multiplier from merged/regime config
```

## 6.3 Front-test input

```text
current price:
- current price from latest available holding data

ATR:
- load_price_history_until(..., 10)의 latest row
- raw row에 atr가 없을 수 있음
- atr가 없으면 close * 0.02 fallback 가능

highest price:
- current_state.highest_prices
- snapshot이 오래되면 drift 가능

multiplier:
- merged/regime config
```

## 6.4 주요 parity gap

```text
1. ATR source mismatch
2. highest_price source mismatch
3. current_state snapshot stale risk
4. fallback ATR usage risk
```

## 6.5 권장 개선 방향

MFU8-3의 1차 구현은 정책 변경이 아니라 diagnostics다.

보유 종목 diagnostics에 다음을 표시한다.

```text
Symbol
Current Price
ATR
ATR Source
Highest Price
Highest Source
Trailing Stop Price
Trailing Triggered
Trailing Multiplier
```

후속 small safe fix에서 다음을 검토한다.

```text
- front-test trailing stop 계산에 indicator pipeline 기반 ATR 사용
- raw 10-day history fallback 최소화
- current_state.highest_prices stale warning 강화
```

## 7. SWITCH_OUT Parity 설계

## 7.1 공용 함수

backtest와 front-test는 같은 switching 판단 함수를 사용한다.

```text
evaluate_switching_opportunity(...)
```

이 점은 좋은 parity 요소다.

## 7.2 Backtest input

```text
candidate set:
- day_data[day_data['buy_signal'] == True]
- 기존 보유 제외

holding scores:
- day_data.loc[s]['score']

sorting:
- holdings score ascending
- candidates score / rs descending
```

## 7.3 Front-test input

```text
candidate set:
- df_candidates 기반
- stale/universe removed guard 통과 후보

holding scores:
- 후보군에 없으면 compute_holding_score_for_switching(...)로 재계산

old fallback:
- 후보군 밖 score=0 fallback 제거됨
```

## 7.4 주요 parity gap

```text
1. backtest는 full day_data 기반 buy_signal universe
2. front-test는 screener candidate list 출발
3. front-test stale/universe guard가 후보 set을 추가로 줄일 수 있음
```

## 7.5 권장 개선 방향

```text
- SWITCH_OUT은 confirmed ACTION으로 유지
- 다만 PARTIAL_MATCH로 문서화
- report diagnostics에 score_gap, premium, candidate/holding score를 표시하는 후속 작업 검토
```

## 8. explicit sell_signal 설계

## 8.1 Backtest behavior

backtest는 explicit sell_signal을 생성하고 실제 매도에 사용한다.

```text
sell_signal = close < exit_low
```

필요 컬럼:

```text
close
exit_low
```

실행:

```text
sell_signal=True
→ pf.sell(...)
→ ReasonCode.EXIT_SIGNAL
```

## 8.2 Front-test current behavior

현재 front-test는 보유 종목에 대해 explicit `sell_signal`을 직접 계산/사용하지 않는다.

```text
daily_plan_generator.py에는 sell_signal direct path 없음
```

## 8.3 MFU8-3 기본 결정

MFU8-3에서는 sell_signal을 바로 confirmed SELL로 연결하지 않는다.

이유:

```text
- confirmed SELL decision이 바뀌는 policy-impacting change이기 때문
- 먼저 parity와 diagnostics를 확인해야 함
```

## 8.4 1차 구현 방향

보유 종목 diagnostics section에 다음을 추가한다.

```text
Symbol
Close
Exit Low
Sell Signal
Sell Signal Source
```

표시 예시:

| Symbol | Close | Exit Low | Sell Signal | Source |
|---|---:|---:|---|---|
| AAPL | 284.18 | 245.70 | False | reconstructed |
| TSLA | 389.37 | 337.24 | False | reconstructed |

## 8.5 후속 정책 결정

다음 질문은 MFU8-3 이후 별도 결정한다.

```text
sell_signal=True이면 front-test에서 confirmed SELL로 표시할 것인가?
```

추천 순서:

```text
1. diagnostics 표시
2. 여러 날짜/종목으로 parity 확인
3. confirmed SELL 승격 여부 결정
```

## 9. REVIEW_EXIT 유지 설계

`symbol_diff_removed`는 다음으로 유지한다.

```text
rebalance.symbol_diff_removed
→ rebalance_review_items
→ REVIEW_EXIT
→ ## 4-0. 리밸런싱 검토 필요
→ journal_rows 미포함
```

MFU8-3에서는 이 정책을 변경하지 않는다.

검증 항목:

```text
REVIEW_EXIT in journal: False
WARNING_ in journal: False
STRATEGY_EXIT in journal: False
```

## 10. 보유 종목 SELL Diagnostics Section 설계

## 10.1 목적

확정 SELL 정책을 바꾸지 않고도, 보유 종목의 매도 관련 상태를 확인할 수 있게 한다.

## 10.2 권장 섹션명

```text
## 3-1. 보유 종목 SELL 진단 (Holding Sell Diagnostics)
```

또는 기존 report 흐름에 맞춰:

```text
## 4-0-2. 보유 종목 SELL 진단 (Holding Sell Diagnostics)
```

권장 위치:

```text
## 3. 트레일링 스탑 감시
## 3-1. 보유 종목 SELL 진단
## 4. 확정 매매 지시
```

## 10.3 표시 필드

```text
Symbol
Close
Exit Low
Sell Signal
ATR
ATR Source
Highest Price
Highest Source
Stop Price
Trailing Triggered
Review Status
Warning Status
```

예시:

| Symbol | Close | Exit Low | Sell Signal | ATR | ATR Source | Highest | Highest Source | Stop Price | Trail Trigger | Review |
|---|---:|---:|---|---:|---|---:|---|---:|---|---|
| AAPL | 284.18 | 245.70 | False | 6.4487 | indicator | 284.18 | max(snapshot,current) | 263.22 | False | REVIEW_EXIT |
| TSLA | 389.37 | 337.24 | False | 14.4013 | indicator | 389.37 | max(snapshot,current) | 342.57 | False | REVIEW_EXIT |

## 10.4 주의사항

```text
- diagnostics는 ACTION이 아니다.
- diagnostics는 journal에 들어가지 않는다.
- sell_signal=True도 이 단계에서는 confirmed SELL로 만들지 않는다.
- trailing_triggered=True는 기존 confirmed SELL 로직이 이미 처리한다.
```

## 11. 추천 구현 순서

### Stage 1: 문서 반영

```text
- MFU8-3 idea / PRD / TRD를 조사 결과 기준으로 업데이트
```

### Stage 2: Small Safe Fix

```text
- 보유 종목 SELL diagnostics section 추가
- sell_signal / exit_low / ATR / stop price / trailing trigger 표시
- trading policy 변경 없음
```

### Stage 3: Trailing input parity 개선

```text
- front-test trailing stop에서 indicator pipeline 기반 ATR 사용
- raw 10-day fallback 최소화
```

### Stage 4: sell_signal policy 결정

```text
- sell_signal=True를 confirmed SELL로 승격할지 결정
```

## 12. 검증 명령

정적 확인:

```bash
python -m py_compile core/daily_plan_generator.py
python -m py_compile scripts/check_decision_parity.py
```

기존 parity 확인:

```bash
python scripts/check_decision_parity.py --date 2026-05-04 --symbol AAPL
python scripts/check_decision_parity.py --date 2026-05-04 --symbol TSLA
```

front-test 확인:

```bash
python scripts/run_front_test.py
```

journal 오염 확인:

```bash
python -c "from pathlib import Path; files=sorted(Path('outputs/front_test').glob('daily_action_plan_*.md')); p=files[-1]; txt=p.read_text(encoding='utf-8'); start=txt.find('## 5.'); journal=txt[start:] if start!=-1 else ''; print('report:', p); print('REVIEW_EXIT in journal:', 'REVIEW_EXIT' in journal); print('WARNING_ in journal:', 'WARNING_' in journal); print('STRATEGY_EXIT in journal:', 'STRATEGY_EXIT' in journal)"
```

## 13. 완료 기준

MFU8-3은 다음을 만족하면 완료로 본다.

```text
1. backtest SELL path가 조사 결과 기반으로 문서화되어 있다.
2. front-test SELL path가 조사 결과 기반으로 문서화되어 있다.
3. SELL Path Matrix가 업데이트되어 있다.
4. explicit sell_signal gap이 명확히 기록되어 있다.
5. trailing stop formula parity와 input parity가 분리되어 설명되어 있다.
6. SWITCH_OUT이 PARTIAL_MATCH로 분류되어 있다.
7. REVIEW_EXIT는 계속 review-only로 남아 있다.
8. REVIEW_EXIT와 WARNING_*는 journal에 들어가지 않는다.
9. 다음 구현 후보가 “보유 종목 SELL diagnostics 표시”로 정의되어 있다.
10. 매매 정책은 변경되지 않았다.
```

## 14. 오픈 질문

1. explicit sell_signal이 True이면 front-test에서 confirmed SELL로 표시할 것인가?
2. sell_signal을 몇 번의 front-test 검증 후 confirmed SELL로 승격할 것인가?
3. trailing stop 계산은 backtest helper를 공용화할 것인가, 아니면 front-test helper를 개선할 것인가?
4. SWITCH_OUT diagnostic을 리포트에 얼마나 자세히 표시할 것인가?
5. regime forced exit와 hedge liquidation은 MFU8-3에 포함할 것인가, 별도 MFU로 분리할 것인가?
6. 보유 종목 SELL diagnostics section을 MFU8-3의 구현 범위로 포함할 것인가, 후속 small safe fix로 분리할 것인가?
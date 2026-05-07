# [PRD] MFU8-3: SELL Path Parity 검증 v1.0

## 0. Context & Status

### 배경

현재 프로젝트는 백테스트와 프론트테스트의 매매 판단 정합성을 단계적으로 강화하고 있다.

선행 작업:

```text
MFU8-1:
- score / rs_val / buy-entry signal parity 검증 스크립트 추가
- scripts/validate_strategy_sync.py
- scripts/check_decision_parity.py

MFU8-2:
- ACTION / REVIEW / WARNING taxonomy 정리
- REVIEW_EXIT journal 제외
- WARNING_* journal 제외
- warning section 추가
```

MFU8-3은 보유 종목에 대한 SELL 판단 정합성을 검증하는 단계다.

최근 조사에서 front-test confirmed SELL 경로는 backtest와 완전 일치하지 않는 것으로 확인되었다.

```text
TRAILING_STOP:
- formula는 유사하지만 input parity 불완전
- PARTIAL_MATCH

SWITCH_OUT:
- 같은 함수 사용
- candidate set / holding score input이 다를 수 있음
- PARTIAL_MATCH

explicit sell_signal:
- backtest에는 있음
- front-test에는 없음
- NOT_IMPLEMENTED

symbol_diff_removed:
- backtest direct sell path 없음
- front-test에서는 REVIEW_EXIT
- journal 미포함
```

따라서 MFU8-3의 핵심 목표는 다음이다.

```text
front-test에서 확정 SELL로 표시되는 항목들이
backtest의 실제 SELL execution path와 같은 의미인지 검증한다.
```

## 1. 목표

MFU8-3의 목표는 backtest와 front-test의 SELL 판단 경로를 비교하고, front-test의 확정 SELL 기준을 안전하게 검증하는 것이다.

비교 대상:

```text
1. explicit sell_signal
2. trailing stop
3. SWITCH_OUT
4. symbol_diff_removed / REVIEW_EXIT
5. regime / hedge exit은 1차 범위에서는 조사만 하고 정책 결정은 보류
```

MFU8-3은 매도 정책을 바꾸는 작업이 아니다.

MFU8-3은 다음을 목표로 한다.

```text
- SELL path 목록화
- 각 SELL path별 입력 데이터와 판단 조건 비교
- 동일 symbol / 동일 data_date 기준 SELL diagnostics 설계
- 불일치 항목은 ACTION이 아니라 REVIEW/WARNING으로 유지
- sell_signal을 먼저 diagnostic으로 노출하고, confirmed SELL 승격은 후속 결정으로 분리
```

## 2. 범위

### In-Scope

```text
- backtest SELL path 조사 결과 반영
- front-test SELL path 조사 결과 반영
- SELL Path Matrix 업데이트
- TRAILING_STOP formula / input parity 구분
- SWITCH_OUT function / input parity 구분
- explicit sell_signal 미구현 gap 문서화
- 보유 종목 SELL diagnostics 설계
- REVIEW_EXIT가 확정 SELL이 아님을 문서화
- journal contamination 재확인
- 현재 보유 종목 AAPL / TSLA 같은 샘플 기준 diagnostics 검토
```

### Out-of-Scope

```text
- backtest sell policy 변경
- front-test sell policy 변경
- sell_signal=True를 즉시 confirmed SELL로 승격
- target/rebalance policy 변경
- symbol_diff_removed를 SELL로 재승격
- broker 주문 연동
- DB schema 변경
- PortfolioDB와 current_state snapshot 통합
- full backtest run 강제
- optimizer 실행
- regime forced exit / hedge liquidation parity 완전 구현
- action/review/warning taxonomy 재설계
```

## 3. 요구사항

## Req 1. Backtest SELL path 목록화 결과 반영

`core/backtest_engine.py` 기준 실제 매도 실행은 `pf.sell(...)` 호출로 확인한다.

문서에 다음 경로를 포함한다.

### 1. REGIME_FILTER_EXCLUSIVE

```text
trigger:
- TARGET_REGIMES 밖이고
- REGIME_FILTER_MODE == 'EXCLUSIVE'

reason:
- REGIME_FILTER_EXCLUSIVE

state update:
- pf.sell(...) 호출
```

### 2. explicit technical sell_signal

```text
trigger:
- row['sell_signal'] == True

reason:
- ReasonCode.EXIT_SIGNAL

state update:
- pf.sell(...) 호출
```

### 3. TRAILING_STOP

```text
trigger:
- pf.check_trailing_stop(...) == True

reason:
- ReasonCode.EXIT_TRAILING_STOP

input:
- close
- atr
- trailing_stop_multiplier
- PortfolioDB highest_price

state update:
- pf.sell(...) 호출
```

### 4. SWITCH_OUT

```text
trigger:
- evaluate_switching_opportunity(...) 결과에 포함

reason:
- ReasonCode.SWITCH_OUT

input:
- candidate DataFrame
- current_pos_scores
- SWITCHING_PREMIUM
- ALLOW_PROFIT_SWITCH
- SWITCHING_MAX_COUNT

state update:
- pf.sell(...) 호출
```

### 5. symbol_diff_removed

```text
direct sell path:
- 확인되지 않음
```

## Req 2. Front-test SELL path 목록화 결과 반영

`core/daily_plan_generator.py` 기준 confirmed SELL / review / warning 경로를 정리한다.

### 1. SWITCH_OUT confirmed SELL

```text
trigger:
- switch_pairs 결과 존재

reason:
- SWITCH_OUT

classification:
- ACTION

journal:
- Yes

backtest equivalent:
- Yes, but PARTIAL_MATCH
```

### 2. TRAILING_STOP confirmed SELL

```text
trigger:
- check_trailing_stop_manual(...) == True

reason:
- TRAILING_STOP

classification:
- ACTION

journal:
- Yes

backtest equivalent:
- Yes, but PARTIAL_MATCH
```

### 3. REVIEW_EXIT review-only

```text
trigger:
- symbol in rebalance.symbol_diff_removed
- symbol not in processed_symbols

reason:
- REVIEW_EXIT

classification:
- REVIEW

journal:
- No

backtest equivalent:
- direct sell equivalent 없음
```

### 4. WARNING items

```text
classification:
- WARNING

journal:
- No
```

## Req 3. SELL Path Matrix 업데이트

문서 또는 구현 결과에 다음 matrix를 포함한다.

| SELL Path | Backtest Trigger | Front-test Trigger | Same? | Front-test Classification | Journal? | Risk | Next Action |
|---|---|---|---|---|---|---|---|
| explicit sell_signal | `row['sell_signal'] == True` | 없음 | NOT_IMPLEMENTED | 없음 | No | 높음 | diagnostic으로 먼저 노출 |
| trailing stop | `pf.check_trailing_stop(close, atr, highest, mult)` | `check_trailing_stop_manual(close, atr/fallback, highest_snapshot, mult)` | PARTIAL_MATCH | ACTION | Yes | 중간~높음 | ATR/highest input parity 개선 |
| SWITCH_OUT | `evaluate_switching_opportunity(...)` | 같은 함수 사용 | PARTIAL_MATCH | ACTION | Yes | 중간 | candidate set / holding score input 진단 유지 |
| symbol_diff_removed | direct sell path 확인 안 됨 | REVIEW_EXIT | MISMATCH but intentionally downgraded | REVIEW | No | 낮아짐 | 현재 상태 유지 |
| regime filter exit | REGIME_FILTER_EXCLUSIVE direct sell | 없음 | NOT_IMPLEMENTED | 없음 | No | 중간 | 정책 여부 별도 결정 |
| hedge-related exit | reason code는 있으나 실행 경로 불명확 | 없음 | INCONCLUSIVE | 없음 | No | 중간 | 별도 조사 |

## Req 4. TRAILING_STOP parity 세부 요구사항

backtest와 front-test의 trailing stop은 formula는 유사하지만 입력값이 다르다.

공통 formula:

```text
stop_price = highest_price - ATR * multiplier
trigger = current_price < stop_price
```

문서와 diagnostics에서 다음을 구분한다.

```text
formula parity:
- 높음

input parity:
- 불완전
```

비교 항목:

```text
- current price source
- highest price source
- ATR source
- trailing_stop_multiplier source
- stop price formula
- triggered condition
- reason label
- action/journal behavior
```

조사 결과 반영:

```text
backtest ATR source:
- day_data['atr']

front-test ATR source:
- load_price_history_until(..., 10)의 latest row
- raw row에는 atr가 없을 수 있음
- 이 경우 close * 0.02 fallback 사용 가능

backtest highest source:
- PortfolioDB.positions.highest_price
- pf.update_market_status(...)로 일별 갱신

front-test highest source:
- current_state.highest_prices
- snapshot이 오래되면 drift 가능
```

요구사항:

```text
- MFU8-3에서는 trailing stop 정책을 바꾸지 않는다.
- 먼저 보유 종목 diagnostics에 ATR source / stop price / trigger 여부를 표시한다.
- 이후 ATR input parity 개선은 별도 small safe fix로 분리한다.
```

## Req 5. SWITCH_OUT parity 세부 요구사항

SWITCH_OUT은 backtest와 front-test가 같은 함수를 사용한다.

```text
evaluate_switching_opportunity(...)
```

하지만 입력 set이 다를 수 있다.

비교 항목:

```text
- candidate score
- holding score
- score_gap
- SWITCHING_PREMIUM
- ALLOW_PROFIT_SWITCH
- current holding PnL
- can_switch_by_profit
- SWITCHING_MAX_COUNT
- candidate universe
```

조사 결과 반영:

```text
backtest candidate set:
- day_data[day_data['buy_signal'] == True]
- 기존 보유 제외

front-test candidate set:
- df_candidates 기반
- stale/universe removed guard 통과 후보만 사용
```

요구사항:

```text
- SWITCH_OUT은 confirmed ACTION으로 유지한다.
- 단, 문서상 PARTIAL_MATCH로 분류한다.
- candidate set drift 가능성을 리스크로 남긴다.
```

## Req 6. explicit sell_signal diagnostics 설계

backtest에는 explicit sell_signal 경로가 있다.

```text
df['sell_signal'] = df['close'] < df['exit_low']
```

backtest는 `sell_signal == True`일 때 실제 매도한다.

front-test는 현재 이 값을 직접 계산/사용하지 않는다.

MFU8-3의 1차 구현 방향:

```text
- sell_signal을 confirmed SELL로 바로 연결하지 않는다.
- 보유 종목 diagnostics에 먼저 표시한다.
```

보유 종목 diagnostics에 포함할 필드:

```text
Symbol
Close
Exit Low
Sell Signal
ATR
Trailing Stop Price
Trailing Triggered
Review Status
Warning Status
```

예시:

| Symbol | Close | Exit Low | Sell Signal | ATR | Stop Price | Trailing Triggered | Review Status |
|---|---:|---:|---|---:|---:|---|---|
| AAPL | 284.18 | 245.70 | False | 6.4487 | 263.22 | False | REVIEW_EXIT |
| TSLA | 389.37 | 337.24 | False | 14.4013 | 342.57 | False | REVIEW_EXIT |

요구사항:

```text
- sell_signal=True를 journal에 넣지 않는다.
- sell_signal=True를 곧바로 SELL action으로 만들지 않는다.
- 확정 SELL 승격 여부는 후속 정책 결정으로 분리한다.
```

## Req 7. REVIEW_EXIT 정책 유지

다음 원칙을 유지한다.

```text
rebalance.symbol_diff_removed
→ REVIEW_EXIT
→ 확정 SELL 아님
→ journal_rows 미포함
```

MFU8-3에서는 `REVIEW_EXIT`를 다시 SELL로 바꾸지 않는다.

## Req 8. Report / Journal 안전성

다음이 유지되어야 한다.

```text
ACTION BUY/SELL만 journal_rows 포함
REVIEW_EXIT journal 미포함
WARNING_* journal 미포함
journal header 유지
```

journal header:

```text
Date | Regime | Symbol | Type | Rec_Shares | Rec_Price | Act_Shares | Act_Price | Reason | Notes
```

## 4. 수용 기준

1. backtest SELL path 목록이 실제 조사 결과로 반영되어야 한다.
2. front-test SELL path 목록이 실제 조사 결과로 반영되어야 한다.
3. SELL Path Matrix가 조사 결과 기반으로 업데이트되어야 한다.
4. explicit sell_signal은 front-test NOT_IMPLEMENTED gap으로 문서화되어야 한다.
5. sell_signal은 우선 diagnostics로만 표시해야 한다.
6. sell_signal=True를 바로 confirmed SELL로 연결하지 않아야 한다.
7. trailing stop은 formula parity와 input parity를 구분해 설명해야 한다.
8. SWITCH_OUT은 같은 함수 사용이지만 input set 차이로 PARTIAL_MATCH로 분류해야 한다.
9. REVIEW_EXIT는 계속 review-only로 남아야 한다.
10. REVIEW_EXIT는 journal에 들어가지 않아야 한다.
11. WARNING_*는 journal에 들어가지 않아야 한다.
12. trading policy는 변경되지 않아야 한다.
13. DB write는 없어야 한다.

## 5. 비기능 요구사항

```text
- read-only 우선
- DB write 금지
- external dependency 추가 금지
- full optimizer 실행 금지
- full backtest 강제 금지
- look-ahead bias 금지
- 기존 CLI behavior 유지
- 기존 report/journal 포맷 유지
- policy-impacting change는 별도 단계로 분리
```

## 6. 검증 명령 후보

```bash
python -m py_compile core/daily_plan_generator.py
python -m py_compile scripts/check_decision_parity.py

python scripts/check_decision_parity.py --date 2026-05-04 --symbol AAPL
python scripts/check_decision_parity.py --date 2026-05-04 --symbol TSLA

python scripts/run_front_test.py
```

journal contamination 확인:

```bash
python -c "from pathlib import Path; files=sorted(Path('outputs/front_test').glob('daily_action_plan_*.md')); p=files[-1]; txt=p.read_text(encoding='utf-8'); start=txt.find('## 5.'); journal=txt[start:] if start!=-1 else ''; print('report:', p); print('REVIEW_EXIT in journal:', 'REVIEW_EXIT' in journal); print('WARNING_ in journal:', 'WARNING_' in journal); print('STRATEGY_EXIT in journal:', 'STRATEGY_EXIT' in journal)"
```

## 7. 후속 단계

MFU8-3 이후 다음 작업을 검토한다.

```text
1. 보유 종목 SELL diagnostics section 추가
2. front-test sell_signal / exit_low 표시
3. trailing stop ATR input parity 개선
4. SWITCH_OUT diagnostics 강화
5. explicit sell_signal을 confirmed SELL로 승격할지 정책 결정
6. regime/hedge exit parity 별도 조사
```
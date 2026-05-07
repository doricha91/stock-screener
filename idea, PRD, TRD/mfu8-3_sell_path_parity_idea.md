# MFU8-3: Backtest-Fronttest SELL Path Parity 검증

## [IDEA] MFU8-3: 보유 종목 매도 판단 정합성 검증

## 1. 배경 및 목적

MFU8의 전체 목표는 백테스트에 추가한 전략, 유니버스, 매매 판단이 프론트테스트에도 누락 없이 반영되는 체계를 만드는 것이다.

선행 단계는 다음과 같다.

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

MFU8-3은 그 다음 단계로, **보유 종목에 대한 SELL 판단이 백테스트와 프론트테스트에서 같은 의미로 작동하는지 검증**한다.

최근 조사에서 다음이 확인되었다.

```text
backtest:
- 실제 SELL 실행은 pf.sell(...) 경로로 확인됨
- 주요 SELL path:
  1. REGIME_FILTER_EXCLUSIVE
  2. explicit technical sell_signal
  3. TRAILING_STOP
  4. SWITCH_OUT
- decision.symbol_diff_removed / rebalance.symbol_diff_removed를 직접 pf.sell(...)로 연결하는 경로는 확인되지 않음

front-test:
- confirmed SELL:
  1. TRAILING_STOP
  2. SWITCH_OUT
- symbol_diff_removed는 REVIEW_EXIT로 분리됨
- REVIEW_EXIT는 action_items와 journal_rows에 들어가지 않음
```

따라서 MFU8-3의 핵심 질문은 다음이다.

```text
front-test에서 확정 SELL로 표시되는 항목들이
backtest의 실제 SELL execution path와 같은 의미인가?
```

## 2. 해결하려는 문제

현재 front-test의 confirmed SELL은 backtest와 완전히 일치하지 않는다.

조사 결과 기준:

```text
TRAILING_STOP:
- formula는 유사
- input parity는 불완전
- PARTIAL_MATCH

SWITCH_OUT:
- 같은 evaluate_switching_opportunity(...) 함수 사용
- candidate set / holding score input이 다를 수 있음
- PARTIAL_MATCH

explicit sell_signal:
- backtest에는 있음
- front-test에는 아직 없음
- NOT_IMPLEMENTED

symbol_diff_removed:
- backtest direct sell path 없음
- front-test에서는 REVIEW_EXIT로 격리됨
- direct SELL risk는 낮아짐
```

가장 큰 남은 gap은 다음이다.

```text
1. explicit sell_signal이 front-test에 없음
2. trailing stop의 ATR / highest_price 입력값 정합성이 불완전함
3. SWITCH_OUT의 candidate universe 입력이 backtest와 다를 수 있음
```

MFU8-3의 목적은 SELL 정책을 새로 만드는 것이 아니라, **현재 SELL path의 정합성을 검증하고 불일치 지점을 명확히 드러내는 것**이다.

## 3. 핵심 원칙

### 3.1 확정 SELL은 backtest execution path와 대응 가능해야 한다

front-test의 확정 SELL은 다음 중 하나와 대응 가능해야 한다.

```text
- explicit sell_signal
- trailing stop
- SWITCH_OUT
```

단, 각 항목은 backtest와 front-test의 계산 경로가 같은지 별도 확인이 필요하다.

### 3.2 target removal은 확정 SELL이 아니다

`rebalance.symbol_diff_removed`는 현재 `REVIEW_EXIT`로 분리되어 있다.

MFU8-3에서도 다음 원칙을 유지한다.

```text
symbol_diff_removed
→ 확정 SELL 아님
→ REVIEW_EXIT
→ journal row 미포함
```

### 3.3 sell_signal은 바로 확정 SELL로 승격하지 않는다

backtest에는 explicit `sell_signal`이 있다.

```text
sell_signal = close < exit_low
```

하지만 front-test에는 아직 이 경로가 없다.

MFU8-3에서는 이를 곧바로 confirmed SELL로 연결하지 않는다.

1차 목표는 다음이다.

```text
- 보유 종목별 sell_signal / exit_low를 진단 정보로 표시
- backtest와 front-test가 같은 값을 계산할 수 있는지 확인
- 확정 SELL 승격 여부는 후속 정책 결정으로 분리
```

### 3.4 불일치하면 ACTION이 아니라 REVIEW/WARNING으로 둔다

backtest와 front-test의 SELL 판단이 불일치하거나 불완전하면 해당 항목은 확정 SELL이 아니라 `REVIEW` 또는 `WARNING`으로 표시한다.

## 4. Must-have

MFU8-3에서 반드시 해야 하는 일:

```text
1. backtest SELL path 목록화
2. front-test SELL path 목록화
3. SELL Path Matrix 작성
4. explicit sell_signal이 front-test에 없는 gap 명시
5. trailing stop formula parity와 input parity를 분리해서 기록
6. SWITCH_OUT 함수 parity와 input universe parity를 분리해서 기록
7. REVIEW_EXIT가 계속 review-only인지 확인
8. REVIEW_EXIT / WARNING_*가 journal에 들어가지 않는지 재확인
9. 보유 종목 SELL diagnostics 설계
10. sell_signal을 바로 confirmed SELL로 연결하지 않는 원칙 명시
```

## 5. Won't-have

이번 MFU8-3에서 하지 않는 일:

```text
- backtest sell policy 변경
- front-test sell policy 변경
- sell_signal=True를 즉시 confirmed SELL로 승격
- target/rebalance 계산 변경
- symbol_diff_removed를 다시 SELL로 승격
- broker 주문 연동
- DB schema 변경
- PortfolioDB와 current_state snapshot 통합
- regime forced exit / hedge liquidation까지 완전 정합화
- full backtest/front-test orchestration parity
```

## 6. 성공 기준

MFU8-3이 완료되면 다음을 설명할 수 있어야 한다.

```text
1. front-test 확정 SELL은 어떤 조건에서만 발생하는가?
2. 그 조건은 backtest sell execution과 대응되는가?
3. explicit sell_signal은 front-test에 구현되어 있는가?
4. TRAILING_STOP은 양쪽에서 같은 formula를 쓰는가?
5. TRAILING_STOP의 ATR / highest input은 같은가?
6. SWITCH_OUT은 같은 함수를 쓰는가?
7. SWITCH_OUT의 candidate set과 holding score input은 같은가?
8. REVIEW_EXIT는 왜 확정 SELL이 아닌가?
9. 어떤 SELL mismatch가 남아 있는가?
10. mismatch가 있으면 report에서 ACTION이 아니라 REVIEW/WARNING으로 표시되는가?
```

## 7. 조사 결과 기준 SELL Path Matrix

| SELL Path | Backtest Trigger | Front-test Trigger | Same? | Front-test Classification | Journal? | Risk | Next Action |
|---|---|---|---|---|---|---|---|
| explicit sell_signal | `row['sell_signal'] == True` | 없음 | NOT_IMPLEMENTED | 없음 | No | 높음 | 보유 종목 diagnostics에 먼저 노출 |
| trailing stop | `pf.check_trailing_stop(close, atr, highest, mult)` | `check_trailing_stop_manual(close, atr/fallback, highest_snapshot, mult)` | PARTIAL_MATCH | ACTION | Yes | 중간~높음 | ATR/highest input parity 개선 |
| SWITCH_OUT | `evaluate_switching_opportunity(...)` | 같은 함수 사용 | PARTIAL_MATCH | ACTION | Yes | 중간 | candidate set / holding score input 진단 유지 |
| symbol_diff_removed | direct sell path 확인 안 됨 | REVIEW_EXIT | MISMATCH but intentionally downgraded | REVIEW | No | 낮아짐 | 현재 상태 유지 |
| regime filter exit | REGIME_FILTER_EXCLUSIVE direct sell 존재 | 없음 | NOT_IMPLEMENTED | 없음 | No | 중간 | 정책 여부 별도 결정 |
| hedge-related exit | reason code는 있으나 실행 경로 불명확 | 없음 | INCONCLUSIVE | 없음 | No | 중간 | 별도 조사 |

## 8. MFU8 전체에서의 위치

MFU8-3은 MFU8 전체 중 “매도 판단 정합성”을 다루는 단계다.

```text
MFU8-1: Score / RS / Entry Signal parity
MFU8-2: Action / Review / Warning taxonomy
MFU8-3: SELL path parity
MFU8-4: 신규 전략 추가 체크리스트 및 자동 검증 강화
MFU8-5: 신규 유니버스 추가 체크리스트 및 universe parity
```

MFU8-3이 끝나야 front-test의 확정 SELL을 더 신뢰할 수 있다.

## 9. 리스크와 한계

- backtest는 PortfolioDB 기반이고, front-test는 current_state snapshot 기반이라 완전 동일화가 어렵다.
- trailing stop은 highest price, ATR, current price source에 따라 결과가 달라질 수 있다.
- front-test current_state snapshot이 오래되면 highest_price drift 위험이 커진다.
- explicit sell_signal은 front-test에서 아직 직접 계산하지 않는다.
- sell_signal을 바로 확정 SELL로 연결하면 매도 정책 변경이 될 수 있으므로 신중해야 한다.
- MFU8-3은 우선 parity 검증과 diagnostics 강화이지 대규모 리팩토링이 아니다.
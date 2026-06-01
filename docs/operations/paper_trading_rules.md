# PAPER14 Paper Trading Rules

## 1. Purpose

이 문서는 현재 PAPER14 paper 운용의 실제 매매 규칙을 정리한 운영 기준 문서다.

- 작성 기준일: `2026-05-27`
- 범위: 종목 점수 산정, 진입 규칙, 청산 규칙, 국면별 가중치, 진입 차단 조건
- 제외: Notion schema 상세, DB 설계, 구현 이력

## 2. Reference Code

이 문서는 아래 코드를 기준으로 정리했다.

- [config.py](/D:/python/StockScreener/config.py)
- [core/portfolio_config.py](/D:/python/StockScreener/core/portfolio_config.py)
- [core/decision_core.py](/D:/python/StockScreener/core/decision_core.py)
- [screener/strategy.py](/D:/python/StockScreener/screener/strategy.py)
- [core/daily_plan_generator.py](/D:/python/StockScreener/core/daily_plan_generator.py)
- [core/target_portfolio_state.py](/D:/python/StockScreener/core/target_portfolio_state.py)
- [core/backtest_engine.py](/D:/python/StockScreener/core/backtest_engine.py)
- [scripts/check_decision_parity.py](/D:/python/StockScreener/scripts/check_decision_parity.py)
- [scripts/paper.py](/D:/python/StockScreener/scripts/paper.py)

## 3. Core Principles

- Notion은 source of truth가 아니다.
- Notion은 입력 UI / 검토 UI / staging layer다.
- CSV / JSON / Markdown / SQLite가 source of truth다.
- Python이 validation / preview / commit / append / export 주체다.
- preview 없이 commit / append 금지다.
- FAIL이 있으면 commit / append 금지다.
- WARNING은 기본 차단이며 `--allow-warnings`가 있을 때만 예외 허용한다.

## 4. Trading Decision Structure

현재 신규 매수 판단은 아래 순서로 이뤄진다.

1. 시장 국면 판단
2. 전략별 signal 계산
3. signal 가중합으로 `score` 계산
4. `score >= score_threshold` 확인
5. `entry_signal == True` 확인
6. `rs_val > 0` 확인
7. stale / 데이터 부족 / 유니버스 제외 여부 확인
8. 목표 현금 비중, 헤지 비중, 최대 보유 수, buying power 제약 확인
9. 최종 진입 / 교체 / 관망 결정

즉, 현재 구조는 단순히 한 지표가 좋다고 사는 방식이 아니라, 현재 국면에서 유효한 신호가 동시에 충분히 겹치고, 상대강도까지 양수인 종목만 사는 구조다.

## 5. Market Regimes

### `BULL`

- 목표 현금 비중: `5%`
- 성격: 추세 추종 강화
- trailing stop multiplier: `3.25`
- 신규 진입에 가장 우호적

### `BEAR`

- 목표 현금 비중: `70%`
- 성격: 방어 모드
- trailing stop multiplier: `1.5`
- 추세형 신규 진입은 사실상 억제

### `UNSTABLE`

- 목표 현금 비중: `30%`
- 성격: 횡보 / 조정 대응
- trailing stop multiplier: `2.5`
- 평균회귀 + 거래량 회복 신호 중심

### `PANIC`

- 목표 현금 비중: `100%`
- 성격: 생존 우선
- trailing stop multiplier: `0.5`
- 신규 매수 금지

## 6. Score System

### 6.1 What `score` means

개별 종목의 `score`는 전략별 매수 신호가 현재 켜졌는지를 국면별 가중치로 더한 값이다.

기본 구조:

- 각 전략은 `signal_{strategy}` 형태의 0/1 신호를 만든다.
- 값이 `1`인 전략만 점수에 기여한다.
- 기여값은 해당 전략의 weight다.
- 여러 전략이 동시에 켜지면 합산된다.
- `rs_val > 0`이면 상대강도 보너스가 추가된다.

개념식:

```text
score =
signal_turtle * turtle_weight +
signal_rsi * rsi_weight +
signal_sma * sma_weight +
signal_bbands * bbands_weight +
signal_macd * macd_weight +
signal_bbs * bbs_weight +
signal_dema * dema_weight +
signal_obv * obv_weight +
signal_mfi * mfi_weight +
signal_vol_spike * vol_spike_weight +
rs bonus if rs_val > 0
```

### 6.2 Strategy groups

#### 추세추종

- `turtle`
- `sma`
- `dema`
- `macd`

#### 평균회귀

- `rsi`
- `bbands`
- `bbs`

#### 거래량 / 수급

- `obv`
- `mfi`
- `vol_spike`

### 6.3 Strategy signal meaning table

| 분류 | 전략 | 신호 의미 | 대표 해석 |
|---|---|---|---|
| 추세추종 | `turtle` | 일정 기간 고점 돌파 | 강한 추세 시작/지속 |
| 추세추종 | `sma` | 단기 SMA가 장기 SMA 상향 돌파 | 중기 추세 전환 |
| 추세추종 | `dema` | 빠른 이동평균 상향 교차 | 빠른 추세 재개 |
| 추세추종 | `macd` | MACD가 signal 상향 돌파 | 모멘텀 전환 |
| 평균회귀 | `rsi` | 과매도 구간 진입 | 눌림 반등 후보 |
| 평균회귀 | `bbands` | 하단 밴드 접촉/이탈 | mean reversion 후보 |
| 평균회귀 | `bbs` | squeeze 이후 상방 돌파 | 변동성 확장 진입 |
| 거래량/수급 | `obv` | OBV가 평균보다 강함 | 수급 우위 |
| 거래량/수급 | `mfi` | 강한 자금 유입 | 매수 압력 확인 |
| 거래량/수급 | `vol_spike` | 거래량 급증 | 참여 강도 확인 |

## 7. Regime Weight Table

주의:

- 아래는 `config.py`의 `REGIME_RULES`에서 명시적으로 확인되는 weight 중심이다.
- `macd`, `bbs`는 국면별 override가 명시적으로 보이지 않아 `기본값 유지 또는 별도 확인 필요`로 본다.

| 분류 | 전략 | BULL | BEAR | UNSTABLE | PANIC |
|---|---|---:|---:|---:|---:|
| 추세추종 | `turtle` | 1.5 | 0.0 | 0.0 | 0.0 |
| 추세추종 | `sma` | 1.0 | 0.0 | 0.0 | 0.0 |
| 추세추종 | `dema` | 1.2 | 0.0 | 0.0 | 0.0 |
| 추세추종 | `macd` | 기본값/확인 필요 | 기본값/확인 필요 | 기본값/확인 필요 | 0.0 취급 필요 |
| 평균회귀 | `rsi` | 0.5 | 0.2 | 1.5 | 0.0 |
| 평균회귀 | `bbands` | 1.0 | 0.2 | 1.2 | 0.0 |
| 평균회귀 | `bbs` | 기본값/확인 필요 | 기본값/확인 필요 | 기본값/확인 필요 | 0.0 취급 필요 |
| 거래량/수급 | `obv` | 0.5 | 0.8 | 0.8 | 0.0 |
| 거래량/수급 | `mfi` | 0.5 | 0.8 | 1.0 | 0.0 |
| 거래량/수급 | `vol_spike` | 0.5 | 1.0 | 0.8 | 0.0 |

### Regime interpretation

- `BULL`: 추세추종 중심. 올라가는 종목을 더 적극적으로 산다.
- `BEAR`: 추세추종을 거의 끄고 수급 확인 비중을 높인다.
- `UNSTABLE`: 평균회귀와 거래량 회복을 더 중시한다.
- `PANIC`: 신규 매수 signal weight를 사실상 0으로 취급한다.

## 8. Score Threshold

### 8.1 Meaning

`score_threshold`는 종합 점수가 최소 기준을 넘었는지 보는 정량 관문이다.

핵심 gate:

- `score >= score_threshold`
- `rs_val > 0`

### 8.2 Current default

기본값으로 보이는 값:

- `score_threshold = 1.5`

단, 실제 실행에서는 아래가 우선한다.

- `make_config()` 병합 결과
- 시장 국면별 override

### 8.3 Practical interpretation

- threshold가 낮으면 후보 수가 늘어난다.
- threshold가 높으면 강한 종목만 통과한다.
- threshold는 진입 신호의 최소 질 기준이다.

## 9. Entry Signal

### 9.1 Definition

`entry_signal`은 “지금 이 종목이 전략상 실제 매수 진입 가능한 상태인가”를 나타내는 최종 boolean gate다.

### 9.2 What it represents

`entry_signal`은 아래를 대표한다.

- 추세 돌파가 나왔는가
- 과매도 반등 구조가 나왔는가
- 수급 / 거래량이 받쳐주는가
- 최종 buy gate 수준까지 조건이 모였는가

### 9.3 Final entry gate

현재 진입 가능 후보는 아래 3개를 동시에 만족해야 한다.

1. `entry_signal == True`
2. `score >= score_threshold`
3. `rs_val > 0`

즉:

- 진입 타이밍이 맞아야 하고
- 신호 강도가 최소 기준을 넘어야 하고
- benchmark 대비 상대 우위도 있어야 한다

## 10. Entry Rules Summary Table

| 항목 | 기준 | 의미 |
|---|---|---|
| `entry_signal` | `True` | 전략상 진입 타이밍 발생 |
| `score` | threshold 이상 | 신호 강도 충분 |
| `rs_val` | `0` 초과 | 상대강도 양수 |
| stale check | 통과 | 최신성 문제 없음 |
| data sufficiency | 통과 | 지표 계산 가능 |
| `max_positions` | 미도달 | 슬롯 여유 있음 |
| buying power | 충분 | 현금 제약 통과 |
| regime | 진입 허용 | `PANIC` 등 금지 국면 아님 |

한 줄 규칙:

- `entry_signal=True`, `score>=threshold`, `rs_val>0`을 만족하고, 제약 조건까지 통과한 종목만 실제 매수 후보다.

## 11. Exit Rules Summary Table

| 항목 | 기준 | 의미 |
|---|---|---|
| trailing stop | stop price 하향 이탈 | 방어 매도 |
| sell signal | `exit_low` 이탈 등 | 전략상 청산 후보 |
| rebalance removal | 목표 포트폴리오 제외 | review 또는 매도 후보 |
| switching | 더 나은 후보 존재 + premium 충족 | 교체 매매 가능 |
| panic / defensive control | 국면상 위험 확대 | 현금화 / 헤지 우선 |

한 줄 규칙:

- 보유 종목은 trailing stop, 리밸런싱 필요, 교체 필요, 방어 국면 전환에 따라 청산 또는 축소된다.

## 12. Buy / Hold / Wait Rules

### Buy

아래를 모두 만족해야 한다.

- `entry_signal == True`
- `score >= score_threshold`
- `rs_val > 0`
- stale candidate 아님
- 유니버스 제거 종목 아님
- 데이터 부족 아님
- buying power 충분
- 목표 현금 비중 훼손 없음
- 최대 보유 종목 수 초과 아님
- 현재 국면에서 신규 진입 허용

### Hold

보유는 아래 상황에서 유지된다.

- trailing stop 미발동
- 전략상 즉시 청산 사유 없음
- 더 우수한 교체 후보 없음
- 강제 방어 모드 전환 없음

### Wait

다음 중 하나면 신규 매수보다 관망이 우선이다.

- `entry_signal=False`
- `score < score_threshold`
- `rs_val <= 0`
- stale data
- 데이터 부족
- buying power 부족
- `max_positions` 도달
- `BEAR` / `PANIC` 등 방어 국면
- preview 단계 `WARNING` 또는 `FAIL`

## 13. Practical Summary

현재 PAPER14의 진입 규칙은 아래로 요약할 수 있다.

- 강세장에서는 추세 신호에 높은 점수를 준다.
- 불안정장에서는 평균회귀와 거래량 회복을 더 본다.
- 하락장에서는 수급 확인 없이는 거의 사지 않는다.
- 공포장에서는 신규 매수를 하지 않는다.
- 어떤 국면이든 `entry_signal`, `score threshold`, `rs_val` 3개를 동시에 통과해야 진입 가능하다.

더 압축하면:

- 강세장에서는 추세를 사고, 불안정장에서는 반등을 사고, 공포장에서는 사지 않는다.

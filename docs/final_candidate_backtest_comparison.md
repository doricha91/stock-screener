# Final Candidate Backtest Comparison

## 1. 문서 목적

이 문서는 최근 최적화 및 OOS 검증 결과를 바탕으로 최종 후보를 2개로 압축하고, 실전 기본값 선정에 필요한 비교 근거를 정리하기 위해 작성했다.

현재 비교 대상은 아래 두 조합이다.

- 후보 A: `max_positions=15`, `UNSTABLE_trailing_stop_multiplier=1.5`
- 후보 B: `max_positions=10`, `UNSTABLE_trailing_stop_multiplier=2.5`

의사결정 목표는 다음과 같다.

- Train 성과 기준으로 더 우수한 조합이 무엇인지 확인
- OOS 강건성 기준으로 더 신뢰할 수 있는 조합이 무엇인지 확인
- 두 후보의 성향 차이를 구조 변수 관점에서 해석

## 2. 비교 대상 및 공통 환경 설정

### 2.1 비교 대상 후보 요약

| 후보 | Optimization ID | OOS Validation ID | 핵심 차이 |
| --- | ---: | ---: | --- |
| 후보 A | `699` | `87` | `max_positions=15`, `UNSTABLE_trailing_stop_multiplier=1.5` |
| 후보 B | `704` | `93` | `max_positions=10`, `UNSTABLE_trailing_stop_multiplier=2.5` |

### 2.2 공통 파라미터

두 후보는 아래 파라미터를 공통으로 사용한다.

- `entry_period=12`
- `exit_period=20`
- `rs_lookback=30`
- `atr_period=20`
- `rsi_period=14`
- `mfi_period=14`
- `sma_short_period=50`
- `sma_long_period=200`
- `score_threshold=1.5`
- `trailing_stop_multiplier=2.5`
- `SWITCHING_PREMIUM=1.0`
- `MIN_MODE_MAINTAIN_DAYS=5`
- `HEDGE_LIQUIDATION_PRIORITY='rs_low'`
- `BULL_target_cash_ratio=0.05`
- `BULL_switching_premium=1.5`
- `BULL_score_threshold=2.0`
- `BULL_trailing_stop_multiplier=3.25`
- `BEAR_target_cash_ratio=0.7`
- `BEAR_score_threshold=2.0`
- `BEAR_trailing_stop_multiplier=1.5`
- `UNSTABLE_target_cash_ratio=0.3`
- `UNSTABLE_score_threshold=1.5`
- `PANIC_target_cash_ratio=1.0`
- `PANIC_trailing_stop_multiplier=0.5`

### 2.3 공통 백테스트 조건

- Train 기간: `2020-01-01 ~ 2023-12-31`
- Test 기간: `2024-01-01 ~ 2025-12-31`
- 실행 엔진: [`core/optimizer_engine.py`](/D:/python/StockScreener/core/optimizer_engine.py), [`core/backtest_engine.py`](/D:/python/StockScreener/core/backtest_engine.py)
- 설정 조립: [`core/config_factory.py`](/D:/python/StockScreener/core/config_factory.py)
- 시장 레짐 사용: `True`
- 레짐 분기: `BULL / UNSTABLE / BEAR / PANIC`

### 2.4 적용된 거래 비용 및 벤치마크 기준

- 현재 백테스트 엔진은 [`screener/portfolio.py`](/D:/python/StockScreener/screener/portfolio.py)에서 `commission` 컬럼과 인자를 지원한다.
- 다만 실제 메인 백테스트 경로인 [`core/backtest_engine.py`](/D:/python/StockScreener/core/backtest_engine.py)에서는 `pf.buy(...)`, `pf.sell(...)` 호출 시 수수료 값을 넘기지 않으므로, 현재 비교 결과는 사실상 `commission=0.0` 기준으로 해석하는 것이 타당하다.
- 현재 메인 백테스트 엔진에는 슬리피지 반영 로직이 직접 포함되어 있지 않다.
- Buy & Hold 벤치마크 수치는 [`compare_benchmark.py`](/D:/python/StockScreener/compare_benchmark.py)의 `calculate_benchmark_stats()` 로직을 사용해 산출했다.
- 본 문서에서는 벤치마크를 단일 기준으로 고정하지 않고, `SPY`와 `QQQ`를 모두 병렬 기준으로 제시한다.

<!-- TODO: 수수료/슬리피지 정책을 실전 가정으로 별도 명시할지 여부는 사용자 결정 필요 -->

## 3. 성과 비교 분석

### 3.1 In-Sample (Train) 결과 비교

| 후보 | Opt ID | Return | CAGR | MDD | Sharpe | PF | Trades |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 후보 A | `699` | `110.66%` | `20.52%` | `-18.55%` | `1.0705` | `1.38` | `795` |
| 후보 B | `704` | `120.90%` | `21.96%` | `-24.29%` | `0.9531` | `1.38` | `473` |

해석:

- 후보 B는 총수익률과 CAGR이 더 높다.
- 후보 A는 MDD와 Sharpe가 더 우수하다.
- PF는 동일하다.
- 후보 B는 거래 수가 훨씬 적어 더 압축된 포트 구조를 가진다.

#### Train 벤치마크 비교

| 구분 | Return | CAGR | MDD |
| --- | ---: | ---: | ---: |
| SPY Buy & Hold | `46.31%` | `10.00%` | `-34.10%` |
| QQQ Buy & Hold | `89.45%` | `17.36%` | `-35.62%` |

| 후보 | vs SPY Alpha | vs QQQ Alpha |
| --- | ---: | ---: |
| 후보 A | `+64.35%p` | `+21.21%p` |
| 후보 B | `+74.59%p` | `+31.45%p` |

해석:

- Train 기준으로 두 후보 모두 SPY와 QQQ를 상회했다.
- 후보 B는 Train 총수익률 기준으로 벤치마크 초과폭이 가장 크다.
- 후보 A는 절대 수익률은 후보 B보다 낮지만, MDD와 Sharpe를 감안하면 더 안정적인 Train 우위 구조로 볼 수 있다.

### 3.2 Out-of-Sample (Test) 결과 비교

| 후보 | OOS ID | Train Sharpe | Test CAGR | Test MDD | Test Sharpe | Robustness |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 후보 A | `87` | `1.07` | `34.71%` | `-22.81%` | `1.56` | `1.45` |
| 후보 B | `93` | `0.95` | `49.59%` | `-23.71%` | `1.99` | `2.09` |

해석:

- OOS 기준으로는 후보 B가 CAGR, Sharpe, Robustness 모두 앞선다.
- 후보 A는 Train 우위가 있었지만 Test에서는 상대적으로 보수적이다.
- 후보 B는 Train 성과가 충분히 높았고 Test에서도 더 강하게 확장됐다.

#### Test 벤치마크 비교

| 구분 | Return | CAGR | MDD |
| --- | ---: | ---: | ---: |
| SPY Buy & Hold | `44.28%` | `20.15%` | `-19.00%` |
| QQQ Buy & Hold | `52.59%` | `23.56%` | `-22.88%` |

| 후보 | vs SPY Alpha | vs QQQ Alpha |
| --- | ---: | ---: |
| 후보 A | `-9.57%p` | `-17.88%p` |
| 후보 B | `+5.31%p` | `-3.00%p` |

해석:

- Test 기준으로 후보 A는 SPY와 QQQ 모두에 뒤진다.
- 후보 B는 SPY는 상회했고, QQQ에는 근소하게 미달했다.
- 따라서 최근 OOS 구간의 벤치마크 상대성과까지 포함하면 후보 B가 더 설득력 있다.

### 3.3 OOS 강건성 및 과최적화 여부 검토

현재 확보된 수치만 보면 두 후보 모두 Test에서 완전히 붕괴하는 형태는 아니다. 다만 성향 차이는 분명하다.

- 후보 A:
  - Train Sharpe가 더 높다.
  - Test Sharpe도 양호하지만 상승 폭은 상대적으로 제한적이다.
  - Train 최적 중심 후보로 해석할 수 있다.
- 후보 B:
  - Train Sharpe는 후보 A보다 낮지만 여전히 충분히 높다.
  - Test Sharpe와 Robustness가 더 높다.
  - 최근 OOS 환경에 더 잘 적응한 후보로 해석할 수 있다.

과최적화 관점에서 보면, 후보 B는 Train만 좋은 조합이 아니라 Test에서도 개선된 결과를 보였다. 따라서 현재까지는 단순 과최적화 후보로 보기 어렵다.

단, OOS 표본은 여전히 단일 구간(`2024-01-01 ~ 2025-12-31`)에 의존하고 있으므로, 이 문서의 결론은 “현재까지 가장 설득력 있는 후보 비교” 수준으로 보는 것이 맞다.

## 4. 핵심 변수 영향력 해석

### 4.1 `max_positions` 차이가 포트폴리오 분산에 미친 영향

후보 A와 후보 B의 가장 큰 구조 차이는 `max_positions`다.

- 후보 A: `15`
- 후보 B: `10`

해석:

- `15`는 더 넓은 분산을 허용한다.
- `10`은 더 적은 종목에 집중한다.

이번 결과에서는 `15`가 Train 기준 Sharpe와 MDD에서 더 유리했고, `10`은 OOS에서 더 높은 CAGR과 Sharpe를 보였다.

즉:

- 후보 A는 더 많은 종목 분산을 통해 Train 구간의 안정성을 확보한 구조
- 후보 B는 더 적은 종목 집중을 통해 최근 OOS 구간에서 성과를 끌어올린 구조

### 4.2 `UNSTABLE_trailing_stop_multiplier` 차이가 수익 실현 및 방어에 미친 영향

후보 A와 후보 B의 두 번째 핵심 차이는 `UNSTABLE_trailing_stop_multiplier`다.

- 후보 A: `1.5`
- 후보 B: `2.5`

해석:

- `1.5`는 더 타이트한 손절/이익보전 성향
- `2.5`는 더 느슨한 추적 손절 성향

이번 결과에서는:

- `1.5`가 Train에서는 더 안정적인 Sharpe 구조를 만들었다.
- `2.5`는 OOS에서 더 높은 수익과 Sharpe를 만들었다.

즉 후보 A는 `UNSTABLE` 구간에서 더 빨리 위험을 줄이는 구조이고, 후보 B는 `UNSTABLE` 구간에서 포지션을 더 오래 유지하면서 최근 구간의 추세를 더 많이 먹은 구조로 볼 수 있다.

### 4.3 변수 상호작용 관점

이번 비교의 핵심은 두 변수가 독립적으로 움직이지 않았다는 점이다.

- `max_positions=15`일 때는 `UNSTABLE_trailing_stop_multiplier=1.5`가 가장 강했다.
- `max_positions=10`일 때는 `UNSTABLE_trailing_stop_multiplier=2.5`가 가장 강했다.

따라서 이 두 후보는 단순히 “손절만 다르다”가 아니라, “포트 구조와 손절 구조가 함께 묶인 패키지”로 보는 것이 맞다.

## 5. 결론 및 최종 선정

### 5.1 장단점 요약

후보 A 장점:

- Train Sharpe 우위
- Train MDD 우위
- 더 넓은 분산 구조
- 안정적 최적화 후보로 해석 가능

후보 A 단점:

- OOS CAGR과 OOS Sharpe가 후보 B보다 낮다
- 최근 환경 적응력 기준에선 다소 보수적이다

후보 B 장점:

- Train 수익률 우위
- OOS CAGR, OOS Sharpe, Robustness 우위
- 거래 수가 더 적어 운용 단순성이 높다

후보 B 단점:

- Train MDD가 더 크다
- Train Sharpe는 후보 A보다 낮다
- 집중도가 더 높아 환경 변화에 민감할 가능성이 있다

### 5.2 최종 판단 기준

선택 기준은 다음처럼 나눌 수 있다.

- Train 안정성과 구조적 균형을 더 중시하면 후보 A
- OOS 강건성과 최근 성과 적응력을 더 중시하면 후보 B

실전 배치 관점에서는 OOS 결과를 더 중시하는 편이 일반적으로 타당하다. 따라서 현재까지의 수치만 보면 후보 B가 기본 후보로 조금 더 설득력 있다.

### 5.3 권장 기본 후보

현재 기준 권장 순서는 다음과 같다.

1. 기본 후보: 후보 B
   - `max_positions=10`
   - `UNSTABLE_trailing_stop_multiplier=2.5`
2. 대안 후보: 후보 A
   - `max_positions=15`
   - `UNSTABLE_trailing_stop_multiplier=1.5`

권장 이유:

- 후보 B는 Train 성과가 충분히 유지되는 상태에서 OOS 성과가 더 강하다.
- 후보 A는 보수형 대안으로 유지할 가치가 있다.

<!-- TODO: 사용자가 보수형 운용을 선호한다면 후보 A를 기본 후보로 둘지 재검토 가능 -->

## 6. 향후 과제 및 참고 자료

### 6.1 보류 사항 및 추가 검증 포인트

- 동일 후보 2개에 대해 추가 OOS 기간 또는 롤링 기간 검증
- 거래 비용(수수료/슬리피지) 가정 도입 시 순위 변화 여부 확인
- `UNSTABLE` 구간만 분리한 성과/거래 로그 비교
- SPY와 QQQ 중 어느 벤치마크를 공식 비교 기준으로 채택할지 결정

### 6.2 참고 데이터

- Train 후보 A: `optimization_log id 699`
- Train 후보 B: `optimization_log id 704`
- OOS 후보 A: `oos_validation_log id 87`
- OOS 후보 B: `oos_validation_log id 93`

### 6.3 관련 코드 경로

- [`core/param_grid.py`](/D:/python/StockScreener/core/param_grid.py)
- [`core/backtest_engine.py`](/D:/python/StockScreener/core/backtest_engine.py)
- [`core/optimizer_engine.py`](/D:/python/StockScreener/core/optimizer_engine.py)
- [`core/optimizer_storage.py`](/D:/python/StockScreener/core/optimizer_storage.py)
- [`config.py`](/D:/python/StockScreener/config.py)
- [`screener/portfolio.py`](/D:/python/StockScreener/screener/portfolio.py)

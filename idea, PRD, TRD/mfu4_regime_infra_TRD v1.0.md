# [TRD] MFU4: 시장 국면 인프라 시스템 기술 설계 v1.0

## 1. 데이터베이스 스키마 확장 (Step 1)
기존 `market_status_log` 테이블을 강화한다.

### 테이블 명: `market_status_log`
- `date` (TEXT, PK): 날짜 (YYYY-MM-DD)
- `status` (TEXT): 최종 판정 국면 (BULL, BEAR, UNSTABLE, PANIC)
- `vix_value` (REAL): 공포 지수 수치
- `trade_halted` (INTEGER): 0 (정상), 1 (매수 중단)
- `triggers` (JSON): 판정 근거 (Breadth 수치, SMA 이격률 등 정교한 값들)
- `description` (TEXT): 판정 요약 텍스트

## 2. 국면 판정 알고리즘 및 전환 관성 (Decision Engine)
단순 상태 판정을 넘어, 시스템의 안정성을 위한 로직을 `_decide_regime` 함수에 구현한다.

### 2.1. 판정 우선순위 (Priority Queue)
1. **PANIC:** VIX 돌파 혹은 급격한 낙폭 발생 시 즉각 전환.
2. **BEAR:** 지수(SPY/QQQ) 중 하나라도 200일선 하회 시.
3. **UNSTABLE:** 브레드스 경고, 50일선 이탈, 혹은 데드크로스 발생 시.
4. **BULL:** 모든 지표 정상.

### 2.2. 국면 전환 관성 (Inertia)
- **목적:** 휩소(Whipsaw)에 의한 잦은 포지션 교체 비용 최소화.
- **로직:** 
    - `PANIC` 진입은 예외 없이 즉시 수행.
    - 그 외 국면 전환 시, 이전 국면이 `PANIC`이 아니었고 유지 기간(`duration`)이 `MIN_MODE_MAINTAIN_DAYS`(5일) 미만이면 국면 전환을 잠금(Lock).
    - 만약 어제 `PANIC`이었으나 오늘 지표가 해소되었다면, 관성을 무시하고 즉시 다음 국면(BEAR, BULL 등)으로 전환하여 기회 비용 최소화.
- **특수 우선순위 (OVERSOLD):**
    - 시장 폭(Breadth)이 15% 이하(`BREADTH_OVERSOLD_THRESHOLD`)인 경우, 장기 이평선 하회(BEAR)보다 우선하여 `UNSTABLE`(스윙) 국면으로 판정. 이는 패닉 셀링 후의 기술적 반등 구간을 공략하기 위함.

## 3. 국면 선택적 백테스트 로직 (Step 3)
백테스트 엔진(`core/backtest_engine.py`)의 일일 리밸런싱 루프에 필터 로직을 추가한다.

### 로직 개요
```python
# Pseudo-code
target_regimes = config.get('TARGET_REGIMES', []) # ['BEAR', 'PANIC']

if target_regimes and current_regime not in target_regimes:
    # 지정된 국면이 아닐 경우 신규 진입을 무시하고 현금화 또는 기존 포지션 관망
    # 예: 'WATCH_ONLY' 모드 작동
```

### 지원 모드 (Regime Filter Modes)
1. **EXCLUSIVE:** 지정된 국면에서만 매매를 수행하고 나머지는 전액 현금화.
2. **FREEZE:** 지정된 국면이 아닐 때는 기존 포지션은 유지하되 신규 진입은 금지.

## 3. 실전 상황 대시보드 산출물 (Step 4)
`run_front_test.py` 실행 시 다음과 같은 형태로 터미널과 리포트에 출력한다.

### Dashboard Output
```text
◈ [MARKET STATUS DASHBOARD] 2026-04-12
------------------------------------------------------------
● Current Regime: [BEAR] (Warning: Downward Trend)
● Recent Transition: UNSTABLE -> UNSTABLE -> BEAR (Last 3 days)
● Critical Triggers:
  - VIX: 28.5 (Rising)
  - MA Cross: Below 200 SMA (Bearish)
  - Breadth: 15% (Extremely Weak)
------------------------------------------------------------
● Action Policy (from config.py):
  - Target Cash Ratio: 30%
  - Trailing Stop Multiplier: 1.5 (Tight)
  - Top Weights: RSI (2.0), BBands (2.0)
------------------------------------------------------------
```

## 4. 구현 및 테스트 계획
1. **Phase 1:** `market_analyzer.py`의 `_upsert_market_status_log`를 보강하여 상세 수치를 JSON으로 기록.
2. **Phase 2:** 백테스트 엔진에 `TARGET_REGIMES` 필터 옵션과 동작 로직 추가.
3. **Phase 3:** `run_front_test.py`에 최근 이력을 조회하여 상황판을 출력하는 헬퍼 함수 추가.
4. **Phase 4:** 실제 백테스트 결과를 통해 국면 필터링이 정확히 작동하는지 검증.

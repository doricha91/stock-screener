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

## 2. 국면 선택적 백테스트 로직 (Step 3)
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

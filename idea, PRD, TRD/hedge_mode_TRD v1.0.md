# [TRD] Hedge 모드(Hedge Mode) 기술 설계서 v1.0

## 1. 목적 (Goal)
`hedge_mode_PRD v1.0.md`의 요구사항을 기술적으로 구현하기 위한 아키텍처 및 데이터 흐름 설계.

## 2. 데이터 아키텍처 (Data Architecture)

### 2.1 신규 자산 데이터 확보
- **대상**: 지수 인버스 ETF (`SH`, `PSQ`, `SDS`, `SQQQ` 등)
- **수집 방식**: `screener/data_collector.py` 내 `update_market_indices` 함수를 확장하여 위 티커들을 `market_index` 테이블에 추가 저장.

## 3. 백테스트 엔진 로직 수정 (`core/backtest_engine.py`)

### 3.1 모드 전환 상태 머신 (State Machine)
- **변수**: `current_mode` (LONG / HEDGE)
- **조건**: `market_analyzer.get_market_state()`의 `regime` 결과에 따라 전환.
- **관성 제어**: `MIN_MODE_MAINTAIN_DAYS` 파라미터를 사용하여 잦은 전환 방지.

### 3.2 매매 로직 및 주문 집행 (Trade Execution)
- **Hedge 진입 트리거 (Long -> Hedge)**:
    1.  `market_analyzer.get_market_state()` 결과가 BEAR 또는 PANIC일 때 즉시 발동.
    2.  **기존 포지션 정리**: `HEDGE_RATIO`만큼의 현금을 확보하기 위해, 보유 종목 중 RS(상대강도)가 가장 낮은 순으로 매도 집행.
    3.  **인버스 직접 매수**: `market_index` 테이블에서 해당 날짜의 `HEDGE_ASSET` 종가(Close)를 조회하여 `PortfolioDB.buy(symbol, price, shares, date, strategy_name="Hedge")` 호출.
- **Hedge 청산 트리거 (Hedge -> Long)**:
    1.  국면이 BULL 또는 UNSTABLE로 복귀하거나, `MIN_MODE_MAINTAIN_DAYS` 경과 후 조건 만족 시 발동.
    2.  보유 중인 인버스 ETF 전량 매도 (`PortfolioDB.sell()` 호출).
    3.  확보된 현금을 다시 스크리너 추천 종목(Long Basket) 매수에 재배정.

## 4. 포트폴리오 관리 (`screener/portfolio.py`)
- **인버스 인식**: `PortfolioDB`가 인버스 자산을 일반 종목과 구분하여 관리할 수 있도록 `strategy_name="Hedge"` 플래그 활용.
- **수익률 계산**: 인버스 자산의 가격 하락이 포트폴리오 가치 상승으로 이어지도록 처리 (기존 매수 로직과 동일하나 자산 성격만 구분).

## 5. 설정 업데이트 (`config.py`)
```python
# Hedge Mode Settings
USE_HEDGE_MODE = True
HEDGE_TARGET_INDEX = 'QQQ'  # 하락 시 대응할 타겟 지수
HEDGE_ASSET = 'PSQ'        # 실제 매수할 인버스 ETF
HEDGE_RATIO_BEAR = 0.2     # BEAR 국면 시 자산의 20% 투입
HEDGE_RATIO_PANIC = 0.5    # PANIC 국면 시 자산의 50% 투입
MIN_MODE_MAINTAIN_DAYS = 5 # 모드 전환 후 최소 유지 일수
```

## 6. 결과 분석 확장 (`backtest_engine.py` & `optimizer_storage.py`)
- **성능 측정**: `safety_stats`에 `hedge_profit` 항목을 추가하여 헤지 전략이 실제로 얼마나 손실을 방어했는지 측정.

## 7. 구현 단계 (Implementation Steps)
1.  **데이터**: `market_index` 테이블에 인버스 ETF 주가 데이터 적재.
2.  **엔진**: `run_backtest_with_config` 내 모드 전환 판정 로직 추가.
3.  **검증**: 2022년 하락장 데이터를 활용하여 헤지 모드 적용 전/후 MDD 비교 테스트.

# [PRD] Hedge 모드(Hedge Mode) 구현 요구사항 정의서 v1.0

## 1. 개요 (Background & Objectives)
*   **배경**: 현재 시스템은 시장 악화 시 '현금 보유' 또는 '매수 중단'의 소극적 방어만 수행함. 하락장에서 수익을 방어하거나 추가 수익을 창출하기 위해 인버스 ETF를 활용한 능동적 헤지 로직이 필요함.
*   **목표**: 시장 국면(Regime)이 BEAR 또는 PANIC으로 전환될 때, 개별 종목 바스켓의 비중을 줄이고 인버스 ETF 포지션을 자동으로 구축하여 전체 포트폴리오의 MDD를 최소화함.

## 2. 주요 기능 범위 (Feature Scope)

### 2.1 국면 기반 모드 전환 (Regime-based Switching)
*   **Long 모드**: BULL 국면에서 작동. 개별 우량주 바스켓(NASDAQ100 등) 100% 운용.
*   **Hedge 모드**: 
    *   **BEAR 국면**: 개별 종목 비중 축소(예: 50%) + 인버스 ETF 진입.
    *   **PANIC 국면**: 개별 종목 전량 청산(현금 100%) + 인버스 ETF 집중 진입 또는 관망.
    *   **UNSTABLE 국면**: 신규 매수 금지 및 기존 종목 트레일링 스탑 강화 (보수적 운용).

### 2.2 헤지 자산 관리 (Asset Selection)
*   **대상 자산**: 지수 추종 인버스 ETF (예: SPY 하락 시 수익이 나는 `SH` 또는 `SDS`, QQQ 하락 시 수익이 나는 `PSQ` 또는 `QID`).
*   **선택 규칙**: 현재 시장 하락을 주도하는 지수(SPY vs QQQ)에 따라 대응하는 인버스 ETF 1개를 선택.

### 2.3 포지션 사이징 및 리스크 관리 (Risk Management)
*   **헤지 비중(Hedge Ratio)**: 전체 자산 대비 인버스 ETF에 할당할 비율 (변수화: 10~30%).
*   **최소 유지 기간**: 잦은 모드 전환(Whipsaw) 방지를 위해 전환 후 최소 N일(예: 5일)간 유지.
*   **손절/익절**: 인버스 ETF에도 별도의 트레일링 스탑 또는 지수 추세 반전 시 즉시 청산 로직 적용.

## 3. 기술적 상세 사양 (Technical Specifications)

### 3.1 추가될 핵심 파라미터 (`config.py` 확장 예시)
*   `USE_HEDGE_MODE`: True/False
*   `HEDGE_ASSET_LIST`: ['SH', 'PSQ', 'SDS', 'SQQQ']
*   `HEDGE_ALLOCATION_RATIO`: 국면별 인버스 비중 (예: BEAR=0.2, PANIC=0.3)
*   `MIN_MODE_MAINTAIN_DAYS`: 모드 전환 최소 유지 기간

### 3.2 로직 흐름 (`backtest_engine.py` 수정 방향)
1.  **매일 아침**: `market_analyzer`를 통해 오늘의 국면(Regime) 확인.
2.  **모드 판정**: 현재 모드와 국면이 일치하는지 확인 (최소 유지 기간 체크).
3.  **포지션 조정**:
    *   Long -> Hedge 전환 시: 상대강도(RS)가 낮은 순으로 종목 매도 -> 확보된 현금으로 `HEDGE_ASSET` 매수.
    *   Hedge -> Long 전환 시: 인버스 ETF 전량 매도 -> 스크리너 추천 종목 매수 시작.

## 4. 성공 지표 (Success Metrics / KPIs)
*   **MDD 개선**: Hedge 모드 미적용 대비 MDD 20% 이상 개선 (예: -30% -> -24%).
*   **CAGR 방어**: 급락장에서도 연간 수익률 훼손 최소화 (15~30% 목표 유지).
*   **전환 효율성**: 연간 모드 전환 횟수 20회 이내 유지 (노이즈 필터링 성능).

## 5. 단계별 구현 로드맵 (Roadmap)
*   **Step 1**: 인버스 ETF 데이터 수집 로직 추가 (`data_collector.py`).
*   **Step 2**: 백테스트 엔진 내 인버스 ETF 매매 가상 로직 구현.
*   **Step 3**: 국면 전환 시 기존 종목 매도 및 헤지 자산 매수 우선순위 로직 개발.
*   **Step 4**: 다양한 헤지 비중 및 레버리지 배수(1x, 2x)에 따른 최적화 테스트.

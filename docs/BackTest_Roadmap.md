# [MFU-BT1] 백테스트 엔진(v2) 아키텍처 및 구현 로드맵

## 1. 아키텍처 목표 및 원칙

본 백테스트(BT) 엔진은 단일 기간의 수익률(CAGR)을 최대화하는 것을 넘어, **'미래에도 살아남을 수 있는 견고한(Robust) 전략'**을 찾는 데 목적이 있습니다. 이를 위해 다음 4가지 핵심 원칙을 강제합니다.

1.  **IS/OOS 분리 (In-Sample / Out-of-Sample)**: 데이터를 훈련(IS)과 검증(OOS)으로 철저히 분리.
2.  **전진 분석 (Walk-Forward Optimization)**: 롤링 윈도우 기반으로 시간에 따른 시장 구조 변화(Regime Shift)에 적응하는지 검증.
3.  **파라미터 고원(Plateau) 탐색**: 가장 높은 수익을 낸 뾰족한 정점(Peak)이 아닌, 파라미터가 조금 변해도 성능이 유지되는 넓은 고원(Plateau)을 최적해로 선정.
4.  **미래 참조(Look-Ahead Bias) 원천 차단**: 시뮬레이터와 최적화기가 특정 시점 $T$에서 $T+1$의 데이터에 접근할 수 없는 데이터 주입 구조.

## 2. 모듈 구성 및 프론트테스트 재사용 전략

프론트테스트용으로 개발된 모듈들을 분석한 결과, **데이터 전처리와 종목 스크리닝 단계는 벡터화(Vectorized)하여 속도를 극대화**하고, **포트폴리오 자산 배분 및 슬롯 관리 단계는 프론트테스트와 동일한 `CurrentPortfolioState` 구조를 재사용하여 이벤트 드리븐(Event-Driven) 방식**으로 시뮬레이션하는 '하이브리드(Hybrid) 아키텍처'를 채택합니다.

*   **Data Loader (`data/loader.py`)**: 
    *   역할: 전체 과거 데이터를 로드하고, IS/OOS 구간을 잘라(Slicing) `Simulator`에 공급. 
    *   특징: Look-Ahead 방지를 위해 `data_manager.py`의 종가, VIX 등의 데이터를 시계열 마스킹 처리하여 반환.
*   **Vectorized Signal Generator (`screener/strategy_v2.py` / `core/indicators.py`)**:
    *   역할: 과거 전 기간에 대한 기술적 지표 및 진입/청산 신호를 Pandas/Numpy로 일괄 사전 연산.
    *   재사용: 기존 `indicator.py`와 `strategy.py`를 활용하되, `DataFrame.apply` 대신 벡터 연산으로 리팩토링하여 최적화 속도 확보.
*   **Event-Driven Simulator (`backtesting/core/simulator.py`)**:
    *   역할: 슬리피지(Slippage)와 수수료를 차감하며 일별 계좌 상태(`CurrentPortfolioState`)를 업데이트.
    *   재사용: `core.target_portfolio_state.py`의 정책을 100% 동일하게 사용하여 FrontTest(FT)와의 로직 불일치(Mismatch) 방지.
*   **Walk-Forward Optimizer (`backtesting/core/optimizer.py`)**:
    *   역할: 파라미터 그리드를 순회하며 IS 구간에서 최적 파라미터를 찾고 OOS 구간에서 성과를 평가. (기존 `core/optimizer_engine.py` 대체)
*   **Evaluator (`backtesting/core/evaluator.py`)**:
    *   역할: CAGR, MDD, Sharpe Ratio, Calmar Ratio 및 2D 히트맵 등을 통한 고원(Plateau) 지수 산출.

## 3. 구현 로드맵 (Phases)

*   **Phase 1: 데이터 주입 구조 및 Data Loader 개발**
    *   `TimeSeriesSplitter`: IS/OOS 날짜 범위를 동적으로 생성하는 제너레이터 구현.
    *   미래 참조 방지를 위한 데이터 접근 인터페이스 `HistoryDataFetcher` 구현.
*   **Phase 2: Hybrid Simulator (엔진 심장부) 구현**
    *   미리 계산된 시그널 맵(Signal Map)을 바탕으로 매일(Day-by-Day) 루프를 도는 엔진.
    *   매수/매도 슬리피지 모델링 및 `CurrentPortfolioState` 갱신 로직 (FrontTest 로직 재사용).
*   **Phase 3: Walk-Forward Optimizer 및 Evaluator 구현**
    *   파라미터 공간(Parameter Space) 정의 모듈.
    *   고원(Plateau) 판별 알고리즘 (인접 파라미터의 분산 페널티 부여).
*   **Phase 4: 시각화 및 검증 리포트 시스템**
    *   IS 성과 vs OOS 성과 비교 차트.
    *   파라미터 지형도(3D Surface or 2D Heatmap) 산출.

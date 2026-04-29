# MFU 5: Active Portfolio Switching TRD v1.0
**Project Iron Dome: 능동적 포트폴리오 순환매 설계**

## 1. 아키텍처 설계
본 설계는 `core/backtest_engine.py`의 매매 루프를 재구조화하여, 단순 매수(Buy)와 교체 매수(Switch)를 독립적인 의사결정 프로세스로 분리한다.

### 1.1 주요 컴포넌트 변화
*   **Decision Core**: 보유 종목의 점수를 후보군과 비교하는 `evaluate_switching_opportunity()` 함수 추가.
*   **Backtest Engine**: `if len(positions) < max_positions` 블록 외부로 교체 로직을 이동시켜 슬롯이 꽉 찬 상태에서도 판단 수행.
*   **Daily Plan Generator**: `TargetPortfolioState`와 `CurrentPortfolioState` 비교 시 '교체 짝짓기' 알고리즘 적용.

## 2. 상세 로직 (Logic Flow)

### 2.1 보유 종목 및 후보군 통합 랭킹 (Global Ranking)
1.  **현재 보유 종목군 ($H$):** 각 종목 $h \in H$의 최신 `score` 계산.
2.  **신규 매수 후보군 ($C$):** 각 종목 $c \in C$의 최신 `score` 계산 및 정렬.
3.  **교체 판정 알고리즘:**
    - 포트폴리오 슬롯이 가득 찼거나 가용 현금이 부족한 경우:
    - $C$의 최상위 종목 $c_{top}$과 $H$의 최하위 종목 $h_{bottom}$을 비교.
    - **조건**: $Score(c_{top}) > Score(h_{bottom}) + Premium$
    - **추가 조건 (선택)**: $Return(h_{bottom}) < 0$ 또는 `ALLOW_PROFIT_SWITCH == True`
    - 위 조건 만족 시: $h_{bottom}$ 매도 지시 및 $c_{top}$ 매수 지시 생성.

### 2.2 실전 집행 가이드 (Daily Plan)
*   **교체 페어링(Pairing)**: 매도와 매수를 한 쌍으로 묶어 리포트에 출력.
    - 예: `[SWITCH] SELL AAPL(Score 1.2) -> BUY NVDA(Score 2.8)`
*   **Buying Power 시뮬레이션**: 매도 체결 후 확보될 현금을 계산하여 매수 가능 수량 산출.

## 3. 설정 파라미터 (Configuration)
*   `SWITCHING_PREMIUM`: (float) 교체를 위한 최소 점수 격차 (기본값 1.0).
*   `ALLOW_PROFIT_SWITCH`: (bool) 수익 중인 종목도 교체 대상에 포함할지 여부 (기본값 False).
*   `SWITCHING_MAX_COUNT`: (int) 하루에 최대 교체 가능한 종목 수 (과도한 회전 방지).

## 4. 데이터 모델 변경
*   **`ReasonCode` 추가**:
    - `SWITCH_OUT`: 더 좋은 종목으로 갈아타기 위한 매도.
    - `SWITCH_IN`: 교체 매매를 통한 진입.
*   **`DecisionLog` 확장**:
    - 교체 결정 시의 비교 대상 종목군과 점수 차이를 기록하는 컬럼 추가.

## 5. 단계별 구현 계획
1.  **Phase 1**: `backtest_engine.py` 내의 교체 루프를 슬롯 제한과 무관하게 작동하도록 구조 개선.
2.  **Phase 2**: `daily_plan_generator.py`에 교체 페어링 출력 로직 추가.
3.  **Phase 3**: `config.py`의 국면별 `SWITCHING_PREMIUM` 최적화 테스트.

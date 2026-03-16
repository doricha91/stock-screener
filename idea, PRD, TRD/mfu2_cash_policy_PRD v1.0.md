# [PRD] MFU2 1단계: 현금 비중 정책 해석 및 계산 Helper 구현 v1.0

## 1. 개요 (Background & Objectives)
*   **배경**: 현재 `target_cash_ratio`는 국면별 설정값으로 존재하지만, 실제 매수 집행 시 강제적인 제약 조건으로 명확히 정의되지 않음.
*   **목표**: `target_cash_ratio`를 "반드시 유지해야 하는 최소 현금 버퍼"로 해석하고, 이를 기반으로 실제 매수 가능 금액(Buying Power)을 계산하는 정책과 도구를 마련함.

## 2. 주요 기능 범위 (Feature Scope)

### 2.1 현금 정책 명세 (Policy Specification)
*   **Minimum Cash Buffer**: `target_cash_ratio`는 단순 권고가 아니라, 계좌에서 절대적으로 유지해야 하는 현금 비중의 하한선으로 정의함.
*   **Excess Cash Only**: 신규 매수는 오직 이 하한선을 초과하는 현금(Excess Cash) 범위 내에서만 허용함.

### 2.2 계산 Helper 추가 (Calculation Helpers)
*   **필수 버퍼 계산**: 총 자산(Total Equity)과 목표 비중을 곱하여 절대 금액 산출.
*   **가용 구매력 계산**: 현재 현금에서 필수 버퍼를 뺀 나머지 금액 산출 (음수일 경우 0으로 처리).

### 2.3 정책 보호 (Policy Protection)
*   **단위 테스트**: 다양한 입력값(정상, 경계값, 음수 등)에 대해 정책이 의도대로 계산되는지 검증하는 테스트 코드 포함.

## 3. 정책 상세 (Policy Details)
*   **Required Cash Buffer** = `Total Equity * target_cash_ratio`
*   **Available Buying Power** = `max(0, Current Cash - Required Cash Buffer)`
*   **해석**: 현재 현금이 필수 버퍼보다 적다면, 구매력은 0이 되며 신규 매수는 차단됨.

## 4. 기술적 상세 사양 (Technical Specifications)
*   **위치**: `core/target_portfolio_state.py` (기존 포트폴리오 상태 관리 모듈과 통합)
*   **함수**:
    - `calculate_required_cash_buffer(total_equity, target_cash_ratio)`
    - `calculate_available_buying_power(current_cash, total_equity, target_cash_ratio)`
    - `get_cash_policy_status(...)`: 종합 진단용 함수.

## 5. 성공 지표 (Success Metrics)
*   **정책 명확성**: 코드와 주석을 통해 `target_cash_ratio`의 집행 해석을 즉시 이해할 수 있음.
*   **정확성**: 단위 테스트 100% 통과.
*   **확장성**: MFU2 후속 단계(엔진 연결)에서 즉시 호출 가능한 구조를 가짐.

## 6. 단계별 구현 로드맵 (MFU2 Roadmap)
*   **1단계 (현재)**: 정책 명세화 및 계산 Helper 구현 (완료).
*   **2단계**: 백테스트 엔진(`core/backtest_engine.py`)에서 Buying Power를 계산하도록 연결 (예정).
*   **3단계**: 실제 신규 매수 로직에 현금 제약 반영 (예정).
*   **4단계**: 현금 부족 시 신규 매수 차단 사유 로깅 강화 (예정).

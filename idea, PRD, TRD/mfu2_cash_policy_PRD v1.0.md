# [PRD] MFU2 4단계: 현금 정책 보고 및 로깅 강화 v1.0

## 1. 배경 및 목표 (Background & Objectives)
*   **배경**: MFU2 1~3단계를 통해 현금 정책의 계산, 엔진 연결, 집행 제약이 구현되었으나, 백테스트 전체 관점에서 정책의 효과와 위반 빈도를 한눈에 파악하기 어려움.
*   **목표**: 현금 정책 관련 이벤트를 표준화하고, 일일 로그에 상태 정보를 추가하며, 백테스트 종료 시 종합 통계를 제공하여 정책 준수 여부를 추적 가능하게 함.

## 2. 주요 기능 범위 (Feature Scope)

### 2.1 이벤트 및 사유 코드 표준화 (Standardized Reason Codes)
*   **이벤트 타입**: `DAILY_CHECK`, `ORDER_BLOCKED`, `ORDER_SKIPPED` 등을 유지하며 의미를 명확히 함.
*   **사유 코드 (Reason Codes)**: 
    *   `CASH_POLICY_OK`: 정책 준수 중.
    *   `BUFFER_VIOLATED`: 필수 현금 버퍼 침범 (현재 현금 < 필수 버퍼).
    *   `BUY_BLOCKED_BY_CASH_BUFFER`: 가용 구매력(BP) 부족으로 신규 매수 원천 차단.
    *   `INSUFFICIENT_BUYING_POWER`: 가용 BP가 있으나 특정 종목 매수 단가에 미달.

### 2.2 일일 상태 로깅 강화 (Daily Status Logging)
*   **CP_Status 요약**: `DAILY_CHECK` 로그의 `details` 필드에 `OK`, `BUFFER_VIOLATED`, `BUY_BLOCKED`, `LIMITED_BUYING_POWER` 등의 상태 문자열 추가.
*   **수치 필드 유지**: `required_cash_buffer`, `available_buying_power`, `is_violating_buffer` 등 기존 필드와 함께 기록.

### 2.3 백테스트 종료 요약 통계 (Summary Statistics)
*   **위반 통계**: `cash_policy_violation_days` (버퍼 위반 일수).
*   **차단/스킵 통계**: `order_blocked_count` (원천 차단), `order_skipped_count` (잔고 부족 스킵).
*   **비중 통계**: `avg_current_cash_ratio`, `avg_target_cash_ratio`, `min_cash_ratio`, `max_cash_ratio`.
*   **구매력 통계**: `avg_available_buying_power`.

### 2.4 정책 해석 및 주석 정리
*   `target_cash_ratio`는 **최소 현금 버퍼(Minimum Buffer)** 정책임을 명시.
*   `available_buying_power`는 버퍼를 제외한 순수 가용 자금임을 정의.

## 3. 기술적 세부 사항 (Technical Specifications)
*   **데이터 구조**: `safety_stats` 딕셔너리에 현금 정책 관련 카운터 및 누적 합계 필드 추가.
*   **계산 로직**: `calculate_metrics` 함수에서 누적 데이터를 바탕으로 평균 및 최종 통계 산출.
*   **로깅**: `DecisionLogger`를 통해 매일의 정책 상태와 매수 제한 사유를 상세 기록.

## 4. 성공 지표 (Success Metrics)
*   백테스트 결과 딕셔너리에 현금 정책 관련 8개 이상의 신규 지표가 포함됨.
*   일일 로그를 통해 현금 정책이 언제, 왜 매수를 차단했는지 추적 가능함.
*   기존 수익률 및 MDD 계산 로직에 영향을 주지 않으면서 정보량만 증가함.

## 5. 단계별 구현 로드맵 (MFU2 Roadmap Update)
*   **1단계**: 정책 명세화 및 계산 Helper 구현 (완료).
*   **2단계**: 엔진 연결 및 로깅 강화 (완료).
*   **3단계**: 실제 집행 제약 반영 (완료).
*   **4단계 (현재)**: 보고 및 요약 통계 강화 (완료).
*   **후속 작업**: MFU4와 연계하여 현금 부족 시 기존 포지션을 줄이는 '강제 감산/교체' 로직 구현 예정.

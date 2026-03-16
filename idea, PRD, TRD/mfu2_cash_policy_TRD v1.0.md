# [TRD] MFU2 4단계: 현금 정책 보고 및 로깅 강화 기술 설계서 v1.0

## 1. 시스템 아키텍처 및 역할
본 모듈은 백테스트 루프 전반에서 발생하는 현금 정책 관련 데이터를 수집, 집계하여 백테스트 종료 시 종합적인 정책 준수 리포트를 생성하는 역할을 수행합니다.

## 2. 주요 모듈 및 파일 역할
### 2.1 `core/backtest_engine.py` (통계 집계 및 리포팅)
- **책임**: 일일 루프 내 통계 누적 및 최종 메트릭 산출.
- **주요 변경 사항**:
    - `safety_stats` 확장: `cash_policy_violation_days`, `order_skipped_count`, `sum_current_cash_ratio`, `sum_target_cash_ratio`, `sum_available_buying_power`, `min_cash_ratio`, `max_cash_ratio`, `total_days` 필드 추가.
    - 일일 업데이트 로직: 매 루프 마지막에 현재 계좌 상태를 `safety_stats`에 누적.
    - `calculate_metrics` 고도화: 누적된 합계 데이터를 `total_days`로 나누어 평균값을 산출하고, 이를 `results` 딕셔너리에 통합.
    - 로깅 강화: `DAILY_CHECK` 이벤트의 `details` 필드에 `CP_Status` 요약 정보를 포함하여 가독성 증대.

## 3. 핵심 데이터 흐름 및 로직
1.  **초기화**: `safety_stats` 내 신규 통계 필드들을 0 또는 초기값으로 설정.
2.  **일일 누적**: 
    - `sum_current_cash_ratio += current_cash / total_equity`
    - `min_cash_ratio = min(min, current)`
    - 위반 발생 시 `cash_policy_violation_days += 1`
3.  **이벤트 기록**: 
    - `ORDER_BLOCKED`: `order_blocked_count` 증가 및 상세 사유 로깅.
    - `ORDER_SKIPPED`: `order_skipped_count` 증가 및 상세 사유 로깅.
4.  **최종 산출**: 백테스트 종료 시 `avg_*` 지표 계산 및 `results` 반환.

## 4. 상세 설계 및 제약사항
- **성능 오버헤드 최소화**: 복잡한 분석 대신 단순 누적 합산 및 카운팅 방식을 사용하여 백테스트 속도 저하를 방지함.
- **데이터 정합성**: `total_days`가 0인 경우를 대비한 예외 처리를 통해 제로 나누기(ZeroDivisionError) 방지.
- **로깅 표준화**: `BUFFER_VIOLATED`, `BUY_BLOCKED`, `LIMITED_BUYING_POWER`, `CASH_POLICY_OK` 등 4가지 상태값으로 정책 현황을 규격화.

## 5. 테스트 및 검증 전략
- **보고 기능 테스트 (`tests/test_mfu2_4_reporting.py`)**:
    - 백테스트 종료 후 반환되는 `results['safety_stats']` 내에 신규 필드들이 존재하고 값이 유효한지 확인.
    - `avg_current_cash_ratio`가 합리적인 범위(0.0~1.0) 내에 있는지 검증.
    - `DecisionLogger`에 의해 생성된 CSV 파일에서 `CP_Status` 문자열이 정상적으로 기록되었는지 확인.

## 6. 향후 과제 (Roadmap Integration)
- **감산 정책 (MFU4)**: 보고된 위반 지표(`cash_policy_violation_days`)를 0으로 만들기 위한 포지션 강제 축소 로직 도입.
- **시각화 연동**: 요약된 통계 데이터를 활용하여 대시보드 또는 차트에 현금 비중 추이를 시각화하는 기능 검토.

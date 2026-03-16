# [TRD] MFU2 2단계: 현금 비중 정책 기술 설계서 v1.0

## 1. 시스템 아키텍처 및 역할
본 모듈은 `target_cash_ratio`를 백테스트 엔진(`core/backtest_engine.py`)에 연결하고, 이를 기록하는 로거(`backtesting/logger.py`)를 확장하여 시스템의 관찰성을 확보합니다.

## 2. 주요 모듈 및 파일 역할
### 2.1 `core/backtest_engine.py` (엔진 통합)
- **책임**: 포트폴리오 상태 관리 및 현금 정책 상태 계산.
- **통합 로직**:
    - `get_cash_policy_status()`를 일일 루프 내에서 호출.
    - `target_state.target_cash_ratio`를 정책의 핵심 입력으로 사용.
    - 리밸런싱 판정 시점(`DAILY_CHECK`) 및 국면 전환 시점(`REGIME_CHANGE`)에 정책 수치 계산.

### 2.2 `backtesting/logger.py` (로깅 계층 확장)
- **책임**: 의사결정 이벤트 로그에 현금 정책 필드 기록.
- **수정 내용**:
    - `DecisionLogger.headers`에 `required_cash_buffer`, `available_buying_power`, `is_violating_buffer` 추가.
    - `log_event` 메서드 시그니처 수정 및 데이터 쓰기 로직 업데이트.

## 3. 핵심 데이터 흐름 및 정책
1.  **입력**: `pf.get_account_status()` -> `cash`, `total_equity`.
2.  **정책**: `target_state.target_cash_ratio` (국면별 목표치).
3.  **수치 산출**: `get_cash_policy_status(cash, total_equity, target_cash_ratio)` 호출.
4.  **로깅**: `d_logger.log_event(...)`를 통해 CSV 파일로 출력.

## 4. 상세 설계 및 제약사항
- **Shallow Integration**: 현재 단계에서는 `available_buying_power`를 실제 매수 로직의 제약 조건으로 사용하지 않고, 기록 및 관찰 목적으로만 사용함.
- **데이터 일관성**: `log_event` 내에서 계산되던 `actual_cash_ratio`와 정책 helper가 반환하는 `current_cash_ratio`를 동일하게 유지함.
- **무영향성**: 정책 계산 실패가 백테스트 전체의 중단으로 이어지지 않도록 방어적으로 접근함.

## 5. 테스트 및 검증 전략
- **통합 테스트 (`tests/test_mfu2_2_integration.py`)**:
    - `run_backtest_with_config` 실행 후 생성된 로그 파일의 헤더 및 데이터 행 검증.
    - 로그 파일 내 `available_buying_power`가 `cash - required_buffer` 계산 결과와 일치하는지 확인.
- **정량적 검증**: 로그 파일의 각 행이 NaN 없이 적절한 수치를 포함하고 있는지 전수 조사.

## 6. 향후 과제 (Roadmap Integration)
- **집행 연결 (Phase 3)**: 매수 루프(`pf.buy`) 진입 전 `available_buying_power`를 기반으로 가용 자금을 강제 제한.
- **차단 사유 로깅 (Phase 4)**: 현금이 부족하여 매수가 불가능할 때, 단순 스킵이 아닌 `INSUFFICIENT_BUYING_POWER` 등의 사유 코드를 로그에 명시.

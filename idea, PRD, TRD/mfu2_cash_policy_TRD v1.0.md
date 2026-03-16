# [TRD] MFU2 1단계: 현금 비중 정책 기술 설계서 v1.0

## 1. 시스템 아키텍처 및 역할
본 모듈은 `target_cash_ratio`를 실제 매매 집행 시의 '경성 제약(Hard Constraint)'으로 변환하기 위한 기술적 기반을 제공합니다.

## 2. 주요 모듈 및 파일 역할
### 2.1 `core/target_portfolio_state.py` (핵심 로직 추가)
- **책임**: 포트폴리오 상태 관리 및 현금 집행 정책 정의.
- **추가된 정책 함수**:
    - `calculate_required_cash_buffer()`: `total_equity * target_cash_ratio` 계산.
    - `calculate_available_buying_power()`: `max(0, current_cash - buffer)` 계산.
    - `get_cash_policy_status()`: 현재 현금 상태의 정책 위반 여부 진단.

## 3. 핵심 데이터 흐름 및 로직
### 3.1 현금 버퍼 및 구매력 계산 정책
1.  **입력**: `current_cash`, `total_equity`, `target_cash_ratio`.
2.  **버퍼 산출**: `target_cash_ratio`를 `[0.0, 1.0]` 범위로 클리핑(clipping) 후 `total_equity`와 곱함.
3.  **구매력 산출**: `current_cash`에서 산출된 버퍼를 차감. 단, 결과가 음수일 경우 `0.0`으로 보정하여 '매수 불가' 상태를 명시적으로 표현.

## 4. 상세 설계 및 제약사항
- **순수 함수 지향**: 모든 계산 함수는 부수 효과가 없으며, 상태 정보(cash, equity 등)를 인자로 직접 전달받음.
- **보수적 해석**: `current_cash`가 `required_buffer`보다 단 1원이라도 적으면 구매력은 즉시 `0`이 됨 (Partial purchase 방지 기반).
- **부동소수점 처리**: `pytest.approx`를 사용하여 미세한 소수점 오차에 대한 테스트 견고성 확보.

## 5. 테스트 및 검증 전략
- **단위 테스트 (`tests/test_cash_policy.py`)**:
    - `target_cash_ratio` 0% 및 100% 경계값 검증.
    - `total_equity` 0일 때의 예외 처리 검증.
    - 현금 부족 시 `available_buying_power`가 음수가 되지 않고 0으로 수렴하는지 확인.
    - 부동소수점 입력에 대한 정확도 검증.

## 6. 향후 과제 (Roadmap Integration)
- **엔진 연동**: `core/backtest_engine.py`에서 기존 하드코딩된 현금 계산 로직을 본 모듈의 함수로 교체.
- **상태 연동**: `CurrentPortfolioState`에 `total_equity`와 `current_cash` 필드 추가를 검토하여 정책 함수와의 인터페이스 간소화.

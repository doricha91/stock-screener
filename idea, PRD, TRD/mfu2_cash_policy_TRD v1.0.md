# [TRD] MFU2: 현금 정책 집행 및 리포팅 시스템 기술 설계서 v1.0

## 1. 시스템 아키텍처 및 역할 (Architecture & Role)
본 모듈은 목표 현금 비중(`target_cash_ratio`)을 실제 매수 제약으로 변환하여, 엔진이 자본 배분 정책을 강제하고 그 결과를 정량적으로 보고할 수 있도록 설계되었습니다.

## 2. 주요 모듈 및 파일 (Key Modules)
### 2.1 `core/target_portfolio_state.py` (정책 계산)
- **주요 함수**: 
    - `calculate_required_cash_buffer`: 총 자산 대비 유지해야 할 최소 현금 금액 산출.
    - `calculate_available_buying_power`: 실제 매수 가능한 초과 현금 산출.
    - `get_cash_policy_status`: 현금 정책 준수 현황(버퍼, 가용자금, 위반여부)을 종합 반환.

### 2.2 `core/backtest_engine.py` (집행 및 집계)
- **집행 제약**: 매수 루프 진입 전 `available_buying_power`를 상한선으로 설정하여 버퍼 침범을 원천 차단.
- **통계 집계**: `safety_stats`를 확장하여 일일 비중 평균, 위반 일수, 차단 횟수 등을 누적.
- **리포팅**: `calculate_metrics`를 통해 누적 데이터를 최종 지표로 변환하여 반환.

### 2.3 `backtesting/logger.py` (관찰성)
- **DecisionLogger**: `DAILY_CHECK`, `ORDER_BLOCKED`, `ORDER_SKIPPED` 등의 이벤트를 통해 정책 결정의 근거를 CSV로 기록.

## 3. 핵심 기술 상태 (Technical State)
- **현금 정책 워크플로우**: 계산 → 엔진 연결 → 집행 제약 → 보고 단계까지 전체 반영 완료.
- **제약 방식**: 'Minimum Cash Buffer' 원칙을 준수하며, 가용 자금 범위 내에서만 `pf.buy` 호출 허용.
- **보고 체계**: 백테스트 종료 시 `avg_current_cash_ratio`, `order_blocked_count` 등 8종 이상의 전용 지표 산출.

## 4. 알려진 한계 및 기술 부채 (Known Limitations)
- **요약 필드 정합성**: `summary.csv`와 `results` 딕셔너리 간의 필드명 및 노출 항목의 추가 정합성 검토 필요.
- **상태 문자열 체계**: 로그에 기록되는 `reason_code` 및 상태 문자열(`BUFFER_VIOLATED` 등)의 체계적 분류 및 문서화 보강 필요.
- **테스트 격리성**: 현재 통합 테스트가 실제 데이터 엔진에 일부 의존하고 있어, 순수 로직 검증을 위한 Unit Test 강화 여지 있음.

## 5. 상태 및 완료 메모 (Status & Closeout Note)
- **상태**: 완료 처리 (후속 보완 일부 남음)
- **메모**: MFU2의 핵심 기술적 목표(집행 제약 및 보고)는 달성되었으며, 현재 시스템은 정책에 기반한 자본 배분을 수행함. 리포팅 품질 개선 및 테스트 강화는 후속 보완 작업으로 관리함.

## 6. 후속 작업 (Next Steps)
- **MFU4 연계**: 현금 부족 시 기존 포지션을 강제로 매도하여 비중을 맞추는 '강제 감산/교체' 로직 설계 및 구현 예정.

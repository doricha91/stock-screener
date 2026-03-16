# [TRD] MFU2 3단계: 현금 비중 정책 기술 설계서 v1.0

## 1. 시스템 아키텍처 및 역할
본 모듈은 `available_buying_power`를 실제 매수 루프의 실행 제약으로 변환하여, 목표 현금 비중을 유지하면서도 가용 자금 범위 내에서 최선의 매수를 수행하도록 설계되었습니다.

## 2. 주요 모듈 및 파일 역할
### 2.1 `core/backtest_engine.py` (집행 로직 고도화)
- **책임**: 가용 구매력 기반의 포지션 사이징 및 진입 차단.
- **주요 변경 사항**:
    - `remaining_bp` 로컬 변수를 도입하여 당일 매수 루프 내의 누적 지출 관리.
    - 매수 루프 진입 전 `remaining_bp <= 0` 여부를 1차 판단.
    - 종목별 매수 수량 결정 시 `min(total_equity/max_positions, remaining_bp)` 공식을 적용하여 개별 종목이 버퍼를 침범하지 않도록 제약.
    - 매수 성공 직후 `remaining_bp`에서 `order_value`를 즉시 차감하여 다음 후보 종목에 대한 구매력 동기화.

## 3. 핵심 데이터 흐름 및 로직
1.  **초기화**: `remaining_bp = cp_status['available_buying_power']`.
2.  **루프 판단**:
    - `remaining_bp <= 0`: `ORDER_BLOCKED` 로그 남기고 루프 건너뜀.
    - `remaining_bp < symbol_price`: `ORDER_SKIPPED` 로그 남기고 해당 종목 스킵.
3.  **수량 산출**: `shares = int(min(target_value, remaining_bp) / price)`.
4.  **자금 갱신**: `remaining_bp -= (shares * price)`.

## 4. 상세 설계 및 제약사항
- **동일 비중 원칙 보존**: 기존의 `total_equity / config['max_positions']` 정책을 기본으로 하되, 남은 구매력이 이보다 적을 경우에만 구매력에 맞춰 수량을 축소함.
- **실시간성 보장**: 루프 내에서 `pf.get_account_status()`를 매번 호출하는 대신 로컬 변수 `remaining_bp`를 통해 논리적 제약을 유지하여 성능과 복잡도 사이의 균형 유지.
- **보수적 로깅**: 매수 불가 시 단순히 스킵하지 않고, `rebalance_reason` 필드에 `BUY_BLOCKED_BY_CASH_BUFFER` 또는 `INSUFFICIENT_BUYING_POWER`를 명시하여 사후 분석 편의성 증대.

## 5. 테스트 및 검증 전략
- **집행 제약 테스트 (`tests/test_mfu2_3_enforcement.py`)**:
    - 현금 비중 90% 설정 시나리오를 통해 신규 매수가 실제로 차단되거나 축소되는지 확인.
    - 로그 파일에서 `ORDER_BLOCKED` 또는 `ORDER_SKIPPED` 이벤트 발생 여부 검증.
    - 백테스트 종료 후 실제 현금 비중이 설정된 하한선을 침범하지 않았는지 확인.

## 6. 향후 과제 (Roadmap Integration)
- **감산 정책 (MFU4)**: 현재는 신규 매수만 차단하고 있으나, 국면 악화 시 기존 포지션을 줄여서 현금 비중을 확보하는 '강제 감산' 로직과의 연결 필요.
- **로깅 고도화 (Phase 4)**: 차단된 주문의 비중과 금액을 요약하여 리포트에 포함하는 기능 보강.

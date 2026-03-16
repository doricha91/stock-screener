# [PRD] MFU2 2단계: 현금 정책 엔진 연결 및 관찰성 강화 v1.0

## 1. 개요 (Background & Objectives)
*   **배경**: MFU2 1단계에서 구현한 현금 정책 helper가 엔진 내부에서 실제로 호출되지 않아, 매 거래일의 구매력(Buying Power) 수치를 확인할 수 없음.
*   **목표**: `backtest_engine.py`의 일일 루프에 현금 정책 helper를 연결하여, 정책 준수 여부와 가용 자금을 매일 계산하고 로그에 기록함.

## 2. 주요 기능 범위 (Feature Scope)

### 2.1 엔진 내부 연결 (Engine Integration)
*   **데이터 흐름**: 엔진의 현재 자산(`total_equity`), 현금(`cash`), 목표 비중(`target_cash_ratio`)을 정책 helper에 전달.
*   **계산 시점**: 매일 리밸런싱 판정 후, 실제 매수 집행 직전에 정책 상태를 계산.

### 2.2 관찰성 보강 (Observability)
*   **DecisionLogger 확장**: 로그 파일(`decision_*.csv`)에 현금 정책 관련 3개 필드 추가.
    - `required_cash_buffer`: 필수 유지 현금액.
    - `available_buying_power`: 신규 매수 가능 금액.
    - `is_violating_buffer`: 정책 위반 여부.

### 2.3 정책 정합성 검증 (Validation)
*   **통합 테스트**: 백테스트 실행 시 로그 파일에 정책 수치가 정확히 기록되는지 검증하는 테스트 추가.

## 3. 기술적 상세 사양 (Technical Specifications)
*   **수정 파일**:
    - `core/backtest_engine.py`: 정책 helper 호출 및 데이터 매핑.
    - `backtesting/logger.py`: 로그 헤더 및 데이터 기록 로직 확장.
*   **데이터 출처**:
    - `total_equity`, `current_cash`: `pf.get_account_status()`로부터 획득.
    - `target_cash_ratio`: `target_state.target_cash_ratio`로부터 획득.

## 4. 성공 지표 (Success Metrics)
*   **관찰 가능성**: 백테스트 로그를 통해 매일의 '필수 현금 버퍼'와 '실제 구매력'을 수치로 확인 가능함.
*   **정확성**: 통합 테스트(`test_mfu2_2_integration.py`)를 통해 계산 로직과 기록 로직의 정합성 확인.
*   **안정성**: 기존 백테스트 실행 결과(수익률 등)에 영향을 주지 않음 (Shallow Integration).

## 5. 단계별 구현 로드맵 (MFU2 Roadmap Update)
*   **1단계**: 정책 명세화 및 계산 Helper 구현 (완료).
*   **2단계 (현재)**: 엔진 연결 및 로깅 강화 (완료).
*   **3단계**: `available_buying_power`를 실제 신규 매수 수량 제한에 반영 (예정).
*   **4단계**: 현금 부족 시 진입 차단 사유 상세 로깅 (예정).

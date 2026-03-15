# [TRD] 백테스트-실전 공통 판단 코어 기술 설계서 v1.0

## 1. 시스템 아키텍처 개요
본 모듈은 백테스트 엔진(`backtest_engine.py`)과 실전 스크리너 간의 판단 기준을 통합하기 위해 설계되었습니다. 모든 로직은 부수 효과(Side-effect)가 없는 순수 함수로 구현되어 테스트와 재사용에 최적화되어 있습니다.

## 2. 주요 모듈 및 파일 역할
### 2.1 `core/target_portfolio_state.py`
- **책임**: 의사결정의 핵심 '두뇌' 역할.
- **주요 함수**:
    - `build_target_portfolio_state()`: 국면, 후보군, 설정을 기반으로 목표 상태 생성 (오케스트레이터).
    - `determine_target_long_slots()`: 보수적 내림 정책 기반 가용 슬롯 계산.
    - `evaluate_rebalance_need()`: 현재 vs 목표 상태 비교 및 사유 코드 산출.

### 2.2 `core/backtest_engine.py` (Integration)
- **연결 방식**: Shallow Integration (기존 실행 로직을 유지하며 판단 정보만 주입).
- **시점**: 시장 데이터 업데이트 후 매매 집행 직전.
- **데이터 변환**: 엔진의 `buy_signal` 데이터를 코어의 `entry_signal`로 보수적 매핑.

### 2.3 `backtesting/logger.py`
- **확장**: `DecisionLogger`에 리밸런싱 관련 4개 필드(`rebalance_needed`, `rebalance_reason`, `target_symbols`, `current_symbols`) 추가 지원.

## 3. 핵심 데이터 구조 (Dataclass)
```python
@dataclass(frozen=True)
class TargetPortfolioState:
    market_state: str
    target_cash_ratio: float
    target_hedge_ratio: float
    target_long_slots: int
    target_symbols: List[str]

@dataclass(frozen=True)
class RebalanceDecision:
    rebalance_needed: bool
    rebalance_reason: List[str]
    # ... 차이 내역 필드들
```

## 4. 상세 설계 정책
### 4.1 슬롯 및 비중 계산
- **가용 비중**: `1.0 - target_cash_ratio - target_hedge_ratio`
- **슬롯 수**: `int(max_positions * 가용 비중)`. 단, `PANIC` 시 강제 0.
- **허용 오차(Tolerance)**: `config` 설정 우선, 기본값 0.05 적용.

### 4.2 후보 종목 정렬 및 필터링
- **필터링**: `entry_signal == True` AND `score >= threshold` AND `rs_val > 0`.
- **정렬 키**: `(-score, -rs_val, symbol)`. 동일 조건 시 알파벳 순 정렬로 결과 일관성 확보.

## 5. 테스트 및 검증 전략
- **단위 테스트 (`tests/test_target_portfolio_state.py`)**:
    - 국면별 슬롯 할당 및 정렬 로직 검증.
    - 리밸런싱 판정 및 허용 오차 경계값 검증.
- **통합 테스트 (`tests/test_mfu1_c_integration.py`)**:
    - 실제 백테스트 루프 내에서 로그 파일 생성 및 컬럼 값 기록 여부 확인.

## 6. 기술적 한계 및 향후 개선 사항
- **실행 분리**: 현재는 판단 결과가 로그에만 남으며, 실제 `buy/sell` 실행 로직은 여전히 기존 방식을 따름.
- **환경 의존성**: 엔진 통합 테스트가 실제 마켓 DB를 요구함 (향후 Mocking 필요).
- **스크리너 미적용**: 실전 스크리너와의 실제 코드 공유는 다음 단계 과제로 남음.

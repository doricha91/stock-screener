# MFU 6: Dynamic Regime Parameter Routing TRD v1.0
**Project Iron Dome: 국면별 파라미터 동적 라우팅 설계**

## 1. 아키텍처 설계
본 설계는 `core/config_factory.py`의 `make_config` 프로세스에 **Parameter Routing Layer**를 추가하여, 외부 주입된 파라미터가 시스템의 중첩된 설정 구조로 올바르게 배달되도록 한다.

### 1.1 주요 컴포넌트 변화
*   **Config Factory (`make_config`)**: `runtime_overrides`를 수신한 즉시 전처리(Pre-processing)를 수행하여 `REGIME_RULES`를 업데이트함.
*   **Param Grid**: `param_grid.py`에서 `{국면}_{변수}` 형식의 변수명을 사용하여 실험군 정의 가능.

## 2. 상세 로직 (Implementation Details)

### 2.1 파라미터 라우팅 알고리즘
```python
# runtime_overrides 예시: {'BEAR_target_cash_ratio': 0.5, 'score_threshold': 1.5}

ALLOWED_ROUTING_PARAMS = [
    'target_cash_ratio', 
    'hedge_ratio', 
    'switching_premium', 
    'score_threshold', 
    'trailing_stop_multiplier'
]

REGIMES = ['BULL', 'BEAR', 'UNSTABLE', 'PANIC']

def route_parameters(base_config, overrides):
    for key, value in overrides.items():
        for regime in REGIMES:
            prefix = f"{regime}_"
            if key.startswith(prefix):
                param_name = key[len(prefix):]
                if param_name in ALLOWED_ROUTING_PARAMS:
                    # 중첩 구조 내부로 직접 주입
                    if regime in base_config['REGIME_RULES']:
                        base_config['REGIME_RULES'][regime][param_name] = value
```

### 2.2 오버라이드 적용 순서 (Precedence)
1.  **Base**: `config.py` 및 `portfolio_config.py`로부터 초기 딕셔너리 생성.
2.  **Global Override**: `runtime_overrides` 중 접두사가 없는 일반 변수 적용.
3.  **Regime Override**: 접두사가 붙은 국면 전용 변수를 `REGIME_RULES` 내부에 주입. (가장 높은 우선순위)

## 3. 데이터 모델 및 제약 사항
*   **Naming**: 반드시 `{국면_대문자}_` 접두사를 사용해야 함 (예: `PANIC_score_threshold`).
*   **Fallback**: 특정 국면의 변수가 실험군에 없으면, 해당 국면은 `config.py`에 정의된 기존 `REGIME_RULES` 값을 그대로 유지함.

## 4. 검증 방안 (Verification)
1.  **단위 테스트**: `make_config` 호출 후 결과물 딕셔너리에서 `REGIME_RULES['BEAR']['target_cash_ratio']`가 주입한 값과 일치하는지 확인.
2.  **통합 테스트**: `run_optimizer.py`에 국면 변수를 포함하여 실행하고, 생성된 `Decision Log`에서 국면 전환 시 해당 파라미터가 실제로 작동하는지 교차 검증.

## 5. 단계별 구현 계획
1.  **Step 1**: `core/config_factory.py`에 `route_parameters` 로직 구현.
2.  **Step 2**: `core/param_grid.py`에 `BEAR_target_cash_ratio` 등 실험 변수 추가.
3.  **Step 3**: 소규모 백테스트를 통한 수치 반영 여부 최종 확인.

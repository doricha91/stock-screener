# Agent Working Rules (AGENTS.md)

이 프로젝트(StockScreener)에서 작업할 때 반드시 준수해야 하는 규칙입니다.

## 1. Development Environment

- Python 버전은 프로젝트에서 명시한 버전을 따른다. 명시가 없다면 Python 3.11 계열을 기본 기준으로 사용한다.
- 패키지 관리는 `pip` 기준으로 수행한다.
- 새로운 라이브러리 추가 전 아래를 확인한다.
  - 기존 핵심 라이브러리와의 호환성
  - Python 버전 호환성
  - 현재 실행 경로 및 테스트에 미치는 영향
- 외부 패키지 추가 시 필요한 경우 관련 의존성 파일도 함께 업데이트한다.

## 2. Database Integrity

- DB 스키마 변경 전 반드시 사용자 승인을 받아야 한다.
- 스키마 변경에는 아래가 포함된다.
  - 테이블 추가/삭제/이름 변경
  - 컬럼 추가/삭제/타입 변경
  - 인덱스/제약조건 변경
- 대량 데이터 수정, 백필(backfill), 재계산 마이그레이션도 반드시 사용자 승인을 받아야 한다.
- `.db` 파일을 직접 수정하거나 DB 툴로 수동 편집하지 않는다.
- DB 변경은 반드시 파이썬 스크립트 또는 프로젝트 내 공식 마이그레이션 코드로만 수행한다.
- 단순 조회 및 검증 목적의 읽기 작업은 승인 없이 가능하다.

## 3. Change Scope and Atomicity

- 한 번의 작업은 하나의 기능, 하나의 버그 수정, 또는 하나의 리팩토링 목표에 집중한다.
- 관련된 여러 파일 수정은 허용되지만, 하나의 변경에 기능 추가와 구조 개편을 섞지 않는다.
- 대규모 구조 변경, 파일 대량 이동, 광범위한 리네이밍은 사용자 승인 없이 진행하지 않는다.
- 작업 순서는 가능한 한 아래를 따른다.
  1. 현재 구조 및 영향 범위 파악
  2. 수정 전략 수립
  3. 필요한 파일만 단계적으로 수정
  4. 검증 수행

## 4. Configuration and Secrets

- 전략 변수, 기간 설정, 경로, 외부 서비스 관련 설정값은 하드코딩하지 않는다.
- 전략 파라미터는 `config.py` 또는 `core/portfolio_config.py`에서 관리한다.
- 경로는 반드시 `core/paths.py`를 통해 관리한다.
- API 키, 토큰, 비밀값은 코드나 `config.py`에 하드코딩하지 않는다.
- 비밀정보는 환경변수 또는 별도 비공개 설정 방식으로 관리한다.
- 단, 함수 내부의 단순 고정 문자열이나 도메인상 의미가 분명한 작은 지역 상수까지 모두 설정 파일로 분리할 필요는 없다.

## 5. Documentation Sync

- 문서는 기능 전체가 아니라 **Minimum Functional Unit (MFU)** 단위로 구분하고 관리한다.
- 하나의 MFU는 사용자 관점 또는 시스템 관점에서 독립적으로 설명 가능한 최소 기능 단위를 의미한다.
- 새로운 기능 추가, 기존 기능 확장, 책임 이동, 구조 변경이 발생하면 해당 변경이 속한 MFU 기준으로 관련 문서를 갱신한다.
- 아래 중 하나에 해당하면 관련 문서를 업데이트한다.
  - 사용자 요구사항 변경
  - 기능 범위 변경
  - 주요 전략 로직 변경
  - 폴더 구조/의존성/실행 방식 변경
- 문서 업데이트 대상은 변경 유형에 맞춰 선택한다.
  - 아이디어/방향 변경: `idea`
  - 요구사항/사용자 시나리오/MVP 변경: `PRD`
  - 구조/기술 스택/의존성/배포/폴더 구조 변경: `TRD`
- `idea`, `PRD`, `TRD` 문서는 서로 독립된 전체 문서 묶음이 아니라, 가능한 한 동일한 MFU를 기준으로 대응되도록 유지한다.
- 하나의 MFU가 변경되면 관련 `idea`, `PRD`, `TRD` 중 필요한 문서만 선택적으로 갱신하되, 문서 간 설명이 서로 충돌하지 않도록 한다.
- 단순 버그 수정, 경미한 리팩토링, 주석 수정은 문서 업데이트를 생략할 수 있다.
- 문서와 코드가 충돌할 경우, 작업 종료 전 둘 중 하나는 반드시 정합하게 맞춘다.

## 6. Mandatory Validation

- 전략 로직, 신호 조건, 파라미터 계산, 포지션 계산, 수익률 계산을 수정한 경우 반드시 검증한다.
- 최소 검증 원칙은 아래와 같다.
  - 엔트리포인트 실행이 필요한 경우: `run_portfolio_backtest.py` 또는 `run_optimizer.py` 중 관련 스크립트 최소 1회 실행
  - 가능하면 빠른 검증 모드 또는 작은 샘플 구간을 우선 사용
- 수치 계산 로직 수정 시 가능한 한 아래 항목 중 relevant 한 값을 기존 결과와 비교한다.
  - 총 수익률
  - MDD
  - 거래 횟수
  - 신호 발생 횟수
  - 포지션 비중 변화
  - 리밸런싱 결과
- 결과 차이가 발생하면 아래 중 하나를 남긴다.
  - 의도된 변경이라는 설명
  - 버그 수정에 따른 변화라는 설명
  - 추가 검증이 필요하다는 명시
- 검증 없이 전략/수치 로직 수정을 완료된 것으로 간주하지 않는다.

## 7. Test Expectations

- 가능한 경우 아래 3종류의 테스트를 우선순위에 따라 유지한다.
  - 스모크 테스트: 주요 실행 파일이 기본 설정에서 정상 실행되는지 확인
  - 핵심 계산 단위 테스트: 이동평균, 수익률, breadth, 드로우다운, 신호 조건 등 핵심 계산 검증
  - 대표 케이스 회귀 테스트: 고정 입력 대비 핵심 결과값이 의도 없이 바뀌지 않는지 확인
- 새 계산 로직을 추가하거나 기존 계산식을 수정하면 관련 단위 테스트 추가를 우선 검토한다.
- 버그 수정 시 재현 가능한 입력이 있다면 회귀 테스트로 남기는 것을 우선 검토한다.
- 테스트가 없거나 부족한 경우, 최소한 실행 검증과 비교 로그를 남긴다.

## 8. Architectural Standards

- 파일 시스템 경로는 반드시 `core/paths.py` 기준으로 처리한다.
- 디렉터리 역할은 아래 기준을 따른다.
  - `core/`: 시스템 프레임워크 (엔진, 설정, 경로)
  - `screener/`: 데이터 수집 및 기술적 지표/신호 계산
  - `backtesting/`: 수익률 엔진 및 리포트/메트릭 생성
  - `scripts/`: 사용자 진입점 및 orchestration (비즈니스 로직 포함 금지)
- `run_*` 또는 `scripts/` 내 진입점 파일은 orchestration 중심으로 유지하고, 핵심 계산 로직을 과도하게 넣지 않는다.

### 8.1 Unified Configuration System (SSOT)

시스템의 모든 설정은 아래 4가지 범주로 분류하며, `core/config_factory.py`의 `make_config()`를 통해서만 최종 실행용 객체로 조립된다.

| 범주 | 명칭 | 파일/위치 | 설명 |
| :--- | :--- | :--- | :--- |
| **A** | **전역 정책** | `config.py` | 시스템 전체 스위치, 시장 국면 정의, 안전장치 활성여부 등 정책적 결정값 |
| **B** | **포트폴리오 구조** | `core/portfolio_config.py` | 초기 자본, 최대 종목 수 등 백테스트 엔진 구동을 위한 기본 구조값 |
| **C** | **최적화 파라미터** | `core/param_grid.py` | Optimizer가 탐색할 대상 변수 그리드 (이전 단계 값들을 덮어씀) |
| **D** | **런타임 오버라이드** | `run_*.py` | 실행 시점에 CLI 인자나 환경 변수로 강제되는 값 (최우선 순위) |

**설정 조립 우선순위 (병합 순서):**
1. `PORTFOLIO_CONFIG` (기본값)
2. `config.py` (전역 정책 반영)
3. `params` (최적화 대상 변수 덮어쓰기)
4. `runtime_overrides` (실행 시점 최종 강제값)

**규칙:**
- **일원화된 전달 경로**: 학습(Phase 1)과 검증(Phase 2) 모두 동일하게 `make_config(..., runtime_overrides=runtime_overrides)`를 호출하여 설정의 일관성을 보장한다.
- **이중 안전장치**: 명시적 주입(`runtime_overrides`)과 전역 패치(`patch_global_config`)를 병행한다. 이는 전역 `config` 모듈을 직접 참조하는 레거시 코드와의 호환성을 유지하면서도, 엔진에는 정확한 런타임 값이 전달되게 하기 위함이다.
- `param_grid.py`에는 최적화 대상이 아닌 "운영 정책" 값을 넣지 않는다.
- `run_*.py` 스크립트는 직접 딕셔너리를 조립하지 않고 `make_config()`에 필요한 override값만 전달한다.
- 새로운 전략 변수를 추가할 경우, 기본값은 `portfolio_config.py`에, 최적화 그리드는 `param_grid.py`에, 실험 스위치는 `config.py`에 배치한다.

## 9. Output and Experiment Hygiene

- 결과물, 로그, 임시 산출물은 프로젝트의 정해진 output 경로 규칙을 따른다.
- 임시 디버그 파일, 수동 백업 파일, 의미 없는 중간 산출물을 프로젝트 루트에 남기지 않는다.
- 기존 결과 파일을 덮어쓸 경우, 검증 또는 비교에 필요한 정보가 사라지지 않는지 먼저 확인한다.

## 10. Safety and Approval Boundaries

- 아래 작업은 사용자 승인 없이 진행하지 않는다.
  - DB 스키마 변경
  - 대량 데이터 마이그레이션
  - 대규모 구조 개편
  - 파일/폴더 대량 삭제 또는 이동
  - 외부 의존성의 중대한 추가/교체
- 확신할 수 없는 변경은 추측으로 진행하지 말고, 불확실성을 명시한 뒤 보수적으로 접근한다.

## 11. Failure Handling

- 검증이 실패하면 동일 작업 안에서 무관한 추가 수정을 이어가지 않는다.
- 먼저 실패 원인을 좁히고, 원인 후보와 영향 범위를 정리한다.
- 수치가 기존과 달라졌다면 “정상 변경”인지 “비의도 왜곡”인지 구분하기 전까지 완료 처리하지 않는다.
- 실행 불가 상태를 만든 경우, 새 기능 추가보다 복구를 우선한다.

## 12. Priority Order When Rules Conflict

- 규칙 간 충돌이 발생하면 아래 우선순위를 따른다.
  1. 데이터 무결성
  2. 수치 정합성 검증
  3. 아키텍처 보존
  4. 문서 동기화
  5. 개발 편의

## 13. Default Agent Workflow

Unless the user explicitly asks for immediate editing, the agent must follow this order:

1. Inspect relevant files.
2. Summarize current behavior.
3. Identify the minimal safe change.
4. List files that may need modification.
5. Edit only the necessary files.
6. Validate the change.
7. Report results, risks, and remaining limitations.

For high-risk areas such as DB schema, strategy logic, backtest metrics, market regime logic, hedge mode, optimizer behavior, and live trading logic, the agent must first provide an analysis before editing.

## 14. Protected Files and Directories

Do not modify, delete, rename, or overwrite the following unless explicitly approved:

- `.env`
- `.env.*`
- `outputs/*.db`
- `outputs/**/*.db`
- `*.sqlite`
- `*.sqlite3`
- API key files
- broker credential files
- generated reports used for comparison
- raw market data files

Read-only inspection is allowed when needed for debugging or validation.

## 15. Forbidden Commands

Do not run destructive commands unless explicitly approved.

Forbidden examples:

- `rm -rf`
- `del /s`
- `rmdir /s`
- commands that delete or overwrite `outputs/`
- commands that rewrite database files
- commands that run live trading or broker order placement
- commands that upload secrets or private data to external services
- commands that install, upgrade, or replace many packages at once without approval

## 16. Backtest Bias Prevention

The agent must not introduce look-ahead bias.

Rules:

- Do not use future prices, future indicators, or future benchmark values for current-day decisions.
- Signal generation must only use data available at the decision timestamp.
- If shifting signals, returns, or positions, explain the timing assumption.
- When modifying entry/exit logic, explicitly state whether the trade is assumed to occur at close, next open, or next close.
- Do not silently fill missing market data in a way that changes strategy behavior.

## 17. Strategy Change Boundary

Do not change strategy behavior for the purpose of improving performance unless the task explicitly asks for strategy research or parameter experimentation.

Bug fixes must preserve the intended strategy behavior as much as possible.

When a change affects performance metrics, report:

1. Whether the metric change is expected.
2. Which logic caused the change.
3. Whether the change is a bug fix, behavior change, or experimental strategy change.

## 18. Live Trading Safety

The agent must not place, simulate as real, or enable live broker orders unless explicitly requested.

Rules:

- Do not add code that submits live orders by default.
- Any broker integration must default to dry-run or paper trading mode.
- Do not change live trading flags from false to true.
- Do not store broker credentials in code.
- Any order execution logic must include explicit confirmation and logging.

## 19. Git Hygiene

Before editing, check the current git status when possible.

Rules:

- Do not overwrite unrelated user changes.
- Do not commit automatically unless explicitly requested.
- Do not create, delete, or rename branches unless explicitly requested.
- If there are pre-existing uncommitted changes, report them before editing.
- Keep diffs small and reviewable.

## 20. Test Reporting Rule

The agent must clearly distinguish between:

- Tests actually run
- Tests only recommended
- Tests that could not be run

If a test was not run, the agent must state the reason.

## 21. Required Final Report Format

After every task, report:

1. Summary
2. Changed files
3. Behavior changes
4. Tests run
5. Tests not run and why
6. Risks and limitations
7. Suggested next step

## 22. Legacy Code Handling

Existing scripts may contain legacy business logic. Do not perform large moves only to satisfy the directory role rules.

When improving structure:

- Prefer small extraction steps.
- Preserve existing CLI behavior.
- Move logic only when the task explicitly asks for refactoring.

## 23. Documentation Conflict Handling

If documentation and code conflict, do not make broad changes automatically.

Instead:

1. Identify the conflict.
2. Decide whether the current task scope includes fixing it.
3. If not in scope, report the conflict as a follow-up item.
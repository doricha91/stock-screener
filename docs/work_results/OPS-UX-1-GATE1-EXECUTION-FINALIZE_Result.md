# OPS-UX-1 Gate1 Execution Finalize 통합 결과

## Summary

기존 사용자 진입점 `02_gate1_execution_input.cmd` 하나에서 V2 EXECUTION 입력의 Finalize와 기존 Gate1 readiness 판정을 순서대로 수행하도록 통합했다. 기존 `gate1` 순수 판정 명령은 유지하고, 래퍼 전용 통합 명령 `gate1-execution-input`을 추가했다. 사용자에게 보이는 최종 JSON과 종료 코드는 Finalize 보조 결과가 아니라 Gate1의 PASS, WAIT, BLOCKED 결과다.

## Changed files

- `ops/runbook_wrappers/02_gate1_execution_input.cmd`
  - 기존 환경·경로·frozen context 전달과 종료 코드 전달을 유지하면서 통합 명령을 호출한다.
- `scripts/runbook_gate_checker.py`
  - Stage A, context, state, Daily Plan 증거를 먼저 검증한 뒤 V2 EXECUTION만 기존 `runbook_state.finalize_execution_input()`으로 Finalize한다.
  - NO_ACTION과 legacy V1은 Finalize를 건너뛴다.
  - Finalize 실패 시 행 조회와 Gate1 판정을 실행하지 않고 BLOCKED를 반환한다.
  - Finalize 성공 뒤에는 기존 Gate1 readiness 구현을 그대로 수행한다.
- `tests/test_runbook_gate_checker.py`
  - V2 PASS, timestamp/history, 재실행 no-op, WAIT 후 PASS, 선행조건 실패, state/context 오류, NO_ACTION, V1, Finalize 실패, query 실패 후 재시도 회귀를 추가했다.
- `tests/test_runbook_stage_wrappers.py`
  - 02번 래퍼의 통합 명령, 환경 인자, 종료 코드, Stage B 미실행을 고정했다.

## Behavior changes

- V2 + EXECUTION + 유효한 선행조건: `input_finalized=false`를 한 번만 `true`로 전환하고 Gate1을 판정한다.
- 이미 Finalize된 V2: `finalized_at`과 `execution_input_finalized` history를 추가 변경하지 않고 Gate1만 재판정한다.
- Finalize 뒤 행이 준비되지 않았으면 WAIT이며 Finalize 상태는 유지된다. 재시도 시 중복 Finalize 없이 PASS로 전환할 수 있다.
- NO_ACTION: Finalize하지 않으며 zero row는 PASS, 예상하지 못한 row는 BLOCKED다.
- legacy V1: V2 Finalize를 호출하지 않고 기존 `actual_price` readiness 의미를 유지한다.
- Stage A 미완료, state 누락, context 불일치, Daily Plan 증거 오류: Finalize 전에 fail-closed한다.
- Finalize 실패: Gate1 행 조회를 수행하지 않는다.
- Finalize 뒤 Notion 조회 실패: BLOCKED지만 Finalize는 유지되며 재시도 시 중복 mutation이 없다.
- Stage B 이후 래퍼는 자동 호출하지 않는다.

## Tests

- `python -m pytest tests/test_runbook_state.py -q`: 38 passed
- `python -m pytest tests/test_runbook_gate_checker.py -q`: 31 passed
- `python -m pytest tests/test_runbook_stage_wrappers.py -q`: 3 passed
- `python -m py_compile scripts/runbook_state.py scripts/runbook_gate_checker.py`: PASS
- `git diff --check`: PASS (기존 LF/CRLF 변환 경고만 존재)

테스트는 pytest의 임시 workspace와 주입한 `row_fetcher`/mock만 사용했다. 실제 Notion write, DB write, broker/order 실행은 없었다.

## Tests not run

전체 저장소 pytest suite는 실행하지 않았다. 이번 변경은 Gate1 상태 계약, Gate1 판정, 래퍼 회귀의 직접 범위이며 필수 지시 테스트와 관련 전용 테스트를 모두 실행했다. 저장소에는 이번 작업 전부터 접근 불가 임시 디렉터리와 다수의 unrelated dirty/untracked 파일이 있어 전체 suite의 신뢰 가능한 범위 분리가 어렵다.

## Risks and limitations

- Finalize와 이후 Gate1 query 사이에는 의도적으로 상태 저장 경계가 있다. 따라서 query 실패 시에도 Finalize는 롤백되지 않는다.
- 실제 Notion 서비스 장애 동작은 mock으로 검증했으며 외부 서비스 호출은 수행하지 않았다.
- 작업 시작 전 존재한 문서 변경, protected DB 변경, 임시 산출물은 수정하거나 정리하지 않았다.
- 지시문에서 참조한 `MFU-EO2_minimal_contract_recommendation.md`는 저장소에서 찾지 못해, 이미 구현된 V2 상수와 `finalize_execution_input()` 계약만 사용했다.

## AGENTS.md compliance

- DB/Notion schema, 전략·수익률·포지션 계산, Stage B 이후 lifecycle을 변경하지 않았다.
- protected DB와 기존 사용자 변경을 보존했다.
- 새 라이브러리, 새 사용자용 wrapper, 자동 commit/push를 추가하지 않았다.
- 실제 외부 write나 주문 실행 없이 temp workspace와 mock으로 검증했다.

## Suggested next step

검토자는 Review Evidence의 acceptance matrix와 scoped diff를 확인한 뒤, 별도 작업에서 실제 paper test 계정의 02번 래퍼를 dry-run 운영 리허설할 수 있다.

## Review Evidence

`docs/work_results/OPS-UX-1-GATE1-EXECUTION-FINALIZE_Review_Evidence.md`

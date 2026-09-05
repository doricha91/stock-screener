# RECOVERY-RESTART-1 결과

## Summary

운영일을 한 번 누락한 paper/test Runbook이 안전 조건을 모두 만족할 때 `restart_data_date == source_trade_date`로 바로 다음 정상 Runbook을 재시작할 수 있도록 Recovery 계약을 보완했다. 기존 multi-day 규칙인 `restart_data_date > source_trade_date`, immutable `runbook_recovery.v1` sidecar, exact target, ledger/hash 검증과 fail-closed lifecycle은 유지했다.

## Changed files

- `core/runbook_recovery.py`: Preview와 sidecar validation이 공유하는 restart 정책 helper, equality 전용 execution commit/ledger guard, source `ACTIVE_INCOMPLETE` 재검증을 추가했다.
- `tests/test_runbook_recovery.py`: equality 성공 lifecycle과 execution/commit/날짜/pair/evidence 실패 회귀를 추가했다.
- `docs/operations/runbook_recovery_contract.md`: multi-day와 missed-operating-day 재시작 날짜 정책을 명시했다.
- `docs/work_results/RECOVERY-RESTART-1_Review_Evidence.md`: 시작 상태, acceptance matrix, 테스트와 범위 검토 증거를 기록했다.

`core/runbook_day_rollover.py`는 기존 valid sidecar의 exact restart pair 소비 동작으로 요구사항을 충족하여 수정하지 않았다.

## Behavior changes

- `restart_data_date > source_trade_date`: 기존 Recovery 동작을 유지한다.
- `restart_data_date == source_trade_date`: 다음 조건을 모두 만족할 때만 허용한다.
  - source가 `ACTIVE_INCOMPLETE`이다.
  - source state에 execution commit report reference가 없다.
  - 성공한 `execution_commit` idempotency record가 없다.
  - source trade date를 포함한 canonical gap ledger row가 0건이다.
  - restart trade date가 source trade date의 정확한 다음 거래일이다.
  - 기존 confirmations, latest completed, source/calendar SHA256, immutable sidecar, target absence가 모두 유효하다.
- `restart_data_date < source_trade_date`: 계속 BLOCKED다.
- Preview와 authorization 후 evidence validation이 같은 날짜·commit 정책을 적용한다.
- source state/artifact는 변경하지 않고 authorization sidecar만 기존 create-only 방식으로 생성한다.

## Tests run

- 신규 equality 집중 검증: `6 passed, 27 deselected`
- `python -m pytest tests/test_runbook_recovery.py -q`: `33 passed`
- `python -m pytest tests/test_runbook_day_rollover.py -q`: `88 passed`
- `python -m py_compile core/runbook_recovery.py core/runbook_day_rollover.py`: PASS
- `git diff --check`: PASS

모든 테스트는 pytest 임시 workspace와 patched paper-account paths를 사용했다. 실제 Notion, DB, broker, 운영 Runbook state write는 없었다.

## Tests not run and why

전체 저장소 pytest suite는 실행하지 않았다. 지시문의 필수 Recovery/rollover suite 121개와 신규 집중 테스트를 모두 실행했으며, 작업 트리에는 이번 작업 전부터 다수의 unrelated dirty/untracked 파일과 접근 불가 임시 디렉터리가 존재한다.

## Risks and limitations

- equality 허용은 paper/test Recovery의 명시적 예외이며 일반 rollover 날짜 정책을 변경하지 않는다.
- execution commit 증거는 state의 commit report reference 또는 PASS idempotency record로 보수적으로 판정한다. 참조 파일이 없어도 state가 증거를 가리키면 fail-closed한다.
- ledger가 없거나 invalid하면 기존과 같이 Recovery가 차단된다.
- 실제 운영 workspace에서 authorize/rollover를 실행하지 않았으므로 외부 환경 리허설은 별도 승인된 paper test 절차가 필요하다.
- 작업 시작 전 존재한 OPS-UX-1 변경, 문서 변경, protected DB와 임시 파일은 수정하거나 정리하지 않았다.

## AGENTS.md compliance

- DB/Runbook state/execution ledger schema를 변경하지 않았다.
- 일반 rollover, Stage A AS-OF, 전략·포지션·수익률 로직을 변경하지 않았다.
- 실제 외부 write, broker 주문, dependency 설치, commit/push를 수행하지 않았다.
- 기존 사용자 변경과 protected DB를 보존했다.
- Recovery 운영 계약 문서를 코드와 동기화했다.

## Suggested next step

Review Evidence의 acceptance matrix와 scoped diff를 검토한 뒤, 별도 승인된 paper test workspace에서 먼저 `preview`만 실행해 source trade date ledger 0건과 exact restart pair를 확인한다.

## Review Evidence

`docs/work_results/RECOVERY-RESTART-1_Review_Evidence.md`

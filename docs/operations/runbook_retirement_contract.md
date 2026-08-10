# Runbook retirement contract

`runbook_retirement.py`는 생성 후 운영이 시작되지 않은 paper/test runbook day만 명시적으로 retire한다. Retire는 원본 state를 PASS 또는 DONE으로 바꾸지 않으며, controller-owned evidence를 `runbook_retirements/<RUNBOOK_DAY_ID>.json`에 기록한다.

## Safety contract

Retire 대상은 다음 조건을 모두 만족해야 한다.

- frozen account/data/trade date와 runbook day ID가 CLI 입력과 정확히 일치
- `current_stage=A`, `current_status=READY`
- completed step/stage 없음
- 모든 raw stage status가 `PENDING`
- artifact, idempotency, recovery, history, error 없음
- runbook별 command/stage/gate/reconciliation/verification evidence 없음
- paper/test 확인과 zero-progress retire 확인을 모두 명시
- 비어 있지 않은 reason 제공

Evidence는 원본 state 상대경로와 SHA-256을 고정한다. State가 이후 변경되거나 evidence의 context/hash가 변조되면 rollover는 해당 retire를 인정하지 않고 fail-closed한다. 같은 reason으로 다시 실행하면 기존 유효 evidence를 변경하지 않고 idempotent PASS를 반환한다.

## Classification

Rollover는 state를 다음과 같이 분류한다.

- `STANDARD_COMPLETED`: 현재 lifecycle의 Stage F/Step21과 Stage E/F evidence가 모두 유효
- `LEGACY_COMPLETED`: 원본 state에 F가 없고 A~E/E18 terminal historical evidence가 모두 유효
- `RETIRED`: strict zero-progress state와 retirement evidence가 현재 hash/context에 일치
- `ACTIVE_INCOMPLETE`: 나머지 모든 경우

다음 runbook 기준일은 `STANDARD_COMPLETED`와 `LEGACY_COMPLETED`의 최신 trade date만 사용한다. `RETIRED`는 blocker에서는 제외하지만 기준일 후보가 되지 않는다.

## Commands

Retire와 검증에는 `scripts/runbook_retirement.py retire` 및 `status`를 사용한다. 정확한 account/date/runbook ID를 항상 함께 전달한다. 실제 운영 명령은 retire 대상과 reason을 operator가 확인한 뒤 실행한다.

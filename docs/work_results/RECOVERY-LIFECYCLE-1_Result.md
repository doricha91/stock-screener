# RECOVERY-LIFECYCLE-1 결과

## Summary

Recovery Preview가 과거의 유효한 `RECOVERY_EXCLUDED` Runbook을 다시 active로 집계하던 lifecycle 분류 버그를 수정했다. Recovery 내부 분류가 rollover와 동일하게 `STANDARD_COMPLETED`, `LEGACY_COMPLETED`, `RETIRED`, `RECOVERY_EXCLUDED`, `ACTIVE_INCOMPLETE`를 구분하며, invalid recovery evidence는 계속 fail-closed되어 `ACTIVE_INCOMPLETE`로 취급된다.

## Changed files

- `core/runbook_recovery.py`: recovery evidence를 제외한 기본 분류와 evidence-aware lifecycle 분류를 분리하고 Preview/Status context에 caller calendar를 전달했다.
- `tests/test_runbook_recovery.py`: 과거 valid recovery 제외, invalid sidecar active 복귀, rollover 분류 일치 회귀 테스트를 추가했다.
- `docs/work_results/RECOVERY-LIFECYCLE-1_Result.md`: 작업 결과를 기록했다.
- `docs/work_results/RECOVERY-LIFECYCLE-1_Review_Evidence.md`: acceptance matrix와 검증 증거를 기록했다.

`core/runbook_day_rollover.py`는 기존 분류가 이미 유효 sidecar를 검증하므로 수정하지 않았다.

## Behavior changes

- 유효한 recovery sidecar가 있는 과거 source Runbook은 새로운 Recovery Preview의 active count에서 제외된다.
- 현재의 실제 `ACTIVE_INCOMPLETE` Runbook만 active로 집계되므로 valid 과거 recovery + 현재 active 조합은 정확히 active 1개가 된다.
- source hash, ledger contradiction, calendar/evidence 등 기존 validator가 sidecar를 invalid로 판정하면 해당 과거 Runbook은 다시 active로 집계된다.
- evidence validator가 source의 원래 상태를 검사할 때는 recovery disposition을 제외한 기본 분류를 사용하므로 자기참조 재귀 없이 source가 원래 `ACTIVE_INCOMPLETE`였는지 확인한다.
- RECOVERY-RESTART-1 equality/multi-day 날짜 정책, 일반 rollover, schema와 외부 lifecycle은 변경하지 않았다.

## Tests run

- 신규 lifecycle 집중 테스트: `2 passed, 33 deselected`
- `python -m pytest tests/test_runbook_recovery.py -q`: `35 passed`
- `python -m pytest tests/test_runbook_day_rollover.py -q`: `88 passed`
- `python -m py_compile core/runbook_recovery.py core/runbook_day_rollover.py`: PASS
- `git diff --check`: PASS
- `git status --short`: 실행 및 기록 완료

## Tests not run and why

전체 저장소 pytest suite는 실행하지 않았다. 작업지시문이 요구한 Recovery/rollover 전체 suite 123개와 신규 집중 테스트를 모두 실행했으며, 저장소에는 이번 작업 전부터 unrelated dirty/untracked workstream과 접근 불가 임시 디렉터리가 다수 존재한다.

## Risks and limitations

- Recovery 내부 분류는 각 active 후보의 sidecar를 실제 validator로 재검증하므로 상태 수에 비례한 파일·ledger 검증 비용이 발생한다. 현재 Runbook 수와 안전 우선 정책에서는 허용 가능한 범위로 판단했다.
- invalid sidecar는 의도대로 active로 복귀하지만, Recovery Preview의 최종 blocker는 active-count/source guard 중심으로 표현될 수 있다. 세부 invalid 이유는 기존 rollover classification/status validator에서 확인 가능하다.
- 실제 운영 workspace, Notion, DB, broker 또는 execution ledger에는 write를 수행하지 않았다.
- 기존 OPS-UX-1, RECOVERY-RESTART-1, protected DB 및 기타 dirty 변경은 보존했다.

## AGENTS.md compliance

- root `AGENTS.md`와 작업지시문 전체를 구현 전에 UTF-8로 읽었다.
- 브랜치 `gemini_cli_update`, 시작 HEAD와 dirty 상태를 확인하고 기존 변경을 덮어쓰지 않았다.
- schema, 전략·수치 로직, 일반 rollover 설계, Stage A AS-OF, live trading을 변경하지 않았다.
- DB/Notion/broker write, dependency 설치, reset/checkout/clean/stash/commit/push를 수행하지 않았다.
- 단일 lifecycle 버그와 직접 회귀 테스트로 변경 범위를 제한했다.

## Suggested next step

Review Evidence의 acceptance matrix와 scoped diff를 검토한 뒤, 필요하면 별도 승인된 paper/test fixture에서 연속 두 번째 Recovery를 preview-only로 리허설한다.

## Review Evidence

`docs/work_results/RECOVERY-LIFECYCLE-1_Review_Evidence.md`

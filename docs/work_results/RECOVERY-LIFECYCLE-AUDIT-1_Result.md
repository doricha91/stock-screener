# RECOVERY-LIFECYCLE-AUDIT-1 결과

## Summary

반복 Recovery lifecycle을 정상 완료 → Recovery #1 → target 완료 → 정상 rollover → Recovery #2 → target 완료 → 정상 rollover까지 감사했다. `RECOVERY_EXCLUDED` 전체를 현재 authorization으로 오인하던 rollover와 initialization guard를 수정해, valid하면서 unconsumed인 Recovery만 현재 후보로 선택하도록 정렬했다.

## Lifecycle audit findings

- Recovery 이력 없음, consumed 1개, unconsumed 1개, invalid evidence, active target, completed target의 기존 동작은 정상이다.
- consumed Recovery 2개 이상은 historical 이력이어야 하지만 rollover와 initialization이 영구 차단했다.
- consumed 여러 개 + unconsumed 1개에서는 현재 unconsumed 하나만 선택해야 하지만 전체 disposition 수로 차단했다.
- 두 번째 Recovery target 완료 후에도 consumed 이력 2개 때문에 정상 lifecycle로 복귀하지 못했다.
- invalid evidence는 `ACTIVE_INCOMPLETE`로 복귀해 active guard에 걸리므로 silently ignored되지 않는다.
- `validate_recovery_evidence()`의 `target_status == PRESENT`가 consumed 판정 SSOT로 적합하며 schema 변경은 필요하지 않았다.

## Root causes

- `RECOVERY_EXCLUDED`는 valid Recovery disposition/history인데 `preview_rollover()`와 `assert_initialization_allowed()`가 이를 곧바로 현재 authorization 집합으로 사용했다.
- 두 경로 모두 consumed 여부를 검사하기 전에 전체 recovery 개수로 `multiple_recovery_authorizations`를 판정했다.
- rollover와 initialization이 current authorization 선택 의미를 공유하지 않았다.

## Changed files

- `core/runbook_recovery.py`: validator 기반 `_current_recovery_authorizations()` helper를 추가하고 initialization guard가 unconsumed 후보만 사용하도록 수정했다.
- `core/runbook_day_rollover.py`: historical consumed Recovery를 제외한 현재 unconsumed 후보 0/1/2+ 선택 정책을 적용했다.
- `tests/test_runbook_recovery.py`: 반복 2회 Recovery 통합 테스트, 실제 운영 날짜 fixture, 복수 unconsumed fail-closed와 initialization 회귀를 추가했다.
- `docs/work_results/RECOVERY-LIFECYCLE-AUDIT-1_Result.md`: 작업 결과를 기록했다.
- `docs/work_results/RECOVERY-LIFECYCLE-AUDIT-1_Review_Evidence.md`: lifecycle 감사와 acceptance evidence를 기록했다.

## Behavior after change

- valid + consumed Recovery는 `RECOVERY_EXCLUDED` 이력으로 남지만 현재 authorization 후보에서는 제외된다.
- current unconsumed valid Recovery가 0개면 일반 rollover, 1개면 exact restart pair, 2개 이상이면 `multiple_recovery_authorizations`로 BLOCKED된다.
- invalid evidence는 계속 `ACTIVE_INCOMPLETE`와 active guard로 fail-closed된다.
- initialization guard도 동일 selection helper를 사용해 여러 historical Recovery 이후 정상 next context와 현재 exact target을 허용한다.
- target 생성 후에는 consumed가 되고 ordinary active guard가 적용되며, target 완료 후 일반 rollover로 복귀한다.
- RECOVERY-RESTART-1 equality/multi-day 날짜 정책과 RECOVERY-LIFECYCLE-1 base/evidence-aware 분류는 변경하지 않았다.

## Repeated-Recovery lifecycle test

`test_repeated_recovery_lifecycle_selects_only_current_authorization`이 하나의 연속 fixture에서 다음을 검증한다.

1. `2026-08-13 → 2026-08-14` Recovery #1 authorize.
2. `2026-08-21 → 2026-08-24` target 생성·완료 및 normal rollover.
3. `2026-08-24 → 2026-08-25` Recovery #2 source 생성·authorize.
4. Recovery #1은 consumed, Recovery #2는 unconsumed임을 확인.
5. rollover가 Recovery #2만 선택해 `2026-08-27 → 2026-08-28` exact pair를 반환.
6. Recovery #2 target 생성 후 consumed와 active guard 확인.
7. target 완료 후 consumed Recovery 2개를 보존한 채 normal `2026-08-28 → 2026-08-31` rollover와 state 초기화 성공.

## Tests run

- 신규 lifecycle 집중: `2 passed, 35 deselected in 6.98s`
- `python -m pytest tests/test_runbook_recovery.py -q`: `37 passed in 30.31s`
- `python -m pytest tests/test_runbook_day_rollover.py -q`: `88 passed in 20.56s`
- `python -m py_compile core/runbook_recovery.py core/runbook_day_rollover.py`: PASS
- `git diff --check`: PASS
- `git status --short`: 실행 및 기록 완료

## Tests not run and why

전체 repository pytest suite는 실행하지 않았다. 작업지시문이 요구한 신규 lifecycle 집중 테스트와 Recovery/rollover 전체 125개 테스트를 실행했으며, 저장소에는 이번 작업 전부터 unrelated dirty/untracked workstream과 접근 불가 임시 디렉터리가 다수 존재한다.

## Risks and limitations

- classification 이후 selection에서 validator를 다시 호출해 TOCTOU 변화도 fail-closed하지만, recovery 이력 수에 비례한 파일·ledger 재검증 비용이 있다.
- 비정상 fixture에서는 unconsumed authorization 2개를 구성할 수 있다. rollover와 initialization은 모두 차단하며, 정상 중앙 초기화 경로는 첫 exact target 외 새 source 생성을 허용하지 않는다.
- 실제 운영 workspace에 대한 read/write 명령은 실행하지 않았으므로 fixture 외 운영 상태 재확인은 사용자 검토 후 read-only preview로 수행해야 한다.
- 기존 dirty 파일과 protected DB는 보존했고 테스트가 노출한 임시 디렉터리는 삭제하지 않았다.

## Structural blockers

None.

## AGENTS.md compliance

- root `AGENTS.md`와 745줄 작업지시문 전체를 UTF-8로 읽었다.
- `gemini_cli_update`와 시작 HEAD/status를 확인하고 선행 RECOVERY-RESTART-1, RECOVERY-LIFECYCLE-1, OPS-UX-1 변경을 보존했다.
- schema, 일반 execution pipeline, Stage A, 전략, Notion 계약을 변경하지 않았다.
- 실제 운영 state/sidecar/ledger, DB, Notion, broker write를 수행하지 않았다.
- reset, checkout, clean, stash, commit, push를 수행하지 않았다.

## Suggested next step

Review Evidence를 검토한 뒤 실제 운영환경에서는 authorize/prepare를 실행하지 말고, 기존 read-only rollover preview를 다시 실행해 현재 unconsumed Recovery 하나와 `2026-08-27 → 2026-08-28` pair가 선택되는지 확인한다.

## Review Evidence

`docs/work_results/RECOVERY-LIFECYCLE-AUDIT-1_Review_Evidence.md`

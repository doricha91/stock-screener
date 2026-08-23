# Summary

PAPER-OPS-RUNBOOK-RECOVERY-CONTRACT1A의 lifecycle gap을 최소 수정했다. Recovery target가 `STANDARD_COMPLETED`된 뒤 consumed sidecar는 historical incident evidence로 남고, initialization guard는 기존 normal `preview_rollover()`가 반환한 exact next context만 허용한다. 실제 운영 workspace에는 read-only 조회만 수행했다.

# Gap fixed

기존에는 target 완료 후 rollover preview가 정상 순차 pair를 반환해도 `assert_initialization_allowed()`가 `recovery_authorization_already_consumed`로 실제 state 생성을 막았다. 이제 consumed recovery를 무조건 허용하지 않고 normal rollover SSOT와 requested context를 정확히 비교해 정상 lifecycle만 재개한다.

# Files changed

Production:

- `core/runbook_recovery.py`

Tests:

- `tests/test_runbook_recovery.py`

Task documents:

- `docs/work_results/PAPER-OPS-RUNBOOK-RECOVERY-CONTRACT1A_Result.md`
- `docs/work_results/PAPER-OPS-RUNBOOK-RECOVERY-CONTRACT1A_Review_Evidence.md`

`core/runbook_day_rollover.py`, `scripts/runbook_state.py`, sidecar schema/CLI/storage와 operations documentation은 CONTRACT1A에서 추가 변경하지 않았다.

# Consumed recovery semantics

Consumed는 recovery target state가 exact context로 이미 존재한다는 뜻이다. Target가 active이면 기존 active guard가 먼저 BLOCK한다. Target가 standard completed이고 다른 active가 없으면 guard는 `preview_rollover()`를 동일 calendar와 account로 호출한다. Preview가 PASS, non-RECOVERY이고 exact requested context와 일치할 때만 생성이 허용된다. Sidecar는 삭제·수정·재활성화되지 않는다.

# Target-active behavior

Recovery target `paper_pilot_202606_2026-08-21_2026-08-24`가 `ACTIVE_INCOMPLETE`인 동안 다음 runbook initialization은 `active_runbook_day_exists`로 BLOCK된다. 기존 CONTRACT1 behavior를 유지했다.

# Target-completed behavior

Target가 `STANDARD_COMPLETED`가 되면 recovery routing은 종료된다. Normal preview는 target를 latest completed baseline으로 사용해 `DATA_DATE=2026-08-24`, `TRADE_DATE=2026-08-25`와 exact runbook ID를 반환한다. `rollover_mode=RECOVERY`는 재사용되지 않는다.

# Normal initialization recovery

Normal preview가 반환한 exact pair `2026-08-24`→`2026-08-25`를 `init_state_file_for_context()`에 전달하면 `CREATED`가 반환된다. 생성 직후 새 state는 ordinary `ACTIVE_INCOMPLETE`이므로 그 다음 추가 initialization은 다시 active guard로 BLOCK된다.

# Arbitrary initialization guard

Consumed sidecar가 존재해도 다음 임의 context는 `recovery_target_mismatch`로 BLOCK된다.

- `2026-08-24`→`2026-08-26`
- `2026-08-25`→`2026-08-26`
- `2026-08-30`→`2026-08-31`

기존 recovery pair를 다시 요청하면 기존 target가 `EXISTING`으로 반환될 뿐 재생성·overwrite되지 않는다.

# Calendar consistency

Initialization guard의 모든 `classify_state()` 호출에 caller가 제공한 `calendar`를 전달한다. Consumed branch의 normal preview에도 같은 객체를 전달한다. 별도 날짜 계산이나 calendar abstraction은 추가하지 않았다. 테스트는 guard 내부에서 default calendar 재로딩이 발생하면 실패하도록 구성했다.

# Recovery sidecar immutability

`runbook_recovery.v1` schema, create-only authorization, `RECOVERY_EXCLUDED` 의미와 storage는 변경하지 않았다. Full lifecycle 전후 sidecar bytes가 동일함을 테스트했다. Sidecar는 completion, retirement, baseline 또는 source state 대체물이 아니다.

# Source incident protection

실제 source `paper_pilot_202606_2026-08-13_2026-08-14`는 수정하지 않았다. 최종 SHA-256은 `22799cb39561210183333fe0b0ae49299aa184709abc96a4dd983b25218b8bcb`로 CONTRACT1과 동일하다. Actual sidecar와 target state는 모두 존재하지 않는다.

# Tests

실제로 실행한 테스트:

- Recovery targeted: 27 passed.
- 핵심 full lifecycle 단일 테스트: 1 passed.
- Recovery/rollover/prep/state/retirement: 193 passed.
- Stage A AS-OF: 29 passed, 기존 dependency deprecation warning 1건.
- MFU-EO2/Stage B: 146 passed.
- Completion/Stage F: 117 passed.
- Stage runner integration: 30 passed.

# Regression results

CONTRACT1 immutable sidecar, duplicate/malformed/hash/calendar/ledger/target conflict fail-closed, exact recovery target, prep consumption과 active guard 회귀가 모두 PASS했다. Normal rollover, legacy/retirement/completion, Stage A AS-OF, MFU-EO2, Stage B 및 Stage F semantics에는 production 변경이 없고 관련 suite가 모두 PASS했다. `py_compile`과 `git diff --check`도 PASS했다.

# Actual operational state protection

실제 `D:\n8n\workspace\stock_screener_ops`에서는 recovery `status`와 SHA/existence 조회만 실행했다. `authorize`, prepare wrapper, Stage A~F, Notion, EOD, broker, ledger/DB write는 실행하지 않았다.

- source SHA-256: `22799cb39561210183333fe0b0ae49299aa184709abc96a4dd983b25218b8bcb`
- ledger SHA-256: `2b6309ce21e3475b69e874cbf92413451ed703f5016f953688304320b3324f00`
- actual recovery sidecar: 없음
- actual recovery target state: 없음

# Risks / limitations

- Target standard completion은 실제 completion evidence가 모두 유효해야 한다. Recovery가 이를 우회하지 않는다.
- Target-completed routing test는 CONTRACT1과 동일하게 target standard classification을 격리해 검증하며, 실제 completion evidence semantics는 별도 117개 completion/Stage F 회귀로 검증했다.
- No-sidecar 기존 workflow는 그대로 유지되어 CONTRACT1A의 exact consumed-recovery guard 대상이 아니다.
- 기존 worktree의 다수 dirty/untracked 변경과 보호 DB 변경은 범위 밖이며 보존했다.

# Decisions Needed

구현에 필요한 추가 결정은 없다. 실제 recovery authorize와 운영 재시작은 여전히 별도 operator 승인 대상이다.

# Suggested next step

Result와 Review Evidence를 검토한다. 실제 운영 recovery를 승인할 경우 CONTRACT1 Result의 exact operator procedure를 따르되 실행 직전 status/preview, source/ledger hash, data readiness를 다시 확인한다.

# Review Evidence path

`docs/work_results/PAPER-OPS-RUNBOOK-RECOVERY-CONTRACT1A_Review_Evidence.md`

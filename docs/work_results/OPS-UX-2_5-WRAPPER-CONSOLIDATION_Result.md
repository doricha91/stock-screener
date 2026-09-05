# Summary

정상 Paper Runbook 운영 surface를 `ops/runbook_wrappers/daily/` 아래 정확히 5개 wrapper로 정리했다. Primary 02~04는 기존 Gate/Stage Python entrypoint를 호출하는 상태 기반 오케스트레이터를 사용하며, 각 단계가 PASS일 때만 다음 단계로 진행한다. 기존 00~10 detailed wrapper는 삭제하거나 의미를 바꾸지 않고 manual recovery/debug surface로 보존했다.

# Before / After operator flow

- Before: 운영자가 `ops/runbook_wrappers/00`부터 `10`까지 세부 wrapper와 인간 입력 경계를 함께 추적해야 했다.
- After: 정상 운영자는 primary 00 → 01 → 02 → 03 → 04만 사용한다. detailed 00~10은 장애 진단과 부분 복구 때만 사용한다.

# Five primary wrappers

| Primary | 역할 | 정상 정지 지점 |
| --- | --- | --- |
| `daily/00_prepare_next_runbook_day.cmd` | 기존 prepare를 그대로 호출 | 동결 날짜 확인 전 |
| `daily/01_stage_a_plan_prep.cmd` | 기존 Stage A를 그대로 호출 | Execution 입력 필요 여부 확인 전 |
| `daily/02_execution_to_review_prep.cmd` | Gate1 → B → B Verify → C | Manual Review 입력 전 |
| `daily/03_review_preview.cmd` | Gate2 → D Preview | 실제 D append 전 preview 검토 |
| `daily/04_close_day.cmd` | D Append → E → F | Runbook day 완료 |

# Human intervention boundaries

- Primary 00은 Stage A를 자동 실행하지 않는다.
- Primary 01은 Primary 02를 자동 실행하지 않는다. EXECUTION일 때만 Manual Execution 입력이 필요하다.
- Primary 02는 Stage C 이후 Manual Review 입력 앞에서 멈춘다.
- Primary 03은 preview 산출물 생성 후 멈추며 D append를 실행하지 않는다.
- Primary 04만 검토된 preview 이후 D append/E/F를 실행한다.

# Resume behavior

- Gate1, B, Verify, C, Gate2, D Preview, D, E, F 중 실패한 단계에서 즉시 중단하고 downstream 호출을 하지 않는다.
- state에서 B가 PASS이면 Primary 02 재시도 시 execution commit을 다시 호출하지 않고 Verify/C부터 진행한다.
- D가 PASS이면 Primary 04 재시도 시 D append를 건너뛰고 E/F를 진행한다.
- E가 PASS이면 F-only repair/resume로 진행한다.
- D/E/F 완료 상태에서는 D와 E를 반복하지 않고 기존 Stage F idempotency/evidence 검사를 다시 사용한다.
- 결과 JSON과 operator summary에 `stopped_at`, 각 stage 결과, recovery command, next action을 제공한다.

# Manual recovery behavior

기존 detailed wrapper는 모두 유지된다. Gate1, Stage B, Stage B Verify, Stage C, Gate2, D Preview, D Append, E/F를 각각 standalone으로 실행할 수 있다. Primary 결과의 recovery command가 해당 detailed wrapper를 가리킨다.

# NO_ACTION behavior

Primary 흐름은 action mode를 새로 판정하거나 EXECUTION으로 강제하지 않는다. 기존 Gate1 및 Stage B/C/D/E/F runner가 NO_ACTION 계약을 그대로 처리한다. 격리된 연속 lifecycle 테스트에서 Primary 02→03→04가 NO_ACTION fixture로 F PASS 및 `STANDARD_COMPLETED` 분류까지 도달했다.

# V1/V2 behavior

- V1과 V2 모두 기존 통합 Gate1 entrypoint에 위임한다.
- V2 EXECUTION의 Finalize → Gate1, already-finalized safe no-op 의미를 변경하지 않았다.
- state의 Gate1/B/C가 이미 PASS인 retry에서는 해당 write를 다시 호출하지 않는다.
- 기존 Gate1 회귀 31건이 통과했다.

# Changed files

- `scripts/runbook_primary_flow.py`: Primary 02~04 상태 기반 fail-fast orchestration과 operator summary.
- `ops/runbook_wrappers/daily/00_prepare_next_runbook_day.cmd` ~ `04_close_day.cmd`: 정확히 5개의 정상 운영 facade.
- `ops/runbook_wrappers/_env.cmd`, `ops/runbook_wrappers/00_prepare_next_runbook_day.cmd`: primary에서 호출될 때만 nested pause 억제.
- `tests/test_runbook_primary_flow.py`: primary, retry, fail-fast, 전체 EXECUTION/NO_ACTION lifecycle 29건.
- `docs/operations/paper_daily_cycle_commands.md`: 5-wrapper Quick Start와 Advanced / Manual Recovery 구분.
- 이 Result 및 Review Evidence 문서.

작업 전부터 존재한 OPS-UX-1/recovery 변경과 DB·임시 산출물은 되돌리거나 수정하지 않았다. `outputs/backtest_log.db`도 이 작업에서 접근하거나 수정하지 않았다.

# Tests run

서로 다른 선택 대상 기준 총 530개 pytest가 PASS했고, 마지막 수정 후 primary/wrapper 32건도 재실행해 PASS했다. 상세 명령과 결과는 Review Evidence에 기록했다.

- Primary flow: 29 passed
- Required wrapper/gate/recovery/rollover: 159 passed
- Stage B verifier/recovery 및 Stage runner 직접 영향: 342 passed
- 최종 primary/wrapper 재검증: 32 passed, pytest cache 쓰기 권한 warning 1건
- `python scripts/runbook_primary_flow.py --help`: PASS (wrapper와 같은 direct-script import 경로 확인)
- `python -m py_compile scripts/runbook_primary_flow.py`: PASS
- `git diff --check`: PASS (기존 파일의 CRLF 전환 경고와 접근 불가 임시 디렉터리 경고만 출력)
- `git status --short`: 실행 및 기록 완료

# Tests not run and why

- 전체 repository pytest suite: 작업지시문이 요구한 suite와 직접 영향 suite 530건을 실행했으며, 대규모 dirty worktree의 무관한 영역까지 포함하는 전체 suite는 범위와 시간상 실행하지 않았다.
- 실제 운영 `.cmd` smoke: 실제 paper operation 및 `D:\n8n\workspace\stock_screener_ops` 쓰기가 금지되어 정적 wrapper 계약과 격리된 pytest로 검증했다.

# Risks and limitations

- `.cmd`의 실제 conda/Notion 환경 연동은 운영 workspace를 사용하지 않았으므로 이번 테스트에서 실행 검증하지 않았다.
- Primary 오케스트레이터는 기존 state/evidence 정확성에 의존한다. evidence가 손상되면 기존 runner와 동일하게 fail-closed 또는 detailed recovery가 필요하다.
- worktree에는 본 작업 전부터 많은 수정·untracked 임시 파일과 일부 접근 불가 테스트 디렉터리가 있다. 본 작업은 이를 정리하지 않았다.

# Structural blockers

없음. 현재 repository의 기존 Gate/Stage entrypoint와 state/evidence 계약으로 안전한 5-wrapper facade를 구성할 수 있었다.

# AGENTS.md compliance

- root `AGENTS.md`를 먼저 읽고 적용했다.
- DB/schema/전략/시장 캘린더/Recovery 정책/Notion schema를 변경하지 않았다.
- protected DB와 실제 운영 workspace에 쓰지 않았다.
- 기존 dirty 변경을 보존했고 reset/checkout/clean/stash/commit/push를 실행하지 않았다.
- 실제 실행 테스트와 미실행 테스트를 구분해 기록했다.

# Suggested next step

Result와 Review Evidence를 먼저 검토한 뒤, 실제 운영에서는 다음 정상 Runbook에서 5-primary-wrapper flow를 단계별로 검증한다.

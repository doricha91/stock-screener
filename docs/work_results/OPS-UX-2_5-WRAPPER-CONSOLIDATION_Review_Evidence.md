# Summary

OPS-UX-2의 5-wrapper daily facade, 상태 기반 orchestration, 인간 개입 경계, 부분 실패 재시도, 기존 detailed recovery 보존을 코드·정적 wrapper 계약·격리 lifecycle 테스트로 검토했다. 기준 branch는 `gemini_cli_update`, 작업 시작 HEAD는 `e17978f332a8853588f287cf5aa2a5ef9bd57c74`였다.

# Before / After operator flow

```text
Before (normal operator surface)
00 -> 01 -> 02 -> 03 -> 04 -> 05 -> 06 -> 07 -> 08 -> 09 -> 10

After (normal operator surface)
Primary 00 -> [date check]
Primary 01 -> [Execution input only if required]
Primary 02 -> [Manual Review input]
Primary 03 -> [Preview review]
Primary 04 -> STANDARD_COMPLETED
```

# Five primary wrappers

`ops/runbook_wrappers/daily/`의 `.cmd` 목록을 테스트에서 정확히 아래 5개로 고정했다.

1. `00_prepare_next_runbook_day.cmd`
2. `01_stage_a_plan_prep.cmd`
3. `02_execution_to_review_prep.cmd`
4. `03_review_preview.cmd`
5. `04_close_day.cmd`

Primary 00/01은 기존 wrapper를 직접 호출한다. Primary 02~04는 `scripts/runbook_primary_flow.py`를 통해 기존 Gate checker, Stage B verifier, Stage runner 함수에 위임한다. 비즈니스 로직, evidence schema, stage semantics를 복제하거나 변경하지 않았다.

# Human intervention boundaries

| 완료된 primary | 자동 실행된 범위 | 반드시 사람이 확인/입력할 경계 | 자동 실행하지 않는 것 |
| --- | --- | --- | --- |
| 00 | next Runbook prepare | frozen account/date/runbook id 확인 | Stage A |
| 01 | Stage A | EXECUTION이면 Manual Execution; NO_ACTION이면 생략 | Gate1/Primary 02 |
| 02 | Gate1, B, B Verify, C | Manual Review 입력 | Gate2/Primary 03 |
| 03 | Gate2, D Preview | preview artifact 검토 | D Append/Primary 04 |
| 04 | D Append, E, F | 완료 결과 확인 | 다음 Runbook prepare |

# Resume behavior

| 시작 상태/실패 | 재실행 동작 | 중복 방지/정지 evidence |
| --- | --- | --- |
| Gate1 WAIT/BLOCKED | GATE1에서 종료 | B/Verify/C 미호출 |
| B FAILED | B에서 종료 | Verify/C 미호출 |
| B PASS, Verify FAILED | retry 시 B skip 후 Verify | execution commit 중복 미호출 |
| C FAILED | C에서 종료 | Gate2 미호출 |
| Gate2 BLOCKED | Gate2에서 종료 | Preview/D Append 미호출 |
| Preview FAILED | Preview에서 종료 | D Append 미호출 |
| D FAILED | D에서 종료 | E/F 미호출 |
| D PASS, E FAILED | retry 시 D skip 후 E | D append 중복 미호출 |
| E PASS, F FAILED | retry 시 D/E skip 후 F | F-only repair semantics |
| F PASS complete rerun | D/E skip, F의 기존 검증 호출 | destructive D/E write 미호출 |

각 실패 결과는 `no_downstream_stage_executed=true`와 해당 detailed recovery command를 반환한다.

# Manual recovery behavior

| Detailed wrapper | Primary mapping | Standalone recovery 역할 |
| --- | --- | --- |
| `00_prepare_next_runbook_day.cmd` | Primary 00 | prepare 재시도 |
| `01_stage_a_plan_prep.cmd` | Primary 01 | Stage A 재시도 |
| `02_gate1_execution_input.cmd` | Primary 02 | integrated Finalize/Gate1 |
| `03_stage_b_execution_commit_sync.cmd` | Primary 02 | Stage B commit/sync |
| `04_stage_b_verify.cmd` | Primary 02 | Stage B evidence verify |
| `05_stage_c_review_prep.cmd` | Primary 02 | Stage C review prep |
| `06_gate2_review_input.cmd` | Primary 03 | Gate2 |
| `07_stage_d_preview.cmd` | Primary 03 | D preview |
| `08_stage_d_append_sync.cmd` | Primary 04 | D append/sync |
| `09_stage_e_eod_close.cmd` | Primary 04 | E 후 정상 F 연결 |
| `10_stage_f_benchmark_notion_sync.cmd` | Primary 04 | F-only repair |

정적 테스트는 위 standalone 파일이 모두 존재하고 기존 wrapper 회귀가 통과하는지 확인했다.

# NO_ACTION behavior

- Primary는 action mode를 변환하지 않는다.
- Primary 01 안내는 Manual Execution을 “필요한 경우에만” 요구한다.
- Primary 02는 NO_ACTION에서도 동일한 기존 Gate/Stage entrypoint를 사용한다.
- `test_primary_02_preserves_action_mode_path[NO_ACTION]` PASS.
- `test_continuous_primary_lifecycle_reaches_standard_completed[NO_ACTION]` PASS.
- Stage D NO_ACTION 및 Stage E NO_ACTION 관련 기존 suite가 모두 PASS했다.

# V1/V2 behavior

- `test_primary_02_delegates_v1_and_v2_gate_semantics`가 V1과 finalized V2 모두 integrated Gate1 entrypoint를 호출함을 검증했다.
- `test_primary_02_already_finalized_retry_skips_gate_and_commit`가 GATE1/B/C PASS retry에서 Gate/commit 재호출이 없음을 검증했다.
- 기존 `tests/test_runbook_gate_checker.py` 31건이 V1 legacy, V2 Finalize/Gate1, already-finalized 및 NO_ACTION 의미를 회귀 검증했다.
- execution contract version, evidence schema, persisted state schema를 변경하지 않았다.

# Changed files

| 파일 | 변경 근거 |
| --- | --- |
| `scripts/runbook_primary_flow.py` | Primary 02~04 orchestration |
| `ops/runbook_wrappers/daily/*.cmd` | 5-command daily facade |
| `ops/runbook_wrappers/_env.cmd` | chained call에서만 pause 억제 |
| `ops/runbook_wrappers/00_prepare_next_runbook_day.cmd` | primary 00 chained call에서만 pause 억제 |
| `tests/test_runbook_primary_flow.py` | 29개 acceptance/lifecycle 회귀 |
| `docs/operations/paper_daily_cycle_commands.md` | primary Quick Start / advanced recovery 분리 |
| Result / Review Evidence | 완료 보고 번들 |

Pre-existing dirty 파일인 `core/runbook_day_rollover.py`, `core/runbook_recovery.py`, OPS-UX-1 Gate1 관련 파일, recovery 문서/테스트, `outputs/backtest_log.db`, 기타 untracked 파일은 본 작업의 변경 대상으로 삼지 않았다.

# Tests run

| 명령 | 결과 |
| --- | --- |
| `python -m pytest tests/test_runbook_primary_flow.py -q` | 최종 재실행 29 passed in 1.85s |
| `python -m pytest tests/test_runbook_stage_wrappers.py -q` | 3 passed in 0.20s |
| `python -m pytest tests/test_runbook_gate_checker.py -q` | 31 passed in 5.96s |
| `python -m pytest tests/test_runbook_recovery.py -q` | 37 passed in 33.50s |
| `python -m pytest tests/test_runbook_day_rollover.py -q` | 88 passed in 22.44s |
| `python -m pytest tests/test_runbook_stage_b_verifier.py tests/test_runbook_stage_b_recovery.py -q` | 60 passed in 13.56s |
| `python -m pytest tests/test_runbook_stage_runner.py tests/test_runbook_stage_runner_gate2.py tests/test_runbook_stage_runner_review_prep.py tests/test_runbook_stage_runner_stage_b.py -q` | 92 passed in 22.13s |
| `python -m pytest tests/test_runbook_stage_runner_stage_d_preview.py tests/test_runbook_stage_runner_stage_d_append.py tests/test_runbook_stage_runner_stage_d_no_action.py -q` | 49 passed in 14.24s |
| `python -m pytest tests/test_runbook_stage_runner_stage_e.py tests/test_runbook_stage_runner_stage_f.py tests/test_runbook_stage_e_no_action_contract.py tests/test_runbook_stage_e_evidence.py -q` | 141 passed in 24.66s |
| `python -m pytest tests/test_runbook_primary_flow.py tests/test_runbook_stage_wrappers.py -q` | 최종 수정 후 32 passed in 1.90s; `.pytest_cache` 쓰기 권한 warning 1건 |
| `python scripts/runbook_primary_flow.py --help` | PASS; direct-script import 및 CLI contract 확인 |
| `python -m py_compile scripts/runbook_primary_flow.py` | PASS |
| `git diff --check` | PASS; CRLF 및 접근 불가 pre-existing temp directory warning만 존재 |
| `git status --short` | 실행 완료; dirty baseline과 본 작업 파일이 함께 표시됨 |

서로 다른 선택 대상 기준 Pytest 합계: 530 passed, 0 failed. 마지막 수정 후 primary/wrapper 32건을 중복 재검증했다.

# Tests not run and why

- 전체 repository pytest suite는 실행하지 않았다. 지정된 필수 suite와 직접 영향 Stage B/D/E/F suite 530건을 실행했고, worktree에 무관한 대규모 기존 변경이 있어 범위를 확대하지 않았다.
- 실제 `D:\n8n\workspace\stock_screener_ops`를 사용하는 `.cmd` lifecycle smoke는 실행하지 않았다. 작업지시문의 실제 paper operation/운영 workspace 쓰기 금지를 지켰다.
- 실제 Notion write simulation과 broker/live 주문은 실행하지 않았다.

# Risks and limitations

- Windows `.cmd`의 실환경 conda activation, account local configuration, Notion credential 동작은 정적 계약만 확인했다.
- state/evidence 자체가 불완전하거나 손상된 경우 primary는 자동 보정하지 않고 fail-closed/recovery 안내에 의존한다.
- `git status`에는 작업 전부터 존재한 protected DB 변경과 많은 untracked/접근 불가 temp directory가 남아 있다. 삭제 승인 범위가 아니므로 보존했다.

# Structural blockers

없음.

# AGENTS.md compliance

- root AGENTS.md와 작업지시문 전체를 작업 기준으로 적용했다.
- 현재 branch/HEAD와 dirty baseline을 편집 전 확인했다.
- 기존 OPS-UX-1 및 recovery lifecycle 변경을 덮어쓰지 않았다.
- DB schema, market/strategy logic, recovery policy, calendar, Notion schema, live trading을 변경하지 않았다.
- 파일 삭제·이동, reset, checkout, clean, stash, commit, push를 수행하지 않았다.
- 테스트는 tmp/격리 객체를 사용했고 실제 운영 workspace를 건드리지 않았다.

# Suggested next step

Result와 Review Evidence를 먼저 검토한 뒤, 실제 운영에서는 다음 정상 Runbook에서 5-primary-wrapper flow를 단계별로 검증한다.

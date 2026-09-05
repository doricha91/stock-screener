# Summary

OPS-UX-2.1은 하위 lifecycle이 아니라 Primary presentation의 결함이었다. Stage C와 Stage D Preview는 이미 올바른 canonical 결과를 생성하고 있었으나 Primary가 이를 버리고 고정 문자열을 출력했다. 수정 후 structured JSON과 terminal summary는 동일한 `next_required_action`을 공유한다.

# Baseline

- Branch: `gemini_cli_update`
- HEAD: `e17978f332a8853588f287cf5aa2a5ef9bd57c74`
- Task file: `D:\python\StockScreener\docs_chatGPT_work\Ops-Ux2.1_no action operator guidance alignmend.md`
- Root `AGENTS.md`: 작업 전 전체 확인
- 기존 dirty/untracked 작업: 보존

# Root cause

| Primary | Canonical 하위 결과 | 기존 결함 |
| --- | --- | --- |
| 02 | Stage C가 EXECUTION/NO_ACTION/verified-zero-write에 맞는 `next_required_action` 생성 | 항상 `Fill Manual Review in Notion` 출력 |
| 02 retry | state에 `stage_c_summary_json` pinned | C PASS만 보고 고정 Manual Review 문구 출력 |
| 03 | Stage D Preview가 `review_preview_skipped`, null/non-null artifact, canonical next action 생성 | 항상 preview artifact 검토 요청 |

# SSOT selection

## Primary 02

1. 이번 실행에서 Stage C를 수행했다면 `run_stage_c()` 반환값의 `next_required_action`을 사용한다.
2. C가 이미 PASS라면 기존 evidence loader `load_stage_c_summary_evidence()`로 pinned `stage_c_summary_json`을 검증하고 `summary.next_required_action`을 사용한다.
3. Primary는 canonical action을 `primary 03` surface에 맞는 문장으로만 변환한다.

사용하지 않은 pseudo-rule:

- candidate count 단독 판정
- execution count 단독 판정
- action mode 단독 판정
- Account Review 질문 재생성

## Primary 03

Stage D Preview 반환값의 다음 authoritative output을 사용한다.

- `review_preview_skipped`
- `review_preview_json`
- `review_preview_md`

명시적 skip 또는 두 artifact가 모두 없으면 검토할 artifact가 없다고 안내한다. 실제 artifact가 있으면 기존 검토 안내를 유지한다.

# Guidance matrix

| Case | Structured `next_required_action` | Terminal `STOP:` | 결과 |
| --- | --- | --- | --- |
| EXECUTION + Manual Review scope | Fill Manual Review, then primary 03 | 동일 | PASS |
| NO_ACTION Primary 02 | No Manual Review input required, then primary 03 | 동일 | PASS |
| EXECUTION + verified-zero-write + scope 0 | No Manual Review input required, then primary 03 | 동일 | PASS |
| EXECUTION + preview artifact | Review preview artifact, then primary 04 | 동일 | PASS |
| NO_ACTION + preview skipped | No review preview required, then primary 04 | 동일 | PASS |
| Gate1 BLOCKED | recovery/repair 안내 | `STOPPED_AT` + Recovery, PASS STOP 없음 | exit 2 |

# Preserved contracts

다음 파일/계약은 수정하지 않았다.

- `core.paper_daily_review_scope`
- Stage C scope/account question 정책
- Gate 2 semantics
- Stage D NO_ACTION skip 구현
- Stage B verification
- Recovery lifecycle/sidecar
- runbook state/evidence/execution schema
- Account Review 질문 정의

NO_ACTION의 Position/Execution/Account Review count 0 정책도 그대로다.

# Test evidence

## Primary acceptance

`python -m pytest tests/test_runbook_primary_flow.py -q`

- 초기 수정 후: 33 passed in 3.42s
- canonical suite 병렬 확인: 33 passed in 3.19s
- CLI stdout capture 추가 후 최종 재실행: 38 passed in 1.95s

포함 evidence:

- EXECUTION Manual Review structured/terminal 문구
- NO_ACTION Manual Review 불필요 structured/terminal 문구
- verified-zero-write empty scope 문구
- preview artifact required 문구
- NO_ACTION preview skipped/null artifact 문구
- BLOCKED recovery 출력과 exit code 2
- PASS 안내와 failure 안내의 비혼합

## Canonical Stage regression

| 명령 | 결과 |
| --- | --- |
| `python -m pytest tests/test_runbook_stage_runner_review_prep.py -q` | 25 passed in 7.55s |
| `python -m pytest tests/test_runbook_stage_runner_stage_d_preview.py -q` | 7 passed in 3.74s |
| `python -m pytest tests/test_runbook_stage_runner_stage_d_no_action.py -q` | 34 passed in 12.10s |
| `python -m pytest tests/test_mfu_eo2_zerocount_standard_downstream.py -q` | 13 passed in 7.38s |
| `python -m pytest tests/test_runbook_stage_wrappers.py -q` | 3 passed in 0.39s |
| `python -m pytest tests/test_runbook_gate_checker.py -q` | 31 passed in 5.21s |
| `python -m pytest tests/test_runbook_stage_runner_gate2.py -q` | 18 passed in 3.03s |
| `python scripts/runbook_primary_flow.py --help` | PASS |
| `python -m py_compile scripts/runbook_primary_flow.py` | PASS |
| `git diff --check` | PASS; pre-existing CRLF warning만 출력 |
| `git status --short` | 실행 완료; 기존 dirty baseline 및 접근 불가 임시 디렉터리 warning 보존 |

최종 선택 대상 기준: 169 passed, 0 failed.

# Tests not run and why

- 전체 repository suite: presentation-layer 직접 영향 범위 밖이며 dirty worktree의 무관한 작업까지 포함하므로 미실행.
- 실제 운영 wrapper/Notion smoke: 실제 workspace 및 외부 상태 변경 방지를 위해 미실행.
- backtest/optimizer: 전략·수치 변경 없음.

# Changed files

- `scripts/runbook_primary_flow.py`
- `tests/test_runbook_primary_flow.py`
- `docs/operations/paper_daily_cycle_commands.md`
- `docs/work_results/OPS-UX-2_1-NO-ACTION-GUIDANCE_Result.md`
- `docs/work_results/OPS-UX-2_1-NO-ACTION-GUIDANCE_Review_Evidence.md`

# Risks and limitations

- Stage C의 canonical semantic signal은 현재 문자열 `next_required_action`이다. 새 canonical wording이 추가되면 Primary presentation mapping도 함께 검토해야 한다.
- actual `.cmd`/Notion credential 연결은 이번 isolated test에서 검증하지 않았다.
- pre-existing protected DB 및 접근 불가 임시 디렉터리 warning은 본 작업 범위 밖이라 보존했다.

# Structural blockers

없음. 기존 Stage 결과만으로 Primary guidance를 정렬할 수 있었다.

# AGENTS.md compliance

- DB/schema/data migration 없음.
- Core/strategy/backtest/market calendar/Recovery 변경 없음.
- protected DB 및 실제 운영 workspace 쓰기 없음.
- reset/checkout/restore/clean/stash/commit/push 없음.
- 기존 dirty/untracked 변경 보존.
- 실제 실행 테스트와 미실행 테스트 분리 기록.

# Suggested next step

Result와 Review Evidence를 먼저 검토한 뒤, 다음 정상 Runbook의 NO_ACTION 및 EXECUTION 각 1회에서 Primary 02/03의 JSON과 terminal `STOP:` 문구가 실제 operator flow와 일치하는지 단계별로 확인한다.

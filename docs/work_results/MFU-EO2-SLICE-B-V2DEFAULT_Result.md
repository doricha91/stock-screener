# MFU-EO2-SLICE-B-V2DEFAULT Result

## Summary

- 판정: PASS
- 새로 생성되는 runbook state의 execution contract 기본값을 `execution_reconciliation_preview.v1`에서 `execution_reconciliation_preview.v2`로 변경했다.
- 기존 explicit v1, execution contract가 없는 legacy state, 진행/완료된 v1 state는 자동 migration하지 않는다.
- 신규 v2 state는 별도 activation 없이 Finalize할 수 있고, `activate-execution-v2` 호출은 exact no-op이다.

## Baseline

- Repository: `D:\python\StockScreener`
- Branch: `gemini_cli_update`
- Start HEAD: `7945ea854faf025db8fd0710e24f5209a32e9f9b`
- Start status: `git status --short --untracked-files=all` 3,002 lines
- 기존 dirty/untracked baseline, protected DB, Slice A/B source와 기존 Result/Evidence/Addendum를 보존했다.
- git add/commit/push/reset/checkout/clean/stash는 실행하지 않았다.

## Current code findings

- `create_initial_state()`만 신규 state에 쓸 contract 기본값을 결정한다.
- `init_state_file()`과 `init_state_file_for_context()`는 경로가 없을 때만 신규 state를 저장하고, 경로가 있으면 persisted state를 그대로 load한다.
- `_state_from_dict()`는 저장된 `execution_contract`를 변경하지 않는다.
- `get_execution_contract()`는 contract가 없는 legacy state를 계속 effective v1으로 해석한다.
- `paper_daily_ops.py`의 expected state는 frozen context만 비교하므로 constructor contract 기본값 변경의 영향을 받지 않는다.
- Gate/Preview의 state-missing fallback은 신규 state 의미이므로 v2가 되며, persisted state가 있으면 항상 저장된 contract version을 사용한다.

## Changed files

- `scripts/runbook_state.py`
  - 신규 state constructor의 execution contract version을 V2로 변경.
- `tests/test_runbook_state.py`
  - 신규 기본 v2, canonical persisted v2, activation 없는 Finalize, activation no-op, explicit v1 및 missing-contract legacy 보존 회귀 추가.
- `tests/test_execution_outcome_flow.py`
  - 진행/완료 v1 activation guard fixture를 explicit v1으로 고정.
- `tests/test_runbook_execution_reconciliation_preview.py`
  - state-missing 신규 Preview의 v2 기대값 반영 및 persisted explicit-v1 dispatch 회귀 추가.
- `tests/test_runbook_gate_checker.py`
  - 기존 Gate 회귀 fixture를 explicit v1으로 고정하고 신규 v2의 Finalize 전 WAIT 회귀 추가.
- `tests/test_runbook_stage_b_verifier.py`
  - 기존 v1 commit/sync report fixture를 explicit v1으로 고정.
- `docs/work_results/MFU-EO2-SLICE-B-V2DEFAULT_Result.md`
- `docs/work_results/MFU-EO2-SLICE-B-V2DEFAULT_Review_Evidence.md`

## Exact behavior change

신규 state:

```json
{
  "execution_contract": {
    "version": "execution_reconciliation_preview.v2",
    "input_finalized": false,
    "finalized_at": null
  }
}
```

- `finalize_execution_input(new_state)`가 activation 없이 성공한다.
- `activate_execution_outcome_v2(new_state) is new_state`가 유지된다.
- 신규 v2 Gate1은 execution input Finalize 전 WAIT한다.
- 신규 v2 Preview는 v2 outcome contract로 dispatch한다.

변하지 않은 동작:

- persisted explicit v1은 v1 dispatch를 유지한다.
- missing-contract legacy state는 effective v1을 유지한다.
- 기존 v2는 v2를 유지한다.
- progressed/completed v1의 explicit late activation guard는 유지된다.
- Commit, importer, outcome derivation, Gate 정책, activation guard, DB/schema는 변경하지 않았다.

## Legacy preservation evidence

- explicit v1 state를 저장한 뒤 `init_state_file_for_context()`로 다시 열면 `EXISTING`과 effective v1을 반환하는 테스트가 통과했다.
- `execution_contract` field를 제거한 legacy payload를 load하면 in-memory contract는 빈 dict이고 `get_execution_contract()`는 v1을 반환하는 테스트가 통과했다.
- persisted explicit-v1 Preview가 `execution_reconciliation_preview.v1`을 생성하는 테스트가 통과했다.
- 기존 v1 Gate 및 Stage B verifier fixture는 explicit v1으로 고정돼 기존 동작을 계속 검증한다.
- completed v1의 activation은 기존 immutable guard로 계속 차단된다.

## Tests run

1. `python -m pytest -q tests\test_runbook_state.py`
   - 38 passed in 16.04s
2. `python -m pytest -q tests\test_execution_outcome_flow.py`
   - 25 passed in 12.85s
3. `python -m pytest -q tests\test_runbook_execution_reconciliation_preview.py`
   - 최초 1 failed, 2 passed: 신규 state의 expected schema가 v1로 고정된 테스트를 확인.
   - 수정 후 4 passed in 12.22s
4. `python -m pytest -q tests\test_runbook_gate_checker.py`
   - 최초 3 failed, 16 passed: 기존 v1 helper가 constructor의 암묵적 v1에 의존함을 확인.
   - 수정 후 20 passed in 26.36s
5. `python -m pytest -q tests\test_runbook_stage_runner.py tests\test_runbook_stage_runner_stage_b.py`
   - 47 passed in 78.56s
6. `python -m pytest -q tests\test_paper_manual_execution_commit.py`
   - 13 passed in 14.24s
7. `python -m pytest -q tests\test_runbook_stage_b_verifier.py`
   - 확장 묶음에서 4건 실패 원인을 explicit-v1 fixture로 수정 후 26 passed in 14.15s
8. Slice A/B 확장 관련 묶음
   - 255 passed in 59.65s
9. `python -m py_compile scripts\runbook_state.py tests\test_runbook_state.py tests\test_execution_outcome_flow.py tests\test_runbook_execution_reconciliation_preview.py tests\test_runbook_gate_checker.py tests\test_runbook_stage_b_verifier.py`
   - exit 0, no output
10. `git diff --check`
    - exit 0, whitespace error 없음; 기존 line-ending warning만 출력

## Tests not run and why

- 전체 repository suite: 작업지시문상 필수가 아니며, 변경 영향 범위를 포함하는 기존 249-test 기준 묶음을 255-test로 확장해 통과했다.
- 실제 Notion/Paper account write 및 live broker: 범위 밖이며 안전 규칙상 실행하지 않았다.
- backtest entrypoint: 전략·신호·수익률 계산 변경이 아니므로 관련이 없다.

## Diff self-review

- production 동작 변경은 constructor의 V1→V2 한 줄뿐이다.
- 나머지 변경은 신규 기본값 또는 기존 v1 의미를 명시하는 회귀 테스트다.
- v1/v2 dispatch, contract 이름, Finalize state machine, Commit, importer, Gate 구현, DB/schema, activation guard, legacy fallback을 재설계하지 않았다.
- 기존 Slice A/B Result/Evidence/Addendum SHA-256은 작업 시작 시 기록값과 동일하다.

## Risks/limitations

- worktree에는 이번 작업 이전부터 많은 dirty/untracked 파일이 있어 현재 diff는 여러 Slice의 누적 변경을 포함한다.
- 신규 v2 runbook은 의도적으로 Finalize 전 Gate1에서 WAIT한다. 운영 순서는 execution input 입력 후 Finalize, Preview/Commit이다.
- 이번 작업은 기존 persisted state migration을 수행하지 않는다.

## Decisions Needed

- 없음.

## Suggested next step

- Review Evidence의 full diff와 untracked test 전문으로 변경 범위를 검토한 뒤, 별도 승인된 git 작업에서 관련 파일만 선별한다.

## Review Evidence path

`docs/work_results/MFU-EO2-SLICE-B-V2DEFAULT_Review_Evidence.md`

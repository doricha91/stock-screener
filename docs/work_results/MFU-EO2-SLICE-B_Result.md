# MFU-EO2-SLICE-B Result

## Summary

MFU-EO2 Slice A의 `derive_execution_outcomes()`를 Notion execution input, runbook 단위 Finalize, reconciliation preview, Stage B Commit 및 verification 경로에 연결했다. Notion의 빈 수량/가격은 이제 `None`으로 보존되고, 명시적으로 v2를 활성화한 runbook만 `execution_reconciliation_preview.v2` 경로를 사용한다. 기존 v1 runbook과 v1 validator/Commit 경로는 유지된다.

## Baseline and AGENTS.md compliance

- 저장소: `D:\python\StockScreener`
- 기준 branch: `gemini_cli_update` (`main` 미사용)
- 시작/현재 HEAD: `7945ea854faf025db8fd0710e24f5209a32e9f9b`
- 루트 `AGENTS.md` 전체를 읽고 적용했다. 하위 `AGENTS.md`는 없었다.
- 시작 시 tracked dirty baseline인 다음 파일은 수정하지 않았다.
  - `docs/operations/paper_daily_cycle_commands.md`
  - `idea, PRD, TRD/paper 운영 기능 개발 로드맵 v1.3.md`
  - `outputs/backtest_log.db`
- 기존 Slice A/FIX1 변경과 Result/Evidence는 보존했고 덮어쓰지 않았다.
- reset, checkout, clean, stash, git add, commit, push를 실행하지 않았다.
- DB schema/data, live broker, 실제 외부 Notion write를 수행하지 않았다.

## Current Code Findings

- 기존 importer는 Notion number blank를 `quantity=0`, `actual_price=0.0`으로 변환했다.
- 기존 reconciliation preview는 `execution_reconciliation_preview.v1` 단일 dispatch였다.
- runbook state는 additive controller state를 저장할 수 있지만 execution contract/Finalize 필드는 없었다.
- 기존 Commit writer는 commit 직전 execution ledger를 다시 읽어 최신 Paper state를 만들고, 별도의 long-position hard cap validator를 실행한 후에만 write했다.
- 기존 Stage B는 commit count가 0인 execution day와 sync 생략을 허용하지 않았다.

## Changed files

Slice B source:

- `core/execution_outcome_flow.py` (new)
- `core/execution_reconciliation.py` (Slice A 파일에 raw invalid-value 보존 연결만 추가)
- `core/notion_manual_execution_importer.py`
- `core/paper_manual_execution_commit.py`
- `scripts/import_notion_executions.py`
- `scripts/runbook_command_registry.py`
- `scripts/runbook_execution_reconciliation_preview.py`
- `scripts/runbook_gate_checker.py`
- `scripts/runbook_stage_b_verifier.py`
- `scripts/runbook_stage_runner.py`
- `scripts/runbook_state.py`

Slice B tests:

- `tests/test_execution_outcome_flow.py` (new)
- `tests/test_paper_manual_execution_commit.py`
- `tests/test_runbook_stage_runner_stage_b.py`

Required completion bundle:

- `docs/work_results/MFU-EO2-SLICE-B_Result.md` (new)
- `docs/work_results/MFU-EO2-SLICE-B_Review_Evidence.md` (new)

## Behavior changes

- Notion quantity/actual price blank는 `None`으로 보존된다. v1 preview에서는 기존과 같이 invalid input으로 차단하되, 더 이상 blank를 명시적 0으로 위조하지 않는다.
- runbook state에 additive `execution_contract`가 생겼다. 기존/누락 필드는 v1로 해석하며 자동 migration하지 않는다.
- `activate-execution-v2`와 `finalize-execution-input` CLI를 제공한다. Finalize 재실행은 state/timestamp/history를 바꾸지 않는 exact no-op이며 Undo/Reopen은 없다.
- completed/started v1 execution state는 v2로 바꿀 수 없다.
- v2 reconciliation은 Slice A SSOT를 호출한 다음 price pair만 검증한다. 별도의 outcome 계산을 복제하지 않는다.
- Finalize 전 blank/blank는 `WAIT`, Finalize 후 blank/blank는 `NOT_EXECUTED`다.
- qty/price 한쪽만 입력, 명시적 0/음수/비수치/NaN/Inf, 초과 수량은 batch `BLOCKED`다.
- Commit은 pinned v2 outcome의 `EXECUTED`/`PARTIAL` key만 고르고, import preview와 symbol/side/qty/price가 정확히 일치하는지 다시 확인한다.
- trade-bearing Commit은 기존 writer를 그대로 사용하므로 최신 ledger state와 hard cap을 write 직전에 재검증한다.
- all-`NOT_EXECUTED`는 trade/ledger/current-state/account-snapshot/position-snapshot/backup write가 0이다. 감사 가능한 zero-write commit evidence만 생성하고 Notion status sync는 실행하지 않는다.
- v2 zero-write Stage B는 verifier까지 PASS할 수 있다.

## Contract and invariant mapping

- v1: `execution_reconciliation_preview.v1` → 기존 `reconcile_plan_and_executions()` 및 기존 commit validator.
- v2: `execution_reconciliation_preview.v2` → normalized input → Slice A `execution_outcome.v2` derivation → price-pair validation → v2 commit selection.
- unsupported version: preview/commit 모두 `BLOCKED`, persistent domain write 0.
- finalized PASS:
  - `planned_count == executed_count + partial_count + not_executed_count`
- commit:
  - `committed_trade_count == executed_count + partial_count`
- all-NOT_EXECUTED:
  - committed trade IDs 0
  - ledger/cash/position writer 미호출
  - state/snapshot write flags false
- any BLOCKED/stale preview mismatch:
  - selected rows empty
  - writer 진입 전 차단

## Tests run

1. Slice B + Slice A:

```text
python -m pytest -q tests\test_execution_outcome_flow.py tests\test_execution_outcome_derivation.py
48 passed in 2.20s
```

2. v1 reconciliation/importer/Commit/state regression:

```text
python -m pytest -q tests\test_execution_reconciliation.py tests\test_notion_manual_execution_importer.py tests\test_paper_manual_execution_commit.py tests\test_runbook_state.py
87 passed in 4.65s
```

3. runbook preview/Gate/Stage B/registry regression:

```text
python -m pytest -q tests\test_runbook_execution_reconciliation_preview.py tests\test_runbook_gate_checker.py tests\test_runbook_stage_runner_stage_b.py tests\test_runbook_command_registry.py
54 passed in 8.62s
```

4. combined related suite:

```text
python -m pytest -q tests\test_execution_outcome_flow.py tests\test_execution_outcome_derivation.py tests\test_execution_reconciliation.py tests\test_runbook_execution_reconciliation_preview.py tests\test_notion_manual_execution_importer.py tests\test_paper_manual_execution_commit.py tests\test_runbook_state.py tests\test_runbook_gate_checker.py tests\test_runbook_stage_runner.py tests\test_runbook_stage_runner_stage_b.py tests\test_runbook_command_registry.py
217 passed in 17.25s
```

5. final focused writer/Stage B verifier suite after self-review fixes:

```text
python -m pytest -q tests\test_execution_outcome_flow.py tests\test_paper_manual_execution_commit.py tests\test_runbook_stage_runner_stage_b.py tests\test_runbook_stage_b_verifier.py
82 passed in 8.13s
```

6. Syntax:

```text
python -m py_compile core\execution_outcome_flow.py core\execution_reconciliation.py core\notion_manual_execution_importer.py core\paper_manual_execution_commit.py scripts\runbook_state.py scripts\runbook_execution_reconciliation_preview.py scripts\import_notion_executions.py scripts\runbook_gate_checker.py scripts\runbook_stage_b_verifier.py scripts\runbook_stage_runner.py scripts\runbook_command_registry.py
PASS (no output)
```

7. Whitespace:

```text
git diff --check
PASS (errors 없음; 기존 LF→CRLF warning만 출력)
```

8. 최종 관련 suite (self-review 보완 전체 포함):

```text
python -m pytest -q tests\test_execution_outcome_flow.py tests\test_execution_outcome_derivation.py tests\test_execution_reconciliation.py tests\test_runbook_execution_reconciliation_preview.py tests\test_notion_manual_execution_importer.py tests\test_paper_manual_execution_commit.py tests\test_runbook_state.py tests\test_runbook_gate_checker.py tests\test_runbook_stage_runner.py tests\test_runbook_stage_runner_stage_b.py tests\test_runbook_stage_b_verifier.py tests\test_runbook_command_registry.py
249 passed in 22.15s
```

## Tests not run and why

- 전체 repository test suite: Slice B와 무관한 대규모 suite 및 기존 dirty/untracked 환경을 건드리지 않기 위해 실행하지 않았다. 관련 importer/reconciliation/Commit/runbook 217-test 묶음과 추가 verifier 묶음을 실행했다.
- 실제 Notion API write / 실제 paper account write / live broker: 범위 및 금지사항에 따라 실행하지 않았다.
- backtest entrypoint: 전략, 신호, 수익률, 포지션 산식 변경이 아니므로 실행 대상이 아니다.

## Diff self-review

- Stage B zero-write 분기를 처음 잘못된 runner success block에 넣은 것을 diff review에서 발견해 Stage B block으로 이동하고 회귀 테스트를 추가했다.
- zero-write 후 verifier 증거가 없던 문제를 zero-write commit evidence + verifier 분기로 보완했다.
- outcome key만으로 stale import preview를 선택하던 결합 위험을 발견해 qty/price/symbol/side exact binding을 추가했다.
- v1 default/validator/commit behavior는 관련 회귀 테스트에서 유지됐다.
- unrelated baseline files, DB, Slice A Result/Evidence는 수정하지 않았다.

## Risks and limitations

- v2는 자동 활성화되지 않는다. 새 runbook에서 명시적으로 `activate-execution-v2` 후 Finalize해야 한다.
- Finalize 이후 input 수정 자체를 Notion에서 물리적으로 잠그지는 않는다. 대신 pinned outcome과 import preview mismatch를 Commit 직전에 fail closed한다.
- zero-write evidence는 감사 artifact이며 domain ledger/state write에는 포함하지 않는다.
- Stage C 이후 review 의미론의 확장은 이번 Slice B 범위가 아니다. Stage B commit 및 verification까지만 v2 zero-write를 연결했다.
- 전체 repository suite는 실행하지 않았다.

## Decisions Needed

없음. 기존 additive runbook state, 기존 reconciliation version naming, 기존 writer 재검증 경계를 이용해 호환성을 해치지 않는 위치를 결정할 수 있었다.

## Suggested next step

독립 검토자가 Review Evidence의 source diff와 테스트 매핑을 확인한 뒤, 별도 MFU에서 all-NOT_EXECUTED 이후 Stage C/Gate2 review 의미론이 필요한지 결정한다.

## Review Evidence path

`docs/work_results/MFU-EO2-SLICE-B_Review_Evidence.md`

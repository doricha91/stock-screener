# MFU-EO2-SLICE-A Result

## Summary

MFU-EO2 Slice A의 pure outcome derivation을 구현했다. 기존 v1 reconciliation, Commit, Notion/DB writer를 연결하거나 변경하지 않고, 정규화된 canonical candidate key 기준 exact-set 검증과 수량 기반 `EXECUTED / PARTIAL / NOT_EXECUTED` 계산을 additive API로 추가했다. FIX1에서 non-dict plan/execution context가 row identity 검증 중 예외를 발생시키던 결함을 최소 guard로 수정했다.

구현 판정은 **완료**다. FIX1 필수 경계와 관련 v1 회귀를 포함해 78개 테스트가 통과했고 Python 정적 컴파일 및 diff 검사를 완료했다.

## Baseline and AGENTS.md compliance

- 작업지시문: `D:\python\StockScreener\docs_chatGPT_work\MFU-EO2-SliceA_pure outcome derivation.md`
- 기준 브랜치: `gemini_cli_update`
- 시작 HEAD: `7945ea854faf025db8fd0710e24f5209a32e9f9b`
- 시작 시 기존 tracked dirty baseline:
  - `docs/operations/paper_daily_cycle_commands.md`
  - `idea, PRD, TRD/paper 운영 기능 개발 로드맵 v1.3.md`
  - `outputs/backtest_log.db`
- 기존 다수 untracked 문서·임시 디렉터리와 권한 제한 `_tmp_*` 경고도 사용자 소유 상태로 보존했다.
- reset, checkout, clean, stash, commit, push를 실행하지 않았다.
- DB/schema, 외부 서비스, Notion, broker, runbook state를 읽거나 쓰는 실행 경로를 호출하지 않았다.
- 전략·신호·포지션·수익률 계산을 변경하지 않았다.

## Current Code Findings

1. canonical key SSOT는 `core.notion_account_keys.build_manual_execution_canonical_key()`다.
2. `core.execution_reconciliation.normalize_plan_items()`는 기존 plan candidate를 `plan_external_key`, `planned_quantity`, account/trade-date가 있는 행으로 정규화한다.
3. `core.execution_reconciliation.normalize_execution_row()`는 execution input을 `manual_execution_external_key`, `actual_quantity`, account/trade-date가 있는 행으로 정규화한다.
4. 기존 `reconcile_plan_and_executions()`는 수량 차이를 `NEEDS_REVIEW`, missing/extra/identity 오류를 `BLOCKED`로 처리하며 `WAIT`, `NOT_EXECUTED`, outcome count를 표현하지 않는다.
5. 기존 Notion importer는 actual quantity를 양의 정수로 검증하지만, Slice A는 Notion producer/reader와 연결하지 않는 pure normalized-input 경계다.
6. batch의 data date와 contract version은 기존 정규화 행에 없으므로 새 pure API의 `plan_context`와 `execution_context`에서 비교한다.
7. FIX1 전에는 context error를 기록한 뒤에도 row identity 검증이 진행되어 non-dict context에서 `.get()` 예외가 가능했다. 현재는 두 context가 dict일 때만 row identity 검증을 수행한다.
8. normalized-input의 `symbol/side`는 두 normalize 함수에서 문자열로 변환되며, identity helper도 `_none_if_blank()` 결과만 `.upper()`하므로 문자열 전제가 코드에서 보장된다.

## Changed files

- `core/execution_reconciliation.py`
  - outcome/status 상수와 pure `derive_execution_outcomes()` API 추가
  - exact-set, context, row identity, quantity 및 count helper 추가
  - 기존 v1 함수의 signature와 동작은 변경하지 않음
- `tests/test_execution_outcome_derivation.py`
  - Slice A 및 FIX1 전용 unit tests 25개 추가
- `docs/work_results/MFU-EO2-SLICE-A_Result.md`
  - 본 상세 결과
- `docs/work_results/MFU-EO2-SLICE-A_Review_Evidence.md`
  - 실제 full status, source diff, 신규 테스트 전체와 validation evidence를 담은 ChatGPT 검토 번들

## Behavior changes

새 `derive_execution_outcomes()`는 다음 입력을 받는다.

- 기존 정규화 plan rows
  - `plan_external_key`
  - `planned_quantity`
  - `account_id`, `trade_date`, `symbol`, `side`
- 기존 정규화 execution rows
  - `manual_execution_external_key`
  - `actual_quantity`
  - `account_id`, `trade_date`, `symbol`, `side`
- batch 제어/문맥
  - `input_finalized`
  - plan/execution의 `account_id`, `data_date`, `trade_date`, `contract_version`

처리 결과는 결정론적으로 candidate key 순서로 정렬되며 다음을 포함한다.

- `runner_result`: `PASS / WAIT / BLOCKED`
- `action_mode`: `EXECUTION / NO_ACTION`
- candidate별 `outcome`, status, reason code
- planned/input/resolved/outcome/waiting/missing/extra/duplicate/invalid count
- `count_invariant_satisfied`
- candidate key가 포함된 정렬된 error 목록
- non-dict context 입력은 예외 없이 `BLOCKED`와 `context_invalid` error 반환

기존 v1 reconciliation preview, commit gate, writer 또는 runbook runner에서는 아직 이 API를 호출하지 않는다.

## Contract and invariant mapping

| 계약 | 구현 결과 |
|---|---|
| candidate 0건 | exact-set/context가 유효하고 양쪽 행이 0개이면 `runner_result=PASS`, `action_mode=NO_ACTION` |
| exact-set | plan/execution canonical key set의 missing/extra를 `BLOCKED` |
| duplicate | plan과 execution 양쪽에서 중복 key를 검출하고 `duplicate_count` 및 error 기록 |
| context/version | account/data-date/trade-date/contract-version 불일치를 `BLOCKED` |
| invalid context type | plan 또는 execution context가 dict가 아니면 예외 없이 `BLOCKED`, `context_invalid` |
| row identity | account/trade-date/symbol/side 불일치를 candidate-key 단위로 `BLOCKED` |
| full execution | `actual_qty == planned_qty`이면 `EXECUTED` |
| partial execution | `0 < actual_qty < planned_qty`이면 `PARTIAL` |
| 미입력·미종료 | exact-set 행은 존재하지만 actual quantity가 공란이면 `WAIT` |
| 미입력·종료 | exact-set 행은 존재하지만 actual quantity가 공란이면 `NOT_EXECUTED` |
| 명시적 0/음수/비수치/NaN/무한대 | 공란과 구분하여 `BLOCKED` |
| 계획 초과 | `actual_qty > planned_qty`이면 `BLOCKED` |
| count invariant | 확정 `PASS`에서 `planned_count == executed_count + partial_count + not_executed_count` |
| 결정론 | 입력 순서를 바꿔도 rows/errors와 전체 결과가 동일 |
| fail-closed | structural/quantity error가 하나라도 있으면 batch 전체 `BLOCKED`; write 가능 flag나 writer 호출 없음 |

Missing execution row 자체는 exact-set 위반이므로 `BLOCKED`다. `WAIT / NOT_EXECUTED`는 canonical execution input 행이 존재하고 actual quantity만 공란인 경우에만 계산된다.

## Tests run

1. Slice A unit tests

   ```text
   python -m pytest -q tests/test_execution_outcome_derivation.py
   25 passed in 0.25s
   ```

2. 관련 v1 reconciliation/candidate/intent 회귀

   ```text
   python -m pytest -q tests/test_execution_reconciliation.py tests/test_paper_daily_plan_candidates.py tests/test_paper_execution_intent.py
   50 passed in 0.43s
   ```

3. reconciliation preview CLI 회귀

   ```text
   python -m pytest -q tests/test_runbook_execution_reconciliation_preview.py
   3 passed in 1.87s
   ```

4. 변경 Python 파일 정적 컴파일

   ```text
   python -m py_compile core\execution_reconciliation.py tests\test_execution_outcome_derivation.py
   PASS
   ```

5. 최종 whitespace 검사

   ```text
   git diff --check
   Exit code: 0
   whitespace error 없음
   ```

   working-copy LF→CRLF 경고만 있었으며 상세 stderr는 Review Evidence에 기록했다.

총 자동화 테스트: **78 passed**.

## Tests not run and why

- 전체 repository test suite는 실행하지 않았다. Slice A는 기존 runtime 연결 없이 한 모듈에 추가된 pure API이므로, 직접 단위 테스트와 인접 v1 reconciliation/candidate/intent/CLI 회귀로 영향 범위를 검증했다.
- backtest/optimizer는 실행하지 않았다. 전략, 신호, 파라미터, 포지션 및 수익률 계산 변경이 없다.
- Notion/외부 DB/live broker 테스트는 실행하지 않았다. Slice A 범위 밖이며 외부 write 금지 조건을 준수했다.
- Commit, Finalize, verifier/idempotency 통합 테스트는 Slice B/C 범위이므로 실행하지 않았다.

## Diff self-review

- 기존 public 함수의 signature 또는 기존 v1 상수 의미를 변경하지 않았다.
- 새 API는 기존 canonical key 필드와 Decimal 변환 helper를 재사용한다.
- set 순회 결과를 직접 노출하지 않고 key와 errors를 명시적으로 정렬한다.
- missing row와 blank actual quantity를 구분한다.
- 명시적 `actual_qty=0`을 `NOT_EXECUTED`로 변환하지 않는다.
- structural error가 있으면 quantity outcome 계산 전에 batch를 차단한다.
- quantity error가 있으면 batch 결과는 항상 `BLOCKED`다.
- non-dict context에서는 row identity helper를 호출하지 않고 기존 `context_invalid` 구조로 차단한다.
- write, commit eligibility 또는 state mutation 결과를 생성하지 않는다.
- 기존 dirty 파일과 보호된 DB 파일을 수정하지 않았다.

## Risks and limitations

1. 이 API는 정규화된 in-memory 행을 대상으로 한다. raw Daily Plan/Notion input과의 연결, Finalize persistence, Commit은 아직 없다.
2. actual price의 공란·유효성 검사는 Slice B input 경계에 남아 있다. Slice A outcome은 지시대로 수량 완결성만 계산한다.
3. quantity는 기존 reconciliation의 `Decimal(str(value))` 의미를 유지한다. 실제 Notion producer의 양의 정수 검증은 Slice B 연결 시 계속 적용해야 한다.
4. `contract_version`은 양쪽 context의 존재와 동일성만 검증한다. 지원 version allowlist/reader dispatch는 실제 v2 producer가 생기는 Slice B/C에서 소유해야 하며 Slice A가 임의 schema를 만들지 않았다.
5. canonical key 형식 생성은 기존 producer/helper 책임이다. 이 API는 정규화된 행의 key exact-set과 row identity를 검증하며 raw key를 새로 생성하지 않는다.
6. 2026-08-14 incident, completed v1 evidence, RETIRED/rollover는 변경하지 않았다.
7. raw caller가 normalized-input 계약을 우회해도 `symbol/side`는 `_none_if_blank()`에서 문자열화되지만, 이번 FIX1은 관련 validation 의미를 확장하지 않았다.

## Decisions Needed

Slice A 완료를 막는 결정 사항은 없다.

Slice B 착수 전에는 다음 연결 정책을 현재 producer/schema와 함께 확정해야 한다.

1. raw execution input에서 blank quantity/price를 손실 없이 유지하는 방식. 현재 Notion importer는 blank quantity/price를 각각 `0`, `0.0`으로 정규화하므로 `WAIT/NOT_EXECUTED`와 invalid zero가 구분되지 않는다.
2. 지원할 v2 contract-version 이름과 reader dispatch 소유 지점.
3. runbook 단위 Finalize의 저장 위치와 idempotent 전이 규칙.

이는 Slice A pure derivation의 동작을 변경하지 않는 Slice B 결정이다.

## Suggested next step

사용자와 ChatGPT Chat이 본 Slice A 결과와 diff를 검토하여 `PASS / 수정 필요 / BLOCKED`를 판정한다. PASS 후에만 Slice B 작업지시문을 작성하고, blank raw input 보존과 Finalize 경계를 먼저 설계한 뒤 Commit 연결을 진행한다.

## Review Evidence file path

`docs/work_results/MFU-EO2-SLICE-A_Review_Evidence.md`

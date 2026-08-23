# Summary

`runbook_recovery.v1` immutable sidecar와 `status`/`preview`/`authorize` CLI를 구현했다. 유효한 sidecar만 오염된 progressed source를 rollover 관점에서 `RECOVERY_EXCLUDED`로 분류하며, 미소비 authorization은 pin된 exact restart pair만 제공한다. source state와 artifacts, account ledger 및 실제 `D:\n8n` workspace는 변경하지 않았다.

실제 운영 workspace에 대한 read-only preview 결과는 source SHA-256 `22799cb39561210183333fe0b0ae49299aa184709abc96a4dd983b25218b8bcb`, latest valid completed `paper_pilot_202606_2026-08-12_2026-08-13`, gap execution 0건, conditional pair `2026-08-21`→`2026-08-24`로 PASS했다. 실제 authorize는 실행하지 않았다.

# Implemented recovery contract

- source는 원본 `ACTIVE_INCOMPLETE` evidence로 남는다.
- 별도 sidecar가 source hash/context, latest completed identity, canonical gap, ledger evidence, calendar identity, exact restart pair, reason, confirmations 및 authorization timestamp를 pin한다.
- authorization은 create-only `O_EXCL` write이며 기존 파일을 덮어쓰지 않는다.
- status와 preview는 read-only이고 authorize는 동일 eligibility를 직전에 다시 계산한다.
- invalid/stale sidecar는 exclusion을 취소하고 source를 다시 `ACTIVE_INCOMPLETE`로 fail-closed 처리한다.

# Files changed

Production/source:

- `core/runbook_recovery.py` — recovery contract, eligibility, sidecar validation/write, initialization guard.
- `scripts/runbook_recovery.py` — status/preview/authorize CLI.
- `core/runbook_day_rollover.py` — `RECOVERY_EXCLUDED` classification과 one-time recovery branch.
- `scripts/runbook_state.py` — 새 context 생성 직전 중앙 initialization guard 호출 한 곳.
- `docs/operations/runbook_recovery_contract.md` — operator safety/CLI contract.

Tests:

- `tests/test_runbook_recovery.py`

Task result/evidence:

- `docs/work_results/PAPER-OPS-RUNBOOK-RECOVERY-CONTRACT1_Result.md`
- `docs/work_results/PAPER-OPS-RUNBOOK-RECOVERY-CONTRACT1_Review_Evidence.md`

`core/runbook_day_prep.py`, Stage A~F runner semantics, retirement, completion validators, benchmark 계산은 변경하지 않았다.

# Sidecar schema and storage

저장 경로는 `<workspace>/runbook_recoveries/<source_runbook_day_id>.json`이다. schema는 `runbook_recovery.v1`, disposition은 `RECOVERY_EXCLUDED`이다.

필드는 account/source identity와 frozen context, source state ref/hash, reason, latest completed state ref/context/hash, no-trade interval과 canonical trading dates, authorization 시 ledger hash, exact restart context/ID, calendar schema/coverage/file hash, 네 가지 operator confirmation 및 timezone-aware `authorized_at`을 포함한다.

sidecar는 completion, retirement, source state 대체물 또는 lifecycle history가 아니다. 기존 sidecar가 있으면 동일 내용의 재실행도 BLOCK하며 status로 기존 authorization을 확인한다.

# Recovery eligibility

authorize와 preview는 다음을 동일하게 검증한다.

1. paper/test account와 네 가지 explicit confirmation.
2. non-empty reason, exact source account/ID/context 및 valid source state.
3. source가 completed/legacy/retired가 아닌 progressed active incomplete이고 유일한 active임.
4. unique latest standard/legacy completed baseline.
5. source trade date부터 restart data date까지 canonical trading-date gap.
6. canonical account execution ledger의 gap execution 0건.
7. restart data/trade가 trading day이고 trade가 data 다음 첫 거래일임.
8. restart pair가 source/latest completed보다 앞으로 진행함.
9. target state/artifact 및 다른 source/account recovery conflict 없음.

위반 시 sidecar를 쓰지 않고 BLOCK한다.

# Source runbook immutability

실제 source `paper_pilot_202606_2026-08-13_2026-08-14`는 계속 Stage A/Step 5 PASS, Gate1~F PENDING이다. 구현 전후 state SHA-256은 `22799cb39561210183333fe0b0ae49299aa184709abc96a4dd983b25218b8bcb`로 동일하다.

실제 Stage A artifacts, command/stage evidence, account daily plan 및 execution ledger를 read-only hash inventory로 재확인했다. 실제 sidecar와 target state는 모두 존재하지 않는다.

# No-trade / gap validation

gap은 source trade date부터 restart data date까지 canonical calendar로 derive한다. 현재 실제 preview 결과는 다음 여섯 날짜다.

- 2026-08-14
- 2026-08-17
- 2026-08-18
- 2026-08-19
- 2026-08-20
- 2026-08-21

canonical account ledger SHA-256은 `2b6309ce21e3475b69e874cbf92413451ed703f5016f953688304320b3324f00`이고 해당 날짜 execution은 0건이다. authorization 후 ledger에 gap execution이 추가되어도 sidecar revalidation이 실패한다. operator confirmation은 ledger 검증을 대체하지 않는다.

# RECOVERY_EXCLUDED classification

rollover는 standard, legacy, retirement 검증을 먼저 유지한다. 그 어느 것도 아닌 source에 대해 recovery sidecar를 검증하고, 현재 source bytes/context/hash, confirmations, pinned completed state, canonical gap/calendar, ledger contradiction 및 target 상태가 모두 유효한 경우에만 `RECOVERY_EXCLUDED`를 반환한다.

`RECOVERY_EXCLUDED`는 active blocker에서만 제외되며 standard/legacy/retired 또는 completed baseline 후보가 아니다. malformed JSON, schema/account/context/disposition/calendar/hash mismatch, ledger contradiction 또는 target conflict가 있으면 source는 `ACTIVE_INCOMPLETE`로 복귀한다.

# One-time restart authorization

미소비 valid sidecar는 오직 sidecar의 exact pair와 target ID만 rollover에 제공한다. CLI/operator가 rollover나 prep에 다른 날짜를 주입하는 새 경로는 없다. sidecar 생성 후 다른 pair preview/authorize도 기존 immutable authorization 때문에 BLOCK된다.

target state가 정확한 context로 생성되면 authorization은 consumed로 판정한다. 이후 sidecar를 다시 제안하지 않으며 target가 active이면 기존 active guard가 적용된다.

# Rollover integration

`preview_rollover()`의 기존 active guard 뒤에 recovery branch를 최소 추가했다.

- invalid/no sidecar: 기존 `active_runbook_day_exists`.
- valid unconsumed sidecar: `rollover_mode=RECOVERY`, exact pinned pair, `safe_to_prepare=true`.
- target active: 기존 active guard BLOCK.
- target standard completed: recovery branch 재사용 없이 기존 latest-completed sequential branch.

# Prep / initialization integration

기존 prep은 rollover의 `next_data_date`, `next_trade_date`, `next_runbook_day_id`를 검증하고 기록하므로 수정 없이 recovery exact pair를 소비한다. 전용 테스트에서 `_runbook_day.local.cmd`에 2026-08-21/2026-08-24/exact target ID만 기록됨을 검증했다.

actual call graph상 별도 `01_initialize_runbook_day.cmd`는 없고 `01_stage_a_plan_prep.cmd`가 Stage A runner를 호출하며 그 runner가 `init_state_file_for_context()`에서 state를 생성한다. 수동 local context 우회를 막기 위해 이 중앙 생성 지점에 guard를 추가했다.

- progressed active source + authorization 없음: BLOCK.
- valid unconsumed authorization + 다른 target: BLOCK.
- valid unconsumed authorization + exact target: 생성 허용.
- target 생성 후 다른 target: existing active guard로 BLOCK.
- fresh workspace 및 기존 정상 first-context semantics: 보존.

# Normal rollover preservation

normal branch의 계산은 변경하지 않았다.

```text
latest STANDARD_COMPLETED / LEGACY_COMPLETED trade date
-> next data date
-> canonical next trading day
-> next trade date
```

retired와 recovery-excluded는 baseline이 아니다. current date auto-jump, missed-day scheduler, historical backfill을 추가하지 않았다. 기존 rollover/retirement/prep/state 166개 사전 회귀와 recovery 포함 186개 회귀가 PASS했다.

# Clean target lifecycle

clean target `paper_pilot_202606_2026-08-21_2026-08-24`가 생성되면 일반 `ACTIVE_INCOMPLETE` state이다. 기존 Stage A readiness/as-of와 Stage A~F/Step 21 completion contract를 모두 통과해야 한다.

target가 standard completed가 되면 다음 정상 rollover는 target trade date `2026-08-24`를 next data date로 사용하고 canonical next trading day를 계산한다. routing test의 대표 calendar 결과는 `2026-08-25`였다. 실제 completion validator 자체는 별도 117개 completion/Stage F 회귀로 검증했다.

# Benchmark / gap handling

benchmark/performance 코드는 변경하지 않았다. recovery는 누락일 0% return, snapshot, benchmark point 또는 historical EOD를 생성하지 않는다. gap은 sidecar의 canonical dates와 no-backfill confirmation으로만 남고, 새 observation은 clean target의 정상 Stage E/F에서 생성되어야 한다.

# Tests

실제로 실행한 테스트:

- recovery 전용 최종: 24 passed.
- recovery + rollover + retirement + prep + state: 186 passed.
- Stage A AS-OF/universe/freshness/cutoff: 29 passed, dependency deprecation warning 1개.
- MFU-EO2/execution reconciliation/Stage B: 146 passed.
- completion/Stage F: 117 passed.
- Stage runner 통합: 30 passed.

중복 포함 총 실행 결과는 모두 PASS다. pytest cache provider는 최종 회귀에서 비활성화했고 각 suite는 별도 `.tmp` basetemp를 사용했다.

# Regression results

- normal sequential/legacy/retirement/active/multiple-active/duplicate/calendar semantics 유지.
- prep exact-pair 소비 및 initialization guard 통과.
- Stage A AS-OF/FIX-1/FIX-1A 관련 회귀 통과.
- MFU-EO2 zero-count, derivation/flow, reconciliation, Stage B 회귀 통과.
- completion manifest/Stage F 및 runner 통합 회귀 통과.
- `python -m py_compile` 및 `git diff --check`는 최종 evidence에 실제 stdout과 함께 기록한다.

# Actual operational state protection

실제 `D:\n8n\workspace\stock_screener_ops`에서는 status와 preview만 실행했다. authorize, 00 prepare, Stage A, Gate, Stage B~F, Notion, EOD, ledger/DB write는 실행하지 않았다.

최종 read-only 확인:

- actual recovery sidecar: 없음.
- actual target state: 없음.
- source state SHA: 불변.
- source artifacts: 불변 hash inventory.
- actual ledger SHA: 불변.

# Risks / limitations

- conditional pair의 실제 Stage A market/universe/config readiness는 운영 실행 시점에 별도로 PASS해야 한다. recovery authorization은 이를 우회하지 않는다.
- sidecar는 authorization 당시 ledger 전체 hash를 evidence로 pin하지만, 이후 정상 거래 append를 허용하기 위해 validity는 전체 hash 동일성이 아니라 gap-date execution contradiction을 재검증한다.
- initialization guard는 실제 per-context Stage runner 생성 경로에 적용된다. legacy single-file `runbook_state.json` utility는 현재 Paper Ops wrapper call graph가 아니므로 변경하지 않았다.
- target-completed recovery routing test는 target classification을 격리해 검증했고, 실제 standard completion evidence semantics는 기존 completion/Stage F 117개 회귀에서 별도로 검증했다.
- 기존 worktree의 다수 dirty/untracked 변경과 보호 DB 변경은 이번 작업 범위가 아니며 보존했다.

# Decisions Needed

구현 계약에 대한 추가 결정은 없다. 실제 `paper_pilot_202606` recovery authorize 및 clean restart 실행은 별도 operator 승인과 실행 직전 evidence/readiness 검토가 필요하다.

# Exact operator procedure after approval

이번 작업에서는 아래 절차를 실행하지 않았다.

1. Read-only status:

```bat
python scripts\runbook_recovery.py status ^
  --workspace D:\n8n\workspace\stock_screener_ops ^
  --account-id paper_pilot_202606 ^
  --runbook-day-id paper_pilot_202606_2026-08-13_2026-08-14
```

2. Read-only preview:

```bat
python scripts\runbook_recovery.py preview ^
  --workspace D:\n8n\workspace\stock_screener_ops ^
  --account-id paper_pilot_202606 ^
  --runbook-day-id paper_pilot_202606_2026-08-13_2026-08-14 ^
  --restart-data-date 2026-08-21 ^
  --restart-trade-date 2026-08-24 ^
  --reason "Stage A look-ahead contaminated; no real trades; missed interval accepted" ^
  --confirm-paper-test ^
  --confirm-contaminated-incomplete ^
  --confirm-no-real-trades ^
  --confirm-gap-without-backfill
```

3. Review `source_state_sha256`, latest completed identity/hash, six gap dates, `execution_count=0`, calendar identity/hash, exact target ID, and actual order absence.
4. After explicit operational approval, replace `preview` with `authorize` using every other argument unchanged.
5. Run status again and require `sidecar_valid=true`, `current_classification=RECOVERY_EXCLUDED`, `consumed=false`.
6. Run read-only rollover preview and require `rollover_mode=RECOVERY`, exact 2026-08-21/2026-08-24 pair and `safe_to_prepare=true`.
7. Run `ops\runbook_wrappers\00_prepare_next_runbook_day.cmd`.
8. Inspect `_account.local.cmd` and `_runbook_day.local.cmd`; require account, pair, and target ID exact match.
9. Run `ops\runbook_wrappers\01_stage_a_plan_prep.cmd`. This is the actual initialization/Stage A wrapper.
10. Require Stage A market freshness, indicator/RS cutoff, universe/config snapshots, account cutoff and provenance/as-of validation PASS.
11. Continue the existing Gate1→Stage B→C→Gate2→D→E→F Paper Ops lifecycle without recovery bypass.

# Review Evidence path

`docs/work_results/PAPER-OPS-RUNBOOK-RECOVERY-CONTRACT1_Review_Evidence.md`

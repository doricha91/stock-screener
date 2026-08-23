# Executive verdict

결론은 **C — recovery contract required**이다. 현재 `paper_pilot_202606_2026-08-13_2026-08-14`는 Stage A/Step 5까지 PASS한 `ACTIVE_INCOMPLETE`이므로 다음 runbook 준비를 fail-closed로 막는다. 기존 retirement는 strict zero-progress 전용이어서 이 상태를 처리할 수 없다.

과거 2026-08-14 및 2026-08-17~2026-08-21을 현재 universe/config로 재생하거나 완료로 가장해서는 안 된다. 정상 sequential rollover는 그대로 보존하고, 오염된 진행 상태를 별도 불변 sidecar로 격리한 뒤 한 번만 명시적으로 clean restart anchor를 승인하는 recovery contract가 필요하다. 2026-08-22 현재 canonical calendar상 후보는 `DATA_DATE=2026-08-21`, `TRADE_DATE=2026-08-24`이다. 이는 실제 실행 전 시장 데이터 완결성 preflight를 다시 통과해야 한다.

이번 작업에서는 운영 상태, DB, ledger, Notion, broker, production source 및 tests를 변경하지 않았다. 허용된 결과/증거 문서만 생성했다.

# Current 2026-08-14 runbook state

- ID: `paper_pilot_202606_2026-08-13_2026-08-14`
- frozen context: account `paper_pilot_202606`, data date `2026-08-13`, trade date `2026-08-14`
- state SHA-256: `22799CB39561210183333FE0B0AE49299AA184709ABC96A4DD983B25218B8BCB`
- created/updated: `2026-08-16T12:52:45.408589+09:00` / `2026-08-16T13:06:25.208845+09:00`
- `current_stage=A`, `current_status=PASS`, `last_completed_step=5`, `last_completed_stage=A`
- Stage A만 PASS이고 GATE1/B/C/GATE2/D/E/F는 모두 PENDING이다.
- Stage A daily-plan JSON/Markdown artifact가 존재한다.
- idempotency record, recovery authorization, `last_error`는 없다.
- 확인된 사고 전제: Stage A 입력이 오염됐고, 실거래/수동 execution은 발생하지 않았으며 Gate1 이후는 실행하지 않았다.

# Current rollover behavior

`core/runbook_day_rollover.py`는 계정의 모든 state를 `STANDARD_COMPLETED`, `LEGACY_COMPLETED`, `RETIRED`, `ACTIVE_INCOMPLETE`로 분류한다. 하나라도 active incomplete가 있으면 날짜 계산 전에 `active_runbook_day_exists`로 BLOCK한다. 따라서 현재 preview는 날짜를 제안하지 않고 `safe_to_prepare=false`를 반환한다.

정상 계산은 오직 latest standard/legacy completed의 trade date를 다음 data date로 사용하고, canonical NYSE calendar의 다음 거래일을 trade date로 사용한다. `RETIRED`는 blocker에서만 제외되며 baseline이 아니다. 이 sequential 규칙은 변경하면 안 된다.

# Does 8/14 block next run?

그렇다. 실제 preview stdout은 `active_runbook_day:paper_pilot_202606_2026-08-13_2026-08-14`를 blocker로 반환했다. `00_prepare_next_runbook_day.cmd`는 write mode의 prep을 호출하고 prep은 먼저 같은 preview를 사용하므로 현재 그대로라면 준비도 BLOCK된다.

현재 prepare가 8월 17일을 제안하는 것은 아니다. active 상태 때문에 아무 날짜도 제안하지 않는다. active 상태만 단순 제외하더라도 latest completed는 8월 13일이므로 정상 rollover는 8월 14일을 다시 계산한다. clean 8월 21일→8월 24일 점프에는 별도 recovery authorization이 필요하다.

# Existing retirement / abandon / recovery mechanisms

기존 `runbook_retirement.v1`은 다음 조건을 모두 요구한다: A/READY 초기 상태, completed step/stage 없음, 모든 stage PENDING, artifact/idempotency/recovery/history/error 없음, workspace evidence 없음. 실제 `status` 결과는 이번 상태에 대해 다음 blocker를 반환했다.

- `state_not_initial_ready`
- `completed_progress_present`
- `stage_progress_present`
- `artifact_evidence_present`
- `history_progress_present`
- `workspace_evidence_present:artifacts`
- `workspace_evidence_present:command_runs`
- `workspace_evidence_present:stage_runs`

따라서 retirement를 완화하거나 기존 증거를 위조해서 적용하면 안 된다. `scripts/runbook_state.py`의 recovery authorization은 Stage B strict-write retry에 국한되며 진행된 Stage A 오염 상태를 abandon하거나 날짜 gap을 승인하는 일반 lifecycle이 아니다. 현재 일반 abandon/recovery lifecycle은 없다.

# Missed-day continuity analysis

canonical calendar상 2026-08-14, 17, 18, 19, 20, 21은 거래일이다. 15~16일과 22~23일은 비거래일이며 21일 다음 거래일은 24일이다.

## Account state

execution log는 44행이고 latest execution date는 2026-08-13이다. 8월 14일 및 17~21일 execution은 모두 0건이다. `load_official_paper_state_for_daily_plan()`은 새 plan date 이하의 execution log로 account state를 재구성하므로, 무거래 gap 자체는 보유수량·현금 cost basis 연속성을 깨지 않는다. clean restart는 8월 13일까지 확정된 ledger를 그대로 사용해야 하며 가상 거래나 backfill execution을 추가하면 안 된다.

다만 시장가 평가/high-watermark는 새 data date의 canonical DB를 사용하므로 실제 재시작 전 2026-08-21 데이터 완결성과 as-of contract를 다시 검증해야 한다.

## EOD / snapshots

account snapshot latest는 2026-08-13(10행), position snapshot latest는 2026-08-13(84행), current-state latest도 2026-08-13이다. 8월 14일 및 17~21일에는 account/position snapshot, current-state, EOD commit이 없다. 이는 실제 운영이 중단됐다는 정직한 gap이며 과거 상태를 현재 가격으로 생성해서 메우면 안 된다.

clean restart가 완료되면 그 run의 Stage E가 새 trade date의 snapshot/current-state를 정식으로 생성한다. series에는 8월 13일에서 clean restart trade date로 점프가 남아야 한다.

## Benchmark / performance

benchmark report의 latest snapshot date는 2026-08-13이다. benchmark/performance는 existing snapshot series를 사용하므로 누락 기간을 수익률 0으로 암묵 보간하거나 current prices로 backfill하면 안 된다. clean restart Stage F는 새 Stage E snapshot을 사용하고, 보고서에는 관측 gap을 명시해야 한다.

## Review / Notion

8월 14일 오염 daily plan은 로컬에 있으나 Gate1 이후 review/import/sync는 수행되지 않았다. 17~21일 plan/review/Notion operational evidence도 없다. 과거 Notion page를 현재 정보로 생성하거나 8월 14일 plan을 정상 plan으로 게시해서는 안 된다. recovery incident evidence와 이후 clean run의 정상 Notion evidence를 구분해야 한다.

## Completion evidence

8월 14일은 Stage E/F와 final status/account snapshot Notion/benchmark Notion 증거가 없으므로 completed로 분류될 수 없다. recovery exclusion은 completion이 아니며 latest completed baseline 후보가 되어서는 안 된다. clean restart는 기존 Stage A~F/Step 21 completion contract를 그대로 통과해야 한다.

# Is historical catch-up required?

아니다. 오히려 금지해야 한다. 당시 의사결정 시점의 universe/config와 운영 입력을 신뢰성 있게 재현할 수 없고 실제 거래도 없었다. current universe/config를 과거 날짜에 적용하면 look-ahead/재현성 왜곡이 생긴다. 누락된 snapshots, plans, reviews, Notion records 및 benchmark points는 명시적 운영 gap으로 유지한다.

# Clean restart eligibility

다음 조건을 모두 만족할 때만 clean restart가 eligible하다.

1. paper/test account이며 live broker/order path가 비활성이다.
2. 오염 state의 context와 SHA-256이 승인 시점과 일치한다.
3. 정확히 하나의 active incomplete state만 있고 그것이 승인 대상이다.
4. latest completed state `paper_pilot_202606_2026-08-12_2026-08-13`가 여전히 valid standard completion이다.
5. 2026-08-14 이후 ledger execution이 0건임을 account-scoped source로 검증한다.
6. 8월 14일 및 17~21일에 실거래가 없었음을 operator가 명시 확인한다.
7. gap을 backfill하지 않고 보고서에 보존한다는 확인이 있다.
8. restart data/trade date가 canonical calendar coverage 내에 있고 순서가 맞는다.
9. restart data date의 market/universe/config as-of preflight가 실행 당일 PASS한다.
10. 동일 account에 유효한 다른 recovery authorization 또는 target runbook state/artifact가 없다.

# Candidate clean restart dates

| Candidate | Calendar result | Judgment |
|---|---|---|
| data 2026-08-13 / trade 2026-08-14 | 둘 다 거래일 | 오염된 기존 run과 충돌하므로 부적격 |
| data 2026-08-14 / trade 2026-08-17 | calendar상 순차 후보 | 과거 catch-up이며 현재 입력으로 재생 금지 |
| data 2026-08-20 / trade 2026-08-21 | calendar상 가능 | 이미 지난 trade date이므로 현재 clean restart로 부적격 |
| data 2026-08-21 / trade 2026-08-24 | 21일과 24일 거래일, weekend skip | **권고 후보**, 단 실행 직전 data readiness 재검증 필요 |

# Recovery options

| Option | Finding | Consequence |
|---|---|---|
| A. Existing mechanism is enough | 거짓. retirement는 progressed state를 거부하고 rollover는 active state를 차단한다. | 선택 불가 |
| B. Minimal ad-hoc state/file edit | 원본 state 수정, fake completion, artifact 삭제는 audit trail과 fail-closed를 훼손한다. | 선택 금지 |
| C. Explicit recovery contract | 원본을 보존하고 별도 hash-pinned disposition과 one-time restart anchor를 둔다. | **권고** |

필수 판단표:

| Question | Finding | Evidence | Consequence |
|---|---|---|---|
| 현재 incomplete가 prepare를 막는가? | Yes | 실제 rollover BLOCK stdout | recovery 전 prepare 금지 |
| prepare가 8/17을 제안하는가? | No | 날짜 계산 전에 active guard | 날짜 점프를 암묵 추론 금지 |
| latest completed만 baseline인가? | Yes | rollover source/classification | normal rule 보존 |
| 기존 retirement로 처리 가능한가? | No | status blocker 8종 | 별도 contract 필요 |
| historical catch-up이 필요한가? | No | execution 0, 당시 입력 재현 불가 | gap 보존, backfill 금지 |
| account state 연속성은 유지되는가? | 거래 ledger 기준 Yes | latest execution 8/13, 이후 0 | 8/13 ledger에서 재구성 |
| snapshot/benchmark 연속성은 완전한가? | No | 모두 latest 8/13 | 관측 gap 명시 |
| clean 8/21→8/24가 calendar상 유효한가? | Yes | bundled NYSE calendar | readiness 조건부 후보 |

# Recommended minimal recovery path

1. 새 `runbook_recovery.v1` sidecar contract를 추가한다. 원본 state/artifact는 변경·삭제하지 않는다.
2. sidecar는 `RECOVERY_EXCLUDED` disposition과 one-time restart authorization을 함께 기록한다.
3. sidecar에 account/context/state ref/state SHA-256, latest completed ID/hash, incident reason, confirmed no-trade interval, calendar-derived gap trading dates, restart dates, confirmations, timestamp를 pin한다.
4. rollover는 유효 sidecar가 있을 때만 대상 active state를 blocker에서 제외한다. 이 분류는 completed/retired와 별도이며 baseline이 아니다.
5. normal rollover 계산은 그대로 둔다. 별도 recovery branch만 sidecar의 exact one-time restart pair를 반환한다.
6. exact target state/artifact가 이미 존재하면 overwrite하지 않고 fail-closed한다. target state가 만들어진 뒤에는 일반 active guard가 다시 적용된다.
7. clean run이 standard completion을 달성하면 그 trade date부터 이후 rollover는 기존 sequential rule로 자동 복귀한다.
8. gap은 completion/benchmark/Notion에서 정상 완료로 가장하지 않고 recovery metadata로만 설명한다.

# Exact state transitions / commands for later execution

아래는 **recovery contract 구현·검토·테스트 완료 후에만 실행할 제안 명령**이다. 이번 audit에서는 실행하지 않았다.

상태 전이:

```text
ACTIVE_INCOMPLETE (original state preserved)
  -> RECOVERY_EXCLUDED + ONE_TIME_RESTART_AUTHORIZED (immutable sidecar)
  -> PREPARED exact 2026-08-21/2026-08-24 local context
  -> ACTIVE new runbook day (normal controller lifecycle)
  -> STANDARD_COMPLETED
  -> subsequent NORMAL_SEQUENTIAL_ROLLOVER
```

제안 명령:

```bat
python scripts\runbook_recovery.py status ^
  --workspace D:\n8n\workspace\stock_screener_ops ^
  --account-id paper_pilot_202606 ^
  --runbook-day-id paper_pilot_202606_2026-08-13_2026-08-14

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

python scripts\runbook_recovery.py authorize ^
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

python scripts\runbook_day_rollover.py ^
  --workspace D:\n8n\workspace\stock_screener_ops ^
  --account-id paper_pilot_202606 ^
  --confirm-paper-test

ops\runbook_wrappers\00_prepare_next_runbook_day.cmd
ops\runbook_wrappers\01_initialize_runbook_day.cmd
```

`authorize` 전후에는 status/preview를 검토하고, 00 실행 전 `DATA_DATE=2026-08-21`, `TRADE_DATE=2026-08-24`, exact target ID, market data readiness를 확인해야 한다. 01 이후에는 기존 Stage A~F 순서를 그대로 따른다.

# Required code changes, if any

이번 audit에서는 코드 변경을 하지 않는다. 후속 MFU에서 최소 다음이 필요하다.

- 신규 `core/runbook_recovery.py`: schema, eligibility, SHA/context pinning, gap/calendar derivation, validation, atomic sidecar write.
- 신규 `scripts/runbook_recovery.py`: read-only status/preview와 명시적 authorize CLI 분리.
- 최소 수정 `core/runbook_day_rollover.py`: valid recovery exclusion과 one-time recovery preview branch. 기존 normal sequential branch는 불변.
- 필요 시 `core/runbook_day_prep.py`/wrapper 문서: recovery preview 결과를 exact pair로 소비하되 arbitrary date 입력은 허용하지 않음.
- 신규/갱신 operations 문서: recovery 승인 경계, gap disclosure, 실행 순서.

# Required tests, if any

후속 구현에서 최소 다음 테스트가 필요하다.

- 현재 8/14 형태의 progressed Stage A는 retirement 불가이고 recovery 전 rollover BLOCK.
- exact eligible incident만 recovery preview/authorize PASS.
- state hash/context 변화, execution 존재, multiple active, missing latest completion, calendar 범위 초과, target 존재 시 fail-closed.
- recovery exclusion은 completed baseline이 아니고 normal rollover 규칙을 바꾸지 않음.
- one-time pair는 8/21→8/24로 고정되고 arbitrary jump/재사용/중복 authorization 차단.
- authorization 후 exact target 준비 가능, target 생성 후 active guard 재적용.
- clean target standard completion 후 다음 rollover는 8/24를 data date로 정상 순차 진행.
- 원본 state/artifact 불변성과 preview read-only 보장.
- gap dates, no-trade evidence, snapshot/benchmark disclosure가 manifest/evidence에 유지됨.

# Risks / limitations

- 2026-08-21 market data가 실제로 완결됐는지는 이번 read-only audit에서 실행 preflight하지 않았다.
- execution log의 0건은 repository account ledger 기준이다. operator의 “실제 주문 없음” 확인을 authorization에 별도로 요구해야 한다.
- Notion live 상태는 조회하지 않았다. 로컬 controller/account evidence상 8월 14일 Gate1 이후 및 17~21일 evidence가 없다는 결론이다.
- recovery branch를 normal rollover에 섞으면 arbitrary jump 경로가 생길 위험이 있다. 별도 schema/confirmations/one-time target 검증이 필수다.
- snapshot gap 때문에 기간 성과 시계열은 불연속이다. 이를 0% 수익률로 해석하면 안 된다.

# Decisions Needed

후속 구현 전에 사용자/operator가 다음을 승인해야 한다.

1. `runbook_recovery.v1` 별도 sidecar와 `RECOVERY_EXCLUDED` 분류 도입.
2. 8월 14일 및 17~21일 무거래·무backfill gap을 공식 수용.
3. 조건부 clean restart pair `2026-08-21`→`2026-08-24`.
4. recovery sidecar를 completion이 아닌 incident/disposition evidence로 취급.

# Suggested next work ID

`PAPER-OPS-RUNBOOK-RECOVERY-CONTRACT1`

# Review Evidence path

`docs/work_results/PAPER-OPS-RUNBOOK-RECOVERY-AUDIT-DESIGN1_Review_Evidence.md`

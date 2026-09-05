# StockScreener 현재 로드맵 및 기능 기준선

- 상태: **공식 기준(Canonical)**
- 최종 갱신일: **2026-09-05**
- 기준 브랜치: `gemini_cli_update`
- 검증 기준 HEAD: `e840344551691382f46ebb27dec71f4b1fd63567`
- 로드맵 비교 기준선: `e17978f332a8853588f287cf5aa2a5ef9bd57c74` (마지막 로드맵 내용 변경)
- 이전 문서의 검증 기준: `4fdb9b0da92626a0fee765106389aff2bd756e70`
- 검증 범위: `4fdb9b0da92626a0fee765106389aff2bd756e70..e840344551691382f46ebb27dec71f4b1fd63567`의 Git commit, 변경 코드·테스트·운영 문서·Result/Review Evidence, 최신 읽기 전용 Paper Ops state
- 최신 실제 운영 증거: `D:\n8n\workspace\stock_screener_ops\runbook_states\paper_pilot_202606_2026-09-04_2026-09-08.json`, `updated_at=2026-09-05T09:12:57.456763+09:00`

## A. 문서 권한과 사용법

`docs/ROADMAP_CURRENT.md`는 StockScreener의 현재 개발 상태, 운영 범위, 공식 우선순위를 판단하는 유일한 current roadmap이다. 과거 로드맵이나 평가 문서의 “현재 상태” 또는 “다음 작업”이 이 문서와 충돌하면 이 문서를 따른다.

이 문서는 상세 PRD/TRD나 실행 계약을 대체하지 않는다. 실제 동작과 완료 판정은 코드, 테스트, 승인된 계약, 실제 운영 evidence를 함께 확인한다.

```text
현재 코드 / 테스트 / 승인된 운영 계약 / 실제 운영 evidence
-> ROADMAP_CURRENT.md의 현재 상태 및 공식 우선순위
-> 최신 initiative별 PRD/TRD
-> 과거 로드맵, 설계 및 평가 이력
```

과거 문서는 설계 근거와 감사 이력으로 보존한다. 새로운 로드맵 파일을 늘리지 않고 현재 상태가 바뀔 때 이 파일을 갱신한다.

## B. 프로젝트 목표와 핵심 설계 원칙

목표는 재현 가능하고 fail-closed인 paper 투자 운영을 유지하면서, 계좌·데이터·실행 evidence의 경계를 먼저 닫고 연구·자동화·소비 계층을 단계적으로 확장하는 것이다. 기능 수보다 데이터 무결성, 수치 정합성, 운영 복구 가능성을 우선한다.

핵심 원칙:

- 실제 사용 evidence 없이 capability를 완료로 올리지 않는다.
- 현재 전략 성능을 높이기 위한 임의 변경보다 timing/as-of/reconciliation 계약을 우선한다.
- 같은 책임의 두 번째 validation, regime, ledger 계층을 만들지 않는다.
- write는 승인·preview·idempotency·evidence 경계를 유지하고 자동화는 read-only부터 확장한다.
- 장기 연구는 현재 paper 운영 backlog와 분리한다.

### 상태 분류

- `COMPLETE`: 코드, 테스트, 계약, 필요한 운영 evidence가 완료 조건을 충족한다.
- `PARTIAL`: 유용한 subset은 구현됐지만 initiative 전체 완료 조건은 충족하지 않는다.
- `DOCUMENTED_ONLY`: 문서 또는 관행만 있고 실행 가능한 구현·검증이 없다.
- `MISSING_NEEDED`: 현재 목표에 필요하지만 canonical 구현이 없다.
- `MISSING_OPTIONAL`: 있으면 유용하지만 현재 운영의 필수 조건은 아니다.
- `DUPLICATE`: 기존 owner가 목적을 이미 담당하므로 별도 계층을 만들지 않는다.
- `DEFERRED`: 선행조건이나 별도 승인이 필요한 장기 항목이다.
- `DROP`: 현재 방향과 충돌하거나 안전상 채택하지 않는다.

`PARTIAL`은 기능 전체가 아니라 확인된 subset만 의미한다. 문서 존재, interface 선언, 테스트 일부, 과거 산출물만으로 `COMPLETE`로 올리지 않는다. 실제 운영 상태와 구현 capability도 분리한다.

### 우선순위 평가 축

우선순위는 다음을 함께 본다.

1. 데이터·계좌 격리와 fail-closed 안전성
2. 현재 paper lifecycle의 미완료 운영 단계
3. 재현성, 관측성, 회귀 방지
4. 확장 전에 닫아야 할 신뢰성 계약
5. 사용자 의사결정 가치와 구현 비용
6. 기존 owner와의 중복 여부

성과를 높이기 위한 전략 변경은 Research Gate와 별도 승인을 거친다. live broker 주문은 이 로드맵 범위가 아니다.

## C. 현재 시스템과 Source of Truth

StockScreener는 안전성을 우선하는 paper-trading 운영 시스템이다. 검증된 계좌 범위에서는 Daily Plan, Manual Execution, reconciliation, review, reporting, A-F runbook과 recovery를 수행할 기반이 있다. 이는 live-ready, 무인 write 자동화, 모든 계좌·전략 확장 완료를 뜻하지 않는다.

Source of Truth 역할은 다음과 같이 고정한다.

- **계좌 범위의 local CSV/JSON/Markdown/SQLite artifact**가 기능적 Source of Truth다.
- **Python**이 validation과 business judgment를 담당한다.
- **Notion**은 staging/input/review/presentation 계층이다.
- **n8n/Telegram**은 allowlist된 orchestration/notification만 담당한다.
- Notion, n8n 또는 Telegram을 원장이나 trading judgment engine으로 승격하지 않는다.

### 현재 허용

- 검증된 paper 계좌와 현재 Windows wrapper/runbook
- as-of 계약을 지키는 Daily Plan
- Manual Execution을 통한 공식 paper execution
- local 및 Notion 기반 review/staging 흐름
- 승인된 Gate와 A-F lifecycle, evidence 검증, recovery 및 rollover
- 일간·주간 report와 현재 exploratory initial-capital benchmark

### 현재 확대하거나 활성화하지 않음

- 검증되지 않은 계좌/profile의 광범위한 확대
- strategy/risk/universe profile 대량 추가
- Telegram 승인만으로 시작되는 write 실행
- n8n 내부 business/trading judgment
- live broker 또는 real-order 연동

## D. 2026-09-05 구현 기준선

기존 검증 기준 `4fdb9b0…` 이후 현재 코드 HEAD `e840344…`까지의 변경을 대조한 현재 판정이다.

### 완료된 계약

- **MFU-EO2 execution outcome contract — COMPLETE**: pure outcome derivation, invalid-context fail-closed, finalize/commit 소비 계약과 zero-count downstream compatibility가 구현·회귀 테스트로 고정됐다. 핵심 근거는 `core/execution_reconciliation.py`, `core/execution_outcome_flow.py`, `scripts/runbook_state.py`, 관련 `tests/test_execution_outcome_*.py`다.
- **Stage A official AS-OF scope — COMPLETE**: source별 cutoff/provenance, immutable universe/config, fail-closed 계약이 `core/stage_a_asof_contract.py`, `core/daily_plan_generator.py`, `tests/test_stage_a_asof_contract.py`에 반영됐다.
- **Runbook recovery contract — COMPLETE**: 승인 토큰, workspace/context 제한, immutable state transition, deny/fail-closed 경로가 `core/runbook_recovery.py`, `tests/test_runbook_recovery.py`에 구현됐다.
- **Recovery restart/repeated lifecycle contract — 좁은 계약 COMPLETE**: missed-operating-day equality guard, 유효한 unconsumed authorization 선택, 반복 Recovery 뒤 정상 rollover 복귀가 코드·운영 계약·Recovery/rollover 회귀 테스트로 고정됐다. 실제 운영 Recovery 재실행은 하지 않았다.
- **Stage F historical completion evidence hardening — COMPLETE**: 과거 completion evidence 보존과 strict validation/self-heal 경로가 Stage F evidence 및 회귀 테스트에 반영됐다.
- **Daily Plan NO_ACTION count contract — 좁은 계약 COMPLETE**: canonical `execution_intent.candidate_execution_count`를 거래 건수 SSOT로 사용하고 placeholder를 거래·경고로 세지 않도록 수정했으며 exporter/CLI 테스트와 실제 2026-09-01 fixture dry-run으로 확인했다. 실제 Notion page backfill은 하지 않았다.

### 완료된 운영 기반

- 시장 데이터, as-of universe, 기술 screening과 ensemble 기반
- 결정론적 market regime, safety trigger, cash/hedge/sizing/long-position cap 정책
- paper ledger, valuation, snapshot, report와 account-aware 경로 기반
- Manual Execution, reconciliation, commit/status sync와 Manual Review 흐름
- read-only Daily Ops Orchestrator, operator summary, fixed A-F runbook과 정상 운영용 5-wrapper Primary facade
- idempotency, no-action lifecycle, strict completion evidence와 rollover/day preparation

### 부분 완료 기반

- Account-aware path와 guard는 폭넓게 구현됐지만 모든 legacy default fallback이 제거되지는 않았다.
- Replay diff와 fingerprint는 구현됐지만 stable action identity와 대표 non-empty corpus가 닫히지 않았다.
- Notion schema/options 검증은 구현됐지만 view drift는 수동 evidence에 의존한다.
- Primary 5-wrapper facade, V2 EXECUTION Finalize 통합, NO_ACTION 안내는 구현·테스트됐지만 실제 Windows `.cmd`의 EXECUTION 운영 경로와 credential 환경은 확인하지 못했다.
- IS/OOS optimizer, paper performance, benchmark, HWM, event/alert, Notion UI는 각 capability의 일부만 충족한다.

### 완료 판정 원칙

완료된 좁은 계약을 더 큰 initiative 전체 완료로 확대 해석하지 않는다. 예를 들어 Stage A lineage 완료는 `DQ-01` 전체 완료가 아니며, account-aware path 존재는 `ACCT-01` 또는 `PF-01` 전체 완료가 아니다.

## E. 최신 실제 Paper Ops 상태

### 실제 확인된 상태

account profile/path 계약과 `runbook_states/`의 수정 시각·frozen context를 대조해 최신 `paper_pilot_202606` 상태 파일을 문서 수정 중 읽기 전용으로 재확인했다.

| 항목 | 실제 값 | 판정 |
|---|---|---|
| Account | `paper_pilot_202606` | frozen context 고정 |
| Data date / Trade date | `2026-09-04` / `2026-09-08` | 날짜 범위 고정 |
| Runbook day ID | `paper_pilot_202606_2026-09-04_2026-09-08` | state와 evidence scope 일치 |
| Stage / Gate | A, Gate 1, B, C, Gate 2, D, E, F 모두 `PASS` | 완료 |
| Action mode | `NO_ACTION`, candidate 0건, execution/review 불필요 | zero-write 경로 |
| Execution contract | `execution_reconciliation_preview.v2` | v2 적용 |
| Actual input finalize | `input_finalized=false` | NO_ACTION이므로 Finalize 불필요, Gate 1 `PASS` |
| Completion | Stage F `PASS`, `completion_mode=NO_ACTION` manifest 존재 | 완료 |
| State updated_at | `2026-09-05T09:12:57.456763+09:00` | 최신 state 기준 |

근거 파일은 다음과 같다.

```text
D:\n8n\workspace\stock_screener_ops\runbook_states\paper_pilot_202606_2026-09-04_2026-09-08.json
D:\n8n\workspace\stock_screener_ops\artifacts\paper_pilot_202606_2026-09-04_2026-09-08\stage_a\daily_action_plan_20260908.json
D:\n8n\workspace\stock_screener_ops\completion_manifests\paper_pilot_202606_2026-09-04_2026-09-08.json
```

이 snapshot에는 현재 미완료 Stage/Gate가 없다. 과거 2026-08-24 snapshot은 현재 상태로 사용하지 않는다.

### 확인하지 못한 상태

실제 Notion page의 현재 저장값과 view의 시각적 일치, n8n·Telegram 상태, broker/order 외부 상태, 5개 Primary `.cmd`가 이 run에 사용됐는지는 확인하지 못했다. workspace의 `context.json`은 `paper_orch_smoke_202606` smoke context를 가리키므로 최신 pilot 상태의 근거로 사용하지 않았다. 확인하지 못한 외부 상태는 추측하지 않고 미검증으로 남긴다.

### 다음 운영 행동

현재 run은 완료됐으므로 추가 Stage/Gate 조치는 없다. 다음 승인된 운영 시점에 일반 rollover/day preparation으로 새 context를 준비하고, Recovery는 실제 incomplete lifecycle이 확인될 때만 별도 승인 절차로 사용한다. 이 문서 작업에서는 Stage/Gate, wrapper, Recovery, rollover, Notion write를 실행하지 않았다.

## F. 공식 우선순위

아래 표가 유일한 공식 실행 순서다. 같은 band 안에서는 위에서 아래 순서를 따른다.

### P0

현재 확인된 미완료 운영 lifecycle은 없다. 완료된 2026-09-08 NO_ACTION run을 현재 P0로 유지하지 않는다.

### P1

기존 공식 P1인 `ACCT-01`, `REPLAY-01`, `NOTION-02`의 순서를 보존한다.

### 후속 단계

| 순서 | Band | Initiative | 다음 종료 조건 / 의존성 |
|---:|---|---|---|
| 1 | P1 신뢰성 | `ACCT-01` | 모든 writer/reader/export/replay가 명시적 account root를 검증하고 조용한 legacy `paper_test` fallback을 제거한다. 다계좌 확대 blocker다. |
| 2 | P1 신뢰성 | `REPLAY-01` | stable action identity와 동일 symbol/action 중복을 포함한 non-empty replay corpus로 순서 독립 matching을 입증한다. replay 기반 자동화 blocker다. |
| 3 | P1 신뢰성 | `NOTION-02` | read-only schema/options/mapping preflight와 문서화된 view-drift 점검·FAIL/WARNING 대응을 운영 주기에 고정한다. Notion 의존 확대 blocker다. |
| 4 | P2 운영 품질 | `OPS-04` -> `OBS-01` | retention/run index와 SLO/관측성을 먼저 고정해 실패·복구 evidence를 검색 가능하게 한다. |
| 5 | P2 회귀 방지 | `TEST-01` | side-effect 분류와 격리가 입증된 suite부터 안전한 CI에 올린다. |
| 6 | P2 read-only 자동화 | `AUTO-03` -> `AUTO-01` | read-only scheduling과 deployment/run evidence만 자동화한다. write stage 승인은 유지한다. |
| 7 | P3 사용자 비교 | `BENCH-02` | cash-flow, dividend, fee, fractional-share 정책 승인 후 월적립식 SPY 비교를 설계·구현한다. |
| 8 | P4 연구 기반 | `RG-01` -> `BT-01` | executable Research Gate를 만들고 IS/OOS를 walk-forward, plateau, cost/slippage/delay stress까지 확장한다. |
| 9 | P4 데이터/설명 | `DQ-01` -> `PA-01` | 전체 데이터 lineage 계약을 좁은 MFU로 확장한 뒤 attribution 합계와 총손익 reconciliation을 구현한다. |
| 10 | P5 확장 모델 | `PF-01` -> `RS-01` | `strategy_id` 귀속과 strategy-account ledger를 먼저 고정한 뒤 strategy/account HWM·drawdown을 영속화한다. |
| 11 | P6 소비 계층 | `EV-01` -> `UI-01` | 공통 event/read model을 먼저 정의하고 read-only 운영 화면을 확장한다. |
| 12 | P7 선택/장기 | `RF-01` -> `DA-01` -> `FA-01` | 검증 가능한 source와 Research Gate가 생긴 뒤 독립 MFU로 재평가한다. 현재 운영 blocker가 아니다. |

`VA-01`과 `MR-01`은 별도 신규 계층으로 실행 순서에 넣지 않는다. 각각 기존 validation owner와 market-regime core가 목적을 담당한다. 확인된 좁은 누락만 기존 owner에서 보완한다.

### 확장 차단 조건

- 다계좌/profile 확대 전 `ACCT-01`
- replay 의존 write 자동화 전 `REPLAY-01`
- Notion 의존 범위 확대 전 `NOTION-02`
- write scheduler 또는 Telegram execution 검토 전 retention, observability, safe CI와 별도 threat model

## G. 통합 Capability 카탈로그

| 코드 | 기능 | 현재 판정 | 확인된 subset과 남은 경계 |
|---|---|---|---|
| `ACCT-01` | Multi-account vertical slice | PARTIAL | account profile/path/guard와 account-scoped Stage F는 있음. 기본 계좌의 legacy root fallback과 전 경로 closure가 남음. |
| `REPLAY-01` | Stable action replay | PARTIAL | plan diff, fingerprint, account/date validation은 있음. `symbol\|action` 중복의 고유 identity와 non-empty corpus가 남음. |
| `NOTION-02` | Schema/view drift guard | PARTIAL | 여러 data source의 property/type/select option validator와 Daily Plan semantic count guard는 있음. 실제 Notion page/view drift는 API 검증이 아닌 수동 spec/checklist 범위. |
| `RG-01` | Research Gate | DOCUMENTED_ONLY | MFU 계약/Result/Review 관행은 있으나 executable 판정기와 공통 KEEP/REFINE/OVERFIT/REJECT 증거가 없음. |
| `BT-01` | 백테스트 강건성 | PARTIAL | IS/OOS와 OOS 재검증은 있음. walk-forward, plateau, 대체 universe, 비용/지연 stress 승격 계약이 없음. |
| `DQ-01` | 데이터 품질·계층 계약 | PARTIAL | Stage A source cutoff/provenance는 완료. 전체 데이터의 canonical lineage metadata 강제는 없음. |
| `VA-01` | 검증 범위/Preflight | DUPLICATE | Stage/Gate/preflight/recovery가 이미 담당. 별도 대형 validation layer는 만들지 않음. |
| `PA-01` | 성과 귀속 | PARTIAL | 종목 P&L, equity/MDD, benchmark excess return은 있음. cash/hedge/cost/timing attribution 합계 계약이 없음. |
| `PF-01` | 다계좌·다전략 모델 | PARTIAL | account-aware 기반은 있음. `strategy_id`, binding, 동일 종목의 전략별 내부 수량 원장이 없음. |
| `RS-01` | HWM/drawdown 위험 상태 | PARTIAL | position HWM/MDD와 미래행 배제는 있음. strategy/account cycle 및 수동 변경 정책이 없음. |
| `EV-01` | 실행 이벤트 표준 | PARTIAL | runbook result/history/alert는 있음. 공통 `event_id/run_id/type/version/severity/payload` 계약이 없음. |
| `UI-01` | Notion + read-only dashboard | PARTIAL | Notion 운영 화면/upsert/reconciliation은 있음. 표준 DB Read Model 기반 GUI는 없음. |
| `MR-01` | Market Regime 점수 | DUPLICATE | 기존 trend/breadth/drawdown/VIX 기반 결정론적 regime core가 목적을 충족. 두 번째 모델은 금지. |
| `RF-01` | Risk Flag | MISSING_OPTIONAL | 개별 guard/alert는 있으나 source/expiry/severity를 갖는 canonical 투자 flag taxonomy는 없음. |
| `DA-01` | 외부 데이터 adapter | DEFERRED | 현재 provider는 동작. provider capability/fallback/provenance adapter는 DQ 이후 재검토. |
| `FA-01` | 기업가치 분석 | DEFERRED | 기본 financials 구조 외 point-in-time ETL, valuation, 독립 backtest가 없음. 별도 research track. |
| `OPS-04` | Artifact retention/run index | PARTIAL | artifact와 evidence는 풍부하지만 공통 보존·검색 정책이 완결되지 않음. |
| `OBS-01` | 운영 observability/SLO | PARTIAL | status/alert/operator summary는 있음. 공식 SLO와 run-level 추세 관측이 남음. |
| `TEST-01` | 안전한 CI | PARTIAL | 광범위한 테스트는 있음. side-effect 격리와 안정적 CI 승격이 남음. |
| `BENCH-02` | 월적립식 SPY benchmark | MISSING_NEEDED | 현재 initial-capital exploratory SPY/QQQ/CASH 비교와 구분. cash-flow 정책 승인부터 필요. |
| `AUTO-03` | Read-only scheduling | PARTIAL | read-only command 기반은 있음. 운영 scheduler evidence와 실패 정책 closure가 남음. |
| `AUTO-01` | Deployment/run evidence | PARTIAL | 정상 운영용 5-wrapper facade와 state 기반 fail-fast/resume은 있음. 실제 `.cmd`/credential 환경 실행과 재현 가능한 배포·실행 증거 표준화가 남음. |
| `CFG-01` | Config SSOT 정합성 | PARTIAL | `make_config()` 조립 계약은 있음. legacy 직접 참조는 점진적으로 정리. |
| `STRAT-04` | 전략 계약 정합성 | PARTIAL | 현재 전략은 운영 가능. 확장보다 기존 timing/contract 검증을 우선. |
| `EXP-01` | profile 확장 | DEFERRED | P1 신뢰성 공백을 닫은 뒤 account/universe/strategy/risk profile을 공식화. |
| `BT-02` | 차세대 simulator/WFO | DEFERRED | no-lookahead loader, hybrid simulator, rolling WFO는 장기 연구. |
| `FUND-01` | Fundamental/quality data | DEFERRED | point-in-time 데이터 계약과 Research Gate가 선행. |
| `UX-01` | Operator UX | PARTIAL | 5-wrapper Primary facade, V2 Finalize 통합, canonical NO_ACTION/preview 안내가 구현·테스트됨. 실제 EXECUTION 운영과 Windows `.cmd`/credential 환경 evidence가 남음. |
| `AUTO-02` | 승인 기반 Telegram execution | DEFERRED | read-only 운영과 승인 threat model 검증 전에는 활성화하지 않음. |

## H. 증거 성숙도

| 코드/범위 | 문서 | 구현 | 테스트 | 실제 운영 | 실패/복구 |
|---|---|---|---|---|---|
| MFU-EO2 | 있음 | 완료 | 있음 | v2 state 적용, 최신 NO_ACTION run은 Finalize 불필요 | invalid-context fail-closed |
| Stage A AS-OF | 있음 | 완료 | 있음 | 2026-09-08 plan `PASS` | cutoff/provenance fail-closed |
| Recovery | 있음 | 완료 | 있음 | 기존 activation evidence 있음, 반복 Recovery 운영 재실행은 미확인 | 승인·context·state guard와 consumed/unconsumed 분류 |
| `ACCT-01` | 있음 | 부분 | 있음 | account-scoped paper ops 사용 | path/context guard, legacy fallback 잔존 |
| `REPLAY-01` | 있음 | 부분 | 있음 | empty/limited replay evidence | duplicate key WARNING 및 auto-match 제외, stable identity 미완료 |
| `NOTION-02` | 있음 | 부분 | 있음 | Notion 흐름 사용 | schema fail/warning, view는 수동 |
| `UX-01` | 있음 | 부분 | Primary/gate/wrapper 관련 테스트 있음 | 최신 NO_ACTION run 완료, Primary `.cmd` 사용 여부는 미확인 | stage evidence 손상 시 fail-closed/recovery 안내 |
| `RG-01` | 있음 | 없음 | 없음 | 문서 관행만 있음 | 없음 |
| `BT-01` | 있음 | IS/OOS 부분 | smoke 부분 | 최근 공식 연구 run 미확인 | 실행 예외 처리 |
| `DQ-01` | 있음 | Stage A 부분 | 있음 | Stage A PASS | as-of fail-closed |
| `PA-01`~`UI-01` | 있음 | 각 subset | 관련 테스트 있음 | 일부 report/ops 사용 | owner별 guard, 공통 계약 미완료 |
| `RF-01`/`DA-01`/`FA-01` | 방향 있음 | canonical 구현 없음 | 없음 | 없음 | 없음 |

## I. 기능별 상세 평가

각 항목의 첫 문장은 **현재 판정과 우선순위**, 이어지는 문장은 **목적과 현재 증거**, **실제 gap과 완료 조건**, **선행조건 및 범위 아님**을 압축해 기록한다. 세부 코드·테스트 근거는 D와 H 및 MFU별 Result/Review Evidence에서 확인한다.

### ACCT-01

`PARTIAL`, P1. account profile/path/guard와 account-scoped evidence는 목적의 일부를 충족한다. 모든 plan/report/replay/alert/export/write가 같은 명시적 account context를 검증하고 조용한 legacy root fallback을 제거해야 완료다. 범위는 paper account 격리이며 무승인 DB migration은 포함하지 않는다.

### REPLAY-01

`PARTIAL`, P1. 현재 replay diff는 account/date/fingerprint와 row 차이를 검증하지만 `symbol|action` 중복은 고유하게 match하지 못한다. stable action identity, 순서 변경, 동일 symbol/date 복수 action과 non-empty corpus를 결정론적으로 검증해야 완료다. replay가 실제 execution을 대신하지 않는다.

### NOTION-02

`PARTIAL`, P1. property/type/select option validator, 운영 view spec과 Daily Plan semantic count guard는 존재한다. read-only 검증을 운영 주기에 고정하고 실제 page/view-drift evidence와 FAIL/WARNING 대응을 닫아야 완료다. Notion을 원장으로 승격하지 않는다.

### RG-01

`DOCUMENTED_ONLY`, P4. MFU 계약과 Result/Review 관행은 있으나 executable gate가 없다. 가설, as-of 데이터, 비용, 실패조건, OOS 결과를 공통 입력으로 받아 KEEP/REFINE/OVERFIT/REJECT 같은 승인된 판정과 evidence를 재현해야 완료다. 성과 보장이나 자동 최적화는 범위가 아니다.

### BT-01

`PARTIAL`, P4. IS/OOS와 OOS 재검증은 구현됐다. 사전 고정 split, rolling WFO, 주변값 plateau, 하위기간/대체 universe, fee/slippage/1일 지연 stress를 하나의 승격 계약에서 판정해야 완료다. 최고 결과 재선택은 강건성 검증이 아니다.

### DQ-01

`PARTIAL`, P4. Stage A AS-OF provenance는 완료됐지만 전체 데이터 계약은 아니다. 핵심 데이터에 `source`, `as_of_date`, `fetched_at`, `timezone`, `currency`, `frequency`, `adjustment_basis`, `schema_version`, `run_id`를 필요한 범위에서 기계 추적해야 완료다. 특정 provider를 절대적 진실로 간주하지 않는다.

### PA-01

`PARTIAL`, P4. 종목 P&L, equity/MDD, benchmark excess return은 있다. 종목, cash, hedge, fee, timing/selection contribution 합계가 총손익과 허용오차 내 reconcile해야 완료다. 설명되지 않은 잔여를 자동으로 alpha라 부르지 않는다.

### PF-01

`PARTIAL`, P5. account identity는 있으나 strategy attribution이 없다. 모든 내부 position/trade가 account와 strategy에 귀속되고 외부 계좌와 내부 전략 원장을 각각 reconcile해야 완료다. broker 잔고에서 전략별 수량을 역추정하지 않는다.

### RS-01

`PARTIAL`, P5. position HWM/MDD와 미래행 배제는 있다. position cycle, 추가매수, 일부매도, 수동 변경, 재시작의 kept/reset/new/deleted 정책과 strategy/account HWM을 고정해야 완료다. `PF-01` identity가 선행한다.

### EV-01

`PARTIAL`, P6. runbook result/history/alert는 구조화됐지만 공통 event 계약은 없다. 소비자가 문자열을 재해석하지 않는 versioned schema와 `event_id/run_id/type/version/severity/payload` 및 중복 방지를 제공해야 완료다. 모든 debug log의 이벤트화는 범위가 아니다.

### UI-01

`PARTIAL`, P6. Notion 운영 화면/upsert/reconciliation은 실제 사용되지만 표준 DB Read Model GUI는 없다. 계좌·계획·실행·reconciliation·경고·성과를 표준 read model로 읽기 전용 조회해야 완료다. 주문 입력이나 Notion 대체 문서 기능은 범위가 아니다.

### MR-01

`DUPLICATE`. 기존 trend/breadth/drawdown/VIX 기반 결정론적 core가 현재 목적을 담당한다. 추가 분석은 원시 trigger와 성과 귀속으로 수행하며 별도의 두 번째 투자 판단 모델을 만들지 않는다.

### RF-01

`MISSING_OPTIONAL`, P7. 개별 guard/alert와 canonical investment flag는 다르다. 각 flag의 source, 유효기간, severity, 해제 조건과 오탐/미탐 평가가 있어야 완료이며, 검증 전 자동 매도·제외에 사용하지 않는다.

### DA-01

`DEFERRED`, P7. 기존 provider는 동작하지만 공통 adapter는 없다. provider 차이와 fallback을 숨기지 않고 raw provenance와 canonical schema를 보존해야 완료다. 현재 가격 계층을 근거 없이 교체하지 않는다.

### FA-01

`DEFERRED`, P7. 기본 financials 구조 외 point-in-time ETL과 valuation/research evidence가 없다. 독립 backtest와 Research Gate 통과 뒤에만 hybrid 후보가 된다. 현재 기술 신호에 검증 없이 혼합하지 않는다.

### 필요한 기존 initiative

`OPS-04`, `OBS-01`, `TEST-01`, `BENCH-02`, `AUTO-03`, `AUTO-01`, `CFG-01`, `STRAT-04`, `EXP-01`, `BT-02`, `FUND-01`, `UX-01`, `AUTO-02`의 판정·경계는 G 카탈로그와 F 공식 순서를 따른다. `UX-01`은 이번 범위에서 `PARTIAL`로 올라갔지만 P1 종료 조건을 충족하거나 별도 우선순위 항목이 된 것은 아니다. 신규 backlog로 중복 생성하지 않는다.

## J. 제외·보류·독립 연구

| 항목 | 결정 |
|---|---|
| 별도 대형 Validation layer (`VA-01`) | `DROP` as new layer. 확인된 누락만 기존 owner에 추가한다. |
| 두 번째 Market Regime 모델 (`MR-01`) | `DROP` as duplicate. 기존 core의 원시값/귀속을 개선한다. |
| CSV-only market database | Historical. SQLite 기반으로 대체됐다. |
| n8n 내부 business/trading judgment | `DROP`. Python이 judgment engine이다. |
| `paper_virtual_fill`을 공식 operator 경로로 사용 | Historical compatibility only. Manual Execution이 공식 경로다. |
| Live broker integration | 현재 paper 목표에서는 `DEFER/DROP_CANDIDATE`. 별도 safety program 승인 없이는 재개하지 않는다. |
| 성과 개선 목적의 무승인 전략 변경 | 금지. Research Gate와 별도 실험 계약이 필요하다. |
| 복잡한 주문 접수·체결 상태 머신 | 현재 paper 목표에서 제외. 실제 필요와 별도 계약이 생길 때 재평가한다. |
| 장중 가격 기반 투자 판단 | 현재 date/as-of 운영 경계 밖이다. |
| ProgramGarden 전체 노드 DSL | 패턴 전체 복제는 하지 않는다. 필요한 owner contract만 좁게 채택한다. |
| 주문 기능이 포함된 대형 GUI | read-only UI 검증 전에는 만들지 않는다. |
| 검증되지 않은 Telegram write execution | 금지. allowlisted notification/read-only 역할만 유지한다. |

## K. 단계별 공식 개발 순서

F의 공식 우선순위 표를 단계 의존성으로 읽으면 다음과 같다.

```text
ACCT-01 -> REPLAY-01 -> NOTION-02
-> OPS-04/OBS-01 -> TEST-01 -> AUTO-03/AUTO-01
-> BENCH-02
-> RG-01/BT-01 -> DQ-01/PA-01
-> PF-01/RS-01 -> EV-01/UI-01
-> 선택·장기 연구
```

- 현재 확인된 미완료 run은 없으며, 새 lifecycle이 생기면 그 운영 closeout을 해당 시점의 P0로 다시 평가한다.
- P1 세 항목은 현재 검증 계좌 사용을 막지는 않지만 다계좌, replay 의존 자동화, Notion 의존 확대를 각각 차단한다.
- retention/observability와 safe CI는 자동화 범위를 넓히기 전에 실패 evidence를 보존한다.
- `BENCH-02`는 현재 exploratory benchmark를 대체하지 않고 별도 cash-flow contract로 추가한다.
- Research Gate가 전략 성능을 보장하거나 최고 parameter를 자동 선택하지 않는다.
- `PF-01`이 strategy attribution identity를 정하기 전에 `RS-01`을 다전략으로 확장하지 않는다.
- 공통 event/read model 없이 consumer별 dashboard parsing을 늘리지 않는다.

## L. 사용자 결정이 필요한 경계

다음은 구현 전에 별도 선택 또는 승인이 필요하다.

- legacy default account fallback 제거 시 호환성/전환 기간
- 월적립식 benchmark의 납입 시점, 금액, dividend, fee, fractional-share, 휴장일 정책
- Research Gate의 승격 판정 이름과 필수 threshold
- DB schema 변경이나 대량 backfill이 필요한 `PF-01`, `DQ-01` 설계
- risk flag의 신뢰 가능한 외부 source 및 자동 정책 반영 여부
- Telegram write approval threat model과 운영 권한
- live broker 연동을 별도 safety program으로 시작할지 여부

## M. 유지관리와 근거

1. 현재 상태와 우선순위는 이 파일 하나에서 관리한다.
2. 새 아이디어만으로 official backlog에 추가하지 않는다.
3. 상태 변경은 코드, 테스트, 계약, 필요한 실제 운영 evidence를 확인한 뒤 반영한다.
4. `COMPLETE`인 좁은 MFU를 상위 capability 전체 완료로 확대하지 않는다.
5. 상세 requirement/design은 initiative별 PRD/TRD에서 관리한다.
6. 변경 시 갱신일, 검증 HEAD, 비교 기준선, 영향 initiative를 기록한다.
7. 과거 상태는 Git history와 historical Result/Review Evidence로 보존한다.
8. `ROADMAP_CURRENT_v2.md`, `ROADMAP_FINAL.md`, 날짜별 current roadmap을 만들지 않는다.
9. 큰 phase 전환이나 저장소 전체 재평가에만 `SYSTEM-AUDIT-YYYYMMDD/`를 만든다.
10. 실제 운영 파일을 수정하거나 실행하지 않고 읽기 전용 evidence로만 인용한다.

현재 참고 근거:

- Operator/runbook: `docs/operations/paper_daily_cycle_commands.md`
- Notion view spec: `docs/operations/notion_view_spec_daily_plans_manual_executions_manual_reviews.md`
- System Audit: `docs_chatGPT_work/codex_results/SYSTEM-AUDIT-20260810/`
- MFU별 완료 증거: `docs/work_results/`
- 현재 구현과 테스트: `core/`, `scripts/`, `tests/`

문서 역할:

```text
ROADMAP_CURRENT.md       = 현재 상태, 범위, 공식 우선순위
SYSTEM-AUDIT-YYYYMMDD/   = 특정 시점의 저장소 전체 평가
initiative PRD/TRD       = 상세 requirement 및 implementation contract
Result/Review Evidence   = 완료 및 검증 증거
Git history              = ROADMAP_CURRENT의 과거 상태
```

# StockScreener 현재 로드맵 및 기능 기준선

- 상태: **공식 기준(Canonical)**
- 최종 갱신일: **2026-09-10**
- 기준 브랜치: `gemini_cli_update`
- 검증 기준 HEAD: `6588b7afddc95aec77d87e178cd6d30cd857c499`
- 로드맵 비교 기준선: `12d52f0cc5f366f58840e16c1400f0da89b832fb` (마지막 로드맵 내용 변경)
- 검증 범위: 이전 검증 시점 `e840344551691382f46ebb27dec71f4b1fd63567` 이후 위 HEAD까지의 Git 변경, 현재 코드·테스트·Result/Review Evidence 및 E의 Paper 실행 산출물. 운영 DB·계좌 state·runbook state는 읽거나 수정하지 않았다.
- 최신 확인 운영 산출물: `D:\n8n\workspace\stock_screener_ops\completion_manifests\paper_pilot_202606_2026-09-08_2026-09-09.json` (파일 수정 시각 `2026-09-09T22:07:51+09:00`; E의 확인 한계 적용)

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

목표는 재현 가능하고 fail-closed인 paper 투자 운영에서 계좌마다 전략 하나를 배정하고, 2개 이상의 계좌를 수동·순차 운영한 뒤 검증된 범위부터 자동화하는 것이다. 이를 위해 신뢰성 blocker 다음에 전략 설정 정합성과 최소 strategy/universe profile binding을 배치한다. 데이터 무결성, 수치 정합성, 운영 복구 가능성에 필요한 안전장치는 유지한다.

핵심 원칙:

- 실제 사용 evidence 없이 capability를 완료로 올리지 않는다.
- 현재 전략 성능을 높이기 위한 임의 변경보다 timing/as-of/reconciliation 계약을 우선한다.
- 같은 책임의 두 번째 validation, regime, ledger 계층을 만들지 않는다.
- 초기 계좌별 binding은 strategy profile 1개와 universe profile 1개이며, risk와 benchmark는 공통 계약을 사용한다. 한 계좌 내부의 다전략 수량 원장은 후순위다.
- write는 승인·preview·idempotency·evidence 경계를 유지하고 자동화는 read-only부터 확장한다.
- 새로운 전략 profile의 운영 등록에는 `BENCH-02`, `RG-01`, `BT-01` 검증을 요구한다. 기존 전략의 binding 구현을 신규 전략 승인으로 해석하지 않는다.
- 장기 연구는 현재 paper 운영 backlog와 분리한다.

### 상태 분류

- `COMPLETE`: 코드, 테스트, 계약, 필요한 운영 evidence가 완료 조건을 충족한다.
- `PARTIAL`: 유용한 subset은 구현됐지만 initiative 전체 완료 조건은 충족하지 않는다.
- `DOCUMENTED_ONLY`: 문서 또는 관행만 있고 실행 가능한 구현·검증이 없다.
- `MISSING_NEEDED`: 현재 목표에 필요하지만 canonical 구현이 없다.
- `MISSING_OPTIONAL`: 있으면 유용하지만 현재 운영의 필수 조건은 아니다.
- `DUPLICATE`: 기존 owner가 목적을 이미 담당하므로 별도 계층을 만들지 않는다.
- `DEFERRED`: 선행조건이나 별도 승인 때문에 구현을 보류한 항목이다. 우선순위 상승만으로 구현 상태가 바뀌지는 않는다.
- `DROP`: 현재 방향과 충돌하거나 안전상 채택하지 않는다.

`PARTIAL`은 기능 전체가 아니라 확인된 subset만 의미한다. 문서 존재, interface 선언, 테스트 일부, 과거 산출물만으로 `COMPLETE`로 올리지 않는다. 실제 운영 상태와 구현 capability도 분리한다.

### 우선순위 평가 축

우선순위는 다음을 함께 본다.

1. 데이터·계좌 격리와 fail-closed 안전성
2. 현재 paper lifecycle의 미완료 운영 단계
3. replay와 Notion 의존 확대 전에 닫아야 할 신뢰성 계약
4. 계좌당 전략 하나의 설정 정합성·binding과 두 계좌 수동·순차 검증
5. 재현성, 관측성, 회귀 방지, 사용자 의사결정 가치와 구현 비용
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
- 검증 전 strategy/universe profile 운영 등록 및 계좌별 독립 risk/benchmark profile 확대
- Telegram 승인만으로 시작되는 write 실행
- n8n 내부 business/trading judgment
- live broker 또는 real-order 연동

## D. 현재 구현 기준선

이전 검증 시점 이후 `6f1d420`의 Roadmap 동기화, `383f42e`/`7978595`/`0da9b0f`의 ACCT-01A/B/C, `12d52f0`의 D 격리 evidence 및 closeout 상태, `6588b7a`의 공통 개발 문서 추가를 대조했다. 이번 변경은 우선순위와 설명을 갱신하며 G의 capability 판정은 모두 유지한다.

### 완료된 계약

- **ACCT-01 — COMPLETE 유지**: canonical account context/path, writer 및 read/report/export/replay closure, A/B/legacy 격리 계약이 완료됐다. `core/paper_account_paths.py`, `core/paper_account_guard.py`, `tests/test_acct01d_isolation.py`와 `docs/work_results/ACCT-01D-ACCOUNT-ISOLATION-EVIDENCE_Review_Evidence.md`의 최종 PASS 및 A/B/C/D closeout 승인이 근거다. D의 기존 기록은 targeted `7 passed`, B/C focused `24 passed`, superset `319 passed, 3 failed`이며 3건은 기존 prepare-data mock signature의 `UNRELATED` 실패다. A/B/C 개별 문서의 당시 pending 표기는 이 최종 승인과 구분한다. migration과 profile binding, 두 계좌 실운영 완료를 포함하지 않는다.
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

- `ACCT-01`의 normal-path silent fallback은 닫혔고 explicit `paper_default` legacy read-only compatibility만 허용된다. 남은 다계좌 확장 범위는 `EXP-01`의 runtime binding과 두 계좌 운영 evidence다.
- Replay diff와 fingerprint는 구현됐지만 stable action identity와 대표 non-empty corpus가 닫히지 않았다.
- Notion schema/options 검증은 구현됐지만 view drift는 수동 evidence에 의존한다.
- `make_config()`는 `PORTFOLIO_CONFIG -> config.py -> params -> runtime_overrides`를 조립한다. 그러나 `screener/screener.py`의 `DEFAULT_PARAMS`, `STRATEGY_WEIGHTS`, 전역 `SCORE_THRESHOLD`는 별도 경로다. `core/daily_plan_generator.py`는 최종 설정을 조립한 뒤 screener에 market/date/tickers만 전달하므로 모든 지표·가중치·판단·sizing 설정이 하나의 runtime 계약으로 닫혔다고 볼 수 없다.
- `core/paper_account_profile.py`의 `strategy_profile`, `universe_profile`, `benchmark_profile`은 선택 문자열의 로드·정규화만 제공한다. 현재 코드·테스트 검색에서 전략/universe registry 검증이나 runtime 선택 소비자는 확인되지 않았다. config snapshot/hash는 있지만 실제 profile ID/version/fingerprint 적용·비교 계약은 미완료다.
- Primary 5-wrapper facade, V2 EXECUTION Finalize 통합, NO_ACTION 안내는 구현·테스트됐다. E의 V2 Paper execution commit 산출물은 추가 확인했으나 실제 Windows `.cmd` 사용과 credential 환경의 재현성은 확인하지 못했다.
- IS/OOS optimizer, paper performance, benchmark, HWM, event/alert, Notion UI는 각 capability의 일부만 충족한다.

### 완료 판정 원칙

완료된 좁은 계약을 더 큰 initiative 전체 완료로 확대 해석하지 않는다. Stage A lineage 완료는 `DQ-01` 전체 완료가 아니며, `ACCT-01` 격리 완료는 `EXP-01` profile binding 또는 `PF-01` 다전략 원장 완료가 아니다. 위 테스트 수치는 기존 evidence를 인용했으며 이번 문서 작업에서 재실행하지 않았다.

## E. 최신 실제 Paper Ops 상태

### 사용자 관찰과 확인 범위

사용자는 Paper 운영을 약 2주간 진행했고 중대한 문제를 경험하지 않았다고 보고했다. 이는 사용자의 운영 관찰이며, 전체 실행 횟수·성공률·무결점 안정성의 입증으로 취급하지 않는다.

이번에는 운영 DB와 계좌 state, runbook state를 열지 않고 completion manifest와 workspace 실행 산출물만 읽기 전용으로 확인했다. 해당 directory에서 확인한 최신 run은 다음과 같다.

| 항목 | 산출물 값 | 확인 범위 |
|---|---|---|
| Account / Runbook day ID | `paper_pilot_202606` / `paper_pilot_202606_2026-09-08_2026-09-09` | plan・commit・manifest의 account/date 일치 |
| Data date / Trade date | `2026-09-08` / `2026-09-09` | 산출물에 기록된 날짜 |
| Action mode | `EXECUTION`, candidate 3건 (BUY 1, SELL 2) | Daily Plan intent와 items 일치 |
| Paper execution | `COMMITTED`, `committed_row_count=3`, broker `PAPER` | Stage B commit report 기록; 원장 재조회는 하지 않음 |
| Execution contract | `execution_commit.v2`, `execution_reconciliation_preview.v2` | Stage B report 버전 |
| EOD | `COMMITTED`, `accounting_close`, fail/failed/blocked count 모두 0 | Stage E report 기록 |
| Completion | `completion_mode=STANDARD`, execution 3행・review 14행 기록 | manifest 존재; 전체 원본 digest 재검증은 하지 않음 |
| Plan digest | workspace plan SHA-256와 manifest의 workspace digest 일치 | 해당 plan 파일만 직접 대조 |

근거 파일 (공통 workspace root: `D:\n8n\workspace\stock_screener_ops`):

```text
artifacts/paper_pilot_202606_2026-09-08_2026-09-09/stage_a/daily_action_plan_20260909.json
artifacts/paper_pilot_202606_2026-09-08_2026-09-09/stage_b/manual_execution_import_commit_20260909.json
artifacts/paper_pilot_202606_2026-09-08_2026-09-09/stage_e/paper_eod_commit_20260909.json
completion_manifests/paper_pilot_202606_2026-09-08_2026-09-09.json
```

최근 수정된 manifest 6개 표본의 trade date는 09-01, 09-02, 09-03, 09-04, 09-08, 09-09다. `STANDARD` 3개는 execution row count 3・1・3, `NO_ACTION` 3개는 0으로 기록되어 있다. 따라서 최신 상태를 NO_ACTION으로만 표현하지 않는다. 이 표본은 전체 운영 횟수나 성공률이 아니며, NO_ACTION evidence를 매매·체결·복구 검증으로 확대하지 않는다. 이전 09-08 NO_ACTION snapshot은 과거 이력으로 보존한다.

### 확인하지 못한 상태

현재 계좌 잔고·포지션·원장과 manifest의 일치, 전체 Stage/Gate의 현재 state, 최신 운영을 생성한 코드 SHA, Notion page/view의 현재 상태, n8n·Telegram·broker 상태와 Primary `.cmd` 사용 여부는 확인하지 않았다. 두 계좌의 profile별 수동·순차 운영, 실행 순서 독립성, 반복 Recovery 운영 evidence도 미확인이다. 하나의 Paper commit 산출물을 이 경계들의 완료 근거로 사용하지 않는다.

### 다음 운영 행동

검토한 최신 run에는 완료 manifest가 있다. 다음 운영 시작 시 현재 lifecycle과 승인된 rollover/day preparation 조건을 확인하고, 실제 incomplete lifecycle이 확인될 때만 Recovery 절차를 적용한다. 이 문서 작업은 운영 실행이나 다음 Phase/MFU 시작을 승인하지 않는다.

## F. 공식 우선순위

아래 표가 유일한 공식 실행 순서다. 같은 band 안에서는 위에서 아래 순서를 따른다.

### P0

검토한 완료 산출물에서 새 P0를 확인하지 못했다. runbook state를 재조회하지 않았으므로 모든 미완료 lifecycle이 없다고 단정하지 않는다. 새 운영 blocker가 확인되면 우선 평가한다.

### P1

`ACCT-01`은 closeout 완료로 현재 P1 실행 항목에서 제외한다. `REPLAY-01`, `NOTION-02`는 신뢰성 blocker로 유지한다. 이후 설정 정합성과 최소 binding을 운영 품질·자동화보다 앞당긴다.

### 후속 단계

| 순서 | Band | Initiative | 목적・선행조건・완료 기준 |
|---:|---|---|---|
| 1 | P1 신뢰성 | `REPLAY-01` | ACCT 격리 기반에서 재현성을 닫는다. stable action identity, 동일 symbol/action 복수 행의 결정론적 구분, 순서 독립 matching, 대표 non-empty corpus와 account/profile fingerprint 비교를 입증한다. |
| 2 | P1 신뢰성 | `NOTION-02` | replay 다음에 Notion 의존 확대를 준비한다. property/type/select option read-only preflight, account/run mapping, view drift 확인 절차와 FAIL/WARNING별 publish·후속 동작 정책을 운영 evidence로 닫는다. |
| 3 | P2 설정 계약 | `CFG-01` -> `STRAT-04` | P1 다음, profile 구현 전에 설정 SSOT와 runtime 적용 경계를 닫는다. 전략 종류·지표·가중치·매수/매도·포지션 크기 및 설정 version/fingerprint가 실제 소비값과 일치해야 한다. |
| 4 | P2 최소 binding | `EXP-01` 최소형 | 설정 계약 이후 account별 strategy/universe 각 1개를 연결한다. 미존재 profile 실행 차단, 실행 evidence의 ID/version 또는 fingerprint와 공통 risk/benchmark 계약을 구현·검증한다. |
| 5 | P2 운영 검증 | `EXP-01` 완료 evidence | binding 이후 두 계좌를 수동·순차 운영한다. 현금·포지션·체결·보고서 격리와 실행 순서 독립성을 입증한다. 신규 code를 만들지 않으며 신규 전략 등록에는 9번 검증이 선행한다. |
| 6 | P3 운영 품질 | `OPS-04` -> `OBS-01` | 두 계좌 evidence를 바탕으로 retention/run index와 SLO/관측성을 고정한다. 실패·복구 evidence의 보존·검색과 run별 추적이 가능해야 한다. |
| 7 | P3 회귀 방지 | `TEST-01` | 운영 계약·관측성 이후 side-effect를 분류·격리한다. 승인 없는 DB/외부 write 없이 관련 suite를 반복 실행하는 안전한 CI를 입증한다. |
| 8 | P3 read-only 자동화 | `AUTO-03` -> `AUTO-01` | 안전한 CI와 관측성 이후 점검·리포트 scheduling 및 배포/run evidence를 자동화한다. read-only allowlist, 실패 대응과 재실행 evidence를 닫고 write stage 승인을 유지한다. |
| 9 | P4 전략 검증 | `BENCH-02` -> `RG-01` -> `BT-01` | 공통 benchmark의 cash-flow 정책 승인 후 비교와 executable Research Gate, IS/OOS・walk-forward・plateau・비용/지연 stress를 닫는다. 새로운 전략 profile 운영 등록의 필수 검증이다. |
| 10 | P4 데이터/설명 | `DQ-01` -> `PA-01` | 연구 검증 기반 이후 데이터 lineage와 성과 설명을 확장한다. source/as-of 추적 및 attribution 합계와 총손익 reconciliation을 입증한다. |
| 11 | P5/P6 후속 확장 | write 자동화 / `AUTO-02`, `EV-01` -> `UI-01` | replay·운영 evidence·실패 정책 closure와 write 권한 승인이 선행한다. 승인·preview·idempotency를 유지한 실행 검증과 공통 event/read model 기반 소비 계층을 각각 닫는다. |

`PF-01 -> RS-01`은 한 계좌 안의 다전략 운용이 필요할 때 수행하는 후순위 확장이다. 계좌당 전략 하나인 현재 목표나 `EXP-01`의 선행조건으로 두지 않는다. `RF-01 -> DA-01 -> FA-01`, `BT-02`, `FUND-01`은 검증 가능한 source와 Research Gate 이후의 선택·장기 연구로 유지한다.

`VA-01`과 `MR-01`은 별도 신규 계층으로 실행 순서에 넣지 않는다. 각각 기존 validation owner와 market-regime core가 목적을 담당한다. 확인된 좁은 누락만 기존 owner에서 보완한다.

### 확장 차단 조건

- `ACCT-01`은 완료됐다. 실제 `paper_default` migration은 별도 승인·후속 작업이며 미수행 상태다.
- `REPLAY-01`, `NOTION-02`는 각각 replay 의존 자동화와 Notion 의존 확대의 신뢰성 blocker다.
- profile 구현 전 `CFG-01 -> STRAT-04`; 다계좌 운영 확대 전 `EXP-01` binding과 두 계좌 수동·순차 evidence가 필요하다.
- 계좌별 독립 `risk_profile`/`benchmark_profile`은 보류하고 공통 계약을 유지한다.
- 새로운 전략 profile 운영 등록 전 `BENCH-02 -> RG-01 -> BT-01` 검증이 필요하다. 4~5번은 기존 전략의 binding 검증이며 신규 전략 연구를 건너뛰는 경로가 아니다.
- read-only 자동화 전 retention/observability와 safe CI; write 자동화 활성화 전 replay·운영 evidence·실패 정책 closure와 명시적 권한 승인이 필요하다. Telegram execution에는 별도 threat model이 필요하다.

## G. 통합 Capability 카탈로그

| 코드 | 기능 | 현재 판정 | 확인된 subset과 남은 경계 |
|---|---|---|---|
| `ACCT-01` | Multi-account vertical slice | COMPLETE | A/B/C/D 계약과 isolation regression이 PASS했다. 명시적 legacy read-only compatibility만 남기고 writer/reader/export/replay의 silent fallback을 폐쇄했다. `paper_default` migration은 별도 미수행 작업이다. |
| `REPLAY-01` | Stable action replay | PARTIAL | plan diff, config/universe fingerprint, account/date validation은 있음. 중복 key는 `STATUS_WARNING` 및 auto-match 제외. stable identity・순서 독립 matching・대표 non-empty corpus・account/profile fingerprint 비교가 남음. |
| `NOTION-02` | Schema/view drift guard | PARTIAL | property/type/select option validator와 semantic count guard는 있음. account/run mapping 및 publish/후속 동작의 FAIL/WARNING 정책을 운영 주기에 고정해야 하며 view drift는 수동 spec/checklist 범위. |
| `RG-01` | Research Gate | DOCUMENTED_ONLY | MFU 계약/Result/Review 관행은 있으나 executable 판정기와 공통 KEEP/REFINE/OVERFIT/REJECT 증거가 없음. |
| `BT-01` | 백테스트 강건성 | PARTIAL | IS/OOS와 OOS 재검증은 있음. walk-forward, plateau, 대체 universe, 비용/지연 stress 승격 계약이 없음. |
| `DQ-01` | 데이터 품질·계층 계약 | PARTIAL | Stage A source cutoff/provenance는 완료. 전체 데이터의 canonical lineage metadata 강제는 없음. |
| `VA-01` | 검증 범위/Preflight | DUPLICATE | Stage/Gate/preflight/recovery가 이미 담당. 별도 대형 validation layer는 만들지 않음. |
| `PA-01` | 성과 귀속 | PARTIAL | 종목 P&L, equity/MDD, benchmark excess return은 있음. cash/hedge/cost/timing attribution 합계 계약이 없음. |
| `PF-01` | 다계좌·다전략 모델 | PARTIAL | account-aware 기반은 있음. 한 계좌 내부의 다전략 `strategy_id` 귀속과 동일 종목별 내부 수량 원장은 미완료. `EXP-01`의 계좌당 단일 전략 binding과 구분하며 후순위. |
| `RS-01` | HWM/drawdown 위험 상태 | PARTIAL | position HWM/MDD와 미래행 배제는 있음. strategy/account cycle 및 수동 변경 정책은 미완료. 다전략 확장은 PF 이후이며 초기 공통 risk contract의 선행조건은 아님. |
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
| `CFG-01` | Config SSOT 정합성 | PARTIAL | `make_config()`와 snapshot/hash는 있음. screener의 별도 지표·가중치·threshold와 최종 소비값의 SSOT/version/fingerprint 정합성은 미완료. profile보다 선행. |
| `STRAT-04` | 전략 계약 정합성 | PARTIAL | 현 전략 subset은 운영 중. 종류·지표·가중치·매수/매도·sizing의 runtime 적용 및 timing 계약을 CFG 다음, profile 전에 검증해야 함. |
| `EXP-01` | profile 확장 | DEFERRED | 우선순위는 앞당기되 구현 보류 판정 유지. 선택 문자열만 있으며 account별 strategy/universe binding, 미존재 차단, profile evidence와 두 계좌 순차 운영은 미완료. risk/benchmark는 공통 계약. |
| `BT-02` | 차세대 simulator/WFO | DEFERRED | no-lookahead loader, hybrid simulator, rolling WFO는 장기 연구. |
| `FUND-01` | Fundamental/quality data | DEFERRED | point-in-time 데이터 계약과 Research Gate가 선행. |
| `UX-01` | Operator UX | PARTIAL | 5-wrapper Primary facade, V2 Finalize 통합, canonical NO_ACTION/preview 안내가 구현·테스트됨. 최신 V2 Paper commit 산출물은 확인했으나 Primary `.cmd` 사용・credential 환경 재현성은 미확인. |
| `AUTO-02` | 승인 기반 Telegram execution | DEFERRED | read-only 운영과 승인 threat model 검증 전에는 활성화하지 않음. |

## H. 증거 성숙도

| 코드/범위 | 문서 | 구현 | 테스트 | 실제 운영 | 실패/복구 |
|---|---|---|---|---|---|
| MFU-EO2 | 있음 | 완료 | 있음 | 09-09 V2 Paper commit report 3행; 이전 NO_ACTION evidence도 있음 | invalid-context fail-closed; 반복 운영 복구 미확인 |
| Stage A AS-OF | 있음 | 완료 | 있음 | 2026-09-08 plan `PASS` | cutoff/provenance fail-closed |
| Recovery | 있음 | 완료 | 있음 | 기존 activation evidence 있음, 반복 Recovery 운영 재실행은 미확인 | 승인·context·state guard와 consumed/unconsumed 분류 |
| `ACCT-01` | 있음 | 완료 | D isolation 및 A/B/C regression 승인됨 | 두 계좌 실운영은 미확인; D는 격리 fixture 검증 | explicit `paper_default` legacy read-only compatibility; migration은 별도 미수행 |
| `REPLAY-01` | 있음 | 부분 | 있음 | empty/limited replay evidence | duplicate key WARNING 및 auto-match 제외, stable identity 미완료 |
| `NOTION-02` | 있음 | 부분 | 있음 | Notion 흐름 사용 | schema fail/warning, view는 수동 |
| `CFG-01`/`STRAT-04` | 있음 | 조립/snapshot 부분 | 기존 config・plan 관련 테스트 있음 | 모든 screener/runtime 소비값과 profile 정합성 미완료 | profile별 설정 오염・순서 독립성 증거 필요 |
| `EXP-01` | 방향/문자열 모델 있음 | runtime binding 미구현 | account profile 테스트는 있음; binding 검증 없음 | 두 계좌 strategy/universe 수동·순차 evidence 없음 | 미존재 profile 실행 차단 필요 |
| `UX-01` | 있음 | 부분 | Primary/gate/wrapper 관련 테스트 있음 | 최신 EXECUTION/commit 및 과거 NO_ACTION 산출물; Primary `.cmd` 사용 미확인 | stage evidence 손상 시 fail-closed/recovery 안내 |
| `RG-01` | 있음 | 없음 | 없음 | 문서 관행만 있음 | 없음 |
| `BT-01` | 있음 | IS/OOS 부분 | smoke 부분 | 최근 공식 연구 run 미확인 | 실행 예외 처리 |
| `DQ-01` | 있음 | Stage A 부분 | 있음 | Stage A PASS | as-of fail-closed |
| `PA-01`~`UI-01` | 있음 | 각 subset | 관련 테스트 있음 | 일부 report/ops 사용 | owner별 guard, 공통 계약 미완료 |
| `RF-01`/`DA-01`/`FA-01` | 방향 있음 | canonical 구현 없음 | 없음 | 없음 | 없음 |

## I. 기능별 상세 평가

각 항목의 첫 문장은 **현재 판정과 우선순위**, 이어지는 문장은 **목적과 현재 증거**, **실제 gap과 완료 조건**, **선행조건 및 범위 아님**을 압축해 기록한다. 세부 코드·테스트 근거는 D와 H 및 MFU별 Result/Review Evidence에서 확인한다.

### ACCT-01

`COMPLETE`, closed. account profile/path/guard, writer/read/report/replay/alert/export closure와 A/B canonical isolation regression이 PASS했다. normal path의 silent legacy root fallback은 제거됐고 legacy는 `paper_default` explicit read-only compatibility로만 허용된다. 실제 `paper_default` migration은 별도 승인 후속 작업으로 미수행이며, 범위는 paper account 격리이고 무승인 DB migration은 포함하지 않는다.

### REPLAY-01

`PARTIAL`, P1. `core/paper_replay_diff.py`는 account/date와 config/universe 등 fingerprint를 비교하지만 `symbol|action` 중복을 고유하게 match하지 못한다. 현재 계약은 `STATUS_WARNING` 및 auto-match 제외이며 `tests/test_paper_replay_diff.py::test_duplicate_symbol_action_key_warns_without_auto_matching`이 이를 고정한다. duplicate 자체를 FAIL로 기록하지 않는다. stable action identity, 동일 symbol/action 복수 행 구분, 순서 독립 matching, 대표 non-empty corpus와 account/profile fingerprint 비교를 닫아야 완료다. profile 비교 계약을 먼저 정의하고 실제 runtime binding 적용은 CFG/STRAT 이후 EXP에서 연결한다. execution commit의 trade ID 존재나 실제 Paper 거래만으로 replay identity gap이 닫히지는 않는다.

### NOTION-02

`PARTIAL`, P1. `core/notion_schema_validator.py`와 관련 테스트는 required property/type 오류를 FAIL, 일부 Account ID 누락·select option 누락을 WARNING으로 구분한다. `scripts/dev/validate_notion_schema.py`는 FAIL일 때만 종료 코드 1을 반환하므로 WARNING 발생 시 publish가 일괄 차단된다고 볼 수 없다. 기존 validator를 재사용해 property/type/select option read-only preflight, active account/run mapping, 수동 view drift 점검 주기·evidence, FAIL/WARNING별 publish 및 후속 동작 정책을 닫아야 완료다. Notion은 staging/review/presentation 계층을 유지한다.

### CFG-01 및 STRAT-04

둘 다 `PARTIAL`, P2이며 `CFG-01 -> STRAT-04 -> EXP-01` 순서다. 목적은 전략 종류·지표 파라미터·전략 가중치·매수/매도 판단·포지션 크기의 설정 owner와 runtime 소비 경계를 명확히 하는 것이다. 기존 `make_config()` 병합 우선순위, 필요한 `patch_global_config` 호환 경로, snapshot/hash helper를 재사용한다. screener와 plan/engine이 실제로 소비한 값까지 설정 version/fingerprint와 일치하고, timing/as-of 계약 및 계좌 간 설정 비오염을 검증해야 완료다. 설정 정리는 성능 개선을 위한 전략·parameter 변경 승인이 아니다.

### EXP-01

`DEFERRED` 유지, P2로 우선순위 상승. P1과 CFG/STRAT closure 이후 최소 binding을 구현하며, 현재 선택 문자열 선언을 구현 완료로 간주하지 않는다. 초기 모델은 다음으로 제한한다.

```text
account
├── strategy_profile 1개
├── universe_profile 1개
├── 공통 risk contract
└── 공통 benchmark contract
```

완료에는 account별 strategy/universe binding, 존재하지 않는 profile 사용 시 실행 차단, 실행 evidence의 profile ID와 version 또는 fingerprint, 계좌별 현금·포지션·체결·보고서 격리가 필요하다. 같은 입력에서 A→B와 B→A 실행 결과가 달라지지 않음을 입증하고 두 계좌 수동·순차 운영 evidence를 남긴다. 5번 운영 검증은 EXP의 완료 조건으로 관리한다. 계좌별 독립 `risk_profile`/`benchmark_profile`은 보류한다. 새로운 전략 profile 등록은 `BENCH-02`, `RG-01`, `BT-01` 검증 이후다.

### RG-01

`DOCUMENTED_ONLY`, P4. MFU 계약과 Result/Review 관행은 있으나 executable gate가 없다. 가설, as-of 데이터, 비용, 실패조건, OOS 결과를 공통 입력으로 받아 KEEP/REFINE/OVERFIT/REJECT 같은 승인된 판정과 evidence를 재현해야 완료다. 성과 보장이나 자동 최적화는 범위가 아니다.

### BT-01

`PARTIAL`, P4. IS/OOS와 OOS 재검증은 구현됐다. 사전 고정 split, rolling WFO, 주변값 plateau, 하위기간/대체 universe, fee/slippage/1일 지연 stress를 하나의 승격 계약에서 판정해야 완료다. 최고 결과 재선택은 강건성 검증이 아니다.

### DQ-01

`PARTIAL`, P4. Stage A AS-OF provenance는 완료됐지만 전체 데이터 계약은 아니다. 핵심 데이터에 `source`, `as_of_date`, `fetched_at`, `timezone`, `currency`, `frequency`, `adjustment_basis`, `schema_version`, `run_id`를 필요한 범위에서 기계 추적해야 완료다. 특정 provider를 절대적 진실로 간주하지 않는다.

### PA-01

`PARTIAL`, P4. 종목 P&L, equity/MDD, benchmark excess return은 있다. 종목, cash, hedge, fee, timing/selection contribution 합계가 총손익과 허용오차 내 reconcile해야 완료다. 설명되지 않은 잔여를 자동으로 alpha라 부르지 않는다.

### PF-01

`PARTIAL`, P5 후순위. `EXP-01`은 계좌 하나에 전략 profile 하나를 연결하고, `PF-01`은 한 계좌 안에서 여러 전략의 포지션·동일 종목 수량과 attribution을 분리한다. 현재 계좌당 전략 하나의 정책에서는 PF를 선행 구현하지 않는다. 다전략 계좌가 필요해지면 모든 내부 position/trade의 account/strategy 귀속과 외부 계좌・내부 전략 원장 reconciliation을 닫아야 완료다. broker 잔고에서 전략별 수량을 역추정하지 않는다.

### RS-01

`PARTIAL`, P5 후순위. position HWM/MDD와 미래행 배제는 있다. position cycle, 추가매수, 일부매도, 수동 변경, 재시작의 kept/reset/new/deleted 정책과 strategy/account HWM을 고정해야 완료다. 다전략 확장에는 `PF-01` identity가 선행하며 초기 EXP의 공통 risk contract를 계좌별 독립 risk profile로 확장하지 않는다.

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

`OPS-04 -> OBS-01`, `TEST-01`, `AUTO-03 -> AUTO-01`은 P3에서 두 계좌 운영 evidence 이후의 관측성・안전한 CI・read-only 자동화를 순차적으로 닫는다. write 활성화는 별도다. `BENCH-02`는 P4에서 공통 cash-flow benchmark 정책과 수치 검증을 닫고 RG/BT의 신규 전략 검증으로 연결한다. `BT-02`, `FUND-01`, `UX-01`, `AUTO-02`의 판정·경계는 G와 F를 따른다. `UX-01`은 기존 `PARTIAL`을 유지하며 이번 Paper commit 증거만으로 완료로 올리지 않는다. 신규 backlog로 중복 생성하지 않는다.

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
| 계좌별 독립 risk/benchmark profile | 보류. 초기 EXP는 공통 risk/benchmark contract를 사용한다. |
| 계좌 내부 다전략 원장 (`PF-01`) 및 다전략 위험 상태 (`RS-01`) | 후순위. 계좌당 전략 하나의 binding과 운영 검증이 우선이며, 다전략 계좌 요구가 생길 때 재평가한다. |

## K. 단계별 공식 개발 순서

F의 공식 우선순위 표를 단계 의존성으로 읽으면 다음과 같다.

```text
ACCT-01 COMPLETE (기반)
-> REPLAY-01 -> NOTION-02
-> CFG-01 -> STRAT-04
-> EXP-01 최소 strategy/universe binding
-> 두 계좌 수동·순차 검증 (EXP-01 완료 evidence)
-> OPS-04 -> OBS-01 -> TEST-01
-> AUTO-03 -> AUTO-01 (read-only)
-> BENCH-02 -> RG-01 -> BT-01
-> DQ-01 -> PA-01
-> write 자동화 승인 검토 / EV-01 -> UI-01
```

- 최신 확인 run에는 완료 manifest가 있으며, 실제 incomplete lifecycle이 확인되면 해당 운영 closeout을 P0로 다시 평가한다.
- `ACCT-01` 완료와 P1의 `REPLAY-01`, `NOTION-02` 미완료를 구분한다. 사용자 운영 관찰은 이 blocker를 해제하지 않는다.
- CFG/STRAT 이전에 profile별 설정 경로를 추가하지 않는다. EXP의 두 계좌 운영 evidence는 기존 account isolation fixture를 대신 인용해 완료할 수 없다.
- retention/observability와 safe CI는 자동화 범위를 넓히기 전에 실패 evidence를 보존한다.
- `BENCH-02`는 현재 exploratory benchmark를 대체하지 않고 별도 cash-flow contract로 추가한다.
- 새로운 전략 profile의 운영 등록은 위 구현 순서와 별개로 BENCH/RG/BT 검증이 선행한다. 그 전에는 기존 전략의 binding 범위만 검증한다.
- Research Gate가 전략 성능을 보장하거나 최고 parameter를 자동 선택하지 않는다.
- `PF-01 -> RS-01`은 다전략 계좌가 필요할 때의 후순위 분기다. 선택·장기 연구는 J와 G의 보류 조건을 따른다.
- 공통 event/read model 없이 consumer별 dashboard parsing을 늘리지 않는다.

## L. 사용자 결정이 필요한 경계

계좌당 전략 하나, strategy/universe 각 1개, 공통 risk/benchmark, 두 계좌 수동·순차 운영 우선 정책은 확정됐으므로 다시 선택하지 않는다. 다음 경계에는 별도 선택 또는 승인이 필요하다.

- 미수행 `paper_default` migration 및 explicit legacy read-only compatibility의 향후 전환/종료 시점
- 초기 운영 대상 두 계좌와 각 profile의 구체적 배정, 신규 전략 등록 시 BENCH/RG/BT 검증 결과 승인
- 계좌별 독립 risk/benchmark 또는 한 계좌 내부 다전략으로 목표를 확장할지 여부
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
10. 운영 evidence는 허용된 범위에서만 읽고 확인 시점・관찰・검증 한계를 구분한다. 이번에는 실행 산출물만 확인하고 운영 DB·계좌 state·runbook state를 열지 않았다.

현재 참고 근거:

- Operator/runbook: `docs/operations/paper_daily_cycle_commands.md`
- Notion view spec: `docs/operations/notion_view_spec_daily_plans_manual_executions_manual_reviews.md`
- System Audit: `docs_chatGPT_work/codex_results/SYSTEM-AUDIT-20260810/`
- MFU별 완료 증거: `docs/work_results/`
- ACCT closeout: `docs/work_results/ACCT-01D-ACCOUNT-ISOLATION-EVIDENCE_Result.md`, `docs/work_results/ACCT-01D-ACCOUNT-ISOLATION-EVIDENCE_Review_Evidence.md`
- Replay 계약: `core/paper_replay_diff.py`, `tests/test_paper_replay_diff.py`
- 설정/profile 경계: `core/config_factory.py`, `core/portfolio_config.py`, `config.py`, `screener/screener.py`, `core/daily_plan_generator.py`, `core/paper_account_profile.py`
- 현재 구현과 테스트: `core/`, `screener/`, `scripts/`, `tests/` (이번 작업은 파일 검토만 수행)

문서 역할:

```text
ROADMAP_CURRENT.md       = 현재 상태, 범위, 공식 우선순위
SYSTEM-AUDIT-YYYYMMDD/   = 특정 시점의 저장소 전체 평가
initiative PRD/TRD       = 상세 requirement 및 implementation contract
Result/Review Evidence   = 완료 및 검증 증거
Git history              = ROADMAP_CURRENT의 과거 상태
```

# StockScreener 현재 로드맵

상태: 공식 기준(Canonical)

최종 갱신일: 2026-08-11

기준 브랜치: `gemini_cli_update`

검증 기준 HEAD: `6ef2c85d95b276d863e71b1104eab39692d8fca4`

근거 기준선: `SYSTEM-AUDIT-20260810`

## A. 문서 권한

`docs/ROADMAP_CURRENT.md`는 StockScreener의 현재 개발 상태, 운영 범위, 우선순위를 판단하는 유일한 공식 로드맵이다.

과거 로드맵의 “현재 상태” 또는 “다음 작업”이 이 문서와 충돌하면 현재 상태와 우선순위는 이 문서를 따른다. 다만 실제 런타임 동작과 기술 계약은 현재 구현 및 승인된 계약을 기준으로 확인해야 한다. 이 로드맵은 상세 PRD/TRD를 대체하지 않는다.

권한 우선순위:

```text
현재 코드 / 테스트 / 승인된 운영 계약
-> ROADMAP_CURRENT.md의 현재 상태 및 우선순위
-> 최신 승인 initiative별 PRD/TRD
-> 과거 로드맵 및 설계 이력
```

과거 로드맵, PRD, TRD는 설계 근거로 보존한다. 세부 기술 계약의 충돌을 로드맵 문구만으로 판단하지 말고 현재 구현과 승인된 initiative 계약을 확인한다.

## B. 현재 시스템 상태

StockScreener는 안전성을 중시하는 성숙한 paper-trading 운영 시스템이다. 검증된 paper 계좌 범위에서는 일간 및 주간 운영이 가능하다.

- 승인된 lifecycle은 Stage A -> Gate 1 -> Stage B -> verification -> Stage C -> Gate 2 -> Stage D -> Stage E -> Stage F -> completion -> rollover까지 포함한다.
- 멱등성, 복구, no-action 운영, completion manifest, legacy completion 분류, zero-progress retirement, 다음 운영일 준비가 구현되어 있다.
- 근거가 확인된 P0 blocker는 없다.
- 현재 단계는 **안전하게 운영하면서 확장 전에 신뢰성을 보강하는 단계**다.

이는 모든 과거 로드맵이 완료됐다는 뜻이 아니다. 현재 시스템은 live-ready, 완전 자동화, 모든 계좌/profile로 확장 완료, 또는 모든 연구 architecture 완료 상태가 아니다.

## C. 현재 운영 범위

### 현재 허용

- 검증된 paper 계좌를 현재 Windows wrapper와 runbook으로 운영한다.
- 날짜를 인식하는 Daily Plan을 생성한다.
- Manual Execution을 공식 paper execution 경로로 사용한다.
- 현재 local 및 Notion staging/input/review 흐름으로 Manual Review를 수행한다.
- 고정된 A-F lifecycle, completion 검증, rollover를 완료한다.
- 일간 paper 운영 근거와 주간 report, review, 현재 benchmark 비교를 생성한다.
- Python을 validation 및 business-judgment engine으로 사용한다. Local CSV/JSON/Markdown/SQLite artifact는 source of truth이고, Notion은 staging/input/review/presentation 계층이다.

### 현재 확대하거나 활성화하지 않음

- 검증되지 않은 계좌로의 광범위한 확대
- strategy, risk, universe profile의 대규모 추가
- Telegram 승인으로 시작되는 write 실행
- n8n 내부의 trading 또는 business judgment
- live broker 또는 real-order 연동

남은 P1 작업은 확장 범위를 제한하지만 검증된 paper 운영 범위를 사용할 수 없게 만드는 blocker는 아니다.

## D. 완료된 기반

- 시장 데이터, as-of universe, 기술적 screening 및 ensemble 기반
- 시장 regime, safety trigger, cash, hedge, sizing 및 long-position cap 정책
- Paper ledger, account state, valuation, snapshot 및 report
- Sidecar와 replay 기반을 포함한 date-aware Daily Plan
- Manual Execution, reconciliation, commit 및 status sync
- Manual Review 준비, append 및 status sync
- Reporting 및 현재 initial-capital benchmark 비교
- Read-only Daily Ops Orchestrator 및 operator summary
- Gate와 Stage B verification을 포함한 고정 A-F runbook
- 멱등성, 안전한 복구, no-action lifecycle 및 엄격한 completion evidence
- Legacy completion 분류, zero-progress retirement 및 rollover/day preparation
- Windows operator wrapper

## E. 지금 운영에 필요한 P1

P0: **없음**.

### 1. ACCT-01 — Multi-account vertical-slice closure

| 항목 | 값 |
|---|---|
| 상태 | MOSTLY_COMPLETE |
| 필요성 | MUST |
| 긴급성 | P1 |
| 지금 필요한 이유 | 남아 있는 default-root 또는 profile fallback이 검증된 계좌 밖으로 운영을 확대할 때 계좌 데이터를 섞을 수 있다. |
| 완료 조건 | 모든 plan, report, replay, alert, export 및 write 경계가 하나의 account root를 해석하고 검증하며, 조용한 `paper_test` fallback이 없어야 한다. |
| 완료 전 확장 차단? | **YES** — 광범위한 multi-account 및 profile 확장 |

### 2. REPLAY-01 — Stable action identity와 non-empty replay

| 항목 | 값 |
|---|---|
| 상태 | MOSTLY_COMPLETE |
| 필요성 | MUST |
| 긴급성 | P1 |
| 지금 필요한 이유 | 같은 symbol/date에 여러 action이 있거나 row 순서가 바뀌어도 replay가 결정론적으로 동작해야 한다. |
| 완료 조건 | Stable action identity 정책과 non-empty replay corpus가 같은 symbol/action의 중복을 포함해 순서와 무관한 결정론적 matching을 입증해야 한다. |
| 완료 전 확장 차단? | **YES** — replay 신뢰성에 의존하는 자동화 또는 확장 |

### 3. NOTION-02 — Schema 및 view drift guard

| 항목 | 값 |
|---|---|
| 상태 | PARTIAL |
| 필요성 | MUST |
| 긴급성 | P1 |
| 지금 필요한 이유 | 외부 Notion property, option, schema, view 변경이 정상적인 운영을 차단하거나 잘못된 경로로 보낼 수 있다. |
| 완료 조건 | 주기적인 read-only preflight가 필수 schema/options/mapping을 검증하고, 문서화된 FAIL/WARNING 대응과 view-drift checklist를 제공해야 한다. |
| 완료 전 확장 차단? | 검증된 현재 흐름에는 차단 아님. 더 넓은 Notion 의존 확장에는 **YES** |

### 최근 완료

- `DOC-01` — **COMPLETE**: 이 공식 `ROADMAP_CURRENT.md`가 현재 로드맵의 권한을 확립했으며 문서 supersession 문제는 pending P1 목록에서 제거됐다.

## F. 다음 단계

| 순서 | Initiative | 결과 / 의존성 |
|---:|---|---|
| 1 | `OPS-04` + `OBS-01` | Artifact retention, run index, 운영 SLO 및 observability. 실패·차단된 복구 근거를 보존한다. |
| 2 | `TEST-01` | Side-effect 기준으로 분류된 안전한 CI. 격리가 입증된 suite부터 자동화한다. |
| 3 | `AUTO-03` / `AUTO-01` | Read-only scheduling과 deployment/run evidence. Write stage는 계속 승인을 요구한다. |
| 4 | `BENCH-02` | Cash-flow/dividend/fee/fraction 정책 승인 후 월적립식 SPY benchmark를 설계·구현한다. |
| 5 | `CFG-01` / `STRAT-04` / `BT-01` | 점진적인 정합성 개선만 수행하며 광범위한 refactor는 하지 않는다. |
| 6 | `EXP-01` | 현재 P1 신뢰성 공백을 닫은 뒤 account/universe/strategy/risk profile을 공식화한다. |

## G. 장기 / 연구

- `BT-02`: 구체적인 no-lookahead loader, hybrid simulator, rolling walk-forward optimization 및 plateau evaluator
- `FUND-01`: Point-in-time fundamental 및 quality data 수집·filtering
- `UX-01`: Drift validation을 재현 가능하게 만든 뒤 Notion operator view와 input UX 개선
- `AUTO-02`: Read-only 운영과 승인 threat model이 수용된 뒤 approval-based Telegram execution

이들은 연구 또는 장기 capability이며 현재 production requirement가 아니다. WFO, fundamentals, approval execution은 COMPLETE가 아니다.

## H. 보류 / 폐기 / 보관

| 항목 | 현재 결정 |
|---|---|
| CSV-only market database | Historical. SQLite로 대체됨. |
| n8n 내부 business/trading judgment | DROP / 대체됨. Python이 judgment engine으로 유지된다. |
| 공식 operator 경로로서의 `paper_virtual_fill` | Historical compatibility로만 유지한다. Manual Execution이 공식 경로다. |
| 단일 hard-coded `paper_test` architecture | Account-aware path 및 identity 처리로 대체됨. |
| 과거 v5.x performance-tuning 예시 | 활성 backlog가 아닌 연구 이력이다. |
| Live broker integration | 현재 paper 목표에서는 DEFER / DROP_CANDIDATE다. 별도로 승인된 safety program 없이는 재개하지 않는다. |

## I. 개발 순서

```text
ACCT-01
-> REPLAY-01
-> NOTION-02
-> retention / observability
-> safe CI
-> read-only scheduling / deployment proof
-> monthly-contribution benchmark
-> account / universe / strategy / risk expansion
-> optional WFO / fundamentals research
```

`DOC-01`은 완료됐으며 pending sequence에 포함하지 않는다.

## J. 공식 참고 자료

현재 운영 및 audit 참고 자료:

- Operator/runbook: `docs/operations/paper_daily_cycle_commands.md`
- SYSTEM AUDIT summary: `docs_chatGPT_work/codex_results/SYSTEM-AUDIT-20260810/SYSTEM_AUDIT_SUMMARY.md`
- Initiative matrix: `docs_chatGPT_work/codex_results/SYSTEM-AUDIT-20260810/03_initiative_matrix.md`
- Gap priority: `docs_chatGPT_work/codex_results/SYSTEM-AUDIT-20260810/06_gap_priority.md`
- Current system map: `docs_chatGPT_work/codex_results/SYSTEM-AUDIT-20260810/05_current_system_map.md`
- Document/code conflicts: `docs_chatGPT_work/codex_results/SYSTEM-AUDIT-20260810/04_document_code_conflicts.md`

Historical reference에는 System Architecture v5.x, Paper roadmap v1.x, OPER/MFU series, `docs_n8n/` roadmap/task series가 포함된다. 이들은 현재 로드맵의 authority가 아니라 historical/design lineage다.

## K. 유지관리 규칙

1. `docs/ROADMAP_CURRENT.md`는 유일한 current roadmap SSOT다.
2. 새 아이디어가 제안됐다는 이유만으로 official backlog에 추가하지 않는다.
3. 실제 개발이 승인된 initiative만 추가하거나 우선순위를 부여한다.
4. 상세 requirement와 implementation design은 최신 initiative별 PRD/TRD에서 관리한다.
5. Code, test, 관련 operating evidence를 확인한 뒤에만 구현 완료로 표시한다.
6. 작은 작업이 끝날 때마다 새 roadmap 파일을 만들지 않는다.
7. `ROADMAP_CURRENT_v2.md`, `ROADMAP_FINAL.md`, `ROADMAP_YYYYMMDD.md` 같은 이름을 일반적인 운영 방식으로 사용하지 않는다.
8. 현재 상태나 우선순위가 바뀌면 같은 `ROADMAP_CURRENT.md`를 수정한다.
9. 수정 시 최소한 `최종 갱신일`, `검증 기준 HEAD` 또는 관련 baseline과 영향받은 initiative 상태/우선순위를 갱신한다.
10. 이 문서의 과거 상태는 Git history로 보존한다.
11. 큰 phase 전환 또는 repository 전체 재평가에만 날짜별 `SYSTEM-AUDIT-YYYYMMDD/`를 생성한다.
12. 새 SYSTEM AUDIT 결과는 이 로드맵에 다시 반영한다.
13. 이전 결정을 지우기 위해 historical roadmap, PRD, TRD를 다시 작성하지 않는다.
14. Superseded 또는 dropped initiative는 여기에 짧은 상태만 남기고 자세한 내용은 source 문서와 Git history에서 확인한다.

문서 역할:

```text
ROADMAP_CURRENT.md       = 현재 상태, 범위, 우선순위
SYSTEM-AUDIT-YYYYMMDD/   = 특정 시점의 repository 전체 평가
initiative PRD/TRD       = 상세 requirement 및 implementation contract
Git history              = ROADMAP_CURRENT의 과거 상태
```

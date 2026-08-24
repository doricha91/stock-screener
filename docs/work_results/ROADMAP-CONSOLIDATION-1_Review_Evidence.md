# ROADMAP-CONSOLIDATION-1 Review Evidence

## AGENTS.md 확인

- `D:\python\StockScreener\AGENTS.md`를 UTF-8로 처음부터 끝까지 읽고 적용했다.
- 문서 전용 범위, dirty worktree 보존, 보호 DB 무수정, Git 비자동 commit 규칙을 지켰다.

## Repository identity

```text
branch: gemini_cli_update
local HEAD: 4fdb9b0da92626a0fee765106389aff2bd756e70
origin/gemini_cli_update: 4fdb9b0da92626a0fee765106389aff2bd756e70
merge-base: 4fdb9b0da92626a0fee765106389aff2bd756e70
ahead/behind: 0 0
remote: https://github.com/doricha91/stock-screener.git
```

첫 sandbox fetch는 `.git/FETCH_HEAD` 권한으로 실패했고, 승인된 escalated `git fetch --no-tags origin gemini_cli_update`로 원격을 확인했다. `main`은 사용하지 않았다.

## Roadmap baseline 결정

- `6ef2c85d95b276d863e71b1104eab39692d8fca4`: canonical roadmap 최초 추가
- `6b00fe47d825eae7c0307ebffa02359ef6c1c2df`: roadmap의 마지막 실제 내용 변경(한국어 canonical 내용)
- 비교 기준은 `6b00fe47…`로 정하고 이전 header SHA도 새 roadmap에 기록했다.

## Baseline 이후 commit과 changed-file summary

```text
7945ea8 fix: preserve historical stage f completion evidence
26075e0 feat(paper-ops): finalize MFU-EO2 execution outcome contract
a941a36 fix(stage-a): enforce as-of provenance and immutable inputs
f979e52 feat(paper-ops): add immutable runbook recovery workflow
03bae12 docs(paper-ops): record recovery activation and Stage A evidence
4fdb9b0 docs(paper-ops): preserve key recovery review evidence
```

63 files, 12,113 insertions, 213 deletions. 핵심 영역은 execution outcome, Stage A provenance, recovery, Stage F evidence와 관련 tests/contracts다.

## 두 원본 문서의 핵심 차이

| 항목 | 기존 roadmap | 기능 벤치마크 v1.1 | 통합 결정 |
|---|---|---|---|
| Authority | 유일한 current roadmap | 평가 기준선 | roadmap만 canonical 유지 |
| Priority | ACCT -> REPLAY -> NOTION | capability별 A-D urgency | 기존 P1을 보존하고 후속을 하나의 순서로 통합 |
| 상태 시점 | 2026-08-11 | MFU-EO2/AS-OF/Recovery 반영 | current HEAD evidence로 갱신 |
| Catalog | 제한적 | 13개 상세 기능 | 13개와 기존 initiative를 G-I에 통합 |
| SoT | local/Python/Notion 역할 | 일부 DB 중심 표현 | account-scoped local artifact 기능별 SoT로 통일 |
| 운영 상태 | 일반 상태 | 2026-08-24 snapshot | 실제 state를 다시 읽어 시점 snapshot으로 기록 |

## 기능 판정 변경 근거

- 비표준 `MOSTLY_COMPLETE`는 `PARTIAL`로 정규화했다.
- `ACCT-01`, `REPLAY-01`, `NOTION-02`는 확인된 gap 때문에 완료로 올리지 않았다.
- MFU-EO2, Stage A AS-OF, Recovery, Stage F evidence는 좁은 계약만 `COMPLETE`다.
- `DQ-01`, `PF-01` 같은 상위 capability는 좁은 완료를 확대하지 않고 `PARTIAL`을 유지했다.
- `VA-01`, `MR-01`은 기존 owner와 중복이다.
- `RG-01`은 executable 판정기가 없어 `DOCUMENTED_ONLY`, `BENCH-02`는 monthly cash-flow contract가 없어 `MISSING_NEEDED`다.

## P1 코드·테스트 근거

### ACCT-01

- `core/paper_account_profile.py`, `core/paper_account_paths.py`, `core/paper_account_guard.py`
- account isolation 및 account-aware Stage F tests
- account-aware 기반은 있으나 default account legacy fallback과 모든 consumer closure가 남아 있다.

### REPLAY-01

- `core/paper_replay_diff.py::compare_daily_plan_payloads`
- `_row_key()`는 `symbol|action`을 사용한다. Duplicate key는 `DUPLICATE_ROW_KEY` / `STATUS_WARNING`으로 기록되고 자동 매칭 및 일반 row comparison 대상에서 제외된다. Duplicate key만으로 전체 결과를 `FAIL`로 차단하지는 않는다.
- `tests/test_paper_replay_diff.py::test_duplicate_symbol_action_key_warns_without_auto_matching`는 overall status로 `STATUS_WARNING`을 기대한다.
- stable action identity와 대표 non-empty replay corpus가 남아 있다.

### NOTION-02

- `core/notion_schema_validator.py::build_expected_schema`, `validate_data_source_schema()`
- property/type/select option 및 여러 data-source target 검증
- `tests/test_notion_schema_validator.py`
- `docs/operations/notion_view_spec_daily_plans_manual_executions_manual_reviews.md`
- view drift는 현재 수동 evidence 경계다.

## 완료 계약 근거

### MFU-EO2

- `core/execution_reconciliation.py::derive_execution_outcomes`
- `core/execution_outcome_flow.py`, `scripts/runbook_state.py`
- `tests/test_execution_outcome_derivation.py`, `tests/test_execution_outcome_flow.py`, zero-count downstream regressions
- 판정: 좁은 outcome/finalize contract `COMPLETE`

### Stage A AS-OF

- `core/stage_a_asof_contract.py`, `core/daily_plan_generator.py`
- `tests/test_stage_a_asof_contract.py`
- source cutoff/provenance, immutable universe/config, fail-closed
- 판정: official 좁은 scope `COMPLETE`

### Runbook Recovery

- `core/runbook_recovery.py`, `tests/test_runbook_recovery.py`
- authorization, frozen context/workspace, immutable transition, deny/fail-closed
- 판정: contract `COMPLETE`

### Stage E/F account path와 Notion sync

- `tests/test_runbook_stage_runner_stage_f.py`
- non-default account의 legacy root 차단, account root/artifact isolation
- Account Snapshot/Benchmark external-key exact validation
- invalid Stage E evidence가 Stage F를 subprocess 없이 차단
- missing/corrupt Notion evidence의 strict self-heal/fail-closed
- 판정: Stage F 좁은 evidence hardening 완료, `ACCT-01` 전체는 partial.

## Benchmark와 optimizer/Research Gate

- `core/paper_benchmark_comparison.py`는 exploratory initial-capital SPY/QQQ/CASH 비교다.
- 월별 cash-flow/dividend/fee/fractional-share/holiday 정책의 `BENCH-02`는 없다.
- `core/optimizer_engine.py`에는 IS/OOS 및 OOS 재검증 subset이 있다.
- rolling WFO, plateau, alternate universe, cost/slippage/day-delay stress의 공통 승격 계약은 없다.
- formal Research Gate module/test/operational result는 확인되지 않았다.
- 판정: `BENCH-02=MISSING_NEEDED`, `BT-01=PARTIAL`, `RG-01=DOCUMENTED_ONLY`.

## 최신 실제 운영 evidence

읽기 전용 확인:

```text
path: D:\n8n\workspace\stock_screener_ops\runbook_states\paper_pilot_202606_2026-08-21_2026-08-24.json
updated_at: 2026-08-23T16:04:45.065597+09:00
account/data/trade: paper_pilot_202606 / 2026-08-21 / 2026-08-24
Stage A: PASS
GATE1/B/C/GATE2/D/E/F: PENDING
contract: execution_reconciliation_preview.v2
input_finalized: false
```

이 시점 이후 actual execution/Notion 입력 여부는 확인하지 못했다.

## 최종 기능 코드 존재 검증

```text
ACCT-01 PASS     REPLAY-01 PASS   NOTION-02 PASS
RG-01 PASS       BT-01 PASS       DQ-01 PASS       VA-01 PASS
PA-01 PASS       PF-01 PASS       RS-01 PASS       EV-01 PASS
UI-01 PASS       MR-01 PASS       RF-01 PASS       DA-01 PASS
FA-01 PASS       OPS-04 PASS      OBS-01 PASS      TEST-01 PASS
BENCH-02 PASS
```

`AUTO-03`, `AUTO-01`, `CFG-01`, `STRAT-04`, `EXP-01`, `BT-02`, `FUND-01`, `UX-01`, `AUTO-02`도 보존했다.

## Migration checklist

삭제 전에 실행한 결과:

```text
설계 원칙: PASS
상태 분류 체계: PASS
우선순위 평가 기준: PASS
13개 기능 코드: PASS
판정·증거·gap·완료 조건: PASS
현재 구현 기준선: PASS
제외·보류: PASS
Source of Truth: PASS
공식 P1·후속 initiative: PASS
공식 우선순위 단일화: PASS
최신 HEAD·기준일: PASS
운영 시점 snapshot: PASS
```

모두 PASS한 뒤에만 중복 기준서를 삭제했다.

## 삭제 파일과 reference 검증

```text
Test-Path docs/00. 투자 시스템 기능 벤치마크 및 개발 우선순위 평가 기준서.md
False
```

삭제 source는 작업 전 untracked였으므로 `git diff -- <path>` 출력이나 Git `D`가 없다. 별도 archive는 만들지 않았다.

- `ACTIVE_BROKEN_REFERENCE`: 없음
- `CURRENT_REFERENCE_UPDATED`: 없음
- `HISTORICAL_REFERENCE_PRESERVED`: `docs_chatGPT_work/Git commit selected review evidence and push.md`, `SS cap priority v1.1 update.md`, `Roadmap-consolidation1.md`, 과거 Review Evidence의 당시 status capture

위 참조는 작업지시·감사 이력이므로 수정하지 않았다.

## 문서 구조 검증

```text
roadmap_exists=True
deleted_source_absent=True
h1_count=1
code_fence_count=8
code_fences_closed=True
missing_codes=<none>
official_priority_table_count=1
branch_recorded=True
full_head_recorded=True
date_recorded=True
table_errors=0
```

변경 전 roadmap A-K와 별도 기준서 13개 section을, 변경 후 canonical A-M 구조(authority, principles, scope, implementation, actual ops, priority, catalog/evidence/detail, exclusions, sequence, decisions, maintenance)로 통합했다.

## Git 및 dirty baseline 증거

작업 시작 tracked dirty:

```text
 M docs/operations/paper_daily_cycle_commands.md
 M idea, PRD, TRD/paper 운영 기능 개발 로드맵 v1.3.md
 M outputs/backtest_log.db
 ?? 다수의 기존 temp/docs/review evidence
 ?? 삭제 전 benchmark 기준서
```

이번 작업 소유 변경:

```text
 M docs/ROADMAP_CURRENT.md
 ?? docs/work_results/ROADMAP-CONSOLIDATION-1_Result.md
 ?? docs/work_results/ROADMAP-CONSOLIDATION-1_Review_Evidence.md
 filesystem deleted: docs/00. 투자 시스템 기능 벤치마크 및 개발 우선순위 평가 기준서.md
```

최종 실행 명령:

```text
git diff --check
git status --short --untracked-files=all
git diff --name-status
git diff --stat
git diff -- docs/ROADMAP_CURRENT.md
git diff -- docs/00. 투자 시스템 기능 벤치마크 및 개발 우선순위 평가 기준서.md
```

`git diff --check`는 PASS했다. full untracked status는 수천 개의 기존 temp artifact를 표시했으며 일부 접근 불가 temp directory warning도 있었다. active roots를 분리해 reference 검증을 완료했다.

보존 확인:

- `docs/operations/paper_daily_cycle_commands.md`: 수정·복원 없음
- `idea, PRD, TRD/paper 운영 기능 개발 로드맵 v1.3.md`: 수정·복원 없음
- `outputs/backtest_log.db`: 보호 파일, 수정·복원 없음
- 기존 untracked/temp: 삭제·정리·이동 없음

## Tests and disposition

- 실행: H1/fence/table/code/metadata/migration/reference/Git read-only 검증
- 실행: `python -m pytest tests/test_paper_replay_diff.py -q` — `15 passed in 0.43s`
- 미실행: 전체 pytest suite와 backtest. 코드·설정·전략·운영 동작을 변경하지 않은 문서 정정이기 때문이다.
- 미실행: wrapper, Stage/Gate, Notion API, n8n. 명시적 금지 범위다.

통합, 삭제, required code/structure/reference/Git 검증은 완료됐다. 외부 운영 상태는 추정하지 않았다.

Commit disposition: this review evidence is included in the authorized `ROADMAP-CONSOLIDATION-1-FIX` commit.

Push disposition: push is performed only after final staged-diff validation.

PR: NOT PERFORMED

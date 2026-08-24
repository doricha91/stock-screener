# Summary

`docs/ROADMAP_CURRENT.md`에 기존 공식 로드맵과 기능 벤치마크 기준서의 유효한 내용을 통합했다. 기존 공식 P1을 보존하고, baseline 이후 완료된 MFU-EO2·Stage A AS-OF·Runbook Recovery·Stage F evidence hardening을 현재 증거에 맞게 반영했다. 하나의 공식 우선순위와 capability catalog, 완료 조건, 제외·보류 정책, 최신 실제 Paper Ops snapshot을 canonical 문서에 정리했다.

Migration checklist가 모두 PASS한 뒤 중복 기준서 `docs/00. 투자 시스템 기능 벤치마크 및 개발 우선순위 평가 기준서.md`를 별도 archive 없이 삭제했다.

# Repository baseline

- Branch: `gemini_cli_update`
- Local HEAD: `4fdb9b0da92626a0fee765106389aff2bd756e70`
- Origin HEAD: `4fdb9b0da92626a0fee765106389aff2bd756e70`
- Ahead/behind: `0/0`
- Comparison base: `6b00fe47d825eae7c0307ebffa02359ef6c1c2df`
- Comparison base 선정 이유: `docs/ROADMAP_CURRENT.md`의 마지막 실제 내용 변경 커밋이다. 문서 헤더가 가리키던 `6ef2c85…`는 영문 원본 추가 SHA이고, `6b00fe47…`가 그 로드맵의 한국어 canonical 내용 변경이다.
- Dirty baseline: 작업 전부터 `docs/operations/paper_daily_cycle_commands.md`, `idea, PRD, TRD/paper 운영 기능 개발 로드맵 v1.3.md`, 보호 대상 `outputs/backtest_log.db`가 수정 상태였다. 다수의 untracked 작업·테스트 산출물도 존재했다. 삭제 대상 기준서는 untracked 상태였고 이전 작업에서 작성된 provenance가 확인됐다.

# Documents consolidated

- Retained canonical document: `docs/ROADMAP_CURRENT.md`
- Consolidated source: `docs/00. 투자 시스템 기능 벤치마크 및 개발 우선순위 평가 기준서.md`
- Preserved historical sources: 기존 PRD/TRD, Result, Review Evidence, 작업지시문은 수정하지 않았다.

# Development since the previous roadmap baseline

## Commits

- `7945ea8` — `fix: preserve historical stage f completion evidence`
- `26075e0` — `feat(paper-ops): finalize MFU-EO2 execution outcome contract`
- `a941a36` — `fix(stage-a): enforce as-of provenance and immutable inputs`
- `f979e52` — `feat(paper-ops): add immutable runbook recovery workflow`
- `03bae12` — `docs(paper-ops): record recovery activation and Stage A evidence`
- `4fdb9b0` — `docs(paper-ops): preserve key recovery review evidence`

## Major changed areas

- Baseline-to-HEAD: 63 files, 12,113 insertions, 213 deletions.
- MFU-EO2 outcome derivation/finalization and downstream zero-count compatibility
- Stage A source cutoff, provenance and immutable input contract
- Recovery authorization/state transition workflow
- Stage F historical completion evidence validation/self-heal
- Associated tests, operations contracts and review evidence

## Newly completed capabilities

- MFU-EO2 execution outcome 좁은 계약: `COMPLETE`
- Stage A official AS-OF 좁은 계약: `COMPLETE`
- Runbook Recovery contract: `COMPLETE`
- Stage F historical completion evidence hardening: `COMPLETE`

## Still-partial capabilities

- `ACCT-01`: account-aware 기반은 있으나 legacy default-root fallback과 전체 vertical slice closure가 남아 있다.
- `REPLAY-01`: replay diff/fingerprint는 있으나 stable action identity와 대표 non-empty corpus가 남아 있다.
- `NOTION-02`: property/type/option validation은 있으나 view drift는 수동 evidence 범위다.
- `BT-01`, `DQ-01`, `PA-01`, `PF-01`, `RS-01`, `EV-01`, `UI-01`: 각 subset만 구현됐다.

## Newly confirmed gaps

- `RG-01`: executable formal Research Gate 부재
- `BENCH-02`: cash-flow 정책을 포함한 월적립식 SPY benchmark 부재
- `PF-01`: `strategy_id`와 strategy-account attribution ledger 부재
- `EV-01`: 공통 versioned domain event schema 부재
- `RF-01`: canonical source/expiry/severity risk-flag taxonomy 부재

# Canonical decisions

- Retained file: `docs/ROADMAP_CURRENT.md`
- Deleted file: `docs/00. 투자 시스템 기능 벤치마크 및 개발 우선순위 평가 기준서.md`
- Source of Truth: account-scoped local CSV/JSON/Markdown/SQLite artifact가 기능적 SoT이고 Python이 validation/business judgment를 담당한다. Notion은 staging/input/review/presentation, n8n/Telegram은 allowlisted orchestration/notification만 담당한다.
- Priority sequence: 현재 run closeout -> `ACCT-01` -> `REPLAY-01` -> `NOTION-02` -> retention/observability -> safe CI -> read-only automation -> `BENCH-02` -> research/data/portfolio/consumer 확장.
- Completed baseline: 좁은 MFU 완료와 상위 capability 완료를 구분한다.
- Deferred scope: live broker, 검증되지 않은 Telegram write, 대형 주문 GUI, 두 번째 regime 모델, Fundamental/Hybrid 연구의 즉시 운영 편입.

# Changed files

- `docs/ROADMAP_CURRENT.md`
- `docs/work_results/ROADMAP-CONSOLIDATION-1_Result.md`
- `docs/work_results/ROADMAP-CONSOLIDATION-1_Review_Evidence.md`

# Deleted files

- `docs/00. 투자 시스템 기능 벤치마크 및 개발 우선순위 평가 기준서.md`

삭제 대상은 작업 시작 시 untracked 파일이었으므로 Git tracked diff에는 `D`로 표시되지 않는다. 파일 시스템 부재와 reference scan으로 삭제를 검증했다.

# Behavior changes

Documentation-only. Python 코드, 테스트 코드, 설정, DB schema, 전략 로직, 운영 state, Notion/n8n workflow는 변경하지 않았다.

# Validation performed

- Branch/local/remote SHA와 ahead/behind 확인
- Baseline-to-HEAD commit 및 changed-file 조사
- 두 원본 문서 전체 읽기와 내용 대조
- 최신 Paper Ops state 읽기 전용 확인
- Migration checklist 12개 항목 PASS 후에만 기준서 삭제
- H1 1개, code fence 짝수, Markdown table 열 수, required feature code, branch/full HEAD/date, 단일 공식 priority table 확인
- 삭제 파일 부재 확인
- active/historical reference 분류
- `git diff --check`, status, name-status, stat, 대상 diff 확인
- 최종 외부 검토에서 `REPLAY-01` duplicate key 처리는 `FAIL`이 아니라 `STATUS_WARNING`이며 duplicate row는 auto-match와 일반 row comparison에서 제외된다는 현재 구현을 재확인했다. `ROADMAP_CURRENT`와 Review Evidence의 과도한 FAIL 차단 표현을 실제 계약에 맞게 정정했다.

# Tests run

문서 구조와 내용에 대한 read-only 검증과 `python -m pytest tests/test_paper_replay_diff.py -q`를 실행했다. Targeted pytest 결과는 `15 passed in 0.43s`다. Markdown 표/H1/fence/feature-code 검사도 PowerShell로 수행했다.

# Tests not run and why

코드·설정·전략·운영 동작을 변경하지 않은 문서 정정 작업이므로 전체 pytest suite와 backtest는 실행하지 않았다. Stage/Gate, wrapper, Notion API도 금지 범위에 따라 실행하지 않았다.

# Protected dirty files

- `outputs/backtest_log.db`: 작업 전부터 수정 상태였으며 읽거나 수정·복원하지 않았다.
- `docs/operations/paper_daily_cycle_commands.md`: 기존 수정 보존
- `idea, PRD, TRD/paper 운영 기능 개발 로드맵 v1.3.md`: 기존 수정 보존
- 기존 untracked 파일과 임시 디렉터리: 삭제·정리하지 않음

# Risks and limitations

- 삭제 대상 기준서는 baseline에서 untracked였으므로 삭제 이력은 Git diff 자체로 보존되지 않는다. 통합 전 전체 내용을 읽고 migration checklist와 Review Evidence에 이관 근거를 남겼다.
- worktree의 매우 많은 기존 untracked 파일과 일부 접근 불가 임시 디렉터리 때문에 full status/reference root scan에는 경고가 발생할 수 있다. active 문서 root를 분리해 검색했다.
- Capability 판정은 현재 HEAD와 확인 가능한 local evidence 기준이며 외부 서비스의 현재 화면 상태를 보장하지 않는다.

# Unverified operational facts

- 최신 확인 state의 `updated_at` 이후 실제 execution 또는 Notion 입력 여부
- 현재 Notion view의 시각적 drift 여부
- 2026-08-24 장중/장후 operator action
- 최근 optimizer 공식 운영 run 결과

# Suggested next step

현재 2026-08-24 run에서 actual execution을 확인하고 승인된 절차로 finalize -> Gate 1 -> Stage B-F -> completion을 순서대로 수행한 뒤 evidence를 보존한다. 개발 작업은 공식 P1의 첫 항목 `ACCT-01` closure부터 시작한다.

Commit: PLANNED IN THIS CHANGESET

Push: PLANNED AFTER VALIDATION

PR: NOT PERFORMED

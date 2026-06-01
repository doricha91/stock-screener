BEGIN MFU-PAPER15-CLOSEOUT_MULTI_ACCOUNT_FOUNDATION_AND_ROADMAP_UPDATE

# MFU-PAPER15-CLOSEOUT 작업 지시문
## Multi-account Foundation Closeout + 후속 구현 로드맵 정리

## 목적

PAPER15 다중계좌 foundation 작업을 closeout하고, 후속 기능 개발 단계를 명확히 정리한다.

이번 작업은 문서화/정리 중심이다. 새 기능 구현, Notion actual write/export, paper 원장 수정, broker/API, cloud runner 작업은 포함하지 않는다.

반드시 명시:

이번 PAPER15-CLOSEOUT은 다중계좌 foundation closeout 및 후속 구현 로드맵 정리 작업이며, 새 기능 구현, Notion actual write/export, paper 원장 수정, broker/API, cloud runner 작업은 포함하지 않는다.

## 배경

PAPER15에서 완료/검증된 핵심 범위:

- non-default account root / path resolver / writer guard
- paper_sandbox 실제 workspace 리허설
- Manual Execution commit
- reports / review-template / review-validate
- review-append
- REVIEW_PARTIAL / REVIEW_DONE local workflow_status
- Daily Ops Status DB 설계
- Daily Ops Status mapping/schema
- Daily Ops Status dry-run exporter
- Daily Ops Status actual create/update
- init-account bootstrap command

첨부 로드맵 v1.0의 우선순위는 유지한다.

0. 다중계좌 구축 환경 점검
1. Daily Ops Status Dashboard
1.5. Export / Sync 정책 정리
2. Alert / Monitoring Report
2.5. Replay / Same-date Diff 최소 하네스
3. Notion UI 개선
3.5. Notion Schema Drift Check
4. Universe 변경 Preview → Universe 확장
5. 전략 확장

이번 closeout에서는 위 로드맵에 아래를 반영한다.

- CLI 문제와 개선 방향
- 계좌별 strategy / universe / profile 도입 기준
- PAPER15에서 완료한 것과 후속으로 넘길 것
- PAPER16 이후 추천 구현 순서

## 작업 범위

### 1. PAPER15 closeout 문서 작성

추가 문서:

docs/TRD/mfu_paper15_multi_account_foundation_closeout.md

포함 항목:

1. Purpose
2. Scope / Non-scope
3. Completed MFUs summary
4. Verified flows
5. Actual workspace rehearsal summary
6. Notion Daily Ops Status create/update summary
7. init-account summary
8. Current limitations
9. Deferred items
10. Closeout decision
11. Follow-up roadmap

Verified flows에는 최소 아래를 포함한다.

paper_sandbox:
- plan / eod dry-run
- Manual Execution commit
- reports
- review-template
- review-validate
- review-append
- status REVIEW_PARTIAL
- Daily Ops Status create
- Daily Ops Status update

Current limitations에는 반드시 포함한다.

- strategy/universe/risk profile은 아직 계좌별 공식 config로 구현되지 않음
- paper_default는 아직 legacy outputs/paper_test 정책 유지
- init-account actual workspace create smoke는 정식 운영 계좌로 수행하지 않음
- CLI wrapper / GUI / cloud runner는 구현하지 않음
- multi-account bulk export는 아직 금지

### 2. 로드맵 v1.1 작성 또는 업데이트

기존 로드맵 문서가 repo에 있으면 업데이트한다. 명확한 기존 파일이 없으면 새 문서로 추가한다.

docs/TRD/paper_ops_feature_roadmap_v1_1.md

v1.1 작성 원칙:

- v1.0의 큰 우선순위는 유지한다.
- 0순위 다중계좌 구축은 foundation 완료로 표시한다.
- 다중계좌 고도화 항목은 후속 하위 과제로 분리한다.
- Daily Ops Status Dashboard는 1순위로 유지한다.
- Alert / Replay / Notion UI / Schema Drift / Universe / Strategy 순서는 유지한다.

### 3. CLI 문제 및 개선 방향 정리

로드맵에 “CLI 운영 복잡도와 개선 방향” 섹션을 추가한다.

현재 문제:

- paper.py와 export_paper_to_notion.py 명령이 분산됨
- dry-run / confirm-actual 구분이 어렵다
- 계좌가 늘어나면 명령 실수 위험이 커진다

도입 기준:

- 지금은 새 CLI wrapper를 만들지 않는다.
- PAPER15 closeout에서는 허용/금지 명령만 SOP에 정리한다.
- 반복 운영 패턴이 2~3개 계좌에서 안정화된 후 wrapper CLI를 도입한다.
- GUI / Notion 버튼 / GitHub Actions는 Alert, Replay, Schema Drift 이후 검토한다.

로드맵 반영 위치:

- 1.5 Export / Sync 정책 정리 아래에 command map 정리 포함
- 또는 별도 1.6 CLI 운영 단순화 후보로 추가

단, CLI wrapper 구현은 이번 작업 범위가 아니다.

### 4. strategy / universe / profile 도입 기준 정리

로드맵에 “Account Profile / Strategy / Universe 도입 기준” 섹션을 추가한다.

공통 유지:

- file schema
- Notion schema
- workflow_status
- validation rule
- path safety
- dry-run / confirm-actual policy
- source-of-truth 원칙

계좌별 변수 후보:

- account_id
- display_name
- initial_cash
- currency
- benchmark_id
- universe_id
- strategy_profile_id
- risk_profile_id
- max_positions
- hedge_enabled
- official_run

strategy profile 후보:

- entry_period
- exit_period
- rs_lookback
- atr_period
- score_threshold
- indicator weights
- trailing_stop_multiplier
- regime-specific overrides

실행별 변수:

- run date
- dry-run / actual
- run_mode
- official_run

도입 시점 기준:

- PAPER15에서는 구현하지 않는다.
- Universe 변경 Preview 전에 account profile boundary를 설계한다.
- Universe 확장 단계에서 universe_id / benchmark_id를 공식화한다.
- 전략 확장 단계 전에 strategy_profile_id / risk_profile_id를 공식화한다.
- profile 구현은 Universe/Strategy 확장의 선행조건이지 PAPER15 closeout blocker가 아니다.

### 5. SOP 최소 업데이트

가능하면 아래 문서를 업데이트한다. 파일이 없거나 범위가 커지면 closeout 문서에만 기록한다.

docs/operations/paper_daily_ops.md
docs/operations/paper_notion_ops.md

반영 항목:

- init-account는 non-default 계좌만 허용
- paper_default init 금지
- Daily Ops Status actual export는 paper_sandbox create/update까지 검증됨
- bulk export / paper_default actual export / cloud runner는 아직 금지
- strategy/universe/profile은 후속 과제

## 후속 단계 분류 기준

문서에 아래 기준을 반드시 포함한다.

P0 즉시 처리:
- 데이터 오염, 잘못된 write, 계좌 혼선, source-of-truth 손상 위험

P1 closeout/SOP 포함:
- 구현은 끝났고 운영자가 알아야 하는 절차/한계

P2 후속 로드맵:
- 중요하지만 PAPER15 foundation 완료를 막지 않는 설계/확장 과제

P3 편의성 개선:
- CLI wrapper, GUI, GitHub Actions, Notion 버튼 등 사용성/자동화

예시 분류:

P1:
- PAPER15 closeout
- Daily Ops Status 사용법
- init-account 사용법
- current allowed/forbidden commands

P2:
- account profile boundary
- strategy_profile / universe_profile / risk_profile
- prepare/preview account-aware audit
- duplicate row audit
- paper_default root convergence

P3:
- CLI wrapper
- GitHub Actions
- GUI
- Notion button execution

## 금지 사항

- 새 기능 구현 금지
- CLI wrapper 구현 금지
- Notion actual write/export 실행 금지
- Daily Ops Status actual export 재실행 금지
- paper 원장 CSV 수정 금지
- outputs 하위 파일 수정 금지
- broker/API 실행 금지
- cloud runner 작업 금지
- paper_default migration 금지
- multi-account bulk export 구현 금지
- git add . 금지
- git add -A 금지

## 허용 사항

- 문서 작성/수정
- 기존 코드 read-only 조사
- read-only status/dry-run 명령 결과 인용
- 로드맵 v1.1 작성
- SOP 최소 업데이트
- git diff 확인
- git status 확인

## 검증 명령

Windows CMD 기준:

```cmd
git diff -- docs\TRD\mfu_paper15_multi_account_foundation_closeout.md
git diff -- docs\TRD\paper_ops_feature_roadmap_v1_1.md
git diff -- docs\operations\paper_daily_ops.md docs\operations\paper_notion_ops.md
git status --short
```

필요 시 read-only 확인만 허용:

```cmd
python scripts\paper.py init-account --account-id paper_growth --initial-cash 100000 --currency USD --date 20260601 --dry-run --json
python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --dry-run --json
```

## 성공 기준

- PAPER15 완료 범위가 명확히 정리된다.
- PAPER15에서 검증한 실제 흐름과 검증하지 않은 한계가 구분된다.
- 로드맵 v1.1에 CLI 문제와 개선 방향이 반영된다.
- 로드맵 v1.1에 strategy/universe/profile 도입 기준이 반영된다.
- 후속 과제가 P0/P1/P2/P3 또는 유사한 기준으로 분류된다.
- SOP에 현재 허용/금지 운영 정책이 최소 반영된다.
- 새 기능 구현과 actual write는 발생하지 않는다.
- outputs와 paper 원장은 수정되지 않는다.

## 결과 보고 형식

5천자 이내.

포함:

1. Summary
2. 생성/수정한 파일
3. PAPER15 closeout 판단
4. 완료된 기능 요약
5. 검증된 flow
6. 남은 한계
7. 로드맵 v1.1 변경 요약
8. CLI 문제 및 개선 방향 반영 내용
9. strategy/universe/profile 도입 기준
10. SOP 업데이트 내용
11. 후속 단계 P0/P1/P2/P3 분류
12. 코드 변경 여부
13. actual write/export 실행 여부
14. outputs 변경 여부
15. 다음 추천 MFU

반드시 명시:

이번 PAPER15-CLOSEOUT은 다중계좌 foundation closeout 및 후속 구현 로드맵 정리 작업이며, 새 기능 구현, Notion actual write/export, paper 원장 수정, broker/API, cloud runner 작업은 포함하지 않는다.

END MFU-PAPER15-CLOSEOUT_MULTI_ACCOUNT_FOUNDATION_AND_ROADMAP_UPDATE

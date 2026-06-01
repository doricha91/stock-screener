BEGIN MFU-PAPER15-CLOSEOUT-ROADMAP-CONSISTENCY-CHECK

# PAPER15 Closeout 문서 표현 보정 + 로드맵/다중계좌 변수 정합성 점검

## 목적

PAPER15-CLOSEOUT 결과물에서 다음 사항이 정확히 반영됐는지 확인하고, 누락/혼동이 있으면 문서만 최소 수정한다.

1. “account profile” 표현이 후속 strategy/risk/universe profile과 혼동되지 않도록 정리
2. Daily Ops Status actual create/update는 PAPER15 진행 중 paper_sandbox 대상으로 이미 검증된 사항이며, 이번 closeout 작업에서는 추가 actual write/export를 실행하지 않았다는 점 명시
3. 전체 로드맵 v1.1이 현재 프로젝트 방향에 맞게 작성됐는지 점검
4. 다중계좌 변수(account_id, display_name, initial_cash, currency, benchmark_id, universe_id, strategy_profile_id, risk_profile_id 등)가 포함되어 있는지 점검
5. 다중계좌 변수와 profile 도입 기준이 향후 작업 방향상 적절한 위치에 배치되어 있는지 점검

## 배경

PAPER15는 “완전한 다중전략 운영 시스템”이 아니라 “다중계좌 foundation” closeout이다.

따라서 문서에서 다음 경계가 명확해야 한다.

- PAPER15에서 완료된 것은 non-default account root/path/writer safety foundation이다.
- strategy/universe/risk profile은 아직 계좌별 공식 config로 구현되지 않았다.
- Daily Ops Status limited actual create/update는 PAPER15 진행 중 paper_sandbox 대상으로 검증된 사항이다.
- 이번 closeout/문서 점검 작업에서는 Notion actual write/export를 새로 실행하면 안 된다.
- CSV/JSON/Markdown/SQLite가 source-of-truth이고 Notion은 input/review/staging/presentation layer다.

## 대상 파일

우선 아래 파일을 점검한다.

- docs/TRD/mfu_paper15_multi_account_foundation_closeout.md
- docs/TRD/paper_ops_feature_roadmap_v1_1.md
- docs/operations/paper_daily_ops.md
- docs/operations/paper_notion_ops.md

로드맵 v1.0 문서가 존재하면 함께 참고한다. 단, 새 로드맵 파일을 불필요하게 만들지 않는다.

## 작업 범위

### 1. account profile 표현 점검/수정

closeout 문서와 roadmap/SOP에서 다음 표현을 검색한다.

- account profile
- non-default account profile
- strategy profile
- risk profile
- universe profile
- account profile boundary

다음과 같은 혼동 가능성이 있으면 수정한다.

잘못 이해될 수 있는 표현:

- non-default account profile / path resolver / writer guard

권장 표현:

- non-default account root / path resolver / writer guard
- non-default account root/config foundation / path resolver / writer guard

단, “account profile boundary”처럼 후속 설계 과제를 의미하는 표현은 유지해도 된다. 대신 그것이 PAPER15에서 구현 완료된 기능이 아니라 P2 후속 과제임을 분명히 한다.

### 2. actual 검증과 이번 작업의 actual 미실행 구분

문서에 아래 취지가 명확히 들어갔는지 확인한다.

- Daily Ops Status limited actual create/update는 PAPER15 진행 중 paper_sandbox 대상으로 이미 검증됨
- 이번 PAPER15 closeout/consistency check 작업에서는 추가 Notion actual write/export를 실행하지 않음
- outputs/paper 원장 수정 없음
- source-of-truth 파일을 새로 변경하는 actual 운영 작업 없음

누락되어 있으면 closeout 문서 또는 Notion SOP addendum에 다음 문장을 자연스럽게 추가한다.

“Daily Ops Status limited actual create/update는 PAPER15 진행 중 paper_sandbox 대상으로 이미 검증된 사항이며, 본 closeout 작업에서는 추가 Notion actual write/export를 실행하지 않는다.”

### 3. 로드맵 v1.1 전체 구조 점검

docs/TRD/paper_ops_feature_roadmap_v1_1.md를 읽고 다음을 점검한다.

- v1.0의 큰 순서가 유지되는가
- 0순위 multi-account foundation이 완료로 표시되어 있는가
- Daily Ops Status Dashboard가 다음 자연스러운 단계로 배치되어 있는가
- Export/Sync 정책 정리가 Daily Ops Status 이후 또는 그 주변의 적절한 위치에 있는가
- Alert/Monitoring, Replay/Same-date Diff, Schema Drift Check, Universe 확장, Strategy 확장이 과도하게 앞당겨지지 않았는가
- CLI wrapper, GUI, GitHub Actions, Notion button execution이 P3 편의성 개선으로 분류되어 있는가
- paper_default root convergence, duplicate row audit, prepare/preview account-aware audit이 P2 또는 적절한 후속 과제로 분류되어 있는가

문서 내 위치가 어색하거나 우선순위가 잘못 읽힐 수 있으면 최소 수정한다.

### 4. 다중계좌 변수 포함 여부 점검

로드맵 또는 closeout 문서에 다음 계좌별 변수 후보가 포함되어 있는지 확인한다.

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

strategy profile 후보가 포함되어 있는지도 확인한다.

- entry_period
- exit_period
- rs_lookback
- atr_period
- score_threshold
- indicator weights
- trailing_stop_multiplier
- regime-specific overrides

실행별 변수 후보가 포함되어 있는지도 확인한다.

- run date
- dry-run / actual
- run_mode
- official_run

누락되어 있으면 roadmap v1.1의 “Account/Profile Boundary”, “Universe/Strategy Expansion prerequisites”, 또는 이에 준하는 적절한 후속 과제 섹션에 추가한다.

중요: 이 변수들을 구현하지 말고, 후속 설계 기준으로만 문서화한다.

### 5. 도입 시점 정합성 점검

다음 기준이 명확히 들어갔는지 확인한다.

- PAPER15에서는 strategy/universe/risk profile을 구현하지 않음
- Universe 변경 Preview 전에 account profile boundary 설계
- Universe 확장 단계에서 universe_id / benchmark_id 공식화
- 전략 확장 전에 strategy_profile_id / risk_profile_id 공식화
- profile 구현은 Universe/Strategy 확장의 선행조건이지만 PAPER15 closeout blocker는 아님

누락되었거나 위치가 부적절하면 roadmap v1.1에 보정한다.

## Non-scope

이번 작업에서는 절대 하지 않는다.

- Python 코드 수정
- 신규 CLI 구현
- wrapper CLI 구현
- GUI / GitHub Actions / Notion button 구현
- Notion actual write/export 실행
- broker/API 연동
- cloud runner 작업
- outputs/paper 원장 수정
- paper_default migration
- 신규 계좌 생성 또는 init-account actual 실행
- 테스트 fixture 외 실제 운영 데이터 수정

## 검증 명령

Windows CMD 기준으로 아래를 실행한다.

```cmd
git status --short
git diff -- docs\TRD\mfu_paper15_multi_account_foundation_closeout.md docs\TRD\paper_ops_feature_roadmap_v1_1.md docs\operations\paper_daily_ops.md docs\operations\paper_notion_ops.md
findstr /S /N /I "account profile non-default account profile strategy_profile_id risk_profile_id universe_id Daily Ops Status actual write export" docs\TRD\mfu_paper15_multi_account_foundation_closeout.md docs\TRD\paper_ops_feature_roadmap_v1_1.md docs\operations\paper_daily_ops.md docs\operations\paper_notion_ops.md
```

문서 수정만 있으므로 pytest는 필수 아님. 단, 프로젝트 정책상 문서 변경에도 smoke가 필요하면 가장 가벼운 문서/CLI smoke만 수행하고 보고한다.

## 성공 기준

- “non-default account profile” 등 혼동 가능한 표현이 정리됨
- PAPER15 완료 범위와 후속 profile 설계 과제가 분리됨
- Daily Ops Status actual 검증은 과거 paper_sandbox 검증 사항이고, 이번 작업에서는 actual write/export 미실행임이 명확함
- roadmap v1.1에 다중계좌 변수 후보와 도입 시점이 포함됨
- roadmap v1.1의 후속 작업 위치가 P0/P1/P2/P3 기준과 일치함
- SOP 업데이트는 최소 addendum 수준을 넘지 않음
- 코드 변경 없음
- outputs/paper 원장 변경 없음
- Notion actual write/export 실행 없음

## Git 주의사항

금지:

```cmd
git add .
git add -A
```

허용되는 stage 예시:

```cmd
git add docs\TRD\mfu_paper15_multi_account_foundation_closeout.md
git add docs\TRD\paper_ops_feature_roadmap_v1_1.md
git add docs\operations\paper_daily_ops.md
git add docs\operations\paper_notion_ops.md
```

실제로 수정된 파일만 개별 stage한다.

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 수정한 파일
3. 내가 지적한 2가지 사항 반영 여부
   - account profile 표현 정리 여부
   - actual 검증 vs 이번 actual 미실행 구분 여부
4. roadmap v1.1 점검 결과
5. 다중계좌 변수 포함 여부
6. 다중계좌 변수/프로필 도입 위치가 적절한지 판단
7. 코드 변경 여부
8. Notion actual write/export 실행 여부
9. outputs/paper 원장 변경 여부
10. git diff 요약
11. 남은 리스크 또는 후속 권장 작업

END MFU-PAPER15-CLOSEOUT-ROADMAP-CONSISTENCY-CHECK
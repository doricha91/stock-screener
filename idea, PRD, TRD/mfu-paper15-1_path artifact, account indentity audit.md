BEGIN MFU-PAPER15-1_PATH_ARTIFACT_ACCOUNT_IDENTITY_AUDIT

# MFU-PAPER15-1 작업 지시문: Path/Artifact Audit + Account Identity Model

## 목적

MFU-PAPER15-1의 목표는 현재 stock-screener의 paper 운영 시스템이 단일계좌 전제를 얼마나 강하게 가지고 있는지 조사하고, 향후 다중계좌 확장을 위한 최소 account identity 모델을 설계하는 것이다.

이번 단계는 조사/설계 전용이다.  
코드 수정, DB write, paper 원장 수정, Notion write/export, migration 구현은 하지 않는다.

반드시 명시:

```text
이번 PAPER15-1은 다중계좌 구축 환경 점검을 위한 path/artifact audit 및 account identity model 설계이며, 코드 구현, DB write, paper 원장 수정, Notion write/export, migration 구현은 포함하지 않는다.
```

## 배경

현재 paper 운영은 `outputs/paper_test` 단일 디렉터리와 단일 paper account를 전제로 구성되어 있다.

대표 artifact:

```text
outputs/paper_test/paper_execution_log.csv
outputs/paper_test/paper_account_snapshot.csv
outputs/paper_test/paper_position_snapshot.csv
outputs/paper_test/paper_current_state_YYYYMMDD.json
outputs/paper_test/daily_action_plan_YYYYMMDD.md
outputs/paper_test/reports/
outputs/paper_test/reviews/
outputs/paper_test/config_snapshots/
outputs/paper_test/replay_diff/
```

앞으로 Daily Ops Status Dashboard, Alert/Monitoring Report, Notion UI 개선, Universe 확장, 전략 확장 등을 진행하기 전에 다중계좌 가능성을 먼저 점검해야 한다.

이유:

```text
단일계좌 전제 상태에서 dashboard, alert, Notion UI를 고도화하면 나중에 다중계좌 전환 시 artifact 경로, status 판정, Notion external key, report export 구조를 다시 수정해야 할 수 있다.
```

## 작업 범위

### 1. Path / Artifact 의존성 조사

아래 파일과 관련 경로 사용처를 조사한다.

```text
core/paths.py
core/paper_account_state.py
core/paper_execution_log.py
core/paper_account_snapshot.py
core/paper_position_snapshot.py
core/paper_current_state_storage.py
core/paper_current_state_serializer.py
core/paper_status.py
core/paper_weekly_status.py
core/paper_benchmark_comparison.py
core/paper_daily_review_summary.py
core/paper_manual_execution_commit.py
core/paper_manual_review_append_commit.py
core/notion_exporters.py
core/notion_manual_execution_importer.py
core/notion_manual_review_importer.py
scripts/paper.py
scripts/export_paper_to_notion.py
scripts/import_notion_executions.py
scripts/import_notion_reviews.py
scripts/sync_notion_execution_status.py
scripts/sync_notion_review_status.py
```

조사 질문:

```text
1. outputs/paper_test 고정 의존성이 어디에 있는가?
2. paper_execution_log.csv는 계좌별 분리가 필요한가?
3. paper_account_snapshot.csv는 계좌별 분리가 필요한가?
4. paper_position_snapshot.csv는 계좌별 분리가 필요한가?
5. paper_current_state_YYYYMMDD.json은 계좌별 분리가 필요한가?
6. reports/, reviews/, config_snapshots/, replay_diff/는 계좌별 분리가 필요한가?
7. dev_backups/는 계좌별 분리가 필요한가, 공통으로 둬도 되는가?
8. front_test와 paper_test의 경계가 다중계좌 도입 시 영향을 받는가?
9. status/dashboard/weekly/benchmark/report 계층은 account_id 없이 동작 가능한가?
10. Notion export/import/status sync에서 계좌 충돌 가능성이 있는가?
```

### 2. Account Identity 모델 조사 및 설계

현재 `PaperAccountState` 또는 관련 artifact에 계좌 식별자가 있는지 조사한다.

필드 후보:

```text
account_id
display_name
currency
initial_cash
strategy_profile
universe_profile
benchmark_profile
notion_profile
broker
account_type
is_default
```

설계 질문:

```text
1. 최소 필수 식별자는 account_id 하나로 충분한가?
2. 기존 단일계좌는 default account로 해석할 수 있는가?
3. currency와 initial_cash는 account identity에 포함되어야 하는가?
4. strategy_profile과 universe_profile은 account identity에 포함해야 하는가, 별도 config로 분리해야 하는가?
5. Notion profile은 계좌별로 분리해야 하는가?
6. live/broker 계좌까지 고려한 이름을 지금부터 써야 하는가, paper 전용으로 제한해야 하는가?
7. 과거 데이터에 account_id가 없을 때 default로 해석 가능한가?
```

### 3. Artifact 분류표 작성

artifact를 아래 4개 그룹으로 분류한다.

```text
A. 계좌별로 반드시 분리해야 하는 artifact
B. 계좌별 분리가 권장되는 artifact
C. 공통으로 유지해도 되는 artifact
D. 추가 조사가 필요한 artifact
```

각 항목에는 이유를 적는다.

예시:

```text
artifact: outputs/paper_test/paper_account_snapshot.csv
분류: A
이유: cash/equity/position_count가 계좌 상태에 종속됨
다중계좌 리스크: account_id 없이 합쳐지면 dashboard와 weekly status가 오염됨
권장 방향: account-specific output root 또는 account_id column 필요
```

## 산출물

아래 문서를 작성한다.

```text
docs/TRD/mfu_paper15_1_multi_account_path_artifact_account_identity.md
```

문서에는 반드시 아래 섹션을 포함한다.

```text
1. Purpose
2. Scope / Non-scope
3. Current single-account assumptions
4. Path / artifact dependency audit
5. Artifact classification
6. Account identity field candidates
7. Recommended minimum account identity model
8. Backward compatibility considerations
9. Open questions
10. Recommended next MFU
```

## 금지 사항

```text
코드 수정 금지
DB write 금지
paper 원장 CSV 수정 금지
outputs/paper_test 파일 수정 금지
outputs/front_test 파일 수정 금지
Notion API write 금지
Notion export 실행 금지
Notion status sync 실행 금지
migration script 작성 금지
paper.py prepare/preview/commit/review/review-append 실행 금지
git add . 금지
git add -A 금지
```

## 허용 사항

```text
파일 읽기
코드 검색
CSV header 확인
JSON 구조 확인
Markdown 문서 읽기
테스트 파일 읽기
문서 작성
read-only 명령 실행
```

허용 가능한 read-only 명령 예시:

```cmd
python scripts\paper.py status --json
type core\paths.py
type core\paper_account_state.py
dir outputs\paper_test
```

writer 성격의 명령은 실행하지 않는다.

## 검증

문서 작업이므로 자동 테스트는 필수 아님.

필수 확인:

```cmd
git diff -- docs/TRD/mfu_paper15_1_multi_account_path_artifact_account_identity.md
git status --short
```

확인 기준:

```text
수정 파일은 원칙적으로 docs/TRD/mfu_paper15_1_multi_account_path_artifact_account_identity.md 하나여야 한다.
코드 파일은 수정되지 않아야 한다.
outputs/ 하위 파일은 수정되지 않아야 한다.
```

## 성공 기준

```text
현재 paper 운영의 단일계좌 전제가 문서화된다.
outputs/paper_test 고정 의존성이 정리된다.
계좌별 분리 필요 artifact와 공통 artifact가 구분된다.
최소 account identity 모델 초안이 제시된다.
기존 단일계좌를 default account로 유지할 수 있는지 판단 근거가 정리된다.
다음 MFU에서 path resolver / CLI 영향도 조사로 넘어갈 수 있다.
코드와 원장 파일은 수정하지 않는다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 조사한 파일
3. 단일계좌 고정 의존성
4. 계좌별 분리 필요 artifact
5. 공통 유지 가능 artifact
6. account identity 최소 모델 제안
7. backward compatibility 판단
8. 주요 리스크
9. open questions
10. 다음 MFU 제안
11. 코드 변경 여부
12. paper 원장 CSV 변경 여부
13. outputs/front_test 변경 여부
14. outputs/paper_test 변경 여부
```

반드시 명시:

```text
이번 PAPER15-1은 다중계좌 구축 환경 점검을 위한 path/artifact audit 및 account identity model 설계이며, 코드 구현, DB write, paper 원장 수정, Notion write/export, migration 구현은 포함하지 않는다.
```

END MFU-PAPER15-1_PATH_ARTIFACT_ACCOUNT_IDENTITY_AUDIT
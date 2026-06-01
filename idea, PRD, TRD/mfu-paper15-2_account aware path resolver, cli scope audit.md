BEGIN MFU-PAPER15-2_ACCOUNT_PATH_RESOLVER_CLI_SCOPE_AUDIT

# MFU-PAPER15-2 작업 지시문: Account-aware Path Resolver / CLI Scope Audit

## 목적

MFU-PAPER15-2의 목표는 PAPER15-1 조사 결과를 바탕으로, 향후 다중계좌 구조를 도입하기 위한 account-aware path resolver 설계와 CLI account scope 영향도를 조사하는 것이다.

이번 단계는 조사/설계 전용이다.  
코드 구현, DB write, paper 원장 수정, Notion write/export, migration 구현은 하지 않는다.

반드시 명시:

```text
이번 PAPER15-2는 account-aware path resolver 및 CLI account scope 조사/설계이며, 코드 구현, DB write, paper 원장 수정, Notion write/export, migration 구현은 포함하지 않는다.
```

## 확정된 전제

PAPER15-1 결과에 따라 아래 방향은 확정 전제로 둔다.

```text
1. 기존 outputs/paper_test는 account_id=paper_default인 legacy default account로 해석한다.
2. 신규 다중계좌 artifact root는 outputs/paper_accounts/{account_id}/ 방향으로 설계한다.
3. Notion은 계좌별 DB 분리가 아니라 단일 DB + account_id property 방향으로 설계한다.
4. strategy_profile, universe_profile, benchmark_profile, notion_profile은 account identity core가 아니라 별도 profile/reference 계층으로 분리한다.
```

## 배경

현재 paper 운영은 outputs/paper_test 단일 root와 account-less artifact를 전제로 한다.

PAPER15-1에서 확인된 주요 리스크:

```text
- paper_execution_log.csv가 account-less라 trade_id 충돌 가능성이 있음
- paper_account_snapshot.csv / paper_position_snapshot.csv가 same-date replace 구조라 계좌 간 overwrite 위험이 있음
- paper_current_state_YYYYMMDD.json이 계좌별로 분리되지 않음
- status / weekly / benchmark / daily review가 단일 paper_root 기준으로 집계됨
- Notion external key가 account_id를 포함하지 않아 계좌 간 row 충돌 가능성이 있음
```

따라서 다음 구현 단계로 가기 전, path resolver와 CLI account scope를 먼저 설계해야 한다.

## 작업 범위

### 1. Account-aware path resolver 설계

아래 구조를 기준으로 path resolver 설계를 제안한다.

```text
Legacy:
outputs/paper_test/

New:
outputs/paper_accounts/{account_id}/
```

조사/설계 질문:

```text
1. legacy outputs/paper_test를 paper_default로 읽는 resolver가 필요한가?
2. 신규 계좌는 outputs/paper_accounts/{account_id}/만 사용하게 할 것인가?
3. paper_default도 장기적으로 outputs/paper_accounts/paper_default/로 옮길 것인가?
4. legacy root와 new root를 동시에 지원할 때 우선순위는 어떻게 둘 것인가?
5. account_id validation 규칙은 무엇으로 둘 것인가?
6. 잘못된 account_id 입력 시 어떤 error를 낼 것인가?
7. tests에서 임시 account root를 어떻게 주입할 것인가?
```

설계 대상 path:

```text
paper_execution_log.csv
paper_account_snapshot.csv
paper_position_snapshot.csv
paper_current_state_YYYYMMDD.json
daily_action_plan_YYYYMMDD.md
reports/
reviews/
config_snapshots/
replay_diff/
archive/
```

### 2. core/paths.py 영향도 조사

아래 함수들이 account_id를 받거나 account context를 통해 동작해야 하는지 조사한다.

```text
paper_current_state_snapshot_path
paper_daily_action_plan_path
paper_execution_log_path
paper_account_snapshot_path
paper_position_snapshot_path
paper_reports_dir
paper_reviews_dir
paper_performance_summary_path
paper_config_snapshots_dir
paper_config_snapshot_path
paper_config_snapshot_archive_dir
paper_replay_diff_dir
paper_regenerated_daily_action_plan_path
paper_daily_plan_diff_report_path
paper_replay_diff_config_snapshot_path
paper_replay_diff_config_snapshot_archive_dir
dev_backups_dir
```

분류 기준:

```text
A. 반드시 account-aware 필요
B. account-aware 권장
C. 공통 유지 가능
D. 추가 조사 필요
```

### 3. CLI account scope 영향도 조사

아래 CLI에 --account-id가 필요한지 조사한다.

```text
scripts/paper.py prepare
scripts/paper.py preview
scripts/paper.py commit
scripts/paper.py status
scripts/paper.py weekly-status
scripts/paper.py benchmark
scripts/paper.py plan
scripts/paper.py eod
scripts/paper.py reports
scripts/paper.py review
scripts/paper.py review-template
scripts/paper.py review-validate
scripts/paper.py review-append
scripts/export_paper_to_notion.py
scripts/import_notion_executions.py
scripts/import_notion_reviews.py
scripts/sync_notion_execution_status.py
scripts/sync_notion_review_status.py
```

검토 질문:

```text
1. 모든 paper CLI에 --account-id를 붙여야 하는가?
2. 기본값은 paper_default로 둘 것인가?
3. 환경변수 STOCK_SCREENER_PAPER_ACCOUNT_ID를 둘 것인가?
4. config/account_profiles.json 같은 파일이 필요한가?
5. CLI 인자, 환경변수, config 기본값 중 우선순위는 어떻게 둘 것인가?
6. 기존 명령을 그대로 실행하면 paper_default로 동작하게 할 수 있는가?
7. Notion import/export/sync는 account_id 없을 때 차단할 것인가, paper_default로 해석할 것인가?
```

권장 우선순위 후보:

```text
1. CLI --account-id
2. 환경변수 STOCK_SCREENER_PAPER_ACCOUNT_ID
3. account profile config의 default
4. fallback paper_default
```

### 4. 다음 구현 MFU 초안 제안

이번 작업은 설계 전용이므로, 구현은 하지 않는다.  
대신 다음 구현 MFU를 쪼개서 제안한다.

예상 후속 MFU 후보:

```text
MFU-PAPER15-3A: account profile model / config skeleton
MFU-PAPER15-3B: account-aware path resolver implementation
MFU-PAPER15-3C: paper.py --account-id read-only command support
MFU-PAPER15-3D: writer command account guard design
MFU-PAPER15-3E: Notion external key account namespace design
```

## 조사 대상 파일

```text
docs/TRD/mfu_paper15_1_multi_account_path_artifact_account_identity.md
core/paths.py
core/paper_account_state.py
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
tests/
```

## 산출물

아래 문서를 작성한다.

```text
docs/TRD/mfu_paper15_2_account_path_resolver_cli_scope.md
```

문서에는 반드시 아래 섹션을 포함한다.

```text
1. Purpose
2. Scope / Non-scope
3. Confirmed decisions from PAPER15-1
4. Proposed account-aware output root policy
5. Legacy paper_test compatibility policy
6. Path resolver design
7. core/paths.py impact table
8. CLI account scope impact table
9. Account selection precedence
10. Risks / open questions
11. Recommended implementation MFUs
```

## 금지 사항

```text
코드 수정 금지
DB write 금지
paper 원장 CSV 수정 금지
outputs/paper_test 파일 수정 금지
outputs/paper_accounts 생성 금지
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
문서 읽기
CSV header 확인
JSON 구조 확인
테스트 파일 읽기
문서 작성
read-only 명령 실행
```

허용 가능한 read-only 명령 예시:

```cmd
python scripts\paper.py status --json
type core\paths.py
type scripts\paper.py
dir outputs\paper_test
```

writer 성격의 명령은 실행하지 않는다.

## 검증

필수 확인:

```cmd
git diff -- docs/TRD/mfu_paper15_2_account_path_resolver_cli_scope.md
git status --short
```

확인 기준:

```text
수정 파일은 원칙적으로 docs/TRD/mfu_paper15_2_account_path_resolver_cli_scope.md 하나여야 한다.
코드 파일은 수정되지 않아야 한다.
outputs/ 하위 파일은 수정되지 않아야 한다.
```

## 성공 기준

```text
account-aware path resolver의 설계 방향이 정리된다.
legacy outputs/paper_test = paper_default 호환 정책이 명확해진다.
outputs/paper_accounts/{account_id}/ 신규 root 정책이 정리된다.
core/paths.py 함수별 account-aware 필요 여부가 분류된다.
paper.py 및 Notion import/export/sync CLI별 --account-id 필요 여부가 정리된다.
account selection precedence가 제안된다.
다음 구현 MFU가 실행 가능한 단위로 제안된다.
코드와 원장 파일은 수정하지 않는다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 조사한 파일
3. path resolver 설계 요약
4. legacy paper_test 호환 정책
5. core/paths.py 영향도
6. CLI별 --account-id 필요 여부
7. account selection precedence 제안
8. 주요 리스크
9. open questions
10. 다음 구현 MFU 제안
11. 코드 변경 여부
12. paper 원장 CSV 변경 여부
13. outputs/front_test 변경 여부
14. outputs/paper_test 변경 여부
15. outputs/paper_accounts 생성 여부
```

반드시 명시:

```text
이번 PAPER15-2는 account-aware path resolver 및 CLI account scope 조사/설계이며, 코드 구현, DB write, paper 원장 수정, Notion write/export, migration 구현은 포함하지 않는다.
```

END MFU-PAPER15-2_ACCOUNT_PATH_RESOLVER_CLI_SCOPE_AUDIT
BEGIN MFU-PAPER17-6-ENV-BASED-NOTION-SETTINGS-FOR-DUPLICATE-AUDIT

# PAPER17-6 .env 기반 Notion Settings로 Duplicate Audit CLI 동작 정합화 + Read-only Smoke 재시도

## 목적

PAPER17-5에서 duplicate audit read-only smoke가 `config/notion_settings.json` 부재로 `settings_error`에서 중단됐다.

하지만 현재 프로젝트 운영 방식은 Notion token과 data source ID를 `config/notion_settings.json`이 아니라 `.env` / 환경변수에서 관리하는 방식이다.

이번 작업의 목적은 다음이다.

1. `scripts/dev/audit_notion_duplicates.py`가 `.env` / 환경변수 기반 설정으로도 동작하도록 정합성을 맞춘다.
2. `config/notion_settings.json`이 없어도 `NOTION_TOKEN`과 `NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID`가 있으면 `daily_ops_status` duplicate audit read-only query가 가능하게 한다.
3. secret 값은 출력하거나 커밋하지 않는다.
4. 수정 후 `paper_sandbox / 2026-05-20` 기준 read-only smoke를 1회 재실행한다.
5. Notion actual write/export/sync는 절대 실행하지 않는다.

## 배경

PAPER17-4A에서 `daily_ops_status` duplicate audit dry-run 기능이 구현됐다.

PAPER17-5 결과:

- smoke command는 실행됨
- 결과는 `settings_error`
- 원인은 `config/notion_settings.json` 부재
- Notion API read 호출 없음
- Notion write/export/sync 없음
- `write_executed=false`

이번 작업은 “settings 파일을 새로 만들자”가 아니다.  
사용자가 실제로 쓰는 `.env` 기반 Notion 설정 방식에 duplicate audit CLI를 맞추는 작업이다.

## 대상 파일

수정 후보:

```text
scripts/dev/audit_notion_duplicates.py
core/notion_duplicate_audit.py
core/notion_settings.py
tests/test_notion_duplicate_audit.py
docs/TRD/mfu_paper17_notion_settings_preflight_and_smoke_rerun.md
docs/TRD/mfu_paper17_daily_ops_duplicate_audit_dry_run.md
```

가능하면 수정 범위는 최소화한다.

## 작업 범위

### 1. 기존 settings 로딩 방식 확인

아래를 확인한다.

```cmd
findstr /S /N /I "load_dotenv dotenv NOTION_TOKEN NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID load_notion_settings allow_missing" *.py core\*.py scripts\*.py scripts\dev\*.py
```

확인할 것:

- 프로젝트에서 `.env`를 이미 로드하는 convention이 있는가
- `python-dotenv` 또는 유사 의존성이 이미 쓰이는가
- `load_notion_settings(allow_missing=False)`가 config 파일 부재 시 무조건 실패하는가
- config 파일 없이 환경변수만으로 Daily Ops Status data source ID를 읽을 수 있는 구조가 있는가

### 2. env-only fallback 구현

`audit_notion_duplicates.py` 또는 적절한 settings helper에 다음 정책을 구현한다.

정책:

- 기존 `config/notion_settings.json` 기반 동작은 깨지지 않아야 한다.
- `config/notion_settings.json`이 없어도 아래 환경변수가 있으면 duplicate audit read-only query가 가능해야 한다.

```text
NOTION_TOKEN
NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID
```

- `.env` 파일이 존재하면 기존 repo convention에 맞게 로드한다.
- `.env` 파일 자체를 출력하거나 커밋하지 않는다.
- token / data source ID 값은 로그나 JSON 결과에 원문 출력하지 않는다.
- env 값이 없으면 기존처럼 안전하게 `settings_error`로 중단한다.
- 어떤 경우에도 write API를 호출하지 않는다.

### 3. smoke 전 readiness 출력

가능하면 CLI 또는 내부 preflight에서 secret-safe readiness를 확인할 수 있게 한다.

출력 예:

```json
{
  "settings_source": "env",
  "notion_token": "set",
  "daily_ops_status_data_source_id": "set",
  "secrets_printed": false
}
```

단, 실제 token이나 data source ID 전체값은 출력하지 않는다.  
구현이 과해지면 문서에만 기록하고 CLI 출력은 최소 유지해도 된다.

### 4. 테스트 보강

테스트를 추가 또는 수정한다.

필수 테스트 후보:

- config 파일이 없어도 env 값이 있으면 settings resolution 성공
- env 값이 없으면 settings_error
- env 기반 경로에서도 `write_executed=false`
- env 기반 경로에서도 `query_by_external_key`만 사용
- token / data source ID가 출력 payload에 원문 노출되지 않음
- `daily_ops_status` 외 target은 계속 차단

실제 Notion API를 호출하지 말고 fake/mock client를 사용한다.

### 5. read-only smoke 재실행

테스트 통과 후 아래 명령을 1회 실행한다.

```cmd
python scripts\dev\audit_notion_duplicates.py --target daily_ops_status --account-id paper_sandbox --date 2026-05-20 --json
```

허용:

- Notion API read/query 호출

금지:

- Notion API write 호출
- Notion actual export/sync
- create_page / update_page / upsert_page_by_external_key
- Daily Ops Status actual rerun

결과에 반드시 `write_executed=false`가 있어야 한다.

### 6. 문서 업데이트

아래 문서 중 필요한 곳만 최소 수정한다.

```text
docs/TRD/mfu_paper17_notion_settings_preflight_and_smoke_rerun.md
docs/TRD/mfu_paper17_daily_ops_duplicate_audit_dry_run.md
```

반영할 내용:

- Duplicate audit CLI는 `.env` / 환경변수 기반 settings도 지원한다.
- 필요한 값은 `NOTION_TOKEN`, `NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID`다.
- `config/notion_settings.json`은 필수 경로가 아니라 선택 경로다.
- secret 파일과 `.env`는 커밋 금지다.
- smoke 결과를 기록한다.

## 검증 명령

Windows CMD 기준으로 실행한다.

```cmd
git status --short

python scripts\dev\audit_notion_duplicates.py --help

pytest tests\test_notion_duplicate_audit.py

python scripts\dev\audit_notion_duplicates.py --target daily_ops_status --account-id paper_sandbox --date 2026-05-20 --json

git diff --check -- scripts\dev\audit_notion_duplicates.py core\notion_duplicate_audit.py core\notion_settings.py tests\test_notion_duplicate_audit.py docs\TRD\mfu_paper17_notion_settings_preflight_and_smoke_rerun.md docs\TRD\mfu_paper17_daily_ops_duplicate_audit_dry_run.md
```

수정하지 않은 파일이 diff check 대상에 포함되어도 문제는 없지만, 실제 stage는 수정된 파일만 한다.

## Non-scope

이번 작업에서는 절대 하지 않는다.

- Notion actual write/export/sync
- Notion API write 호출
- create_page / update_page / upsert_page_by_external_key 호출
- Daily Ops Status actual rerun
- paper_default actual export
- multi-account bulk export
- detail exporter actual
- Manual Execution/Review status sync actual
- outputs/paper 원장 수정
- `.env` 커밋
- `config/notion_settings.json` 커밋
- token 또는 data source ID 원문 출력
- wrapper CLI / GitHub Actions / GUI / Notion button 구현

## Git 주의사항

금지:

```cmd
git add .
git add -A
```

절대 stage 금지:

```text
.env
config/notion_settings.json
secret이 포함된 파일
outputs/backtest_log.db
backtest_log.db
analysis_results/*.png
idea, PRD, TRD/*
```

## 성공 기준

- duplicate audit CLI가 `.env` / 환경변수 기반 설정을 지원함
- `config/notion_settings.json`이 없어도 env 값이 있으면 read-only query까지 도달 가능함
- env 값이 없으면 안전하게 `settings_error`로 중단함
- secret 값이 출력되지 않음
- Notion write/export/sync 없음
- `write_executed=false` 유지
- 테스트 통과
- smoke 결과가 `settings_error`가 아니라 실제 query 결과 또는 `query_error`까지 진행됨
- outputs/paper 원장 변경 없음

## 커밋 정책

이번 작업은 구현 + 문서 업데이트 후 커밋까지 진행한다.

커밋 전:

```cmd
git status --short
git diff --check -- scripts\dev\audit_notion_duplicates.py core\notion_duplicate_audit.py core\notion_settings.py tests\test_notion_duplicate_audit.py docs\TRD\mfu_paper17_notion_settings_preflight_and_smoke_rerun.md docs\TRD\mfu_paper17_daily_ops_duplicate_audit_dry_run.md
pytest tests\test_notion_duplicate_audit.py
```

stage는 수정된 파일만 개별로 한다.

예시:

```cmd
git add scripts\dev\audit_notion_duplicates.py
git add core\notion_duplicate_audit.py
git add tests\test_notion_duplicate_audit.py
git add docs\TRD\mfu_paper17_notion_settings_preflight_and_smoke_rerun.md
git add docs\TRD\mfu_paper17_daily_ops_duplicate_audit_dry_run.md
```

커밋 메시지:

```cmd
git commit -m "feat: support env based Notion settings for duplicate audit"
```

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 생성/수정한 파일
3. 기존 settings 로딩 방식 확인 결과
4. env-only fallback 구현 내용
5. 필요한 환경변수
6. secret 출력/stage/commit 여부
7. 테스트 결과
8. read-only smoke 실행 여부
9. smoke 명령
10. Notion API read 호출 여부
11. Notion write/export/sync 실행 여부
12. smoke 결과 요약
   - target
   - account_id
   - status_date
   - external_key
   - match_count
   - classification
   - recommended_action
   - write_executed
13. smoke 결과 해석
14. 커밋 생성 여부
15. 커밋 SHA / 메시지
16. outputs/paper 원장 변경 여부
17. 남은 리스크
18. PAPER17-7 추천 작업

END MFU-PAPER17-6-ENV-BASED-NOTION-SETTINGS-FOR-DUPLICATE-AUDIT
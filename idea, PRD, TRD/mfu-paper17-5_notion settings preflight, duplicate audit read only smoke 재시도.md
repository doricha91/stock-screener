BEGIN MFU-PAPER17-5-NOTION-SETTINGS-PREFLIGHT-AND-READ-ONLY-SMOKE-RERUN

# PAPER17-5 Notion Settings Preflight + Duplicate Audit Read-only Smoke 재시도

## 목적

PAPER17-4B에서 `config/notion_settings.json` 부재로 `settings_error`가 발생해 Daily Ops Status duplicate audit이 Notion API read까지 도달하지 못했다.

이번 PAPER17-5의 목적은 다음이다.

1. Daily Ops Status duplicate audit에 필요한 Notion settings/data source 설정 경로를 확인한다.
2. secret 파일이나 token을 커밋하지 않도록 안전 정책을 문서화한다.
3. 설정이 준비되어 있으면 `paper_sandbox / 2026-05-20` 기준 read-only smoke를 재실행한다.
4. 설정이 준비되어 있지 않으면 actual/read를 우회하지 않고 settings_error 상태를 유지하며 필요한 설정 방법만 문서화한다.
5. smoke 결과를 문서화한다.

이번 작업은 read-only preflight/smoke 작업이다.  
Notion actual write/export/sync는 절대 실행하지 않는다.

## 배경

PAPER17-4A에서 daily_ops_status duplicate audit dry-run이 구현됐다.

커밋:

```text
7f3d5c1d8cc4fb730c8569ad00ea7bf2edebd28c
feat: add PAPER17 daily ops duplicate audit dry run
```

PAPER17-4B에서 read-only smoke를 실행했으나 결과는 settings_error였다.

실행 명령:

```cmd
python scripts\dev\audit_notion_duplicates.py --target daily_ops_status --account-id paper_sandbox --date 2026-05-20 --json
```

결과 요약:

```text
classification = settings_error
recommended_action = stop_actual_settings_error
write_executed = false
Notion API read 호출 없음
Notion write/export/sync 없음
```

원인:

```text
config/notion_settings.json 부재로 Daily Ops Status data source 설정을 읽지 못함
```

## 작업 범위

### 1. Notion settings 로딩 경로 확인

다음 파일을 확인한다.

```cmd
type core\notion_settings.py
type config\notion_settings.example.json
type config\notion_property_mapping.example.json
type scripts\dev\audit_notion_duplicates.py
type core\notion_duplicate_audit.py
type docs\TRD\mfu_paper17_duplicate_audit_read_only_smoke.md
```

확인할 것:

- Daily Ops Status data source ID를 어디서 읽는가
- `config/notion_settings.json`이 필요한가
- 환경변수 override가 가능한가
- `NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID` 같은 환경변수가 사용되는가
- Notion token은 어디서 읽는가
- example config와 실제 config의 차이는 무엇인가
- 실제 secret 파일이 git tracked 대상인지 여부

### 2. secret 안전 정책 확인

반드시 지킨다.

금지:

```text
- Notion token 출력
- data source ID 전체값을 결과 보고에 그대로 노출
- config/notion_settings.json 커밋
- .env 커밋
- secret이 포함된 파일 stage
- git add .
- git add -A
```

허용:

```text
- config/notion_settings.example.json 확인
- 환경변수 이름 문서화
- 실제 값은 마스킹해서 보고
- settings 존재 여부만 보고
```

결과 보고에서 secret 값은 아래처럼 마스킹한다.

```text
NOTION_TOKEN = set / not set
NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID = set / not set
data_source_id = ****abcd
```

### 3. settings preflight 문서 생성

아래 문서를 생성한다.

```cmd
docs\TRD\mfu_paper17_notion_settings_preflight_and_smoke_rerun.md
```

포함할 섹션:

1. Purpose
2. Background
3. Required Settings
4. Supported Configuration Paths
5. Secret Safety Policy
6. Preflight Checklist
7. Read-only Smoke Command
8. Smoke Result
9. Interpretation
10. Remaining Limitations
11. PAPER17-6 Recommendation

반드시 명시:

- `config/notion_settings.json` 또는 환경변수 기반 설정이 필요함
- secret 파일은 커밋 금지
- Daily Ops Status duplicate audit은 read-only query만 수행해야 함
- duplicate audit은 actual export 승인이 아님
- write_executed=false가 반드시 유지되어야 함

### 4. read-only smoke 재실행

먼저 help 확인:

```cmd
python scripts\dev\audit_notion_duplicates.py --help
```

설정이 준비되어 있으면 아래 명령을 1회 실행한다.

```cmd
python scripts\dev\audit_notion_duplicates.py --target daily_ops_status --account-id paper_sandbox --date 2026-05-20 --json
```

주의:

- Notion API read 호출은 허용
- Notion API write 호출은 금지
- Notion actual export/sync 금지
- 실패하면 실패 결과를 그대로 기록
- `settings_error`가 다시 발생하면 설정 누락으로 기록하고 중단
- `query_error`가 발생하면 query 실패로 기록하고 중단
- 어떤 경우에도 actual export로 우회하지 않음

### 5. smoke 결과 문서화

문서에 결과를 기록한다.

기록할 항목:

```text
target
account_id
status_date
external_key
match_count
page_ids count 또는 masked page_ids
classification
recommended_action
write_executed
Notion API read 호출 여부
Notion write/export/sync 실행 여부
```

해석 기준:

```text
create_candidate
→ 같은 External Key row가 없음. actual 시 create 후보지만, actual 승인 아님.

update_candidate
→ 같은 External Key row 1건. actual 시 update 후보지만, actual 승인 아님.

duplicate_blocker
→ 같은 External Key row 2건 이상. actual 중단.

manual_review_required
→ key/date/account/page_id 정합성 수동 확인 필요. actual 중단.

settings_error
→ 설정 문제. actual 중단.

query_error
→ Notion query 문제. actual 중단.
```

## 검증 명령

Windows CMD 기준으로 실행한다.

```cmd
git status --short

python scripts\dev\audit_notion_duplicates.py --help

python scripts\dev\audit_notion_duplicates.py --target daily_ops_status --account-id paper_sandbox --date 2026-05-20 --json

type docs\TRD\mfu_paper17_notion_settings_preflight_and_smoke_rerun.md

findstr /N /I "settings_error query_error read-only daily_ops_status paper_sandbox 2026-05-20 External Key match_count classification recommended_action write_executed secret token data source" docs\TRD\mfu_paper17_notion_settings_preflight_and_smoke_rerun.md

git diff --check -- docs\TRD\mfu_paper17_notion_settings_preflight_and_smoke_rerun.md
```

단, settings가 준비되어 있지 않다면 smoke 명령은 `settings_error`로 종료될 수 있다. 이 경우도 정상적으로 문서화한다.

## Non-scope

이번 작업에서는 절대 하지 않는다.

- Python 코드 수정
- duplicate audit 기능 확장
- Notion actual write/export/sync
- Notion API write 호출
- create_page / update_page / upsert_page_by_external_key 호출
- Daily Ops Status actual rerun
- paper_default actual export
- multi-account bulk export
- Manual Execution/Review status sync actual
- detail exporter actual
- outputs/paper 원장 수정
- config/notion_settings.json 커밋
- .env 커밋
- secret 값 출력
- schema/view drift 자동 점검 구현
- wrapper CLI / GitHub Actions / GUI / Notion button 구현

## Git 주의사항

절대 사용 금지:

```cmd
git add .
git add -A
```

커밋 후보는 원칙적으로 아래 문서 하나다.

```cmd
docs\TRD\mfu_paper17_notion_settings_preflight_and_smoke_rerun.md
```

아래 파일은 절대 stage하지 않는다.

```text
config/notion_settings.json
.env
secret이 포함된 파일
outputs/backtest_log.db
backtest_log.db
analysis_results/*.png
idea, PRD, TRD/*
unrelated local artifacts
```

## 성공 기준

- Notion settings/data source 설정 경로가 문서화됨
- secret 안전 정책이 명확히 문서화됨
- read-only smoke가 재실행됨 또는 settings_error로 안전하게 중단됨
- 결과가 문서화됨
- write_executed=false가 유지됨
- Notion actual write/export/sync 실행 없음
- outputs/paper 원장 변경 없음
- secret 파일이 stage/commit되지 않음
- git diff --check 통과

## 커밋 정책

이번 작업은 문서 생성 후 커밋까지 진행한다.

커밋 전 확인:

```cmd
git status --short
git diff --check -- docs\TRD\mfu_paper17_notion_settings_preflight_and_smoke_rerun.md
```

stage / commit:

```cmd
git add docs\TRD\mfu_paper17_notion_settings_preflight_and_smoke_rerun.md

git diff --cached --name-only
git diff --cached

git commit -m "docs: record PAPER17 Notion settings preflight smoke"

git log -1 --stat
git status --short
```

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 생성/수정한 파일
3. settings 로딩 경로 확인 결과
4. 필요한 설정 항목
5. secret 파일 stage/commit 여부
6. read-only smoke 실행 여부
7. smoke 명령
8. Notion API read 호출 여부
9. Notion write/export/sync 실행 여부
10. smoke 결과 요약
   - target
   - account_id
   - status_date
   - external_key
   - match_count
   - classification
   - recommended_action
   - write_executed
11. smoke 결과 해석
12. 커밋 생성 여부
13. 커밋 SHA / 메시지
14. outputs/paper 원장 변경 여부
15. 남은 리스크
16. PAPER17-6 추천 작업

END MFU-PAPER17-5-NOTION-SETTINGS-PREFLIGHT-AND-READ-ONLY-SMOKE-RERUN
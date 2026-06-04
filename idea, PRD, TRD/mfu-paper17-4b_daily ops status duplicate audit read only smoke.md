BEGIN MFU-PAPER17-4B-COMMIT-AND-READ-ONLY-SMOKE

# PAPER17-4A 커밋 + Daily Ops Status Duplicate Audit Read-only Smoke

## 목적

PAPER17-4A에서 구현한 daily_ops_status duplicate audit dry-run 결과물을 먼저 커밋한다.

그 다음 PAPER17-4B로 `paper_sandbox / 2026-05-20` 기준 read-only Notion API smoke를 1회 실행하고, 실제 duplicate audit 결과를 문서화한다.

이번 작업은 read-only 검증이다.

절대 하지 말 것:

- Notion actual write/export/sync 실행
- Notion API write 호출
- create_page / update_page / upsert_page_by_external_key 호출
- Daily Ops Status actual rerun
- paper_default actual export
- multi-account bulk export
- outputs/paper 원장 수정

## 배경

PAPER17-4A에서 daily_ops_status 전용 duplicate audit dry-run이 구현됐다.

생성 파일:

- core/notion_duplicate_audit.py
- scripts/dev/audit_notion_duplicates.py
- tests/test_notion_duplicate_audit.py
- docs/TRD/mfu_paper17_daily_ops_duplicate_audit_dry_run.md

검토 결과:

- daily_ops_status 전용 read-only audit로 동작
- production code에서 Notion client 호출은 query_by_external_key만 사용
- create_page / update_page / upsert_page_by_external_key 호출 없음
- 모든 결과에 write_executed=false 포함
- tests/test_notion_duplicate_audit.py: 10 passed
- git diff --check 통과
- blocker 없음

PAPER17-4B는 이 구현을 커밋하고, 실제 Notion DB에 대해 read-only query가 정상 동작하는지 1회 확인한다.

## 1단계: PAPER17-4A 구현물 커밋

### 대상 파일

아래 4개 파일만 커밋한다.

```cmd
core\notion_duplicate_audit.py
scripts\dev\audit_notion_duplicates.py
tests\test_notion_duplicate_audit.py
docs\TRD\mfu_paper17_daily_ops_duplicate_audit_dry_run.md
```

### 확인 명령

```cmd
git status --short

git diff --check -- core\notion_duplicate_audit.py scripts\dev\audit_notion_duplicates.py tests\test_notion_duplicate_audit.py docs\TRD\mfu_paper17_daily_ops_duplicate_audit_dry_run.md

pytest tests\test_notion_duplicate_audit.py
```

### stage / commit

절대 사용 금지:

```cmd
git add .
git add -A
```

실행:

```cmd
git add core\notion_duplicate_audit.py
git add scripts\dev\audit_notion_duplicates.py
git add tests\test_notion_duplicate_audit.py
git add docs\TRD\mfu_paper17_daily_ops_duplicate_audit_dry_run.md

git diff --cached --name-only
git diff --cached

git commit -m "feat: add PAPER17 daily ops duplicate audit dry run"

git log -1 --stat
git status --short
```

## 2단계: read-only smoke 실행 전 안전 확인

read-only smoke는 실제 Notion API read를 1회 수행할 수 있다.  
write는 절대 수행하지 않는다.

실행 전 아래를 확인한다.

```cmd
python scripts\dev\audit_notion_duplicates.py --help
```

확인할 것:

- `--target daily_ops_status`만 지원
- `--account-id` 필요
- `--date` 또는 `--external-key` 필요
- write 관련 옵션 없음
- `--confirm-actual` 없음

## 3단계: read-only Notion API smoke 1회 실행

대상:

```text
target = daily_ops_status
account_id = paper_sandbox
date = 2026-05-20
external_key = daily_ops_status:paper_sandbox:2026-05-20
```

실행 명령:

```cmd
python scripts\dev\audit_notion_duplicates.py --target daily_ops_status --account-id paper_sandbox --date 2026-05-20 --json
```

주의:

- 이 명령은 Notion DB query/read만 수행해야 한다.
- Notion write/export/sync를 실행하면 안 된다.
- 결과에 반드시 `"write_executed": false`가 있어야 한다.
- 결과가 `settings_error` 또는 `query_error`여도 임의로 다른 actual 명령을 실행하지 않는다.
- 실패하면 실패 결과를 그대로 문서화한다.
- Notion token, DB ID 등 secret 값은 결과 보고에 노출하지 않는다.

## 4단계: smoke 결과 문서화

아래 문서를 생성한다.

```cmd
docs\TRD\mfu_paper17_duplicate_audit_read_only_smoke.md
```

문서에 포함할 섹션:

1. Purpose
2. Smoke Scope
3. Command
4. Read-only Safety Policy
5. Smoke Result
6. Classification Result
7. Interpretation
8. Limitations
9. Next Recommendation

### 반드시 포함할 내용

#### Smoke Scope

- target: daily_ops_status
- account_id: paper_sandbox
- status_date: 2026-05-20
- external_key: daily_ops_status:paper_sandbox:2026-05-20
- Notion API read 호출 여부
- Notion write/export/sync 실행 여부: 없음

#### Smoke Result

CLI 출력에서 secret을 제외하고 다음을 요약한다.

- target
- account_id
- status_date
- external_key
- match_count
- page_ids 수 또는 page_id list
  - page_id가 민감하다고 판단되면 전체 값 대신 일부 마스킹 가능
- classification
- recommended_action
- write_executed

#### Interpretation

classification별 해석:

- create_candidate: 현재 동일 External Key row가 없어 actual 시 create 후보
- update_candidate: 동일 External Key row 1건이 있어 actual 시 update 후보
- duplicate_blocker: 동일 External Key row가 2건 이상이므로 actual 중단
- manual_review_required: key/date/account/page_id 정합성 확인 필요
- settings_error/query_error: 설정 또는 query 문제로 smoke 실패, actual 금지

#### Limitations

- 이번 smoke는 daily_ops_status / paper_sandbox / 2026-05-20 단일 케이스만 확인
- schema validation을 대체하지 않음
- view/filter drift 검증을 대체하지 않음
- actual export 승인 아님
- duplicate cleanup 기능 아님
- multi-account bulk export 허용 아님

## 5단계: smoke 문서 검증 및 커밋

### 확인 명령

```cmd
type docs\TRD\mfu_paper17_duplicate_audit_read_only_smoke.md

findstr /N /I "read-only daily_ops_status paper_sandbox 2026-05-20 External Key match_count classification recommended_action write_executed Notion write export sync" docs\TRD\mfu_paper17_duplicate_audit_read_only_smoke.md

git diff --check -- docs\TRD\mfu_paper17_duplicate_audit_read_only_smoke.md
```

### stage / commit

절대 사용 금지:

```cmd
git add .
git add -A
```

실행:

```cmd
git add docs\TRD\mfu_paper17_duplicate_audit_read_only_smoke.md

git diff --cached --name-only
git diff --cached

git commit -m "docs: record PAPER17 duplicate audit read-only smoke"

git log -2 --stat
git status --short
```

## Non-scope

이번 작업에서는 절대 하지 않는다.

- Python 코드 추가 수정
- duplicate audit 기능 확장
- duplicate cleanup 구현
- Notion actual write/export/sync
- Notion API write 호출
- create_page / update_page / upsert_page_by_external_key 호출
- Daily Ops Status actual rerun
- paper_default actual export
- multi-account bulk export
- detail exporter actual
- Manual Execution/Review status sync actual
- outputs/paper 원장 수정
- schema/view drift 자동 점검 구현
- wrapper CLI / GitHub Actions / GUI / Notion button 구현
- Alert / Replay / Universe / Strategy 작업

## 성공 기준

- PAPER17-4A 구현물이 별도 커밋됨
- unit test가 통과함
- read-only smoke가 1회 실행됨
- smoke 실행 중 Notion write/export/sync 없음
- smoke 결과에 write_executed=false가 포함됨
- smoke 결과가 문서화됨
- smoke 문서가 별도 커밋됨
- settings_error/query_error가 발생해도 actual로 우회하지 않음
- outputs/paper 원장 변경 없음
- unrelated 파일이 stage/commit되지 않음

## Git 주의사항

절대 사용 금지:

```cmd
git add .
git add -A
```

기존 워크트리에 unrelated 변경이 남아 있을 수 있으므로, 커밋 전후 반드시 확인한다.

```cmd
git status --short
```

이번 작업에 포함하면 안 되는 예:

```text
outputs/backtest_log.db
backtest_log.db
analysis_results/*.png
idea, PRD, TRD/*
unrelated local artifacts
```

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. PAPER17-4A 커밋 생성 여부
3. PAPER17-4A 커밋 SHA / 메시지
4. read-only smoke 실행 여부
5. smoke 명령
6. Notion API read 호출 여부
7. Notion write/export/sync 실행 여부
8. smoke 결과 요약
   - target
   - account_id
   - status_date
   - external_key
   - match_count
   - classification
   - recommended_action
   - write_executed
9. smoke 결과 해석
10. smoke 문서 생성 여부
11. smoke 문서 커밋 SHA / 메시지
12. 테스트 결과
13. git diff --check 결과
14. outputs/paper 원장 변경 여부
15. 제외한 unrelated 파일
16. 남은 리스크
17. PAPER17-5 추천 작업

END MFU-PAPER17-4B-COMMIT-AND-READ-ONLY-SMOKE
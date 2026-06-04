BEGIN MFU-PAPER17-4A-DAILY-OPS-DUPLICATE-AUDIT-DRY-RUN

# PAPER17-3 커밋 + Daily Ops Status Duplicate Audit Dry-run 설계/구현

## 목적

먼저 PAPER17-3 Export / Sync Command Gate SOP 문서를 커밋한다.

그 다음 PAPER17-4A로 `daily_ops_status` 대상의 최소 duplicate audit dry-run interface를 설계하고 구현한다.

이 작업의 목표는 Notion actual export 전에 특정 `account_id` / `status_date` / `External Key` 기준으로 Notion row 매칭 상태를 확인해 아래처럼 분류하는 것이다.

- 0건: create_candidate
- 1건: update_candidate
- 2건 이상: duplicate_blocker
- page_id mismatch 또는 판단 불가: manual_review_required

이번 작업은 read-only audit이다. Notion actual write/export/sync는 절대 실행하지 않는다.

## 배경

PAPER17-3 Command Gate SOP에서 다음이 정리됐다.

- 현재 일반 허용 actual은 Daily Ops Status `paper_sandbox` 단일 guarded actual뿐이다.
- actual 전 dry-run, schema PASS, External Key 확인, duplicate 의심 없음, 사용자 명시 승인이 필요하다.
- `--all` actual, multi-account bulk actual, account_id 생략 actual, paper_default actual은 금지다.
- duplicate 의심 시 actual 중단이다.
- External Key는 수동 수정 금지다.

PAPER17-4A는 이 중 “duplicate 의심 없음”을 확인하기 위한 최소 read-only audit interface를 만든다.

## 1단계: PAPER17-3 커밋

### 대상 파일

```cmd
docs\TRD\mfu_paper17_export_sync_command_gate_sop.md
```

### 확인 명령

```cmd
git status --short
type docs\TRD\mfu_paper17_export_sync_command_gate_sop.md
git diff --check -- docs\TRD\mfu_paper17_export_sync_command_gate_sop.md
```

### stage / commit

금지:

```cmd
git add .
git add -A
```

실행:

```cmd
git add docs\TRD\mfu_paper17_export_sync_command_gate_sop.md
git diff --cached --name-only
git diff --cached
git commit -m "docs: define PAPER17 export sync command gate"
git log -1 --stat
git status --short
```

## 2단계: Duplicate Audit 설계/구현

## 구현 범위

### 대상

이번 구현 대상은 `daily_ops_status` 하나로 제한한다.

지원할 key 형식:

```text
daily_ops_status:{account_id}:{status_date}
```

예:

```text
daily_ops_status:paper_sandbox:2026-05-20
```

### 권장 생성/수정 파일

구현 후보:

```text
core/notion_duplicate_audit.py
scripts/dev/audit_notion_duplicates.py
tests/test_notion_duplicate_audit.py
docs/TRD/mfu_paper17_daily_ops_duplicate_audit_dry_run.md
```

파일명은 기존 repo convention에 맞춰 조정해도 된다. 단, 범위를 넓히지 않는다.

### CLI 요구사항

권장 CLI:

```cmd
python scripts\dev\audit_notion_duplicates.py --target daily_ops_status --account-id paper_sandbox --date 2026-05-20 --json
```

선택 옵션:

```cmd
--external-key daily_ops_status:paper_sandbox:2026-05-20
--expected-page-id <page_id>
--json
```

정책:

- `--target`은 이번 단계에서 `daily_ops_status`만 허용
- `--account-id` 필수
- `--date` 또는 `--external-key` 필수
- `--date`는 `YYYY-MM-DD` 형식 권장
- `--external-key`를 직접 받는 경우에도 `account_id` / `date`와 불일치하면 FAIL 또는 manual_review_required
- write 관련 옵션 금지
- `--confirm-actual` 같은 actual 옵션 추가 금지

### 출력 형식

JSON 출력에는 최소 아래 필드를 포함한다.

```json
{
  "target": "daily_ops_status",
  "account_id": "paper_sandbox",
  "status_date": "2026-05-20",
  "external_key": "daily_ops_status:paper_sandbox:2026-05-20",
  "match_count": 1,
  "page_ids": ["..."],
  "classification": "update_candidate",
  "recommended_action": "safe_to_update_after_required_preflight",
  "write_executed": false
}
```

classification 후보:

```text
create_candidate
update_candidate
duplicate_blocker
manual_review_required
settings_error
query_error
```

recommended_action 후보:

```text
safe_to_create_after_required_preflight
safe_to_update_after_required_preflight
stop_actual_duplicate_detected
stop_actual_manual_review_required
stop_actual_settings_error
stop_actual_query_error
```

### 판정 규칙

필수 규칙:

```text
match_count = 0
→ classification = create_candidate
→ recommended_action = safe_to_create_after_required_preflight

match_count = 1
→ classification = update_candidate
→ recommended_action = safe_to_update_after_required_preflight

match_count >= 2
→ classification = duplicate_blocker
→ recommended_action = stop_actual_duplicate_detected

expected_page_id가 제공됐고 실제 1건 page_id와 다름
→ classification = manual_review_required

external_key / account_id / date 불일치
→ classification = manual_review_required
```

모든 결과에 `write_executed=false`를 포함한다.

### Notion 접근 정책

이 audit은 read-only여야 한다.

허용:

- Notion DB query/read
- settings/schema read
- mocked Notion client 테스트

금지:

- create_page
- update_page
- upsert_page_by_external_key
- status sync actual
- export actual
- Notion row 수정
- Notion property 수정

기존 `core/notion_client.py`에 `query_by_external_key`가 있으면 이를 우선 재사용한다.  
기존 client 구조가 다르면 repo convention에 맞추되, write API를 호출하지 않는다.

## 3단계: 문서 작성

아래 문서를 생성한다.

```text
docs/TRD/mfu_paper17_daily_ops_duplicate_audit_dry_run.md
```

포함할 섹션:

1. Purpose
2. Scope
3. CLI
4. Input Contract
5. Output Contract
6. Classification Rules
7. Read-only Safety Policy
8. Example Outputs
9. Test Coverage
10. Remaining Limitations
11. PAPER17-4B Recommendation

반드시 명시:

- 이번 audit은 `daily_ops_status` 한정
- Notion write 없음
- actual export/sync 실행 없음
- duplicate audit이 schema validation을 대체하지 않음
- schema validation이 duplicate audit을 대체하지 않음
- actual 실행 여부는 이 audit만으로 결정하지 않으며, Command Gate SOP의 preflight 전체를 통과해야 함

## 테스트 요구사항

가능하면 unit test를 작성한다.

테스트 대상:

- external key 생성
- 0건 → create_candidate
- 1건 → update_candidate
- 2건 이상 → duplicate_blocker
- expected_page_id mismatch → manual_review_required
- account/date/external_key mismatch → manual_review_required
- write_executed는 항상 false
- target이 daily_ops_status가 아니면 fail 또는 unsupported

테스트는 실제 Notion API를 호출하지 말고 mock/fake client를 사용한다.

## 검증 명령

Windows CMD 기준으로 실행한다.

```cmd
git status --short
python scripts\dev\audit_notion_duplicates.py --help
pytest tests\test_notion_duplicate_audit.py
type docs\TRD\mfu_paper17_daily_ops_duplicate_audit_dry_run.md
findstr /N /I "daily_ops_status duplicate audit External Key create_candidate update_candidate duplicate_blocker manual_review_required write_executed false read-only" docs\TRD\mfu_paper17_daily_ops_duplicate_audit_dry_run.md
git diff --check -- core\notion_duplicate_audit.py scripts\dev\audit_notion_duplicates.py tests\test_notion_duplicate_audit.py docs\TRD\mfu_paper17_daily_ops_duplicate_audit_dry_run.md
```

실제 Notion read API를 호출하는 smoke는 기본 검증에 포함하지 않는다.  
필요하면 별도 수동 명령으로만 제시하고 실행하지 않는다.

예시 수동 read-only smoke 후보:

```cmd
python scripts\dev\audit_notion_duplicates.py --target daily_ops_status --account-id paper_sandbox --date 2026-05-20 --json
```

단, 이 명령이 Notion API read를 수행한다면 결과 보고에 “read-only API call 여부”를 명확히 보고한다.

## Non-scope

이번 작업에서는 절대 하지 않는다.

- Notion actual write/export/sync 실행
- Notion API write 호출
- create_page / update_page / upsert 실행
- Daily Ops Status actual rerun
- paper_default actual export
- multi-account bulk export
- detail exporter actual guard 구현
- Manual Execution/Review status sync confirm guard 구현
- duplicate cleanup 구현
- schema/view drift 자동 점검 구현
- wrapper CLI / GitHub Actions / GUI / Notion button 구현
- outputs/paper 원장 수정
- trading logic 수정
- Universe / Strategy 확장

## 성공 기준

- PAPER17-3 Command Gate SOP가 커밋됨
- `daily_ops_status` duplicate audit dry-run 설계 문서가 생성됨
- read-only duplicate audit core가 구현됨
- CLI가 추가됨
- unit test가 추가되고 통과함
- 0/1/2건 이상 매칭 판정이 구현됨
- expected_page_id mismatch 판정이 구현됨
- 모든 audit 결과에 `write_executed=false`가 포함됨
- Notion write API 호출 없음
- Notion actual export/sync 실행 없음
- outputs/paper 원장 변경 없음
- `git diff --check` 대상 파일 기준 통과

## Git 주의사항

금지:

```cmd
git add .
git add -A
```

이번 PAPER17-4A 구현 결과는 아직 커밋하지 않는다.  
생성/수정 파일과 검증 결과만 보고한다.

커밋 후보는 결과 보고에 명시한다.

예상 후보:

```cmd
core\notion_duplicate_audit.py
scripts\dev\audit_notion_duplicates.py
tests\test_notion_duplicate_audit.py
docs\TRD\mfu_paper17_daily_ops_duplicate_audit_dry_run.md
```

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. PAPER17-3 커밋 생성 여부
3. PAPER17-3 커밋 SHA / 메시지
4. 생성/수정한 파일
5. duplicate audit CLI 요약
6. classification 규칙 요약
7. read-only safety 보장 방식
8. 테스트 추가/통과 여부
9. Notion API read 호출 여부
10. Notion write/export/sync 실행 여부
11. outputs/paper 원장 변경 여부
12. git diff --check 결과
13. 커밋 후보 파일
14. PAPER17-4B 추천 작업

END MFU-PAPER17-4A-DAILY-OPS-DUPLICATE-AUDIT-DRY-RUN
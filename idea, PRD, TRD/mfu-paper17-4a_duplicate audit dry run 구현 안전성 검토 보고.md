BEGIN MFU-PAPER17-4A-IMPLEMENTATION-REVIEW-REPORT

# PAPER17-4A Duplicate Audit Dry-run 구현 안전성 검토 보고

## 목적

PAPER17-4A에서 구현된 daily_ops_status duplicate audit dry-run 기능이 의도대로 read-only / dry-run audit으로만 동작하는지 검토하고 보고한다.

이번 작업은 검토 전용이다.  
코드 수정, 문서 수정, 커밋, Notion API 호출, Notion write/export/sync 실행은 하지 않는다.

검토 대상은 다음이다.

1. CLI가 `daily_ops_status` 외 target을 확실히 막는지
2. `--account-id`가 필수인지
3. `--date` 또는 `--external-key` 정합성 검사가 안전한지
4. `query_by_external_key` 외 write성 메서드를 호출하지 않는지
5. `settings_error` / `query_error` 처리 방식이 안전한지
6. JSON 출력에 `write_executed=false`가 항상 들어가는지
7. 테스트가 위 안전 조건을 충분히 검증하는지

## 배경

PAPER17-4A는 daily_ops_status 전용 duplicate audit dry-run을 구현했다.

생성 파일:

- core/notion_duplicate_audit.py
- scripts/dev/audit_notion_duplicates.py
- tests/test_notion_duplicate_audit.py
- docs/TRD/mfu_paper17_daily_ops_duplicate_audit_dry_run.md

목표 classification:

- match_count = 0 → create_candidate
- match_count = 1 → update_candidate
- match_count >= 2 → duplicate_blocker
- expected_page_id mismatch → manual_review_required
- external_key / account_id / date mismatch → manual_review_required
- settings/query error → settings_error 또는 query_error

모든 결과에는 `write_executed=false`가 포함되어야 한다.

## 검토 범위

### 1. 파일 본문 확인

아래 파일을 읽고 검토한다.

```cmd
type core\notion_duplicate_audit.py
type scripts\dev\audit_notion_duplicates.py
type tests\test_notion_duplicate_audit.py
type docs\TRD\mfu_paper17_daily_ops_duplicate_audit_dry_run.md
```

### 2. daily_ops_status target 제한 확인

확인할 것:

- `--target daily_ops_status`만 허용되는가
- 다른 target 입력 시 fail / unsupported / error로 처리되는가
- 다른 Notion DB target으로 확장된 흔적이 없는가
- 문서에도 이번 범위가 daily_ops_status 한정이라고 명시되어 있는가

### 3. 필수 입력 검증 확인

확인할 것:

- `--account-id`가 필수인가
- `--date` 또는 `--external-key` 입력 정책이 명확한가
- 보고서에는 `--external-key`를 직접 넣어도 `--date`를 요구한다고 되어 있었는데, 실제 구현도 그런가
- `--date` 형식은 `YYYY-MM-DD`로 검증되는가
- external key 형식은 `daily_ops_status:{account_id}:{status_date}`인지 확인하는가
- account_id/date/external_key가 서로 불일치하면 `manual_review_required` 또는 안전한 실패로 처리되는가

### 4. read-only safety 확인

확인할 것:

- core audit이 `query_by_external_key`만 사용하는가
- `create_page` 호출이 없는가
- `update_page` 호출이 없는가
- `upsert_page_by_external_key` 호출이 없는가
- status sync actual / export actual 경로를 호출하지 않는가
- CLI에 `--confirm-actual` 같은 write 유도 옵션이 없는가
- 모든 결과에 `write_executed=false`가 포함되는가

검색 명령 예시:

```cmd
findstr /S /N /I "create_page update_page upsert_page_by_external_key confirm-actual write_executed query_by_external_key" core\notion_duplicate_audit.py scripts\dev\audit_notion_duplicates.py tests\test_notion_duplicate_audit.py
```

### 5. error handling 확인

확인할 것:

- settings/config 오류가 `settings_error`로 안전하게 반환되는가
- Notion query 오류가 `query_error`로 안전하게 반환되는가
- 오류 발생 시에도 write를 시도하지 않는가
- 오류 결과에도 `write_executed=false`가 포함되는가
- exception을 삼켜서 성공처럼 보이게 하지 않는가

### 6. 테스트 확인

아래 테스트를 실행한다.

```cmd
pytest tests\test_notion_duplicate_audit.py
```

테스트가 최소 아래를 포함하는지 확인한다.

- 0건 → create_candidate
- 1건 → update_candidate
- 2건 이상 → duplicate_blocker
- expected_page_id mismatch → manual_review_required
- external_key / account_id / date mismatch → manual_review_required
- unsupported target 처리
- write_executed는 항상 false
- fake client에서 write 메서드 호출 시 실패

### 7. diff check

아래 명령을 실행한다.

```cmd
git diff --check -- core\notion_duplicate_audit.py scripts\dev\audit_notion_duplicates.py tests\test_notion_duplicate_audit.py docs\TRD\mfu_paper17_daily_ops_duplicate_audit_dry_run.md
```

## Non-scope

이번 작업에서는 절대 하지 않는다.

- 코드 수정
- 문서 수정
- 커밋
- git add
- Notion API read 호출
- Notion API write 호출
- Notion actual export/sync 실행
- outputs/paper 원장 수정
- duplicate cleanup 구현
- schema/view drift 구현
- paper_sandbox actual rerun
- paper_default actual export
- multi-account bulk export

## 성공 기준

검토 보고에서 아래를 판단할 수 있어야 한다.

- daily_ops_status 외 target이 막혀 있는지
- `--account-id`가 필수인지
- date/external-key 정합성 검사가 안전한지
- write API 호출 경로가 없는지
- error handling이 안전한지
- `write_executed=false`가 모든 결과에 포함되는지
- 테스트가 통과하는지
- PAPER17-4A를 커밋해도 되는지
- 커밋 전 수정이 필요한 blocker가 있는지

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 검토한 파일
3. daily_ops_status target 제한 확인 결과
4. 필수 입력 검증 확인 결과
5. date / external-key 정합성 확인 결과
6. read-only safety 확인 결과
7. write API 호출 여부
8. error handling 확인 결과
9. write_executed=false 보장 여부
10. 테스트 실행 결과
11. git diff --check 결과
12. 발견한 blocker
13. 발견한 non-blocking 개선점
14. PAPER17-4A 커밋 가능 여부
15. 커밋 후보 파일

END MFU-PAPER17-4A-IMPLEMENTATION-REVIEW-REPORT
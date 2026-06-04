BEGIN MFU-PAPER17-7-DAILY-OPS-STATUS-ACTUAL-PREFLIGHT

# PAPER17-7 Daily Ops Status Actual Preflight 정식화

## 목적

Daily Ops Status actual export 전에 반드시 확인해야 하는 항목을 하나의 read-only preflight 절차/명령으로 정식화한다.

이번 작업의 목표는 다음이다.

1. settings/env 존재 확인
2. Daily Ops Status schema validation 확인
3. duplicate audit 확인
4. External Key / account_id / status_date 정합성 확인
5. Command Gate 조건 확인
6. actual 실행 가능/불가를 PASS / WARNING / FAIL로 요약
7. 단, actual export 자체는 절대 실행하지 않음

이번 작업은 actual 실행이 아니라 actual 전 안전 점검이다.

## 배경

PAPER17-6에서 duplicate audit CLI가 `.env` / 환경변수 기반 설정을 지원하도록 정합화됐다.

현재 필요한 환경변수:

- NOTION_TOKEN
- NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID

PAPER17-6 read-only smoke 결과:

- target: daily_ops_status
- account_id: paper_sandbox
- status_date: 2026-05-20
- external_key: daily_ops_status:paper_sandbox:2026-05-20
- match_count: 1
- classification: update_candidate
- recommended_action: safe_to_update_after_required_preflight
- write_executed: false

해석:

- 동일 External Key row가 1건 존재하므로 actual 승인 시 create가 아니라 update 후보
- 그러나 actual export 승인 자체는 아님

PAPER17-7은 이 결과를 바탕으로 Daily Ops Status actual 전 preflight를 공식화한다.

## 대상 파일

생성/수정 후보:

```text
core/notion_daily_ops_actual_preflight.py
scripts/dev/preflight_daily_ops_status_actual.py
tests/test_notion_daily_ops_actual_preflight.py
docs/TRD/mfu_paper17_daily_ops_status_actual_preflight.md
```

기존 파일은 필요한 경우만 최소 수정한다.

참고 파일:

```text
core/notion_duplicate_audit.py
scripts/dev/audit_notion_duplicates.py
scripts/dev/validate_notion_schema.py
core/notion_settings.py
docs/TRD/mfu_paper17_export_sync_command_gate_sop.md
docs/TRD/mfu_paper17_daily_ops_duplicate_audit_dry_run.md
docs/TRD/mfu_paper17_notion_settings_preflight_and_smoke_rerun.md
```

## 구현 요구사항

### 1. Preflight CLI 추가

권장 명령:

```cmd
python scripts\dev\preflight_daily_ops_status_actual.py --account-id paper_sandbox --date 2026-05-20 --json
```

지원 옵션:

```text
--account-id
--date
--external-key
--expected-page-id
--json
```

정책:

- target은 daily_ops_status로 고정
- --account-id 필수
- --date 필수
- external key 기본값: daily_ops_status:{account_id}:{date}
- --external-key가 제공되면 account/date와 정합성 확인
- 실제 actual export 명령은 실행하지 않음
- --confirm-actual 옵션 추가 금지
- write_executed=false 유지

### 2. Preflight 단계

아래 checks를 수행한다.

```text
settings_env_check
schema_validation_check
duplicate_audit_check
external_key_check
account_scope_check
command_gate_check
```

각 check는 다음 중 하나로 분류한다.

```text
PASS
WARNING
FAIL
SKIPPED
```

### 3. 판정 정책

최종 결과 필드:

```json
{
  "target": "daily_ops_status",
  "account_id": "paper_sandbox",
  "status_date": "2026-05-20",
  "external_key": "daily_ops_status:paper_sandbox:2026-05-20",
  "overall_status": "PASS",
  "checks": [],
  "duplicate_audit": {},
  "recommended_action": "actual_allowed_only_after_explicit_user_approval",
  "write_executed": false
}
```

최종 판정 규칙:

```text
하나라도 FAIL → overall_status = FAIL
WARNING만 있고 FAIL 없음 → overall_status = WARNING
모두 PASS 또는 허용된 SKIPPED → overall_status = PASS
```

필수 FAIL 조건:

```text
NOTION_TOKEN 없음
NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID 없음
schema validation FAIL
duplicate_audit classification = duplicate_blocker
duplicate_audit classification = settings_error
duplicate_audit classification = query_error
account_id != paper_sandbox
account_id 누락
external_key 불일치
date 형식 오류
```

WARNING 후보:

```text
schema validation command를 실행하지 못했지만 수동 확인 필요
expected_page_id 미제공
duplicate audit은 update_candidate지만 actual 승인 전 사용자 확인 필요
```

### 4. Command Gate 반영

현재 allowed guarded actual은 아래 하나뿐임을 결과에 명시한다.

```cmd
python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --confirm-actual --json
```

단, preflight가 PASS여도 actual 실행은 자동 승인하지 않는다.

반드시 문서와 출력에 다음 취지를 포함한다.

```text
Preflight PASS means prerequisites appear satisfied.
It does not execute actual export.
It does not replace explicit user approval.
```

### 5. Read-only Safety

허용:

```text
환경변수 존재 확인
schema read/validation
Notion query/read
duplicate audit read-only query
```

금지:

```text
create_page
update_page
upsert_page_by_external_key
actual export
status sync actual
outputs/paper 원장 수정
```

## 테스트 요구사항

테스트 파일:

```text
tests/test_notion_daily_ops_actual_preflight.py
```

필수 테스트:

```text
settings/env 누락 → FAIL
account_id != paper_sandbox → FAIL
external_key 불일치 → FAIL
duplicate_audit create_candidate → PASS 또는 WARNING
duplicate_audit update_candidate → PASS 또는 WARNING
duplicate_audit duplicate_blocker → FAIL
schema validation FAIL → FAIL
write_executed=false 항상 포함
preflight가 write API를 호출하지 않음
```

실제 Notion API는 테스트에서 호출하지 말고 fake/mock을 사용한다.

## 문서 작성

생성 문서:

```text
docs/TRD/mfu_paper17_daily_ops_status_actual_preflight.md
```

포함 섹션:

1. Purpose
2. Scope
3. CLI
4. Input Contract
5. Preflight Checks
6. Output Contract
7. PASS / WARNING / FAIL Policy
8. Read-only Safety Policy
9. Example Outputs
10. Test Coverage
11. Limitations
12. PAPER17-8 Recommendation

반드시 명시:

- actual export를 실행하지 않음
- preflight PASS는 actual 승인 아님
- explicit user approval은 여전히 별도 필요
- paper_sandbox 외 actual은 계속 금지
- paper_default actual은 계속 금지
- multi-account bulk actual은 계속 금지

## 검증 명령

Windows CMD 기준:

```cmd
git status --short

python scripts\dev\preflight_daily_ops_status_actual.py --help

pytest tests\test_notion_duplicate_audit.py
pytest tests\test_notion_daily_ops_actual_preflight.py

python scripts\dev\preflight_daily_ops_status_actual.py --account-id paper_sandbox --date 2026-05-20 --json

type docs\TRD\mfu_paper17_daily_ops_status_actual_preflight.md

findstr /N /I "preflight PASS WARNING FAIL daily_ops_status paper_sandbox External Key duplicate schema command gate explicit user approval write_executed false" docs\TRD\mfu_paper17_daily_ops_status_actual_preflight.md

git diff --check -- core\notion_daily_ops_actual_preflight.py scripts\dev\preflight_daily_ops_status_actual.py tests\test_notion_daily_ops_actual_preflight.py docs\TRD\mfu_paper17_daily_ops_status_actual_preflight.md
```

실제 preflight 명령은 Notion read/query를 수행할 수 있다.  
단, Notion write/export/sync는 절대 실행하지 않는다.

## Non-scope

이번 작업에서는 절대 하지 않는다.

```text
Notion actual write/export/sync
Daily Ops Status actual export 실행
paper_default actual export
multi-account bulk export
detail exporter actual
Manual Execution/Review status sync actual
create_page / update_page / upsert_page_by_external_key 호출
outputs/paper 원장 수정
duplicate cleanup
schema/view drift 자동 점검 구현
wrapper CLI / GitHub Actions / GUI / Notion button 구현
Alert / Replay / Universe / Strategy 작업
```

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
secret 포함 파일
outputs/backtest_log.db
backtest_log.db
analysis_results/*.png
idea, PRD, TRD/*
```

이번 작업은 구현/문서 작성 후 아직 커밋하지 말고 결과만 보고한다.

커밋 후보 예시:

```cmd
core\notion_daily_ops_actual_preflight.py
scripts\dev\preflight_daily_ops_status_actual.py
tests\test_notion_daily_ops_actual_preflight.py
docs\TRD\mfu_pscripts\dev\preflight_daily_ops_status_actual.py
tests\test_notion_daily_ops_actual_preflight.py
docs\TRD\mfu_paper17_daily_ops_status_actual_preflight.md
```

## 성공 기준

- Daily Ops Status actual preflight CLI가 추가됨
- settings/env, schema, duplicate audit, External Key, account scope, command gate가 하나의 결과로 요약됨
- PASS / WARNING / FAIL 정책이 구현됨
- paper_sandbox 외 actual readiness는 FAIL 처리됨
- duplicate_blocker는 FAIL 처리됨
- preflight PASS가 actual 승인 아님이 명확함
- write_executed=false 유지
- Notion write/export/sync 실행 없음
- outputs/paper 원장 변경 없음
- 테스트 통과
- git diff --check 통과

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 생성/수정한 파일
3. preflight CLI 요약
4. preflight checks 목록
5. PASS / WARNING / FAIL 판정 정책
6. read-only safety 보장 방식
7. 테스트 결과
8. 실제 preflight 실행 여부
9. preflight 명령
10. Notion API read 호출 여부
11. Notion write/export/sync 실행 여부
12. preflight 결과 요약
   - overall_status
   - account_id
   - status_date
   - external_key
   - duplicate classification
   - schema validation result
   - recommended_action
   - write_executed
13. outputs/paper 원장 변경 여부
14. git diff --check 결과
15. 커밋 후보 파일
16. 남은 리스크
17. PAPER17-8 추천 작업

END MFU-PAPER17-7-DAILY-OPS-STATUS-ACTUAL-PREFLIGHT
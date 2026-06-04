# Deferred Actual Approval Flow Note

## 1. Purpose

이 문서는 PAPER17에서 논의된 Daily Ops Status actual export 승인 흐름을 정리한다.

현재 우선순위는 Alert / Monitoring Report 구축이다.  
Daily Ops Status actual export 실행 흐름은 Alert 기능 구현 이후, 실제 actual 실행 직전에 이 문서를 기준으로 별도 MFU에서 구현한다.

## 2. Background

PAPER17에서 Daily Ops Status actual export 전 안전 체계가 구축되었다.

완료된 주요 요소:

- Export / Sync Command Gate
- Daily Ops Status duplicate audit dry-run
- `.env` 기반 Notion settings 연동
- read-only Notion duplicate smoke
- Daily Ops Status actual preflight
- PASS / WARNING / FAIL 기반 preflight 결과

PAPER17-7 preflight는 settings/env, schema validation, duplicate audit, External Key, account scope, Command Gate를 하나의 read-only 결과로 요약한다. actual export는 실행하지 않으며, `write_executed=false`를 유지한다. :contentReference[oaicite:0]{index=0}

## 3. Current Issue

현재 preflight는 `expected_page_id`가 없으면 WARNING을 반환한다.

이유는 다음과 같다.

- duplicate audit 결과 `match_count=1`이면 동일 External Key row가 1건 존재한다.
- 이 경우 actual export는 create가 아니라 update 후보가 된다.
- 하지만 `expected_page_id`가 없으면, 운영자가 “이 row가 내가 의도한 정확한 Notion row다”라고 명시 확인한 상태는 아니다.
- 따라서 PAPER17-7에서는 보수적으로 WARNING을 반환한다.

현재 구조에서 수동으로 처리하면 다음과 같은 번거로운 절차가 된다.

```text
1. preflight 실행
2. duplicate audit 결과의 page_id 확인
3. page_id를 복사
4. --expected-page-id로 다시 preflight 실행
5. actual 승인 판단
```

이 방식은 안전하지만, 매일 반복하는 운영 UX로는 부적절하다.

## 4. Decision

`expected_page_id`를 운영자가 매번 직접 복사해서 입력하는 방식은 최종 운영 방식으로 채택하지 않는다.

대신 다음 방향을 채택한다.

```text
Preflight가 observed_page_id를 report에 기록한다.
Actual command는 preflight report를 입력으로 받아 검증한다.
운영자는 page_id를 직접 입력하지 않고, preflight report 기준으로 actual 실행을 명시 승인한다.
```

즉, `expected_page_id`는 장기적으로 수동 입력값이 아니라, preflight report에서 actual flow로 전달되는 검증값이 되어야 한다.

## 5. Target Flow

향후 actual export 직전 구현할 목표 흐름은 다음이다.

### Step 1. Preflight report 생성

```cmd
python scripts\dev\preflight_daily_ops_status_actual.py --account-id paper_sandbox --date 2026-05-20 --json --output <preflight_report.json>
```

Preflight report에는 최소 다음이 포함되어야 한다.

```json
{
  "target": "daily_ops_status",
  "account_id": "paper_sandbox",
  "status_date": "2026-05-20",
  "external_key": "daily_ops_status:paper_sandbox:2026-05-20",
  "overall_status": "PASS",
  "schema_validation_result": "PASS",
  "duplicate_audit": {
    "classification": "update_candidate",
    "match_count": 1,
    "page_ids": ["..."]
  },
  "observed_page_id": "...",
  "write_executed": false
}
```

### Step 2. 운영자 확인

운영자는 preflight report를 확인한다.

확인 항목:

- account_id가 의도한 계좌인가
- status_date가 의도한 날짜인가
- External Key가 예상과 일치하는가
- schema validation이 PASS인가
- duplicate audit이 duplicate_blocker가 아닌가
- match_count가 1이면 observed_page_id가 존재하는가
- overall_status가 PASS 또는 승인 가능한 WARNING인가
- actual export를 실제로 실행할 의도가 있는가

### Step 3. actual 명령이 preflight report를 소비

향후 actual export 명령은 다음과 같은 형태를 목표로 한다.

```cmd
python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --confirm-actual --preflight-report <preflight_report.json> --json
```

actual command는 report를 읽고 다음을 검증해야 한다.

- report target이 `daily_ops_status`인가
- report account_id가 CLI account_id와 같은가
- report status_date가 actual 대상 날짜와 같은가
- report External Key가 actual 대상과 같은가
- report가 너무 오래되지 않았는가
- schema validation이 PASS인가
- duplicate audit이 duplicate_blocker가 아닌가
- match_count=1이면 observed_page_id가 존재하는가
- report의 `write_executed=false`가 유지되어 있었는가
- 사용자가 `--confirm-actual`을 명시했는가

## 6. Safety Policy

향후 구현 시 유지해야 할 원칙:

- preflight report는 actual 승인 자체가 아니다.
- actual export에는 여전히 명시적 사용자 승인이 필요하다.
- actual command는 preflight report 없이 실행되면 안 된다.
- `paper_default` actual은 계속 금지한다.
- multi-account bulk actual은 계속 금지한다.
- `--all` actual은 계속 금지한다.
- External Key 수동 수정은 금지한다.
- Notion 실패만으로 local source-of-truth를 rollback하지 않는다.
- Telegram, Slack, Notion 등 외부 전송 기능은 actual 실행 조건으로 사용하지 않는다.

## 7. Relationship with Alert / Monitoring

이 actual approval flow는 Alert / Monitoring Report 이후에 구현한다.

우선순위:

```text
1. PAPER18 Alert / Monitoring Report 구축
2. Alert report가 preflight WARNING / FAIL / duplicate risk / sync failure를 예외로 표시
3. 이후 실제 Daily Ops Status actual export가 필요해지는 시점에 이 문서를 기준으로 approval flow 구현
```

Alert Report에서는 다음 정책을 따른다.

```text
actual_intent=false:
- expected_page_id missing WARNING은 강한 alert로 승격하지 않는다.
- INFO 또는 suppressed 처리 가능하다.

actual_intent=true:
- expected_page_id 또는 preflight report 검증 부족은 NEEDS_REVIEW로 승격한다.
- duplicate_blocker, schema FAIL, account mismatch는 BLOCKING으로 승격한다.
```

## 8. Deferred Implementation Candidates

향후 actual 직전 MFU 후보:

### Option A. Preflight Report Artifact

- preflight 결과를 JSON 파일로 저장
- observed_page_id 포함
- report timestamp 포함
- source hash 또는 command args 포함
- secret/page_id 마스킹 정책 정리

### Option B. Actual Export Report Consumer

- `export_paper_to_notion.py --daily-ops-status`가 `--preflight-report`를 받을 수 있게 구현
- CLI args와 preflight report 정합성 검증
- mismatch 시 actual 차단
- report stale 시 actual 차단
- duplicate_blocker 시 actual 차단

### Option C. Approval Record

- actual 승인 시 별도 approval record 생성
- 승인자, 승인 시각, 대상 account/date/external_key 기록
- 단, 승인 기록은 source-of-truth 원장과 분리

## 9. Non-scope for Now

현재 Alert / Monitoring 구축 전에는 다음을 하지 않는다.

- Daily Ops Status actual export 실행
- `--preflight-report` actual consumer 구현
- actual approval record 구현
- Telegram/Slack actual 승인 연동
- Notion write/export/sync 자동화
- paper_default actual 허용
- multi-account bulk actual 허용

## 10. Final Decision

현재 단계에서는 Alert / Monitoring Report를 먼저 구축한다.

Daily Ops Status actual export를 실제로 실행하기 전에는 이 문서를 다시 검토하고, 다음 원칙에 따라 구현한다.

```text
사용자가 expected_page_id를 직접 복사해 넣는 흐름은 최종 운영 UX로 채택하지 않는다.

preflight report가 observed_page_id와 safety checks를 기록하고,
actual command가 그 report를 검증하며,
사용자는 report 기준으로 명시 승인만 수행하는 구조를 목표로 한다.
```
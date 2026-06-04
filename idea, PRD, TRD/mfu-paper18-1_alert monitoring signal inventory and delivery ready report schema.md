BEGIN MFU-PAPER18-1-ALERT-MONITORING-DESIGN

# PAPER18-1 Alert / Monitoring Signal Inventory and Delivery-ready Report Schema

## 목적

PAPER18 Alert / Monitoring Report의 1단계 설계 문서를 작성한다.

이번 작업의 핵심은 Alert Report를 Daily Ops Status Dashboard의 중복 상태판으로 만들지 않고, 운영자가 놓치면 안 되는 예외/위험만 보여주는 Paper Ops Exception Report로 정의하는 것이다.

이번 작업은 설계 전용이다. 코드 구현, Notion write/export/sync, Telegram 전송, outputs/paper 원장 수정은 하지 않는다.

## 배경

PAPER17은 Export / Sync Policy Hardening으로 closeout 완료됐다.

PAPER17에서 완료된 핵심:

- Export / Sync Command Gate
- Duplicate audit dry-run
- .env 기반 Notion settings 정합화
- Daily Ops Status actual preflight
- schema validation + duplicate audit + command gate 통합 preflight
- actual export는 아직 미승인
- preflight PASS/WARNING은 actual 승인 자체가 아님

PAPER18은 로드맵상 Export / Sync 정책 정리 다음 단계이며, 목적은 WARNING / FAIL / Notion sync 실패 / 운영 누락을 놓치지 않게 하는 것이다.

사용자 결정사항:

1. Alert Report 범위: 예외/위험만 표시
2. 실행 시점: 최종적으로 중간/마지막 둘 다 지원 가능하게 설계하되, 초기 구현은 daily loop 마지막 기준
3. Severity 정책: BLOCKING / NEEDS_REVIEW / SYNC_FAILED / INFO
4. 초기 alert source: Daily Ops Status + PAPER17 preflight
5. actual preflight WARNING: actual_intent에 따라 승격 여부 결정
6. 출력 형식: JSON + Markdown, 계좌별 저장
7. Telegram 등 외부 전송은 후속
8. 민감정보는 모두 마스킹

## 생성 파일

아래 문서를 생성한다.

```cmd
docs\TRD\mfu_paper18_alert_monitoring_signal_inventory_and_schema.md
```

## 참고 파일

가능하면 아래 파일을 확인하고 설계에 반영한다.

```cmd
docs\TRD\paper_ops_feature_roadmap_v1_1.md
docs\TRD\mfu_paper17_export_sync_policy_hardening_closeout.md
docs\TRD\mfu_paper17_daily_ops_status_actual_preflight.md
docs\TRD\mfu_paper17_export_sync_command_gate_sop.md
docs\TRD\mfu_paper16_daily_ops_status_dashboard_closeout.md
docs\operations\paper_daily_ops.md
docs\operations\paper_notion_ops.md
```

파일명이 일부 다르면 repo에서 유사 파일을 찾아 확인한다.

## 문서 필수 섹션

문서에는 아래 섹션을 포함한다.

1. Purpose
2. Non-overlap with Daily Ops Status Dashboard
3. User Decisions
4. Initial Scope
5. Alert Sources
6. Severity Policy
7. AlertItem JSON Schema
8. Markdown Report Structure
9. Account-based Output Path Policy
10. actual_intent Policy
11. Redaction / Secret Safety Policy
12. Delivery Adapter Boundary
13. Timing / Phase Policy
14. False Positive / False Negative Risks
15. Non-scope
16. PAPER18-2 Recommendation

## 설계 요구사항

### 1. Dashboard와 역할 분리

반드시 명시한다.

```text
Daily Ops Status Dashboard = 운영 진행 상태판
Alert / Monitoring Report = 예외/위험/중단조건 리포트
```

Alert Report는 정상 상태 전체를 나열하지 않는다.  
정상 완료 항목은 기본적으로 숨기거나 INFO count 수준으로만 요약한다.

### 2. 초기 Alert Sources

초기 source는 아래로 제한한다.

```text
- Daily Ops Status
- PAPER17 Daily Ops Status actual preflight
```

후속 source로만 남길 항목:

```text
- Manual Execution preview/commit/status sync
- Manual Review preview/append/status sync
- data freshness
- same-date commit guard
- Daily Review Summary
- schema/view drift
- replay/diff
```

### 3. Severity Policy

아래 severity를 사용한다.

```text
BLOCKING
NEEDS_REVIEW
SYNC_FAILED
INFO
```

초기 판정 예시:

```text
BLOCKING:
- preflight FAIL
- schema validation FAIL
- duplicate_blocker
- account_id mismatch
- source-of-truth artifact missing/corrupt

NEEDS_REVIEW:
- actual_intent=true 상태에서 preflight WARNING
- expected_page_id missing before intended actual
- manual/operator confirmation required

SYNC_FAILED:
- local source-of-truth commit/append는 성공했지만 Notion sync/export 실패

INFO:
- update_candidate
- preflight PASS
- actual_intent=false 상태의 expected_page_id missing WARNING
```

### 4. actual_intent Policy

반드시 포함한다.

```text
actual_intent=false:
- expected_page_id missing WARNING은 강한 alert로 승격하지 않는다.
- INFO 또는 suppressed 처리 가능하다.

actual_intent=true:
- expected_page_id / preflight report 검증 부족은 NEEDS_REVIEW로 승격한다.
- duplicate_blocker, schema FAIL, account mismatch는 BLOCKING이다.
```

실제 actual export는 PAPER18 범위가 아니며, 별도 명시 승인 전까지 금지다.

### 5. AlertItem JSON Schema

Delivery-ready JSON schema를 설계한다.

예시 필드:

```json
{
  "schema_version": "paper_alert_report.v1",
  "severity": "NEEDS_REVIEW",
  "category": "DAILY_OPS_PREFLIGHT",
  "account_id": "paper_sandbox",
  "status_date": "2026-05-20",
  "title": "Daily Ops actual preflight returned WARNING",
  "message": "expected_page_id was not provided.",
  "recommended_action": "Confirm page_id only if actual export is intended.",
  "evidence": {},
  "source": "daily_ops_actual_preflight",
  "source_path": "outputs/...",
  "external_safe": true,
  "sendable": false,
  "redacted": true
}
```

### 6. Output Path Policy

계좌별 저장을 기본으로 설계한다.

후보 예시:

```text
outputs/paper_test/accounts/{account_id}/alerts/paper_alert_report_{YYYYMMDD}.json
outputs/paper_test/accounts/{account_id}/alerts/paper_alert_report_{YYYYMMDD}.md
```

repo의 기존 account root convention이 다르면 그것을 우선한다.

### 7. Redaction / Secret Safety

외부 전송 확장을 고려해 마스킹 정책을 정의한다.

반드시 마스킹:

```text
- Notion token
- Notion data source id
- Notion page_id 전체값
- 절대경로
- secret/env 값
```

표시 가능 후보:

```text
- account_id
- status_date
- severity
- category
- classification
- recommended_action
```

### 8. Delivery Adapter Boundary

PAPER18-1에서는 Telegram/Slack/Email을 구현하지 않는다.

다만 구조상 아래처럼 분리한다.

```text
Alert Engine -> JSON/Markdown Report
Delivery Adapter -> 후속에서 JSON을 읽어 Telegram/Slack/Email 전송
```

전송 실패는 source-of-truth 실패가 아니다.

### 9. Timing / Phase Policy

초기 구현은 daily loop closeout 시점 기준으로 설계한다.

향후 phase 후보:

```text
closeout
checkpoint
pre-actual
```

중간 단계에서는 아직 정상적으로 완료되지 않은 항목을 누락으로 오탐하지 않도록 phase-aware 정책을 둔다.

## Non-scope

이번 작업에서는 절대 하지 않는다.

```text
Python 코드 구현
Alert report CLI 구현
Telegram/Slack/Email 전송 구현
Notion actual write/export/sync
Daily Ops Status actual export
outputs/paper 원장 수정
schema/view drift 구현
replay/diff 구현
duplicate cleanup
paper_default actual 허용
multi-account bulk actual 허용
```

## 검증 명령

Windows CMD 기준으로 실행한다.

```cmd
git status --short

type docs\TRD\mfu_paper18_alert_monitoring_signal_inventory_and_schema.md

findstr /N /I "Dashboard Alert BLOCKING NEEDS_REVIEW SYNC_FAILED INFO actual_intent JSON Markdown Telegram redaction paper_sandbox source-of-truth" docs\TRD\mfu_paper18_alert_monitoring_signal_inventory_and_schema.md

git diff --check -- docs\TRD\mfu_paper18_alert_monitoring_signal_inventory_and_schema.md
```

## Git 주의사항

금지:

```cmd
git add .
git add -A
```

이번 작업은 설계 문서 생성까지만 하고 커밋하지 않는다.  
커밋 후보는 결과 보고에만 명시한다.

커밋 후보:

```cmd
docs\TRD\mfu_paper18_alert_monitoring_signal_inventory_and_schema.md
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
unrelated local artifacts
```

## 성공 기준

- PAPER18-1 설계 문서가 생성됨
- Alert Report가 Dashboard와 중복되지 않도록 정의됨
- 초기 source가 Daily Ops Status + PAPER17 preflight로 제한됨
- severity 정책이 정의됨
- actual_intent 정책이 정의됨
- 계좌별 JSON/Markdown 출력 정책이 정의됨
- delivery-ready schema가 정의됨
- Telegram 등 외부 전송은 후속으로 분리됨
- 민감정보 마스킹 정책이 포함됨
- 코드 변경 없음
- Notion write/export/sync 없음
- outputs/paper 원장 변경 없음
- git diff --check 통과

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 생성/수정한 파일
3. Dashboard와 Alert Report 역할 분리 내용
4. 사용자 결정사항 반영 여부
5. 초기 Alert Sources
6. Severity Policy 요약
7. actual_intent 정책 요약
8. AlertItem JSON schema 요약
9. Markdown report 구조 요약
10. 계좌별 output path 정책
11. 민감정보 마스킹 정책
12. Delivery adapter boundary
13. 코드 변경 여부
14. Notion write/export/sync 실행 여부
15. outputs/paper 원장 변경 여부
16. git diff --check 결과
17. PAPER18-2 추천 작업

END MFU-PAPER18-1-ALERT-MONITORING-DESIGN
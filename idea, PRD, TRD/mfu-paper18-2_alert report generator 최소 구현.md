BEGIN MFU-PAPER18-2-ALERT-REPORT-GENERATOR

# PAPER18-1 커밋 + PAPER18-2 Alert Report Generator 최소 구현

## 목적

먼저 PAPER18-1 Alert / Monitoring 설계 문서를 커밋한다.

그 다음 PAPER18-2로 `paper_sandbox` closeout 기준의 로컬 Alert Report generator를 최소 구현한다.

Alert Report는 Daily Ops Status Dashboard의 중복 상태판이 아니다.  
정상 상태 전체를 나열하지 않고, 예외 / 위험 / 중단조건만 JSON + Markdown으로 출력하는 Paper Ops Exception Report다.

이번 작업은 read-only report 생성 작업이다.

절대 하지 말 것:

- Notion actual write/export/sync
- Daily Ops Status actual export
- Telegram/Slack/Email 전송
- outputs/paper 원장 수정
- commit/append/status sync 실행

## 배경

PAPER18-1 설계 결과:

- Alert Report 범위: 예외/위험만 표시
- 초기 실행 시점: daily loop closeout
- Severity: BLOCKING / NEEDS_REVIEW / SYNC_FAILED / INFO
- 초기 source: Daily Ops Status + PAPER17 Daily Ops Status actual preflight
- actual_intent=false이면 expected_page_id missing WARNING은 강한 alert로 승격하지 않음
- actual_intent=true이면 preflight WARNING은 NEEDS_REVIEW
- output: 계좌별 JSON + Markdown
- Telegram 등 외부 전송은 후속
- 민감정보는 마스킹

## 1단계: PAPER18-1 설계 문서 커밋

### 대상 파일

```cmd
docs\TRD\mfu_paper18_alert_monitoring_signal_inventory_and_schema.md
```

### 확인

```cmd
git status --short
type docs\TRD\mfu_paper18_alert_monitoring_signal_inventory_and_schema.md
git diff --check -- docs\TRD\mfu_paper18_alert_monitoring_signal_inventory_and_schema.md
```

### stage / commit

절대 사용 금지:

```cmd
git add .
git add -A
```

실행:

```cmd
git add docs\TRD\mfu_paper18_alert_monitoring_signal_inventory_and_schema.md
git diff --cached --name-only
git diff --cached
git commit -m "docs: design PAPER18 alert monitoring report"
git log -1 --stat
git status --short
```

이미 동일 문서가 커밋되어 있으면 새 커밋을 만들지 말고 보고한다.

## 2단계: Alert Report Generator 최소 구현

## 구현 범위

초기 구현은 `paper_sandbox` / closeout phase 전용으로 제한한다.

지원 입력:

```text
Daily Ops Status payload
PAPER17 Daily Ops Status actual preflight payload
```

실제 repo artifact 경로가 아직 불명확하면, core 함수는 dict payload를 입력받도록 만들고 CLI는 JSON 파일 입력을 받게 한다.

권장 CLI:

```cmd
python scripts\dev\generate_paper_alert_report.py --account-id paper_sandbox --date 2026-05-20 --phase closeout --daily-ops-status-json <path> --preflight-json <path> --json
```

지원 옵션:

```text
--account-id
--date
--phase closeout
--actual-intent
--daily-ops-status-json
--preflight-json
--output-dir
--json
```

초기에는 `phase=closeout`만 허용한다.  
`checkpoint`, `pre-actual`은 future로 남긴다.

## 생성/수정 후보 파일

```text
core/paper_alert_report.py
scripts/dev/generate_paper_alert_report.py
tests/test_paper_alert_report.py
docs/TRD/mfu_paper18_alert_report_generator_minimal.md
```

기존 convention에 맞는 더 적절한 파일명이 있으면 조정 가능하다.

## AlertItem 요구사항

AlertItem 최소 필드:

```json
{
  "schema_version": "paper_alert_report.v1",
  "severity": "NEEDS_REVIEW",
  "category": "DAILY_OPS_PREFLIGHT",
  "account_id": "paper_sandbox",
  "status_date": "2026-05-20",
  "title": "...",
  "message": "...",
  "recommended_action": "...",
  "evidence": {},
  "source": "daily_ops_actual_preflight",
  "source_path": "...",
  "external_safe": true,
  "sendable": false,
  "redacted": true
}
```

Report envelope:

```json
{
  "schema_version": "paper_alert_report.v1",
  "account_id": "paper_sandbox",
  "report_date": "2026-05-20",
  "phase": "closeout",
  "actual_intent": false,
  "summary": {
    "blocking_count": 0,
    "needs_review_count": 0,
    "sync_failed_count": 0,
    "info_count": 1
  },
  "items": []
}
```

## Severity 정책

필수 구현:

```text
preflight overall_status=FAIL
→ BLOCKING

preflight schema_validation_result=FAIL
→ BLOCKING

duplicate_audit.classification=duplicate_blocker
→ BLOCKING

account mismatch
→ BLOCKING

preflight overall_status=WARNING + actual_intent=true
→ NEEDS_REVIEW

expected_page_id missing + actual_intent=true
→ NEEDS_REVIEW

preflight overall_status=WARNING + actual_intent=false
→ INFO 또는 suppressed

duplicate_audit.classification=update_candidate + actual_intent=false
→ INFO

preflight overall_status=PASS
→ INFO 또는 suppressed
```

초기 구현에서는 normal completed 상태 전체를 확장 표시하지 않는다.

## Markdown 출력

Markdown 구조:

```text
# Paper Ops Exception Report - {account_id} - {date}

## Summary
- BLOCKING: n
- NEEDS_REVIEW: n
- SYNC_FAILED: n
- INFO: n

## Blocking
...

## Needs Review
...

## Sync Failed
...

## Info / Suppressed Summary
...

## Source Inputs
...

## Redaction Notes
...
```

INFO는 기본적으로 요약 중심으로 표시한다.

## Output path 정책

기본 출력 경로:

```text
outputs/paper_accounts/{account_id}/alerts/paper_alert_report_{YYYYMMDD}.json
outputs/paper_accounts/{account_id}/alerts/paper_alert_report_{YYYYMMDD}.md
```

테스트에서는 `tmp_path` 또는 `--output-dir`을 사용해 실제 outputs를 오염시키지 않는다.

## Redaction 정책

반드시 마스킹:

```text
Notion token
Notion data source id
full Notion page_id
absolute local path
secret/env value
```

허용 표시:

```text
account_id
status_date
severity
category
duplicate classification
schema validation result
recommended_action
```

page_id는 필요 시 끝 4자리만 남기고 `****1234` 형태로 마스킹한다.  
절대경로는 repo-relative 또는 `<redacted_path>`로 변환한다.

## 테스트 요구사항

`tests/test_paper_alert_report.py`를 추가한다.

필수 테스트:

```text
preflight FAIL → BLOCKING
duplicate_blocker → BLOCKING
actual_intent=true + WARNING → NEEDS_REVIEW
actual_intent=false + expected_page_id warning → INFO 또는 suppressed
update_candidate → INFO
summary count 계산
JSON report schema_version 포함
Markdown report 생성
계좌별 output path 생성
민감정보 마스킹
Telegram/delivery 실행 없음
```

테스트는 fixture payload 또는 dict 입력을 사용한다.  
Notion API 호출 금지.

## 검증 명령

Windows CMD 기준:

```cmd
git status --short

python scripts\dev\generate_paper_alert_report.py --help

pytest tests\test_paper_alert_report.py

type docs\TRD\mfu_paper18_alert_report_generator_minimal.md

findstr /N /I "Alert Report BLOCKING NEEDS_REVIEW SYNC_FAILED INFO actual_intent JSON Markdown redaction paper_sandbox delivery" docs\TRD\mfu_paper18_alert_report_generator_minimal.md

git diff --check -- core\paper_alert_report.py scripts\dev\generate_paper_alert_report.py tests\test_paper_alert_report.py docs\TRD\mfu_paper18_alert_report_generator_minimal.md
```

가능하면 fixture 기반 CLI smoke도 실행한다.  
단, 실제 Notion API 호출, actual export, source-of-truth 변경은 금지한다.

## 문서 작성

생성 문서:

```text
docs/TRD/mfu_paper18_alert_report_generator_minimal.md
```

포함 섹션:

1. Purpose
2. Scope
3. CLI
4. Input Contract
5. AlertItem Schema
6. Severity Mapping
7. actual_intent Policy
8. Output Path Policy
9. Markdown Report Format
10. Redaction Policy
11. Test Coverage
12. Limitations
13. PAPER18-3 Recommendation

반드시 명시:

- Alert Report는 Dashboard 중복이 아님
- 정상 상태 전체 나열 금지
- 초기 source는 Daily Ops Status + PAPER17 preflight
- Telegram/Slack/Email 전송은 후속
- read-only report 생성만 수행

## Non-scope

이번 작업에서는 절대 하지 않는다.

```text
Notion write/export/sync
Daily Ops Status actual export
Telegram/Slack/Email 전송
outputs/paper 원장 수정
commit/append/status sync 실행
schema/view drift 구현
replay/diff 구현
manual execution/review source 연결
paper_default actual 허용
multi-account bulk actual 허용
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
unrelated local artifacts
```

이번 PAPER18-2 구현 결과는 아직 커밋하지 않는다.  
결과 보고에 커밋 후보 파일만 명시한다.

예상 커밋 후보:

```cmd
core\paper_alert_report.py
scripts\dev\generate_paper_alert_report.py
tests\test_paper_alert_report.py
docs\TRD\mfu_paper18_alert_report_generator_minimal.md
```

## 성공 기준

- PAPER18-1 설계 문서가 커밋됨
- Alert Report generator 최소 구현 완료
- JSON + Markdown report 생성 가능
- 계좌별 output path 정책 구현
- severity / actual_intent 정책 구현
- 민감정보 마스킹 구현
- 테스트 통과
- Notion API 호출 없음
- Notion write/export/sync 없음
- outputs/paper 원장 변경 없음
- git diff --check 통과

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. PAPER18-1 커밋 생성 여부
3. PAPER18-1 커밋 SHA / 메시지
4. 생성/수정한 파일
5. Alert Report generator CLI 요약
6. 입력 payload 정책
7. severity / actual_intent 정책 구현 요약
8. JSON/Markdown output 요약
9. 계좌별 output path 정책
10. redaction 구현 요약
11. 테스트 결과
12. Notion API 호출 여부
13. Notion write/export/sync 실행 여부
14. outputs/paper 원장 변경 여부
15. git diff --check 결과
16. 커밋 후보 파일
17. 남은 리스크
18. PAPER18-3 추천 작업

END MFU-PAPER18-2-ALERT-REPORT-GENERATOR
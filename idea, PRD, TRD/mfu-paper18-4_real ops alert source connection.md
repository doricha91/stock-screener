BEGIN MFU-PAPER18-4-REAL-OPS-ALERT-SOURCE-CONNECTION

# PAPER18-4 Real Ops Alert Source Connection

## 목적

PAPER18-4에서는 Alert Report generator가 fixture payload뿐 아니라 실제 운영 artifact/source를 읽어 Alert Report를 생성할 수 있도록 최소 연결을 구현한다.

핵심 목표:

1. account_id/date 기준으로 실제 운영 source 파일을 찾거나 명시 입력받는다.
2. Daily Ops Status payload와 PAPER17 preflight payload를 Alert Report generator에 연결한다.
3. sync failure, review pending/incomplete, preflight warning/fail 같은 실제 운영 위험을 AlertItem으로 변환한다.
4. JSON/Markdown Alert Report를 계좌별 경로 또는 --output-dir에 생성한다.
5. Notion API 호출, Notion write/export/sync, 외부 전송은 하지 않는다.

이번 작업은 read-only source connection이다.

## 배경

PAPER18 진행 상황:

- PAPER18-1: Alert / Monitoring Report 설계 완료
- PAPER18-2: Alert Report generator 최소 구현 완료
- PAPER18-3: INFO suppression policy와 CLI smoke test hardening 완료

PAPER18-3 정책:

- JSON에는 INFO AlertItem을 보존한다.
- Markdown에서는 BLOCKING / NEEDS_REVIEW / SYNC_FAILED만 상세 표시한다.
- INFO는 count/reason 중심으로 suppress한다.
- actual_intent=false + expected_page_id missing은 suppressed INFO다.
- actual_intent=true + preflight WARNING은 NEEDS_REVIEW다.
- Notion API/write/export/sync와 외부 전송은 없다.

PAPER18-4는 “실제 운영 source 연결” 단계다.  
단, 아직 source 범위는 Daily Ops Status + PAPER17 preflight 중심으로 유지한다.

## 대상 파일

수정/생성 후보:

```text
core/paper_alert_report.py
scripts/dev/generate_paper_alert_report.py
tests/test_paper_alert_report.py
docs/TRD/mfu_paper18_real_ops_alert_source_connection.md
```

필요하다면 source resolver 전용 파일을 추가해도 된다.

```text
core/paper_alert_sources.py
```

단, 파일 수를 불필요하게 늘리지 않는다.

## 구현 범위

### 1. Source input 정책

현재 CLI는 JSON 파일 경로를 입력으로 받는다.

기존 명시 입력은 유지한다.

```cmd
python scripts\dev\generate_paper_alert_report.py --account-id paper_sandbox --date 2026-05-20 --phase closeout --daily-ops-status-json <path> --preflight-json <path> --output-dir <path> --json
```

PAPER18-4에서는 다음 중 가능한 최소 구현을 추가한다.

권장:

```text
A. 명시 JSON 입력 경로 유지
B. account_id/date 기준 기본 source path resolver 추가
C. source 파일이 없을 때 missing source alert 생성 또는 source_missing 상태 기록
```

실제 repo의 account-aware output convention을 우선 사용한다.

기본 후보 경로:

```text
outputs/paper_accounts/{account_id}/...
```

정확한 기존 artifact 경로가 불명확하면, 자동 discovery는 과도하게 구현하지 말고 문서화한 뒤 명시 JSON 입력 방식을 유지한다.

### 2. Daily Ops Status source 연결

Daily Ops Status payload에서 아래 신호를 AlertItem으로 변환한다.

필드명은 실제 payload에 맞춰 구현한다. 필드가 없으면 안전하게 source_missing 또는 unknown으로 처리한다.

초기 감지 후보:

```text
workflow_status가 incomplete/unknown/fail 성격 → NEEDS_REVIEW 또는 BLOCKING
review_progress_status가 partial/not_done 성격 → NEEDS_REVIEW
sync_status가 failed/sync_failed 성격 → SYNC_FAILED
필수 artifact/status field 누락 → NEEDS_REVIEW
명확한 source-of-truth artifact missing/corrupt → BLOCKING
```

주의:

- 정상 상태 전체를 AlertItem으로 나열하지 않는다.
- 정상 상태는 INFO count 또는 source summary에만 남긴다.
- 판단이 애매하면 BLOCKING으로 과격하게 올리지 말고 NEEDS_REVIEW로 둔다.

### 3. PAPER17 preflight source 연결

기존 preflight payload 정책을 유지한다.

```text
overall_status=FAIL → BLOCKING
schema_validation_result=FAIL → BLOCKING
duplicate_audit.classification=duplicate_blocker → BLOCKING
account mismatch → BLOCKING
actual_intent=true + overall_status=WARNING → NEEDS_REVIEW
actual_intent=false + expected_page_id missing WARNING → suppressed INFO
update_candidate + actual_intent=false → INFO
```

### 4. source_missing 정책

source file이 없거나 JSON parsing이 실패할 수 있다.

정책:

```text
daily_ops_status source missing at closeout phase → NEEDS_REVIEW
preflight source missing + actual_intent=false → INFO 또는 suppressed
preflight source missing + actual_intent=true → NEEDS_REVIEW
JSON parse error → BLOCKING 또는 NEEDS_REVIEW
```

추천:

- parse error는 source가 존재하지만 읽을 수 없는 것이므로 BLOCKING 후보
- 단순 missing은 phase/actual_intent에 따라 조정

### 5. CLI 옵션

기존 옵션은 유지한다.

추가 후보:

```text
--auto-source
--source-root
--strict-sources
```

권장 최소 구현:

```text
--source-root <path>
```

이 옵션이 있으면 account/date 기준으로 source resolver가 기본 위치를 찾는다.

단, 자동 경로가 불확실하면 이번 단계에서는 문서화만 하고, CLI는 명시 JSON 입력을 유지해도 된다.

### 6. 출력 정책

기존 정책 유지:

```text
outputs/paper_accounts/{account_id}/alerts/paper_alert_report_{YYYYMMDD}.json
outputs/paper_accounts/{account_id}/alerts/paper_alert_report_{YYYYMMDD}.md
```

테스트와 smoke는 반드시 `tmp_path` 또는 `--output-dir`을 사용한다.  
실제 outputs/paper_accounts를 테스트에서 오염시키지 않는다.

## 테스트 요구사항

`tests/test_paper_alert_report.py`를 보강한다.

필수 테스트:

```text
- Daily Ops Status sync failure → SYNC_FAILED
- Daily Ops Status review partial/incomplete → NEEDS_REVIEW
- Daily Ops Status missing source at closeout → NEEDS_REVIEW
- malformed JSON source → BLOCKING 또는 NEEDS_REVIEW
- preflight missing + actual_intent=false → INFO/suppressed
- preflight missing + actual_intent=true → NEEDS_REVIEW
- 실제 source resolver는 tmp_path fixture에서만 동작
- JSON/Markdown 생성 유지
- INFO suppression 정책 유지
- Notion API 호출 없음
- delivery_executed=false 유지
```

## 문서 작성

생성 문서:

```text
docs/TRD/mfu_paper18_real_ops_alert_source_connection.md
```

포함 섹션:

1. Purpose
2. Scope
3. Source Inputs
4. Daily Ops Status Mapping
5. Preflight Mapping
6. Missing / Malformed Source Policy
7. CLI
8. Output Path Policy
9. Read-only Safety Policy
10. Test Coverage
11. Limitations
12. PAPER18-5 Recommendation

반드시 명시:

- Alert Report는 Dashboard 중복이 아니다.
- 정상 상태 전체 나열 금지.
- 실제 source 연결은 read-only다.
- Notion API 호출 없음.
- Notion write/export/sync 없음.
- 외부 전송 없음.
- source가 없을 때 무리하게 actual/export/sync로 보완하지 않는다.

## 검증 명령

Windows CMD 기준:

```cmd
git status --short

python scripts\dev\generate_paper_alert_report.py --help

pytest tests\test_paper_alert_report.py

type docs\TRD\mfu_paper18_real_ops_alert_source_connection.md

findstr /N /I "source Daily Ops sync failed review partial missing malformed preflight actual_intent read-only Notion delivery" docs\TRD\mfu_paper18_real_ops_alert_source_connection.md

git diff --check -- core\paper_alert_report.py scripts\dev\generate_paper_alert_report.py tests\test_paper_alert_report.py docs\TRD\mfu_paper18_real_ops_alert_source_connection.md
```

새 파일을 추가했다면 diff check 대상에 포함한다.

예:

```cmd
git diff --check -- core\paper_alert_sources.py
```

## 구현 후 자체 점검 항목

Codex는 구현 후 아래를 직접 확인하고 결과 보고에 포함한다.

### Source 연결 점검

- Daily Ops Status payload가 Alert source로 처리되는가
- preflight payload가 기존 정책대로 처리되는가
- sync failure가 SYNC_FAILED로 분류되는가
- review partial/incomplete가 NEEDS_REVIEW로 분류되는가
- missing source가 phase/actual_intent에 따라 적절히 분류되는가
- malformed JSON이 안전하게 alert로 전환되는가

### Dashboard 중복 방지 점검

- 정상 완료 상태 전체를 AlertItem으로 나열하지 않는가
- Markdown이 Dashboard처럼 변질되지 않는가
- INFO는 JSON에 보존되고 Markdown에서는 suppress되는가

### Safety 점검

- Notion API 호출이 없는가
- Notion write/export/sync 호출이 없는가
- Telegram/Slack/Email 전송이 없는가
- commit/append/status sync 실행이 없는가
- outputs/paper 원장 변경이 없는가
- 테스트가 실제 outputs/paper_accounts를 오염시키지 않는가

### Redaction 점검

- 기존 마스킹 정책이 유지되는가
- page_id/data_source_id/secret-like 값이 원문 노출되지 않는가
- absolute path가 원문 노출되지 않는가

### Git 점검

- unrelated 파일이 staged 되지 않았는가
- `.env`, `config/notion_settings.json`, outputs/backtest_log.db 등이 staged 되지 않았는가
- `git diff --check`가 통과했는가

blocker가 있으면 커밋하지 말고 보고한다.  
blocker가 없고 테스트가 통과하면 PAPER18-4 결과를 커밋한다.

## Non-scope

이번 작업에서는 절대 하지 않는다.

```text
Notion API 호출
Notion write/export/sync
Daily Ops Status actual export
Telegram/Slack/Email 전송
outputs/paper 원장 수정
commit/append/status sync 실행
Manual Execution/Review 세부 source 연결
data freshness source 연결
schema/view drift 구현
replay/diff 구현
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

## 커밋 정책

구현 후 자체 점검에서 blocker가 없고 테스트가 통과하면 실제 수정/생성 파일만 개별 stage한다.

예상 후보:

```cmd
git add core\paper_alert_report.py
git add scripts\dev\generate_paper_alert_report.py
git add tests\test_paper_alert_report.py
git add docs\TRD\mfu_paper18_real_ops_alert_source_connection.md
```

새 파일이 있다면 개별 추가:

```cmd
git add core\paper_alert_sources.py
```

커밋 메시지:

```cmd
git commit -m "feat: connect PAPER18 alert report to real ops sources"
```

커밋 후 확인:

```cmd
git log -1 --stat
git status --short
```

## 성공 기준

- 실제 운영 source 연결 범위가 구현됨
- Daily Ops Status sync failure / review incomplete 계열 alert가 생성됨
- PAPER17 preflight 정책이 유지됨
- missing/malformed source 정책이 구현됨
- JSON/Markdown output이 유지됨
- INFO suppression 정책이 유지됨
- 테스트 통과
- Notion API 호출 없음
- Notion write/export/sync 없음
- 외부 전송 없음
- outputs/paper 원장 변경 없음
- 자체 점검 결과가 보고됨
- blocker 없으면 커밋 완료

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 생성/수정한 파일
3. 실제 운영 source 연결 내용
4. Daily Ops Status mapping 요약
5. Preflight mapping 유지 여부
6. missing/malformed source 정책
7. CLI 변경 여부
8. JSON/Markdown output 영향
9. INFO suppression 유지 여부
10. 테스트 결과
11. Notion API 호출 여부
12. Notion write/export/sync 실행 여부
13. 외부 전송 실행 여부
14. outputs/paper 원장 변경 여부
15. 자체 점검 결과
16. git diff --check 결과
17. 커밋 생성 여부
18. 커밋 SHA / 메시지
19. 제외한 unrelated 파일
20. 남은 리스크
21. PAPER18-5 추천 작업

END MFU-PAPER18-4-REAL-OPS-ALERT-SOURCE-CONNECTION
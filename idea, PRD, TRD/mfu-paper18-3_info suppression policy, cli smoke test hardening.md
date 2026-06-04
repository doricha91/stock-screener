BEGIN MFU-PAPER18-3-INFO-SUPPRESSION-AND-CLI-SMOKE-HARDENING

# PAPER18-2 커밋 + PAPER18-3 INFO Suppression Policy / CLI Smoke Test Hardening

## 목적

먼저 PAPER18-2 Alert Report generator 최소 구현물을 커밋한다.

그 다음 PAPER18-3로 다음을 구현한다.

1. Markdown에서 INFO 항목을 기본적으로 count 중심으로 줄인다.
2. JSON에는 INFO 항목을 보존한다.
3. actual_intent=false 상태의 expected_page_id missing WARNING은 suppressed INFO로 처리한다.
4. actual_intent=true 상태의 expected_page_id missing 또는 preflight WARNING은 NEEDS_REVIEW로 유지한다.
5. fixture 기반 CLI smoke를 정식 테스트로 보강한다.
6. 작업 후 자체 점검을 수행하고, 통과 시 PAPER18-3도 별도 커밋한다.

이번 작업은 read-only Alert Report generator 개선이다.

절대 하지 말 것:

- Notion API 호출
- Notion write/export/sync
- Daily Ops Status actual export
- Telegram/Slack/Email 전송
- outputs/paper 원장 수정
- commit/append/status sync 실행

## 배경

PAPER18-2 구현 검토 결과:

- blocker 없음
- AlertItem schema는 설계와 대체로 일치
- severity / actual_intent 정책 구현됨
- Notion API 호출 없음
- Notion write/export/sync 없음
- 테스트 10 passed
- git diff --check 통과
- 현재 INFO는 Markdown에서 title/message/action이 표시되어 완전한 suppression은 아님

사용자 결정사항:

- 현재 redaction 수준은 수용한다.
- INFO는 JSON에 보존하되 Markdown에서는 count 중심으로 줄인다.
- actual_intent=false의 expected_page_id missing은 suppressed INFO로 처리한다.
- actual_intent=true에서는 NEEDS_REVIEW로 승격한다.

## 1단계: PAPER18-2 커밋

### 대상 파일

아래 4개 파일만 커밋한다.

```cmd
core\paper_alert_report.py
scripts\dev\generate_paper_alert_report.py
tests\test_paper_alert_report.py
docs\TRD\mfu_paper18_alert_report_generator_minimal.md
```

### 검증

```cmd
git status --short
pytest tests\test_paper_alert_report.py
git diff --check -- core\paper_alert_report.py scripts\dev\generate_paper_alert_report.py tests\test_paper_alert_report.py docs\TRD\mfu_paper18_alert_report_generator_minimal.md
```

### stage / commit

금지:

```cmd
git add .
git add -A
```

실행:

```cmd
git add core\paper_alert_report.py
git add scripts\dev\generate_paper_alert_report.py
git add tests\test_paper_alert_report.py
git add docs\TRD\mfu_paper18_alert_report_generator_minimal.md

git diff --cached --name-only
git diff --cached

git commit -m "feat: add PAPER18 alert report generator"

git log -1 --stat
git status --short
```

## 2단계: PAPER18-3 구현

## 수정 후보 파일

```text
core/paper_alert_report.py
scripts/dev/generate_paper_alert_report.py
tests/test_paper_alert_report.py
docs/TRD/mfu_paper18_alert_report_generator_minimal.md
docs/TRD/mfu_paper18_info_suppression_and_cli_smoke_hardening.md
```

필요한 파일만 최소 수정한다.

## 구현 요구사항

### 1. INFO suppression 정책

JSON report에는 INFO AlertItem을 보존한다.

Markdown report에서는 기본적으로 다음만 상세 표시한다.

```text
BLOCKING
NEEDS_REVIEW
SYNC_FAILED
```

INFO는 기본적으로 상세 목록을 펼치지 않고 count 중심으로 표시한다.

예시:

```text
## Info / Suppressed Summary
- INFO: 2
- Suppressed INFO: 1
- INFO details are preserved in JSON.
```

### 2. suppressed INFO 필드

AlertItem 또는 report item에 아래 중 적절한 필드를 추가한다.

```json
{
  "suppressed_in_markdown": true,
  "suppression_reason": "actual_intent=false"
}
```

정책:

```text
actual_intent=false + expected_page_id missing
→ severity=INFO
→ suppressed_in_markdown=true
→ suppression_reason=actual_intent=false

actual_intent=true + expected_page_id missing
→ severity=NEEDS_REVIEW
→ suppressed_in_markdown=false
```

### 3. Markdown 출력 정책

Markdown에서는 다음 원칙을 지킨다.

```text
- BLOCKING / NEEDS_REVIEW / SYNC_FAILED는 상세 표시
- INFO는 기본 상세 표시하지 않음
- suppressed INFO는 count와 reason만 표시
- 정상 상태 전체 나열 금지
- Dashboard처럼 상태판화 금지
```

단, JSON에는 모든 AlertItem을 보존한다.

### 4. CLI smoke test hardening

fixture 기반 CLI smoke를 정식 테스트로 편입한다.

테스트 조건:

```text
- tmp_path에 임시 preflight JSON 생성
- tmp_path 또는 임시 output-dir 사용
- CLI main 또는 subprocess equivalent 실행
- JSON report 생성 확인
- Markdown report 생성 확인
- 실제 outputs/paper_accounts 경로를 오염시키지 않음
- Notion API 호출 없음
- delivery_executed=false
- notion_write_export_sync_executed=false 또는 동등한 안전 필드 확인
```

가능하면 `scripts/dev/generate_paper_alert_report.py`의 main 함수를 직접 호출하는 방식으로 테스트한다. subprocess가 더 안정적이면 사용해도 된다.

### 5. 문서 작성

아래 문서를 생성한다.

```text
docs/TRD/mfu_paper18_info_suppression_and_cli_smoke_hardening.md
```

포함 섹션:

1. Purpose
2. Scope
3. INFO Suppression Policy
4. actual_intent Policy
5. Markdown Behavior
6. JSON Preservation Policy
7. CLI Smoke Test Hardening
8. Test Coverage
9. Limitations
10. PAPER18-4 Recommendation

반드시 명시:

- INFO는 JSON에 보존
- Markdown은 예외/위험 중심
- actual_intent=false의 expected_page_id warning은 suppressed INFO
- actual_intent=true의 expected_page_id warning은 NEEDS_REVIEW
- Telegram/Slack/Email 전송은 후속
- Notion API 호출 없음
- outputs/paper 원장 변경 없음

## 테스트 요구사항

`tests/test_paper_alert_report.py`에 아래 테스트를 추가 또는 보강한다.

필수:

```text
- actual_intent=false + expected_page_id missing → INFO + suppressed_in_markdown=true
- actual_intent=true + expected_page_id missing → NEEDS_REVIEW + suppressed_in_markdown=false
- JSON에는 suppressed INFO item이 보존됨
- Markdown에는 suppressed INFO 상세 title/message가 펼쳐지지 않음
- Markdown summary에는 suppressed count가 표시됨
- BLOCKING / NEEDS_REVIEW / SYNC_FAILED는 Markdown에 상세 표시됨
- fixture 기반 CLI smoke가 tmp_path output-dir에 JSON/Markdown을 생성함
- CLI smoke가 실제 outputs/paper_accounts를 오염시키지 않음
- delivery_executed=false
- Notion API 호출 없음
```

## 검증 명령

Windows CMD 기준:

```cmd
git status --short

python scripts\dev\generate_paper_alert_report.py --help

pytest tests\test_paper_alert_report.py

type docs\TRD\mfu_paper18_info_suppression_and_cli_smoke_hardening.md

findstr /N /I "INFO suppressed Markdown JSON actual_intent expected_page_id NEEDS_REVIEW BLOCKING SYNC_FAILED CLI smoke delivery Notion" docs\TRD\mfu_paper18_info_suppression_and_cli_smoke_hardening.md

git diff --check -- core\paper_alert_report.py scripts\dev\generate_paper_alert_report.py tests\test_paper_alert_report.py docs\TRD\mfu_paper18_alert_report_generator_minimal.md docs\TRD\mfu_paper18_info_suppression_and_cli_smoke_hardening.md
```

## 구현 후 자체 점검 항목

Codex는 구현 후 아래 항목을 스스로 확인하고 결과 보고에 포함한다.

### 정책 점검

- JSON에는 INFO AlertItem이 보존되는가
- Markdown에서는 INFO 상세가 기본적으로 suppress되는가
- suppressed INFO count가 summary 또는 Info/Suppressed Summary에 표시되는가
- actual_intent=false expected_page_id missing이 INFO/suppressed 처리되는가
- actual_intent=true expected_page_id missing이 NEEDS_REVIEW로 처리되는가
- BLOCKING / NEEDS_REVIEW / SYNC_FAILED 상세는 Markdown에 표시되는가
- Alert Report가 Dashboard처럼 정상 상태 전체를 나열하지 않는가

### 안전성 점검

- Notion API 호출이 없는가
- Notion write/export/sync 호출이 없는가
- Telegram/Slack/Email 전송이 없는가
- delivery_executed=false가 유지되는가
- 실제 outputs/paper_accounts 경로를 테스트가 오염시키지 않는가
- outputs/paper 원장 변경이 없는가

### Redaction 점검

- 기존 redaction 정책을 깨지 않았는가
- page_id/data_source_id/secret-like 값이 JSON/Markdown에 원문 노출되지 않는가
- absolute path가 원문 노출되지 않는가

### Git 점검

- unrelated 파일이 staged 되지 않았는가
- `.env`, `config/notion_settings.json`, outputs/backtest_log.db 등이 staged 되지 않았는가
- `git diff --check` 통과했는가

수정이 필요한 blocker를 발견하면 커밋하지 말고 보고한다.  
blocker가 없고 테스트가 통과하면 PAPER18-3 결과를 커밋한다.

## Non-scope

이번 작업에서는 절대 하지 않는다.

```text
Notion API 호출
Notion write/export/sync
Daily Ops Status actual export
Telegram/Slack/Email 전송
outputs/paper 원장 수정
commit/append/status sync 실행
Manual Execution/Review source 연결
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

## PAPER18-3 커밋 정책

구현 후 자체 점검에서 blocker가 없고 테스트가 통과하면 아래 파일 중 실제 수정/생성된 파일만 개별 stage한다.

예상 후보:

```cmd
git add core\paper_alert_report.py
git add scripts\dev\generate_paper_alert_report.py
git add tests\test_paper_alert_report.py
git add docs\TRD\mfu_paper18_alert_report_generator_minimal.md
git add docs\TRD\mfu_paper18_info_suppression_and_cli_smoke_hardening.md
```

커밋 메시지:

```cmd
git commit -m "feat: harden PAPER18 alert info suppression and CLI smoke"
```

커밋 후 확인:

```cmd
git log -2 --stat
git status --short
```

## 성공 기준

- PAPER18-2 구현물이 커밋됨
- PAPER18-3 INFO suppression 정책이 구현됨
- JSON에는 INFO가 보존됨
- Markdown은 INFO를 count 중심으로 suppress함
- actual_intent=false expected_page_id warning은 suppressed INFO
- actual_intent=true expected_page_id warning은 NEEDS_REVIEW
- fixture 기반 CLI smoke test가 정식 테스트에 포함됨
- Notion API 호출 없음
- Notion write/export/sync 없음
- outputs/paper 원장 변경 없음
- 테스트 통과
- git diff --check 통과
- PAPER18-3 자체 점검 결과가 보고됨
- blocker 없으면 PAPER18-3 커밋 완료

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. PAPER18-2 커밋 생성 여부
3. PAPER18-2 커밋 SHA / 메시지
4. PAPER18-3 생성/수정 파일
5. INFO suppression 정책 구현 요약
6. actual_intent 정책 구현 요약
7. Markdown 출력 변경 요약
8. JSON 보존 정책 확인
9. CLI smoke test hardening 내용
10. 테스트 결과
11. Notion API 호출 여부
12. Notion write/export/sync 실행 여부
13. outputs/paper 원장 변경 여부
14. 자체 점검 결과
15. git diff --check 결과
16. PAPER18-3 커밋 생성 여부
17. PAPER18-3 커밋 SHA / 메시지
18. 제외한 unrelated 파일
19. 남은 리스크
20. PAPER18-4 추천 작업

END MFU-PAPER18-3-INFO-SUPPRESSION-AND-CLI-SMOKE-HARDENING
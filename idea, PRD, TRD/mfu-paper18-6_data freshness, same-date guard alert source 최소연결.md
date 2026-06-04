BEGIN MFU-PAPER18-6-FRESHNESS-AND-SAME-DATE-GUARD-ALERT-SOURCES

# PAPER18-6 Data Freshness / Same-date Guard Alert Source 최소 연결

## 목적

PAPER18-6에서는 Alert Report generator에 data freshness와 same-date guard 계열의 최소 alert source를 연결한다.

이번 작업의 목표는 다음이다.

1. data freshness stale / fail 신호를 AlertItem으로 변환한다.
2. same-date commit guard blocked / fail 신호를 AlertItem으로 변환한다.
3. source path 후보를 과하게 확정하지 않고, 명시 JSON 입력과 --source-root 후보 탐색을 지원한다.
4. 기존 Daily Ops Status, PAPER17 preflight, Manual Execution/Review alert 정책을 깨지 않는다.
5. PAPER18 closeout 가능 여부를 판단할 수 있게 남은 한계를 문서화한다.

이번 작업은 read-only alert source 확장이다.  
Notion API 호출, Notion write/export/sync, commit/append/status sync 실행, outputs/paper 원장 수정은 하지 않는다.

## 배경

PAPER18 진행 상태:

- PAPER18-1: Alert / Monitoring 설계 완료
- PAPER18-2: Alert Report generator 최소 구현 완료
- PAPER18-3: INFO suppression / CLI smoke hardening 완료
- PAPER18-4: Daily Ops Status + PAPER17 preflight 실제 source 연결 완료
- PAPER18-5: Manual Execution / Manual Review high-level signal 연결 완료

PAPER18-5 이후 남은 주요 alert source 후보는 다음이다.

- data freshness
- same-date guard
- schema/view drift
- replay/diff

이번 PAPER18-6에서는 data freshness와 same-date guard만 최소 연결한다.  
schema/view drift와 replay/diff는 후속 로드맵으로 남긴다.

## 대상 파일

수정/생성 후보:

```text
core/paper_alert_report.py
scripts/dev/generate_paper_alert_report.py
tests/test_paper_alert_report.py
docs/TRD/mfu_paper18_freshness_and_same_date_guard_alert_sources.md
```

필요하면 source resolver 관련 기존 파일을 최소 수정한다.

## 구현 범위

### 1. CLI 입력 옵션

기존 옵션은 유지한다.

필요 시 아래 명시 입력 옵션을 추가한다.

```text
--freshness-json
--same-date-guard-json
```

명시 JSON 입력은 `--source-root` 후보 탐색보다 우선한다.

`--source-root` 후보 파일명은 repo convention을 확인한 뒤 최소로 둔다.  
확정 producer가 불명확하면 문서에 candidate로 기록한다.

후보 예시:

```text
data_freshness_{YYYYMMDD}.json
freshness_{YYYYMMDD}.json
market_data_freshness_{YYYYMMDD}.json
same_date_guard_{YYYYMMDD}.json
same_date_commit_guard_{YYYYMMDD}.json
commit_guard_{YYYYMMDD}.json
```

### 2. Data freshness mapping

payload 필드명은 실제/fixture 구조에 맞추되, 아래 신호를 지원한다.

권장 필드 후보:

```text
freshness_status
data_freshness_status
market_data_status
stale_symbols_count
stale_source_count
max_stale_days
```

mapping 정책:

```text
freshness_status = FAIL / FAILED
→ BLOCKING

freshness_status = STALE
→ BLOCKING 또는 NEEDS_REVIEW
초기 기본값은 BLOCKING. 단, payload가 warning 성격이면 NEEDS_REVIEW.

freshness_status = WARNING
→ NEEDS_REVIEW

stale_symbols_count > 0
→ NEEDS_REVIEW 또는 BLOCKING
초기 기본값은 NEEDS_REVIEW.

max_stale_days가 명시 threshold를 넘음
→ BLOCKING

account mismatch
→ BLOCKING

malformed freshness JSON
→ BLOCKING

freshness source missing at closeout
→ suppressed INFO
```

주의:

- freshness source producer contract가 아직 약하면 missing을 BLOCKING으로 올리지 않는다.
- 명확한 stale/fail payload가 있을 때만 강한 alert로 승격한다.
- 정상 fresh 상태를 AlertItem으로 과도하게 나열하지 않는다.

### 3. Same-date guard mapping

payload 필드명은 실제/fixture 구조에 맞추되, 아래 신호를 지원한다.

권장 필드 후보:

```text
same_date_guard_status
commit_guard_status
blocked
block_reason
existing_commit_count
same_date_commit_exists
```

mapping 정책:

```text
same_date_guard_status = BLOCKED / FAIL / FAILED
→ BLOCKING

blocked = true
→ BLOCKING

same_date_commit_exists = true
→ NEEDS_REVIEW 또는 BLOCKING
초기 기본값은 NEEDS_REVIEW. 명시 block_reason이 있으면 BLOCKING.

commit_guard_status = WARNING
→ NEEDS_REVIEW

account/date mismatch
→ BLOCKING

malformed same-date guard JSON
→ BLOCKING

same-date guard source missing at closeout
→ suppressed INFO
```

주의:

- same-date guard는 source-of-truth 보호와 관련되므로 blocked/fail은 강하게 본다.
- 단순 source missing은 producer contract가 약하면 BLOCKING으로 올리지 않는다.

### 4. 중복 / suppression 정책

기존 정책 유지:

- JSON에는 INFO 보존
- Markdown은 BLOCKING / NEEDS_REVIEW / SYNC_FAILED 중심
- INFO는 count/reason 중심
- 정상 상태 전체 나열 금지

같은 원인으로 Daily Ops Status와 신규 source가 중복 alert를 만들면 하나로 합치거나 더 구체적인 source만 남긴다.

### 5. 문서 작성

생성 문서:

```text
docs/TRD/mfu_paper18_freshness_and_same_date_guard_alert_sources.md
```

포함 섹션:

1. Purpose
2. Scope
3. Source Path Candidates
4. Data Freshness Mapping
5. Same-date Guard Mapping
6. Missing / Malformed Source Policy
7. CLI Changes
8. Duplicate Alert Avoidance
9. Read-only Safety Policy
10. Test Coverage
11. Limitations
12. PAPER18 Closeout Recommendation

반드시 명시:

- producer contract가 불명확한 source는 candidate로 둔다.
- missing source는 초기에는 suppressed INFO 중심으로 둔다.
- malformed JSON은 BLOCKING이다.
- Notion/API/write/export/sync 없음.
- 외부 전송 없음.
- outputs/paper 원장 변경 없음.
- schema/view drift와 replay/diff는 후속이다.

## 테스트 요구사항

`tests/test_paper_alert_report.py`를 보강한다.

필수 테스트:

```text
Data freshness FAIL → BLOCKING
Data freshness STALE → BLOCKING 또는 NEEDS_REVIEW
Data freshness stale count > 0 → NEEDS_REVIEW
Malformed freshness JSON → BLOCKING
Missing freshness source at closeout → suppressed INFO

Same-date guard BLOCKED/FAIL → BLOCKING
blocked=true → BLOCKING
same_date_commit_exists=true → NEEDS_REVIEW 또는 BLOCKING
Malformed same-date guard JSON → BLOCKING
Missing same-date guard source at closeout → suppressed INFO

명시 JSON 입력이 --source-root 후보보다 우선
INFO suppression 정책 유지
Markdown이 Dashboard처럼 정상 상태를 나열하지 않음
Notion API 호출 없음
외부 delivery 없음
tmp_path 사용으로 실제 outputs 오염 없음
```

## 검증 명령

Windows CMD 기준:

```cmd
git status --short

python scripts\dev\generate_paper_alert_report.py --help

pytest tests\test_paper_alert_report.py

type docs\TRD\mfu_paper18_freshness_and_same_date_guard_alert_sources.md

findstr /N /I "freshness stale same-date guard blocked malformed missing suppressed read-only Notion delivery closeout" docs\TRD\mfu_paper18_freshness_and_same_date_guard_alert_sources.md

git diff --check -- core\paper_alert_report.py scripts\dev\generate_paper_alert_report.py tests\test_paper_alert_report.py docs\TRD\mfu_paper18_freshness_and_same_date_guard_alert_sources.md
```

## 구현 후 자체 점검 항목

Codex는 구현 후 아래를 확인하고 결과 보고에 포함한다.

### Source mapping 점검

- freshness FAIL/STALE/WARNING이 의도대로 분류되는가
- same-date guard BLOCKED/FAIL이 BLOCKING으로 분류되는가
- same_date_commit_exists 같은 애매한 신호를 과도하게 BLOCKING으로 올리지 않았는가
- malformed JSON은 alert로 안전하게 전환되는가
- missing source는 producer contract가 약한 상태에서 과도하게 BLOCKING 처리되지 않는가

### 기존 정책 회귀 점검

- Daily Ops Status / preflight / Manual Execution / Manual Review 기존 테스트가 유지되는가
- INFO suppression 정책이 유지되는가
- Markdown이 정상 상태판처럼 변질되지 않는가
- JSON에는 INFO item이 보존되는가

### Safety 점검

- Notion API 호출이 없는가
- Notion write/export/sync 호출이 없는가
- Telegram/Slack/Email 전송이 없는가
- commit/append/status sync 실행이 없는가
- outputs/paper 원장 변경이 없는가
- 테스트가 실제 outputs/paper_accounts를 오염시키지 않는가

### Git 점검

- unrelated 파일이 staged 되지 않았는가
- `.env`, `config/notion_settings.json`, outputs/backtest_log.db 등이 staged 되지 않았는가
- `git diff --check`가 통과했는가

blocker가 있으면 커밋하지 말고 보고한다.  
blocker가 없고 테스트가 통과하면 PAPER18-6 결과를 커밋한다.

## Non-scope

이번 작업에서는 절대 하지 않는다.

```text
Notion API 호출
Notion write/export/sync
Daily Ops Status actual export
Telegram/Slack/Email 전송
outputs/paper 원장 수정
commit/append/status sync 실행
schema/view drift 구현
replay/diff 구현
row-level Manual Execution/Review 분석
freshness producer 구현
same-date guard producer 구현
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

자체 점검에서 blocker가 없고 테스트가 통과하면 실제 수정/생성 파일만 개별 stage한다.

예상 후보:

```cmd
git add core\paper_alert_report.py
git add scripts\dev\generate_paper_alert_report.py
git add tests\test_paper_alert_report.py
git add docs\TRD\mfu_paper18_freshness_and_same_date_guard_alert_sources.md
```

커밋 메시지:

```cmd
git commit -m "feat: add PAPER18 freshness and same-date guard alerts"
```

커밋 후 확인:

```cmd
git log -1 --stat
git status --short
```

## 성공 기준

- Data freshness source가 AlertItem으로 변환됨
- Same-date guard source가 AlertItem으로 변환됨
- stale/fail/blocked/malformed 정책이 구현됨
- missing source는 과도하게 BLOCKING 처리되지 않음
- INFO suppression 정책 유지
- 기존 Daily Ops / Preflight / Manual signal 정책 유지
- 테스트 통과
- Notion API/write/export/sync 없음
- 외부 전송 없음
- outputs/paper 원장 변경 없음
- blocker 없으면 커밋 완료
- PAPER18 closeout 가능 여부가 보고됨

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 생성/수정한 파일
3. Data freshness source mapping 요약
4. Same-date guard source mapping 요약
5. missing/malformed source 정책
6. CLI 변경 여부
7. INFO suppression 유지 여부
8. 기존 alert source 회귀 여부
9. 테스트 결과
10. Notion API 호출 여부
11. Notion write/export/sync 실행 여부
12. 외부 전송 실행 여부
13. outputs/paper 원장 변경 여부
14. 자체 점검 결과
15. git diff --check 결과
16. 커밋 생성 여부
17. 커밋 SHA / 메시지
18. 제외한 unrelated 파일
19. 남은 리스크
20. PAPER18 closeout 가능 여부
21. 다음 추천 작업

END MFU-PAPER18-6-FRESHNESS-AND-SAME-DATE-GUARD-ALERT-SOURCES
BEGIN MFU-PAPER18-5-SOURCE-PATH-ALIGNMENT-AND-MANUAL-SIGNAL

# PAPER18-5 Alert Source Path Alignment + Manual Execution/Review High-level Signal

## 목적

PAPER18-5에서는 Alert Report generator의 실제 운영 source 연결을 한 단계 확장한다.

이번 작업의 핵심은 두 가지다.

1. Alert generator가 기대하는 source path와 실제 운영 artifact 후보를 최소 표로 정리한다.
2. Manual Execution / Manual Review의 “상위 상태 신호”를 Alert source로 연결한다.

이번 작업은 read-only alert source 확장이다.  
Notion API 호출, Notion write/export/sync, commit/append/status sync 실행, outputs/paper 원장 수정은 하지 않는다.

## 배경

PAPER18-4에서 완료된 것:

- `--source-root` 기반 source resolver 추가
- Daily Ops Status source 연결
- PAPER17 preflight source 연결
- missing/malformed source 정책 구현
- INFO suppression 유지
- 테스트 21 passed
- Notion API/write/export/sync 없음
- 커밋: 2794cc30a88aec49b93d0942aba1f79e45cfe017

PAPER18-4의 남은 리스크:

- `--source-root` resolver는 의도적으로 좁음
- 실제 운영 artifact 생성 위치와 Alert source 기대 경로가 아직 약함
- Manual Execution / Manual Review source가 아직 미연결

## 대상 파일

수정/생성 후보:

```text
core/paper_alert_report.py
scripts/dev/generate_paper_alert_report.py
tests/test_paper_alert_report.py
docs/TRD/mfu_paper18_source_path_alignment_and_manual_signal.md
```

필요하면 기존 구조에 맞춰 source resolver 파일을 추가해도 된다.

```text
core/paper_alert_sources.py
```

## 작업 범위

### 1. Source Path Alignment 최소 정리

repo의 기존 docs/code/tests를 확인해 다음 source 후보를 표로 정리한다.

필수 확인 대상:

```text
Daily Ops Status source
PAPER17 actual preflight source
Manual Execution preview/commit/status sync source
Manual Review preview/append/status sync source
```

문서에는 아래 형식의 표를 넣는다.

```text
Source | Current/Expected Filename | Producer Command | Alert Use | Status
```

중요:

- 경로 계약을 과하게 새로 만들지 않는다.
- 실제 producer가 불명확하면 “candidate / needs upstream contract”로 둔다.
- 명시 JSON 입력은 계속 공식 fallback으로 유지한다.
- `--source-root` 자동 탐색은 좁게 유지한다.

### 2. Manual Execution high-level signal 연결

세부 row-level 분석은 하지 않는다.  
상위 상태만 AlertItem으로 변환한다.

필드명은 실제 payload 또는 fixture에 맞춰 안전하게 처리한다.

후보 mapping:

```text
execution_preview_result = FAIL/FAILED
→ BLOCKING

execution_preview_result = WARNING
→ NEEDS_REVIEW

execution_commit_status = MISSING/NOT_COMMITTED at closeout
→ NEEDS_REVIEW

execution_sync_status = FAILED/SYNC_FAILED
→ SYNC_FAILED

execution_pending_row_count > 0
→ NEEDS_REVIEW

execution_source missing at closeout
→ INFO 또는 NEEDS_REVIEW
```

초기 정책:

- 명확한 FAIL은 BLOCKING
- sync 실패는 SYNC_FAILED
- 미입력/미완료/대기 상태는 NEEDS_REVIEW
- source missing은 아직 producer contract가 약하면 과격하게 BLOCKING 처리하지 않는다

### 3. Manual Review high-level signal 연결

후보 mapping:

```text
review_validation_result = FAIL/FAILED
→ BLOCKING

review_append_status = MISSING/NOT_APPENDED at closeout
→ NEEDS_REVIEW

review_sync_status = FAILED/SYNC_FAILED
→ SYNC_FAILED

review_pending_row_count > 0
→ NEEDS_REVIEW

review_progress_status = PARTIAL/NOT_STARTED/READY/UNKNOWN
→ NEEDS_REVIEW

review_source missing at closeout
→ INFO 또는 NEEDS_REVIEW
```

주의:

- PAPER18-4에서 이미 Daily Ops Status의 review_progress_status 일부를 처리했다면 중복 AlertItem을 만들지 않는다.
- 같은 의미의 alert가 중복되면 하나로 합치거나 evidence에 source를 추가한다.

### 4. CLI 정책

기존 CLI 옵션을 유지한다.

```text
--account-id
--date
--phase closeout
--actual-intent
--daily-ops-status-json
--preflight-json
--source-root
--output-dir
--json
```

필요 시 명시 입력 옵션을 추가한다.

```text
--manual-execution-json
--manual-review-json
```

명시 JSON 입력은 `--source-root`보다 우선한다.

### 5. Missing / malformed 정책

```text
malformed manual execution/review JSON
→ BLOCKING 또는 NEEDS_REVIEW

manual execution/review source missing at closeout
→ 초기에는 INFO 또는 NEEDS_REVIEW
→ producer contract가 확정되지 않았으면 BLOCKING 금지

actual_intent=true와 직접 관련 있는 preflight 문제
→ 기존 정책 유지
```

## 테스트 요구사항

`tests/test_paper_alert_report.py`를 보강한다.

필수 테스트:

```text
Manual Execution preview FAIL → BLOCKING
Manual Execution sync failed → SYNC_FAILED
Manual Execution pending rows → NEEDS_REVIEW
Manual Review validation FAIL → BLOCKING
Manual Review sync failed → SYNC_FAILED
Manual Review pending rows → NEEDS_REVIEW
Daily Ops Status review signal과 Manual Review signal 중복 방지
malformed manual source → alert 생성
명시 JSON 입력이 --source-root보다 우선
INFO suppression 정책 유지
Notion API 호출 없음
외부 delivery 없음
tmp_path 사용으로 실제 outputs 오염 없음
```

## 문서 작성

생성 문서:

```text
docs/TRD/mfu_paper18_source_path_alignment_and_manual_signal.md
```

포함 섹션:

1. Purpose
2. Scope
3. Source Path Alignment Table
4. Manual Execution High-level Signal Mapping
5. Manual Review High-level Signal Mapping
6. Missing / Malformed Source Policy
7. CLI Changes
8. Duplicate Alert Avoidance
9. Read-only Safety Policy
10. Test Coverage
11. Limitations
12. PAPER18-6 Recommendation

## 검증 명령

Windows CMD 기준:

```cmd
git status --short

python scripts\dev\generate_paper_alert_report.py --help

pytest tests\test_paper_alert_report.py

type docs\TRD\mfu_paper18_source_path_alignment_and_manual_signal.md

findstr /N /I "Manual Execution Manual Review source path sync failed pending malformed read-only duplicate alert" docs\TRD\mfu_paper18_source_path_alignment_and_manual_signal.md

git diff --check -- core\paper_alert_report.py scripts\dev\generate_paper_alert_report.py tests\test_paper_alert_report.py docs\TRD\mfu_paper18_source_path_alignment_and_manual_signal.md
```

새 파일을 추가했다면 diff check 대상에 포함한다.

## 구현 후 자체 점검 항목

Codex는 구현 후 아래를 확인하고 결과 보고에 포함한다.

### Source path 점검

- Daily Ops Status / preflight source 기대 경로가 문서화됐는가
- Manual Execution / Manual Review source 후보가 문서화됐는가
- producer가 불명확한 source를 확정된 것처럼 쓰지 않았는가
- 명시 JSON 입력이 `--source-root`보다 우선하는가

### Manual signal 점검

- Manual Execution FAIL/WARNING/pending/sync_failed가 적절히 분류되는가
- Manual Review FAIL/pending/sync_failed가 적절히 분류되는가
- Daily Ops Status와 Manual Review에서 같은 의미의 alert가 중복 생성되지 않는가
- source missing을 과도하게 BLOCKING으로 올리지 않았는가

### Dashboard 중복 방지 점검

- 정상 상태 전체를 AlertItem으로 나열하지 않는가
- Markdown INFO suppression 정책이 유지되는가
- Alert Report가 예외/위험 중심으로 유지되는가

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
blocker가 없고 테스트가 통과하면 PAPER18-5 결과를 커밋한다.

## Non-scope

이번 작업에서는 절대 하지 않는다.

```text
Notion API 호출
Notion write/export/sync
Daily Ops Status actual export
Telegram/Slack/Email 전송
outputs/paper 원장 수정
commit/append/status sync 실행
Manual Execution/Review row-level 상세 분석
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

자체 점검에서 blocker가 없고 테스트가 통과하면 실제 수정/생성 파일만 개별 stage한다.

예상 후보:

```cmd
git add core\paper_alert_report.py
git add scripts\dev\generate_paper_alert_report.py
git add tests\test_paper_alert_report.py
git add docs\TRD\mfu_paper18_source_path_alignment_and_manual_signal.md
```

새 파일이 있으면 개별 추가한다.

```cmd
git add core\paper_alert_sources.py
```

커밋 메시지:

```cmd
git commit -m "feat: add PAPER18 manual ops alert signals"
```

커밋 후 확인:

```cmd
git log -1 --stat
git status --short
```

## 성공 기준

- Source path alignment가 최소 표로 문서화됨
- Manual Execution high-level signal이 AlertItem으로 변환됨
- Manual Review high-level signal이 AlertItem으로 변환됨
- sync failure는 SYNC_FAILED로 분류됨
- pending/incomplete는 NEEDS_REVIEW로 분류됨
- validation/preview FAIL은 BLOCKING으로 분류됨
- 중복 alert가 과도하게 생성되지 않음
- INFO suppression 정책 유지
- 테스트 통과
- Notion API/write/export/sync 없음
- 외부 전송 없음
- outputs/paper 원장 변경 없음
- blocker 없으면 커밋 완료

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 생성/수정한 파일
3. Source path alignment 요약
4. Manual Execution signal mapping 요약
5. Manual Review signal mapping 요약
6. missing/malformed source 정책
7. CLI 변경 여부
8. 중복 alert 방지 방식
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
21. PAPER18-6 추천 작업

END MFU-PAPER18-5-SOURCE-PATH-ALIGNMENT-AND-MANUAL-SIGNAL
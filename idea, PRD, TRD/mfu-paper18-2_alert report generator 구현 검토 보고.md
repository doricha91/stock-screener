BEGIN MFU-PAPER18-2-IMPLEMENTATION-REVIEW-REPORT

# PAPER18-2 Alert Report Generator 구현 검토 보고

## 목적

PAPER18-2 Alert Report generator 최소 구현이 PAPER18-1 설계 의도대로 동작하는지 검토하고 보고한다.

이번 작업은 검토 전용이다.  
코드 수정, 문서 수정, 커밋, git add, Notion API 호출, Notion write/export/sync, outputs/paper 원장 수정은 하지 않는다.

## 검토 대상 파일

아래 파일을 읽고 검토한다.

```cmd
type core\paper_alert_report.py
type scripts\dev\generate_paper_alert_report.py
type tests\test_paper_alert_report.py
type docs\TRD\mfu_paper18_alert_report_generator_minimal.md
```

## 검토 항목

### 1. AlertItem schema 확인

확인할 것:

- `schema_version = paper_alert_report.v1`이 유지되는가
- AlertItem에 최소 필드가 포함되는가
  - severity
  - category
  - account_id
  - status_date
  - title
  - message
  - recommended_action
  - evidence
  - source
  - source_path
  - external_safe
  - sendable
  - redacted
- Report envelope에 summary count와 items가 포함되는가
- delivery 관련 필드가 있더라도 실제 전송 기능과 섞이지 않는가

### 2. severity / actual_intent 정책 확인

확인할 것:

- preflight overall_status=FAIL → BLOCKING
- schema_validation_result=FAIL → BLOCKING
- duplicate_audit.classification=duplicate_blocker → BLOCKING
- account mismatch → BLOCKING
- actual_intent=true + preflight WARNING → NEEDS_REVIEW
- expected_page_id missing + actual_intent=true → NEEDS_REVIEW
- expected_page_id missing + actual_intent=false → INFO 또는 suppressed
- update_candidate + actual_intent=false → INFO
- Daily Ops Status sync failure → SYNC_FAILED
- 정상 상태 전체를 Alert Report에 과도하게 나열하지 않는가

### 3. INFO 표시 / suppression 확인

확인할 것:

- INFO 항목이 Markdown 본문에 과도하게 확장 표시되지 않는가
- INFO가 Dashboard 중복 상태판처럼 변질되지 않는가
- INFO가 표시된다면 Summary 또는 Info 섹션에 제한적으로 들어가는가
- suppressed 개념이 있으면 summary count 또는 별도 요약으로 안전하게 표현되는가
- PAPER18-3에서 추가 결정이 필요한 부분이 있으면 명확히 보고한다

### 4. Redaction 적용 범위 확인

확인할 것:

- message
- title
- recommended_action
- evidence
- source_path
- Markdown output
- JSON output

위 항목에 민감정보 마스킹이 적용되는가.

반드시 마스킹되어야 하는 값:

- Notion token
- secret-like string
- Notion data source id
- full Notion page_id
- absolute local path
- env/secret 값

기대 형태:

```text
page_id / data_source_id -> ****last4
absolute path -> <redacted_path> 또는 repo-relative path
```

### 5. output path / output-dir 확인

확인할 것:

- 기본 경로가 계좌별로 저장되는가

```text
outputs/paper_accounts/{account_id}/alerts/paper_alert_report_{YYYYMMDD}.json
outputs/paper_accounts/{account_id}/alerts/paper_alert_report_{YYYYMMDD}.md
```

- `--output-dir` 사용 시 실제 outputs를 오염시키지 않고 지정 경로에 생성되는가
- 테스트에서 `tmp_path`를 사용해 실제 outputs를 건드리지 않는가
- paper_default legacy path를 임의로 확장하거나 actual 정책과 섞지 않는가

### 6. Delivery boundary 확인

확인할 것:

- Telegram / Slack / Email 전송 코드가 없는가
- delivery adapter가 실행되지 않는가
- sendable/external_safe 필드는 있어도 실제 외부 전송은 하지 않는가
- delivery failure를 source-of-truth failure로 취급하지 않는 설계인가

### 7. read-only safety 확인

확인할 것:

- Notion API를 호출하지 않는가
- Notion write/export/sync를 실행하지 않는가
- commit/append/status sync를 실행하지 않는가
- outputs/paper 원장을 수정하지 않는가
- CLI smoke가 fixture/input JSON만 읽고 JSON/Markdown report만 쓰는가

검색 명령 예시:

```cmd
findstr /S /N /I "NotionClient create_page update_page upsert export sync Telegram Slack Email requests post commit append" core\paper_alert_report.py scripts\dev\generate_paper_alert_report.py tests\test_paper_alert_report.py
```

### 8. 테스트 확인

아래를 실행한다.

```cmd
pytest tests\test_paper_alert_report.py
```

테스트가 최소 아래를 포함하는지 확인한다.

- preflight FAIL → BLOCKING
- duplicate_blocker → BLOCKING
- actual_intent=true + WARNING → NEEDS_REVIEW
- actual_intent=false + expected_page_id warning → INFO 또는 suppressed
- update_candidate → INFO
- summary count 계산
- JSON schema_version 포함
- Markdown 생성
- 계좌별 output path 생성
- 민감정보 마스킹
- delivery 실행 없음
- Notion API 호출 없음

### 9. CLI smoke 확인

가능하면 fixture 또는 임시 JSON 파일로 CLI smoke를 실행한다.

조건:

- `--output-dir`은 임시 디렉터리 사용
- 실제 outputs 계좌 경로 오염 금지
- Notion API 호출 금지

예시:

```cmd
python scripts\dev\generate_paper_alert_report.py --help
```

이미 테스트에서 충분히 CLI smoke를 수행했다면 그 사실을 보고한다.

### 10. diff check

아래 명령을 실행한다.

```cmd
git diff --check -- core\paper_alert_report.py scripts\dev\generate_paper_alert_report.py tests\test_paper_alert_report.py docs\TRD\mfu_paper18_alert_report_generator_minimal.md
```

## Non-scope

이번 작업에서는 절대 하지 않는다.

- 코드 수정
- 문서 수정
- 커밋
- git add
- Notion API 호출
- Notion write/export/sync
- Telegram/Slack/Email 전송
- outputs/paper 원장 수정
- 실제 outputs 계좌 경로에 smoke 산출물 생성
- schema/view drift 구현
- Manual Execution/Review source 연결
- Replay/Diff 구현

## 성공 기준

보고서만으로 아래를 판단할 수 있어야 한다.

- AlertItem schema가 설계와 맞는지
- severity / actual_intent 정책이 정확한지
- INFO가 Dashboard 중복처럼 과다 노출되지 않는지
- redaction이 충분한지
- output path와 `--output-dir` 정책이 안전한지
- delivery 기능이 실행되지 않는지
- Notion API / write / sync 호출이 없는지
- 테스트가 통과하는지
- PAPER18-2를 커밋해도 되는지
- 커밋 전 blocker가 있는지

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 검토한 파일
3. AlertItem schema 확인 결과
4. severity / actual_intent 정책 확인 결과
5. INFO 표시 / suppression 확인 결과
6. redaction 적용 범위 확인 결과
7. output path / output-dir 확인 결과
8. delivery boundary 확인 결과
9. read-only safety 확인 결과
10. 테스트 실행 결과
11. CLI smoke 확인 결과
12. git diff --check 결과
13. 발견한 blocker
14. 발견한 non-blocking 개선점
15. PAPER18-2 커밋 가능 여부
16. 커밋 후보 파일

END MFU-PAPER18-2-IMPLEMENTATION-REVIEW-REPORT
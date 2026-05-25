# MFU-PAPER14-6: Daily Review Summary Notion Export

## 목적

이번 PAPER14-6은 Daily Review Summary Notion read-only export 작업이며, Manual Execution import/commit, Notion status back-write, broker/API 연동은 수행하지 않는다.

이 문서는 Manual Execution commit 이후 하루 운영 결과를 요약한 `Daily Review Summary`를 Notion에 표시/검토용으로 export하기 위한 source artifact, schema contract, export 정책을 정리한다.

핵심 원칙:

- CSV / JSON / Markdown / SQLite = source of truth
- Notion = presentation / review layer

## 역할 정의

- `Daily Plan`
  - 오늘 실행할 계획
- `Manual Executions`
  - 실제 체결 입력
- `Daily Review Summary`
  - 하루 운영 결과 요약

즉 `Daily Review Summary`는 입력 원천이 아니라, 이미 확정된 ledger / snapshot / commit report를 사람이 빠르게 검토하기 위한 read-only 결과 계층이다.

## Source Artifact

우선순위:

1. `outputs/paper_test/reports/manual_execution_import_commit_YYYYMMDD.json`
2. `outputs/paper_test/reports/manual_execution_import_preview_YYYYMMDD.json`
3. `outputs/paper_test/paper_execution_log.csv`
   - `date = review_date`
   - `source = notion_manual_execution`
4. `outputs/paper_test/paper_account_snapshot.csv`
5. `outputs/paper_test/paper_position_snapshot.csv`
6. `outputs/paper_test/paper_current_state_YYYYMMDD.json` 존재 시 참고

정책:

- exporter는 Notion `Manual Executions` row를 다시 읽지 않는다.
- commit report가 있으면 그것을 1차 source로 사용한다.
- commit report가 없으면 execution log와 snapshot으로 fallback summary를 만든다.
- commit report가 없다고 export 자체를 실패시키지는 않는다.

## Data Source Key

- `daily_review_summaries`

환경변수 override:

- `NOTION_DAILY_REVIEW_SUMMARIES_DATA_SOURCE_ID`

config fallback:

- `data_sources.daily_review_summaries`

## Schema Contract

`Daily Review Summaries` DB는 아래 3그룹 속성으로 나눈다.

1. 핵심 요약 필드
2. 원천 파일 / 추적 필드
3. 동기화 관리 필드

### 1. 핵심 요약 필드

- `Name`
- `External Key`
- `Review Date`
- `Review Status`
- `Availability Status`
- `Committed Trade Count`
- `Warning Count`
- `Fail Count`
- `Cash Start`
- `Cash End`
- `Cash Impact`
- `Position Impact Summary`

권장 타입:

- `Name`: `Title`
- `External Key`: `Rich text`
- `Review Date`: `Date`
- `Review Status`: `Select`
- `Availability Status`: `Select`
- `Committed Trade Count`: `Number`
- `Warning Count`: `Number`
- `Fail Count`: `Number`
- `Cash Start`: `Number`
- `Cash End`: `Number`
- `Cash Impact`: `Number`
- `Position Impact Summary`: `Rich text`

속성 설명:

- `Name`
  - 목록에서 리뷰 row를 바로 식별하는 제목
  - 예: `Daily Review Summary 2026-05-25`
- `External Key`
  - 동일 날짜 export 재실행 시 upsert 기준이 되는 키
- `Review Date`
  - 리뷰 대상 날짜
- `Review Status`
  - 하루 운영 결과의 최종 요약 상태
- `Availability Status`
  - source artifact를 얼마나 확보했는지 나타내는 상태
- `Committed Trade Count`
  - commit된 manual execution 건수
- `Warning Count`
  - warning 요약 개수
- `Fail Count`
  - preview 기준 fail 개수
- `Cash Start`
  - manual execution 반영 전 기준 현금
- `Cash End`
  - manual execution 반영 후 기준 현금
- `Cash Impact`
  - `Cash End - Cash Start`
- `Position Impact Summary`
  - 종목별 수량 변화 요약

### 2. 원천 파일 / 추적 필드

- `Commit Report Path`
- `Preview Report Path`
- `Latest Snapshot Date`
- `Schema Version`

권장 타입:

- `Commit Report Path`: `Rich text`
- `Preview Report Path`: `Rich text`
- `Latest Snapshot Date`: `Date`
- `Schema Version`: `Rich text`

속성 설명:

- `Commit Report Path`
  - 1차 source artifact 경로
- `Preview Report Path`
  - preview source artifact 경로
- `Latest Snapshot Date`
  - review 계산에 사용한 최신 snapshot 날짜
- `Schema Version`
  - exporter payload schema 버전

### 3. 동기화 관리 필드

- `Synced At`
- `Sync Status`

권장 타입:

- `Synced At`: `Rich text`
- `Sync Status`: `Select`

속성 설명:

- `Synced At`
  - exporter 실행 시각 텍스트
- `Sync Status`
  - Notion sync 결과 상태

## Select Option Contract

### Review Status

권장 option:

- `PASS`
- `PASS_WITH_WARNINGS`
- `FAIL`
- `NO_ACTIVITY`

의미:

- `PASS`
  - commit 결과와 요약 계산이 정상이고 추가 warning이 없음
- `PASS_WITH_WARNINGS`
  - 결과는 유효하지만 warning이 존재
- `FAIL`
  - preview fail count가 있거나 요약 계산이 실패 상태
- `NO_ACTIVITY`
  - 해당 날짜 manual execution activity가 없음

### Availability Status

권장 option:

- `AVAILABLE`
- `NO_COMMIT_REPORT`
- `NO_MANUAL_EXECUTIONS`
- `PARTIAL`
- `UNKNOWN`

의미:

- `AVAILABLE`
  - commit report 기준으로 정상 요약 가능
- `NO_COMMIT_REPORT`
  - commit report는 없지만 ledger fallback으로 요약 가능
- `NO_MANUAL_EXECUTIONS`
  - 해당 날짜 manual execution activity 자체가 없음
- `PARTIAL`
  - 일부 source만 존재해 제한적으로 요약 가능
- `UNKNOWN`
  - 상태를 명확히 판정하기 어려움

### Sync Status

권장 option:

- `SYNCED`

## External Key 정책

형식:

- `daily_review_summary:{review_date}`

예:

- `daily_review_summary:2026-05-25`

정책:

- 동일 날짜 export 재실행 시 새 row를 만들지 않고 update한다.
- 동일 날짜 row가 2개 이상이면 error로 간주한다.

## 계산 규칙

### committed trade count

- commit report가 있으면 `committed_rows` 길이를 사용한다.
- commit report가 없으면 execution log fallback row 수를 사용한다.

### warning count

- commit report의 `validation_issues` 중 `severity = WARNING` 개수를 사용한다.
- fallback 경로에서는 `commit report missing` warning 1건을 부여할 수 있다.

### fail count

- preview report의 `fail_count`를 사용한다.
- preview report가 없으면 기본 `0`

### cash_start / cash_end / cash_impact

- `cash_end`
  - account snapshot latest row의 `cash`
- `cash_start`
  - preview report의 `projected_cash_start` 우선 사용
  - 없으면 commit report가 가리키는 preview report 참조
  - 그것도 없으면 committed trade gross cash delta를 역산
- `cash_impact`
  - `cash_end - cash_start`

### position impact summary

- committed trade item을 종목별 순증감 수량으로 합산
- 예:
  - `AAPL:+1`
  - `GEN:-3`

## Page Body 구성

page body는 간결한 block 조합으로 작성한다.

구성:

- `오늘의 리뷰 요약`
- `체결 요약`
- `포지션 변화`
- `경고 / 특이사항`
- `원천 파일`

정책:

- Notion table block은 필수 아님
- bullet / plain text block 우선
- source of truth 상세를 Notion 본문에 모두 복제하지 않음

## Dry-run / Actual Export 정책

- `--dry-run`
  - payload 생성만 수행
  - Notion write 금지
- non-dry-run
  - 사용자의 명시적 허용 시에만 수행
- `--all`
  - 이번 MFU에서는 자동 포함하지 않아도 됨

## Manual Executions와의 관계

- `Manual Executions`
  - 입력 / staging 계층
- `Daily Review Summary`
  - 결과 요약 / 검토 계층

중요:

- Daily Review Summary export는 `Manual Executions` row를 수정하지 않는다.
- paper ledger를 수정하지 않는다.
- broker/API를 호출하지 않는다.

## 제외 범위

- Manual Execution import
- Manual Execution commit
- Notion Manual Executions status back-write
- Daily Plan source 수정
- broker/API 연동
- Notion DB 자동 생성

## 테스트 요약

검증 범위:

- commit report primary path
- no-commit-report fallback
- no-activity path
- property payload type
- External Key
- dry-run path
- schema validator의 `daily_review_summaries` contract

## 남은 리스크

- commit report가 없으면 warning detail은 fallback 수준으로 제한된다.
- `paper_current_state_YYYYMMDD.json`이 특정 날짜에 없을 수 있으며, 그 경우 path는 빈 값으로 둘 수 있다.
- page body는 intentionally compact 정책이므로 richer diagnostics가 필요하면 후속 MFU에서 확장하는 것이 적절하다.

## Closeout Verification

이번 PAPER14-6-closeout_revision은 Daily Review Summary Notion export의 actual export 검증 증적을 보완 문서화하는 작업이며, 코드 수정, Notion export 재실행, paper ledger 수정, Manual Execution import/commit/status sync는 수행하지 않았다.

### 1. Actual export 검증 결과

사용자 확인 기준으로 아래 항목이 완료된 것으로 기록한다.

- Daily Review Summaries data source id 설정 완료
- schema validation 수행 완료
- actual export 1차 결과: `created` 확인
- actual export 2차 결과: `updated` 확인
- External Key 기반 upsert 정상 확인

External Key 정책:

- `daily_review_summary:{review_date}`

실제 예시:

- `daily_review_summary:2026-05-25`

판단:

- 동일 날짜에 대해 1차 export에서 row가 생성되었고, 2차 export에서 동일 row가 update되었으므로 Daily Review Summary Notion export의 upsert 동작은 정상으로 판단한다.

### 2. Notion UI 확인 결과

아래 property가 Notion UI에서 확인된 것으로 기록한다.

- `Review Date`
- `Review Status`
- `Availability Status`
- `Committed Trade Count`
- `Warning Count`
- `Fail Count`
- `Cash Start`
- `Cash End`
- `Cash Impact`
- `Position Impact Summary`
- `Commit Report Path`
- `Preview Report Path`
- `Latest Snapshot Date`
- `Schema Version`
- `Synced At`
- `Sync Status`

추가 판단:

- 핵심 요약 필드, 원천 파일 추적 필드, 동기화 관리 필드가 모두 UI에서 확인 가능하므로 review layer로서 필요한 최소 정보는 충족된 것으로 본다.

### 3. Page body 확인 결과

아래 page body 섹션이 확인된 것으로 기록한다.

- `오늘의 리뷰 요약`
- `체결 요약`
- `포지션 변화`
- `경고 / 특이사항`
- `원천 파일`

추가 판단:

- page body는 상세 원장을 대체하지 않고, 하루 운영 결과를 빠르게 검토하는 compact summary 구조로 동작한다.

### 4. 수정하지 않은 것

이번 closeout_revision에서 아래 항목은 수행하지 않았다.

- `paper_execution_log.csv` 수정 없음
- `paper_account_snapshot.csv` 수정 없음
- `paper_position_snapshot.csv` 수정 없음
- `paper_current_state_YYYYMMDD.json` 수정 없음
- Manual Execution import 재실행 없음
- Manual Execution commit 재실행 없음
- Manual Execution status back-write 재실행 없음
- Notion DB schema 변경 없음
- Python 코드 수정 없음

### 5. 최종 판정

최종 결론:

- PAPER14-6 Daily Review Summary Notion export는 `created -> updated` actual export 검증까지 완료됐다.
- Daily Review Summary는 Daily Plan / Manual Executions / Account Snapshot / Weekly / Benchmark export 흐름과 함께 PAPER14 Notion review layer의 일일 결과 요약 역할을 수행한다.

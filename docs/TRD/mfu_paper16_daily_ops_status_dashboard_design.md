# PAPER16-1 Daily Ops Status Dashboard 설계

## 목적

`Daily Ops Status` Notion DB를 운영자가 실제로 보기 쉬운 대시보드로 구성하기 위한 설계 문서다. 이 문서는 Alert/Monitoring, Replay, Schema Drift, Universe 확장, Strategy 확장으로 넘어가기 전에 수동 Notion view 구성, 표시 필드 우선순위, 상태값 해석, 설정 체크리스트를 고정한다.

이번 MFU는 설계 전용이다. Notion view를 생성하거나 수정하지 않고, Notion actual write/export를 실행하지 않으며, Python 코드와 paper source-of-truth 산출물을 변경하지 않는다.

## 범위 / 비범위

범위:

- Daily Ops Status dashboard 목적
- 권장 Notion view
- 표시 필드 우선순위
- 상태값 해석표
- 수동 Notion view 설정 체크리스트
- 최소 SOP addendum

비범위:

- Notion DB/view 실제 생성 또는 수정
- Notion actual write/export
- exporter 또는 schema 코드 변경
- wrapper CLI / GUI / GitHub Actions / Notion button 구현
- Alert / Replay / Schema Drift / Universe / Strategy 구현
- `paper_default` migration
- outputs/paper 원장 변경

## Source-of-truth 원칙

CSV, JSON, Markdown, SQLite가 source-of-truth다. 로컬 `paper.py status`와 로컬 산출물이 실제 운영 상태를 정의한다.

Notion `Daily Ops Status`는 presentation layer다. 로컬 상태 row를 운영자가 보기 쉽게 요약하지만, ledger, review, execution, account state의 권위 있는 원본은 아니다.

PAPER15에서 `paper_sandbox`를 대상으로 제한적 Daily Ops Status actual create/update가 검증됐다. PAPER16-1에서는 추가 Notion actual write/export를 실행하지 않고, Codex가 Notion 화면을 직접 수정하지 않는다.

## Dashboard가 답해야 하는 운영 질문

- 어떤 account/date를 보고 있는가?
- daily plan이 준비됐는가?
- execution/current state/snapshot 단계가 끝났는가?
- reports와 review template이 준비됐는가?
- review가 미시작, 일부 append, 완료 중 어디에 있는가?
- Daily Ops Status row가 Notion에 sync됐는가?
- 다음에 로컬 PC에서 어떤 명령 또는 수동 확인을 해야 하는가?
- missing file, validation failure, sync failure 때문에 막힌 row가 있는가?

초기 적용은 `paper_sandbox`에 집중한다. `paper_default` actual export, multi-account bulk export, 자동화 trigger export는 별도 안전 검토 전까지 금지한다.

## 현재 Mapping 기준

Mapping section:

- `daily_ops_status`

External Key:

- `daily_ops_status:{account_id}:{status_date}`

현재 매핑된 주요 property:

| Mapping key | Notion property | Type |
| --- | --- | --- |
| `name` | `Name` | title |
| `external_key` | `External Key` | rich_text |
| `account_id` | `Account ID` | select |
| `status_date` | `Status Date` | date |
| `workflow_status` | `Workflow Status` | select |
| `review_progress_status` | `Review Progress Status` | select |
| `review_completion_ratio` | `Review Completion Ratio` | number |
| `next_recommended_command` | `Next Recommended Command` | rich_text |
| `blocking_reason` | `Blocking Reason` | rich_text |
| `plan_exists` | `Plan Exists` | checkbox |
| `current_state_exists` | `Current State Exists` | checkbox |
| `account_snapshot_exists` | `Account Snapshot Exists` | checkbox |
| `position_snapshot_exists` | `Position Snapshot Exists` | checkbox |
| `execution_log_rows_for_date` | `Execution Log Rows For Date` | number |
| `reports_ready` | `Reports Ready` | checkbox |
| `daily_review_summary_exists` | `Daily Review Summary Exists` | checkbox |
| `performance_summary_exists` | `Performance Summary Exists` | checkbox |
| `review_template_exists` | `Review Template Exists` | checkbox |
| `review_template_row_count` | `Review Template Row Count` | number |
| `review_validation_result` | `Review Validation Result` | select |
| `manual_review_log_exists` | `Manual Review Log Exists` | checkbox |
| `manual_review_log_row_count` | `Manual Review Log Row Count` | number |
| `review_answered_row_count` | `Review Answered Row Count` | number |
| `review_pending_row_count` | `Review Pending Row Count` | number |
| `last_status_checked_at` | `Last Status Checked At` | date |
| `sync_status` | `Sync Status` | select |
| `synced_at` | `Synced At` | date |
| `schema_version` | `Schema Version` | rich_text |
| `source_root` | `Source Root` | rich_text |

## 필드 우선순위

Primary fields:

- `Status Date`
- `Account ID`
- `Workflow Status`
- `Review Progress Status`
- `Review Completion Ratio`
- `Sync Status`
- `Next Recommended Command`
- `Blocking Reason`
- `Synced At`
- `External Key`

Secondary fields:

- `Plan Exists`
- `Current State Exists`
- `Account Snapshot Exists`
- `Position Snapshot Exists`
- `Execution Log Rows For Date`
- `Reports Ready`
- `Review Template Exists`
- `Review Validation Result`
- `Manual Review Log Exists`
- `Manual Review Log Row Count`
- `Review Answered Row Count`
- `Review Pending Row Count`

보통 숨겨도 되는 필드:

- `Schema Version`
- `Source Root`
- `Last Status Checked At`
- `Daily Review Summary Exists`
- `Performance Summary Exists`
- `Review Template Row Count`

`External Key`는 troubleshooting view에서는 보여야 한다. 운영자가 대시보드에 익숙해진 뒤에는 고수준 daily view에서 숨겨도 된다.

## 권장 View

### Today Ops

목적:

- 오늘 또는 선택한 운영 날짜의 계좌별 상태를 확인한다.

권장 filter:

- `Status Date`가 today이거나 수동으로 선택한 operation date.

권장 sort:

- `Account ID` 오름차순
- `Workflow Status` 오름차순

권장 group:

- `Account ID`

표시 필드:

- `Name`
- `Account ID`
- `Status Date`
- `Workflow Status`
- `Review Progress Status`
- `Review Completion Ratio`
- `Sync Status`
- `Next Recommended Command`
- `Blocking Reason`
- `Synced At`

숨김 필드:

- `Source Root`
- `Schema Version`
- troubleshooting이 아니면 세부 artifact checkbox

운영 판단:

- 각 계좌에서 다음 로컬 명령 또는 수동 확인이 무엇인지 결정한다.

### By Account

목적:

- 계좌별 최근 운영 이력을 확인한다.

권장 filter:

- 기본은 없음. 필요하면 `Status Date` 최근 30일.

권장 sort:

- `Status Date` 내림차순

권장 group:

- `Account ID`

표시 필드:

- `Status Date`
- `Workflow Status`
- `Review Progress Status`
- `Sync Status`
- `Review Pending Row Count`
- `Next Recommended Command`
- `External Key`

숨김 필드:

- 특정 계좌/날짜를 조사하지 않는 한 상세 artifact flags

운영 판단:

- 특정 계좌가 같은 workflow 단계에서 반복적으로 멈추는지 확인한다.

### Needs Action

목적:

- 운영자 조치가 필요한 row를 모아 본다.

권장 filter:

- `Workflow Status`가 `NO_PLAN`, `PLAN_READY`, `COMMITTED`, `REVIEW_READY`, `REVIEW_PARTIAL`, `UNKNOWN_OR_INCOMPLETE` 중 하나
- 또는 `Sync Status`가 `FAILED`
- 또는 `Review Validation Result`가 `FAIL`

권장 sort:

- `Status Date` 내림차순
- `Workflow Status` 오름차순

권장 group:

- `Workflow Status`

표시 필드:

- `Account ID`
- `Status Date`
- `Workflow Status`
- `Review Progress Status`
- `Review Pending Row Count`
- `Review Validation Result`
- `Sync Status`
- `Blocking Reason`
- `Next Recommended Command`

숨김 필드:

- `Schema Version`
- `Source Root`
- 필요하지 않은 artifact flags

운영 판단:

- 다음 로컬 명령, manual review 완료, schema/sync troubleshooting 중 무엇을 해야 하는지 결정한다.

### Recent Sync

목적:

- 최근 Daily Ops Status Notion sync 결과를 확인한다.

권장 filter:

- `Synced At` 최근 7일. 초기 rollout 중에는 filter 없이 사용 가능.

권장 sort:

- `Synced At` 내림차순

권장 group:

- `Sync Status`

표시 필드:

- `Account ID`
- `Status Date`
- `External Key`
- `Sync Status`
- `Synced At`
- `Last Status Checked At`
- `Workflow Status`
- `Review Progress Status`

숨김 필드:

- 대부분의 artifact existence flags

운영 판단:

- dry-run, actual sync, failed sync 중 어떤 presentation 상태가 최신인지 확인한다.

### Review Closeout

목적:

- 계좌/날짜별 review 완료 상태에 집중한다.

권장 filter:

- `Workflow Status`가 `REVIEW_READY`, `REVIEW_PARTIAL`, `REVIEW_DONE` 중 하나

권장 sort:

- `Review Pending Row Count` 내림차순
- `Status Date` 내림차순

권장 group:

- `Review Progress Status`

표시 필드:

- `Account ID`
- `Status Date`
- `Workflow Status`
- `Review Progress Status`
- `Review Completion Ratio`
- `Review Template Exists`
- `Review Validation Result`
- `Manual Review Log Exists`
- `Review Answered Row Count`
- `Review Pending Row Count`
- `Next Recommended Command`

숨김 필드:

- upstream 문제 조사 중이 아니면 execution/snapshot 필드

운영 판단:

- pending review row를 채울지, `review-append`를 실행할지, 해당 날짜를 완료로 볼지 결정한다.

## 상태값 해석

### Workflow Status

| Value | 의미 | 운영자 조치 |
| --- | --- | --- |
| `NO_PLAN` | daily plan artifact가 없다. | 해당 account/date의 plan을 생성한다. |
| `PLAN_READY` | plan은 있지만 같은 날짜의 state/snapshot이 없다. | EOD dry-run 또는 execution/current-state 단계를 확인한다. |
| `COMMITTED` | local source-of-truth는 갱신됐지만 reports/review가 준비되지 않았다. | reports를 생성하고 review template을 준비한다. |
| `REVIEW_READY` | reports/template/validation이 준비됐고 review append가 남아 있다. | review 입력을 완료한 뒤 local review append를 실행한다. |
| `REVIEW_PARTIAL` | 일부 review row가 append됐지만 pending row가 남아 있다. | pending row를 완료하고 review validation/append를 다시 실행한다. |
| `REVIEW_DONE` | template과 log 기준 review row가 완료됐다. | 즉시 필요한 review 조치는 없다. 필요하면 sync/presentation을 확인한다. |
| `UNKNOWN_OR_INCOMPLETE` | 상태를 안전하게 분류할 수 없다. | local artifact와 `Blocking Reason`을 확인한다. |

### Review Progress Status

| Value | 의미 | 운영자 조치 |
| --- | --- | --- |
| `NOT_STARTED` | review template은 있지만 answer/log row가 완료되지 않았다. | append 전에 review row를 채운다. |
| `READY` | ready-to-append 상태를 표현할 future 후보 값이다. | 코드/SOP가 의미를 확정하기 전까지는 review action needed로 취급한다. |
| `PARTIAL` | 일부 review row는 완료/append됐지만 pending row가 남아 있다. | pending row를 완료한다. |
| `DONE` | review 진행이 완료됐다. | validation/sync 실패가 아니면 추가 review 조치는 없다. |
| `UNKNOWN` | 진행도를 판단할 수 없다. | local template/log 정합성을 확인한다. |
| `NOT_APPLICABLE` | 아직 review template/progress 맥락이 적용되지 않는다. | workflow status를 기준으로 upstream 조치를 판단한다. |

### Sync Status

| Value | 의미 | 운영자 조치 |
| --- | --- | --- |
| `DRY_RUN` | Notion write 없이 payload만 생성됐다. | 검사 목적이며 Notion row update는 기대하지 않는다. |
| `SYNCED` | Daily Ops Status row가 실제로 create/update됐다. | 필요하면 표시 필드가 local status와 일치하는지 확인한다. |
| `FAILED` | actual sync failure 또는 failure summary를 나타내는 current/operator concept다. | local source-of-truth를 rollback하지 말고 Notion/schema/export 오류를 확인한다. |
| `SKIPPED` | 의도적으로 sync를 생략하는 future 후보 상태다. | 재실행 전 skip reason을 확인한다. |

## 수동 Notion View 설정 체크리스트

기본 설정:

- DB 이름이 `Daily Ops Status`인지 확인한다.
- property 이름이 `config/notion_property_mapping.example.json`과 일치하는지 확인한다.
- `Account ID`, `Workflow Status`, `Review Progress Status`, `Sync Status`가 select property인지 확인한다.
- `External Key`가 최소 하나의 troubleshooting view에서 보이는지 확인한다.
- 첫 dashboard 단계에서는 relation/rollup dependency를 만들지 않는다.

생성할 view:

- `Today Ops`
- `By Account`
- `Needs Action`
- `Recent Sync`
- `Review Closeout`

각 view 설정:

- 위에서 정의한 filter를 적용한다.
- 위에서 정의한 sort를 적용한다.
- 운영자가 빠르게 볼 수 있을 때만 group을 적용한다.
- primary fields를 앞쪽에 둔다.
- debug/internal fields는 troubleshooting view가 아니면 숨긴다.
- 표시 property 이름이 이 문서와 mapping 파일과 일치하는지 확인한다.

안전 체크:

- Notion을 source-of-truth로 사용하지 않는다.
- future migration procedure가 아닌 한 `External Key`를 수동 수정하지 않는다.
- Notion sync 성공만으로 local ledger 성공을 추론하지 않는다.
- 이 dashboard 설계만으로 bulk export나 `paper_default` actual export를 열지 않는다.
- 첫 수동 dashboard 정리 대상은 `paper_sandbox`로 둔다.

## 기존 Notion DB와의 관계

`Daily Ops Status`는 운영 dashboard다. 기존 Notion DB는 detail/staging DB로 유지한다.

- `Daily Plans`: plan presentation
- `Manual Executions`: execution input/staging
- `Manual Reviews`: review input/staging
- `Account Snapshots`: account state presentation
- `Weekly Reports`: weekly summary presentation
- `Benchmark Reports`: benchmark comparison presentation
- `Daily Review Summaries`: daily outcome presentation

초기 dashboard는 `Account ID`, `Status Date`, `External Key` 관례만으로 느슨하게 연결한다. relation/rollup 설계는 dashboard가 안정화된 뒤 검토한다.

## Risks / Open Questions

- `FAILED`, `SKIPPED`, `READY`는 설계상 유효하지만 모든 코드 경로에서 안정적으로 emit되는 값은 아닐 수 있다.
- `Review Progress Status = READY`는 validated-ready와 not-started를 구분하려면 future semantics 결정이 필요하다.
- "today" filter는 실제 operation date와 calendar date가 다를 수 있으므로 운영 날짜 기준을 확인해야 한다.
- 기존 SOP 파일에는 legacy text와 encoding artifact가 남아 있다. 이번 MFU는 SOP 전체 재작성 대신 최소 addendum만 추가한다.

## Recommended Next MFU

PAPER16-2에서는 dashboard 주변 운영 SOP를 구체화한다.

- 각 `Workflow Status`별 command map
- actual export rerun policy
- schema validation 대응 정책
- `paper_sandbox` 및 향후 승인된 non-default account용 운영자 체크리스트

BEGIN MFU-PAPER15-4E_NOTION_DAILY_OPS_STATUS_DB_DESIGN

# MFU-PAPER15-4E 작업 지시문: Notion Daily Ops Status DB 설계

## 목적

MFU-PAPER15-4E의 목표는 다중계좌 운영 관찰을 위한 Notion `Daily Ops Status` DB를 설계하는 것이다.

이번 단계는 설계 문서화 전용이다. Notion DB 실제 생성, Notion API write/sync/export, 코드 구현, mapping 파일 수정, paper 원장 수정은 하지 않는다.

반드시 명시:

이번 PAPER15-4E는 Notion Daily Ops Status DB 설계 작업이며, Notion DB 실제 생성, Notion API write/sync/export, 코드 구현, mapping 파일 수정, paper 원장 수정은 포함하지 않는다.

## 배경

PAPER15-4D에서 로컬 `paper.py status`에 `REVIEW_PARTIAL`, `REVIEW_DONE`이 추가되었다.

현재 로컬 workflow status 후보:

- NO_PLAN
- PLAN_READY
- COMMITTED
- REVIEW_READY
- REVIEW_PARTIAL
- REVIEW_DONE
- UNKNOWN_OR_INCOMPLETE

기존 Notion DB들은 상세 데이터 표시용이다.

- Daily Plans
- Account Snapshots
- Weekly Reports
- Benchmark Reports
- Daily Review Summaries
- Manual Executions
- Manual Reviews

이번 작업은 기존 DB를 대체하지 않고, 계좌별·날짜별 운영 상태를 한눈에 보는 관제 DB를 설계한다.

## 설계 원칙

1. Notion은 source-of-truth가 아니다.
2. 로컬 CSV/JSON/Markdown/SQLite와 `paper.py status`가 source-of-truth다.
3. Daily Ops Status DB는 read-only export / presentation layer다.
4. 계좌별 DB를 복제하지 않고 단일 DB + Account ID로 간다.
5. 기존 상세 DB와 relation/rollup은 초기 단계에서 넣지 않는다.
6. External Key는 account-aware로 설계한다.

## 설계 대상 DB

권장 DB 이름: Daily Ops Status

대안 이름도 비교한다.

- Paper Daily Ops Status
- Account Daily Ops Status

## External Key 설계

권장 형식:

daily_ops_status:{account_id}:{status_date}

예시:

- daily_ops_status:paper_sandbox:2026-05-20
- daily_ops_status:paper_default:2026-05-20

정책:

- account_id는 반드시 포함한다.
- date는 YYYY-MM-DD 형식으로 통일한다.
- legacy account-less key는 만들지 않는다.
- paper_default도 신규 DB에서는 account-aware key만 사용한다.

## 권장 Property 설계

아래 property를 설계하고, 각 property별 type / 설명 / source field를 표로 정리한다.

필수 후보:

- Name
- External Key
- Account ID
- Status Date
- Workflow Status
- Review Progress Status
- Review Completion Ratio
- Next Recommended Command
- Blocking Reason
- Plan Exists
- Current State Exists
- Account Snapshot Exists
- Position Snapshot Exists
- Execution Log Rows For Date
- Reports Ready
- Daily Review Summary Exists
- Performance Summary Exists
- Review Template Exists
- Review Template Row Count
- Review Validation Result
- Manual Review Log Exists
- Manual Review Log Row Count
- Review Answered Row Count
- Review Pending Row Count
- Last Status Checked At
- Sync Status
- Synced At
- Schema Version
- Source Root

권장 type 후보:

- Name: title
- External Key: rich_text
- Account ID: select
- Status Date: date
- Workflow Status: select
- Review Progress Status: select
- Review Completion Ratio: number 또는 percent
- Next Recommended Command: rich_text
- Blocking Reason: rich_text
- Exists 계열: checkbox
- Count 계열: number
- Result/Status 계열: select
- Synced At / Last Status Checked At: date
- Source Root: rich_text

Workflow Status option:

- NO_PLAN
- PLAN_READY
- COMMITTED
- REVIEW_READY
- REVIEW_PARTIAL
- REVIEW_DONE
- UNKNOWN_OR_INCOMPLETE

Review Progress Status option 후보:

- NOT_STARTED
- READY
- PARTIAL
- DONE
- UNKNOWN
- NOT_APPLICABLE

Sync Status option 후보:

- DRY_RUN
- SYNCED
- FAILED
- SKIPPED

## View 설계

최소 view를 설계한다.

1. Today by Account
   - Status Date = today
   - Account ID 기준 group
   - Workflow Status 표시

2. Needs Action
   - Workflow Status가 NO_PLAN, PLAN_READY, COMMITTED, REVIEW_READY, REVIEW_PARTIAL, UNKNOWN_OR_INCOMPLETE
   - Next Recommended Command 표시

3. Review Closeout
   - REVIEW_READY / REVIEW_PARTIAL / REVIEW_DONE 중심
   - Review Pending Row Count 표시

4. By Account
   - Account ID별 전체 이력

5. Failed / Unknown
   - Workflow Status = UNKNOWN_OR_INCOMPLETE 또는 Sync Status = FAILED

## 기존 DB와의 관계

이번 단계에서는 relation/rollup을 넣지 않는 방향을 우선 검토한다.

문서에 아래를 명확히 적는다.

- Daily Ops Status DB는 관제판이다.
- 기존 DB들은 상세 데이터 DB다.
- 초기에는 External Key / Account ID / Date로 느슨하게 연결한다.
- relation/rollup은 후속 안정화 이후 검토한다.

## 후속 MFU 분리

이번 단계에서는 구현하지 않는다.

후속 후보:

- PAPER15-4F: Notion Daily Ops Status mapping/schema 추가
- PAPER15-4G: local paper.py status → Daily Ops Status dry-run exporter
- PAPER15-4H: Daily Ops Status actual export 제한 실행
- PAPER15-4I: legacy Notion row migration preview

## 조사 대상 파일

- core/paper_status.py
- config/notion_property_mapping.example.json
- core/notion_exporters.py
- core/notion_schema_validator.py
- scripts/export_paper_to_notion.py
- docs/TRD/mfu_paper15_4d_local_review_workflow_status_semantics.md
- docs/TRD/mfu_paper15_4c_paper_sandbox_review_append_rehearsal.md

## 산출물

필수 문서:

docs/TRD/mfu_paper15_4e_notion_daily_ops_status_db_design.md

문서 필수 포함:

1. Purpose
2. Scope / Non-scope
3. Current local workflow status model
4. Why a separate Daily Ops Status DB is needed
5. DB name recommendation
6. External Key design
7. Property table with type/source/description
8. Workflow Status option list
9. Review Progress option list
10. Recommended Notion views
11. Relationship with existing Notion DBs
12. Manual Notion setup checklist
13. Risks / open questions
14. Recommended next MFUs

## 금지 사항

- Notion DB 실제 생성 금지
- Notion API write/sync/export 금지
- config/notion_property_mapping.example.json 수정 금지
- core/notion_exporters.py 수정 금지
- core/paper_status.py 수정 금지
- schema validator 수정 금지
- paper 원장 CSV 수정 금지
- outputs 하위 파일 수정 금지
- broker/API 실행 금지
- cloud runner 작업 금지
- git add . 금지
- git add -A 금지

## 허용 사항

- 코드/문서 read-only 조사
- 설계 문서 작성
- read-only status 명령 실행
- git diff 확인
- git status 확인

허용 read-only 명령 예시:

```cmd
python scripts\paper.py status --account-id paper_sandbox --json
type config\notion_property_mapping.example.json
type core\paper_status.py
```

## 검증 명령

Windows CMD 기준:

```cmd
git diff -- docs\TRD\mfu_paper15_4e_notion_daily_ops_status_db_design.md
git status --short
```

필요 시 read-only 확인:

```cmd
python scripts\paper.py status --account-id paper_sandbox --json
```

## 성공 기준

- Daily Ops Status DB의 목적과 역할이 명확히 정의된다.
- External Key 형식이 account-aware로 정의된다.
- 필수 property와 type이 정리된다.
- Workflow Status / Review Progress Status option이 정리된다.
- 권장 Notion view가 정의된다.
- 기존 Notion DB와의 관계가 정리된다.
- 사용자가 Notion에서 해야 할 수동 작업 체크리스트가 작성된다.
- 후속 구현 MFU가 분리된다.
- 코드, mapping, Notion, outputs, paper 원장은 수정하지 않는다.

## 결과 보고 형식

5천자 이내.

포함:

1. Summary
2. 생성/수정한 파일
3. 추천 DB 이름
4. External Key 설계
5. 필수 property 목록
6. Workflow Status options
7. Review Progress Status options
8. 추천 views
9. 기존 Notion DB와의 관계
10. 사용자가 Notion에서 해야 할 작업
11. Risks / open questions
12. 다음 MFU 제안
13. 코드 변경 여부
14. mapping 변경 여부
15. Notion actual write/sync/export 실행 여부
16. outputs 변경 여부

반드시 명시:

이번 PAPER15-4E는 Notion Daily Ops Status DB 설계 작업이며, Notion DB 실제 생성, Notion API write/sync/export, 코드 구현, mapping 파일 수정, paper 원장 수정은 포함하지 않는다.

END MFU-PAPER15-4E_NOTION_DAILY_OPS_STATUS_DB_DESIGN

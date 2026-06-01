BEGIN MFU-PAPER15-3E_NOTION_EXTERNAL_KEY_ACCOUNT_NAMESPACE_DESIGN

# MFU-PAPER15-3E 작업 지시문: Notion External Key Account Namespace Design

## 목적

MFU-PAPER15-3E의 목표는 다중계좌 도입에 맞춰 Notion DB의 Account ID property, External Key namespace, 기존 row 호환 정책, 후속 migration 범위를 설계하는 것이다.

이번 단계는 조사/설계 전용이다.  
코드 구현, Notion API write, Notion schema 변경, 기존 External Key migration, paper 원장 수정은 하지 않는다.

반드시 명시:

```text
이번 PAPER15-3E는 Notion external key account namespace 조사/설계이며, 코드 구현, Notion write/export/sync, Notion schema migration, paper 원장 수정, DB write는 포함하지 않는다.
```

## 확정 전제

```text
1. 기존 단일계좌는 account_id=paper_default로 해석한다.
2. Notion DB는 계좌별로 분리하지 않고 단일 DB + Account ID property 방향으로 설계한다.
3. 기존 Notion row는 account_id가 없더라도 paper_default로 해석한다.
4. 신규 External Key에는 account_id를 포함한다.
5. 기존 External Key 수동 수정 또는 migration은 이번 단계에서 하지 않는다.
6. writer path 적용은 PAPER15-3F에서 진행한다.
```

## 현재 Notion 관찰 사항

사용자 확인 결과:

```text
- 모든 주요 Notion DB에 External Key 필드는 존재한다.
- Account ID 또는 계좌 관련 필드는 현재 없다.
- 현재 External Key는 account-less 구조다.
```

현재 확인된 key 예시:

```text
weekly_report:2026-05-09:2026-05-20
benchmark:2026-05-20:exploratory
account_snapshot:2026-05-20
daily_plan:2026-05-20
manual_execution:2026-05-25:AAPL:BUY:01
daily_review_summary:2026-05-25
manual_review:2026-05-25:AAPL:Q001
```

## 조사 대상 파일

```text
config/notion_property_mapping.example.json
config/notion_settings.example.json
core/notion_mapping.py
core/notion_exporters.py
core/notion_schema_validator.py
core/notion_manual_execution_importer.py
core/notion_manual_review_importer.py
core/notion_manual_execution_status_sync.py
core/notion_manual_review_status_sync.py
scripts/export_paper_to_notion.py
scripts/import_notion_executions.py
scripts/import_notion_reviews.py
scripts/sync_notion_execution_status.py
scripts/sync_notion_review_status.py
scripts/dev/validate_notion_schema.py
docs/operations/paper_notion_ops.md
docs/TRD/mfu_paper15_*.md
tests/test_notion*
```

## 설계 범위

### 1. Account ID property 설계

아래 DB에 Account ID property가 필요한지 설계한다.

```text
Daily Plans
Manual Executions
Account Snapshots
Weekly Reports
Benchmark Reports
Daily Review Summaries
Manual Reviews
```

권장 방향:

```text
Property name: Account ID
Type 후보: Select 우선, Text 대안
초기 option: paper_default
```

검토 질문:

```text
1. Account ID는 모든 DB에 필수인가?
2. Select와 Text 중 무엇이 안전한가?
3. 기존 row는 Account ID가 비어 있어도 paper_default로 해석할 것인가?
4. 새 row부터 Account ID를 필수로 요구할 것인가?
5. Manual Executions / Manual Reviews의 READY view에 Account ID 필터가 필요한가?
```

### 2. External Key account namespace 설계

현재 account-less key를 account-aware key로 확장한다.

권장 key 후보:

```text
daily_plan:{account_id}:{date}
account_snapshot:{account_id}:{snapshot_date}
weekly_report:{account_id}:{period_start}:{period_end}
benchmark:{account_id}:{latest_snapshot_date}:{run_mode}
daily_review_summary:{account_id}:{review_date}
manual_execution:{account_id}:{execution_date}:{symbol}:{side}:{sequence}
manual_review:{account_id}:{review_date}:{symbol}:{question_id}
```

예시:

```text
daily_plan:paper_default:2026-05-20
account_snapshot:paper_default:2026-05-20
manual_execution:paper_default:2026-05-25:AAPL:BUY:01
manual_review:paper_default:2026-05-25:AAPL:Q001
```

검토 질문:

```text
1. account_id는 External Key의 어느 위치에 들어가야 하는가?
2. 기존 key와 새 key를 동시에 지원해야 하는가?
3. upsert lookup은 새 key만 볼 것인가, legacy key fallback도 볼 것인가?
4. legacy row를 업데이트할 때 새 key로 바꿀 것인가, 별도 migration 전까지 유지할 것인가?
5. 같은 날짜/심볼/side가 계좌별로 중복될 때 충돌이 없어지는가?
```

### 3. DB별 위험도와 적용 순서 설계

DB별 위험도를 분류한다.

권장 위험도 순서:

```text
1. Manual Executions
2. Manual Reviews
3. Daily Plans
4. Account Snapshots
5. Daily Review Summaries
6. Weekly Reports
7. Benchmark Reports
```

각 DB별로 아래를 정리한다.

```text
- 현재 key 형식
- 신규 key 형식
- Account ID property 필요 여부
- legacy paper_default 해석 방식
- migration 필요 여부
- 후속 구현 위치
- Notion에서 사용자가 해야 할 작업
```

### 4. 후속 MFU 설계

이번 단계에서는 구현하지 않고 후속 작업을 나눈다.

후속 후보:

```text
PAPER15-3E-1: Notion Account ID property manual setup guide
PAPER15-3E-2: notion_property_mapping.example.json account_id 추가
PAPER15-3E-3: exporter external key namespace 구현
PAPER15-3E-4: Manual Execution/Review importer account filter 설계
PAPER15-3E-5: legacy Notion row migration preview
```

## 산출물

필수 문서:

```text
docs/TRD/mfu_paper15_3e_notion_external_key_account_namespace_design.md
```

문서에는 반드시 포함한다.

```text
1. Purpose
2. Scope / Non-scope
3. Current Notion account-less key inventory
4. Account ID property recommendation
5. DB-by-DB external key namespace design
6. Legacy paper_default compatibility policy
7. Upsert / import / status sync impact
8. Manual Notion setup checklist
9. Migration strategy
10. Risks / open questions
11. Recommended next MFUs
```

## 금지 사항

```text
코드 구현 금지
Notion API write 금지
Notion export 실행 금지
Notion status sync 실행 금지
Notion DB property 직접 변경 금지
기존 External Key 수동/자동 수정 금지
migration script 작성 금지
paper 원장 CSV 수정 금지
DB write 금지
outputs 하위 파일 수정 금지
writer path 적용 금지
git add . 금지
git add -A 금지
```

## 허용 사항

```text
파일 읽기
코드 검색
기존 mapping/config/example 조사
테스트 파일 조사
문서 작성
read-only 명령 실행
```

허용 read-only 명령 예시:

```cmd
type config\notion_property_mapping.example.json
type core\notion_exporters.py
type core\notion_manual_execution_importer.py
type core\notion_manual_review_importer.py
```

## 검증

필수 확인:

```cmd
git diff -- docs\TRD\mfu_paper15_3e_notion_external_key_account_namespace_design.md
git status --short
```

확인 기준:

```text
수정 파일은 원칙적으로 docs/TRD/mfu_paper15_3e_notion_external_key_account_namespace_design.md 하나여야 한다.
코드 파일은 수정되지 않아야 한다.
config 파일은 수정되지 않아야 한다.
outputs/ 하위 파일은 수정되지 않아야 한다.
```

## 성공 기준

```text
모든 Notion DB의 Account ID property 필요 여부가 정리된다.
DB별 신규 External Key 형식이 정의된다.
기존 account-less row를 paper_default로 해석하는 정책이 정리된다.
legacy key와 new key의 공존/전환 정책이 정리된다.
Manual Executions / Manual Reviews의 계좌 충돌 위험이 설명된다.
사용자가 Notion에서 해야 할 수동 작업 체크리스트가 작성된다.
후속 구현 MFU가 실행 가능한 단위로 제안된다.
코드와 Notion, 원장, outputs는 수정하지 않는다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 조사한 파일
3. 현재 Notion key inventory
4. Account ID property 권장안
5. DB별 신규 External Key 설계
6. legacy paper_default 호환 정책
7. upsert/import/status sync 영향
8. 사용자가 Notion에서 해야 할 작업
9. migration 전략
10. 주요 리스크
11. open questions
12. 다음 MFU 제안
13. 코드 변경 여부
14. config 변경 여부
15. Notion write/export/sync 실행 여부
16. outputs 변경 여부
```

반드시 명시:

```text
이번 PAPER15-3E는 Notion external key account namespace 조사/설계이며, 코드 구현, Notion write/export/sync, Notion schema migration, paper 원장 수정, DB write는 포함하지 않는다.
```

END MFU-PAPER15-3E_NOTION_EXTERNAL_KEY_ACCOUNT_NAMESPACE_DESIGN
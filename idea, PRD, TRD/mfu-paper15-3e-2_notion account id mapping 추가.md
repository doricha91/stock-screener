BEGIN PAPER15-NOTION-MAP

# PAPER15-NOTION-MAP 작업 지시문: Notion Account ID Mapping 추가

## 목적

PAPER15-NOTION-MAP의 목표는 사용자가 Notion 7개 DB에 수동 추가한 `Account ID` property를 Python 설정/검증 계층에서 인식할 수 있도록 mapping example과 schema validation 관련 테스트를 보강하는 것이다.

이번 단계는 mapping/schema 인식 단계다.  
External Key 생성 로직 변경, exporter/importer/status sync 동작 변경, Notion write/export/sync 실행, 기존 row migration은 하지 않는다.

반드시 명시:

```text
이번 PAPER15-NOTION-MAP은 Notion Account ID property를 mapping/schema 계층에 반영하는 작업이며, External Key 생성 로직 변경, Notion write/export/sync, 기존 row migration, paper 원장 수정은 포함하지 않는다.
```

## 확정 전제

```text
1. 사용자가 Notion 주요 DB에 Account ID property를 추가했다.
2. Property name은 Account ID다.
3. Type은 Select 기준으로 설계한다.
4. 초기 option은 paper_default다.
5. 기존 legacy row는 Account ID가 비어 있어도 paper_default로 해석할 예정이다.
6. 신규 account-aware External Key 구현은 후속 PAPER15-NOTION-KEY에서 진행한다.
```

## 대상 Notion DB

아래 7개 DB mapping에 `account_id`를 추가한다.

```text
daily_plans
manual_executions
account_snapshots
weekly_reports
benchmark_reports
daily_review_summaries
manual_reviews
```

권장 mapping:

```json
"account_id": "Account ID"
```

## 구현 범위

### 1. mapping example 수정

수정 대상:

```text
config/notion_property_mapping.example.json
```

각 관련 section에 아래 key를 추가한다.

```json
"account_id": "Account ID"
```

주의:

```text
기존 property 이름은 변경하지 않는다.
기존 external_key mapping은 변경하지 않는다.
기존 status/import/sync mapping은 변경하지 않는다.
```

### 2. schema validator 보강

조사 후 필요한 경우 아래 파일을 수정한다.

```text
core/notion_schema_validator.py
scripts/dev/validate_notion_schema.py
```

목표:

```text
- Account ID property를 optional 또는 required 후보로 인식할 수 있게 한다.
- 이번 단계에서 실제 Notion schema migration은 하지 않는다.
- schema validator가 Account ID 누락 여부를 report할 수 있으면 좋다.
```

권장 정책:

```text
Account ID는 다중계좌 전환 필수 property이지만, 기존 사용자 환경 호환을 위해 validator severity는 WARNING부터 시작한다.
후속 단계에서 REQUIRED/FAIL로 승격 가능하다고 문서화한다.
```

### 3. 테스트 보강

수정/추가 후보:

```text
tests/test_notion_schema_validator.py
tests/test_notion_mapping.py
```

테스트 항목:

```text
1. mapping example의 7개 section에 account_id가 존재한다.
2. account_id가 Account ID로 매핑된다.
3. schema validator가 Account ID property를 인식한다.
4. Account ID 누락 시 WARNING 또는 명확한 issue로 보고된다.
5. 기존 mapping key들은 깨지지 않는다.
```

### 4. 문서 추가

문서 추가:

```text
docs/TRD/paper15_notion_map_account_id.md
```

문서 포함 항목:

```text
1. Purpose
2. Scope / Non-scope
3. User-side Notion setup completed
4. Mapping changes
5. Schema validation policy
6. Why External Key logic is not changed yet
7. Next step
```

## 금지 사항

```text
External Key 생성 로직 변경 금지
core/notion_exporters.py의 upsert 동작 변경 금지
manual execution/review importer 로직 변경 금지
status sync 로직 변경 금지
Notion API write 금지
Notion export 실행 금지
Notion status sync 실행 금지
기존 Notion row migration script 작성 금지
paper 원장 CSV 수정 금지
DB write 금지
outputs 하위 파일 수정 금지
writer path 적용 금지
config/notion_settings.json 생성/수정 금지
git add . 금지
git add -A 금지
```

## 허용 사항

```text
config/notion_property_mapping.example.json 수정
schema validator 보강
관련 단위 테스트 추가/수정
TRD 문서 추가
read-only 파일 확인
pytest 실행
```

## 검증 명령

Windows CMD 기준:

```cmd
python -m pytest tests\test_notion_schema_validator.py
python -m pytest tests\test_notion_mapping.py
git diff -- config\notion_property_mapping.example.json core\notion_schema_validator.py scripts\dev\validate_notion_schema.py
git diff -- docs\TRD\paper15_notion_map_account_id.md
git status --short
```

테스트 파일명이 다르면 실제 수정/추가한 테스트 파일 기준으로 실행한다.

## 성공 기준

```text
7개 Notion DB mapping section에 account_id가 추가된다.
account_id는 Account ID property로 매핑된다.
schema validator가 Account ID property를 인식하거나 누락을 report할 수 있다.
기존 mapping key와 기존 Notion 동작은 깨지지 않는다.
External Key 생성 로직은 변경하지 않는다.
Notion write/export/sync는 실행하지 않는다.
paper 원장, DB, outputs는 수정하지 않는다.
후속 External Key namespace 구현 단계로 넘어갈 수 있다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 생성/수정한 파일
3. mapping에 추가한 section
4. Account ID property mapping 정책
5. schema validator 변경 여부
6. 테스트 결과
7. 기존 Notion export/import/sync 영향 여부
8. External Key 생성 로직 변경 여부
9. Notion write/export/sync 실행 여부
10. outputs 변경 여부
11. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER15-NOTION-MAP은 Notion Account ID property를 mapping/schema 계층에 반영하는 작업이며, External Key 생성 로직 변경, Notion write/export/sync, 기존 row migration, paper 원장 수정은 포함하지 않는다.
```

END PAPER15-NOTION-MAP
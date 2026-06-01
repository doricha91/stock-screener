BEGIN MFU-PAPER15-3E-3_NOTION_EXPORTER_EXTERNAL_KEY_NAMESPACE

# MFU-PAPER15-3E-3 작업 지시문: Notion Exporter External Key Account Namespace 구현

## 목적

MFU-PAPER15-3E-3의 목표는 Notion read-only exporter 계층에서 Account ID property와 account-aware External Key를 사용하도록 구현하는 것이다.

이번 단계는 read-only export 대상의 key namespace 구현에 한정한다.  
Manual Execution / Manual Review importer, status sync, Notion row migration preview, writer path 적용은 하지 않는다.

반드시 명시:

```text
이번 PAPER15-3E-3은 Notion read-only exporter의 Account ID property 및 account-aware External Key 구현이며, Manual Execution/Review importer 변경, status sync 변경, Notion row migration preview, paper 원장 수정, writer path 적용은 포함하지 않는다.
```

## 배경

PAPER15-3E에서 신규 External Key 형식을 설계했다.

```text
daily_plan:{account_id}:{date}
account_snapshot:{account_id}:{snapshot_date}
weekly_report:{account_id}:{period_start}:{period_end}
benchmark:{account_id}:{latest_snapshot_date}:{run_mode}
daily_review_summary:{account_id}:{review_date}
```

PAPER15-3E-2에서 아래 7개 mapping section에 `account_id: Account ID`가 추가되었고, schema validator는 Account ID를 WARNING 수준의 권장 property로 인식한다.

```text
daily_plans
manual_executions
account_snapshots
weekly_reports
benchmark_reports
daily_review_summaries
manual_reviews
```

이번 단계에서는 read-only exporter만 account-aware로 만든다.

## 구현 범위

### 1. read-only exporter 대상

이번 단계에서 적용할 대상:

```text
Daily Plans
Account Snapshots
Weekly Reports
Benchmark Reports
Daily Review Summaries
```

이번 단계에서 제외할 대상:

```text
Manual Executions importer
Manual Reviews importer
Manual Execution status sync
Manual Review status sync
legacy Notion row migration preview
```

### 2. account_id 입력 정책

exporter entrypoint와 payload builder에 `account_id`를 전달할 수 있게 한다.

대상 후보:

```text
scripts/export_paper_to_notion.py
core/notion_exporters.py
```

정책:

```text
--account-id 생략 시 paper_default
account_id는 core.paper_account_profile.validate_account_id 사용
Account ID property에는 account_id 값을 쓴다
```

CLI 추가 후보:

```cmd
python scripts\export_paper_to_notion.py --daily-plan --account-id paper_default --dry-run --json
python scripts\export_paper_to_notion.py --weekly --account-id paper_default --dry-run --json
```

### 3. External Key 생성 함수 추가

가능하면 공통 helper를 추가한다.

파일 후보:

```text
core/notion_account_keys.py
```

함수 후보:

```text
build_daily_plan_external_key(account_id, plan_date)
build_account_snapshot_external_key(account_id, snapshot_date)
build_weekly_report_external_key(account_id, period_start, period_end)
build_benchmark_report_external_key(account_id, latest_snapshot_date, run_mode)
build_daily_review_summary_external_key(account_id, review_date)
```

출력 예:

```text
daily_plan:paper_default:2026-05-20
account_snapshot:paper_default:2026-05-20
weekly_report:paper_default:2026-05-09:2026-05-20
benchmark:paper_default:2026-05-20:exploratory
daily_review_summary:paper_default:2026-05-25
```

### 4. Account ID property write

각 read-only export payload에 아래 property를 포함한다.

```text
account_id -> Account ID
```

Notion property type은 Select 기준으로 생성한다.

주의:

```text
기존 External Key property mapping 이름은 변경하지 않는다.
기존 status/sync property 이름은 변경하지 않는다.
```

### 5. legacy key fallback 정책

paper_default에 한해 legacy key fallback을 구현한다.

정책:

```text
1. 새 account-aware key로 기존 page를 먼저 찾는다.
2. 없고 account_id == paper_default이면 legacy account-less key로 한 번 더 찾는다.
3. legacy page를 찾은 경우 같은 page를 update 대상으로 삼을 수 있다.
4. non-default account에는 legacy fallback을 절대 허용하지 않는다.
```

주의:

```text
이번 단계에서 실제 Notion export/write는 실행하지 않는다.
legacy row rewrite가 실제로 발생하는지는 dry-run/test payload로만 검증한다.
```

### 6. dry-run / summary 출력 보강

export summary에 아래를 포함한다.

```text
account_id
external_key
legacy_external_key, if applicable
legacy_fallback_used
data_source_key
target
action
dry_run
```

## 테스트

테스트 파일 후보:

```text
tests/test_notion_account_keys.py
tests/test_notion_exporters_account_namespace.py
tests/test_export_paper_to_notion_cli.py
```

테스트 항목:

```text
1. read-only target별 account-aware external key 생성
2. invalid account_id 실패
3. payload에 Account ID select property 포함
4. paper_default legacy key fallback 후보 생성
5. non-default account는 legacy fallback 없음
6. dry-run summary에 account_id / external_key 포함
7. 기존 account_id 없는 호출은 paper_default로 동작
8. Manual Execution / Manual Review importer/status sync는 변경되지 않음
```

Notion API 실제 호출은 mock/fake client로만 검증한다.

## 산출물

예상 수정/추가 파일:

```text
core/notion_account_keys.py
core/notion_exporters.py
scripts/export_paper_to_notion.py
tests/test_notion_account_keys.py
tests/test_notion_exporters_account_namespace.py
```

필요 시 수정:

```text
tests/test_notion_exporters.py
tests/test_export_paper_to_notion_cli.py
```

문서 추가:

```text
docs/TRD/mfu_paper15_3e_3_notion_exporter_external_key_namespace.md
```

## 금지 사항

```text
Manual Execution importer 변경 금지
Manual Review importer 변경 금지
status sync 로직 변경 금지
Notion API write 실행 금지
Notion export actual 실행 금지
기존 Notion row migration script 작성 금지
paper 원장 CSV 수정 금지
DB write 금지
outputs 하위 파일 수정 금지
writer path 적용 금지
core/paths.py writer path 변경 금지
git add . 금지
git add -A 금지
```

## 허용 사항

```text
read-only exporter key 생성 로직 구현
Account ID property payload 추가
export_paper_to_notion.py에 --account-id 추가
dry-run summary 보강
fake/mock Notion client 테스트
TRD 문서 추가
pytest 실행
```

## 검증 명령

Windows CMD 기준:

```cmd
python -m pytest tests\test_notion_account_keys.py
python -m pytest tests\test_notion_exporters_account_namespace.py
python -m pytest tests\test_notion_mapping.py tests\test_notion_schema_validator.py
python scripts\export_paper_to_notion.py --daily-plan --account-id paper_default --dry-run --json
git diff -- core\notion_account_keys.py core\notion_exporters.py scripts\export_paper_to_notion.py
git diff -- docs\TRD\mfu_paper15_3e_3_notion_exporter_external_key_namespace.md
git status --short
```

테스트 파일명이 다르면 실제 추가/수정한 테스트 파일 기준으로 실행한다.

## 성공 기준

```text
read-only exporter가 account_id를 받을 수 있다.
--account-id 생략 시 paper_default로 동작한다.
read-only export External Key가 account-aware 형식으로 생성된다.
Account ID property가 export payload에 포함된다.
paper_default에 한해 legacy key fallback 후보를 처리할 수 있다.
non-default account는 legacy fallback을 사용하지 않는다.
dry-run summary에 account_id와 external_key가 표시된다.
Manual Execution/Review importer와 status sync는 변경되지 않는다.
Notion actual write/export는 실행하지 않는다.
paper 원장, DB, outputs는 수정하지 않는다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 생성/수정한 파일
3. 적용한 read-only export 대상
4. 신규 External Key 형식
5. Account ID property payload 처리
6. legacy fallback 정책
7. --account-id CLI 동작
8. dry-run summary 변경
9. 테스트 결과
10. importer/status sync 변경 여부
11. Notion write/export 실행 여부
12. outputs 변경 여부
13. 다음 MFU 제안
```

반드시 명시:

```text
이번 PAPER15-3E-3은 Notion read-only exporter의 Account ID property 및 account-aware External Key 구현이며, Manual Execution/Review importer 변경, status sync 변경, Notion row migration preview, paper 원장 수정, writer path 적용은 포함하지 않는다.
```

END MFU-PAPER15-3E-3_NOTION_EXPORTER_EXTERNAL_KEY_NAMESPACE
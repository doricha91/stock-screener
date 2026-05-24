## Purpose

이번 PAPER14-4는 Daily Plan read-only Notion export 추가 작업이며, Daily Review Summary, Performance Summary, Manual Review 입력 연동은 포함하지 않는다.

- source of truth = CSV / JSON / Markdown / SQLite
- Notion = presentation / review layer

## Daily Plan Source Artifact

Daily Plan export는 새 원천 파일을 만들지 않는다. 기존 paper 운영 루프에서 생성되는 아래 산출물을 그대로 읽는다.

- Markdown: `outputs/paper_test/daily_action_plan_YYYYMMDD.md`
- Config snapshot JSON: `outputs/paper_test/config_snapshots/paper_config_snapshot_YYYYMMDD.json`

확정 근거:

- `scripts/paper.py`의 `plan`, `preview` 단계가 `scripts/run_paper_daily_plan.py`를 호출한다.
- `scripts/run_paper_daily_plan.py`는 Daily Plan Markdown과 config snapshot JSON을 함께 생성한다.

필드 출처:

- `plan_date`: config snapshot JSON의 `plan_date`
- `regime`: config snapshot JSON의 `market_state.regime` 우선, 없으면 `market_status_summary.regime`
- `confirmed_trade_count`: Daily Plan Markdown의 `## 4.` 확정 매매 지시 테이블 row 수
- `review_item_count`: Daily Plan Markdown의 `## 4-0.` review-only table row 수
- `warning_count`: Daily Plan Markdown의 `## 4-0-1.` warnings table row 수

## Notion Data Source Key

- data source key: `daily_plans`
- env override: `NOTION_DAILY_PLANS_DATA_SOURCE_ID`

`config/notion_settings.example.json`에도 `data_sources.daily_plans`를 추가한다.

## Property Mapping

`config/notion_property_mapping.example.json`

- `name` -> `Name`
- `external_key` -> `External Key`
- `plan_date` -> `Plan Date`
- `regime` -> `Regime`
- `confirmed_trade_count` -> `Confirmed Trade Count`
- `review_item_count` -> `Review Item Count`
- `warning_count` -> `Warning Count`
- `markdown_path` -> `Markdown Path`
- `json_path` -> `JSON Path`
- `schema_version` -> `Schema Version`
- `synced_at` -> `Synced At`
- `sync_status` -> `Sync Status`

## Property Type

- `Name`: `title`
- `External Key`: `rich_text`
- `Plan Date`: `date`
- `Regime`: `select`
- `Confirmed Trade Count`: `number`
- `Review Item Count`: `number`
- `Warning Count`: `number`
- `Markdown Path`: `rich_text`
- `JSON Path`: `rich_text`
- `Schema Version`: `rich_text`
- `Synced At`: `rich_text`
- `Sync Status`: `select`

주의:

- `External Key`는 `rich_text`
- `Synced At`은 `date`가 아니라 `rich_text`

## Select Option Candidates

- `Regime`
  - 확정 후보: `BULL`, `BEAR`, `PANIC`
  - 설명: config snapshot의 regime 값을 그대로 upper-case select로 보낸다.
- `Sync Status`
  - 확정: `SYNCED`

select option 누락은 schema validation에서 기본적으로 `WARNING` 대상이다. 속성 자체가 없거나 타입이 다르면 `FAIL`이다.

## External Key Policy

- format: `daily_plan:{plan_date}`
- example: `daily_plan:2026-05-20`

Upsert policy:

- 0 rows found -> `created`
- 1 row found -> `updated`
- 2+ rows found -> error

## CLI Usage

지원 명령:

```cmd
python scripts\export_paper_to_notion.py --daily-plan --dry-run --json
python scripts\export_paper_to_notion.py --daily-plan --json
python scripts\dev\validate_notion_schema.py --daily-plan
python scripts\dev\validate_notion_schema.py --all --json
```

현재 구현에서는 `--all` export에 `daily-plan`을 자동 포함하지 않는다.

이유:

- PAPER14-4 직후에는 Daily Plan export를 개별 실행으로 분리해 원인 분석을 단순화한다.
- 기존 PAPER14-3 대상의 동작 범위를 불필요하게 넓히지 않는다.

## Dry-Run / Actual Export Policy

- `--dry-run`은 payload summary만 생성하고 Notion write를 하지 않는다.
- actual export는 사용자가 명시적으로 허용한 경우에만 실행한다.
- page body는 짧은 summary paragraph만 작성한다.
- page body 고도화는 이번 범위에 포함하지 않는다.

## Excluded Scope

- Daily Review Summary export
- Performance Summary export
- Manual Review 입력 연동
- Notion DB 자동 생성
- Notion schema migration
- page body 고도화

## Test Result

권장 검증:

```cmd
python -m py_compile core\notion_exporters.py
python -m py_compile core\notion_schema_validator.py
python -m py_compile scripts\export_paper_to_notion.py
python -m py_compile scripts\dev\validate_notion_schema.py

python -m pytest tests\test_notion_exporters.py tests\test_notion_schema_validator.py tests\test_notion_settings.py tests\test_notion_mapping.py tests\test_notion_client.py -q

python scripts\export_paper_to_notion.py --daily-plan --dry-run --json
```

## Remaining Risks

- Daily Plan count 3종은 현재 Markdown section/table 구조에 의존한다.
- Daily Plan 전용 JSON artifact가 아직 없으므로, 향후 Markdown 포맷이 바뀌면 parser도 함께 조정해야 한다.
- `daily_plans` data source id가 아직 설정되지 않은 환경에서는 actual schema read를 건너뛰고 warning으로 보고할 수 있다.

## 4B Page Body Enrichment

이번 PAPER14-4B는 Daily Plan page body enrichment 작업이며, Daily Review Summary, Performance Summary, Manual Review 입력 연동, 신규 DB 추가는 포함하지 않는다.

원칙:

- DB property는 필터/정렬용 요약만 유지한다.
- 상세 운영 내용은 page body에 넣는다.
- source of truth는 여전히 원천 Markdown / JSON이다.
- Notion은 presentation / review layer다.

### Page Body Structure

Daily Plan page body는 아래 순서로 구성한다.

- `오늘의 운영 요약`
- `확정 거래`
- `검토 필요 항목`
- `경고`
- `원천 파일`

요약 섹션에는 아래를 포함한다.

- `Plan Date`
- `Regime`
- `Confirmed Trades`
- `Review Items`
- `Warnings`
- 가능하면 Markdown `## 1.` 시장 요약 섹션의 앞부분 1~3줄

### Markdown Parsing Basis

섹션 기준은 실제 source Markdown의 heading prefix를 따른다.

- 시장 요약: `## 1.`
- 확정 거래: `## 4.`
- 검토 필요 항목: `## 4-0.`
- 경고: `## 4-0-1.`

테이블은 Notion native table로 변환하지 않고, bullet/plain text 중심으로 변환한다.

표시 예:

- 확정 거래: `BUY ABC 10 @ $12.34 - ENTRY_SIGNAL`
- 검토 항목: `BRK-B 20 @ $480.90 - REVIEW_EXIT (manual check)`
- 경고: `GEN [HIGH] WARNING_HIGHEST_PRICE_INCONSISTENT - highest mismatch`

### Fallback Policy

- 섹션 파싱 실패는 export 전체 실패로 취급하지 않는다.
- 최소 summary와 source path는 항상 body에 남긴다.
- 섹션을 찾지 못하면 fallback paragraph를 넣는다.

예:

- `Section ## 4. could not be parsed. See source markdown path.`

### Why Properties Are Not Expanded

이번 4B에서는 Daily Plans DB property를 늘리지 않는다.

이유:

- 종목별 상세 property는 필터/정렬보다 body reading 용도에 가깝다.
- 상세 trade / warning을 property로 올리면 schema가 빠르게 비대해진다.
- Trade Items / Warning Items 같은 별도 DB는 이번 범위가 아니다.

### 4B Test Focus

- 운영 요약 섹션이 body에 포함되는지
- 확정 거래 / 검토 / 경고 섹션이 있으면 body에 포함되는지
- 섹션이 없어도 fallback body로 export payload가 계속 생성되는지
- source markdown/json path가 body 하단에 포함되는지

### 4B Remaining Risks

- 현재 parser는 heading prefix와 Markdown table 구조가 유지된다는 전제에 기대고 있다.
- 향후 Daily Plan Markdown 서식이 크게 바뀌면 parser와 테스트를 같이 갱신해야 한다.

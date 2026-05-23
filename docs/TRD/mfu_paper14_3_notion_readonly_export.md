# MFU-PAPER14-3 Notion Read-only Export

## Scope

이번 PAPER14-3은 Weekly Reports / Benchmark Reports / Account Snapshots의 Notion read-only export 구현이며, review 입력 연동과 paper 원장 수정은 포함하지 않는다.

포함:

- weekly report export
- benchmark report export
- latest account snapshot export
- dry-run support
- smoke create-path verification

제외:

- Daily Plan export
- Daily Review Summary export
- Performance Summary export
- Manual Review import/export
- Notion DB auto-creation

## Data source ID terminology

최신 Notion API 기준으로 설정과 환경변수는 `data source id`를 기준으로 사용한다.

공식 환경변수:

- `NOTION_WEEKLY_REPORTS_DATA_SOURCE_ID`
- `NOTION_BENCHMARK_REPORTS_DATA_SOURCE_ID`
- `NOTION_ACCOUNT_SNAPSHOTS_DATA_SOURCE_ID`
- `NOTION_SMOKE_DATA_SOURCE_ID`

공식 설정 키:

- `config/notion_settings.json`
- root key: `data_sources`

과거 `databases` 키는 호환용 fallback으로만 유지한다.

## CLI

- `python scripts/export_paper_to_notion.py --weekly`
- `python scripts/export_paper_to_notion.py --benchmark`
- `python scripts/export_paper_to_notion.py --account-snapshot`
- `python scripts/export_paper_to_notion.py --all`
- `python scripts/export_paper_to_notion.py --dry-run`

## External keys

- weekly: `weekly_report:{actual_start}:{actual_end}`
- benchmark: `benchmark:{latest_snapshot_date}:{run_mode}`
- account snapshot: `account_snapshot:{snapshot_date}`

## Safety

- source files are read-only
- Notion write occurs only when `--dry-run` is not used
- paper ledger CSV and `outputs/front_test` are not modified

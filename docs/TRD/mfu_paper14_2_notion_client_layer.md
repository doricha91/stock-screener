# MFU-PAPER14-2 Notion Client Layer

## Scope

이번 PAPER14-2는 Notion 공통 client/settings/mapping/upsert 레이어 구현이며, 실제 paper report export는 포함하지 않는다.

포함:

- settings loader
- property mapping loader
- Notion API client
- External Key 기반 upsert helper
- smoke test script 정리

제외:

- Weekly / Benchmark / Account snapshot export
- Notion data source 자동 생성
- review 입력 연동

## Implemented pieces

- `core/notion_settings.py`
- `core/notion_mapping.py`
- `core/notion_client.py`
- `scripts/dev/notion_smoke_test.py`

## Terminology

- 최신 Notion API 기준으로 설정 레이어는 `data source id`를 사용한다.
- 운영용 환경변수 예:
  - `NOTION_SMOKE_DATA_SOURCE_ID`
  - `NOTION_WEEKLY_REPORTS_DATA_SOURCE_ID`
  - `NOTION_BENCHMARK_REPORTS_DATA_SOURCE_ID`
  - `NOTION_ACCOUNT_SNAPSHOTS_DATA_SOURCE_ID`
- `config/notion_settings.json`에서는 `data_sources`를 공식 키로 사용한다.
- 과거 `databases` 키는 호환용 fallback으로만 유지한다.

## Security notes

- token은 `NOTION_TOKEN` 환경변수로만 읽는다.
- 실제 `config/notion_settings.json`은 repo에 커밋하지 않는다.
- 실제 property override 파일이 필요하면 `config/notion_property_mapping.json`을 로컬 전용으로 둔다.
- 에러 메시지와 로그에 token value를 출력하지 않는다.

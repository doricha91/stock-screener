# MFU-PAPER14-3A 작업 지시문
# 목표: Notion 설정 레이어의 database id 용어를 data source id 기준으로 정리한다.
# 주의: 이번 작업에서는 실제 Notion 운영 DB에 export하지 않는다. actual write 검증은 PAPER14-3D에서 한다.

## 배경

현재 PAPER14-3 exporter는 최신 Notion API 흐름에 맞춰 data_source_id를 사용하고 있다.

예:
- export_weekly_report_to_notion()
  - env_override="NOTION_WEEKLY_REPORTS_DATA_SOURCE_ID"
  - 반환값을 data_source_id 변수에 저장
  - _upsert_or_dry_run(..., data_source_id=...)
- _upsert_or_dry_run()
  - data_source_id가 없으면 "Notion data source id is required..." 에러
  - client.upsert_page_by_external_key(data_source_id=...) 호출

그런데 core/notion_settings.py는 아직 아래처럼 database 용어를 사용한다.

- NotionSettings.databases
- get_notion_database_id()
- "Missing Notion database id for key ..." 에러 메시지
- config/notion_settings.json의 "databases" 키

이 때문에 실제로는 data source id를 넣어야 하는데 database id를 넣는 것처럼 오해할 위험이 있다.

## 작업 목표

1. Notion 설정 레이어의 공식 명칭을 data source id 기준으로 정리한다.
2. 기존 databases 설정은 바로 제거하지 말고 deprecated fallback으로 유지한다.
3. env override 우선순위는 유지한다.
4. 기존 exporter 동작은 깨지지 않게 한다.
5. 실제 Notion write/export는 실행하지 않는다.

## 포함 범위

### 1. core/notion_settings.py 수정

다음 구조를 목표로 한다.

- NotionSettings.databases → NotionSettings.data_sources로 전환
- load_notion_settings()는 config의 "data_sources"를 우선 읽는다.
- 기존 "databases" 키는 deprecated fallback으로 허용한다.
- get_notion_data_source_id() 함수를 새로 만든다.
- 기존 get_notion_database_id()는 호환용 wrapper로 남기되, 내부에서 get_notion_data_source_id()를 호출하게 한다.
- 에러 메시지는 database id가 아니라 data source id로 수정한다.

권장 우선순위:

1. env_override 값
2. settings.data_sources[database_key]
3. deprecated settings.databases 또는 config의 "databases" fallback

단, dataclass 구조를 바꿀 때 기존 테스트와 호출부가 깨지지 않도록 최소 변경으로 처리한다.
필요하다면 databases property를 deprecated alias로 남긴다.

예상 신규 함수명:

- get_notion_data_source_id(settings, data_source_key, env=None, env_override=None)

기존 함수는 제거하지 않는다.

- get_notion_database_id(...)  # deprecated wrapper

### 2. 호출부 정리

아래 파일들을 검색해서 database_id 용어가 잘못 남아 있는지 확인한다.

- core/notion_exporters.py
- core/notion_client.py
- scripts/export_paper_to_notion.py
- scripts/dev/notion_smoke_test.py
- tests/test_notion_settings.py
- tests/test_notion_exporters.py
- config/notion_settings.example.json
- docs/TRD/mfu_paper14_3_notion_readonly_export.md
- docs/operations 관련 Notion 문서가 있으면 함께 확인

notion_exporters.py에서는 가능하면 get_notion_database_id import를 get_notion_data_source_id로 바꾼다.

예:
- from core.notion_settings import ..., get_notion_data_source_id

그리고 아래 호출을 data source 기준으로 변경한다.

- get_notion_database_id(...) → get_notion_data_source_id(...)

단, 동작은 동일해야 한다.

### 3. config 예시 수정

config/notion_settings.example.json이 있다면 아래처럼 data_sources를 공식 예시로 변경한다.

{
  "enabled": true,
  "token_env": "NOTION_TOKEN",
  "data_sources": {
    "weekly_reports": "",
    "benchmark_reports": "",
    "account_snapshots": "",
    "smoke_test": ""
  }
}

기존 databases는 example에서는 제거하거나, 주석이 불가능한 JSON 특성을 고려해 문서에서 deprecated라고 설명한다.
실제 로더에서는 databases fallback을 유지한다.

### 4. 문서 수정

문서에서 다음 표현을 정리한다.

- database id → data source id
- Notion DB ID → Notion data source ID
- NOTION_*_DATA_SOURCE_ID env를 공식 설정 방식으로 명시

특히 다음 내용을 명확히 남긴다.

- Notion에서 사람이 복사해야 하는 값은 최신 API 기준 data source id이다.
- 현재 env 변수명:
  - NOTION_WEEKLY_REPORTS_DATA_SOURCE_ID
  - NOTION_BENCHMARK_REPORTS_DATA_SOURCE_ID
  - NOTION_ACCOUNT_SNAPSHOTS_DATA_SOURCE_ID
- config에서는 data_sources를 우선 사용한다.
- databases 키는 과거 호환용 fallback이다.

## 제외 범위

이번 MFU-PAPER14-3A에서는 절대 하지 않는다.

- 실제 Notion Weekly Reports export 실행
- 실제 Benchmark Reports export 실행
- 실제 Account Snapshots export 실행
- Notion DB schema validation 추가
- select option 전체 조사
- Notion DB 자동 생성
- paper 원장 CSV 수정
- report JSON/Markdown 재생성
- Daily Plan / Daily Review / Performance Summary export 구현
- Manual Review import 구현

## 테스트

최소 아래 테스트를 실행한다.

1. 설정 관련 테스트

python -m pytest tests/test_notion_settings.py -q

2. Notion export 관련 기존 테스트

python -m pytest tests/test_notion_exporters.py tests/test_notion_client.py tests/test_notion_mapping.py -q

3. 컴파일 확인

python -m py_compile core/notion_settings.py
python -m py_compile core/notion_exporters.py
python -m py_compile scripts/export_paper_to_notion.py
python -m py_compile scripts/dev/notion_smoke_test.py

4. dry-run 확인만 수행

아래는 Notion write가 없어야 한다.

python scripts/export_paper_to_notion.py --weekly --dry-run --json
python scripts/export_paper_to_notion.py --benchmark --dry-run --json
python scripts/export_paper_to_notion.py --account-snapshot --dry-run --json

주의:
- 이번 단계에서 --weekly, --benchmark, --account-snapshot을 dry-run 없이 실행하지 않는다.

## 완료 조건

작업 완료 보고에는 아래를 포함한다.

1. 변경한 파일 목록
2. 공식 설정 키가 data_sources로 바뀌었는지
3. databases fallback을 유지했는지
4. get_notion_data_source_id() 추가 여부
5. get_notion_database_id() 호환 wrapper 유지 여부
6. env override 우선순위 유지 여부
7. 테스트 결과
8. dry-run 결과
9. 실제 Notion write/export를 하지 않았다는 확인
10. 남은 리스크

## 예상 리스크

- dataclass 필드명을 바꾸면서 기존 테스트가 깨질 수 있다.
- 문서 일부에 database id 표현이 남을 수 있다.
- config/notion_settings.json을 실제 운영 파일로 쓰는 경우, databases fallback이 없으면 기존 로컬 설정이 깨질 수 있다.
- 최신 Notion API 기준으로는 data source id가 맞지만, 기존 코드/문서에 database라는 이름이 남아 있어 혼동 가능성이 있다.

## 핵심 원칙

이번 작업은 기능 확장이 아니라 명칭과 설정의 안전성 개선이다.
외부 Notion에 쓰는 작업은 하지 말고, 로컬 테스트와 dry-run까지만 수행한다.
# MFU-PAPER14-2 작업 지시문: Notion client / settings / mapping / upsert helper 구현

## 목적

PAPER14-2의 목표는 PAPER14-1에서 설계한 Notion 연동 방향을 바탕으로, 실제 report export 전에 사용할 공통 기반 레이어를 구현하는 것이다.

이번 단계에서는 Notion API 인증, 설정 로딩, property mapping, External Key 기반 upsert helper를 구현한다.

반드시 명시:

```text
이번 PAPER14-2는 Notion 공통 client/settings/mapping/upsert 레이어 구현이며, weekly/benchmark/account snapshot 실제 export, Notion DB 자동 생성, review 입력 연동은 포함하지 않는다.
```

## 배경

수동 smoke test 결과:

```text
1차 실행: CREATED
2차 실행: UPDATED
```

즉 아래가 검증됐다.

```text
NOTION_TOKEN 정상
NOTION_SMOKE_DATA_SOURCE_ID 정상
Notion DB connection 권한 정상
External Key 기반 create/update 방향 정상
```

이제 smoke test 임시 코드를 프로젝트용 공통 레이어로 정리한다.

## 구현 파일

추가 후보:

```text
core/notion_client.py
core/notion_settings.py
core/notion_mapping.py
scripts/dev/notion_smoke_test.py
tests/test_notion_client.py
tests/test_notion_settings.py
tests/test_notion_mapping.py
docs/TRD/mfu_paper14_2_notion_client_layer.md
```

수정 후보:

```text
tests/test_paper_cli.py
.gitignore
config/notion_settings.example.json
config/notion_property_mapping.example.json
```

## 핵심 구현 범위

### 1. Notion settings loader

`config/notion_settings.example.json` 구조를 기준으로 설정을 읽는다.

예:

```json
{
  "enabled": false,
  "token_env": "NOTION_TOKEN",
  "databases": {
    "smoke_test": "",
    "weekly_reports": "",
    "benchmark_reports": "",
    "account_snapshots": ""
  }
}
```

요구사항:

```text
실제 token 값은 파일에서 읽지 않는다.
token_env 이름만 설정 파일에 둔다.
실제 token은 os.environ에서 읽는다.
notion_settings.json이 없으면 명확한 에러 또는 disabled 상태 처리.
실제 notion_settings.json은 gitignore 대상.
```

### 2. Property mapping loader

`config/notion_property_mapping.example.json` 구조를 기준으로 mapping을 읽는다.

예:

```json
{
  "smoke_test": {
    "external_key": "External Key",
    "name": "Name",
    "status": "Status",
    "smoke_date": "Smoke Date",
    "value": "Value",
    "note": "Note"
  }
}
```

요구사항:

```text
Python 코드에 Notion property name을 흩뿌리지 않는다.
mapping 파일을 통해 JSON/internal field -> Notion property name으로 변환한다.
추후 한글 property name으로 바뀌어도 mapping만 수정하면 되게 한다.
```

### 3. Notion client

`core/notion_client.py`에 최소 client를 구현한다.

기능 후보:

```text
get_bot_user()
retrieve_data_source(data_source_id)
query_by_external_key(data_source_id, external_key, external_key_property)
create_page(data_source_id, properties, children=None)
update_page(page_id, properties)
upsert_page_by_external_key(...)
```

요구사항:

```text
Authorization: Bearer token 사용
Notion-Version은 기존 smoke test에서 사용한 값 또는 프로젝트 상수로 관리
HTTP error 발생 시 status code와 response body를 포함한 명확한 예외 발생
timeout 설정
requests.Session 사용 가능
```

### 4. External Key upsert helper

공통 upsert 정책:

```text
External Key가 있으면 update
External Key가 없으면 create
```

함수 예:

```text
upsert_page_by_external_key(
    data_source_id,
    external_key,
    external_key_property,
    properties,
    children=None
)
```

동작:

```text
1. External Key로 기존 row 조회
2. 0개면 create
3. 1개면 update
4. 2개 이상이면 중복 위험으로 error 또는 first update + warning 중 하나 선택
```

권장:

```text
2개 이상이면 error 처리
```

이유:

```text
Notion 중복 row는 운영 기록 신뢰성을 떨어뜨리므로 조용히 넘어가면 안 된다.
```

### 5. Smoke test script 정리

기존 임시 smoke test를 `scripts/dev/notion_smoke_test.py`로 정리한다.

동작:

```text
.env / 환경변수에서 NOTION_TOKEN 읽기
config/notion_settings.json 또는 환경변수에서 smoke data source id 읽기
core/notion_client.py의 upsert helper 사용
첫 실행 create, 두 번째 실행 update 가능
```

단, 실제 paper report export는 하지 않는다.

## CLI 범위

이번 단계에서는 `paper.py notion-export` 같은 운영 명령은 만들지 않는다.

허용:

```text
python scripts/dev/notion_smoke_test.py
```

선택적으로 dry validation 명령:

```text
python scripts/dev/notion_smoke_test.py --check-only
```

## 보안 요구사항

반드시 확인:

```text
.env는 gitignore
config/notion_settings.json은 gitignore
config/notion_settings.example.json은 커밋 가능
config/notion_property_mapping.example.json은 커밋 가능
토큰을 출력하지 않음
테스트 로그에 token 일부도 출력하지 않음
```

## 제외 범위

이번 단계에서 하지 않는다.

```text
Weekly Reports export 구현
Benchmark Reports export 구현
Account Snapshots export 구현
Daily Plan export 구현
Markdown -> Notion block 변환 구현
Notion DB 자동 생성
Notion schema migration
review import
review append 연동
paper 원장 CSV 수정
reports 재생성
outputs/front_test 수정
```

## 테스트

mock 기반 테스트를 작성한다. 실제 Notion API 호출은 unit test에서 하지 않는다.

필수 테스트:

```text
1. settings loader가 token_env를 읽고 환경변수 token을 가져옴
2. token이 없으면 명확한 에러
3. database id가 없으면 명확한 에러
4. property mapping loader가 mapping을 읽음
5. 누락된 mapping key 처리
6. query_by_external_key payload가 올바름
7. 기존 row 0개면 create 호출
8. 기존 row 1개면 update 호출
9. 기존 row 2개 이상이면 error
10. HTTP 4xx/5xx 응답에서 명확한 예외
11. token 값이 로그/예외 메시지에 노출되지 않음
12. paper 원장 CSV와 outputs/front_test를 수정하지 않음
```

실제 API smoke test는 수동 검증으로 분리한다.

## 검증 명령

```text
set PYTHONPATH=.

python -m pytest tests/test_notion_client.py tests/test_notion_settings.py tests/test_notion_mapping.py -q
python -m py_compile core/notion_client.py
python -m py_compile core/notion_settings.py
python -m py_compile core/notion_mapping.py
python -m py_compile scripts/dev/notion_smoke_test.py

python scripts/dev/notion_smoke_test.py
python scripts/dev/notion_smoke_test.py
```

두 번째 smoke test 실행에서 create가 아니라 update가 되어야 한다.

주의:

```text
scripts/dev/notion_smoke_test.py는 Notion의 smoke test DB에 테스트 row를 create/update한다.
paper 원장 CSV는 수정하지 않는다.
```

## 성공 기준

```text
Notion settings loader가 구현된다.
Notion property mapping loader가 구현된다.
Notion client가 구현된다.
External Key 기반 upsert helper가 구현된다.
기존 smoke test가 공통 client를 사용하도록 정리된다.
첫 smoke 실행은 create, 두 번째 실행은 update가 가능하다.
token과 실제 DB ID는 커밋되지 않는다.
Weekly/Benchmark 등 실제 report export는 아직 구현하지 않는다.
paper 원장 CSV와 outputs/front_test는 수정되지 않는다.
테스트가 통과한다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 변경 파일
3. settings loader 구현 내용
4. mapping loader 구현 내용
5. Notion client 구현 내용
6. upsert helper 정책
7. smoke test script 변경 내용
8. 보안 처리
9. 제외한 항목
10. 테스트 결과
11. 실제 smoke test 실행 결과
12. Notion row create/update 여부
13. paper 원장 CSV 변경 여부
14. outputs/front_test 변경 여부
15. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER14-2는 Notion 공통 client/settings/mapping/upsert 레이어 구현이며, 실제 paper report export는 포함하지 않는다.
```
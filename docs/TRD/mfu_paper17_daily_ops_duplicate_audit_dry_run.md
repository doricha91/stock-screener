# PAPER17-4A Daily Ops Status Duplicate Audit Dry-run

## Purpose

PAPER17-4A는 `daily_ops_status` actual export 전에 특정 `account_id` / `status_date` / `External Key` 기준으로 Notion row 매칭 상태를 read-only로 확인하는 duplicate audit dry-run interface를 추가한다.

이 audit은 actual 실행 여부를 단독으로 결정하지 않는다. Command Gate SOP의 전체 preflight 중 duplicate risk 확인 단계만 담당한다.

## Scope

Scope:

- target은 `daily_ops_status` 하나로 제한한다.
- Notion row query/read만 수행한다.
- External Key 기준 match count를 분류한다.
- JSON 결과에 `write_executed=false`를 항상 포함한다.
- unit test는 fake client만 사용한다.

Non-scope:

- Notion write
- actual export/sync
- duplicate cleanup
- schema/view drift 자동 점검
- detail exporter duplicate audit
- Manual Execution/Review status sync duplicate audit

## CLI

권장 CLI:

```cmd
python scripts\dev\audit_notion_duplicates.py --target daily_ops_status --account-id paper_sandbox --date 2026-05-20 --json
```

선택 옵션:

```cmd
--external-key daily_ops_status:paper_sandbox:2026-05-20
--expected-page-id <page_id>
--json
```

정책:

- `--target`은 `daily_ops_status`만 허용한다.
- `--account-id`는 필수다.
- `--date` 또는 `--external-key`가 필요하다.
- `--external-key`가 제공되면 `--date`도 요구해 account/date/key 정합성을 확인한다.
- actual/write 관련 옵션은 없다.

## Input Contract

입력:

- `target`: `daily_ops_status`
- `account_id`: audited account id
- `date`: `YYYY-MM-DD` 또는 `YYYYMMDD`
- `external_key`: optional, 제공 시 expected key와 일치해야 함
- `expected_page_id`: optional, update rerun에서 예상 page 검증용

External Key 형식:

```text
daily_ops_status:{account_id}:{status_date}
```

예:

```text
daily_ops_status:paper_sandbox:2026-05-20
```

## Output Contract

JSON 출력 최소 필드:

```json
{
  "target": "daily_ops_status",
  "account_id": "paper_sandbox",
  "status_date": "2026-05-20",
  "external_key": "daily_ops_status:paper_sandbox:2026-05-20",
  "match_count": 1,
  "page_ids": ["..."],
  "classification": "update_candidate",
  "recommended_action": "safe_to_update_after_required_preflight",
  "write_executed": false
}
```

classification 후보:

- `create_candidate`
- `update_candidate`
- `duplicate_blocker`
- `manual_review_required`
- `settings_error`
- `query_error`

recommended_action 후보:

- `safe_to_create_after_required_preflight`
- `safe_to_update_after_required_preflight`
- `stop_actual_duplicate_detected`
- `stop_actual_manual_review_required`
- `stop_actual_settings_error`
- `stop_actual_query_error`

## Classification Rules

판정 규칙:

| Condition | Classification | Recommended Action |
| --- | --- | --- |
| `match_count = 0` | `create_candidate` | `safe_to_create_after_required_preflight` |
| `match_count = 1` | `update_candidate` | `safe_to_update_after_required_preflight` |
| `match_count >= 2` | `duplicate_blocker` | `stop_actual_duplicate_detected` |
| `expected_page_id` provided and actual single page differs | `manual_review_required` | `stop_actual_manual_review_required` |
| `external_key` / `account_id` / `date` mismatch | `manual_review_required` | `stop_actual_manual_review_required` |
| settings load/data source id error | `settings_error` | `stop_actual_settings_error` |
| Notion query error | `query_error` | `stop_actual_query_error` |

모든 결과는 `write_executed=false`를 포함한다.

## Read-only Safety Policy

Read-only safety:

- `query_by_external_key`만 사용한다.
- `create_page`를 호출하지 않는다.
- `update_page`를 호출하지 않는다.
- `upsert_page_by_external_key`를 호출하지 않는다.
- status sync actual을 실행하지 않는다.
- export actual을 실행하지 않는다.
- Notion property나 row를 수정하지 않는다.

## Example Outputs

0건:

```json
{
  "classification": "create_candidate",
  "recommended_action": "safe_to_create_after_required_preflight",
  "match_count": 0,
  "page_ids": [],
  "write_executed": false
}
```

1건:

```json
{
  "classification": "update_candidate",
  "recommended_action": "safe_to_update_after_required_preflight",
  "match_count": 1,
  "page_ids": ["page-id"],
  "write_executed": false
}
```

2건 이상:

```json
{
  "classification": "duplicate_blocker",
  "recommended_action": "stop_actual_duplicate_detected",
  "match_count": 2,
  "page_ids": ["page-1", "page-2"],
  "write_executed": false
}
```

## Test Coverage

Unit test coverage:

- External Key 생성/정규화
- 0건 -> `create_candidate`
- 1건 -> `update_candidate`
- 2건 이상 -> `duplicate_blocker`
- expected_page_id mismatch -> `manual_review_required`
- account/date/external_key mismatch -> `manual_review_required`
- `write_executed=false`
- unsupported target CLI failure

Tests use fake clients and do not call the Notion API.

## Remaining Limitations

Limitations:

- 이번 audit은 `daily_ops_status` 한정이다.
- duplicate audit은 schema validation을 대체하지 않는다.
- schema validation은 duplicate audit을 대체하지 않는다.
- audit PASS만으로 actual 실행이 허용되는 것은 아니다.
- Command Gate SOP의 전체 preflight를 통과해야 actual 후보가 될 수 있다.
- 실제 Notion read smoke는 이번 기본 검증에서 실행하지 않는다.

## PAPER17-4B Recommendation

PAPER17-4B 추천:

- 실제 Notion read-only smoke를 별도 승인하에 1회 수행한다.
- `paper_sandbox` / `2026-05-20` 기준 duplicate audit 결과를 기록한다.
- 이후 detail exporter target으로 audit 범위를 확장할지 결정한다.
- actual export rerun은 계속 별도 승인 대상으로 둔다.

# MFU-PAPER14-3B Notion Schema Contract

## Scope

이번 PAPER14-3B는 Weekly / Benchmark / Account Snapshot Notion DB의 속성명, 속성 타입, select option 후보를 정리하는 문서화 작업이며, 실제 Notion export/write는 포함하지 않는다.

대상 DB:

- Weekly Reports
- Benchmark Reports
- Account Snapshots

비포함:

- actual Notion export/write
- Notion DB 자동 생성
- schema validation API 구현
- Daily Plan / Daily Review / Performance Summary / Manual Review 연동

## Contract Rules

- Notion 설정과 exporter는 `database id`가 아니라 `data source id`를 사용한다.
- exporter payload 기준 타입을 Notion UI schema와 맞춘다.
- 비율/수익률/MDD는 `% 문자열`이 아니라 raw decimal `Number`로 보낸다.
- `Synced At`은 현재 `Date`가 아니라 `Rich text`다.
- `Official Run`은 현재 `Checkbox`가 아니라 `Select`다.
- `Symbols`는 현재 `Multi-select`가 아니라 `Rich text`다.
- `Markdown Path`, `JSON Path`는 `Rich text`다.
- select option은 아래 3단계로 구분한다.
  - `확정`: 코드에서 직접 생성되거나 fallback까지 포함해 강제되는 값
  - `관찰`: 현재 sample JSON/CSV 또는 테스트 fixture에서 확인된 값
  - `후보`: 문맥상 가능하지만 중앙 enum으로 완전히 고정되지 않은 값

## Weekly Reports DB

Source files:

- `outputs/paper_test/reports/paper_weekly_status_summary.json`
- `outputs/paper_test/reports/paper_weekly_status_summary.md`

External Key:

- `weekly_report:{period.actual_start}:{period.actual_end}`

| Notion Property | Type | Exporter Source Key | Value Source | Select Option | Required | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Name | Title | `name` | exporter synthetic title | - | Yes | `Weekly Report {actual_start} to {actual_end}` |
| External Key | Rich text | `external_key` | exporter synthetic key | - | Yes | upsert key |
| Period Start | Date | `period.actual_start` | weekly JSON | - | Yes | `YYYY-MM-DD` |
| Period End | Date | `period.actual_end` | weekly JSON | - | Yes | `YYYY-MM-DD` |
| Latest Snapshot Date | Date | `latest_snapshot_date` | weekly JSON | - | Yes | `YYYY-MM-DD` |
| Coverage Status | Select | `period.coverage_status` | weekly JSON / `core/paper_weekly_status.py` | see below | Yes | period coverage semantic |
| Overall Status | Select | `overall_status` | weekly JSON / `core/paper_weekly_status.py` | see below | Yes | overall weekly status |
| Snapshot Count | Number | `period.snapshot_count` | weekly JSON | - | Yes | integer number |
| End Equity | Number | `account_summary.end_equity_market_value` | weekly JSON | - | Yes | raw number |
| Equity Change % | Number | `account_summary.equity_change_pct` | weekly JSON | - | Yes | decimal number, Notion UI can display percent |
| Cash Ratio | Number | `account_summary.end_cash_ratio_market_value` | weekly JSON | - | Yes | decimal number |
| Trade Count | Number | `trade_summary.trade_count` | weekly JSON | - | Yes | integer number |
| Gap Count | Number | `operation_gaps.count` | exporter derived count | - | Yes | count of total gaps |
| High Gap Count | Number | `operation_gaps.high_count` | exporter derived count | - | Yes | count where severity=`HIGH` |
| Markdown Path | Rich text | `markdown_path` | exporter runtime path | - | Yes | current local relative path |
| JSON Path | Rich text | `json_path` | exporter runtime path | - | Yes | current local relative path |
| Schema Version | Rich text | `schema_version` | weekly JSON | - | Yes | observed `paper_weekly_status.v1` |
| Synced At | Rich text | `synced_at` | exporter runtime timestamp | - | Yes | ISO-like text, not Notion Date |
| Sync Status | Select | `sync_status` | exporter constant | see below | Yes | exporter currently writes one fixed value |

### Weekly Reports select options

#### Coverage Status

- 확정:
  - `FULL`
  - `PARTIAL`
  - `EMPTY`
- 관찰:
  - sample JSON: `PARTIAL`
  - test fixture: `FULL`, `EMPTY`, `PARTIAL`
- 후보:
  - 없음

#### Overall Status

- 확정:
  - `PASS`
  - `PASS_WITH_WARNINGS`
  - `FAIL`
- 관찰:
  - sample JSON: `PASS_WITH_WARNINGS`
  - test fixture: `PASS`, `PASS_WITH_WARNINGS`, `FAIL`
- 후보:
  - 없음

#### Sync Status

- 확정:
  - `SYNCED`
- 관찰:
  - exporter constant only
- 후보:
  - 없음

## Benchmark Reports DB

Source files:

- `outputs/paper_test/reports/paper_benchmark_comparison.json`
- `outputs/paper_test/reports/paper_benchmark_comparison.md`

External Key:

- `benchmark:{latest_snapshot_date}:{run_mode}`

| Notion Property | Type | Exporter Source Key | Value Source | Select Option | Required | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Name | Title | `name` | exporter synthetic title | - | Yes | `Benchmark Report {latest_snapshot_date} {run_mode}` |
| External Key | Rich text | `external_key` | exporter synthetic key | - | Yes | upsert key |
| Latest Snapshot Date | Date | `latest_snapshot_date` | benchmark JSON | - | Yes | `YYYY-MM-DD` |
| Run Mode | Select | `run_mode` | benchmark JSON / exporter uppercases | see below | Yes | select receives uppercase text |
| Official Run | Select | `official_run` | benchmark JSON / exporter bool mapping | see below | Yes | `Checkbox` 아님 |
| Availability Status | Select | `availability_status` | benchmark JSON / exporter fallback | see below | Yes | top-level availability only |
| Paper Return | Number | `summary.paper.paper_return` | benchmark JSON | - | Yes | decimal number |
| SPY Return | Number | `summary.benchmarks.SPY.benchmark_return` | benchmark JSON | - | Yes | decimal number |
| QQQ Return | Number | `summary.benchmarks.QQQ.benchmark_return` | benchmark JSON | - | Yes | decimal number |
| CASH Return | Number | `summary.benchmarks.CASH.benchmark_return` | benchmark JSON | - | Yes | decimal number |
| Excess vs SPY | Number | `summary.benchmarks.SPY.excess_return` | benchmark JSON | - | Yes | decimal number |
| Excess vs QQQ | Number | `summary.benchmarks.QQQ.excess_return` | benchmark JSON | - | Yes | decimal number |
| Excess vs CASH | Number | `summary.benchmarks.CASH.excess_return` | benchmark JSON | - | Yes | decimal number |
| Paper MDD | Number | `summary.paper.paper_max_drawdown` | benchmark JSON | - | Yes | decimal number |
| SPY MDD | Number | `summary.benchmarks.SPY.benchmark_max_drawdown` | benchmark JSON | - | Yes | decimal number |
| QQQ MDD | Number | `summary.benchmarks.QQQ.benchmark_max_drawdown` | benchmark JSON | - | Yes | decimal number |
| Markdown Path | Rich text | `markdown_path` | exporter runtime path | - | Yes | current local relative path |
| JSON Path | Rich text | `json_path` | exporter runtime path | - | Yes | current local relative path |
| Schema Version | Rich text | `schema_version` | benchmark JSON | - | Yes | observed `paper_benchmark_comparison.v1` |
| Synced At | Rich text | `synced_at` | exporter runtime timestamp | - | Yes | ISO-like text, not Notion Date |
| Sync Status | Select | `sync_status` | exporter constant | see below | Yes | exporter currently writes one fixed value |

### Benchmark Reports select options

#### Run Mode

- 확정:
  - exporter는 `run_mode` 문자열을 upper-case select로 보낸다
- 관찰:
  - sample JSON: `exploratory`
  - Notion select payload: `EXPLORATORY`
  - test fixture: `EXPLORATORY`
- 후보:
  - future mode values if `core/paper_benchmark_comparison.py` expands beyond current hardcoded `exploratory`

#### Official Run

- 확정:
  - `TRUE`
  - `FALSE`
- 관찰:
  - sample JSON: `false`
  - Notion select payload: `FALSE`
- 후보:
  - 없음

#### Availability Status

- 확정:
  - `AVAILABLE`
  - `INSUFFICIENT_DATA`
  - exporter fallback: `UNKNOWN`
- 관찰:
  - sample JSON: `AVAILABLE`
  - test fixture: `AVAILABLE`, `INSUFFICIENT_DATA`
- 후보:
  - 없음 for top-level property

주의:

- benchmark summary 내부 개별 심볼 status에는 `UNAVAILABLE`이 존재할 수 있다.
- 하지만 현재 Notion property `Availability Status`는 top-level `summary["availability_status"]`만 보며, per-symbol status를 직접 export하지 않는다.

#### Sync Status

- 확정:
  - `SYNCED`
- 관찰:
  - exporter constant only
- 후보:
  - 없음

## Account Snapshots DB

Source file:

- `outputs/paper_test/paper_account_snapshot.csv`

External Key:

- `account_snapshot:{snapshot_date}`

현재 exporter 정책:

- 기본 export는 최신 snapshot row 1개만 대상으로 한다.

| Notion Property | Type | Exporter Source Key | Value Source | Select Option | Required | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Name | Title | `name` | exporter synthetic title | - | Yes | `Account Snapshot {snapshot_date}` |
| External Key | Rich text | `external_key` | exporter synthetic key | - | Yes | upsert key |
| Snapshot Date | Date | `snapshot_date` | account snapshot CSV | - | Yes | `YYYY-MM-DD` |
| Initial Cash | Number | `initial_cash` | account snapshot CSV | - | Yes | raw number |
| Cash | Number | `cash` | account snapshot CSV | - | Yes | raw number |
| Total Equity Market Value | Number | `total_equity_market_value` | account snapshot CSV | - | Yes | raw number |
| Total Equity Cost Basis | Number | `total_equity_cost_basis` | account snapshot CSV | - | Yes | raw number |
| Unrealized PnL | Number | `unrealized_pnl` | account snapshot CSV | - | Yes | raw number |
| Cash Ratio Market Value | Number | `cash_ratio_market_value` | account snapshot CSV | - | Yes | decimal number |
| Cash Ratio Cost Basis | Number | `cash_ratio_cost_basis` | account snapshot CSV | - | Yes | decimal number |
| Position Count | Number | `position_count` | account snapshot CSV | - | Yes | integer number |
| Symbols | Rich text | `symbols` | account snapshot CSV | - | Yes | `Multi-select` 아님, pipe-joined text |
| Valuation Status | Select | `market_valuation_status` | account snapshot CSV / exporter uppercases | see below | Yes | empty value is coerced to `UNKNOWN` |
| Valuation Price Date | Date | `valuation_price_date` | account snapshot CSV | - | Yes | blank can become empty date payload |
| Synced At | Rich text | `synced_at` | exporter runtime timestamp | - | Yes | ISO-like text, not Notion Date |
| Sync Status | Select | `sync_status` | exporter constant | see below | Yes | exporter currently writes one fixed value |

### Account Snapshots select options

#### Valuation Status

- 확정:
  - `UNKNOWN` fallback when CSV value is blank
- 관찰:
  - sample CSV: `SUCCESS`
  - tests around account snapshot generation: `NOT_RUN`, `SUCCESS`, `FAILED`
- 후보:
  - row-driven uppercase values from `paper_account_snapshot.csv`
  - nearby paper reporting tests also observe `PARTIAL`, so future CSV rows may contain `PARTIAL`

주의:

- current exporter does not centrally enumerate all possible valuation statuses.
- safest Notion UI contract is to pre-create at least:
  - `SUCCESS`
  - `FAILED`
  - `NOT_RUN`
  - `UNKNOWN`
- if the broader paper pipeline starts persisting `partial`, add `PARTIAL` as a select option before actual export.

#### Sync Status

- 확정:
  - `SYNCED`
- 관찰:
  - exporter constant only
- 후보:
  - 없음

## Select Option Summary

### Weekly Reports

- Coverage Status:
  - 확정: `FULL`, `PARTIAL`, `EMPTY`
  - 관찰: `PARTIAL`
- Overall Status:
  - 확정: `PASS`, `PASS_WITH_WARNINGS`, `FAIL`
  - 관찰: `PASS_WITH_WARNINGS`
- Sync Status:
  - 확정: `SYNCED`

### Benchmark Reports

- Run Mode:
  - 확정: upper-case of `run_mode`
  - 관찰: `EXPLORATORY`
- Official Run:
  - 확정: `TRUE`, `FALSE`
  - 관찰: `FALSE`
- Availability Status:
  - 확정: `AVAILABLE`, `INSUFFICIENT_DATA`, exporter fallback `UNKNOWN`
  - 관찰: `AVAILABLE`
- Sync Status:
  - 확정: `SYNCED`

### Account Snapshots

- Valuation Status:
  - 확정: `UNKNOWN` fallback
  - 관찰: `SUCCESS`, `FAILED`, `NOT_RUN`
  - 후보: `PARTIAL`
- Sync Status:
  - 확정: `SYNCED`

## Operator Checklist Before Actual Export

Notion UI에서 사람이 먼저 확인할 것:

1. 각 DB는 `data source id` 기준으로 설정한다.
2. 속성명은 `config/notion_property_mapping.example.json`과 정확히 맞춘다.
3. `Synced At`는 `Rich text`로 만든다.
4. `Official Run`은 `Select`로 만든다.
5. `Symbols`는 `Rich text`로 만든다.
6. percent-like number fields는 exporter raw decimal을 받도록 `Number`로 만들고, 필요하면 Notion 표시 형식만 `%`로 지정한다.
7. `Valuation Status`는 최소 `SUCCESS`, `FAILED`, `NOT_RUN`, `UNKNOWN`을 미리 만든다.
8. `Availability Status`는 최소 `AVAILABLE`, `INSUFFICIENT_DATA`, `UNKNOWN`을 미리 만든다.


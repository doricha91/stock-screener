# MFU-PAPER12-3 Weekly Status Schema Stabilization

## Summary

이번 PAPER12-3은 weekly-status output schema stabilization 작업이며, Notion API 연동, HTML/CSV 생성, paper 원장 수정은 포함하지 않는다.

이번 단계의 목적은 `paper_weekly_status_summary.json`을 외부 시스템이 안정적으로 소비할 수 있는 고정 schema로 정리하는 것이다.

## Schema Changes

Top-level JSON 구조를 아래처럼 고정했다.

```json
{
  "schema_version": "paper_weekly_status.v1",
  "generated_at": "...",
  "period": {},
  "latest_snapshot_date": "...",
  "overall_status": "...",
  "operation_coverage": [],
  "account_summary": {},
  "position_summary": {},
  "trade_summary": {},
  "review_summary": {},
  "operation_gaps": [],
  "recommended_next_actions": [],
  "source_files": {},
  "limitations": []
}
```

`schema_version = paper_weekly_status.v1`를 추가해 추후 구조 변경 추적 기준으로 사용한다.

## Raw Value Policy

JSON에는 포맷 문자열 대신 raw value를 저장한다.

- 금액: `number`
- 비율: `%` 문자열이 아닌 decimal `number`
- 날짜: `YYYY-MM-DD`
- 상태: enum-like string

예:

- `equity_change_pct = -0.0017239`
- `end_equity_market_value = 99827.61`

Markdown만 사람이 읽기 쉬운 표시용 포맷을 허용한다.

## Period Semantics

`period`는 아래 필드를 가진다.

```json
{
  "basis": "snapshot_date",
  "requested_start": "YYYY-MM-DD|null",
  "requested_end": "YYYY-MM-DD|null",
  "actual_start": "YYYY-MM-DD|null",
  "actual_end": "YYYY-MM-DD|null",
  "included_snapshot_dates": [],
  "snapshot_count": 0,
  "coverage_status": "FULL|PARTIAL|EMPTY"
}
```

정책:

- `basis`는 고정으로 `snapshot_date`
- 기본 `--days N`은 최근 N개 snapshot row
- `coverage_status = FULL`:
  - 명시 범위에서 시작/종료가 요청 범위와 일치
  - 또는 기본 `--days`에서 충분한 snapshot row가 있음
- `coverage_status = PARTIAL`:
  - 요청 범위를 일부만 커버
  - 또는 available snapshot row가 요청 수보다 적음
- `coverage_status = EMPTY`:
  - 요청 범위에 snapshot row가 없음

## Source Files Metadata

`source_files`는 source provenance를 남긴다.

예:

```json
{
  "account_snapshot": {
    "path": "outputs/paper_test/paper_account_snapshot.csv",
    "exists": true,
    "latest_date": "2026-05-20",
    "row_count": 4
  }
}
```

현재 포함:

- `account_snapshot`
- `position_snapshot`
- `execution_log`
- `daily_review_summary`
- `performance_summary`
- `review_template`
- `review_validation_report`

## Operation Gap Standardization

`operation_gaps` 각 row는 아래 필드를 가진다.

```json
{
  "date": "YYYY-MM-DD",
  "code": "MISSING_REPORTS",
  "severity": "MEDIUM",
  "message": "..."
}
```

severity 허용값:

- `HIGH`
- `MEDIUM`
- `LOW`

예시 code:

- `UNKNOWN_OR_INCOMPLETE`
- `INCOMPLETE_COMMIT_SNAPSHOT`
- `MISSING_POSITION_SNAPSHOT`
- `REVIEW_VALIDATION_FAILED`
- `MISSING_REPORTS`
- `MISSING_REVIEW_TEMPLATE`
- `NO_TRADES_RECORDED`
- `HIGH_PRIORITY_REVIEW_PENDING`
- `NO_SNAPSHOTS_IN_RANGE`

## Markdown Changes

Markdown에는 아래를 명시한다.

- schema version
- period basis
- requested/actual period
- coverage status
- included snapshot dates
- source files summary

계산값은 사람이 읽기 쉽게 금액/비율 포맷을 적용하지만, JSON raw value와 의미가 일치하도록 유지한다.

## Notion Mapping Candidates

이번 단계에서는 Notion API 연동을 구현하지 않지만, 아래 매핑 후보를 권장한다.

- `period.actual_start` -> Date
- `period.actual_end` -> Date
- `overall_status` -> Select
- `period.coverage_status` -> Select
- `period.snapshot_count` -> Number
- `account_summary.end_equity_market_value` -> Number
- `account_summary.equity_change_pct` -> Number
- `trade_summary.trade_count` -> Number
- `len(operation_gaps)` -> Number
- `recommended_next_actions` -> Rich Text
- `source_files.account_snapshot.path` -> Text
- `source_files.execution_log.row_count` -> Number
- `markdown_report_path` -> Text candidate
- `json_report_path` -> Text candidate

## Excluded

- Notion API integration
- HTML report generation
- CSV export
- Streamlit UI
- Obsidian export
- operator action prose expansion
- paper ledger mutation

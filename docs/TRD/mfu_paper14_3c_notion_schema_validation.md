# MFU-PAPER14-3C Notion Schema Validation

## Scope

- Add read-only Notion data source schema validation for:
  - `weekly_reports`
  - `benchmark_reports`
  - `account_snapshots`
- Validate required property names and property types against the PAPER14 exporter contract
- Report select option gaps as warnings

## Out of Scope

- Actual Notion export/write
- Page create/update/delete
- Notion data source creation
- Paper ledger mutation

## Components

- `core/notion_client.py`
  - read-only data source schema retrieval with clearer error translation
- `core/notion_schema_validator.py`
  - expected schema definition and validation logic
- `scripts/dev/validate_notion_schema.py`
  - operator CLI for text/JSON validation output
- `tests/test_notion_schema_validator.py`
  - schema validator regression tests

## Validation Policy

- Missing required property: `FAIL`
- Property type mismatch: `FAIL`
- Missing recommended select option: `WARNING`
- All required properties and types match, with no warnings: `PASS`

## Safety

이번 PAPER14-3C는 Notion data source schema read-only validation 구현이며, 실제 Notion export/write는 포함하지 않는다.

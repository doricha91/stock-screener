# Notion View Spec: Daily Plans, Manual Executions, Manual Reviews

## 1. Purpose

This document defines recommended operating views for the Notion `Daily Plans`, `Manual Executions`, and `Manual Reviews` data sources using the actual project property mapping and read-only schema validation results.

이번 MFU-UI1은 실제 Notion mapping/schema 기준으로 Daily Plans, Manual Executions, Manual Reviews의 운영용 view spec을 문서화하는 작업이며, 코드 수정, DB write, paper 원장 수정, Notion write/export/sync, Notion view 실제 변경, Manual Execution commit, Manual Review append, broker/API 연동은 포함하지 않는다.

## 2. Scope / Non-scope

Scope:

- Document recommended manual Notion views.
- Define visible properties, hidden properties, filters, sorts, groups, and daily usage notes.
- Separate user-editable properties from system-managed properties.

Non-scope:

- Notion view creation or modification.
- Notion property deletion, rename, or type change.
- Notion write/export/sync.
- Local source-of-truth writes, commits, appends, or broker/API work.

## 3. Source of truth for property names

Property names come from `config/notion_property_mapping.example.json`. The local `config/notion_property_mapping.json` file was not present in this workspace during this check, so the loader would fall back to the example mapping.

Read-only schema validation confirmed that the actual Notion data sources match the configured mapping:

| Target | Validation command | Result |
| --- | --- | --- |
| `daily_plans` | `python scripts\dev\validate_notion_schema.py --daily-plan --json` | `PASS`, 13 properties checked |
| `manual_executions` | `python scripts\dev\validate_notion_schema.py --manual-executions --json` | `PASS`, 20 properties checked |
| `manual_reviews` | `python scripts\dev\validate_notion_schema.py --manual-reviews --json` | `PASS`, 18 properties checked |

## 4. Safety rules

- Do not delete properties.
- Do not rename properties.
- Do not change property types.
- Define only view-level hide/show/order/filter/sort/group rules.
- Keep one `System Debug` view per DB with all properties visible.
- Treat Notion as input UI, review UI, and staging layer.
- CSV / JSON / Markdown / SQLite remain source-of-truth.
- Python remains the validation, preview, commit, append, export, and sync actor.

## 5. Daily Plans DB view spec

Official mapped properties:

`Name`, `External Key`, `Account ID`, `Plan Date`, `Regime`, `Confirmed Trade Count`, `Review Item Count`, `Warning Count`, `Markdown Path`, `JSON Path`, `Schema Version`, `Synced At`, `Sync Status`.

Daily Plans is read-only for operators. Users should inspect the plan page and exported fields, not manually edit row properties.

### 5.1 Today Plan

Layout: Table

Visible properties:

1. `Name`
2. `Account ID`
3. `Plan Date`
4. `Regime`
5. `Confirmed Trade Count`
6. `Review Item Count`
7. `Warning Count`
8. `Sync Status`

Hidden properties:

- `External Key`
- `Markdown Path`
- `JSON Path`
- `Schema Version`
- `Synced At`

Filter:

- `Account ID = <active_account_id>`
- `Plan Date = <operation_date>`

Sort:

- `Plan Date` descending
- `Name` ascending

Group: N/A

Usage:

- Operator opens the current plan and checks confirmed trades, review items, and warnings.
- No properties are expected to be manually edited.

### 5.2 Plan History

Layout: Table

Visible properties:

1. `Name`
2. `Account ID`
3. `Plan Date`
4. `Regime`
5. `Confirmed Trade Count`
6. `Review Item Count`
7. `Warning Count`
8. `Sync Status`
9. `Synced At`

Hidden properties:

- `External Key`
- `Markdown Path`
- `JSON Path`
- `Schema Version`

Filter:

- `Account ID = <active_account_id>`
- `Plan Date is within past 7 days` or another operator-selected history window

Sort:

- `Plan Date` descending

Group: N/A

Usage:

- Operator reviews recent plan history and sync status.

### 5.3 System Debug

Layout: Table

Visible properties:

1. `Name`
2. `External Key`
3. `Account ID`
4. `Plan Date`
5. `Regime`
6. `Confirmed Trade Count`
7. `Review Item Count`
8. `Warning Count`
9. `Markdown Path`
10. `JSON Path`
11. `Schema Version`
12. `Synced At`
13. `Sync Status`

Hidden properties: N/A

Filter: N/A

Sort:

- `Plan Date` descending
- `Account ID` ascending

Group: N/A

Usage:

- Debug export/source-path issues and External Key routing.

## 6. Manual Executions DB view spec

Official mapped properties:

`Name`, `External Key`, `Account ID`, `Execution Date`, `Plan Date`, `Symbol`, `Side`, `Quantity`, `Actual Price`, `Commission`, `Currency`, `Broker`, `Status`, `Linked Daily Plan Key`, `Note`, `Validation Status`, `Validation Message`, `Import Status`, `Imported At`, `Synced At`.

Manual Executions is an operator input DB. Python imports only rows where `Status = READY` for the selected `Execution Date` and `Account ID`.

### 6.1 Today Execution Input

Layout: Table

Visible properties:

1. `Name`
2. `Execution Date`
3. `Symbol`
4. `Side`
5. `Quantity`
6. `Actual Price`
7. `Commission`
8. `Status`
9. `Note`
10. `Validation Status`
11. `Validation Message`
12. `Import Status`

Hidden properties:

- `External Key`
- `Account ID`
- `Plan Date`
- `Currency`
- `Broker`
- `Linked Daily Plan Key`
- `Imported At`
- `Synced At`

Filter:

- `Account ID = <active_account_id>`
- `Execution Date = <operation_date>`
- `Import Status is empty` or `Import Status != COMMITTED`

Sort:

- `Symbol` ascending
- `Side` ascending

Group: N/A

Usage:

- User enters or checks `Quantity`, `Actual Price`, `Commission`, `Status`, and `Note`.
- Set `Status = READY` only after row values are ready for preview.
- `Currency`, `Broker`, `Linked Daily Plan Key`, `Account ID`, and `Plan Date` can usually stay hidden if defaults/templates are correct, but they should be verified in `System Debug` if preview fails.

### 6.2 Execution Done

Layout: Table

Visible properties:

1. `Name`
2. `Account ID`
3. `Execution Date`
4. `Symbol`
5. `Side`
6. `Quantity`
7. `Actual Price`
8. `Commission`
9. `Validation Status`
10. `Import Status`
11. `Imported At`
12. `Synced At`

Hidden properties:

- `External Key`
- `Plan Date`
- `Currency`
- `Broker`
- `Status`
- `Linked Daily Plan Key`
- `Note`
- `Validation Message`

Filter:

- `Account ID = <active_account_id>`
- `Execution Date is within past 7 days` or another operator-selected window
- `Import Status = COMMITTED`

Sort:

- `Execution Date` descending
- `Symbol` ascending

Group:

- `Execution Date`

Usage:

- Confirm completed imported executions and sync status after commit/status sync.

### 6.3 System Debug

Layout: Table

Visible properties:

1. `Name`
2. `External Key`
3. `Account ID`
4. `Execution Date`
5. `Plan Date`
6. `Symbol`
7. `Side`
8. `Quantity`
9. `Actual Price`
10. `Commission`
11. `Currency`
12. `Broker`
13. `Status`
14. `Linked Daily Plan Key`
15. `Note`
16. `Validation Status`
17. `Validation Message`
18. `Import Status`
19. `Imported At`
20. `Synced At`

Hidden properties: N/A

Filter: N/A

Sort:

- `Execution Date` descending
- `Account ID` ascending
- `Symbol` ascending

Group: N/A

Usage:

- Debug READY-row import, validation failures, External Key routing, and status sync.

## 7. Manual Reviews DB view spec

Official mapped properties:

`Name`, `External Key`, `Account ID`, `Review Date`, `Symbol`, `Question ID`, `Question`, `Manual Answer`, `Review Status`, `Follow-up Needed`, `Review Tag`, `Reviewer Note`, `Source Template Key`, `Validation Status`, `Validation Message`, `Import Status`, `Imported At`, `Synced At`.

Manual Reviews is an operator answer DB. Python imports only rows where `Import Status = READY` for the selected `Review Date` and `Account ID`.

### 7.1 Today Review Answer

Layout: Table

Visible properties:

1. `Name`
2. `Review Date`
3. `Symbol`
4. `Question`
5. `Manual Answer`
6. `Review Status`
7. `Follow-up Needed`
8. `Review Tag`
9. `Reviewer Note`
10. `Import Status`
11. `Validation Status`
12. `Validation Message`

Hidden properties:

- `External Key`
- `Account ID`
- `Question ID`
- `Source Template Key`
- `Imported At`
- `Synced At`

Filter:

- `Account ID = <active_account_id>`
- `Review Date = <operation_date>`
- `Import Status = DRAFT` or `Import Status = READY`

Sort:

- `Symbol` ascending
- `Question ID` ascending

Group:

- `Symbol`

Usage:

- User answers `Manual Answer`, sets `Review Status`, sets `Follow-up Needed`, selects `Review Tag`, writes `Reviewer Note` if useful, then changes `Import Status` from `DRAFT` to `READY`.
- `Question ID` is useful for stable sorting but can stay hidden in the daily answer view.

### 7.2 Review Done

Layout: Table

Visible properties:

1. `Name`
2. `Account ID`
3. `Review Date`
4. `Symbol`
5. `Question`
6. `Review Status`
7. `Follow-up Needed`
8. `Review Tag`
9. `Validation Status`
10. `Import Status`
11. `Imported At`
12. `Synced At`

Hidden properties:

- `External Key`
- `Question ID`
- `Manual Answer`
- `Reviewer Note`
- `Source Template Key`
- `Validation Message`

Filter:

- `Account ID = <active_account_id>`
- `Review Date is within past 7 days` or another operator-selected window
- `Import Status = COMMITTED`

Sort:

- `Review Date` descending
- `Symbol` ascending
- `Question ID` ascending

Group:

- `Review Date`

Usage:

- Confirm appended review rows and status sync after Manual Review append.

### 7.3 System Debug

Layout: Table

Visible properties:

1. `Name`
2. `External Key`
3. `Account ID`
4. `Review Date`
5. `Symbol`
6. `Question ID`
7. `Question`
8. `Manual Answer`
9. `Review Status`
10. `Follow-up Needed`
11. `Review Tag`
12. `Reviewer Note`
13. `Source Template Key`
14. `Validation Status`
15. `Validation Message`
16. `Import Status`
17. `Imported At`
18. `Synced At`

Hidden properties: N/A

Filter: N/A

Sort:

- `Review Date` descending
- `Account ID` ascending
- `Symbol` ascending
- `Question ID` ascending

Group: N/A

Usage:

- Debug template export, READY-row import, validation failures, External Key routing, and status sync.

## 8. Minimal daily operating views

Recommended minimum set:

| DB | Minimal daily view | Operator action |
| --- | --- | --- |
| Daily Plans | `Today Plan` | Read plan, review counts, warnings, and page body |
| Manual Executions | `Today Execution Input` | Enter actual execution details and set `Status = READY` |
| Manual Reviews | `Today Review Answer` | Enter answers and set `Import Status = READY` |

The three `System Debug` views should exist but are not the normal daily working surface.

## 9. System Debug view policy

Each DB should have exactly one troubleshooting-oriented `System Debug` view with all mapped properties visible.

Policy:

- Keep all mapped properties visible.
- Use no default filter.
- Sort by the main date field descending.
- Use only for troubleshooting, schema checks, External Key checks, source path checks, validation failures, and sync audit.

## 10. Properties users should edit

Daily Plans:

- None in normal operation.

Manual Executions:

- `Quantity`
- `Actual Price`
- `Commission`
- `Status`
- `Note`

Manual Reviews:

- `Manual Answer`
- `Review Status`
- `Follow-up Needed`
- `Review Tag`
- `Reviewer Note`
- `Import Status`

## 11. Properties users should not edit

Daily Plans:

- All mapped properties are system/export managed.

Manual Executions:

- `External Key`
- `Validation Status`
- `Validation Message`
- `Import Status`
- `Imported At`
- `Synced At`

Usually do not edit unless explicitly correcting a staging-row setup issue:

- `Account ID`
- `Execution Date`
- `Plan Date`
- `Symbol`
- `Side`
- `Currency`
- `Broker`
- `Linked Daily Plan Key`

Manual Reviews:

- `External Key`
- `Account ID`
- `Review Date`
- `Symbol`
- `Question ID`
- `Question`
- `Source Template Key`
- `Validation Status`
- `Validation Message`
- `Imported At`
- `Synced At`

## 12. Manual setup checklist

Daily Plans:

- Create `Today Plan`, `Plan History`, and `System Debug`.
- Verify `Today Plan` filters use the active account and operation date.
- Keep Daily Plans read-only for operators.

Manual Executions:

- Create `Today Execution Input`, `Execution Done`, and `System Debug`.
- Make `Quantity`, `Actual Price`, `Commission`, `Status`, and `Note` easy to see.
- Keep system fields hidden in daily input view.
- Confirm `Status = READY` is visible in the daily input view.

Manual Reviews:

- Create `Today Review Answer`, `Review Done`, and `System Debug`.
- Keep `Manual Answer`, `Review Status`, `Follow-up Needed`, `Review Tag`, `Reviewer Note`, and `Import Status` visible.
- Keep `Question ID` hidden but sort by it.
- Confirm `Import Status = DRAFT/READY` rows are visible in the answer view.

## 13. Future impact / expected changes

Expected follow-up changes:

- Manual Review question generation may become more selective, which should reduce row volume in `Today Review Answer`.
- Daily Ops Status actual export guard expansion may add a stronger daily dashboard for active account closeout.
- An account-aware vertical slice audit may identify additional properties or views for weekly, benchmark, account snapshot, daily review summary, alert, replay, and daily ops status flows.
- A future Daily Ops Orchestrator may reduce the need to manually inspect debug views by showing stage status and next action recommendations.

## 14. Verification commands

Commands used for this specification:

```cmd
python scripts\dev\validate_notion_schema.py --help
python scripts\dev\validate_notion_schema.py --daily-plan --json
python scripts\dev\validate_notion_schema.py --manual-executions --json
python scripts\dev\validate_notion_schema.py --manual-reviews --json
git diff -- docs/operations/notion_view_spec_daily_plans_manual_executions_manual_reviews.md
git diff --check
git status --short
```

Validation results:

- `daily_plans`: `PASS`
- `manual_executions`: `PASS`
- `manual_reviews`: `PASS`

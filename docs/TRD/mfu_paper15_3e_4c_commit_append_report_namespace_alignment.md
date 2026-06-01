# PAPER15-3E-4C Commit / Append Report Namespace Alignment

## 1. Purpose

Manual Execution commit report와 Manual Review append commit report가 status sync가 기대하는 account-aware payload contract를 안정적으로 제공하도록 정렬한다.

## 2. Scope / Non-scope

Scope:
- commit/append sidecar JSON row payload에 `account_id`, account-aware `canonical_key`, legacy compatibility field 추가
- `paper_default` legacy preview/report 정규화
- non-default preview commit/append 차단 유지

Non-scope:
- writer path account-aware 적용
- non-default commit/append 허용
- Notion actual sync/write
- Notion row migration
- paper ledger migration

## 3. Report Contract

Manual Execution commit report row:
- `account_id`
- `canonical_key`
- `legacy_canonical_key`
- `legacy_key_compatible`
- `page_id`
- `validation_status`
- `validation_issues`
- `commit_status`

Manual Review append report row:
- `account_id`
- `canonical_key`
- `legacy_canonical_key`
- `legacy_key_compatible`
- `page_id`
- `validation_status`
- `validation_warnings`
- `append_status`

## 4. Account Policy

- preview payload에 `account_id`가 없으면 `paper_default`
- candidate-level `account_id`가 있으면 root와 일치해야 한다
- `paper_default`만 legacy canonical key 허용
- non-default + legacy-only canonical key는 실패

## 5. Legacy Compatibility

legacy execution key:
- `manual_execution:2026-05-25:AAPL:BUY:01`

normalized execution key:
- `manual_execution:paper_default:2026-05-25:AAPL:BUY:01`

legacy review key:
- `manual_review:2026-05-25:AAPL:Q001`

normalized review key:
- `manual_review:paper_default:2026-05-25:AAPL:Q001`

## 6. Relationship To Status Sync

status sync는 commit/append report만 읽고 아래를 만들 수 있어야 한다.
- `Account ID`
- `External Key`
- legacy compatibility metadata

즉 commit/append core가 sidecar contract를 안정적으로 제공하면, status sync는 preview payload를 다시 보지 않아도 된다.

## 7. Next MFU Dependency

다음 단계는 writer path와 commit/append core 자체를 account-aware root에 연결하는 MFU다. 그 전까지는 non-default commit/append를 열지 않는다.

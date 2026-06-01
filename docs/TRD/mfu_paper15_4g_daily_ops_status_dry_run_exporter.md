## Purpose

로컬 `paper.py status` 결과를 `Daily Ops Status` Notion payload로 변환하는 dry-run exporter를 추가한다.

## Scope / Non-scope

- Scope
  - `--daily-ops-status` dry-run CLI
  - account-aware external key 생성
  - status -> Notion property payload 변환
  - dry-run JSON summary
- Non-scope
  - Notion actual write/sync/export
  - Notion page create/update/upsert
  - `paper.py status` semantics 변경
  - paper 원장 수정

## Added CLI options

- `python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --dry-run --json`
- `python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --date 20260520 --dry-run --json`

정책:

- `--daily-ops-status`는 이번 단계에서 `--dry-run` 필수
- 다른 export target과 동시 실행 금지
- `--account-id` 생략 시 `paper_default`

## Daily Ops Status external key

- `daily_ops_status:{account_id}:{status_date}`
- 예: `daily_ops_status:paper_sandbox:2026-05-20`

## Status to Notion payload mapping

source:

- `run_paper_status(...)`

핵심 property mapping:

- `Name` = `{account_id} {status_date} Daily Ops Status`
- `External Key`
- `Account ID`
- `Status Date`
- `Workflow Status`
- `Review Progress Status`
- `Review Completion Ratio`
- `Next Recommended Command`
- `Blocking Reason`
- existence / count / review progress 계열
- `Sync Status = DRY_RUN`
- `Last Status Checked At` = dry-run 생성 시각
- `Synced At` = dry-run 생성 시각
- `Schema Version = daily_ops_status.v1`
- `Source Root = status.paths.paper_root`

## Blocking Reason derivation

- `NO_PLAN` -> `daily plan missing`
- `PLAN_READY` -> `snapshot/current state missing`
- `COMMITTED` -> `reports/review not ready`
- `REVIEW_READY` -> `review append pending`
- `REVIEW_PARTIAL` -> `pending review rows remain`
- `UNKNOWN_OR_INCOMPLETE` -> `inspect status details`
- `REVIEW_DONE` -> empty string

## Dry-run JSON summary

필수 필드:

- `target`
- `dry_run`
- `would_write`
- `account_id`
- `status_date`
- `external_key`
- `workflow_status`
- `review_progress_status`
- `data_source_configured`
- `notion_properties`
- `source_status`

## Why actual export is deferred

- 이번 단계는 payload contract 고정이 목적이다.
- Notion DB가 있어도 page create/update/upsert는 하지 않는다.
- actual export는 후속 MFU에서 제한적으로 연다.

## Next MFU recommendation

- `PAPER15-4H`: Daily Ops Status actual export 제한 실행

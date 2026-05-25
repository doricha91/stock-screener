# MFU-PAPER14-5D: Manual Execution Commit

## 목적

PAPER14-5C preview JSON을 commit 기준 artifact로 사용해 검증된 candidate만 `paper_execution_log.csv`에 반영한다.

- Notion = 입력 대기 / staging layer
- Preview JSON = commit 기준 artifact
- CSV / SQLite = 최종 source of truth

이번 PAPER14-5D는 Manual Executions preview 결과를 paper execution ledger에 commit하는 작업이며, Notion status back-write, Daily Review Summary export, broker/API 연동은 수행하지 않는다.

## commit 원칙

- commit은 Notion을 다시 읽지 않는다.
- `--preview-json`으로 넘긴 preview JSON만 사용한다.
- preview와 실제 commit 시점 사이에 Notion row가 바뀌었으면 preview를 다시 생성해야 한다.

## CLI

```cmd
python scripts\import_notion_executions.py --date 2026-05-25 --preview --json
python scripts\import_notion_executions.py --date 2026-05-25 --commit --preview-json outputs\paper_test\reports\manual_execution_import_preview_20260525.json
python scripts\import_notion_executions.py --date 2026-05-25 --commit --preview-json outputs\paper_test\reports\manual_execution_import_preview_20260525.json --allow-warnings
```

## preview 기반 commit 정책

commit 금지:

- preview JSON 없음
- preview `execution_date`와 `--date` 불일치
- `fail_count > 0`
- `commit_allowed = false`
- `commit_allowed = true_with_warnings`인데 `--allow-warnings` 없음

commit 대상:

- `validation_status = PASS` 또는 `WARNING`
- fail severity 없음

## WARNING 처리 정책

- WARNING preview는 기본적으로 commit 금지
- `--allow-warnings`가 있을 때만 commit 허용
- WARNING 상세는 commit sidecar에 그대로 보존

## ledger mapping

Manual Execution candidate -> `paper_execution_log.csv`

- `execution_date` -> `date`
- `symbol` -> `symbol`
- `side` -> `side`
- `quantity` -> `shares`
- `actual_price` -> `price`
- `note` -> `notes`
- `source` -> `notion_manual_execution`
- `reason` -> `manual_execution_import`

shares 부호:

- BUY = positive
- SELL = negative

`trade_id`는 기존 `build_paper_trade_id()` 규칙을 그대로 사용한다.

## sidecar 보존 정책

`paper_execution_log.csv` schema는 확장하지 않는다.

`commission / currency / broker`는 sidecar report에만 보존한다.

산출물:

- `outputs/paper_test/reports/manual_execution_import_commit_YYYYMMDD.json`
- `outputs/paper_test/reports/manual_execution_import_commit_YYYYMMDD.md`

포함 내용:

- `canonical_key`
- `page_id`
- `commission`
- `currency`
- `broker`
- validation warnings
- preview json path
- committed trade id

## state refresh 정책

commit 후 다음을 갱신한다.

- `paper_execution_log.csv`
- `paper_account_snapshot.csv`
- `paper_position_snapshot.csv`

기존 helper 재사용:

- `append_paper_execution_log()`
- `build_paper_state_from_trades()`
- `value_paper_account_state()`
- `build_paper_account_snapshot_row()`
- `save_paper_account_snapshot()`
- `build_paper_position_snapshot_rows()`
- `save_paper_position_snapshot()`

이번 5D에서는 `paper_current_state_YYYYMMDD.json`은 갱신하지 않는다.

## 실패 / 중복 방지

- commit 전 `outputs/dev_backups/*`에 원장 CSV 백업 생성
- duplicate trade id가 이미 있으면 commit 차단
- append pre-check와 실제 append count가 다르면 commit 차단
- snapshot/position write 실패 시 dev backup으로 rollback

## 제외 범위

- Notion Validation Status back-write
- Notion Import Status back-write
- Daily Review Summary export
- broker/API 연동
- execution log schema 확장

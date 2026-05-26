# Paper Daily Operation Guide

## 1. 목적

이 문서는 paper trading 운영자가 매일 어떤 명령을 어떤 순서로 실행해야 하는지 정리한다.  
자동매매 실행 문서가 아니라 paper test 운영 절차 문서다.

운영 표준은 `scripts/paper.py`의 shortcut command를 기준으로 한다.

## 2. 기본 운영 루틴

기본 순서는 아래와 같다.

1. `prepare`
2. `preview`
3. `commit`
4. `review`
5. `status`

예시:

```bash
python scripts/paper.py prepare --date 20260520
python scripts/paper.py preview --date 20260520
python scripts/paper.py commit --date 20260520
python scripts/paper.py review
python scripts/paper.py status --date 20260520
```

## 3. 각 명령의 의미

### `prepare`

- `prepare-data + data-freshness`
- `market_data.db` 입력 준비 후 freshness를 확인한다.
- DB writer command다.
- 기본적으로 아래를 수행한다.
  - `market_index` 갱신
  - `tickers` 갱신
  - `daily_price` 갱신
  - `daily_indicators` 갱신

### `preview`

- `data-freshness + plan + eod dry-run`
- `daily_action_plan` 생성과 EOD 반영 결과를 미리 본다.
- `commit`은 하지 않는다.
- 원장을 쓰지 않는 preview 단계다.

### `commit`

- `eod --commit`
- `paper_current_state`, `paper_account_snapshot`, `paper_position_snapshot`을 저장한다.
- 같은 날짜 snapshot이 있으면 기본 차단된다.
- 의도적으로 같은 날짜를 교체할 때만 `--replace`를 사용한다.

### `review`

- `reports + review-template + review-validate`
- PAPER9 report와 PAPER10 review template/validation을 한 번에 재생성한다.
- `review-append`는 실행하지 않는다.

### `status`

- 현재 운영 상태를 read-only로 요약한다.
- 최신 상태 확인 또는 특정 날짜 상태 점검에 사용한다.

## 4. 날짜 정책

- `prepare`, `preview`, `commit`은 같은 날짜를 사용한다.
- `--date`는 paper 운영 기준일, 즉 as-of date다.
- 한국 시간의 오늘과 미국장 기준 거래일이 다를 수 있으므로 날짜를 명시한다.
- `review`는 기본적으로 날짜 없이 최신 상태 기준으로 실행한다.

예시:

```bash
python scripts/paper.py prepare --date 20260520
python scripts/paper.py preview --date 20260520
python scripts/paper.py commit --date 20260520
```

## 5. warning 처리 기준

기본 정책:

- `PASS` -> 계속 진행
- `PASS_WITH_WARNINGS` -> 기본 중단
- `FAIL` -> 중단

warning 상태를 의도적으로 통과할 때만 `--allow-warnings`를 사용한다.

쉽게 무시하면 안 되는 warning:

- `daily_price latest date is older than target_date`
- `SPY latest date is older than target_date`
- `daily_indicators`가 `daily_price`보다 오래됨

상대적으로 위험도가 낮은 optional warning:

- `universe_snapshot_YYYYMMDD.json` 없음

`universe`는 매일 갱신하지 않을 수 있다. 필요하면 아래처럼 실행한다.

```bash
python scripts/paper.py prepare --date 20260520 --universe
```

## 6. preview에서 확인할 것

`preview` 후에는 아래를 확인한다.

- `data-freshness` 결과가 `PASS`인지
- `plan_date`와 `data_date`가 기대와 맞는지
- `daily_action_plan` 저장 경로가 `outputs/paper_test` 하위인지
- EOD dry-run 결과
- `ready_for_paper_trade`
- `rows_to_append`
- `write_performed=False`
- account preview 요약

주의:

- `preview`는 원장을 쓰지 않는다.
- 확정 매매가 없어도, 그날 snapshot 저장이 필요하면 `commit`은 여전히 의미가 있다.

## 7. commit에서 확인할 것

`commit` 후에는 아래를 확인한다.

- preflight `PASS`
- `rows_appended`
- `paper_current_state` 저장 여부
- `paper_account_snapshot` 저장 여부
- `paper_position_snapshot` 저장 여부
- `outputs/front_test` 변경 없음

같은 날짜 재실행 정책:

- 기본 `commit`은 같은 날짜 snapshot이 있으면 차단된다.
- 의도적으로 재실행할 때만 `--replace`를 사용한다.
- `--replace` 사용 시 기존 EOD 로직이 backup을 만든 뒤 같은 날짜 snapshot을 교체할 수 있다.

예시:

```bash
python scripts/paper.py commit --date 20260520 --replace
```

운영 표준에서는 `--replace`를 일상적으로 사용하지 않는다.

## 8. review에서 확인할 것

`review` 후에는 아래 파일을 확인한다.

- `outputs/paper_test/reports/paper_daily_review_summary.md`
- `outputs/paper_test/reviews/paper_manual_review_log_template.md`
- `outputs/paper_test/reviews/paper_manual_review_log_validation_report.md`

명시 사항:

- `review`는 `review-append`를 실행하지 않는다.
- `review-append`는 사람이 template에 답변을 작성한 뒤 별도로 실행한다.
- 즉, `review`는 review material 생성과 validation까지만 담당한다.

## 9. status 사용법

예시:

```bash
python scripts/paper.py status
python scripts/paper.py status --date 20260520
python scripts/paper.py status --date 20260520 --verbose
python scripts/paper.py status --json
```

`workflow_status` 의미:

- `NO_PLAN`
- `PLAN_READY`
- `COMMITTED`
- `REVIEW_READY`
- `UNKNOWN_OR_INCOMPLETE`

`next_recommended_command` 정책:

- `NO_PLAN` -> `paper.py preview --date YYYYMMDD`
- `PLAN_READY` -> `paper.py commit --date YYYYMMDD`
- `COMMITTED` -> `paper.py review`
- `REVIEW_READY` -> `no immediate action`
- `UNKNOWN_OR_INCOMPLETE` -> 상태 상세 확인 후 수동 판단

## 10. 문제 상황별 대응

### prepare에서 freshness warning 발생

- 기본 정책은 중단이다.
- warning 내용을 먼저 확인한다.
- 특히 `daily_indicators` stale warning은 plan 품질에 직접 영향이 있으므로 쉽게 무시하지 않는다.
- 정말 의도된 예외 상황일 때만 `--allow-warnings`를 사용한다.

### preview에서 `rows_to_append=0`

- 거래 없는 날이면 정상일 수 있다.
- `write_performed=False`와 함께 확인한다.
- 그날 snapshot 저장이 필요하면 `commit`은 여전히 고려할 수 있다.

### commit에서 same-date snapshot exists로 차단

- 기본 차단이 정상 동작한 것이다.
- 정말 같은 날짜 snapshot 교체가 필요한 경우에만 `--replace`를 사용한다.
- 왜 재실행이 필요한지 먼저 확인한 뒤 진행한다.

### review validation FAIL

- `paper_manual_review_log_validation_report.md`와 issues CSV를 먼저 확인한다.
- `manual_answer`, `review_status`, `follow_up_needed`, `review_tag` 형식을 점검한다.
- validation이 PASS가 되기 전까지 append는 실행하지 않는다.

### status가 `UNKNOWN_OR_INCOMPLETE`

- plan/snapshot/report/review 파일 간 상태가 어긋난 경우다.
- 저수준 진단용 명령으로 원인을 좁힌다.
  - `paper.py data-freshness --date YYYYMMDD`
  - `paper.py preflight --date YYYYMMDD --stage plan`
  - `paper.py preflight --date YYYYMMDD --stage eod`

### DB 최신 날짜가 target date보다 이전

- 기본적으로 `prepare`를 다시 점검해야 한다.
- 휴장일인지 먼저 확인한다.
- 휴장일이 아니라면 data readiness가 부족한 상태로 보고 `preview`를 바로 진행하지 않는다.

## 11. 금지/주의 명령

운영 표준에서는 아래 저수준 명령을 직접 쓰지 않는다.

```bash
python scripts/paper.py eod --date YYYYMMDD --commit
```

이유:

- 저수준 명령이라 운영 shortcut의 same-date commit guard 흐름을 우회할 수 있다.
- 운영 표준은 `paper.py commit`을 사용한다.

아래도 일상 운영에 포함하지 않는다.

- `setup_db.py`
- `review-append` 자동 실행
- `run-all` 또는 `daily` 형태의 자동 commit 체인

문제 진단이 필요할 때만 개별 명령을 사용하고, 일상 운영은 shortcut 기준으로 유지한다.

## 12. PAPER14 Notion Export SOP Addendum

This addendum documents the PAPER14 Notion export step for paper operations.

Notion export is added after the existing loop:

`prepare -> preview -> commit -> review -> status -> notion export`

### 12.1 Role of Notion

Notion export does not replace the source artifacts produced by the paper workflow.

- Notion export는 CSV/JSON/Markdown/SQLite 원천 데이터를 대체하지 않는다.
- Notion은 검토와 표시를 위한 presentation/review layer다.
- Source of truth remains local CSV / JSON / Markdown / SQLite outputs.
- If Notion export fails, the paper ledger is not considered failed when the source artifacts were generated correctly.
- Notion export failure should be logged separately and fixed before the next operational cycle.

### 12.2 Execution order

Run schema validation first, then dry-run, then actual export.

```bash
cd /d D:\python\StockScreener
set PYTHONPATH=.

python scripts\dev\validate_notion_schema.py --all --json

python scripts\export_paper_to_notion.py --weekly --dry-run --json
python scripts\export_paper_to_notion.py --benchmark --dry-run --json
python scripts\export_paper_to_notion.py --account-snapshot --dry-run --json

python scripts\export_paper_to_notion.py --weekly --json
python scripts\export_paper_to_notion.py --benchmark --json
python scripts\export_paper_to_notion.py --account-snapshot --json
```

Operational rules:

- If schema validation returns any `FAIL`, do not run actual export.
- If any dry-run fails, do not run actual export.
- Run actual export per target, not with `--all`.
- Execution order is fixed:
  - `weekly`
  - `benchmark`
  - `account-snapshot`

### 12.3 Success criteria

- Schema validation result is `PASS` or `WARNING`
- All three dry-run commands succeed
- All three actual export commands succeed
- No duplicate row is created for the same `External Key`
- Major properties are visible in the Notion UI

### 12.4 Failure handling

Schema validation `FAIL`:

- Fix the Notion DB property names, property types, or select configuration.
- Do not run actual export.

Dry-run failure:

- Check the source JSON / CSV / Markdown paths and the Notion property mapping.
- Do not run actual export.

Actual export failure:

- Check `NOTION_TOKEN`, data source id values, and integration permissions.
- Do not modify source ledger files to compensate for the Notion failure.
- Record the failure in the operation log or task report and retry after the cause is fixed.

### 12.5 Security and configuration

- `NOTION_TOKEN` must be managed only through `.env` or environment variables.
- Real data source ids must be stored only in `config/notion_settings.json` or environment variables.
- `config/notion_settings.json` should remain gitignored.
- `config/notion_property_mapping.json` should remain gitignored.
- Never expose tokens or real data source ids in logs or operational documents.

### 12.6 Out of scope

The following are not part of the current SOP step:

- Daily Plan export
- Daily Review Summary export
- Performance Summary export
- Manual Review input integration
- Notion DB auto-creation
- Notion schema migration
- page body improvement

## 13. PAPER14 Notion and Review Daily Loop

The following loop supersedes the earlier PAPER14 addendum scope and reflects the
current daily paper operation with Manual Review included.

`Prepare -> Daily Plan -> Plan Export -> Action -> Manual Executions Input -> Execution Preview -> Execution Commit -> State Refresh -> Execution Status Sync -> Daily Review Summary -> Manual Review Input -> Manual Review Preview -> Manual Review Append -> Manual Review Status Sync -> Weekly / Benchmark / Account Snapshot Export`

Recommended daily order:

1. `Prepare / preflight`
2. `Daily Plan` generation
3. `Daily Plan` Notion export
4. Confirm `Daily Plan` in Notion
5. Execute the actual action
6. Enter `Manual Executions` in Notion
7. Run `Manual Executions` preview
8. Review preview and run execution commit
9. Confirm `paper_account_snapshot`, `paper_position_snapshot`, and `paper_current_state`
10. Run `Manual Executions` status sync
11. Export `Daily Review Summary`
12. Confirm `Daily Review Summary` in Notion
13. Enter `Manual Reviews` in Notion
14. Run `Manual Reviews` preview
15. Review preview and run review append
16. Run `Manual Reviews` status sync
17. Run `Weekly / Benchmark / Account Snapshot` export as needed

Reference:

- Detailed Notion procedure is documented in [paper_notion_ops.md](paper_notion_ops.md).

## 14. Review and Notion Operating Policy

### 14.1 Source of truth

- Notion is an input UI / review UI / staging layer.
- CSV / JSON / Markdown / SQLite remain the source of truth.
- Python is the validation / preview / commit / append owner.

### 14.2 When Manual Review is required

- If trades or fills occurred, `Manual Review` is required.
- If there was any `WARNING`, `FAIL`, or meaningful plan deviation, `Manual Review` is required.
- If there was no trade and `Daily Review Summary` reports `NO_ACTIVITY`, `Manual Review` can be skipped.

### 14.3 Smartphone vs local PC

Smartphone-friendly steps:

- Check `Daily Plan`
- Enter `Manual Executions`
- Check `Daily Review Summary`
- Enter `Manual Reviews`
- Check Notion status fields such as `READY` and `COMMITTED`

Local PC only:

- Run preview commands
- Run commit / append commands
- Refresh ledger / review log / state artifacts
- Run status back-write
- Run Notion export and sync commands

### 14.4 WARNING / FAIL policy

- If any preview result contains `FAIL`, do not run commit or append.
- If preview result contains `WARNING`, block by default.
- Use `--allow-warnings` only when the operator explicitly accepts the warning.
- When warnings are accepted, record the reason in the review note or operation note.

### 14.5 Notion sync failure policy

- If Python source-of-truth commit succeeds but Notion status sync fails, do not roll back the source artifacts.
- Re-run only the status sync step using the same commit report.

Reason:

- Notion status sync is a presentation / status layer.
- Source-of-truth commit success is judged separately from Notion sync success.

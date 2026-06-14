# Paper Daily Cycle 명령어 Runbook

이 문서는 n8n 자동화 이전에 운영자가 매일 Paper Daily Ops 사이클을 수동으로 돌릴 때 보는 실전 운영 매뉴얼이다. 현재 repo의 CLI와 코드 경로를 기준으로 작성했다.

근거가 되는 주요 진입점:

- `scripts\paper.py`
- `scripts\paper_daily_ops.py`
- `scripts\export_paper_to_notion.py`
- `scripts\import_notion_executions.py`
- `scripts\import_notion_reviews.py`
- `scripts\sync_notion_execution_status.py`
- `scripts\sync_notion_review_status.py`

운영 원칙:

- Local CSV/JSON/Markdown/SQLite 산출물이 source of truth다.
- Notion은 입력, 검토, staging, 상태 표시 UI다.
- broker/API/order 실행은 이 문서 범위가 아니다.

## 1. Quick Start

매일 먼저 운영 변수 3개를 정한다.

```cmd
cd /d D:\python\StockScreener
conda activate HANTU311_64

set ACCOUNT_ID=paper_orch_smoke_202606
set ACCOUNT_ID=paper_pilot_202606
set DATA_DATE=2026-06-12
set TRADE_DATE=2026-06-15
```

변수 의미:

- `ACCOUNT_ID`: 운영할 paper 계좌. 예: `paper_orch_smoke_202606`, `paper_pilot_202606`, `paper_sandbox`.
- `DATA_DATE`: 매매 판단에 사용할 최신 완료 미국장 데이터 날짜.
- `TRADE_DATE`: 실제 다음 paper 매매/운영 대상 날짜.

예:

- 한국시간 토요일 아침에 금요일 미국장이 마감된 뒤 운영한다면 `DATA_DATE`는 금요일 미국장 날짜다.
- `TRADE_DATE`는 다음 미국 거래일이다.

항상 Orchestrator 상태 확인으로 시작한다.

```cmd
python scripts\paper_daily_ops.py status --account-id %ACCOUNT_ID% --data-date %DATA_DATE% --trade-date %TRADE_DATE% --json > outputs\orch_status.json

python -c "import json; p=json.load(open(r'outputs\orch_status.json',encoding='utf-8')); print(json.dumps(p.get('operator_summary'),ensure_ascii=False,indent=2))"
```

먼저 확인할 필드:

- `current_step`
- `recommended_operator_action`
- `next_command`
- `command_type`
- `risk_level`
- `requires_manual_approval`
- `warnings`
- `blockers`
- `terminal`

## 2. 전체 운영 흐름

| Step | 단계 | 목적 | 명령 | 성격 | 자동화 | 승인 | 정상 기준 | 실패 시 확인 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | Orchestrator 상태 | 다음 단계 판단 | `python scripts\paper_daily_ops.py status ... --json` | read-only | 가능 | 불필요 | `operator_summary` 확인 가능 | `blockers`, `warnings`, `current_step` 확인 |
| 1 | Data prepare | market data 입력 준비 | `python scripts\paper.py prepare-data --date %DATA_DATE% --universe` | DB/universe write | 금지 | 필요 | errors 없음 | network/yfinance/DB 상태 확인 |
| 2 | Data freshness | DB 준비 상태 확인 | `python scripts\paper.py data-freshness --date %DATA_DATE%` | read-only | 가능 | 불필요 | `result: PASS` | `FAIL`이면 plan 금지 |
| 3 | Daily Plan | 계좌별 plan 생성 | `python scripts\paper.py plan --data-date %DATA_DATE% --trade-date %TRADE_DATE% --account-id %ACCOUNT_ID%` | local artifact write | 금지 | 필요 | md/json/config snapshot 생성 | freshness/preflight/date 확인 |
| 4 | Daily Plan Notion export | plan을 Notion에 표시 | `export_paper_to_notion.py --daily-plan ...` | Notion write | 금지 | 필요 | failed count 0 | Notion schema/auth 확인 |
| 5 | Manual Execution template | 실행 입력 row 생성 | `export_paper_to_notion.py --manual-execution-template ...` | Notion write | 금지 | 필요 | 후보 row 생성 또는 no-op | plan 후보/Notion 결과 확인 |
| 6 | Notion Execution 입력 | 실제 체결 정보 입력 | Notion UI | 수동 Notion edit | 금지 | 사용자 입력 | `Actual Price`, `Status=READY` | 계좌/date 필터 확인 |
| 7 | Execution preview | Notion 실행 row 검증 | `import_notion_executions.py --preview ...` | read + preview file | 가능 | 불필요 | `fail_count=0` | Notion row 값 수정 |
| 8 | Execution commit | 실행 preview commit | `import_notion_executions.py --commit ...` | local ledger/state write | 금지 | 필요 | commit report 생성 | 실패 시 sync 금지 |
| 9 | Execution status sync | 실행 상태 Notion 반영 | `sync_notion_execution_status.py ...` | Notion write | 금지 | 필요 | failed count 0 | 같은 commit report로 재시도 |
| 10 | Daily Review | review 산출물 생성 | `python scripts\paper.py review ...` | local report/review write | 금지 | 필요 | validation PASS | preflight/report 오류 확인 |
| 11 | Manual Review template | review 입력 row 생성 | `export_paper_to_notion.py --manual-review-template ...` | Notion write | 금지 | 필요 | review row 생성 | template date/Notion 결과 확인 |
| 12 | Notion Review 입력 | review 답변 작성 | Notion UI | 수동 Notion edit | 금지 | 사용자 입력 | `Manual Answer`, `Review Status`, `Import Status` 준비 | `Import Status=READY` 확인 |
| 13 | Review preview | review row 검증 | `import_notion_reviews.py --preview ...` | read + preview file | 가능 | 불필요 | `fail_count=0` | Notion row 값 수정 |
| 14 | Review append | review log append | `import_notion_reviews.py --commit ...` | local review log write | 금지 | 필요 | appended count 정상 | 실패 시 중단 |
| 15 | Review status sync | review 상태 Notion 반영 | `sync_notion_review_status.py ...` | Notion write | 금지 | 필요 | failed count 0 | 같은 commit report로 재시도 |
| 16 | EOD dry-run | 마감 preview | `python scripts\paper.py eod ... --dry-run` | read-only | 가능 | 불필요 | write intent 확인 | commit 전 반드시 검토 |
| 17 | EOD commit | local state/snapshot 마감 | `python scripts\paper.py eod ... --commit` | local state/snapshot write | 금지 | 필요 | current state/snapshot write | guard/preflight 실패 확인 |
| 18 | Final status | 완료 확인 | `paper.py status`, `paper_daily_ops.py status` | read-only | 가능 | 불필요 | `REVIEW_DONE`, terminal true | blocker/conflict 해결 |

## 3. Canonical Command Sequence

### 3.1 Orchestrator 초기 확인

```cmd
python scripts\paper_daily_ops.py status --account-id %ACCOUNT_ID% --data-date %DATA_DATE% --trade-date %TRADE_DATE% --json > outputs\orch_status.json

python -c "import json; p=json.load(open(r'outputs\orch_status.json',encoding='utf-8')); print(json.dumps(p.get('operator_summary'),ensure_ascii=False,indent=2))"
```

정상:

- 새 사이클 초반에는 `terminal=false`일 수 있다.
- `current_step`이 다음 필요한 단계를 가리킨다.
- `next_command`가 있으면 그 명령을 우선 검토한다.
- 진행 전 `blockers=[]`인지 확인한다.

멈춰야 하는 경우:

- `recommended_operator_action=RESOLVE_CONFLICT`
- `blockers`가 비어 있지 않음
- `command_type=UNKNOWN`인데 명령 의미를 아직 검토하지 않음

### 3.2 Data Prepare

공식 paper wrapper:

```cmd
python scripts\paper.py prepare-data --date %DATA_DATE% --universe
```

이 명령은 현재 Daily Ops 기준 canonical data prepare wrapper다. 준비하는 항목:

- market index data
- ticker info
- stock price data
- `daily_indicators`
- `--universe` 사용 시 universe snapshot

주의:

- read-only가 아니다.
- `outputs\market_data.db`와 universe snapshot 파일을 수정할 수 있다.
- yfinance/network 의존성이 있다.
- 미국 장마감 직후에는 데이터 공급 지연으로 freshness warning 또는 fail이 날 수 있다.

shortcut:

```cmd
python scripts\paper.py prepare --date %DATA_DATE% --universe
```

`prepare`는 `prepare-data` 후 `data-freshness`를 실행한다. `PASS_WITH_WARNINGS`면 기본 중단하며, 계속하려면 `--allow-warnings`가 필요하다.

standalone 대체 명령도 존재하지만 Daily Ops 기준 우선순위는 낮다.

```cmd
python screener\data_collector.py && python data_processor.py
```

### 3.3 Data Freshness 확인

```cmd
python scripts\paper.py data-freshness --date %DATA_DATE%
```

정상:

- `result: PASS`
- `error_count: 0`

결과 의미:

- `PASS`: required market data check 통과.
- `PASS_WITH_WARNINGS`: error는 없지만 warning이 있다. 단, explicit-date plan은 strict freshness를 사용하므로 plan이 중단될 수 있다.
- `FAIL`: plan 생성 금지.

freshness checker가 확인하는 주요 항목:

- `daily_price`
- `market_index` (`SPY` 필수, `QQQ`, `^VIX`도 확인)
- `daily_indicators`
- `tickers`
- quarterly/as-of universe snapshot

보조 DB 날짜 확인 명령:

```cmd
python -c "import sqlite3; con=sqlite3.connect(r'outputs\market_data.db'); cur=con.cursor(); target='%DATA_DATE%'; tables=[r[0] for r in cur.execute('select name from sqlite_master where type=?',('table',))]; wanted=['daily_price','daily_indicators','market_index','market_status_log']; [print(t,'max_date=',cur.execute(f'select max(date) from {t}').fetchone()[0],'rows_target=',cur.execute(f'select count(*) from {t} where date=?',(target,)).fetchone()[0]) for t in wanted if t in tables and 'date' in [r[1] for r in cur.execute(f'pragma table_info({t})')]]; con.close()"
```

이 보조 명령은 `outputs\market_data.db`를 읽기만 한다.

### 3.4 Daily Plan 생성

```cmd
python scripts\paper.py plan --data-date %DATA_DATE% --trade-date %TRADE_DATE% --account-id %ACCOUNT_ID%
```

실행 전 확인:

- `data-freshness --date %DATA_DATE%` 결과가 `PASS`.
- `DATA_DATE`는 완료된 미국장 날짜.
- `TRADE_DATE`는 `DATA_DATE` 이후이며 주말이 아님.

정상:

- 계좌 root 아래 `daily_action_plan_YYYYMMDD.md` 생성.
- 계좌 root 아래 `daily_action_plan_YYYYMMDD.json` 생성.
- 계좌별 config snapshot 생성.
- plan candidate는 0개일 수도 있다. 0개면 no-action day일 수 있다.

생성 후 Orchestrator를 다시 확인한다.

```cmd
python scripts\paper_daily_ops.py status --account-id %ACCOUNT_ID% --data-date %DATA_DATE% --trade-date %TRADE_DATE% --json > outputs\orch_status.json
python -c "import json; p=json.load(open(r'outputs\orch_status.json',encoding='utf-8')); print(json.dumps(p.get('operator_summary'),ensure_ascii=False,indent=2))"
```

### 3.5 Daily Plan Notion Export

Orchestrator의 `next_command`를 우선 사용한다. 일반 형식:

```cmd
python scripts\export_paper_to_notion.py --daily-plan --account-id %ACCOUNT_ID% --date %TRADE_DATE% --confirm-actual --json
```

실행 전 확인:

- Daily Plan stage가 `DONE`.
- Notion write 명령임을 인지.
- 사용자 승인 필요.

정상:

- create/update 결과가 출력된다.
- failed count가 0이다.
- account/date가 현재 운영 변수와 일치한다.

## 4. Manual Execution 운영

### 4.1 Template Export

```cmd
python scripts\export_paper_to_notion.py --manual-execution-template --account-id %ACCOUNT_ID% --date %TRADE_DATE% --confirm-actual --json
```

성격:

- Notion write.
- 사용자 승인 필요.

정상:

- `candidate_count` 확인 가능.
- Manual Executions DB에 row가 create/update 된다.
- failed count가 0이다.

`candidate_count=0`이면 no-action day일 수 있다. Orchestrator가 Manual Execution 단계를 no-op `DONE` 처리하는지 확인한다.

### 4.2 Notion Manual Execution 입력

Manual Executions DB에서 아래 속성을 확인하거나 입력한다.

- `Account ID`: `%ACCOUNT_ID%`와 일치해야 한다.
- `Execution Date`: `%TRADE_DATE%`와 일치해야 한다.
- `Symbol`
- `Side`: `BUY` 또는 `SELL`
- `Quantity`
- `Plan Price`: 참고값
- `Actual Price`: paper execution에 사용할 실제 체결가
- `Commission`: 필요 시 입력, 기본 0 가능
- `Currency`: 보통 `USD`
- `Broker`: 보통 `PAPER`
- `Status`: preview/commit 대상이면 `READY`
- `Import Status`: 초기에는 not imported 계열이며 commit/sync 후 갱신됨
- `Validation Status` / `Validation Message`: sync 이후 확인

preview로 넘기기 위한 조건:

- Actual Price 입력 완료.
- `Status=READY`.
- Account ID와 Execution Date 필터 일치.

### 4.3 Execution Preview

```cmd
python scripts\import_notion_executions.py --date %TRADE_DATE% --account-id %ACCOUNT_ID% --preview --json
```

성격:

- Notion read + preview artifact 생성.
- local ledger commit은 하지 않음.
- 자동화 가능.

정상:

- 일반 실행일이면 `candidate_count > 0`.
- `fail_count=0`.
- `commit_allowed`가 true 또는 검토 가능한 true-with-warnings.

`candidate_count=0`이면 확인할 것:

- 원래 no-action day인지.
- Notion row가 `Status=READY`인지.
- `Actual Price`가 입력됐는지.
- `Account ID`가 `%ACCOUNT_ID%`인지.
- `Execution Date`가 `%TRADE_DATE%`인지.

### 4.4 Execution Commit

preview 명령이 출력한 preview JSON 경로 또는 Orchestrator가 추천한 경로를 사용한다.

```cmd
python scripts\import_notion_executions.py --date %TRADE_DATE% --account-id %ACCOUNT_ID% --commit --preview-json "<EXECUTION_PREVIEW_JSON>" --json
```

성격:

- local source-of-truth artifact write.
- 사용자 승인 필요.

실행 전 확인:

- preview JSON/summary를 검토.
- `fail_count=0`.
- projected cash/position impact 확인.
- `--allow-warnings`는 warning을 명시적으로 수용할 때만 사용.

정상:

- commit report JSON/Markdown 생성.
- committed row count가 예상 candidate count와 일치.
- execution log/current state/snapshot update가 report에 표시됨.

### 4.5 Execution Status Sync

```cmd
python scripts\sync_notion_execution_status.py --date %TRADE_DATE% --account-id %ACCOUNT_ID% --commit-report "<EXECUTION_COMMIT_REPORT>" --json
```

성격:

- Notion status field write.
- 사용자 승인 필요.

정상:

- sync 성공.
- updated count가 committed row 수와 일치.
- failed count가 0.

local commit이 성공한 뒤 Notion sync만 실패했다면 local source-of-truth를 rollback하지 않는다. Notion/schema/auth 문제를 고친 뒤 같은 commit report로 재시도한다.

### 4.6 Execution Candidate가 0개인 날

no-action day 흐름이다.

조건:

- Daily Plan은 존재.
- 실제 BUY/SELL execution candidate는 0개.

예상 Orchestrator 상태:

- `MANUAL_EXECUTION_TEMPLATE=DONE`
- `MANUAL_EXECUTION_PREVIEW=DONE`
- `MANUAL_EXECUTION_COMMIT=DONE`
- `MANUAL_EXECUTION_STATUS_SYNC=DONE`
- stage detail에 `no_execution_candidates=true`

운영:

- Manual Execution commit은 필요 없다.
- Daily Review로 넘어간다.
- final closure를 위해 EOD no-action roll-forward가 필요할 수 있다.

## 5. Daily Review 운영

### 5.1 Daily Review 생성

```cmd
python scripts\paper.py review --account-id %ACCOUNT_ID% --date %TRADE_DATE%
```

성격:

- local reports/review files write.
- 사용자 승인 필요.

주요 생성/갱신 파일:

- `reports\paper_daily_review_summary.md`
- `reports\paper_performance_summary.md`
- `reviews\paper_manual_review_log_template.csv`
- `reviews\paper_manual_review_log_validation_report.md`
- 계좌 reports directory 아래 symbol review worksheet/report

정상:

- `PAPER REPORTS` success.
- review template row count 확인.
- validation result가 `PASS`.

날짜 guard:

- review template CSV의 모든 `review_date`는 `%TRADE_DATE%`여야 한다.
- no-action day에서는 daily review/performance summary의 snapshot date가 `%DATA_DATE%` 또는 최신 이전 snapshot date일 수 있다. `no_execution_candidates=true`이면 이 mismatch는 blocker가 아니라 warning이다.
- review template date mismatch는 no-action day에도 blocker다.

## 6. Manual Review 운영

### 6.1 Template Export

```cmd
python scripts\export_paper_to_notion.py --manual-review-template --account-id %ACCOUNT_ID% --date %TRADE_DATE% --confirm-actual --json
```

성격:

- Notion write.
- 사용자 승인 필요.

정상:

- candidate count 확인.
- row create/update 확인.
- failed count 0.

### 6.2 Notion Manual Review 입력

Manual Reviews DB에서 아래 속성을 확인하거나 입력한다.

- `Account ID`: `%ACCOUNT_ID%`와 일치.
- `Review Date`: `%TRADE_DATE%`와 일치.
- `Symbol`
- `Question ID`
- `Question`
- `Manual Answer`: append 전 필수.
- `Review Status`: 답변 완료 후 reviewed/REVIEWED.
- `Import Status`: preview/append 대상으로 보내려면 `READY`.
- `Follow Up Needed`: 필요 시 입력.
- `Review Tag`: 필요 시 입력. 예: execution quality, position sizing, risk management.
- `Reviewer Note`: 선택.
- `Validation Status` / `Validation Message`: sync 이후 확인.

중요:

- `Manual Answer`만 작성하면 충분하지 않다.
- `Review Status=reviewed`만으로도 충분하지 않다.
- importer는 `Import Status=READY` row를 조회한다. row가 `DRAFT`에 남아 있으면 preview가 `candidate_count=0`을 반환할 수 있다.

### 6.3 Review Preview

```cmd
python scripts\import_notion_reviews.py --date %TRADE_DATE% --account-id %ACCOUNT_ID% --preview --json
```

성격:

- Notion read + preview artifact 생성.
- review log append는 하지 않음.
- 자동화 가능.

정상:

- `candidate_count`가 해당 account/date에서 READY 처리한 Notion review row 수와 일치.
- `fail_count=0`.
- `append_allowed`가 true 또는 검토 가능한 true-with-warnings.

`candidate_count=0`이면 확인할 것:

- `Import Status=READY`
- `Review Status=reviewed` 또는 `REVIEWED`
- `Manual Answer`가 비어 있지 않음
- `Account ID=%ACCOUNT_ID%`
- `Review Date=%TRADE_DATE%`
- Notion view filter가 관련 row를 숨기고 있지 않은지

### 6.4 Review Append

```cmd
python scripts\import_notion_reviews.py --date %TRADE_DATE% --account-id %ACCOUNT_ID% --commit --preview-json "<REVIEW_PREVIEW_JSON>" --json
```

성격:

- local review log source-of-truth append.
- 사용자 승인 필요.

실행 전 확인:

- preview JSON/summary 검토.
- `fail_count=0`.
- duplicate warning이 있으면 `--allow-warnings` 사용 전 명시적으로 수용.

정상:

- status committed.
- appended count가 예상 row 수와 일치.
- failed count 0.
- backup/report path 출력.

### 6.5 Review Status Sync

```cmd
python scripts\sync_notion_review_status.py --date %TRADE_DATE% --account-id %ACCOUNT_ID% --commit-report "<REVIEW_COMMIT_REPORT>" --json
```

성격:

- Notion status field write.
- 사용자 승인 필요.

정상:

- sync 성공.
- updated count가 appended row 수와 일치.
- failed count 0.
- `Import Status` / validation field가 committed review import 결과를 반영.

append가 성공한 뒤 Notion sync만 실패했다면 local review log를 rollback하지 않는다. Notion/schema/auth 문제를 고친 뒤 같은 commit report로 재시도한다.

## 7. EOD 운영

### 7.1 EOD Dry-Run

```cmd
python scripts\paper.py eod --date %TRADE_DATE% --account-id %ACCOUNT_ID% --dry-run
```

성격:

- read-only.
- 자동화 가능.

확인할 필드:

- `no_action_day`
- `execution_candidate_count`
- `ready_preview_count`
- `would_append_execution_log`
- `would_write_current_state`
- `would_write_account_snapshot`
- `would_write_position_snapshot`
- `source_snapshot_date`
- `target_snapshot_date`
- `write_performed`

일반 실행일:

- `ready_preview_count`가 0보다 클 수 있다.
- `would_append_execution_log=true`일 수 있다.

no-action day:

- `no_action_day=true`
- `ready_preview_count=0`
- `would_append_execution_log=false`
- account state 재구성과 market valuation이 가능하면 current-state/account-snapshot/position-snapshot write intent가 true여야 한다.

### 7.2 EOD Commit

```cmd
python scripts\paper.py eod --date %TRADE_DATE% --account-id %ACCOUNT_ID% --commit
```

성격:

- local ledger/state/snapshot write.
- 사용자 승인 필요.

실행 전 확인:

- EOD dry-run 결과를 검토했다.
- same-date replacement가 필요하지 않다.
- Orchestrator blocker가 없다.
- no-action day라면 `would_append_execution_log=false`를 확인했다.

정상:

- preflight PASS.
- `paper_current_state_YYYYMMDD.json` write 수행.
- account snapshot row write 수행.
- market valuation 성공 시 position snapshot row write 수행.
- no-action day에서는 `rows_appended=0`이 정상일 수 있다.
- `replaced_same_date=false`.

replacement guard:

- same-date replacement는 임의로 사용하지 않는다.
- `--replace`는 `paper.py commit` shortcut 경로에 있으며 명시 승인 필요.
- daily operation에서는 `eod --dry-run` 후 `eod --commit`을 우선 권장한다.

## 8. Final Status 확인

### 8.1 Local Paper Status

```cmd
python scripts\paper.py status --account-id %ACCOUNT_ID% --date %TRADE_DATE% --json
```

성공 기준:

- `workflow_status=REVIEW_DONE`
- `same_date_snapshot_exists=true`
- `current_state_exists=true`
- `account_snapshot_exists=true`
- `position_snapshot_exists=true`
- `review_progress_status=DONE`
- `errors=[]`
- `next_recommended_command="no immediate action"`

### 8.2 Orchestrator Final Status

local-only 확인:

```cmd
python scripts\paper_daily_ops.py status --account-id %ACCOUNT_ID% --data-date %DATA_DATE% --trade-date %TRADE_DATE% --json > outputs\orch_status.json
python -c "import json; p=json.load(open(r'outputs\orch_status.json',encoding='utf-8')); print(json.dumps(p.get('operator_summary'),ensure_ascii=False,indent=2))"
```

선택적 Notion live-read 확인:

```cmd
python scripts\paper_daily_ops.py status --account-id %ACCOUNT_ID% --data-date %DATA_DATE% --trade-date %TRADE_DATE% --json --include-notion-read > outputs\orch_status.json
python -c "import json; p=json.load(open(r'outputs\orch_status.json',encoding='utf-8')); print(json.dumps(p.get('operator_summary'),ensure_ascii=False,indent=2))"
```

성공 기준:

- `workflow_status=REVIEW_DONE`
- `overall_status=PASS`
- `current_step=FINAL_STATUS`
- `current_step_status=DONE`
- `operator_message="Daily ops loop is complete."`
- `recommended_operator_action=NONE`
- `next_command=null`
- `warnings=[]`
- `blockers=[]`
- `terminal=true`
- `has_reconciliation_conflicts=false`
- `conflict_count=0`

주의:

- local-only Orchestrator status는 terminal일 수 있지만, 선택적 Notion live-read가 stale UI status 때문에 warning/conflict를 표시할 수 있다.
- local source-of-truth artifact가 맞다면 Notion live-read conflict는 UI/status reconciliation follow-up으로 본다.

## 9. Orchestrator `next_command` 사용 규칙

각 단계 후 Orchestrator status를 다시 실행한다. `operator_summary.next_command`가 있으면 기억에 의존한 명령보다 그 명령을 우선 사용한다.

`command_type`과 `risk_level`을 실행 gate로 사용한다.

- `READ_ONLY`: 자동화 가능. 예: status, data-freshness, preview, EOD dry-run.
- `NOTION_WRITE`: Notion create/update/sync write. 사용자 승인 필요.
- `LEDGER_WRITE`: local ledger/review log/snapshot/source-of-truth write. preview 검토와 사용자 승인 필요.
- `UNKNOWN`: 자동 실행 금지. 명령 의미를 확인한 뒤 수동 실행.

`recommended_operator_action`별 운영:

- `RUN_NEXT_COMMAND`: command type 확인 후 실행.
- `WAIT_FOR_INPUT`: Notion 또는 사용자 수동 입력 대기.
- `RUN_COMMIT`: preview output 검토 후 승인 필요.
- `RUN_SYNC`: commit report 검토 후 승인 필요.
- `RESOLVE_CONFLICT`: risky command 실행 금지. conflict 먼저 해결.
- `NONE`: 완료 또는 즉시 실행할 작업 없음.

## 10. Troubleshooting

### Freshness FAIL

- `%DATA_DATE%`에 대해 `prepare-data`를 실행했는지 확인.
- `daily_price`, `daily_indicators`, `market_index` max date 확인.
- `%DATA_DATE%`가 실제 미국 거래일인지 확인.
- freshness가 해결되기 전 plan 실행 금지.

### Freshness PASS_WITH_WARNINGS

- warning line을 모두 확인.
- 단독 freshness 명령은 warning 상태로 종료될 수 있지만 explicit-date plan은 strict freshness 때문에 중단될 수 있다.
- 원인을 확인한 뒤 `prepare-data` 재실행 또는 `%DATA_DATE%` 조정을 결정한다.

### Plan Candidate Count 0

- 정상일 수 있다.
- Orchestrator가 Manual Execution 단계를 no-op `DONE` 처리하는지 확인.
- Daily Review로 진행.
- final closure 전에 EOD no-action roll-forward가 필요할 수 있다.

### Manual Execution Preview `candidate_count=0`

- no-action day이면 정상일 수 있다.
- 그 외에는 Notion의 `Actual Price`, `Status=READY`, `Account ID`, `Execution Date`를 확인한다.

### Manual Review Preview `candidate_count=0`

- `Manual Answer` 확인.
- `Review Status=reviewed` 확인.
- `Import Status=READY` 확인.
- `Account ID` 확인.
- `Review Date` 확인.

### EOD Warning: No READY_FOR_PAPER_TRADE Previews To Append

- no-action day이면 정상일 수 있다.
- `no_action_day=true` 확인.
- `would_append_execution_log=false` 확인.
- commit 전 current-state/account-snapshot/position-snapshot write intent가 true인지 확인.

### Final Status WARNING 또는 BLOCKED

- `paper.py status`와 Orchestrator status를 모두 확인.
- `workflow_status`가 아직 `PLAN_READY`인지 확인.
- `same_date_snapshot_exists` 확인.
- `review_progress_status` 확인.
- Orchestrator `blockers`, `warnings`, reconciliation conflict 확인.

## 11. 안전 경계

자동화 가능:

- `python scripts\paper_daily_ops.py status ...`
- `python scripts\paper.py status ...`
- `python scripts\paper.py data-freshness ...`
- `python scripts\import_notion_executions.py --preview ...`
- `python scripts\import_notion_reviews.py --preview ...`
- `python scripts\paper.py eod ... --dry-run`

승인 필요:

- `python scripts\paper.py prepare-data ...`
- `python scripts\paper.py prepare ...`
- `python scripts\paper.py plan ...`
- `python scripts\export_paper_to_notion.py ... --confirm-actual`
- `python scripts\import_notion_executions.py --commit ...`
- `python scripts\import_notion_reviews.py --commit ...`
- `python scripts\sync_notion_execution_status.py ...`
- `python scripts\sync_notion_review_status.py ...`
- `python scripts\paper.py eod ... --commit`
- `python scripts\paper.py commit ...`

자동 실행 금지:

- broker/API/order command
- preview 검토 없는 `import_notion_* --commit`
- dry-run 검토 없는 `paper.py eod --commit`
- 명시 승인 없는 `paper.py commit`
- `--replace` 사용
- generated source-of-truth output 수동 수정/복사

## 12. 매일 운영 체크리스트

- [ ] `ACCOUNT_ID` 확인.
- [ ] `DATA_DATE`가 최신 완료 미국장 데이터 날짜인지 확인.
- [ ] `TRADE_DATE`가 다음 운영/거래 날짜인지 확인.
- [ ] 초기 Orchestrator status 확인.
- [ ] data refresh가 필요하고 승인됐으면 `prepare-data` 실행 완료.
- [ ] `data-freshness` 결과 `PASS` 확인.
- [ ] Daily Plan 생성 완료.
- [ ] 승인 후 Daily Plan Notion export 완료.
- [ ] Manual Execution 필요 여부 확인.
- [ ] Execution preview/commit/sync 완료 또는 no-op path 확인.
- [ ] Daily Review 생성 완료.
- [ ] 승인 후 Manual Review Template export 완료.
- [ ] Notion Manual Review row 작성 완료.
- [ ] Review preview/append/sync 완료.
- [ ] EOD dry-run 검토 완료.
- [ ] 필요 시 승인 후 EOD commit 실행.
- [ ] `paper.py status`가 `REVIEW_DONE`인지 확인.
- [ ] Orchestrator가 `PASS` / `terminal=true`인지 확인.
- [ ] generated outputs와 live account artifact를 git commit하지 않음.

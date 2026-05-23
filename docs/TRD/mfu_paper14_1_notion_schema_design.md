# MFU-PAPER14-1 Notion Schema Design

## 1. Scope

이번 PAPER14-1은 Notion DB schema & export mapping 설계이며, Notion API 구현과 데이터 export는 포함하지 않는다.

이번 단계는 설계/문서화 전용이다.

- Notion API 호출 없음
- 실제 Notion DB 생성 없음
- 실제 데이터 sync 없음
- review 입력 연동 없음
- paper 원장 CSV 수정 없음

## 2. Notion Usage Purpose

Notion의 목적은 시스템이 생성한 정보를 쉽게 읽고, 운영 기록을 보관하고, 나중에 수동 review 입력 UI로 확장하는 것이다.

Notion은 다음 역할만 가진다.

- presentation layer
- operator review layer
- manual note hub
- later-stage manual workflow surface

Notion은 다음 역할을 가지지 않는다.

- 계산 엔진
- paper 원장의 원천 저장소
- SQLite / CSV / JSON 대체 저장소
- 전략 의사결정 source of truth

## 3. Phase Split

### Phase 1: Read-only export

1차 단방향 export 대상:

- Weekly Reports
- Benchmark Reports
- Daily Plans
- Account Snapshots
- Daily Review Summaries
- Performance Summaries

### Phase 2: Manual review input surface

2차 입력 연동 대상:

- Manual Reviews

정책:

- 1차에서는 Python -> Notion 단방향 export만 한다.
- Notion에서 수정한 값은 시스템으로 다시 읽어오지 않는다.
- 2차에서만 review 입력 연동을 별도 MFU로 다룬다.

## 4. Recommended Notion Workspace Structure

```text
Paper Trading Hub
├─ Weekly Reports DB
├─ Benchmark Reports DB
├─ Daily Plans DB
├─ Account Snapshots DB
├─ Daily Review Summaries DB
├─ Performance Summaries DB
└─ Manual Reviews DB
```

## 5. Common Property Policy

모든 DB에 공통으로 둘 속성 후보:

- `Name`
- `External Key`
- `Source Type`
- `Source Path`
- `JSON Path`
- `Markdown Path`
- `Synced At`
- `Sync Status`
- `Schema Version`

권장 Notion property type:

- `Name` -> `Title`
- `External Key` -> `Rich text`
- 날짜 -> `Date`
- 상태값 -> `Select`
- 숫자 -> `Number`
- 비율 -> `Number`
- 긴 설명 -> `Rich text`
- 파일 경로 -> `Rich text`

정책:

- Notion DB 속성명은 영어로 시작한다.
- Python은 JSON field -> Notion property name mapping layer를 통해 속성명을 해석한다.
- 나중에 한글 속성명으로 바꾸더라도 mapping 파일만 수정하면 export 코드는 유지되게 설계한다.

## 6. External Key Policy

모든 export 대상은 중복 생성을 막기 위해 `External Key`를 가진다.

추천 key:

- `weekly_report:{actual_start}:{actual_end}`
- `benchmark:{latest_snapshot_date}:{run_mode}`
- `daily_plan:{date}`
- `account_snapshot:{snapshot_date}`
- `daily_review_summary:{date_or_latest_snapshot_date}`
- `performance_summary:{latest_snapshot_date_or_latest}`
- `manual_review:{review_key}`

향후 upsert 정책:

- External Key가 있으면 update
- External Key가 없으면 create

이번 단계에서는 정책만 설계하고 구현하지 않는다.

## 7. Mapping Layer Design

Python 코드가 Notion property name을 직접 하드코딩하지 않도록 mapping layer를 둔다.

예시:

```json
{
  "weekly_reports": {
    "period.actual_start": "Period Start",
    "period.actual_end": "Period End",
    "overall_status": "Overall Status",
    "period.coverage_status": "Coverage Status",
    "period.snapshot_count": "Snapshot Count",
    "account_summary.end_equity_market_value": "End Equity"
  }
}
```

추후 한글 속성명 전환 예시:

```json
{
  "weekly_reports": {
    "period.actual_start": "기간 시작",
    "period.actual_end": "기간 종료",
    "overall_status": "전체 상태"
  }
}
```

권장 구현 단위:

- source type별 mapping section
- JSON path -> Notion property name
- property type metadata는 문서 또는 별도 schema table로 유지

## 8. DB-by-DB Schema Design

### 8.1 Weekly Reports DB

목적:

- weekly operator summary archive
- status / gap / equity change review entrypoint

source file:

- `outputs/paper_test/reports/paper_weekly_status_summary.json`
- `outputs/paper_test/reports/paper_weekly_status_summary.md`

권장 properties:

- `Name`
- `External Key`
- `Period Start`
- `Period End`
- `Latest Snapshot Date`
- `Coverage Status`
- `Overall Status`
- `Snapshot Count`
- `End Equity`
- `Equity Change %`
- `Cash Ratio`
- `Trade Count`
- `Gap Count`
- `High Gap Count`
- `Markdown Path`
- `JSON Path`
- `Schema Version`
- `Synced At`

추천 mapping 예:

- `period.actual_start` -> `Period Start`
- `period.actual_end` -> `Period End`
- `latest_snapshot_date` -> `Latest Snapshot Date`
- `period.coverage_status` -> `Coverage Status`
- `overall_status` -> `Overall Status`
- `period.snapshot_count` -> `Snapshot Count`
- `account_summary.end_equity_market_value` -> `End Equity`
- `account_summary.equity_change_pct` -> `Equity Change %`
- `account_summary.end_cash_ratio_market_value` -> `Cash Ratio`

page body:

- Markdown summary 본문
- 또는 operation gaps / recommended actions condensed text

1차 export 여부:

- 포함

2차 입력 연동 여부:

- 없음

### 8.2 Benchmark Reports DB

목적:

- paper vs SPY / QQQ / CASH comparison archive

source file:

- `outputs/paper_test/reports/paper_benchmark_comparison.json`
- `outputs/paper_test/reports/paper_benchmark_comparison.md`

권장 properties:

- `Name`
- `External Key`
- `Latest Snapshot Date`
- `Run Mode`
- `Official Run`
- `Availability Status`
- `Paper Return`
- `SPY Return`
- `QQQ Return`
- `CASH Return`
- `Excess vs SPY`
- `Excess vs QQQ`
- `Excess vs CASH`
- `Paper MDD`
- `SPY MDD`
- `QQQ MDD`
- `Markdown Path`
- `JSON Path`
- `Schema Version`
- `Synced At`

추천 mapping 예:

- `latest_snapshot_date` -> `Latest Snapshot Date`
- `run_mode` -> `Run Mode`
- `official_run` -> `Official Run`
- `availability_status` -> `Availability Status`
- `summary.paper.paper_return` -> `Paper Return`
- `summary.benchmarks.SPY.benchmark_return` -> `SPY Return`
- `summary.benchmarks.QQQ.benchmark_return` -> `QQQ Return`
- `summary.benchmarks.CASH.benchmark_return` -> `CASH Return`
- `summary.benchmarks.SPY.excess_return` -> `Excess vs SPY`

page body:

- Markdown benchmark comparison 본문

1차 export 여부:

- 포함

2차 입력 연동 여부:

- 없음

### 8.3 Daily Plans DB

목적:

- daily action plan archive
- plan-date / regime / warning-level review

source file:

- `outputs/paper_test/daily_action_plan_YYYYMMDD.md`

권장 properties:

- `Name`
- `External Key`
- `Plan Date`
- `Regime`
- `Confirmed Trade Count`
- `Review Item Count`
- `Warning Count`
- `Action Plan Path`
- `Source Type`
- `Synced At`

page body:

- `daily_action_plan_YYYYMMDD.md` 본문

비고:

- plan markdown은 section parsing이 필요할 수 있다.
- 1차에서는 page body 중심 export + 최소 metadata extraction만 권장한다.

1차 export 여부:

- 포함

2차 입력 연동 여부:

- 없음

### 8.4 Account Snapshots DB

목적:

- daily account state ledger mirror

source file:

- `outputs/paper_test/paper_account_snapshot.csv`

권장 properties:

- `Name`
- `External Key`
- `Snapshot Date`
- `Initial Cash`
- `Cash`
- `Total Equity Market Value`
- `Total Equity Cost Basis`
- `Unrealized PnL`
- `Cash Ratio Market Value`
- `Cash Ratio Cost Basis`
- `Position Count`
- `Symbols`
- `Valuation Status`
- `Valuation Price Date`
- `Synced At`

추천 mapping 예:

- `snapshot_date` -> `Snapshot Date`
- `initial_cash` -> `Initial Cash`
- `cash` -> `Cash`
- `total_equity_market_value` -> `Total Equity Market Value`
- `total_equity_cost_basis` -> `Total Equity Cost Basis`
- `unrealized_pnl` -> `Unrealized PnL`
- `cash_ratio_market_value` -> `Cash Ratio Market Value`
- `cash_ratio_cost_basis` -> `Cash Ratio Cost Basis`
- `position_count` -> `Position Count`
- `symbols` -> `Symbols`
- `market_valuation_status` -> `Valuation Status`
- `valuation_price_date` -> `Valuation Price Date`

page body:

- 기본은 없음
- 필요 시 selected metadata note 추가 가능

1차 export 여부:

- 포함

2차 입력 연동 여부:

- 없음

### 8.5 Daily Review Summaries DB

목적:

- operator-facing daily review summary archive

source file:

- `outputs/paper_test/reports/paper_daily_review_summary.md`

권장 properties:

- `Name`
- `External Key`
- `Review Date`
- `Latest Snapshot Date`
- `Review Summary Path`
- `Schema Version`
- `Synced At`

page body:

- `paper_daily_review_summary.md` 본문

주의:

- latest overwrite 구조다.
- historical truth source가 아니라 export 시점 archive page로 취급한다.

1차 export 여부:

- 포함

2차 입력 연동 여부:

- 없음

### 8.6 Performance Summaries DB

목적:

- latest account-level performance summary archive

source file:

- `outputs/paper_test/reports/paper_performance_summary.md`

권장 properties:

- `Name`
- `External Key`
- `Latest Snapshot Date`
- `Performance Summary Path`
- `Schema Version`
- `Synced At`

page body:

- `paper_performance_summary.md` 본문

주의:

- latest overwrite 구조다.
- export 시점 archive page로 취급한다.

1차 export 여부:

- 포함

2차 입력 연동 여부:

- 없음

### 8.7 Manual Reviews DB

목적:

- manual review workflow의 future bidirectional surface

source file:

- `outputs/paper_test/reviews/paper_manual_review_log_template.csv`
- `outputs/paper_test/reviews/paper_manual_review_log.csv`

권장 properties:

- `Name`
- `External Key`
- `Review Date`
- `Symbol`
- `Review Type`
- `Bucket`
- `Severity`
- `Status`
- `Decision`
- `Action`
- `Note`
- `Source`
- `Synced At`
- `Appended At`

정책:

- Manual Reviews DB는 2차 양방향 연동 대상이다.
- 초기에는 export / import 구현을 하지 않는다.

1차 export 여부:

- 제외

2차 입력 연동 여부:

- 포함 예정

## 9. Config File Design

### 9.1 notion_settings.example.json

```json
{
  "enabled": false,
  "token_env": "NOTION_TOKEN",
  "data_sources": {
    "weekly_reports": "",
    "benchmark_reports": "",
    "daily_plans": "",
    "account_snapshots": "",
    "daily_review_summaries": "",
    "performance_summaries": "",
    "manual_reviews": ""
  }
}
```

설명:

- 실제 token은 저장하지 않는다.
- 실제 DB ID도 저장하지 않는다.
- runtime은 `NOTION_TOKEN` 환경변수를 읽는다.

### 9.2 notion_property_mapping.example.json

```json
{
  "weekly_reports": {
    "period.actual_start": "Period Start",
    "period.actual_end": "Period End",
    "overall_status": "Overall Status"
  },
  "benchmark_reports": {
    "latest_snapshot_date": "Latest Snapshot Date",
    "summary.paper.paper_return": "Paper Return"
  }
}
```

## 10. Security Policy

- `NOTION_TOKEN`은 환경변수로만 관리한다.
- 실제 `notion_settings.json`은 repo에 커밋하지 않는다.
- 실제 DB ID는 example 파일에 넣지 않는다.
- 실제 운영용 설정 파일은 `.gitignore` 대상이어야 한다.
- token / DB ID / workspace private metadata를 code constant로 하드코딩하지 않는다.

## 11. Export Layer Recommendation

향후 구현 시 export layer는 아래 순서를 권장한다.

1. source JSON / CSV / Markdown 로드
2. normalized payload 생성
3. mapping layer로 Notion property names resolve
4. external key 조회
5. upsert 판단
6. page body / property payload 구성
7. Notion API write

이번 단계에서는 1~3 설계만 다룬다.

## 12. Recommended Rollout Order

Notion 연동 구현 순서 권장:

1. Weekly Reports
2. Benchmark Reports
3. Account Snapshots
4. Daily Plans
5. Daily Review Summaries
6. Performance Summaries
7. Manual Reviews

이유:

- Weekly / Benchmark는 JSON schema가 비교적 안정화되어 있다.
- Account snapshot은 row-based source라 sync semantics가 단순하다.
- Daily review / performance markdown은 overwrite 구조라 export timing policy를 먼저 정해야 한다.
- Manual Reviews는 2차 양방향 설계와 연결된다.

## 13. Risks / Notes

- latest overwrite markdown reports는 historical source가 아니라 archive page source로 봐야 한다.
- Daily Plans DB는 markdown parsing complexity가 가장 크다.
- Manual Reviews DB는 2차 양방향 설계 없이 먼저 구현하면 source-of-truth 혼선이 생길 수 있다.
- property rename을 직접 코드에서 처리하면 추후 한글 속성명 전환 비용이 커진다. mapping layer를 유지해야 한다.

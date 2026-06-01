# MFU-PAPER14-1 작업 지시문: Notion DB schema & export mapping 설계

## 목적

PAPER14-1의 목표는 paper trading 시스템에서 생성되는 주요 정보를 Notion에 읽기 전용으로 export하기 위한 Notion DB schema, mapping layer, external key, 설정 파일 구조를 설계하는 것이다.

이번 단계는 설계/문서화 전용이다.  
Notion API 호출, 실제 DB 생성, 데이터 export 구현, review 입력 연동은 하지 않는다.

반드시 명시:

```text
이번 PAPER14-1은 Notion DB schema & export mapping 설계이며, Notion API 구현, 실제 데이터 동기화, review 입력 연동은 포함하지 않는다.
```

## 확정 정책

아래 정책을 전제로 설계한다.

```text
1. Notion은 원천 데이터 저장소가 아니라 presentation / review layer다.
2. 1차 연동은 Python → Notion 단방향 export만 한다.
3. Notion에서 수정한 값은 1차 단계에서 시스템으로 다시 가져오지 않는다.
4. 원천 데이터는 CSV / JSON / Markdown / SQLite다.
5. Notion DB 속성명은 영어로 시작한다.
6. Python에는 JSON field → Notion property mapping layer를 둔다.
7. 추후 한글 속성명으로 바꾸더라도 mapping 파일만 수정하면 되게 설계한다.
8. Notion DB는 사용자가 Notion UI에서 직접 만들고, Python은 DB ID를 설정 파일로 받아 사용한다.
9. token은 환경변수로 관리한다.
10. DB ID와 property mapping은 gitignore된 설정 파일 또는 example 파일로 관리한다.
```

## 설계 대상 Notion DB

아래 7개 DB를 설계한다.

```text
1. Weekly Reports DB
2. Benchmark Reports DB
3. Daily Plans DB
4. Account Snapshots DB
5. Daily Review Summaries DB
6. Performance Summaries DB
7. Manual Reviews DB
```

단, 1차 구현 대상은 읽기 전용 export다.

```text
1차 읽기 전용 export:
- Weekly Reports
- Benchmark Reports
- Daily Plans
- Account Snapshots
- Daily Review Summaries
- Performance Summaries

2차 입력 연동:
- Manual Reviews
```

## 산출물

작성할 문서:

```text
docs/TRD/mfu_paper14_1_notion_schema_design.md
```

선택적으로 example 설정 파일 초안 작성:

```text
config/notion_settings.example.json
config/notion_property_mapping.example.json
```

주의:

```text
실제 token이나 실제 database id는 절대 작성하지 않는다.
notion_settings.json 같은 실제 설정 파일은 생성하지 않거나, 생성하더라도 .gitignore 대상임을 문서화한다.
```

## 문서에 포함할 내용

### 1. Notion 사용 목적

아래를 명확히 쓴다.

```text
Notion의 목적은 시스템이 생성한 정보를 쉽게 읽고, 운영 기록을 보관하고, 나중에 수동 review 입력 UI로 확장하는 것이다.
Notion은 계산 엔진이나 paper 원장의 원천 저장소가 아니다.
```

### 2. 전체 Notion 구조

추천 구조:

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

### 3. 공통 속성 정책

모든 DB에 공통으로 둘 속성 후보:

```text
Name
External Key
Source Type
Source Path
JSON Path
Markdown Path
Synced At
Sync Status
Schema Version
```

Notion property type 후보:

```text
Name -> Title
External Key -> Rich text
Date 계열 -> Date
상태값 -> Select
숫자 -> Number
비율 -> Number, Notion 표시 형식은 percent 후보
긴 설명 -> Rich text
파일 경로 -> Rich text 또는 URL 후보
```

### 4. External Key 정책

중복 생성을 막기 위해 모든 export 대상에는 External Key를 둔다.

추천 key:

```text
weekly_report:{actual_start}:{actual_end}
benchmark:{latest_snapshot_date}:{run_mode}
daily_plan:{date}
account_snapshot:{snapshot_date}
daily_review_summary:{date_or_latest_snapshot_date}
performance_summary:{latest_snapshot_date_or_latest}
manual_review:{review_key}
```

정책:

```text
External Key가 있으면 update
External Key가 없으면 create
```

이번 단계에서는 정책만 설계하고 구현하지 않는다.

### 5. Mapping Layer 설계

Python 코드가 Notion property name을 직접 하드코딩하지 않도록 mapping layer를 설계한다.

예시 구조:

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

추후 한글 속성명으로 바꿀 경우:

```json
{
  "weekly_reports": {
    "period.actual_start": "기간 시작",
    "account_summary.end_equity_market_value": "최종 자산"
  }
}
```

### 6. DB별 schema 설계

각 DB에 대해 아래를 정리한다.

```text
목적
source file
Notion properties
property type
JSON/Markdown field mapping
External Key
page body에 넣을 내용
1차 export 여부
2차 입력 연동 여부
```

#### Weekly Reports DB

Source:

```text
outputs/paper_test/reports/paper_weekly_status_summary.json
outputs/paper_test/reports/paper_weekly_status_summary.md
```

속성 후보:

```text
Name
External Key
Period Start
Period End
Latest Snapshot Date
Coverage Status
Overall Status
Snapshot Count
End Equity
Equity Change %
Cash Ratio
Trade Count
Gap Count
High Gap Count
Markdown Path
JSON Path
Synced At
```

#### Benchmark Reports DB

Source:

```text
outputs/paper_test/reports/paper_benchmark_comparison.json
outputs/paper_test/reports/paper_benchmark_comparison.md
```

속성 후보:

```text
Name
External Key
Latest Snapshot Date
Run Mode
Official Run
Availability Status
Paper Return
SPY Return
QQQ Return
CASH Return
Excess vs SPY
Excess vs QQQ
Excess vs CASH
Paper MDD
SPY MDD
QQQ MDD
Markdown Path
JSON Path
Synced At
```

#### Daily Plans DB

Source:

```text
outputs/paper_test/daily_action_plan_YYYYMMDD.md
```

속성 후보:

```text
Name
External Key
Plan Date
Regime
Confirmed Trade Count
Review Item Count
Warning Count
Action Plan Path
Synced At
```

Page body:

```text
daily_action_plan_YYYYMMDD.md 본문 또는 주요 섹션
```

#### Account Snapshots DB

Source:

```text
outputs/paper_test/paper_account_snapshot.csv
```

속성 후보:

```text
Name
External Key
Snapshot Date
Initial Cash
Cash
Total Equity Market Value
Total Equity Cost Basis
Unrealized PnL
Cash Ratio Market Value
Cash Ratio Cost Basis
Position Count
Symbols
Valuation Status
Valuation Price Date
Synced At
```

#### Daily Review Summaries DB

Source:

```text
outputs/paper_test/reports/paper_daily_review_summary.md
```

속성 후보:

```text
Name
External Key
Review Date
Latest Snapshot Date
Review Summary Path
Synced At
```

Page body:

```text
paper_daily_review_summary.md 본문
```

#### Performance Summaries DB

Source:

```text
outputs/paper_test/reports/paper_performance_summary.md
```

속성 후보:

```text
Name
External Key
Latest Snapshot Date
Performance Summary Path
Synced At
```

Page body:

```text
paper_performance_summary.md 본문
```

주의:

```text
performance summary는 latest overwrite 구조이므로 historical source로 보지 않는다.
export 시점의 archive page로 취급한다.
```

#### Manual Reviews DB

Source:

```text
outputs/paper_test/reviews/paper_manual_review_log_template.csv
outputs/paper_test/reviews/paper_manual_review_log.csv
```

이번 단계에서는 입력 연동 설계만 한다.

속성 후보:

```text
Name
External Key
Review Date
Symbol
Review Type
Bucket
Severity
Status
Decision
Action
Note
Source
Synced At
Appended At
```

정책:

```text
Manual Reviews DB는 2차 양방향 연동 대상이다.
초기에는 export/import 구현하지 않는다.
```

## 설정 파일 설계

`config/notion_settings.example.json` 후보:

```json
{
  "enabled": false,
  "token_env": "NOTION_TOKEN",
  "databases": {
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

`config/notion_property_mapping.example.json` 후보:

```json
{
  "weekly_reports": {
    "period.actual_start": "Period Start",
    "period.actual_end": "Period End",
    "overall_status": "Overall Status"
  },
  "benchmark_reports": {
    "latest_snapshot_date": "Latest Snapshot Date",
    "summary.paper_return": "Paper Return"
  }
}
```

주의:

```text
실제 notion_settings.json은 .gitignore 대상이다.
NOTION_TOKEN은 환경변수로 둔다.
```

## 제외 범위

이번 단계에서 하지 않는다.

```text
Notion API 호출
Notion DB 자동 생성
실제 DB ID 입력
실제 token 입력
데이터 export 구현
upsert 구현
Markdown → Notion block 변환 구현
review import 구현
review append 연동
paper 원장 CSV 수정
reports 재생성
```

## 허용 작업

```text
문서 작성
설정 파일 example 작성
mapping example 작성
기존 JSON/Markdown 산출물 구조 확인
```

writer 명령은 실행하지 않는다.

## 검증

문서 작업이므로 테스트는 필수 아님.

허용:

```text
python scripts/paper.py weekly-status --json
python scripts/paper.py benchmark --json
Get-Content docs/TRD/mfu_paper14_1_notion_schema_design.md
```

금지:

```text
prepare 실행
preview 실행
commit 실행
review 실행
review-append 실행
Notion API 호출
paper 원장 CSV 수정
```

## 성공 기준

```text
Notion 사용 목적이 문서화된다.
1차 단방향 export와 2차 review 입력 연동이 분리된다.
Notion DB 목록이 확정된다.
각 DB의 source file과 property schema가 정리된다.
External Key 정책이 정리된다.
mapping layer 정책이 정리된다.
설정 파일 구조가 정리된다.
token/DB ID 보안 정책이 정리된다.
Notion API 구현은 하지 않는다.
paper 원장 CSV와 outputs/front_test는 수정하지 않는다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 변경 파일
3. Notion 사용 목적
4. 설계한 DB 목록
5. DB별 source file
6. DB별 주요 properties
7. External Key 정책
8. Mapping layer 정책
9. 설정 파일 구조
10. 보안 정책
11. 제외한 항목
12. 실행한 검증 명령
13. 코드 변경 여부
14. paper 원장 CSV 변경 여부
15. outputs/front_test 변경 여부
16. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER14-1은 Notion DB schema & export mapping 설계이며, Notion API 구현과 데이터 export는 포함하지 않는다.
```
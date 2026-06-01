# MFU-PAPER12-3 작업 지시문: weekly-status output schema stabilization

## 목적

PAPER12-3의 목표는 PAPER12-2에서 구현한 `weekly-status` Markdown/JSON 리포트의 출력 구조를 안정화하여, 추후 Notion, HTML, Obsidian, 대시보드 연동이 쉬운 형태로 정리하는 것이다.

이번 단계는 출력 품질 개선 및 데이터 포맷 정리 작업이다.

반드시 명시:

```text
이번 PAPER12-3은 weekly-status 출력 schema 안정화 작업이며, Notion API 연동, HTML 생성, CSV 생성, Streamlit UI, paper 원장 수정은 포함하지 않는다.
```

## 배경

PAPER12-2에서 아래 산출물이 생성됐다.

```text
outputs/paper_test/reports/paper_weekly_status_summary.md
outputs/paper_test/reports/paper_weekly_status_summary.json
```

현재 포함 항목:

```text
operation coverage
account summary
position summary
trade summary
review summary
operation gaps
recommended next actions
```

PAPER12-3에서는 새 기능을 크게 추가하지 않고, JSON/Markdown을 추후 외부 앱에서 안정적으로 읽을 수 있게 구조를 정리한다.

## 구현 파일

수정 후보:

```text
core/paper_weekly_status.py
scripts/generate_paper_weekly_status.py
scripts/paper.py
tests/test_paper_weekly_status.py
tests/test_paper_cli.py
docs/TRD/mfu_paper12_3_weekly_status_schema_stabilization.md
```

대규모 리팩토링은 금지한다.

## 핵심 요구사항

### 1. JSON schema_version 추가

JSON top-level에 schema version을 추가한다.

```json
{
  "schema_version": "paper_weekly_status.v1"
}
```

목적:

```text
추후 Notion/HTML/Streamlit 연동 시 JSON 구조 변경을 추적하기 위함
```

### 2. JSON top-level 구조 고정

최소 top-level 구조를 아래처럼 고정한다.

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

기존 필드명을 불필요하게 바꾸지 않는다.  
변경이 필요하면 TRD에 이유를 기록한다.

### 3. raw value 정책 고정

JSON에는 사람이 보기 좋게 포맷된 문자열보다 raw 값을 우선 저장한다.

정책:

```text
금액: number
비율: decimal number
날짜: YYYY-MM-DD 문자열
날짜/시간: ISO-like 문자열
통화: currency 필드로 분리
상태값: enum-like string
```

예:

```json
{
  "currency": "USD",
  "end_equity_market_value": 99827.61,
  "cash_ratio_market_value": 0.604489,
  "equity_change_pct": -0.0017
}
```

금지:

```json
{
  "end_equity_market_value": "$99,827.61",
  "cash_ratio_market_value": "60.45%"
}
```

단, Markdown에서는 최소한의 가독성 포맷을 허용한다.

### 4. period coverage semantics 정리

`period`에 아래 필드를 추가하거나 정리한다.

```json
{
  "period": {
    "basis": "snapshot_date",
    "requested_start": "YYYY-MM-DD",
    "requested_end": "YYYY-MM-DD",
    "actual_start": "YYYY-MM-DD",
    "actual_end": "YYYY-MM-DD",
    "included_snapshot_dates": [],
    "snapshot_count": 0,
    "coverage_status": "FULL|PARTIAL|EMPTY"
  }
}
```

정책:

```text
basis는 snapshot_date로 고정
snapshot_count = 0 -> EMPTY
요청 범위 내 일부 snapshot만 있으면 PARTIAL
요청 범위와 snapshot coverage가 충분히 일치하면 FULL
```

주의:

```text
calendar week 전체를 커버한다는 의미로 과장하지 않는다.
리포트는 snapshot_date 기준 rollup임을 Markdown에도 명시한다.
```

### 5. source_files metadata 추가

JSON에 source file 정보를 추가한다.

예:

```json
{
  "source_files": {
    "account_snapshot": {
      "path": "outputs/paper_test/paper_account_snapshot.csv",
      "exists": true,
      "latest_date": "2026-05-20"
    },
    "position_snapshot": {
      "path": "outputs/paper_test/paper_position_snapshot.csv",
      "exists": true,
      "latest_date": "2026-05-20"
    },
    "execution_log": {
      "path": "outputs/paper_test/paper_execution_log.csv",
      "exists": true,
      "row_count": 10
    }
  }
}
```

목적:

```text
나중에 리포트가 어떤 원천 파일을 기반으로 생성됐는지 추적 가능하게 함
```

### 6. operation_gaps code/severity 표준화

gap마다 최소한 아래 필드를 갖게 한다.

```json
{
  "date": "YYYY-MM-DD",
  "code": "MISSING_POSITION_SNAPSHOT",
  "severity": "HIGH",
  "message": "..."
}
```

필수 필드:

```text
date
code
severity
message
```

허용 severity:

```text
HIGH
MEDIUM
LOW
```

이번 단계에서는 gap별 장문 해설, operator_message, recommended_command는 추가하지 않는다.

### 7. Notion mapping 후보 문서화

Notion API 연동은 하지 않는다.  
다만 TRD 문서에 JSON 필드와 Notion DB 속성 후보를 정리한다.

예:

```text
period.actual_start -> Date
period.actual_end -> Date
overall_status -> Select
period.coverage_status -> Select
period.snapshot_count -> Number
account_summary.end_equity_market_value -> Number
account_summary.equity_change_pct -> Number
trade_summary.trade_count -> Number
operation_gaps.length -> Number
recommended_next_actions -> Text 또는 Relation 후보
markdown_report_path -> Text
json_report_path -> Text
```

### 8. Markdown 최소 개선

Markdown은 과하게 예쁘게 만들지 않는다.

다만 아래는 명확히 표시한다.

```text
- schema version
- period basis = snapshot_date
- coverage status
- included snapshot dates
- source files summary
```

금액/비율 포맷팅은 최소 수준만 허용한다.

## 제외 범위

이번 단계에서 하지 않는다.

```text
Notion API 연동
HTML 리포트 생성
CSV 산출물 추가
Streamlit UI 작성
Obsidian export
gap별 장문 operator action 설명 추가
과도한 Markdown 디자인 개선
paper 원장 CSV 수정
prepare/preview/commit/review 실행
reports 전체 재생성 로직 변경
```

## 테스트

수정/추가 테스트:

```text
tests/test_paper_weekly_status.py
tests/test_paper_cli.py
```

필수 테스트:

```text
1. JSON에 schema_version이 포함됨
2. JSON top-level 필드가 고정 구조를 만족함
3. period.basis가 snapshot_date로 기록됨
4. coverage_status가 FULL/PARTIAL/EMPTY 중 하나로 계산됨
5. included_snapshot_dates가 날짜 문자열 리스트로 출력됨
6. account_summary 숫자값이 문자열이 아닌 number로 출력됨
7. 비율값이 % 문자열이 아닌 decimal number로 출력됨
8. source_files metadata가 포함됨
9. operation_gaps가 code/severity/message 필드를 포함함
10. severity가 HIGH/MEDIUM/LOW 외 값이면 실패
11. Markdown에 schema version과 coverage status가 표시됨
12. paper 원장 CSV를 수정하지 않음
13. outputs/front_test를 수정하지 않음
```

테스트는 임시 디렉터리와 임시 CSV를 사용한다.  
실제 paper 원장 파일은 수정하지 않는다.

## 검증 명령

```text
set PYTHONPATH=.

python -m pytest tests/test_paper_weekly_status.py tests/test_paper_cli.py -q
python -m py_compile core/paper_weekly_status.py
python -m py_compile scripts/generate_paper_weekly_status.py
python -m py_compile scripts/paper.py

python scripts/paper.py weekly-status
python scripts/paper.py weekly-status --json
```

주의:

```text
weekly-status는 reports 폴더의 Markdown/JSON 산출물을 갱신할 수 있다.
paper 원장 CSV는 수정하지 않는다.
```

## 성공 기준

```text
weekly-status JSON에 schema_version이 추가된다.
JSON top-level 구조가 안정화된다.
raw value 정책이 적용된다.
period coverage semantics가 명확해진다.
source_files metadata가 포함된다.
operation_gaps code/severity가 표준화된다.
Notion mapping 후보가 TRD에 문서화된다.
Markdown은 snapshot_date 기준 리포트임을 명확히 표시한다.
Notion/HTML/CSV/Streamlit 연동은 구현하지 않는다.
paper 원장 CSV와 outputs/front_test는 수정하지 않는다.
테스트가 통과한다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 변경 파일
3. JSON schema 변경 사항
4. period coverage 변경 사항
5. raw value 정책 적용 내용
6. source_files metadata
7. operation_gaps 표준화
8. Markdown 변경 사항
9. Notion mapping 문서화 내용
10. 제외한 항목
11. 테스트 결과
12. 실제 weekly-status 실행 결과
13. paper 원장 CSV 변경 여부
14. outputs/front_test 변경 여부
15. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER12-3은 weekly-status output schema stabilization 작업이며, Notion API 연동, HTML/CSV 생성, paper 원장 수정은 포함하지 않는다.
```
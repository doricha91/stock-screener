# MFU-PAPER11-10 작업 지시문: paper.py status 명령 추가

## 목적

PAPER11-10의 목표는 `scripts/paper.py status` 명령을 추가해, paper 운영 루프가 현재 어디까지 진행됐는지 한눈에 확인할 수 있게 하는 것이다.

이번 단계는 read-only 운영 상태 요약 기능이다.  
prepare-data, plan, eod commit, reports, review append를 실행하지 않는다.

반드시 명시:

```text
이번 PAPER11-10은 paper.py status 구현이며, 데이터 수집, plan 생성, EOD commit, reports 재생성, review append는 포함하지 않는다.
```

## 배경

현재 운영용 shortcut은 아래 4개다.

```text
paper.py prepare --date YYYYMMDD
paper.py preview --date YYYYMMDD
paper.py commit --date YYYYMMDD
paper.py review
```

PAPER11-9에서는 같은 날짜 snapshot이 이미 있으면 `paper.py commit`을 기본 차단하고, `--replace`가 있을 때만 재실행을 허용하는 guard를 추가했다.

이제 운영자가 자주 확인해야 할 질문은 다음이다.

```text
오늘 prepare 했나?
preview 했나?
commit 했나?
review 했나?
최신 snapshot 날짜는?
reports는 최신 snapshot을 반영했나?
같은 날짜 commit이 이미 된 상태인가?
```

## 구현 파일

수정:

```text
scripts/paper.py
tests/test_paper_cli.py
docs/TRD/mfu_paper11_10_paper_status.md
```

권장 추가:

```text
core/paper_status.py
tests/test_paper_status.py
```

대규모 리팩토링은 금지한다.

## CLI 요구사항

추가 명령:

```text
python scripts/paper.py status
python scripts/paper.py status --date YYYYMMDD
```

선택 옵션:

```text
--json
--verbose
```

`--json`은 기계 판독용 출력이 필요할 때만 사용한다.  
기본은 사람이 읽기 쉬운 콘솔 출력이다.

## status 기본 동작

### 1. 날짜 미지정

```text
python scripts/paper.py status
```

동작:

```text
latest daily_action_plan date 확인
latest paper_current_state date 확인
latest account snapshot date 확인
latest position snapshot date 확인
latest reports 상태 확인
latest review template / validation 상태 확인
```

### 2. 날짜 지정

```text
python scripts/paper.py status --date 20260520
```

동작:

```text
해당 날짜 기준으로 prepare/preview/commit/review 진행 여부를 추정한다.
```

## 확인할 파일

### paper plan

```text
outputs/paper_test/daily_action_plan_YYYYMMDD.md
```

있으면:

```text
plan_exists: true
```

### current state

```text
outputs/paper_test/paper_current_state_YYYYMMDD.json
```

있으면:

```text
current_state_exists: true
```

### account snapshot

```text
outputs/paper_test/paper_account_snapshot.csv
```

확인:

```text
snapshot_date == YYYY-MM-DD row 존재 여부
latest snapshot_date
cash
total_equity_market_value
unrealized_pnl
position_count
symbols
```

### position snapshot

```text
outputs/paper_test/paper_position_snapshot.csv
```

확인:

```text
snapshot_date == YYYY-MM-DD row 존재 여부
해당 날짜 row count
symbols
latest snapshot_date
```

### execution log

```text
outputs/paper_test/paper_execution_log.csv
```

확인:

```text
row count
latest trade date
해당 날짜 trade row count
```

단, 거래 없는 날은 row가 없어도 정상일 수 있다.

### reports

```text
outputs/paper_test/reports/paper_daily_review_summary.md
outputs/paper_test/reports/paper_performance_summary.md
```

확인:

```text
파일 존재 여부
modified time
가능하면 latest snapshot date가 report 내용 또는 summary에 반영됐는지
```

복잡하면 1차 구현에서는 존재 여부와 modified time만 확인한다.

### review

```text
outputs/paper_test/reviews/paper_manual_review_log_template.csv
outputs/paper_test/reviews/paper_manual_review_log_validation_report.md
outputs/paper_test/reviews/paper_manual_review_log.csv
```

확인:

```text
template exists
template row count
validation report exists
validation PASS 여부
manual review log exists
manual review log row count
```

## 운영 상태 판정

상태는 아래처럼 요약한다.

```text
NO_PLAN
PLAN_READY
COMMITTED
REVIEW_READY
UNKNOWN_OR_INCOMPLETE
```

권장 판정:

```text
plan 없음 -> NO_PLAN
plan 있음, commit snapshot 없음 -> PLAN_READY
account/position/current_state snapshot 있음 -> COMMITTED
reports + review template + validation PASS -> REVIEW_READY
중간 파일 불일치 -> UNKNOWN_OR_INCOMPLETE
```

추가로 다음 안내를 출력한다.

```text
next_recommended_command
```

예:

```text
NO_PLAN -> paper.py preview --date YYYYMMDD
PLAN_READY -> paper.py commit --date YYYYMMDD
COMMITTED -> paper.py review
REVIEW_READY -> no immediate action
```

단, `preview`는 plan을 생성하므로 plan이 없을 때 next command는 `preview`가 맞다.

## 출력 예시

```text
PAPER STATUS
  date: 2026-05-20
  workflow_status: REVIEW_READY
  latest_snapshot_date: 2026-05-20
  daily_action_plan: exists
  current_state: exists
  account_snapshot: exists
  position_snapshot: exists
  execution_log_rows_for_date: 0
  reports: exists
  review_template: exists
  review_validation: PASS
  next_recommended_command: no immediate action
```

## 안전 원칙

status는 read-only다.

금지:

```text
prepare-data 실행
data-freshness 실행
plan 생성
eod dry-run 실행
eod commit 실행
reports 재생성
review-template 생성
review-validate 실행
review-append 실행
DB write
paper CSV 수정
outputs/front_test 수정
```

## 테스트

추가/수정 테스트:

```text
tests/test_paper_status.py
tests/test_paper_cli.py
```

필수 테스트:

```text
1. paper.py --help에 status 표시
2. status --date가 지정 날짜 파일들을 조회
3. daily_action_plan 없으면 NO_PLAN
4. plan 있고 commit snapshot 없으면 PLAN_READY
5. current_state/account/position snapshot 있으면 COMMITTED
6. reports + review validation PASS면 REVIEW_READY
7. execution log row가 없어도 거래 없는 날이면 error 처리하지 않음
8. account snapshot 최신 날짜를 올바르게 읽음
9. same-date snapshot 존재 여부를 표시
10. status는 writer 함수들을 호출하지 않음
11. --json 출력이 유효 JSON
12. outputs/front_test를 수정하지 않음
```

테스트는 임시 파일/CSV를 사용한다.  
실제 paper 원장 파일을 수정하지 않는다.

## 검증 명령

```text
set PYTHONPATH=.

python -m pytest tests/test_paper_status.py tests/test_paper_cli.py -q
python -m py_compile core/paper_status.py
python -m py_compile scripts/paper.py

python scripts/paper.py --help
python scripts/paper.py status
python scripts/paper.py status --date 20260520
```

## 성공 기준

```text
paper.py status 명령이 추가된다.
날짜 미지정 시 최신 운영 상태를 요약한다.
--date 지정 시 해당 날짜 진행 상태를 요약한다.
prepare/preview/commit/review 진행 여부를 읽기 전용으로 추정한다.
next recommended command를 출력한다.
거래 없는 날 execution log row 0건을 정상으로 해석한다.
writer 함수나 EOD commit을 실행하지 않는다.
outputs/front_test를 수정하지 않는다.
테스트가 통과한다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 변경 파일
3. 추가된 CLI
4. status 판정 기준
5. 확인하는 파일/CSV
6. workflow_status 종류
7. next_recommended_command 정책
8. --json 지원 여부
9. 제외한 항목
10. 테스트 결과
11. 실제 status 실행 결과
12. paper 원장 CSV 변경 여부
13. outputs/front_test 변경 여부
14. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER11-10은 paper.py status 구현이며, 데이터 수집, plan 생성, EOD commit, reports 재생성, review append는 포함하지 않는다.
```
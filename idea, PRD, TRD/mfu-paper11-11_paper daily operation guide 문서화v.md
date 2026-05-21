# MFU-PAPER11-11 작업 지시문: paper daily operation guide 문서화

## 목적

PAPER11-11의 목표는 현재 완성된 paper 운영 루프를 실제 운영자가 매일 따라 할 수 있도록 문서화하는 것이다.

이번 단계는 문서화 전용이다.  
코드 수정, DB write, paper 원장 수정, EOD commit 실행은 하지 않는다.

반드시 명시:

```text
이번 PAPER11-11은 paper daily operation guide 문서화이며, 코드 변경, 데이터 수집, plan 생성, EOD commit, reports 재생성은 포함하지 않는다.
```

## 배경

현재 paper 운영용 shortcut은 아래 5개다.

```text
paper.py prepare --date YYYYMMDD
paper.py preview --date YYYYMMDD
paper.py commit --date YYYYMMDD
paper.py review
paper.py status [--date YYYYMMDD]
```

개별 진단용 명령은 유지한다.

```text
prepare-data
data-freshness
preflight
plan
eod
reports
review-template
review-validate
review-append
```

운영자는 기본적으로 shortcut만 사용하고, 문제 발생 시 개별 명령으로 원인을 확인한다.

## 산출물

새 문서 작성:

```text
docs/operations/paper_daily_ops.md
```

필요 시 TRD 보조 문서 작성:

```text
docs/TRD/mfu_paper11_11_paper_daily_ops_guide.md
```

## 문서 구성

`docs/operations/paper_daily_ops.md`는 아래 목차로 작성한다.

### 1. 목적

아래 내용을 설명한다.

```text
이 문서는 paper trading 운영자가 매일 어떤 명령을 어떤 순서로 실행해야 하는지 정리한다.
자동매매 실행 문서가 아니라 paper test 운영 절차 문서다.
```

### 2. 기본 운영 루틴

아래 순서를 명확히 적는다.

```text
1. prepare
2. preview
3. commit
4. review
5. status
```

명령 예시:

```text
python scripts/paper.py prepare --date 20260520
python scripts/paper.py preview --date 20260520
python scripts/paper.py commit --date 20260520
python scripts/paper.py review
python scripts/paper.py status --date 20260520
```

### 3. 각 명령의 의미

각 shortcut의 역할을 설명한다.

```text
prepare
= prepare-data + data-freshness
= market_data.db 입력 준비 후 freshness 확인
= DB writer

preview
= data-freshness + plan + eod dry-run
= daily_action_plan 생성 및 EOD 반영 미리보기
= commit은 하지 않음

commit
= eod --commit
= paper current state/account snapshot/position snapshot 저장
= 같은 날짜 snapshot이 있으면 기본 차단
= --replace가 있을 때만 재실행 허용

review
= reports + review-template + review-validate
= review-append는 실행하지 않음

status
= 현재 운영 상태를 read-only로 요약
```

### 4. 날짜 정책

아래 정책을 명확히 쓴다.

```text
prepare / preview / commit은 같은 날짜를 사용한다.
--date는 paper 운영 기준일/as-of date다.
한국 시간의 오늘과 미국장 기준 거래일이 다를 수 있으므로 날짜를 명시한다.
review는 기본적으로 날짜 없이 최신 상태 기준으로 실행한다.
```

예시:

```text
미국장 2026-05-20 데이터를 처리하는 경우:
python scripts/paper.py prepare --date 20260520
python scripts/paper.py preview --date 20260520
python scripts/paper.py commit --date 20260520
```

### 5. warning 처리 기준

아래 정책을 적는다.

```text
PASS -> 계속 진행
PASS_WITH_WARNINGS -> 기본 중단
FAIL -> 중단
--allow-warnings가 있을 때만 warning 상태 통과
```

특히 아래 warning은 쉽게 무시하지 말라고 명시한다.

```text
daily_price latest date is older than target_date
SPY latest date is older than target_date
daily_indicators가 daily_price보다 오래됨
```

universe snapshot 없음은 optional warning으로 설명한다.

```text
universe_snapshot_YYYYMMDD.json 없음은 매일 갱신하지 않을 수 있으므로 상대적으로 낮은 위험
필요 시 prepare --universe 사용
```

### 6. preview에서 확인할 것

preview 후 확인 항목을 정리한다.

```text
data-freshness PASS 여부
plan_date와 data_date 일치 여부
daily_action_plan 저장 경로
EOD dry-run 결과
ready_for_paper_trade
rows_to_append
write_performed=False
account preview
```

주의:

```text
preview는 원장을 쓰지 않는다.
확정 매매가 없어도 commit은 그날 account/position snapshot 저장을 위해 필요할 수 있다.
```

### 7. commit에서 확인할 것

commit 후 확인 항목을 정리한다.

```text
preflight PASS
rows_appended
paper_current_state saved
paper_account_snapshot saved
paper_position_snapshot saved
front_test 변경 없음
```

같은 날짜 재실행 정책:

```text
기본 commit은 같은 날짜 snapshot이 있으면 차단된다.
의도적으로 재실행할 때만 --replace 사용.
--replace 사용 시 기존 파일 backup 후 같은 날짜 snapshot을 교체할 수 있다.
```

### 8. review에서 확인할 것

review 후 확인할 파일을 정리한다.

```text
outputs/paper_test/reports/paper_daily_review_summary.md
outputs/paper_test/reviews/paper_manual_review_log_template.md
outputs/paper_test/reviews/paper_manual_review_log_validation_report.md
```

명시:

```text
review는 review-append를 실행하지 않는다.
review-append는 사람이 template에 답변을 작성한 뒤 별도로 실행한다.
```

### 9. status 사용법

예시:

```text
python scripts/paper.py status
python scripts/paper.py status --date 20260520
python scripts/paper.py status --date 20260520 --verbose
python scripts/paper.py status --json
```

workflow status 설명:

```text
NO_PLAN
PLAN_READY
COMMITTED
REVIEW_READY
UNKNOWN_OR_INCOMPLETE
```

next recommended command 정책도 문서화한다.

### 10. 문제 상황별 대응

아래 케이스를 포함한다.

```text
prepare에서 freshness warning 발생
preview에서 rows_to_append=0
commit에서 same-date snapshot exists로 차단
review validation FAIL
status가 UNKNOWN_OR_INCOMPLETE
DB 최신 날짜가 target date보다 이전
```

각 케이스별 권장 대응을 짧게 적는다.

### 11. 금지/주의 명령

운영 표준에서는 아래를 직접 쓰지 않는다고 명시한다.

```text
python scripts/paper.py eod --date YYYYMMDD --commit
```

이유:

```text
저수준 명령이라 same-date commit guard가 적용되지 않을 수 있다.
운영 표준은 paper.py commit을 사용한다.
```

또한 아래는 일상 운영에 포함하지 않는다.

```text
setup_db.py
review-append 자동 실행
run-all/daily 자동 commit
```

## 검증

문서 작업이므로 테스트는 필수 아님.

단, 아래는 실행 가능하다.

```text
python scripts/paper.py --help
python scripts/paper.py status --date 20260520
```

writer 명령은 실행하지 않는다.

금지:

```text
prepare 실행 금지
preview 실행 금지
commit 실행 금지
review 실행 금지
review-append 실행 금지
DB write 금지
paper 원장 CSV 수정 금지
```

## 성공 기준

```text
docs/operations/paper_daily_ops.md가 생성된다.
운영용 shortcut 5개의 역할이 명확히 설명된다.
prepare/preview/commit/review/status 순서가 문서화된다.
warning 처리 기준이 문서화된다.
same-date commit guard와 --replace 정책이 문서화된다.
review-append가 자동 실행되지 않는 이유가 설명된다.
문제 상황별 대응이 포함된다.
코드와 원장 파일은 수정하지 않는다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 변경 파일
3. 문서 목차
4. 문서화한 운영 루틴
5. warning 처리 정책
6. commit 재실행 정책
7. review-append 정책
8. 문제 상황별 대응 포함 여부
9. 실행한 검증 명령
10. 코드 변경 여부
11. paper 원장 CSV 변경 여부
12. outputs/front_test 변경 여부
13. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER11-11은 paper daily operation guide 문서화이며, 코드 변경과 writer 명령 실행은 포함하지 않는다.
```
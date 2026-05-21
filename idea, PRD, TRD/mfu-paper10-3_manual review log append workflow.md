# MFU-PAPER10-3 작업 지시문: manual review log append workflow

## 기준

브랜치: gemini_cli_update  
기준 SHA: c6ed2bce27a8f08afc64c882d8c7abe05849c303

## 목적

PAPER10-3의 목표는 `paper_manual_review_log_template.csv`에서 사람이 의미 있게 처리한 review row만 골라, 누적 원장인 `paper_manual_review_log.csv`에 append하는 workflow를 구현하는 것이다.

이번 단계는 append 전용이다.  
기존 row update/overwrite는 구현하지 않는다.

반드시 명시:

```text
이번 PAPER10-3은 manual review log append workflow이며, 기존 row update/overwrite는 포함하지 않는다.
매수/매도/보유 제안은 포함하지 않는다.
```

## 입력

필수 입력:

```text
outputs/paper_test/reviews/paper_manual_review_log_template.csv
```

검증 입력:

```text
outputs/paper_test/reviews/paper_manual_review_log_validation_report.md
outputs/paper_test/reviews/paper_manual_review_log_validation_issues.csv
```

참고:
- validator 로직은 PAPER10-2의 `core/paper_manual_review_log_validator.py`를 재사용한다.
- append 전에 validator를 실행하거나 같은 검증 함수를 호출한다.

## 산출물

누적 로그:

```text
outputs/paper_test/reviews/paper_manual_review_log.csv
```

append report:

```text
outputs/paper_test/reviews/paper_manual_review_log_append_report.md
```

선택 산출물:

```text
outputs/paper_test/reviews/paper_manual_review_log_append_issues.csv
```

## 구현 파일

권장 추가 파일:

```text
core/paper_manual_review_log_append.py
scripts/append_paper_manual_review_log.py
tests/test_paper_manual_review_log_append.py
docs/TRD/mfu_paper10_3_manual_review_log_append.md
```

## 핵심 정책

### 1. append 전 validator 강제

append 전에 validator를 반드시 실행한다.

정책:

```text
error_count = 0 이면 append 가능
error_count > 0 이면 append 중단
warning_count > 0 이어도 append 가능
```

append 중단 시에도 append report를 생성하고 이유를 기록한다.

### 2. append 대상 row

pending row는 누적 log에 넣지 않는다.

append 대상:

```text
review_status in reviewed, deferred, not_applicable
```

append 제외:

```text
review_status = pending
```

이유:
pending row는 아직 사람이 처리하지 않은 질문이므로 누적 log를 오염시킬 수 있다.

### 3. reviewed row 규칙

```text
review_status = reviewed 인 row는 manual_answer가 있어야 한다.
```

이 검증은 validator에서 error로 잡아야 한다.  
append 단계에서는 validator error가 있으면 중단한다.

### 4. deferred / not_applicable row 규칙

```text
review_status = deferred
review_status = not_applicable
```

이 둘은 manual_answer가 없어도 append 가능하다.

다만 `deferred`인데 `reviewer_note`와 `review_tag`가 모두 비어 있으면 validator warning으로 남긴다.

### 5. duplicate key

중복 기준:

```text
review_date + symbol + question_id
```

정책:

```text
기존 log에 같은 key가 있으면 skip
이번 append batch 안에 같은 key가 중복되어도 skip
overwrite 금지
```

중복 skip은 error가 아니다.  
append report에 `rows_skipped_duplicate`로 기록한다.

### 6. 누적 log 생성 규칙

```text
paper_manual_review_log.csv가 없으면 새로 생성한다.
있으면 기존 row 뒤에 append한다.
```

단, 기존 row는 절대 수정하지 않는다.

### 7. 기존 manual_answer 보존

기존 log에 같은 key가 있으면 새 template row로 덮어쓰지 않는다.

금지:

```text
기존 manual_answer 수정
기존 review_status 수정
기존 reviewer_note 수정
기존 row 삭제
```

## append report 구성

`paper_manual_review_log_append_report.md`에 포함:

```text
1. 생성 일시
2. input template path
3. target log path
4. validation result
5. validation error/warning count
6. total template rows
7. rows_considered_for_append
8. rows_appended
9. rows_skipped_pending
10. rows_skipped_duplicate
11. rows_skipped_invalid
12. existing_log_row_count_before
13. final_log_row_count_after
14. appended symbols
15. skipped duplicate keys
16. limitations
```

Limitations에 반드시 포함:

```text
- This append workflow does not update or overwrite existing rows.
- Pending rows are intentionally not appended.
- This is a manual review log workflow, not a buy/sell/hold recommendation system.
- Append duplicate key is review_date + symbol + question_id.
```

## append issues CSV 컬럼

선택 산출물 생성 시 컬럼:

```text
severity
row_number
symbol
question_id
issue_code
message
```

사용 예:

```text
skipped_pending
skipped_duplicate
append_aborted_validation_error
```

## 절대 금지

```text
paper_execution_log.csv 수정 금지
paper_account_snapshot.csv 수정 금지
paper_position_snapshot.csv 수정 금지
기존 report CSV 수정 금지
paper_manual_review_log_template.csv 수정 금지
outputs/front_test 수정 금지
DB 수정 금지
--commit 실행 금지
기존 log row update/overwrite 금지
기존 log row delete 금지
manual_answer 자동 작성 금지
review_status 자동 변경 금지
weekly rollup 구현 금지
improvement backlog 구현 금지
actionable commentary 생성 금지
매수/매도/보유 추천 금지
대규모 리팩토링 금지
```

## 테스트

테스트 파일:

```text
tests/test_paper_manual_review_log_append.py
```

필수 테스트:

```text
1. log 파일이 없으면 새로 생성
2. log 파일이 있으면 append
3. pending row는 append 제외
4. reviewed row는 append
5. deferred row는 append
6. not_applicable row는 append
7. duplicate key는 skip
8. batch 내부 duplicate도 skip
9. 기존 manual_answer overwrite 금지
10. validator error가 있으면 append 중단
11. validator warning만 있으면 append 진행
12. append report 생성
13. append issues CSV 생성 또는 skip 기록
14. 원본 template CSV를 수정하지 않음
15. is_actionable=false 유지
```

## 검증 명령

```bat
set PYTHONPATH=.

python -m pytest tests/test_paper_manual_review_log_append.py -q
python -m py_compile core/paper_manual_review_log_append.py
python -m py_compile scripts/append_paper_manual_review_log.py
python scripts/append_paper_manual_review_log.py
```

## 성공 기준

```text
paper_manual_review_log.csv가 생성 또는 append된다
pending row는 append되지 않는다
reviewed/deferred/not_applicable row만 append된다
중복 key는 skip된다
기존 row는 절대 수정되지 않는다
append 전 validator가 강제된다
append report가 생성된다
원본 template과 outputs/front_test는 수정되지 않는다
테스트가 통과한다
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 변경 파일
3. 산출물 경로
4. validation result
5. total template rows
6. rows considered/appended/skipped
7. duplicate skip 결과
8. existing/final log row count
9. append 정책 요약
10. 제외한 항목
11. 테스트 결과
12. 원본 CSV 변경 여부
13. outputs/front_test 변경 여부
14. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER10-3은 manual review log append workflow이며, 기존 row update/overwrite는 포함하지 않는다.
```
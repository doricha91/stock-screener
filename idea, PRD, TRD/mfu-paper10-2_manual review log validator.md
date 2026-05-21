# MFU-PAPER10-2 작업 지시문: manual review log validator

## 기준

브랜치: gemini_cli_update  
기준 SHA: c6ed2bce27a8f08afc64c882d8c7abe05849c303

## 목적

PAPER10-2의 목표는 PAPER10-1에서 생성한 `paper_manual_review_log_template.csv` 또는 향후 작성될 manual review log CSV의 형식을 검증하는 validator를 만드는 것이다.

이번 단계는 **검증 전용**이다.  
append workflow, 누적 log 생성, update/overwrite 기능은 구현하지 않는다.

반드시 명시:

```text
이번 PAPER10-2는 manual review log validator이며, append workflow는 포함하지 않는다.
매수/매도/보유 제안은 포함하지 않는다.
```

## 입력

검증 대상:

```text
outputs/paper_test/reviews/paper_manual_review_log_template.csv
```

향후 호환 대상:

```text
outputs/paper_test/reviews/paper_manual_review_log.csv
```

단, 이번 단계에서 `paper_manual_review_log.csv`를 생성하지 않는다.

## 산출물

생성 파일:

```text
outputs/paper_test/reviews/paper_manual_review_log_validation_report.md
outputs/paper_test/reviews/paper_manual_review_log_validation_issues.csv
```

## 구현 파일

권장 추가 파일:

```text
core/paper_manual_review_log_validator.py
scripts/validate_paper_manual_review_log.py
tests/test_paper_manual_review_log_validator.py
docs/TRD/mfu_paper10_2_manual_review_log_validator.md
```

## 핵심 원칙

### 1. validation only

허용:
- CSV 로딩
- 필수 컬럼 검증
- 허용값 검증
- 중복 key 검증
- manual_answer / review_status 관계 검증
- validation report 생성

금지:
- append workflow
- 누적 log 생성
- 기존 row 수정
- 기존 row 삭제
- manual_answer 자동 작성
- review_status 자동 변경
- actionable commentary
- 매수/매도/보유 추천

### 2. 기존 파일 수정 금지

검증 대상 CSV를 절대 수정하지 않는다.  
문제는 report와 issues CSV에만 기록한다.

## 검증 정책

### 1. 필수 컬럼

아래 컬럼이 없으면 error 처리한다.

```text
review_date
symbol
review_bucket
review_priority
sample_size_flag
symbol_status
question_id
question_text
question_category
is_actionable
manual_answer
review_status
follow_up_needed
review_tag
reviewer_note
source_worksheet_path
created_at
```

### 2. review_status 허용값

허용값:

```text
pending
reviewed
deferred
not_applicable
```

검증 규칙:

```text
review_status가 허용값 외이면 error
review_status = reviewed 인데 manual_answer가 비어 있으면 error
review_status = pending 인데 manual_answer가 있어도 warning
review_status = deferred 인데 reviewer_note와 review_tag가 모두 비어 있으면 warning
```

### 3. follow_up_needed 허용값

허용값:

```text
true
false
TRUE
FALSE
1
0
```

검증 규칙:

```text
허용값 외이면 error
follow_up_needed = true 인데 reviewer_note와 review_tag가 모두 비어 있으면 warning
```

### 4. review_tag 허용값

허용 태그:

```text
entry_rule
exit_rule
position_sizing
market_regime
risk_management
data_quality
execution_quality
signal_quality
psychology
other
""
```

검증 규칙:

```text
허용값 외이면 warning
빈값은 허용
이번 단계에서는 다중 태그를 지원하지 않는다
```

### 5. is_actionable

검증 규칙:

```text
모든 row의 is_actionable은 false여야 한다
true 또는 기타 값이면 error
```

### 6. 중복 row 기준

중복 key:

```text
review_date + symbol + question_id
```

검증 규칙:

```text
같은 key가 2개 이상이면 error
```

주의:
PAPER10-2에서는 중복을 삭제하거나 병합하지 않는다.  
append 시 중복 skip 정책은 PAPER10-3에서 구현한다.

### 7. 빈값 검증

error:
```text
symbol blank
question_id blank
question_text blank
review_status blank
is_actionable blank
```

warning:
```text
review_date blank
source_worksheet_path blank
created_at blank
```

## validation report 구성

`paper_manual_review_log_validation_report.md`에 포함:

```text
1. 생성 일시
2. 입력 파일 경로
3. row count
4. error count
5. warning count
6. duplicate key count
7. review_status 분포
8. follow_up_needed 분포
9. review_tag 분포
10. validation result: PASS / FAIL
11. limitations
```

PASS 기준:

```text
error_count = 0
```

warning이 있어도 PASS 가능하다.  
단, warning count는 명확히 표시한다.

## issues CSV 컬럼

`paper_manual_review_log_validation_issues.csv` 컬럼:

```text
severity
row_number
symbol
question_id
field
issue_code
message
```

severity:

```text
error
warning
```

## 절대 금지

```text
paper_execution_log.csv 수정 금지
paper_account_snapshot.csv 수정 금지
paper_position_snapshot.csv 수정 금지
기존 report CSV 수정 금지
paper_manual_review_log_template.csv 수정 금지
paper_manual_review_log.csv 생성/수정 금지
outputs/front_test 수정 금지
DB 수정 금지
--commit 실행 금지
append workflow 구현 금지
row update/overwrite 구현 금지
manual_answer 자동 생성 금지
매수/매도/보유 추천 금지
weekly rollup 구현 금지
improvement backlog 구현 금지
대규모 리팩토링 금지
```

## 테스트

테스트 파일:

```text
tests/test_paper_manual_review_log_validator.py
```

필수 테스트:

```text
1. 정상 template은 PASS
2. 필수 컬럼 누락 감지
3. 잘못된 review_status 감지
4. reviewed인데 manual_answer blank면 error
5. deferred인데 note/tag blank면 warning
6. 잘못된 follow_up_needed 감지
7. follow_up_needed=true인데 note/tag blank면 warning
8. 잘못된 review_tag warning
9. is_actionable=true error
10. duplicate key error
11. symbol/question_id/question_text blank error
12. issues CSV 생성
13. validation report 생성
14. 원본 CSV를 수정하지 않음
```

## 검증 명령

```bat
set PYTHONPATH=.

python -m pytest tests/test_paper_manual_review_log_validator.py -q
python -m py_compile core/paper_manual_review_log_validator.py
python -m py_compile scripts/validate_paper_manual_review_log.py
python scripts/validate_paper_manual_review_log.py
```

## 성공 기준

```text
manual review log validator가 생성된다
validation report markdown이 생성된다
validation issues CSV가 생성된다
정상 template은 PASS 처리된다
error/warning이 구분된다
중복 key 검증이 된다
is_actionable=false 정책이 검증된다
append workflow는 구현하지 않는다
원본 CSV와 outputs/front_test는 수정하지 않는다
테스트가 통과한다
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 변경 파일
3. 산출물 경로
4. validation 대상 파일
5. validation result
6. error/warning count
7. 검증 정책 요약
8. 제외한 항목
9. 테스트 결과
10. 원본 CSV 변경 여부
11. outputs/front_test 변경 여부
12. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER10-2는 manual review log validator이며, append workflow는 PAPER10-3으로 분리한다.
```
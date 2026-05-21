# MFU-PAPER10-1 작업 지시문: manual review log template 생성

## 기준

브랜치: gemini_cli_update  
기준 SHA: c6ed2bce27a8f08afc64c882d8c7abe05849c303

## 목적

PAPER10-1의 목표는 PAPER9-8의 review worksheet를 기반으로, 사람이 복기 결과를 기록할 수 있는 **manual review log template**을 생성하는 것이다.

이번 단계는 복기 답변 저장 양식만 만든다.  
아직 validation, append workflow, weekly rollup, improvement backlog는 구현하지 않는다.

반드시 명시:

```text
This is a manual review log template.
It does not recommend buy/sell/hold actions.
is_actionable = false
```

## 배경

PAPER9에서는 아래 체계가 완성됐다.

```text
daily review summary
symbol side-by-side performance
review bucket classification
review worksheet
report index
```

하지만 아직 사람이 worksheet 질문에 답변한 내용을 누적 저장할 공식 log template은 없다.

PAPER10은 복기 기록을 운영 데이터로 누적하는 단계이며, PAPER10-1은 그 첫 단계다.

## 입력

필수 입력:

```text
outputs/paper_test/reports/paper_symbol_review_worksheet.csv
outputs/paper_test/reports/paper_symbol_review_buckets.csv
```

참고 가능:

```text
outputs/paper_test/reports/paper_daily_review_summary.md
outputs/paper_test/reports/paper_symbol_review_worksheet.md
```

## 산출물

생성 파일:

```text
outputs/paper_test/reviews/paper_manual_review_log_template.csv
outputs/paper_test/reviews/paper_manual_review_log_template.md
```

주의:
- `outputs/paper_test/reports/`가 아니라 `outputs/paper_test/reviews/` 아래에 생성한다.
- reports는 시스템 산출물, reviews는 사람이 작성/보관할 복기 기록 영역으로 분리한다.

## 구현 파일

권장 추가 파일:

```text
core/paper_manual_review_log_template.py
scripts/generate_paper_manual_review_log_template.py
tests/test_paper_manual_review_log_template.py
docs/TRD/mfu_paper10_1_manual_review_log_template.md
```

## 핵심 원칙

### 1. review-only 유지

이번 산출물은 수동 복기 기록용이다.

금지:
```text
매수 추천
매도 추천
보유 추천
비중 조절 제안
action plan 생성
전략 수정 제안
```

### 2. 손익 재계산 금지

입력 CSV의 값을 그대로 참조한다.

금지:
```text
paper_execution_log.csv replay
paper_position_snapshot.csv 재집계
realized/unrealized/total PnL 재계산
bucket 재분류
worksheet 질문 재생성
```

### 3. 사람이 채울 칸을 명확히 만든다

템플릿은 자동 생성 필드와 수동 입력 필드를 분리한다.

자동 생성 필드:
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
```

수동 입력 필드:
```text
manual_answer
review_status
follow_up_needed
review_tag
reviewer_note
```

## CSV 컬럼

`paper_manual_review_log_template.csv` 최소 컬럼:

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

기본값:

```text
review_date = 생성일 또는 빈값 중 하나로 통일
manual_answer = ""
review_status = pending
follow_up_needed = false
review_tag = ""
reviewer_note = ""
is_actionable = false
```

`review_status` 후보는 문서에만 명시하고, validation은 PAPER10-2에서 구현한다.

후보:
```text
pending
reviewed
deferred
not_applicable
```

## Markdown 구성

`paper_manual_review_log_template.md`에 포함:

```text
1. Header
2. Purpose
3. How to Use
4. Review Log Fields
5. Pending Review Items
6. Limitations
```

### How to Use에 포함할 내용

```text
1. CSV에서 manual_answer를 작성한다.
2. review_status를 pending/reviewed/deferred/not_applicable 중 하나로 수동 입력한다.
3. 후속 점검이 필요하면 follow_up_needed를 true로 표시한다.
4. review_tag에는 entry_rule, exit_rule, position_sizing, market_regime, data_quality 같은 태그를 수동 입력할 수 있다.
5. 이 템플릿은 매매 지시가 아니라 복기 기록용이다.
```

## 절대 금지

```text
paper_execution_log.csv 수정 금지
paper_account_snapshot.csv 수정 금지
paper_position_snapshot.csv 수정 금지
기존 report CSV 수정 금지
outputs/front_test 수정 금지
DB 수정 금지
--commit 실행 금지
손익 재계산 금지
bucket 재분류 금지
worksheet 질문 재생성 금지
actionable commentary 생성 금지
매수/매도/보유 추천 금지
review log validation 구현 금지
weekly rollup 구현 금지
improvement backlog 생성 금지
대규모 리팩토링 금지
```

## 테스트

테스트 파일:

```text
tests/test_paper_manual_review_log_template.py
```

필수 테스트:

```text
1. review log template CSV 생성
2. review log template markdown 생성
3. worksheet question row가 template row로 변환됨
4. manual_answer가 빈값으로 생성됨
5. review_status 기본값이 pending
6. follow_up_needed 기본값이 false
7. is_actionable이 항상 false
8. source_worksheet_path 포함
9. reports가 아닌 reviews 경로에 생성
10. non-actionable 문구 포함
11. 필수 입력 누락 시 명확한 error
12. 원본 report CSV를 수정하지 않음
```

## 검증 명령

```bat
set PYTHONPATH=.

python -m pytest tests/test_paper_manual_review_log_template.py -q
python -m py_compile core/paper_manual_review_log_template.py
python -m py_compile scripts/generate_paper_manual_review_log_template.py
python scripts/generate_paper_manual_review_log_template.py
```

## 성공 기준

```text
paper_manual_review_log_template.csv 생성
paper_manual_review_log_template.md 생성
outputs/paper_test/reviews/ 경로 사용
수동 입력 필드가 포함됨
is_actionable = false 유지
매수/매도/보유 제안 없음
기존 CSV와 outputs/front_test 수정 없음
테스트 통과
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 변경 파일
3. 산출물 경로
4. 생성된 review template row 수
5. 포함된 자동 생성 필드
6. 포함된 수동 입력 필드
7. non-actionable 유지 여부
8. 제외한 항목
9. 테스트 결과
10. 원본 CSV 변경 여부
11. outputs/front_test 변경 여부
12. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER10-1은 manual review log template 생성이며, 매수/매도/보유 제안은 포함하지 않는다.
```
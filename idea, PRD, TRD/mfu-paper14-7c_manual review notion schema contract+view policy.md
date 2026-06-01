# MFU-PAPER14-7C 작업 지시문: Manual Review Notion schema contract + view policy

## 목적

기존 Python Review 원장 구조를 기준으로, Notion Manual Review 입력 DB의 schema contract와 view policy를 설계한다.

이번 작업은 조사/설계/문서화 작업이다.  
Notion DB 생성, Python importer 구현, review commit 구현, Notion actual write는 수행하지 않는다.

반드시 명시:

```text
이번 PAPER14-7C는 Manual Review Notion schema contract와 view policy를 설계하는 작업이며, Notion Review DB 생성, Review import/commit 구현, Python 코드 수정, Notion actual export/write는 수행하지 않았다.
```

---

## 기준 커밋

기준 커밋:

```text
ffd2350f5933376f4bc2b9fec26901d76f0b797d
```

최근 로그에 아래 커밋이 있어야 한다.

```text
18e2fb5 PAPER14-7B: assess manual review flow and Notion placement
```

작업 전 확인:

```cmd
cd /d D:\python\StockScreener
git rev-parse HEAD
git log --oneline -15
git status --short
```

기준 SHA 이후 상태가 아니면 중단하고 보고한다.

---

## 배경

PAPER14-7B 조사 결과, Review는 이미 Python 쪽에 아래 흐름이 존재한다.

```text
template 생성
→ validation
→ append
→ final log
```

관련 CLI:

```text
paper.py review
paper.py review-template
paper.py review-validate
paper.py review-append
```

기존 source of truth 후보:

```text
outputs/paper_test/reviews/paper_manual_review_log.csv
```

원칙:

```text
Notion = 입력 UI / staging layer
Python = 검증 / 정규화 / commit 주체
CSV / Markdown = Review source of truth
```

---

## 조사 대상

반드시 확인한다.

```text
core/paper_manual_review_log_template.py
core/paper_manual_review_log_validator.py
core/paper_manual_review_log_append.py
core/paper_daily_review_summary.py
scripts/paper.py
scripts/generate_paper_manual_review_log_template.py
scripts/validate_paper_manual_review_log.py
scripts/append_paper_manual_review_log.py
docs/operations/paper_daily_ops.md
outputs/paper_test/reviews/
outputs/paper_test/reports/
tests/
```

특히 아래 파일의 실제 column/schema를 확인한다.

```text
outputs/paper_test/reviews/paper_manual_review_log.csv
outputs/paper_test/reviews/paper_manual_review_log_template.csv
outputs/paper_test/reviews/paper_manual_review_log_template.md
outputs/paper_test/reviews/paper_manual_review_log_validation_report.md
outputs/paper_test/reviews/paper_manual_review_log_append_report.md
```

파일이 없으면 없다고 보고하고, 생성 CLI가 있는지 확인한다.

---

## 확인할 질문

문서에서 아래 질문에 답한다.

### 1. 기존 Review CSV schema

확인할 것:

```text
컬럼 목록
필수 컬럼
사용자가 입력하는 컬럼
Python이 생성/관리하는 컬럼
validation에 쓰이는 컬럼
append 후 final log에 남는 컬럼
```

특히 아래 필드 존재 여부를 확인한다.

```text
review_date
symbol
question_id
question
manual_answer
review_status
follow_up_needed
review_tag
reviewer_note
source_path
created_at
```

실제 이름이 다르면 실제 컬럼명을 기준으로 문서화한다.

### 2. Notion row 단위 후보 비교

아래 후보를 비교한다.

```text
A. 질문 1개 = Notion row 1개
B. 날짜 1개 = Notion row 1개, 질문/답변은 page body
C. template row와 answer row를 같은 DB에서 Status로 분리
D. template DB와 answer DB를 분리
```

판단 기준:

```text
기존 CSV와 매핑 용이성
모바일 입력 편의성
후속 importer 구현 난이도
검증 가능성
중복/누락 방지
Notion 화면 복잡도
```

### 3. 권장 Notion DB schema

후보 DB 이름:

```text
Manual Reviews
```

기본 속성 후보를 제안한다.

```text
Name
External Key
Review Date
Symbol
Question ID
Question
Manual Answer
Review Status
Follow-up Needed
Review Tag
Reviewer Note
Source Template Key
Validation Status
Validation Message
Import Status
Imported At
Synced At
```

단, 실제 기존 CSV 컬럼과 맞지 않으면 기존 CSV에 맞춰 조정한다.

### 4. View policy

사용자 요구:

```text
스마트폰에서 입력 가능해야 한다.
메인 화면에 너무 많은 정보가 노출되면 안 된다.
```

최소 view 후보를 제안한다.

```text
Input
Validation
Technical
Committed
```

Input view에는 사용자가 실제로 작성할 필드만 표시한다.

예:

```text
Review Date
Symbol
Question
Manual Answer
Review Status
Follow-up Needed
Review Tag
Reviewer Note
```

숨김 후보:

```text
External Key
Question ID
Source Template Key
Validation Status
Validation Message
Import Status
Imported At
Synced At
```

### 5. 후속 흐름 설계

후속 MFU에서 구현할 흐름을 제안한다.

```text
Review template 생성
→ Notion Manual Reviews에 template/export 또는 입력 row 준비
→ 사용자가 Notion에서 답변 작성
→ Python read-only import
→ validation / preview
→ 사용자 승인
→ paper_manual_review_log.csv append
→ append report 생성
→ Notion Review status back-write
```

단, 이번 7C에서는 구현하지 않는다.

---

## 최종 권고안 형식

아래 중 하나로 결론을 낸다.

```text
권고 A: 질문 1개 = Notion row 1개로 간다.
권고 B: 날짜 1개 = Notion row 1개로 간다.
권고 C: 기존 Review CSV 구조를 먼저 정비한 뒤 Notion schema를 확정한다.
권고 D: Review Notion 입력은 보류하고 기존 CSV/MD Review만 유지한다.
```

각 권고에는 반드시 이유와 반론을 포함한다.

---

## 결과 문서

추가 문서:

```text
docs/TRD/mfu_paper14_7c_manual_review_notion_schema_contract.md
```

포함 내용:

```text
1. 목적
2. 기존 Review CSV/MD 구조 조사 결과
3. 기존 Review CLI 흐름
4. Notion row 단위 후보 비교
5. 권장 Manual Reviews DB schema
6. 필수 입력 필드 / 선택 필드 / 시스템 관리 필드 구분
7. 권장 view policy
8. 스마트폰 입력 편의성 평가
9. 후속 importer/commit 흐름
10. 최종 권고안
11. 반론과 검증
12. 다음 MFU 제안
```

---

## 금지 사항

```text
Python 코드 수정 금지
config 수정 금지
Notion DB 생성 금지
Notion actual write/export 금지
Review import/commit 구현 금지
Manual Execution import/commit/status sync 재실행 금지
paper ledger CSV 수정 금지
review CSV/MD 수정 금지
output 파일 수정/삭제 금지
DB/PNG 파일 수정/삭제 금지
git add . 금지
git add -A 금지
```

---

## 검증 명령

문서 작업이므로 테스트는 필수 아님.

상태와 검색만 확인한다.

```cmd
cd /d D:\python\StockScreener
git status --short
git diff --name-only

findstr /S /N /I "paper_manual_review manual_review review_status manual_answer follow_up_needed review_tag reviewer_note" *.py *.md *.csv
```

필요 시 review 관련 테스트만 확인한다.

```cmd
set PYTHONPATH=.
python -m pytest tests -q -k "manual_review or review_log"
```

테스트 실패 시 수정하지 말고 보고한다.

---

## 커밋 정책

문서만 커밋한다.

```cmd
git add docs\TRD\mfu_paper14_7c_manual_review_notion_schema_contract.md
git diff --cached --name-only
git commit -m "PAPER14-7C: design Manual Review Notion schema and views"
```

staged 파일에 위 문서 외 파일이 있으면 커밋하지 말고 보고한다.

---

## 성공 기준

```text
기존 Review CSV/MD 구조가 확인된다.
기존 Review CLI 흐름이 정리된다.
Notion row 단위 후보가 비교된다.
Manual Reviews DB schema contract 초안이 정리된다.
Input / Validation / Technical / Committed view policy가 정리된다.
스마트폰 입력 편의성이 평가된다.
최종 권고안과 후속 MFU가 제안된다.
코드와 config는 수정하지 않는다.
문서만 커밋된다.
```

---

## 결과 보고 형식

5천자 이내.

```text
1. Summary
2. 기준 커밋 확인 결과
3. 변경 파일
4. 조사한 파일
5. 기존 Review CSV/MD schema
6. 기존 Review CLI 흐름
7. Notion row 단위 후보 비교
8. 권장 Manual Reviews DB schema
9. 필수 입력/선택/관리 필드 구분
10. view policy
11. 스마트폰 입력 편의성 평가
12. 최종 권고안
13. 반론과 검증
14. 코드 수정 여부
15. output/CSV 수정 여부
16. 테스트 실행 여부와 결과
17. 커밋 hash와 message
18. 다음 MFU 제안
```

반드시 명시:

```text
이번 PAPER14-7C는 Manual Review Notion schema contract와 view policy를 설계하는 작업이며, Notion Review DB 생성, Review import/commit 구현, Python 코드 수정, Notion actual export/write는 수행하지 않았다.
```
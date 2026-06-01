# MFU-PAPER14-7D 작업 지시문: Manual Review read-only importer preview

## 목적

Notion `Manual Reviews` DB에 질문 단위 row로 입력된 사후복기 답변을 Python에서 read-only로 가져와 validation preview를 생성한다.

이번 작업은 preview 단계다.  
`paper_manual_review_log.csv` append, Notion status back-write, Review commit은 수행하지 않는다.

반드시 명시:

```text
이번 PAPER14-7D는 Manual Review read-only importer preview 작업이며, Review append commit, Notion status back-write, Python review 원장 수정, Notion actual write는 수행하지 않았다.
```

---

## 기준 커밋

기준 커밋:

```text
ffd2350f5933376f4bc2b9fec26901d76f0b797d
```

최근 로그에 아래 커밋이 있어야 한다.

```text
4b4ffa2 PAPER14-7C: design Manual Review Notion schema and views
```

작업 전 확인:

```cmd
cd /d D:\python\StockScreener
git rev-parse HEAD
git log --oneline -15
git status --short
```

---

## 배경

PAPER14-7C에서 아래 정책을 확정했다.

```text
질문 1개 = Notion row 1개
사용자 입력 필드는 최소화한다.
Python CSV/MD = Review source of truth
Notion = 입력 UI / staging layer
```

기존 Review 원장:

```text
outputs/paper_test/reviews/paper_manual_review_log.csv
```

기존 template/source 후보:

```text
outputs/paper_test/reviews/paper_manual_review_log_template.csv
outputs/paper_test/reviews/paper_manual_review_log_template.md
```

사용자 입력 중심 필드:

```text
Manual Answer
Review Status
Follow-up Needed
Review Tag
Reviewer Note
```

---

## Notion 설정

새 data source key:

```text
manual_reviews
```

환경변수 override:

```env
NOTION_MANUAL_REVIEWS_DATA_SOURCE_ID=...
```

config fallback:

```json
{
  "data_sources": {
    "manual_reviews": ""
  }
}
```

---

## 구현 파일 후보

```text
core/notion_manual_review_importer.py
core/notion_schema_validator.py
scripts/import_notion_reviews.py
config/notion_property_mapping.example.json
config/notion_settings.example.json
tests/test_notion_manual_review_importer.py
tests/test_notion_schema_validator.py
docs/TRD/mfu_paper14_7d_manual_review_import_preview.md
```

필요 시 참조:

```text
core/paper_manual_review_log_validator.py
core/paper_manual_review_log_append.py
core/paper_manual_review_log_template.py
scripts/paper.py
```

---

## Notion property mapping

`config/notion_property_mapping.example.json`에 추가한다.

```json
{
  "manual_reviews": {
    "name": "Name",
    "external_key": "External Key",
    "review_date": "Review Date",
    "symbol": "Symbol",
    "question_id": "Question ID",
    "question": "Question",
    "manual_answer": "Manual Answer",
    "review_status": "Review Status",
    "follow_up_needed": "Follow-up Needed",
    "review_tag": "Review Tag",
    "reviewer_note": "Reviewer Note",
    "source_template_key": "Source Template Key",
    "validation_status": "Validation Status",
    "validation_message": "Validation Message",
    "import_status": "Import Status",
    "imported_at": "Imported At",
    "synced_at": "Synced At"
  }
}
```

권장 타입:

```text
Name = Title
External Key = Rich text
Review Date = Date
Symbol = Rich text
Question ID = Rich text
Question = Rich text
Manual Answer = Rich text
Review Status = Select
Follow-up Needed = Select 또는 Checkbox
Review Tag = Select 또는 Multi-select
Reviewer Note = Rich text
Source Template Key = Rich text
Validation Status = Select
Validation Message = Rich text
Import Status = Select
Imported At = Rich text
Synced At = Rich text
```

---

## Import 대상 정책

기본 import 대상:

```text
Review Date = --date
Import Status != COMMITTED
```

가능하면 사용자가 작성 완료 표시를 할 수 있도록 아래 중 하나를 지원한다.

```text
Review Status가 비어 있지 않음
또는
Import Status = READY
```

우선 권장:

```text
Import Status = READY인 row만 candidate
```

단, 실제 7C 문서와 기존 schema를 확인해 더 적절한 조건이 있으면 보고한다.

---

## Normalization 정책

Notion row를 internal review candidate로 변환한다.

매핑:

```text
Review Date -> review_date
Symbol -> symbol
Question ID -> question_id
Question -> question_text
Manual Answer -> manual_answer
Review Status -> review_status
Follow-up Needed -> follow_up_needed
Review Tag -> review_tag
Reviewer Note -> reviewer_note
Source Template Key -> source_template_key
External Key -> notion_external_key
```

기존 CSV 컬럼과 이름이 다르면 기존 CSV schema에 맞춰 내부 candidate를 구성한다.

---

## Validation 규칙

FAIL 후보:

```text
Review Date 없음
Symbol 없음
Question ID 없음
Question 없음
Manual Answer 없음
Review Status 없음
동일 batch 내 review_date + symbol + question_id 중복
이미 paper_manual_review_log.csv에 같은 review_date + symbol + question_id 존재
```

WARNING 후보:

```text
Follow-up Needed 없음
Review Tag 없음
Reviewer Note 없음
Source Template Key 없음
Question이 template 원문과 불일치
template에 없는 question_id
```

기존 `paper_manual_review_log_validator.py`의 규칙을 최대한 재사용하거나, 재사용이 어렵다면 preview용 validation으로 분리하고 보고한다.

---

## Preview report

출력 후보:

```text
outputs/paper_test/reports/manual_review_import_preview_YYYYMMDD.json
outputs/paper_test/reports/manual_review_import_preview_YYYYMMDD.md
```

포함 내용:

```text
review_date
candidate_count
pass_count
warning_count
fail_count
append_allowed
normalized candidates
validation issues
duplicate candidates
source_data_source_id
```

정책:

```text
FAIL이 하나라도 있으면 append_allowed=false
WARNING만 있으면 append_allowed=true_with_warnings
모두 PASS면 append_allowed=true
```

---

## CLI

새 스크립트:

```cmd
python scripts\import_notion_reviews.py --date 2026-05-25 --preview --json
python scripts\import_notion_reviews.py --date 2026-05-25 --preview
```

이번 단계에서 `--commit`은 구현하지 않는다.

```text
--commit이 들어오면 “not implemented in PAPER14-7D”로 실패시킨다.
```

---

## Schema validation

`validate_notion_schema.py`에 추가:

```cmd
python scripts\dev\validate_notion_schema.py --manual-reviews
```

data source id가 없으면 WARNING skip으로 처리한다.

---

## 금지 사항

```text
paper_manual_review_log.csv 수정 금지
review CSV/MD append 금지
Notion status back-write 금지
Notion actual write 금지
Manual Execution import/commit/status sync 재실행 금지
paper ledger CSV 수정 금지
output 파일 삭제 금지
DB/PNG 파일 수정/삭제 금지
git add . 금지
git add -A 금지
```

preview report 생성은 허용한다. 단, output/report 파일은 commit하지 않는다.

---

## 테스트 요구사항

추가/수정 테스트:

```text
tests/test_notion_manual_review_importer.py
tests/test_notion_schema_validator.py
```

검증할 것:

```text
1. Notion row를 question-level candidate로 normalize한다.
2. 사용자 입력 필드 중심으로 validation한다.
3. missing Manual Answer는 FAIL 처리한다.
4. missing optional fields는 WARNING 처리한다.
5. batch duplicate를 잡는다.
6. existing paper_manual_review_log.csv duplicate를 잡는다.
7. preview JSON/Markdown payload가 생성된다.
8. --commit은 실패한다.
9. paper_manual_review_log.csv는 수정하지 않는다.
10. Notion write는 호출하지 않는다.
```

---

## 검증 명령

Windows CMD 기준:

```cmd
cd /d D:\python\StockScreener
set PYTHONPATH=.

python -m py_compile core\notion_manual_review_importer.py
python -m py_compile scripts\import_notion_reviews.py
python -m py_compile core\notion_schema_validator.py

python -m pytest tests\test_notion_manual_review_importer.py tests\test_notion_schema_validator.py -q
```

data source id가 설정되어 있으면:

```cmd
python scripts\dev\validate_notion_schema.py --manual-reviews
python scripts\import_notion_reviews.py --date 2026-05-25 --preview --json
```

---

## 문서화

추가 문서:

```text
docs/TRD/mfu_paper14_7d_manual_review_import_preview.md
```

포함 내용:

```text
목적
question-level row 정책
minimal input field 정책
source of truth 원칙
Notion mapping
validation 규칙
preview report 구조
제외 범위
후속 7E append commit 계획
```

---

## 커밋 정책

코드와 문서만 커밋한다.

```cmd
git add core\notion_manual_review_importer.py
git add scripts\import_notion_reviews.py
git add core\notion_schema_validator.py
git add config\notion_property_mapping.example.json
git add config\notion_settings.example.json
git add tests\test_notion_manual_review_importer.py
git add tests\test_notion_schema_validator.py
git add docs\TRD\mfu_paper14_7d_manual_review_import_preview.md
git diff --cached --name-only
git commit -m "PAPER14-7D: add Manual Review import preview"
```

output/report/CSV 파일은 commit하지 않는다.

---

## 성공 기준

```text
Manual Reviews schema validation target이 추가된다.
NOTION_MANUAL_REVIEWS_DATA_SOURCE_ID를 사용할 수 있다.
Notion Manual Reviews row를 read-only로 import할 수 있다.
질문 단위 row가 normalized review candidate로 변환된다.
사용자 입력 필드 중심 validation preview가 생성된다.
append_allowed가 PASS/WARNING/FAIL에 따라 계산된다.
paper_manual_review_log.csv는 수정하지 않는다.
Notion write는 수행하지 않는다.
테스트가 통과한다.
```

---

## 결과 보고 형식

5천자 이내.

```text
1. Summary
2. 기준 커밋 확인 결과
3. 변경 파일
4. 추가된 env/config key
5. 추가된 CLI
6. schema validation 추가 내용
7. Notion read-only import 동작
8. normalization 정책
9. validation 규칙
10. preview report 생성 결과
11. 테스트 결과
12. Notion write 여부
13. review CSV/MD 수정 여부
14. 커밋 hash와 message
15. stage하지 않은 output 파일
16. 남은 리스크
17. 다음 MFU 제안
```

반드시 명시:

```text
이번 PAPER14-7D는 Manual Review read-only importer preview 작업이며, Review append commit, Notion status back-write, Python review 원장 수정, Notion actual write는 수행하지 않았다.
```
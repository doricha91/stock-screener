# MFU-PAPER14-7C: Manual Review Notion schema contract + view policy

## 1. 목적

이번 PAPER14-7C는 Manual Review Notion schema contract와 view policy를 설계하는 작업이며, Notion Review DB 생성, Review import/commit 구현, Python 코드 수정, Notion actual export/write는 수행하지 않았다.

본 문서는 기존 Python Review 원장 구조를 기준으로, Notion을 Review 입력 UI 또는 staging layer로 사용할 때 필요한 DB schema와 view 정책을 정리한다.

기본 원칙은 아래와 같다.

- Notion = 입력 UI / staging layer
- Python = 검증 / 정규화 / commit 주체
- CSV / Markdown = Review source of truth


## 2. 기존 Review CSV/MD 구조 조사 결과

### 2.1 실제 Review 원장 후보

조사 결과, 기존 Review source of truth 후보는 아래 파일이다.

- `outputs/paper_test/reviews/paper_manual_review_log.csv`

이 파일은 append 이후 최종적으로 누적되는 review log이며, Notion 연동을 하더라도 최종 원장은 이 CSV를 유지하는 편이 자연스럽다.

### 2.2 template / report / 파생 파일

Review 흐름에서 사용되는 주요 파일은 아래와 같다.

- `outputs/paper_test/reviews/paper_manual_review_log_template.csv`
- `outputs/paper_test/reviews/paper_manual_review_log_template.md`
- `outputs/paper_test/reviews/paper_manual_review_log_validation_report.md`
- `outputs/paper_test/reviews/paper_manual_review_log_append_report.md`
- `outputs/paper_test/reports/paper_daily_review_summary.md`
- `outputs/paper_test/reviews/paper_symbol_review_worksheet.csv`
- `outputs/paper_test/reviews/paper_symbol_review_buckets.csv`

정리하면:

- `paper_daily_review_summary.md`
  - 시스템이 생성하는 daily result summary
- `paper_symbol_review_buckets.csv`, `paper_symbol_review_worksheet.csv`
  - review 대상을 정리하는 upstream worksheet
- `paper_manual_review_log_template.csv`
  - 사람이 답변할 review template
- `paper_manual_review_log.csv`
  - 최종 review source of truth

### 2.3 기존 Review CSV schema

실제 template 및 final log 기준 핵심 컬럼은 아래와 같다.

- `review_date`
- `symbol`
- `review_bucket`
- `review_priority`
- `sample_size_flag`
- `symbol_status`
- `question_id`
- `question_text`
- `question_category`
- `is_actionable`
- `manual_answer`
- `review_status`
- `follow_up_needed`
- `review_tag`
- `reviewer_note`
- `source_worksheet_path`
- `created_at`

### 2.4 컬럼 역할 구분

사용자 입력 중심 컬럼:

- `manual_answer`
- `review_status`
- `follow_up_needed`
- `review_tag`
- `reviewer_note`

Python이 생성/관리하는 컬럼:

- `review_date`
- `symbol`
- `review_bucket`
- `review_priority`
- `sample_size_flag`
- `symbol_status`
- `question_id`
- `question_text`
- `question_category`
- `is_actionable`
- `source_worksheet_path`
- `created_at`

validation에 직접 쓰이는 컬럼:

- `review_status`
- `manual_answer`
- `follow_up_needed`
- `review_tag`
- `reviewer_note`
- `is_actionable`
- `review_date`
- `symbol`
- `question_id`

append 후 final log에 남는 컬럼:

- 위 컬럼 전체


## 3. 기존 Review CLI 흐름

기존 review 관련 CLI는 아래와 같이 연결되어 있다.

- `paper.py review`
- `paper.py review-template`
- `paper.py review-validate`
- `paper.py review-append`

흐름 정리:

1. `review-template`
   - review template CSV/MD 생성
2. `review-validate`
   - template 작성 결과 검증
3. `review-append`
   - 검증 통과 row를 최종 review log CSV에 append
4. `review`
   - reports -> review-template -> review-validate shortcut
   - 자동으로 `review-append`까지 수행하지는 않음

즉 현재 Python review 구조는 이미 `template -> validate -> append -> final log`로 정리되어 있다.


## 4. Notion row 단위 후보 비교

### A. 질문 1개 = Notion row 1개

장점:

- 기존 CSV schema와 1:1 매핑이 가장 쉽다.
- `review_date + symbol + question_id` 기준 dedupe/validation이 명확하다.
- 후속 importer 구현이 단순하다.
- append 정책과 자연스럽게 연결된다.

단점:

- row 수가 많아진다.
- 모바일에서 하루 review 항목이 많을 때 피로도가 생길 수 있다.

### B. 날짜 1개 = Notion row 1개, 질문/답변은 page body

장점:

- Notion row 수가 적다.
- 화면이 단순하다.

단점:

- 기존 CSV 질문 단위 구조와 매핑이 어렵다.
- validation granularity가 떨어진다.
- 일부 질문만 누락된 경우 탐지가 어렵다.

### C. template row와 answer row를 같은 DB에서 Status로 분리

장점:

- DB를 하나만 쓰면 된다.

단점:

- mobile input과 technical row가 섞일 수 있다.
- Notion view policy가 복잡해진다.
- importer가 template/answer 상태를 더 세밀하게 구분해야 한다.

### D. template DB와 answer DB를 분리

장점:

- 역할 분리는 명확하다.

단점:

- DB 수가 늘어난다.
- 운영 복잡도가 커진다.
- 기존 Python source 구조에 비해 과하다.


## 5. 권장 Manual Reviews DB schema

권장 DB 이름:

- `Manual Reviews`

기본 설계 원칙:

- 질문 1개 = Notion row 1개
- 기존 CSV의 질문 단위 구조를 그대로 따른다.
- 사용자가 스마트폰에서 입력해야 하는 필드는 최소화한다.
- validation/import/status 관련 필드는 시스템 관리 필드로 분리한다.

### 5.1 권장 속성 목록

- `Name`
- `External Key`
- `Review Date`
- `Symbol`
- `Question ID`
- `Question`
- `Manual Answer`
- `Review Status`
- `Follow-up Needed`
- `Review Tag`
- `Reviewer Note`
- `Source Template Key`
- `Validation Status`
- `Validation Message`
- `Import Status`
- `Imported At`
- `Synced At`

### 5.2 기존 CSV와의 대응

기존 CSV 컬럼과 직접 대응되는 핵심 필드는 아래와 같다.

- `Review Date` <- `review_date`
- `Symbol` <- `symbol`
- `Question ID` <- `question_id`
- `Question` <- `question_text`
- `Manual Answer` <- `manual_answer`
- `Review Status` <- `review_status`
- `Follow-up Needed` <- `follow_up_needed`
- `Review Tag` <- `review_tag`
- `Reviewer Note` <- `reviewer_note`
- `Source Template Key` <- `source_worksheet_path` 또는 template row key

운영 편의상 아래 시스템 컨텍스트 필드를 추가 후보로 둘 수 있다.

- `Review Bucket`
- `Review Priority`
- `Sample Size Flag`
- `Symbol Status`
- `Question Category`

다만 1차 schema에서는 메인 입력 화면 복잡도를 줄이기 위해 필수 속성으로 강제하지 않는 편이 낫다.


## 6. 필수 입력 필드 / 선택 필드 / 시스템 관리 필드 구분

### 6.1 필수 입력 필드

- `Review Date`
- `Symbol`
- `Question`
- `Manual Answer`
- `Review Status`

권장 타입:

- `Review Date` = `Date`
- `Symbol` = `Rich text`
- `Question` = `Rich text`
- `Manual Answer` = `Rich text`
- `Review Status` = `Select`

### 6.2 선택 / 운영 편의 필드

- `Follow-up Needed`
- `Review Tag`
- `Reviewer Note`

권장 타입:

- `Follow-up Needed` = `Select` 또는 `Checkbox`
- `Review Tag` = `Select`
- `Reviewer Note` = `Rich text`

Python validator와의 일관성을 우선하면 `Follow-up Needed`는 boolean 의미를 갖는 `Select`로 두는 편이 안전하다.

### 6.3 시스템 관리 필드

- `Name`
- `External Key`
- `Question ID`
- `Source Template Key`
- `Validation Status`
- `Validation Message`
- `Import Status`
- `Imported At`
- `Synced At`

권장 타입:

- `Name` = `Title`
- `External Key` = `Rich text`
- `Question ID` = `Rich text`
- `Source Template Key` = `Rich text`
- `Validation Status` = `Select`
- `Validation Message` = `Rich text`
- `Import Status` = `Select`
- `Imported At` = `Rich text`
- `Synced At` = `Rich text`


## 7. 권장 view policy

사용자 요구는 아래와 같다.

- 스마트폰에서 입력 가능해야 한다.
- 메인 화면에 너무 많은 정보가 노출되면 안 된다.

이를 기준으로 아래 view를 권장한다.

### 7.1 Input

사용자가 실제로 답변을 작성하는 기본 화면.

표시 권장 필드:

- `Review Date`
- `Symbol`
- `Question`
- `Manual Answer`
- `Review Status`
- `Follow-up Needed`
- `Review Tag`
- `Reviewer Note`

숨김 권장 필드:

- `External Key`
- `Question ID`
- `Source Template Key`
- `Validation Status`
- `Validation Message`
- `Import Status`
- `Imported At`
- `Synced At`

### 7.2 Validation

Python validation 이후 확인하는 화면.

표시 권장 필드:

- `Review Date`
- `Symbol`
- `Question`
- `Manual Answer`
- `Review Status`
- `Follow-up Needed`
- `Review Tag`
- `Validation Status`
- `Validation Message`

필터 후보:

- `Validation Status = FAIL`
- `Validation Status = WARNING`

### 7.3 Technical

import/debug용 화면.

표시 권장 필드:

- `Name`
- `External Key`
- `Review Date`
- `Symbol`
- `Question ID`
- `Question`
- `Review Status`
- `Source Template Key`
- `Validation Status`
- `Validation Message`
- `Import Status`
- `Imported At`
- `Synced At`

### 7.4 Committed

최종 CSV append 완료 row 확인용 화면.

표시 권장 필드:

- `Review Date`
- `Symbol`
- `Question`
- `Review Status`
- `Follow-up Needed`
- `Review Tag`
- `Import Status`
- `Imported At`

필터 후보:

- `Import Status = COMMITTED`


## 8. 스마트폰 입력 편의성 평가

스마트폰 입력 관점에서 보면:

- `질문 1개 = Notion row 1개`는 row 수가 늘지만,
- 각 row가 짧고 입력 필드가 제한되어 있어 모바일 편집 자체는 단순하다.

특히 아래 조건에서는 모바일 사용성이 유지된다.

- Input view에 기술 필드를 숨긴다.
- 기본 정렬을 `Review Date`, `Symbol`, `Question ID`로 고정한다.
- `Review Status`, `Follow-up Needed`, `Review Tag`는 select 위주로 둔다.

주의점:

- 하루 review 질문 수가 많으면 row navigation 비용이 커진다.
- 따라서 template 자체가 과도하게 길어지지 않도록 Python 쪽 질문 생성 정책도 후속 점검 대상이다.


## 9. 후속 importer/commit 흐름

후속 MFU에서 구현할 권장 흐름은 아래와 같다.

1. Python이 review template를 생성한다.
2. Notion `Manual Reviews` DB에 입력 row를 준비하거나 export한다.
3. 사용자가 Notion에서 답변을 작성한다.
4. Python이 Notion row를 read-only import한다.
5. validation / preview를 수행한다.
6. 사용자 승인 후 `paper_manual_review_log.csv`에 append한다.
7. append report를 생성한다.
8. Notion row에 `Validation Status`, `Import Status`, `Imported At` 등을 back-write한다.

중요:

- Notion은 source of truth가 아니다.
- 최종 원장은 여전히 `paper_manual_review_log.csv`다.


## 10. 최종 권고안

권고 A: 질문 1개 = Notion row 1개로 간다.

이유:

- 기존 CSV schema와 가장 잘 맞는다.
- 기존 validator/append 흐름과 바로 연결된다.
- dedupe key를 `review_date + symbol + question_id`로 안정적으로 둘 수 있다.
- 사용자가 스마트폰에서 질문별로 순차 입력하기도 용이하다.


## 11. 반론과 검증

반론:

- 질문별 row는 너무 많아져 Notion 화면이 복잡해질 수 있다.
- 날짜 1개 = row 1개 + page body 방식이 더 간단해 보일 수 있다.

검증:

- 기존 Python 원장은 질문 단위 row 구조다.
- validator와 append 정책도 질문 단위다.
- 따라서 날짜 단위 row로 바꾸면 importer/validation/append 전부를 재설계해야 한다.

결론:

- 모바일 화면 단순성만 보면 날짜 단위 row가 매력적일 수 있지만,
- 현재 system architecture와 source-of-truth 원칙을 유지하려면 질문 단위 row가 더 안전하다.


## 12. 다음 MFU 제안

권장 후속 순서:

1. `PAPER14-7D`: Manual Review read-only importer preview
2. `PAPER14-7E`: Manual Review validation / append commit
3. `PAPER14-7F`: Manual Review status back-write
4. `PAPER14-7G`: Review 포함 운영 SOP 보강

장기적으로는 Review template row를 Notion에 어떻게 준비할지:

- Python export로 미리 올릴지
- 사용자가 기본 row를 수동 생성할지

이 두 가지 중 운영 비용이 낮은 방식을 별도 평가하는 것이 좋다.

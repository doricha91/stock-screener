# MFU-PAPER14-7D: Manual Review read-only importer preview

## 1. 목적

이번 PAPER14-7D는 Manual Review read-only importer preview 작업이며, Review append commit, Notion status back-write, Python review 원장 수정, Notion actual write는 수행하지 않았다.

본 MFU의 목표는 Notion `Manual Reviews` DB에 질문 단위 row로 입력된 사후복기 답변을 Python에서 read-only로 가져와, 기존 review 원장 구조에 맞는 validation preview를 생성하는 것이다.


## 2. question-level row 정책

`PAPER14-7C`에서 확정한 정책을 그대로 따른다.

- 질문 1개 = Notion row 1개
- 기존 CSV 기준 dedupe key = `review_date + symbol + question_id`
- Notion은 입력 UI 또는 staging layer
- 최종 review 원장은 `paper_manual_review_log.csv`


## 3. minimal input field 정책

사용자 입력 중심 필드는 아래에 한정한다.

- `Manual Answer`
- `Review Status`
- `Follow-up Needed`
- `Review Tag`
- `Reviewer Note`

나머지 필드는 template 또는 시스템 관리 필드로 본다.


## 4. source of truth 원칙

기본 원칙:

- Notion = 입력 UI / staging layer
- Python = 검증 / 정규화 / append commit 주체
- CSV / Markdown = Review source of truth

이번 7D에서는 아래 파일을 읽기만 한다.

- `outputs/paper_test/reviews/paper_manual_review_log.csv`
- `outputs/paper_test/reviews/paper_manual_review_log_template.csv`


## 5. Notion mapping

새 data source key:

- `manual_reviews`

환경변수 override:

- `NOTION_MANUAL_REVIEWS_DATA_SOURCE_ID`

예시 property mapping:

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

import candidate 기본 조건:

- `Review Date = --date`
- `Import Status = READY`

## 5-1. Manual Reviews DB 속성 정리

`Manual Reviews` DB는 아래 3개 그룹으로 나누어 정리한다.

1. 사용자 입력 중심 필드
2. 질문 식별 / 추적 필드
3. 검증 / import 관리 필드

### 1. 사용자 입력 중심 필드

- `Manual Answer`
- `Review Status`
- `Follow-up Needed`
- `Review Tag`
- `Reviewer Note`

권장 타입:

- `Manual Answer`: `Rich text`
- `Review Status`: `Select`
- `Follow-up Needed`: `Select` 또는 `Checkbox`
- `Review Tag`: `Select` 또는 `Multi-select`
- `Reviewer Note`: `Rich text`

속성 설명:

- `Manual Answer`
  - 사용자가 질문에 대해 직접 작성하는 사후복기 답변
- `Review Status`
  - 해당 질문에 대한 검토 완료 상태
- `Follow-up Needed`
  - 추가 확인 또는 후속 액션 필요 여부
- `Review Tag`
  - 사후복기 분류 태그
- `Reviewer Note`
  - 자유 메모, 보강 설명, 다음 점검 메모

### 2. 질문 식별 / 추적 필드

- `Name`
- `External Key`
- `Review Date`
- `Symbol`
- `Question ID`
- `Question`
- `Source Template Key`

권장 타입:

- `Name`: `Title`
- `External Key`: `Rich text`
- `Review Date`: `Date`
- `Symbol`: `Rich text`
- `Question ID`: `Rich text`
- `Question`: `Rich text`
- `Source Template Key`: `Rich text`

속성 설명:

- `Name`
  - Notion 목록 화면에서 row를 식별하기 위한 제목
  - 예: `2026-05-25 AAPL review_loss_1`
- `External Key`
  - Notion row와 Python preview/import 결과를 안정적으로 연결하기 위한 식별자
- `Review Date`
  - review 대상 날짜
- `Symbol`
  - review 대상 종목
- `Question ID`
  - 기존 template/CSV 기준 질문 식별자
- `Question`
  - 사용자가 답변할 실제 질문 원문
- `Source Template Key`
  - 어떤 template row 또는 worksheet source에서 왔는지 추적하기 위한 키

### 3. 검증 / import 관리 필드

- `Validation Status`
- `Validation Message`
- `Import Status`
- `Imported At`
- `Synced At`

권장 타입:

- `Validation Status`: `Select`
- `Validation Message`: `Rich text`
- `Import Status`: `Select`
- `Imported At`: `Rich text`
- `Synced At`: `Rich text`

속성 설명:

- `Validation Status`
  - Python preview/validator 기준 PASS/WARNING/FAIL 상태
- `Validation Message`
  - warning 또는 fail 상세 메시지 요약
- `Import Status`
  - preview 대상인지, commit 완료인지 등 review import workflow 상태
- `Imported At`
  - 최종 append commit 완료 시각
- `Synced At`
  - Notion row와 Python sync 처리 시각

## 5-2. 권장 select / boolean option

### Review Status

권장 option:

- `pending`
- `reviewed`
- `deferred`
- `not_applicable`

의미:

- `pending`
  - 아직 답변/검토 완료 전 상태
- `reviewed`
  - 답변 작성 완료, 일반 검토 완료 상태
- `deferred`
  - 답변은 남기되 후속 검토로 넘기는 상태
- `not_applicable`
  - 해당 질문이 이번 review row에 실질적으로 적용되지 않는 상태

### Follow-up Needed

권장 option:

- `true`
- `false`

의미:

- `true`
  - 해당 질문에 대해 추가 확인, 후속 조사, 다음 회차 점검이 필요함
- `false`
  - 현재 답변 기준으로 추가 후속 조치가 필요하지 않음

정책:

- 기존 Python validator와의 정합성을 위해 의미상 boolean으로 유지한다.
- Notion 속성 타입은 `Select` 또는 `Checkbox`를 허용하되, importer에서는 `true/false` 의미로 정규화한다.

### Review Tag

권장 option:

- `entry_rule`
- `exit_rule`
- `position_sizing`
- `market_regime`
- `risk_management`
- `data_quality`
- `execution_quality`
- `signal_quality`
- `psychology`
- `other`

의미:

- `entry_rule`
  - 진입 조건 해석, 진입 신호 품질, 진입 시점 판단 문제
- `exit_rule`
  - 청산 조건, stop rule, 이익실현/손절 실행 문제
- `position_sizing`
  - 포지션 크기, 비중, sizing 규칙 관련 문제
- `market_regime`
  - 시장 국면 판단, regime 전환 대응, macro context 관련 문제
- `risk_management`
  - 손실 통제, 리스크 한도, 보호 장치 관련 문제
- `data_quality`
  - 데이터 누락, 가격 이상치, source artifact 정합성 문제
- `execution_quality`
  - 체결 품질, 주문 실행, 실제 체결과 계획 차이 관련 문제
- `signal_quality`
  - 신호 자체의 품질, false positive/negative, 전략 적합성 문제
- `psychology`
  - 사용자의 심리, 규칙 이탈, discretionary 판단 개입 문제
- `other`
  - 위 분류에 명확히 들어가지 않는 기타 review 메모

정책:

- 단일 태그면 `Select`
- 다중 태그를 허용하려면 `Multi-select`
- 기존 Python validator는 comma-separated multiple tag를 warning으로 보므로, 1차 운영은 단일 태그 기준이 더 안전하다.

### Validation Status

권장 option:

- `NOT_CHECKED`
- `PASS`
- `WARNING`
- `FAIL`

의미:

- `NOT_CHECKED`
  - Python preview/validator를 아직 실행하지 않은 상태
- `PASS`
  - 필수 입력과 기존 validator 규칙을 모두 만족한 상태
- `WARNING`
  - import는 가능하지만, 보강 메모 또는 선택 필드 누락 등 경고가 있는 상태
- `FAIL`
  - append commit 전 반드시 수정해야 하는 오류가 있는 상태

### Import Status

권장 option:

- `DRAFT`
- `READY`
- `PREVIEWED`
- `COMMITTED`
- `SKIPPED`

의미:

- `DRAFT`
  - 사용자가 아직 입력 중인 상태
- `READY`
  - preview 대상 후보로 읽어도 되는 상태
- `PREVIEWED`
  - Python preview는 완료됐지만 아직 append commit 전 상태
- `COMMITTED`
  - 최종 review log append 완료 상태
- `SKIPPED`
  - 정책상 import 대상에서 제외된 상태


## 6. validation 규칙

### 6.1 FAIL

- `Review Date` 없음
- `Symbol` 없음
- `Question ID` 없음
- `Question` 없음
- `Manual Answer` 없음
- `Review Status` 없음
- `Review Status = pending`
- 동일 batch 내 `review_date + symbol + question_id` 중복
- 기존 `paper_manual_review_log.csv`에 같은 review key 존재

### 6.2 WARNING

- `Follow-up Needed` 없음
- `Review Tag` 없음
- `Reviewer Note` 없음
- `Source Template Key` 없음
- template에 없는 `question_id`
- template와 `Question` 원문 불일치

### 6.3 기존 validator 재사용 범위

기존 `paper_manual_review_log_validator.py`의 아래 규칙을 preview에도 재사용한다.

- `review_status` 허용값 검사
- `follow_up_needed` 허용값 검사
- `review_tag` 허용값 검사
- duplicate key 검사
- `follow_up_needed=true`일 때 context 유무 검사

단, 이번 7D preview는 append 전 단계이므로 `Manual Answer 없음 = FAIL`, `pending = FAIL`을 별도로 더 엄격하게 적용한다.


## 7. preview report 구조

출력 파일:

- `outputs/paper_test/reports/manual_review_import_preview_YYYYMMDD.json`
- `outputs/paper_test/reports/manual_review_import_preview_YYYYMMDD.md`

포함 내용:

- `review_date`
- `candidate_count`
- `pass_count`
- `warning_count`
- `fail_count`
- `append_allowed`
- `normalized candidates`
- `validation issues`
- `duplicate_candidates`
- `source_data_source_id`

판정 규칙:

- FAIL 하나라도 있으면 `append_allowed=false`
- WARNING만 있으면 `append_allowed=true_with_warnings`
- 모두 PASS면 `append_allowed=true`


## 8. 제외 범위

이번 작업에서 하지 않는다.

- `paper_manual_review_log.csv` append
- review CSV/MD overwrite
- Notion `Validation Status / Import Status` back-write
- Notion actual write
- Review commit
- Manual Execution import/commit/status sync 재실행
- paper ledger CSV 수정


## 9. 후속 7E append commit 계획

후속 MFU에서 구현할 권장 흐름:

1. Notion `Manual Reviews` row read-only import
2. validation preview 생성
3. 사용자 승인
4. `paper_manual_review_log.csv` append
5. append report 생성
6. Notion review row status back-write

즉 7D는 append 직전의 preview 계층에 해당한다.


## 10. 테스트 결과

테스트 범위:

- question-level row normalization
- missing `Manual Answer` FAIL
- optional field WARNING
- batch duplicate FAIL
- existing review log duplicate FAIL
- preview JSON/Markdown 생성
- `--commit` not implemented failure


## 11. 남은 리스크

- 현재 template 비교는 로컬 `paper_manual_review_log_template.csv`가 존재할 때만 수행한다.
- `Question` mismatch는 warning으로만 처리하며 auto-fix는 하지 않는다.
- 모바일 입력 row 수가 많아질 수 있어, 장기적으로 template question count를 함께 관리할 필요가 있다.

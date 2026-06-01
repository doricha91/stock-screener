# MFU-PAPER14-7B 작업 지시문: 사후복기 Review 구조 조사 및 Notion 운영 루프 위치 정리

## 목적

paper 전체 운영 루프에서 사후복기 Review가 어떤 역할을 해야 하는지 조사하고, 기존 Python의 `paper_manual_review` 관련 코드/CSV/MD 구조를 확인한다.

Review도 Notion을 source of truth로 두지 않는다.

기본 원칙:

```text
Notion = 입력 UI / 검토 UI / staging layer
Python = 검증 / 정규화 / commit 주체
CSV / Markdown / SQLite = source of truth
```

이번 작업은 조사/설계 문서화 작업이다.  
Notion Review DB 생성, Python import/commit 구현, 기존 review 코드 수정은 수행하지 않는다.

반드시 명시:

```text
이번 PAPER14-7B는 사후복기 Review 구조 조사 및 Notion 운영 루프 위치 정리 작업이며, Notion Review DB 생성, Review import/commit 구현, Python 코드 수정, Notion actual export는 수행하지 않았다.
```

---

## 기준 커밋

기준 커밋:

```text
ffd2350f5933376f4bc2b9fec26901d76f0b797d
```

최근 로그에 아래 커밋들이 있어야 한다.

```text
317e0d8 PAPER14-6: add Daily Review Summary closeout verification
5ed9982 PAPER14-7A: assess Performance Summary Notion scope
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

현재 Notion 연동 흐름은 아래까지 완료되어 있다.

```text
Daily Plan 생성
→ Daily Plan Notion export
→ Manual Executions에 실제 체결 입력
→ Python read-only import
→ validation preview
→ preview 기반 ledger commit
→ account / position / current_state 갱신
→ Manual Execution status back-write
→ Daily Review Summary Notion export
```

하지만 여기서 `Daily Review Summary`는 시스템이 생성한 하루 운영 결과 요약이다.

이번에 조사할 사후복기 Review는 별도 개념이다.

```text
Daily Review Summary
= 시스템이 만든 결과 요약 report

Manual Review / Retrospective
= 사람이 작성하는 사후복기, 판단, 실수, 개선점, 다음 액션 기록
```

사용자 요구:

```text
Review도 Notion을 원장으로 두지 않는다.
Python의 CSV / Markdown을 Review source of truth로 둔다.
Notion은 작성 UI 또는 staging layer로만 사용한다.
```

---

## 조사 대상

먼저 기존 review 관련 코드를 전부 찾는다.

Windows CMD 기준:

```cmd
findstr /S /N /I "paper_manual_review manual_review review retrospective retrospection" *.py *.md *.json
```

반드시 확인할 후보:

```text
scripts/
core/
tests/
docs/
outputs/paper_test/
outputs/paper_test/reports/
docs/operations/
```

특히 아래 항목이 있는지 확인한다.

```text
paper_manual_review 관련 Python 파일
review CSV 생성/저장 코드
review Markdown 생성/저장 코드
review preview/commit CLI
paper.py review 관련 명령
Daily Review Summary와 review의 연결 여부
manual review schema 또는 테스트
```

---

## 확인할 질문

문서에서 아래 질문에 답한다.

### 1. 기존 Review 코드가 실제로 존재하는가?

확인할 것:

```text
파일명
함수명
CLI 명령
입력 source
출력 CSV/MD 경로
테스트 파일
현재 사용 여부
```

만약 `paper_manual_review`라는 정확한 이름이 없으면, 유사 기능을 찾고 “정확한 이름은 없음”이라고 보고한다.

### 2. Review source of truth는 무엇이어야 하는가?

후보:

```text
paper_manual_review.csv
manual_review_YYYYMMDD.md
daily_review_manual_notes.csv
기존 코드가 정의한 다른 CSV/MD
```

결론은 반드시 아래 원칙과 맞아야 한다.

```text
Notion은 source of truth가 아니다.
Review 원장은 Python 쪽 CSV/MD다.
```

### 3. Notion은 Review 흐름에서 어디에 들어가야 하는가?

후보 흐름:

```text
Daily Review Summary 확인
→ 사용자가 Notion Review 입력 DB에 사후복기 작성
→ Python이 Notion Review 입력값 read-only import
→ validation / preview
→ 사용자 승인
→ review CSV/MD commit
→ Notion Review row status back-write
```

이 흐름이 적절한지 평가한다.

### 4. paper 전체 운영 루프에서 Review 위치는 어디인가?

현재 루프를 기준으로 Notion 위치를 정리한다.

```text
Prepare
→ Daily Plan
→ Plan Export
→ Action
→ Actual Action Input
→ Validation Preview
→ Commit
→ State Refresh
→ Status Sync
→ Reports
→ Review / Retrospective
→ Weekly / Benchmark / Next Plan
```

각 단계에서 아래를 구분한다.

```text
Python 실행 단계
Notion 입력/확인 단계
source of truth 파일
스마트폰에서 가능한 단계
반드시 로컬 PC에서 해야 하는 단계
```

### 5. 스마트폰 운영 가능 범위는 어디까지인가?

아래 기준으로 판단한다.

```text
스마트폰에서 가능한 것:
- Daily Plan 확인
- Manual Executions 입력
- Daily Review Summary 확인
- Manual Review / Retrospective 입력

로컬 PC에서 해야 하는 것:
- preview 실행
- commit 실행
- ledger/state 갱신
- status back-write
- export 실행
```

원격 실행, GitHub Actions, 모바일 웹 UI는 이번 작업에서 구현하지 말고 장단점만 간단히 평가한다.

---

## 결과 문서

추가 문서:

```text
docs/TRD/mfu_paper14_7b_review_flow_assessment.md
```

포함 내용:

```text
1. 목적
2. 기존 paper_manual_review 관련 코드 조사 결과
3. 기존 Review CSV/MD source 후보
4. Daily Review Summary와 Manual Review의 차이
5. Review source of truth 원칙
6. Notion Review staging layer 후보 흐름
7. paper 전체 운영 루프에서 Notion 위치
8. 스마트폰 가능 단계 / 로컬 PC 필수 단계
9. 구현 필요 여부와 후속 MFU 제안
10. 리스크와 반론
```

---

## 최종 권고안 형식

아래 중 하나로 명확히 결론을 낸다.

```text
권고 A: 기존 paper_manual_review 구조를 활용해 Notion Review input/import/commit을 설계한다.
권고 B: 기존 review 코드가 미흡하므로 먼저 Python CSV/MD Review 원장 구조를 정비한다.
권고 C: Review는 당장은 Notion-only 메모로 두되, Python source-of-truth 전환 전까지 자동화하지 않는다.
권고 D: Review 기능은 보류하고 운영 SOP부터 정리한다.
```

각 권고에는 반드시 이유와 반론을 포함한다.

---

## 금지 사항

```text
Python 코드 수정 금지
config 수정 금지
Notion DB 생성 금지
Notion actual export 실행 금지
Review import/commit 구현 금지
Manual Execution import/commit/status sync 재실행 금지
paper ledger CSV 수정 금지
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

findstr /S /N /I "paper_manual_review manual_review review retrospective retrospection" *.py *.md *.json
```

필요 시 기존 테스트 상태만 확인한다.

```cmd
set PYTHONPATH=.
python -m pytest tests\test_paper_manual_execution_commit.py tests\test_notion_manual_execution_importer.py tests\test_notion_manual_execution_status_sync.py -q
```

테스트 실패 시 수정하지 말고 보고한다.

---

## 커밋 정책

문서만 커밋한다.

```cmd
git add docs\TRD\mfu_paper14_7b_review_flow_assessment.md
git diff --cached --name-only
git commit -m "PAPER14-7B: assess manual review flow and Notion placement"
```

커밋 전 staged 파일에 위 문서 외 파일이 있으면 커밋하지 말고 보고한다.

---

## 성공 기준

```text
기존 paper_manual_review 관련 코드/문서/출력물이 조사된다.
Review source of truth 후보가 정리된다.
Daily Review Summary와 Manual Review의 역할 차이가 정리된다.
Notion이 Review 흐름에서 staging layer로 들어갈 위치가 정리된다.
전체 paper 운영 루프에서 Notion의 위치가 정리된다.
스마트폰 가능 단계와 로컬 PC 필수 단계가 구분된다.
후속 MFU가 제안된다.
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
4. 조사한 파일/검색 결과
5. paper_manual_review 관련 코드 존재 여부
6. Review CSV/MD source 후보
7. Daily Review Summary와 Manual Review 차이
8. Notion Review staging 흐름 제안
9. 전체 paper 운영 루프에서 Notion 위치
10. 스마트폰 가능 단계 / 로컬 PC 필수 단계
11. 최종 권고안
12. 반론과 검증
13. 코드 수정 여부
14. output/CSV 수정 여부
15. 테스트 실행 여부와 결과
16. 커밋 hash와 message
17. 다음 MFU 제안
```

반드시 명시:

```text
이번 PAPER14-7B는 사후복기 Review 구조 조사 및 Notion 운영 루프 위치 정리 작업이며, Notion Review DB 생성, Review import/commit 구현, Python 코드 수정, Notion actual export는 수행하지 않았다.
```
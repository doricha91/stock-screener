# MFU-PAPER14-6-closeout 작업 지시문: Daily Review Summary actual export 검증 문서화

## 목적

PAPER14-6에서 구현한 Daily Review Summary Notion export의 실제 검증 결과를 문서화하고, PAPER14-6을 closeout한다.

이번 작업은 문서화 작업이다.

반드시 명시:

```text
이번 PAPER14-6-closeout은 Daily Review Summary Notion export의 actual export 검증 결과를 문서화하는 작업이며, 코드 수정, paper ledger 수정, Manual Execution commit, Notion status back-write는 수행하지 않는다.
```

---

## 기준 커밋

기준 커밋:

```text
ffd2350f5933376f4bc2b9fec26901d76f0b797d
```

최근 로그에 아래 커밋들이 있어야 한다.

```text
7ebf999 PAPER14-5E: sync Manual Execution status back to Notion
3a1771f PAPER14-6: export Daily Review Summary to Notion
```

작업 전 확인:

```cmd
cd /d D:\python\StockScreener
git rev-parse HEAD
git log --oneline -12
git status --short
```

기준 SHA 이후 상태가 아니면 중단하고 보고한다.

---

## 배경

PAPER14-6에서 아래 기능이 구현됐다.

```text
daily_review_summaries Notion export target 추가
Daily Review Summary payload 생성
Daily Review Summary page body 생성
schema validation 추가
--daily-review-summary CLI 추가
dry-run 성공
```

이후 사용자가 직접 Notion data source id를 설정하고 actual export를 진행했다.

확인된 결과:

```text
1차 actual export: created 확인
2차 actual export: updated 확인
```

따라서 External Key 기반 upsert가 정상 동작한 것으로 문서화한다.

External Key:

```text
daily_review_summary:{review_date}
```

예:

```text
daily_review_summary:2026-05-25
```

---

## 수정 대상

기본 수정 문서:

```text
docs/TRD/mfu_paper14_6_daily_review_summary_notion_export.md
```

필요 시 추가 문서:

```text
docs/TRD/mfu_paper14_6_closeout.md
```

원칙:

```text
기본은 기존 6번 TRD 문서에 closeout section을 추가한다.
문서가 너무 길어지면 별도 closeout 문서를 추가한다.
```

---

## 문서화 요구사항

아래 내용을 추가한다.

```text
1. Daily Review Summaries data source id 설정 완료 여부
2. schema validation 결과
3. dry-run 결과
4. actual export 1차 결과: created
5. actual export 2차 결과: updated
6. External Key upsert 검증 결과
7. Notion UI 확인 결과
8. page body 구성 확인
9. paper ledger 수정 없음
10. Manual Execution import/commit 재실행 없음
11. Notion Manual Executions status back-write 없음
12. 남은 리스크
13. 다음 단계 제안
```

Notion UI 확인 항목:

```text
Review Date
Review Status
Availability Status
Committed Trade Count
Warning Count
Cash Start
Cash End
Cash Impact
Position Impact Summary
Commit Report Path
Preview Report Path
Sync Status
```

page body 확인 항목:

```text
오늘의 리뷰 요약
체결 요약
포지션 변화
경고 / 특이사항
원천 파일
```

---

## 제외 범위

이번 작업에서 하지 않는다.

```text
Python 코드 수정 금지
config 수정 금지
Notion actual export 재실행 금지
Manual Execution import 재실행 금지
Manual Execution commit 재실행 금지
Notion status back-write 재실행 금지
paper_execution_log.csv 수정 금지
paper_account_snapshot.csv 수정 금지
paper_position_snapshot.csv 수정 금지
paper_current_state_YYYYMMDD.json 수정 금지
output 파일 수정/삭제 금지
DB/PNG 파일 수정/삭제 금지
git add . 금지
git add -A 금지
```

---

## 검증 명령

문서 작업이므로 코드 테스트는 선택이다.  
상태 확인만 우선 수행한다.

```cmd
cd /d D:\python\StockScreener
git diff --name-only
git status --short
```

필요 시 기존 테스트 상태만 확인한다.

```cmd
set PYTHONPATH=.
python -m pytest tests\test_daily_review_summary_exporter.py tests\test_notion_exporters.py tests\test_notion_schema_validator.py -q
```

테스트 실패 시 수정하지 말고 보고한다.

---

## 커밋 정책

문서만 커밋한다.

기존 문서 수정 시:

```cmd
git add docs\TRD\mfu_paper14_6_daily_review_summary_notion_export.md
```

별도 closeout 문서 추가 시:

```cmd
git add docs\TRD\mfu_paper14_6_closeout.md
```

커밋 전 확인:

```cmd
git diff --cached --name-only
```

커밋 메시지:

```cmd
git commit -m "PAPER14-6: document Daily Review Summary export closeout"
```

output / CSV / backup / DB 파일은 커밋하지 않는다.

---

## 성공 기준

```text
PAPER14-6 actual export created → updated 검증 결과가 문서화된다.
Daily Review Summary External Key upsert 정책이 검증 완료로 기록된다.
Notion UI 확인 결과가 기록된다.
paper ledger 수정 없음이 명시된다.
Manual Execution import/commit/status sync 재실행 없음이 명시된다.
문서만 커밋된다.
```

---

## 결과 보고 형식

5천자 이내.

```text
1. Summary
2. 기준 커밋 확인 결과
3. 변경 파일
4. 문서화한 actual export 결과
5. created → updated 확인 내용
6. Notion UI 확인 내용
7. page body 확인 내용
8. paper ledger 수정 여부
9. Manual Execution import/commit/status sync 재실행 여부
10. 테스트 실행 여부와 결과
11. 커밋 hash와 message
12. stage하지 않은 파일
13. 남은 리스크
14. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER14-6-closeout은 Daily Review Summary Notion export의 actual export 검증 결과를 문서화한 작업이며, 코드 수정, paper ledger 수정, Manual Execution commit, Notion status back-write는 수행하지 않았다.
```
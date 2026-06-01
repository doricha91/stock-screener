# MFU-PAPER14-6-closeout_revision 작업 지시문

## 목적

PAPER14-6 Daily Review Summary Notion export 문서에 actual export 검증 결과를 보완한다.

이전 closeout 작업에서 `docs/TRD/mfu_paper14_6_daily_review_summary_notion_export.md`를 한글로 구조화한 것은 유지한다.  
이번 revision은 그 문서에 `Closeout Verification` 섹션을 추가해 실제 Notion export 검증 결과를 명확히 남기는 작업이다.

반드시 명시:

```text
이번 PAPER14-6-closeout_revision은 Daily Review Summary Notion export의 actual export 검증 증적을 보완 문서화하는 작업이며, 코드 수정, Notion export 재실행, paper ledger 수정, Manual Execution import/commit/status sync는 수행하지 않았다.
```

---

## 기준 커밋

기준 커밋:

```text
ffd2350f5933376f4bc2b9fec26901d76f0b797d
```

최근 로그에 아래 커밋들이 있어야 한다.

```text
3a1771f PAPER14-6: export Daily Review Summary to Notion
```

작업 전 확인:

```cmd
cd /d D:\python\StockScreener
git rev-parse HEAD
git log --oneline -12
git status --short
git diff --name-only
```

주의:

```text
이전 closeout에서 수정한 docs/TRD/mfu_paper14_6_daily_review_summary_notion_export.md 내용은 되돌리지 않는다.
현재 해당 문서가 uncommitted 상태라면 기존 변경을 보존한 채 closeout verification만 추가한다.
```

---

## 수정 대상

수정 파일:

```text
docs/TRD/mfu_paper14_6_daily_review_summary_notion_export.md
```

새 파일은 만들지 않는다.  
기존 문서에 아래 섹션을 추가한다.

```text
## Closeout Verification
```

---

## 추가할 내용

`Closeout Verification` 섹션에 아래 내용을 명확히 기록한다.

### 1. Actual export 검증 결과

사용자 확인 기준:

```text
Daily Review Summaries data source id 설정 완료
schema validation 수행 완료
actual export 1차 결과: created 확인
actual export 2차 결과: updated 확인
External Key 기반 upsert 정상 확인
```

External Key:

```text
daily_review_summary:{review_date}
```

실제 예시:

```text
daily_review_summary:2026-05-25
```

### 2. Notion UI 확인 결과

아래 property가 Notion UI에서 확인됐다고 기록한다.

```text
Review Date
Review Status
Availability Status
Committed Trade Count
Warning Count
Fail Count
Cash Start
Cash End
Cash Impact
Position Impact Summary
Commit Report Path
Preview Report Path
Latest Snapshot Date
Schema Version
Synced At
Sync Status
```

### 3. Page body 확인 결과

아래 page body 섹션이 확인됐다고 기록한다.

```text
오늘의 리뷰 요약
체결 요약
포지션 변화
경고 / 특이사항
원천 파일
```

### 4. 수정하지 않은 것

아래 항목도 명시한다.

```text
paper_execution_log.csv 수정 없음
paper_account_snapshot.csv 수정 없음
paper_position_snapshot.csv 수정 없음
paper_current_state_YYYYMMDD.json 수정 없음
Manual Execution import 재실행 없음
Manual Execution commit 재실행 없음
Manual Execution status back-write 재실행 없음
Notion DB schema 변경 없음
Python 코드 수정 없음
```

### 5. 최종 판정

아래와 같이 결론을 남긴다.

```text
PAPER14-6 Daily Review Summary Notion export는 created → updated actual export 검증까지 완료됐다.
Daily Review Summary는 Daily Plan / Manual Executions / Account Snapshot / Weekly / Benchmark export 흐름과 함께 PAPER14 Notion review layer의 일일 결과 요약 역할을 수행한다.
```

---

## 금지 사항

```text
Python 코드 수정 금지
config 수정 금지
Notion actual export 재실행 금지
schema validation 재실행 필수 아님
Manual Execution import 재실행 금지
Manual Execution commit 재실행 금지
Manual Execution status sync 재실행 금지
paper ledger CSV 수정 금지
paper_current_state JSON 수정 금지
output 파일 수정/삭제 금지
DB/PNG 파일 수정/삭제 금지
git add . 금지
git add -A 금지
```

---

## 테스트

문서 보완 작업이므로 테스트는 필수 아님.

상태 확인만 수행한다.

```cmd
git diff --name-only
git status --short
```

테스트를 실행하지 않았다면 결과 보고에 아래처럼 적는다.

```text
테스트 미실행: 문서 보완 작업이며 코드 변경이 없기 때문
```

---

## 커밋 정책

문서만 stage한다.

```cmd
git add docs\TRD\mfu_paper14_6_daily_review_summary_notion_export.md
git diff --cached --name-only
git commit -m "PAPER14-6: add Daily Review Summary closeout verification"
```

커밋 전 `git diff --cached --name-only`에 위 문서 외 파일이 있으면 커밋하지 말고 보고한다.

---

## 성공 기준

```text
기존 PAPER14-6 문서 정리 내용이 보존된다.
Closeout Verification 섹션이 추가된다.
created → updated actual export 검증 결과가 명확히 기록된다.
Notion UI property 확인 결과가 기록된다.
page body 확인 결과가 기록된다.
paper ledger / Manual Execution 관련 작업을 재실행하지 않았음이 기록된다.
문서만 커밋된다.
```

---

## 결과 보고 형식

5천자 이내.

```text
1. Summary
2. 기준 커밋 확인 결과
3. 변경 파일
4. 추가한 Closeout Verification 내용
5. created → updated 검증 기록 여부
6. Notion UI 확인 기록 여부
7. page body 확인 기록 여부
8. 코드 수정 여부
9. paper ledger 수정 여부
10. Manual Execution import/commit/status sync 재실행 여부
11. 테스트 실행 여부와 결과
12. 커밋 hash와 message
13. stage하지 않은 파일
14. 남은 리스크
15. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER14-6-closeout_revision은 Daily Review Summary Notion export의 actual export 검증 증적을 보완 문서화한 작업이며, 코드 수정, Notion export 재실행, paper ledger 수정, Manual Execution import/commit/status sync는 수행하지 않았다.
```
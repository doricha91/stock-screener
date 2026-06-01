# MFU-PAPER14-7G 작업 지시문: Review 포함 운영 SOP 보강

## 목적

PAPER14 Notion 운영 흐름에 Manual Review / Retrospective 절차를 포함해 실제 daily paper 운영 SOP를 보강한다.

이번 작업은 운영 문서화 작업이다.  
Python 코드 수정, Notion export/write 실행, review append 재실행, paper ledger 수정은 수행하지 않는다.

반드시 명시:

```text
이번 PAPER14-7G는 Manual Review까지 포함한 paper 운영 SOP 문서 보강 작업이며, Python 코드 수정, Notion actual write/export, Review append commit, paper trading ledger 수정은 수행하지 않았다.
```

---

## 기준 커밋

기준 커밋:

```text
ffd2350f5933376f4bc2b9fec26901d76f0b797d
```

최근 로그에 아래 커밋들이 있어야 한다.

```text
7fcd7a1 PAPER14-7E: commit Manual Review preview to review log
64f5ff5 PAPER14-7F: sync Manual Review status back to Notion
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

현재 완료된 Notion / Review 흐름:

```text
Daily Plan 생성
→ Daily Plan Notion export
→ Notion에서 Daily Plan 확인
→ 실제 action 수행
→ Notion Manual Executions 입력
→ Manual Executions preview
→ preview 기반 execution commit
→ account / position / current_state 갱신
→ Manual Executions status sync
→ Daily Review Summary Notion export
→ Notion에서 Daily Review Summary 확인
→ Notion Manual Reviews 입력
→ Manual Reviews preview
→ preview 기반 review append
→ paper_manual_review_log.csv 반영
→ Manual Reviews status sync
```

Manual Review row가 Notion UI에서 `COMMITTED`로 변경된 것도 사용자 확인 완료됐다.

---

## 운영 정책 결정 사항

SOP에 아래 정책을 명시한다.

### 1. Review 수행 기준

```text
거래/체결이 있었던 날 → Manual Review 필수
WARNING / FAIL / 계획 이탈이 있었던 날 → Manual Review 필수
거래가 없고 Daily Review Summary가 NO_ACTIVITY인 날 → Manual Review 생략 가능
```

### 2. 스마트폰 / 로컬 PC 역할 구분

스마트폰에서 가능한 단계:

```text
Daily Plan 확인
Manual Executions 입력
Daily Review Summary 확인
Manual Reviews 입력
Notion status 확인
```

로컬 PC에서 해야 하는 단계:

```text
preview 실행
commit / append 실행
ledger / review log / state 갱신
status back-write
Notion export / sync
```

### 3. WARNING / FAIL 처리 원칙

```text
FAIL 있으면 commit/append 금지
WARNING 있으면 기본 차단
--allow-warnings를 명시했을 때만 commit/append 허용
WARNING을 허용한 경우 사유를 review 또는 operation note에 남긴다
```

### 4. Notion sync 실패 처리

```text
Python CSV/ledger/review log commit 성공 후 Notion status sync 실패
→ 원장 rollback 하지 않음
→ 같은 commit report로 status sync만 재실행
```

이유:

```text
Notion status sync는 presentation/status layer다.
원장 commit 성공 여부와 분리한다.
```

### 5. Source of truth 원칙

```text
Notion = 입력 UI / 검토 UI / staging layer
CSV / JSON / Markdown / SQLite = source of truth
Python = validation / preview / commit / append 주체
```

---

## 수정 대상 문서

우선 수정:

```text
docs/operations/paper_daily_ops.md
```

새 문서 추가 권장:

```text
docs/operations/paper_notion_ops.md
```

원칙:

```text
paper_daily_ops.md = 전체 daily operation 요약
paper_notion_ops.md = Notion 연동 상세 절차
```

기존 문서가 이미 충분히 크다면 상세 절차는 `paper_notion_ops.md`에 분리하고, `paper_daily_ops.md`에는 링크/요약만 둔다.

---

## 문서화 요구사항

### paper_daily_ops.md에 추가/수정할 내용

아래 전체 daily loop를 반영한다.

```text
1. Prepare / preflight
2. Daily Plan 생성
3. Daily Plan Notion export
4. Notion에서 Daily Plan 확인
5. 실제 action 수행
6. Notion Manual Executions 입력
7. Manual Executions preview
8. preview 확인 후 execution commit
9. account / position / current_state 갱신 확인
10. Manual Executions status sync
11. Daily Review Summary export
12. Notion에서 Daily Review Summary 확인
13. Notion Manual Reviews 입력
14. Manual Reviews preview
15. preview 확인 후 review append
16. Manual Reviews status sync
17. Weekly / Benchmark / Account Snapshot export
```

### paper_notion_ops.md에 포함할 내용

```text
1. Notion DB별 역할
2. Manual Executions 운영 절차
3. Manual Reviews 운영 절차
4. Daily Review Summary 확인 절차
5. Import Status / Validation Status 의미
6. READY → COMMITTED 상태 흐름
7. created / updated / dry-run 의미
8. WARNING / FAIL 대응
9. 스마트폰 가능 단계와 PC 필수 단계
10. Notion sync 실패 시 재실행 절차
```

---

## 반드시 포함할 명령 예시

Windows CMD 기준으로 작성한다.

Manual Executions:

```cmd
python scripts\import_notion_executions.py --date 2026-05-25 --preview --json
python scripts\import_notion_executions.py --date 2026-05-25 --commit --preview-json outputs\paper_test\reports\manual_execution_import_preview_20260525.json --allow-warnings
python scripts\sync_notion_execution_status.py --date 2026-05-25 --commit-report outputs\paper_test\reports\manual_execution_import_commit_20260525.json --json
```

Daily Review Summary:

```cmd
python scripts\export_paper_to_notion.py --daily-review-summary --date 2026-05-25 --dry-run --json
python scripts\export_paper_to_notion.py --daily-review-summary --date 2026-05-25 --json
```

Manual Reviews:

```cmd
python scripts\import_notion_reviews.py --date 2026-05-25 --preview --json
python scripts\import_notion_reviews.py --date 2026-05-25 --commit --preview-json outputs\paper_test\reports\manual_review_import_preview_20260525.json --allow-warnings
python scripts\sync_notion_review_status.py --date 2026-05-25 --commit-report outputs\paper_test\reports\manual_review_import_commit_20260525.json --json
```

---

## 제외 범위

이번 작업에서 하지 않는다.

```text
Python 코드 수정 금지
config 수정 금지
Notion actual export/write 실행 금지
Manual Execution commit 재실행 금지
Manual Review append 재실행 금지
status sync 재실행 금지
paper_execution_log.csv 수정 금지
paper_account_snapshot.csv 수정 금지
paper_position_snapshot.csv 수정 금지
paper_current_state_YYYYMMDD.json 수정 금지
paper_manual_review_log.csv 수정 금지
output 파일 수정/삭제 금지
DB/PNG 파일 수정/삭제 금지
git add . 금지
git add -A 금지
```

---

## 검증 명령

문서 작업이므로 테스트는 필수 아님.

```cmd
cd /d D:\python\StockScreener
git status --short
git diff --name-only
```

필요 시 문서 관련 검색만 수행한다.

```cmd
findstr /S /N /I "Manual Reviews Manual Executions Daily Review Summary COMMITTED READY allow-warnings" docs\operations\*.md docs\TRD\*.md
```

---

## 커밋 정책

문서만 커밋한다.

```cmd
git add docs\operations\paper_daily_ops.md
git add docs\operations\paper_notion_ops.md
git diff --cached --name-only
git commit -m "PAPER14-7G: document Notion review operations SOP"
```

`paper_notion_ops.md`를 추가하지 않았다면 stage하지 않는다.  
staged 파일에 문서 외 파일이 있으면 커밋하지 말고 보고한다.

---

## 성공 기준

```text
Review 포함 paper daily operation loop가 문서화된다.
Notion의 위치가 입력 UI / 검토 UI / staging layer로 명확히 정리된다.
source of truth 원칙이 문서화된다.
스마트폰 가능 단계와 로컬 PC 필수 단계가 구분된다.
Manual Executions / Daily Review Summary / Manual Reviews 절차가 모두 SOP에 들어간다.
WARNING / FAIL 처리 정책이 문서화된다.
Notion sync 실패 시 rollback하지 않고 sync만 재실행하는 정책이 문서화된다.
문서만 커밋된다.
```

---

## 결과 보고 형식

5천자 이내.

```text
1. Summary
2. 기준 커밋 확인 결과
3. 변경 파일
4. paper_daily_ops.md 변경 내용
5. paper_notion_ops.md 추가/변경 내용
6. Review 포함 운영 루프 정리 내용
7. 스마트폰 가능 단계 / 로컬 PC 필수 단계
8. WARNING / FAIL 처리 정책
9. Notion sync 실패 대응 정책
10. source of truth 원칙
11. 코드 수정 여부
12. CSV/output 수정 여부
13. 테스트 실행 여부와 결과
14. 커밋 hash와 message
15. stage하지 않은 파일
16. 남은 리스크
17. 다음 MFU 제안
```

반드시 명시:

```text
이번 PAPER14-7G는 Manual Review까지 포함한 paper 운영 SOP 문서 보강 작업이며, Python 코드 수정, Notion actual write/export, Review append commit, paper trading ledger 수정은 수행하지 않았다.
```
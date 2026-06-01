# MFU-PAPER14-5D-1 작업 지시문: paper_current_state 갱신 여부 조사

## 목적

Manual Executions commit 이후 `paper_current_state_YYYYMMDD.json`을 갱신 흐름에 포함해야 하는지 코드 기반으로 조사하고 권고안을 작성한다.

이번 작업은 조사/판단 작업이다.

반드시 명시:

```text
이번 PAPER14-5D-1은 paper_current_state_YYYYMMDD.json 포함 여부를 코드 기반으로 판단하는 조사 작업이며, 실제 구현, paper ledger commit, Notion back-write는 수행하지 않았다.
```

---

## 기준 커밋

기준 커밋:

```text
ffd2350f5933376f4bc2b9fec26901d76f0b797d
```

최근 로그에 아래 커밋들이 있어야 한다.

```text
e63a2f2 PAPER14-5C: add Manual Executions import preview
b921af3 PAPER14-5D: commit Manual Executions preview to paper ledger
```

작업 전 확인:

```cmd
cd /d D:\python\StockScreener
git rev-parse HEAD
git log --oneline -10
git status --short
```

기준 SHA 이후 상태가 아니면 중단하고 보고한다.

---

## 배경

PAPER14-5D에서 Notion Manual Executions preview 결과를 `paper_execution_log.csv`에 commit했다.

5D 결과:

```text
AAPL BUY 1주 @ 100.0 commit 성공
paper_execution_log.csv 갱신
paper_account_snapshot.csv 갱신
paper_position_snapshot.csv 갱신
paper_current_state_YYYYMMDD.json은 미갱신
```

이번 작업은 `paper_current_state_YYYYMMDD.json`도 commit 흐름에 포함해야 하는지 판단하는 것이다.

---

## 조사 대상

반드시 확인:

```text
scripts/import_notion_executions.py
core/paper_manual_execution_commit.py
core/paths.py
scripts/run_paper_eod_update.py
scripts/paper.py
core/paper_account_state.py
core/paper_execution_log.py
core/paper_trade_preview.py
core/paper_commit_guard.py
```

전체 검색:

```cmd
findstr /S /N /I "paper_current_state current_state" *.py *.md
```

---

## 확인할 질문

문서에서 아래에 답한다.

```text
1. paper_current_state_YYYYMMDD.json은 어디서 생성되는가?
2. 어떤 입력 source에서 파생되는가?
3. 어디서 사용되는가?
   - Daily Plan
   - status/review
   - Weekly Report
   - Notion export
   - paper current status
4. 5D commit 후 이 파일이 stale이면 문제가 생기는가?
5. 이미 갱신된 paper_execution_log/account_snapshot/position_snapshot과 어떤 관계인가?
6. commit 직후 갱신해야 하는가, 아니면 별도 refresh 단계가 적절한가?
```

---

## 선택지 비교

아래 선택지를 비교한다.

```text
A. 5D commit 직후 즉시 갱신
B. 5E Notion status back-write 전에 별도 refresh
C. Daily Review Summary export 직전에 갱신
D. 현재는 포함하지 않음
```

판단 기준:

```text
운영 안정성
source of truth 원칙
stale data 위험
구현 영향 범위
테스트 가능성
rollback 가능성
```

---

## 결과 문서

추가 문서:

```text
docs/TRD/mfu_paper14_5d1_paper_current_state_assessment.md
```

포함 내용:

```text
1. 목적
2. 조사 파일
3. 생성 경로
4. 사용처
5. stale 위험
6. snapshot CSV와의 관계
7. 선택지 비교
8. 최종 권고안
9. 반론과 검증
10. 후속 MFU 제안
```

권고안은 아래 중 하나로 명확히 낸다.

```text
권고 A: 5D commit 흐름에 포함
권고 B: 5E 전에 별도 refresh
권고 C: Daily Review Summary export 직전에 재생성
권고 D: 현재는 포함하지 않음
```

---

## 금지 사항

```text
코드 수정 금지
paper_current_state 생성 로직 수정 금지
paper_execution_log.csv 수정 금지
paper_account_snapshot.csv 수정 금지
paper_position_snapshot.csv 수정 금지
Notion write/back-write 금지
Daily Review Summary export 구현 금지
Manual Executions commit 재실행 금지
outputs 파일 생성/수정 금지
git add . 금지
git add -A 금지
```

---

## 검증 명령

```cmd
cd /d D:\python\StockScreener
set PYTHONPATH=.

findstr /S /N /I "paper_current_state current_state" *.py *.md

python -m pytest tests\test_paper_manual_execution_commit.py tests\test_notion_manual_execution_importer.py -q
```

테스트 실패 시 수정하지 말고 보고한다.

---

## 커밋 정책

문서만 커밋한다.

```cmd
git add docs\TRD\mfu_paper14_5d1_paper_current_state_assessment.md
git diff --cached --name-only
git commit -m "PAPER14-5D: assess paper current state refresh policy"
```

필요할 때만 기존 5D 문서에 짧은 참조를 추가한다.

---

## 성공 기준

```text
paper_current_state 생성 경로가 확인된다.
사용처가 확인된다.
Manual Execution commit 이후 stale 위험이 평가된다.
5D/5E/Daily Review 중 어느 단계에 포함할지 권고안이 나온다.
구현 없이 문서만 커밋된다.
```

---

## 결과 보고 형식

5천자 이내.

```text
1. Summary
2. 기준 커밋 확인 결과
3. 변경 파일
4. 조사한 파일
5. paper_current_state 생성 경로
6. paper_current_state 사용처
7. stale 위험 평가
8. snapshot CSV와의 관계
9. 선택지 비교
10. 최종 권고안
11. 반론과 검증 결과
12. 코드 수정 여부
13. output/CSV 수정 여부
14. 테스트 결과
15. 커밋 hash와 message
16. 다음 MFU 제안
```
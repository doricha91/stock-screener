# MFU-PAPER14-7A 작업 지시문: Performance Summary 필요성 평가 및 Notion 잔여 범위 결정

## 목적

PAPER14 Notion review layer에서 별도 `Performance Summary` DB가 필요한지 평가하고, 남은 Notion 작업 범위를 결정한다.

이번 작업은 조사/판단/문서화 작업이다.  
Performance Summary export 구현, Notion DB 생성, Python 코드 수정은 수행하지 않는다.

반드시 명시:

```text
이번 PAPER14-7A는 Performance Summary 필요성 평가 및 Notion 잔여 범위 결정 작업이며, Performance Summary export 구현, Notion DB 생성, Python 코드 수정, Notion actual export는 수행하지 않았다.
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
317e0d8 PAPER14-6: add Daily Review Summary closeout verification
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

현재 PAPER14 Notion layer에는 아래 흐름이 구현되어 있다.

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

현재 Notion 대상 후보/구현 대상:

```text
Daily Plans
Manual Executions
Daily Review Summaries
Account Snapshots
Weekly Reports
Benchmark Reports
```

남은 후보:

```text
Performance Summary
통합 export / 운영 명령 정리
Notion closeout
운영 SOP 문서화
```

이번 작업은 `Performance Summary`가 정말 별도 DB로 필요한지 판단한다.

---

## 조사 대상

반드시 확인한다.

```text
docs/TRD/mfu_paper14_3b_notion_schema_contract.md
docs/TRD/mfu_paper14_4_daily_plan_notion_export.md
docs/TRD/mfu_paper14_5b_manual_executions_schema_contract.md
docs/TRD/mfu_paper14_5d_manual_execution_commit.md
docs/TRD/mfu_paper14_5e_notion_execution_status_sync.md
docs/TRD/mfu_paper14_6_daily_review_summary_notion_export.md
config/notion_property_mapping.example.json
core/notion_exporters.py
core/daily_review_summary_exporter.py
scripts/export_paper_to_notion.py
outputs/paper_test/
outputs/paper_test/reports/
```

필요 시 성과 지표 source 후보도 확인한다.

```text
outputs/paper_test/paper_account_snapshot.csv
outputs/paper_test/paper_position_snapshot.csv
outputs/paper_test/paper_execution_log.csv
outputs/paper_test/reports/*benchmark*
outputs/paper_test/reports/*weekly*
```

---

## 평가 질문

문서에서 아래 질문에 답한다.

### 1. 기존 Notion DB별 역할

아래 DB가 어떤 판단을 담당하는지 정리한다.

```text
Daily Plans
Manual Executions
Daily Review Summaries
Account Snapshots
Weekly Reports
Benchmark Reports
```

### 2. Performance Summary 후보 역할

Performance Summary가 담당할 수 있는 후보 역할을 정의한다.

예:

```text
누적 성과 요약
기간별 수익률
MDD
CAGR
win rate
profit factor
trade count
benchmark 대비 누적 초과수익
월간/분기별 성과 요약
```

### 3. 기존 DB와의 중복 여부

아래 항목이 기존 DB에 이미 있는지 확인한다.

```text
Paper Return
SPY / QQQ / CASH Return
Excess Return
MDD
End Equity
Equity Change %
Trade Count
Cash Ratio
Position Count
Warning / Gap / Coverage Status
```

### 4. Performance Summary만 제공할 수 있는 정보

기존 DB로 충분하지 않은 정보가 있는지 정리한다.

예:

```text
전체 기간 누적 성과
월간/분기별 성과 추세
전략 안정성 지표
운영 기간별 성과 요약
성과 요약 dashboard anchor
```

### 5. 구현 가치와 위험

아래 기준으로 판단한다.

```text
운영 의사결정 가치
기존 DB와의 중복
Notion 복잡도 증가
source artifact 존재 여부
구현 난이도
데이터 신뢰도
현재 paper 데이터량의 충분성
```

---

## 선택지

최종 권고안은 아래 중 하나로 명확히 낸다.

```text
권고 A: Performance Summary DB를 구현한다.
권고 B: 별도 DB는 만들지 않고 Weekly / Benchmark / Account view 개선으로 대체한다.
권고 C: 현재는 보류하고 forward/paper 데이터가 더 쌓인 뒤 재평가한다.
권고 D: Performance Summary는 만들지 않고 Notion closeout/SOP로 넘어간다.
```

각 권고에는 반드시 이유와 반론을 포함한다.

예:

```text
권고: C
이유: 현재 Benchmark Reports와 Weekly Reports가 성과 비교를 이미 제공하고, paper 데이터량이 적어 누적 성과 summary의 판단 가치가 제한적이다.
반론: 장기적으로 누적 성과 dashboard anchor가 필요할 수 있다.
검증: 필요한 metric이 기존 DB에서 이미 확인 가능한지 비교했다.
```

---

## Notion 잔여 범위 결정

Performance Summary 판단과 별개로, 남은 Notion 작업 범위를 제안한다.

후보:

```text
1. Performance Summary export 구현 여부
2. export_paper_to_notion.py --all 포함 여부
3. Notion DB별 view policy 문서화 필요 여부
4. PAPER14 Notion closeout 문서화
5. 운영 SOP 문서화
```

최종 로드맵을 제안한다.

예:

```text
다음 단계 1: Performance Summary 보류
다음 단계 2: Notion 통합 export / --all 정책 정리
다음 단계 3: PAPER14 Notion closeout
다음 단계 4: 운영 SOP 문서화
```

---

## 결과 문서

추가 문서:

```text
docs/TRD/mfu_paper14_7a_performance_summary_assessment.md
```

포함 내용:

```text
1. 목적
2. 현재 Notion DB별 역할
3. Performance Summary 후보 역할
4. 기존 DB와의 중복 항목
5. Performance Summary 고유 가치 후보
6. source artifact 후보
7. 구현 난이도와 리스크
8. 선택지 비교
9. 최종 권고안
10. 반론과 검증
11. Notion 잔여 범위 결정
12. 다음 MFU 제안
```

---

## 금지 사항

```text
Python 코드 수정 금지
config 수정 금지
Notion DB 생성 금지
Notion actual export 실행 금지
Performance Summary export 구현 금지
paper ledger CSV 수정 금지
output 파일 수정/삭제 금지
DB/PNG 파일 수정/삭제 금지
Manual Execution import/commit/status sync 재실행 금지
Daily Review Summary export 재실행 금지
git add . 금지
git add -A 금지
```

---

## 검증 명령

문서 작업이므로 코드 테스트는 필수 아님.

상태와 검색만 확인한다.

```cmd
cd /d D:\python\StockScreener
git status --short
git diff --name-only
findstr /S /N /I "performance_summary performance summaries benchmark weekly return mdd cagr win_rate profit_factor" *.py *.md
```

필요 시 테스트 상태만 확인한다.

```cmd
set PYTHONPATH=.
python -m pytest tests\test_daily_review_summary_exporter.py tests\test_notion_exporters.py tests\test_notion_schema_validator.py -q
```

테스트 실패 시 수정하지 말고 보고한다.

---

## 커밋 정책

문서만 커밋한다.

```cmd
git add docs\TRD\mfu_paper14_7a_performance_summary_assessment.md
git diff --cached --name-only
git commit -m "PAPER14-7A: assess Performance Summary Notion scope"
```

커밋 전 staged 파일에 위 문서 외 파일이 있으면 커밋하지 말고 보고한다.

---

## 성공 기준

```text
Performance Summary 필요성 평가가 완료된다.
기존 Notion DB와의 중복 여부가 정리된다.
Performance Summary 고유 가치가 있는지 판단된다.
구현/보류/대체 중 하나로 명확한 권고안이 나온다.
Notion 잔여 범위와 다음 MFU가 제안된다.
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
5. 현재 Notion DB별 역할 정리
6. Performance Summary 후보 역할
7. 기존 DB와의 중복 평가
8. 고유 가치 평가
9. source artifact 후보
10. 선택지 비교
11. 최종 권고안
12. 반론과 검증
13. Notion 잔여 범위 결정
14. 코드 수정 여부
15. output/CSV 수정 여부
16. 테스트 실행 여부와 결과
17. 커밋 hash와 message
18. 다음 MFU 제안
```

반드시 명시:

```text
이번 PAPER14-7A는 Performance Summary 필요성 평가 및 Notion 잔여 범위 결정 작업이며, Performance Summary export 구현, Notion DB 생성, Python 코드 수정, Notion actual export는 수행하지 않았다.
```
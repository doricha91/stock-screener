# MFU-PAPER14-0: Notion Integration Direction

## 목적

PAPER14의 목적은 paper trading 시스템에서 생성되는 주요 정보를 Notion에서 쉽게 읽고, 이후 수동 리뷰를 편하게 작성할 수 있도록 연동 방향을 정리하는 것이다.

이번 PAPER14-0은 구현이 아니라 방향 정리 문서화 단계다.

```text
이번 PAPER14-0은 Notion 연동 방향 문서화이며, Notion API 구현, DB 생성, 데이터 동기화, review 입력 연동은 포함하지 않는다.
```

---

## Notion 사용 목적

Notion은 계산 엔진이나 원천 데이터 저장소가 아니다.

Notion의 목적은 다음이다.

```text
1. 시스템이 생성한 정보를 사람이 쉽게 읽는 공간
2. 주간/일간 운영 기록을 보관하는 공간
3. 수동 리뷰와 판단 메모를 작성하는 공간
4. 나중에 review 입력 UI로 확장할 수 있는 운영 콘솔
```

계산, 성과 산출, benchmark 비교, snapshot 생성은 기존 Python/CSV/JSON 시스템이 담당한다.

---

## 연동 기본 원칙

초기에는 단방향 export로 시작한다.

```text
Python / JSON / Markdown
→ Notion
```

초기에는 Notion에서 작성한 내용을 다시 시스템으로 가져오는 양방향 연동은 하지 않는다.

이유:

```text
- 단방향 export가 구현과 검증이 더 단순함
- 중복 sync, 수정 충돌, validation 문제가 적음
- 기존 paper 원장 CSV를 안전하게 유지할 수 있음
```

양방향 입력 연동은 추후 단계에서 별도로 진행한다.

---

## 1차 연동: 읽기 전용 Export

초기 Notion 연동 대상은 사람이 읽어야 하는 정보 중심으로 한다.

우선순위는 다음과 같다.

### 1. Weekly Status Summary

Source:

```text
outputs/paper_test/reports/paper_weekly_status_summary.json
outputs/paper_test/reports/paper_weekly_status_summary.md
```

목적:

```text
주간 운영 상태, 계좌 변화, position 변화, operation gap 확인
```

Notion 형태:

```text
Weekly Report DB + 상세 page body
```

---

### 2. Benchmark Comparison

Source:

```text
outputs/paper_test/reports/paper_benchmark_comparison.json
outputs/paper_test/reports/paper_benchmark_comparison.md
```

목적:

```text
Paper 성과를 SPY / QQQ / CASH와 비교
```

Notion 형태:

```text
Benchmark Report DB + 상세 page body
```

---

### 3. Daily Action Plan

Source:

```text
outputs/paper_test/daily_action_plan_YYYYMMDD.md
```

목적:

```text
그날의 시장 국면, 매매 판단, review-only 종목, warning, 후보 필터 진단 보관
```

Notion 형태:

```text
Daily Plan DB + page body
```

---

### 4. Daily Account Snapshot

Source:

```text
outputs/paper_test/paper_account_snapshot.csv
```

목적:

```text
일별 cash, equity, unrealized PnL, cash ratio, position count 확인
```

Notion 형태:

```text
Daily Account Snapshot DB
```

---

### 5. Daily Review Summary

Source:

```text
outputs/paper_test/reports/paper_daily_review_summary.md
```

목적:

```text
일일 복기 요약 확인
```

Notion 형태:

```text
Daily Review Summary page 또는 DB
```

---

### 6. Paper Performance Summary

Source:

```text
outputs/paper_test/reports/paper_performance_summary.md
```

목적:

```text
현재 누적 성과 요약 확인
```

Notion 형태:

```text
Performance Summary page
```

주의:

```text
reports 계열은 latest overwrite 구조이므로 historical source로 직접 사용하지 않는다.
필요 시 export 시점에 Notion page로 archive한다.
```

---

## 2차 연동: Review 입력

단방향 export가 안정화된 뒤, Notion을 수동 리뷰 입력 UI로 확장한다.

대상:

```text
outputs/paper_test/reviews/paper_manual_review_log_template.csv
outputs/paper_test/reviews/paper_manual_review_log.csv
```

목표:

```text
CSV 직접 작성 대신 Notion에서 review 작성
Notion 입력값을 다시 validator / append workflow와 연결
```

주의:

```text
이 단계부터는 양방향 sync가 필요하다.
중복 처리, 수정 반영, validation, append 정책을 별도 MFU에서 설계한다.
```

---

## 장기 구조

권장 구조:

```text
Python system
= 계산, 판단, 리포트 생성

CSV / JSON / SQLite
= 원천 데이터와 구조화 데이터

Markdown
= 사람이 읽는 로컬 리포트

Notion
= 운영 기록, 리포트 보관, 수동 리뷰 입력 UI
```

Notion은 원천 데이터베이스가 아니라 presentation / review layer로 사용한다.

---

## PAPER14 예상 단계

```text
PAPER14-1:
Notion DB schema 조사 및 설계

PAPER14-2:
Weekly Status Summary 단방향 export

PAPER14-3:
Benchmark Comparison 단방향 export

PAPER14-4:
Daily Action Plan / Account Snapshot export

PAPER14-5:
Daily Review / Performance Summary export

PAPER14-6:
Review Template / Manual Review Log 입력 연동 설계

PAPER14-7:
Notion Review 입력값 import / validate / append workflow 구현
```

---

## 제외 범위

PAPER14-0에서는 아래를 하지 않는다.

```text
Notion API 호출
Notion DB 생성
token 설정
데이터 export 구현
review import 구현
paper 원장 CSV 수정
reports 재생성
```

---

## 결론

Notion 연동은 처음부터 모든 기능을 양방향으로 만들지 않는다.

1차는 읽기 전용 export로 시작한다.

```text
weekly status
benchmark
daily action plan
account snapshot
daily review summary
performance summary
```

2차에서 review 입력 연동을 진행한다.

이 방향이 paper 원장 안전성과 운영 편의성을 동시에 확보하는 가장 현실적인 접근이다.
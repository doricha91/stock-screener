# MFU-OPER9-16 Date-Scoped Review Artifact Guard

## 개요
Daily Ops Orchestrator가 날짜 없는 고정 파일명의 review artifact를 현재 trade_date의 완료 근거로 오판하여 단계를 건너뛰는 문제를 해결한다.

## 문제 상황
- 2026-06-09 사이클에서 Daily Plan 생성 직후, Orchestrator가 `DAILY_PLAN_NOTION_EXPORT` 대신 `MANUAL_REVIEW_TEMPLATE`을 추천함.
- 원인: 이전 2026-06-08의 review artifact들이 고정 파일명(`paper_daily_review_summary.md`, `paper_manual_review_log_template.csv` 등)으로 남아 있었고, Orchestrator는 파일 존재 여부만 체크하여 2026-06-09의 `DAILY_REVIEW`가 완료된 것으로 오판함.

## 해결 방법
Orchestrator의 `DAILY_REVIEW` 및 `MANUAL_REVIEW_TEMPLATE` 단계 판정 시, artifact 내부의 날짜 정보를 읽어 현재 `trade_date`와 일치하는지 검증하는 date-scoped guard를 추가한다.

### 구현 세부사항
1. **Helper Functions 추가**
   - `_get_csv_dates(path, column)`: CSV 파일에서 특정 컬럼의 모든 날짜를 추출.
   - `_get_markdown_date(path, labels)`: Markdown 파일에서 특정 라벨(예: "Latest snapshot date") 뒤의 날짜를 추출.

2. **DAILY_REVIEW Stage 보강**
   - `paper_manual_review_log_template.csv`의 모든 `review_date`가 `trade_date`와 일치해야 함.
   - `paper_daily_review_summary.md`의 `Latest snapshot date`가 `trade_date`와 일치해야 함.
   - `paper_performance_summary.md`의 `Latest Snapshot Date` 등이 `trade_date`와 일치해야 함 (불일치 시 warning).
   - 위 조건 미충족 시 `DAILY_REVIEW`는 `DONE`이 아닌 `READY`(재생성 필요) 상태가 됨.

3. **MANUAL_REVIEW_TEMPLATE Stage 보강**
   - `paper_manual_review_log_template.csv`의 날짜가 현재 `trade_date`와 맞지 않으면 `BLOCKED` 처리하고 stale date를 명시함.

## 검증 결과
- `tests/test_paper_daily_ops_orchestrator_guard.py`를 통해 stale artifact 상황에서 `DAILY_REVIEW`가 `DONE`이 되지 않고 `DAILY_PLAN_NOTION_EXPORT`가 정상적으로 추천됨을 확인.
- 기존 72개의 Orchestrator 테스트 케이스 통과 확인.
- Mixed dates 상황에 대한 방어 로직 확인.

## 관련 파일
- `core/paper_daily_ops_orchestrator.py`
- `tests/test_paper_daily_ops_orchestrator_guard.py`
- `tests/test_paper_daily_ops_orchestrator.py` (테스트 헬퍼 업데이트)

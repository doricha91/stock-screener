# Paper 운영 기능 개발 로드맵 v1.0

## 0. 로드맵 목적

이 로드맵은 stock-screener 프로젝트의 Paper 운영 기능 개발 우선순위를 고정하기 위한 기준 문서다.

현재 목표는 전략을 무리하게 확장하는 것이 아니라, Paper 운영을 매일 안정적으로 반복할 수 있는 구조를 먼저 만드는 것이다.

핵심 원칙은 다음과 같다.

- Notion은 입력 UI / 검토 UI / staging layer로만 사용한다.
- CSV / JSON / Markdown / SQLite를 source-of-truth로 유지한다.
- Python이 validation / preview / commit / append / export의 주체다.
- 신규 기능은 운영 안정성, 상태 가시성, 재현성 확보 이후에 확장한다.

---

## 1. 최종 개발 우선순위

### 0순위. 다중계좌 구축 환경 점검

목적:
- 현재 단일계좌 전제 구조가 얼마나 코드와 artifact 경로에 박혀 있는지 점검한다.
- 바로 다중계좌를 구현하지 않고, account/profile 기반 확장 가능성을 먼저 조사한다.

주요 확인 항목:
- outputs/paper_test 단일 경로 의존성
- paper_execution_log.csv, paper_account_snapshot.csv, paper_position_snapshot.csv의 계좌 분리 가능성
- paper_current_state_YYYYMMDD.json의 계좌별 분리 필요성
- Notion DB에 account/profile 필드가 필요한지 여부
- 기존 단일계좌 운영을 깨지 않는 migration 방향

산출물:
- 다중계좌 영향 분석 문서
- 계좌별 artifact 분리 설계안
- 후속 구현 범위 제안

판단 기준:
- 기존 단일계좌 운영을 유지하면서 계좌별 output/state/log 분리가 가능한가?

---

### 1순위. Daily Ops Status Dashboard

목적:
- 오늘 Paper 운영이 어디까지 완료되었는지 한눈에 확인한다.
- 운영자가 다음에 실행해야 할 명령을 즉시 알 수 있게 한다.

주요 기능:
- Daily Plan 생성 여부 확인
- Daily Plan Notion export 여부 확인
- Manual Execution preview / commit / status sync 여부 확인
- account snapshot / position snapshot / current_state 갱신 여부 확인
- Daily Review Summary export 여부 확인
- Manual Review preview / append / status sync 여부 확인
- 오늘 운영 완료 여부 판정
- next recommended command 출력

산출물:
- paper.py status 고도화
- daily ops completion report
- JSON / Markdown 상태 리포트

판단 기준:
- 운영자가 “오늘 무엇이 남았는지”와 “다음에 무엇을 실행해야 하는지” 바로 알 수 있는가?

---

### 1.5순위. Export / Sync 정책 정리

목적:
- Notion export와 status sync의 의미를 명확히 통일한다.
- Dashboard가 export/sync 완료 여부를 정확히 판정할 수 있게 한다.

주요 기능:
- daily export와 weekly/export-all 정책 분리
- dry-run / actual write 기준 정리
- status sync 성공/실패/부분성공 상태 정의
- 같은 commit report로 status sync 재실행하는 정책 정리
- export_paper_to_notion.py --all 범위 재정의

산출물:
- export/sync 정책 문서
- CLI 옵션 정리
- dashboard 판정 기준 반영

판단 기준:
- export/sync 상태가 애매하지 않고, 재시도 정책이 명확한가?

---

### 2순위. Alert / Monitoring Report

목적:
- WARNING / FAIL / Notion sync 실패 / 운영 누락을 놓치지 않게 한다.

주요 기능:
- data freshness stale 감지
- preflight FAIL 감지
- preview WARNING / FAIL 감지
- same-date commit guard 차단 감지
- Notion status sync 실패 감지
- daily loop incomplete 감지
- blocking issue와 non-blocking issue 구분

Alert 등급:
- BLOCKING: 운영 중단 필요
- NEEDS_REVIEW: 수동 판단 필요
- SYNC_FAILED: source-of-truth는 성공했지만 Notion sync 실패
- INFO: 참고용 정보

산출물:
- alert markdown report
- alert JSON report
- daily incomplete report

판단 기준:
- 운영을 멈춰야 하는 문제를 자동으로 드러내는가?

---

### 2.5순위. Replay / Same-date Diff 최소 하네스

목적:
- 같은 날짜의 Daily Plan을 다시 생성했을 때 결과 차이를 감지한다.
- 유니버스 확장이나 전략 확장 전 재현성 위험을 줄인다.

주요 기능:
- 기존 daily_action_plan과 재생성 plan 비교
- config snapshot 비교
- universe snapshot 비교
- action / symbol / quantity / price / warning 차이 요약
- 차이가 발생한 원인 후보 표시

산출물:
- regenerated daily plan
- daily plan diff report
- config snapshot diff
- universe snapshot diff

판단 기준:
- 같은 날짜 plan 재생성 결과가 같거나, 차이가 발생해도 원인을 설명할 수 있는가?

---

### 3순위. Notion UI 개선

목적:
- Notion을 예쁘게 꾸미는 것이 아니라, 모바일 입력과 검토 오류를 줄인다.

주요 개선 방향:
- 오늘 입력해야 할 Manual Executions만 보이는 view
- 오늘 입력해야 할 Manual Reviews만 보이는 view
- READY / COMMITTED / SYNCED 상태 가독성 개선
- WARNING row 필터 view
- 입력 필드 최소화
- 사용자가 수정하면 안 되는 필드 숨김 또는 하단 배치

산출물:
- Notion view 개선안
- Manual Execution 입력 UI 개선안
- Manual Review 입력 UI 개선안
- 모바일 운영 cheat sheet 업데이트

판단 기준:
- 스마트폰에서 입력 실수와 확인 누락이 줄어드는가?

---

### 3.5순위. Notion Schema Drift Check

목적:
- Notion UI 변경 후 Python import/export/status sync가 깨지는 것을 방지한다.

주요 기능:
- 필수 property 존재 여부 확인
- select option 존재 여부 확인
- mapping 파일과 실제 Notion DB 차이 확인
- status sync가 수정해도 되는 필드만 수정하는지 확인
- 누락/불일치 발생 시 commit/export 차단 또는 경고

산출물:
- schema validation report
- missing property report
- select option mismatch report
- mapping drift report

판단 기준:
- Notion UI를 바꿔도 Python 연동이 안전하게 유지되는가?

---

### 4순위. Universe 변경 Preview → Universe 확장

목적:
- 유니버스를 바로 확장하지 않고, 변경 영향을 먼저 확인한다.

1단계:
- universe added / removed / kept report
- 현재 보유 종목 중 removed 여부 확인
- universe 변경이 Daily Plan에 미치는 영향 확인

2단계:
- S&P500 / NASDAQ100 외 universe 확장 검토
- 미국 전체 중 시총 / 거래대금 필터
- 한국 전체 중 시총 / 영업이익 / 거래대금 필터
- custom universe snapshot 지원

산출물:
- universe change preview report
- holding impact report
- custom universe 설계안
- universe snapshot 정책 문서

판단 기준:
- 유니버스 변경이 포지션, 후보군, Daily Plan에 미치는 영향이 설명 가능한가?

---

### 5순위. 전략 확장

목적:
- 운영 안정성, 상태 가시성, 재현성, 유니버스 관리가 확보된 이후 신규 전략을 확장한다.

주요 기능:
- 신규 전략 후보 정의
- 전략별 signal / score / weight 분리
- 기존 전략 대비 성과 비교
- backtest-paper parity 검증
- 전략 변경 시 Daily Plan diff 확인

산출물:
- strategy extension 설계안
- strategy comparison report
- backtest-paper parity report
- 전략별 regression test

판단 기준:
- 신규 전략이 기존 전략과 비교 가능한 방식으로 검증되는가?

---

## 2. 보류 항목

아래 항목은 현재 로드맵 후순위로 둔다.

### Cloud / 원격 실행

보류 이유:
- status dashboard, alert, replay가 먼저 안정화되어야 한다.
- 처음부터 cloud commit/append를 허용하면 source-of-truth 손상 위험이 있다.

재검토 조건:
- dry-run 전용 GitHub Actions 또는 cloud runner부터 검토한다.

### 스마트폰 단독 commit / append

보류 이유:
- 현재 원칙상 source-of-truth 변경은 로컬 PC에서 Python으로 수행한다.
- 모바일 단독 commit은 운영 사고 위험이 크다.

재검토 조건:
- alert, schema check, replay, audit log가 충분히 갖춰진 뒤 검토한다.

### Performance Summary Notion DB

보류 이유:
- Weekly Reports, Benchmark Reports, Account Snapshots, Daily Review Summaries와 중복 가능성이 크다.
- paper 데이터가 충분히 쌓인 뒤 판단하는 것이 적절하다.

재검토 조건:
- 최소 수 주 이상의 paper 운영 데이터가 누적된 뒤 재평가한다.

### Broker / API 연동

보류 이유:
- Paper 운영 안정화 전에는 live 연동이 이르다.
- 주문 API는 실수 비용이 크다.

재검토 조건:
- Paper 운영 누락, 상태 불명확, 재현성 문제가 충분히 해결된 뒤 검토한다.

---

## 3. 개발 진행 원칙

- 한 번에 큰 기능을 만들지 않는다.
- MFU 단위로 쪼개서 구현한다.
- 각 MFU는 문서, 코드, 테스트, 운영 명령, 성공 기준을 포함한다.
- source-of-truth artifact를 수정하는 기능은 반드시 preview 단계를 둔다.
- FAIL은 commit/append 금지다.
- WARNING은 기본 차단이며, 명시적 허용이 있을 때만 진행한다.
- Notion sync 실패는 source-of-truth rollback 사유가 아니다.
- Notion sync 실패 시 같은 commit report로 status sync만 재실행한다.

---

## 4. 최종 로드맵 요약

0. 다중계좌 구축 환경 점검
1. Daily Ops Status Dashboard
1.5. Export / Sync 정책 정리
2. Alert / Monitoring Report
2.5. Replay / Same-date Diff 최소 하네스
3. Notion UI 개선
3.5. Notion Schema Drift Check
4. Universe 변경 Preview → Universe 확장
5. 전략 확장

---

## 5. 핵심 결론

현재 stock-screener Paper 운영의 병목은 전략 부족이 아니라 운영 신뢰도다.

따라서 앞으로의 기능 개발은 다음 순서를 따른다.

1. 계좌/상태/artifact 구조를 먼저 안정화한다.
2. 오늘 운영이 끝났는지 명확히 보이게 한다.
3. 위험 신호를 놓치지 않게 한다.
4. 같은 날짜 결과를 재현 가능하게 만든다.
5. Notion 입력 오류를 줄인다.
6. 그 다음 유니버스와 전략을 확장한다.
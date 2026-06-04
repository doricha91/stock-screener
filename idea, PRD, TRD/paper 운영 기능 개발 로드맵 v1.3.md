# Paper 운영 기능 개발 로드맵 v1.3

## 1. Purpose

이번 ROADMAP-V1.3 작업은 Daily Ops Orchestrator / 운영 루프 통합을 다음 우선순위로 공식화하기 위한 로드맵 문서 작업이며, 코드 구현, DB write, paper 원장 수정, Notion write/export/sync, 신규 CLI 구현은 포함하지 않는다.

이 문서는 `stock-screener` 프로젝트의 Paper 운영 기능 개발 순서를 v1.3 기준으로 정합화한다. v1.2에서는 PAPER20 이후 다음 작업이 Stable Plan Row Identity / Non-empty Replay Smoke Expansion으로 정리되어 있었지만, 현재 목표는 개장일마다 반자동 운영 루프를 안정적으로 반복하는 것이다.

따라서 v1.3에서는 Daily Ops Orchestrator / 운영 루프 통합을 다음 우선순위로 두고, 기존 후속 과제의 순서를 재정렬한다.

기준 SHA:

```text
0c702e2547a1660bf95d0fbb71a89d07efa9cc3e
```

## 2. Core Principles

- Notion은 입력 UI / 검토 UI / staging layer다.
- CSV / JSON / Markdown / SQLite가 source-of-truth다.
- Python이 validation / preview / commit / append / export / report generation의 주체다.
- FAIL은 commit/append 금지다.
- WARNING은 기본 차단이며, 명시적 허용이 있을 때만 진행한다.
- Notion sync 실패는 source-of-truth rollback 사유가 아니다.
- generated smoke artifact는 source-of-truth가 아니며 기본적으로 commit하지 않는다.
- 실제 원장 변경, Notion actual write/export/sync, 외부 전송은 명시 승인과 안전장치가 있어야 한다.

## 3. v1.3 Update Summary

v1.2의 완료 흐름은 유지한다.

- PAPER16: Daily Ops Status Dashboard 완료
- PAPER17: Export / Sync Policy Hardening 완료
- PAPER18: Alert / Monitoring Report 완료
- PAPER19: Replay / Same-date Diff 완료
- PAPER20: Replay Wrapper Operational Smoke / Runbook 완료

v1.3의 핵심 변경은 다음과 같다.

- Daily Ops Orchestrator / 운영 루프 통합을 다음 작업으로 둔다.
- Stable Plan Row Identity / Non-empty Replay Smoke Expansion은 후속 중요 과제로 이동한다.
- Notion UI 개선은 Orchestrator 이후 진행한다.
- Notion UI 개선 후에는 Schema/View Drift Check가 거의 반드시 뒤따라야 한다.
- 새 작업에 PAPER21 번호를 강제로 붙이지 않는다. 필요하면 신규 우선순위 또는 Orchestrator 단계로 표현한다.

## 4. Current Completed PAPER Flow

현재 Paper 운영 기능은 다음 기반까지 구축된 상태다.

| Flow | Status | Notes |
|---|---|---|
| PAPER16 - Daily Ops Status Dashboard | 완료 | Daily Ops Status, command map, rerun policy, Notion view 수동 정리 |
| PAPER17 - Export / Sync Policy Hardening | 완료 | dry-run / actual / confirm guard, duplicate audit, actual preflight, rollback 금지 원칙 |
| PAPER18 - Alert / Monitoring Report | 완료 | Paper Ops Exception Report, source-root 연결, freshness / same-date guard source 연결 |
| PAPER19 - Replay / Same-date Diff | 완료 | Daily Plan JSON sidecar, config hash, replay diff wrapper 최소 체인 |
| PAPER20 - Replay Wrapper Operational Smoke / Runbook | 완료 | controlled baseline capture, replay smoke, `PASS_WITH_METADATA_DIFF`, runbook 정리 |

PAPER20 이후에도 stable plan row identity, non-empty action row replay, schema/view drift automation, universe hash, market data as-of, indicator/state snapshot hash 등은 후속 과제로 남아 있다.

## 5. Updated Roadmap Table

| Priority | Work | v1.3 Status | Notes |
|---:|---|---|---|
| 0 | 다중계좌 구축 환경 점검 | 부분 반영 / 후속 필요 | account-aware 경로와 운영 산출물은 일부 반영됨 |
| 1 | Daily Ops Status Dashboard | 완료 | PAPER16 |
| 1.5 | Export / Sync 정책 정리 | 완료 | PAPER17 |
| 2 | Alert / Monitoring Report | 완료 | PAPER18 |
| 2.5 | Replay / Same-date Diff 최소 체인 | 완료 | PAPER19 |
| 2.6 | Replay Wrapper Operational Smoke / Runbook | 완료 | PAPER20 |
| 2.7 | Daily Ops Orchestrator / 운영 루프 통합 | 다음 작업 | 신규 우선순위 / Orchestrator 단계 |
| 2.8 | Stable Plan Row Identity / Non-empty Replay Smoke Expansion | 후속 중요 과제 | action row replay 신뢰성 확장 |
| 3 | Notion UI 개선 | Orchestrator 이후 | 입력/검토 오류를 줄이는 UI 정리 |
| 3.5 | Notion Schema/View Drift Check | Notion UI 이후 필요 | UI 변경 후 Python 연동 파손 방지 |
| 4 | Universe 변경 Preview -> Universe 확장 | 후속 | universe 변경 영향 preview 후 확장 |
| 5 | 전략 확장 | 후속 | 운영 루프 안정화 이후 검토 |

## 6. Next Work: Daily Ops Orchestrator / 운영 루프 통합

### 목적

Daily Ops Orchestrator의 목적은 개장일마다 사람이 여러 명령을 기억해서 실행하는 구조를 줄이는 것이다.

prepare / preflight / plan / export / manual execution / commit / review / alert / replay check / closeout 단계를 하나의 운영 흐름으로 정리한다. 오늘 무엇을 했고, 무엇이 남았고, 어떤 단계가 BLOCKING/WARNING/PASS인지 한눈에 확인하게 한다.

### 초기 성격

초기 Orchestrator는 다음에 가깝다.

```text
stage status aggregator
next action recommender
ops checklist compiler
command map 정합화 계층
gate policy 해석 계층
```

초기 Orchestrator는 다음이 아니다.

```text
자동 실행기
Notion actual write/export/sync 실행기
source-of-truth commit/append 자동화 도구
외부 전송 도구
Broker/API 연동 도구
```

### Stage 후보

초기 stage 후보는 다음과 같다.

```text
prepare / preflight
daily plan generation
daily plan JSON sidecar check
Notion daily plan export readiness
Manual Execution input readiness
Manual Execution preview
Manual Execution commit eligibility
Manual Execution status sync readiness
Daily Review Summary readiness
Manual Review input readiness
Manual Review append eligibility
Manual Review status sync readiness
Alert Report check
Replay / same-date diff check
Daily Ops closeout
```

### 첫 MFU 범위

첫 MFU는 설계 문서로 제한한다.

포함 범위:

```text
기존 CLI / report / source artifact inventory
stage 목록 정의
stage별 input/output artifact 정의
stage별 PASS/WARNING/BLOCKING/NOT_STARTED 판정 후보
stage별 next action recommendation 후보
actual/commit/export/sync 자동 실행 금지 정책
Orchestrator가 참조해야 할 기존 runbook / SOP 목록
후속 구현 MFU 분해
```

제외 범위:

```text
신규 자동 실행기 구현
Notion API 호출
Notion actual write/export/sync
Manual Execution commit
Manual Review append
source-of-truth 원장 변경
외부 전송
```

## 7. Deferred Important Work: Stable Plan Row Identity / Non-empty Replay Smoke Expansion

Stable Plan Row Identity / Non-empty Replay Smoke Expansion은 중요하지만 v1.3 기준 다음 작업은 아니다.

후속 중요 과제로 유지하는 이유는 다음과 같다.

- PAPER20 controlled smoke는 성공했지만 `items_count=0` 기반이었으므로 action row 재현성 검증은 제한적이다.
- 실제 action row가 있는 Daily Plan에서 symbol/action/quantity/price diff를 더 안정적으로 해석하려면 stable row identity가 필요하다.
- duplicate row key, row order 변화, 동일 symbol/action 중복에 대한 정책이 필요하다.
- non-empty replay smoke는 Daily Ops Orchestrator가 운영 흐름을 정리한 뒤 더 자연스럽게 배치할 수 있다.

이 과제는 source-of-truth 원장 변경, Notion actual write/export/sync, Manual Execution commit, Manual Review append 없이 설계와 read-only replay 검증부터 진행해야 한다.

## 8. Next After Orchestrator: Notion UI 개선

Notion UI 개선은 Orchestrator 이후에 진행한다.

목적은 Notion을 꾸미는 것이 아니라, 모바일 입력과 검토 오류를 줄이는 것이다. Orchestrator가 stage와 next action을 먼저 정의하면, Notion view는 그 stage 흐름을 보조하는 입력 UI / 검토 UI / staging layer로 정리할 수 있다.

주요 후보:

- 오늘 입력해야 할 Manual Executions view
- 오늘 입력해야 할 Manual Reviews view
- READY / COMMITTED / SYNCED 상태 가시성 개선
- WARNING row 필터 view
- 입력 필드 최소화
- 사용자가 수정하면 안 되는 필드 숨김 또는 하단 배치
- PAPER16에서 보류된 filter hardening 재검토

## 9. Required Follow-up After Notion UI: Schema/View Drift Check

Notion UI 개선 후에는 Schema/View Drift Check가 거의 반드시 뒤따라야 한다.

이유는 Notion view, filter, select option, 표시 필드가 바뀌면 Python import/export/status sync와 운영 판단이 깨질 수 있기 때문이다.

점검 후보:

- 필수 property 존재 여부 확인
- select option 존재 여부 확인
- mapping 파일과 실제 Notion DB 차이 확인
- status sync가 허용 필드만 수정하는지 확인
- view/filter/sort/표시 필드 drift 점검
- Notion UI 변경 후 Python 연동과 운영 판단이 안전하게 유지되는지 확인

## 10. Later Roadmap: Universe Preview / Strategy Expansion

Universe Preview / Universe 확장은 Notion UI와 Schema/View Drift Check 이후 후속 과제로 둔다.

Universe 변경은 바로 확장하지 않고 preview를 먼저 둔다.

- universe added / removed / kept report
- 현재 보유 종목 중 removed 여부 확인
- universe 변경이 Daily Plan에 미치는 영향 확인
- universe snapshot 정책 검토
- PAPER19~20의 `universe_hash` 후보와 연결

전략 확장은 운영 루프 안정화 이후 후속으로 둔다.

- 신규 전략 후보 정의
- 전략별 signal / score / weight 분리
- 기존 전략 대비 성과 비교
- backtest-paper parity 검증
- 전략 변경 시 Daily Plan diff 확인
- PAPER19~20 replay diff를 전략 변경 검증에 활용

## 11. Hold Items

다음 항목은 현재 로드맵 후순위로 유지한다.

- Cloud / 원격 실행
- 스마트폰 단독 commit / append
- Performance Summary Notion DB
- Broker / API 연동
- Telegram / Slack / Email external delivery

보류 이유는 source-of-truth 변경과 외부 전송 또는 live/broker 위험이 운영 루프 안정화보다 앞서면 복구와 감사가 어려워지기 때문이다.

## 12. Development Principles

- 한 번에 한 MFU만 진행한다.
- 각 MFU는 문서, 코드, 테스트, 운영 명령, 성공 기준을 포함한다.
- source-of-truth artifact를 수정하는 기능은 반드시 preview 단계를 둔다.
- FAIL은 commit/append 금지다.
- WARNING은 기본 차단이며, 명시적 허용이 있을 때만 진행한다.
- Notion sync 실패는 source-of-truth rollback 사유가 아니다.
- Notion sync 실패 시 같은 commit report로 status sync만 재시도한다.
- Replay / diff 계열 기능은 원인 단정이 아니라 원인 후보를 제시한다.
- 실제 운영 smoke 전에 `--output-dir`을 명시해 공식 계좌 artifact 오염을 피한다.
- generated smoke artifact는 기본적으로 commit하지 않는다.
- 기존 Markdown / CSV / SQLite source-of-truth 의미를 바꾸는 변경은 별도 명시 검토로 진행한다.
- `producer_source`는 생성 도구 출처 metadata이며 hash 제외 대상이다.
- `strategy_source`, `universe_source`, `market_data_source`는 의미 있는 입력 조건일 수 있으므로 hash-significant 후보로 취급한다.
- 실제 원장 변경, Notion actual write/export/sync, 외부 전송은 명시 승인과 안전장치가 있어야 한다.

## 13. Final Roadmap Summary v1.3

```text
0. 다중계좌 구축 환경 점검 - 부분 반영 / 후속 필요
1. Daily Ops Status Dashboard - 완료
1.5. Export / Sync 정책 정리 - 완료
2. Alert / Monitoring Report - 완료
2.5. Replay / Same-date Diff 최소 체인 - 완료
2.6. Replay Wrapper Operational Smoke / Runbook - 완료
2.7. Daily Ops Orchestrator / 운영 루프 통합 - 다음 작업
2.8. Stable Plan Row Identity / Non-empty Replay Smoke Expansion - 후속 중요 과제
3. Notion UI 개선 - Orchestrator 이후
3.5. Notion Schema/View Drift Check - Notion UI 이후 필요
4. Universe 변경 Preview -> Universe 확장 - 후속
5. 전략 확장 - 후속
```

## 14. Key Conclusion

현재 Paper 운영의 병목은 신규 전략 부족이 아니라 개장일마다 반복 가능한 운영 루프의 안정성이다.

v1.3 기준으로 다음 작업은 Stable Plan Row Identity가 아니라 Daily Ops Orchestrator / 운영 루프 통합이다. Orchestrator는 자동 실행기가 아니라 stage status aggregator / next action recommender / ops checklist compiler / command map 정합화 계층 / gate policy 해석 계층으로 시작한다.

Stable Plan Row Identity / Non-empty Replay Smoke Expansion은 후속 중요 과제로 유지한다. Notion UI 개선은 Orchestrator 이후 진행하고, Notion UI 개선 후에는 Schema/View Drift Check를 이어서 진행한다.

이번 ROADMAP-V1.3 작업은 Daily Ops Orchestrator / 운영 루프 통합을 다음 우선순위로 공식화하기 위한 로드맵 문서 작업이며, 코드 구현, DB write, paper 원장 수정, Notion write/export/sync, 신규 CLI 구현은 포함하지 않는다.

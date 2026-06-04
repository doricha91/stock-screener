# Paper 운영 기능 개발 로드맵 v1.2

## 0. 로드맵 목적

이 로드맵은 `stock-screener` 프로젝트의 Paper 운영 기능 개발 우선순위를 고정하기 위한 기준 문서다.

현재 목표는 전략을 무리하게 확장하는 것이 아니라, Paper 운영을 매일 안정적으로 반복할 수 있는 구조를 먼저 만드는 것이다.

핵심 원칙은 다음과 같다.

- Notion은 입력 UI / 검토 UI / staging layer로만 사용한다.
- CSV / JSON / Markdown / SQLite를 source-of-truth로 유지한다.
- Python이 validation / preview / commit / append / export / report generation의 주체다.
- 신규 기능은 운영 안정성, 상태 가시성, 위험 감지, 재현성 확보 이후에 확장한다.
- 실제 원장 변경, Notion actual write/export/sync, 외부 전송은 항상 명시 승인과 안전장치를 전제로 한다.
- Replay / diff 계열 기능은 원인 단정이 아니라 차이와 원인 후보를 표시한다.
- generated smoke artifact는 source-of-truth가 아니며 기본적으로 commit하지 않는다.

---

## 0.1. v1.2 업데이트 요약

v1.1 이후 완료된 주요 작업은 다음과 같다.

- PAPER20: Replay Wrapper Operational Smoke / Runbook closeout 완료
- dev-only Daily Plan controlled baseline capture CLI 추가
- `paper_sandbox / 2026-05-26` controlled baseline capture + replay wrapper smoke 실행
- config_hash false WARNING 원인 분석 완료
- `source` → `producer_source` 명확화 및 hash normalization 보강
- 최종 replay smoke 결과 `PASS_WITH_METADATA_DIFF` 확인
- `docs/operations/paper_replay_diff_runbook.md` 운영 runbook 정리

v1.2의 핵심 변경점은 다음과 같다.

- v1.1의 “다음 작업”이던 PAPER20을 완료 상태로 갱신한다.
- Replay / Same-date Diff는 “구현 완료”에서 “controlled smoke + runbook까지 완료”로 격상한다.
- PAPER21을 다음 작업으로 신설한다.
- PAPER21의 목적은 Stable Plan Row Identity / Non-empty Replay Smoke Expansion이다.
- Notion UI 개선, Schema/View Drift Check, Universe 변경 Preview, 전략 확장은 후속으로 유지한다.

---

## 1. 현재 완료 상태 요약

| 구분 | 항목 | 현재 상태 | 관련 PAPER |
|---|---|---:|---|
| 0순위 | 다중계좌 구축 환경 점검 | 부분 반영 / 후속 필요 | PAPER16~20에서 account-aware 경로 일부 반영 |
| 1순위 | Daily Ops Status Dashboard | 완료 | PAPER16 |
| 1.5순위 | Export / Sync 정책 정리 | 완료 | PAPER17 |
| 2순위 | Alert / Monitoring Report | 완료 | PAPER18 |
| 2.5순위 | Replay / Same-date Diff 최소 체인 | 완료 | PAPER19 |
| 2.6순위 | Replay Wrapper Operational Smoke / Runbook | 완료 | PAPER20 |
| 2.7순위 | Stable Plan Row Identity / Non-empty Replay Smoke Expansion | 다음 작업 | PAPER21 |
| 3순위 | Notion UI 개선 | 일부 반영 / 후속 | PAPER16 수동 view 정리, filter hardening deferred |
| 3.5순위 | Notion Schema/View Drift Check | 미착수 | 후속 |
| 4순위 | Universe 변경 Preview → Universe 확장 | 미착수 | 후속 |
| 5순위 | 전략 확장 | 미착수 | 후속 |

---

## 2. 완료된 기능 상세

### 2.1. PAPER16 — Daily Ops Status Dashboard

상태: 완료

목적:
- 오늘 Paper 운영이 어디까지 완료되었는지 한눈에 확인한다.
- 운영자가 다음에 실행해야 할 명령을 즉시 알 수 있게 한다.

완료 내용:
- Daily Ops Status Dashboard 설계
- 상태별 command map / rerun policy 정리
- Daily Ops Status Notion view 수동 정리 및 consistency check
- Today Ops, By Account, Needs Action, Recent Sync, Review Closeout view 정리
- filter hardening은 row visibility 문제로 후속 보류

주요 한계:
- Notion view 검증은 사용자 화면/수동 보고 기준
- 자동 schema/view drift check 없음
- filter hardening 미완료

---

### 2.2. PAPER17 — Export / Sync Policy Hardening

상태: 완료

목적:
- Notion export와 status sync의 의미를 명확히 통일한다.
- actual export/sync 전에 command gate, duplicate audit, preflight를 통해 위험을 줄인다.

완료 내용:
- Export / Sync command classification
- dry-run / actual / confirm guard 정책 정리
- duplicate audit dry-run 구현
- `.env` 기반 Notion settings 호환
- Daily Ops Status actual preflight 구현
- source-of-truth 성공 후 Notion sync 실패 시 rollback 금지 원칙 정리

주요 한계:
- actual preflight smoke 범위는 제한적
- 실제 actual export는 아직 수행하지 않음
- schema/view drift automation은 없음

---

### 2.3. PAPER18 — Alert / Monitoring Report

상태: 완료

목적:
- WARNING / FAIL / Notion sync 실패 / 운영 누락을 놓치지 않게 한다.
- Daily Ops Status Dashboard와 중복되지 않는 Paper Ops Exception Report를 만든다.

완료된 Alert source:
- Daily Ops Status
- PAPER17 actual preflight
- Manual Execution high-level signal
- Manual Review high-level signal
- Data freshness
- Same-date guard

등급:
- BLOCKING: 운영 중단 필요
- NEEDS_REVIEW: 수동 판단 필요
- SYNC_FAILED: source-of-truth는 성공했지만 sync/export/status reflection 실패
- INFO: 참고용 정보

완료 내용:
- Alert Report 설계
- JSON / Markdown generator 구현
- INFO suppression 정책 구현
- 실제 source-root 연결
- Manual Execution / Manual Review high-level signal 연결
- freshness / same-date guard source 연결
- read-only safety 유지

주요 한계:
- freshness / same-date guard producer contract는 아직 candidate 수준
- schema/view drift source 미연결
- replay/diff source는 PAPER19~20에서 별도 진행
- external delivery adapter 미구현

---

### 2.4. PAPER19 — Replay / Same-date Diff

상태: 완료

목적:
- 같은 날짜의 Daily Plan을 다시 생성하거나 비교했을 때, 기존 official/committed Daily Plan과 어떤 차이가 나는지 감지한다.
- 유니버스/전략 확장 전 재현성 위험을 줄인다.

완료된 최소 체인:
1. Daily Plan JSON diff core/CLI
2. `paper_daily_plan.v1` JSON sidecar producer
3. sidecar → replay diff smoke
4. minimal fingerprints
5. `paper_config_hash.v1` helper / sidecar populate
6. replay wrapper minimal dry-run

주요 산출물:
- `scripts/dev/diff_daily_plan.py`
- `scripts/dev/replay_daily_plan_diff.py`
- `paper_daily_plan.v1` sidecar
- `paper_config_hash.v1`
- replay diff JSON / Markdown report
- replay-only `runs/{run_id}` output 구조

Replay wrapper flow:
1. baseline sidecar 입력
2. account/date 검증
3. `runs/{run_id}` 생성
4. `generate_daily_plan(run_mode=replay, official_run=false)` 호출
5. regenerated Markdown / JSON sidecar / config snapshot 생성
6. `compare_daily_plan_files()` diff
7. JSON / Markdown diff report 생성
8. safety marker 유지

Safety markers:
- `write_executed=false`
- `actual_executed=false`
- `notion_api_called=false`
- `notion_sync_executed=false`
- `notion_write_export_sync_executed=false`
- `commit_append_executed=false`

주요 한계:
- PAPER19 단독 closeout 시점에는 실제 `paper_sandbox` baseline sidecar 기반 smoke가 제한적이었다.
- `stable plan_item_id` 미구현
- `universe_hash` 미구현
- `market_data_asof` 미구현
- `indicator_snapshot_hash` 미구현
- `state_snapshot_hash` 미구현
- Manual Execution / Review replay 미포함
- Notion sync replay 미포함

---

### 2.5. PAPER20 — Replay Wrapper Operational Smoke / Runbook

상태: 완료

목적:
- PAPER19에서 구현한 replay wrapper를 실제 운영에 가까운 controlled smoke로 검증한다.
- 운영자가 replay diff 결과를 해석할 수 있는 runbook을 정리한다.
- 실제 운영 루프에 편입하기 전, generated artifact와 safety boundary를 명확히 한다.

완료 체인:
1. baseline inventory
2. 기존 sidecar blocker 확인
3. controlled output-dir blocker 확인
4. dev-only Daily Plan controlled baseline capture CLI 구현
5. controlled baseline capture 실행
6. replay wrapper smoke 실행
7. config_hash WARNING 분석
8. `source` → `producer_source` 명확화
9. `source` / `producer_source`를 provenance metadata로 hash 제외
10. controlled smoke 재실행
11. 최종 `PASS_WITH_METADATA_DIFF` 확인
12. replay diff runbook 정리

주요 산출물:
- `scripts/dev/capture_daily_plan_baseline.py`
- `docs/operations/paper_replay_diff_runbook.md`
- `docs/TRD/mfu_paper20_replay_smoke_runbook_closeout.md`

최종 smoke 결과:
- `overall_status = PASS_WITH_METADATA_DIFF`
- `diff_categories = METADATA_DIFF`
- `config_hash diff 없음`
- `cause_candidates = []`

해석:
- 핵심 Daily Plan 비교 필드는 일치했다.
- 남은 차이는 timestamp / path / run metadata / provenance metadata 계열이다.
- `PASS_WITH_METADATA_DIFF`는 read-only replay smoke 성공으로 볼 수 있다.
- 단, actual/export/sync/commit/append 승인 의미는 아니다.

config_hash false warning 해소:
- PAPER20-5에서 `config_hash` WARNING 발생
- PAPER20-6에서 원인을 `source` provenance metadata 차이로 분석
- PAPER20-7에서 새 산출물은 `producer_source` 사용
- legacy `source`와 신규 `producer_source`는 모두 hash 제외
- `strategy_source`, `universe_source`, `market_data_source`는 semantic 후보로 hash-significant 유지

Safety policy:
- Notion API/write/export/sync 없음
- actual export 없음
- Manual Execution commit 없음
- Manual Review append 없음
- source-of-truth ledger commit/append 없음
- outputs/paper 원장 변경 없음
- generated smoke artifacts는 생성될 수 있으나 기본적으로 commit 금지

Generated artifact policy:
- `outputs/tmp*`
- `outputs/tmp_paper20_baseline_capture/*`
- `outputs/tmp_paper20_replay_smoke/*`
- `outputs/paper_accounts/*` generated smoke artifacts

위 경로는 stage/commit 금지다.

주요 한계:
- `items_count=0` smoke였으므로 action-row 재현성 검증은 제한적이다.
- 2026-05-26 plan은 `data_date=2026-05-20` 기준이므로 trading correctness 검증이 아니다.
- historical actual-operation verification이 아니다.
- `stable plan_item_id` 미구현
- `universe_hash` 미구현
- `market_data_asof` 미구현
- `indicator_snapshot_hash` 미구현
- `state_snapshot_hash` 미구현
- 공식 `scripts/run_paper_daily_plan.py --output-dir` 정식 지원 여부는 후속 판단

---

## 3. 다음 작업: PAPER21 Stable Plan Row Identity / Non-empty Replay Smoke Expansion

### 3.1. 목적

PAPER21은 PAPER19~20에서 구축한 replay/same-date diff 체인을 실제 action row가 있는 Daily Plan에도 안정적으로 확장하기 위한 작업이다.

PAPER20의 controlled smoke는 성공했지만 `items_count=0`이었기 때문에, action/symbol/quantity/price row가 존재하는 상황의 재현성 검증은 아직 충분하지 않다.

PAPER21의 목표:
- Daily Plan row identity를 안정화한다.
- 동일 symbol/action 중복 또는 row order 변화에 취약하지 않게 한다.
- non-empty Daily Plan replay smoke를 안전하게 확장한다.
- replay diff report가 실제 action row 차이를 더 신뢰성 있게 보여주도록 한다.

### 3.2. 주요 작업 후보

- 현재 row identity 정책 점검
- `symbol + action` key의 한계 정리
- stable `plan_item_id` 설계
- `plan_item_id` 후보:
  - deterministic row hash
  - symbol + action + reason_code
  - symbol + action + normalized intent
  - producer-generated stable id
- 기존 `paper_daily_plan.v1` sidecar와 하위호환 정책 정리
- duplicate row key 처리 정책 보강
- non-empty fixture 기반 replay diff 테스트 추가
- 가능하면 controlled non-empty smoke 후보 날짜/조건 검토
- non-empty smoke가 trading correctness 검증이 아님을 명시

### 3.3. Non-scope

PAPER21에서는 다음을 기본적으로 하지 않는다.

- Notion API/write/export/sync
- actual export
- Manual Execution commit
- Manual Review append
- source-of-truth ledger commit/append
- Universe 확장
- 신규 전략 도입
- Broker/API 연동
- Telegram/Slack/Email external delivery
- 공식 `run_paper_daily_plan.py --output-dir` 정식 지원

### 3.4. 성공 기준

- stable row identity 정책이 정의됨
- non-empty Daily Plan replay diff 테스트가 추가됨
- duplicate row key 처리 기준이 명확해짐
- action/symbol/quantity/price diff 해석이 더 안정화됨
- Notion/API/write/export/sync 없음
- source-of-truth 원장 변경 없음

---

## 4. 후속 로드맵

### 4.1. Notion UI 개선

상태: 후속

목적:
- Notion을 예쁘게 꾸미는 것이 아니라, 모바일 입력과 검토 오류를 줄인다.

주요 개선 방향:
- 오늘 입력해야 할 Manual Executions만 보이는 view
- 오늘 입력해야 할 Manual Reviews만 보이는 view
- READY / COMMITTED / SYNCED 상태 가독성 개선
- WARNING row 필터 view
- 입력 필드 최소화
- 사용자가 수정하면 안 되는 필드 숨김 또는 하단 배치
- PAPER16에서 보류한 filter hardening 재검토

판단 기준:
- 스마트폰에서 입력 실수와 확인 누락이 줄어드는가?

---

### 4.2. Notion Schema/View Drift Check

상태: 후속

목적:
- Notion UI 변경 후 Python import/export/status sync가 깨지는 것을 방지한다.

주요 기능:
- 필수 property 존재 여부 확인
- select option 존재 여부 확인
- mapping 파일과 실제 Notion DB 차이 확인
- status sync가 수정해도 되는 필드만 수정하는지 확인
- view/filter/sort/표시 필드 drift 점검 후보

판단 기준:
- Notion UI를 바꿔도 Python 연동과 운영 판단이 안전하게 유지되는가?

---

### 4.3. Universe 변경 Preview → Universe 확장

상태: 후속

목적:
- 유니버스를 바로 확장하지 않고, 변경 영향을 먼저 확인한다.

1단계:
- universe added / removed / kept report
- 현재 보유 종목 중 removed 여부 확인
- universe 변경이 Daily Plan에 미치는 영향 확인
- universe snapshot 정책 검토
- PAPER19~20의 `universe_hash` 후보와 연결

2단계:
- S&P500 / NASDAQ100 외 universe 확장 검토
- 미국 전체 중 시총 / 거래대금 필터
- 한국 전체 중 시총 / 영업이익 / 거래대금 필터
- custom universe snapshot 지원

판단 기준:
- 유니버스 변경이 포지션, 후보군, Daily Plan에 미치는 영향이 설명 가능한가?

---

### 4.4. 전략 확장

상태: 후속

목적:
- 운영 안정성, 상태 가시성, 위험 감지, 재현성이 확보된 이후 신규 전략을 확장한다.

주요 기능:
- 신규 전략 후보 정의
- 전략별 signal / score / weight 분리
- 기존 전략 대비 성과 비교
- backtest-paper parity 검증
- 전략 변경 시 Daily Plan diff 확인
- PAPER19~20 replay diff를 전략 변경 검증에 활용

판단 기준:
- 신규 전략이 기존 전략과 비교 가능한 방식으로 검증되는가?

---

## 5. 보류 항목

아래 항목은 현재 로드맵 후순위로 둔다.

### Cloud / 원격 실행

보류 이유:
- status dashboard, alert, replay smoke/runbook이 먼저 안정화되어야 한다.
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

## 6. 개발 진행 원칙

- 한 번에 큰 기능을 만들지 않는다.
- MFU 단위로 쪼개서 구현한다.
- 각 MFU는 문서, 코드, 테스트, 운영 명령, 성공 기준을 포함한다.
- source-of-truth artifact를 수정하는 기능은 반드시 preview 단계를 둔다.
- FAIL은 commit/append 금지다.
- WARNING은 기본 차단이며, 명시적 허용이 있을 때만 진행한다.
- Notion sync 실패는 source-of-truth rollback 사유가 아니다.
- Notion sync 실패 시 같은 commit report로 status sync만 재실행한다.
- Replay / diff 계열 기능은 원인 단정이 아니라 원인 후보를 표시한다.
- 실제 운영 smoke 전에는 `--output-dir`을 명시해 공식 계좌 artifact 오염을 피한다.
- generated smoke artifact는 기본적으로 commit하지 않는다.
- 기존 Markdown / CSV / SQLite source-of-truth 의미를 바꾸는 변경은 별도 명시 검토 후 진행한다.
- `producer_source`는 생성 도구 출처 metadata이며 hash 제외 대상이다.
- `strategy_source`, `universe_source`, `market_data_source`는 의미 있는 입력 조건일 수 있으므로 hash-significant 후보로 취급한다.

---

## 7. 최종 로드맵 요약 v1.2

0. 다중계좌 구축 환경 점검 — 부분 반영 / 후속 필요
1. Daily Ops Status Dashboard — 완료
1.5. Export / Sync 정책 정리 — 완료
2. Alert / Monitoring Report — 완료
2.5. Replay / Same-date Diff 최소 체인 — 완료
2.6. Replay Wrapper Operational Smoke / Runbook — 완료
2.7. Stable Plan Row Identity / Non-empty Replay Smoke Expansion — 다음 작업, PAPER21
3. Notion UI 개선 — 후속
3.5. Notion Schema/View Drift Check — 후속
4. Universe 변경 Preview → Universe 확장 — 후속
5. 전략 확장 — 후속

---

## 8. 핵심 결론

현재 stock-screener Paper 운영의 병목은 전략 부족이 아니라 운영 신뢰도였다.

v1.2 기준으로 Daily Ops Status, Export/Sync 정책, Alert/Monitoring, Replay/Same-date Diff, Replay Wrapper Operational Smoke / Runbook의 최소 기반은 구축됐다.

PAPER20에서 controlled replay smoke는 최종 `PASS_WITH_METADATA_DIFF`까지 확인되었고, `config_hash` false WARNING도 `producer_source` 정리와 hash normalization 보강으로 해소됐다.

따라서 다음 단계는 신규 전략 확장이 아니라, PAPER21에서 stable plan row identity와 non-empty replay smoke를 확장해 action row가 있는 Daily Plan에서도 재현성 점검을 신뢰할 수 있게 만드는 것이다.

그 다음에 Notion UI/Schema Drift, Universe Preview, 전략 확장 순서로 진행한다.

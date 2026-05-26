# MFU-PAPER14-Notion Closeout

## 1. 목적과 범위

이번 PAPER14-Notion-closeout은 PAPER14 Notion 연동 전체 범위를 정리하고 완료/보류/후속 범위를 문서화하는 작업이며, Python 코드 수정, Notion actual write/export, Manual Execution commit, Manual Review append, paper trading ledger 수정은 수행하지 않았다.

PAPER14 Notion 연동의 목적은 paper trading 운영에서 다음 두 가지를 분리하는 것이다.

- source-of-truth 관리
- 모바일/검토 친화적인 입력 및 표시 계층

최종 원칙:

- Notion = 입력 UI / 검토 UI / staging layer
- CSV / JSON / Markdown / SQLite = source of truth
- Python = validation / preview / commit / append / export 주체

이번 closeout 문서는 PAPER14에서 구현된 Notion 연동 전체를 다음 관점에서 정리한다.

- 어떤 DB가 어떤 역할을 하는지
- 어떤 source artifact를 기준으로 동작하는지
- 어떤 흐름이 실제 운영 가능한 상태인지
- 어떤 항목이 보류되었는지
- 어떤 후속 MFU가 적절한지

## 2. PAPER14 완료 범위

PAPER14에서 완료된 범위:

- `Daily Plans` read-only export
- `Manual Executions` input -> preview -> commit -> status sync
- `Account Snapshots` read-only export
- `Weekly Reports` read-only export
- `Benchmark Reports` read-only export
- `Daily Review Summaries` read-only export
- `Manual Reviews` input -> preview -> append -> status sync
- Review 포함 운영 SOP 보강

PAPER14에서 제외 또는 보류된 범위:

- `Performance Summary` 별도 DB 구현
- Notion DB 자동 생성
- Notion schema migration
- Notion을 source of truth로 사용하는 구조
- broker/API 연동
- 스마트폰 단독 commit / append 실행
- GitHub Actions / cloud runner 기반 운영
- `paper_daily_ops.md` 전체 리팩토링
- `export_paper_to_notion.py --all` 최종 정책 정리

## 3. Notion DB별 역할

| DB | 역할 | source artifact | write 방향 | upsert key / external key | 주요 status 필드 | 완료 상태 | 후속 리스크 |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| `Daily Plans` | 당일 실행 계획 표시 | `daily_action_plan_YYYYMMDD.md`, `paper_config_snapshot_YYYYMMDD.json` | Python -> Notion | `daily_plan:{plan_date}` | `Sync Status` | 완료 | Markdown 구조 변경 시 body/parser 영향 |
| `Manual Executions` | 실제 체결 입력 staging | Notion row 입력, local preview/commit report | Notion -> Python -> CSV -> Notion status sync | `manual_execution:{execution_date}:{symbol}:{side}:{sequence}` | `Status`, `Validation Status`, `Import Status` | 완료 | warning 허용 운영, sidecar 의존 |
| `Account Snapshots` | 계좌 상태 표시 | `paper_account_snapshot.csv` | Python -> Notion | snapshot date 기준 external key | `Sync Status`, `Valuation Status` | 완료 | valuation freshness 해석 필요 |
| `Weekly Reports` | 주간 운영 rollup | weekly summary markdown/json | Python -> Notion | period 기반 external key | `Overall Status`, `Coverage Status`, `Sync Status` | 완료 | 운영 gap 해석을 문서와 함께 봐야 함 |
| `Benchmark Reports` | benchmark 비교 표시 | benchmark comparison markdown/json | Python -> Notion | run/snapshot 기반 external key | `Availability Status`, `Sync Status` | 완료 | exploratory metric 해석 주의 |
| `Daily Review Summaries` | 하루 운영 결과 요약 | commit report, preview report, account/position snapshot, execution log | Python -> Notion | `daily_review_summary:{review_date}` | `Review Status`, `Availability Status`, `Sync Status` | 완료 | commit report가 없을 때 fallback 해석 제한 |
| `Manual Reviews` | 사후복기 답변 입력 staging | Notion row 입력, local preview/commit report | Notion -> Python -> CSV -> Notion status sync | `manual_review:{review_date}:{symbol}:{question_id}` | `Validation Status`, `Import Status` | 완료 | mobile 입력 row 수 증가, warning 운영 필요 |

메모:

- `Performance Summary`는 mapping 예시상 placeholder가 남아 있지만, 별도 운영 DB로는 closeout 범위에 포함하지 않는다.

## 4. 완료된 운영 흐름

PAPER14 closeout 시점의 최종 daily loop:

Prepare / preflight  
-> Daily Plan 생성  
-> Daily Plan Notion export  
-> Notion에서 Daily Plan 확인  
-> 실제 action 수행  
-> Notion Manual Executions 입력  
-> Manual Executions preview  
-> execution commit  
-> account / position / current_state 갱신  
-> Manual Executions status sync  
-> Daily Review Summary export  
-> Notion에서 Daily Review Summary 확인  
-> Notion Manual Reviews 입력  
-> Manual Reviews preview  
-> review append  
-> Manual Reviews status sync  
-> Weekly / Benchmark / Account Snapshot export

핵심 분리:

- 계획 계층: `Daily Plans`
- 실제 체결 입력 계층: `Manual Executions`
- 결과 요약 계층: `Daily Review Summaries`
- 사후복기 입력 계층: `Manual Reviews`
- 기간/상태 요약 계층: `Account Snapshots`, `Weekly Reports`, `Benchmark Reports`

## 5. Artifact Flow

### 5.1 Daily Plan export flow

local plan source 생성  
-> property/body payload 구성  
-> dry-run  
-> actual export  
-> External Key 기준 created / updated upsert

### 5.2 Manual Execution flow

Notion input  
-> Python read-only import  
-> preview JSON  
-> user-approved commit  
-> `paper_execution_log.csv` update  
-> account / position / current_state 갱신  
-> commit sidecar JSON  
-> Notion status back-write

### 5.3 Daily Review Summary flow

commit report / execution log / account snapshot / position snapshot  
-> read-only summary payload 계산  
-> dry-run  
-> actual export  
-> `daily_review_summary:{review_date}` 기준 upsert

### 5.4 Manual Review flow

Notion input  
-> Python read-only import  
-> preview JSON  
-> user-approved append  
-> `paper_manual_review_log.csv` update  
-> commit sidecar JSON  
-> Notion status back-write

### 5.5 Weekly / Benchmark / Account Snapshot export flow

local report / snapshot source 생성  
-> payload 계산  
-> dry-run  
-> actual export  
-> External Key 기준 upsert

## 6. Status와 Safety 정책

### 용어

- `READY`
  - Notion 입력이 완료되어 Python preview 대기 상태
- `COMMITTED`
  - source-of-truth artifact 반영이 끝난 상태
- `SYNCED`
  - read-only export row가 최신 동기화 시각으로 반영된 상태
- `PASS`
  - blocking issue 없음
- `WARNING`
  - 비차단 이슈가 있음
- `FAIL`
  - blocking issue가 있음
- `created`
  - External Key로 기존 row가 없어 새 row 생성
- `updated`
  - External Key로 기존 row 1개를 찾아 update
- `dry-run`
  - payload / decision path만 생성, write 없음
- `--allow-warnings`
  - WARNING preview를 운영자가 명시적으로 허용할 때만 사용하는 override

### 안전 정책

- `FAIL`이 있으면 commit / append 금지
- `WARNING`이 있으면 기본 차단
- `--allow-warnings`가 있을 때만 commit / append 허용
- warning 허용 사유는 review note 또는 operation note에 남긴다
- Notion sync 실패 시 원장 rollback은 하지 않는다
- Notion sync 실패 시 같은 commit report로 sync만 재실행한다

이유:

- source of truth는 local CSV / JSON / Markdown / SQLite다
- Notion sync는 presentation / status layer이므로 commit 성공 여부와 분리한다

## 7. 스마트폰 / 로컬 PC 역할

### 스마트폰에서 가능한 단계

- `Daily Plan` 확인
- `Manual Executions` 입력
- `Daily Review Summary` 확인
- `Manual Reviews` 입력
- Notion의 `READY`, `COMMITTED` 등 상태값 확인

### 로컬 PC에서 해야 하는 단계

- preview 실행
- commit / append 실행
- ledger / review log / current state 갱신
- status back-write
- Notion export / sync

결론:

- 스마트폰은 입력/검토 UI로는 충분히 유효하다
- source-of-truth 변경을 동반하는 commit / append는 로컬 PC가 필수다

## 8. Performance Summary 보류 기록

`Performance Summary`는 7A 판단에 따라 현재 보류한다.

보류 이유:

- `Benchmark Reports`, `Weekly Reports`, `Account Snapshots`, `Daily Review Summaries` 조합으로 핵심 성과 판단을 상당 부분 커버한다
- 별도 `Performance Summary` DB는 장기 dashboard anchor 역할은 가능하지만 현재는 중복이 많다
- stable structured source artifact보다 markdown 중심 artifact 비중이 높다
- paper 데이터량이 아직 적어 장기 성과 summary의 판단 가치가 제한적이다

따라서 현재 closeout 결론은 다음과 같다.

- `Performance Summary`는 구현하지 않는다
- 추후 forward/paper 데이터가 더 쌓이고 stable JSON source가 생기면 재평가한다

## 9. 운영 문서 상태

현재 운영 문서:

- `docs/operations/paper_daily_ops.md`
- `docs/operations/paper_notion_ops.md`

의미:

- `paper_daily_ops.md`는 전체 운영 loop 요약
- `paper_notion_ops.md`는 Notion 세부 절차

제약:

- `paper_daily_ops.md`에는 오래된 section과 최신 addendum/추가 section이 병존한다
- 이번 closeout에서는 해당 문서를 전면 리팩토링하지 않고, 현행 운영 가능 상태로만 정리한다

## 10. 보류 / 제외 항목

- `Performance Summary`: 현재 보류
- Notion DB 자동 생성: 제외
- Notion schema migration: 제외
- Notion을 source of truth로 사용하는 구조: 제외
- broker/API 연동: 제외
- 스마트폰 단독 commit / append 실행: 제외
- GitHub Actions / cloud runner 운영: 보류
- `paper_daily_ops.md` 전체 리팩토링: 후속 MFU
- `export_paper_to_notion.py --all` 정책 정리: 후속 검토 가능

## 11. 남은 리스크

- `paper_daily_ops.md`에 오래된 section과 최신 addendum이 병존
- 일부 Notion DB별 view policy는 TRD 문서를 함께 봐야 함
- warning 허용 사유 기록이 운영자 습관에 의존
- Notion API / network 실패 가능성
- unrelated worktree 변경이 누적되어 있음

## 12. 최종 판정

PAPER14 Notion review/input layer는 다음 범위까지 1차 운영 가능한 상태로 closeout한다.

- `Daily Plans`
- `Manual Executions`
- `Daily Review Summaries`
- `Manual Reviews`
- `Account Snapshots`
- `Weekly Reports`
- `Benchmark Reports`

정리:

- `Daily Plan`, `Manual Executions`, `Daily Review Summary`, `Manual Reviews`까지 일일 운영 루프가 닫혔다
- source-of-truth 원칙은 유지된다
- Notion은 입력 / 검토 / staging layer로만 사용된다
- `Performance Summary`는 현재 보류한다

## 13. 다음 MFU 제안

- `paper_daily_ops.md` 리팩토링 MFU
- `export_paper_to_notion.py --all` 정책 정리 MFU
- 운영 SOP 압축 / cheat sheet MFU
- 모바일/원격 실행 검토 MFU
- `Performance Summary` 재평가 MFU

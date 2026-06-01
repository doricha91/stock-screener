# PAPER15-3E: Notion External Key Account Namespace Design

## 1. Purpose

이번 문서는 다중계좌 도입에 맞춰 Notion DB의 `Account ID` property, `External Key` namespace, legacy `paper_default` 호환 정책, 후속 migration 범위를 설계한다.

## 2. Scope / Non-scope

포함:
- 현재 account-less Notion key inventory 정리
- `Account ID` property 권장안
- DB별 신규 account-aware `External Key` 형식 정의
- legacy `paper_default` 해석 정책
- upsert / import / status sync 영향 정리
- Manual Notion setup checklist
- migration 전략과 후속 MFU 제안

제외:
- 코드 구현
- Notion API write / export / sync 실행
- Notion schema migration
- 기존 row `External Key` 변경
- paper 원장 수정
- DB write

## 3. Current Notion Account-less Key Inventory

현재 확인된 주요 key 형식:

- `weekly_report:{period_start}:{period_end}`
- `benchmark:{latest_snapshot_date}:{run_mode}`
- `account_snapshot:{snapshot_date}`
- `daily_plan:{plan_date}`
- `daily_review_summary:{review_date}`
- `manual_execution:{execution_date}:{symbol}:{side}:{sequence}`
- `manual_review:{review_date}:{symbol}:{question_id}`

현재 구조의 문제:

- 계좌 차원이 key에 없어서 같은 날짜/심볼/side/question 조합이 다른 계좌에서 충돌할 수 있다.
- exporter upsert는 `External Key`만 기준으로 하므로 multi-account row를 단일 row로 덮어쓸 위험이 있다.
- Manual Execution / Manual Review status sync는 `canonical_key -> External Key` 재기록 구조라 계좌 충돌에 취약하다.

## 4. Account ID Property Recommendation

권장안:

- Property name: `Account ID`
- 권장 type: `Select`
- 대안 type: `Rich text`

권장 이유:

- 운영자가 mobile UI에서 값 선택하기 쉽다.
- 오타를 줄일 수 있다.
- READY / COMMITTED / view filter에 넣기 쉽다.

대안이 필요한 경우:

- 계좌 수가 매우 많거나 option 관리가 번거로운 경우 `Rich text`도 가능하다.
- 다만 현재 범위에서는 `Select`가 더 안전하다.

권장 정책:

- 아래 모든 DB에 `Account ID` 추가
  - `Daily Plans`
  - `Manual Executions`
  - `Account Snapshots`
  - `Weekly Reports`
  - `Benchmark Reports`
  - `Daily Review Summaries`
  - `Manual Reviews`
- 초기 option:
  - `paper_default`
- 기존 row는 `Account ID`가 비어 있어도 `paper_default`로 해석
- 신규 row는 계좌-aware 구현 이후 `Account ID`를 사실상 필수로 취급

## 5. DB-by-DB External Key Namespace Design

### 5.1 Daily Plans

- 현재 key:
  - `daily_plan:{plan_date}`
- 신규 key:
  - `daily_plan:{account_id}:{plan_date}`
- `Account ID`:
  - 필요
- legacy 해석:
  - `Account ID` blank 또는 legacy key면 `paper_default`
- migration:
  - 필요하지만 이번 단계에서는 미실행
- 후속 구현 위치:
  - exporter
- 사용자 수동 작업:
  - DB에 `Account ID` property 추가

### 5.2 Manual Executions

- 현재 key:
  - `manual_execution:{execution_date}:{symbol}:{side}:{sequence}`
- 신규 key:
  - `manual_execution:{account_id}:{execution_date}:{symbol}:{side}:{sequence}`
- `Account ID`:
  - 필수 수준 권장
- legacy 해석:
  - `Account ID` blank면 `paper_default`
- migration:
  - 기존 READY / COMMITTED row 모두 영향 가능
- 후속 구현 위치:
  - importer, status sync
- 사용자 수동 작업:
  - `READY` view에 `Account ID = paper_default` filter 추가 권장

### 5.3 Account Snapshots

- 현재 key:
  - `account_snapshot:{snapshot_date}`
- 신규 key:
  - `account_snapshot:{account_id}:{snapshot_date}`
- `Account ID`:
  - 필요
- legacy 해석:
  - blank -> `paper_default`
- migration:
  - 낮은 복잡도, exporter 중심
- 후속 구현 위치:
  - exporter
- 사용자 수동 작업:
  - 기존 row에 `Account ID` column visible 설정

### 5.4 Weekly Reports

- 현재 key:
  - `weekly_report:{period_start}:{period_end}`
- 신규 key:
  - `weekly_report:{account_id}:{period_start}:{period_end}`
- `Account ID`:
  - 필요
- legacy 해석:
  - blank -> `paper_default`
- migration:
  - exporter 중심
- 후속 구현 위치:
  - exporter
- 사용자 수동 작업:
  - account별 view 또는 filter 추가 검토

### 5.5 Benchmark Reports

- 현재 key:
  - `benchmark:{latest_snapshot_date}:{run_mode}`
- 신규 key:
  - `benchmark:{account_id}:{latest_snapshot_date}:{run_mode}`
- `Account ID`:
  - 필요
- legacy 해석:
  - blank -> `paper_default`
- migration:
  - exporter 중심
- 후속 구현 위치:
  - exporter
- 사용자 수동 작업:
  - exploratory / official view에 `Account ID` filter 검토

### 5.6 Daily Review Summaries

- 현재 key:
  - `daily_review_summary:{review_date}`
- 신규 key:
  - `daily_review_summary:{account_id}:{review_date}`
- `Account ID`:
  - 필요
- legacy 해석:
  - blank -> `paper_default`
- migration:
  - exporter 중심
- 후속 구현 위치:
  - exporter
- 사용자 수동 작업:
  - review 날짜와 함께 `Account ID` visible 유지

### 5.7 Manual Reviews

- 현재 key:
  - `manual_review:{review_date}:{symbol}:{question_id}`
- 신규 key:
  - `manual_review:{account_id}:{review_date}:{symbol}:{question_id}`
- `Account ID`:
  - 필수 수준 권장
- legacy 해석:
  - blank -> `paper_default`
- migration:
  - READY / COMMITTED row 모두 영향 가능
- 후속 구현 위치:
  - importer, status sync
- 사용자 수동 작업:
  - `READY` view에 `Account ID = paper_default` filter 추가 권장

## 6. Legacy paper_default Compatibility Policy

확정 정책:

- 기존 단일계좌 row는 `account_id = paper_default`로 해석
- 기존 `External Key`가 account-less여도 `paper_default` row로 본다
- 기존 row를 즉시 재작성하지 않는다

권장 compatibility 방식:

- 신규 exporter / importer / sync는 새 key를 primary로 사용
- legacy row lookup fallback은 `paper_default`에서만 제한적으로 허용
- legacy row를 update할 때는 즉시 새 key로 바꾸지 않고, 별도 migration 전까지 유지하는 보수적 전략이 안전하다

이유:

- 사용자가 Notion에서 기존 row를 이미 운영 중일 수 있다
- 일괄 key rewrite는 duplicate / orphan row 위험이 있다

## 7. Upsert / Import / Status Sync Impact

### Exporter 영향

영향 대상:

- weekly
- benchmark
- account snapshot
- daily plan
- daily review summary

필요 변경:

- `Account ID` property write
- `External Key` 생성 함수에 `account_id` 인자 추가
- upsert lookup은 새 key 기준
- `paper_default`일 때만 legacy key fallback optional 지원 검토

### Manual Execution Importer 영향

영향 대상:

- preview candidate normalization
- canonical key
- linked daily plan key
- status sync payload

권장 변경:

- candidate에 `account_id` 추가
- canonical key를 `manual_execution:{account_id}:...`로 확장
- `Linked Daily Plan Key`도 `daily_plan:{account_id}:{plan_date}`로 확장
- READY query는 가능하면 `Account ID` filter 포함

### Manual Review Importer 영향

권장 변경:

- candidate에 `account_id` 추가
- canonical key를 `manual_review:{account_id}:...`로 확장
- READY query에 `Account ID` filter 포함

### Status Sync 영향

현재:

- commit report의 `canonical_key`를 Notion `External Key`에 다시 씀

후속 필요:

- commit report 자체가 account-aware canonical key를 기록해야 함
- sync는 `page_id`가 있어도 payload의 `External Key`를 account-aware 값으로 써야 함

## 8. Manual Notion Setup Checklist

사용자가 Notion에서 해야 할 수동 작업:

1. 각 DB에 `Account ID` property 추가
2. type은 가능하면 `Select`
3. 초기 option으로 `paper_default` 추가
4. `Manual Executions`의 READY view에 `Account ID` filter 추가 검토
5. `Manual Reviews`의 READY view에 `Account ID` filter 추가 검토
6. 필요 시 `paper_default`만 보이는 view와 전체 계좌 view를 분리
7. `Account ID`를 table visible column으로 유지
8. 기존 legacy row는 당장 수정하지 않고 blank 상태를 허용

## 9. Migration Strategy

이번 단계 결론:

- 즉시 migration 하지 않는다

권장 순서:

1. `Account ID` property 수동 추가
2. mapping example에 `account_id` 키 추가
3. exporter / importer / sync를 새 namespace로 구현
4. `paper_default`에 대해 legacy lookup fallback 지원
5. migration preview를 먼저 생성
6. 실제 row rewrite는 별도 MFU에서 선택적으로 수행

권장 migration 원칙:

- create/update보다 preview가 먼저
- legacy row 자동 rewrite 금지
- duplicate candidate / duplicate row 위험을 먼저 점검

## 10. Risks / Open Questions

주요 리스크:

- `Manual Executions`와 `Manual Reviews`는 READY view에 account filter가 없으면 다른 계좌 row를 함께 읽을 수 있다
- exporter upsert에서 legacy key와 new key 공존 시 duplicate page가 생길 수 있다
- `Select` option을 수동으로 추가해야 하므로 운영 discipline이 필요하다
- `paper_default` blank row를 언제까지 허용할지 정책을 정해야 한다

open questions:

- `Account ID`를 `Select`로 고정할지 `Rich text`도 허용할지
- exporter가 `paper_default` legacy row를 새 key row로 update할지 새 row로 create할지
- status sync에서 legacy row의 `External Key`를 바꾸는 시점을 언제로 둘지
- account_id option이 많아질 경우 view policy를 어떻게 단순화할지

## 11. Recommended Next MFUs

- `PAPER15-3E-1`: Notion Account ID property manual setup guide
- `PAPER15-3E-2`: `config/notion_property_mapping.example.json`에 `account_id` 추가
- `PAPER15-3E-3`: exporter external key namespace 구현
- `PAPER15-3E-4`: Manual Execution / Review importer account filter 설계 및 구현
- `PAPER15-3E-5`: legacy Notion row migration preview

## Purpose

이번 PAPER14-5A는 Notion Manual Execution Input 설계 및 검증 흐름 정의 작업이며, 실제 Notion import, paper ledger commit, Daily Review Summary export는 포함하지 않는다.

핵심 원칙:

- Notion = 입력 대기 / staging layer
- Python = 검증 / 정규화 / 원장 반영 주체
- CSV / SQLite = 최종 source of truth

Notion 입력값은 바로 원장에 반영하지 않는다. 반드시 아래 흐름을 따른다.

`Notion 입력 -> Python read-only import -> validation -> preview report -> 사용자 확인 -> commit -> paper execution ledger 반영`

## Problem Definition

현재 Daily Plan은 시스템이 생성한 계획이며, 실제 체결과 다를 수 있다.

대표 차이:

- 실제 체결가와 계획가 차이
- 실제 체결수량과 계획수량 차이
- 부분 체결 / 미체결
- 수수료 / 세금 / 환전 차이
- 실제 현금 잔고와 예상 잔고 차이

현재 paper workflow는 Daily Plan markdown의 journal 섹션을 읽어 `paper_execution_log.csv`로 반영한다. 이 방식은 CSV를 직접 수정하지 않아도 되지만, 사람이 실제 체결값을 편하게 입력하는 UI는 부족하다.

Notion은 입력 UI로는 유용하지만 source of truth가 되면 안 된다.

- Daily Plan은 read-only system plan
- Manual Executions는 사람이 입력하는 staging data
- 최종 ledger는 여전히 `paper_execution_log.csv`, `paper_account_snapshot.csv`, `paper_position_snapshot.csv`와 관련 state 산출물이다

## Proposed Notion DB

후보 data source 이름:

- `Manual Executions`

### Minimal ledger-required fields

- `Execution Date`
- `Symbol`
- `Side`
- `Quantity`
- `Actual Price`

### Operational convenience fields

- `Name`
- `External Key`
- `Plan Date`
- `Commission`
- `Currency`
- `Broker`
- `Status`
- `Linked Daily Plan Key`
- `Note`
- `Validation Status`
- `Validation Message`
- `Import Status`
- `Imported At`
- `Synced At`

### Recommended properties and types

- `Name`: `Title`
- `External Key`: `Rich text`
- `Execution Date`: `Date`
- `Plan Date`: `Date`
- `Symbol`: `Rich text`
- `Side`: `Select` (`BUY`, `SELL`)
- `Quantity`: `Number`
- `Actual Price`: `Number`
- `Commission`: `Number`
- `Currency`: `Select` (`USD`, `KRW`)
- `Broker`: `Select` or `Rich text`
- `Status`: `Select` (`DRAFT`, `READY`, `IMPORTED`, `REJECTED`)
- `Linked Daily Plan Key`: `Rich text`
- `Note`: `Rich text`
- `Validation Status`: `Select` (`NOT_CHECKED`, `PASS`, `WARNING`, `FAIL`)
- `Validation Message`: `Rich text`
- `Import Status`: `Select` (`NOT_IMPORTED`, `PREVIEWED`, `COMMITTED`, `SKIPPED`)
- `Imported At`: `Rich text`
- `Synced At`: `Rich text`

권장 분리:

- 원장 반영 필수: `Execution Date`, `Symbol`, `Side`, `Quantity`, `Actual Price`
- 운영 편의 / 추적: 나머지 필드

## External Key Policy

Notion row는 사용자가 key를 직접 입력하지 않게 하는 편이 안전하다.

권장 canonical key:

- `manual_execution:{execution_date}:{symbol}:{side}:{sequence}`

예:

- `manual_execution:2026-05-25:GEN:BUY:01`

설계 이유:

- 같은 날짜에 같은 종목을 여러 번 체결할 수 있다
- partial fill을 별도 row로 두는 것이 이후 검증과 취소/누락 추적에 유리하다
- `sequence` 없이는 같은 종목/방향 다중 체결을 구분하기 어렵다

권장 정책:

- 사용자 입력 필드로 `sequence`를 노출하지 않고, Python import 시 date+symbol+side 순으로 안정적으로 부여
- 같은 raw row를 다시 preview/import해도 같은 sequence를 재현할 수 있게 정렬 규칙을 고정
- 중복 import 방지는 `External Key`와 최종 `trade_id`를 모두 사용

추가 고려:

- 후속 commit 단계에서 `trade_id`는 현재 `paper_execution_log` 규칙과 호환되게 `date|symbol|side|shares|price|reason|source` 기반으로 다시 생성
- Notion `External Key`는 staging row dedupe 목적, `trade_id`는 ledger dedupe 목적

## Validation Rules

최소 FAIL 규칙:

- `Symbol` 없음
- `Side`가 `BUY`/`SELL` 아님
- `Quantity <= 0`
- `Actual Price <= 0`
- `Execution Date` 없음
- 동일 배치 내 `External Key` 중복
- 기존 imported set와 충돌하는 중복 row
- `SELL` 수량이 현재 보유수량보다 큼
- `BUY` 반영 후 현금이 음수

WARNING 후보:

- `Daily Plan`에 없는 `Symbol`
- `Plan Date` 없음
- `Linked Daily Plan Key` 없음
- `Commission` 비어 있음
- `Currency` 비어 있음
- `Broker` 비어 있음
- 계획 수량/가격과 실제 체결값 차이가 큼

정책 제안:

- `Commission` 비어 있으면 기본값 `0`으로 정규화하되 `WARNING`
- `Currency` 비어 있으면 계좌 기본 통화 `USD`를 적용하되 `WARNING`
- `Daily Plan`에 없는 종목은 기본 `WARNING`
  - 단, 운영 정책상 계획 외 매매를 금지한다면 후속 MFU에서 `FAIL`로 승격 가능

추가 검증:

- `Quantity`는 integer
- `Actual Price`, `Commission`은 numeric
- `Execution Date`가 commit 대상 date와 다르면 `WARNING` 또는 batch split
- `Status != READY` 인 row는 preview 대상에서 제외하거나 `SKIPPED`

## Preview -> Commit Flow

권장 CLI 방향 1:

```cmd
python scripts\paper.py execution-import preview --source notion --date YYYY-MM-DD
python scripts\paper.py execution-import commit --source notion --date YYYY-MM-DD
```

권장 CLI 방향 2:

```cmd
python scripts\import_notion_executions.py --date YYYY-MM-DD --preview
python scripts\import_notion_executions.py --date YYYY-MM-DD --commit
```

현 시점 권장:

- 기존 `paper.py` shortcut에 바로 섞기보다 별도 importer script로 시작
- 이유: preview/commit 정책과 오류 메시지를 분리하기 쉽고 기존 `paper.py commit`을 오염시키지 않음

preview 산출물 후보:

- `outputs/paper_test/reports/manual_execution_import_preview_YYYYMMDD.md`
- `outputs/paper_test/reports/manual_execution_import_preview_YYYYMMDD.json`

preview 내용:

- imported candidate row count
- PASS / WARNING / FAIL count
- normalized execution rows
- plan-vs-actual diff
- projected cash / holdings impact
- duplicate / missing / out-of-plan diagnostics

commit 정책:

- validation `FAIL`이 있으면 commit 금지
- `WARNING`만 있으면 사용자가 명시적으로 허용할 때만 commit
- commit은 preview JSON을 기준으로 동일 배치를 재현 가능해야 함
- commit 후 Notion `Import Status` / `Imported At` update는 후속 MFU로 미룸

## Existing Ledger Linkage

현재 commit 파이프라인의 첫 실제 ledger 입력은 `paper_execution_log.csv`다.

현재 `paper_execution_log.csv` 컬럼:

- `trade_id`
- `date`
- `regime`
- `symbol`
- `side`
- `shares`
- `price`
- `gross_amount`
- `source`
- `status`
- `reason`
- `notes`
- `rec_shares`
- `rec_price`
- `created_at`

현재 상태 적용 규칙:

- `core.paper_account_state.apply_paper_trade()`
  - `BUY`: 현금 감소, avg price / highest price 갱신
  - `SELL`: 보유수량 차감, realized pnl 반영
  - `SELL` 초과 수량 금지
  - `BUY` 현금 부족 금지

계좌/포지션 snapshot은 `paper_execution_log`에서 파생된다.

- `paper_account_snapshot.csv`
  - snapshot date 기준 cash / equity / realized/unrealized pnl / valuation status
- `paper_position_snapshot.csv`
  - symbol별 shares / avg_price / market_value / unrealized pnl

### Proposed staging-to-ledger mapping

Notion `Manual Executions` row -> normalized execution row -> `paper_execution_log.csv`

초안 매핑:

- `Execution Date` -> `date`
- `Symbol` -> `symbol`
- `Side` -> `side`
- `Quantity` -> `shares`
  - `BUY`는 positive
  - `SELL`는 ledger row에서 negative로 변환
- `Actual Price` -> `price`
- `Commission` -> 우선 preview 계산용 별도 field로 보관, 현 ledger schema에는 직접 저장하지 않음
- `Currency` -> 계좌 통화 검증용
- `Note` -> `notes`
- `Linked Daily Plan Key` -> 직접 ledger 컬럼은 없고 preview/report linkage 용도
- plan 대비 추천치가 있으면 `rec_shares`, `rec_price`로 채울 수 있음
- `source` -> 신규 상수 예: `notion_manual_execution`
- `reason` -> 신규 상수 예: `manual_execution_import`
- `status` -> ledger write 시 `READY_FOR_PAPER_TRADE` 또는 commit 전 preview 내부 상태

중요 제약:

- 현재 ledger schema에는 `commission`, `broker`, `currency` dedicated column이 없다
- 따라서 5A 단계에서는 schema change 없이 설계만 남긴다
- 후속 구현에서는
  - `notes`에 임시 보존할지
  - 별도 sidecar JSON/report로 보존할지
  - schema extension 승인을 받을지
를 결정해야 한다

## Relationship to Daily Review Summary

정책:

- `Manual Executions` = 사람이 입력한 실제 체결
- `Daily Review Summary` = 그 결과를 요약해 보여주는 read-only report

흐름:

1. Manual Executions에 사람이 입력
2. Python preview/validation
3. 사용자 승인 후 commit
4. ledger 반영 완료
5. 그 결과를 Daily Review Summary가 읽어 요약

즉, Daily Review Summary는 수동 입력 원천이 아니라 commit 이후 결과 요약 계층이다.

이번 5A에서는 Daily Review Summary export를 구현하지 않는다.

## Suggested Future MFUs

- `PAPER14-5B`: Notion Manual Executions schema contract + read-only importer preview
- `PAPER14-5C`: preview report generation + validation engine
- `PAPER14-5D`: commit path to `paper_execution_log.csv`
- `PAPER14-5E`: post-commit Notion status sync
- `PAPER14-6`: Daily Review Summary export based on committed manual executions

## Out of Scope

- Notion `Manual Executions` DB 실제 생성
- Notion schema validation 구현
- Notion execution row read 구현
- paper ledger commit 구현
- Daily Review Summary export 구현
- Performance Summary export 구현
- Manual Review 입력 연동 구현
- broker/API 연동
- 실제 Notion write

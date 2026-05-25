## Purpose

이번 PAPER14-5B는 Manual Executions schema contract와 Notion view policy 문서화 작업이며, 실제 Notion import, paper ledger commit, Daily Review Summary export는 수행하지 않는다.

이 문서는 `Manual Executions` Notion DB의 안정적인 schema contract와 운영 view 정책을 확정한다.

핵심 원칙:

- Notion은 입력 대기 / staging layer다
- Python은 검증 / 정규화 / import / commit 주체다
- CSV / SQLite는 최종 source of truth다

## Baseline

기준 커밋:

- `ffd2350f5933376f4bc2b9fec26901d76f0b797d`

이 문서는 PAPER14-5A 설계를 구체화해, 후속 importer / validator / preview report가 의존할 속성명과 view 정책을 고정하는 목적을 가진다.

## Current Ledger Constraints

조사 결과:

- `paper_execution_log.csv` 현재 컬럼
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
- dedicated column 부재
  - `commission` 없음
  - `currency` 없음
  - `broker` 없음
- BUY / SELL shares 표현
  - BUY는 positive shares
  - SELL는 negative shares
- account state 검증
  - BUY 현금 부족 금지
  - SELL 초과 수량 금지
- commit guard
  - 같은 `snapshot_date`가 기존 snapshot/current_state에 있으면 기본 차단

따라서 Manual Executions schema는 미래 확장 여지를 남기되, 현재 ledger에 없는 필드는 optional 운영 필드로 유지해야 한다.

## Schema Contract

후보 DB 이름:

- `Manual Executions`

속성은 세 그룹으로 나눈다.

1. 필수 입력 필드
2. 선택 입력 / 운영 편의 필드
3. 검증 / import 관리 필드

### 1. Required Input Fields

이 필드들은 후속 importer preview가 읽기 위해 사실상 필수다.

- `Name`
- `Execution Date`
- `Symbol`
- `Side`
- `Quantity`
- `Actual Price`
- `Status`

권장 타입:

- `Name`: `Title`
- `Execution Date`: `Date`
- `Symbol`: `Rich text`
- `Side`: `Select`
  - 권장 option: `BUY`, `SELL`
- `Quantity`: `Number`
- `Actual Price`: `Number`
- `Status`: `Select`
  - 권장 option: `DRAFT`, `READY`, `IMPORTED`, `REJECTED`

권장 의미:

- `Name`: 사람이 목록에서 식별하기 쉬운 row label
  - 예: `2026-05-25 GEN BUY`
- `Execution Date`: 실제 체결일
- `Symbol`: 실제 체결 종목
- `Side`: `BUY` / `SELL`
- `Quantity`: 절대 수량
  - Notion에는 음수 입력을 강제하지 않는다
  - SELL의 음수 변환은 Python importer가 담당한다
- `Actual Price`: 실제 체결가
- `Status`: 사용자의 입력 진행 상태

### 2. Optional Input / Operational Convenience Fields

이 필드들은 입력 편의와 추적용이지만, 현 ledger schema에 직접 일대일 대응하지 않는 것도 포함한다.

- `Plan Date`
- `Commission`
- `Currency`
- `Broker`
- `Note`
- `Linked Daily Plan Key`

권장 타입:

- `Plan Date`: `Date`
- `Commission`: `Number`
- `Currency`: `Select`
  - 권장 option: `USD`, `KRW`
- `Broker`: `Select` 또는 `Rich text`
- `Note`: `Rich text`
- `Linked Daily Plan Key`: `Rich text`

정책:

- `Commission / Currency / Broker`는 우선 optional field다
- 현재 ledger schema에는 dedicated column이 없으므로, 최종 commit 반영 방식은 후속 MFU에서 결정한다
- `Linked Daily Plan Key`는 `daily_plan:{plan_date}`와 연결하기 위한 보조 필드다

### 3. Validation / Import Management Fields

이 필드들은 사용자가 메인 입력 화면에서 항상 볼 필요는 없지만, importer와 검증 흐름에는 중요하다.

- `External Key`
- `Validation Status`
- `Validation Message`
- `Import Status`
- `Imported At`
- `Synced At`

권장 타입:

- `External Key`: `Rich text`
- `Validation Status`: `Select`
  - 권장 option: `NOT_CHECKED`, `PASS`, `WARNING`, `FAIL`
- `Validation Message`: `Rich text`
- `Import Status`: `Select`
  - 권장 option: `NOT_IMPORTED`, `PREVIEWED`, `COMMITTED`, `SKIPPED`
- `Imported At`: `Rich text`
- `Synced At`: `Rich text`

정책:

- `External Key`는 후속 importer가 안정적으로 dedupe하기 위해 필요하다
- `Validation *` 필드는 Python validation 결과를 Notion에 반영할 때 사용한다
- `Import *` 필드는 preview / commit 상태를 추적할 때 사용한다

## External Key Policy

권장 포맷:

- `manual_execution:{execution_date}:{symbol}:{side}:{sequence}`

예:

- `manual_execution:2026-05-25:GEN:BUY:01`

정책:

- 사용자가 직접 입력하지 않도록 하는 것이 권장된다
- Python importer가 정렬 규칙에 따라 생성하는 편이 안정적이다
- 같은 날짜 같은 종목 같은 방향에 여러 체결이 있을 수 있으므로 `sequence`가 필요하다
- partial fill은 별도 row로 유지하는 편이 추적과 검증에 유리하다

중복 방지:

- staging dedupe: `External Key`
- ledger dedupe: `trade_id`

## View Policy

사용자 요구사항:

- 메인 입력 화면에는 최소 필드만 보여야 한다
- 기술/검증 필드는 숨기고 별도 view에서 확인해야 한다

중요:

- Notion view에서 필드를 숨기는 것은 Python 코드 수정이 아니다
- 속성명/타입을 바꾸면 후속 Python importer, mapping, validator 수정이 필요하다

### View 1: `Input`

목적:

- 사용자가 실제 체결을 편하게 입력하는 기본 화면

표시 권장 필드:

- `Name`
- `Execution Date`
- `Symbol`
- `Side`
- `Quantity`
- `Actual Price`
- `Commission`
- `Note`
- `Status`

숨김 권장 필드:

- `External Key`
- `Plan Date`
- `Currency`
- `Broker`
- `Linked Daily Plan Key`
- `Validation Status`
- `Validation Message`
- `Import Status`
- `Imported At`
- `Synced At`

필터 권장:

- `Status != IMPORTED`

추가 권장:

- 정렬: `Execution Date desc`, 그 다음 `Name asc`

### View 2: `Validation`

목적:

- Python validation 이후 이상 row를 운영자가 확인하는 화면

표시 권장 필드:

- `Execution Date`
- `Symbol`
- `Side`
- `Quantity`
- `Actual Price`
- `Status`
- `Validation Status`
- `Validation Message`
- `Import Status`

필터 후보:

- `Validation Status = FAIL`
- 또는 `Validation Status = WARNING`

추가 권장:

- `Status = READY` 위주로 필터하면 운영성이 좋아진다

### View 3: `Technical`

목적:

- importer/debug/schema 확인용 전체 화면

표시 권장 필드:

- `Name`
- `External Key`
- `Execution Date`
- `Plan Date`
- `Symbol`
- `Side`
- `Quantity`
- `Actual Price`
- `Commission`
- `Currency`
- `Broker`
- `Linked Daily Plan Key`
- `Status`
- `Validation Status`
- `Validation Message`
- `Import Status`
- `Imported At`
- `Synced At`

정책:

- 메인 운영자가 아니라 검증/개발자/운영 점검용 화면이다

### View 4: `Committed`

목적:

- 이미 반영된 입력 이력을 확인하는 화면

필터 후보:

- `Import Status = COMMITTED`
- 또는 `Status = IMPORTED`

표시 권장 필드:

- `Execution Date`
- `Symbol`
- `Side`
- `Quantity`
- `Actual Price`
- `Status`
- `Import Status`
- `Imported At`
- `Note`

## Policy Decisions

이번 5B에서 확정하는 결정:

- 메인 입력 view는 최소 필드만 표시한다
- 기술/검증/import 필드는 숨기고 별도 view에서 확인한다
- `Commission / Currency / Broker`는 optional field로 유지한다
- 현재 ledger schema에 dedicated column이 없으므로 commit 반영 방식은 후속 MFU에서 결정한다
- `Daily Plan`에 없는 `Symbol`은 기본 `WARNING` 후보로 둔다
- `Quantity`는 Notion에서 절대값으로 입력하고, BUY/SELL 부호 반영은 Python importer가 담당한다
- `Status`는 사람 중심 운영 상태, `Import Status`는 시스템 import 상태로 역할을 분리한다

## Stability Requirements for Future Importer

후속 Python importer가 의존할 안정 계약:

- 속성명은 본 문서 기준으로 고정
- 타입도 본 문서 기준으로 고정
- `Side`, `Status`, `Validation Status`, `Import Status`의 select 성격 유지
- `External Key`는 `Rich text`
- `Validation Message`는 `Rich text`
- `Imported At`, `Synced At`는 `Rich text`

변경 영향:

- 속성명 변경 -> importer / validator / preview report 수정 필요
- 타입 변경 -> Notion parsing / validation 수정 필요
- select option 변경 -> validator / 운영 정책 수정 필요

## Out of Scope

- Notion `Manual Executions` DB 실제 생성
- Notion schema validation 구현
- Notion row read/import 구현
- validation engine 구현
- preview report 생성
- `paper_execution_log.csv` commit 구현
- Daily Review Summary export 구현
- Performance Summary export 구현
- 실제 Notion write
- paper 원장 CSV 수정
- `config/*.example` 수정
- Python 코드 수정

# PAPER15-NOTION-MAP: Notion Account ID Mapping

## 1. Purpose

이번 작업은 사용자가 Notion 주요 DB에 수동 추가한 `Account ID` property를 Python mapping / schema validation 계층에서 인식하도록 반영하는 것이다.

## 2. Scope / Non-scope

포함:
- `config/notion_property_mapping.example.json`에 `account_id` 추가
- schema validator가 `Account ID` property를 인식하고 누락을 report하도록 보강
- 관련 단위 테스트 보강

제외:
- `External Key` 생성 로직 변경
- exporter / importer / status sync 동작 변경
- Notion write / export / sync 실행
- 기존 row migration

## 3. User-side Notion Setup Completed

전제:
- 사용자가 주요 7개 Notion DB에 `Account ID` property를 수동 추가했다.
- property name은 `Account ID`다.
- type은 `Select` 기준이다.
- 초기 option은 `paper_default`다.

## 4. Mapping Changes

`account_id: "Account ID"`를 아래 section에 추가했다.

- `daily_plans`
- `manual_executions`
- `account_snapshots`
- `weekly_reports`
- `benchmark_reports`
- `daily_review_summaries`
- `manual_reviews`

기존 property 이름과 기존 `external_key` mapping은 바꾸지 않았다.

## 5. Schema Validation Policy

현재 정책:
- `Account ID`는 multi-account 전환용 권장 property로 인식한다.
- schema validator는 `Account ID`가 있으면 type/option을 확인한다.
- `Account ID`가 없으면 `FAIL`이 아니라 `WARNING`으로 report한다.

의도:
- 기존 사용자 환경과의 호환 유지
- 후속 단계에서 severity를 `REQUIRED/FAIL`로 올릴 수 있는 준비

## 6. Why External Key Logic Is Not Changed Yet

이번 단계는 mapping/schema 인식 단계다.

아직 하지 않는 것:
- `daily_plan:{account_id}:...` 같은 key namespace 적용
- exporter upsert key 변경
- importer canonical key 변경
- status sync payload 변경

이유:
- `Account ID` property를 mapping과 validator가 먼저 알아야 후속 구현이 안전하다.
- key namespace 변경은 별도 단계에서 exporter / importer / sync를 함께 바꿔야 한다.

## 7. Next Step

다음 단계 권장:
- `PAPER15-NOTION-KEY`

예상 범위:
- exporter external key namespace 구현
- manual execution / review canonical key account namespace 구현
- status sync payload account namespace 반영

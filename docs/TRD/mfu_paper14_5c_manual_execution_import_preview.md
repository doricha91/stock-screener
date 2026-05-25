# MFU-PAPER14-5C: Manual Executions Import Preview

## 1. 목적

이번 PAPER14-5C는 Notion `Manual Executions` DB에서 `Status=READY`인 row를 read-only로 읽고, Python에서 정규화/검증한 뒤 preview report를 생성하는 단계다.

- Notion = 입력 대기 / staging layer
- Python = 검증 / 정규화 / preview 생성 주체
- CSV / SQLite = 최종 source of truth

이번 PAPER14-5C는 Manual Executions read-only import + validation preview 작업이며, paper ledger commit, Daily Review Summary export, Notion status back-write는 수행하지 않는다.

## 2. 대상 설정

- data source key: `manual_executions`
- env override: `NOTION_MANUAL_EXECUTIONS_DATA_SOURCE_ID`
- config fallback:

```json
{
  "data_sources": {
    "manual_executions": ""
  }
}
```

## 3. schema validation

필수 속성:

- `Name` -> `title`
- `Execution Date` -> `date`
- `Symbol` -> `rich_text`
- `Side` -> `select`
- `Quantity` -> `number`
- `Actual Price` -> `number`
- `Status` -> `select`

선택/관리 속성:

- `External Key` -> `rich_text`
- `Plan Date` -> `date`
- `Commission` -> `number`
- `Currency` -> `select`
- `Broker` -> `select` 또는 `rich_text`
- `Note` -> `rich_text`
- `Linked Daily Plan Key` -> `rich_text`
- `Validation Status` -> `select`
- `Validation Message` -> `rich_text`
- `Import Status` -> `select`
- `Imported At` -> `rich_text`
- `Synced At` -> `rich_text`

정책:

- 속성 누락 / 타입 불일치 = `FAIL`
- select option 누락 = `WARNING`
- `manual_executions` data source id가 없으면 read-only validation은 `WARNING`으로 skip 가능

## 4. import 대상 정책

기본 preview 대상:

- `Execution Date = --date`
- `Status = READY`

즉 아래 상태는 preview candidate에서 제외된다.

- `DRAFT`
- `IMPORTED`
- `REJECTED`

## 5. normalization 정책

Notion row는 아래 internal candidate로 정규화된다.

- `Execution Date` -> `execution_date`
- `Plan Date` -> `plan_date`
- `Symbol` -> `symbol`, `upper().strip()`
- `Side` -> `side`, `BUY/SELL`
- `Quantity` -> 양수 정수
- `Actual Price` -> `actual_price`
- `Commission` -> 비어 있으면 `0` + `WARNING`
- `Currency` -> 비어 있으면 `USD` + `WARNING`
- `Broker` -> optional
- `Note` -> `note`
- `Linked Daily Plan Key` -> `linked_daily_plan_key`

SELL도 Notion 입력에서는 양수 수량으로 받고, signed shares 변환은 후속 commit 단계에서 처리한다.

## 6. validation 규칙

FAIL:

- `Execution Date` 없음
- `Symbol` 없음
- `Side`가 `BUY/SELL` 아님
- `Quantity <= 0`
- `Actual Price <= 0`
- 기존 `paper_execution_log.csv`와 prospective trade id 중복
- `SELL` 수량이 현재 보유수량 초과
- `BUY` 후 예상 현금 음수

WARNING:

- `Plan Date` 없음
- `Linked Daily Plan Key` 없음
- `Commission` 없음 -> `0` 정규화
- `Currency` 없음 -> `USD` 정규화
- `Broker` 없음

보류:

- Daily Plan 대비 종목/가격/수량 차이 비교는 이번 5C 구현 범위에서 제외했다.
- 관련 경고 규칙은 후속 MFU에서 추가 가능하다.

## 7. canonical key 정책

preview 내부 dedupe용 canonical key:

```text
manual_execution:{execution_date}:{symbol}:{side}:{sequence}
```

정렬 기준:

1. `Execution Date`
2. `Symbol`
3. `Side`
4. Notion `created_time` 또는 `page_id`

동일 날짜/종목/side 다중 체결은 `01`, `02` 순서로 sequence를 부여한다.

## 8. preview report

산출물:

- `outputs/paper_test/reports/manual_execution_import_preview_YYYYMMDD.json`
- `outputs/paper_test/reports/manual_execution_import_preview_YYYYMMDD.md`

포함 내용:

- candidate row count
- PASS / WARNING / FAIL count
- normalized rows
- validation messages
- projected cash impact
- projected position impact
- `commit_allowed`

`commit_allowed` 정책:

- FAIL 포함 -> `false`
- WARNING만 존재 -> `true_with_warnings`
- 전부 PASS -> `true`

## 9. CLI

지원:

```cmd
python scripts\import_notion_executions.py --date 2026-05-25 --preview
python scripts\import_notion_executions.py --date 2026-05-25 --preview --json
```

비지원:

```cmd
python scripts\import_notion_executions.py --date 2026-05-25 --commit
```

`--commit`은 `not implemented in PAPER14-5C`로 실패시킨다.

## 10. 기존 원장 연결

read-only 검증 입력:

- `outputs/paper_test/paper_execution_log.csv`
- `outputs/paper_test/paper_account_snapshot.csv`
- `outputs/paper_test/paper_position_snapshot.csv`

현재 5C에서는:

- 현금 부족 여부 확인
- 보유수량 초과 SELL 여부 확인
- prospective trade id 중복 여부 확인

만 수행한다.

원장 CSV는 수정하지 않는다.

## 11. 제외 범위

- paper ledger commit
- Notion status back-write
- Daily Review Summary export
- Performance Summary export
- Manual Review 입력 연동
- broker/API 연동
- 원장 CSV 수정

## 12. 남은 리스크

- `commission / currency / broker`는 현재 ledger dedicated column이 없어서 commit 저장 정책이 아직 없다.
- Daily Plan 대비 체결 편차 검증은 아직 없다.
- fractional quantity 입력은 현재 FAIL 처리한다.

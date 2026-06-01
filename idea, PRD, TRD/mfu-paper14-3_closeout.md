# MFU-PAPER14-3-closeout 작업 지시문

## 목적

MFU-PAPER14-3의 실제 Notion export 검증 결과를 문서화하고, Notion UI 표시 설정 및 각 속성 설명을 운영 참고 문서로 남긴다.

이번 작업은 PAPER14-3 마감 문서화 작업이다.

반드시 명시:

```text
이번 PAPER14-3-closeout은 Weekly / Benchmark / Account Snapshot Notion export 검증 결과와 Notion UI 표시 설정을 문서화하는 작업이며, page body 개선, 추가 export 구현, 실제 Notion write는 포함하지 않는다.
```

---

## 배경

PAPER14-3D에서 실제 Notion export 검증이 완료됐다.

확인된 결과:

```text
schema validation: PASS
dry-run 3종: 성공
1차 actual export: weekly / benchmark / account 모두 CREATED
2차 actual export: weekly / benchmark / account 모두 UPDATED
```

External Key:

```text
weekly_report:2026-05-09:2026-05-20
benchmark:2026-05-20:exploratory
account_snapshot:2026-05-20
```

사용자는 Notion UI에서 row 생성과 주요 property 표시를 확인했다.  
숫자 표시 형식은 Notion UI에서 조정했고, raw decimal 값이 percent 표시로 정상 변환되는 것을 확인했다.

예:

```text
0.6044888 → 60.44888%
```

---

## 구현 파일

추가 후보:

```text
docs/TRD/mfu_paper14_3d_actual_export_verification.md
```

수정 후보:

```text
docs/TRD/mfu_paper14_3b_notion_schema_contract.md
docs/TRD/mfu_paper14_3_notion_readonly_export.md
```

권장:

```text
1. 3D 검증 결과는 새 문서로 추가
2. 3B schema contract에는 UI 표시 설정과 속성 설명 보강
3. 기존 3_notion_readonly_export 문서는 필요할 때만 짧게 참조 추가
```

---

## 문서화 요구사항

### 1. Actual export 검증 결과 문서화

`docs/TRD/mfu_paper14_3d_actual_export_verification.md`에 아래를 정리한다.

```text
- 검증 일자
- 대상 data source
- schema validation 결과
- dry-run 결과
- 1차 actual export 결과
- 2차 actual export 결과
- External Key 목록
- CREATED / UPDATED 결과
- 중복 row 없음 판단 근거
- 실제 Notion UI 확인 결과
- 제외 범위
- 남은 리스크
```

### 2. Notion UI 표시 설정 문서화

`docs/TRD/mfu_paper14_3b_notion_schema_contract.md`에 아래를 추가한다.

공통 원칙:

```text
- exporter는 비율/수익률/MDD 값을 raw decimal Number로 보낸다.
- Notion UI에서는 해당 Number 속성을 Percent 표시로 설정한다.
- 금액 계열은 Dollar 또는 천 단위 숫자 표시로 설정한다.
- count 계열은 정수 표시로 설정한다.
- Synced At은 Date가 아니라 Rich text/Text 속성이다.
```

### 3. Weekly Reports 속성 설명

아래 속성별 설명과 표시 설정을 문서화한다.

```text
Name: report title
External Key: upsert key
Period Start / Period End: report coverage period
Latest Snapshot Date: latest snapshot included
Coverage Status: FULL / PARTIAL / EMPTY
Overall Status: PASS / PASS_WITH_WARNINGS / FAIL
Snapshot Count: integer
End Equity: account equity at period end, money display
Equity Change %: raw decimal, percent display
Cash Ratio: raw decimal, percent display
Trade Count: integer
Gap Count: integer
High Gap Count: integer
Markdown Path / JSON Path: source artifact path
Schema Version: source schema version
Synced At: exported timestamp as text
Sync Status: SYNCED
```

### 4. Benchmark Reports 속성 설명

```text
Name: benchmark report title
External Key: upsert key
Latest Snapshot Date: comparison date
Run Mode: EXPLORATORY / future official modes
Official Run: TRUE / FALSE select
Availability Status: AVAILABLE / INSUFFICIENT_DATA / UNKNOWN
Paper Return: raw decimal, percent display
SPY / QQQ / CASH Return: raw decimal, percent display
Excess vs SPY / QQQ / CASH: raw decimal, percent display
Paper MDD / SPY MDD / QQQ MDD: raw decimal, percent display
Markdown Path / JSON Path: source artifact path
Schema Version: source schema version
Synced At: exported timestamp as text
Sync Status: SYNCED
```

### 5. Account Snapshots 속성 설명

```text
Name: account snapshot title
External Key: upsert key
Snapshot Date: snapshot date
Initial Cash: money display
Cash: money display
Total Equity Market Value: money display
Total Equity Cost Basis: money display
Unrealized PnL: money display
Cash Ratio Market Value: raw decimal, percent display
Cash Ratio Cost Basis: raw decimal, percent display
Position Count: integer
Symbols: text, not multi-select
Valuation Status: SUCCESS / FAILED / NOT_RUN / UNKNOWN / PARTIAL
Valuation Price Date: date
Synced At: exported timestamp as text
Sync Status: SYNCED
```

---

## 제외 범위

이번 작업에서 하지 않는다.

```text
page body 개선
Markdown 전체 block 변환
Daily Plan export
Daily Review Summary export
Performance Summary export
Manual Review 입력 연동
Notion DB 자동 생성
schema migration
실제 Notion export/write
paper 원장 CSV 수정
outputs/front_test 수정
한글 경로 문서 수정/삭제
DB/PNG/output 파일 수정/삭제
```

---

## 검증 명령

문서 작업 후 코드 상태만 확인한다.

```cmd
cd /d D:\python\StockScreener
set PYTHONPATH=.

python -m pytest tests\test_notion_exporters.py tests\test_notion_settings.py tests\test_notion_mapping.py tests\test_notion_client.py tests\test_notion_schema_validator.py -q
```

선택적으로 read-only validation만 실행한다.

```cmd
python scripts\dev\validate_notion_schema.py --all --json
```

주의:

```text
export_paper_to_notion.py의 non-dry-run 명령은 실행하지 않는다.
```

---

## 커밋 정책

문서 변경만 커밋한다.

권장 stage:

```cmd
git add docs\TRD\mfu_paper14_3d_actual_export_verification.md
git add docs\TRD\mfu_paper14_3b_notion_schema_contract.md
```

필요 시에만:

```cmd
git add docs\TRD\mfu_paper14_3_notion_readonly_export.md
```

커밋 전 확인:

```cmd
git diff --cached --name-only
```

커밋 메시지:

```cmd
git commit -m "PAPER14-3D: document actual Notion export verification"
```

---

## 성공 기준

```text
PAPER14-3D actual export 결과가 문서화된다.
Notion UI 표시 설정이 문서화된다.
각 속성의 의미와 표시 형식이 문서화된다.
page body 개선은 하지 않는다.
실제 Notion export/write는 수행하지 않는다.
테스트 또는 read-only validation 결과가 보고된다.
문서 변경만 커밋된다.
```

---

## 결과 보고 형식

5천자 이내.

```text
1. Summary
2. 변경 파일
3. actual export 검증 결과 문서화 내용
4. Notion UI 표시 설정 문서화 내용
5. Weekly 속성 설명 추가 내용
6. Benchmark 속성 설명 추가 내용
7. Account Snapshot 속성 설명 추가 내용
8. page body 개선 미수행 확인
9. 실제 Notion export/write 미수행 확인
10. 테스트 또는 validation 결과
11. 커밋 hash와 message
12. paper 원장 CSV 변경 여부
13. outputs/front_test 변경 여부
14. 남은 리스크
15. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER14-3-closeout은 PAPER14-3 실제 export 검증 결과와 Notion UI 표시 설정을 문서화한 작업이며, page body 개선과 추가 export 구현은 수행하지 않았다.
```
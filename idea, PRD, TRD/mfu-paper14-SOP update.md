# MFU-PAPER14-SOP-update 작업 지시문

## 목적

PAPER14-3 완료 결과를 운영 SOP에 반영한다.

이번 작업의 목표는 기존 paper 운영 루프에 Notion export 절차를 추가하되, Notion을 source of truth가 아니라 presentation / review layer로 명확히 정의하는 것이다.

반드시 명시:

```text
Notion export는 CSV/JSON/Markdown/SQLite 원천 데이터를 대체하지 않는다.
Notion은 검토와 표시를 위한 presentation/review layer다.
```

---

## 배경

현재 paper 운영 루프는 아래 흐름이다.

```text
prepare → preview → commit → review → status
```

PAPER14-3에서 아래가 완료됐다.

```text
- Weekly Reports Notion export
- Benchmark Reports Notion export
- Account Snapshot Notion export
- Notion schema contract 문서화
- schema validation 구현
- actual export CREATED → UPDATED 검증
- Notion UI 표시 설정 문서화
```

검증 결과:

```text
schema validation: PASS
dry-run: 성공
1차 actual export: 3개 모두 CREATED
2차 actual export: 3개 모두 UPDATED
```

---

## 구현 파일

수정 대상:

```text
docs/operations/paper_daily_ops.md
```

참조 문서:

```text
docs/TRD/mfu_paper14_3b_notion_schema_contract.md
docs/TRD/mfu_paper14_3d_actual_export_verification.md
```

필요 시 새 문서 추가 가능:

```text
docs/operations/paper_notion_export_ops.md
```

단, 우선은 `paper_daily_ops.md` 업데이트를 기본으로 한다.

---

## SOP 반영 요구사항

### 1. Notion export 위치

기존 루프 뒤에 Notion export 단계를 추가한다.

```text
prepare → preview → commit → review → status → notion export
```

단, Notion export는 paper operation의 원천 데이터 생성 이후 실행한다.

### 2. Notion export 성격

아래 정책을 문서화한다.

```text
- Notion은 presentation/review layer다.
- source of truth는 CSV/JSON/Markdown/SQLite다.
- Notion export 실패는 paper ledger 실패가 아니다.
- 원천 데이터가 정상 생성되어 있으면 paper operation 자체는 유효하다.
- Notion export 실패는 별도 기록하고 다음 회차 전에 수정한다.
```

### 3. 실행 순서

SOP에 아래 순서를 명시한다.

```cmd
cd /d D:\python\StockScreener
set PYTHONPATH=.

python scripts\dev\validate_notion_schema.py --all --json

python scripts\export_paper_to_notion.py --weekly --dry-run --json
python scripts\export_paper_to_notion.py --benchmark --dry-run --json
python scripts\export_paper_to_notion.py --account-snapshot --dry-run --json

python scripts\export_paper_to_notion.py --weekly --json
python scripts\export_paper_to_notion.py --benchmark --json
python scripts\export_paper_to_notion.py --account-snapshot --json
```

정책:

```text
- schema validation에서 FAIL이 있으면 actual export 금지
- dry-run 실패 시 actual export 금지
- actual export는 --all이 아니라 개별 실행
- 개별 실행 순서: weekly → benchmark → account-snapshot
```

### 4. 성공 기준

아래를 SOP에 추가한다.

```text
- schema validation 결과가 PASS 또는 WARNING
- dry-run 3종 성공
- actual export 3종 성공
- 동일 External Key 기준으로 중복 row가 생기지 않음
- Notion UI에서 주요 property가 표시됨
```

### 5. 실패 대응

아래를 문서화한다.

```text
schema validation FAIL:
- Notion DB 속성명/타입/select 설정을 수정한다.
- actual export를 실행하지 않는다.

dry-run 실패:
- source JSON/CSV/Markdown 경로와 mapping을 확인한다.
- actual export를 실행하지 않는다.

actual export 실패:
- Notion token, data source id, integration 권한을 확인한다.
- 원천 데이터는 수정하지 않는다.
- 실패 내용을 운영 로그나 작업 보고에 남긴다.
```

### 6. 제외 범위

SOP에 아직 포함하지 않는다.

```text
Daily Plan export
Daily Review Summary export
Performance Summary export
Manual Review 입력 연동
Notion DB 자동 생성
Notion schema migration
page body 개선
```

---

## 보안 요구사항

아래를 SOP에 명시하거나 확인한다.

```text
NOTION_TOKEN은 .env 또는 환경변수로만 관리
실제 data source id는 config/notion_settings.json 또는 .env에만 보관
config/notion_settings.json은 gitignore 대상
config/notion_property_mapping.json은 gitignore 대상
토큰과 실제 data source id를 로그/문서에 노출하지 않음
```

---

## 검증 명령

문서 수정 후 아래를 실행한다.

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
이번 SOP 업데이트 작업에서는 actual export를 다시 실행하지 않는다.
```

---

## 커밋 정책

문서 변경만 커밋한다.

권장 stage:

```cmd
git add docs\operations\paper_daily_ops.md
```

새 문서를 추가한 경우에만:

```cmd
git add docs\operations\paper_notion_export_ops.md
```

커밋 전 확인:

```cmd
git diff --cached --name-only
```

커밋 메시지:

```cmd
git commit -m "PAPER14: document Notion export operations SOP"
```

---

## 금지 사항

```text
코드 수정 금지
실제 Notion export/write 금지
paper 원장 CSV 수정 금지
outputs/front_test 수정 금지
DB/PNG/output 파일 수정/삭제 금지
한글 경로 문서 수정/삭제 금지
git add . 금지
git add -A 금지
git reset --hard 금지
git clean -fd 금지
```

---

## 성공 기준

```text
paper_daily_ops.md에 Notion export 운영 절차가 반영된다.
Notion이 source of truth가 아니라 presentation/review layer임이 명시된다.
schema validation → dry-run → actual export 순서가 문서화된다.
실패 대응 정책이 문서화된다.
Daily Plan / Daily Review / Performance Summary / Manual Review는 제외된다.
문서 변경만 커밋된다.
```

---

## 결과 보고 형식

5천자 이내.

```text
1. Summary
2. 변경 파일
3. SOP에 추가한 Notion export 위치
4. source of truth 정책 반영 여부
5. 실행 명령 추가 내용
6. 실패 대응 정책
7. 제외 범위
8. 테스트 또는 validation 결과
9. 실제 Notion export/write 미수행 확인
10. 커밋 hash와 message
11. paper 원장 CSV 변경 여부
12. outputs/front_test 변경 여부
13. 남은 리스크
14. 다음 단계 제안
```

반드시 명시:

```text
이번 작업은 PAPER14 Notion export 운영 SOP 문서화이며, 실제 Notion export/write와 코드 수정은 수행하지 않았다.
```
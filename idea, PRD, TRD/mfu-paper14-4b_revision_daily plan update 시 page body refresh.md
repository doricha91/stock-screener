# MFU-PAPER14-4B_revision 작업 지시문: Daily Plan update 시 page body refresh

## 목적

MFU-PAPER14-4B_revision의 목표는 기존 Daily Plan Notion page가 update될 때도 page body가 최신 Daily Plan Markdown 기준으로 갱신되도록 수정하는 것이다.

이번 정책:

```text
Daily Plan page body는 exporter-managed 영역으로 간주한다.
사용자는 Daily Plan page body에 수동 메모를 남기지 않는다.
수동 메모는 후속 Daily Review / Manual Review에서 다룬다.
```

반드시 명시:

```text
이번 PAPER14-4B_revision은 Daily Plan updated path에서 page body를 refresh하는 작업이며, Daily Review Summary, Performance Summary, Manual Review 입력 연동은 수행하지 않는다.
```

---

## 배경

PAPER14-4B에서 Daily Plan page body 개선이 구현됐다.

page body 구조:

```text
오늘의 운영 요약
확정 거래
검토 필요 항목
경고
원천 파일
```

하지만 실제 실행 결과:

```cmd
python scripts\export_paper_to_notion.py --daily-plan --json
```

결과는 `action=updated`였고, Notion page body는 이전 내용과 동일했다.

추정 원인:

```text
create path에서는 children/body가 들어가지만,
update path에서는 properties만 update되고 page body children은 갱신되지 않는다.
```

---

## 구현 파일

수정 후보:

```text
core/notion_client.py
core/notion_exporters.py
tests/test_notion_client.py
tests/test_notion_exporters.py
docs/TRD/mfu_paper14_4_daily_plan_notion_export.md
```

필요 시 추가:

```text
docs/TRD/mfu_paper14_4b_revision_daily_plan_body_refresh.md
```

---

## 구현 전 확인

먼저 실제 코드 흐름을 확인한다.

```text
1. upsert_page_by_external_key()의 create path에서 children/body가 어떻게 처리되는지
2. update path에서 children/body가 무시되는지
3. NotionClient가 page body children 삭제/교체/append 기능을 이미 지원하는지
4. Notion API에서 page body를 교체할 수 있는 안전한 방식
```

중요:

```text
추측으로 구현하지 말고 현재 NotionClient 구조를 먼저 확인한다.
```

---

## 동작 정책

### 1. Daily Plan page body는 exporter-managed

Daily Plans에 한해서 아래 정책을 적용한다.

```text
- Daily Plan page body는 시스템이 생성한 최신 계획 본문이다.
- export를 다시 실행하면 page body는 최신 source markdown 기준으로 재생성된다.
- 사용자가 page body에 직접 쓴 메모는 보존 대상이 아니다.
- 사용자 메모는 후속 Daily Review / Manual Review에서 다룬다.
```

### 2. update 시 body refresh

Daily Plan upsert에서 기존 page를 update할 때:

```text
1. 기존 properties 업데이트
2. 기존 page body를 제거 또는 비움
3. 최신 Daily Plan body blocks를 다시 append
```

단, 아래는 지켜야 한다.

```text
- Weekly / Benchmark / Account Snapshot update 동작을 깨지 않는다.
- body refresh는 우선 Daily Plan에만 적용한다.
- 기존 page body 제거는 Daily Plan에만 허용한다.
```

### 3. 구현 방식

가능하면 NotionClient에 명시적인 함수로 구현한다.

후보 함수명:

```python
replace_page_children(page_id: str, children: list[dict]) -> None
```

또는:

```python
refresh_page_body(page_id: str, children: list[dict]) -> None
```

정책:

```text
- token 값 로그 출력 금지
- 삭제/교체 실패 시 명확한 error 반환
- body refresh 실패 시 export 결과를 실패로 보고
```

---

## CLI 정책

기존 명령을 그대로 사용한다.

```cmd
python scripts\export_paper_to_notion.py --daily-plan --dry-run --json
python scripts\export_paper_to_notion.py --daily-plan --json
```

dry-run에서는 실제 body 삭제/append를 하지 않는다.

actual export에서만 update path body refresh를 수행한다.

---

## 테스트 요구사항

추가/수정 테스트:

```text
tests/test_notion_client.py
tests/test_notion_exporters.py
```

검증할 것:

```text
1. Daily Plan create path에서 body children이 포함된다.
2. Daily Plan update path에서 body refresh가 호출된다.
3. dry-run에서는 body refresh가 호출되지 않는다.
4. Weekly / Benchmark / Account Snapshot update path는 기존 동작을 유지한다.
5. body refresh 실패 시 명확히 실패로 처리한다.
6. Daily Review / Performance / Manual Review 기능은 추가되지 않는다.
```

mock 기반으로 검증하고, 실제 Notion write는 사용자가 허용한 경우에만 수행한다.

---

## 검증 명령

Windows CMD 기준:

```cmd
cd /d D:\python\StockScreener
set PYTHONPATH=.

python -m py_compile core\notion_client.py
python -m py_compile core\notion_exporters.py
python -m py_compile scripts\export_paper_to_notion.py

python -m pytest tests\test_notion_client.py tests\test_notion_exporters.py tests\test_notion_settings.py tests\test_notion_mapping.py tests\test_notion_schema_validator.py -q

python scripts\export_paper_to_notion.py --daily-plan --dry-run --json
```

Daily Plans data source id가 설정되어 있고 사용자가 허용한 경우에만 actual export를 실행한다.

```cmd
python scripts\dev\validate_notion_schema.py --daily-plan
python scripts\export_paper_to_notion.py --daily-plan --json
python scripts\export_paper_to_notion.py --daily-plan --json
```

기대:

```text
1차: updated 또는 created
2차: updated
Notion UI에서 Daily Plan page body가 개선된 구조로 갱신됨
```

---

## 금지 사항

```text
Daily Review Summary export 구현 금지
Performance Summary export 구현 금지
Manual Review 입력 연동 금지
신규 DB 추가 금지
Daily Plan DB property 대량 추가 금지
Notion DB 자동 생성 금지
Notion schema migration 금지
Weekly / Benchmark / Account body 동작 임의 변경 금지
원천 Markdown/JSON 수정 금지
paper 원장 CSV 수정 금지
outputs/front_test 수정 금지
DB/PNG/output 파일 수정/삭제 금지
한글 경로 문서 수정/삭제 금지
git add . 금지
git add -A 금지
```

---

## 문서화

아래 문서를 업데이트한다.

```text
docs/TRD/mfu_paper14_4_daily_plan_notion_export.md
```

추가할 내용:

```text
- Daily Plan page body는 exporter-managed라는 정책
- update 시 page body refresh 정책
- 사용자 메모는 Daily Review / Manual Review로 분리한다는 원칙
- dry-run에서는 body refresh를 수행하지 않는다는 점
- 남은 리스크
```

---

## 커밋 정책

권장 commit message:

```cmd
git commit -m "PAPER14-4B: refresh Daily Plan page body on update"
```

커밋 전 확인:

```cmd
git diff --cached --name-only
```

보호 대상, output, DB, 한글 경로 문서가 포함되면 커밋하지 않는다.

---

## 성공 기준

```text
Daily Plan update path에서 page body가 최신 내용으로 refresh된다.
dry-run은 실제 body 변경을 하지 않는다.
Daily Plan page body는 exporter-managed 정책으로 문서화된다.
Weekly / Benchmark / Account Snapshot export 동작은 깨지지 않는다.
테스트가 통과한다.
실제 export를 수행한 경우 Notion UI에서 body 변경이 확인된다.
Daily Review / Performance / Manual Review는 구현하지 않는다.
```

---

## 결과 보고 형식

5천자 이내.

```text
1. Summary
2. 변경 파일
3. 원인 확인 결과
4. NotionClient 변경 내용
5. Daily Plan update body refresh 구현 내용
6. dry-run 동작
7. actual export 수행 여부
8. Notion UI 확인 결과
9. 테스트 결과
10. 제외 범위 준수 여부
11. 커밋 hash와 message
12. 남은 리스크
13. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER14-4B_revision은 Daily Plan updated path에서 page body를 refresh하는 작업이며, Daily Review Summary, Performance Summary, Manual Review 입력 연동은 수행하지 않았다.
```
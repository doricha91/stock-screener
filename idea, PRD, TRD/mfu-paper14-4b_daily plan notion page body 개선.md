# MFU-PAPER14-4B 작업 지시문: Daily Plan Notion page body 개선

## 목적

MFU-PAPER14-4B의 목표는 Daily Plan Notion row의 page body를 사람이 읽기 좋은 운영 계획 형태로 개선하는 것이다.

이번 작업은 DB property 확장이 아니라 page body 개선이다.

반드시 명시:

이번 PAPER14-4B는 Daily Plan page body enrichment 작업이며, Daily Review Summary, Performance Summary, Manual Review 입력 연동, 신규 DB 추가는 포함하지 않는다.

---

## 배경

PAPER14-4에서 Daily Plan Notion export가 구현됐다.

현재 Daily Plan source artifact:

- Markdown: outputs/paper_test/daily_action_plan_YYYYMMDD.md
- Config snapshot JSON: outputs/paper_test/config_snapshots/paper_config_snapshot_YYYYMMDD.json

현재 Notion property에는 아래 요약값이 들어간다.

- Plan Date
- Regime
- Confirmed Trade Count
- Review Item Count
- Warning Count
- Markdown Path
- JSON Path
- Schema Version
- Synced At
- Sync Status

하지만 현재 page body는 요약 count 중심이라, Notion만 보고 “오늘 실제로 무엇을 해야 하는지” 판단하기 어렵다.

---

## 구현 파일

수정 후보:

- core/notion_exporters.py
- tests/test_notion_exporters.py
- docs/TRD/mfu_paper14_4_daily_plan_notion_export.md

필요 시 추가 후보:

- core/daily_plan_markdown_parser.py
- tests/test_daily_plan_markdown_parser.py

단, 불필요한 파일 증가는 피한다. 기존 exporter 안에서 작게 처리 가능하면 우선 기존 파일에 구현한다.

---

## 구현 전 조사

먼저 실제 Markdown 구조를 확인한다.

조사 대상:

- outputs/paper_test/daily_action_plan_*.md
- outputs/paper_test/config_snapshots/paper_config_snapshot_*.json
- core/notion_exporters.py
- tests/test_notion_exporters.py

확인할 섹션:

- 확정 거래 섹션
- 검토 필요 항목 섹션
- 경고 섹션
- 시장 상태 또는 운영 요약 섹션

PAPER14-4에서 count를 산출하던 기준 섹션도 함께 확인한다.

- confirmed_trade_count: Markdown `## 4.` 테이블 row 수
- review_item_count: Markdown `## 4-0.` 테이블 row 수
- warning_count: Markdown `## 4-0-1.` 테이블 row 수

중요:

Markdown 섹션명이나 표 구조를 추측하지 말고, 실제 파일을 읽고 파싱 기준을 정한다.

---

## Page body 요구사항

Daily Plan page body는 아래 구조를 목표로 한다.

```text
## 오늘의 운영 요약

- Plan Date: ...
- Regime: ...
- Confirmed Trades: ...
- Review Items: ...
- Warnings: ...

## 확정 거래

원천 Markdown의 확정 거래 테이블을 사람이 읽기 좋은 형태로 표시한다.

## 검토 필요 항목

원천 Markdown의 검토 필요 항목 테이블을 사람이 읽기 좋은 형태로 표시한다.

## 경고

원천 Markdown의 경고 테이블을 사람이 읽기 좋은 형태로 표시한다.

## 원천 파일

- Markdown Path: ...
- JSON Path: ...
```

Notion API block 지원 범위가 제한되면, 표를 완전한 Notion table로 만들지 말고 bullet 또는 plain text block으로 표현해도 된다.

우선순위:

1. 내용 누락 없이 읽기 쉽게 표시
2. 실패하지 않는 안정성
3. Notion table 고도화는 후순위

---

## 파싱 정책

Markdown 파싱은 보수적으로 구현한다.

정책:

- 섹션을 찾지 못해도 export 전체를 실패시키지 않는다.
- 섹션 파싱 실패 시 WARNING 성격의 fallback body를 만든다.
- 최소 summary는 항상 들어가야 한다.
- 원천 Markdown 파일은 수정하지 않는다.
- 원천 JSON 파일은 수정하지 않는다.

fallback 예시:

```text
Confirmed trades section could not be parsed.
See source markdown path: ...
```

---

## DB property 정책

이번 4B에서는 Daily Plans DB property를 대량 추가하지 않는다.

유지:

- Plan Date
- Regime
- Confirmed Trade Count
- Review Item Count
- Warning Count
- Markdown Path
- JSON Path
- Schema Version
- Synced At
- Sync Status

추가 금지 또는 보류:

- 종목별 상세 property
- 거래별 상세 property
- 별도 Trade Items DB
- 별도 Warning Items DB

원칙:

Property = 필터/정렬용 요약  
Page body = 사람이 읽는 상세 내용

---

## CLI 정책

기존 명령을 그대로 사용한다.

```cmd
python scripts\export_paper_to_notion.py --daily-plan --dry-run --json
python scripts\export_paper_to_notion.py --daily-plan --json
```

dry-run 결과에서도 page body 생성 요약이 확인 가능하면 좋다.

단, actual export는 사용자가 명시적으로 허용한 경우에만 실행한다.

---

## 테스트 요구사항

추가/수정 테스트:

- tests/test_notion_exporters.py
- 필요 시 tests/test_daily_plan_markdown_parser.py

검증할 것:

1. Daily Plan page body에 운영 요약이 포함된다.
2. 확정 거래 섹션이 있으면 body에 포함된다.
3. 검토 필요 항목 섹션이 있으면 body에 포함된다.
4. 경고 섹션이 있으면 body에 포함된다.
5. 섹션이 없어도 export payload 생성은 실패하지 않는다.
6. Markdown path / JSON path가 하단에 포함된다.
7. 기존 weekly/benchmark/account export 테스트가 깨지지 않는다.
8. Daily Review / Performance / Manual Review는 추가되지 않는다.

---

## 검증 명령

Windows CMD 기준:

```cmd
cd /d D:\python\StockScreener
set PYTHONPATH=.

python -m py_compile core\notion_exporters.py
python -m py_compile scripts\export_paper_to_notion.py

python -m pytest tests\test_notion_exporters.py tests\test_notion_settings.py tests\test_notion_mapping.py tests\test_notion_client.py tests\test_notion_schema_validator.py -q

python scripts\export_paper_to_notion.py --daily-plan --dry-run --json
```

Daily Plans data source가 설정되어 있고 사용자가 허용한 경우에만 actual export 검증을 실행한다.

```cmd
python scripts\dev\validate_notion_schema.py --daily-plan
python scripts\export_paper_to_notion.py --daily-plan --json
python scripts\export_paper_to_notion.py --daily-plan --json
```

기대:

- 1차: created 또는 updated
- 2차: updated

---

## 금지 사항

- Daily Review Summary export 구현 금지
- Performance Summary export 구현 금지
- Manual Review 입력 연동 금지
- Notion DB 자동 생성 금지
- Notion schema migration 금지
- 신규 Trade Items DB 생성 금지
- Daily Plan 원천 Markdown 구조 변경 금지
- paper 원장 CSV 수정 금지
- outputs/front_test 수정 금지
- DB/PNG/output 파일 수정/삭제 금지
- 한글 경로 문서 수정/삭제 금지
- git add . 금지
- git add -A 금지

---

## 문서화

아래 문서를 업데이트한다.

- docs/TRD/mfu_paper14_4_daily_plan_notion_export.md

추가할 내용:

- 4B page body 개선 목적
- Markdown 파싱 기준
- fallback 정책
- DB property를 늘리지 않는 이유
- page body 구성
- 제외 범위
- 테스트 결과
- 남은 리스크

---

## 커밋 정책

권장 commit message:

```cmd
git commit -m "PAPER14-4B: improve Daily Plan Notion page body"
```

커밋 전 확인:

```cmd
git diff --cached --name-only
```

지정 파일 외 보호 대상, output, DB, 한글 경로 문서가 포함되면 커밋하지 않는다.

---

## 성공 기준

- Daily Plan page body가 운영 요약 / 확정 거래 / 검토 항목 / 경고 / 원천 파일 섹션을 포함한다.
- DB property는 과도하게 늘어나지 않는다.
- Markdown 섹션 파싱 실패 시에도 안전하게 fallback된다.
- --daily-plan --dry-run --json이 성공한다.
- 기존 PAPER14 export 테스트가 깨지지 않는다.
- 실제 export를 수행한 경우 2차 실행에서 updated가 확인된다.
- Daily Review / Performance / Manual Review는 구현하지 않는다.

---

## 결과 보고 형식

5천자 이내.

1. Summary
2. 변경 파일
3. Daily Plan Markdown 구조 조사 결과
4. page body 개선 내용
5. 확정 거래 표시 방식
6. 검토 필요 항목 표시 방식
7. 경고 표시 방식
8. fallback 정책
9. DB property 추가 여부
10. dry-run 결과
11. actual export 수행 여부
12. 테스트 결과
13. 제외 범위 준수 여부
14. 커밋 hash와 message
15. 남은 리스크
16. 다음 단계 제안

반드시 명시:

이번 PAPER14-4B는 Daily Plan page body enrichment 작업이며, Daily Review Summary, Performance Summary, Manual Review 입력 연동은 수행하지 않았다.
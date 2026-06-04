BEGIN MFU-PAPER19-5-DAILY-PLAN-JSON-SIDECAR-PRODUCER

# PAPER19-5 Daily Plan JSON Sidecar Producer Minimal Implementation

## 목적

Daily Plan 생성 시 기존 Markdown 산출물은 유지하면서, 같은 구조화 데이터에서 `paper_daily_plan.v1` JSON sidecar를 함께 생성하는 최소 구현을 한다.

이번 작업의 핵심은 “Markdown을 JSON으로 파싱”하는 것이 아니라, `generate_daily_plan()` 내부의 기존 구조화 데이터에서 Markdown과 JSON을 병행 생성하는 것이다.

## 배경

PAPER19-4 확인 결과:

- official Daily Plan CLI는 `scripts/run_paper_daily_plan.py`
- 핵심 생성 함수는 `core.daily_plan_generator.generate_daily_plan()`
- 현재 공식 산출물은 `daily_action_plan_YYYYMMDD.md` 중심
- `paper_config_snapshot_YYYYMMDD.json`은 config snapshot이며 Daily Plan action JSON이 아님
- `generate_daily_plan()` 내부에는 Markdown 렌더링 전 `action_items`, `rebalance_review_items`, `warning_items`, `journal_rows` 등 구조화 dict/list가 존재함
- 아직 stable normalized Daily Plan JSON object/schema는 없음

## 구현 원칙

반드시 지킨다.

```text
기존 daily_action_plan_YYYYMMDD.md 파일명과 출력 내용은 변경하지 않는다.
기존 paper_config_snapshot_YYYYMMDD.json 의미는 변경하지 않는다.
Notion 관련 파일, mapping, export/sync 코드는 수정하지 않는다.
Notion API/write/export/sync를 실행하지 않는다.
outputs/paper 원장을 수정하지 않는다.
JSON sidecar는 기존 Markdown을 대체하지 않고 추가 산출물로만 생성한다.
```

## 대상 파일 후보

필요한 파일만 최소 수정한다.

```text
core/daily_plan_generator.py
scripts/run_paper_daily_plan.py
tests/test_daily_plan_json_sidecar.py
docs/TRD/mfu_paper19_daily_plan_json_sidecar_producer.md
```

기존 테스트 위치/파일명이 더 적절하면 맞춰 사용한다.

## 구현 요구사항

### 1. JSON sidecar schema

JSON schema version:

```text
paper_daily_plan.v1
```

필수 필드:

```json
{
  "schema_version": "paper_daily_plan.v1",
  "account_id": "paper_sandbox",
  "plan_date": "2026-05-20",
  "run_mode": "exploratory",
  "official_run": false,
  "generated_at": "...",
  "items": [],
  "fingerprints": {}
}
```

`items[]`는 기존 `action_items`를 normalize한다.

기본 매핑:

```text
type   -> action
shares -> quantity
price  -> price
symbol -> symbol
warning -> warning
reason -> reason
note -> note
```

필드가 없으면 `null` 또는 생략하되, 테스트에서 일관되게 검증한다.

### 2. Markdown과 JSON shared source

반드시 같은 내부 구조화 데이터에서 Markdown과 JSON을 생성한다.

금지:

```text
Markdown 생성 후 Markdown을 다시 파싱해 JSON 생성
Markdown 출력 형식 변경
JSON 생성을 위해 trading/plan 판단 로직 변경
```

### 3. CLI / output 정책

기존 Daily Plan Markdown output은 유지한다.

JSON sidecar 파일명 후보:

```text
daily_action_plan_YYYYMMDD.json
```

기존 repo convention이 더 적절하면 사용하되, `paper_config_snapshot_YYYYMMDD.json`과 혼동되면 안 된다.

테스트와 smoke는 반드시 `tmp_path` 또는 임시 output 경로를 사용한다. 실제 운영 outputs를 오염시키지 않는다.

### 4. run_mode / official_run 전달 확인

`run_mode`, `official_run`, `account_id`, `plan_date`가 generator boundary에서 안정적으로 JSON에 들어가는지 확인한다.

불명확하면 임의 추측하지 말고 최소 변경으로 전달 경로를 명확히 하고 문서에 남긴다.

## 테스트 요구사항

테스트를 추가한다.

필수 검증:

```text
Markdown 산출물은 기존처럼 생성됨
JSON sidecar도 함께 생성됨
JSON schema_version = paper_daily_plan.v1
account_id / plan_date / run_mode / official_run 포함
action_items의 type/shares/price가 action/quantity/price로 normalize됨
warning/reason/note가 있으면 JSON에 반영됨
paper_config_snapshot_YYYYMMDD.json 의미를 변경하지 않음
Markdown 내용을 JSON 생성 때문에 변경하지 않음
Notion API 호출 없음
Notion write/export/sync 없음
테스트는 tmp_path 사용
```

가능하면 기존 Markdown 문자열을 생성 전후 비교하는 회귀 테스트를 넣는다. 기존 fixture가 없으면 새 테스트에서 “JSON sidecar 추가가 Markdown rendering output을 바꾸지 않음”을 최소 검증한다.

## 문서 작성

생성 문서:

```text
docs/TRD/mfu_paper19_daily_plan_json_sidecar_producer.md
```

포함 섹션:

1. Purpose
2. Scope
3. Implemented JSON Schema
4. Markdown Compatibility
5. Field Normalization
6. Output Path Policy
7. run_mode / official_run Handling
8. Test Coverage
9. Notion / Export Safety
10. Limitations
11. PAPER19-6 Recommendation

## 검증 명령

Windows CMD 기준:

```cmd
git status --short

python scripts\run_paper_daily_plan.py --help

pytest tests\test_daily_plan_json_sidecar.py

git diff --check -- core\daily_plan_generator.py scripts\run_paper_daily_plan.py tests\test_daily_plan_json_sidecar.py docs\TRD\mfu_paper19_daily_plan_json_sidecar_producer.md
```

기존 Daily Plan 관련 테스트가 있다면 함께 실행한다.

## 구현 후 자체 점검 항목

Codex는 결과 보고에 아래를 반드시 포함한다.

```text
- 기존 Markdown 파일명/출력 변경 여부
- JSON sidecar 파일명/경로
- paper_config_snapshot_YYYYMMDD.json 의미 변경 여부
- type/shares/price -> action/quantity/price normalize 확인
- run_mode/official_run 전달 확인
- Notion 관련 파일 수정 여부
- Notion API/write/export/sync 실행 여부
- outputs/paper 원장 변경 여부
- 테스트가 실제 outputs를 오염시키지 않았는지
- git diff --check 결과
- blocker / non-blocking 개선점
```

## Non-scope

이번 작업에서는 절대 하지 않는다.

```text
Daily Plan 전략 로직 변경
Markdown 포맷 변경
Markdown parser 구현
PAPER19 diff core 변경
replay wrapper 구현
Notion API 호출
Notion write/export/sync
actual export
outputs/paper 원장 수정
실제 운영 Daily Plan 생성 실행
schema/view drift
Telegram/Slack/Email 전송
```

## Git 주의사항

금지:

```cmd
git add .
git add -A
```

절대 stage 금지:

```text
.env
config/notion_settings.json
secret 포함 파일
outputs/backtest_log.db
backtest_log.db
analysis_results/*.png
idea, PRD, TRD/*
unrelated local artifacts
```

## 커밋 정책

자체 점검에서 blocker가 없고 테스트가 통과하면 실제 수정/생성 파일만 개별 stage한다.

예상 후보:

```cmd
git add core\daily_plan_generator.py
git add scripts\run_paper_daily_plan.py
git add tests\test_daily_plan_json_sidecar.py
git add docs\TRD\mfu_paper19_daily_plan_json_sidecar_producer.md
```

실제 수정하지 않은 파일은 stage하지 않는다.

커밋 메시지:

```cmd
git commit -m "feat: add PAPER19 daily plan JSON sidecar"
```

## 성공 기준

- 기존 Markdown Daily Plan 출력이 유지됨
- Daily Plan JSON sidecar가 생성됨
- `paper_daily_plan.v1` schema가 적용됨
- `action_items`가 diff contract에 맞게 normalize됨
- `run_mode` / `official_run`이 JSON에 포함됨
- `paper_config_snapshot` 의미가 변경되지 않음
- Notion/API/write/export/sync 없음
- outputs/paper 원장 변경 없음
- 테스트 통과
- git diff --check 통과
- 커밋 완료

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 생성/수정한 파일
3. JSON sidecar 구현 요약
4. 기존 Markdown 영향 여부
5. JSON schema / 필드 요약
6. action_items normalization 요약
7. run_mode / official_run 처리
8. paper_config_snapshot 영향 여부
9. 테스트 결과
10. Notion API/write/export/sync 실행 여부
11. outputs/paper 원장 변경 여부
12. 자체 점검 결과
13. git diff --check 결과
14. 커밋 생성 여부
15. 커밋 SHA / 메시지
16. 제외한 unrelated 파일
17. 남은 리스크
18. PAPER19-6 추천 작업

END MFU-PAPER19-5-DAILY-PLAN-JSON-SIDECAR-PRODUCER
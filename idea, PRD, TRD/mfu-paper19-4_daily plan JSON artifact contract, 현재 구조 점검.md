BEGIN MFU-PAPER19-4-DAILY-PLAN-JSON-ARTIFACT-CONTRACT-AND-GENERATION-STRUCTURE-CHECK

# PAPER19-4 Daily Plan JSON Artifact Contract + 현재 생성 구조 점검

## 목적

PAPER19-4에서는 Daily Plan을 Markdown만 유지할지, JSON artifact를 병행 생성할지 판단하기 위해 현재 Daily Plan 생성 구조를 점검하고, JSON 병행 생성 시 필요한 artifact contract를 문서화한다.

이번 작업은 설계/점검 전용이다.

중요:
- 코드 구현하지 않는다.
- Daily Plan 생성 명령을 실제 실행하지 않는다.
- JSON producer를 아직 만들지 않는다.
- Notion API/write/export/sync 실행하지 않는다.
- outputs/paper 원장 수정하지 않는다.

## 배경

PAPER19-2에서 Daily Plan JSON 두 개를 비교하는 diff core/CLI가 구현됐다.

PAPER19-3에서 확인된 핵심 리스크:

- 현재 repo는 `daily_action_plan_YYYYMMDD.md` 중심이다.
- 공식 baseline JSON producer가 아직 없다.
- 향후 replay/diff를 안정적으로 운영하려면 structured JSON artifact가 필요할 수 있다.
- 단, JSON producer 구현 전 현재 Daily Plan 생성 코드가 구조화된 plan data를 이미 갖고 있는지 확인해야 한다.

사용자 판단:
- Markdown raw diff만으로는 장기적으로 취약하다.
- C안, 즉 Daily Plan 생성 시 Markdown + JSON 병행 생성을 검토한다.
- 단, 바로 구현하지 말고 작업량/구조를 먼저 점검한다.

## 생성 파일

```cmd
docs\TRD\mfu_paper19_daily_plan_json_artifact_contract_and_generation_structure_check.md
```

## 참고/조사 명령

아래를 실행해 Daily Plan 생성 구조를 찾는다.

```cmd
git status --short

findstr /S /N /I "daily_action_plan daily plan Daily Plan plan markdown md json action_items actions rows recommended" docs\*.md docs\TRD\*.md docs\operations\*.md scripts\*.py scripts\dev\*.py core\*.py

findstr /S /N /I "paper.py plan daily_ops plan --dry-run reports" scripts\*.py scripts\dev\*.py core\*.py
```

필요하면 관련 파일을 `type`으로 확인한다.

## 문서 필수 섹션

1. Purpose
2. Current Daily Plan Generation Structure
3. Markdown-only Diff Assessment
4. JSON Artifact Contract
5. Markdown + JSON Shared Source Principle
6. Baseline / Regenerated JSON Policy
7. Proposed Output Paths
8. Required Fields
9. Optional Fields / Fingerprints
10. Implementation Options and Estimated Work
11. Risks
12. Non-scope
13. PAPER19-5 Recommendation

## 점검 요구사항

### 1. 현재 생성 구조 확인

다음을 확인해 문서화한다.

```text
- Daily Plan Markdown을 생성하는 파일/함수/CLI
- 내부에서 action item list 같은 구조화 데이터가 이미 존재하는지
- 아니면 Markdown 문자열을 직접 조립하는지
- account_id/date/official_run/run_mode가 어디서 전달되는지
- 현재 JSON 출력이 이미 있는지
```

구조를 확정할 수 없으면 “needs follow-up inspection”으로 명시한다. 추측 금지.

### 2. Markdown-only diff 평가

Markdown만 비교하는 방식의 장단점을 정리한다.

반드시 포함:

```text
장점:
- 기존 artifact를 그대로 사용
- 추가 JSON producer 불필요
- 단기 작업량 작음

단점:
- 표/문구/공백 변경에 취약
- symbol/action/quantity/price 추출 안정성 낮음
- replay/diff, alert, wrapper 확장에 불리
```

결론은 강제하지 말고, 현재 구조 점검 결과에 따라 판단한다.

### 3. JSON Artifact Contract 설계

Daily Plan JSON artifact 후보 schema를 정의한다.

필수 필드 후보:

```json
{
  "schema_version": "paper_daily_plan.v1",
  "account_id": "paper_sandbox",
  "plan_date": "2026-05-20",
  "run_mode": "exploratory",
  "official_run": false,
  "generated_at": "...",
  "items": [
    {
      "symbol": "AAPL",
      "action": "BUY",
      "quantity": 10,
      "price": 200.0,
      "warning": null,
      "reason": "...",
      "note": "..."
    }
  ],
  "fingerprints": {
    "config_hash": "...",
    "universe_hash": "...",
    "state_snapshot_hash": "...",
    "market_data_asof": "...",
    "code_commit_sha": "..."
  }
}
```

없는 필드는 optional로 둔다.

### 4. Shared Source Principle

반드시 명시한다.

```text
Markdown을 만든 뒤 JSON으로 파싱하면 안 된다.
동일한 normalized Daily Plan object에서 Markdown과 JSON을 동시에 생성해야 한다.
```

이 원칙이 깨지면 Markdown과 JSON 불일치 위험이 생긴다.

### 5. baseline / regenerated 정책

정리할 것:

```text
baseline JSON = official/committed Daily Plan artifact
regenerated JSON = replay/diff용 dry-run regenerated artifact
regenerated는 baseline을 절대 덮어쓰지 않음
```

후보 경로:

```text
outputs/paper_accounts/{account_id}/plans/daily_plan_{YYYYMMDD}.json
outputs/paper_accounts/{account_id}/replay_diff/runs/{run_id}/regenerated_daily_plan.json
```

실제 repo convention이 다르면 후보로만 기록한다.

### 6. 작업량 추정

현재 생성 구조에 따라 작업량을 추정한다.

```text
A. 이미 구조화된 plan data가 있음
→ JSON producer 구현은 비교적 작음

B. Markdown 문자열 중심
→ normalized plan object 도입 또는 리팩토링 필요
→ 작업량 증가
```

대략 MFU 수로 추정한다.

## Non-scope

이번 작업에서는 절대 하지 않는다.

```text
Python 코드 수정
JSON producer 구현
Daily Plan 생성 실행
paper.py plan 실행
replay wrapper 구현
Notion API 호출
Notion write/export/sync
actual export
outputs/paper 원장 수정
실제 운영 artifact 수정
```

## 검증 명령

```cmd
type docs\TRD\mfu_paper19_daily_plan_json_artifact_contract_and_generation_structure_check.md

findstr /N /I "Daily Plan JSON Markdown normalized artifact baseline regenerated schema_version fingerprints shared source" docs\TRD\mfu_paper19_daily_plan_json_artifact_contract_and_generation_structure_check.md

git diff --check -- docs\TRD\mfu_paper19_daily_plan_json_artifact_contract_and_generation_structure_check.md
```

## 구현 후 자체 점검 항목

Codex는 문서 작성 후 아래를 확인하고 결과 보고에 포함한다.

```text
- Daily Plan 생성 위치를 확인했는가
- 구조화된 plan data 존재 여부를 확인했는가
- Markdown-only diff의 장단점을 균형 있게 적었는가
- JSON artifact contract가 PAPER19-2 diff input과 호환되는가
- Markdown+JSON shared source principle을 명시했는가
- baseline/regenerated가 명확히 구분됐는가
- 구현 없이 문서만 작성했는가
- Notion/API/write/export/sync가 없었는가
- outputs/paper 원장 변경이 없었는가
- git diff --check가 통과했는가
```

blocker가 있으면 커밋하지 말고 보고한다.  
blocker가 없으면 문서만 커밋한다.

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

```cmd
git add docs\TRD\mfu_paper19_daily_plan_json_artifact_contract_and_generation_structure_check.md

git diff --cached --name-only
git diff --cached

git commit -m "docs: define PAPER19 daily plan JSON artifact contract"

git log -1 --stat
git status --short
```

## 성공 기준

- 현재 Daily Plan 생성 구조가 조사됨
- Markdown-only diff 평가가 정리됨
- JSON artifact contract가 정의됨
- Markdown + JSON shared source principle이 명시됨
- baseline/regenerated JSON 정책이 정리됨
- 구현 옵션별 작업량이 정리됨
- 코드 변경 없음
- Daily Plan 생성 실행 없음
- Notion/API/write/export/sync 없음
- outputs/paper 원장 변경 없음
- 문서 커밋 완료

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 생성/수정한 파일
3. 현재 Daily Plan 생성 구조 확인 결과
4. 구조화된 plan data 존재 여부
5. Markdown-only diff 평가
6. JSON artifact contract 요약
7. shared source principle 반영 여부
8. baseline/regenerated JSON 정책
9. 예상 작업량
10. 코드 변경 여부
11. Daily Plan 생성 실행 여부
12. Notion API/write/export/sync 실행 여부
13. outputs/paper 원장 변경 여부
14. 자체 점검 결과
15. git diff --check 결과
16. 커밋 생성 여부
17. 커밋 SHA / 메시지
18. 제외한 unrelated 파일
19. 남은 리스크
20. PAPER19-5 추천 작업

END MFU-PAPER19-4-DAILY-PLAN-JSON-ARTIFACT-CONTRACT-AND-GENERATION-STRUCTURE-CHECK
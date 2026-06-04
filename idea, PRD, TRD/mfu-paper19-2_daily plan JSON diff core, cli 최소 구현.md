BEGIN MFU-PAPER19-2-DAILY-PLAN-JSON-DIFF-CORE

# PAPER19-2 PAPER19-1 커밋 + Daily Plan JSON Diff Core / CLI 최소 구현

## 목적

먼저 PAPER19-1 설계 문서를 커밋한다.

그 다음 PAPER19-2로 baseline Daily Plan JSON과 regenerated Daily Plan JSON 두 파일을 비교해 JSON/Markdown diff report를 생성하는 최소 core/CLI를 구현한다.

이번 작업은 pure comparison / dry-run 성격이다.

절대 하지 말 것:

- Daily Plan 자동 재생성
- replay 실행
- Notion API 호출
- Notion write/export/sync
- actual export
- outputs/paper 원장 수정
- execution/review replay
- schema/view drift 구현

## 배경

PAPER19-1에서 정한 기본 방향:

- 초기 범위는 단일 account_id / 단일 date의 Daily Plan diff
- baseline_plan = official 또는 committed Daily Plan artifact
- regenerated_plan = 같은 account/date로 다시 생성된 별도 artifact
- PAPER19-2는 우선 두 JSON 파일 비교만 구현
- 원인 확정 금지, fingerprint 기반 원인 후보만 표시
- price 비교는 초기 exact 비교
- metadata-only diff는 `PASS_WITH_METADATA_DIFF`로 처리
- 기본 row key는 `symbol + action`
- 중복 row key는 임의 매칭하지 않고 WARNING으로 표시

## 1단계: PAPER19-1 문서 커밋

### 대상 파일

```cmd
docs\TRD\mfu_paper19_replay_same_date_diff_scope_and_contract.md
```

### 검증

```cmd
git status --short
git diff --check -- docs\TRD\mfu_paper19_replay_same_date_diff_scope_and_contract.md
```

### stage / commit

금지:

```cmd
git add .
git add -A
```

실행:

```cmd
git add docs\TRD\mfu_paper19_replay_same_date_diff_scope_and_contract.md

git diff --cached --name-only
git diff --cached

git commit -m "docs: define PAPER19 replay same-date diff scope"

git log -1 --stat
git status --short
```

이미 같은 문서가 커밋되어 있으면 새 커밋을 만들지 말고 보고한다.

## 2단계: Daily Plan JSON Diff Core 구현

## 생성/수정 후보 파일

```text
core/paper_replay_diff.py
scripts/dev/diff_daily_plan.py
tests/test_paper_replay_diff.py
docs/TRD/mfu_paper19_daily_plan_json_diff_core.md
```

기존 naming convention에 더 맞는 파일명이 있으면 조정 가능하다.

## CLI 요구사항

권장 명령:

```cmd
python scripts\dev\diff_daily_plan.py --account-id paper_sandbox --date 2026-05-20 --baseline-plan <path> --regenerated-plan <path> --output-dir <path> --json
```

지원 옵션:

```text
--account-id
--date
--baseline-plan
--regenerated-plan
--output-dir
--json
```

초기에는 account/date/source-root 자동 탐색을 하지 않는다.  
명시 파일 입력만 지원한다.

## 비교 요구사항

초기 핵심 비교 필드:

```text
symbol
action
quantity
price
warning
reason
note
```

있으면 비교 후보:

```text
cash_impact
allocation
target_weight
stop_price
```

없는 필드는 조용히 무시하되, 문서에 optional field로 기록한다.

## row identity 정책

기본 row key:

```text
symbol + action
```

정책:

```text
동일 symbol/action이 중복되지 않으면 해당 key로 비교
baseline에만 있는 row → SYMBOL_SET_DIFF
regenerated에만 있는 row → SYMBOL_SET_DIFF
동일 key 양쪽 존재 → 필드 비교
중복 symbol/action 발생 → DUPLICATE_ROW_KEY WARNING
```

중복 key를 임의 순서로 매칭하지 않는다.

## diff category

최소 category:

```text
NO_DIFF
METADATA_DIFF
WARNING_DIFF
PRICE_DIFF
QUANTITY_DIFF
ACTION_DIFF
SYMBOL_SET_DIFF
DUPLICATE_ROW_KEY
CONFIG_OR_UNIVERSE_DIFF
STATE_OR_MARKET_FINGERPRINT_DIFF
MALFORMED_INPUT
ACCOUNT_DATE_MISMATCH
MISSING_INPUT
```

## overall status 정책

```text
PASS:
- 핵심 필드 차이 없음

PASS_WITH_METADATA_DIFF:
- generated_at, report_id, path 같은 metadata만 다름

WARNING:
- price 차이
- warning/reason/note 차이
- fingerprint-only 차이
- duplicate row key

FAIL:
- missing/malformed input
- account/date mismatch
- symbol set 차이
- action 차이
- quantity 차이
```

여러 diff가 있으면 가장 심한 상태를 overall_status로 둔다.

## fingerprint / cause candidate 정책

다음 값을 있으면 비교한다.

```text
config_hash
universe_hash
state_snapshot_hash
state_snapshot_path
market_data_asof
indicator_snapshot_hash
code_commit_sha
generator_version
```

정책:

- full snapshot을 report에 복사하지 않는다.
- fingerprint가 다르면 cause_candidate로 기록한다.
- 원인을 단정하지 않는다.

표현 예:

```text
quantity changed.
config_hash also changed.
Config change is a possible cause candidate.
```

금지 표현:

```text
quantity changed because config changed.
```

## 출력 정책

기본 output 경로:

```text
outputs/paper_accounts/{account_id}/replay_diff/paper_daily_plan_diff_{YYYYMMDD}.json
outputs/paper_accounts/{account_id}/replay_diff/paper_daily_plan_diff_{YYYYMMDD}.md
```

테스트와 smoke는 반드시 `--output-dir` 또는 `tmp_path`를 사용한다.  
실제 outputs 계좌 경로를 테스트에서 오염시키지 않는다.

JSON envelope 후보:

```json
{
  "schema_version": "paper_daily_plan_replay_diff.v1",
  "account_id": "paper_sandbox",
  "plan_date": "2026-05-20",
  "overall_status": "WARNING",
  "summary": {},
  "diffs": [],
  "fingerprint_diffs": [],
  "cause_candidates": [],
  "write_executed": false
}
```

Markdown 구조:

```text
# Daily Plan Replay Diff - {account_id} - {date}

## Summary
## Failures
## Warnings
## Metadata / Fingerprint Differences
## Cause Candidates
## Input Files
## Safety Notes
```

## 테스트 요구사항

`tests/test_paper_replay_diff.py`를 생성한다.

필수 테스트:

```text
same plan → PASS / NO_DIFF
metadata only diff → PASS_WITH_METADATA_DIFF
symbol 추가/삭제 → FAIL / SYMBOL_SET_DIFF
action 변경 → FAIL / ACTION_DIFF
quantity 변경 → FAIL / QUANTITY_DIFF
price 변경 → WARNING / PRICE_DIFF
warning/reason 변경 → WARNING / WARNING_DIFF
config_hash 변경 → cause candidate 기록
universe_hash 변경 → cause candidate 기록
account/date mismatch → FAIL
malformed JSON → FAIL / MALFORMED_INPUT
missing input → FAIL / MISSING_INPUT
duplicate symbol/action key → WARNING / DUPLICATE_ROW_KEY
JSON report 생성
Markdown report 생성
tmp_path output-dir 사용
write_executed=false
Notion API 호출 없음
```

테스트는 fixture JSON을 사용한다. 실제 운영 plan 파일을 수정하지 않는다.

## 문서 작성

생성 문서:

```text
docs/TRD/mfu_paper19_daily_plan_json_diff_core.md
```

포함 섹션:

1. Purpose
2. Scope
3. CLI
4. Input Contract
5. Row Identity Policy
6. Diff Categories
7. PASS / WARNING / FAIL Policy
8. Fingerprint / Cause Candidate Policy
9. JSON / Markdown Output
10. Test Coverage
11. Limitations
12. PAPER19-3 Recommendation

반드시 명시:

- Daily Plan 자동 재생성 없음
- 두 JSON 파일 비교만 수행
- 원인 단정 금지
- Notion/API/write/export/sync 없음
- outputs/paper 원장 변경 없음

## 검증 명령

Windows CMD 기준:

```cmd
git status --short

python scripts\dev\diff_daily_plan.py --help

pytest tests\test_paper_replay_diff.py

type docs\TRD\mfu_paper19_daily_plan_json_diff_core.md

findstr /N /I "Daily Plan Replay Diff baseline regenerated symbol action quantity price warning fingerprint PASS WARNING FAIL" docs\TRD\mfu_paper19_daily_plan_json_diff_core.md

git diff --check -- core\paper_replay_diff.py scripts\dev\diff_daily_plan.py tests\test_paper_replay_diff.py docs\TRD\mfu_paper19_daily_plan_json_diff_core.md
```

## 구현 후 자체 점검 항목

Codex는 구현 후 아래를 확인하고 결과 보고에 포함한다.

### Diff 정책 점검

- same plan이 PASS로 처리되는가
- metadata-only diff가 PASS_WITH_METADATA_DIFF로 처리되는가
- symbol/action/quantity diff가 FAIL로 처리되는가
- price/warning/reason diff가 WARNING으로 처리되는가
- duplicate row key를 임의 매칭하지 않는가
- 가장 심한 diff가 overall_status에 반영되는가

### Fingerprint 점검

- config/universe/state/market/code fingerprint 차이가 cause_candidate로 기록되는가
- 원인을 단정하는 표현이 없는가
- full snapshot을 report에 복사하지 않는가

### Safety 점검

- Daily Plan 재생성을 실행하지 않는가
- Notion API 호출이 없는가
- Notion write/export/sync가 없는가
- outputs/paper 원장 변경이 없는가
- 테스트가 실제 outputs 경로를 오염시키지 않는가
- write_executed=false가 유지되는가

### Git 점검

- unrelated 파일이 staged 되지 않았는가
- `.env`, `config/notion_settings.json`, outputs/backtest_log.db 등이 staged 되지 않았는가
- git diff --check가 통과했는가

blocker가 있으면 커밋하지 말고 보고한다.  
blocker가 없고 테스트가 통과하면 PAPER19-2 결과를 커밋한다.

## Non-scope

이번 작업에서는 절대 하지 않는다.

```text
Daily Plan 자동 재생성
paper.py plan 실행
replay 실행
Notion API 호출
Notion write/export/sync
actual export
outputs/paper 원장 수정
실제 운영 plan 파일 수정
execution/review replay
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
git add core\paper_replay_diff.py
git add scripts\dev\diff_daily_plan.py
git add tests\test_paper_replay_diff.py
git add docs\TRD\mfu_paper19_daily_plan_json_diff_core.md
```

커밋 메시지:

```cmd
git commit -m "feat: add PAPER19 daily plan replay diff core"
```

커밋 후 확인:

```cmd
git log -1 --stat
git status --short
```

## 성공 기준

- PAPER19-1 설계 문서가 커밋됨
- Daily Plan JSON diff core가 구현됨
- CLI가 baseline/regenerated JSON을 비교함
- JSON/Markdown diff report 생성 가능
- PASS/WARNING/FAIL 정책 구현
- fingerprint cause candidate 기록
- 테스트 통과
- Notion/API/write/export/sync 없음
- outputs/paper 원장 변경 없음
- blocker 없으면 PAPER19-2 커밋 완료

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. PAPER19-1 커밋 생성 여부
3. PAPER19-1 커밋 SHA / 메시지
4. 생성/수정한 파일
5. CLI 요약
6. input contract 요약
7. row identity 정책
8. diff category / status 정책
9. fingerprint / cause candidate 정책
10. JSON/Markdown output 요약
11. 테스트 결과
12. Notion API 호출 여부
13. Notion write/export/sync 실행 여부
14. outputs/paper 원장 변경 여부
15. 자체 점검 결과
16. git diff --check 결과
17. PAPER19-2 커밋 생성 여부
18. PAPER19-2 커밋 SHA / 메시지
19. 제외한 unrelated 파일
20. 남은 리스크
21. PAPER19-3 추천 작업

END MFU-PAPER19-2-DAILY-PLAN-JSON-DIFF-CORE
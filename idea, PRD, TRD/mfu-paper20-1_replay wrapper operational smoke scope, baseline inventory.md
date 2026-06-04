BEGIN MFU-PAPER20-1-REPLAY-WRAPPER-OPERATIONAL-SMOKE-SCOPE

# PAPER20-1 Replay Wrapper Operational Smoke Scope / Baseline Inventory

## 목적

PAPER20-1에서는 PAPER19에서 구현한 Replay Wrapper를 실제 운영에 가까운 조건에서 smoke 하기 전에, 사용할 baseline sidecar 후보와 실행 범위를 점검하고 문서화한다.

이번 작업은 조사/설계 전용이다.

절대 하지 말 것:
- replay wrapper 실행
- Daily Plan 생성 실행
- Notion API 호출
- Notion write/export/sync
- actual export
- outputs/paper 원장 수정
- generated artifact 커밋

## 배경

PAPER19는 closeout 완료됐다.

완료된 최소 체인:

```text
Daily Plan JSON diff core/CLI
→ paper_daily_plan.v1 sidecar producer
→ sidecar replay diff smoke
→ minimal fingerprints
→ paper_config_hash.v1 helper/populate
→ replay wrapper minimal dry-run
```

PAPER20의 목적은 기능 확장이 아니라, 실제 paper_sandbox baseline sidecar로 replay wrapper를 안전하게 smoke하고, 운영자가 결과를 해석할 수 있는 runbook을 만드는 것이다.

PAPER20-1은 실제 smoke 전 준비 단계다.

## 생성 파일

```cmd
docs\TRD\mfu_paper20_replay_wrapper_operational_smoke_scope.md
```

## 조사 대상

아래를 확인한다.

```cmd
git status --short

dir outputs /S /B | findstr /I "daily_action_plan_.*\.json"
dir outputs /S /B | findstr /I "paper_daily_plan_diff"
dir outputs /S /B | findstr /I "replay_diff"
dir outputs /S /B | findstr /I "paper_config_snapshot"

python scripts\dev\replay_daily_plan_diff.py --help
python scripts\dev\diff_daily_plan.py --help
```

필요하면 관련 문서를 확인한다.

```cmd
type docs\TRD\mfu_paper19_replay_same_date_diff_closeout.md
type docs\TRD\mfu_paper19_daily_plan_replay_wrapper_minimal.md
```

파일이 없으면 없는 것으로 문서화한다. 추측하지 않는다.

## 문서 필수 섹션

1. Purpose
2. Scope
3. Current PAPER19 Replay Chain
4. Baseline Sidecar Inventory
5. Baseline Eligibility Criteria
6. Proposed Smoke Date / Account
7. Explicit --output-dir Policy
8. Smoke Command Draft
9. Safety Policy
10. Expected PASS / WARNING / FAIL Interpretation
11. Non-scope
12. PAPER20-2 Recommendation

## 점검 요구사항

### 1. Baseline sidecar inventory

paper_sandbox 기준으로 사용할 수 있는 baseline sidecar 후보를 찾는다.

후보 파일 예:

```text
daily_action_plan_YYYYMMDD.json
```

각 후보에 대해 가능한 범위에서 확인한다.

```text
- file path
- account_id
- plan_date
- schema_version = paper_daily_plan.v1 여부
- run_mode
- official_run
- items 개수
- fingerprints 존재 여부
- config_hash 존재 여부
- config_hash_policy 존재 여부
```

주의:
- 실제 파일 내용을 대량 복사하지 않는다.
- 민감하거나 긴 path는 필요 시 축약한다.
- 후보가 없으면 “no eligible baseline sidecar found”로 기록한다.

### 2. Baseline eligibility criteria

PAPER20-2 smoke에 사용할 baseline 조건을 정의한다.

추천 기준:

```text
- account_id = paper_sandbox
- schema_version = paper_daily_plan.v1
- plan_date가 명확함
- items[]가 존재함
- generated artifact가 임시 테스트 fixture가 아님
- 가능하면 official 또는 committed Daily Plan sidecar
- config_hash/config_hash_policy가 있으면 우선
```

### 3. Proposed smoke date / account

후보가 있으면 PAPER20-2에서 사용할 account/date를 제안한다.

```text
account_id = paper_sandbox
date = 후보 sidecar의 plan_date
baseline_plan = 후보 sidecar path
```

후보가 여러 개면 가장 최근 정상 sidecar를 우선하되, 이유를 문서화한다.

### 4. Explicit --output-dir policy

반드시 명시한다.

```text
PAPER20-2에서는 --output-dir을 반드시 명시한다.
초기 smoke에서 --output-dir 생략 금지.
```

추천 경로 후보:

```text
outputs/paper_accounts/paper_sandbox/replay_diff_smoke/PAPER20_YYYYMMDD/
```

또는 더 안전한 임시 경로:

```text
outputs/tmp_paper20_replay_smoke/
```

단, smoke 산출물은 기본적으로 커밋하지 않는다.

### 5. Smoke command draft

PAPER20-2에서 실행할 명령 초안을 작성한다.

예:

```cmd
python scripts\dev\replay_daily_plan_diff.py --account-id paper_sandbox --date YYYY-MM-DD --baseline-plan <baseline_sidecar_path> --output-dir <explicit_output_dir> --json
```

이번 PAPER20-1에서는 실행하지 않는다.

### 6. Safety policy

반드시 포함한다.

```text
- replay wrapper는 dry-run 검증용이다.
- baseline sidecar는 덮어쓰지 않는다.
- official Daily Plan artifact를 덮어쓰지 않는다.
- Notion API/write/export/sync 없음.
- actual/export/sync/commit/append 없음.
- outputs/paper 원장 변경 없음.
- smoke 산출물은 기본적으로 커밋하지 않는다.
```

## Non-scope

이번 작업에서는 절대 하지 않는다.

```text
replay wrapper 실행
Daily Plan 생성 실행
actual export
Notion API 호출
Notion write/export/sync
outputs/paper 원장 수정
generated smoke artifact 커밋
stable plan_item_id 구현
universe_hash 구현
market_data_asof 구현
indicator_snapshot_hash 구현
state_snapshot_hash 구현
runbook 최종 작성
```

## 검증 명령

Windows CMD 기준:

```cmd
git status --short

type docs\TRD\mfu_paper20_replay_wrapper_operational_smoke_scope.md

findstr /N /I "PAPER20 replay wrapper operational smoke baseline sidecar paper_sandbox output-dir PASS WARNING FAIL Notion" docs\TRD\mfu_paper20_replay_wrapper_operational_smoke_scope.md

git diff --check -- docs\TRD\mfu_paper20_replay_wrapper_operational_smoke_scope.md
```

## 자체 점검 항목

Codex는 결과 보고에 아래를 포함한다.

```text
- baseline sidecar 후보를 확인했는가
- 후보가 없다면 없다고 명확히 기록했는가
- account_id/date/schema_version/items/fingerprints를 가능한 범위에서 확인했는가
- PAPER20-2 smoke에 사용할 후보 account/date/path를 제안했는가
- --output-dir 명시 정책을 포함했는가
- smoke command draft를 작성했는가
- replay wrapper를 실행하지 않았는가
- Daily Plan 생성을 실행하지 않았는가
- Notion/API/write/export/sync가 없었는가
- outputs/paper 원장 변경이 없었는가
- 코드 변경 없이 문서만 작성했는가
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
outputs/paper_accounts/*
outputs/tmp*
replay smoke generated artifacts
idea, PRD, TRD/*
unrelated local artifacts
```

주의:
- 이번 작업에서 생성한 문서만 stage한다.
- smoke 산출물이나 outputs 파일은 절대 stage하지 않는다.

## 커밋 정책

```cmd
git add docs\TRD\mfu_paper20_replay_wrapper_operational_smoke_scope.md

git diff --cached --name-only
git diff --cached

git commit -m "docs: define PAPER20 replay wrapper smoke scope"

git log -1 --stat
git status --short
```

## 성공 기준

- PAPER20-1 scope 문서가 생성됨
- baseline sidecar inventory가 정리됨
- smoke에 사용할 account/date/path 후보가 제안됨
- --output-dir 명시 정책이 정리됨
- PAPER20-2 smoke command draft가 작성됨
- replay wrapper 실행 없음
- Daily Plan 생성 실행 없음
- Notion/API/write/export/sync 없음
- outputs/paper 원장 변경 없음
- generated artifact stage 없음
- 문서 커밋 완료

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 생성/수정한 파일
3. baseline sidecar inventory 요약
4. eligible baseline 후보 여부
5. 제안 smoke account/date/path
6. --output-dir 정책
7. PAPER20-2 smoke command draft
8. replay wrapper 실행 여부
9. Daily Plan 생성 실행 여부
10. Notion API/write/export/sync 실행 여부
11. outputs/paper 원장 변경 여부
12. generated artifact stage 여부
13. 자체 점검 결과
14. git diff --check 결과
15. 커밋 생성 여부
16. 커밋 SHA / 메시지
17. 제외한 unrelated 파일
18. 남은 리스크
19. PAPER20-2 추천 작업

END MFU-PAPER20-1-REPLAY-WRAPPER-OPERATIONAL-SMOKE-SCOPE
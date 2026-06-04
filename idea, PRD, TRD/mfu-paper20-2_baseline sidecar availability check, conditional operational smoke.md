BEGIN MFU-PAPER20-2-BASELINE-SIDECAR-CHECK-AND-CONDITIONAL-OPERATIONAL-SMOKE

# PAPER20-2 Baseline Sidecar Availability Check + Conditional Operational Smoke

## 목적

PAPER20-2에서는 PAPER20-1에서 확인한 blocker를 재점검한 뒤, eligible paper_sandbox Daily Plan JSON sidecar가 있으면 replay wrapper operational smoke를 실행한다.

sidecar가 없으면 replay wrapper를 실행하지 않고 blocker 문서만 작성한다.

이번 작업은 조건부 smoke 작업이다.

핵심 원칙:

```text
eligible baseline sidecar 있음  → explicit --output-dir로 replay wrapper smoke 실행
eligible baseline sidecar 없음  → smoke 실행 금지, blocker 문서화
```

## 배경

PAPER20-1 결과:

- `outputs/**/daily_action_plan_*.json` 검색 결과 없음
- `outputs/paper_accounts/paper_sandbox/daily_action_plan_20260520.md`는 존재
- `outputs/paper_accounts/paper_sandbox/daily_action_plan_20260520.json`은 없음
- `paper_config_snapshot_20260520.json`, `paper_current_state_20260520.json`, `replay_diff/` 디렉터리는 존재
- 추천 account/date 후보는 `paper_sandbox / 2026-05-20`
- 단, baseline sidecar가 없으면 PAPER20-2 smoke는 실행하면 안 됨

## 생성 파일

```cmd
docs\TRD\mfu_paper20_baseline_sidecar_check_and_operational_smoke.md
```

## 1단계: Baseline sidecar availability 재확인

먼저 아래를 실행한다.

```cmd
git status --short

dir outputs /S /B | findstr /I "daily_action_plan_.*\.json"
dir outputs /S /B | findstr /I "daily_action_plan_20260520.json"
dir outputs /S /B | findstr /I "paper_config_snapshot_20260520.json"
dir outputs /S /B | findstr /I "paper_current_state_20260520.json"

python scripts\dev\replay_daily_plan_diff.py --help
python scripts\dev\diff_daily_plan.py --help
```

후보 sidecar가 있으면 내용을 최소 확인한다.

확인 항목:

```text
schema_version = paper_daily_plan.v1
account_id = paper_sandbox
plan_date = 2026-05-20 또는 명확한 날짜
items[] 존재
fingerprints 존재
config_hash / config_hash_policy 존재 여부
generated artifact가 unit-test fixture가 아닌지
```

민감하거나 긴 내용을 문서에 대량 복사하지 않는다.

## 2단계: 조건부 분기

### A. eligible baseline sidecar가 없을 경우

아래를 지킨다.

```text
- replay wrapper 실행 금지
- Daily Plan 생성 실행 금지
- sidecar 생성 시도 금지
- Notion/API/write/export/sync 금지
- outputs/paper 원장 변경 금지
```

문서에는 다음을 기록한다.

```text
- no eligible baseline sidecar found
- missing expected path
- smoke not executed
- blocker reason
- recommended next step: baseline sidecar creation/approval task
```

이 경우에도 문서만 커밋한다.

### B. eligible baseline sidecar가 있을 경우

명시 `--output-dir`로만 smoke를 실행한다.

권장 output dir:

```text
outputs/tmp_paper20_replay_smoke/
```

예상 명령:

```cmd
python scripts\dev\replay_daily_plan_diff.py --account-id paper_sandbox --date 2026-05-20 --baseline-plan outputs\paper_accounts\paper_sandbox\daily_action_plan_20260520.json --output-dir outputs\tmp_paper20_replay_smoke --json
```

주의:

```text
--output-dir 생략 금지
generated smoke artifact 커밋 금지
baseline/official artifact overwrite 금지
```

## Smoke 실행 시 확인 항목

eligible sidecar가 있어서 smoke를 실행한 경우, 아래를 확인한다.

```text
- wrapper exit code
- generated run_id
- regenerated Markdown path
- regenerated JSON sidecar path
- generated config snapshot path
- diff JSON report path
- diff Markdown report path
- overall_status: PASS / WARNING / FAIL
- write_executed=false
- actual_executed=false
- notion_api_called=false
- notion_sync_executed=false
- notion_write_export_sync_executed=false
- commit_append_executed=false
- baseline file overwrite 없음
- official Daily Plan artifact overwrite 없음
```

WARNING/FAIL이 나오면 즉시 수정하지 말고 문서에 원인 후보와 다음 MFU 후보로 기록한다.

## 문서 필수 섹션

생성 문서:

```cmd
docs\TRD\mfu_paper20_baseline_sidecar_check_and_operational_smoke.md
```

필수 섹션:

1. Purpose
2. PAPER20-1 Baseline Blocker Recap
3. Baseline Sidecar Re-check
4. Eligibility Decision
5. Conditional Smoke Execution
6. Output-dir Policy
7. Smoke Result
8. PASS / WARNING / FAIL Interpretation
9. Safety Verification
10. Generated Artifact Policy
11. Non-scope
12. PAPER20-3 Recommendation

## PASS / WARNING / FAIL 해석

문서에 아래를 포함한다.

```text
PASS:
- compared Daily Plan fields match
- operational replay smoke usable for read-only validation

WARNING:
- price/warning/reason/note/fingerprint/config_hash 차이
- 원인 후보는 있으나 확정 아님
- 실제 운영 반영 전 수동 검토 필요

FAIL:
- baseline missing/malformed
- account/date mismatch
- symbol/action/quantity 차이
- replay wrapper smoke 실패
```

PASS여도 actual/export/sync가 허용되는 것은 아니라고 명시한다.

## Non-scope

이번 작업에서는 절대 하지 않는다.

```text
eligible sidecar가 없을 때 sidecar 생성
Daily Plan 생성 실행
official artifact 재생성
Notion API 호출
Notion write/export/sync
actual export
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

문서 작성 후 실행한다.

```cmd
type docs\TRD\mfu_paper20_baseline_sidecar_check_and_operational_smoke.md

findstr /N /I "PAPER20 baseline sidecar eligible blocker smoke output-dir PASS WARNING FAIL write_executed Notion" docs\TRD\mfu_paper20_baseline_sidecar_check_and_operational_smoke.md

git diff --check -- docs\TRD\mfu_paper20_baseline_sidecar_check_and_operational_smoke.md
```

smoke를 실행한 경우, 생성 artifact는 status에서 확인하되 stage하지 않는다.

```cmd
git status --short
```

## 자체 점검 항목

Codex는 결과 보고에 아래를 포함한다.

```text
- eligible baseline sidecar 존재 여부
- smoke 실행 여부
- sidecar가 없을 경우 smoke를 실행하지 않았는가
- smoke를 실행했다면 explicit --output-dir을 사용했는가
- generated artifacts를 stage하지 않았는가
- baseline/official artifact overwrite가 없었는가
- Notion/API/write/export/sync가 없었는가
- outputs/paper 원장 변경이 없었는가
- 문서만 stage했는가
- git diff --check가 통과했는가
```

blocker가 있더라도 문서화가 목적이면 문서 커밋은 가능하다.  
단, 코드 변경이나 generated artifact 커밋은 금지한다.

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
outputs/tmp_paper20_replay_smoke/*
replay smoke generated artifacts
idea, PRD, TRD/*
unrelated local artifacts
```

이번 작업에서 stage 가능한 파일은 원칙적으로 아래 하나뿐이다.

```cmd
git add docs\TRD\mfu_paper20_baseline_sidecar_check_and_operational_smoke.md
```

커밋 메시지:

```cmd
git commit -m "docs: record PAPER20 replay wrapper smoke check"
```

## 성공 기준

성공은 두 경우로 나뉜다.

### Case A: baseline sidecar 없음

```text
- eligible sidecar 없음이 재확인됨
- replay wrapper 실행하지 않음
- blocker가 문서화됨
- sidecar 생성/원장 변경/Notion 작업 없음
- 문서 커밋 완료
```

### Case B: baseline sidecar 있음

```text
- eligible sidecar 확인됨
- explicit --output-dir로 smoke 실행됨
- diff JSON/Markdown report 생성됨
- safety markers 확인됨
- generated artifacts stage 없음
- 문서 커밋 완료
```

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 생성/수정한 파일
3. baseline sidecar re-check 결과
4. eligible baseline 여부
5. smoke 실행 여부
6. 실행한 경우 command / output-dir / overall_status
7. 실행하지 않은 경우 blocker reason
8. generated artifact 생성 여부
9. generated artifact stage 여부
10. baseline/official artifact overwrite 여부
11. Notion API/write/export/sync 실행 여부
12. outputs/paper 원장 변경 여부
13. PASS/WARNING/FAIL 해석 요약
14. 자체 점검 결과
15. git diff --check 결과
16. 커밋 생성 여부
17. 커밋 SHA / 메시지
18. 제외한 unrelated 파일
19. 남은 리스크
20. PAPER20-3 추천 작업

END MFU-PAPER20-2-BASELINE-SIDECAR-CHECK-AND-CONDITIONAL-OPERATIONAL-SMOKE
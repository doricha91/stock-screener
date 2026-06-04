BEGIN MFU-PAPER20-5-CONTROLLED-BASELINE-CAPTURE-AND-REPLAY-WRAPPER-SMOKE

# PAPER20-5 Controlled Baseline Capture + Replay Wrapper Smoke

## 목적

PAPER20-5에서는 PAPER20-4에서 추가한 dev-only capture CLI를 실제로 사용해 `paper_sandbox / 2026-05-26` 기준 controlled baseline sidecar를 생성하고, 그 sidecar를 baseline으로 replay wrapper smoke를 실행한다.

이번 작업은 실제 운영 검증이 아니라 controlled smoke다.

반드시 명시한다.

```text
This is not historical actual-operation verification.
This is controlled operational smoke based on current code, current database, and current configuration.
```

한국어 의미:

```text
이번 smoke는 과거 2026-05-26 당시 실제 운영 결과의 재현성 검증이 아니다.
현재 코드/현재 DB/현재 config 기준으로 baseline capture와 replay wrapper가 정상 연결되는지 확인하는 controlled smoke다.
```

## 배경

PAPER20-3에서는 `scripts/run_paper_daily_plan.py`에 controlled output-dir 지원이 없어 blocker가 발생했다.

PAPER20-4에서 이를 해결하기 위해 아래 dev-only CLI를 추가했다.

```cmd
python scripts\dev\capture_daily_plan_baseline.py --account-id paper_sandbox --date 2026-05-26 --output-dir outputs\tmp_paper20_baseline_capture --json
```

PAPER20-5에서는 이 CLI를 실제로 실행하고, 이어서 replay wrapper smoke를 실행한다.

## 생성 파일

문서만 커밋한다.

```cmd
docs\TRD\mfu_paper20_controlled_baseline_capture_and_replay_smoke_result.md
```

## 생성되지만 커밋 금지인 artifact

아래 산출물은 생성될 수 있으나 절대 stage/commit하지 않는다.

```text
outputs/tmp_paper20_baseline_capture/*
outputs/tmp_paper20_replay_smoke/*
```

## 1단계: 사전 상태 확인

```cmd
git status --short

python scripts\dev\capture_daily_plan_baseline.py --help
python scripts\dev\replay_daily_plan_diff.py --help
python scripts\dev\diff_daily_plan.py --help
```

기존 unrelated 변경은 기록만 하고 stage하지 않는다.

## 2단계: Controlled baseline capture 실행

아래 명령을 실행한다.

```cmd
python scripts\dev\capture_daily_plan_baseline.py --account-id paper_sandbox --date 2026-05-26 --output-dir outputs\tmp_paper20_baseline_capture --json
```

확인할 것:

```text
- command exit code
- markdown_path
- sidecar_json_path
- config_snapshot_path
- account_id = paper_sandbox
- plan_date = 2026-05-26
- run_mode = baseline_capture
- official_run = false
- write_executed=false
- actual_executed=false
- notion_api_called=false
- notion_sync_executed=false
- notion_write_export_sync_executed=false
- commit_append_executed=false
```

생성된 sidecar에서 확인할 것:

```text
schema_version = paper_daily_plan.v1
items[] 존재
fingerprints 존재
config_hash 존재 여부
config_hash_policy = paper_config_hash.v1 여부
```

config_hash 누락은 blocker가 아니라 WARNING으로 기록한다.  
sidecar missing/malformed는 blocker로 기록하고 replay wrapper는 실행하지 않는다.

## 3단계: Replay wrapper smoke 실행

baseline sidecar가 정상 생성된 경우에만 실행한다.

예상 baseline path:

```text
outputs\tmp_paper20_baseline_capture\daily_action_plan_20260526.json
```

명령:

```cmd
python scripts\dev\replay_daily_plan_diff.py --account-id paper_sandbox --date 2026-05-26 --baseline-plan outputs\tmp_paper20_baseline_capture\daily_action_plan_20260526.json --output-dir outputs\tmp_paper20_replay_smoke --json
```

반드시 `--output-dir`을 명시한다.

확인할 것:

```text
- wrapper exit code
- run_id
- regenerated Markdown path
- regenerated JSON sidecar path
- regenerated config snapshot path
- diff JSON report path
- diff Markdown report path
- overall_status
- write_executed=false
- actual_executed=false
- notion_api_called=false
- notion_sync_executed=false
- notion_write_export_sync_executed=false
- commit_append_executed=false
```

## 4단계: 결과 해석

문서에 결과를 아래 기준으로 기록한다.

```text
PASS:
- compared Daily Plan fields match
- controlled replay smoke chain works
- actual/export/sync 승인 의미는 아님

PASS_WITH_METADATA_DIFF:
- generated_at, run_id, path 등 metadata 차이 중심
- 일반적으로 운영 중단 사유는 아님

WARNING:
- price/warning/reason/note/fingerprint/config_hash 차이
- 원인 후보는 있으나 확정 아님
- 후속 검토 필요

FAIL:
- baseline missing/malformed
- account/date mismatch
- symbol/action/quantity 차이
- replay wrapper execution failure
```

WARNING/FAIL이 나와도 즉시 수정하지 말고 문서화한다.

## 5단계: 운영 루프 readiness checklist

문서에 아래 체크리스트를 포함한다.

```text
Daily Plan:
- controlled baseline capture 실행 가능 여부
- Markdown 생성 여부
- JSON sidecar 생성 여부
- config snapshot 생성 여부
- current_state 참조 가능 여부

Replay:
- replay wrapper 실행 가능 여부
- regenerated sidecar 생성 여부
- diff JSON/Markdown report 생성 여부
- safety marker 확인 여부

Notion:
- Notion export/sync 실행하지 않음
- Manual Execution/Review sync 실행하지 않음

Ledger:
- commit/append 실행하지 않음
- account/position/current_state 원장 변경하지 않음

Market Data:
- 2026-05-20 이후 market data update를 하지 않았다는 한계 명시
- 2026-05-26 plan은 trading correctness 검증이 아니라 operational smoke임을 명시
```

## 문서 필수 섹션

```text
1. Purpose
2. Historical Verification Boundary
3. Controlled Baseline Capture Result
4. Baseline Sidecar Eligibility
5. Replay Wrapper Smoke Result
6. PASS / WARNING / FAIL Interpretation
7. Safety Marker Verification
8. Operating Loop Readiness Checklist
9. Market Data Limitation
10. Generated Artifact Policy
11. Known Limitations
12. PAPER20-6 Recommendation
```

## 검증 명령

문서 작성 후 실행한다.

```cmd
type docs\TRD\mfu_paper20_controlled_baseline_capture_and_replay_smoke_result.md

findstr /N /I "controlled baseline replay smoke historical verification output-dir PASS WARNING FAIL write_executed Notion market data" docs\TRD\mfu_paper20_controlled_baseline_capture_and_replay_smoke_result.md

git diff --check -- docs\TRD\mfu_paper20_controlled_baseline_capture_and_replay_smoke_result.md

git status --short
```

## Non-scope

이번 작업에서는 절대 하지 않는다.

```text
과거 실제 운영 결과 검증이라고 표현
Notion API 호출
Notion write/export/sync
actual export
Manual Execution commit
Manual Review append
source-of-truth ledger commit/append
account/position/current_state 원장 변경
generated artifact 커밋
stable plan_item_id 구현
universe_hash 구현
market_data_asof 구현
indicator_snapshot_hash 구현
state_snapshot_hash 구현
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
outputs/paper_accounts/*
outputs/tmp*
outputs/tmp_paper20_baseline_capture/*
outputs/tmp_paper20_replay_smoke/*
generated smoke artifacts
idea, PRD, TRD/*
unrelated local artifacts
```

stage 가능한 파일은 원칙적으로 아래 하나뿐이다.

```cmd
git add docs\TRD\mfu_paper20_controlled_baseline_capture_and_replay_smoke_result.md
```

커밋 메시지:

```cmd
git commit -m "docs: record PAPER20 controlled replay smoke result"
```

## 성공 기준

성공 또는 blocker 모두 문서화하면 된다.

성공 기준:

```text
- 2026-05-26 controlled baseline capture 실행
- baseline JSON sidecar 생성 및 eligibility 확인
- replay wrapper smoke 실행
- diff JSON/Markdown report 생성
- overall_status 기록
- safety marker 확인
- generated artifact stage 없음
- Notion/API/write/export/sync 없음
- outputs/paper 원장 변경 없음
- 문서만 커밋
```

Blocker 기준:

```text
- baseline capture 실패
- sidecar missing/malformed
- replay wrapper 실행 실패
- diff report 미생성
```

blocker가 발생하면 즉시 중단하고 문서화한다.

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 생성/수정한 파일
3. baseline capture 실행 여부
4. baseline capture command / output-dir
5. baseline sidecar eligibility 결과
6. replay wrapper smoke 실행 여부
7. replay command / output-dir
8. overall_status
9. diff report paths
10. safety marker 확인 결과
11. operating loop readiness checklist 요약
12. historical verification boundary 반영 여부
13. market data limitation 반영 여부
14. generated artifact 생성 여부
15. generated artifact stage 여부
16. Notion API/write/export/sync 실행 여부
17. outputs/paper 원장 변경 여부
18. 자체 점검 결과
19. git diff --check 결과
20. 커밋 생성 여부
21. 커밋 SHA / 메시지
22. 제외한 unrelated 파일
23. 남은 리스크
24. PAPER20-6 추천 작업

END MFU-PAPER20-5-CONTROLLED-BASELINE-CAPTURE-AND-REPLAY-WRAPPER-SMOKE
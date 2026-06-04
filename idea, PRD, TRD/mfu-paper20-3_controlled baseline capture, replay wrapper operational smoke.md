BEGIN MFU-PAPER20-3-CONTROLLED-BASELINE-CAPTURE-AND-REPLAY-SMOKE

# PAPER20-3 Controlled Baseline Capture + Replay Wrapper Operational Smoke

## 목적

PAPER20-3에서는 2026-05-26 기준 Daily Plan을 현재 코드/현재 DB/현재 config로 controlled output directory에 1차 생성해 baseline sidecar를 확보하고, 그 baseline sidecar를 사용해 replay wrapper operational smoke를 실행한다.

이번 작업은 “과거 2026-05-26 당시 실제 운영 결과 검증”이 아니다.

명확한 정의:

```text
This is not historical actual-operation verification.
This is controlled operational smoke based on current code, current database, and current configuration.
```

한국어 정의:

```text
이번 smoke는 과거 2026-05-26 당시 실제 운영 결과의 재현성 검증이 아니다.
현재 코드/현재 DB/현재 config 기준으로 baseline capture와 replay wrapper가 정상 연결되는지 확인하는 controlled smoke다.
```

## 배경

PAPER20-1/2 결과:

- 기존 paper_sandbox / 2026-05-20에는 Markdown, config snapshot, current_state snapshot은 존재
- 하지만 `daily_action_plan_20260520.json` sidecar는 없음
- JSON sidecar 기능은 PAPER19 이후 구현되었으므로 과거 날짜의 official baseline JSON이 없는 것은 정상
- PAPER20-2는 eligible baseline sidecar 부재로 replay wrapper를 실행하지 않고 blocker 문서화로 종료

따라서 PAPER20-3에서는 과거 sidecar를 억지로 복원하지 않고, 2026-05-26 controlled baseline을 새로 capture한 뒤 replay smoke를 수행한다.

## 생성 파일

```cmd
docs\TRD\mfu_paper20_controlled_baseline_capture_and_replay_smoke.md
```

## 허용 범위

허용:

```text
- 2026-05-26 Daily Plan controlled baseline 생성
- controlled output directory에 Markdown + JSON sidecar + config snapshot 생성
- 생성된 baseline sidecar eligibility 확인
- replay wrapper 실행
- replay wrapper가 regenerated Markdown/JSON/config snapshot 생성
- baseline vs regenerated diff JSON/Markdown report 생성
- 전체 운영루프 readiness checklist 작성
```

금지:

```text
- Notion API 호출
- Notion write/export/sync
- actual export
- Manual Execution commit
- Manual Review append
- source-of-truth 원장 commit/append
- account/position/current_state 원장 변경
- generated artifacts 커밋
- outputs/backtest_log.db 커밋
```

## 핵심 안전 원칙

반드시 지킨다.

```text
- 모든 baseline capture / replay smoke 산출물은 명시 output-dir 아래에만 생성한다.
- official artifact overwrite 금지.
- baseline artifact overwrite 금지.
- generated smoke artifacts는 기본적으로 커밋하지 않는다.
- 문서만 커밋한다.
- Notion/export/sync/commit/append 계열 명령은 실행하지 않는다.
```

## 권장 디렉터리

Controlled baseline capture:

```text
outputs/tmp_paper20_baseline_capture/
```

Replay smoke:

```text
outputs/tmp_paper20_replay_smoke/
```

위 디렉터리의 생성물은 smoke artifact이며 기본적으로 git stage/commit 금지다.

## 1단계: 사전 확인

먼저 아래를 실행한다.

```cmd
git status --short

python scripts\run_paper_daily_plan.py --help
python scripts\dev\replay_daily_plan_diff.py --help
python scripts\dev\diff_daily_plan.py --help
```

Daily Plan 생성 명령이 명시 output directory 또는 controlled output path를 지원하는지 확인한다.

중요:

```text
명시 output-dir 또는 controlled output path로 Daily Plan을 생성할 수 없으면,
official artifact overwrite 위험이 있으므로 생성하지 말고 blocker로 문서화한다.
```

## 2단계: Controlled baseline capture

2026-05-26 기준 Daily Plan을 controlled output directory에 생성한다.

목표 산출물:

```text
outputs/tmp_paper20_baseline_capture/daily_action_plan_20260526.md
outputs/tmp_paper20_baseline_capture/daily_action_plan_20260526.json
outputs/tmp_paper20_baseline_capture/.../paper_config_snapshot_20260526.json
```

실제 CLI 옵션은 `python scripts\run_paper_daily_plan.py --help` 결과에 맞춰 사용한다.

예상 명령 초안:

```cmd
python scripts\run_paper_daily_plan.py --account-id paper_sandbox --date 2026-05-26 --output-dir outputs\tmp_paper20_baseline_capture
```

위 명령은 예시다. 실제 옵션명이 다르면 repo의 CLI에 맞춘다.

실행 전 확인:

```text
- account_id = paper_sandbox
- date = 2026-05-26
- output target = outputs/tmp_paper20_baseline_capture/
- Notion/export/sync 옵션 없음
- commit/append 옵션 없음
```

## 3단계: Baseline sidecar eligibility 확인

생성된 baseline sidecar를 확인한다.

예상 path:

```text
outputs/tmp_paper20_baseline_capture/daily_action_plan_20260526.json
```

확인 항목:

```text
schema_version = paper_daily_plan.v1
account_id = paper_sandbox
plan_date = 2026-05-26
items[] 존재
fingerprints 존재
generator_version 존재
config_snapshot_path 존재
config_hash 존재 여부
config_hash_policy = paper_config_hash.v1 여부
state_snapshot_path 존재 여부
```

민감하거나 긴 JSON 본문을 문서에 대량 복사하지 않는다. 요약만 기록한다.

## 4단계: Replay wrapper smoke 실행

eligible baseline sidecar가 확인되면 replay wrapper를 실행한다.

예상 명령:

```cmd
python scripts\dev\replay_daily_plan_diff.py --account-id paper_sandbox --date 2026-05-26 --baseline-plan outputs\tmp_paper20_baseline_capture\daily_action_plan_20260526.json --output-dir outputs\tmp_paper20_replay_smoke --json
```

반드시 `--output-dir`을 명시한다.

실행 후 확인 항목:

```text
- wrapper exit code
- run_id
- regenerated Markdown path
- regenerated JSON sidecar path
- regenerated config snapshot path
- diff JSON report path
- diff Markdown report path
- overall_status: PASS / PASS_WITH_METADATA_DIFF / WARNING / FAIL
- write_executed=false
- actual_executed=false
- notion_api_called=false
- notion_sync_executed=false
- notion_write_export_sync_executed=false
- commit_append_executed=false
```

## 5단계: PASS / WARNING / FAIL 해석

문서에 결과 해석을 기록한다.

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

중요:

```text
PASS여도 actual/export/sync/commit/append를 허용하는 것이 아니다.
WARNING/FAIL이 나오면 즉시 수정하지 말고 원인 후보와 후속 MFU로 기록한다.
```

## 6단계: 전체 운영루프 readiness checklist

이번 작업에서 전체 운영루프를 직접 실행하지 않는다. 대신 readiness checklist로 점검한다.

문서에 아래를 포함한다.

```text
Daily Plan:
- controlled Daily Plan 생성 가능 여부
- Markdown 생성 여부
- JSON sidecar 생성 여부
- config snapshot 생성 여부
- current_state 참조 가능 여부

Replay:
- replay wrapper 실행 가능 여부
- regenerated sidecar 생성 여부
- diff report 생성 여부
- safety marker 확인 여부

Notion:
- Notion export/sync 실행하지 않음
- Manual Execution/Review sync 실행하지 않음
- 향후 Notion UI 개선 전 확인할 항목 기록

Ledger:
- commit/append 실행하지 않음
- account/position/current_state 원장 변경하지 않음

Market Data:
- 2026-05-20 이후 market data update를 하지 않았다는 한계 명시
- 따라서 2026-05-26 plan은 trading correctness 검증이 아니라 operational smoke임을 명시
```

## 문서 필수 섹션

생성 문서:

```cmd
docs\TRD\mfu_paper20_controlled_baseline_capture_and_replay_smoke.md
```

필수 섹션:

1. Purpose
2. Historical Verification Boundary
3. Controlled Baseline Capture
4. Baseline Sidecar Eligibility
5. Replay Wrapper Smoke
6. Output Directory Policy
7. PASS / WARNING / FAIL Result
8. Safety Marker Verification
9. Operating Loop Readiness Checklist
10. Market Data Limitation
11. Generated Artifact Policy
12. Non-scope
13. PAPER20-4 Recommendation

## Non-scope

이번 작업에서는 절대 하지 않는다.

```text
과거 실제 운영 결과 검증이라고 표현
Markdown에서 JSON 역생성
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

## 검증 명령

문서 작성 후 실행한다.

```cmd
type docs\TRD\mfu_paper20_controlled_baseline_capture_and_replay_smoke.md

findstr /N /I "controlled baseline replay smoke historical verification output-dir PASS WARNING FAIL write_executed Notion market data" docs\TRD\mfu_paper20_controlled_baseline_capture_and_replay_smoke.md

git diff --check -- docs\TRD\mfu_paper20_controlled_baseline_capture_and_replay_smoke.md
```

상태 확인:

```cmd
git status --short
```

주의:

```text
outputs/tmp_paper20_baseline_capture/*
outputs/tmp_paper20_replay_smoke/*
```

는 생성되어도 stage하지 않는다.

## 자체 점검 항목

Codex는 결과 보고에 아래를 포함한다.

```text
- Daily Plan baseline capture 실행 여부
- baseline capture command
- baseline output-dir
- baseline sidecar path
- baseline sidecar eligibility 결과
- replay wrapper smoke 실행 여부
- replay wrapper command
- replay output-dir
- overall_status
- diff report paths
- safety marker 확인 결과
- generated artifact 생성 여부
- generated artifact stage 여부
- Notion/API/write/export/sync 실행 여부
- outputs/paper 원장 변경 여부
- historical verification이 아니라 controlled smoke로 문서화했는지
- market data freshness 한계를 명시했는지
- git diff --check 결과
```

blocker가 있으면 즉시 중단하고 문서화한다.  
예: controlled output-dir로 Daily Plan 생성 불가, baseline sidecar 미생성, replay wrapper failure.

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
replay smoke generated artifacts
idea, PRD, TRD/*
unrelated local artifacts
```

이번 작업에서 stage 가능한 파일은 원칙적으로 아래 하나뿐이다.

```cmd
git add docs\TRD\mfu_paper20_controlled_baseline_capture_and_replay_smoke.md
```

커밋 메시지:

```cmd
git commit -m "docs: record PAPER20 controlled replay smoke"
```

## 성공 기준

성공 기준:

```text
- 2026-05-26 controlled baseline Daily Plan이 생성됨
- baseline JSON sidecar가 paper_daily_plan.v1로 확인됨
- replay wrapper smoke가 explicit --output-dir로 실행됨
- diff JSON/Markdown report가 생성됨
- PASS/WARNING/FAIL 결과가 문서화됨
- historical actual-operation verification이 아님을 명확히 기록함
- market data freshness 한계를 명확히 기록함
- Notion/API/write/export/sync 없음
- source-of-truth 원장 변경 없음
- generated artifacts stage 없음
- 문서만 커밋 완료
```

Blocker도 문서화하면 성공으로 인정 가능:

```text
- controlled output-dir로 Daily Plan 생성 불가
- baseline sidecar 미생성
- replay wrapper 실행 불가
```

단, 이 경우 원인을 명확히 기록하고 generated artifact를 stage하지 않는다.

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 생성/수정한 파일
3. controlled baseline capture 실행 여부
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
24. PAPER20-4 추천 작업

END MFU-PAPER20-3-CONTROLLED-BASELINE-CAPTURE-AND-REPLAY-SMOKE
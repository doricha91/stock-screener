BEGIN MFU-PAPER20-CLOSEOUT-REPLAY-SMOKE-RUNBOOK

# PAPER20 Replay Smoke Runbook Closeout

## 목적

PAPER20 Replay Wrapper Operational Smoke / Runbook 작업을 closeout 문서로 정리하고 커밋한다.

이번 작업에는 runbook 최종 정합성 점검/업데이트를 포함한다.

단, 이번 작업은 문서화 전용이다.

금지:
- Python 코드 수정
- replay smoke 재실행
- Daily Plan 생성 실행
- Notion API 호출
- Notion write/export/sync
- actual export
- source-of-truth ledger commit/append
- outputs/paper 원장 수정
- generated artifact 커밋

## 배경

PAPER20의 목적은 PAPER19에서 구현한 replay wrapper를 실제 운영에 가까운 controlled smoke로 검증하고, 운영자가 PASS/WARNING/FAIL 결과를 해석할 수 있는 runbook을 정리하는 것이었다.

PAPER20 진행 요약:

```text
PAPER20-1: replay wrapper smoke scope / baseline inventory
PAPER20-2: baseline sidecar 없음 재확인, smoke blocker 문서화
PAPER20-3: controlled output-dir 부재로 capture/smoke blocker 문서화
PAPER20-4: dev-only controlled baseline capture CLI 구현
PAPER20-5: controlled baseline capture + replay smoke 실행, config_hash WARNING 확인
PAPER20-6: config_hash WARNING 분석, source provenance false warning으로 분류, runbook 작성
PAPER20-7: source -> producer_source 명확화, source/producer_source hash 제외, smoke 재실행, PASS_WITH_METADATA_DIFF 확인
```

PAPER20-7 최종 결과:

```text
overall_status = PASS_WITH_METADATA_DIFF
config_hash diff 없음
cause_candidates = []
write_executed=false
actual_executed=false
notion_api_called=false
notion_sync_executed=false
notion_write_export_sync_executed=false
commit_append_executed=false
```

## 생성/수정 파일

필수 생성:

```cmd
docs\TRD\mfu_paper20_replay_smoke_runbook_closeout.md
```

필요 시 업데이트:

```cmd
docs\operations\paper_replay_diff_runbook.md
```

runbook이 이미 충분하면 큰 수정 없이 closeout 문서에서 “확인 완료”로 기록한다.  
PAPER20-7 결과가 반영되어 있지 않으면 최소 업데이트한다.

## closeout 문서 필수 섹션

1. Purpose
2. PAPER20 Scope
3. Completed Work
4. Controlled Smoke Timeline
5. Dev-only Capture CLI
6. Replay Smoke Result
7. config_hash False Warning Resolution
8. PASS_WITH_METADATA_DIFF Interpretation
9. Runbook Status
10. Safety Verification
11. Generated Artifact Policy
12. Known Limitations
13. Closeout Decision
14. Next MFU Recommendation

## 반드시 포함할 내용

### 1. 완료 체인

아래를 명시한다.

```text
baseline inventory
-> baseline sidecar blocker 확인
-> controlled output-dir blocker 확인
-> dev-only capture CLI 구현
-> controlled baseline capture 실행
-> replay wrapper smoke 실행
-> config_hash false WARNING 분석
-> producer_source rename / hash normalization 보강
-> controlled smoke 재실행
-> PASS_WITH_METADATA_DIFF 확인
-> runbook 정리
```

### 2. PASS_WITH_METADATA_DIFF 해석

아래 취지로 정리한다.

```text
PASS_WITH_METADATA_DIFF는 Daily Plan 비교 핵심 필드는 일치하지만,
timestamp/path/run metadata 같은 메타데이터 차이가 남은 상태다.

PAPER20-7 기준 config_hash false warning은 해소됐고,
cause_candidates는 비어 있다.

이 상태는 read-only replay smoke 성공으로 볼 수 있지만,
actual/export/sync/commit/append를 승인하는 의미는 아니다.
```

### 3. Runbook 반영 사항

`docs\operations\paper_replay_diff_runbook.md`에 아래가 들어있는지 확인한다.

```text
- PASS 해석
- PASS_WITH_METADATA_DIFF 해석
- WARNING 해석
- config_hash WARNING triage
- FAIL 해석
- generated artifact 비커밋 정책
- Notion/API/write/export/sync 금지
- PASS여도 actual/export/sync 승인 아님
- source/producer_source는 provenance metadata로 취급
- strategy_source/universe_source/market_data_source는 semantic 후보로 hash-significant
```

부족하면 최소 수정한다.

### 4. Safety policy

반드시 명시한다.

```text
- Notion API/write/export/sync 없음
- actual export 없음
- Manual Execution commit 없음
- Manual Review append 없음
- source-of-truth ledger commit/append 없음
- outputs/paper 원장 변경 없음
- generated smoke artifacts는 생성됐지만 커밋하지 않음
- outputs/tmp_paper20_baseline_capture/*
- outputs/tmp_paper20_replay_smoke/*
  는 stage/commit 금지
```

### 5. 남은 한계

반드시 포함한다.

```text
- items_count=0 smoke였으므로 action-row 재현성 검증은 제한적
- 2026-05-26 plan은 data_date=2026-05-20 기준이므로 trading correctness 검증이 아님
- historical actual-operation verification이 아님
- universe_hash 미구현
- market_data_asof 미구현
- indicator_snapshot_hash 미구현
- state_snapshot_hash 미구현
- stable plan_item_id 미구현
- 공식 run_paper_daily_plan.py --output-dir 정식 지원은 후속 판단
```

## Non-scope

이번 작업에서는 절대 하지 않는다.

```text
Python 코드 수정
테스트 코드 수정
replay smoke 재실행
Daily Plan 생성 실행
Notion API 호출
Notion write/export/sync
actual export
source-of-truth ledger commit/append
outputs/paper 원장 수정
generated artifact 커밋
schema/view drift 구현
Notion UI 개선
```

## 검증 명령

Windows CMD 기준:

```cmd
git status --short

type docs\TRD\mfu_paper20_replay_smoke_runbook_closeout.md

findstr /N /I "PAPER20 closeout replay smoke runbook PASS_WITH_METADATA_DIFF producer_source config_hash Notion generated artifact" docs\TRD\mfu_paper20_replay_smoke_runbook_closeout.md

type docs\operations\paper_replay_diff_runbook.md

findstr /N /I "PASS PASS_WITH_METADATA_DIFF WARNING FAIL config_hash producer_source generated artifact actual export sync" docs\operations\paper_replay_diff_runbook.md

git diff --check -- docs\TRD\mfu_paper20_replay_smoke_runbook_closeout.md docs\operations\paper_replay_diff_runbook.md
```

실제로 runbook을 수정하지 않았으면 diff check 대상에서 제외해도 된다.

## 자체 점검 항목

Codex는 결과 보고에 아래를 포함한다.

```text
- PAPER20 전체 목적이 closeout 문서에 정리됐는가
- PAPER20-1~7 흐름이 빠짐없이 정리됐는가
- PASS_WITH_METADATA_DIFF 해석이 명확한가
- config_hash false warning 해소가 반영됐는가
- runbook 작성/업데이트 여부
- generated artifact 비커밋 정책이 명시됐는가
- historical verification/trading correctness 한계가 명시됐는가
- 코드 변경 없이 문서만 작업했는가
- Notion/API/write/export/sync가 없었는가
- outputs/paper 원장 변경이 없었는가
- generated artifact가 stage되지 않았는가
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
outputs/tmp_paper20_baseline_capture/*
outputs/tmp_paper20_replay_smoke/*
generated smoke artifacts
idea, PRD, TRD/*
unrelated local artifacts
```

stage 후보:

```cmd
git add docs\TRD\mfu_paper20_replay_smoke_runbook_closeout.md
git add docs\operations\paper_replay_diff_runbook.md
```

실제 수정한 파일만 stage한다.

커밋 메시지:

```cmd
git commit -m "docs: close out PAPER20 replay smoke runbook"
```

## 성공 기준

```text
- PAPER20 closeout 문서 생성
- replay smoke runbook 정합성 확인 또는 업데이트
- PASS_WITH_METADATA_DIFF 해석 정리
- config_hash false warning 해소 결과 정리
- generated artifact 비커밋 정책 정리
- historical verification/trading correctness 한계 정리
- 코드 변경 없음
- Notion/API/write/export/sync 없음
- outputs/paper 원장 변경 없음
- generated artifacts stage 없음
- 문서 커밋 완료
```

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 생성/수정한 파일
3. closeout 판단 요약
4. PAPER20 완료 체인
5. replay smoke 최종 결과
6. PASS_WITH_METADATA_DIFF 해석
7. config_hash false warning 해소 반영 여부
8. runbook 작성/업데이트 여부
9. generated artifact 정책
10. historical verification / trading correctness 한계
11. Notion API/write/export/sync 실행 여부
12. outputs/paper 원장 변경 여부
13. generated artifact stage 여부
14. 자체 점검 결과
15. git diff --check 결과
16. 커밋 생성 여부
17. 커밋 SHA / 메시지
18. 제외한 unrelated 파일
19. 남은 리스크
20. 다음 MFU 추천

END MFU-PAPER20-CLOSEOUT-REPLAY-SMOKE-RUNBOOK
BEGIN MFU-PAPER20-6-CONFIG-HASH-WARNING-ANALYSIS-AND-RUNBOOK

# PAPER20-6 Replay Smoke config_hash WARNING Analysis + Interpretation Runbook

## 목적

PAPER20-5 controlled replay smoke에서 발생한 `overall_status=WARNING`의 원인인 `config_hash diff`를 분석한다.

핵심 질문:

```text
이번 config_hash 차이는 실제 의미 있는 config 차이인가?
아니면 controlled output-dir, 생성 시각, 경로, run metadata 등으로 인한 false warning인가?
```

이번 작업은 분석/문서화 중심이다.  
필요하면 기존 helper를 이용한 diagnostic command는 실행할 수 있지만, 기능 수정은 하지 않는다.

## 배경

PAPER20-5 결과:

```text
- controlled baseline capture 실행 성공
- replay wrapper smoke 실행 성공
- overall_status = WARNING
- Daily Plan action/quantity/price 차이 없음
- config_hash 차이만 cause candidate로 기록됨
- baseline sidecar items_count = 0
- plan_date = 2026-05-26
- generation data_date = 2026-05-20
- trading correctness 검증 아님
```

PAPER20-6의 목표는 이 WARNING을 바로 없애는 것이 아니라, 원인을 분석하고 운영 해석 기준을 정리하는 것이다.

## 생성 파일

```cmd
docs\TRD\mfu_paper20_config_hash_warning_analysis.md
docs\operations\paper_replay_diff_runbook.md
```

이미 적절한 runbook 문서가 있으면 새로 만들지 말고 업데이트해도 된다.

## 참고 artifact

우선 PAPER20-5 산출물이 남아 있는지 확인한다.

```cmd
dir outputs\tmp_paper20_baseline_capture /S /B
dir outputs\tmp_paper20_replay_smoke /S /B
```

예상 후보:

```text
outputs\tmp_paper20_baseline_capture\daily_action_plan_20260526.json
outputs\tmp_paper20_baseline_capture\config_snapshots\paper_config_snapshot_20260526.json

outputs\tmp_paper20_replay_smoke\runs\<run_id>\daily_action_plan_20260526.json
outputs\tmp_paper20_replay_smoke\runs\<run_id>\config_snapshots\paper_config_snapshot_20260526.json
outputs\tmp_paper20_replay_smoke\runs\<run_id>\paper_daily_plan_diff_20260526.json
outputs\tmp_paper20_replay_smoke\runs\<run_id>\paper_daily_plan_diff_20260526.md
```

PAPER20-5 보고 기준 run_id 후보:

```text
20260604_065248
```

단, 실제 workspace에 없으면 추측하지 말고 “artifact not found”로 기록한다.

## 1단계: 사전 확인

```cmd
git status --short

python scripts\dev\capture_daily_plan_baseline.py --help
python scripts\dev\replay_daily_plan_diff.py --help
python scripts\dev\diff_daily_plan.py --help
```

## 2단계: 기존 PAPER20-5 artifact 확인

다음을 확인한다.

```text
- baseline sidecar path
- regenerated sidecar path
- baseline config snapshot path
- regenerated config snapshot path
- diff JSON report path
- diff Markdown report path
```

확인할 필드:

```text
baseline sidecar:
- schema_version
- account_id
- plan_date
- run_mode
- official_run
- items_count
- fingerprints.config_snapshot_path
- fingerprints.config_hash
- fingerprints.config_hash_policy

regenerated sidecar:
- schema_version
- account_id
- plan_date
- run_mode
- official_run
- items_count
- fingerprints.config_snapshot_path
- fingerprints.config_hash
- fingerprints.config_hash_policy
```

긴 JSON 본문을 문서에 대량 복사하지 않는다. 요약만 기록한다.

## 3단계: config snapshot 차이 분석

baseline config snapshot과 regenerated config snapshot을 비교한다.

확인할 것:

```text
- raw config snapshot 파일 경로가 다른가
- raw config snapshot 내용이 다른가
- normalize_paper_config_for_hash() 결과가 다른가
- compute_paper_config_hash_from_file() 결과가 다른가
- 차이가 generated_at/run_id/path/output_dir 계열인지
- 차이가 run_mode/official_run/account/date/state path 등 semantic 후보인지
```

가능하면 Python one-liner 또는 짧은 임시 diagnostic command로 아래를 확인한다.

```text
- baseline raw hash
- regenerated raw hash
- baseline normalized hash
- regenerated normalized hash
- normalized key-level diff summary
```

주의:

```text
임시 diagnostic output은 outputs/tmp 또는 콘솔 출력만 사용한다.
진단용 임시 파일은 커밋하지 않는다.
```

## 4단계: false warning 여부 판단

아래 기준으로 판단한다.

### false warning 가능성이 높은 경우

```text
- Daily Plan items/action/quantity/price 차이 없음
- normalized config의 의미 있는 필드 차이 없음
- 차이가 output_dir, generated_at, run_id, temp path, artifact path 등에서만 발생
- baseline_capture vs replay run directory 차이로만 config_hash가 달라짐
```

### 실제 config warning 가능성이 있는 경우

```text
- normalized config에서 max_positions, risk, sizing, account, universe, strategy, cash policy 등 의미 있는 필드 차이 존재
- run_mode/official_run 차이가 Daily Plan 결과에 영향을 줄 수 있음
- state snapshot path가 다른 실제 state를 가리킬 가능성 있음
```

### 불확실한 경우

```text
- artifact가 없어서 비교 불가
- normalized diff를 충분히 확인할 수 없음
- config snapshot 구조가 복잡해 semantic 여부 판단이 어려움
```

## 5단계: runbook 정리

`docs\operations\paper_replay_diff_runbook.md`에 PASS/WARNING/FAIL 해석을 정리한다.

반드시 포함:

```text
PASS:
- compared Daily Plan fields match
- operational replay smoke read-only validation 가능
- actual/export/sync 승인 의미 아님

PASS_WITH_METADATA_DIFF:
- generated_at, run_id, path 등 metadata 중심 차이
- 보통 운영 중단 사유 아님

WARNING:
- price/warning/reason/note/fingerprint/config_hash 차이
- 원인 후보이며 확정 원인 아님
- config_hash warning은 normalized config diff를 확인해야 함

FAIL:
- baseline missing/malformed
- account/date mismatch
- symbol/action/quantity 차이
- replay wrapper failure
```

config_hash warning 전용 해석도 추가한다.

```text
config_hash WARNING triage:
1. action/quantity diff가 있는지 먼저 확인
2. normalized config diff 확인
3. volatile/path/run metadata 차이인지 확인
4. semantic config 차이면 후속 MFU로 분리
5. false warning이면 hash normalization policy 보강 후보로 기록
```

## 문서 필수 섹션

### docs/TRD/mfu_paper20_config_hash_warning_analysis.md

필수 섹션:

1. Purpose
2. PAPER20-5 Warning Recap
3. Artifact Availability
4. Baseline vs Regenerated Sidecar Summary
5. Config Snapshot Raw Comparison
6. Normalized Config Hash Comparison
7. Diff Classification
8. False Warning Assessment
9. Operational Interpretation
10. Safety Verification
11. Known Limitations
12. PAPER20-7 Recommendation

### docs/operations/paper_replay_diff_runbook.md

필수 섹션:

1. Purpose
2. When to Run Replay Diff
3. Required Safety Rules
4. PASS Interpretation
5. PASS_WITH_METADATA_DIFF Interpretation
6. WARNING Interpretation
7. config_hash WARNING Triage
8. FAIL Interpretation
9. What Not To Do
10. Follow-up Decision Rules

## Non-scope

이번 작업에서는 절대 하지 않는다.

```text
config_hash helper 수정
normalization policy 코드 수정
replay wrapper 코드 수정
Daily Plan generator 코드 수정
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
type docs\TRD\mfu_paper20_config_hash_warning_analysis.md

findstr /N /I "config_hash WARNING false warning normalized config baseline regenerated cause candidate" docs\TRD\mfu_paper20_config_hash_warning_analysis.md

type docs\operations\paper_replay_diff_runbook.md

findstr /N /I "PASS WARNING FAIL config_hash replay diff runbook Notion actual sync" docs\operations\paper_replay_diff_runbook.md

git diff --check -- docs\TRD\mfu_paper20_config_hash_warning_analysis.md docs\operations\paper_replay_diff_runbook.md

git status --short
```

필요하면 기존 테스트를 가볍게 확인한다.

```cmd
pytest tests\test_paper_config_hash.py
pytest tests\test_paper_replay_diff.py
```

## 자체 점검 항목

Codex는 결과 보고에 아래를 포함한다.

```text
- PAPER20-5 artifacts 존재 여부
- baseline sidecar / regenerated sidecar 비교 요약
- baseline config snapshot / regenerated config snapshot 비교 요약
- normalized config hash 비교 결과
- config_hash WARNING이 false warning인지, real warning인지, inconclusive인지
- 판단 근거
- runbook 작성/업데이트 여부
- 코드 변경 여부
- generated artifact stage 여부
- Notion/API/write/export/sync 실행 여부
- outputs/paper 원장 변경 여부
- git diff --check 결과
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

stage 가능한 파일:

```cmd
git add docs\TRD\mfu_paper20_config_hash_warning_analysis.md
git add docs\operations\paper_replay_diff_runbook.md
```

커밋 메시지:

```cmd
git commit -m "docs: analyze PAPER20 replay config hash warning"
```

## 성공 기준

성공 기준:

```text
- PAPER20-5 config_hash WARNING 분석 완료
- false warning / real warning / inconclusive 중 하나로 분류
- 판단 근거 문서화
- PASS/WARNING/FAIL runbook 작성 또는 업데이트
- 코드 변경 없음
- Notion/API/write/export/sync 없음
- outputs/paper 원장 변경 없음
- generated artifacts stage 없음
- 문서만 커밋
```

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 생성/수정한 파일
3. PAPER20-5 artifact availability
4. baseline vs regenerated sidecar 요약
5. config snapshot raw 비교 요약
6. normalized config hash 비교 요약
7. config_hash WARNING 분류: false / real / inconclusive
8. 판단 근거
9. runbook 작성/업데이트 요약
10. 코드 변경 여부
11. generated artifact stage 여부
12. Notion API/write/export/sync 실행 여부
13. outputs/paper 원장 변경 여부
14. 테스트/검증 결과
15. 자체 점검 결과
16. git diff --check 결과
17. 커밋 생성 여부
18. 커밋 SHA / 메시지
19. 제외한 unrelated 파일
20. 남은 리스크
21. PAPER20-7 추천 작업

END MFU-PAPER20-6-CONFIG-HASH-WARNING-ANALYSIS-AND-RUNBOOK
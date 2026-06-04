BEGIN MFU-PAPER19-CLOSEOUT

# PAPER19 Replay / Same-date Diff Closeout

## 목적

PAPER19 Replay / Same-date Diff 작업을 closeout 문서로 정리하고 커밋한다.

이번 작업은 문서화 전용이다.

금지:
- Python 코드 수정
- Daily Plan 생성/replay 실행
- Notion API 호출
- Notion write/export/sync
- actual export
- outputs/paper 원장 수정
- schema/view drift 구현
- 추가 기능 구현

## 배경

PAPER19의 목적은 같은 날짜 Daily Plan을 다시 생성하거나 비교했을 때, 기존 official/committed Daily Plan과 어떤 차이가 나는지 감지하는 최소 재현성 점검 장치를 구축하는 것이었다.

PAPER19에서 최종적으로 연결된 최소 체인:

1. Daily Plan JSON diff core/CLI
2. Daily Plan JSON sidecar producer
3. sidecar → replay diff smoke
4. minimal fingerprints
5. paper_config_hash.v1
6. replay wrapper minimal dry-run

PAPER19-10 결과 기준으로 replay wrapper는 baseline sidecar를 검증하고, replay-only run dir에 regenerated Daily Plan Markdown/JSON sidecar/config snapshot을 생성한 뒤, 기존 diff core로 JSON/Markdown diff report를 생성한다.

## 완료 커밋 정리

closeout 문서에 아래 커밋을 정리한다.

```text
a98e6e54dd97b15801698c799a55a5cb9149b20d
docs: define PAPER19 replay same-date diff scope

a6a40ed5ea0c743b674034407f5c68061989def4
feat: add PAPER19 daily plan replay diff core

bef90e951201152d73694b1c120b5bb76a124a04
docs: design PAPER19 daily plan replay source alignment

247cb79908413911b8e92ab524ad94d158559a63
docs: define PAPER19 daily plan JSON artifact contract

27d122d0249a0ac37ed3d020c364eaa6051c3678
feat: add PAPER19 daily plan JSON sidecar

a252cdddae7dcffdd936dce5558b70e1c5b41202
test: connect PAPER19 daily plan sidecar to replay diff

24e323118c9cda189edff50a3ef464eb7f6bcdbf
feat: populate PAPER19 daily plan sidecar fingerprints

da9abb1ea2d2fb5b96c37d8f10359c8bf57cd59f
docs: define PAPER19 config hash policy

beb128ff93d3fb861f0bdc03ec46fb09da5de65a
feat: add PAPER19 config hash fingerprints

f4b02d2d5c461e9f196468f5ab5ed65f8c5428dd
feat: add PAPER19 daily plan replay wrapper
```

## 생성 파일

```cmd
docs\TRD\mfu_paper19_replay_same_date_diff_closeout.md
```

## closeout 문서 필수 섹션

1. Purpose
2. PAPER19 Scope
3. Completed Work
4. Delivered Artifacts
5. Replay / Same-date Diff Flow
6. JSON Sidecar Contract
7. Config Hash / Fingerprint Policy
8. Replay Wrapper Dry-run Safety
9. Validation Summary
10. Known Limitations
11. Deferred Items
12. Closeout Decision
13. Next MFU Recommendation

## 반드시 포함할 내용

### 1. 완료된 기능

아래를 명시한다.

```text
- baseline/regenerated Daily Plan JSON diff core 구현
- scripts/dev/diff_daily_plan.py CLI 구현
- paper_daily_plan.v1 sidecar 생성
- 기존 Markdown Daily Plan 출력 유지
- paper_config_snapshot 의미/경로 유지
- sidecar가 replay diff input으로 호환됨을 smoke test로 검증
- generator_version/config_snapshot_path/state_snapshot_path populate
- paper_config_hash.v1 helper 구현
- sidecar에 config_hash/config_hash_policy populate
- scripts/dev/replay_daily_plan_diff.py minimal dry-run wrapper 구현
```

### 2. Replay wrapper flow

아래 흐름을 정리한다.

```text
1. baseline sidecar 입력
2. account/date 검증
3. replay-only runs/{run_id} 생성
4. generate_daily_plan()을 run_mode=replay, official_run=false로 호출
5. regenerated Markdown/JSON sidecar/config snapshot 생성
6. compare_daily_plan_files()로 diff
7. JSON/Markdown diff report 생성
8. safety marker 유지
```

### 3. Safety policy

반드시 명시한다.

```text
- baseline/official artifact overwrite 없음
- write_executed=false
- actual_executed=false
- notion_api_called=false
- notion_sync_executed=false
- notion_write_export_sync_executed=false
- commit_append_executed=false
- Notion API/write/export/sync 없음
- outputs/paper 원장 변경 없음
```

### 4. 테스트 요약

최종 검증 명령과 결과를 요약한다.

```text
python scripts\dev\replay_daily_plan_diff.py --help
python scripts\dev\diff_daily_plan.py --help
python scripts\run_paper_daily_plan.py --help

pytest tests\test_paper19_replay_wrapper.py
pytest tests\test_paper_replay_diff.py
pytest tests\test_daily_plan_json_sidecar.py
pytest tests\test_paper_config_hash.py
pytest tests\test_paper19_sidecar_replay_diff_smoke.py
```

PAPER19-10 보고 기준:
- replay wrapper test 6 passed
- replay diff test 15 passed
- sidecar test 6 passed
- config hash test 5 passed
- sidecar replay smoke 6 passed

### 5. 남은 한계

반드시 포함한다.

```text
- --output-dir 미지정 시 계좌별 replay_diff 경로에 산출물이 생길 수 있음
- 실제 운영 데이터 기반 end-to-end smoke는 아직 제한적
- 테스트에서는 heavy data dependency를 fake generator로 격리
- stable row id / plan_item_id 미구현
- universe_hash 미구현
- market_data_asof 미구현
- indicator_snapshot_hash 미구현
- state_snapshot_hash 미구현
- Manual Execution/Review replay는 미포함
- Notion sync replay는 미포함
```

### 6. closeout 판단

아래 취지로 정리한다.

```text
PAPER19 is closeout-ready because the minimal Daily Plan replay/same-date diff chain now exists: JSON sidecar generation, config hash fingerprints, pure diff core, sidecar smoke validation, and dry-run replay wrapper.
```

### 7. 다음 추천 작업

PAPER19 이후 추천은 아래 중 하나로 정리한다.

우선 추천:

```text
PAPER20 Replay Wrapper Operational Smoke / Runbook
- 실제 paper_sandbox baseline sidecar로 replay wrapper를 수동 smoke
- --output-dir 명시 사용 정책 정리
- PASS/WARNING/FAIL 결과 해석 runbook 작성
```

후속 후보:

```text
- stable plan_item_id / row identity hardening
- richer fingerprints: universe_hash, market_data_asof, indicator_snapshot_hash, state_snapshot_hash
- schema/view drift check
- external delivery adapter
```

## 검증 명령

Windows CMD 기준:

```cmd
git status --short

type docs\TRD\mfu_paper19_replay_same_date_diff_closeout.md

findstr /N /I "PAPER19 closeout replay same-date diff sidecar config_hash wrapper dry-run write_executed Notion baseline regenerated" docs\TRD\mfu_paper19_replay_same_date_diff_closeout.md

git diff --check -- docs\TRD\mfu_paper19_replay_same_date_diff_closeout.md
```

테스트 재확인이 필요하면 아래를 실행한다.

```cmd
pytest tests\test_paper19_replay_wrapper.py tests\test_paper_replay_diff.py tests\test_daily_plan_json_sidecar.py tests\test_paper_config_hash.py tests\test_paper19_sidecar_replay_diff_smoke.py
```

## 구현 후 자체 점검 항목

Codex는 문서 작성 후 아래를 확인하고 결과 보고에 포함한다.

```text
- PAPER19 목적이 재현성 점검으로 정리됐는가
- 완료된 체인이 빠짐없이 정리됐는가
- JSON sidecar / config_hash / replay wrapper 관계가 명확한가
- dry-run safety가 명확한가
- Notion/API/write/export/sync 없음이 명시됐는가
- outputs/paper 원장 변경 없음이 명시됐는가
- 남은 한계가 과장 없이 정리됐는가
- 다음 MFU 추천이 명확한가
- 코드 변경 없이 문서만 작성했는가
- git diff --check가 통과했는가
```

blocker가 있으면 커밋하지 말고 보고한다.  
blocker가 없으면 closeout 문서만 커밋한다.

## Non-scope

이번 작업에서는 절대 하지 않는다.

```text
Python 코드 수정
테스트 코드 수정
Daily Plan 생성 실행
replay wrapper 실행
actual export
Notion API 호출
Notion write/export/sync
outputs/paper 원장 수정
schema/view drift 구현
external delivery 구현
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

문서만 개별 stage한다.

```cmd
git add docs\TRD\mfu_paper19_replay_same_date_diff_closeout.md

git diff --cached --name-only
git diff --cached

git commit -m "docs: close out PAPER19 replay same-date diff"

git log -1 --stat
git status --short
```

## 성공 기준

- PAPER19 closeout 문서가 생성됨
- 완료 범위가 명확히 정리됨
- replay wrapper dry-run safety가 정리됨
- 테스트 결과가 요약됨
- 남은 한계와 후속 작업이 정리됨
- 코드 변경 없음
- Notion/API/write/export/sync 없음
- outputs/paper 원장 변경 없음
- unrelated 파일 stage 없음
- closeout 문서 커밋 완료

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 생성/수정한 파일
3. closeout 판단 요약
4. 완료된 PAPER19 체인
5. replay wrapper flow 요약
6. JSON sidecar / config_hash 정책 반영 여부
7. dry-run safety 반영 여부
8. 테스트 결과 요약
9. Notion API/write/export/sync 실행 여부
10. outputs/paper 원장 변경 여부
11. 자체 점검 결과
12. git diff --check 결과
13. 커밋 생성 여부
14. 커밋 SHA / 메시지
15. 제외한 unrelated 파일
16. 남은 리스크
17. 다음 MFU 추천

END MFU-PAPER19-CLOSEOUT
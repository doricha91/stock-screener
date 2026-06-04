BEGIN MFU-PAPER20-4-DEV-ONLY-DAILY-PLAN-CONTROLLED-CAPTURE-CLI

# PAPER20-4 Dev-only Daily Plan Controlled Baseline Capture CLI

## 목적

PAPER20-4에서는 PAPER20-3에서 확인된 blocker를 해소하기 위해, 공식 운영 CLI를 변경하지 않고 `scripts/dev/` 아래에 개발/검증 전용 Daily Plan controlled baseline capture CLI를 추가한다.

목표는 `paper_sandbox / 2026-05-26` 같은 날짜의 Daily Plan Markdown + JSON sidecar + config snapshot을 명시 output-dir 아래에만 생성할 수 있게 하는 것이다.

이번 작업은 dev-only capture CLI 구현이다.  
PAPER20-4에서는 replay wrapper smoke를 실행하지 않는다.  
실제 controlled baseline capture 실행도 테스트의 tmp_path/fake 범위로만 제한한다.

## 배경

PAPER20-3 결과:

- `scripts/run_paper_daily_plan.py`는 현재 `--date`만 지원하고 `--output-dir` 또는 controlled output path를 지원하지 않음
- 그래서 official artifact overwrite 위험 없이 2026-05-26 baseline sidecar를 만들 수 없어 capture/smoke를 실행하지 않음
- PAPER20-4에서는 공식 운영 CLI에 바로 `--output-dir`을 추가하지 않고, dev-only capture CLI로 해결하기로 결정
- 추후 필요하면 공식 운영 CLI의 controlled output 지원은 별도 기능으로 분리

## 구현 원칙

반드시 지킨다.

```text
- 공식 운영 CLI scripts/run_paper_daily_plan.py의 의미를 바꾸지 않는다.
- Notion API/write/export/sync를 실행하지 않는다.
- actual/export/sync/commit/append를 실행하지 않는다.
- account/position/current_state 원장을 변경하지 않는다.
- official Daily Plan artifact를 덮어쓰지 않는다.
- generated artifact는 명시 --output-dir 아래에만 생성한다.
- generated artifact는 커밋하지 않는다.
```

## 생성/수정 후보 파일

```text
scripts/dev/capture_daily_plan_baseline.py
tests/test_paper20_capture_daily_plan_baseline.py
docs/TRD/mfu_paper20_dev_only_daily_plan_controlled_capture_cli.md
```

가능하면 기존 공식 CLI 파일은 수정하지 않는다.

수정 금지 후보:

```text
scripts/run_paper_daily_plan.py
```

단, import 가능한 helper가 반드시 필요하고 기존 동작을 바꾸지 않는 최소 변경이면 보고 후 제한적으로 허용한다. 기본 방침은 새 dev-only CLI로 해결한다.

## CLI 요구사항

신규 CLI 후보:

```cmd
python scripts\dev\capture_daily_plan_baseline.py --account-id paper_sandbox --date 2026-05-26 --output-dir outputs\tmp_paper20_baseline_capture --json
```

필수 옵션:

```text
--account-id
--date
--output-dir
```

선택 옵션:

```text
--json
--run-mode
```

기본 정책:

```text
run_mode = baseline_capture
official_run = false
```

주의:

```text
--output-dir은 필수다.
--output-dir 없이는 실행 실패해야 한다.
기본 output-dir을 outputs/paper_accounts/...로 잡지 않는다.
```

## 구현 요구사항

### 1. 기존 generator 재사용

가능하면 `core.daily_plan_generator.generate_daily_plan()`를 직접 호출한다.

PAPER19-10 replay wrapper에서 이미 replay-only run dir 생성 흐름이 있으므로, 해당 패턴을 참고한다.

단, 다음은 하지 않는다.

```text
- strategy logic 변경
- Markdown rendering 변경
- JSON sidecar schema 변경
- config snapshot schema 변경
- replay diff core 변경
```

### 2. output-dir 격리

CLI는 모든 생성물을 `--output-dir` 아래에만 생성해야 한다.

예상 생성물:

```text
{output_dir}/daily_action_plan_YYYYMMDD.md
{output_dir}/daily_action_plan_YYYYMMDD.json
{output_dir}/config_snapshots/paper_config_snapshot_YYYYMMDD.json
```

실제 generator convention이 다르면 그 convention을 따르되, 공식 artifact 경로에 쓰지 않아야 한다.

### 3. safety summary

`--json` 출력 또는 console summary에 아래 safety marker를 포함한다.

```json
{
  "write_executed": false,
  "actual_executed": false,
  "notion_api_called": false,
  "notion_sync_executed": false,
  "notion_write_export_sync_executed": false,
  "commit_append_executed": false
}
```

또한 다음을 포함한다.

```text
account_id
plan_date
output_dir
markdown_path
sidecar_json_path
config_snapshot_path
run_mode
official_run
```

### 4. sidecar eligibility check

CLI 실행 후 생성된 sidecar를 로드해 최소 eligibility를 확인한다.

확인 항목:

```text
schema_version = paper_daily_plan.v1
account_id = 입력 account_id
plan_date = 입력 date
items[] 존재
fingerprints 존재
config_hash/config_hash_policy 존재 여부
```

config_hash가 없으면 실패로 보지 말고 WARNING 또는 summary note로 남긴다.  
단, malformed sidecar는 실패로 처리한다.

## 테스트 요구사항

새 테스트 파일:

```text
tests/test_paper20_capture_daily_plan_baseline.py
```

필수 테스트:

```text
--help 통과
--output-dir 없으면 실패
tmp_path output-dir 아래에만 파일 생성
official artifact 경로를 쓰지 않음
generate_daily_plan 호출 인자에 account_id/date/output_dir/run_mode/official_run 반영
summary에 safety marker 포함
sidecar eligibility 확인 성공
malformed/missing sidecar 처리
Notion/API/export/sync 호출 없음
```

실제 Daily Plan 생성이 무겁거나 market DB 의존성이 있으면 `generate_daily_plan()` 호출부를 monkeypatch/fake generator로 대체해 CLI orchestration만 검증한다.

PAPER20-4에서는 실제 2026-05-26 capture를 수행하지 않는다.  
실제 capture는 PAPER20-5에서 수행한다.

## 문서 작성

생성 문서:

```text
docs/TRD/mfu_paper20_dev_only_daily_plan_controlled_capture_cli.md
```

필수 섹션:

1. Purpose
2. PAPER20-3 Blocker Recap
3. Dev-only CLI Design
4. CLI Contract
5. Output-dir Safety Policy
6. Generated Artifact Policy
7. Sidecar Eligibility Check
8. Test Coverage
9. Non-scope
10. PAPER20-5 Recommendation

반드시 명시:

```text
- 이 CLI는 운영용 공식 CLI가 아니라 dev-only smoke helper다.
- 과거 실제 운영 검증을 수행하지 않는다.
- 공식 artifact overwrite를 피하기 위한 controlled capture용이다.
- generated artifacts는 커밋하지 않는다.
- 추후 필요하면 공식 run_paper_daily_plan.py의 controlled output 지원은 별도 MFU로 검토한다.
```

## 검증 명령

Windows CMD 기준:

```cmd
git status --short

python scripts\dev\capture_daily_plan_baseline.py --help

pytest tests\test_paper20_capture_daily_plan_baseline.py

type docs\TRD\mfu_paper20_dev_only_daily_plan_controlled_capture_cli.md

findstr /N /I "dev-only controlled baseline capture output-dir sidecar safety Notion official artifact PAPER20" docs\TRD\mfu_paper20_dev_only_daily_plan_controlled_capture_cli.md

git diff --check -- scripts\dev\capture_daily_plan_baseline.py tests\test_paper20_capture_daily_plan_baseline.py docs\TRD\mfu_paper20_dev_only_daily_plan_controlled_capture_cli.md
```

기존 replay 관련 regression이 가볍다면 함께 실행한다.

```cmd
pytest tests\test_paper19_replay_wrapper.py tests\test_daily_plan_json_sidecar.py tests\test_paper_config_hash.py
```

## 구현 후 자체 점검 항목

Codex는 결과 보고에 아래를 포함한다.

```text
- 신규 dev-only CLI 경로
- CLI 옵션 요약
- --output-dir 필수 여부
- generate_daily_plan 호출 방식
- run_mode / official_run 값
- output-dir 격리 확인
- sidecar eligibility check 방식
- safety marker 출력 여부
- 실제 2026-05-26 capture 실행 여부
- Notion/API/write/export/sync 실행 여부
- outputs/paper 원장 변경 여부
- generated artifact 생성/스테이지 여부
- 공식 run_paper_daily_plan.py 수정 여부
- 테스트 결과
- git diff --check 결과
```

## Non-scope

이번 작업에서는 절대 하지 않는다.

```text
실제 2026-05-26 controlled baseline capture 실행
replay wrapper smoke 실행
공식 운영 CLI의 의미 변경
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
공식 run_paper_daily_plan.py --output-dir 정식 지원
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

## 커밋 정책

자체 점검에서 blocker가 없고 테스트가 통과하면 실제 수정/생성 파일만 개별 stage한다.

예상 후보:

```cmd
git add scripts\dev\capture_daily_plan_baseline.py
git add tests\test_paper20_capture_daily_plan_baseline.py
git add docs\TRD\mfu_paper20_dev_only_daily_plan_controlled_capture_cli.md
```

커밋 메시지:

```cmd
git commit -m "feat: add PAPER20 dev daily plan capture CLI"
```

커밋 후 확인:

```cmd
git log -1 --stat
git status --short
```

## 성공 기준

- dev-only capture CLI가 추가됨
- `--output-dir`이 필수임
- controlled output-dir 아래에만 생성하도록 설계됨
- sidecar eligibility check가 있음
- safety marker가 출력됨
- 공식 운영 CLI 의미 변경 없음
- 실제 2026-05-26 capture 실행 없음
- replay wrapper smoke 실행 없음
- Notion/API/write/export/sync 없음
- outputs/paper 원장 변경 없음
- generated artifact stage 없음
- 테스트 통과
- git diff --check 통과
- 커밋 완료

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 생성/수정한 파일
3. dev-only capture CLI 요약
4. CLI 옵션 / --output-dir 정책
5. generate_daily_plan 호출 방식
6. run_mode / official_run 처리
7. output-dir 격리 정책
8. sidecar eligibility check
9. safety marker 출력
10. 실제 capture 실행 여부
11. replay wrapper smoke 실행 여부
12. Notion API/write/export/sync 실행 여부
13. outputs/paper 원장 변경 여부
14. generated artifact 생성/stage 여부
15. 공식 run_paper_daily_plan.py 수정 여부
16. 테스트 결과
17. 자체 점검 결과
18. git diff --check 결과
19. 커밋 생성 여부
20. 커밋 SHA / 메시지
21. 제외한 unrelated 파일
22. 남은 리스크
23. PAPER20-5 추천 작업

END MFU-PAPER20-4-DEV-ONLY-DAILY-PLAN-CONTROLLED-CAPTURE-CLI
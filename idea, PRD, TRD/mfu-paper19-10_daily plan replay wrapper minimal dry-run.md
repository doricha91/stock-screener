BEGIN MFU-PAPER19-10-DAILY-PLAN-REPLAY-WRAPPER-MINIMAL-DRY-RUN

# PAPER19-10 Daily Plan Replay Wrapper Minimal Dry-run

## 목적

PAPER19-10에서는 Daily Plan replay/same-date diff의 최소 wrapper를 구현한다.

핵심 목표:

1. existing baseline Daily Plan JSON sidecar를 입력받는다.
2. 같은 account/date 기준 regenerated Daily Plan을 replay-only run directory에 dry-run 생성한다.
3. 생성된 regenerated sidecar와 baseline sidecar를 기존 replay diff core로 비교한다.
4. JSON/Markdown diff report를 생성한다.
5. 모든 결과에 `write_executed=false` 성격을 유지한다.

이번 작업은 read-only / dry-run replay wrapper다.  
actual/export/sync/원장 commit/append는 절대 하지 않는다.

## 배경

PAPER19 진행 상태:

- PAPER19-2: `core.paper_replay_diff`와 `scripts/dev/diff_daily_plan.py` 구현 완료
- PAPER19-5: Daily Plan JSON sidecar 생성 완료
- PAPER19-6: sidecar → diff smoke 완료
- PAPER19-7: sidecar 최소 fingerprints populate
- PAPER19-9: `paper_config_hash.v1` helper 구현 및 sidecar `config_hash/config_hash_policy` populate 완료

PAPER19-10은 위 조각들을 연결하는 orchestration 단계다.

## 대상 파일 후보

필요한 파일만 수정/생성한다.

```text
scripts/dev/replay_daily_plan_diff.py
tests/test_paper19_replay_wrapper.py
docs/TRD/mfu_paper19_daily_plan_replay_wrapper_minimal.md
```

필요 시 기존 파일 최소 수정:

```text
core/daily_plan_generator.py
scripts/run_paper_daily_plan.py
```

단, 기존 generator / Markdown output / strategy logic 변경은 금지한다.

## CLI 요구사항

신규 CLI 후보:

```cmd
python scripts\dev\replay_daily_plan_diff.py --account-id paper_sandbox --date 2026-05-20 --baseline-plan <path> --output-dir <path> --json
```

지원 옵션:

```text
--account-id
--date
--baseline-plan
--output-dir
--json
```

선택 후보:

```text
--run-id
--keep-generated-markdown
```

초기에는 `--confirm-actual`, `--notion`, `--sync`, `--commit` 같은 옵션을 만들지 않는다.

## Wrapper Flow

구현 흐름:

```text
1. account_id/date/baseline_plan 입력 검증
2. baseline sidecar JSON 로드
3. baseline account_id/date mismatch면 FAIL report 또는 non-zero exit
4. replay run dir 생성
   {output_dir}/runs/{run_id}/
5. 기존 Daily Plan generator를 dry-run/replay-only output 경로로 호출
6. regenerated Markdown + regenerated JSON sidecar를 run dir에 생성
7. regenerated sidecar 경로 확인
8. core.paper_replay_diff 또는 diff_daily_plan 로직으로 baseline vs regenerated 비교
9. diff JSON/Markdown report를 run dir 또는 output_dir에 저장
10. console JSON 출력 옵션 지원
11. write_executed=false / actual_executed=false / notion_sync_executed=false 성격을 report 또는 wrapper summary에 기록
```

주의:

- baseline 파일을 절대 덮어쓰지 않는다.
- replay run dir 밖의 official Daily Plan artifact를 수정하지 않는다.
- generated config snapshot이 필요하면 replay run dir 안에만 생성한다.
- 실제 운영 outputs를 테스트에서 오염시키지 않는다.

## 기존 generator 호출 정책

먼저 `generate_daily_plan()`와 `scripts/run_paper_daily_plan.py`의 기존 signature를 확인한다.

가능하면 Python 함수 호출로 구현한다.

```text
replay wrapper -> generate_daily_plan(..., output_dir=run_dir, account_id=..., plan_date=..., official_run=false 또는 replay mode)
```

단, 기존 generator가 `run_mode=official, official_run=true`를 공식 wrapper에서만 전달하고 있다면, replay wrapper에서는 아래 중 더 안전한 방식을 선택하고 문서에 남긴다.

```text
A. baseline metadata에 맞춰 run_mode/official_run을 명시 전달
B. replay run metadata로 run_mode=replay 또는 exploratory, official_run=false 사용
```

중요:

- 어떤 값을 선택하든 원인 단정 금지
- baseline과 regenerated의 `run_mode/official_run` 차이는 diff/fingerprint 후보가 될 수 있음
- 기존 official output을 덮어쓰지 않는 것이 우선

## Output 정책

기본 output 구조 후보:

```text
{output_dir}/runs/{run_id}/regenerated_daily_action_plan_{YYYYMMDD}.md
{output_dir}/runs/{run_id}/regenerated_daily_action_plan_{YYYYMMDD}.json
{output_dir}/runs/{run_id}/paper_daily_plan_diff_{YYYYMMDD}.json
{output_dir}/runs/{run_id}/paper_daily_plan_diff_{YYYYMMDD}.md
```

기본 `output_dir`는 명시 입력을 권장한다.  
default를 둔다면 계좌별 replay path를 사용한다.

```text
outputs/paper_accounts/{account_id}/replay_diff/
```

테스트는 반드시 `tmp_path` 사용.

## 테스트 요구사항

새 테스트 파일 후보:

```text
tests/test_paper19_replay_wrapper.py
```

필수 테스트:

```text
--help 통과
baseline missing → FAIL 또는 non-zero
baseline account/date mismatch → FAIL 또는 non-zero
wrapper가 replay run dir에 regenerated sidecar를 생성
wrapper가 baseline을 덮어쓰지 않음
wrapper가 diff JSON/Markdown report를 생성
same baseline/regenerated fixture 흐름 → PASS 또는 expected status
quantity 차이 fixture/monkeypatch → FAIL/QUANTITY_DIFF
config_hash 차이 → WARNING/cause candidate
write_executed=false / actual_executed=false / notion_sync_executed=false 확인
Notion API 호출 없음
outputs/paper 원장 변경 없음
tmp_path만 사용
```

테스트에서 실제 Daily Plan 생성이 무겁거나 외부 데이터 의존성이 있으면, `generate_daily_plan()` 호출부를 monkeypatch/fake generator로 대체해 wrapper orchestration을 검증한다.

## 문서 작성

생성 문서:

```text
docs/TRD/mfu_paper19_daily_plan_replay_wrapper_minimal.md
```

포함 섹션:

1. Purpose
2. Scope
3. CLI
4. Wrapper Flow
5. Baseline / Regenerated Handling
6. Output Path Policy
7. Dry-run Safety Policy
8. Diff Integration
9. Test Coverage
10. Limitations
11. PAPER19 Closeout Recommendation

반드시 명시:

```text
- wrapper는 orchestration만 담당한다.
- diff 판단은 기존 core.paper_replay_diff가 담당한다.
- baseline은 절대 overwrite하지 않는다.
- regenerated artifact는 replay-only run dir에만 생성한다.
- Notion/API/write/export/sync 없음.
- 원인 단정 금지.
```

## 검증 명령

Windows CMD 기준:

```cmd
git status --short

python scripts\dev\replay_daily_plan_diff.py --help
python scripts\dev\diff_daily_plan.py --help
python scripts\run_paper_daily_plan.py --help

pytest tests\test_paper19_replay_wrapper.py
pytest tests\test_paper_replay_diff.py
pytest tests\test_daily_plan_json_sidecar.py
pytest tests\test_paper_config_hash.py
pytest tests\test_paper19_sidecar_replay_diff_smoke.py

type docs\TRD\mfu_paper19_daily_plan_replay_wrapper_minimal.md

findstr /N /I "replay wrapper baseline regenerated dry-run write_executed actual_executed Notion diff run dir" docs\TRD\mfu_paper19_daily_plan_replay_wrapper_minimal.md

git diff --check -- scripts\dev\replay_daily_plan_diff.py tests\test_paper19_replay_wrapper.py docs\TRD\mfu_paper19_daily_plan_replay_wrapper_minimal.md
```

실제 수정한 기존 파일이 있으면 diff check 대상에 포함한다.

## 구현 후 자체 점검 항목

Codex는 결과 보고에 아래를 포함한다.

### Wrapper 점검

```text
- 신규 CLI 경로와 옵션
- baseline 로드/검증 방식
- regenerated sidecar 생성 경로
- diff core 호출 방식
- output JSON/Markdown 경로
- run_id 생성 방식
```

### Safety 점검

```text
- baseline overwrite 없음
- official Daily Plan artifact overwrite 없음
- Notion API/write/export/sync 없음
- actual/export/sync/commit/append 없음
- outputs/paper 원장 변경 없음
- 테스트가 tmp_path 사용
- write_executed=false 또는 동등 safety marker 존재
```

### Diff 점검

```text
- same plan PASS 확인
- quantity diff FAIL 확인
- config_hash diff WARNING/cause candidate 확인
- 원인 단정 표현 없음
- 기존 diff/sidecar/config_hash 테스트 회귀 없음
```

### Git 점검

```text
- unrelated 파일 stage 없음
- .env, config/notion_settings.json, outputs/backtest_log.db stage 없음
- git diff --check 통과
```

blocker가 있으면 커밋하지 말고 보고한다.  
blocker가 없고 테스트가 통과하면 커밋한다.

## Non-scope

이번 작업에서는 절대 하지 않는다.

```text
actual export
Notion API 호출
Notion write/export/sync
paper ledger commit/append
Manual Execution/Review replay
schema/view drift
plan_item_id 구현
stable row id 리팩토링
universe_hash 구현
market_data_asof 구현
indicator_snapshot_hash 구현
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
git add scripts\dev\replay_daily_plan_diff.py
git add tests\test_paper19_replay_wrapper.py
git add docs\TRD\mfu_paper19_daily_plan_replay_wrapper_minimal.md
```

기존 파일을 수정했다면 해당 파일만 개별 stage한다.

커밋 메시지:

```cmd
git commit -m "feat: add PAPER19 daily plan replay wrapper"
```

커밋 후 확인:

```cmd
git log -1 --stat
git status --short
```

## 성공 기준

- replay wrapper CLI가 추가됨
- baseline sidecar 입력 검증 가능
- regenerated sidecar가 replay-only run dir에 생성됨
- 기존 diff core로 baseline/regenerated 비교 가능
- JSON/Markdown diff report 생성 가능
- baseline/official artifact overwrite 없음
- write_executed=false 성격 유지
- Notion/API/write/export/sync 없음
- outputs/paper 원장 변경 없음
- 테스트 통과
- git diff --check 통과
- 커밋 완료
- PAPER19 closeout 가능 여부가 보고됨

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 생성/수정한 파일
3. replay wrapper CLI 요약
4. wrapper flow 요약
5. baseline 검증 방식
6. regenerated sidecar 생성 방식
7. diff integration 방식
8. output path 정책
9. dry-run safety 확인
10. 테스트 결과
11. Notion API/write/export/sync 실행 여부
12. outputs/paper 원장 변경 여부
13. 자체 점검 결과
14. git diff --check 결과
15. 커밋 생성 여부
16. 커밋 SHA / 메시지
17. 제외한 unrelated 파일
18. 남은 리스크
19. PAPER19 closeout 가능 여부
20. 다음 추천 작업

END MFU-PAPER19-10-DAILY-PLAN-REPLAY-WRAPPER-MINIMAL-DRY-RUN
BEGIN MFU-PAPER19-6-SIDECAR-DIFF-SMOKE-AND-FINGERPRINT-SCOPE

# PAPER19-6 Daily Plan JSON Sidecar → Replay Diff Smoke + Fingerprint Scope Design

## 목적

PAPER19-5에서 생성된 `paper_daily_plan.v1` JSON sidecar가 PAPER19-2의 `diff_daily_plan.py` / `core.paper_replay_diff` 입력으로 실제 호환되는지 smoke test로 고정한다.

또한 config / universe / state / market / code fingerprint를 sidecar에 어떤 범위로 채울지 설계 문서로 정리한다.

이번 작업은 최소 연결/검증 단계다.

## 배경

PAPER19-5 완료 상태:

- 기존 Markdown Daily Plan 출력 유지
- 같은 basename의 JSON sidecar 생성
- 기본 파일명: `daily_action_plan_YYYYMMDD.json`
- schema: `paper_daily_plan.v1`
- fields: account_id, plan_date, run_mode, official_run, generated_at, items, fingerprints
- `type -> action`, `shares -> quantity`, `price -> price`, `symbol -> symbol` normalization 구현
- `fingerprints`는 현재 빈 object
- `plan_item_id`는 아직 없음

## 대상 파일 후보

필요한 파일만 최소 수정한다.

```text
tests/test_paper_replay_diff.py
tests/test_daily_plan_json_sidecar.py
docs/TRD/mfu_paper19_sidecar_diff_smoke_and_fingerprint_scope.md
```

필요하면 새 smoke 전용 테스트 파일을 추가해도 된다.

```text
tests/test_paper19_sidecar_replay_diff_smoke.py
```

가능하면 core 로직 수정은 피한다.  
sidecar가 diff input으로 이미 호환된다면 테스트/문서만 추가한다.

## 구현 범위

### 1. Sidecar → Diff smoke test

`paper_daily_plan.v1` sidecar 형태의 fixture JSON 2개를 만들고, 기존 diff core 또는 CLI가 이를 비교할 수 있음을 테스트한다.

필수 케이스:

```text
same sidecar plan → PASS
quantity changed sidecar → FAIL / QUANTITY_DIFF
warning changed sidecar → WARNING / WARNING_DIFF
fingerprints changed sidecar → WARNING + cause_candidate
```

테스트는 `tmp_path`를 사용한다.

금지:

```text
실제 outputs/paper_accounts 경로 사용
실제 운영 Daily Plan 생성 실행
Notion/API/write/export/sync
```

CLI smoke가 적절하면 아래 형태를 tmp_path에서 실행한다.

```cmd
python scripts\dev\diff_daily_plan.py --account-id paper_sandbox --date 2026-05-20 --baseline-plan <tmp_baseline.json> --regenerated-plan <tmp_regenerated.json> --output-dir <tmp_out> --json
```

### 2. Sidecar compatibility 점검

확인할 것:

```text
paper_daily_plan.v1의 items[]가 diff core의 input contract와 호환되는가
account_id / plan_date가 정확히 읽히는가
action / quantity / price / warning / reason / note가 비교되는가
fingerprints object가 있으면 fingerprint diff로 잡히는가
missing optional fields가 실패를 만들지 않는가
```

### 3. Fingerprint scope 설계

이번 작업에서는 fingerprint 값을 실제로 채우지 않는다.  
문서로만 범위를 정리한다.

후보:

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

문서에 아래를 구분한다.

```text
PAPER19-7에서 바로 채울 수 있는 후보
후속 producer contract가 필요한 후보
당장 제외할 후보
```

추천 초기 우선순위:

```text
1. config_hash 또는 config_snapshot_path
2. universe_hash 또는 universe_id
3. state_snapshot_path
4. code_commit_sha / generator_version
5. market_data_asof
```

단, 실제 repo에서 쉽게 얻을 수 없는 값은 추측해서 구현하지 않는다.

## 문서 작성

생성 문서:

```text
docs/TRD/mfu_paper19_sidecar_diff_smoke_and_fingerprint_scope.md
```

필수 섹션:

1. Purpose
2. Sidecar → Diff Compatibility
3. Smoke Test Coverage
4. Fingerprint Scope
5. Immediate Candidates
6. Deferred Candidates
7. Non-scope
8. PAPER19-7 Recommendation

반드시 명시:

```text
- sidecar는 diff core의 공식 입력 후보가 됨
- fingerprints는 이번 작업에서 실제 populate하지 않음
- 원인 단정 금지
- Notion/API/write/export/sync 없음
- outputs/paper 원장 변경 없음
```

## 테스트 요구사항

실행:

```cmd
python scripts\dev\diff_daily_plan.py --help

pytest tests\test_paper_replay_diff.py
pytest tests\test_daily_plan_json_sidecar.py
```

새 테스트 파일을 만들었다면 함께 실행한다.

```cmd
pytest tests\test_paper19_sidecar_replay_diff_smoke.py
```

## 검증 명령

```cmd
git status --short

type docs\TRD\mfu_paper19_sidecar_diff_smoke_and_fingerprint_scope.md

findstr /N /I "sidecar diff smoke fingerprint config_hash universe_hash state_snapshot code_commit_sha generator_version Notion" docs\TRD\mfu_paper19_sidecar_diff_smoke_and_fingerprint_scope.md

git diff --check -- tests\test_paper_replay_diff.py tests\test_daily_plan_json_sidecar.py docs\TRD\mfu_paper19_sidecar_diff_smoke_and_fingerprint_scope.md
```

새 테스트 파일이 있으면 diff check 대상에 포함한다.

## 구현 후 자체 점검 항목

Codex는 결과 보고에 아래를 포함한다.

```text
- paper_daily_plan.v1 sidecar가 diff input으로 호환되는지
- same / quantity diff / warning diff / fingerprint diff smoke 결과
- optional field 누락 처리 여부
- diff core 수정 여부
- 실제 Daily Plan 생성 실행 여부
- 실제 outputs 오염 여부
- fingerprints 실제 populate 여부
- Notion API/write/export/sync 실행 여부
- outputs/paper 원장 변경 여부
- git diff --check 결과
- blocker / non-blocking 개선점
```

blocker가 없고 테스트가 통과하면 커밋한다.

## Non-scope

이번 작업에서는 절대 하지 않는다.

```text
fingerprint 실제 populate 구현
plan_item_id 구현
Daily Plan 자동 재생성 wrapper 구현
실제 운영 Daily Plan 생성 실행
Notion API 호출
Notion write/export/sync
actual export
outputs/paper 원장 수정
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

실제 수정/생성 파일만 개별 stage한다.

예상 후보:

```cmd
git add tests\test_paper_replay_diff.py
git add tests\test_daily_plan_json_sidecar.py
git add docs\TRD\mfu_paper19_sidecar_diff_smoke_and_fingerprint_scope.md
```

새 테스트 파일이 있으면:

```cmd
git add tests\test_paper19_sidecar_replay_diff_smoke.py
```

커밋 메시지:

```cmd
git commit -m "test: connect PAPER19 daily plan sidecar to replay diff"
```

## 성공 기준

- `paper_daily_plan.v1` sidecar fixture가 replay diff input으로 검증됨
- same / quantity / warning / fingerprint diff smoke가 통과함
- JSON/Markdown diff report 생성 검증됨
- fingerprint populate 범위가 문서화됨
- 실제 fingerprint populate는 하지 않음
- Notion/API/write/export/sync 없음
- outputs/paper 원장 변경 없음
- 테스트 통과
- git diff --check 통과
- 커밋 완료

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 생성/수정한 파일
3. sidecar → diff smoke 구현 요약
4. smoke test coverage
5. fingerprint scope 설계 요약
6. diff core 수정 여부
7. 실제 Daily Plan 생성 실행 여부
8. Notion API/write/export/sync 실행 여부
9. outputs/paper 원장 변경 여부
10. 테스트 결과
11. 자체 점검 결과
12. git diff --check 결과
13. 커밋 생성 여부
14. 커밋 SHA / 메시지
15. 제외한 unrelated 파일
16. 남은 리스크
17. PAPER19-7 추천 작업

END MFU-PAPER19-6-SIDECAR-DIFF-SMOKE-AND-FINGERPRINT-SCOPE
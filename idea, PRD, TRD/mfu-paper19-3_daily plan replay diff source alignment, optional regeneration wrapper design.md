BEGIN MFU-PAPER19-3-SOURCE-ALIGNMENT-REGENERATION-WRAPPER-DESIGN

# PAPER19-3 Daily Plan Replay Diff Source Alignment / Optional Regeneration Wrapper Design

## 목적

PAPER19-3에서는 PAPER19-2에서 구현한 Daily Plan JSON diff core/CLI를 실제 운영 루프와 어떻게 연결할지 설계한다.

핵심 목표:

1. official/committed baseline Daily Plan JSON이 어디서 생산·보관되어야 하는지 정리한다.
2. regenerated Daily Plan JSON을 향후 어떤 방식으로 생성할지 wrapper 설계를 정리한다.
3. pure diff와 regeneration 실행을 분리하는 원칙을 명확히 한다.
4. source-of-truth, Notion, actual export, 원장을 변경하지 않는 read-only/dry-run 구조를 유지한다.

이번 작업은 설계 문서화 전용이다.  
Python 코드 구현, Daily Plan 재생성 실행, paper.py plan 실행, Notion API 호출, outputs/paper 원장 수정은 하지 않는다.

## 배경

PAPER19-2 완료 상태:

- PAPER19-1 설계 문서 커밋 완료
- Daily Plan JSON diff core/CLI 구현 완료
- 명시 입력된 baseline JSON / regenerated JSON 두 파일 비교 가능
- JSON/Markdown diff report 생성 가능
- 테스트 15 passed
- Notion API/write/export/sync 없음
- outputs/paper 원장 변경 없음

남은 리스크:

- 현재 입력은 JSON 전용이다.
- 실제 Daily Plan이 Markdown 중심이면 baseline/regenerated JSON 생산 계약이 필요하다.
- symbol + action row key가 실제 plan에서 충분하지 않을 경우 stable row id 정책이 필요하다.

## 생성 파일

```cmd
docs\TRD\mfu_paper19_daily_plan_replay_source_alignment_and_wrapper_design.md
```

## 참고 대상

가능하면 아래를 확인한다.

```cmd
findstr /S /N /I "daily plan daily_plan plan --account-id official_run commit committed output json markdown" docs\*.md docs\TRD\*.md docs\operations\*.md scripts\*.py scripts\dev\*.py core\*.py
findstr /S /N /I "diff_daily_plan paper_replay_diff replay_diff baseline regenerated" core\*.py scripts\dev\*.py tests\*.py docs\TRD\*.md
```

## 문서 필수 섹션

1. Purpose
2. Current PAPER19-2 State
3. Baseline Daily Plan Source Alignment
4. Regenerated Daily Plan Source Alignment
5. Pure Diff vs Regeneration Wrapper Boundary
6. Proposed Wrapper Flow
7. Output / Handoff Path Policy
8. Safety Policy
9. Row Identity / Stable ID Consideration
10. Test Strategy
11. Non-scope
12. PAPER19-4 Recommendation

## 설계 요구사항

### 1. Baseline Daily Plan Source Alignment

baseline은 다음으로 정의한다.

```text
baseline_plan = official 또는 committed Daily Plan JSON artifact
```

문서에서 확인/정리할 것:

```text
- 현재 Daily Plan이 JSON으로 생산되는가
- Markdown만 있다면 JSON artifact 생산이 필요한가
- official/committed 기준은 어떤 명령/단계에서 확정되는가
- baseline artifact는 임시 preview가 아니라 운영에 사용된 plan이어야 함
```

후보 경로는 계좌별 구조에 맞춘다.

```text
outputs/paper_accounts/{account_id}/plans/daily_plan_{YYYYMMDD}.json
outputs/paper_accounts/{account_id}/replay_diff/baseline_daily_plan_{YYYYMMDD}.json
```

실제 repo convention이 다르면 그것을 우선한다.

### 2. Regenerated Daily Plan Source Alignment

regenerated는 다음으로 정의한다.

```text
regenerated_plan = 같은 account/date/config 조건으로 dry-run 재생성한 별도 JSON artifact
```

주의:

- PAPER19-3에서는 regenerated plan을 생성하지 않는다.
- 향후 wrapper가 생성하더라도 원장/commit/append/export/sync를 수행하면 안 된다.
- regenerated artifact는 baseline을 덮어쓰지 않아야 한다.

후보 경로:

```text
outputs/paper_accounts/{account_id}/replay_diff/regenerated_daily_plan_{YYYYMMDD}.json
outputs/paper_accounts/{account_id}/replay_diff/runs/{run_id}/regenerated_daily_plan.json
```

### 3. Pure Diff와 Wrapper Boundary

반드시 명시한다.

```text
diff_daily_plan.py
= 이미 존재하는 두 JSON 파일을 비교하는 pure comparison tool

future replay wrapper
= regenerated JSON을 dry-run으로 생성한 뒤 diff_daily_plan.py에 넘기는 orchestrator
```

PAPER19-2의 diff core는 plan 생성 로직을 몰라야 한다.  
재생성 실행과 diff 비교를 섞지 않는다.

### 4. Proposed Wrapper Flow

향후 wrapper 후보 CLI를 설계한다.

예시:

```cmd
python scripts\dev\replay_daily_plan_diff.py --account-id paper_sandbox --date 2026-05-20 --baseline-plan <path> --output-dir <path> --json
```

흐름:

```text
1. account/date 입력 확인
2. baseline Daily Plan JSON 경로 확인
3. Daily Plan dry-run generation command 후보 확인
4. regenerated JSON을 replay_diff 전용 경로에 저장
5. diff_daily_plan.py 또는 core diff를 호출
6. JSON/Markdown diff report 생성
7. write_executed=false 유지
```

중요:

- wrapper는 기본적으로 dry-run only여야 한다.
- `--confirm-actual` 같은 옵션을 두지 않는다.
- Notion/export/sync와 연결하지 않는다.
- source-of-truth 원장을 수정하지 않는다.

### 5. Output / Handoff Path Policy

diff report 경로는 PAPER19-2 정책을 유지한다.

```text
outputs/paper_accounts/{account_id}/replay_diff/paper_daily_plan_diff_{YYYYMMDD}.json
outputs/paper_accounts/{account_id}/replay_diff/paper_daily_plan_diff_{YYYYMMDD}.md
```

wrapper run artifact 후보:

```text
outputs/paper_accounts/{account_id}/replay_diff/runs/{YYYYMMDD_HHMMSS}/regenerated_daily_plan.json
outputs/paper_accounts/{account_id}/replay_diff/runs/{YYYYMMDD_HHMMSS}/paper_daily_plan_diff.json
outputs/paper_accounts/{account_id}/replay_diff/runs/{YYYYMMDD_HHMMSS}/paper_daily_plan_diff.md
```

### 6. Row Identity / Stable ID Consideration

PAPER19-2는 기본 row key를 `symbol + action`으로 사용한다.

PAPER19-3 문서에는 다음을 포함한다.

```text
- symbol + action은 초기 최소 key다.
- 동일 symbol/action이 여러 줄이면 DUPLICATE_ROW_KEY WARNING이다.
- 향후 Daily Plan producer가 stable row id를 제공할 수 있는지 확인 필요.
- stable id 후보: plan_item_id, external_key, symbol+action+reason_code, deterministic rank.
- 임의 row order matching은 금지한다.
```

### 7. Test Strategy

PAPER19-4 구현 시 테스트 후보를 정리한다.

```text
- baseline path가 없으면 wrapper 중단
- regenerated artifact는 baseline을 덮어쓰지 않음
- wrapper가 source-of-truth 원장을 수정하지 않음
- wrapper가 Notion/API/export/sync를 호출하지 않음
- regenerated JSON을 diff core에 전달함
- diff 결과 JSON/Markdown 생성
- tmp_path 기반 테스트
```

## Non-scope

이번 작업에서는 절대 하지 않는다.

```text
Python 코드 구현
wrapper CLI 구현
Daily Plan 재생성 실행
paper.py plan 실행
Notion API 호출
Notion write/export/sync
actual export
outputs/paper 원장 수정
실제 Daily Plan artifact 수정
execution/review replay
schema/view drift
Telegram/Slack/Email 전송
```

## 검증 명령

Windows CMD 기준:

```cmd
git status --short

type docs\TRD\mfu_paper19_daily_plan_replay_source_alignment_and_wrapper_design.md

findstr /N /I "baseline regenerated wrapper pure diff dry-run Daily Plan source-of-truth Notion stable row id" docs\TRD\mfu_paper19_daily_plan_replay_source_alignment_and_wrapper_design.md

git diff --check -- docs\TRD\mfu_paper19_daily_plan_replay_source_alignment_and_wrapper_design.md
```

## 구현 후 자체 점검 항목

Codex는 문서 작성 후 아래를 확인하고 결과 보고에 포함한다.

### Source alignment 점검

- baseline Daily Plan JSON 정의가 명확한가
- regenerated Daily Plan JSON 정의가 명확한가
- official/committed baseline과 임시 preview를 구분했는가
- 실제 repo convention이 불명확한 항목을 확정처럼 쓰지 않았는가

### Boundary 점검

- pure diff와 regeneration wrapper의 책임이 분리됐는가
- diff core가 plan generation을 몰라야 한다는 원칙이 포함됐는가
- wrapper가 dry-run only여야 한다는 점이 명확한가

### Safety 점검

- 코드 수정이 없는가
- Daily Plan 재생성을 실행하지 않았는가
- Notion/API/write/export/sync가 없는가
- outputs/paper 원장 변경이 없는가
- 실제 운영 artifact를 수정하지 않았는가

### Git 점검

- unrelated 파일이 staged 되지 않았는가
- `.env`, `config/notion_settings.json`, outputs/backtest_log.db 등이 staged 되지 않았는가
- git diff --check가 통과했는가

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
idea, PRD, TRD/*
unrelated local artifacts
```

## 커밋 정책

문서만 개별 stage한다.

```cmd
git add docs\TRD\mfu_paper19_daily_plan_replay_source_alignment_and_wrapper_design.md

git diff --cached --name-only
git diff --cached

git commit -m "docs: design PAPER19 daily plan replay source alignment"

git log -1 --stat
git status --short
```

## 성공 기준

- PAPER19-3 설계 문서가 생성됨
- baseline/regenerated source alignment가 정리됨
- pure diff와 regeneration wrapper boundary가 명확함
- wrapper 후보 흐름이 dry-run only로 설계됨
- output/handoff path 정책이 정리됨
- stable row id 고려사항이 포함됨
- 코드 변경 없음
- Daily Plan 재생성 실행 없음
- Notion/API/write/export/sync 없음
- outputs/paper 원장 변경 없음
- closeout 전 후속 구현 방향이 명확함
- 문서 커밋 완료

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 생성/수정한 파일
3. baseline source alignment 요약
4. regenerated source alignment 요약
5. pure diff / wrapper boundary 요약
6. proposed wrapper flow
7. output / handoff path 정책
8. stable row id 고려사항
9. 코드 변경 여부
10. Daily Plan 재생성 실행 여부
11. Notion API/write/export/sync 실행 여부
12. outputs/paper 원장 변경 여부
13. 자체 점검 결과
14. git diff --check 결과
15. 커밋 생성 여부
16. 커밋 SHA / 메시지
17. 제외한 unrelated 파일
18. 남은 리스크
19. PAPER19-4 추천 작업

END MFU-PAPER19-3-SOURCE-ALIGNMENT-REGENERATION-WRAPPER-DESIGN
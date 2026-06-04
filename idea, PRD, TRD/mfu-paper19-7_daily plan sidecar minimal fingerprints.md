BEGIN MFU-PAPER19-7-DAILY-PLAN-SIDECAR-MINIMAL-FINGERPRINTS

# PAPER19-7 Daily Plan JSON Sidecar Minimal Fingerprint Population

## 목적

PAPER19-7에서는 PAPER19-5에서 추가한 `paper_daily_plan.v1` JSON sidecar의 `fingerprints` object에 최소 fingerprint 값을 실제로 채운다.

핵심 목표:

1. Daily Plan sidecar에 generator_version, config_snapshot_path 또는 config_hash, state_snapshot_path, 선택적 code_commit_sha를 최소 populate한다.
2. PAPER19-2 replay diff가 이 fingerprint 차이를 `cause_candidates`로 감지하는지 테스트한다.
3. 기존 Markdown 출력, Notion 흐름, paper_config_snapshot 의미를 변경하지 않는다.

이번 작업은 Daily Plan JSON sidecar metadata 보강 작업이다.  
Daily Plan 전략 로직, Markdown 포맷, Notion export/sync, 원장 commit/append는 변경하지 않는다.

## 배경

PAPER19 진행 상태:

- PAPER19-2: Daily Plan JSON diff core/CLI 구현 완료
- PAPER19-5: Daily Plan 생성 시 `paper_daily_plan.v1` JSON sidecar 생성 완료
- PAPER19-6: sidecar가 replay diff input으로 호환됨을 smoke test로 확인 완료

PAPER19-6 남은 리스크:

- 실제 sidecar의 `fingerprints`가 아직 빈 object
- `plan_item_id` 없음
- 중복 symbol+action row는 여전히 warning 기반 처리

이번 PAPER19-7에서는 `plan_item_id`는 구현하지 않는다.  
`fingerprints` 최소 populate만 진행한다.

## 대상 파일 후보

필요한 파일만 최소 수정한다.

```text
core/daily_plan_generator.py
scripts/run_paper_daily_plan.py
tests/test_daily_plan_json_sidecar.py
tests/test_paper19_sidecar_replay_diff_smoke.py
docs/TRD/mfu_paper19_daily_plan_sidecar_minimal_fingerprints.md
```

필요하면 기존 테스트에 추가하되, 불필요한 파일은 만들지 않는다.

## 구현 요구사항

### 1. fingerprints 최소 필드

`paper_daily_plan.v1` sidecar의 `fingerprints`에 아래 필드를 가능한 범위에서 채운다.

우선순위:

```text
generator_version
config_snapshot_path 또는 config_hash
state_snapshot_path
code_commit_sha
```

정책:

```text
- generator_version은 고정 문자열 또는 기존 version convention이 있으면 그 값을 사용한다.
- config_snapshot_path는 이미 생성되는 paper_config_snapshot_YYYYMMDD.json 경로를 참조한다.
- config_hash가 이미 쉽게 계산/사용 가능하면 사용하되, 과한 hashing 로직은 만들지 않는다.
- state_snapshot_path가 generator boundary에서 명확히 존재하면 기록한다.
- code_commit_sha는 기존 유틸/환경값이 있으면 기록하고, 없으면 null 또는 생략한다.
```

주의:

```text
추측해서 fake hash를 만들지 않는다.
값을 얻기 어렵다면 null 또는 omitted로 두고 문서에 limitation으로 남긴다.
```

### 2. 이번 범위에서 제외할 fingerprint

이번 작업에서 아래는 구현하지 않는다.

```text
universe_hash
market_data_asof
indicator_snapshot_hash
state_snapshot_hash
```

이 값들은 producer contract가 더 필요하므로 deferred로 둔다.

### 3. 기존 산출물 영향 금지

반드시 지킨다.

```text
- 기존 daily_action_plan_YYYYMMDD.md 파일명/내용 변경 금지
- paper_config_snapshot_YYYYMMDD.json 의미/경로 변경 금지
- JSON sidecar는 기존 Markdown을 대체하지 않음
- Notion 관련 파일 수정 금지
- Notion API/write/export/sync 실행 금지
- outputs/paper 원장 수정 금지
```

### 4. replay diff 연동 테스트

PAPER19-6에서 확인한 sidecar → diff smoke를 확장한다.

필수 테스트:

```text
- sidecar fingerprints가 JSON에 포함됨
- generator_version이 기록됨
- config_snapshot_path 또는 config_hash가 기록됨
- fingerprint가 다른 baseline/regenerated sidecar를 diff하면 WARNING 발생
- fingerprint diff가 cause_candidates에 기록됨
- 원인 단정 표현이 없음
```

`cause_candidates` 표현은 “possible cause candidate” 수준이어야 한다.  
“because config changed”처럼 원인을 단정하지 않는다.

## 문서 작성

생성 문서:

```text
docs/TRD/mfu_paper19_daily_plan_sidecar_minimal_fingerprints.md
```

포함 섹션:

1. Purpose
2. Scope
3. Implemented Fingerprints
4. Deferred Fingerprints
5. Sidecar Schema Impact
6. Replay Diff Cause Candidate Impact
7. Markdown / Notion Safety
8. Test Coverage
9. Limitations
10. PAPER19-8 Recommendation

반드시 명시:

```text
- fingerprints는 원인 확정이 아니라 원인 후보 추적용이다.
- full snapshot을 sidecar에 복사하지 않는다.
- Markdown output은 변경하지 않는다.
- Notion/API/write/export/sync 없음.
- universe/market/indicator hash는 후속이다.
```

## 테스트 요구사항

아래 테스트를 실행한다.

```cmd
python scripts\run_paper_daily_plan.py --help
python scripts\dev\diff_daily_plan.py --help

pytest tests\test_daily_plan_json_sidecar.py
pytest tests\test_paper19_sidecar_replay_diff_smoke.py
pytest tests\test_paper_replay_diff.py
```

기존 Daily Plan 관련 회귀 테스트가 있으면 함께 실행한다.

```cmd
pytest tests\test_paper_daily_plan_generation.py tests\test_paper_config_snapshot.py
```

## 검증 명령

Windows CMD 기준:

```cmd
git status --short

type docs\TRD\mfu_paper19_daily_plan_sidecar_minimal_fingerprints.md

findstr /N /I "fingerprint generator_version config_snapshot config_hash state_snapshot code_commit_sha cause candidate Notion Markdown" docs\TRD\mfu_paper19_daily_plan_sidecar_minimal_fingerprints.md

git diff --check -- core\daily_plan_generator.py scripts\run_paper_daily_plan.py tests\test_daily_plan_json_sidecar.py tests\test_paper19_sidecar_replay_diff_smoke.py docs\TRD\mfu_paper19_daily_plan_sidecar_minimal_fingerprints.md
```

실제로 수정하지 않은 파일은 diff check 대상에서 제외해도 된다.

## 구현 후 자체 점검 항목

Codex는 결과 보고에 아래를 반드시 포함한다.

### Fingerprint 점검

```text
- sidecar fingerprints에 어떤 필드를 실제로 채웠는가
- generator_version 값은 무엇인가
- config_snapshot_path/config_hash 중 무엇을 선택했는가
- state_snapshot_path가 기록되는가
- code_commit_sha는 기록되는가, 아니면 null/omitted인가
- universe_hash/market_data_asof/indicator_snapshot_hash를 구현하지 않았는가
```

### Replay diff 점검

```text
- fingerprint 차이가 WARNING으로 감지되는가
- cause_candidates에 기록되는가
- 원인 단정 표현이 없는가
- 기존 quantity/warning diff smoke가 깨지지 않았는가
```

### Safety 점검

```text
- 기존 Markdown 출력 변경 여부
- paper_config_snapshot 의미 변경 여부
- Notion 관련 파일 수정 여부
- Notion API/write/export/sync 실행 여부
- outputs/paper 원장 변경 여부
- 실제 운영 Daily Plan 생성 실행 여부
- 테스트가 tmp_path를 사용했는가
```

### Git 점검

```text
- unrelated 파일이 staged 되지 않았는가
- .env, config/notion_settings.json, outputs/backtest_log.db 등이 staged 되지 않았는가
- git diff --check가 통과했는가
```

blocker가 있으면 커밋하지 말고 보고한다.  
blocker가 없고 테스트가 통과하면 커밋한다.

## Non-scope

이번 작업에서는 절대 하지 않는다.

```text
plan_item_id 구현
stable row id 리팩토링
universe_hash 구현
market_data_asof 구현
indicator_snapshot_hash 구현
state_snapshot_hash 구현
Daily Plan 전략 로직 변경
Markdown 포맷 변경
Markdown parser 구현
replay wrapper 구현
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

자체 점검에서 blocker가 없고 테스트가 통과하면 실제 수정/생성 파일만 개별 stage한다.

예상 후보:

```cmd
git add core\daily_plan_generator.py
git add scripts\run_paper_daily_plan.py
git add tests\test_daily_plan_json_sidecar.py
git add tests\test_paper19_sidecar_replay_diff_smoke.py
git add docs\TRD\mfu_paper19_daily_plan_sidecar_minimal_fingerprints.md
```

실제 수정하지 않은 파일은 stage하지 않는다.

커밋 메시지:

```cmd
git commit -m "feat: populate PAPER19 daily plan sidecar fingerprints"
```

커밋 후 확인:

```cmd
git log -1 --stat
git status --short
```

## 성공 기준

- Daily Plan JSON sidecar fingerprints가 최소 populate됨
- generator_version이 기록됨
- config_snapshot_path 또는 config_hash가 기록됨
- state_snapshot_path는 가능한 경우 기록됨
- code_commit_sha는 가능한 경우 기록됨
- replay diff가 fingerprint 차이를 WARNING/cause candidate로 감지함
- 기존 sidecar/diff 테스트가 통과함
- 기존 Markdown 출력 영향 없음
- paper_config_snapshot 의미 변경 없음
- Notion/API/write/export/sync 없음
- outputs/paper 원장 변경 없음
- git diff --check 통과
- 커밋 완료

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 생성/수정한 파일
3. sidecar fingerprint 구현 요약
4. generator_version 처리
5. config_snapshot_path/config_hash 처리
6. state_snapshot_path 처리
7. code_commit_sha 처리
8. deferred fingerprint 목록
9. replay diff cause candidate 검증
10. 기존 Markdown 영향 여부
11. paper_config_snapshot 영향 여부
12. 테스트 결과
13. Notion API/write/export/sync 실행 여부
14. outputs/paper 원장 변경 여부
15. 자체 점검 결과
16. git diff --check 결과
17. 커밋 생성 여부
18. 커밋 SHA / 메시지
19. 제외한 unrelated 파일
20. 남은 리스크
21. PAPER19-8 추천 작업

END MFU-PAPER19-7-DAILY-PLAN-SIDECAR-MINIMAL-FINGERPRINTS
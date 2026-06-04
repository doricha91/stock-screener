BEGIN MFU-PAPER19-9-CONFIG-HASH-HELPER-AND-SIDECAR-POPULATE

# PAPER19-9 Config Hash Helper v1 + Daily Plan Sidecar Populate

## 목적

PAPER19-8에서 설계한 `paper_config_hash.v1` 정책을 실제 helper로 구현하고, Daily Plan JSON sidecar의 `fingerprints`에 `config_hash`와 `config_hash_policy`를 populate한다.

이번 작업은 config fingerprint 구현 작업이다.  
Replay wrapper 구현은 PAPER19-10에서 별도 진행한다.

## 배경

PAPER19-8 완료 상태:

- `config_snapshot_path`는 trace metadata로 정의됨
- `config_hash`는 설정 내용의 stable semantic fingerprint로 정의됨
- 정책명: `paper_config_hash.v1`
- 알고리즘 후보: `sha256`
- volatile/runtime/local metadata는 hash에서 제외해야 함
- 원인 단정 금지

PAPER19-9 목표:

```text
config snapshot 내용이 의미 있게 바뀌면 hash가 바뀐다.
generated_at/path/run_id 같은 runtime metadata만 바뀌면 hash는 바뀌지 않는다.
```

## 대상 파일 후보

필요한 파일만 수정한다.

```text
core/daily_plan_generator.py
scripts/run_paper_daily_plan.py
tests/test_daily_plan_json_sidecar.py
docs/TRD/mfu_paper19_config_hash_helper_and_sidecar_populate.md
```

필요하면 helper 파일을 추가한다.

```text
core/paper_config_hash.py
tests/test_paper_config_hash.py
```

## 구현 요구사항

### 1. config hash helper 구현

`paper_config_hash.v1` helper를 구현한다.

권장 함수 후보:

```text
compute_paper_config_hash(config: dict) -> str
normalize_paper_config_for_hash(config: dict) -> dict
```

hash 출력 형식:

```text
sha256:<hex>
```

정책명:

```text
paper_config_hash.v1
```

### 2. normalization 정책

반드시 안정적으로 normalize한다.

포함 방향:

```text
Daily Plan 결과에 영향을 줄 수 있는 config 값은 유지한다.
```

제외 방향:

```text
generated_at
created_at
updated_at
run_id
absolute_path
local_path
report_path
log_path
temporary path
machine/user-specific path
secret/token/env-like 값
```

구현 방식은 repo의 실제 config snapshot 구조를 확인한 뒤 정한다.

권장:

```text
- JSON key sort
- compact separators
- UTF-8
- volatile field recursive 제거
- absolute path / local path 제거 또는 repo-relative normalization
```

실제 snapshot 구조가 불명확한 필드는 추측해서 whitelist하지 않는다.  
불확실하면 “full config minus documented volatile fields” 방식으로 작게 구현하고 문서에 한계를 남긴다.

### 3. sidecar populate

Daily Plan sidecar의 `fingerprints`에 아래를 추가한다.

```json
{
  "config_snapshot_path": "...",
  "config_hash": "sha256:...",
  "config_hash_policy": "paper_config_hash.v1"
}
```

정책:

```text
config_snapshot_path가 존재하고 파일을 읽을 수 있으면 config_hash를 기록한다.
파일이 없거나 malformed면 Daily Plan 생성 전체를 깨뜨리지 말고 config_hash를 omitted/null 처리한다.
단, 테스트와 문서에 이 한계를 명확히 남긴다.
```

주의:

```text
paper_config_snapshot_YYYYMMDD.json 의미/경로를 변경하지 않는다.
기존 Markdown 출력은 변경하지 않는다.
Notion 관련 파일은 수정하지 않는다.
```

### 4. replay diff 연동

기존 replay diff는 fingerprints 차이를 cause candidate로 감지한다.

테스트로 확인한다.

```text
baseline config_hash != regenerated config_hash
→ WARNING
→ cause_candidates에 config_hash 차이 기록
→ 원인 단정 표현 없음
```

## 문서 작성

생성 문서:

```text
docs/TRD/mfu_paper19_config_hash_helper_and_sidecar_populate.md
```

필수 섹션:

1. Purpose
2. Scope
3. Implemented Helper
4. Normalization Policy
5. Excluded Volatile Fields
6. Sidecar Fingerprint Impact
7. Replay Diff Cause Candidate Impact
8. Test Coverage
9. Limitations
10. PAPER19-10 Recommendation

반드시 명시:

```text
- config_hash는 원인 확정이 아니라 원인 후보 추적용이다.
- generated_at/path/run_id 변화만으로 hash가 바뀌면 안 된다.
- full snapshot을 diff report에 복사하지 않는다.
- Notion/API/write/export/sync 없음.
```

## 테스트 요구사항

필수 테스트:

```text
같은 config, key order 다름 → hash 동일
generated_at만 다름 → hash 동일
run_id만 다름 → hash 동일
absolute/local path만 다름 → hash 동일
semantic field 변경 → hash 다름
secret/token/env-like field는 hash input에서 제외
sidecar에 config_hash/config_hash_policy 기록
config snapshot missing 시 sidecar 생성이 실패하지 않음
config_hash 차이가 replay diff cause candidate로 기록됨
```

실행 명령:

```cmd
python scripts\run_paper_daily_plan.py --help
python scripts\dev\diff_daily_plan.py --help

pytest tests\test_paper_config_hash.py
pytest tests\test_daily_plan_json_sidecar.py
pytest tests\test_paper19_sidecar_replay_diff_smoke.py
pytest tests\test_paper_replay_diff.py
pytest tests\test_paper_daily_plan_generation.py tests\test_paper_config_snapshot.py
```

파일이 없는 테스트 명령은 실제 생성한 테스트 파일 기준으로 조정한다.

## 검증 명령

```cmd
git status --short

type docs\TRD\mfu_paper19_config_hash_helper_and_sidecar_populate.md

findstr /N /I "config_hash paper_config_hash.v1 sha256 normalize generated_at run_id path sidecar cause candidate" docs\TRD\mfu_paper19_config_hash_helper_and_sidecar_populate.md

git diff --check -- core\paper_config_hash.py core\daily_plan_generator.py scripts\run_paper_daily_plan.py tests\test_paper_config_hash.py tests\test_daily_plan_json_sidecar.py tests\test_paper19_sidecar_replay_diff_smoke.py docs\TRD\mfu_paper19_config_hash_helper_and_sidecar_populate.md
```

실제로 수정하지 않은 파일은 diff check 대상에서 제외해도 된다.

## 구현 후 자체 점검 항목

Codex는 결과 보고에 아래를 반드시 포함한다.

### Hash helper 점검

```text
- helper 파일/함수명
- hash 출력 형식
- policy name
- normalization 방식
- excluded volatile fields
- semantic field 변경 시 hash 변경 여부
- generated_at/path/run_id 변경 시 hash 불변 여부
```

### Sidecar 점검

```text
- sidecar에 config_hash가 기록되는가
- config_hash_policy가 기록되는가
- config_snapshot_path 의미/경로를 변경하지 않았는가
- config snapshot missing/malformed 시 동작
```

### Replay diff 점검

```text
- config_hash 차이가 WARNING/cause candidate로 감지되는가
- 원인 단정 표현이 없는가
- 기존 quantity/warning/fingerprint diff smoke가 깨지지 않았는가
```

### Safety 점검

```text
- 기존 Markdown 출력 변경 여부
- Daily Plan 전략 로직 변경 여부
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
Replay wrapper 구현
Daily Plan 자동 재생성 orchestration
plan_item_id 구현
stable row id 리팩토링
universe_hash 구현
market_data_asof 구현
indicator_snapshot_hash 구현
state_snapshot_hash 구현
Daily Plan 전략 로직 변경
Markdown 포맷 변경
Markdown parser 구현
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
git add core\paper_config_hash.py
git add core\daily_plan_generator.py
git add scripts\run_paper_daily_plan.py
git add tests\test_paper_config_hash.py
git add tests\test_daily_plan_json_sidecar.py
git add tests\test_paper19_sidecar_replay_diff_smoke.py
git add docs\TRD\mfu_paper19_config_hash_helper_and_sidecar_populate.md
```

실제 수정하지 않은 파일은 stage하지 않는다.

커밋 메시지:

```cmd
git commit -m "feat: add PAPER19 config hash fingerprints"
```

커밋 후 확인:

```cmd
git log -1 --stat
git status --short
```

## 성공 기준

- `paper_config_hash.v1` helper가 구현됨
- `sha256:<hex>` 형식 config_hash가 생성됨
- volatile/runtime/local metadata 변경만으로 hash가 바뀌지 않음
- semantic config field 변경 시 hash가 바뀜
- sidecar에 config_hash/config_hash_policy가 기록됨
- replay diff가 config_hash 차이를 WARNING/cause candidate로 감지함
- 기존 Markdown 출력 영향 없음
- paper_config_snapshot 의미 변경 없음
- Notion/API/write/export/sync 없음
- outputs/paper 원장 변경 없음
- 테스트 통과
- git diff --check 통과
- 커밋 완료

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 생성/수정한 파일
3. config hash helper 구현 요약
4. normalization 정책
5. excluded volatile fields
6. semantic field 변경 테스트 결과
7. volatile field 변경 테스트 결과
8. sidecar config_hash/config_hash_policy populate 요약
9. config snapshot missing/malformed 처리
10. replay diff cause candidate 검증
11. 기존 Markdown 영향 여부
12. paper_config_snapshot 영향 여부
13. 테스트 결과
14. Notion API/write/export/sync 실행 여부
15. outputs/paper 원장 변경 여부
16. 자체 점검 결과
17. git diff --check 결과
18. 커밋 생성 여부
19. 커밋 SHA / 메시지
20. 제외한 unrelated 파일
21. 남은 리스크
22. PAPER19-10 추천 작업

END MFU-PAPER19-9-CONFIG-HASH-HELPER-AND-SIDECAR-POPULATE
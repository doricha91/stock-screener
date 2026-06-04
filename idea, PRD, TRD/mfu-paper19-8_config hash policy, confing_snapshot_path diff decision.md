BEGIN MFU-PAPER19-8-CONFIG-HASH-POLICY-DESIGN

# PAPER19-8 Config Hash Policy v1 + config_snapshot_path Diff Decision

## 목적

PAPER19-8에서는 Daily Plan replay/same-date diff에서 사용할 `config_hash` 정책을 설계하고, 현재 sidecar에 들어가는 `config_snapshot_path`를 diff에서 어떻게 해석할지 결정한다.

이번 작업은 설계 전용이다.

코드 구현, hashing helper 구현, Daily Plan 생성 실행, Notion API/write/export/sync, outputs/paper 원장 수정은 하지 않는다.

## 배경

PAPER19-7 완료 상태:

- `paper_daily_plan.v1` sidecar fingerprints에 최소 값 populate 완료
- 현재 fingerprints:
  - `generator_version = paper_daily_plan.v1`
  - `config_snapshot_path`
  - `state_snapshot_path`
- `config_hash`는 과한 hashing 로직을 피하기 위해 미구현
- `code_commit_sha`는 안전 유틸/convention 미확인으로 omitted
- `config_snapshot_path`는 trace metadata이며, 아직 `config_hash` 대체 필드처럼 비교되지는 않음

이번 PAPER19-8은 바로 `config_hash`를 구현하지 않고, 안정적인 hash 정책을 먼저 문서화한다.

## 생성 파일

```cmd
docs\TRD\mfu_paper19_config_hash_policy_and_replay_diff_decision.md
```

## 참고 대상

가능하면 아래를 확인한다.

```cmd
findstr /S /N /I "paper_config_snapshot config_snapshot_path config_hash fingerprints replay_diff cause candidate" core\*.py scripts\*.py scripts\dev\*.py tests\*.py docs\TRD\*.md
```

## 문서 필수 섹션

1. Purpose
2. Current State
3. config_snapshot_path Role
4. config_hash Purpose
5. Stable Hashing Policy v1
6. Include / Exclude Field Policy
7. Canonicalization Policy
8. Replay Diff Interpretation
9. Non-scope
10. PAPER19-9 Recommendation

## 설계 요구사항

### 1. config_snapshot_path 역할 정의

다음을 명시한다.

```text
config_snapshot_path는 설정 스냅샷 파일 위치를 추적하는 trace metadata다.
경로가 같다고 내용이 같다는 보장은 없다.
경로가 다르다고 설정 내용이 반드시 다르다는 뜻도 아니다.
```

Replay diff에서의 권장 해석:

```text
config_snapshot_path만 다름
→ FAIL 금지
→ 약한 WARNING 또는 INFO성 cause candidate 후보
→ 원인 단정 금지
```

표현 예:

```text
config_snapshot_path differs.
Config source may differ. This is a cause candidate, not a confirmed cause.
```

### 2. config_hash 목적 정의

다음을 명시한다.

```text
config_hash는 설정 내용의 안정적 fingerprint다.
의미 있는 설정 변경에는 hash가 바뀌고,
generated_at/path/run_id 같은 runtime metadata 변경에는 hash가 바뀌지 않아야 한다.
```

### 3. Stable Hashing Policy v1

정책 이름 후보:

```text
paper_config_hash.v1
```

hash algorithm 후보:

```text
sha256
```

sidecar 후보 필드:

```json
{
  "fingerprints": {
    "config_snapshot_path": "...",
    "config_hash": "sha256:...",
    "config_hash_policy": "paper_config_hash.v1"
  }
}
```

### 4. Include 후보

Daily Plan 결과에 영향을 줄 수 있는 설정만 포함 후보로 둔다.

예:

```text
account_id
currency
benchmark_id
universe_id
strategy_profile_id
risk_profile_id
max_positions
hedge_enabled
official_run
cash/risk/sizing/trade limit 관련 설정
```

실제 config snapshot 구조에서 확인되지 않은 필드는 확정처럼 쓰지 말고 후보로 둔다.

### 5. Exclude 후보

실행 때마다 바뀌거나 로컬 환경에 의존하는 값은 제외 후보로 둔다.

예:

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
```

### 6. Canonicalization 정책

다음을 포함한다.

```text
- JSON key sort
- compact separators
- UTF-8
- stable numeric types
- absolute path 제외 또는 repo-relative normalization
- volatile timestamp 제외
```

단, 실제 구현은 후속으로 남긴다.

### 7. Replay Diff 해석 정책

정리할 것:

```text
config_snapshot_path diff only
→ weak cause candidate

config_hash diff
→ stronger WARNING cause candidate

path different + hash same
→ 저장 위치만 다를 가능성

path same + hash different
→ 같은 경로의 config 내용 변경 가능성

path different + hash different
→ config 변경 가능성 높음
```

단, 어떤 경우에도 “config 때문에 plan이 바뀌었다”고 단정하지 않는다.

## Non-scope

이번 작업에서는 절대 하지 않는다.

```text
Python 코드 구현
config_hash helper 구현
sidecar schema 변경
Daily Plan 생성 실행
replay diff 실행
Notion API 호출
Notion write/export/sync
outputs/paper 원장 수정
actual export
code_commit_sha 구현
```

## 검증 명령

Windows CMD 기준:

```cmd
git status --short

type docs\TRD\mfu_paper19_config_hash_policy_and_replay_diff_decision.md

findstr /N /I "config_snapshot_path config_hash paper_config_hash.v1 sha256 canonicalization include exclude cause candidate replay diff" docs\TRD\mfu_paper19_config_hash_policy_and_replay_diff_decision.md

git diff --check -- docs\TRD\mfu_paper19_config_hash_policy_and_replay_diff_decision.md
```

## 구현 후 자체 점검 항목

Codex는 문서 작성 후 아래를 확인하고 결과 보고에 포함한다.

```text
- config_snapshot_path를 trace metadata로 정의했는가
- config_snapshot_path diff를 FAIL로 보지 않도록 명시했는가
- config_hash 목적과 policy version을 정의했는가
- include/exclude 후보를 구분했는가
- generated_at/path/run_id 같은 volatile field 제외 원칙을 명시했는가
- canonicalization 정책을 명시했는가
- 원인 단정 금지를 명시했는가
- 코드 구현 없이 문서만 작성했는가
- Notion/API/write/export/sync가 없었는가
- outputs/paper 원장 변경이 없었는가
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
idea, PRD, TRD/*
unrelated local artifacts
```

## 커밋 정책

문서만 개별 stage한다.

```cmd
git add docs\TRD\mfu_paper19_config_hash_policy_and_replay_diff_decision.md

git diff --cached --name-only
git diff --cached

git commit -m "docs: define PAPER19 config hash policy"

git log -1 --stat
git status --short
```

## 성공 기준

- config_snapshot_path 역할이 명확히 정리됨
- config_hash 목적과 `paper_config_hash.v1` 정책이 정의됨
- include/exclude/canonicalization 기준이 정리됨
- replay diff 해석 정책이 정리됨
- 원인 단정 금지가 명시됨
- 코드 변경 없음
- Daily Plan 생성 실행 없음
- Notion/API/write/export/sync 없음
- outputs/paper 원장 변경 없음
- 문서 커밋 완료

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 생성/수정한 파일
3. config_snapshot_path 역할 정리
4. config_hash 목적 정리
5. Stable hashing policy v1 요약
6. include field 후보
7. exclude field 후보
8. canonicalization 정책
9. replay diff 해석 정책
10. 코드 변경 여부
11. Daily Plan 생성/replay 실행 여부
12. Notion API/write/export/sync 실행 여부
13. outputs/paper 원장 변경 여부
14. 자체 점검 결과
15. git diff --check 결과
16. 커밋 생성 여부
17. 커밋 SHA / 메시지
18. 제외한 unrelated 파일
19. 남은 리스크
20. PAPER19-9 추천 작업

END MFU-PAPER19-8-CONFIG-HASH-POLICY-DESIGN
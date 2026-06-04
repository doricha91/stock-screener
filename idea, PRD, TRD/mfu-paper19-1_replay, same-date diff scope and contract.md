BEGIN MFU-PAPER19-1-REPLAY-SAME-DATE-DIFF-SCOPE

# PAPER19-1 Replay / Same-date Diff Scope and Contract

## 목적

PAPER19 Replay / Same-date Diff의 1단계 설계 문서를 작성한다.

PAPER19의 목적은 같은 날짜의 Daily Plan을 다시 생성하거나 비교했을 때, 기존 Daily Plan과 어떤 차이가 나는지 감지하는 최소 재현성 점검 장치를 만드는 것이다.

이번 PAPER19-1은 설계 전용이다.  
Python 코드 구현, replay 실행, plan 재생성, Notion API 호출, Notion write/export/sync, outputs/paper 원장 수정은 하지 않는다.

## 배경

PAPER18 Alert / Monitoring Report는 closeout 완료됐다.

다음 단계는 Replay / Same-date Diff Minimal Harness다.

Replay / Same-date Diff는 수익률 개선 기능이 아니라 운영 재현성 검증 기능이다.

핵심 질문:

```text
같은 account/date의 Daily Plan을 다시 비교했을 때,
기존 official/committed Daily Plan과 regenerated Daily Plan이 같은가?
다르다면 무엇이 달라졌는가?
원인 후보를 추적할 최소 fingerprint가 있는가?
```

중요 원칙:

```text
결과 차이는 명확히 기록한다.
원인 후보는 fingerprint/hash/path/as-of 중심으로만 기록한다.
원인을 단정하지 않는다.
```

## 생성 파일

아래 문서를 생성한다.

```cmd
docs\TRD\mfu_paper19_replay_same_date_diff_scope_and_contract.md
```

## 참고 파일

가능하면 아래 파일을 확인한다. 파일명이 다르면 유사 파일을 찾아 확인한다.

```cmd
docs\TRD\paper_ops_feature_roadmap_v1_1.md
docs\TRD\mfu_paper18_alert_monitoring_closeout.md
docs\operations\paper_daily_ops.md
docs\operations\paper_notion_ops.md
```

Daily Plan 관련 출력/문서/스크립트도 repo에서 확인한다.

```cmd
findstr /S /N /I "Daily Plan daily_plan plan --account-id official_run committed" docs\*.md docs\TRD\*.md docs\operations\*.md scripts\*.py scripts\dev\*.py core\*.py
```

## 문서 필수 섹션

문서에는 아래 섹션을 포함한다.

1. Purpose
2. Scope
3. Baseline / Regenerated Plan Definition
4. Input Contract
5. Diff Fields
6. Diff Categories
7. PASS / WARNING / FAIL Policy
8. Fingerprint / Cause Candidate Policy
9. Output Path Policy
10. JSON / Markdown Report Shape
11. Test Strategy
12. Non-scope
13. PAPER19-2 Recommendation

## 설계 요구사항

### 1. 초기 범위

초기 PAPER19는 Daily Plan diff만 다룬다.

포함:

```text
- baseline Daily Plan JSON
- regenerated Daily Plan JSON
- 단일 account_id
- 단일 date
- JSON + Markdown diff report 설계
```

제외:

```text
- execution replay
- review replay
- Notion sync replay
- actual export replay
- portfolio state 완전 복원
- 여러 날짜 batch replay
- plan 재생성 자동 실행
```

### 2. baseline / regenerated 정의

기본 정의:

```text
baseline_plan = official 또는 committed Daily Plan artifact
regenerated_plan = 같은 account/date로 다시 생성된 Daily Plan artifact
```

단, PAPER19-1에서는 plan 재생성 자동화는 하지 않는다.  
PAPER19-2도 우선 두 JSON 파일 비교부터 시작하는 방향으로 설계한다.

### 3. 비교 필드

초기 비교 대상:

```text
symbol
action
quantity
price
warning
reason
note
```

있으면 후보로 포함:

```text
cash_impact
allocation
target_weight
stop_price
```

### 4. diff category

초기 category 후보:

```text
NO_DIFF
METADATA_DIFF
WARNING_DIFF
PRICE_DIFF
QUANTITY_DIFF
ACTION_DIFF
SYMBOL_SET_DIFF
CONFIG_OR_UNIVERSE_DIFF
STATE_OR_MARKET_FINGERPRINT_DIFF
```

### 5. 판정 정책

기본 정책:

```text
PASS:
- 핵심 필드 차이 없음
- metadata만 다른 경우는 PASS 또는 PASS_WITH_METADATA_DIFF 후보

WARNING:
- warning / reason / note 차이
- price 차이
- fingerprint 차이만 있고 plan action/quantity 차이가 없는 경우

FAIL:
- symbol set 차이
- action 차이
- quantity 차이
```

가격 비교는 초기에는 exact 비교로 설계한다.  
tolerance는 후속 옵션으로 둔다.

### 6. fingerprint / cause candidate 정책

원인 후보 추적용으로 아래를 설계한다.

```text
config_hash
universe_hash
state_snapshot_hash 또는 path
market_data_asof
indicator_snapshot_hash 후보
code_commit_sha
generator_version
```

주의:

```text
full snapshot을 report에 복사하지 않는다.
hash/path/as-of/sha 중심으로 기록한다.
원인을 단정하지 않는다.
```

표현 예:

```text
quantity가 달라졌다.
config fingerprint도 다르다.
따라서 config 변경이 원인 후보일 수 있다.
```

금지 표현:

```text
quantity가 달라진 원인은 config 변경이다.
```

### 7. 출력 경로 정책

계좌별 경로를 설계한다.

```text
outputs/paper_accounts/{account_id}/replay_diff/paper_daily_plan_diff_{YYYYMMDD}.json
outputs/paper_accounts/{account_id}/replay_diff/paper_daily_plan_diff_{YYYYMMDD}.md
```

테스트와 smoke는 tmp_path / --output-dir을 사용해 실제 outputs를 오염시키지 않는 방향으로 설계한다.

### 8. 테스트 전략

테스트는 실제 운영 파일을 변경하지 않는다.

fixture JSON 2개를 만들어 비교하는 방식으로 설계한다.

필수 테스트 후보:

```text
same plan → PASS / NO_DIFF
symbol 추가/삭제 → FAIL / SYMBOL_SET_DIFF
action 변경 → FAIL / ACTION_DIFF
quantity 변경 → FAIL / QUANTITY_DIFF
price 변경 → WARNING / PRICE_DIFF
warning/reason 변경 → WARNING / WARNING_DIFF
metadata only 변경 → PASS 또는 metadata-only status
config_hash 변경 → cause candidate 기록
universe_hash 변경 → cause candidate 기록
JSON/Markdown report 생성
```

## Non-scope

이번 작업에서는 절대 하지 않는다.

```text
Python 코드 구현
CLI 구현
Daily Plan 재생성 실행
Notion API 호출
Notion write/export/sync
actual export
outputs/paper 원장 수정
실제 운영 plan 파일 수정
execution/review replay
schema/view drift 구현
Telegram/Slack/Email 전송
```

## 검증 명령

Windows CMD 기준:

```cmd
git status --short

type docs\TRD\mfu_paper19_replay_same_date_diff_scope_and_contract.md

findstr /N /I "Replay Same-date Diff Daily Plan baseline regenerated fingerprint PASS WARNING FAIL symbol action quantity price warning" docs\TRD\mfu_paper19_replay_same_date_diff_scope_and_contract.md

git diff --check -- docs\TRD\mfu_paper19_replay_same_date_diff_scope_and_contract.md
```

## 구현 후 자체 점검 항목

Codex는 문서 작성 후 아래를 자체 점검하고 결과 보고에 포함한다.

### Scope 점검

- PAPER19가 Daily Plan diff로 제한됐는가
- plan 재생성 자동 실행을 후속으로 남겼는가
- execution/review/Notion replay를 제외했는가
- baseline과 regenerated 정의가 명확한가

### Diff 정책 점검

- 비교 필드가 명확한가
- diff category가 과도하게 많지 않은가
- PASS / WARNING / FAIL 기준이 명확한가
- price tolerance는 후속으로 남겼는가

### Fingerprint 점검

- 원인 후보를 fingerprint 중심으로 기록했는가
- full snapshot 복사를 피했는가
- 원인을 단정하지 않는다고 명시했는가

### Safety 점검

- 코드 수정이 없는가
- Notion API/write/export/sync가 없는가
- outputs/paper 원장 변경이 없는가
- 실제 운영 artifact를 수정하지 않았는가

### Git 점검

- unrelated 파일이 staged 되지 않았는가
- `.env`, `config/notion_settings.json`, outputs/backtest_log.db 등이 staged 되지 않았는가
- git diff --check가 통과했는가

이번 작업은 설계 문서 생성까지만 하고 커밋하지 않는다.  
커밋 후보만 결과 보고에 명시한다.

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

## 성공 기준

- PAPER19-1 설계 문서가 생성됨
- Daily Plan diff 중심 범위가 명확함
- baseline / regenerated 정의가 명확함
- 비교 필드와 diff category가 정의됨
- PASS / WARNING / FAIL 정책이 정의됨
- fingerprint / cause candidate 정책이 정의됨
- output path와 test strategy가 정의됨
- 코드 변경 없음
- Notion/API/write/export/sync 없음
- outputs/paper 원장 변경 없음
- git diff --check 통과

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 생성/수정한 파일
3. PAPER19-1 scope 요약
4. baseline / regenerated 정의
5. 비교 필드
6. diff category
7. PASS / WARNING / FAIL 정책
8. fingerprint / cause candidate 정책
9. output path 정책
10. test strategy
11. Non-scope 정리
12. 코드 변경 여부
13. Notion API/write/export/sync 실행 여부
14. outputs/paper 원장 변경 여부
15. 자체 점검 결과
16. git diff --check 결과
17. 커밋 후보 파일
18. 남은 결정사항
19. PAPER19-2 추천 작업

END MFU-PAPER19-1-REPLAY-SAME-DATE-DIFF-SCOPE
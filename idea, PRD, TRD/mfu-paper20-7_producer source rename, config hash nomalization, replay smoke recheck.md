BEGIN MFU-PAPER20-7-PRODUCER-SOURCE-RENAME-AND-CONFIG-HASH-NORMALIZATION

# PAPER20-7 Producer Source Rename + Config Hash Normalization + Replay Smoke Recheck

## 목적

PAPER20-7에서는 PAPER20-6에서 확인된 config_hash false WARNING의 원인을 해소한다.

핵심 목표:

1. 현재 config snapshot의 `source` 필드가 producer/provenance metadata임을 명확히 한다.
2. 새 산출물에서는 `source` 대신 `producer_source`를 사용한다.
3. `paper_config_hash.v1` normalization에서 `source`와 `producer_source`를 모두 hash 제외 대상으로 처리한다.
4. controlled baseline capture + replay wrapper smoke를 재실행해 config_hash false WARNING이 해소되는지 확인한다.

## 배경

PAPER20-6 분석 결과:

```text
- PAPER20-5 replay smoke overall_status = WARNING
- Daily Plan action/symbol/quantity/price/warning diff = 0
- normalized config diff = source only
- baseline source = capture_daily_plan_baseline
- regenerated source = replay_daily_plan_diff
- semantic config 차이는 확인되지 않음
- config_hash WARNING은 high-confidence false warning으로 분류됨
```

현재 `source`는 전략/유니버스/데이터 source가 아니라 “어떤 producer가 artifact를 만들었는가”를 나타내는 provenance metadata다.

따라서 앞으로는 명시적으로 `producer_source`라는 이름을 사용한다.

## 생성/수정 후보 파일

필요한 파일만 수정한다.

```text
core/paper_config_hash.py
core/daily_plan_generator.py
scripts/dev/capture_daily_plan_baseline.py
scripts/dev/replay_daily_plan_diff.py
tests/test_paper_config_hash.py
tests/test_paper20_capture_daily_plan_baseline.py
tests/test_paper19_replay_wrapper.py
docs/TRD/mfu_paper20_producer_source_rename_and_config_hash_normalization.md
```

실제 수정하지 않은 파일은 stage하지 않는다.

## 구현 요구사항

### 1. source → producer_source 명확화

새로 생성되는 config snapshot 또는 related metadata에서 기존 `source` 대신 `producer_source`를 사용한다.

예:

```json
{
  "producer_source": "capture_daily_plan_baseline"
}
```

또는:

```json
{
  "producer_source": "replay_daily_plan_diff"
}
```

주의:

```text
- producer_source는 artifact를 생성한 도구/명령의 출처다.
- strategy_source, universe_source, market_data_source와 혼동하지 않는다.
- 향후 전략/유니버스/데이터 source는 별도 semantic field로 둔다.
```

### 2. 하위호환 처리

기존 PAPER20-5 artifact에는 `source`가 남아 있을 수 있다.

따라서 normalization에서는 아래 둘을 모두 provenance metadata로 취급한다.

```text
source
producer_source
```

정책:

```text
- 새 산출물: producer_source 사용
- 기존 산출물: source가 있으면 provenance metadata로 인식
- paper_config_hash.v1 hash input에서는 source / producer_source 모두 제외
```

### 3. config hash normalization 보강

`paper_config_hash.v1`에서 아래 필드가 달라도 hash가 같아야 한다.

```text
generated_at
run_id
path-like key
source
producer_source
```

단, 아래 semantic 후보는 함부로 제외하지 않는다.

```text
strategy_source
strategy_profile_id
universe_source
universe_id
market_data_source
config_profile_id
risk_profile_id
```

이런 필드는 plan 결과에 영향을 줄 수 있으므로 향후 별도 정책이 필요하다.

### 4. 테스트 보강

필수 테스트:

```text
source만 다름 → config_hash 동일
producer_source만 다름 → config_hash 동일
source vs producer_source 표현 차이만 있음 → config_hash 동일
strategy_source가 다름 → config_hash 다름
universe_source가 다름 → config_hash 다름
semantic field 변경 시 hash 다름
generated_at/run_id/path/source/producer_source 변경 시 hash 동일
```

### 5. Controlled replay smoke 재실행

구현/테스트 통과 후 PAPER20-5와 같은 controlled smoke를 재실행한다.

Baseline capture:

```cmd
python scripts\dev\capture_daily_plan_baseline.py --account-id paper_sandbox --date 2026-05-26 --output-dir outputs\tmp_paper20_baseline_capture --json
```

Replay smoke:

```cmd
python scripts\dev\replay_daily_plan_diff.py --account-id paper_sandbox --date 2026-05-26 --baseline-plan outputs\tmp_paper20_baseline_capture\daily_action_plan_20260526.json --output-dir outputs\tmp_paper20_replay_smoke --json
```

확인할 것:

```text
- overall_status
- config_hash diff 발생 여부
- action/symbol/quantity/price/warning diff 여부
- safety markers
- generated artifacts stage 금지
```

기대 결과:

```text
config_hash false WARNING이 해소되어 PASS 또는 PASS_WITH_METADATA_DIFF가 되는지 확인한다.
```

만약 여전히 WARNING이면 즉시 수정하지 말고 새 원인을 문서화한다.

## 문서 작성

생성 문서:

```text
docs/TRD/mfu_paper20_producer_source_rename_and_config_hash_normalization.md
```

필수 섹션:

1. Purpose
2. PAPER20-6 False Warning Recap
3. source vs producer_source Decision
4. Hash Normalization Change
5. Backward Compatibility
6. Semantic Source Field Policy
7. Test Coverage
8. Controlled Replay Smoke Recheck
9. Safety Verification
10. Known Limitations
11. PAPER20-8 Recommendation

반드시 명시:

```text
- source는 현재 producer/provenance metadata로 판단한다.
- 새 산출물은 producer_source를 사용한다.
- source/producer_source는 hash input에서 제외한다.
- strategy_source/universe_source/market_data_source는 의미 있는 입력 조건일 수 있으므로 함부로 제외하지 않는다.
- 이번 smoke는 과거 실제 운영 검증이 아니라 current code/current DB/current config 기반 controlled smoke다.
```

## Non-scope

이번 작업에서는 절대 하지 않는다.

```text
strategy_source/universe_source/market_data_source 구현
universe_hash 구현
market_data_asof 구현
indicator_snapshot_hash 구현
state_snapshot_hash 구현
stable plan_item_id 구현
Notion API 호출
Notion write/export/sync
actual export
Manual Execution commit
Manual Review append
source-of-truth ledger commit/append
account/position/current_state 원장 변경
generated smoke artifact 커밋
공식 run_paper_daily_plan.py --output-dir 정식 지원
```

## 검증 명령

Windows CMD 기준:

```cmd
git status --short

python scripts\dev\capture_daily_plan_baseline.py --help
python scripts\dev\replay_daily_plan_diff.py --help

pytest tests\test_paper_config_hash.py
pytest tests\test_paper20_capture_daily_plan_baseline.py
pytest tests\test_paper19_replay_wrapper.py

type docs\TRD\mfu_paper20_producer_source_rename_and_config_hash_normalization.md

findstr /N /I "producer_source source config_hash normalization false warning strategy_source universe_source replay smoke" docs\TRD\mfu_paper20_producer_source_rename_and_config_hash_normalization.md

git diff --check -- core\paper_config_hash.py core\daily_plan_generator.py scripts\dev\capture_daily_plan_baseline.py scripts\dev\replay_daily_plan_diff.py tests\test_paper_config_hash.py tests\test_paper20_capture_daily_plan_baseline.py tests\test_paper19_replay_wrapper.py docs\TRD\mfu_paper20_producer_source_rename_and_config_hash_normalization.md
```

실제 수정하지 않은 파일은 diff check 대상에서 제외해도 된다.

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

stage 후보:

```cmd
git add core\paper_config_hash.py
git add core\daily_plan_generator.py
git add scripts\dev\capture_daily_plan_baseline.py
git add scripts\dev\replay_daily_plan_diff.py
git add tests\test_paper_config_hash.py
git add tests\test_paper20_capture_daily_plan_baseline.py
git add tests\test_paper19_replay_wrapper.py
git add docs\TRD\mfu_paper20_producer_source_rename_and_config_hash_normalization.md
```

실제 수정한 파일만 stage한다.

커밋 메시지:

```cmd
git commit -m "fix: exclude PAPER20 producer source from config hash"
```

## 성공 기준

```text
- 새 산출물에서 producer_source가 사용됨
- 기존 source는 하위호환으로 provenance metadata 처리됨
- source/producer_source 차이만으로 config_hash가 달라지지 않음
- strategy_source/universe_source 차이는 hash에 반영됨
- controlled replay smoke 재실행 결과가 문서화됨
- config_hash false WARNING 해소 여부가 기록됨
- Notion/API/write/export/sync 없음
- outputs/paper 원장 변경 없음
- generated artifacts stage 없음
- 테스트 통과
- git diff --check 통과
- 커밋 완료
```

## 결과 보고 형식

5천자 이내로 보고한다.

1. Summary
2. 생성/수정한 파일
3. source → producer_source 변경 요약
4. 하위호환 처리
5. config_hash normalization 변경 요약
6. semantic source field 정책
7. 테스트 결과
8. controlled baseline capture 재실행 여부
9. replay smoke 재실행 여부
10. overall_status
11. config_hash WARNING 해소 여부
12. diff report paths
13. safety marker 확인 결과
14. generated artifact 생성 여부
15. generated artifact stage 여부
16. Notion API/write/export/sync 실행 여부
17. outputs/paper 원장 변경 여부
18. git diff --check 결과
19. 커밋 생성 여부
20. 커밋 SHA / 메시지
21. 제외한 unrelated 파일
22. 남은 리스크
23. PAPER20-8 추천 작업

END MFU-PAPER20-7-PRODUCER-SOURCE-RENAME-AND-CONFIG-HASH-NORMALIZATION
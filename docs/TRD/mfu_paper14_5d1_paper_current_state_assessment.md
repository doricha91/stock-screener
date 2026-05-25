# MFU-PAPER14-5D-1: paper_current_state Refresh Assessment

## 1. 목적

Manual Executions commit 이후 `paper_current_state_YYYYMMDD.json`을 같은 commit 흐름에 포함해야 하는지 코드 기준으로 판단한다.

이번 PAPER14-5D-1은 paper_current_state_YYYYMMDD.json 포함 여부를 코드 기반으로 판단하는 조사 작업이며, 실제 구현, paper ledger commit, Notion back-write는 수행하지 않았다.

## 2. 조사 파일

- `scripts/import_notion_executions.py`
- `core/paper_manual_execution_commit.py`
- `core/paths.py`
- `scripts/run_paper_eod_update.py`
- `scripts/paper.py`
- `core/paper_account_state.py`
- `core/paper_execution_log.py`
- `core/paper_trade_preview.py`
- `core/paper_commit_guard.py`
- `core/paper_current_state_storage.py`
- `core/paper_current_state_serializer.py`
- `core/paper_state_provider.py`
- `core/paper_status.py`

## 3. 생성 경로

`paper_current_state_YYYYMMDD.json`은 `scripts/run_paper_eod_update.py` commit path에서 생성된다.

구체 흐름:

1. `paper_execution_log.csv`에서 trade rows를 읽는다.
2. `build_paper_state_from_trades()`로 `PaperAccountState`를 재구성한다.
3. `save_paper_current_state()`가 `paper_account_state_to_current_state_dict()`를 사용해
   `outputs/paper_test/paper_current_state_YYYYMMDD.json`을 저장한다.

즉 이 파일은 별도 원천 입력이 아니라 `paper_execution_log.csv`에서 파생되는 derived snapshot이다.

## 4. 사용처

### Daily Plan

직접 사용하지 않는다.

`core/paper_state_provider.py`는 Daily Plan용 official paper state를 `paper_execution_log.csv`에서 다시 계산한다. `paper_current_state_YYYYMMDD.json`을 읽지 않는다.

### status / review / workflow 표시

직접 또는 간접적으로 사용된다.

- `core/paper_status.py`
  - latest current state date
  - current state exists 여부
  - `COMMITTED` workflow 판정
- `core/paper_commit_guard.py`
  - 같은 날짜 current_state 존재 여부를 commit 차단 조건에 포함
- `core/paper_weekly_status.py`
  - day coverage / missing steps 판단에 `current_state_exists` 사용

### Weekly Report

직접 수치 원천은 아니지만, commit coverage completeness 판단에 사용된다.

### Notion export

PAPER14-3 범위의 weekly / benchmark / account / daily plan Notion export는 `paper_current_state`를 직접 읽지 않는다.

### paper current status / operator workflow

사용된다. status와 preflight 성격의 운영 판단에서 “same-date snapshot set complete” 신호로 취급된다.

## 5. stale 위험

Manual Execution commit 후 `paper_current_state`가 stale 또는 missing이면 다음 문제가 생긴다.

1. `paper_status`가 같은 날짜 account/position snapshot은 있는데 current_state는 없는 불완전 상태로 보인다.
2. `paper_weekly_status`가 `MISSING_CURRENT_STATE` 또는 incomplete coverage로 해석할 수 있다.
3. `paper_commit_guard`는 account/position/current_state 3종 중 current_state가 비어 있으므로 같은 날짜 commit 세트가 완결되지 않은 것처럼 보이게 된다.
4. `paper_account_snapshot.csv`의 `source_current_state` provenance가 비게 된다.

반대로 전략 계산 자체의 stale 위험은 제한적이다.

- Daily Plan official state는 execution log에서 재계산한다.
- source of truth는 여전히 execution log / snapshot CSV다.

즉 기능적 거래 의사결정보다 운영 상태 표시와 commit completeness 측면의 stale 위험이 더 크다.

## 6. snapshot CSV와의 관계

관계는 다음과 같다.

- `paper_execution_log.csv` = 최종 원천 ledger
- `paper_account_snapshot.csv` = execution log 기반 계좌 요약 snapshot
- `paper_position_snapshot.csv` = execution log + market valuation 기반 포지션 snapshot
- `paper_current_state_YYYYMMDD.json` = execution log 기반 current holdings/cash/highest price snapshot

모두 execution log에서 파생되지만 용도가 다르다.

- account/position snapshot은 성과/평가/Notion export에 유리
- current_state는 상태 복원/운영 completeness/legacy current-state shape 호환에 유리

따라서 current_state는 source of truth는 아니지만, 기존 paper commit 세트의 일부로 설계되어 있다.

## 7. 선택지 비교

### A. 5D commit 직후 즉시 갱신

장점:

- 같은 execution log 기준으로 derived artifacts 3종 + current_state를 한 번에 정합하게 맞출 수 있다.
- `paper_status`, `paper_weekly_status`, `paper_commit_guard`가 바로 일관된 상태를 본다.
- `run_paper_eod_update.py`의 기존 commit semantics와 가장 가깝다.
- rollback 단위도 “manual execution commit 1회”로 묶기 쉽다.

단점:

- write surface가 하나 늘어난다.
- 5D rollback에 current_state도 포함해야 한다.

### B. 5E Notion status back-write 전에 별도 refresh

장점:

- 5D를 더 작게 유지할 수 있다.

단점:

- 5D와 5E 사이에 stale window가 생긴다.
- status/weekly/guard 결과가 중간 기간 동안 왜곡될 수 있다.
- source of truth는 맞아도 operator-facing completeness가 깨진다.

### C. Daily Review Summary export 직전에 갱신

장점:

- review/export 직전 재생성이라 downstream 문서는 최신일 수 있다.

단점:

- status/weekly/guard stale window가 더 길어진다.
- commit 직후 상태와 review 직전 상태가 달라질 수 있다.
- commit 단위 atomicity가 약해진다.

### D. 현재는 포함하지 않음

장점:

- 구현 영향이 가장 작다.

단점:

- commit 세트가 영구적으로 불완전해진다.
- `paper_status` / `paper_weekly_status` / `paper_commit_guard`와 설계 의도가 어긋난다.
- `source_current_state` provenance가 지속적으로 비게 된다.

## 8. 최종 권고안

권고 A: 5D commit 흐름에 포함

이유:

1. `paper_current_state`는 execution log에서 즉시 재생성 가능한 derived snapshot이다.
2. Daily Plan 계산은 execution log 재계산 기반이라 current_state가 source of truth는 아니지만, 운영 상태/coverage/guard에서는 commit 세트 일부로 사용된다.
3. 이미 `run_paper_eod_update.py`의 공식 EOD commit 흐름이 current_state -> account snapshot -> position snapshot 순으로 저장한다.
4. Manual Execution commit만 current_state를 빼면 같은 프로젝트 안에서 commit semantics가 분기된다.

권고 구현 원칙:

- execution log append 성공 후 같은 `PaperAccountState` 객체로 `paper_current_state`를 같이 저장
- account/position snapshot과 동일 rollback 단위로 묶기
- `source_current_state`도 실제 저장 경로로 채우기

## 9. 반론과 검증

### 반론 1. Daily Plan이 current_state를 안 읽는데 굳이 필요하지 않다

부분적으로 맞다.  
하지만 status / weekly / commit guard는 current_state 존재를 commit completeness 신호로 사용한다. 따라서 “전략 계산에는 불필요”와 “운영 세트에서 제외 가능”은 다르다.

### 반론 2. current_state는 source of truth가 아니니 늦게 갱신해도 된다

원칙 자체는 맞다.  
하지만 늦게 갱신할수록 derived artifact 세트가 날짜 기준으로 분리되고, operator-facing 상태 판단이 왜곡된다.

### 검증 결과

- 생성 경로: `run_paper_eod_update.py`에서 확인
- Daily Plan source: `core/paper_state_provider.py`에서 execution log 기반 재계산 확인
- status usage: `core/paper_status.py`에서 확인
- weekly usage: `core/paper_weekly_status.py` 검색 결과 확인
- guard usage: `core/paper_commit_guard.py`에서 확인

## 10. 후속 MFU 제안

- `PAPER14-5D-2`: Manual Execution commit에 `save_paper_current_state()` 포함
- 같은 작업에서 rollback 범위를 `paper_execution_log / current_state / account_snapshot / position_snapshot` 4종으로 통일

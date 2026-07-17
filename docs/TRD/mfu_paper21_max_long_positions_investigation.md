# 최대 롱 보유 종목 10개 — 코드 조사 결과

## 1. 조사 범위와 기준

- Repository: `D:\python\StockScreener`
- Branch: `gemini_cli_update`
- 조사 기준 HEAD: `073ec9a1688e020742c42dad82e6ab7a43fdbd93`
- 정책: `max_long_positions = 10`은 절대 hard cap
- 기존 `target_long_slots`는 시장 국면별 전략 목표로 별도 유지
- 이번 조사에서는 production, test, DB, Notion schema를 수정하지 않았다.
- “Plan은 있으나 미체결” 상태는 범위에서 제외했다.

조사 당시 working tree에는 기존 Phase 변경과 unrelated dirty 파일이 누적되어 있었다. 특히 `core/daily_plan_generator.py`, runbook 계층, No-action 관련 파일과 테스트가 변경 또는 untracked 상태였으며 모두 보존했다.

## 2. 관련 코드 경로

| 역할 | 파일 | 함수/객체 |
|---|---|---|
| 기본 포트폴리오 설정 | `core/portfolio_config.py` | `PORTFOLIO_CONFIG` |
| 설정 조립 | `core/config_factory.py` | `make_config()`, `get_regime_config()` |
| 국면별 목표 슬롯 | `core/target_portfolio_state.py` | `determine_target_long_slots()` |
| 후보 순위와 목표 종목 | `core/target_portfolio_state.py` | `rank_candidates()`, `select_target_symbols()` |
| 현재/목표 차이 | `core/target_portfolio_state.py` | `compare_symbol_sets()`, `evaluate_rebalance_need()` |
| Daily Plan | `core/daily_plan_generator.py` | `generate_daily_plan()` |
| Active Switching action | `core/daily_plan_generator.py` | `build_switch_action_items()` |
| 일반 전략 진입 | `core/daily_plan_generator.py` | `build_strategy_entry_action_items()` |
| Switching 평가 | `core/backtest_engine.py` | `evaluate_switching_opportunity()` |
| Paper 현재 상태 로드 | `core/paper_state_provider.py` | `load_official_paper_state_for_daily_plan()` |
| 체결 로그 상태 재생 | `core/paper_account_state.py` | `apply_paper_trade()`, `build_paper_state_from_trades()` |
| Current state 직렬화 | `core/paper_current_state_serializer.py` | `paper_account_state_to_current_state_dict()` |
| Position snapshot | `core/paper_position_snapshot.py` | `build_paper_position_snapshot_rows()` |
| Manual Execution 정규화 | `core/notion_manual_execution_importer.py` | `normalize_manual_execution_pages()` |
| Execution Preview | `core/notion_manual_execution_importer.py` | `build_manual_execution_preview()` |
| Preview position loader | `core/notion_manual_execution_importer.py` | `_load_latest_position_shares()` |
| Execution Commit | `core/paper_manual_execution_commit.py` | `commit_manual_execution_preview()` |
| Commit reconciliation | `core/execution_reconciliation.py` | `validate_reconciliation_preview_for_commit()` |
| Commit CLI | `scripts/import_notion_executions.py` | `main()` |
| Manual template export | `core/notion_exporters.py` | `_manual_execution_template_candidates_from_sidecar()` |
| Backtest 실행 | `core/backtest_engine.py` | `run_backtest_with_config()` |

## 3. 현재 `max_positions` 의미와 사용 위치

`core/portfolio_config.py`에는 이미 `max_positions = 10`이 있다. 현재 이 값은 서로 다른 세 책임을 동시에 가진다.

1. `target_long_slots` 계산 기준
2. 종목당 투자금 계산의 분모
3. 백테스트 일반 BUY의 position count 제한

주요 사용처는 다음과 같다.

- `core/target_portfolio_state.py`: `int(max_positions * available_ratio)`
- `core/position_sizing.py`: `total_equity / max_positions`
- `core/daily_plan_generator.py`: 일반 BUY 수량 계산에 전달
- `core/backtest_engine.py`: `len(pf.get_positions()) >= max_positions`
- `core/paper_config_snapshot.py`: 최종 설정 기록
- `core/param_grid.py`: optimizer 값 `[10]`

Paper Preview와 Commit에는 distinct 롱 종목 hard cap 검사가 없다. 따라서 `max_long_positions`를 별도 정책으로 추가하고 기존 `max_positions` 및 `target_long_slots` 의미는 유지해야 한다.

## 4. 현재 보유 포지션 판정

공식 Paper Daily Plan은 execution log를 읽어 `PaperAccountState`를 재생한다.

- 신규 BUY: position dict에 symbol 추가
- 기존 종목 BUY: 기존 shares와 평균단가 갱신
- 부분 SELL: 남은 shares로 position 유지
- 전량 SELL: position dict에서 symbol 제거

따라서 `PaperAccountState.positions`를 기준으로 하면 전량 청산 종목과 quantity 0 종목은 자연스럽게 제외된다.

반면 Preview의 `_load_latest_position_shares()`는 최신 snapshot 날짜의 모든 row를 읽으며 다음을 검사하지 않는다.

- `position_status == OPEN`
- `shares > 0`

공식 snapshot writer는 현재 보유 position만 `OPEN`으로 기록하지만 legacy 또는 외부 row가 섞이는 경우 CLOSED/zero position이 holdings에 포함될 수 있다.

## 5. Daily Plan의 현재 문제

- projected distinct long count를 계산하지 않는다.
- 일반 BUY 생성은 현금과 sizing만 검사한다.
- `REVIEW_EXIT`는 실행 SELL이 아니지만 신규 BUY 슬롯 계산에 반영되지 않는다.
- Target Portfolio에서 제외된 종목이 review-only로 남은 상태에서 신규 target BUY가 추가되면 실제 보유 수가 증가할 수 있다.
- 현재 10개, review-only 제외 1개, 신규 BUY 1개인 경우 11개가 될 수 있다.
- 기존 보유 종목 추가 BUY는 Daily Plan 일반 entry 함수에서 건너뛰지만 Preview/Commit에서는 가능하므로 공통 정책은 이를 distinct 증가로 보지 않아야 한다.

후보 우선순위도 보존되지 않는다. `rank_candidates()`는 score 내림차순, RS 내림차순, symbol 오름차순이지만 `compare_symbol_sets()`가 added symbols를 알파벳순으로 다시 정렬한다. 슬롯보다 후보가 많으면 `target_state.target_symbols`의 원래 순서로 잘라야 한다.

## 6. SELL/BUY 순서와 Active Switching

`build_switch_action_items()`는 각 pair 내부에서는 다음 순서를 만든다.

```text
SWITCH_OUT A
SWITCH_IN B
SWITCH_OUT C
SWITCH_IN D
```

그 뒤 trailing-stop SELL과 일반 BUY가 추가되므로 전체 action에서 모든 SELL 후 모든 BUY는 보장되지 않는다.

Switch 평가 단계의 pair에는 다음 연결 정보가 있다.

- `sell_symbol`
- `buy_symbol`
- `buy_row`
- `worst_h`
- `score_gap`

그러나 Daily Plan JSON과 Notion row에는 구조화된 pair id가 없고 reason 문자열만 남는다. Hard cap은 최종 수량 투영으로 검증할 수 있으므로 pair id가 필수는 아니지만 감사성과 명시적 일대일 교체 보장을 위해 `switch_pair_id`를 sidecar에 추가하는 방안을 권장한다.

현재 switch-out 수량은 보유 shares 전체이므로 Daily Plan 기준으로는 전량 SELL이다.

## 7. Execution Preview의 현재 문제

Preview는 latest cash와 position snapshot을 읽고 candidate를 순차 적용하므로 projected position 계산에 필요한 기본 데이터는 이미 있다. 그러나 다음이 없다.

- distinct position count
- long/hedge 분리
- 신규 symbol BUY와 기존 symbol 추가 BUY 구분
- 전량 SELL과 부분 SELL 구분
- `max_long_positions` 검사
- `target_long_slots` 검사
- projected long count 출력

Candidate 정렬은 `(execution_date, symbol, side, created_time)`이다. SELL 우선순위가 없어 다른 symbol의 BUY가 SELL보다 먼저 계산될 수 있으며, 매도대금 사용 가능 여부가 알파벳순에 영향을 받을 수 있다.

## 8. Execution Commit의 현재 문제

Commit은 Preview와 별도로 execution log의 trade id와 account snapshot을 다시 읽는다. 그러나 최신 상태를 쓰기 전에 재구성해 hard cap을 검사하지 않는다.

현재 순서는 다음과 같다.

```text
Preview JSON 검증
→ duplicate append pre-check
→ backup
→ execution log append
→ 전체 execution log 재생
→ current/account/position snapshot 저장
```

SELL 초과나 cash 부족은 append 후 상태 재생에서 실패하고 rollback될 수 있지만 position cap 위반은 예외 자체가 없다. Preview 후 다른 체결로 계좌 상태가 바뀐 경우에도 cap 위반을 막지 못한다.

권장 순서는 다음과 같다.

```text
Preview JSON 검증
→ 최신 execution log 재생
→ candidate batch 메모리 투영
→ hard cap 독립 검증
→ 성공한 경우에만 backup/append
```

## 9. 헤지 분리

백테스트는 `strategy_name == "Hedge"`로 hedge를 구분하지만 일반 BUY cap은 `len(pf.get_positions())`를 사용하므로 hedge까지 count한다.

Paper execution log와 position snapshot에는 `strategy_name` 또는 `position_role`이 없다. 또한 `paper_account_state_to_current_state_dict()`는 `hedge_symbols=[]`, `current_hedge_ratio=0.0`을 반환한다.

최소 변경은 다음 설정의 합집합을 hedge symbol set으로 사용해 공통 helper에 전달하는 것이다.

```text
config.HEDGE_TICKERS
config.HEDGE_ASSET
```

장기적으로 execution log에 position role을 추가하는 방식이 더 안전하지만 이는 별도 스키마 변경 승인 대상이다.

## 10. 공통 helper 설계

신규 모듈 후보:

```text
core/long_position_policy.py
```

권장 API:

```python
classify_open_positions(...)
calculate_projected_long_positions(...)
calculate_available_long_slots(...)
validate_long_position_limits(...)
```

### `classify_open_positions()`

- symbol 정규화
- shares/quantity가 0보다 큰 position만 open으로 분류
- status가 있으면 `OPEN`만 인정
- hedge symbol을 long 집합에서 제외

### `calculate_projected_long_positions()`

- 현재 symbol별 shares에 실행 BUY/SELL을 적용
- SELL quantity가 현재 shares와 같을 때만 슬롯 확보
- 부분 SELL은 슬롯 미확보
- SELL 초과는 invalid
- 기존 open symbol BUY는 distinct count 불변
- 신규 symbol BUY만 distinct count 증가
- REVIEW_EXIT는 executable action이 아니므로 제외

### `calculate_available_long_slots()`

```text
post_full_sell_count
= current_long_count - confirmed_full_sell_count

raw_general_slots
= max(
    0,
    min(
        max_long_positions - post_full_sell_count,
        target_long_slots - post_full_sell_count
    )
  )
```

Switch-in이 있으면 해당 슬롯을 먼저 예약하거나 일반 BUY 허용 수에서 distinct switch-in 수를 차감해야 한다.

### `validate_long_position_limits()`

권장 오류 코드:

- `max_long_positions_exceeded`
- `target_long_slots_exceeded`
- `sell_does_not_free_position_slot`
- `projected_position_count_invalid`

기존 Paper Preview와 reconciliation 계층의 lower snake case 스타일에 맞는다.

## 11. 계층별 책임

### Daily Plan

- 초과 BUY를 생성하지 않는다.
- 확정 전량 SELL만 슬롯으로 계산한다.
- switch-in 슬롯을 먼저 예약한다.
- 일반 BUY는 전략 후보 순위를 보존해 절단한다.
- 모든 확정 SELL이 BUY보다 먼저 나오도록 action을 안정 정렬한다.

### Execution Preview

- 운영자 수정과 계획 불일치를 차단한다.
- partial SELL 또는 REVIEW_EXIT가 슬롯을 만든 것으로 취급하지 않는다.
- current/projected long count와 오류 코드를 결과에 기록한다.

### Commit

- 최신 execution log를 다시 읽는다.
- 실제 write 전에 독립적으로 projected state를 검증한다.
- 실패 시 execution log와 snapshot을 변경하지 않는다.

### Backtest

- `strategy_name != "Hedge"` position만 long cap에 포함한다.
- hedge 포함 count로 인해 결과가 바뀌면 버그 수정에 따른 의도된 변화로 기록한다.

## 12. 단계별 구현 계획

1. `core/portfolio_config.py`에 `max_long_positions = 10`을 추가한다.
2. `param_grid.py`에는 추가하지 않는다. hard cap은 최적화 대상이 아니다.
3. 순수 계산 모듈 `core/long_position_policy.py`와 단위 테스트를 추가한다.
4. Daily Plan에서 current long 분류, confirmed full SELL, switch reservation, 일반 BUY trimming을 적용한다.
5. Preview snapshot loader에서 OPEN/positive shares만 읽고 공통 검증을 적용한다.
6. Commit이 최신 execution log 기반으로 write 전 독립 재검증하도록 변경한다.
7. Backtest 일반 BUY count에서 hedge를 제외한다.
8. No-action sidecar와 runbook 경로가 빈 action 목록에서 그대로 유지되는지 회귀 검증한다.
9. 동일 MFU의 PRD/TRD 문서를 필요한 범위에서 동기화한다.

예상 production 변경 파일:

```text
core/portfolio_config.py
core/long_position_policy.py
core/daily_plan_generator.py
core/notion_manual_execution_importer.py
core/paper_manual_execution_commit.py
core/backtest_engine.py
scripts/import_notion_executions.py  # commit 오류 코드 전달이 필요한 경우
```

## 13. 필수 테스트 계획

| 시나리오 | 예상 결과 |
|---|---|
| 현재 9개 + 신규 BUY 1개 | projected 10, 허용 |
| 현재 10개 + 신규 BUY 1개 | `max_long_positions_exceeded` |
| 현재 10개 + 전량 SELL 1개 + 신규 BUY 1개 | projected 10, 허용 |
| 현재 10개 + REVIEW_EXIT 1개 + 신규 BUY | BUY 차단 |
| 현재 10개 + 부분 SELL + 신규 BUY | 슬롯 미확보, BUY 차단 |
| 현재 10개 + 기존 종목 추가 BUY | distinct 10, 허용 |
| 현재 10개 + SWITCH_OUT/IN | projected 10, 허용 |
| 현재 11개 + 신규 BUY | 신규 distinct BUY 차단, 자동 SELL 없음 |
| 롱 10개 + 헤지 1개 | long count 10, 정책상 허용 |
| Preview 후 계좌 상태 변경 | Commit 최신 state에서 재검증 후 위반 차단 |
| NO_ACTION Day | `items=[]`, 기존 No-action 경로 회귀 없음 |

추가 테스트:

- CLOSED 및 zero shares snapshot 제외
- SELL 초과 수량 invalid
- target slots 초과 별도 오류
- switch-in 슬롯의 일반 BUY 재사용 방지
- 후보 trimming 순위 보존
- 모든 SELL이 모든 BUY보다 먼저 위치
- direct core commit도 CLI와 동일하게 차단

## 14. No-action 회귀 위험

Daily Plan의 최종 `items`가 비면 기존 `execution_intent.action_mode=NO_ACTION` 경로로 이어져야 한다.

- warning/review item을 executable item에 넣지 않는다.
- 빈 action 목록을 invalid로 처리하지 않는다.
- wrapper와 No-action orchestration을 재설계하지 않는다.
- cap 적용은 최종 executable action 확정 지점에서 수행한다.
- 기존 `build_execution_intent([])` 계약을 회귀 테스트한다.

## 15. 미확정 사항과 권고

1. Paper hedge role metadata가 없으므로 최소 구현에서는 configured hedge ticker set을 사용한다.
2. 시작 상태가 10개 초과이면 projected count가 여전히 10을 초과하는 switch-in도 차단하는 것을 권장한다.
3. 일반 BUY 공식에는 switch-in 예약을 추가 반영해야 hard cap이 유지된다.
4. Preview의 snapshot freshness를 검증하고 Commit의 최종 권위는 execution log 재생 상태로 둔다.
5. 부분 SELL은 거래로 허용하되 position 슬롯을 확보하지 않는 것으로 분리한다.

## 16. 조사 판정

```text
SUCCESS
```

조사 과정에서 production/test/DB/Notion schema 변경과 Git write 작업은 수행하지 않았다.

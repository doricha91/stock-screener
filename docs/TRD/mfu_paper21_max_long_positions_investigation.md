# 최대 롱 보유 종목 hard cap — 조사 및 MFU-SAFE1 최종 결과

> 문서 상태: MFU-SAFE1 구현 및 통합 검증 완료. 아래 1~16절은 구현 전 조사 기록이며,
> 현재 확정 정책과 검증 결과는 17절을 기준으로 한다.

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

## 17. MFU-SAFE1 최종 구현 및 검증 결과

### 17.1 최종 상태와 구현 커밋

MFU-SAFE1은 Paper Daily Plan과 Manual Execution Preview/Commit에 동일한 distinct long
hard-cap 정책을 적용하는 것으로 완료됐다. 구현 커밋은 다음과 같다.

| 단계 | 커밋 | 내용 |
|---|---|---|
| 공통 정책 | `b13353fccc46f9fefe8af6e826eca889c7f0d4f9` | Paper long-position hard-cap 공통 정책과 설정 추가 |
| Daily Plan | `670e666177855c49c4e65efbfe05f1253007d052` | 후보 절단, over-cap 복구, 최종 action 재검증 |
| Manual Execution | `0b93dbf298e43c26c2c51ebb146075b484a44329` | Preview/Commit 독립 hard-cap 재검증과 config hedge SSOT |

통합 검증 기준 HEAD는 `0b93dbf298e43c26c2c51ebb146075b484a44329`이다.

### 17.2 확정 정책

- `max_long_positions`의 SSOT는 `core/portfolio_config.py`의 `PORTFOLIO_CONFIG`이며 기본값은 10이다.
- hard cap은 국면별 목표인 `target_long_slots` 및 sizing용 `max_positions`와 별개다.
- runtime override로 15, 20 같은 값을 주입할 수 있으며 구현에는 literal 10 의존성이 없다.
- `max_long_positions`는 `core/param_grid.py`에 없으며 optimizer 탐색 대상이 아니다.
- hedge SSOT는 호출 시점의 `config.HEDGE_TICKERS`다. symbol은 공통 `normalize_symbol()`로 정규화한다.
- current-state JSON의 `hedge_symbols`는 파생 출력이며 Manual Execution 정책 입력이 아니다.
- config에 없는 custom symbol은 state JSON에 hedge로 기록돼 있어도 일반 long으로 계산한다.

### 17.3 Daily Plan 동작

- 일반 신규 BUY 후보는 기존 전략 순위인 score 내림차순, RS 내림차순, symbol 오름차순을
  보존한 채 사용 가능한 long slot 수로 절단한다.
- 기존 종목 추가매수는 distinct long 수를 증가시키지 않는다.
- 전량 SELL만 slot을 확보하며 부분 SELL과 review-only `REVIEW_EXIT`는 slot을 확보하지 않는다.
- 시작 상태가 cap을 초과하면 active switching과 신규 BUY를 실행하지 않는다.
- over-cap 복구는 유효한 보유 점수를 한 번만 계산한 결과를 사용해 전략 순위가 가장 낮은
  종목부터 필요한 수만큼 전량 `LONG_POSITION_CAP_RECOVERY` SELL을 생성한다.
- 점수를 계산할 수 없는 보유 종목이 있으면 SELL을 추정하지 않고
  `WARNING_LONG_POSITION_RECOVERY_SCORE_UNAVAILABLE` 운영자 확인 경고를 남긴다.
- 모든 action 생성 후 공통 정책으로 다시 검증하며, 위반 시 Markdown/journal/JSON sidecar 기록 전에 중단한다.

### 17.4 Manual Execution Preview/Commit 동작

- Preview는 account-scoped position snapshot과 실제 READY candidate의 `Act_Shares` 및
  `Actual Price`를 사용해 전체 batch를 검증한다.
- Commit은 Preview의 `long_position_policy`, `projected_count`, hedge metadata 또는 validation
  결과를 신뢰하지 않는다.
- Commit은 account-scoped execution log를 다시 replay한 최신 position과 호출 시점의
  `config.HEDGE_TICKERS`로 실제 commit action 전체를 독립 재검증한다.
- cap 위반 batch는 허용 가능한 SELL이 함께 있어도 부분 commit하지 않고 전체 차단한다.
- hard-cap 검증은 append pre-check, backup, execution-log append, snapshot, archive 및 sidecar
  write보다 앞에 있다. 검증 실패 시 persistent write는 0회다.
- `Actual Price`와 `Act_Shares`는 Preview에서 Commit execution row까지 유지된다.

### 17.5 스키마와 백테스트 영향

- DB schema, Notion schema, execution-log 포맷은 변경하지 않았다.
- 최초 MFU-SAFE1 커밋의 부모 `ed421f8d22c34c913bb148dcee7d7717feee01b8`부터 통합 검증
  기준 HEAD까지 `core/backtest_engine.py`, `backtesting/`, `core/optimizer_engine.py`,
  `core/optimizer_storage.py`, `scripts/run_portfolio_backtest.py`, `scripts/run_optimizer.py`,
  `core/param_grid.py`, `core/position_sizing.py`에는 MFU-SAFE1 변경이 없다.
- `core/backtest_engine.py`, `core/param_grid.py`, `backtesting/`에는
  `max_long_positions`, `long_position_policy`, `manual_execution_long_position_cap` 참조가 없다.
- 따라서 Paper hard cap은 backtest engine 실행 경로에 연결되지 않았고 optimizer parameter로도 추가되지 않았다.

### 17.6 통합 테스트와 완전 격리 smoke

`tests/test_mfu_safe1_end_to_end.py`는 다음 실제 경계를 연결한다.

```text
통제된 CurrentPortfolioState
→ generate_daily_plan()
→ Daily Plan JSON action
→ fixture Notion page
→ normalize_manual_execution_pages()
→ build_manual_execution_preview()
→ commit_manual_execution_preview()
→ execution log replay
```

검증 결과:

- 정상 흐름: non-hedge 9종목과 신규 후보 2개에서 Daily Plan이 상위 1개만 선택하고,
  Preview/Commit 후 최종 distinct long이 10임을 확인했다.
- 복구 흐름: non-hedge 11종목에서 최저 점수 1종목의 전량 복구 SELL만 생성하고,
  Preview/Commit 후 최종 distinct long이 10임을 확인했다.
- 상태 변화: Preview 당시 허용된 batch가 Commit 직전 별도 position 추가로 11개가 되면
  Commit 독립 재검증이 전체 batch를 차단하고 persistent write가 0회임을 확인했다.
- `Actual Price`와 `Act_Shares`가 최종 execution row에 그대로 유지됨을 확인했다.
- end-to-end 전용 검증은 3개 테스트가 통과했다.
- 정상/복구 smoke는 `D:\python\mfu_safe1_4_smoke_20260720_211436_2487981`에서 실행했으며
  2개 테스트가 통과했다. account snapshot, position snapshot, execution log, current-state JSON,
  Daily Plan 및 Manual Execution report는 모두 이 고유 외부 경로 아래에서만 생성한 뒤 제거했다.
- 필수 관련 테스트와 무쓰기 switching parity 테스트는 총 150개가 통과했다.
- 유일한 warning은 외부 `pandas_ta`가 사용하는 `pkg_resources` deprecation warning이다.
- 운영 Paper 경로 374개 파일의 경로, SHA-256, UTC timestamp, size manifest가 smoke 전후 동일했다.
- 전체 회귀 실행 중 기존 `tests/test_paper_manual_execution_commit.py`의 default-account fixture가
  운영 archive에 156-byte current-state backup 한 개를 생성하는 격리 한계를 확인했다. 작업 전
  manifest에 없던 이번 실행 산출물임을 이름, 생성 시각, 크기와 SHA-256으로 확인해 해당 파일만
  제거했으며, 최종 운영 manifest는 작업 전 값과 다시 일치했다.

### 17.7 백테스트 실행 판정

`tests/test_smoke_optimizer.py`는 `backtest_log_db_path()`의 SQLite DB에 결과를 기록하므로 실행하지 않았다.
`tests/test_smoke_backtest.py`는 `core.backtest_engine.prepare_market_data()`를 통해 운영 market DB를
읽으며 완전한 임시 DB 격리가 없으므로 실행하지 않았다. 대신 MFU 기준 전체 diff, 실행 경로 참조 검색,
공통 정책 단위 테스트와 파일 write가 없는 `tests/test_paper_switching_parity.py`를 검증했다.

### 17.8 남은 제한 사항과 후속 문서

- Paper position role schema를 추가하지 않았으므로 hedge 분류는 configured ticker에 의존한다.
- Daily Plan과 Manual Execution 사이의 운영자/Notion 검토 경계는 유지되며 직접 자동 실행 API는 없다.
- 이번 검증은 fixture Notion read와 mock valuation을 사용했으며 실제 Notion, Telegram, broker 또는 live 주문을 실행하지 않았다.
- 향후 전체 Manual Execution 회귀 실행에서는 default-account backup 경로도 외부 temp root로
  monkeypatch해 위 테스트 fixture의 운영 archive 생성 가능성을 제거해야 한다.
- 보호 문서 `docs/operations/paper_daily_cycle_commands.md`와
  `idea, PRD, TRD/paper 운영 기능 개발 로드맵 v1.3.md`는 이번 작업에서 수정하지 않았으며 후속 문서 동기화 대상으로 남긴다.

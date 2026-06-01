# MFU-PAPER15-1 Multi-Account Path / Artifact Audit and Account Identity Model

## 1. Purpose

이번 PAPER15-1은 다중계좌 구축 환경 점검을 위한 path/artifact audit 및 account identity model 설계이며, 코드 구현, DB write, paper 원장 수정, Notion write/export, migration 구현은 포함하지 않는다.

이 문서는 현재 stock-screener의 paper 운영 시스템이 단일계좌 전제를 얼마나 강하게 가지고 있는지 조사하고, 향후 다중계좌 확장을 위해 필요한 최소 account identity 모델을 제안한다.

## 2. Scope / Non-scope

### Scope

- `outputs/paper_test` 고정 의존성 조사
- paper account/report/review artifact의 계좌별 분리 필요성 평가
- `PaperAccountState` 및 관련 저장 계층의 account identity 부재 여부 확인
- Notion import/export/status sync의 계좌 충돌 가능성 평가
- backward compatibility 관점에서 default account 해석 가능성 검토

### Non-scope

- 코드 구현
- migration script 작성
- DB schema 변경
- artifact 파일명 변경
- `paper.py` CLI 변경
- Notion actual write/export 실행

## 3. Current Single-Account Assumptions

현재 paper 운영은 구조적으로 “단일 environment + 단일 paper account”를 전제한다.

핵심 징후는 아래와 같다.

1. `core/paths.py`가 `PAPER_TEST_DIR = outputs/paper_test`를 전역 상수로 고정한다.
2. 주요 원장/derived artifact가 모두 고정 파일명 하나를 사용한다.
3. `PaperAccountState`에는 `account_id`, `display_name`, `strategy_profile` 같은 계좌 식별 정보가 없다.
4. `paper_status`, `paper_weekly_status`, `paper_benchmark_comparison`, `paper_daily_review_summary`가 모두 단일 `paper_root`를 기준으로 동작한다.
5. Notion external key가 날짜나 심볼만 포함하고 account dimension이 없다.

즉 현재 구조는 “paper_test 아래 하나의 계좌 세계관”을 공유한다고 보는 것이 맞다.

## 4. Path / Artifact Dependency Audit

### 4.1 `core/paths.py`

가장 강한 단일계좌 고정점이다.

- `PAPER_TEST_DIR = outputs/paper_test`
- `paper_execution_log_path() -> outputs/paper_test/paper_execution_log.csv`
- `paper_account_snapshot_path() -> outputs/paper_test/paper_account_snapshot.csv`
- `paper_position_snapshot_path() -> outputs/paper_test/paper_position_snapshot.csv`
- `paper_current_state_snapshot_path(date) -> outputs/paper_test/paper_current_state_YYYYMMDD.json`
- `paper_daily_action_plan_path(date) -> outputs/paper_test/daily_action_plan_YYYYMMDD.md`
- `paper_reports_dir() -> outputs/paper_test/reports`
- `paper_reviews_dir() -> outputs/paper_test/reviews`
- `paper_config_snapshots_dir() -> outputs/paper_test/config_snapshots`
- `paper_replay_diff_dir() -> outputs/paper_test/replay_diff`
- `dev_backups_dir() -> outputs/dev_backups`

판단:

- 현재 path resolver는 `account_id` 개념을 전혀 모른다.
- 다중계좌 도입 시 가장 먼저 영향받는 계층이다.

### 4.2 `core/paper_account_state.py`

현재 `PaperAccountState`는 아래 정보만 가진다.

- `cash`
- `currency`
- `positions`
- `applied_trade_ids`
- `realized_pnl`
- `realized_pnl_by_symbol`

부재:

- `account_id`
- `display_name`
- `broker`
- `account_type`
- `strategy_profile`
- `universe_profile`

판단:

- 메모리상의 상태 객체도 단일계좌 전제다.
- 특히 `applied_trade_ids`가 계좌별 namespace 없이 한 집합으로 관리된다.

### 4.3 `core/paper_execution_log.py`

고정 전제:

- `assert_paper_path(log_path, PAPER_TEST_DIR)`
- `PAPER_EXECUTION_LOG_COLUMNS`에 `account_id`가 없다.
- `trade_id`는 `date/symbol/side/shares/price/reason/source` 해시로 생성된다.

리스크:

- 동일 날짜에 다른 계좌가 같은 수동 execution을 넣으면 `trade_id` 충돌 가능성이 있다.
- ledger를 합쳐 두면 duplicate 방지 로직이 계좌 간 거래까지 중복으로 볼 수 있다.

판단:

- `paper_execution_log.csv`는 계좌별 분리가 사실상 필수다.

### 4.4 `core/paper_account_snapshot.py`

고정 전제:

- `assert_paper_path(snapshot_path, PAPER_TEST_DIR)`
- row schema에 `account_id`가 없다.
- `snapshot_date` 기준으로 same-date row를 replace한다.

리스크:

- 동일 날짜에 계좌가 2개면 하나의 CSV에서 row가 섞인다.
- `save_paper_account_snapshot()`는 same-date replace이므로 account dimension이 없으면 다른 계좌 row를 덮어쓸 수 있다.

판단:

- `paper_account_snapshot.csv`는 계좌별 분리가 필수다.

### 4.5 `core/paper_position_snapshot.py`

고정 전제:

- `assert_paper_path(snapshot_path, PAPER_TEST_DIR)`
- row schema에 `account_id`가 없다.
- `snapshot_date` 기준으로 같은 날짜 row를 replace한다.

리스크:

- 동일 심볼을 여러 계좌가 보유하면 한 CSV에서 계좌 구분이 없다.
- same-date replace가 계좌별 row를 날릴 수 있다.

판단:

- `paper_position_snapshot.csv`도 계좌별 분리가 필수다.

### 4.6 `core/paper_current_state_storage.py` / `core/paper_current_state_serializer.py`

고정 전제:

- `paper_current_state_YYYYMMDD.json`
- payload에 `account_id`가 없다.
- serializer는 `current_symbols`, `shares`, `avg_price`, `highest_prices`, `absolute_cash`만 쓴다.

리스크:

- 날짜당 하나의 current state만 저장할 수 있다.
- 같은 날짜에 두 계좌 state를 따로 저장할 수 없다.

판단:

- `paper_current_state_YYYYMMDD.json`은 계좌별 분리가 필수다.

### 4.7 `core/paper_status.py`

고정 전제:

- default root는 `PAPER_TEST_DIR`
- `build_paper_status_paths()`가 단일 `paper_root` 아래 `reports`, `reviews`, snapshot csv를 고정한다.
- latest date 판정도 하나의 account timeline만 전제한다.

리스크:

- 다중계좌가 한 root를 공유하면 `workflow_status`가 계좌 혼합 상태가 된다.
- Daily Ops Status Dashboard의 per-account view가 불가능하다.

판단:

- status 계층은 `account_id` 또는 account-specific root 없이 안전하지 않다.

### 4.8 `core/paper_weekly_status.py`

고정 전제:

- default root는 `PAPER_TEST_DIR`
- account/position/execution을 모두 단일 root에서 읽는다.
- output도 `paper_weekly_status_summary.md/json` 하나다.

리스크:

- 주간 coverage, equity 변화, trade summary, review summary가 계좌 간 섞인다.

판단:

- weekly status는 account-specific root 또는 account_id-aware aggregator가 필요하다.

### 4.9 `core/paper_benchmark_comparison.py`

고정 전제:

- root default는 `paper_account_snapshot_path().parent`
- `initial_cash`를 snapshot 첫 row에서 읽는다.
- paper vs benchmark 비교를 단일 equity curve로 본다.

리스크:

- 여러 계좌가 섞이면 benchmark 비교가 무의미해진다.
- `initial_cash`도 어떤 계좌의 값인지 모호해진다.

판단:

- benchmark report는 계좌별 분리가 필수다.

### 4.10 `core/paper_daily_review_summary.py`

고정 전제:

- report index와 report path 문자열이 `outputs/paper_test/reports/...`로 하드코딩돼 있다.
- summary는 하나의 account-level report 묶음을 전제한다.

리스크:

- review summary가 특정 계좌가 아니라 paper_test 전체를 대표하는 문서로 굳어진다.

판단:

- daily review summary와 report index도 계좌별 분리가 권장된다.

### 4.11 `core/paper_manual_execution_commit.py`

고정 전제:

- `paper_execution_log_path()`
- `paper_account_snapshot_path()`
- `paper_position_snapshot_path()`
- `paper_current_state_snapshot_path(execution_date)`
- `PAPER_TEST_DIR / "archive"`
- `paper_reports_dir()`

리스크:

- manual execution commit이 항상 단일 계좌 원장을 갱신한다.
- sidecar report는 `manual_execution_import_commit_YYYYMMDD.*` 하나다.

판단:

- commit path 자체가 single-account commit pipeline이다.

### 4.12 `core/paper_manual_review_append_commit.py`

고정 전제:

- `paper_reviews_dir() / "paper_manual_review_log.csv"`
- `paper_reviews_dir() / "paper_manual_review_log_template.csv"`
- `paper_reports_dir()`
- `dev_backups_dir()`

리스크:

- review log와 template가 계좌 구분 없이 누적된다.
- 같은 `review_date/symbol/question_id` 조합은 계좌 간 충돌 가능성이 있다.

판단:

- manual review log 계층도 계좌별 분리가 권장된다. 실무적으로는 거의 필수에 가깝다.

### 4.13 Notion export/import/status sync

확인된 external key 예:

- `weekly_report:{start}:{end}`
- `benchmark:{latest_snapshot_date}:{run_mode}`
- `account_snapshot:{snapshot_date}`
- `daily_plan:{plan_date}`
- `daily_review_summary:{review_date}`
- `manual_execution:{execution_date}:{symbol}:{side}:{seq}`
- `manual_review:{review_date}:{symbol}:{question_id}`

리스크:

- 계좌 dimension이 external key에 없다.
- account-specific data source를 따로 두지 않으면 서로 overwrite / duplicate / stale sync 충돌이 가능하다.
- `NOTION_*_DATA_SOURCE_ID`도 현재는 target별 1개만 전제한다.

판단:

- Notion 계층은 계좌 충돌 가능성이 높다.
- account-aware external key 또는 account-specific Notion profile이 필요하다.

### 4.14 `scripts/paper.py`, `scripts/export_paper_to_notion.py`, import/sync scripts

고정 전제:

- `paper.py`는 `PAPER_TEST_DIR`를 암묵 기본 root로 사용한다.
- `export_paper_to_notion.py`도 account 선택 인자가 없다.
- execution/review import/status sync도 특정 계좌를 고르는 파라미터가 없다.

판단:

- CLI 계층은 아직 “현재 기본 paper account 하나”만 다룬다.

## 5. Artifact Classification

### A. 계좌별로 반드시 분리해야 하는 artifact

| artifact | 분류 이유 | 다중계좌 리스크 | 권장 방향 |
|---|---|---|---|
| `outputs/paper_test/paper_execution_log.csv` | trade ledger 자체가 계좌 상태를 결정 | trade_id 중복, 계좌 간 ledger 오염 | account-specific output root 또는 `account_id` column |
| `outputs/paper_test/paper_account_snapshot.csv` | cash/equity/position_count가 계좌 상태에 종속 | same-date replace 충돌 | account-specific root 또는 `account_id + snapshot_date` |
| `outputs/paper_test/paper_position_snapshot.csv` | holdings와 valuation이 계좌 종속 | 동일 심볼 보유 시 혼합 | account-specific root 또는 `account_id + snapshot_date + symbol` |
| `outputs/paper_test/paper_current_state_YYYYMMDD.json` | current cash/positions/highest price가 계좌 종속 | 날짜당 하나만 존재 가능 | account-specific root 또는 파일명에 account_id 포함 |
| `outputs/paper_test/daily_action_plan_YYYYMMDD.md` | plan 자체가 계좌/전략별로 달라질 수 있음 | 어떤 계좌의 plan인지 불명확 | account-specific root 권장 |
| `outputs/paper_test/reports/paper_weekly_status_summary.*` | status/equity/trade/review 요약이 계좌 종속 | dashboard 오염 | 계좌별 분리 |
| `outputs/paper_test/reports/paper_benchmark_comparison.*` | benchmark 비교는 계좌 초기자본과 equity curve에 종속 | benchmark 비교 무효화 | 계좌별 분리 |
| `outputs/paper_test/reports/paper_daily_review_summary.md` | 하루 운영 결과 요약이 계좌 종속 | review layer 오염 | 계좌별 분리 |

### B. 계좌별 분리가 권장되는 artifact

| artifact | 이유 | 다중계좌 리스크 | 권장 방향 |
|---|---|---|---|
| `outputs/paper_test/reviews/` 전체 | review template/log가 계좌별 decision context를 반영 | 같은 질문 key 충돌, review backlog 혼합 | 계좌별 review root |
| `outputs/paper_test/reports/paper_symbol_review_buckets.csv` | review bucket이 보유/손익 상태에 종속 | symbols/review priority 혼합 | 계좌별 분리 |
| `outputs/paper_test/reports/paper_symbol_review_worksheet.csv` | review 질문이 계좌별 holdings/performance에서 파생 | worksheet 혼합 | 계좌별 분리 |
| `outputs/paper_test/config_snapshots/` | plan 생성 시점의 config provenance | 어떤 계좌 config인지 모호 | 계좌별 분리 |
| `outputs/paper_test/replay_diff/` | regenerated plan diff가 계좌 context를 전제 | diff 결과 혼선 | 계좌별 분리 |
| Notion external key namespace | 현재는 날짜/심볼만 사용 | page overwrite / duplicate | external key에 account_id 포함 |
| Notion data source profile | 계좌마다 view/filter/ownership 다를 수 있음 | 같은 DB에서 계좌 혼재 | account-specific notion_profile 검토 |

### C. 공통으로 유지해도 되는 artifact

| artifact | 이유 | 주의점 |
|---|---|---|
| `outputs/dev_backups/` | backup staging 디렉터리는 공통으로 둘 수 있음 | 파일명에 account_id 포함 필요 |
| `outputs/market_data.db` | market data는 계좌 공통 source | 전략/유니버스 분리와는 별개 |
| `outputs/backtest_log.db` | optimizer/backtest 로그는 paper account identity와 직접 동일하지 않음 | live/paper/profiles 분리 규칙은 별도 필요 |
| 공통 TRD / ops 문서 | 시스템 설계 문서 자체는 공통 유지 가능 | account-aware 예시 추가 필요 |

### D. 추가 조사가 필요한 artifact

| artifact | 이유 | 추가 조사 포인트 |
|---|---|---|
| `outputs/front_test/` 전체 | paper와 front-test 경계가 현재 디렉터리로 분리됨 | 다중계좌 도입 시 front/paper/account 축을 어떻게 조합할지 |
| `paper_realized_trade_journal.csv` 및 downstream realized reports | 현재는 execution log에서 파생 | account-aware realized PnL key 설계 필요 |
| report regeneration safety / audit reports | 현재 paper_test reports를 기준으로 생성 | 계좌별 최신 report semantics 필요 |
| notion settings/mapping 구조 | data source id가 target별 1개 전제 | account profile별 mapping override가 필요한지 |

## 6. Account Identity Field Candidates

후보 필드를 아래처럼 나눌 수 있다.

### Core identity

- `account_id`
- `display_name`
- `account_type`
- `is_default`

### Financial identity

- `currency`
- `initial_cash`

### Operating profile

- `strategy_profile`
- `universe_profile`
- `benchmark_profile`
- `notion_profile`

### External/broker identity

- `broker`

## 7. Recommended Minimum Account Identity Model

권장 최소 모델:

```text
account_id
display_name
currency
initial_cash
account_type
is_default
```

권장 예시:

```json
{
  "account_id": "paper_default",
  "display_name": "Paper Default",
  "currency": "USD",
  "initial_cash": 100000.0,
  "account_type": "paper",
  "is_default": true
}
```

### 필드별 판단

#### `account_id`

필수다.

이유:

- path namespace
- artifact key namespace
- Notion external key namespace
- backup/report naming

을 모두 묶는 최소 식별자다.

#### `display_name`

강력 권장이다.

이유:

- operator UI / dashboard / Notion에서 사람 친화적으로 구분해야 한다.
- 다만 machine identity는 `account_id`가 맡아야 한다.

#### `currency`

최소 모델에 포함하는 것이 맞다.

이유:

- account snapshot / benchmark / performance summary 해석에 직접 영향
- 향후 multi-currency 확장과 충돌 방지

#### `initial_cash`

최소 모델에 포함하는 것이 맞다.

이유:

- benchmark comparison, return baseline, reset semantics에 필요
- 현재도 snapshot과 benchmark 계층이 `initial_cash`에 의존한다.

#### `account_type`

최소 모델에 포함 권장한다.

권장 값:

- `paper`

이유:

- 지금은 paper 전용이어도 naming을 너무 paper-only로 잠그기보다, 나중에 `live`, `broker_sim`, `sandbox`를 구분할 수 있는 최소 여지를 두는 편이 낫다.

#### `is_default`

최소 모델에 포함 권장한다.

이유:

- 기존 단일계좌 backward compatibility를 자연스럽게 유지할 수 있다.
- CLI에서 account 미지정 시 fallback account를 정하는 데 필요하다.

### 이번 최소 모델에서 제외 권장

#### `strategy_profile`

계좌 identity보다는 별도 config/profile layer가 적절하다.

이유:

- 전략 실험이 바뀌어도 계좌 자체 identity가 바뀌는 것은 아니다.
- 다만 account와 profile의 연결은 별도 참조 필드로 둘 수 있다.

#### `universe_profile`

`strategy_profile`과 같은 이유로 identity core에서는 제외 권장.

#### `benchmark_profile`

계좌 core identity가 아니라 report/export policy에 가깝다.

#### `notion_profile`

필요성은 높지만 최소 identity core보다는 integration profile에 가깝다.

#### `broker`

현재 paper 전용에서는 optional metadata로 두는 편이 적절하다.

## 8. Backward Compatibility Considerations

### 8.1 기존 단일계좌를 default account로 해석 가능한가

가능하다. 그리고 그렇게 하는 것이 가장 안전하다.

권장 해석:

- 기존 `outputs/paper_test` = `account_id = paper_default`

이 방식의 장점:

- 기존 artifact를 즉시 invalid로 만들지 않는다.
- migration 없이도 “legacy default account”라는 의미를 줄 수 있다.

### 8.2 과거 데이터에 account_id가 없을 때

아래 규칙으로 backward compatibility를 둘 수 있다.

```text
account_id가 없으면 paper_default로 해석
```

단, 이 해석은 다음 전제를 가진다.

- 과거 파일들이 실제로는 한 계좌만 담고 있었다.
- 같은 date/symbol/trade 조합이 여러 계좌에서 섞인 legacy data는 없었다.

### 8.3 Path compatibility

권장 방향:

- 1단계: 기존 `outputs/paper_test`를 `paper_default`의 legacy root로 인정
- 2단계: 신규 계좌는 `outputs/paper_accounts/{account_id}/...` 같은 구조로 분리
- 3단계: resolver가 legacy root와 new root를 모두 읽을 수 있게 전환

### 8.4 Notion compatibility

기존 external key는 모두 account dimension이 없다.

예:

- `account_snapshot:2026-05-25`
- `daily_plan:2026-05-25`
- `manual_execution:2026-05-25:AAPL:BUY:01`

다중계좌 시 권장 방향:

```text
account_snapshot:{account_id}:{snapshot_date}
daily_plan:{account_id}:{plan_date}
manual_execution:{account_id}:{execution_date}:{symbol}:{side}:{seq}
manual_review:{account_id}:{review_date}:{symbol}:{question_id}
```

즉 backward compatibility는 가능하지만, Notion key namespace 변경은 후속 migration/dual-read 전략이 필요하다.

## 9. Open Questions

1. multi-account path를 `outputs/paper_accounts/{account_id}` 형태로 둘지, `outputs/paper_test/{account_id}` 형태로 둘지
2. `front_test`와 `paper_test`를 environment 축으로 유지할지, environment/account 2단 path로 갈지
3. `strategy_profile`, `universe_profile`, `benchmark_profile`을 identity model에 넣을지, 별도 account config 참조로 둘지
4. Notion data source를 계좌별로 완전히 분리할지, 한 DB에서 `account_id` property로 같이 운영할지
5. benchmark comparison의 `initial_cash`와 reset semantics를 계좌별로 어떻게 명시할지
6. `dev_backups/` 파일명 규칙에 account_id를 반드시 넣을지
7. current `paper_weekly_status`와 `paper_status`를 account root 방식으로 일반화할지, CSV에 `account_id` column을 추가할지

## 10. Recommended Next MFU

권장 다음 단계:

### MFU-PAPER15-2

`path resolver / CLI account scope audit`

범위 권장:

- account-aware path resolver 초안
- legacy `paper_test` -> `paper_default` compatibility 전략
- `paper.py`, import/export/sync CLI에 `--account-id`를 넣을 때 영향 범위 조사

그 다음 단계 후보:

### MFU-PAPER15-3

`artifact schema and external key migration plan`

범위 권장:

- execution/account/position/current_state/review log의 `account_id` 반영 방식
- Notion external key namespace 전환안
- report root와 backup naming 전환안


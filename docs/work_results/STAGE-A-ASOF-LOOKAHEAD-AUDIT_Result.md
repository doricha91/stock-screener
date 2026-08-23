# STAGE-A-ASOF-LOOKAHEAD-AUDIT Result

## Summary

- 기준 브랜치/HEAD: `gemini_cli_update` / `7945ea854faf025db8fd0710e24f5209a32e9f9b`
- 조사 대상: `paper_pilot_202606`, `DATA_DATE=2026-08-13`, `TRADE_DATE=2026-08-14`, `runbook_day_id=paper_pilot_202606_2026-08-13_2026-08-14`
- 실제 Stage A 실행 시각: 2026-08-16 12:52:50~13:06:25 KST
- 종합 판정: **CONFIRMED**. 가격/시장국면/지표/RS cutoff는 작동했지만, 2026-08-16에 조회한 실시간 ticker 및 지수 구성종목을 2026-08-13 입력처럼 사용했다. 실제 후보 DAY·POOL이 이 미래 관측 유니버스 때문에 제외되었다.
- 이 작업은 조사와 수정 설계만 수행했다. 소스, 테스트, runbook state, 운영 산출물 및 DB는 변경하지 않았다.

## 2026-08-14 incident finding

판정은 **CONFIRMED**다.

1. `01_stage_a_plan_prep.cmd`는 2026-08-16에 `DATA_DATE=2026-08-13`, `TRADE_DATE=2026-08-14`로 Stage A를 실행했다.
2. Step 1 `prepare-data --date 2026-08-13 --universe`의 날짜 인자는 산출물 label에만 쓰였다. `update_market_indices()`, `update_tickers_info()`, `update_stock_data()` 및 `fetch_live_basket_symbols()`는 상한 날짜 없이 실행 시점의 최신 자료를 수집했다.
3. `universe_snapshot_20260813.json`은 2026-08-16 12:59:51 KST에 생성되었고 `as_of`를 2026-08-13으로 기록했다. 실제 관측 시각/원천 유효일은 저장하지 않았다.
4. Daily Plan은 최신 `tickers` 테이블을 screen 모집단으로 사용하고 위 스냅샷의 `removed`만 제외했다. 실행 로그는 후보 DAY·POOL을 `Freshness Guard`가 제외했음을 명시한다. 따라서 미래에 관측한 구성종목 정보가 실제 의사결정 입력에 들어갔다.
5. 반면 네 주문의 가격은 모두 2026-08-13 DB 종가와 정확히 일치하고 2026-08-14 종가와 다르다.

| canonical key | symbol | side | qty | plan price | 2026-08-13 close | 2026-08-14 close | 가격 판정 |
|---|---:|---:|---:|---:|---:|---:|---|
| `manual_execution:paper_pilot_202606:2026-08-14:AXON:SELL:01` | AXON | SELL | 15 | 615.5900268554688 | 615.5900268554688 | 612.8300170898438 | 8/13 일치 |
| `manual_execution:paper_pilot_202606:2026-08-14:MRK:BUY:01` | MRK | BUY | 68 | 135.5500030517578 | 135.5500030517578 | 135.83999633789062 | 8/13 일치 |
| `manual_execution:paper_pilot_202606:2026-08-14:VRTX:SELL:01` | VRTX | SELL | 15 | 516.4400024414062 | 516.4400024414062 | 505.75 | 8/13 일치 |
| `manual_execution:paper_pilot_202606:2026-08-14:CSGP:BUY:01` | CSGP | BUY | 234 | 33.04999923706055 | 33.04999923706055 | 32.380001068115234 | 8/13 일치 |

실제 네 주문이 미래 유니버스가 없었어도 동일했을지는 **CANNOT EXCLUDE**다. DAY·POOL을 포함한 대체 실행 산출물이 없고, 당시 원천 유니버스의 역사적 구성도 보존되지 않았기 때문이다. 다만 입력 오염과 실제 후보 제외 자체는 확인되므로 사고 전체 판정은 `CONFIRMED`다.

## Stage A call graph

| 단계 | 호출/입력 | 날짜 선택 | 산출물 | 다음 소비자 |
|---|---|---|---|---|
| wrapper | `ops/runbook_wrappers/01_stage_a_plan_prep.cmd` | env의 DATA_DATE/TRADE_DATE를 그대로 전달 | Stage A stdout | `runbook_stage_runner.py stage-a` |
| runner | `run_stage_a()` → registry Step 0~5 | frozen context | command result, state, summary | 각 command 및 Gate 1 |
| Step 0 | `paper_daily_ops.py status` | data/trade date 명시 | `000_status.json/log/txt` | operator 상태 |
| Step 1 | `paper.py prepare-data --date DATA_DATE --universe` → `run_paper_prepare_data()` | label은 DATA_DATE, 수집 상한 없음 | market DB, ticker metadata, universe snapshot | freshness, market/screener/universe readers |
| Step 2 | `paper.py data-freshness --date DATA_DATE` → `run_paper_data_freshness_check()` | target_date와 DB의 전체 MAX 비교 | `002_data_freshness.*` | Stage A 통과 조건 |
| Step 3 entry | `paper.py plan --data-date ... --trade-date ...` → `run_paper_daily_plan()` | 명시 날짜 검증 | account-scoped plan/config snapshot | `generate_daily_plan()` |
| market | `get_market_state(target_date=DATA_DATE)` | `daily_indicators MAX(date) <= DATA_DATE`; index `date <=` | market state | regime/config overlay, plan |
| candidates | `build_screener_results(end_date=DATA_DATE)` | price SQL `date <= DATA_DATE` | 후보/재계산 지표 | score/RS/target state |
| RS | `load_market_index_series(... end_date=DATA_DATE)` 및 `calculate_candidate_rs_val()` | benchmark/stock 모두 `<= DATA_DATE` | RS 값 | candidate ranking |
| universe | `load_universe_snapshot_as_of_quarter(DATA_DATE)` | 파일명의 날짜 `<= DATA_DATE` | active/removed + metadata | 현재는 removed 제외에만 사용 |
| account | `load_official_paper_state_for_daily_plan(DATA_DATE)` | execution rows `<= DATA_DATE` | CurrentPortfolioState | holdings/cash/sizing |
| config | `make_config()` + regime overlay | 실행 시점 현재 코드/설정; snapshot은 TRADE_DATE 이름 | config snapshot/hash | scoring/sizing 및 Notion export |
| plan artifact | `generate_daily_plan()` | payload data/trade date | MD/JSON, pinned workspace copy | Step 4/5, Gate 1 |
| Step 4 | `export_paper_to_notion.py --daily-plan --date TRADE_DATE` | plan/config artifact date | Notion Daily Plan row | operator |
| Step 5 | `--manual-execution-template --date TRADE_DATE` | plan JSON items | 4 execution template rows | Gate 1/manual input |

## AS-OF Contract Gap Matrix

| source | 실제 선택 | DATA_DATE 상한 | 실제 사고 판정 | gap |
|---|---|---|---|---|
| Market price/index | DB는 8/14까지 저장; readers는 `<= 8/13` | 강제됨 | **EXCLUDED** | lineage가 plan에 기록되지 않음 |
| Indicators | prepare는 8/14까지 계산; market reader는 `<= 8/13`, screener는 cutoff price로 재계산 | 강제됨 | **EXCLUDED** | freshness가 target row가 아니라 global MAX 정렬을 검사 |
| RS | stock/benchmark 모두 `end_date=8/13` | 강제됨 | **EXCLUDED** | 실제 source max date가 artifact에 없음 |
| Universe/ticker set | 8/16 실시간 수집을 `as_of=8/13`으로 저장; latest tickers가 screen 모집단 | 강제되지 않음 | **CONFIRMED** | observed_at/effective date 부재, active_symbols 미사용 |
| Account state | executions `<= 8/13`; 실제 state snapshot도 8/13 | 강제됨 | **EXCLUDED** | fingerprint selector는 trade date를 cutoff로 사용 가능 |
| Config | 8/16 실행 시 현재 config로 생성, 8/14 이름으로 저장 | 역사 버전 강제 없음 | **CANNOT EXCLUDE** | effective_at/source revision/replay policy 부재 |

## Market / Indicator / RS findings

- DB는 현재도 `daily_price`, `daily_indicators`, `market_index` 모두 최대 2026-08-14다. Step 1 수집 함수에는 end date가 없으므로 실행 당시에도 DATA_DATE 이후 행을 저장한 구조다.
- 이 저장 자체는 Option B 모델에서는 허용 가능하다. 실제 소비자가 강제 cutoff를 적용하기 때문이다.
- 시장국면은 `_coerce_date()`가 `MAX(daily_indicators.date) WHERE date <= target_date`를 사용하고 `_get_market_series()`가 `date <= end_date`를 사용한다. 실제 config snapshot의 market state date도 2026-08-13이다.
- screener는 `get_price_data(..., end_date=signal_date)`를 호출하고 SQL 및 후속 dataframe 양쪽에서 cutoff한다. 모든 기술지표는 그 잘린 price frame에서 다시 계산된다.
- 후보 RS와 보유종목 재평가도 stock/benchmark 데이터를 2026-08-13까지만 읽는다.
- 네 주문 가격 및 로그의 MRK/CSGP 후보 가격은 8/13 종가와 일치한다. 따라서 이 세 source에서 실제 미래행 사용은 배제한다.
- 남은 문제는 provenance다. plan에는 각 계산의 source max date가 없어 코드와 DB를 재대조해야만 배제할 수 있다.

## Universe findings

- `refresh_universe_snapshot_for_date()`는 실행 당일의 Wikipedia S&P 500/NASDAQ-100을 읽으면서 payload `as_of`에는 요청한 과거 날짜를 넣는다.
- snapshot 파일 생성 시각은 2026-08-16 12:59:51 KST로 DATA_DATE 및 TRADE_DATE보다 늦다.
- `build_screener_results()`의 기본 ticker는 최신 DB `tickers` 테이블이다. snapshot `active_symbols`는 ticker 입력으로 전달되지 않고 `removed`만 사후 제외에 사용된다.
- 실제 로그에서 8개 후보 중 DAY·POOL이 이 removed set 때문에 제외되었다. 그러므로 단순 잠재 위험이 아니라 실제 decision path 오염이다.
- 파일명/`as_of` label이 데이터 관측 시점을 증명하지 않으므로 현재 `quarterly_as_of` loader만으로는 historical as-of가 보장되지 않는다.

## Account state findings

- `load_official_paper_state_for_daily_plan(2026-08-13)`은 execution log를 2026-08-13 이하로 제한한다.
- 실제 execution log의 마지막 날짜는 2026-08-13이고, pinned state fingerprint는 `paper_current_state_20260813.json`이다. 파일도 2026-08-13 23:32 KST에 마지막 기록되었다.
- 실제 입력 오염은 배제한다.
- 설계 gap: `run_paper_daily_plan()`은 fingerprint용 snapshot을 `latest_current_state_snapshot_path(account_paths, normalized_db_date)`로 선택하여 trade date까지 허용한다. 현재 사고에서는 8/14 snapshot이 없어 안전했지만, 존재하면 계산 state와 fingerprint가 불일치할 수 있다. cutoff를 반드시 `normalized_data_date`로 바꿔야 한다.

## Config findings

- `make_config()`는 현재 `PORTFOLIO_CONFIG`와 현재 import된 `config.py`를 조립하고, `save_paper_config_snapshot()`은 실행 시점에 snapshot을 만든다.
- 실제 snapshot은 2026-08-16 13:06:18 KST에 생성되었지만 파일명/plan date는 2026-08-14다.
- 현재 설정 관련 파일은 조사 시작 시 dirty가 아니고 관련 committed code는 DATA_DATE 이전이지만, 실행 당시 working tree 및 effective config revision을 artifact가 보존하지 않는다. 따라서 미래 설정 사용 여부는 **CANNOT EXCLUDE**다.
- 현재-day 운영에서는 trade 전에 현재 설정을 freeze하는 것이 정상이다. delayed historical run에서는 당시 이미 존재한 immutable snapshot이 없으면 현재 설정으로 재생하지 말고 BLOCK해야 한다.

## Root cause

공통 원인은 `DATA_DATE`를 전달하는 것과 각 source의 **관측/유효 시점**을 증명하고 제한하는 것을 동일시한 것이다.

- prepare 단계는 날짜를 수집 상한이 아니라 label로 취급한다.
- freshness는 `latest >= target`을 성공으로 보아 미래행이 섞인 저장소도 PASS한다.
- consumer별 cutoff 구현이 분산되어 누락 여부를 중앙에서 검증하지 않는다.
- universe/config에는 관측 시각, effective date, source revision이 없다.
- plan artifact에는 source별 selected max date 및 validator 결과가 없다.

## Fix options

### Option A — prepare only to DATA_DATE

- 장점: DB 자체에 미래행이 없어 단순하고 사고 표면이 작다.
- 단점: 최신 DB를 과거 실행마다 되감거나 별도 DB가 필요하고, incremental 수집 API가 end date를 정확히 지원해야 한다. 기존 current-day 준비 흐름과 충돌하며 shared DB 운영 비용이 크다.
- universe의 역사 데이터가 없는 문제와 config 역사 버전 문제는 이것만으로 해결되지 않는다.

### Option B — store latest, consumers force as_of_date

- 장점: 현재 DB 운영 및 성능을 보존한다. 시장/지표/RS는 이미 대부분 이 형태다.
- 단점: 새 reader 하나가 cutoff를 빠뜨리면 재발한다. 파일명만 과거인 live universe/config 문제를 자동으로 막지 못한다.

### Option C — Option B plus safety validator

- 장점: 현재 구조를 최소 변경하면서 source별 cutoff, provenance, fail-closed를 Stage A 경계에서 보장한다.
- 단점: source lineage schema와 delayed historical universe/config 정책을 명시해야 한다.

## Recommended minimal design

**Option C**를 권고한다. owner는 새 core 계약 모듈(제안: `core/stage_a_asof_contract.py`)과 Stage A runner로 둔다.

1. `StageAAsOfContext(account_id, data_date, trade_date, generated_at)`를 runner frozen context에서 만들고 모든 official reader에 명시적으로 전달한다. official path에서 `as_of_date=None`을 금지한다.
2. 시장/가격 reader는 기존 `date <= data_date`를 유지하고 반환 dataframe/series의 max date가 cutoff 이하인지 공통 validator가 재검사한다. 위반 시 행을 조용히 삭제하지 말고 BLOCK한다.
3. screener는 official 호출 시 `end_date=data_date`를 필수로 하고, indicator는 cutoff된 price frame에서만 계산한다. precomputed indicator reader도 `date <= data_date` 및 selected max date를 반환한다.
4. RS는 stock과 benchmark 양쪽의 selected max date를 기록하고 각각 cutoff 이하가 아니면 BLOCK한다.
5. universe snapshot schema에 `observed_at`, `effective_as_of`, `source_revision/source_url`, `capture_mode`를 추가한다. delayed historical run에서 `observed_at > trade_date`인 live capture를 과거 `as_of`로 저장하지 않는다. 역사 snapshot/provider가 없으면 BLOCK한다.
6. `universe_snapshot.active_symbols`를 `build_screener_results(tickers=...)`의 canonical 모집단으로 전달한다. 최신 `tickers` 테이블은 metadata lookup에만 사용하고 membership SSOT로 사용하지 않는다.
7. account state 계산 cutoff와 fingerprint cutoff를 모두 `data_date`로 통일한다. snapshot payload date도 validator가 확인하고 future execution/state row가 하나라도 선택되면 BLOCK한다.
8. config는 current-day 실행에서는 trade 전에 snapshot을 immutable하게 생성·pin한다. delayed historical 실행에서는 당시 생성된 snapshot/revision을 요구하고 없으면 BLOCK한다. snapshot에 source commit/hash, observed_at/effective_at을 기록하고 기존 trade-date artifact를 묵시적으로 overwrite하지 않는다.
9. freshness는 target-date coverage를 source별로 검사한다. 저장소의 future max는 정보로 기록하되 target row의 존재/coverage를 대신하지 못하게 한다.
10. Daily Plan fingerprint에 source별 `{source, selected_max_date, observed_at, artifact_hash, validator_result}`를 추가한다. Step 3 직전/직후 validator가 모두 PASS해야 plan 및 Notion export가 진행된다.
11. current-day 동작은 유지한다: 최신 확정 market date가 data_date이고, trade 전에 캡처한 universe/config라면 기존 결과를 보존한다. write behavior와 order semantics는 바꾸지 않는다.

## Required tests

구현 작업에서 다음 테스트를 추가한다. 이번 audit에서는 테스트 코드를 변경하지 않았다.

1. delayed historical: DB가 data_date+1까지 있어도 market/indicator/RS/price 결과가 data_date까지만 사용되고 고정 fixture와 동일해야 한다.
2. future contamination: reader가 future row를 반환하면 validator가 삭제 후 계속하지 않고 `future_source_row`로 BLOCK해야 한다.
3. universe provenance: 실행일 live membership을 과거 as_of label로 저장하려는 경우 BLOCK; 역사 snapshot의 `active_symbols`만 screen tickers로 전달되는지 검증한다.
4. candidate regression: DAY/POOL 같은 membership 차이가 후보/순위에 반영되는 fixture로 current tickers fallback을 금지한다.
5. account: data_date+1 execution 및 current-state snapshot이 존재해도 계산/fingerprint 모두 data_date 이하를 선택한다.
6. config: delayed run에 historical immutable snapshot이 없으면 BLOCK하고, 올바른 source hash snapshot이면 PASS한다.
7. freshness: global max가 target 이후여도 target row가 없으면 FAIL; target coverage가 있으면 future stored rows를 진단에 기록하며 PASS한다.
8. current-day regression: 정상 Stage A 0~5, 4-candidate/NO_ACTION 양쪽 intent, artifact pinning, Notion export 계약이 동일해야 한다.
9. source-specific lineage: market, indicator, RS, universe, account, config 각각 selected max/effective date/hash가 plan sidecar에 기록되는지 검증한다.

## Impact / regression risks

- 유니버스 canonical 모집단 변경은 후보 수와 실제 주문을 바꿀 수 있다. 이는 성과 개선 목적이 아니라 look-ahead 제거에 따른 의도된 버그 수정이다.
- historical universe/config가 없는 과거 날짜는 이전처럼 억지 생성되지 않고 BLOCK될 수 있다.
- schema 확장 시 기존 snapshot/plan reader의 backward compatibility가 필요하다. legacy artifact는 `provenance_missing`으로 명시적으로 다뤄야 하며 silently trusted 해서는 안 된다.
- source별 max-date 조회는 비용이 있으므로 이미 읽은 frame의 metadata를 재사용하되 검증을 생략하면 안 된다.
- DB schema 변경은 필요하지 않도록 JSON lineage를 우선한다. DB schema가 필요해지면 AGENTS.md에 따라 별도 승인이 필요하다.

## Decisions Needed

1. `STAGE-A-ASOF-FIX-1`에서 Option C를 채택할지 승인 필요.
2. delayed historical universe의 승인 가능한 원천을 정해야 한다: 사전 캡처 snapshot만 허용할지, effective-date를 제공하는 별도 역사 provider를 도입할지.
3. delayed historical config가 없을 때 무조건 BLOCK할지, 명시적 exploratory/replay 모드에서만 현재 config 사용을 허용할지 정해야 한다. official Stage A 기본은 BLOCK을 권고한다.
4. 오염된 2026-08-14 plan/Notion rows를 무효 표시하거나 역사 source 확보 후 재생할지는 별도 운영 승인 대상이다. 이번 audit은 운영 산출물을 변경하지 않았다.

## Suggested FIX work ID

`STAGE-A-ASOF-FIX-1 — Official Stage A as-of lineage and fail-closed validator`

## Review Evidence path

`docs/work_results/STAGE-A-ASOF-LOOKAHEAD-AUDIT_Review_Evidence.md`

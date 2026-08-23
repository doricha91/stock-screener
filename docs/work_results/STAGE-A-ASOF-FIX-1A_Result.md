# Summary

STAGE-A-ASOF-FIX-1A를 완료했다. Official Stage A의 Step 1 data preparation은 validated immutable universe snapshot의 `active_symbols`를 canonical ticker set으로 사용한다. Historical official run은 current/live membership source를 호출하지 않으며, current-day official run은 live universe를 한 번 snapshot으로 capture한 뒤 같은 snapshot symbols를 data refresh에 재사용한다.

# Gap fixed

FIX-1에서는 Step 3 screener membership만 snapshot `active_symbols`로 고정되어 있었고, Step 1은 snapshot resolve 후에도 `collect_daily_tickers()`를 호출했다. 이 경로를 제거해 official Step 1과 Step 3의 universe membership SSOT를 동일한 validated snapshot으로 통일했다.

# Files changed

Production:

- `core/paper_prepare_data.py`: official snapshot을 읽고 기존 as-of validator로 재검증한 뒤 정규화된 non-empty `active_symbols`를 ticker metadata/price updater에 전달한다. Legacy path의 collector는 유지했다.

Tests:

- `tests/test_paper_prepare_data.py`: historical valid snapshot, current-day single capture/reuse, historical missing fail-closed, Step 1/Step 3 membership equality를 검증한다. 기존 legacy 테스트도 그대로 통과한다.

새 schema, lifecycle, mode, reason taxonomy는 추가하지 않았다. `core/stage_a_asof_contract.py`와 다른 production 파일은 변경하지 않았다.

# Official preparation universe SSOT

`trade_date`와 `include_universe=True`가 전달된 official Stage A preparation은 먼저 universe snapshot을 resolve 또는 capture한다. 이어 저장된 artifact를 다시 읽어 기존 `validate_universe_snapshot()`으로 검증하고, `active_symbols`를 trim/uppercase/deduplicate/sort한 결과만 `update_tickers_info()`와 `update_stock_data()`에 전달한다. canonical set이 비면 기존 `asof_provenance_invalid` reason으로 BLOCK한다.

# Historical behavior

Valid immutable historical snapshot이 있으면 그 snapshot의 `active_symbols`만 Step 1 ticker set으로 사용한다. 이 경로에서는 `collect_daily_tickers()`, `get_sp500_tickers()`, `get_nasdaq100_tickers()`, `fetch_live_basket_symbols()`를 membership source로 호출하지 않는다. Snapshot이 없으면 기존 `historical_universe_snapshot_missing`으로 price/index/ticker/indicator refresh 전에 BLOCK한다.

# Current-day behavior

기존 FIX-1 current-day capture를 유지했다. 기존 valid snapshot이 있으면 그대로 재사용하며, 없으면 live universe를 한 번 capture해 immutable snapshot을 만든다. 이후 data refresh는 capture 함수의 live 결과를 별도로 재조회하지 않고 저장된 snapshot `active_symbols`를 사용한다.

# Legacy behavior

`trade_date`가 없는 non-official/legacy `prepare-data`는 기존 `collect_daily_tickers()`를 그대로 사용한다. 기존 skip-prices, skip-indicators, universe enabled/disabled behavior도 유지된다.

# Tests

실행한 테스트:

1. FIX-1A 필수 Stage A 묶음: `76 passed, 1 warning`.
2. Universe/config/freshness/MFU-EO2/Stage B 회귀: `128 passed, 1 warning`.
3. Notion exporter 회귀: `57 passed`.
4. `python -m py_compile core/paper_prepare_data.py tests/test_paper_prepare_data.py`: PASS.
5. `git diff --check`: PASS. 기존 working-copy LF/CRLF warning만 출력됐다.

# Regression results

총 261개 관련 테스트가 통과했다. FIX-1 config/account/market/indicator/RS/lineage 계약, Stage A runner fail-closed, MFU-EO2 execution semantics, Stage B, NO_ACTION/all-NOT_EXECUTED 및 Notion export 계약에는 production 변경이 없다. Legacy preparation 회귀도 통과했다.

전체 repository suite는 실행하지 않았다. 직전 FIX-1 검증에서 기존 접근 불가 root pytest 임시 디렉터리들과 7개 top-level `import conftest` collection 오류가 확인됐으며, 이번 변경과 직접 관련된 필수·회귀 suite를 분리 실행했다.

# 2026-08-14 run protection

`paper_pilot_202606_2026-08-13_2026-08-14` runbook/state/artifact를 읽거나 수정하지 않았다. activation, finalize, Gate, Stage B~F, backfill을 실행하지 않았다. 테스트는 고유한 system temp workspace만 사용했다.

# Risks / limitations

- Official contract activation은 기존 command contract대로 `include_universe=True`와 `trade_date` 전달에 의존한다.
- Historical provider/backfill은 범위 밖이며 snapshot/provenance가 없으면 계속 BLOCK한다.
- Current-day 최초 capture는 기존 live Wikipedia universe provider 가용성에 의존한다.
- Working tree의 기존 다수 dirty/untracked 파일과 protected DB 변경은 보존했으며 정리하지 않았다.

# Decisions Needed

없음.

# Review Evidence path

`docs/work_results/STAGE-A-ASOF-FIX-1A_Review_Evidence.md`

# Summary

STAGE-A-ASOF-FIX-1을 구현했다. Official Stage A는 DATA_DATE와 TRADE_DATE를 명시한 공통 as-of context를 사용하며, market/indicator/RS/universe/account/config의 provenance가 모두 PASS인 경우에만 Daily Plan을 pin하고 Notion/export 단계로 진행한다. 과거 실행에서 immutable universe 또는 config snapshot이 없거나 유효하지 않으면 live/current fallback 없이 BLOCK한다.

# Implemented contract

- Option C(shared latest store + official cutoff enforcement + Stage A provenance validator)를 적용했다.
- 공식 경로의 최대 허용 market/indicator/RS/account 계산일은 DATA_DATE다.
- universe는 validated immutable snapshot, config는 validated immutable snapshot/revision만 허용한다.
- Daily Plan JSON에 6개 source의 `as_of_lineage`를 기록하고 Stage A runner가 export 전에 재검증한다.
- `asof_provenance_missing`, `asof_provenance_invalid`, `asof_future_source`, `historical_universe_snapshot_missing`, `historical_config_snapshot_missing`을 안정적인 fail-closed reason으로 사용한다.

# Files changed

Production:

- `core/stage_a_asof_contract.py`: 공통 context, hash, universe/config/lineage validator와 안정적 BLOCK 오류를 추가했다.
- `core/paper_prepare_data.py`: 공식 universe 준비를 current-day immutable capture 또는 historical immutable reuse로 제한했다.
- `core/universe_manager.py`: 선택된 snapshot provenance metadata를 노출했다.
- `core/paper_config_snapshot.py`: full config와 provenance를 기록하고 공식 snapshot을 immutable하게 재사용한다.
- `core/paper_data_freshness.py`: global max가 아니라 DATA_DATE exact coverage를 검증한다.
- `core/daily_plan_generator.py`: snapshot `active_symbols`를 공식 membership SSOT로 사용하고 6-source lineage 검증 후 산출물을 기록한다.
- `scripts/run_paper_daily_plan.py`: config pin, account calculation/fingerprint DATA_DATE cutoff, provenance 주입을 구현했다.
- `scripts/paper.py`: 공식 prepare/plan 인자와 구조화된 BLOCK 전달을 추가했다.
- `scripts/runbook_command_registry.py`: Stage A prepare/plan command에 frozen context와 as-of enforcement를 전달한다.
- `scripts/runbook_stage_runner.py`: Daily Plan lineage를 export 전에 검증하고 구조화된 차단을 BLOCKED로 보존한다.

Tests:

- `tests/test_stage_a_asof_contract.py`: 신규 contract 경계 테스트다.
- `tests/test_paper_data_freshness.py`: exact DATA_DATE coverage와 future global max 회귀를 추가했다.
- `tests/test_paper_daily_plan_generation.py`: historical config pin 및 account D+1 배제 회귀를 추가했다.
- `tests/test_runbook_stage_runner.py`: 정상 EXECUTION/NO_ACTION과 lineage fail-closed 회귀를 추가했다.

Audit 예상 파일 중 `screener/screener.py`는 수정하지 않았다. 기존 `build_screener_results(tickers=..., end_date=...)` 계약이 필요한 membership과 cutoff를 이미 지원하므로 호출부 변경만으로 충분했다. DB schema, Stage B~F 구현, MFU-EO2 구현 파일은 이 FIX에서 변경하지 않았다.

# Universe fix

Current-day 공식 실행은 TRADE_DATE 당일 관측된 live membership을 DATA_DATE effective snapshot으로 한 번 저장하고 provenance(`effective_as_of`, `observed_at`, `source`, `source_revision`, `capture_mode`)를 남긴다. Historical 실행은 DATA_DATE 이하의 기존 immutable snapshot만 재사용한다. snapshot이 없거나 provenance가 유효하지 않으면 live fetch를 호출하지 않고 BLOCK한다. 공식 screener의 canonical 모집단은 validated snapshot의 `active_symbols`이며 최신 `tickers`는 membership fallback으로 사용하지 않는다.

# Config fix

Current-day 공식 실행은 regime overlay 후의 `full_config`를 TRADE_DATE immutable snapshot으로 저장하며 `observed_at`, `effective_at`, `source_revision`, `capture_mode`를 기록한다. 같은 경로의 유효한 snapshot은 overwrite/archive 없이 재사용한다. Historical 실행은 해당 frozen context에 맞는 기존 snapshot만 pin하며 누락·불일치·미래 관측이면 BLOCK한다. 현재 config로 과거 snapshot을 합성하거나 backfill하지 않는다.

# Market / Indicator / RS validation

기존 loader의 `end_date=DATA_DATE` 및 market-state target cutoff를 유지했다. 공식 plan은 market selected date, indicator candidate source date, RS benchmark max date를 lineage에 기록한다. 실제 선택된 날짜가 DATA_DATE를 넘으면 조용히 drop하지 않고 `asof_future_source`로 BLOCK한다. benchmark series가 비어 provenance를 증명할 수 없는 경우도 BLOCK한다.

# Account cutoff fix

계좌 상태 계산 입력일과 fingerprint용 current-state snapshot 선택일을 모두 DATA_DATE로 통일했다. TRADE_DATE 또는 D+1 snapshot이 존재해도 `latest_current_state_snapshot_path(..., DATA_DATE)`만 선택하며, lineage의 `selected_max_date`도 DATA_DATE로 pin한다.

# Freshness behavior

- global max > DATA_DATE이고 DATA_DATE exact row가 있으면 PASS 가능하다.
- daily_price 또는 daily_indicators에 DATA_DATE row가 없으면 FAIL한다.
- required market index의 DATA_DATE row가 없으면 SPY 또는 strict mode에서 FAIL한다.
- 미래 row가 DB에 존재한다는 사실만으로 실패시키지 않으며, official reader가 그 row를 실제 선택하면 BLOCK한다.

# Stage A fail-closed behavior

Stage A command registry는 prepare-data에 DATA_DATE/TRADE_DATE/account_id를, plan에 `--enforce-asof-contract`를 전달한다. prepare/plan의 contract 오류는 구조화된 `{blocked, reason, detail, source}` payload와 exit code 2로 반환된다. runner는 Daily Plan execution intent 검증 직후 6-source lineage를 검증하며 실패 시 Step 4/5 Notion Daily Plan export 및 execution template export를 실행하지 않는다.

# Lineage evidence

Daily Plan JSON의 `as_of_lineage`에는 market, indicator, rs, universe, account, config가 모두 포함된다. 각 source는 source, selected/effective date, observed_at, revision 또는 artifact hash, validator_result를 포함한다. Universe/config는 실제 snapshot file SHA-256도 lineage에 기록한다. runner가 pinned Daily Plan을 다시 읽어 같은 frozen context로 검증한다.

# 2026-08-14 run protection

`paper_pilot_202606_2026-08-13_2026-08-14`의 기존 runbook state, Daily Plan, account snapshot, execution/review artifacts를 읽거나 수정하지 않았다. activation/finalize/Gate 1/Stage B~F를 실행하지 않았고 backfill도 수행하지 않았다. 모든 실행 검증은 pytest 임시 workspace에서 수행했다.

# Tests

실행한 테스트:

1. Stage A targeted/regression: `104 passed, 1 warning`.
2. Universe/config/MFU-EO2/Stage B 관련 회귀: `111 passed, 1 warning`.
3. Notion exporter 회귀: `57 passed`.
4. `python -m py_compile` 대상 production/test 파일: PASS.
5. `git diff --check`: PASS(기존 working-copy LF/CRLF warning만 출력).

초기 표적 실행에서 pytest 기본 temp ACL로 38 setup error가 발생했고 저장소 내부 basetemp로 재실행해 104 PASS를 확인했다. 첫 관련 회귀 실행의 Notion 2건은 저장소 내부 basetemp의 상대경로 정규화 차이였으며 시스템 temp에서 해당 suite를 재실행해 57 PASS를 확인했다.

# Regression results

Current-day Stage A의 EXECUTION, NO_ACTION, pinned Daily Plan, Notion Daily Plan export, execution template 흐름은 runner 회귀에서 유지됐다. MFU-EO2 derivation/flow/zero-count와 Stage B runner 회귀 111개가 통과해 execution semantics, v1/v2, all-NOT_EXECUTED 및 downstream behavior의 비의도 변경이 없음을 확인했다.

전체 repository pytest는 완료하지 못했다. 루트 실행은 기존 접근 불가 `_tmp_pytest_*` 디렉터리 37개와 `tmpvt37771o` 때문에 collection error가 발생했고, `tests/` 한정 실행도 기존 7개 테스트가 `import conftest`를 top-level module로 찾지 못해 collection 단계에서 중단됐다. 변경 관련 suite는 위의 272개 통과로 대체 검증했다.

# Risks / limitations

- 과거 universe/config snapshot을 새로 제공하거나 backfill하는 기능은 의도적으로 구현하지 않았다. 기존 snapshot에 신규 provenance가 없으면 historical official Stage A는 BLOCK한다.
- Universe current-day capture는 기존 live Wikipedia provider의 가용성에 의존한다.
- 공통 validator는 source provenance와 선택 cutoff를 검증하지만 DB 자체를 immutable revision store로 전환하지는 않는다.
- 기존 working tree에는 본 작업 이전의 다수 변경과 protected DB 변경이 남아 있으며 본 작업은 이를 복구·정리하지 않았다.

# Decisions Needed

없음. Historical snapshot provider/backfill이 필요해질 경우 별도 승인과 별도 작업으로 설계해야 한다.

# Review Evidence path

`docs/work_results/STAGE-A-ASOF-FIX-1_Review_Evidence.md`

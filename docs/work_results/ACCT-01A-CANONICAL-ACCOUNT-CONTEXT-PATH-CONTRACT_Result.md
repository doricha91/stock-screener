# ACCT-01A Canonical Account Context / Path Contract Result

## Task

- Task: ACCT-01A Canonical Account Context / Path Contract
- Base SHA: `6f1d420182a3741c39ea61de09e73421b81baf9a`
- Base remote: `origin/gemini_cli_update`
- Task branch: `acct-01a-account-context-contract`
- Isolated worktree: `C:\Users\inocha\AppData\Local\Temp\StockScreener_ACCT01A_20260905`
- Verdict: `PENDING_CHATGPT_REVIEW`

## Scope

이번 변경은 account path resolver와 writer guard의 중앙 계약, 그 계약의 단위 테스트, 직접 영향받은 status account-scope 테스트만 수정한다. 실제 consumer 전체 전환, 실제 데이터 migration, 운영 smoke는 각각 ACCT-01B/C/D에 남긴다. persisted schema는 추가하거나 변경하지 않았다.

## Policy implemented

| Concern | Implemented contract |
| --- | --- |
| Read account omission | `resolve_paper_account_profile(None)`의 configured default account를 사용한다. |
| Canonical root | `PAPER_ACCOUNTS_ROOT / resolved_account_id`, 즉 `outputs/paper_accounts/<account_id>`이다. |
| Legacy default | `allow_legacy_default=True`를 명시한 read-only 호출에서만 `outputs/paper_test`를 선택할 수 있다. |
| Canonical precedence | canonical `paper_default` root가 존재하면 explicit compatibility 요청에도 canonical root를 우선한다. |
| Direct write omission | `resolve_writer_account_context(None)`은 명시적 account 또는 frozen runbook context를 요구하며 실패한다. frozen context 설계는 변경하지 않았다. |
| Writer target | canonical root만 정상 target이다. legacy context는 writer guard에서 허용되지 않는다. |
| Root creation | 정상 owner는 기존 `paper.py init-account --confirm-create` → `initialize_paper_account()`이다. |
| Transitional creation | 기존 generic `create=True` API는 ACCT-01B caller closure 전까지 남지만 legacy compatibility 또는 legacy root와 결합하면 실패한다. |

## Files changed

| File | Reason | Core change |
| --- | --- | --- |
| `core/paper_account_paths.py` | canonical resolution을 기본 계약으로 고정 | 두 resolver의 `allow_legacy_default` 기본값을 `False`로 변경하고 legacy+create를 차단했다. |
| `core/paper_account_guard.py` | direct write와 legacy writer의 fail-closed 기반 고정 | omitted account를 거부하고 canonical-only resolution 및 legacy writer 차단을 적용했다. |
| `tests/test_paper_account_paths.py` | 기존 silent fallback 기대를 새 계약으로 전환 | configured default, canonical precedence, explicit legacy read, no-create, legacy+create 차단을 검증한다. |
| `tests/test_paper_account_guard.py` | writer/legacy 계약 검증 | omitted write, canonical explicit write, legacy 차단, containment를 검증한다. |
| `tests/test_paper_status_account_scope.py` | 직접 영향 caller 회귀 기대 갱신 | default status metadata가 silent legacy가 아니라 canonical root를 나타내도록 변경했다. |
| `docs/work_results/ACCT-01A-CANONICAL-ACCOUNT-CONTEXT-PATH-CONTRACT_Result.md` | 구현 및 조사 evidence | 본 문서다. |
| `docs/work_results/ACCT-01A-CANONICAL-ACCOUNT-CONTEXT-PATH-CONTRACT_Review_Evidence.md` | 독립 검토 입력 | 승인 전 checklist와 위험을 기록한다. |
| `docs/work_results/ACCT-01A-CANONICAL-ACCOUNT-CONTEXT-PATH-CONTRACT_Changes.patch` | exact review patch | Base SHA 대비 아래 source/test 5개 unified diff만 포함한다. |

## Review bundle diff alignment

### Changed source/test files

```text
core/paper_account_guard.py
core/paper_account_paths.py
tests/test_paper_account_guard.py
tests/test_paper_account_paths.py
tests/test_paper_status_account_scope.py
```

### git diff --name-status

```text
M  core/paper_account_guard.py
M  core/paper_account_paths.py
M  tests/test_paper_account_guard.py
M  tests/test_paper_account_paths.py
M  tests/test_paper_status_account_scope.py
```

### git diff --stat

```text
 core/paper_account_guard.py              |  23 ++++-
 core/paper_account_paths.py              |  26 +++++-
 tests/test_paper_account_guard.py        | 149 ++++++++++++++++++++-----------
 tests/test_paper_account_paths.py        | 121 +++++++++++++++++++++++--
 tests/test_paper_status_account_scope.py |   6 +-
 5 files changed, 258 insertions(+), 67 deletions(-)
```

Exact source/test unified diff:

`docs/work_results/ACCT-01A-CANONICAL-ACCOUNT-CONTEXT-PATH-CONTRACT_Changes.patch`

Patch의 `diff --git` header는 위 5개 파일과 일치하며 Result/Review Evidence, unrelated dirty 파일, 운영 output, DB를 포함하지 않는다.

Evidence 보강 작업 전후 source/test blob hash는 동일하다.

| File | Before | After |
| --- | --- | --- |
| `core/paper_account_paths.py` | `27b543f2245ce209e4a8f9853108432a0cfc6e9d` | `27b543f2245ce209e4a8f9853108432a0cfc6e9d` |
| `core/paper_account_guard.py` | `5b3d9fddcd1e412a67c76ca1917d996d6f48fe3b` | `5b3d9fddcd1e412a67c76ca1917d996d6f48fe3b` |
| `tests/test_paper_account_paths.py` | `3356792727056e66e69abb32a7170bb1039822c7` | `3356792727056e66e69abb32a7170bb1039822c7` |
| `tests/test_paper_account_guard.py` | `221e50e42daf143deac15073bf3f1b5d5c4385e3` | `221e50e42daf143deac15073bf3f1b5d5c4385e3` |
| `tests/test_paper_status_account_scope.py` | `92de08ce156fb8a0cc13ac20579896007274b9bf` | `92de08ce156fb8a0cc13ac20579896007274b9bf` |

## Behavior Before / After

| Area | Before | After | Compatibility |
| --- | --- | --- | --- |
| Omitted/default read | canonical root 부재 시 legacy root 자동 선택 가능 | configured default의 canonical root 반환 | explicit legacy read shim 유지 |
| Explicit legacy read | default option으로도 선택 가능 | `paper_default`와 explicit compatibility flag 모두 필요 | read-only |
| Direct writer omission | `paper_default`로 간주 | `ValueError` | frozen runbook context는 B에서 caller closure |
| Legacy writer | 정상 writer로 승인 가능 | guard에서 차단 | write compatibility 없음 |
| Root creation | legacy target도 generic create 가능 | legacy/create 결합 실패 | canonical generic create는 B/C 전까지 임시 유지 |

## Direct path search results

아래 표는 source caller를 파일 단위로 전수 분류한 것이다. 같은 파일의 복수 symbol은 한 행에 묶었다.

| File | Symbol/caller | Read/write | Current behavior | Remaining gap | Target MFU |
| --- | --- | --- | --- | --- | --- |
| `core/paths.py` | `PAPER_TEST_DIR`, legacy path helpers | mixed | legacy singleton path와 import-time directory creation 유지 | generic legacy helpers의 consumer 제거 | B/C |
| `core/paper_account_paths.py` | resolver, `PaperAccountPaths` | mixed | canonical default, explicit legacy read, transitional canonical create | generic create 제거 | B |
| `core/paper_account_guard.py` | writer context/guard, containment | write guard | omitted/legacy write fail-closed | frozen-context callers의 end-to-end 연결 | B |
| `core/paper_account_bootstrap.py` | bootstrap plan/initialize | write | explicit canonical non-default initialization | 운영 isolated evidence | D |
| `scripts/paper.py` | read/write CLI handlers | mixed | resolver/guard 사용; 일부 handler는 generic create 사용 | writer/read command별 explicit account closure | B/C |
| `core/paper_account_snapshot.py` | snapshot read/write | mixed | `account_paths`가 없으면 `PAPER_TEST_DIR` | writer context 필수화 | B |
| `core/paper_current_state_storage.py` | current-state store | write | 기본 legacy containment | canonical writer root 연결 | B |
| `core/paper_execution_log.py` | execution log append | write | 기본 legacy containment | canonical writer root 연결 | B |
| `core/paper_position_snapshot.py` | position snapshot | mixed | `account_paths`가 없으면 legacy | writer context 필수화 | B |
| `core/paper_manual_execution_commit.py` | execution commit/archive fallback | write | 일부 fallback이 `PAPER_TEST_DIR` | canonical commit root closure | B |
| `core/paper_manual_review_log_append.py` | review append | write | optional path에서 legacy containment | canonical append root closure | B |
| `core/paper_manual_review_log_template.py` | review template | mixed | optional path에서 legacy containment | account-root chain closure | B/C |
| `core/paper_manual_review_log_validator.py` | review validation/report | mixed | optional path에서 legacy containment | account-root chain closure | B/C |
| `core/paper_preflight_check.py` | preflight reads/report writes | mixed | no-context path와 메시지가 legacy 기준 | canonical context 및 diagnostics 전환 | B/C |
| `scripts/reset_paper_execution_log.py` | reset/archive | write | legacy singleton 전용 | explicit account writer closure | B |
| `scripts/run_paper_eod_update.py` | EOD state/snapshot writes | write | 일부 no-context legacy fallback | frozen account context closure | B |
| `scripts/import_notion_executions.py` | import preview/commit | write | canonical resolver이나 generic create 사용 | create owner 분리, writer context closure | B |
| `scripts/import_notion_reviews.py` | review import/append | write | canonical resolver이나 generic create 사용 | create owner 분리, writer context closure | B |
| `scripts/sync_notion_execution_status.py` | execution status sync | external write | generic create 사용 | no-create account resolution과 namespace closure | B |
| `scripts/sync_notion_review_status.py` | review status sync | external write | generic create 사용 | no-create account resolution과 namespace closure | B |
| `scripts/runbook_execution_reconciliation_preview.py` | reconciliation evidence | mixed | frozen root를 받지만 generic create 사용 | create 제거와 context containment | B |
| `scripts/runbook_stage_b_recovery.py` | recovery | mixed | frozen account/root resolver 사용 | writer lifecycle closure | B |
| `scripts/runbook_stage_runner.py` | stage runner | mixed | frozen account resolver 사용 | 모든 writer target 검증 | B |
| `core/runbook_recovery.py` | recovery context resolution | read | canonical resolver 기본값을 상속 | legacy recovery compatibility 명시화 | B/C |
| `core/runbook_day_rollover.py` | rollover context resolution | read | stored account/root resolver 사용 | legacy rollover compatibility 명시화 | B/C |
| `core/notion_exporters.py` | export source resolution | read/external write | canonical은 명시, 별도 legacy source adapter 유지 | legacy adapter와 path serialization closure | C |
| `core/notion_daily_ops_status_exporter.py` | daily ops export source | read/external write | account resolver 사용 | read/export 전수 closure | C |
| `core/paper_daily_ops_orchestrator.py` | preflight/account scan | read | legacy fallback warning/scan 로직 유지 | canonical-only 운영 scan | C |
| `core/paper_alert_report.py` | alert source/report | read | account resolver 사용 | alert path 전수 검증 | C |
| `core/paper_replay_diff.py` | replay output | write | generic create 사용 | explicit prepared output root | C |
| `scripts/dev/capture_daily_plan_baseline.py` | baseline state read | read | account resolver 사용 | explicit compatibility 분류 | C |
| `scripts/dev/replay_daily_plan_diff.py` | replay read/output | mixed | generic create 사용 | explicit prepared output root | C |
| `core/paper_daily_review_summary.py` | daily review | mixed | optional path legacy assertions | canonical report chain | C |
| `core/paper_performance_summary.py` | performance summary | mixed | optional path legacy assertions | canonical report chain | C |
| `core/paper_realized_ranking_report.py` | ranking report | mixed | optional path legacy assertions | canonical report chain | C |
| `core/paper_realized_trade_journal.py` | trade journal | mixed | optional path legacy assertions | canonical report chain | C |
| `core/paper_symbol_realized_performance.py` | realized report | mixed | optional path legacy assertions | canonical report chain | C |
| `core/paper_symbol_review_buckets.py` | review buckets | mixed | optional path legacy assertions | canonical report chain | C |
| `core/paper_symbol_review_worksheet.py` | worksheet | mixed | optional path legacy assertions | canonical report chain | C |
| `core/paper_symbol_side_by_side_performance.py` | side-by-side report | mixed | optional path legacy assertions | canonical report chain | C |
| `core/paper_symbol_unrealized_performance.py` | unrealized report | mixed | optional path legacy assertions | canonical report chain | C |
| `core/paper_state_provider.py` | state source | read | default execution log가 legacy | canonical state-provider context | C |
| `core/paper_status.py` | daily status | read | `account_paths` 없으면 legacy; supplied context는 canonical metadata | default read context closure | C |
| `core/paper_weekly_status.py` | weekly status | read | no-context fallback가 legacy | default read context closure | C |
| `core/paper_safety.py` | legacy path assertion | guard | `PAPER_TEST_DIR` 중심 오류 계약 | account-root aware guard로 caller 전환 | B/C |
| `scripts/audit_paper_performance_inputs.py` | input audit | read | module constants가 legacy | canonical account option | C |
| `scripts/generate_paper_drawdown.py` | drawdown generator | mixed | module constants가 legacy | canonical account option | C |
| `scripts/generate_paper_equity_curve.py` | equity generator | mixed | module constants가 legacy | canonical account option | C |
| `scripts/check_paper_data_freshness.py` | freshness report CLI | mixed | help/output 설명이 legacy | account-root aware output | C |
| `scripts/check_paper_plan_regeneration_diff.py` | replay diff message | read | legacy output 문구 유지 | canonical replay path | C |
| `scripts/check_paper_preflight.py` | preflight CLI | mixed | report root가 legacy | account-root aware output | C |
| `scripts/check_paper_report_regeneration_safety.py` | regeneration safety | read | default root가 legacy | canonical account option | C |
| `scripts/paper_daily_ops.py` | daily ops root | mixed | explicit account resolver 또는 supplied workspace | lifecycle account closure | B/C |

`PAPER15` 검색은 기존 PAPER15 multi-account TRD/PRD, operations 문서, 관련 tests 및 `core/paper_account_guard.py`의 safety 문구를 확인했다. 기존 account profile, path resolver, writer guard, Notion namespace, report-root, smoke, bootstrap 계약을 새 capability로 중복 생성하지 않고 ACCT-01 후속 소유권에 연결했다.

구현 후 `outputs/paper_test`, `outputs/paper_accounts`, `PAPER_TEST_DIR`, `LEGACY_PAPER_DEFAULT_ROOT`, `PAPER_ACCOUNTS_ROOT`, `allow_legacy_default`, 두 path resolver, 두 writer-context/guard symbol, `create=True`, `init-account`, `confirm-create`, `PAPER15`를 모두 다시 검색했다. source caller 분류는 위 표와 아래 `create=True` 표에 정리했다. Evidence 자체가 검색 문자열을 포함하므로 자기참조하는 match count는 판정 근거로 사용하지 않았다.

## create=True caller inventory

| File:line | Caller/use | Why still needed now | Owner | Removal MFU |
| --- | --- | --- | --- | --- |
| `core/paper_replay_diff.py:233` | replay output directory | caller가 output preparation을 resolver에 의존 | replay owner | ACCT-01C |
| `scripts/dev/replay_daily_plan_diff.py:59` | dev replay output | 동일 | replay owner | ACCT-01C |
| `scripts/import_notion_executions.py:78,186` | import preview/commit directories | 기존 importer가 directory preparation을 겸함 | execution import owner | ACCT-01B |
| `scripts/import_notion_reviews.py:68,111` | review preview/append directories | 기존 importer가 directory preparation을 겸함 | review import owner | ACCT-01B |
| `scripts/paper.py:624` | plan | CLI writer가 root preparation을 겸함 | Paper CLI owner | ACCT-01B |
| `scripts/paper.py:676` | EOD commit-controlled create | commit path에서만 create flag 사용 | Paper CLI/EOD owner | ACCT-01B |
| `scripts/paper.py:788,822,851,878` | reports/review commands | writer/report handler가 directories를 준비 | Paper CLI owner | ACCT-01B/C |
| `scripts/runbook_execution_reconciliation_preview.py:105` | runbook reconciliation evidence | frozen workspace 아래 evidence directory 준비 | runbook owner | ACCT-01B |
| `scripts/sync_notion_execution_status.py:65` | execution sync | sync entrypoint가 root preparation을 겸함 | execution sync owner | ACCT-01B |
| `scripts/sync_notion_review_status.py:65` | review sync | sync entrypoint가 root preparation을 겸함 | review sync owner | ACCT-01B |

Temporary compatibility는 `core/paper_account_paths.py`의 generic `create=True` canonical-directory 생성 분기다. 위 callers가 아직 이를 호출하므로 ACCT-01A에서 제거하지 않았다. legacy compatibility와 함께 사용하거나 explicit legacy root를 target으로 하면 실패한다.

## Legacy compatibility remaining

- `allow_legacy_default=True`는 `paper_default` read-only compatibility를 위한 명시적 shim으로 남아 있다.
- `core/notion_exporters.py`에는 `PAPER_TEST_DIR`를 source로 만드는 명시적 legacy adapter가 남아 있다.
- `core/paths.py`와 다수 report/writer module의 no-context fallback은 아직 `PAPER_TEST_DIR`에 의존한다.
- 실제 `outputs/paper_test` 데이터는 이동, 복사, 이름 변경, 삭제하지 않았다.

## ACCT-01B follow-up list

1. writer entrypoint가 explicit account 또는 frozen runbook context를 항상 전달하도록 closure한다.
2. snapshot/current-state/execution/review/EOD writer의 `PAPER_TEST_DIR` fallback을 제거한다.
3. importer/status-sync/runbook/CLI의 generic `create=True`를 제거하고 bootstrap owner와 분리한다.
4. 모든 writer target을 resolved canonical account root 아래로 containment 검증한다.

## ACCT-01C follow-up list

1. status, weekly status, state provider, reports, audit/generator의 no-context legacy reads를 명시적 canonical/default 또는 legacy-read mode로 분리한다.
2. Notion exporter의 explicit legacy adapter와 source path serialization을 검토한다.
3. replay, alert, daily ops, baseline tooling의 account/path closure를 수행한다.
4. legacy 관련 CLI/help/diagnostic 문구를 canonical contract에 맞춘다.

## ACCT-01D follow-up list

1. isolated `paper_sandbox`에서 default/non-default account 교차오염 smoke evidence를 만든다.
2. bootstrap dry-run/confirm-create와 existing-target protection을 운영과 분리된 filesystem에서 재검증한다.
3. 실제 운영 state가 아니라 복제된 fixture로 full local lifecycle isolation을 검증한다.

## Tests run

| Command | Result | Count/notes |
| --- | --- | --- |
| `python -m py_compile core/paper_account_paths.py core/paper_account_guard.py` | 성공 | 2 modules |
| `$env:STOCK_SCREENER_MARKET_DB='D:\python\StockScreener\outputs\market_data.db'; pytest tests/test_paper_account_paths.py tests/test_paper_account_guard.py tests/test_paper_account_profile.py tests/test_paper_account_bootstrap.py tests/test_paper_cli_init_account.py tests/test_paper_status_account_scope.py -q --basetemp C:\Users\inocha\AppData\Local\Temp\acct01a_final_pytest` | 성공 | final focused bundle, 64 tests; one dependency deprecation warning |
| `$env:STOCK_SCREENER_MARKET_DB='D:\python\StockScreener\outputs\market_data.db'; $testFiles=@(rg -l 'paper_account_paths\|paper_account_guard\|resolve_writer_account_context\|guard_paper_writer_account\|build_paper_account_paths\|resolve_paper_account_root' tests -g '*.py'); pytest $testFiles -q --basetemp C:\Users\inocha\AppData\Local\Temp\acct01a_all_direct_pytest` | 일부 실패 | 40 files; 670 succeeded, 14 failed |
| Same dynamic affected-test selection at Base SHA in a clean detached worktree, with `--tb=line --basetemp C:\Users\inocha\AppData\Local\Temp\acct01a_baseline_direct_pytest` | 일부 실패 | 40 files; 660 succeeded, same 14 node IDs failed |
| `pytest tests/test_paper_account_paths.py tests/test_paper_account_guard.py -q --basetemp .pytest_acct01a_targeted` | 성공 | 25 tests before the final explicit-root edge cases were added; cache warning only |
| `pytest tests/test_paper_account_profile.py tests/test_paper_account_bootstrap.py -q --basetemp .pytest_acct01a_profile_bootstrap_only` | 성공 | 31 tests |
| `$env:STOCK_SCREENER_MARKET_DB='D:\python\StockScreener\outputs\market_data.db'; pytest tests/test_paper_cli_init_account.py -q --basetemp .pytest_acct01a_cli_init` | 성공 | 3 tests; DB path was read-only import dependency |
| `$env:STOCK_SCREENER_MARKET_DB=...; pytest tests/test_paper_status_account_scope.py -q --basetemp .pytest_acct01a_status` | 성공 | 3 tests |
| account/profile/bootstrap/status/runbook/Notion/report 11-file regression bundle | 일부 실패 | 274 succeeded, 2 relative-basetemp path serialization failures; superseded by the absolute-basetemp affected run |
| account-scope/guard/status/writer/report 7-file caller bundle | 일부 실패 | 29 succeeded, 1 superseded status legacy expectation, 1 unrelated existing `enforce_asof_contract` test-double mismatch |
| `git diff --check` | 성공 | whitespace errors 없음 |

초기 targeted test는 Windows 기본 pytest temp root 권한 오류로 `9 succeeded, 16 setup errors`였고 repository-local `--basetemp` 재실행으로 대체했다. profile/bootstrap/CLI 최초 묶음은 isolated worktree에 `outputs/market_data.db`가 없어 collection error였고, profile/bootstrap을 분리한 뒤 CLI import에는 원본 DB 파일의 읽기 전용 환경 경로만 제공했다. DB write command는 실행하지 않았다.

전수 direct-reference 묶음의 14 failures는 중앙 resolver/guard assertion failure가 아니었다. 분류는 daily-plan fixture의 `initial_cash` 누락 1건, SAFE1/PAPER15/smoke의 snapshot/path/lifecycle fixture 불일치 5건, `enforce_asof_contract` mock signature 불일치 1건, worktree-relative legacy backup directory fixture 불일치 7건이다. Base SHA clean worktree에서도 동일한 14 node ID와 같은 failure family가 재현되었다. 각 항목은 Review Evidence에 기록했다. 테스트가 만든 임시 output directories는 제거했으며 보호 대상 `outputs/backtest_log.db`의 working/HEAD blob은 모두 `4257291614663b6d167ec081f4691b393800c720`로 동일했다.

## Tests not run

- actual Notion write/API: 작업 금지이며 ACCT-01C/B의 외부 integration 범위다.
- actual Paper operating state mutation 및 full operational smoke: 작업 금지이며 ACCT-01D 범위다.
- broker/order: 작업 금지다.
- production DB migration/read-write validation: schema/data 변경 범위가 아니며 금지다.
- `outputs/paper_test` migration: 명시적으로 금지됐다.
- 전체 pytest/backtest/optimizer: account/path 계약의 직접 영향 테스트만 수행했고 전략/수치 로직을 변경하지 않았다.

## Known risks

- ACCT-01B 전에는 omitted-account writer consumer가 새 guard 예외를 적절히 사용자 메시지로 변환하지 못할 수 있다.
- generic `create=True` callers가 canonical directories를 bootstrap 외 경로에서 계속 생성할 수 있다.
- ACCT-01C 전에는 no-context report/read/export caller가 계속 legacy singleton을 읽을 수 있다.
- Notion exporter regression에서 두 source path가 worktree-relative 문자열로 반환되어 absolute `tmp_path` 기대와 불일치했다. 이번 중앙 계약 변경 전 기준 HEAD에도 같은 serialization 코드가 있으며 C에서 검토해야 한다.
- `scripts/paper.py` plan test의 mock signature가 현재 production caller의 `enforce_asof_contract`와 맞지 않는 기준 HEAD 테스트 문제가 별도로 남아 있다.

## Known limitations

- 테스트 filesystem isolation은 실제 Paper 운영 workspace/account 간 isolation evidence를 대신하지 않는다.
- 실제 legacy data 존재 여부, migration readiness, 현재 운영 account state는 확인하지 않았다.
- frozen runbook context의 구조나 persisted schema를 변경하지 않았다.
- 이 문서는 구현 및 검사 evidence이며 최종 승인 문서가 아니다.
